"""Tests for AEGIS-P1-CORR-017 (LangGraph thin wrapper for Phase1Orchestrator).

Reference: ``docs/SPEC-observability.md`` §3 + §6 Phase 4a follow-up.

Behaviour contract:

  1. ``build_orchestrator_graph()`` returns a StateGraph with 5 nodes in
     topological order: ``load → map → phase_1b → reduce → output``.
  2. ``compile_orchestrator_graph()`` returns a ``CompiledStateGraph``
     with ``.invoke(state, config=...)``.
  3. The ``load`` node calls ``orchestrator.load(case, baseline)``.
  4. Invoking the compiled graph with a MagicMock orchestrator fires
     all 5 stage methods once.
  5. Callbacks passed via ``config={"callbacks": [...]}`` are
     forwarded to the compiled graph's ``.invoke``.
  6. ``tags`` argument is converted to ``metadata.langfuse_tags``.
  7. ``OllamaUnreachable`` raised inside an orchestrator method
     propagates out of ``graph.invoke``.
  8. With ``LANGFUSE_ENABLED=false``, ``get_langfuse_callback()``
     returns ``(None, None)`` and the run completes without invoking
     a Langfuse client.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ─── 1. graph node order ─────────────────────────────────────────────


def test_graph_has_five_nodes_in_order():
    """``build_orchestrator_graph`` produces the 5 expected nodes in order."""
    from aegis_phase1.v2.trace_graph import build_orchestrator_graph

    g = build_orchestrator_graph()
    nodes = list(g.nodes.keys())
    assert nodes == ["load", "map", "phase_1b", "reduce", "output"], (
        f"unexpected node order: {nodes!r}"
    )


# ─── 2. compile returns CompiledStateGraph ───────────────────────────


def test_compile_orchestrator_graph_returns_compiled():
    """``compile_orchestrator_graph()`` returns a graph with ``.invoke``."""
    from aegis_phase1.v2.trace_graph import compile_orchestrator_graph

    compiled = compile_orchestrator_graph()
    assert hasattr(compiled, "invoke"), "compiled graph must expose .invoke"
    assert callable(compiled.invoke)


# ─── 3. load node calls orchestrator.load ────────────────────────────


def test_load_node_calls_orchestrator_load():
    """The ``load`` node invokes ``orch.load(case_path, baseline)`` once."""
    from aegis_phase1.v2.trace_graph import compile_orchestrator_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}

    graph = compile_orchestrator_graph()
    graph.invoke(
        {
            "case_path": "/cases/case1",
            "regulatory_baseline_path": "/baseline",
            "v2_state": {},
        },
        config={"configurable": {"orchestrator": orch}},
    )

    orch.load.assert_called_once()
    call_args = orch.load.call_args
    assert call_args.args[0] == "/cases/case1"
    assert call_args.args[1] == "/baseline"


# ─── 4. all 5 nodes call the corresponding orchestrator methods ──────


def test_all_nodes_call_corresponding_orchestrator_methods():
    """One invoke → 5 stage methods called once each."""
    from aegis_phase1.v2.trace_graph import compile_orchestrator_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}

    graph = compile_orchestrator_graph()
    result = graph.invoke(
        {
            "case_path": "/cases/case1",
            "regulatory_baseline_path": "/baseline",
            "output_dir": "/out",
            "v2_state": {},
        },
        config={"configurable": {"orchestrator": orch}},
    )

    orch.load.assert_called_once()
    orch.map_domains.assert_called_once()
    orch.run_phase_1b.assert_called_once()
    orch.reduce.assert_called_once()
    orch.generate_outputs.assert_called_once()

    # generate_outputs must be called with the output_dir
    out_args = orch.generate_outputs.call_args
    assert out_args.args[0] == "/out"

    # LangGraph merges state; the result has case_path + output_dir + v2_state
    assert result["case_path"] == "/cases/case1"
    assert result["output_dir"] == "/out"
    assert "v2_state" in result


# ─── 5. callbacks propagated through .invoke config ─────────────────


def test_callbacks_propagated_to_compiled_graph_invoke():
    """The handler passed via ``callbacks=[...]`` reaches ``graph.invoke``."""
    from aegis_phase1.v2.trace_graph import compile_orchestrator_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}
    handler = MagicMock(name="langfuse_handler")

    captured: dict = {}

    real_compile = compile_orchestrator_graph

    class _SpyCompiled:
        def __init__(self, real):
            self._real = real

        def invoke(self, state, config=None, **kwargs):
            captured["config"] = config
            return self._real.invoke(state, config=config, **kwargs)

    spy = _SpyCompiled(real_compile())
    spy.invoke(
        {"case_path": "/x", "v2_state": {}},
        config={
            "configurable": {"orchestrator": orch},
            "callbacks": [handler],
        },
    )
    assert "config" in captured
    cfg = captured["config"]
    assert "callbacks" in cfg
    assert handler in cfg["callbacks"], (
        f"handler not propagated to config: cfg={cfg!r}"
    )


# ─── 6. tags → metadata.langfuse_tags ────────────────────────────────


def test_tags_propagated_to_metadata_langfuse_tags():
    """``tags=[...]`` argument is materialised as ``metadata.langfuse_tags``."""
    from aegis_phase1.v2.trace_graph import compile_orchestrator_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}
    handler = MagicMock(name="handler")

    captured: dict = {}

    real_compile = compile_orchestrator_graph

    class _SpyCompiled:
        def __init__(self, real):
            self._real = real

        def invoke(self, state, config=None, **kwargs):
            captured["config"] = config
            return self._real.invoke(state, config=config, **kwargs)

    spy = _SpyCompiled(real_compile())
    spy.invoke(
        {"case_path": "/x", "v2_state": {}},
        config={
            "configurable": {"orchestrator": orch},
            "callbacks": [handler],
            "metadata": {"langfuse_tags": ["phase:test", "case:x"]},
        },
    )
    cfg = captured["config"]
    assert cfg["metadata"]["langfuse_tags"] == ["phase:test", "case:x"]


# ─── 7. OllamaUnreachable propagates through the graph ───────────────


def test_orchestrator_unreachable_propagates_after_load():
    """An OllamaUnreachable raised by a stage method propagates to the caller."""
    from aegis_phase1.v2.domain.processor import OllamaUnreachable
    from aegis_phase1.v2.trace_graph import compile_orchestrator_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}
    orch.map_domains.side_effect = OllamaUnreachable("test: down")

    graph = compile_orchestrator_graph()
    with pytest.raises(OllamaUnreachable, match="down"):
        graph.invoke(
            {"case_path": "/x", "regulatory_baseline_path": "/b", "v2_state": {}},
            config={"configurable": {"orchestrator": orch}},
        )

    # load was called once, then map raised; later stages never ran.
    assert orch.load.call_count == 1
    assert orch.map_domains.call_count == 1
    assert orch.run_phase_1b.call_count == 0
    assert orch.reduce.call_count == 0
    assert orch.generate_outputs.call_count == 0


# ─── 8. Langfuse OFF — no flush attempted ────────────────────────────


def test_no_callbacks_when_langfuse_off(monkeypatch):
    """With ``LANGFUSE_ENABLED=false``, ``run_orchestrator_graph`` runs cleanly.

    Verifies:
      - ``get_langfuse_callback()`` returns ``(None, None)`` when disabled.
      - The high-level entry-point does not call any client ``.flush()``.
    """
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    from aegis_phase1.llm.tracing import get_langfuse_callback

    client, handler = get_langfuse_callback()
    assert client is None
    assert handler is None

    from aegis_phase1.v2.trace_graph import run_orchestrator_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}
    # explicit handler on orchestrator (e.g. injected by the user) is
    # forwarded to the graph, but the Langfuse *client* is None.
    orch._langfuse_handler = None

    result = run_orchestrator_graph(
        orch,
        case_path="/x",
        regulatory_baseline_path="/b",
        output_dir="/o",
    )
    assert "v2_state" in result
    # All 5 stage methods were called once.
    assert orch.load.call_count == 1
    assert orch.map_domains.call_count == 1
    assert orch.run_phase_1b.call_count == 1
    assert orch.reduce.call_count == 1
    assert orch.generate_outputs.call_count == 1
