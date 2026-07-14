"""Tests for filter_regs."""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.regs import filter_regs
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
    mock_state["company_context"].applicable_regs = ["GDPR", "CRA"]

    result = filter_regs(mock_state, "D-04")
    assert "NIS2" not in result
    assert result == ["CRA", "GDPR"]


def test_returns_all_when_no_company_context(mock_state: V2State) -> None:
    mock_state["company_context"] = None

    result = filter_regs(mock_state, "D-04")
    assert result == ["CRA", "GDPR"]


def test_returns_empty_for_unknown_domain(mock_state: V2State) -> None:
    assert filter_regs(mock_state, "D-99") == []


def test_returns_empty_when_ontology_missing() -> None:
    state = make_empty_state()
    assert filter_regs(state, "D-04") == []


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