"""Smoke tests for ``aegis_phase1.llm.chat_minimax.ChatMinimax`` (CORR-062 S2).

Reference: ``00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md``
``Model Configuration`` block (line 156)::

    model: MiniMax-M2.7
    provider: MiniMaxChat

The methodology was designed against the MiniMax M-series; the
``ChatMinimax`` adapter wraps the Mavis gateway (Anthropic Messages
protocol) so the rest of the AEGIS Phase 1 pipeline
(parser, validator, executor) is model-agnostic.

These tests:
  1. Verify message conversion (SystemMessage → top-level ``system``,
     HumanMessage → ``user``).
  2. Verify request body shape (model, max_tokens, messages, system).
  3. Verify response parsing (text + usage + response_metadata).
  4. Verify api_key resolution (constructor > MINIMAX_API_KEY >
     MAVIS_ACCESS_TOKEN).
  5. Verify the chat can be constructed and ``invoke`` called
     end-to-end against a mocked httpx (no real network).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


# ─── 1. Message conversion ────────────────────────────────────────


def test_convert_messages_splits_system_from_rest():
    """SystemMessage → top-level system; HumanMessage → user; AI → assistant."""
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    messages = [
        SystemMessage(content="You are a helpful AEGIS assistant."),
        HumanMessage(content="What is the CRA?"),
        AIMessage(content="The CRA is the Cyber Resilience Act."),
        HumanMessage(content="When does it apply?"),
    ]
    system, rest = ChatMinimax._convert_messages(messages)

    assert system == "You are a helpful AEGIS assistant."
    assert len(rest) == 3
    assert rest[0] == {"role": "user", "content": "What is the CRA?"}
    assert rest[1] == {"role": "assistant", "content": "The CRA is the Cyber Resilience Act."}
    assert rest[2] == {"role": "user", "content": "When does it apply?"}


def test_convert_messages_no_system():
    """No SystemMessage → system is None."""
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    messages = [HumanMessage(content="hello")]
    system, rest = ChatMinimax._convert_messages(messages)
    assert system is None
    assert rest == [{"role": "user", "content": "hello"}]


def test_convert_messages_concatenates_multiple_systems():
    """Multiple SystemMessages are joined with double newlines (Anthropic
    supports one system field; we collapse N into one)."""
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    messages = [
        SystemMessage(content="Block 1."),
        HumanMessage(content="Q"),
        SystemMessage(content="Block 2."),
    ]
    system, rest = ChatMinimax._convert_messages(messages)
    assert system == "Block 1.\n\nBlock 2."
    assert rest == [{"role": "user", "content": "Q"}]


# ─── 2. Response parsing ─────────────────────────────────────────


def test_parse_response_extracts_text_and_usage():
    """Anthropic response shape → AIMessage with text + response_metadata
    + usage_metadata (the shape UnifiedInvoker._extract_usage expects).
    """
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    data = {
        "id": "msg_01ABC",
        "type": "message",
        "role": "assistant",
        "model": "MiniMax-M3",
        "content": [
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "world."},
        ],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    msg = ChatMinimax._parse_response(data)

    assert isinstance(msg, AIMessage)
    assert msg.content == "Hello world."
    assert msg.response_metadata["model"] == "MiniMax-M3"
    assert msg.response_metadata["stop_reason"] == "end_turn"
    assert msg.response_metadata["input_tokens"] == 100
    assert msg.response_metadata["output_tokens"] == 50
    assert msg.usage_metadata == {
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
    }


def test_parse_response_handles_missing_usage():
    """Defensive: no usage block → zeros, never raises."""
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    data = {
        "content": [{"type": "text", "text": "ok"}],
    }
    msg = ChatMinimax._parse_response(data)
    assert msg.content == "ok"
    assert msg.usage_metadata == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


# ─── 3. API key resolution ───────────────────────────────────────


def test_resolve_api_key_from_constructor():
    """Constructor api_key takes priority when not the placeholder."""
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    chat = ChatMinimax(api_key="sk-real-token-123")
    assert chat._resolve_api_key() == "sk-real-token-123"


def test_resolve_api_key_treats_placeholder_as_empty(monkeypatch):
    """``sk-xxx`` placeholder is ignored (must come from env)."""
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("MAVIS_ACCESS_TOKEN", raising=False)
    chat = ChatMinimax(api_key="sk-xxx")
    with pytest.raises(ValueError, match="no api_key configured"):
        chat._resolve_api_key()


def test_resolve_api_key_falls_back_to_minimax_env(monkeypatch):
    """When constructor is empty/placeholder, MINIMAX_API_KEY is used."""
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    monkeypatch.setenv("MINIMAX_API_KEY", "sk-from-minimax-env")
    monkeypatch.delenv("MAVIS_ACCESS_TOKEN", raising=False)
    chat = ChatMinimax(api_key="sk-xxx")
    assert chat._resolve_api_key() == "sk-from-minimax-env"


def test_resolve_api_key_falls_back_to_mavis_env(monkeypatch):
    """When MINIMAX_API_KEY is missing, MAVIS_ACCESS_TOKEN is used."""
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("MAVIS_ACCESS_TOKEN", "sk-from-mavis-env")
    chat = ChatMinimax(api_key="")
    assert chat._resolve_api_key() == "sk-from-mavis-env"


def test_resolve_api_key_constructor_beats_env(monkeypatch):
    """If constructor has a real key, env vars are ignored."""
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    monkeypatch.setenv("MINIMAX_API_KEY", "sk-from-env")
    monkeypatch.setenv("MAVIS_ACCESS_TOKEN", "sk-from-env-2")
    chat = ChatMinimax(api_key="sk-from-constructor")
    assert chat._resolve_api_key() == "sk-from-constructor"


# ─── 4. End-to-end (mocked httpx, no real network) ───────────────


def test_generate_posts_correct_request_and_parses_response():
    """Mocked httpx: verify the request body + URL + headers shape
    and the returned ChatResult wraps the parsed AIMessage.
    """
    from aegis_phase1.llm.chat_minimax import ChatMinimax

    fake_response_payload = {
        "id": "msg_01XYZ",
        "type": "message",
        "role": "assistant",
        "model": "MiniMax-M3",
        "content": [{"type": "text", "text": "## Status\n- applicable: YES"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1234, "output_tokens": 56},
    }

    mock_response = MagicMock()
    mock_response.json.return_value = fake_response_payload
    mock_response.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    chat = ChatMinimax(
        model="MiniMax-M3",
        api_key="sk-test-key",
        max_tokens=2048,
        temperature=0.0,
    )

    with patch("aegis_phase1.llm.chat_minimax.httpx.Client", return_value=mock_client):
        result = chat._generate(
            messages=[
                SystemMessage(content="You are an AEGIS assistant."),
                HumanMessage(content="Evaluate CRA applicability."),
            ],
        )

    # Result is a ChatResult with one generation
    assert len(result.generations) == 1
    msg = result.generations[0].message
    assert msg.content.startswith("## Status")
    assert msg.usage_metadata["input_tokens"] == 1234
    assert msg.usage_metadata["output_tokens"] == 56

    # Request shape
    call_args = mock_client.post.call_args
    url = call_args.args[0]
    body = call_args.kwargs["json"]
    headers = call_args.kwargs["headers"]

    assert url.endswith("/messages"), f"Expected /messages endpoint; got {url}"
    assert body["model"] == "MiniMax-M3"
    assert body["max_tokens"] == 2048
    assert body["system"] == "You are an AEGIS assistant."
    assert body["messages"] == [
        {"role": "user", "content": "Evaluate CRA applicability."},
    ]
    assert body["temperature"] == 0.0
    assert headers["x-api-key"] == "sk-test-key"
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["content-type"] == "application/json"


# ─── 5. Integration with UnifiedInvoker (provider=minimax) ──────


def test_unified_invoker_with_minimax_provider():
    """``UnifiedInvoker(provider='minimax')`` builds a ``ChatMinimax`` chat
    (not ``ChatOllama``). The heavy invoker + dispatcher chain works
    unchanged.
    """
    from aegis_phase1.llm.chat_minimax import ChatMinimax
    from aegis_phase1.llm.unified import UnifiedInvoker

    invoker = UnifiedInvoker(
        model="MiniMax-M3",
        provider="minimax",
        api_key="sk-test",
    )

    # The chat is a ChatMinimax, not a ChatOllama
    assert isinstance(invoker.chat, ChatMinimax)
    assert invoker.provider == "minimax"
    assert invoker.model == "MiniMax-M3"
    # Default base URL is the Mavis gateway
    assert "minimax.io" in invoker.chat.base_url


def test_unified_invoker_default_provider_is_ollama():
    """Backward compat: omitting provider still uses ChatOllama."""
    from langchain_ollama import ChatOllama

    from aegis_phase1.llm.unified import UnifiedInvoker

    invoker = UnifiedInvoker(model="gemma4:e4b")
    assert invoker.provider == "ollama"
    assert isinstance(invoker.chat, ChatOllama)
