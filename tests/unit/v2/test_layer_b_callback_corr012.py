"""Tests for Langfuse callback threading into Layer B (AEGIS-P1-CORR-012).

Reference: ``docs/SPEC-observability.md`` §6 (Phase 3, contract CORR-012).

Goal:
    Wire Langfuse tracing into Layer B (``v2/llm.UnifiedInvoker``) so the
    MAP-stage call (1 site) and the 11 narrative calls all flow through
    a chokepoint that merges ``_langfuse_handler`` into the chat
    ``config``. Mirrors CORR-011 (Layer A) and re-uses CORR-010's
    ``_extract_usage`` pattern so token counts are populated.

Behaviour contract verified here:

  1. ``UnifiedInvoker(langfuse_handler=h)`` → ``chat.invoke`` receives
     ``config={"callbacks":[h]}`` when called.
  2. ``UnifiedInvoker()`` (default handler=None) → ``chat.invoke`` is
     called WITHOUT callbacks in config (empty callbacks list).
  3. ``_extract_usage`` reads Ollama ``response_metadata`` primary path.
  4. ``_extract_usage`` returns zeros on missing / empty metadata, no raise.
  5. ``invoke`` returns ``"usage"`` key in result dict, populated.
  6. Caller-supplied ``config={"callbacks":[existing]}`` is preserved;
     Langfuse handler is APPENDED, not overwritten.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ─── Helpers ──────────────────────────────────────────────────────────


class _FakeAIMessage:
    """Minimal stand-in for ``langchain_core.messages.AIMessage``."""

    def __init__(
        self,
        content: str = "ok",
        response_metadata: dict | None = None,
        usage_metadata: dict | None = None,
    ) -> None:
        self.content = content
        self.response_metadata = response_metadata or {}
        self.usage_metadata = usage_metadata or {}


def _build_invoker_with_mocked_chat(
    *,
    handler: object | None = None,
    response: object | None = None,
):
    """Construct a ``UnifiedInvoker`` whose internal ``ChatOllama`` is a MagicMock.

    Returns ``(invoker, mock_chat_instance)`` so tests can introspect the
    call arguments passed to ``chat.invoke``. The mock yields
    ``response`` (defaulting to a benign ``_FakeAIMessage``).

    Note: ``llm/unified.py`` does ``from langchain_ollama import ChatOllama``
    INSIDE ``UnifiedInvoker.__init__`` (lazy import), so we patch at the
    source module (``langchain_ollama.ChatOllama``) — patching
    ``aegis_phase1.llm.unified.ChatOllama`` has no effect because the symbol
    is never bound there.
    """
    response = response if response is not None else _FakeAIMessage()
    with patch(
        "langchain_ollama.ChatOllama"
    ) as MockChatOllama:
        mock_instance = MagicMock(name="ChatOllamaInstance")
        mock_instance.invoke.return_value = response
        MockChatOllama.return_value = mock_instance

        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker(langfuse_handler=handler)
        yield invoker, mock_instance


# ─── 1. Callback attached when handler present ────────────────────────


def test_callback_attached_when_handler_present():
    """Handler is threaded into config={'callbacks':[handler]} at the chat site."""
    handler = MagicMock(name="LangfuseHandler")
    gen = _build_invoker_with_mocked_chat(handler=handler)
    invoker, mock_chat = next(gen)

    try:
        result = invoker.invoke("hello")
    finally:
        next(gen, None)

    assert result["status"] == "OK"
    assert mock_chat.invoke.call_count == 1
    call_kwargs = mock_chat.invoke.call_args.kwargs
    assert "config" in call_kwargs, (
        "config kwarg must be forwarded to chat.invoke when handler is set"
    )
    assert call_kwargs["config"]["callbacks"] == [handler]


# ─── 2. No callback when handler is None (default) ────────────────────


def test_no_callback_when_handler_is_none():
    """Without a handler, ``chat.invoke(msgs)`` keeps its legacy signature."""
    with patch("langchain_ollama.ChatOllama") as MockChatOllama:
        mock_instance = MagicMock(name="ChatOllamaInstance")
        mock_instance.invoke.return_value = _FakeAIMessage()
        MockChatOllama.return_value = mock_instance

        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker()
        assert invoker._langfuse_handler is None

        result = invoker.invoke("hello")

    assert result["status"] == "OK"
    mock_instance.invoke.assert_called_once()
    call_args = mock_instance.invoke.call_args
    call_kwargs = call_args.kwargs
    assert call_kwargs == {} or not call_kwargs.get("config", {}).get("callbacks"), (
        f"Expected no callbacks in config when handler is None; got {call_kwargs!r}"
    )


# ─── 3. _extract_usage — Ollama response_metadata primary path ────────


def test_extract_usage_ollama_response_metadata():
    """Primary path: Ollama ``prompt_eval_count`` / ``eval_count``."""
    from aegis_phase1.llm.unified import _extract_usage

    msg = _FakeAIMessage(
        response_metadata={
            "model": "gemma4:e4b",
            "prompt_eval_count": 1234,
            "eval_count": 567,
            "done": True,
        }
    )
    usage = _extract_usage(msg)
    assert usage["prompt_tokens"] == 1234
    assert usage["completion_tokens"] == 567
    assert usage["total_tokens"] == 1801


# ─── 4. _extract_usage — empty / missing metadata returns zeros ───────


def test_extract_usage_empty_response_metadata():
    """Empty ``response_metadata`` dict AND empty content → zeros, no raise.

    CORR-021: when content is non-empty, the fallback estimates tokens
    from len(content)//4 (1 token minimum). This test uses empty content
    to verify the strictly-zero path still works.
    """
    from aegis_phase1.llm.unified import _extract_usage

    msg = _FakeAIMessage(content="", response_metadata={}, usage_metadata={})
    usage = _extract_usage(msg)
    assert usage == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def test_extract_usage_missing_response_metadata():
    """No ``response_metadata`` attribute → zeros, no raise."""
    from aegis_phase1.llm.unified import _extract_usage

    bare = MagicMock(spec=[])
    bare.response_metadata = None
    bare.usage_metadata = None
    usage = _extract_usage(bare)
    assert usage == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


# ─── 5. invoke returns ``usage`` key with token counts ────────────────


def test_invoke_returns_usage_key():
    """Successful invoke returns ``usage`` dict with non-zero tokens."""
    handler = MagicMock(name="LangfuseHandler")
    fake = _FakeAIMessage(
        response_metadata={
            "prompt_eval_count": 100,
            "eval_count": 50,
            "done": True,
        }
    )
    gen = _build_invoker_with_mocked_chat(handler=handler, response=fake)
    invoker, _ = next(gen)
    try:
        result = invoker.invoke("hello")
    finally:
        next(gen, None)

    assert "usage" in result
    assert result["usage"]["prompt_tokens"] == 100
    assert result["usage"]["completion_tokens"] == 50
    assert result["usage"]["total_tokens"] == 150


# ─── 6. Caller's callbacks preserved (handler APPENDED) ───────────────


def test_callback_chain_preserved():
    """Caller-supplied callbacks are kept; handler is appended, not overwritten."""
    handler = MagicMock(name="LangfuseHandler")
    other = MagicMock(name="OtherCallback")
    fake = _FakeAIMessage()

    gen = _build_invoker_with_mocked_chat(handler=handler, response=fake)
    invoker, mock_chat = next(gen)
    try:
        result = invoker.invoke("hello", config={"callbacks": [other]})
    finally:
        next(gen, None)

    assert result["status"] == "OK"
    call_kwargs = mock_chat.invoke.call_args.kwargs
    callbacks = call_kwargs["config"]["callbacks"]
    assert other in callbacks, "Caller-supplied callback must be preserved"
    assert handler in callbacks, "Langfuse handler must be appended to the chain"
    assert len(callbacks) == 2, (
        f"Expected exactly [other, handler]; got {callbacks!r}"
    )