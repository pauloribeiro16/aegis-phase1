"""Unit tests for the Phase 3 deterministic/enhanced decoupling.

Sprint Phase 3 decouple: ``generate_outputs`` was split into
``generate_deterministic_docs`` (always safe to run) and
``generate_enhanced_docs`` (skipped when ``MAP_FAILED``).

The deterministic half must:

1. Produce 5 deterministic artefacts (04 body, 05, 06, 07, 07b)
   plus the xlsx, even when MAP has not run.
2. Run successfully when ``current_stage`` is ``MAP_FAILED`` (since
   they only depend on LOAD-stage data and deterministic fallbacks).

The enhanced half must:

1. Return the state unchanged (with a warning) when ``current_stage``
   is ``MAP_FAILED``.

These tests deliberately avoid I/O where possible and focus on the
state machine contract. The end-to-end artefact counts are validated
in the integration suite (``test_runner_cli.py``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aegis_phase1.v2.orchestrator import Phase1Orchestrator
from aegis_phase1.v2.runner import DEFAULT_CASE, DEFAULT_PREPROC


def _build_minimal_state() -> dict[str, Any]:
    """Return a minimal V2State dict sufficient for deterministic renderers.

    The renderers are defensive — they fall back to deterministic
    baselines when fields are missing — so an essentially-empty state
    is enough to exercise the contract.
    """
    return {
        "current_stage": "LOADED",
        "case_path": "case1-tinytask",
        "preprocessing_path": "",
        "regulatory_baseline_path": "",
        "company_context": None,
        "architecture_inventory": {},
        "stakeholders": [],
        "business_goals": [],
        "taxonomy_entries": [],
        "ontology": {},
        "regulations": [],
        "subdomains": {},
        "preprocessing": {},
        "domain_results": {},
        "aggregated_data": {},
        "output_paths": {},
        "errors": [],
    }


def test_generate_deterministic_docs_runs_without_map(tmp_path: Path) -> None:
    """``generate_deterministic_docs`` produces the 5 deterministic docs without MAP."""
    work_dir = tmp_path / "work"
    orch = Phase1Orchestrator(work_dir=str(work_dir), llm_invoker=None)
    orch.state.update(_build_minimal_state())

    orch.generate_deterministic_docs(output_dir=str(tmp_path))
    paths = orch.state.get("output_paths") or {}

    # The dict should contain at least the 5 deterministic doc keys.
    assert isinstance(paths, dict)
    assert "AEGIS-P1-04" in paths, f"Missing 04 body in {sorted(paths)}"
    assert "AEGIS-P1-05" in paths
    assert "AEGIS-P1-06" in paths
    assert "AEGIS-P1-07" in paths
    assert "AEGIS-P1-07b" in paths

    # Each path should point to an actual file on disk.
    for label, p in paths.items():
        if label == "AEGIS-P1-XLSX":
            continue
        assert Path(p).exists(), f"{label} -> {p} does not exist"


def test_generate_deterministic_docs_after_map_failed(tmp_path: Path) -> None:
    """Deterministic docs still run when ``current_stage`` is ``MAP_FAILED``."""
    work_dir = tmp_path / "work"
    orch = Phase1Orchestrator(work_dir=str(work_dir), llm_invoker=None)
    orch.state.update(_build_minimal_state())
    orch.state["current_stage"] = "MAP_FAILED"

    orch.generate_deterministic_docs(output_dir=str(tmp_path))
    paths = orch.state.get("output_paths") or {}

    assert "AEGIS-P1-04" in paths
    assert "AEGIS-P1-05" in paths
    # current_stage must be updated to the deterministic completion marker
    assert orch.state["current_stage"] == "OUTPUT_DONE_DETERMINISTIC"


def test_generate_enhanced_docs_skips_when_map_failed(tmp_path: Path) -> None:
    """``generate_enhanced_docs`` is a no-op (returns state unchanged) on ``MAP_FAILED``."""
    work_dir = tmp_path / "work"
    orch = Phase1Orchestrator(work_dir=str(work_dir), llm_invoker=None)
    orch.state.update(_build_minimal_state())
    orch.state["current_stage"] = "MAP_FAILED"
    prior_stage = orch.state["current_stage"]
    prior_paths = dict(orch.state.get("output_paths") or {})

    orch.generate_enhanced_docs(output_dir=str(tmp_path))

    # Stage must not have advanced past MAP_FAILED.
    assert orch.state["current_stage"] == prior_stage
    # No new artefacts should have been added.
    assert orch.state.get("output_paths") == prior_paths


def test_generate_outputs_composite_runs_both_halves(tmp_path: Path) -> None:
    """Legacy ``generate_outputs`` runs deterministic + enhanced."""
    work_dir = tmp_path / "work"
    orch = Phase1Orchestrator(work_dir=str(work_dir), llm_invoker=None)
    orch.state.update(_build_minimal_state())

    orch.generate_outputs(output_dir=str(tmp_path))

    # Deterministic + enhanced docs should all be present.
    paths = orch.state.get("output_paths") or {}
    for key in (
        "AEGIS-P1-04",
        "AEGIS-P1-05",
        "AEGIS-P1-06",
        "AEGIS-P1-07",
        "AEGIS-P1-07b",
    ):
        assert key in paths, f"Missing {key} after composite generate_outputs"
    # Final stage marker.
    assert orch.state["current_stage"] == "OUTPUT_DONE"


def test_state_persistence_round_trip(tmp_path: Path) -> None:
    """After deterministic docs run, ``state.json`` is written and re-loadable."""
    work_dir = tmp_path / "work"
    orch = Phase1Orchestrator(work_dir=str(work_dir), llm_invoker=None)
    orch.state.update(_build_minimal_state())

    orch.generate_deterministic_docs(output_dir=str(tmp_path))

    state_file = work_dir / "state.json"
    assert state_file.exists(), "state.json must be persisted"

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["current_stage"] == "OUTPUT_DONE_DETERMINISTIC"
    assert "AEGIS-P1-04" in saved["output_paths"]


def test_cli_deterministic_only_flag_in_help() -> None:
    """Smoke: the new flag is wired into the CLI parser."""
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, "-m", "aegis_phase1.v2.runner", "--help"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
        timeout=30,
    )
    assert result.returncode == 0
    assert "--deterministic-only" in result.stdout


@pytest.mark.skipif(
    not Path(DEFAULT_CASE).exists(),
    reason="canonical case path not present",
)
def test_deterministic_end_to_end_against_case1(tmp_path: Path) -> None:
    """End-to-end smoke: load() + generate_deterministic_docs() on the canonical case.

    This is the operationally relevant scenario: after a LOAD-only run,
    the operator should still be able to produce baseline artefacts
    even before MAP is exercised.
    """
    work_dir = tmp_path / "work"
    orch = Phase1Orchestrator(work_dir=str(work_dir), llm_invoker=None)
    orch.load(DEFAULT_CASE, DEFAULT_PREPROC)
    orch.generate_deterministic_docs(output_dir=str(tmp_path))
    paths = orch.state.get("output_paths") or {}

    # 5 deterministic docs + xlsx → ≥6 entries.
    assert len(paths) >= 6, f"Expected ≥6 artefacts, got {len(paths)}: {sorted(paths)}"