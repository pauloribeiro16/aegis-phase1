"""CORR-106 — tests for the transformers-provider plumbing.

Stdlib-only. Tests:

1. ``TransformersInvoker.provider`` is "transformers" (class attribute).
2. ``build_llm_invoker(provider="transformers")`` returns a
   TransformersInvoker with that attribute reachable via getattr (the
   orchestrator's discovery mechanism).
3. ``TransformersChat`` shim exposes ``.model`` + ``.base_url`` and
   routes ``.invoke([SystemMessage, HumanMessage])`` to the underlying
   invoker with ``system_prompt=`` set on the system message.
4. ``UnifiedInvoker._ensure_ollama`` is a no-op when ``provider != "ollama"``
   (it would otherwise probe localhost:11434 and fail-loud).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from aegis_phase1.llm.transformers_invoker import (
    TransformersChat,
    TransformersInvoker,
)
from aegis_phase1.llm.unified import UnifiedInvoker
from aegis_phase1.v2.llm import build_llm_invoker

# Use the shared venv (where the LLM deps live) — these tests import
# the LLM modules directly, so we need them on sys.path.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

# Avoid HF model download attempts in the test environment.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


# ────────────────────────────────────────────────────────────────────
# 1. Class attribute on TransformersInvoker
# ────────────────────────────────────────────────────────────────────


def test_transformers_invoker_has_provider_class_attr():
    """Without this class attr, the orchestrator's getattr(...,
    'provider', 'ollama') falls back to 'ollama' and the transformers
    branch is silently skipped — the JOB 1846584 failure mode."""
    assert TransformersInvoker.provider == "transformers"


# ────────────────────────────────────────────────────────────────────
# 2. build_llm_invoker honouring provider='transformers'
# ────────────────────────────────────────────────────────────────────


def test_build_llm_invoker_returns_transformers():
    """Auto-detect via ``model`` would also pick this up (HF Hub
    convention: contains '/'), but explicit provider is the contract."""
    inv = build_llm_invoker(model="fake/model", provider="transformers")
    assert isinstance(inv, TransformersInvoker)
    assert inv.provider == "transformers"
    assert inv.model_id == "fake/model"


# ────────────────────────────────────────────────────────────────────
# 3. TransformersChat shim interface
# ────────────────────────────────────────────────────────────────────


class _FakeMessage:
    """Minimal duck-typed LangChain message with ``.content`` and ``.type``."""

    def __init__(self, role: str, content: str) -> None:
        self.type = role
        self.content = content


class _RecorderInvoker(TransformersInvoker):
    """Records the (prompt, feedback, system_prompt) of the last call
    without doing any model work."""

    last_call: tuple[str, str, str | None] | None = None

    def __init__(self, canned_response: str = "FAKE_RESPONSE") -> None:
        # Skip the real __init__ — no model load.
        self.model_id = "fake/model"
        self.model = "fake/model"
        self._canned = canned_response
        self.provider = "transformers"
        self.max_new_tokens = 1024

    def invoke(self, prompt, feedback="", *, system_prompt=None, config=None):
        type(self).last_call = (prompt, feedback, system_prompt)
        return {"raw": self._canned, "status": "OK", "usage": {}}


def test_transformers_chat_routes_system_and_user():
    rec = _RecorderInvoker()
    chat = TransformersChat(rec)
    assert chat.model == "fake/model"
    assert chat.base_url == "hf://fake/model"

    msgs = [
        _FakeMessage("system", "SYS_TEXT"),
        _FakeMessage("human", "USER_TEXT"),
    ]
    out = chat.invoke(msgs)
    # The shim returns an object with `.content`
    assert out.content == "FAKE_RESPONSE"
    # system_prompt was forwarded as the system message
    assert _RecorderInvoker.last_call == ("USER_TEXT", "", "SYS_TEXT")


def test_transformers_chat_user_only_fallback():
    rec = _RecorderInvoker()
    chat = TransformersChat(rec)
    msgs = [_FakeMessage("human", "ONLY_USER")]
    chat.invoke(msgs)
    assert _RecorderInvoker.last_call == ("ONLY_USER", "", None)


# ────────────────────────────────────────────────────────────────────
# 4. UnifiedInvoker._ensure_ollama must skip when provider != ollama
# ────────────────────────────────────────────────────────────────────


def test_ensure_ollama_noop_when_provider_is_transformers(monkeypatch):
    """If _ensure_ollama probed localhost:11434 when provider='transformers',
    it would always fail and abort the run before the model is ever
    asked to load (JOB 1846584 symptom)."""
    # Build a UnifiedInvoker with provider='transformers' — does NOT
    # touch the network (no Chat* class is constructed).
    inv = UnifiedInvoker(
        model="fake/model",
        base_url="http://localhost:11434",
        provider="transformers",
    )
    assert inv.provider == "transformers"
    # The probe function (probe_ollama) would raise LLMUnreachableError
    # if called here; we want the early-return to prevent that.
    from aegis_phase1.llm.unified import LLMUnreachableError

    try:
        inv._ensure_ollama("test_source")
    except LLMUnreachableError as exc:
        pytest.fail(
            f"_ensure_ollama should be a no-op for provider='transformers', "
            f"but raised: {exc}"
        )


def test_ensure_ollama_still_runs_for_ollama(monkeypatch):
    """Regression guard: the no-op must ONLY apply when provider != ollama.
    The default path (Ollama) must still probe — otherwise we lose the
    fast-fail that saved CORR-015."""
    inv = UnifiedInvoker(provider="ollama")

    # Force the probe to fail: replace the cache so the next call actually
    # executes the network probe. We patch ``probe_ollama`` to return
    # False so we can verify the probe ran without any network I/O.
    from aegis_phase1.llm import unified as unified_mod

    monkeypatch.setattr(unified_mod, "probe_ollama", lambda url: False)
    inv._ollama_reachable = None  # bust cache
    inv._ollama_probe_ts = 0.0

    from aegis_phase1.llm.unified import LLMUnreachableError

    with pytest.raises(LLMUnreachableError):
        inv._ensure_ollama("test_source")
