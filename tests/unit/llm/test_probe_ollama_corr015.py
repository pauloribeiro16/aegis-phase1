"""Tests for the Ollama health probe + retry-storm suppression (AEGIS-P1-CORR-015).

Reference: ``docs/SPEC-observability.md`` §1 (C4) + §6 (Phase 5).

Goal:
    When Ollama is unreachable, the invoker must short-circuit BEFORE the
    chat call so the retry loop cannot spam the JSONL log with
    ``python_error`` lines (was 788 vs 60 llm_call). The probe is cached
    per-instance for ``_PROBE_TTL_SECONDS`` to avoid re-probing on every
    call when many invocations happen in sequence.

Behaviour contracts verified here:

  1. ``probe_ollama`` returns True on a 200 response.
  2. ``probe_ollama`` returns False on ``ConnectionRefusedError``.
  3. ``probe_ollama`` returns False on ``TimeoutError``.
  4. ``probe_ollama`` returns False on ``URLError``.
  5. ``invoke_raw`` raises ``OllamaUnreachableError`` when probe fails.
  6. ``invoke_raw`` does NOT call ``chat.invoke`` when probe fails (no retry).
  7. Probe result is cached within the TTL window (subsequent calls skip probe).
  8. ``OllamaUnreachableError`` is exported from ``aegis_phase1.llm.unified``.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ─── Helpers ──────────────────────────────────────────────────────────


class _FakeAIMessage:
    """Minimal stand-in for ``langchain_core.messages.AIMessage``."""

    def __init__(self, content: str = "ok") -> None:
        self.content = content
        self.response_metadata: dict = {}
        self.usage_metadata: dict = {}


def _patched_chat() -> tuple[MagicMock, MagicMock]:
    """Patch ``langchain_ollama.ChatOllama``; return ``(MockClass, mock_instance)``."""
    MockChatOllama = MagicMock(name="ChatOllama")
    mock_instance = MagicMock(name="ChatOllamaInstance")
    mock_instance.invoke.return_value = _FakeAIMessage()
    MockChatOllama.return_value = mock_instance
    return MockChatOllama, mock_instance


# ─── 1. probe_ollama — happy path ─────────────────────────────────────


def test_probe_ollama_returns_true_when_reachable():
    """HTTP 200 on /api/version → probe returns True."""
    from aegis_phase1.llm.unified import probe_ollama

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", mock_urlopen):
        result = probe_ollama("http://localhost:11434")

    assert result is True


# ─── 2-4. probe_ollama — failure modes ────────────────────────────────


def test_probe_ollama_returns_false_on_connection_refused():
    """ConnectionRefusedError → False (does not raise)."""
    from aegis_phase1.llm.unified import probe_ollama

    with patch(
        "urllib.request.urlopen",
        side_effect=ConnectionRefusedError("[Errno 111] Connection refused"),
    ):
        result = probe_ollama("http://localhost:11434")

    assert result is False


def test_probe_ollama_returns_false_on_timeout():
    """TimeoutError → False (does not raise)."""
    from aegis_phase1.llm.unified import probe_ollama

    with patch("urllib.request.urlopen", side_effect=TimeoutError):
        result = probe_ollama("http://localhost:11434")

    assert result is False


def test_probe_ollama_returns_false_on_url_error():
    """URLError → False (does not raise)."""
    from urllib.error import URLError

    from aegis_phase1.llm.unified import probe_ollama

    with patch("urllib.request.urlopen", side_effect=URLError("name or service not known")):
        result = probe_ollama("http://localhost:11434")

    assert result is False


# ─── 5. invoke_raw — short-circuit on probe failure ───────────────────


def test_invoke_raw_raises_unreachable_when_probe_fails():
    """When probe_ollama returns False, invoke_raw raises OllamaUnreachableError."""
    MockChatOllama, mock_instance = _patched_chat()
    with (
        patch("langchain_ollama.ChatOllama", MockChatOllama),
        patch("aegis_phase1.llm.unified.probe_ollama", return_value=False) as mock_probe,
    ):
        from aegis_phase1.llm.unified import OllamaUnreachableError, UnifiedInvoker

        invoker = UnifiedInvoker(model="gemma4:e4b")

        with pytest.raises(OllamaUnreachableError) as exc_info:
            invoker.invoke_raw("hi")

    assert exc_info.value.base_url == "http://localhost:11434"
    assert exc_info.value.source == "invoke_raw"
    assert "Ollama not reachable" in str(exc_info.value)
    mock_probe.assert_called_once_with("http://localhost:11434")


# ─── 6. invoke_raw — no chat call when probe fails ────────────────────


def test_invoke_raw_does_not_retry_when_unreachable():
    """The chat.invoke must NEVER be called when the probe fails (no spam)."""
    MockChatOllama, mock_instance = _patched_chat()
    with (
        patch("langchain_ollama.ChatOllama", MockChatOllama),
        patch("aegis_phase1.llm.unified.probe_ollama", return_value=False),
    ):
        from aegis_phase1.llm.unified import OllamaUnreachableError, UnifiedInvoker

        invoker = UnifiedInvoker(model="gemma4:e4b")

        with pytest.raises(OllamaUnreachableError):
            invoker.invoke_raw("hi")

    mock_instance.invoke.assert_not_called()


# ─── 7. Probe result is cached within the TTL window ──────────────────


def test_probe_cached_within_window():
    """Two invoke_raw calls within TTL → probe_ollama called once (cached)."""
    MockChatOllama, _mock_instance = _patched_chat()
    with (
        patch("langchain_ollama.ChatOllama", MockChatOllama),
        patch("aegis_phase1.llm.unified.probe_ollama", return_value=True) as mock_probe,
    ):
        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker(model="gemma4:e4b")
        invoker.invoke_raw("first")
        invoker.invoke_raw("second")

    assert mock_probe.call_count == 1, (
        f"Expected probe called once within TTL window; got {mock_probe.call_count}"
    )


def test_probe_rechecked_after_ttl_expires():
    """After the TTL window, probe_ollama is called again on next invoke."""
    MockChatOllama, _mock_instance = _patched_chat()
    with (
        patch("langchain_ollama.ChatOllama", MockChatOllama),
        patch("aegis_phase1.llm.unified.probe_ollama", return_value=True) as mock_probe,
        patch("aegis_phase1.llm.unified._PROBE_TTL_SECONDS", 0.0),
    ):
        from aegis_phase1.llm.unified import UnifiedInvoker

        invoker = UnifiedInvoker(model="gemma4:e4b")
        invoker.invoke_raw("first")
        invoker.invoke_raw("second")

    assert mock_probe.call_count == 2


# ─── 8. OllamaUnreachableError is exported ────────────────────────────


def test_probe_ollama_exception_exported():
    """OllamaUnreachableError is importable from aegis_phase1.llm.unified."""
    from aegis_phase1.llm import unified as unified_mod
    from aegis_phase1.llm.unified import OllamaUnreachableError

    assert hasattr(unified_mod, "OllamaUnreachableError")
    assert "OllamaUnreachableError" in unified_mod.__all__
    assert issubclass(OllamaUnreachableError, RuntimeError)


def test_ollama_unreachable_error_carries_attributes():
    """OllamaUnreachableError exposes .base_url and .source attributes."""
    from aegis_phase1.llm.unified import OllamaUnreachableError

    exc = OllamaUnreachableError("http://example:11434", "unit-test")
    assert exc.base_url == "http://example:11434"
    assert exc.source == "unit-test"
    assert "http://example:11434" in str(exc)
    assert "unit-test" in str(exc)


def test_probe_ollama_helper_exported():
    """probe_ollama is part of the public API of aegis_phase1.llm.unified."""
    from aegis_phase1.llm import unified as unified_mod
    from aegis_phase1.llm.unified import probe_ollama

    assert "probe_ollama" in unified_mod.__all__
    assert callable(probe_ollama)