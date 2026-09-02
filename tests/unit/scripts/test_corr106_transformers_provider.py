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


# ────────────────────────────────────────────────────────────────────
# 5. Follow-ups from JOB 1866405 (the actual scout run)
# ────────────────────────────────────────────────────────────────────


def test_compute_max_memory_enumerates_all_devices():
    """Pure helper: pre-fix only included device 0, leading to a
    single-GPU OOM on the 31B scout (JOB 1866405)."""
    inv = TransformersInvoker(model_id="fake/model")
    budget = inv._compute_max_memory(n_devices=3, device_total_bytes=40 * 1024**3, utilization=0.9)
    assert set(budget.keys()) == {0, 1, 2, "cpu"}
    for idx in (0, 1, 2):
        gib = float(budget[idx].rstrip("GiB"))
        # 40 GiB * 0.9 - 0.2 GiB safety ≈ 35.8 GiB per GPU.
        assert 34 <= gib <= 36, f"GPU {idx} budget {gib}GiB outside expected range"
    assert budget["cpu"] == "30GiB"


def test_compute_max_memory_below_one_floor():
    """Edge case: tiny GPU + low utilization → budget clamped to 1 GiB."""
    inv = TransformersInvoker(model_id="fake/model")
    budget = inv._compute_max_memory(n_devices=1, device_total_bytes=2 * 1024**3, utilization=0.5)
    # 2 GiB * 0.5 - 0.2 = 0.8 GiB → clamped to 1.0 GiB
    assert budget[0] == "1.0GiB"


def test_aegis_max_new_tokens_env_var(monkeypatch):
    """The SBATCH sets AEGIS_MAX_NEW_TOKENS=16384 (qwen3.8 generated
    122 599-token outputs; default 1024 would truncate every call)."""
    monkeypatch.setenv("AEGIS_MAX_NEW_TOKENS", "16384")
    inv = TransformersInvoker(model_id="fake/model")
    assert inv.max_new_tokens == 16384


def test_aegis_max_new_tokens_explicit_arg_wins(monkeypatch):
    """Constructor kwarg overrides env var."""
    monkeypatch.setenv("AEGIS_MAX_NEW_TOKENS", "16384")
    inv = TransformersInvoker(model_id="fake/model", max_new_tokens=2048)
    assert inv.max_new_tokens == 2048


def test_aegis_max_new_tokens_default_when_no_env(monkeypatch):
    monkeypatch.delenv("AEGIS_MAX_NEW_TOKENS", raising=False)
    inv = TransformersInvoker(model_id="fake/model")
    assert inv.max_new_tokens == TransformersInvoker.DEFAULT_MAX_NEW_TOKENS


# ────────────────────────────────────────────────────────────────────
# 6. factory.get_invoker(provider="transformers") — CORR-106 follow-up
# ────────────────────────────────────────────────────────────────────


def test_factory_transformers_returns_phase1_invoker(monkeypatch):
    """Post-CORR-106 (JOB 1867060 fix): factory must return a full
    Phase1LLMInvoker with loaders, not a bare TransformersInvoker.
    The previous version returned a bare TransformersInvoker, which
    made invoker_to_executor() fail with 'Invoker is missing required
    dependencies: [prompt_loader, catalog_loader, validator,
    llm_logger, format_logger]'.

    Verification: the returned object has the loaders AND a
    transformers provider; its heavy-path (Phase1LLMInvoker.invoke_spec)
    then routes through TransformersChat.
    """
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    from aegis_phase1.prompts_v2.factory import get_invoker

    inv = get_invoker(model="fake/model", provider="transformers")
    # Must have the loaders that invoker_to_executor() needs.
    for attr in ("prompts", "catalogs", "validator", "llm_logger", "format_logger"):
        assert getattr(inv, attr, None) is not None, (
            f"factory transformers result missing required loader: {attr}"
        )
    assert inv.provider == "transformers"
    assert inv.model == "fake/model"


def test_factory_transformers_requires_explicit_model(monkeypatch):
    """Without an explicit model kwarg, factory raises (Ollama defaults
    do not apply to HF path)."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    from aegis_phase1.prompts_v2.factory import get_invoker

    with pytest.raises(ValueError, match="explicit `model` kwarg"):
        get_invoker(provider="transformers")


def test_orchestrator_phase1b_executor_supports_transformers(monkeypatch):
    """CORR-106 follow-up: when ``for_phase_1b=True`` the orchestrator
    must NOT short-circuit the transformers provider. Pre-fix, the
    transformers short-circuit ran unconditionally, so ``run_phase_1b``
    saw ``Phase 1B RATIONALE skipped`` (JOB 1866845 symptom).

    We assert this by patching the factory to return a real
    Phase1LLMInvoker and verifying the executor is built (not None).
    """
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")

    from aegis_phase1.llm.transformers_invoker import TransformersInvoker
    from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator(
        llm_invoker=TransformersInvoker(model_id="fake/model"),
    )
    # Sanity: without for_phase_1b, transformers short-circuits (None).
    assert orch._get_phase1_executor() is None

    # Patch the factory to return a stub invoker and the
    # invoker_to_executor helper to return a sentinel executor. The
    # point is to confirm the orchestrator's transformers guard is
    # bypassed when for_phase_1b=True.
    from aegis_phase1.prompts_v2 import factory as factory_mod
    from aegis_phase1.prompts_v2 import phase1_executor as exec_mod

    sentinel_executor = Phase1Executor.__new__(Phase1Executor)
    sentinel_executor.invoker = None  # not used; we only assert identity

    class _StubInv:
        pass

    monkeypatch.setattr(factory_mod, "get_invoker", lambda **kw: _StubInv())
    monkeypatch.setattr(exec_mod, "invoker_to_executor", lambda inv: sentinel_executor)

    result = orch._get_phase1_executor(for_phase_1b=True)
    assert result is sentinel_executor, (
        f"for_phase_1b=True should NOT short-circuit on transformers; "
        f"got {result!r} (None = the guard fired, sentinel = path executed)"
    )
