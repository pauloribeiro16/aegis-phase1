"""Tests for filter_regs."""

from __future__ import annotations

import pytest

from aegis_phase1.v2.domain.filters.regs import NoRegsForDomainError, filter_regs
from aegis_phase1.v2.state import V2State

from .conftest import make_empty_state


def test_returns_sorted_unique_regs_for_domain(mock_state: V2State) -> None:
    result = filter_regs(mock_state, "D-04")
    assert result == ["CRA", "GDPR"]


def test_domain_with_single_regulation(mock_state: V2State) -> None:
    result = filter_regs(mock_state, "D-05")
    assert result == ["GDPR"]


def test_intersects_with_applicable_regs(mock_state: V2State) -> None:
    """When a sub-domain cites NIS2 but the company is not subject, NIS2 is dropped."""
    mock_state["ontology"]["subdomains"]["covered"].append(
        {
            "id": "D-04.5",
            "domain_id": "D-04",
            "source_regulations": ["GDPR", "NIS2"],
        }
    )
    assert mock_state["company_context"] is not None
    mock_state["company_context"].applicable_regs = ["GDPR", "CRA"]

    result = filter_regs(mock_state, "D-04")
    assert "NIS2" not in result
    assert result == ["CRA", "GDPR"]


def test_returns_all_when_no_company_context(mock_state: V2State) -> None:
    mock_state["company_context"] = None

    result = filter_regs(mock_state, "D-04")
    assert result == ["CRA", "GDPR"]


def test_unknown_domain_raises_NoRegsForDomainError(mock_state: V2State) -> None:
    """CORR-102: unknown domain with no participating subdomains → raise
    NoRegsForDomainError (was: [] + ERROR log, pre-CORR-102).

    Before CORR-101, ``filter_regs`` fell back to returning the full
    ``company_context.applicable_regs`` when the ontology and
    ``state['subdomains']`` lacked source_regs for the requested
    domain. This silently included regulations that had zero
    participating subdomains in the requested domain — a correctness
    issue.

    CORR-101 (defense-in-depth) promoted this to [] + ERROR log.
    CORR-102 promotes it further to a hard exception so the loader
    failure / schema drift is investigated loudly.

    NB: the trigger condition is ``_participating_regs_in_domain``
    returning ``None`` (no data source has any subdomain for D-XX).
    When data sources exist but no subdomain carries regs, the
    function returns ``[]`` to preserve CORR-101 contract test
    expectations.
    """
    with pytest.raises(NoRegsForDomainError) as exc_info:
        filter_regs(mock_state, "D-99")
    assert exc_info.value.domain_id == "D-99"
    assert "D-99" in str(exc_info.value)


def test_empty_state_raises_NoRegsForDomainError() -> None:
    """CORR-102: empty state (no ontology, no subdomains) → raise."""
    state = make_empty_state()
    with pytest.raises(NoRegsForDomainError) as exc_info:
        filter_regs(state, "D-04")
    assert exc_info.value.domain_id == "D-04"


def test_subdomains_exist_but_no_regs_returns_empty() -> None:
    """CORR-102: data sources are populated but no subdomain carries regs → [].

    This is the case1 D-04 contract-test scenario: preproc catalogue
    has D-04.1..D-04.4 subdomains but their participating_regulations
    are empty. The contract expects [] (NOT raise). Only the
    genuinely-no-data case raises.
    """
    from aegis_phase1.models import ComplexityTier
    from aegis_phase1.v2.state import CompanyContext, SubDomainDef

    state = {
        "current_stage": "LOADED",
        "case_path": "/tmp/case",
        "preprocessing_path": "/tmp/preproc",
        "company_context": CompanyContext(
            company_name="X",
            sector="Tech",
            jurisdiction="PT",
            employees=8,
            revenue=1_000_000.0,
            scale="MICRO",
            applicable_regs=["GDPR", "CRA"],
            complexity_tier=ComplexityTier.LOW,
            security_fte=0.5,
            tech_stack=[],
        ),
        "taxonomy_entries": [],
        "ontology": {},
        "regulations": [],
        "subdomains": {
            "D-04.1": SubDomainDef(
                document_id="AEGIS-PREPROC-SD-D-04.1",
                title="t", status="DRAFT",
                section1_crda=[], section2_hso={"hl_objective": "", "per_reg_sos": [], "emergent_tensions": []},
                section3_requirements=[],
                frontmatter={"document_id": "AEGIS-PREPROC-SD-D-04.1"},
            ),
        },
        "preprocessing": {},
        "domain_results": {},
        "aggregated_data": {},
        "output_paths": {},
        "errors": [],
    }
    # No participating regs in D-04 subdomains, ontology empty, no
    # fallback path. But _participating_regs_in_domain returns an
    # empty set (not None) because the subdomains exist. So
    # filter_regs returns [] (CORR-101 contract), NOT raise.
    result = filter_regs(state, "D-04")
    assert result == []


def test_accepts_flat_subdomains_list(mock_state: V2State) -> None:
    """Fallback: ontology.subdomains may be a flat list, not {covered: [...]}."""
    mock_state["ontology"]["subdomains"] = mock_state["ontology"]["subdomains"]["covered"]

    result = filter_regs(mock_state, "D-04")
    assert result == ["CRA", "GDPR"]


def test_dedupes_repeated_regulations(mock_state: V2State) -> None:
    """Two sub-domains both cite GDPR — only one entry should be returned."""
    mock_state["ontology"]["subdomains"]["covered"][0]["source_regulations"] = ["GDPR"]
    mock_state["ontology"]["subdomains"]["covered"][1]["source_regulations"] = ["GDPR"]

    result = filter_regs(mock_state, "D-04")
    assert result.count("GDPR") == 1
