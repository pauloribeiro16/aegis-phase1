"""Tests for AEGIS-P1-CORR-016: trace_id pinning in Langfuse handler.

Reference: docs/SPEC-observability.md + Langfuse trace_id pinning pattern
(adopted from aegis-kg/core/agent/tracing.py:163-165).

The bug pre-CORR-016: `CallbackHandler()` created a SEPARATE root trace per LLM
invocation — all 13 call sites created 13 disjoint traces.

The fix: `CallbackHandler(trace_context={"trace_id": client.create_trace_id()})`
pins every span/generation to ONE root trace.

Tests use MagicMock for the Langfuse SDK (no real server, no Ollama). The trace_id
string is what we observe; we never care about the Langfuse client method semantics
beyond the return-value plumbing.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from aegis_phase1.llm.tracing import get_langfuse_callback


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")
    yield


def test_handler_carry_trace_context(monkeypatch):
    """Handler must be created with trace_context={'trace_id': client.create_trace_id()}."""
    fake_client = MagicMock()
    fake_client.create_trace_id.return_value = "test-trace-abc123"

    fake_handler = MagicMock()
    fake_handler.tags = []

    with patch("langfuse.Langfuse", return_value=fake_client) as FakeLangfuse, \
         patch("langfuse.langchain.CallbackHandler", return_value=fake_handler) as FakeHandler:
        client, handler = get_langfuse_callback(case_name="case01", phase="phase1")

    # Langfuse client was constructed with the env-derived creds
    FakeLangfuse.assert_called_once_with(
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
        host="http://localhost:3000",
    )
    fake_client.create_trace_id.assert_called_once_with()

    # ★ THE KEY ASSERTION: CallbackHandler was constructed with trace_context
    args, kwargs = FakeHandler.call_args
    assert "trace_context" in kwargs, "CallbackHandler must receive trace_context"
    assert kwargs["trace_context"] == {"trace_id": "test-trace-abc123"}
    assert client is fake_client
    assert handler is fake_handler


def test_handler_tags_attached_case_and_phase():
    """Tags ['phase:phase1', 'case:case01'] set on the handler instance."""
    fake_client = MagicMock()
    fake_client.create_trace_id.return_value = "trace-1"
    fake_handler = MagicMock()
    fake_handler.tags = []

    with patch("langfuse.Langfuse", return_value=fake_client), \
         patch("langfuse.langchain.CallbackHandler", return_value=fake_handler):
        _, handler = get_langfuse_callback(case_name="case01", phase="phase1")

    assert sorted(handler.tags) == ["case:case01", "phase:phase1"]


def test_handler_tags_omit_missing_case():
    """When case_name is empty, the case: tag is NOT added; phase: tag still is."""
    fake_client = MagicMock()
    fake_client.create_trace_id.return_value = "trace-1"
    fake_handler = MagicMock()
    fake_handler.tags = []

    with patch("langfuse.Langfuse", return_value=fake_client), \
         patch("langfuse.langchain.CallbackHandler", return_value=fake_handler):
        _, handler = get_langfuse_callback(case_name="", phase="phase1")

    assert handler.tags == ["phase:phase1"]


def test_master_switch_off_returns_none(monkeypatch):
    """LANGFUSE_ENABLED=false must short-circuit to (None, None)."""
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")

    fake_client_class = MagicMock()
    fake_handler_class = MagicMock()
    with patch("langfuse.Langfuse", fake_client_class), \
         patch("langfuse.langchain.CallbackHandler", fake_handler_class):
        client, handler = get_langfuse_callback("case01", "phase1")

    assert client is None
    assert handler is None
    fake_client_class.assert_not_called()
    fake_handler_class.assert_not_called()


def test_credentials_missing_returns_none(monkeypatch):
    """If LANGFUSE_PUBLIC_KEY or SECRET_KEY empty, return (None, None) and warn."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")

    with patch("langfuse.Langfuse") as FakeLangfuse, \
         patch("langfuse.langchain.CallbackHandler") as FakeHandler:
        client, handler = get_langfuse_callback("case01", "phase1")

    assert client is None
    assert handler is None
    FakeLangfuse.assert_not_called()
    FakeHandler.assert_not_called()


def test_default_enabled_true():
    """When LANGFUSE_ENABLED is unset, default is true (CORR-016 opt-in for downstream)."""
    monkeypatch_ = os.environ.copy()
    os.environ.pop("LANGFUSE_ENABLED", None)
    os.environ["LANGFUSE_PUBLIC_KEY"] = "pk"
    os.environ["LANGFUSE_SECRET_KEY"] = "sk"
    try:
        fake_client = MagicMock()
        fake_client.create_trace_id.return_value = "trace-default"
        fake_handler = MagicMock()
        fake_handler.tags = []

        with patch("langfuse.Langfuse", return_value=fake_client), \
             patch("langfuse.langchain.CallbackHandler", return_value=fake_handler):
            client, handler = get_langfuse_callback("c1", "p1")

        assert client is fake_client
        assert handler is fake_handler
    finally:
        os.environ.clear()
        os.environ.update(monkeypatch_)


def test_two_invocations_use_different_trace_ids_each_time():
    """Each top-level call generates a fresh trace_id (one trace per pipeline run)."""
    counter = {"n": 0}

    def next_trace():
        counter["n"] += 1
        return f"trace-{counter['n']:04d}"

    fake_client = MagicMock()
    fake_client.create_trace_id.side_effect = next_trace
    fake_handler1, fake_handler2 = MagicMock(), MagicMock()
    fake_handler1.tags = fake_handler2.tags = []
    handlers_iter = iter([fake_handler1, fake_handler2])

    with patch("langfuse.Langfuse", return_value=fake_client), \
         patch("langfuse.langchain.CallbackHandler", side_effect=lambda **kw: next(handlers_iter)):
        c1, h1 = get_langfuse_callback("case1", "phase1")
        c2, h2 = get_langfuse_callback("case2", "phase1")

    assert h1 is fake_handler1 and h2 is fake_handler2
    assert fake_client.create_trace_id.call_count == 2
    # But within ONE pipeline run (one get_langfuse_callback call),
    # multiple LLM invokes would share the SAME trace_id — that's the fix.
