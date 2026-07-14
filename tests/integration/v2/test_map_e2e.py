"""End-to-end integration test for the MAP stage (v2 pipeline).

Exercises the full ``Phase1Orchestrator`` in mock mode against the
canonical case (``Case_01_TinyTask_SaaS``) and the canonical
preprocessing directory (``Methodology-main/00_METHODOLOGY/PREPROCESSING``).

Three scenarios:

1. ``test_e2e_mock_mode``              — full pipeline, all 10 domains OK.
2. ``test_e2e_partial_failure_blocks_advance`` — 1 domain returns garbage;
   ``MapPartialFailure`` is raised and partial state is persisted.
3. ``test_e2e_retry_failed_recovery``  — after a partial failure, retrying
   only the failed domains recovers the pipeline.

Note: ``MapPartialFailure`` lives in ``aegis_phase1.v2.domain.processor``,
not in the orchestrator module.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegis_phase1.v2.domain.processor import MapPartialFailure
from aegis_phase1.v2.llm import MockInvoker, build_llm_invoker
from aegis_phase1.v2.orchestrator import Phase1Orchestrator
from aegis_phase1.v2.runner import DEFAULT_CASE, DEFAULT_PREPROC
from aegis_phase1.v2.state import CompanyContext

VALID_OUTPUT = (
    "ADAPTED_OBJECTIVE: Adapted objective text spanning three sentences. "
    "It references the company reality. It is bounded by proportionality.\n"
    "KEY_ADJUSTMENTS:\n"
    "- adjustment 1\n"
    "- adjustment 2\n"
    "- adjustment 3\n"
    "CONFIDENCE: HIGH"
)
INVALID_OUTPUT = "garbage no format whatsoever"

# Map index 0..9 → domain D-01..D-10; index 3 = D-04
_FAILED_INDEX = 3


# DomainProcessor retries up to 3 times per domain; provide 3 failing
# responses so the result is genuinely FAILED (not rescued by a retry).
_MAX_RETRIES = 3


def _ok_script() -> list[dict]:
    return [{"raw": VALID_OUTPUT, "status": "OK"}] * 10


def _failing_script(failed_index: int = _FAILED_INDEX) -> list[dict]:
    """Script where one domain fails all 3 retries; others succeed on attempt 1."""
    script: list[dict] = []
    for i in range(10):
        if i == failed_index:
            script.extend(
                [{"raw": INVALID_OUTPUT, "status": "OK"}] * _MAX_RETRIES
            )
        else:
            script.append({"raw": VALID_OUTPUT, "status": "OK"})
    return script


def _reload_state_from_disk(work_dir: Path, llm_invoker) -> Phase1Orchestrator:
    """Build a fresh orchestrator and rehydrate its state from ``state.json``.

    The orchestrator does not expose a ``load_from_disk`` method, so we
    manually reconstruct it. The Pydantic ``CompanyContext`` is re-instantiated
    from the dict (otherwise ``assemble_inputs`` would fail on attribute
    access).
    """
    orch = Phase1Orchestrator(work_dir=str(work_dir), llm_invoker=llm_invoker)
    state_path = work_dir / "state.json"
    saved = json.loads(state_path.read_text(encoding="utf-8"))

    cc_data = saved.get("company_context")
    if isinstance(cc_data, dict):
        saved["company_context"] = CompanyContext(**cc_data)

    orch.state.update(saved)  # type: ignore[typeddict-item]
    return orch


def test_e2e_mock_mode(tmp_path: Path) -> None:
    """Full pipeline in mock mode — all 10 domains complete OK."""
    work_dir = tmp_path / "work"

    orch = Phase1Orchestrator(
        work_dir=str(work_dir),
        llm_invoker=build_llm_invoker(),
    )

    state = orch.load(DEFAULT_CASE, DEFAULT_PREPROC)
    assert state["current_stage"] == "LOADED"
    assert len(state["subdomains"]) == 38
    assert state["company_context"] is not None

    state = orch.map_domains()
    assert state["current_stage"] == "MAPPED"
    assert len(state["domain_results"]) == 10
    assert all(
        r["llm_status"] == "OK" for r in state["domain_results"].values()
    ), "All 10 domains should be OK in mock mode"


def test_e2e_partial_failure_blocks_advance(tmp_path: Path) -> None:
    """If any domain returns unparseable output, MapPartialFailure is raised.

    Partial state (with the FAILED domain) is persisted to ``state.json``
    before the exception propagates, so the operator can inspect it and
    trigger a retry.
    """
    work_dir = tmp_path / "work"
    orch = Phase1Orchestrator(
        work_dir=str(work_dir),
        llm_invoker=MockInvoker(script=_failing_script()),
    )
    orch.load(DEFAULT_CASE, DEFAULT_PREPROC)

    with pytest.raises(MapPartialFailure) as exc_info:
        orch.map_domains()

    assert "D-04" in str(exc_info.value)

    state_file = work_dir / "state.json"
    assert state_file.exists(), "state.json must be persisted even on partial failure"

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert "D-04" in saved["domain_results"]
    assert saved["domain_results"]["D-04"]["llm_status"] == "FAILED"

    failed_ids = [
        did for did, r in saved["domain_results"].items()
        if r["llm_status"] == "FAILED"
    ]
    assert failed_ids == ["D-04"], "Only D-04 should have failed in this script"


def test_e2e_retry_failed_recovery(tmp_path: Path) -> None:
    """After a partial failure, retrying only D-04 recovers the pipeline.

    Sequence:
        1. First run with a failing script → MapPartialFailure, D-04 FAILED.
        2. Build a fresh orchestrator with a healthy mock, reload state from
           disk (re-instantiating ``CompanyContext``), then call
           ``retry_failed(["D-04"])``.
        3. D-04 now has ``llm_status=OK``; all other domains are unchanged.
    """
    work_dir = tmp_path / "work"

    # ── 1. First run: D-04 fails ──────────────────────────────────────
    orch = Phase1Orchestrator(
        work_dir=str(work_dir),
        llm_invoker=MockInvoker(script=_failing_script()),
    )
    orch.load(DEFAULT_CASE, DEFAULT_PREPROC)

    with pytest.raises(MapPartialFailure):
        orch.map_domains()

    # ── 2. Reload from disk with a fresh invoker ───────────────────────
    fixed_script = [{"raw": VALID_OUTPUT, "status": "OK"}]
    new_invoker = MockInvoker(script=fixed_script)
    orch2 = _reload_state_from_disk(work_dir, new_invoker)

    # Sanity: other domains are still OK from the first run
    for did in ("D-01", "D-02", "D-03", "D-05", "D-06", "D-07", "D-08", "D-09", "D-10"):
        assert orch2.state["domain_results"][did]["llm_status"] == "OK"
    assert orch2.state["domain_results"]["D-04"]["llm_status"] == "FAILED"

    # ── 3. Retry only D-04 ─────────────────────────────────────────────
    orch2.retry_failed(["D-04"])

    assert orch2.state["domain_results"]["D-04"]["llm_status"] == "OK"
    # All 10 domains OK after recovery
    assert all(
        r["llm_status"] == "OK" for r in orch2.state["domain_results"].values()
    )
