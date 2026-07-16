"""Test for CORR-003 Phase A: invoker bypass fix.

Architectural bug fixed in this contract:
    ``Phase1Orchestrator._get_phase1_executor()`` constructed its own
    ``Phase1LLMInvoker`` via ``factory.get_invoker(model=OLLAMA_MODEL)``,
    ignoring ``self.llm_invoker`` (the runner-configured MockInvoker /
    UnifiedInvoker). This meant ``--model`` and ``--mock-llm`` did not
    propagate consistently between MAP-stage and REDUCE-stage LLMs.

Phase A fix:
    ``_get_phase1_executor()`` now reads ``self.llm_invoker.model`` first
    (UnifiedInvoker exposes this; MockInvoker does not), falling back to
    the env-var ``OLLAMA_MODEL`` when the configured invoker has no
    ``.model`` attribute. MOCK_LLM is still respected by the existing
    guard at the top of ``_get_phase1_executor``.
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


def _seed_minimal_reduce_state(orch) -> None:
    """Seed the minimal state required by ``orch.reduce()`` to proceed.

    Avoids touching the real ``load()`` / ``map_domains()`` paths —
    we are testing ``_get_phase1_executor()`` behaviour, not full I/O.
    """
    orch.state["case_path"] = "/tmp/test"
    orch.state["company_context"] = {}
    orch.state["domain_results"] = {}
    orch.state["subdomains"] = {}
    orch.state["preprocessing"] = {"ambiguities": []}
    # Seed aggregated_data so reduce() can complete without raising
    # on missing keys (deterministic stages run before REDUCE-LLM).
    orch.state["aggregated_data"] = {
        "concatenated": {},
        "merged": {},
        "conflicts": [],
        "profile": {},
        "synthesis": None,
        "compound_events": None,
    }


def test_reduce_propagates_model_from_llm_invoker(monkeypatch):
    """REDUCE-LLM must use ``self.llm_invoker.model`` when present.

    Bug confirmation: BEFORE the fix, ``_get_phase1_executor()`` always
    passed ``os.environ['OLLAMA_MODEL']`` to ``factory.get_invoker()``,
    so a runner-configured ``--model custom:test`` was silently
    overridden for REDUCE LLMs.

    This test FAILS before the fix (env var wins) and PASSES after
    (llm_invoker.model wins).
    """
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    # Force env var to something the model from llm_invoker is NOT,
    # so the test can distinguish "env-var won" from "llm_invoker won".
    monkeypatch.setenv("OLLAMA_MODEL", "env-fallback-model")
    monkeypatch.delenv("MOCK_LLM", raising=False)

    mock_invoker = MagicMock()
    mock_invoker.model = "configured-model:99b"  # UnifiedInvoker exposes this

    orch = Phase1Orchestrator(
        work_dir=tempfile.mkdtemp(),
        llm_invoker=mock_invoker,
    )
    _seed_minimal_reduce_state(orch)

    with patch("aegis_phase1.prompts_v2.factory.get_invoker") as mock_get_invoker:
        # Return a MagicMock shaped like a Phase1LLMInvoker so
        # invoker_to_executor() can extract its loaders/loggers.
        mock_p1 = MagicMock()
        mock_p1.prompts = MagicMock()
        mock_p1.catalogs = MagicMock()
        mock_p1.validator = MagicMock()
        mock_p1.llm_logger = MagicMock()
        mock_p1.format_logger = MagicMock()
        mock_get_invoker.return_value = mock_p1

        orch.reduce()

    # get_invoker should be called exactly once (still used for full
    # Phase1LLMInvoker construction; only its model arg is now sourced
    # from self.llm_invoker.model).
    assert mock_get_invoker.call_count == 1, (
        f"Expected get_invoker called once, got {mock_get_invoker.call_count}"
    )

    # The KEY assertion: model kwarg must come from llm_invoker, NOT env.
    actual_model = mock_get_invoker.call_args.kwargs.get("model")
    assert actual_model == "configured-model:99b", (
        f"Expected model from llm_invoker ('configured-model:99b'), "
        f"got {actual_model!r}. Bug: env var OLLAMA_MODEL leaked through."
    )


def test_reduce_falls_back_to_env_var_when_llm_invoker_lacks_model(monkeypatch):
    """When llm_invoker has no .model, REDUCE-LLM uses OLLAMA_MODEL env.

    This is the existing fallback behaviour — preserved by the fix.
    MockInvoker (used in tests / MOCK_LLM mode) does not expose a
    ``.model`` attribute, so this code path is the common case in CI.
    """
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    monkeypatch.setenv("OLLAMA_MODEL", "env-only-model:7b")
    monkeypatch.delenv("MOCK_LLM", raising=False)

    # spec=[] prevents MagicMock from auto-creating .model (simulates MockInvoker).
    mock_invoker = MagicMock(spec=[])

    orch = Phase1Orchestrator(
        work_dir=tempfile.mkdtemp(),
        llm_invoker=mock_invoker,
    )
    _seed_minimal_reduce_state(orch)

    with patch("aegis_phase1.prompts_v2.factory.get_invoker") as mock_get_invoker:
        mock_p1 = MagicMock()
        mock_p1.prompts = MagicMock()
        mock_p1.catalogs = MagicMock()
        mock_p1.validator = MagicMock()
        mock_p1.llm_logger = MagicMock()
        mock_p1.format_logger = MagicMock()
        mock_get_invoker.return_value = mock_p1

        orch.reduce()

    assert mock_get_invoker.call_count == 1
    actual_model = mock_get_invoker.call_args.kwargs.get("model")
    assert actual_model == "env-only-model:7b", (
        f"Expected env-var fallback ('env-only-model:7b'), got {actual_model!r}"
    )


def test_skip_reduce_llms_still_works_after_fix():
    """``--skip-reduce-llms`` flag still short-circuits the executor path."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    mock_invoker = MagicMock()
    mock_invoker.model = "any-model:1b"

    orch = Phase1Orchestrator(
        work_dir=tempfile.mkdtemp(),
        llm_invoker=mock_invoker,
    )
    orch.set_skip_reduce_llms(True)
    _seed_minimal_reduce_state(orch)

    with patch("aegis_phase1.prompts_v2.factory.get_invoker") as mock_get_invoker:
        orch.reduce()

    # --skip-reduce-llms must cause _get_phase1_executor to return None,
    # so get_invoker is NEVER called.
    assert mock_get_invoker.call_count == 0, (
        f"Expected get_invoker NOT called under --skip-reduce-llms, "
        f"got {mock_get_invoker.call_count} calls"
    )
    assert orch._skip_reduce_llms is True