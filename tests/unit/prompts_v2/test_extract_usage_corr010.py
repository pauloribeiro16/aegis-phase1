"""Test fix for ``_extract_usage`` tokens=0 (AEGIS-P1-CORR-010).

Reference: ``docs/SPEC-observability.md`` §6 (Phase 1, contract CORR-010).

The function under test (``Phase1LLMInvoker._extract_usage``) used to look
for OpenAI-style ``token_usage`` / ``usage`` keys inside ``response_metadata``
and call ``hasattr()`` on the ``usage_metadata`` TypedDict. Both branches
returned zeros for real Ollama responses, so 60/60 events landed on
``llm-calls.jsonl`` with ``total_tokens == 0``.

These tests verify that:

1. ``response_metadata`` with Ollama's ``prompt_eval_count`` / ``eval_count``
   is parsed correctly (primary path).
2. Missing / empty / partial ``response_metadata`` returns zeros (no raise).
3. ``usage_metadata`` with langchain-core canonical keys
   (``input_tokens`` / ``output_tokens`` / ``total_tokens``) is parsed via
   ``.get()`` (regression for bug b — the old ``hasattr`` always missed it).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker


class FakeAIMessage:
    """Minimal stand-in for ``langchain_core.messages.AIMessage``.

    Carries ``response_metadata`` and/or ``usage_metadata``. We avoid importing
    ``AIMessage`` directly so the test stays free of any real LLM call
    dependency.
    """

    def __init__(self, response_metadata=None, usage_metadata=None) -> None:
        self.response_metadata = response_metadata
        self.usage_metadata = usage_metadata


def test_extract_usage_ollama_response_metadata() -> None:
    """Primary path: Ollama top-level ``prompt_eval_count`` / ``eval_count``."""
    msg = FakeAIMessage(
        response_metadata={
            "model": "gemma4:e4b",
            "prompt_eval_count": 1234,
            "eval_count": 567,
            "done": True,
        }
    )
    usage = Phase1LLMInvoker._extract_usage(msg)
    assert usage["prompt_tokens"] == 1234
    assert usage["completion_tokens"] == 567
    assert usage["total_tokens"] == 1801


def test_extract_usage_missing_response_metadata() -> None:
    """No ``response_metadata`` attribute at all → zeros, no raise."""
    msg = MagicMock(spec=[])  # no attributes defined
    msg.response_metadata = None
    msg.usage_metadata = None
    usage = Phase1LLMInvoker._extract_usage(msg)
    assert usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def test_extract_usage_empty_response_metadata() -> None:
    """Empty ``response_metadata`` dict → zeros, no raise."""
    msg = FakeAIMessage(response_metadata={}, usage_metadata={})
    usage = Phase1LLMInvoker._extract_usage(msg)
    assert usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def test_extract_usage_partial_response_metadata() -> None:
    """Only ``model`` key in ``response_metadata`` → defaults to zero, no raise."""
    msg = FakeAIMessage(response_metadata={"model": "gemma4:e4b"})
    usage = Phase1LLMInvoker._extract_usage(msg)
    assert usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def test_extract_usage_usage_metadata_fallback() -> None:
    """langchain-core canonical fallback via ``.get()``.

    Regression for the old ``hasattr(meta, "input_tokens")`` branch which
    always returned False because ``UsageMetadata`` is a TypedDict, not an
    object with attributes.
    """
    msg = FakeAIMessage(
        usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
    )
    usage = Phase1LLMInvoker._extract_usage(msg)
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 50
    assert usage["total_tokens"] == 150