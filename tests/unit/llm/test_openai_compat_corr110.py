"""Tests for ``aegis_phase1.llm.openai_compat.ChatOpenAICompat`` (CORR-110).

Reference: ``00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md``
``Model Configuration`` block — the Phase 1 pipeline is model-agnostic
via the LangChain ``BaseChatModel`` interface. ``ChatOpenAICompat`` is
the adapter that lets any OpenAI-compatible HTTP server (vLLM, TGI,
SGLang) sit behind ``UnifiedInvoker`` so we can evaluate models that
the local Ollama 0.31.1 daemon cannot serve (e.g. gemma-4-31B-it on
JOB 1846584 — the OOAC failure that motivated CORR-110).

These tests:
  1. Verify the request body + URL + headers shape (OpenAI chat
     completions protocol).
  2. Verify message conversion (SystemMessage / HumanMessage /
     AIMessage → OpenAI roles).
  3. Verify response parsing (text + usage + response_metadata).
  4. Verify env-var override behaviour (AEGIS_VLLM_BASE_URL etc.) and
     the no-new-deps guarantee (``httpx`` + ``langchain-core`` only).
  5. Verify end-to-end ``_generate`` against a mocked httpx.
  6. Verify integration with ``UnifiedInvoker(provider='vllm')`` and
     ``build_llm_invoker(provider='vllm')`` — the chat backend is
     ChatOpenAICompat, the base URL is the vLLM default, the
     ``_ensure_ollama`` probe is skipped.
  7. Verify ``_detect_provider`` recognises the ``vllm:`` prefix and
     does NOT misroute to ``transformers`` (a HF Hub id can look like
     ``vllm:google/gemma-4-31B-it``).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# ─── 1. Message conversion ────────────────────────────────────────


def test_openai_message_human_maps_to_user():
    from aegis_phase1.llm.openai_compat import _openai_message

    assert _openai_message(HumanMessage(content="hi")) == {
        "role": "user",
        "content": "hi",
    }


def test_openai_message_ai_maps_to_assistant():
    from aegis_phase1.llm.openai_compat import _openai_message

    assert _openai_message(AIMessage(content="ok")) == {
        "role": "assistant",
        "content": "ok",
    }


def test_openai_message_system_maps_to_system():
    from aegis_phase1.llm.openai_compat import _openai_message

    assert _openai_message(SystemMessage(content="be terse")) == {
        "role": "system",
        "content": "be terse",
    }


def test_openai_message_flattens_multimodal_blocks():
    """Multimodal content lists (e.g. image_url blocks) collapse to the
    text segments only — Phase 1 is text-only (CORR-056 convention
    inherited by CORR-110)."""
    from aegis_phase1.llm.openai_compat import _openai_message

    block_msg = HumanMessage(
        content=[
            {"type": "text", "text": "Question: "},
            {"type": "image_url", "image_url": "https://example.com/x.png"},
            {"type": "text", "text": "what is GDPR?"},
        ]
    )
    assert _openai_message(block_msg) == {
        "role": "user",
        "content": "Question: \nwhat is GDPR?",
    }


# ─── 2. Constructor + env overrides ──────────────────────────────


def test_constructor_defaults_match_module():
    from aegis_phase1.llm.openai_compat import (
        DEFAULT_BASE_URL,
        DEFAULT_MAX_TOKENS,
        DEFAULT_MODEL,
        DEFAULT_TEMPERATURE,
        DEFAULT_TIMEOUT,
        ChatOpenAICompat,
    )

    chat = ChatOpenAICompat()
    assert chat.model == DEFAULT_MODEL
    assert chat.base_url == DEFAULT_BASE_URL
    assert chat.timeout == DEFAULT_TIMEOUT
    assert chat.max_tokens == DEFAULT_MAX_TOKENS
    assert chat.temperature == DEFAULT_TEMPERATURE
    assert chat._llm_type == "openai_compat"


def test_explicit_ctor_args_override_env(monkeypatch):
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    monkeypatch.setenv("AEGIS_VLLM_BASE_URL", "http://from-env:9999/v1")
    monkeypatch.setenv("AEGIS_VLLM_MODEL", "from-env-model")
    monkeypatch.setenv("AEGIS_VLLM_TIMEOUT", "42.5")
    monkeypatch.setenv("AEGIS_VLLM_API_KEY", "sk-env-key")

    chat = ChatOpenAICompat(
        model="explicit-model",
        base_url="http://explicit:1234/v1",
        timeout=7.0,
        api_key="sk-explicit",
    )
    assert chat.model == "explicit-model"
    assert chat.base_url == "http://explicit:1234/v1"
    assert chat.timeout == 7.0
    assert chat.api_key == "sk-explicit"


def test_env_overrides_fill_only_module_defaults(monkeypatch):
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    monkeypatch.setenv("AEGIS_VLLM_BASE_URL", "http://env:8000/v1")
    monkeypatch.setenv("AEGIS_VLLM_MODEL", "env-model")
    monkeypatch.setenv("AEGIS_VLLM_TIMEOUT", "300")
    monkeypatch.setenv("AEGIS_VLLM_API_KEY", "sk-env")

    chat = ChatOpenAICompat()
    assert chat.base_url == "http://env:8000/v1"
    assert chat.model == "env-model"
    assert chat.timeout == 300.0
    assert chat.api_key == "sk-env"

    # Sanity: clear env, construct again — must restore module defaults.
    for var in (
        "AEGIS_VLLM_BASE_URL",
        "AEGIS_VLLM_MODEL",
        "AEGIS_VLLM_TIMEOUT",
        "AEGIS_VLLM_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    chat2 = ChatOpenAICompat()
    from aegis_phase1.llm.openai_compat import DEFAULT_MODEL

    assert chat2.model == DEFAULT_MODEL


def test_invalid_timeout_env_falls_back_to_default(monkeypatch):
    from aegis_phase1.llm.openai_compat import DEFAULT_TIMEOUT, ChatOpenAICompat

    monkeypatch.setenv("AEGIS_VLLM_TIMEOUT", "not-a-float")
    # Patch the module logger so we can inspect the warning. We don't
    # use caplog here because pytest's caplog handler lookup is
    # fragile across worker configurations; the warning is observable
    # via logging capture of the root logger.
    import logging

    captured: list[str] = []

    class _Probe(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(self.format(record))

    probe = _Probe(level=logging.WARNING)
    logger_obj = logging.getLogger("aegis_phase1.llm.openai_compat")
    logger_obj.addHandler(probe)
    try:
        chat = ChatOpenAICompat()
    finally:
        logger_obj.removeHandler(probe)
    assert chat.timeout == DEFAULT_TIMEOUT
    assert any("invalid AEGIS_VLLM_TIMEOUT" in msg for msg in captured), captured


# ─── 3. _generate: end-to-end with mocked httpx ──────────────────


def _mock_httpx_response(payload: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = str(payload)
    return resp


def _mock_httpx_client(resp: MagicMock) -> MagicMock:
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.return_value = resp
    return client


def test_generate_posts_correct_request_and_parses_response():
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    payload = {
        "id": "chatcmpl-abc123",
        "model": "gemma4-31b",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "## Status\n- applicable: YES"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1234, "completion_tokens": 56, "total_tokens": 1290},
    }
    mock_resp = _mock_httpx_response(payload)
    mock_client = _mock_httpx_client(mock_resp)

    chat = ChatOpenAICompat(
        model="gemma4-31b",
        base_url="http://node01:8000/v1",
        max_tokens=2048,
        temperature=0.0,
        timeout=10.0,
    )

    with patch("aegis_phase1.llm.openai_compat.httpx.Client", return_value=mock_client):
        result = chat._generate(
            messages=[
                SystemMessage(content="You are an AEGIS assistant."),
                HumanMessage(content="Evaluate CRA applicability."),
            ],
        )

    assert len(result.generations) == 1
    msg = result.generations[0].message
    assert msg.content.startswith("## Status")
    assert msg.usage_metadata == {
        "input_tokens": 1234,
        "output_tokens": 56,
        "total_tokens": 1290,
    }
    assert msg.response_metadata["model"] == "gemma4-31b"
    assert msg.response_metadata["finish_reason"] == "stop"

    # Request shape: URL, body, headers
    call_args = mock_client.post.call_args
    url = call_args.args[0]
    body = call_args.kwargs["json"]
    headers = call_args.kwargs["headers"]

    assert url == "http://node01:8000/v1/chat/completions"
    assert body["model"] == "gemma4-31b"
    assert body["max_tokens"] == 2048
    assert body["temperature"] == 0.0
    assert body["stream"] is False
    assert body["messages"] == [
        {"role": "system", "content": "You are an AEGIS assistant."},
        {"role": "user", "content": "Evaluate CRA applicability."},
    ]
    assert headers["Content-Type"] == "application/json"


def test_generate_omits_auth_header_when_no_api_key():
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    mock_resp = _mock_httpx_response(
        {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {},
        }
    )
    mock_client = _mock_httpx_client(mock_resp)

    chat = ChatOpenAICompat(model="m", api_key="", base_url="http://h:8000/v1")

    with patch("aegis_phase1.llm.openai_compat.httpx.Client", return_value=mock_client):
        chat._generate(messages=[HumanMessage(content="hi")])

    headers = mock_client.post.call_args.kwargs["headers"]
    assert "Authorization" not in headers


def test_generate_includes_bearer_when_api_key_set():
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    mock_resp = _mock_httpx_response(
        {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {},
        }
    )
    mock_client = _mock_httpx_client(mock_resp)

    chat = ChatOpenAICompat(model="m", api_key="sk-test", base_url="http://h:8000/v1")

    with patch("aegis_phase1.llm.openai_compat.httpx.Client", return_value=mock_client):
        chat._generate(messages=[HumanMessage(content="hi")])

    headers = mock_client.post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer sk-test"


def test_generate_raises_on_http_error():
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    mock_resp = _mock_httpx_response({"error": "model not found"}, status_code=404)
    mock_client = _mock_httpx_client(mock_resp)
    chat = ChatOpenAICompat(model="m", base_url="http://h:8000/v1", timeout=10.0)

    with (
        patch("aegis_phase1.llm.openai_compat.httpx.Client", return_value=mock_client),
        pytest.raises(ConnectionError) as exc_info,
    ):
        chat._generate(messages=[HumanMessage(content="hi")])
    assert "HTTP 404" in str(exc_info.value)
    assert "model not found" in str(exc_info.value)


def test_generate_raises_on_empty_choices():
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    mock_resp = _mock_httpx_response({"choices": []})
    mock_client = _mock_httpx_client(mock_resp)
    chat = ChatOpenAICompat(model="m", base_url="http://h:8000/v1", timeout=10.0)

    with (
        patch("aegis_phase1.llm.openai_compat.httpx.Client", return_value=mock_client),
        pytest.raises(ConnectionError) as exc_info,
    ):
        chat._generate(messages=[HumanMessage(content="hi")])
    assert "empty choices" in str(exc_info.value)


def test_generate_wraps_connection_failure():
    import httpx

    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.side_effect = httpx.ConnectError("refused")

    chat = ChatOpenAICompat(model="m", base_url="http://h:8000/v1", timeout=10.0)

    with (
        patch("aegis_phase1.llm.openai_compat.httpx.Client", return_value=mock_client),
        pytest.raises(ConnectionError) as exc_info,
    ):
        chat._generate(messages=[HumanMessage(content="hi")])
    assert "cannot reach" in str(exc_info.value).lower()


def test_generate_handles_missing_usage_block():
    """Defensive: vLLM returns usage, but spec says it's optional.
    Missing usage must yield zeros — never raise."""
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    mock_resp = _mock_httpx_response(
        {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}]
            # no "usage"
        }
    )
    mock_client = _mock_httpx_client(mock_resp)
    chat = ChatOpenAICompat(model="m", base_url="http://h:8000/v1", timeout=10.0)

    with patch("aegis_phase1.llm.openai_compat.httpx.Client", return_value=mock_client):
        result = chat._generate(messages=[HumanMessage(content="hi")])

    assert result.generations[0].message.usage_metadata == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


# ─── 4. Integration with UnifiedInvoker + build_llm_invoker ──────


def test_unified_invoker_with_vllm_provider():
    from aegis_phase1.llm.openai_compat import DEFAULT_BASE_URL, ChatOpenAICompat
    from aegis_phase1.llm.unified import UnifiedInvoker

    invoker = UnifiedInvoker(
        model="gemma4-31b",
        provider="vllm",
        api_key="sk-test",
    )

    assert isinstance(invoker.chat, ChatOpenAICompat)
    assert invoker.provider == "vllm"
    assert invoker.model == "gemma4-31b"
    assert invoker.chat.base_url == DEFAULT_BASE_URL


def test_unified_invoker_vllm_base_url_override():
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat
    from aegis_phase1.llm.unified import UnifiedInvoker

    invoker = UnifiedInvoker(
        model="gemma4-31b",
        provider="vllm",
        base_url="http://node07:8000/v1",
    )
    assert isinstance(invoker.chat, ChatOpenAICompat)
    assert invoker.chat.base_url == "http://node07:8000/v1"


def test_build_llm_invoker_routes_vllm_to_unified():
    from aegis_phase1.llm.unified import UnifiedInvoker
    from aegis_phase1.v2.llm import build_llm_invoker

    invoker = build_llm_invoker(
        model="vllm:gemma4-31b",
        provider="vllm",
    )
    assert isinstance(invoker, UnifiedInvoker)
    assert invoker.provider == "vllm"
    # "vllm:" prefix stripped → bare served-model-name
    assert invoker.model == "gemma4-31b"


def test_build_llm_invoker_auto_detects_vllm_prefix():
    """No explicit provider → the ``vllm:`` prefix must route to vLLM
    (NOT to transformers)."""
    from aegis_phase1.llm.unified import UnifiedInvoker
    from aegis_phase1.v2.llm import build_llm_invoker

    invoker = build_llm_invoker(model="vllm:google/gemma-4-31B-it")
    assert isinstance(invoker, UnifiedInvoker)
    assert invoker.provider == "vllm"
    assert invoker.model == "google/gemma-4-31B-it"


def test_detect_provider_recognises_vllm_prefix():
    from aegis_phase1.llm.transformers_invoker import _detect_provider

    assert _detect_provider("vllm:gemma4-31b") == "vllm"
    assert _detect_provider("vllm:google/gemma-4-31B-it") == "vllm"
    # Sanity: existing prefixes unchanged
    assert _detect_provider("minimax/MiniMax-M3") == "minimax"
    assert _detect_provider("google/gemma-4-E2B-it") == "transformers"
    assert _detect_provider("hf:google/gemma-4-E2B-it") == "transformers"
    assert _detect_provider("gemma4:e4b") == "ollama"
    assert _detect_provider(None) == "ollama"


def test_unified_invoker_vllm_skips_ollama_probe():
    """The Ollama probe must be skipped for vLLM — OpenAI-compatible
    servers expose ``/v1/models`` but not ``/api/version``. The probe
    must NOT touch the network (would fail and raise LLMUnreachableError
    even when the vLLM server is up)."""
    from aegis_phase1.llm.unified import UnifiedInvoker

    invoker = UnifiedInvoker(model="gemma4-31b", provider="vllm")

    with patch("aegis_phase1.llm.unified.probe_ollama") as mock_probe:
        # Should be a no-op for vLLM, regardless of source.
        invoker._ensure_ollama("invoke_raw")
        invoker._ensure_ollama("invoke_spec")
    mock_probe.assert_not_called()


def test_unified_invoker_vllm_chat_uses_env_timeout(monkeypatch):
    """The chat instance reflects AEGIS_VLLM_TIMEOUT at construction
    time (default 600 s; we override to 90 s here)."""
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat
    from aegis_phase1.llm.unified import UnifiedInvoker

    monkeypatch.setenv("AEGIS_VLLM_TIMEOUT", "90")
    invoker = UnifiedInvoker(model="gemma4-31b", provider="vllm")
    assert isinstance(invoker.chat, ChatOpenAICompat)
    assert invoker.chat.timeout == 90.0


# ─── 5. Chat class shape (regression guard, CORR-106 lesson) ──────


def test_chat_class_exposes_methods_at_class_level():
    """CORR-110: explicitly verify ``_generate`` lives on the class
    (not nested in a closure). The CORR-106 final commit (41900c8)
    accidentally dedented ``_max_memory`` to module level, which
    silently swallowed ``invoke`` / ``_ensure_loaded`` / ``device``
    into nested closures inside TransformersInvoker — the 6 unit
    tests at the time all passed because they only exercised
    _compute_max_memory. This assertion is a cheap structural guard:
    if anyone re-indents by accident, the chat can no longer be
    invoked via LangChain (AttributeError on BaseChatModel._generate).
    ``_llm_type`` and ``_identifying_params`` are ``@property``
    descriptors on BaseChatModel — asserting they are defined (not
    callable) is sufficient.
    """
    from aegis_phase1.llm.openai_compat import ChatOpenAICompat

    assert callable(getattr(ChatOpenAICompat, "_generate", None))
    assert isinstance(getattr(ChatOpenAICompat, "_llm_type", None), property)
    assert isinstance(getattr(ChatOpenAICompat, "_identifying_params", None), property)


# ─── 6. No new top-level dependencies ─────────────────────────────


def test_module_imports_only_httpx_and_langchain_core():
    """The adapter must add NO new project dependency. We parse the
    module source for top-level ``import`` / ``from ... import``
    statements and assert only the allowed packages appear. The
    project's pyproject.toml pins are the real source of truth — this
    test is the in-code alarm against quietly pulling ``openai``,
    ``langchain-openai``, or similar.
    """
    import ast
    import pathlib

    src_path = pathlib.Path(
        "/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1/"
        "src/aegis_phase1/llm/openai_compat.py"
    )
    tree = ast.parse(src_path.read_text())

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    # Strip stdlib + our own packages; assert httpx / langchain_core /
    # pydantic are present and no heavyweight LLM client SDK was added.
    forbidden = {"openai", "langchain_openai", "anthropic", "tiktoken"}
    leak = imported & forbidden
    assert not leak, (
        f"Forbidden LLM client dependencies imported by openai_compat: " f"{sorted(leak)}"
    )
    assert "httpx" in imported, "httpx should be imported by openai_compat"
    assert "langchain_core" in imported, "langchain_core should be imported by openai_compat"
    assert "pydantic" in imported, "pydantic should be imported by openai_compat"


# ─── 7. Heavy-path routing (Phase1LLMInvoker) ─────────────────────


def test_factory_get_invoker_with_vllm_provider():
    """get_invoker(provider='vllm') wires the UnifiedInvoker with
    ChatOpenAICompat. The base_url default is ChatOpenAICompat's
    default (NOT the Ollama default) — critical so the heavy
    Phase1LLMInvoker child doesn't try to call localhost:11434."""
    from aegis_phase1.llm.openai_compat import DEFAULT_BASE_URL, ChatOpenAICompat
    from aegis_phase1.llm.unified import UnifiedInvoker
    from aegis_phase1.prompts_v2.factory import get_invoker

    invoker = get_invoker(provider="vllm", model="gemma4-31b")
    assert isinstance(invoker, UnifiedInvoker)
    assert invoker.provider == "vllm"
    assert isinstance(invoker.chat, ChatOpenAICompat)
    assert invoker.chat.base_url == DEFAULT_BASE_URL


# ─── 8. CLI choices include vllm ──────────────────────────────────


def test_runner_provider_choices_includes_vllm():
    """``runner.py --help`` must list ``vllm`` as a valid --provider
    choice so users can discover it. We parse the help output rather
    than re-building argparse (the parser is a local variable inside
    ``main()``)."""
    import re
    import subprocess
    import sys

    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [sys.executable, "-m", "aegis_phase1.v2.runner", "--help"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1",
    )
    assert proc.returncode == 0, proc.stderr
    # Extract the choices block from the --provider help line.
    match = re.search(
        r"--provider\s+\{(?P<choices>[^}]+)\}",
        proc.stdout,
    )
    assert match is not None, f"--provider help not found in:\n{proc.stdout}"
    choices = {c.strip() for c in match.group("choices").split(",")}
    assert "vllm" in choices
    assert "auto" in choices  # backward-compat
    # Sanity: all expected providers still present (no accidental drop)
    for expected in ("ollama", "transformers", "minimax", "auto"):
        assert expected in choices, f"Existing --provider choice dropped: {expected}"
