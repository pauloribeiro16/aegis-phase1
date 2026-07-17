"""Tests for ``aegis_phase1.llm.UnifiedInvoker`` (AEGIS-P1-CORR-013).

Reference: ``docs/SPEC-observability.md`` §3.2 (design) + §6 (Phase 4a).

Goal:
    Verify the unified invoker wraps both the heavy (Phase1LLMInvoker)
    and the light (free-text) paths into one class, threads the Langfuse
    handler into ``config["callbacks"]`` when present, and remains byte-
    identical to the legacy invokers when ``LANGFUSE_ENABLED=false``.

Behaviour contracts verified here:

  1. Default constructor fills ``model``, ``_langfuse_handler``, ``chat``.
  2. ``invoke_raw`` returns ``{raw, status, usage}``; ``usage`` is read
     from Ollama-native ``response_metadata`` (primary path).
  3. ``invoke_raw`` appends the Langfuse handler to
     ``config["callbacks"]`` (dedupe; caller chain preserved).
  4. ``invoke_raw`` calls chat WITHOUT a ``config`` kwarg when no handler
     is set (byte-identical legacy behaviour).
  5. ``invoke_spec`` delegates to a lazy ``Phase1LLMInvoker`` child.
  6. ``LANGFUSE_ENABLED=false`` (default) and no handler → ``callbacks``
     is the empty list, ``config`` is ``{}`` — i.e. byte-identical to
     the pre-CORR-011/012 pipelines.
"""
from __future__ import annotations

import os
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


def _patched_chat(response: object | None = None) -> tuple[MagicMock, MagicMock]:
    """Patch ``langchain_ollama.ChatOllama``; return ``(MockClass, mock_instance)``.

    ``UnifiedInvoker.__init__`` (lazy) imports ``langchain_ollama.ChatOllama``,
    so we patch at the source module (per the CORR-012 test file's
    convention) and yield the patch context.
    """
    MockChatOllama = MagicMock(name="ChatOllama")
    mock_instance = MagicMock(name="ChatOllamaInstance")
    mock_instance.invoke.return_value = response if response is not None else _FakeAIMessage()
    MockChatOllama.return_value = mock_instance
    return MockChatOllama, mock_instance


# ─── 1. Init defaults ─────────────────────────────────────────────────


def test_unified_invoker_init_defaults():
    """Default constructor fills model, _langfuse_handler, chat."""
    MockChatOllama, mock_instance = _patched_chat()
    with patch("langchain_ollama.ChatOllama", MockChatOllama):
        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker(model="gemma4:e4b")

    assert invoker.model == "gemma4:e4b"
    assert invoker._langfuse_handler is None
    assert invoker.chat is mock_instance
    assert invoker.base_url == "http://localhost:11434"
    assert invoker.timeout == 120
    assert invoker._heavy is None
    MockChatOllama.assert_called_once_with(
        model="gemma4:e4b",
        base_url="http://localhost:11434",
        timeout=120,
    )


# ─── 2. invoke_raw returns dict with usage key ────────────────────────


def test_invoke_raw_returns_dict_with_usage_key():
    """invoke_raw returns the canonical {raw, status, usage} shape."""
    fake = _FakeAIMessage(
        content="hello world",
        response_metadata={
            "model": "gemma4:e4b",
            "prompt_eval_count": 100,
            "eval_count": 50,
            "done": True,
        },
    )
    MockChatOllama, mock_instance = _patched_chat(response=fake)
    with patch("langchain_ollama.ChatOllama", MockChatOllama):
        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker()
        result = invoker.invoke_raw("hello")

    assert result["raw"] == "hello world"
    assert result["status"] == "OK"
    assert result["usage"] == {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    }


# ─── 3. invoke_raw appends Langfuse handler ──────────────────────────


def test_invoke_raw_appends_langfuse_handler():
    """Handler is threaded into config={'callbacks':[handler]} at the chat site."""
    handler = MagicMock(name="LangfuseHandler")
    MockChatOllama, mock_instance = _patched_chat()
    with patch("langchain_ollama.ChatOllama", MockChatOllama):
        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker(langfuse_handler=handler)
        invoker.invoke_raw("hi")

    mock_instance.invoke.assert_called_once()
    call_kwargs = mock_instance.invoke.call_args.kwargs
    assert "config" in call_kwargs, (
        "config kwarg must be forwarded to chat.invoke when handler is set"
    )
    assert call_kwargs["config"]["callbacks"] == [handler]


# ─── 4. invoke_raw no callbacks when handler is None ──────────────────


def test_invoke_raw_no_callback_when_no_handler():
    """Without a handler, chat.invoke receives config with callbacks=[]."""
    MockChatOllama, mock_instance = _patched_chat()
    with patch("langchain_ollama.ChatOllama", MockChatOllama):
        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker()
        assert invoker._langfuse_handler is None

        invoker.invoke_raw("hi")

    mock_instance.invoke.assert_called_once()
    call_kwargs = mock_instance.invoke.call_args.kwargs
    assert "config" in call_kwargs, (
        f"Expected config kwarg on chat.invoke; got {call_kwargs!r}"
    )
    assert call_kwargs["config"]["callbacks"] == [], (
        f"Expected empty callbacks list when handler is None; got {call_kwargs!r}"
    )


# ─── 5. invoke_spec delegates to heavy ───────────────────────────────


def test_invoke_spec_delegates_to_heavy():
    """invoke_spec routes the heavy call to a Phase1LLMInvoker child."""
    from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker

    expected_result = {
        "status": "OK",
        "parsed_output": {"x": 42},
        "validation": {"valid": True},
    }

    with patch.object(Phase1LLMInvoker, "invoke", return_value=expected_result) as mock_invoke:
        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker(prompt_loader=MagicMock(name="PromptLoader"))
        result = invoker.invoke_spec("P1B-LLM-01-INTERPRETATION", {"x": 1})

    assert result == expected_result
    mock_invoke.assert_called_once()
    call_args = mock_invoke.call_args
    assert call_args.args[0] == "P1B-LLM-01-INTERPRETATION"
    assert call_args.args[1] == {"x": 1}


def test_invoke_spec_reuses_cached_heavy():
    """Second invoke_spec call reuses the same heavy child (no rebuild)."""
    from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker

    with patch.object(Phase1LLMInvoker, "invoke", return_value={"status": "OK"}):
        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker(prompt_loader=MagicMock(name="PromptLoader"))
        first = invoker._get_heavy()
        second = invoker._get_heavy()

    assert first is second


# ─── 6. Langfuse off by default → no callback ────────────────────────


def test_langfuse_off_yields_no_callback(monkeypatch):
    """With LANGFUSE_ENABLED=false (default) and no explicit handler,
    chat.invoke is called with config={callbacks: []}.
    """
    monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
    MockChatOllama, mock_instance = _patched_chat()
    with patch("langchain_ollama.ChatOllama", MockChatOllama):
        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker()
        invoker.invoke_raw("x")

    mock_instance.invoke.assert_called_once()
    call_kwargs = mock_instance.invoke.call_args.kwargs
    assert "config" in call_kwargs
    assert call_kwargs["config"]["callbacks"] == []


# ─── Bonus: _extract_usage unit tests (covers both metadata paths) ───


def test_extract_usage_ollama_response_metadata():
    """Primary path: Ollama ``prompt_eval_count`` / ``eval_count``."""
    from aegis_phase1.llm.unified import _extract_usage

    msg = _FakeAIMessage(
        response_metadata={"prompt_eval_count": 200, "eval_count": 80}
    )
    usage = _extract_usage(msg)
    assert usage == {
        "prompt_tokens": 200,
        "completion_tokens": 80,
        "total_tokens": 280,
    }


def test_extract_usage_langchain_core_fallback():
    """Fallback path: langchain-core ``usage_metadata`` shape."""
    from aegis_phase1.llm.unified import _extract_usage

    msg = _FakeAIMessage(
        response_metadata={},
        usage_metadata={
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        },
    )
    usage = _extract_usage(msg)
    assert usage == {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
    }


def test_extract_usage_empty_returns_zeros():
    """Empty metadata → zeros, never raises."""
    from aegis_phase1.llm.unified import _extract_usage

    msg = _FakeAIMessage(response_metadata={}, usage_metadata={})
    usage = _extract_usage(msg)
    assert usage == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def test_merge_handler_no_handler_returns_empty_callback_list():
    """_merge_handler_into_config(None, None) returns {callbacks: []}."""
    from aegis_phase1.llm.unified import _merge_handler_into_config

    cfg = _merge_handler_into_config(None, None)
    assert cfg == {"callbacks": []}


def test_merge_handler_appends_handler_when_no_existing_callbacks():
    """Handler is appended to an empty callbacks list."""
    from aegis_phase1.llm.unified import _merge_handler_into_config

    handler = MagicMock(name="Handler")
    cfg = _merge_handler_into_config(handler, None)
    assert cfg["callbacks"] == [handler]


def test_merge_handler_deduplicates_when_handler_already_present():
    """Calling twice with same handler does not append duplicate."""
    from aegis_phase1.llm.unified import _merge_handler_into_config

    handler = MagicMock(name="Handler")
    other = MagicMock(name="Other")
    cfg = _merge_handler_into_config(handler, {"callbacks": [other, handler]})
    assert cfg["callbacks"] == [other, handler]


# ─── Bonus: polymorphic invoke dispatcher ────────────────────────────


def test_invoke_dispatches_to_spec_when_inputs_is_dict():
    """invoke(spec_id, dict) routes to invoke_spec."""
    from aegis_phase1.llm.unified import UnifiedInvoker

    invoker = UnifiedInvoker()
    invoker.invoke_spec = MagicMock(return_value={"status": "OK"})  # type: ignore[method-assign]
    invoker.invoke_raw = MagicMock()  # type: ignore[method-assign]

    result = invoker.invoke("P1B-LLM-01", {"x": 1})

    invoker.invoke_spec.assert_called_once_with("P1B-LLM-01", {"x": 1}, config=None)
    invoker.invoke_raw.assert_not_called()
    assert result == {"status": "OK"}


def test_invoke_dispatches_to_raw_when_inputs_is_not_dict():
    """invoke(prompt) routes to invoke_raw (narrative callers)."""
    from aegis_phase1.llm.unified import UnifiedInvoker

    invoker = UnifiedInvoker()
    invoker.invoke_spec = MagicMock()  # type: ignore[method-assign]
    invoker.invoke_raw = MagicMock(return_value={"raw": "hi", "status": "OK"})  # type: ignore[method-assign]

    result = invoker.invoke("hello world")

    invoker.invoke_raw.assert_called_once()
    invoker.invoke_spec.assert_not_called()
    assert result == {"raw": "hi", "status": "OK"}


def test_default_model_is_2b():
    """CORR-020: default model switched from gemma4:e4b to gemma4:e2b."""
    from aegis_phase1.llm.unified import UnifiedInvoker

    assert UnifiedInvoker.DEFAULT_MODEL == "gemma4:e2b"
