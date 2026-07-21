"""Tests for CORR-037-T3a: orchestrator v2 loader opt-in wiring.

Verifies that the orchestrator's ``_load_v2_catalog`` method populates
the v2_* state keys ONLY when the typed loaders are injected via the
constructor, and is a no-op otherwise (backwards-compatible with the v1
state shape that 2076 existing tests depend on).
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
    """Provide a per-test tmp work_dir to avoid state.json collisions."""
    with tempfile.TemporaryDirectory(prefix="aegis-test-orch-t3a-") as d:
        yield Path(d)


# --- No loaders injected: backwards-compat --------------------------------


def test_no_loaders_state_keys_absent(tmp_work_dir: Path) -> None:
    """When no v2 loaders are injected, _load_v2_catalog is a no-op.

    The 7 legacy v1 state keys (company_context, etc.) are still
    populated by load(); the v2_* keys are NOT added.
    """
    orch = Phase1Orchestrator(work_dir=str(tmp_work_dir))
    orch._load_v2_catalog("cases/case1-tinytask")
    # v2_* keys should NOT exist when no loaders injected
    for key in (
        "v2_company_profile",
        "v2_company_facts",
        "v2_applicable_regs",
        "v2_subdomains",
        "v2_srs",
        "v2_sos",
        "v2_pairs",
        "v2_audit_both_pass",
    ):
        assert key not in orch.state, f"{key} should be absent when no loaders injected"


def test_no_loaders_constructor_unchanged(tmp_work_dir: Path) -> None:
    """Default constructor (no kwargs) still works — backwards compat."""
    orch = Phase1Orchestrator(work_dir=str(tmp_work_dir))
    assert orch.preproc_catalog is None
    assert orch.case_profile_loader is None


# --- With loaders: v2_* state keys populated -----------------------------


def test_with_loaders_state_keys_populated(tmp_work_dir: Path) -> None:
    """When both loaders are injected, _load_v2_catalog populates v2_* keys."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")

    # 8 v2_* keys should be present
    for key in (
        "v2_company_profile",
        "v2_company_facts",
        "v2_applicable_regs",
        "v2_declared_regs",
        "v2_obligated_party",
        "v2_subdomains",
        "v2_srs",
        "v2_sos",
        "v2_pairs",
        "v2_audit_both_pass",
    ):
        assert key in orch.state, f"{key} should be present with loaders injected"


def test_v2_company_facts_canonical(tmp_work_dir: Path) -> None:
    """v2_company_facts is CompanyFacts with post-CORR-036 canonical values."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    facts = orch.state["v2_company_facts"]
    assert facts.name == "TinyTask Lda."
    assert facts.employees == 8
    assert facts.revenue_eur == 2000000
    assert facts.scale == "MICRO"


def test_v2_applicable_regs_sorted(tmp_work_dir: Path) -> None:
    """v2_applicable_regs is sorted alphabetically per case_profile contract."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    assert orch.state["v2_applicable_regs"] == ["CRA", "GDPR"]


def test_v2_obligated_party(tmp_work_dir: Path) -> None:
    """v2_obligated_party maps reg → role (controller/manufacturer)."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    assert orch.state["v2_obligated_party"] == {
        "GDPR": "controller",
        "CRA": "manufacturer",
    }


def test_v2_subdomains_count(tmp_work_dir: Path) -> None:
    """v2_subdomains has exactly 38 entries (CORR-030 invariant)."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    assert len(orch.state["v2_subdomains"]) == 38


def test_v2_srs_count(tmp_work_dir: Path) -> None:
    """v2_srs has exactly 282 entries."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    assert len(orch.state["v2_srs"]) == 282


def test_v2_pairs_count(tmp_work_dir: Path) -> None:
    """v2_pairs has exactly 196 entries."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    assert len(orch.state["v2_pairs"]) == 196


def test_v2_audit_both_pass(tmp_work_dir: Path) -> None:
    """v2_audit_both_pass is True when CSF + SO/SR gates both pass."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    assert orch.state["v2_audit_both_pass"] is True


# --- Partial injection ---------------------------------------------------


def test_only_case_profile_injected(tmp_work_dir: Path) -> None:
    """Injecting only case_profile_loader populates v2_company_* but not v2_subdomains."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    # case_profile keys present
    assert "v2_company_facts" in orch.state
    assert "v2_applicable_regs" in orch.state
    # preproc_catalog keys absent
    assert "v2_subdomains" not in orch.state
    assert "v2_srs" not in orch.state
    assert "v2_audit_both_pass" not in orch.state


def test_only_preproc_catalog_injected(tmp_work_dir: Path) -> None:
    """Injecting only preproc_catalog populates v2_subdomains but not v2_company_*."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    # preproc_catalog keys present
    assert "v2_subdomains" in orch.state
    assert "v2_srs" in orch.state
    assert "v2_audit_both_pass" in orch.state
    # case_profile keys absent
    assert "v2_company_facts" not in orch.state
    assert "v2_applicable_regs" not in orch.state


# --- Idempotency ---------------------------------------------------------


def test_idempotent_invocation(tmp_work_dir: Path) -> None:
    """Calling _load_v2_catalog twice produces equivalent state.

    Note: the loaders themselves cache via @functools.cache, so the
    Pydantic objects are the SAME instance on repeat calls (intentional
    behaviour — see PreprocCatalogLoader/CaseProfileLoader docs).
    """
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    first_facts = orch.state["v2_company_facts"]
    first_subs_count = len(orch.state["v2_subdomains"])
    first_audit = orch.state["v2_audit_both_pass"]

    orch._load_v2_catalog("cases/case1-tinytask")
    # Same instance (loader cache) — verify identity
    assert orch.state["v2_company_facts"] is first_facts
    # Verify content unchanged
    assert len(orch.state["v2_subdomains"]) == first_subs_count == 38
    assert orch.state["v2_audit_both_pass"] is first_audit is True


# --- T3b (proper): state["subdomains"] source -------------------------------


def test_state_subdomains_from_preproc_catalog(tmp_work_dir: Path) -> None:
    """When preproc_catalog is injected, state['subdomains'] is populated
    by PreprocCatalogLoader.load_subdomains() (T3b proper).

    The state shape (dict keyed by sub-id) matches v1, so consumers
    like filter_subdomains are unaffected after T3c's shape-agnostic
    refactor.
    """
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
    )
    # We can't call full load() (requires regulatory_baseline_path);
    # but we can simulate the T3b swap logic directly.
    from aegis_phase1.v2.domain.filters.subdomains import filter_subdomains
    from aegis_phase1.v2.state import V2State

    subs_list = orch.preproc_catalog.load_subdomains()
    orch.state["subdomains"] = {s.id: s for s in subs_list}
    state: V2State = orch.state  # type: ignore[assignment]

    # filter_subdomains should now consume the v2 Pydantic Subdomain objects
    # (shape-agnostic via T3c) and return SubdomainSummary dicts.
    summaries = filter_subdomains(state, "D-01")
    assert len(summaries) == 4  # D-01.1, D-01.2, D-01.3, D-01.4
    for s in summaries:
        assert s["id"].startswith("D-01.")
        assert "title" in s
        assert "hso_hl" in s
        assert "hso_per_reg" in s


def test_state_subdomains_fallback_to_v1(tmp_work_dir: Path) -> None:
    """When no preproc_catalog is injected, _load_v2_catalog is a no-op
    and the v1 SubDomainLoader is the source of state['subdomains']
    (T3b keeps the v1 fallback for backwards compat)."""
    orch = Phase1Orchestrator(work_dir=str(tmp_work_dir))
    # Without preproc_catalog, _load_v2_catalog doesn't add v2_subdomains.
    orch._load_v2_catalog("cases/case1-tinytask")
    assert "v2_subdomains" not in orch.state
    # The orchestrator is still in a usable state (no v2_* keys, but
    # the constructor is happy with no loaders).
