"""CORR-054 tests: log the full prompts (system + user) sent to the LLM.

Pre-CORR-054, the JSONL log only recorded ``system_prompt_length`` and
``user_prompt_length``. The actual content the model saw was invisible
to the user — impossible to debug instructions the model may have
ignored, impossible to spot a missing catalog merge, impossible to
reproduce a hallucination. This file pins the new contract:

  * Every ``llm_call`` event carries ``request.system_prompt`` and
    ``request.user_prompt`` (full content, no truncation).
  * Every ``format_error`` event carries the same two fields.
  * Every ``markdown_parse_error`` event carries the same two fields.
  * Every ``python_error`` event carries the same two fields (even
    when the failure was in ``llm.invoke(...)`` before we ever saw a
    response, or in the prompt-render step before the call).
  * The legacy ``system_prompt_length`` / ``user_prompt_length`` keys
    are kept for backward-compat with grep-based tooling.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _make_invoker():
    """Build a Phase1LLMInvoker with real PromptLoader + mock loggers."""
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker
    from aegis_phase1.prompts_v2.loader import PromptLoader
    from aegis_phase1.prompts_v2.logging_helper import JSONLLogger

    prompt_loader = PromptLoader(root=get_prompts_root())
    # CORR-042: P1B-LLM-01 needs tipo2 + tipo3 catalogs. Provide a
    # mock that returns a minimal list for each. The exact content
    # doesn't matter for this test — we only care that the prompt
    # lands in the JSONL log verbatim.
    catalog_loader = MagicMock()
    catalog_loader.load.return_value = [{"id": "test-catalog-entry"}]
    return Phase1LLMInvoker(
        prompt_loader=prompt_loader,
        catalog_loader=catalog_loader,
        llm_logger=MagicMock(spec=JSONLLogger),
        format_logger=MagicMock(spec=JSONLLogger),
        model="gemma4:e2b",
        base_url="http://localhost:11434",
    )


def _captured_llm_call_event(invoker) -> dict:
    """Find the llm_call event in the llm_logger's .log() call_args_list."""
    for call in invoker.llm_logger.log.call_args_list:
        event = call.args[0]
        if event.get("event") == "llm_call":
            return event
    raise AssertionError("No llm_call event was logged")


# ──────────────────────────────────────────────────────────────────
# (a) Success path: llm_call event has full prompts
# ──────────────────────────────────────────────────────────────────


def test_llm_call_event_includes_full_system_and_user_prompts() -> None:
    """(a) The llm_call event's request block must contain the FULL
    system_prompt and user_prompt that were sent to Ollama — not just
    their lengths.
    """
    invoker = _make_invoker()

    with patch("aegis_phase1.prompts_v2.invoker.probe_ollama", return_value=True):
        with patch("aegis_phase1.prompts_v2.invoker.ChatOllama") as mock_chat:
            llm_inst = MagicMock()
            llm_inst.invoke.return_value = MagicMock(
                content=json.dumps(
                    {
                        "prompt_spec_id": "P1B-LLM-01-INTERPRETATION",
                        "case_id": "case1-tinytask",
                        "regulation": "GDPR",
                        "interpretations": [],
                    }
                )
            )
            mock_chat.return_value = llm_inst

            invoker.invoke(
                "P1B-LLM-01-INTERPRETATION",
                inputs={"case_id": "case1-tinytask", "regulation": "GDPR"},
                max_retries=1,
            )

    # ── Inspect the captured prompts (what was sent to Ollama) ──
    msgs = llm_inst.invoke.call_args.args[0]
    sys_msg = next(m for m in msgs if not m.content.startswith("# INPUTS"))
    user_msg = next(m for m in msgs if "INPUTS" in m.content)
    expected_system = sys_msg.content
    expected_user = user_msg.content

    # ── Inspect the logged event ──
    event = _captured_llm_call_event(invoker)
    request = event["request"]

    assert "system_prompt" in request, (
        "CORR-054: llm_call event missing request.system_prompt"
    )
    assert "user_prompt" in request, (
        "CORR-054: llm_call event missing request.user_prompt"
    )
    assert request["system_prompt"] == expected_system, (
        "CORR-054: logged system_prompt does not match the one sent to Ollama"
    )
    assert request["user_prompt"] == expected_user, (
        "CORR-054: logged user_prompt does not match the one sent to Ollama"
    )

    # Backward-compat: lengths still present.
    assert request["system_prompt_length"] == len(expected_system)
    assert request["user_prompt_length"] == len(expected_user)


def test_llm_call_event_prompts_are_nonempty_for_real_spec() -> None:
    """(a2) The logged prompts are non-empty and > 100 bytes (regression
    guard: a previous bug could log an empty string).
    """
    invoker = _make_invoker()

    with patch("aegis_phase1.prompts_v2.invoker.probe_ollama", return_value=True):
        with patch("aegis_phase1.prompts_v2.invoker.ChatOllama") as mock_chat:
            llm_inst = MagicMock()
            llm_inst.invoke.return_value = MagicMock(
                content=json.dumps(
                    {
                        "prompt_spec_id": "P1B-LLM-01-INTERPRETATION",
                        "case_id": "case1-tinytask",
                        "regulation": "GDPR",
                        "interpretations": [],
                    }
                )
            )
            mock_chat.return_value = llm_inst

            invoker.invoke(
                "P1B-LLM-01-INTERPRETATION",
                inputs={"case_id": "case1-tinytask", "regulation": "GDPR"},
                max_retries=1,
            )

    event = _captured_llm_call_event(invoker)
    request = event["request"]

    # Real prompt is multi-KB (system) and contains the inputs JSON (user).
    assert len(request["system_prompt"]) > 1000, (
        f"system_prompt suspiciously small: {len(request['system_prompt'])} bytes"
    )
    assert "case1-tinytask" in request["user_prompt"], (
        "user_prompt should contain the case_id from inputs"
    )
    assert "GDPR" in request["user_prompt"], (
        "user_prompt should contain the regulation from inputs"
    )


# ──────────────────────────────────────────────────────────────────
# (b) format_error path: prompts also logged
# ──────────────────────────────────────────────────────────────────


def test_format_error_event_includes_full_prompts() -> None:
    """(b) When RobustParser fails, the format_error event must also
    carry the prompts so the user can correlate the parse failure
    with the exact request the model saw.

    Uses P1B-LLM-02-RATIONALE (legacy JSON Schema path) instead of
    P1B-LLM-01 because P1B-LLM-01 is now handled by MarkdownParser
    (post-CORR-050) and never reaches RobustParser.
    """
    invoker = _make_invoker()

    with patch("aegis_phase1.prompts_v2.invoker.probe_ollama", return_value=True):
        with patch("aegis_phase1.prompts_v2.invoker.ChatOllama") as mock_chat:
            llm_inst = MagicMock()
            # Return an empty string — RobustParser's pre-check at the
            # top returns ok=False immediately for empty input (before
            # any strategy is tried), which is the only reliable way
            # to trigger the format_error path (the strategies list
            # has a final ``construct_minimal_object`` fallback that
            # always succeeds on non-empty input).
            llm_inst.invoke.return_value = MagicMock(content="")
            mock_chat.return_value = llm_inst

            result = invoker.invoke(
                "P1B-LLM-02-RATIONALE",
                inputs={"case_id": "case1-tinytask", "regulation": "GDPR"},
                max_retries=1,
            )

    assert result["status"] in ("PARSE_ERROR", "SCHEMA_ERROR", "FAILED_AFTER_RETRIES")

    # format_logger was called
    assert invoker.format_logger.log.called, "format_logger was never called"

    # Find the format_error event
    format_events = [
        c.args[0]
        for c in invoker.format_logger.log.call_args_list
        if c.args[0].get("event") == "format_error"
    ]
    assert format_events, "No format_error event was logged"
    fmt = format_events[0]
    assert "request" in fmt, "format_error event missing request block"
    req = fmt["request"]
    assert "system_prompt" in req, "format_error missing system_prompt"
    assert "user_prompt" in req, "format_error missing user_prompt"
    assert len(req["system_prompt"]) > 1000
    assert "case1-tinytask" in req["user_prompt"]


# ──────────────────────────────────────────────────────────────────
# (c) python_error path: prompts also logged
# ──────────────────────────────────────────────────────────────────


def test_python_error_event_includes_full_prompts() -> None:
    """(c) When the LLM call itself raises (timeout, connection refused,
    etc.), the python_error event must carry the prompts — otherwise
    the user has no way to reproduce the failure.
    """
    invoker = _make_invoker()

    with patch("aegis_phase1.prompts_v2.invoker.probe_ollama", return_value=True):
        with patch("aegis_phase1.prompts_v2.invoker.ChatOllama") as mock_chat:
            llm_inst = MagicMock()
            llm_inst.invoke.side_effect = ConnectionError("ollama down")
            mock_chat.return_value = llm_inst

            result = invoker.invoke(
                "P1B-LLM-02-RATIONALE",
                inputs={"case_id": "case1-tinytask", "regulation": "GDPR"},
                max_retries=1,
            )

    assert result["status"] == "FAILED_AFTER_RETRIES"

    # Find the python_error event in llm_logger
    py_events = [
        c.args[0]
        for c in invoker.llm_logger.log.call_args_list
        if c.args[0].get("event") == "python_error"
    ]
    assert py_events, "No python_error event was logged"
    py = py_events[0]
    assert "request" in py, "python_error event missing request block"
    req = py["request"]
    assert "system_prompt" in req
    assert "user_prompt" in req
    assert len(req["system_prompt"]) > 1000
    assert "case1-tinytask" in req["user_prompt"]
