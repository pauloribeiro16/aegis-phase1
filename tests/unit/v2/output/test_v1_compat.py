"""Tests for CORR-037-T4c: v1-compat shim for output consumers.

The compat shim (``aegis_phase1.v2.output._v1_compat``) provides
functions that the 10 output consumers (doc_04..07, xlsx_generator)
call once per function to obtain v1-shaped data from v2_* state keys.
The shim lives in the output package (not the orchestrator) so
consumers are explicit about their data dependencies.
"""

from __future__ import annotations

from aegis_phase1.v2.output._v1_compat import (
    get_architecture_inventory,
    get_business_goals,
    get_company_context,
    get_ontology,
    get_preprocessing,
    get_regulations,
    get_stakeholders,
)
from aegis_phase1.v2.orchestrator import Phase1Orchestrator

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def orch_with_v2(tmp_path: Path) -> Phase1Orchestrator:
    """Orchestrator with v2 loaders injected and load() run on case1."""
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

    orch = Phase1Orchestrator(
        work_dir=str(tmp_path),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    # Populate the v2_* state keys (and v1 shim keys via T4b shim)
    orch._load_v2_catalog("cases/case1-tinytask")
    return orch


# --- get_company_context -------------------------------------------------


def test_company_context_from_v2_facts(orch_with_v2: Phase1Orchestrator) -> None:
    """get_company_context reads v2_company_facts and produces a v1-shape dict."""
    state = orch_with_v2.state
    cc = get_company_context(state)
    assert cc is not None
    assert cc["company_name"] == "TinyTask Lda."
    assert cc["employees"] == 8
    assert cc["revenue"] == 2000000.0
    assert cc["scale"] == "MICRO"
    assert cc["applicable_regs"] == ["CRA", "GDPR"]
    assert cc["complexity_tier"] == "LOW"  # 8 employees < 50
    assert cc["security_fte"] == 0.85
    # tech_stack may be empty (case1's classification.yaml doesn't have it
    # populated); just verify the field exists and is a list.
    assert isinstance(cc["tech_stack"], list)


def test_company_context_complexity_tier_heuristic() -> None:
    """The complexity_tier estimate is based on employee count."""
    from aegis_phase1.v2.loader.case_profile import CompanyFacts
    from aegis_phase1.v2.output._v1_compat import _estimate_complexity_tier

    f250 = CompanyFacts(name="X", employees=250, revenue_eur=0, sector="", jurisdiction="", scale="LARGE")
    f50 = CompanyFacts(name="X", employees=50, revenue_eur=0, sector="", jurisdiction="", scale="MEDIUM")
    f10 = CompanyFacts(name="X", employees=10, revenue_eur=0, sector="", jurisdiction="", scale="MICRO")
    assert _estimate_complexity_tier(f250) == "HIGH"
    assert _estimate_complexity_tier(f50) == "MEDIUM"
    assert _estimate_complexity_tier(f10) == "LOW"


def test_company_context_no_v2_no_v1_returns_none() -> None:
    """No v2 facts and no v1 key → None."""
    state: dict = {}
    assert get_company_context(state) is None


# --- get_regulations ------------------------------------------------------


def test_regulations_from_v2_applicable(orch_with_v2: Phase1Orchestrator) -> None:
    state = orch_with_v2.state
    assert get_regulations(state) == ["CRA", "GDPR"]


def test_regulations_fallback_to_v1_key() -> None:
    """Without v2, falls back to state['regulations'] (backwards compat)."""
    state = {"regulations": ["OLD_REG"]}
    assert get_regulations(state) == ["OLD_REG"]


def test_regulations_empty_default() -> None:
    state: dict = {}
    assert get_regulations(state) == []


# --- get_ontology ---------------------------------------------------------


def test_ontology_from_v2_pairs(orch_with_v2: Phase1Orchestrator) -> None:
    state = orch_with_v2.state
    ont = get_ontology(state)
    assert ont["regulations"] == ["CRA", "GDPR"]
    assert isinstance(ont["overlaps"], list)
    assert len(ont["overlaps"]) == 196  # all v2_pairs
    assert ont["source_regulations"] == {}
    assert ont["stacks"] == []


def test_ontology_empty_default() -> None:
    state: dict = {}
    ont = get_ontology(state)
    assert ont["regulations"] == []
    assert ont["overlaps"] == []


# --- get_architecture_inventory ------------------------------------------


def test_architecture_inventory_v1_buckets(orch_with_v2: Phase1Orchestrator) -> None:
    state = orch_with_v2.state
    inv = get_architecture_inventory(state)
    assert "N.1_systems" in inv
    assert "N.2_auth" in inv
    assert "N.3_cloud" in inv
    assert "N.4_data_flows" in inv
    assert "N.5_data_stores" in inv
    assert "N.6_other" in inv
    assert len(inv["N.1_systems"]) == 5
    assert len(inv["N.2_auth"]) == 3


def test_architecture_inventory_empty_default() -> None:
    state: dict = {}
    inv = get_architecture_inventory(state)
    assert inv == {}


# --- get_stakeholders + get_business_goals --------------------------------


def test_stakeholders_from_v2_profile(orch_with_v2: Phase1Orchestrator) -> None:
    state = orch_with_v2.state
    shs = get_stakeholders(state)
    assert len(shs) == 7
    assert shs[0]["id"] == "SH-01"


def test_business_goals_from_v2_profile(orch_with_v2: Phase1Orchestrator) -> None:
    state = orch_with_v2.state
    goals = get_business_goals(state)
    assert len(goals) == 5
    assert goals[0]["id"] == "BG-01"


def test_stakeholders_empty_default() -> None:
    state: dict = {}
    assert get_stakeholders(state) == []
    assert get_business_goals(state) == []


# --- get_preprocessing ---------------------------------------------------


def test_preprocessing_from_v2_pairs(orch_with_v2: Phase1Orchestrator) -> None:
    state = orch_with_v2.state
    pp = get_preprocessing(state)
    assert "cross_regulation" in pp
    assert len(pp["cross_regulation"]) == 196
    assert pp["audit_both_pass"] is True


def test_preprocessing_empty_default() -> None:
    state: dict = {}
    pp = get_preprocessing(state)
    assert pp["cross_regulation"] == []
    assert pp["audit_both_pass"] is False
