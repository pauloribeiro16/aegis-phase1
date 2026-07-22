"""Tests for Langfuse callback threading into Phase1LLMInvoker (AEGIS-P1-CORR-011).

Reference: ``docs/SPEC-observability.md`` §6 (Phase 2, contract CORR-011).

Goal:
    Thread ``config`` (with ``callbacks=[handler]``) from the public ``invoke()``
    through ``_attempt()`` to ``llm.invoke(messages, config=...)`` so that
    Langfuse's ``CallbackHandler`` actually fires when LANGFUSE_ENABLED=true.

Behaviour contract verified here:

  1. When the invoker was constructed with a ``langfuse_handler``, every
     internal ``chat.invoke(...)`` call passes ``config={"callbacks":[handler]}``.
  2. When no handler is wired (default — LANGFUSE_ENABLED=false), the existing
     ``self.chat.invoke(messages)`` call signature is preserved (no ``config=``
     kwarg added), so today's behaviour is byte-identical.
  3. If a caller passes ``config={"callbacks":[some_other]}``, the Langfuse
     handler is APPENDED, not overwriting the existing chain.
  4. ``get_langfuse_callback()`` master switch sanity (LANGFUSE_ENABLED=false).
  5. ``get_langfuse_callback()`` opt-in path returns a handler when credentials
     are provided (mocked — no real Langfuse connection).
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker


# CORR-055 (2026-07-22): the _FakeAIMessage default content changed from
# '{"items": []}' to valid P1B-LLM-01 markdown. Pre-CORR-050, the validator
# was a no-op mock and any JSON would yield status=OK. Post-CORR-050, the
# invoker consults the real MARKDOWN_PARSERS registry; P1B-LLM-01-INTERPRETATION
# has a registered P1BLLM01Parser that requires '## Status' etc., so the
# mock must return markdown matching the template. See CONTRACT-055.md.


# ─── Helpers ──────────────────────────────────────────────────────────


# CORR-055: content must be valid P1B-LLM-01 markdown (not '{"items": []}').
# Before CORR-050, the validator was a no-op and any JSON would pass.
# After CORR-050, P1B-LLM-01-INTERPRETATION has a registered MarkdownParser
# that requires '## Status' + '## Interpretations' + '## Derogations' sections.
_VALID_P1B_LLM_01_MARKDOWN = """## Status

- status: OK
- confidence: HIGH

## Interpretations

### INT-01

- entry_id: TIPO2-TEST
- applicable: YES
- activation_rationale: Test rationale for callback wiring verification.
- layer0_refs: SubDomains/D-04.3.md
- legal_refs: GDPR Art. 33(1)
- company_fact_refs: test=true

## Derogations

### DER-01

- entry_id: TIPO3-TEST
- activation_verdict: NOT_ACTIVATED
- activation_rationale: Test derogation for callback wiring.
- layer0_refs: SubDomains/D-04.3.md
- legal_refs: GDPR Art. 2(2)(c)
- company_fact_refs: test=true
"""


class _FakeAIMessage:
    """Minimal stand-in for ``langchain_core.messages.AIMessage``.

    CORR-055: default content is now valid P1B-LLM-01 markdown so the
    invoker's MarkdownParser succeeds (status=OK). The original
    '{"items": []}' worked before CORR-050 because the validator was
    mocked, but post-CORR-050 the parser registry is real and rejects
    JSON that doesn't match the markdown template.
    """

    def __init__(self, content: str = _VALID_P1B_LLM_01_MARKDOWN) -> None:
        self.content = content
        self.response_metadata = {}
        self.usage_metadata = {}


def _build_invoker(*, handler: object | None = None) -> Phase1LLMInvoker:
    """Build a Phase1LLMInvoker with stubbed loaders (no real PROMPTS/ scan).

    Returns an instance ready for direct ``chat.invoke`` patching.
    """
    pl = MagicMock(name="PromptLoader")
    pl.render.return_value = {"system": "S", "user": "U"}
    pl.load.return_value = {"schema": {}}
    return Phase1LLMInvoker(
        prompt_loader=pl,
        catalog_loader=MagicMock(name="CatalogLoader"),
        validator=MagicMock(name="Validator"),
        llm_logger=MagicMock(name="LLMLogger"),
        format_logger=MagicMock(name="FormatLogger"),
        langfuse_handler=handler,
    )


def _patched_chat(invoker: Phase1LLMInvoker, response: object | None = None) -> MagicMock:
    """Replace ``invoker.chat`` with a MagicMock that yields ``response``.

    ``invoker.chat`` is constructed lazily inside ``_attempt`` from
    ``ChatOllama(**kwargs)``. We patch the *class* so every construction in
    the test returns the same controlled mock.
    """
    mock_response = response if response is not None else _FakeAIMessage()
    with patch(
        "aegis_phase1.prompts_v2.invoker.ChatOllama"
    ) as MockChatOllama:
        mock_instance = MagicMock(name="ChatOllamaInstance")
        mock_instance.invoke.return_value = mock_response
        MockChatOllama.return_value = mock_instance
        yield mock_instance


# ─── 1. Callback attached when handler present ────────────────────────


def test_callback_attached_when_handler_present():
    """Handler is threaded into config={'callbacks':[handler]} at the chat site."""
    handler = MagicMock(name="LangfuseHandler")
    invoker = _build_invoker(handler=handler)

    for mock_chat in _patched_chat(invoker):
        result = invoker.invoke("P1B-LLM-01-INTERPRETATION", {"x": 1})

    assert result["status"] == "OK"
    assert mock_chat.invoke.call_count == 1
    call_kwargs = mock_chat.invoke.call_args.kwargs
    assert "config" in call_kwargs, (
        "config kwarg must be forwarded to chat.invoke when handler is set"
    )
    assert call_kwargs["config"]["callbacks"] == [handler]


# ─── 2. No callback when handler is None (default) ────────────────────


def test_no_callback_when_handler_is_none():
    """Without a handler, ``chat.invoke(messages)`` keeps its legacy signature."""
    invoker = _build_invoker(handler=None)
    # Sanity: explicit None, mirroring the master-switch-off path.
    assert invoker._langfuse_handler is None

    for mock_chat in _patched_chat(invoker):
        result = invoker.invoke("P1B-LLM-01-INTERPRETATION", {"x": 1})

    assert result["status"] == "OK"
    mock_chat.invoke.assert_called_once()
    call_kwargs = mock_chat.invoke.call_args.kwargs
    # Either no kwargs at all, or config empty — but config MUST NOT carry a
    # callbacks list (because there's no handler to thread).
    assert call_kwargs == {} or not call_kwargs.get("config", {}).get("callbacks"), (
        f"Expected no callbacks in config when handler is None; got {call_kwargs!r}"
    )


# ─── 3. Handler is APPENDED, not overwriting caller's callbacks ───────


def test_callback_chain_includes_other_callbacks():
    """If the caller passes its own callbacks, the Langfuse handler is appended."""
    handler = MagicMock(name="LangfuseHandler")
    other = MagicMock(name="OtherCallback")
    invoker = _build_invoker(handler=handler)

    for mock_chat in _patched_chat(invoker):
        result = invoker.invoke(
            "P1B-LLM-01-INTERPRETATION",
            {"x": 1},
            config={"callbacks": [other]},
        )

    assert result["status"] == "OK"
    call_kwargs = mock_chat.invoke.call_args.kwargs
    callbacks = call_kwargs["config"]["callbacks"]
    assert other in callbacks, "Caller-supplied callback must be preserved"
    assert handler in callbacks, "Langfuse handler must be appended to the chain"
    assert len(callbacks) == 2, (
        f"Expected exactly [other, handler]; got {callbacks!r}"
    )


# ─── 4. Master switch off → no handler ────────────────────────────────


def test_master_switch_off_no_handler(monkeypatch):
    """``LANGFUSE_ENABLED=false`` → ``(None, None)`` from get_langfuse_callback()."""
    from aegis_phase1.llm.tracing import get_langfuse_callback

    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    client, handler = get_langfuse_callback()
    assert client is None
    assert handler is None


# ─── 5. Master switch on + credentials → handler returned (mocked) ────


def test_master_switch_on_returns_handler(monkeypatch):
    """LANGFUSE_ENABLED=true + valid keys → real handler (no live network).

    ``tracing.py`` does local imports inside ``get_langfuse_callback()``::

        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

    So we patch at the SOURCE modules (``langfuse.Langfuse``,
    ``langfuse.langchain.CallbackHandler``) — patching the consumer module's
    attribute namespace would have no effect. The wiring contract is what we
    test: the function returns ``(client, handler)`` where ``handler`` is the
    ``CallbackHandler`` instance.
    """
    from aegis_phase1.llm.tracing import get_langfuse_callback

    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-CHANGEME")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-CHANGEME")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")

    mock_client_instance = MagicMock(name="LangfuseClientInstance")
    mock_handler_instance = MagicMock(name="CallbackHandlerInstance")

    with patch(
        "langfuse.Langfuse"
    ) as MockLangfuse, patch(
        "langfuse.langchain.CallbackHandler"
    ) as MockHandler:
        MockLangfuse.return_value = mock_client_instance
        MockHandler.return_value = mock_handler_instance

        client, handler = get_langfuse_callback()

    assert client is mock_client_instance
    assert handler is mock_handler_instance
