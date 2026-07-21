"""CORR-039-T6 Block 4: P1B-LLM-01 integration tests (with MockInvoker).

Verifies the wiring in run_p1b_single (T4):
  - catalog filtering via self.catalog_loader
  - clause_mapping_context as the coverage_matrix_row source
  - per_reg iteration works with a stub executor
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_orchestrator_with_loaders(work_dir: str):
    """Create a Phase1Orchestrator with all 3 loaders + state populated."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    o = Phase1Orchestrator(
        work_dir=work_dir,
        preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
        catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
    )
    o._load_v2_catalog("cases/case1-tinytask")
    return o


def test_filtered_catalogs_for_gdpr_returns_tipo2_and_tipo3() -> None:
    """_load_filtered_catalogs_for_reg('GDPR') returns 1 tipo2 + 1 tipo3 entry."""
    with tempfile.TemporaryDirectory() as d:
        o = _make_orchestrator_with_loaders(d)
        cc = o.state.get("company_context") or {}
        fcats = o._load_filtered_catalogs_for_reg("GDPR", cc)
    assert isinstance(fcats, dict)
    assert "tipo2" in fcats
    assert "tipo3" in fcats
    # case1 has 1 GDPR-applicable tipo2 + 1 GDPR-applicable tipo3
    assert len(fcats["tipo2"]) >= 1
    assert len(fcats["tipo3"]) >= 1
    # The first GDPR tipo2 should be TIPO2-GDPR-RTS-DEADLINES (or similar GDPR entry)
    assert any("GDPR" in e.get("applies_to", []) for e in fcats["tipo2"])
    assert any("GDPR" in e.get("applies_to", []) for e in fcats["tipo3"])


def test_filtered_catalogs_for_cra_returns_cra_only() -> None:
    """_load_filtered_catalogs_for_reg('CRA') returns CRA-applicable entries only."""
    with tempfile.TemporaryDirectory() as d:
        o = _make_orchestrator_with_loaders(d)
        cc = o.state.get("company_context") or {}
        fcats = o._load_filtered_catalogs_for_reg("CRA", cc)
    for entry in fcats["tipo2"]:
        assert "CRA" in entry.get("applies_to", [])
    for entry in fcats["tipo3"]:
        assert "CRA" in entry.get("applies_to", [])


def test_filtered_catalogs_for_reg_not_in_catalog_returns_empty() -> None:
    """_load_filtered_catalogs_for_reg('NOT_A_REAL_REG') returns empty (catalog has no such reg)."""
    with tempfile.TemporaryDirectory() as d:
        o = _make_orchestrator_with_loaders(d)
        cc = o.state.get("company_context") or {}
        fcats = o._load_filtered_catalogs_for_reg("NOT_A_REAL_REG", cc)
    # The filter is by catalog content, not by company applicability.
    # A reg with no entries in tipo2/tipo3 → empty result.
    assert fcats["tipo2"] == []
    assert fcats["tipo3"] == []


def test_filtered_catalogs_tipo3_has_predicate_verdict() -> None:
    """tipo3 entries are enriched with predicate_verdict (True/False/None)."""
    with tempfile.TemporaryDirectory() as d:
        o = _make_orchestrator_with_loaders(d)
        cc = o.state.get("company_context") or {}
        fcats = o._load_filtered_catalogs_for_reg("GDPR", cc)
    for entry in fcats["tipo3"]:
        assert "predicate_verdict" in entry, (
            f"tipo3 entry {entry.get('entry_id')} missing predicate_verdict"
        )
        assert entry["predicate_verdict"] in (True, False, None)


def test_run_p1b_single_passes_layer0_catalog_to_executor() -> None:
    """run_p1b_single includes layer0_catalog={tipo2: [...], tipo3: [...]} in executor call."""
    from aegis_phase1.v2.llm import MockInvoker

    with tempfile.TemporaryDirectory() as d:
        o = _make_orchestrator_with_loaders(d)
        o.llm_invoker = MockInvoker()
        # Mock the executor to capture the inputs
        captured = {}

        def fake_run_phase_1b(*args, **kwargs):
            captured.update(kwargs)
            return {
                "per_reg": {},
                "aggregated_interpretations": [],
                "aggregated_derogations": [],
                "aggregated_synthesis": {"GDPR": {"synth": "ok"}},
                "status": "OK",
            }

        with patch.object(o, "_get_phase1_executor") as mock_exc:
            mock_exc.return_value = MagicMock()
            mock_exc.return_value.run_phase_1b.side_effect = fake_run_phase_1b
            result = o.run_p1b_single("P1B-LLM-01-INTERPRETATION", "GDPR")
        # Verify layer0_catalog was passed
        assert "layer0_catalog" in captured, "layer0_catalog not passed to executor"
        assert isinstance(captured["layer0_catalog"], dict)
        assert "tipo2" in captured["layer0_catalog"]
        assert "tipo3" in captured["layer0_catalog"]
        # Verify coverage_matrix_row comes from clause_mapping_context (not empty)
        assert "coverage_matrix_row" in captured
        assert len(captured["coverage_matrix_row"]) > 0, (
            "coverage_matrix_row should be populated from ClauseMappingContext"
        )
        # Verify the call returned the per-reg synthesis
        assert result == {"synth": "ok"}


def test_run_p1b_single_returns_none_when_no_executor() -> None:
    """run_p1b_single returns None when _get_phase1_executor returns None."""
    with tempfile.TemporaryDirectory() as d:
        o = _make_orchestrator_with_loaders(d)
        # Force _get_phase1_executor to return None
        with patch.object(o, "_get_phase1_executor", return_value=None):
            result = o.run_p1b_single("P1B-LLM-01-INTERPRETATION", "GDPR")
        assert result is None
