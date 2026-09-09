"""CORR-116 S2: parse-error feedback injection in the retry loop.

Before this contract, the retry loop in :func:`Phase1LLMInvoker.invoke`
was blind — when ``_attempt`` returned ``parse_status == 'PARSE_ERROR'``,
no feedback was injected and the next attempt ran with identical
inputs. At temperature 0 the three attempts produced three identical
failures and the call exited with ``PARSE_ERROR``.

The fix reuses the existing ``feedback_prompt`` / ``previous_response``
channel (the same plumbing RefGate already uses) to inject a corrective
message that names the missing structure. ``max_retries`` stays at 3.

These tests drive :func:`Phase1LLMInvoker.invoke` by patching
``_attempt`` directly with scripted return dicts — the same pattern
used by ``test_ref_gate_corr112.py``. We capture the inputs of each
attempt via a wrapper so we can assert what was injected on retry.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker
from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.ref_gate import GateResult


def _make_invoker() -> Phase1LLMInvoker:
    """Build a Phase1LLMInvoker with stubbed prompt + catalog loaders."""
    prompt_loader = MagicMock(spec=PromptLoader)
    prompt_loader.render.return_value = {"system": "sys-stub", "user": "user-stub"}
    prompt_loader.load.return_value = {"schema": {}}

    catalog_loader = MagicMock(spec=CatalogLoader)
    catalog_loader.load.return_value = []

    return Phase1LLMInvoker(
        prompt_loader=prompt_loader,
        catalog_loader=catalog_loader,
    )


def _ok_result(raw: str = "ok") -> dict[str, Any]:
    return {
        "ok": True,
        "parse_status": "PARSED",
        "parsed_output": {"echo": raw},
        "validation": {"valid": True, "warnings": []},
        "gate_result": GateResult(valid=True, violations=[]),
        "raw_response": raw,
        "latency_ms": 1.0,
        "usage": {},
    }


def _parse_error_result(
    err: str = "no `##` headers found in markdown",
    raw: str = "no headers, just prose",
) -> dict[str, Any]:
    return {
        "ok": False,
        "parse_status": "PARSE_ERROR",
        "parsed_output": None,
        "validation": None,
        "gate_result": None,
        "raw_response": raw,
        "latency_ms": 1.0,
        "error": err,
    }


def test_parse_error_then_ok_injects_feedback_on_retry() -> None:
    """Attempt 1 returns PARSE_ERROR; attempt 2 returns OK.

    The next attempt's user prompt must contain:
      - the parser error string
      - the spec's required-structure excerpt
    """
    invoker = _make_invoker()
    err_str = "no `##` headers found in markdown"

    attempt_1 = _parse_error_result(err=err_str, raw="totally unstructured prose")
    attempt_2 = _ok_result(raw="## Status\n- status: OK\n- confidence: HIGH\n")

    captured: list[dict[str, Any]] = []
    original_attempt = invoker._attempt

    def _spy(**kwargs: Any) -> dict[str, Any]:
        captured.append({"inputs": dict(kwargs.get("inputs") or {})})
        if len(captured) == 1:
            return attempt_1
        return attempt_2

    invoker._attempt = _spy  # type: ignore[method-assign]
    try:
        result = invoker.invoke(
            "P1B-LLM-01-INTERPRETATION",
            inputs={"case_id": "case1"},
            max_retries=3,
        )
    finally:
        invoker._attempt = original_attempt  # type: ignore[method-assign]

    # 1) End-state is OK and took 2 attempts.
    assert result["status"] == "OK", f"expected OK, got {result['status']!r}"
    assert result["retry_count"] == 2, f"expected retry_count=2, got {result['retry_count']}"

    # 2) Two _attempt calls happened.
    assert len(captured) == 2, f"expected 2 attempts, got {len(captured)}"

    # 3) Attempt 1 had no feedback channel populated (first try is fresh).
    attempt1_inputs = captured[0]["inputs"]
    assert (
        "feedback_prompt" not in attempt1_inputs
    ), "attempt 1 must not have feedback_prompt — first try is fresh"
    assert (
        "previous_response" not in attempt1_inputs
    ), "attempt 1 must not have previous_response — first try is fresh"

    # 4) Attempt 2 was injected with both feedback channels.
    attempt2_inputs = captured[1]["inputs"]
    feedback_prompt = attempt2_inputs.get("feedback_prompt", "")
    previous_response = attempt2_inputs.get("previous_response", "")

    assert feedback_prompt, "attempt 2 must have feedback_prompt populated"
    assert previous_response, "attempt 2 must have previous_response populated"

    # 5) Feedback mentions the parser error string.
    assert (
        err_str in feedback_prompt
    ), f"feedback_prompt must contain parser error; got {feedback_prompt!r}"

    # 6) Feedback mentions the spec's required structure (P1B-01 has a
    #    ## Status / ## Interpretations / ## Derogations template).
    assert (
        "## Status" in feedback_prompt
    ), f"feedback_prompt must mention ## Status; got {feedback_prompt!r}"
    assert (
        "## Interpretations" in feedback_prompt
    ), f"feedback_prompt must mention ## Interpretations; got {feedback_prompt!r}"

    # 7) The previous raw response is included verbatim (truncated to 500).
    assert (
        previous_response == "totally unstructured prose"
    ), f"previous_response mismatch; got {previous_response!r}"


def test_first_try_success_does_not_inject_feedback() -> None:
    """When attempt 1 succeeds (the common case), feedback is NOT touched.

    This is the no-behaviour-change branch: the existing
    feedback_prompt/previous_response plumbing is only populated when
    an attempt fails with PARSE_ERROR. A first-try success must make
    exactly one attempt and never trigger the feedback channel.
    """
    invoker = _make_invoker()

    attempt_1 = _ok_result(raw="## Status\n- status: OK\n- confidence: HIGH\n")

    captured: list[dict[str, Any]] = []
    original_attempt = invoker._attempt

    def _spy(**kwargs: Any) -> dict[str, Any]:
        captured.append({"inputs": dict(kwargs.get("inputs") or {})})
        return attempt_1

    invoker._attempt = _spy  # type: ignore[method-assign]
    try:
        result = invoker.invoke(
            "P1B-LLM-01-INTERPRETATION",
            inputs={"case_id": "case1"},
            max_retries=3,
        )
    finally:
        invoker._attempt = original_attempt  # type: ignore[method-assign]

    # 1) One attempt only — no retry on first-try success.
    assert len(captured) == 1, f"expected 1 attempt on first-try success, got {len(captured)}"

    # 2) Result is OK.
    assert result["status"] == "OK"
    assert result["retry_count"] == 1

    # 3) The single attempt had NO feedback channel populated.
    attempt1_inputs = captured[0]["inputs"]
    assert "feedback_prompt" not in attempt1_inputs
    assert "previous_response" not in attempt1_inputs


def test_parse_error_all_attempts_exhausts_retries_with_parse_error_status() -> None:
    """MockInvoker returns non-parseable on all attempts.

    After ``max_retries=3`` the loop ends; the final status must be
    ``PARSE_ERROR`` (not the older ``FAILED_AFTER_RETRIES``), proving
    the new classifier at the bottom of :func:`invoke` is still
    effective.
    """
    invoker = _make_invoker()

    err_str = "no `##` headers found in markdown"
    bad_responses = [_parse_error_result(err=err_str, raw=f"garbage {i}") for i in range(3)]

    captured: list[dict[str, Any]] = []
    original_attempt = invoker._attempt

    def _spy(**kwargs: Any) -> dict[str, Any]:
        captured.append({"inputs": dict(kwargs.get("inputs") or {})})
        idx = len(captured) - 1
        return bad_responses[idx]

    invoker._attempt = _spy  # type: ignore[method-assign]
    try:
        result = invoker.invoke(
            "P1B-LLM-01-INTERPRETATION",
            inputs={"case_id": "case1"},
            max_retries=3,
        )
    finally:
        invoker._attempt = original_attempt  # type: ignore[method-assign]

    # 1) Three attempts were made (== max_retries).
    assert len(captured) == 3, f"expected 3 attempts, got {len(captured)}"

    # 2) Final status is PARSE_ERROR.
    assert result["status"] == "PARSE_ERROR", f"expected PARSE_ERROR, got {result['status']!r}"

    # 3) retry_count == max_retries (we exhausted retries).
    assert result["retry_count"] == 3

    # 4) Each retry beyond the first carried feedback.
    #    Attempt 1: no feedback (fresh).
    assert "feedback_prompt" not in captured[0]["inputs"]
    #    Attempt 2: feedback injected with parser error.
    assert err_str in captured[1]["inputs"].get("feedback_prompt", "")
    assert captured[1]["inputs"].get("previous_response") == "garbage 0"
    #    Attempt 3: feedback injected with parser error (from attempt 2).
    assert err_str in captured[2]["inputs"].get("feedback_prompt", "")
    assert captured[2]["inputs"].get("previous_response") == "garbage 1"
