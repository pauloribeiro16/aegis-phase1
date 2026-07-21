"""Tests for CORR-037-T4b: orchestrator v1 state keys shim.

The shim (``_populate_v1_state_keys_from_v2``) populates the legacy
v1 state keys (company_context, ontology, architecture_inventory,
business_goals, stakeholders, regulations, subdomains, preprocessing)
from the v2_* keys, so the 8 output consumers (doc_04/05/06/07 + xlsx)
continue to work after the v1 loaders are removed in T4.

Future T4c will migrate consumers to read v2_* keys directly and drop
the shim.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator


@pytest.fixture
def tmp_work_dir() -> Path:
    with tempfile.TemporaryDirectory(prefix="aegis-test-orch-t4b-") as d:
        yield Path(d)


def test_shim_populates_company_context(tmp_work_dir: Path) -> None:
    """v1 state['company_context'] is built from v2_company_facts."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    # The shim is called inside _load_v2_catalog
    assert "company_context" in orch.state
    cc = orch.state["company_context"]
    assert cc["company_name"] == "TinyTask Lda."
    assert cc["employees"] == 8
    assert cc["revenue"] == 2000000.0
    assert cc["scale"] == "MICRO"
    assert cc["applicable_regs"] == ["CRA", "GDPR"]
    assert cc["complexity_tier"] == "LOW"  # 8 employees < 50


def test_shim_populates_ontology(tmp_work_dir: Path) -> None:
    """v1 state['ontology'] is derived from v2_pairs + v2_applicable_regs."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    ont = orch.state["ontology"]
    assert ont["regulations"] == ["CRA", "GDPR"]
    assert isinstance(ont["overlaps"], list)
    assert len(ont["overlaps"]) == 196  # all pairs


def test_shim_populates_preprocessing(tmp_work_dir: Path) -> None:
    """v1 state['preprocessing'] is derived from v2_pairs + audit."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    pp = orch.state["preprocessing"]
    assert "cross_regulation" in pp
    assert pp["audit_both_pass"] is True
    assert len(pp["cross_regulation"]) == 196


def test_shim_populates_stakeholders_business_goals(tmp_work_dir: Path) -> None:
    """v1 state['stakeholders'] + state['business_goals'] from case_profile."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    assert len(orch.state["stakeholders"]) == 7
    assert len(orch.state["business_goals"]) == 5


def test_shim_populates_architecture_inventory(tmp_work_dir: Path) -> None:
    """v1 state['architecture_inventory'] keyed by v1 N.*_.* buckets."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    inv = orch.state["architecture_inventory"]
    # v1 used N.1-N.6 buckets
    assert "N.1_systems" in inv
    assert "N.2_auth" in inv
    assert "N.3_cloud" in inv
    assert "N.4_data_flows" in inv
    assert "N.5_data_stores" in inv
    assert len(inv["N.1_systems"]) == 5
    assert len(inv["N.2_auth"]) == 3


def test_shim_no_op_without_v2_loaders(tmp_work_dir: Path) -> None:
    """Without any v2 loaders injected, the shim is a no-op.

    Note: the state already has v1 keys initialized to default empty
    values by ``_init_state()``. The shim only populates them with
    real data when v2 loaders are injected. The test asserts the
    keys remain at their default empty values (not enriched by the
    shim).
    """
    orch = Phase1Orchestrator(work_dir=str(tmp_work_dir))
    orch._load_v2_catalog("cases/case1-tinytask")
    # V1 keys exist in state but are empty (default init values, not shim output)
    assert orch.state.get("company_context") is None
    assert orch.state.get("ontology") in (None, {}, "")
    assert orch.state.get("stakeholders") == [] or orch.state.get("stakeholders") is None
    # No v2_* keys either (the v2 catalog wasn't loaded)
    assert "v2_company_profile" not in orch.state
    assert "v2_subdomains" not in orch.state


def test_shim_preserves_existing_v1_keys(tmp_work_dir: Path) -> None:
    """If v1 keys are already set, the shim does not overwrite them."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    # Pre-populate v1 state key
    orch.state["company_context"] = {"sentinel": "PRESET"}
    orch._load_v2_catalog("cases/case1-tinytask")
    # The shim must NOT overwrite the pre-existing v1 key
    assert orch.state["company_context"] == {"sentinel": "PRESET"}


def test_shim_is_idempotent(tmp_work_dir: Path) -> None:
    """Calling _load_v2_catalog twice produces the same shim state."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    cc1 = orch.state["company_context"]
    ont1 = orch.state["ontology"]
    orch._load_v2_catalog("cases/case1-tinytask")
    cc2 = orch.state["company_context"]
    ont2 = orch.state["ontology"]
    # Idempotent (may have new Pydantic instances but equal content)
    assert cc1 == cc2
    assert ont1 == ont2
