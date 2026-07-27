"""Smoke tests for CORR-062 S1 v4 + v5 fixes (real-model dispatcher chain).

Reference: ``execution/CORR-062-S1-RUN-LOG.md``

These tests validate the two fixes that exposed the S1 v3 → v4 → v5
regression chain, **without** contacting Ollama or loading any model:

  1. CORR-062 S1 v4 fix (commit 280bdd0):
     ``UnifiedInvoker.invoke()`` accepts and forwards the ``state=`` kwarg
     to ``invoke_spec()`` (which in turn forwards it to the heavy
     ``Phase1LLMInvoker`` child). Previously the dispatcher signature
     rejected ``state=`` with TypeError on every S1 call site that was
     rewired during CORR-061 S3b.

  2. CORR-062 S1 v5 fix (commit 8465140):
     ``Phase1LLMInvoker.invoke()`` handles ``config["callbacks"]`` being
     a ``BaseCallbackManager`` (LangChain ``RunnableConfig`` shape set
     by ``with_config()`` / ``bind()`` in the LangGraph executor path)
     — not just a plain list. The previous code did
     ``list(config.get("callbacks") or [])`` and crashed with
     ``TypeError: 'CallbackManager' object is not iterable`` on the v4
     run.

Both fixes are non-trivial (the dispatcher is polymorphic on ``inputs``
type, the callback container can be one of four shapes), so we want a
test that exercises the **exact** call chain from the v4 crash report,
including the CallbackManager-in-config path. Runs in < 1s.

Test pattern: build a real ``Phase1LLMInvoker`` with stubbed loaders
and patch ``ChatOllama`` at the source module (per the CORR-011
convention in ``test_langfuse_callback_corr011.py``), so the actual
v5 fix code runs and we can verify the resulting config shape.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest


# ─── Helpers (mirrors the CORR-011 test pattern) ───────────────────


class _FakeAIMessage:
    """Minimal stand-in for ``langchain_core.messages.AIMessage``."""

    def __init__(
        self,
        content: str = "{}",
        response_metadata: dict | None = None,
        usage_metadata: dict | None = None,
    ) -> None:
        self.content = content
        self.response_metadata = response_metadata or {
            "model": "gemma4:e2b",
            "prompt_eval_count": 100,
            "eval_count": 50,
            "done": True,
        }
        self.usage_metadata = usage_metadata or {}


@contextmanager
def _patched_chat_ollama(response: _FakeAIMessage | None = None):
    """Patch ``ChatOllama`` so ``_attempt`` short-circuits at the chat.

    The actual ``Phase1LLMInvoker.invoke`` runs (so the v5 fix code
    executes), but the LLM call is replaced with a MagicMock that
    returns ``response`` immediately. Yields the mock instance for
    call-introspection.
    """
    fake = response or _FakeAIMessage()
    with patch("aegis_phase1.prompts_v2.invoker.ChatOllama") as MockChatOllama:
        mock_instance = MagicMock(name="ChatOllamaInstance")
        mock_instance.invoke.return_value = fake
        MockChatOllama.return_value = mock_instance
        yield mock_instance


def _build_invoker(*, handler: object | None = None) -> "Phase1LLMInvoker":  # type: ignore[name-defined]  # noqa: F821
    """Build a real ``Phase1LLMInvoker`` with stubbed loaders (no Ollama)."""
    from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker

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


def _make_callback_manager(handlers: list | None = None) -> MagicMock:
    """Build a stand-in for ``langchain_core.callbacks.BaseCallbackManager``.

    The real ``BaseCallbackManager`` exposes ``.handlers`` and
    ``.inheritable_handlers`` as list attributes. We only need those
    two attributes for the v5 fix code path.
    """
    cm = MagicMock(name="BaseCallbackManager")
    cm.handlers = list(handlers or [])
    cm.inheritable_handlers = []
    return cm


# ─── 1. state= is forwarded through the dispatcher ──────────────────


def test_invoke_forwards_state_kwarg_to_invoke_spec():
    """CORR-062 S1 v4: invoke(spec_id, dict, state=X) forwards state=X
    to invoke_spec, which in turn passes it to the heavy child.
    """
    from aegis_phase1.llm.unified import UnifiedInvoker

    invoker = UnifiedInvoker()
    invoker.invoke_spec = MagicMock(return_value={"status": "OK"})  # type: ignore[method-assign]
    invoker.invoke_raw = MagicMock()  # type: ignore[method-assign]

    state_obj = {"per_spec_markdown": {}, "case_id": "case1-tinytask"}
    result = invoker.invoke("P1B-LLM-01-INTERPRETATION", {"x": 1}, state=state_obj)

    # The fix: state is forwarded to invoke_spec, not dropped
    invoker.invoke_spec.assert_called_once_with(
        "P1B-LLM-01-INTERPRETATION", {"x": 1}, config=None, state=state_obj
    )
    invoker.invoke_raw.assert_not_called()
    assert result == {"status": "OK"}


def test_invoke_dispatcher_signature_accepts_state_kwarg():
    """Sanity check: ``invoke`` signature includes ``state=`` kwarg.

    If somebody removes it, this test catches it before S1.
    """
    import inspect

    from aegis_phase1.llm.unified import UnifiedInvoker

    sig = inspect.signature(UnifiedInvoker.invoke)
    assert "state" in sig.parameters, (
        f"state= kwarg missing from UnifiedInvoker.invoke signature: {sig}"
    )
    # Must be keyword-only (after the *), to keep backwards compat with
    # the existing invoke_raw callers that pass positional feedback=.
    assert sig.parameters["state"].kind == inspect.Parameter.KEYWORD_ONLY


# ─── 2. CallbackManager-in-config is handled by heavy.invoke ────────


def test_heavy_invoke_does_not_crash_with_callback_manager():
    """CORR-062 S1 v5 regression guard: Phase1LLMInvoker.invoke() must
    not raise TypeError when config['callbacks'] is a BaseCallbackManager.

    The v4 run crashed with::

        File ".../prompts_v2/invoker.py", line 221, in invoke
            existing = list(config.get("callbacks") or [])
        TypeError: 'CallbackManager' object is not iterable

    This test wires the full LangGraph-shaped config (callbacks as a
    BaseCallbackManager + Langfuse handler) and asserts:

    1. The call reaches the chat (i.e. no TypeError aborted the
       dispatcher — the v5 fix worked).
    2. The chat received a **list** of callbacks (the v5 fix flattens
       the CallbackManager before passing downstream).
    3. Both the pre-existing handler and the Langfuse handler are
       preserved in the list (idempotent-attach semantics).

    The validator is mocked and rejects the response, so the final
    ``status`` is ``FAILED_AFTER_RETRIES`` — that's the expected
    downstream behaviour and not what we're testing here.
    """
    existing_handler = MagicMock(name="ExistingHandler")
    cm = _make_callback_manager(handlers=[existing_handler])
    langfuse_handler = MagicMock(name="LangfuseHandler")
    invoker = _build_invoker(handler=langfuse_handler)

    with _patched_chat_ollama() as mock_chat:
        # If the v5 fix was missing, this would raise TypeError.
        invoker.invoke(
            "P1B-LLM-01-INTERPRETATION",
            {"x": 1},
            config={"callbacks": cm},
        )

    # 1. Chat was actually reached (no TypeError)
    assert mock_chat.invoke.call_count >= 1
    call_kwargs = mock_chat.invoke.call_args.kwargs
    assert "config" in call_kwargs, (
        f"Expected config kwarg on chat.invoke; got {call_kwargs!r}"
    )
    # 2. Callbacks was flattened to a list
    assert isinstance(call_kwargs["config"]["callbacks"], list), (
        f"Expected callbacks to be flattened to a list; got {type(call_kwargs['config']['callbacks'])}"
    )
    # 3. Both handlers preserved
    assert existing_handler in call_kwargs["config"]["callbacks"]
    assert langfuse_handler in call_kwargs["config"]["callbacks"]


def test_heavy_invoke_does_not_crash_with_callback_manager_and_state():
    """End-to-end smoke: Phase1LLMInvoker.invoke() with state= AND
    CallbackManager-shaped config (the exact shape from
    phase1_executor.py:run in the v4 crash) must complete the
    dispatcher path without TypeError.
    """
    cm = _make_callback_manager(handlers=[])
    state_obj = {"per_spec_markdown": {}}
    invoker = _build_invoker(handler=MagicMock(name="LangfuseHandler"))

    with _patched_chat_ollama() as mock_chat:
        # If the v4 fix was missing, this would raise TypeError on the
        # state= kwarg. If the v5 fix was missing, on the CallbackManager.
        invoker.invoke(
            "P1B-LLM-01-INTERPRETATION",
            {"x": 1},
            state=state_obj,
            config={"callbacks": cm},
        )

    # Chat was reached → both v4 (state=) and v5 (CallbackManager) fixes work
    assert mock_chat.invoke.call_count >= 1


# ─── 3. Backwards-compat for the legacy list path ───────────────────


def test_heavy_invoke_handles_list_in_config_backwards_compat():
    """Legacy path: config['callbacks'] as a plain list still works
    (with Langfuse handler attached — same path that previously worked
    in v3 and before the v4 run exposed the CallbackManager issue).
    """
    existing_handler = MagicMock(name="ExistingHandler")
    invoker = _build_invoker(handler=MagicMock(name="LangfuseHandler"))

    with _patched_chat_ollama() as mock_chat:
        invoker.invoke(
            "P1B-LLM-01-INTERPRETATION",
            {"x": 1},
            config={"callbacks": [existing_handler]},
        )

    assert mock_chat.invoke.call_count >= 1
    call_kwargs = mock_chat.invoke.call_args.kwargs
    assert existing_handler in call_kwargs["config"]["callbacks"]


def test_heavy_invoke_handles_no_config():
    """Defensive: no config at all still works (no Langfuse handler
    attached → v5 fix branch is skipped, callbacks stays as None).
    """
    invoker = _build_invoker(handler=None)

    with _patched_chat_ollama() as mock_chat:
        invoker.invoke("P1B-LLM-01-INTERPRETATION", {"x": 1})

    assert mock_chat.invoke.call_count >= 1
