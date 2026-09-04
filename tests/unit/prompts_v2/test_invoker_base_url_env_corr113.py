"""CORR-113: base_url resolution at Phase1LLMInvoker.__init__ level.

KG-eval jobs on Deucalion serve Ollama on a per-JOB port, exported via
OLLAMA_BASE_URL (or OLLAMA_HOST). The factory path already honoured
OLLAMA_BASE_URL (CORR-069 S3); this covers the direct-constructor path
and the OLLAMA_HOST fallback.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker


def _make(**kwargs) -> Phase1LLMInvoker:
    return Phase1LLMInvoker(
        prompt_loader=MagicMock(),
        catalog_loader=MagicMock(),
        llm_logger=MagicMock(),
        format_logger=MagicMock(),
        **kwargs,
    )


def test_explicit_base_url_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://from-env:12345")
    invoker = _make(base_url="http://explicit:9999")
    assert invoker.base_url == "http://explicit:9999"


def test_ollama_base_url_env_used_without_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://job-port:11434")
    invoker = _make()
    assert invoker.base_url == "http://job-port:11434"


def test_ollama_host_env_gets_scheme_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "node07:11434")
    invoker = _make()
    assert invoker.base_url == "http://node07:11434"


def test_ollama_host_env_with_scheme_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "http://node07:11434")
    invoker = _make()
    assert invoker.base_url == "http://node07:11434"


def test_no_env_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    invoker = _make()
    assert invoker.base_url == Phase1LLMInvoker.DEFAULT_BASE_URL


def test_base_url_env_ignored_for_minimax(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://job-port:11434")
    invoker = _make(provider="minimax")
    assert "job-port" not in invoker.base_url
