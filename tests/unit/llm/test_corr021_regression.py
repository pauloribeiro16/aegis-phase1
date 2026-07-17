"""Tests for AEGIS-P1-CORR-021: langfuse callback cache + token fallback.

Reference: docs/SPEC-observability.md + regression report from real run.

Two bugs found in a real `--run-all-traced` run:

1. **Multiple traces instead of one.** Every call to ``get_langfuse_callback()``
   generated a fresh ``trace_id``. The pipeline called it 3+ times
   (orchestrator init, factory.get_invoker, output stage) → 3 disjoint
   Langfuse traces instead of one nested tree.

2. **Zero tokens in some LLM calls** (P1B-LLM-02-RATIONALE at e2b model).
   Ollama with ``format=json_schema`` constrained generation returned
   ``response_metadata={}`` for some responses (nested-JSON anomaly).
   The extraction code was correct but had no fallback.

Fixes:
- Module-level cache in ``tracing.py:get_langfuse_callback``.
- Character-based token estimate as last-resort fallback in both
  ``unified.py:_extract_usage`` and ``invoker.py:_extract_usage``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aegis_phase1.llm import tracing as tracing_mod
from aegis_phase1.llm.unified import _extract_usage as unified_extract


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    """Reset module-level cache + env between tests."""
    tracing_mod._invalidate_langfuse_cache()
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")
    yield
    tracing_mod._invalidate_langfuse_cache()


# ─── Cache: get_langfuse_callback returns SAME handler per pipeline run ────


def test_callback_cached_across_calls_same_args():
    """REGRESSION: multiple calls return the SAME handler (same trace_id)."""
    fake_client = MagicMock()
    fake_client.create_trace_id.return_value = "trace-abc-123"
    fake_handler = MagicMock()
    fake_handler.tags = []

    with patch("langfuse.Langfuse", return_value=fake_client), \
         patch("langfuse.langchain.CallbackHandler", return_value=fake_handler):
        c1, h1 = tracing_mod.get_langfuse_callback(case_name="case01", phase="phase1")
        c2, h2 = tracing_mod.get_langfuse_callback(case_name="case01", phase="phase1")
        c3, h3 = tracing_mod.get_langfuse_callback(case_name="case01", phase="phase1")

    assert c1 is c2 is c3, "client should be the same instance across calls"
    assert h1 is h2 is h3, "handler should be the same instance across calls"
    # Langfuse client should have been constructed ONCE, not three times
    assert fake_client.create_trace_id.call_count == 1, (
        "create_trace_id should be called once, not per call"
    )


def test_callback_cache_invalidated_on_args_change():
    """Different (case_name, phase) creates a new cache entry."""
    fake_client = MagicMock()
    fake_client.create_trace_id.side_effect = ["trace-1", "trace-2"]
    handler_seq = iter([MagicMock(name="h1"), MagicMock(name="h2")])

    with patch("langfuse.Langfuse", return_value=fake_client), \
         patch("langfuse.langchain.CallbackHandler", side_effect=lambda **kw: next(handler_seq)):
        _, h1 = tracing_mod.get_langfuse_callback(case_name="case01", phase="phase1")
        _, h2 = tracing_mod.get_langfuse_callback(case_name="case02", phase="phase1")

    assert h1 is not h2
    assert fake_client.create_trace_id.call_count == 2


def test_callback_disabled_returns_none():
    """LANGFUSE_ENABLED=false returns (None, None) without populating cache."""
    with patch.dict("os.environ", {"LANGFUSE_ENABLED": "false"}, clear=False):
        c, h = tracing_mod.get_langfuse_callback()
    assert c is None
    assert h is None


def test_callback_invalidate_helper_clears_cache():
    """Test helper _invalidate_langfuse_cache forces re-creation."""
    fake_client = MagicMock()
    fake_client.create_trace_id.side_effect = ["trace-1", "trace-2"]
    handler_seq = iter([MagicMock(name="h1"), MagicMock(name="h2")])

    with patch("langfuse.Langfuse", return_value=fake_client), \
         patch("langfuse.langchain.CallbackHandler", side_effect=lambda **kw: next(handler_seq)):
        _, h1 = tracing_mod.get_langfuse_callback(case_name="x")
        tracing_mod._invalidate_langfuse_cache()
        _, h2 = tracing_mod.get_langfuse_callback(case_name="x")

    assert h1 is not h2
    assert fake_client.create_trace_id.call_count == 2


# ─── Token fallback: estimate from raw content when metadata empty ─────


def test_unified_extract_usage_falls_back_to_chars_when_metadata_empty():
    """REGRESSION: P1B-LLM-02 returned response_metadata={} → 0 tokens.

    Fallback must estimate from content length (1 token ≈ 4 chars).
    """
    response = MagicMock()
    response.response_metadata = {}            # empty
    response.usage_metadata = None            # empty
    response.content = "x" * 8000              # 8000 chars → ~2000 tokens

    usage = unified_extract(response)
    assert usage["completion_tokens"] == 2000
    assert usage["total_tokens"] == 2000
    # prompt_tokens still 0 (we don't have prompt content here)
    assert usage["prompt_tokens"] == 0


def test_unified_extract_usage_uses_official_path_first():
    """When response_metadata has tokens, fallback is NOT used."""
    response = MagicMock()
    response.response_metadata = {"prompt_eval_count": 100, "eval_count": 50}
    response.usage_metadata = None
    response.content = "x" * 10000

    usage = unified_extract(response)
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 50
    assert usage["total_tokens"] == 150


def test_unified_extract_usage_handles_empty_content():
    """If both metadata AND content are empty, return zeros (mock fixture)."""
    # Use a simple object — no MagicMock repr contamination.
    class FakeResponse:
        response_metadata = {}
        usage_metadata = None
        content = ""

    usage = unified_extract(FakeResponse())
    assert usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def test_unified_extract_usage_uses_usage_metadata_fallback():
    """When response_metadata empty but usage_metadata has values, use them."""
    response = MagicMock()
    response.response_metadata = {}
    response.usage_metadata = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
    response.content = "should not be used"

    usage = unified_extract(response)
    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 20
    assert usage["total_tokens"] == 30


# ─── Houdini demo: revert the cache fix → multiple trace_ids ────────────────


def test_houdini_no_cache_means_multiple_trace_ids():
    """REGRESSION: without the cache, every call would create a new trace_id.

    Simulated by invalidating the cache between every call.
    """
    fake_client = MagicMock()
    fake_client.create_trace_id.side_effect = ["t1", "t2", "t3"]
    handler_seq = iter([MagicMock(name=f"h{i}") for i in range(3)])

    with patch("langfuse.Langfuse", return_value=fake_client), \
         patch("langfuse.langchain.CallbackHandler", side_effect=lambda **kw: next(handler_seq)):
        trace_ids = []
        for _ in range(3):
            tracing_mod._invalidate_langfuse_cache()
            _, h = tracing_mod.get_langfuse_callback(case_name="x", phase="p")
            trace_ids.append(h)
        assert trace_ids[0] is not trace_ids[1]
        assert trace_ids[1] is not trace_ids[2]
