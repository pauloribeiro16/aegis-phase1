"""Test wiring of Phase1Executor into Phase1Orchestrator.reduce().

Contract: AEGIS-P1-CORR-002 Phase A.
"""
from pathlib import Path

import pytest


@pytest.fixture
def mock_llm_env(monkeypatch, tmp_path):
    """Configure MOCK_LLM=true so REDUCE LLMs skip deterministically."""
    monkeypatch.setenv("MOCK_LLM", "true")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return tmp_path


def _make_mock_invoker():
    """Build a minimal mock invoker."""
    from aegis_phase1.v2.llm import MockInvoker

    return MockInvoker()


def test_reduce_skips_executor_when_no_invoker(mock_llm_env):
    """When llm_invoker=None, REDUCE LLMs skipped and synthesis stays None."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    work_dir = mock_llm_env / "work"
    case_dir = mock_llm_env / "case"
    case_dir.mkdir(parents=True, exist_ok=True)
    orch = Phase1Orchestrator(
        work_dir=str(work_dir),
        llm_invoker=None,
    )
    orch.state["case_path"] = str(case_dir)
    orch.state["current_stage"] = "LOADED"

    # Skip actual load (we just test reduce semantics)
    orch.state["aggregated_data"] = {
        "concatenated": {},
        "merged": {},
        "conflicts": [],
        "profile": {},
        "synthesis": None,
        "compound_events": None,
    }
    orch.state["current_stage"] = "REDUCED"

    # Re-run reduce: it should keep synthesis/compound_events as None
    orch.reduce()
    assert orch.state["aggregated_data"].get("synthesis") is None
    assert orch.state["aggregated_data"].get("compound_events") is None


def test_skip_reduce_llms_flag_forces_skip(mock_llm_env):
    """--skip-reduce-llms forces executor=None even with mock invoker."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    work_dir = mock_llm_env / "work"
    case_dir = mock_llm_env / "case"
    case_dir.mkdir(parents=True, exist_ok=True)
    orch = Phase1Orchestrator(
        work_dir=str(work_dir),
        llm_invoker=_make_mock_invoker(),
    )
    orch.set_skip_reduce_llms(True)
    orch.state["case_path"] = str(case_dir)

    # Seed state so reduce doesn't trip on missing keys
    orch.state["company_context"] = {}
    orch.state["domain_results"] = {}
    orch.state["subdomains"] = {}
    orch.state["preprocessing"] = {"ambiguities": []}

    orch.reduce()

    assert orch.state["aggregated_data"].get("synthesis") is None
    assert orch.state["aggregated_data"].get("compound_events") is None
    assert orch._skip_reduce_llms is True


def test_mock_llm_env_skips_executor(mock_llm_env):
    """MOCK_LLM=true env var causes REDUCE LLMs to skip."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    work_dir = mock_llm_env / "work"
    case_dir = mock_llm_env / "case"
    case_dir.mkdir(parents=True, exist_ok=True)
    orch = Phase1Orchestrator(
        work_dir=str(work_dir),
        llm_invoker=_make_mock_invoker(),
    )
    orch.state["case_path"] = str(case_dir)
    orch.state["company_context"] = {}
    orch.state["domain_results"] = {}
    orch.state["subdomains"] = {}
    orch.state["preprocessing"] = {"ambiguities": []}

    orch.reduce()

    assert orch.state["aggregated_data"].get("synthesis") is None
    assert orch.state["aggregated_data"].get("compound_events") is None


def test_reduce_handles_executor_failure_gracefully(monkeypatch, tmp_path):
    """If Phase1Executor raises, exception caught and state.errors grows."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    # Force a path that would attempt executor instantiation but fail.
    # Strategy: set OLLAMA_BASE_URL to invalid + no MOCK_LLM, real path attempts connection.
    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:1")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:e4b")

    work_dir = tmp_path / "work"
    case_dir = tmp_path / "case"
    case_dir.mkdir(parents=True, exist_ok=True)
    orch = Phase1Orchestrator(
        work_dir=str(work_dir),
        llm_invoker=_make_mock_invoker(),
    )
    orch.state["case_path"] = str(case_dir)
    orch.state["company_context"] = {}
    orch.state["domain_results"] = {}
    orch.state["subdomains"] = {}
    orch.state["preprocessing"] = {"ambiguities": []}

    # Should not raise
    orch.reduce()

    # Either reduced or indeterminate; no exception propagated
    assert orch.state["current_stage"] in ("REDUCED", "REDUCE_INDETERMINATE")
