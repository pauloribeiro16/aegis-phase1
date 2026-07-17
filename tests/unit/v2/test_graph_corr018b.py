"""Tests for AEGIS-P1-CORR-018b — sub-graph hierarchy + 10 OUTPUT nodes + C7.

Reference: ``execution/CONTRACT-018b.md`` (the contract draft, mirrored in
the user prompt for this delivery).

Behaviour contract:

  - Root graph: ``load_baseline`` + 4 sub-phase nodes (5 total).
  - ``build_subphase_map`` returns a compiled graph with 10 ``map_DXX``
    user nodes (compiled graphs add a ``__start__`` sentinel).
  - ``build_subphase_1b`` returns 4 user nodes (interp_GDPR, interp_CRA,
    rat_GDPR, rat_CRA).
  - ``build_subphase_reduce`` returns 3 user nodes (deterministic,
    synthesis, compound).
  - ``build_subphase_output`` returns 10 user nodes (doc_04_body, 04a..d,
    05, 06, 07, 07b, xlsx).
  - Sub-graph invocation propagates ``run_name`` via ``config=``.
  - ``map_single_domain``, ``DomainProcessor``, ``run_p1b_single``, and
    ``reduce_*`` all accept ``config`` for the C7 fix.
  - Render functions (doc_XX) thread ``config`` through to
    :func:`render_mandatory_narrative`.
  - Hierarchical ``subphase:*`` Langfuse tags are appended in
    :func:`run_phase1_graph`.
  - Sub-graph invocation creates a nested CHAIN "LangGraph" span
    (verified via config-capture, since LangChain's tracing isn't
    exercised here).
  - ``graph.py`` does NOT use ``from __future__ import annotations``
    (CORR-017 lesson preserved).
  - Legacy ``map_domains`` keeps its 10-call behaviour unchanged.

All tests use ``MagicMock`` for the orchestrator and ``llm_invoker`` —
no real LLM traffic.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ─── 1. root graph has exactly 5 nodes ────────────────────────────────


def test_root_graph_has_5_top_level_nodes() -> None:
    """The root graph built by ``build_phase1_graph`` has 5 top-level nodes.

    Was 18 in CORR-018a. After CORR-018b, the root contains
    ``load_baseline`` + 4 sub-phase wrapper nodes.
    """
    from aegis_phase1.v2.graph import build_phase1_graph

    g = build_phase1_graph()
    names = set(g.nodes.keys())
    expected = {
        "load_baseline",
        "subphase_map",
        "subphase_1b",
        "subphase_reduce",
        "subphase_output",
    }
    assert names == expected, f"got {sorted(names)!r}"


# ─── 2. build_subphase_map returns a compiled graph with 10 map nodes ─


def test_subphase_map_compiled_graph_has_10_nodes() -> None:
    """``build_subphase_map`` returns a compiled graph with 10 ``map_DXX`` nodes."""
    from aegis_phase1.v2.graph import build_subphase_map

    g = build_subphase_map()
    assert hasattr(g, "invoke"), "sub-phase must be compiled (has .invoke)"
    user_nodes = [n for n in g.nodes if not n.startswith("__")]
    assert len(user_nodes) == 10, f"expected 10 user nodes, got {user_nodes!r}"
    expected_names = {f"map_D{i:02d}" for i in range(1, 11)}
    assert set(user_nodes) == expected_names


# ─── 3. build_subphase_1b returns 4 nodes ─────────────────────────────


def test_subphase_1b_compiled_graph_has_4_nodes() -> None:
    """``build_subphase_1b`` returns a compiled graph with 4 user nodes."""
    from aegis_phase1.v2.graph import build_subphase_1b

    g = build_subphase_1b()
    user_nodes = [n for n in g.nodes if not n.startswith("__")]
    assert len(user_nodes) == 4, f"expected 4 user nodes, got {user_nodes!r}"
    expected_names = {"interp_GDPR", "interp_CRA", "rat_GDPR", "rat_CRA"}
    assert set(user_nodes) == expected_names


# ─── 4. build_subphase_reduce returns 3 nodes ─────────────────────────


def test_subphase_reduce_compiled_graph_has_3_nodes() -> None:
    """``build_subphase_reduce`` returns 3 user nodes."""
    from aegis_phase1.v2.graph import build_subphase_reduce

    g = build_subphase_reduce()
    user_nodes = [n for n in g.nodes if not n.startswith("__")]
    assert len(user_nodes) == 3, f"expected 3 user nodes, got {user_nodes!r}"
    expected_names = {"deterministic", "synthesis", "compound"}
    assert set(user_nodes) == expected_names


# ─── 5. build_subphase_output returns 10 nodes ────────────────────────


def test_subphase_output_compiled_graph_has_10_nodes() -> None:
    """``build_subphase_output`` returns 10 user nodes (NEW in CORR-018b)."""
    from aegis_phase1.v2.graph import build_subphase_output

    g = build_subphase_output()
    user_nodes = [n for n in g.nodes if not n.startswith("__")]
    assert len(user_nodes) == 10, f"expected 10 user nodes, got {user_nodes!r}"
    expected_names = {
        "doc_04_body",
        "doc_04a",
        "doc_04b",
        "doc_04c",
        "doc_04d",
        "doc_05",
        "doc_06",
        "doc_07",
        "doc_07b",
        "xlsx",
    }
    assert set(user_nodes) == expected_names


# ─── 6. sub-graph node invoke propagates config with run_name ─────────


def test_subgraph_node_invoke_propagates_config() -> None:
    """When the root graph invokes a sub-graph, the inner config carries run_name.

    We capture the config passed to the (mocked) compiled sub-graph's
    ``invoke`` and verify the run_name is a non-empty meaningful string
    and that any parent metadata is preserved.
    """
    from aegis_phase1.v2 import graph as graph_module

    fake_subgraph = MagicMock(name="fake_compiled_subgraph")
    fake_subgraph.invoke.return_value = {"stage_outputs": {"mock": "ok"}}

    node_fn = graph_module._make_subgraph_node(
        fake_subgraph,
        run_name="MAP Sub-Phase",
        metadata={"subphase": "map"},
    )

    parent_cfg: dict[str, Any] = {
        "configurable": {"orchestrator": object()},
        "metadata": {"langfuse_tags": ["phase:phase1"]},
    }
    result = node_fn(
        {"stage_outputs": {"load": {"x": 1}}},
        parent_cfg,
    )

    assert fake_subgraph.invoke.called, "compiled sub-graph was never invoked"
    kwargs = fake_subgraph.invoke.call_args.kwargs
    assert "config" in kwargs, f"inner config missing: {kwargs!r}"
    inner_cfg = kwargs["config"]
    assert inner_cfg["run_name"] == "MAP Sub-Phase", inner_cfg
    assert inner_cfg["metadata"]["langfuse_tags"] == ["phase:phase1"], inner_cfg
    assert inner_cfg["metadata"]["subphase"] == "map", inner_cfg

    assert result["stage_outputs"]["mock"] == "ok"
    assert result["stage_outputs"]["load"] == {"x": 1}


# ─── 7. map_single_domain accepts config; DomainProcessor + invoke see it


def test_map_single_domain_accepts_config_param() -> None:
    """``map_single_domain`` accepts ``config``; ``DomainProcessor`` and the
    underlying ``llm_invoker.invoke`` see it.
    """
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator(work_dir="/tmp/aegis-c018b-test-cfg", llm_invoker=None)

    captured_cfg: dict[str, Any] = {}

    class _FakeProcessor:
        def __init__(self, **kwargs: Any) -> None:
            captured_cfg["init"] = dict(kwargs)

        def process(self, domain_id: str, state: Any) -> dict[str, Any]:
            captured_cfg["process_called"] = True
            return {"domain_id": domain_id, "llm_status": "OK"}

    with patch(
        "aegis_phase1.v2.domain.processor.DomainProcessor", _FakeProcessor
    ):
        sentinel_cfg = {"run_name": "MAP D-04 Incident Response"}
        result = orch.map_single_domain("D-04", config=sentinel_cfg)

    assert result["domain_id"] == "D-04"
    assert result["llm_status"] == "OK"
    assert captured_cfg["init"].get("config") == sentinel_cfg, captured_cfg
    assert captured_cfg.get("process_called") is True


# ─── 7b. llm_invoker.invoke receives self.config from DomainProcessor ─


def test_domain_processor_threads_config_to_llm_invoke() -> None:
    """``DomainProcessor.process`` forwards ``self.config`` to ``llm_invoker.invoke``."""
    from aegis_phase1.v2.domain.processor import DomainProcessor

    llm_invoker = MagicMock(name="llm_invoker")
    llm_invoker.invoke.return_value = {
        "raw": "{}",
        "status": "OK",
        "usage": None,
    }
    parser = MagicMock(name="parser")
    parser.parse.return_value = MagicMock(
        success=True,
        adapted_objective="obj",
        key_adjustments=[],
        confidence="HIGH",
    )

    with patch(
        "aegis_phase1.v2.domain.processor.OutputParser",
        lambda: parser,
    ):
        with patch(
            "aegis_phase1.v2.domain.processor.assemble_inputs",
            lambda state, did: {"subdomains": [], "cross_reg_analysis": [],
                               "applicable_regs": ["GDPR"]},
        ):
            with patch(
                "aegis_phase1.v2.domain.processor.render_prompt",
                lambda inputs, feedback="": "PROMPT",
            ):
                proc = DomainProcessor(
                    llm_invoker=llm_invoker,
                    log_dir=None,
                    config={"run_name": "MAP D-01 Data Protection"},
                )
                proc.process("D-01", {"company_context": None})

    assert llm_invoker.invoke.called
    call = llm_invoker.invoke.call_args
    assert call.kwargs.get("config") == {
        "run_name": "MAP D-01 Data Protection"
    }


# ─── 8. narrative renderers accept config (threaded) ──────────────────


def test_narrative_renders_receive_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """``render_doc_XX`` (LLM-bearing docs) threads ``config`` to ``render_mandatory_narrative``."""
    from aegis_phase1.v2.output import doc_04a

    captured: dict[str, Any] = {}

    def fake_render_mandatory_narrative(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "fake narrative"

    monkeypatch.setattr(doc_04a, "render_mandatory_narrative", fake_render_mandatory_narrative)
    monkeypatch.setattr(
        "aegis_phase1.v2.output.doc_04a.write_output",
        lambda output_dir, filename, content: f"{output_dir}/{filename}",
    )

    llm_invoker = MagicMock(name="llm_invoker")
    llm_invoker.invoke.return_value = {"raw": "ok", "status": "OK"}

    result = doc_04a.render_doc_04a(
        {"company_context": None},
        "/tmp/out",
        llm_invoker,
        config={"run_name": "OUTPUT 04a"},
    )

    assert "AEGIS-P1-04a" in result
    assert captured.get("config") == {"run_name": "OUTPUT 04a"}, captured


# ─── 9. run_phase1_graph adds hierarchical langfuse tags ──────────────


def test_hierarchy_in_langfuse_format() -> None:
    """``run_phase1_graph`` appends ``subphase:*`` tags to ``langfuse_tags``.

    The caller-supplied tags are preserved at the front; the four
    ``subphase:*`` tags are appended in canonical order.
    """
    from aegis_phase1.v2.graph import run_phase1_graph

    orch = MagicMock(name="orchestrator")
    orch.state = {"current_stage": "INIT"}

    captured: dict[str, Any] = {}

    real_compile = None
    try:
        from aegis_phase1.v2.graph import compile_phase1_graph

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
                tags=["phase:phase1", "case:mycase"],
            )
        finally:
            graph_module.compile_phase1_graph = original_compile  # type: ignore[assignment]
    except Exception:
        raise

    cfg = captured["config"]
    tags = cfg["metadata"]["langfuse_tags"]
    assert tags[:2] == ["phase:phase1", "case:mycase"]
    assert set(tags[2:]) == {
        "subphase:map",
        "subphase:1b",
        "subphase:reduce",
        "subphase:output",
    }


# ─── 10. sub-graph invoke creates a nested CHAIN span ─────────────────


def test_subgraph_creates_nested_chain_span() -> None:
    """A sub-graph invocation creates a nested ``CHAIN "LangGraph"`` observation.

    We mock the compiled sub-graph and verify its ``invoke`` was called
    with the inner config that includes the meaningful ``run_name``
    (which becomes the parent chain span name in Langfuse).
    """
    from aegis_phase1.v2 import graph as graph_module

    captured: list[dict[str, Any]] = []

    class _FakeCompiled:
        def invoke(self, state: Any, config: Any = None, **kwargs: Any) -> Any:
            captured.append({"config": config, "state": state})
            return {"stage_outputs": {"fake_node": "ok"}}

    node_fn = graph_module._make_subgraph_node(
        _FakeCompiled(),
        run_name="OUTPUT Sub-Phase",
        metadata={"subphase": "output"},
    )

    parent_cfg = {
        "configurable": {"orchestrator": MagicMock()},
        "metadata": {"langfuse_tags": ["phase:phase1"]},
    }
    node_fn({"stage_outputs": {"load": {}}}, parent_cfg)

    assert len(captured) == 1
    inner_cfg = captured[0]["config"]
    assert inner_cfg["run_name"] == "OUTPUT Sub-Phase"
    # LangChain treats a sub-graph invoke as a CHAIN "LangGraph" by default;
    # the run_name we pass becomes the chain span name.
    assert "run_name" in inner_cfg
    assert "metadata" in inner_cfg
    assert inner_cfg["metadata"]["subphase"] == "output"


# ─── 11. graph.py does NOT import from __future__ import annotations ──


def test_no_pep563_in_graph() -> None:
    """``graph.py`` must NOT use ``from __future__ import annotations`` (CORR-017 lesson).

    Matches an actual import statement (``^from __future__ import annotations$``)
    at line start, NOT the docstring text that explains why PEP-563 is
    forbidden.
    """
    import pathlib
    import re

    graph_path = (
        pathlib.Path(__file__).resolve().parents[3]
        / "src"
        / "aegis_phase1"
        / "v2"
        / "graph.py"
    )
    text = graph_path.read_text(encoding="utf-8")
    bad = re.search(r"^from __future__ import annotations\s*$", text, re.MULTILINE)
    assert bad is None, (
        f"graph.py uses PEP-563 (line {bad.start() if bad else '?'}) — "
        "breaks LangGraph runtime config injection"
    )


# ─── 12. legacy map_domains still calls map_single_domain 10 times ────


def test_legacy_map_domains_unchanged(tmp_path: Any) -> None:
    """``Phase1Orchestrator.map_domains`` still loops ``map_single_domain`` 10×.

    Regression guard for the S1 refactor preserved through CORR-018b:
    the legacy ``map_domains`` method must still call the granular
    ``map_single_domain`` for each of the 10 domain IDs.
    """
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator(work_dir=str(tmp_path), llm_invoker=None)

    called_with: list[str] = []

    def _spy(domain_id: str, **_: Any) -> dict[str, Any]:
        called_with.append(domain_id)
        return {"domain_id": domain_id, "llm_status": "OK"}

    orch.map_single_domain = _spy  # type: ignore[method-assign]
    # map_domains also constructs a DomainProcessor via map_single_domain's
    # default branch when no processor is passed; replace that path with
    # a no-op so the test does not require real LLM files.
    import aegis_phase1.v2.domain.processor as _dp

    class _StubProcessor:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def process(self, did: str, state: Any) -> dict[str, Any]:
            return {"domain_id": did, "llm_status": "OK"}

    with patch.object(_dp, "DomainProcessor", _StubProcessor):
        from aegis_phase1.v2.domain.processor import MapPartialFailure

        try:
            orch.map_domains()
        except MapPartialFailure:
            pass  # ignore — not relevant to this assertion

    assert sorted(called_with) == [f"D-{i:02d}" for i in range(1, 11)], called_with


# ─── 13. (bonus) orchestrator exposes all 10 granular render methods ───


def test_orchestrator_exposes_10_granular_render_methods() -> None:
    """The orchestrator must expose the 10 granular render methods used by output nodes."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    expected = {
        "render_doc_04_body",
        "render_doc_04a",
        "render_doc_04b",
        "render_doc_04c",
        "render_doc_04d",
        "render_doc_05",
        "render_doc_06",
        "render_doc_07",
        "render_doc_07b",
        "generate_xlsx_workbook",
    }
    actual = set(dir(Phase1Orchestrator))
    missing = expected - actual
    assert not missing, f"missing granular render methods: {missing!r}"


# ─── 14. (bonus) run_p1b_single + reduce_* accept config ──────────────


def test_run_p1b_single_accepts_config() -> None:
    """``run_p1b_single(spec_id, reg_id, *, config=None)`` accepts the config kwarg."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator(work_dir="/tmp/aegis-c018b-p1b", llm_invoker=None)
    assert orch._get_phase1_executor() is None

    sentinel_cfg = {"run_name": "P1B-LLM-01 INTERPRETATION (GDPR)"}
    result = orch.run_p1b_single(
        "P1B-LLM-01-INTERPRETATION", "GDPR", config=sentinel_cfg
    )
    assert result is None  # no executor -> returns None (preserved legacy behaviour)


def test_reduce_synthesis_and_compound_accept_config() -> None:
    """``reduce_synthesis`` and ``reduce_compound`` accept ``config`` kwarg."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator(work_dir="/tmp/aegis-c018b-red", llm_invoker=None)
    assert orch.reduce_synthesis(config={"run_name": "x"}) is None
    assert orch.reduce_compound(config={"run_name": "y"}) is None
