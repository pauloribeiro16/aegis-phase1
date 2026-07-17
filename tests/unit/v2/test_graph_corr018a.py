"""Tests for AEGIS-P1-CORR-018a S2 (root LangGraph API surface + runner).

Reference: ``execution/CONTRACT-018a.md`` §"Files to change".

Behaviour contract:

  1. ``build_phase1_graph()`` returns a StateGraph whose root nodes are
     consistent with the sub-graph-hierarchy introduced in CORR-018b
     (5 root nodes: ``load_baseline`` + 4 sub-phase nodes). The
     sub-graph topology itself is verified in
     ``test_graph_corr018b.py``.
  2. ``compile_phase1_graph()`` returns a compiled graph with ``.invoke``.
  3. The ``load_baseline`` node delegates to ``orchestrator.load``.
  4. Each ``map_DNN`` node delegates to ``orchestrator.map_single_domain``
     for the matching ``D-NN`` identifier (10 of them — fired via the
     ``subphase_map`` sub-graph invocation).
  5. ``run_phase1_graph(orch, ..., callbacks=[handler])`` threads the
     handler through ``run_config["callbacks"]``.
  6. ``tags=[...]`` is materialised as ``run_config["metadata"]["langfuse_tags"]``
     (with the four ``subphase:*`` tags added automatically).
  7. The REDUCE chain tolerates ``_get_phase1_executor`` returning ``None``
     (deterministic reduce still completes; LLM-bearing reduce nodes
     gracefully no-op).
  8. Legacy ``Phase1Orchestrator.run_all()`` still drives the four legacy
     public methods in order — regression guard for S1's refactor.

NOTE: The CORR-018a "18-node flat graph" structure has been refactored
into the 4-sub-phase hierarchy (CORR-018b). The structural test
(``test_graph_has_5_root_nodes`` below) replaces the legacy
``test_graph_has_18_nodes`` and lives in this file for API surface
continuity.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


# ─── 1. graph root structure (CORR-018b supersedes CORR-018a flat 18) ──


def test_graph_has_5_root_nodes_with_subphase_names() -> None:
    """``build_phase1_graph`` returns a StateGraph with exactly 5 root nodes.

    Replaces the CORR-018a "18-node flat graph" assertion. After
    CORR-018b, the root graph contains ``load_baseline`` + 4 sub-phase
    wrapper nodes; per-domain/per-spec/per-doc nodes live inside the
    compiled sub-graphs (verified separately in
    ``test_graph_corr018b.py``).
    """
    from aegis_phase1.v2.graph import build_phase1_graph

    g = build_phase1_graph()
    names = list(g.nodes.keys())
    assert len(names) == 5, f"expected 5 root nodes, got {len(names)}: {names!r}"

    expected = {
        "load_baseline",
        "subphase_map",
        "subphase_1b",
        "subphase_reduce",
        "subphase_output",
    }
    assert set(names) == expected, (
        f"missing={expected - set(names)} extra={set(names) - expected}"
    )


# ─── 2. compile returns CompiledStateGraph ────────────────────────────


def test_compile_phase1_graph_returns_compiled() -> None:
    """``compile_phase1_graph()`` returns a graph exposing ``.invoke``."""
    from aegis_phase1.v2.graph import compile_phase1_graph

    compiled = compile_phase1_graph()
    assert hasattr(compiled, "invoke"), "compiled graph must expose .invoke"
    assert callable(compiled.invoke)


# ─── 3. load_baseline delegates to orch.load ─────────────────────────


def test_load_baseline_calls_orchestrator_load() -> None:
    """The first node invokes ``orch.load(case_path, baseline)`` exactly once."""
    from aegis_phase1.v2.graph import compile_phase1_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}

    graph = compile_phase1_graph()
    graph.invoke(
        {
            "case_path": "/cases/case1",
            "regulatory_baseline_path": "/baseline",
            "stage_outputs": {},
        },
        config={"configurable": {"orchestrator": orch}},
    )

    orch.load.assert_called_once()
    call_args = orch.load.call_args
    assert call_args.args[0] == "/cases/case1"
    assert call_args.args[1] == "/baseline"


# ─── 4. each map_DNN delegates to orch.map_single_domain ─────────────


def test_map_node_calls_map_single_domain_for_each_domain() -> None:
    """All 10 ``map_DNN`` nodes fire ``orch.map_single_domain("D-NN", config=...)`` once.

    After CORR-018b, ``map_single_domain`` is invoked with a ``config=``
    kwarg carrying the per-node ``run_name`` so the nested LLM
    GENERATION span is named (C7 fix). We assert each call was made
    with the matching positional ``domain_id`` regardless of kwargs.
    """
    from aegis_phase1.v2.graph import compile_phase1_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}

    graph = compile_phase1_graph()
    graph.invoke(
        {
            "case_path": "/cases/case1",
            "regulatory_baseline_path": "/baseline",
            "stage_outputs": {},
        },
        config={"configurable": {"orchestrator": orch}},
    )

    orch.load.assert_called_once()

    seen_domain_ids = {
        call.args[0]
        for call in orch.map_single_domain.call_args_list
        if call.args
    }
    for i in range(1, 11):
        did = f"D-{i:02d}"
        assert did in seen_domain_ids, (
            f"orch.map_single_domain was not called with {did!r}; "
            f"seen={sorted(seen_domain_ids)!r}"
        )


# ─── 5. callbacks propagate through run_config ────────────────────────


def test_run_phase1_graph_attaches_callback_in_config() -> None:
    """The handler in ``callbacks=[...]`` reaches ``graph.invoke`` as a config arg."""
    from aegis_phase1.v2.graph import compile_phase1_graph, run_phase1_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}
    handler = MagicMock(name="langfuse_handler")

    captured: dict[str, Any] = {}

    real_compile = compile_phase1_graph

    class _SpyCompiled:
        def __init__(self, real: Any) -> None:
            self._real = real

        def invoke(self, state: Any, config: Any = None, **kwargs: Any) -> Any:
            captured["config"] = config
            return self._real.invoke(state, config=config, **kwargs)

    import aegis_phase1.v2.graph as graph_module

    original_compile = graph_module.compile_phase1_graph
    graph_module.compile_phase1_graph = lambda: _SpyCompiled(real_compile())  # type: ignore[assignment]
    try:
        run_phase1_graph(
            orch,
            case_path="/x",
            regulatory_baseline_path="/b",
            callbacks=[handler],
        )
    finally:
        graph_module.compile_phase1_graph = original_compile  # type: ignore[assignment]

    assert "config" in captured, "graph.invoke was never called"
    cfg = captured["config"]
    assert "callbacks" in cfg, f"callbacks missing from run_config: {cfg!r}"
    assert handler in cfg["callbacks"], (
        f"handler not propagated to config: cfg={cfg!r}"
    )


# ─── 6. tags → metadata.langfuse_tags ────────────────────────────────


def test_run_phase1_graph_propagates_tags() -> None:
    """``tags=[...]`` is materialised as ``metadata.langfuse_tags``."""
    from aegis_phase1.v2.graph import compile_phase1_graph, run_phase1_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}

    captured: dict[str, Any] = {}

    real_compile = compile_phase1_graph

    class _SpyCompiled:
        def __init__(self, real: Any) -> None:
            self._real = real

        def invoke(self, state: Any, config: Any = None, **kwargs: Any) -> Any:
            captured["config"] = config
            return self._real.invoke(state, config=config, **kwargs)

    import aegis_phase1.v2.graph as graph_module

    original_compile = graph_module.compile_phase1_graph
    graph_module.compile_phase1_graph = lambda: _SpyCompiled(real_compile())  # type: ignore[assignment]
    try:
        run_phase1_graph(
            orch,
            case_path="/x",
            regulatory_baseline_path="/b",
            tags=["phase:test", "case:x"],
        )
    finally:
        graph_module.compile_phase1_graph = original_compile  # type: ignore[assignment]

    cfg = captured["config"]
    assert "metadata" in cfg, f"metadata missing from run_config: {cfg!r}"
    tags = cfg["metadata"]["langfuse_tags"]
    # CORR-018b: run_phase1_graph auto-appends subphase:* tags.
    assert tags[:2] == ["phase:test", "case:x"]
    assert "subphase:map" in tags
    assert "subphase:1b" in tags
    assert "subphase:reduce" in tags
    assert "subphase:output" in tags


# ─── 7. reduce chain tolerates executor=None ─────────────────────────


def test_graph_skips_reduce_when_phase1_executor_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``_get_phase1_executor`` returns ``None``, deterministic reduce still runs.

    Uses a real :class:`Phase1Orchestrator` with ``llm_invoker=None`` so
    the natural guard in :meth:`_get_phase1_executor` returns ``None`` —
    no monkeypatching of the private method is required. Reduces are then
    exercised directly to verify they complete without raising.
    """
    from aegis_phase1.v2.domain.processor import DOMAIN_NAMES
    from aegis_phase1.v2.graph import _make_map_node
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    # 1. Sanity: with no llm_invoker, _get_phase1_executor returns None.
    orch = Phase1Orchestrator(work_dir="/tmp/aegis-test-graph-018a", llm_invoker=None)
    assert orch._get_phase1_executor() is None, (
        "Phase1Orchestrator(llm_invoker=None) must return None executor"
    )

    # 2. reduce_deterministic does not depend on the executor and must run.
    profile = orch.reduce_deterministic()
    assert isinstance(profile, dict)
    assert orch.state["current_stage"] == "REDUCED"
    assert "aggregated_data" in orch.state

    # 3. reduce_synthesis sees executor=None and returns None gracefully.
    synth = orch.reduce_synthesis()
    assert synth is None

    # 4. reduce_compound sees an empty cache and returns None gracefully.
    compound = orch.reduce_compound()
    assert compound is None

    # 5. The MAP node factory is callable for every D-NN and reflects the
    #    DOMAIN_NAMES catalogue in the span name (defensive — calls are
    #    not invoked here to avoid real LLM traffic; we just exercise the
    #    factory surface).
    for i in range(1, 11):
        did = f"D-{i:02d}"
        node = _make_map_node(did)
        assert callable(node)
        assert did in DOMAIN_NAMES

    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)


# ─── 8. legacy run_all unchanged ─────────────────────────────────────


def test_legacy_run_all_unchanged(tmp_path: Any) -> None:
    """``Phase1Orchestrator.run_all`` still drives the legacy S0 methods in order.

    Acts as a regression guard for the S1 refactor: every legacy public
    method on ``Phase1Orchestrator`` must remain invoked exactly once when
    ``run_all`` is called, in the canonical order
    ``load → map_domains → run_phase_1b → reduce → generate_outputs``.
    """
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator(work_dir=str(tmp_path), llm_invoker=None)

    call_order: list[str] = []

    def _record(name: str) -> Any:
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            call_order.append(name)
            if name == "load":
                orch.state["current_stage"] = "LOADED"
                return orch.state
            if name == "reduce":
                orch.state["current_stage"] = "REDUCED"
                return orch.state
            if name == "generate_outputs":
                orch.state["current_stage"] = "OUTPUT_DONE"
            return orch.state

        return _wrapped

    orch.load = _record("load")  # type: ignore[method-assign]
    orch.map_domains = _record("map_domains")  # type: ignore[method-assign]
    orch.run_phase_1b = _record("run_phase_1b")  # type: ignore[method-assign]
    orch.reduce = _record("reduce")  # type: ignore[method-assign]
    orch.generate_outputs = _record("generate_outputs")  # type: ignore[method-assign]

    result = orch.run_all(
        case_path=str(tmp_path / "fake_case"),
        regulatory_baseline_path=str(tmp_path / "fake_baseline"),
        output_dir=str(tmp_path / "out"),
    )

    assert call_order == [
        "load",
        "map_domains",
        "run_phase_1b",
        "reduce",
        "generate_outputs",
    ], f"unexpected legacy sequence: {call_order!r}"
    assert result["current_stage"] == "OUTPUT_DONE"
