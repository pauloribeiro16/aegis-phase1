"""Tests for AEGIS-P1-CORR-019: CallbackManager handling in _merge_handler_into_config.

Reference: docs/SPEC-observability.md + regression report from real run.

Bug pre-CORR-019:
    LangGraph injects a ``langchain_core.callbacks.manager.CallbackManager``
    (not a list) into ``config["callbacks"]`` when invoking a sub-graph.
    Our ``_merge_handler_into_config`` did ``list(cfg.get("callbacks") or [])``
    which raised ``TypeError: 'CallbackManager' object is not iterable``.

Fix:
    Normalize the callbacks value: list → as-is; CallbackManager → use its
    ``.handlers`` attribute; single handler object → wrap in list. Then
    append the Langfuse handler (if any) and return a dict whose
    ``callbacks`` key is always a plain list.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.callbacks import CallbackManager

from aegis_phase1.llm.unified import _merge_handler_into_config


def test_callbacks_none_returns_empty_list():
    cfg = _merge_handler_into_config(handler=None, config=None)
    assert cfg["callbacks"] == []


def test_callbacks_list_is_preserved():
    handler_a = MagicMock(name="handler_a")
    handler_b = MagicMock(name="handler_b")
    cfg = _merge_handler_into_config(
        handler=None, config={"callbacks": [handler_a, handler_b]}
    )
    assert cfg["callbacks"] == [handler_a, handler_b]


def test_langfuse_handler_appended_to_existing_list():
    handler_a = MagicMock(name="handler_a")
    langfuse = MagicMock(name="langfuse")
    cfg = _merge_handler_into_config(
        handler=langfuse, config={"callbacks": [handler_a]}
    )
    assert cfg["callbacks"] == [handler_a, langfuse]


def test_callbackmanager_is_normalized_to_handlers_list():
    """REGRESSION: LangGraph injects CallbackManager; we must not crash."""
    handler_a = MagicMock(name="handler_a")
    cm = CallbackManager([handler_a])
    langfuse = MagicMock(name="langfuse")
    cfg = _merge_handler_into_config(handler=langfuse, config={"callbacks": cm})
    assert isinstance(cfg["callbacks"], list)
    assert handler_a in cfg["callbacks"]
    assert langfuse in cfg["callbacks"]
    assert len(cfg["callbacks"]) == 2


def test_empty_callbackmanager_returns_list_with_just_handler():
    cm = CallbackManager([])
    langfuse = MagicMock(name="langfuse")
    cfg = _merge_handler_into_config(handler=langfuse, config={"callbacks": cm})
    assert cfg["callbacks"] == [langfuse]


def test_callbackmanager_without_handlers_attr_falls_back_to_single_item():
    """A CallbackManager without a .handlers attr (e.g. broken mock) — wrap raw."""

    class FakeCM:
        pass

    raw = FakeCM()
    langfuse = MagicMock(name="langfuse")
    cfg = _merge_handler_into_config(handler=langfuse, config={"callbacks": raw})
    assert cfg["callbacks"] == [raw, langfuse]


def test_single_callable_handler_is_wrapped_in_list():
    """A bare callback object (not a list, not a CallbackManager) gets wrapped."""
    # Use a non-MagicMock object that does NOT have a .handlers attribute
    class BareCallback:
        pass
    cb = BareCallback()
    cfg = _merge_handler_into_config(handler=None, config={"callbacks": cb})
    assert cfg["callbacks"] == [cb]


def test_callbackmanager_handler_dedup():
    """If the Langfuse handler is already in the CallbackManager, don't double-add."""
    langfuse = MagicMock(name="langfuse")
    cm = CallbackManager([langfuse])
    cfg = _merge_handler_into_config(handler=langfuse, config={"callbacks": cm})
    assert cfg["callbacks"].count(langfuse) == 1


def test_input_config_not_mutated():
    """The input config dict must not be mutated (we return a new dict)."""
    input_cfg = {"callbacks": [MagicMock()], "metadata": {"k": "v"}}
    langfuse = MagicMock()
    original_callbacks = list(input_cfg["callbacks"])
    _merge_handler_into_config(handler=langfuse, config=input_cfg)
    assert input_cfg["callbacks"] == original_callbacks
    assert "langfuse" not in [str(c) for c in input_cfg["callbacks"]]
    assert input_cfg["metadata"] == {"k": "v"}


def test_end_to_end_with_unified_invoker():
    """Smoke test: UnifiedInvoker.invoke_raw doesn't crash on CallbackManager config.

    This is the actual production scenario reported in the bug report.
    """
    from unittest.mock import patch as mock_patch
    from aegis_phase1.llm.unified import UnifiedInvoker

    handler_a = MagicMock(name="handler_a")
    langfuse = MagicMock(name="langfuse")
    cm = CallbackManager([handler_a])

    # Patch ChatOllama at source so all instances get a mocked chat field
    fake_response = MagicMock()
    fake_response.content = "OK"
    fake_response.usage_metadata = {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}
    fake_chat = MagicMock()
    fake_chat.invoke = MagicMock(return_value=fake_response)

    with mock_patch("langchain_ollama.ChatOllama", return_value=fake_chat):
        inv = UnifiedInvoker(model="gemma4:e4b")
        inv._langfuse_handler = langfuse

        result = inv.invoke_raw("Say OK", config={"callbacks": cm})
        assert result["status"] == "OK"
        assert result["usage"]["total_tokens"] == 7
        # Verify the config passed to chat.invoke has the handler merged in
        call_args = fake_chat.invoke.call_args
        # chat.invoke(messages, config=cfg) — config is the 2nd arg by kwarg
        passed_cfg = call_args.kwargs.get("config")
        assert langfuse in passed_cfg["callbacks"]
        assert handler_a in passed_cfg["callbacks"]
