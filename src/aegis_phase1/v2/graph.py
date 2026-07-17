"""AEGIS Phase 1 full LangGraph (CORR-018b — sub-graph hierarchy).

Provides a hierarchical LangGraph structure that mirrors the aegis-kg
trace pattern: one root trace with four nested sub-graphs
(MAP / 1B / REDUCE / OUTPUT), each containing its own linear chain
of named nodes. This produces a three-level Langfuse hierarchy:

    TRACE "AEGIS Phase 1"
    └── CHAIN "LangGraph"                 (root graph)
        ├── SPAN  "load_baseline"
        ├── SPAN  "subphase_map"           (root node)
        │   └── CHAIN "MAP Sub-Phase"     (sub-graph invoke)
        │       ├── SPAN "map_D01"        (per-domain node)
        │       │   └── GEN  "MAP D-01 …"
        │       └── …
        ├── SPAN  "subphase_1b"
        │   └── CHAIN "P1B Sub-Phase"
        │       ├── SPAN "interp_GDPR"
        │       │   └── GEN  "P1B-LLM-01 INTERPRETATION (GDPR)"
        │       └── …
        ├── SPAN  "subphase_reduce"
        │   └── CHAIN "REDUCE Sub-Phase"
        │       ├── SPAN "deterministic"
        │       ├── SPAN "synthesis"
        │       └── SPAN "compound"
        └── SPAN  "subphase_output"
            └── CHAIN "OUTPUT Sub-Phase"
                ├── SPAN "doc_04_body"
                ├── SPAN "doc_04a"
                │   └── GEN  "OUTPUT 04a …"
                └── …

CRITICAL: ``from __future__ import annotations`` is INTENTIONALLY NOT used here
because PEP-563 string annotations break LangGraph's runtime annotation
introspection that decides whether to inject the ``config`` kwarg into node
callables. Without real annotations, ``config`` becomes ``None`` inside every
node. See CORR-017 post-merge notes for the captured regression pattern.
"""

import logging
from pathlib import Path
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from aegis_phase1.llm.tracing import get_langfuse_callback
from aegis_phase1.v2.domain.processor import DOMAIN_NAMES, MapPartialFailure, OllamaUnreachable
from aegis_phase1.v2.orchestrator import Phase1Orchestrator

logger = logging.getLogger(__name__)


class Phase1GraphState(TypedDict, total=False):
    """Per-run state carried through the 4-sub-phase Phase 1 graph.

    Attributes:
        case_path: Absolute case directory path.
        regulatory_baseline_path: Optional regulatory baseline directory.
        output_dir: Output directory for generated artefacts.
        case_name: Derived case identifier (for trace tags).
        stage_outputs: Per-node result aggregator keyed by node id; useful
            for tests that introspect intermediate stages. The canonical
            pipeline state lives on the orchestrator instance.
        map_complete: Completion flags for the MAP stage (reserved for
            conditional edges in future contracts; not consumed here).
        p1b_complete: Completion flags for the Phase 1B stage (reserved).
        reduce_complete: Completion flags for the REDUCE stage (reserved).
        output_complete: Completion flags for the OUTPUT stage (reserved).
    """

    case_path: str
    regulatory_baseline_path: str | None
    output_dir: str
    case_name: str
    stage_outputs: dict[str, Any]
    map_complete: dict[str, bool]
    p1b_complete: dict[str, bool]
    reduce_complete: dict[str, bool]
    output_complete: dict[str, bool]


def _orchestrator_from(config: RunnableConfig | None) -> Phase1Orchestrator:
    """Pull the shared orchestrator out of ``config["configurable"]``.

    Raises a RuntimeError with actionable guidance if the LangGraph node is
    invoked without the canonical ``configurable["orchestrator"]`` payload —
    typically caused by forgetting to use :func:`run_phase1_graph` as the
    entry point or by PEP-563 string annotations breaking LangGraph's
    runtime config injection (CORR-017 lesson).
    """
    if config is None:
        raise RuntimeError(
            "LangGraph node called without RunnableConfig — "
            "ensure compile().invoke(state, config=run_config) is used."
        )
    if not isinstance(config, dict):
        raise RuntimeError(
            "LangGraph node received a non-dict RunnableConfig; "
            "compile().invoke(state, config=dict_run_config) is required."
        )
    configurable = config.get("configurable")
    if not isinstance(configurable, dict) or "orchestrator" not in configurable:
        raise RuntimeError(
            "config['configurable']['orchestrator'] missing — "
            "use run_phase1_graph() as the entry point."
        )
    return configurable["orchestrator"]


def _add_named_callback(
    config: RunnableConfig | None,
    run_name: str,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a RunnableConfig with run_name and metadata merged in.

    LangChain's chat models honour ``config['run_name']`` as the GENERATION
    name in Langfuse — this is how we get ``MAP D-01 Asset Management``
    instead of ``ChatOllama`` for the nested LLM call.

    ``extra_metadata`` is merged on top of any existing ``metadata`` dict
    so per-node ``langfuse_tags`` / spec identifiers accumulate without
    clobbering run-level metadata.
    """
    cfg: dict[str, Any] = dict(config) if isinstance(config, dict) else {}
    cfg["run_name"] = run_name
    if extra_metadata:
        meta = dict(cfg.get("metadata") or {})
        meta.update(extra_metadata)
        cfg["metadata"] = meta
    return cfg


def _merge_stage_outputs(parent: dict[str, Any] | None, child: Any) -> dict[str, Any]:
    """Merge a child graph's ``stage_outputs`` into the parent's.

    The child sub-graph runs over a copy of the parent's state and returns
    its own updated dict; we must reconcile both into the parent's
    ``stage_outputs`` to preserve the canonical run-level aggregator.
    """
    merged: dict[str, Any] = dict(parent or {})
    if isinstance(child, dict):
        for key, value in child.items():
            merged[key] = value
    return merged


# ─── Stage 0: LOAD (root-only direct node) ────────────────────────────


def _load_baseline(state: Phase1GraphState, config: RunnableConfig) -> dict:
    """Stage 0 — LOAD. Delegates to ``orch.load(case_path, baseline)``."""
    orch = _orchestrator_from(config)
    orch.load(state["case_path"], state.get("regulatory_baseline_path"))
    return {"stage_outputs": {"load": dict(orch.state)}}


# ─── MAP nodes (live inside subphase_map sub-graph) ────────────────────


def _make_map_node(domain_id: str):
    """Factory: build a per-domain MAP node.

    The LangGraph span name is set by ``g.add_node(name=...)``; the
    callable name only affects Python ``__name__``.
    """
    domain_name = DOMAIN_NAMES.get(domain_id, domain_id)
    span_name = f"MAP {domain_id} {domain_name}"

    def node(state: Phase1GraphState, config: RunnableConfig) -> dict:
        orch = _orchestrator_from(config)
        cfg = _add_named_callback(
            config,
            span_name,
            {"domain_id": domain_id, "stage": "MAP"},
        )
        try:
            result = orch.map_single_domain(domain_id, config=cfg)
        except MapPartialFailure as exc:
            logger.warning("MAP %s partial failure: %s", domain_id, exc)
            return {
                "stage_outputs": {
                    f"map_{domain_id}": {
                        "domain_id": domain_id,
                        "llm_status": "FAILED",
                        "error": str(exc),
                    }
                },
                "map_complete": {domain_id: True},
            }
        except OllamaUnreachable:
            raise
        complete = dict(state.get("map_complete") or {})
        complete[domain_id] = True
        return {
            "stage_outputs": {f"map_{domain_id}": result},
            "map_complete": complete,
        }

    node.__name__ = f"map_{domain_id}"
    return node


def _p1b_interp_node(reg_id: str):
    """Factory: build a P1B-LLM-01 INTERPRETATION node for one regulation."""
    span_name = f"P1B-LLM-01 INTERPRETATION ({reg_id})"

    def node(state: Phase1GraphState, config: RunnableConfig) -> dict:
        orch = _orchestrator_from(config)
        cfg = _add_named_callback(
            config,
            span_name,
            {"spec": "P1B-LLM-01", "regulation": reg_id, "stage": "P1B"},
        )
        result = orch.run_p1b_single(
            "P1B-LLM-01-INTERPRETATION", reg_id, config=cfg
        )
        complete = dict(state.get("p1b_complete") or {})
        complete[f"interp_{reg_id}"] = True
        return {
            "stage_outputs": {f"p1b_interp_{reg_id}": result},
            "p1b_complete": complete,
        }

    return node


def _p1b_rationale_node(reg_id: str):
    """Factory: build a P1B-LLM-02 RATIONALE node for one regulation."""
    span_name = f"P1B-LLM-02 RATIONALE ({reg_id})"

    def node(state: Phase1GraphState, config: RunnableConfig) -> dict:
        orch = _orchestrator_from(config)
        cfg = _add_named_callback(
            config,
            span_name,
            {"spec": "P1B-LLM-02", "regulation": reg_id, "stage": "P1B"},
        )
        result = orch.run_p1b_single(
            "P1B-LLM-02-RATIONALE", reg_id, config=cfg
        )
        complete = dict(state.get("p1b_complete") or {})
        complete[f"rat_{reg_id}"] = True
        return {
            "stage_outputs": {f"p1b_rat_{reg_id}": result},
            "p1b_complete": complete,
        }

    return node


# ─── REDUCE nodes (live inside subphase_reduce sub-graph) ──────────────


def _reduce_det(state: Phase1GraphState, config: RunnableConfig) -> dict:
    """REDUCE — Deterministic. Always runs (no LLM)."""
    orch = _orchestrator_from(config)
    cfg = _add_named_callback(config, "REDUCE Deterministic", {"stage": "REDUCE-DET"})
    result = orch.reduce_deterministic()
    complete = dict(state.get("reduce_complete") or {})
    complete["det"] = True
    return {
        "stage_outputs": {"reduce_det": result},
        "reduce_complete": complete,
    }


def _reduce_synthesis(state: Phase1GraphState, config: RunnableConfig) -> dict:
    """REDUCE — P1C-LLM-03 STRATEGIC SYNTHESIS. No-op when executor is None."""
    orch = _orchestrator_from(config)
    cfg = _add_named_callback(
        config,
        "P1C-LLM-03 STRATEGIC SYNTHESIS",
        {"spec": "P1C-LLM-03", "stage": "REDUCE-SYNTH"},
    )
    result = orch.reduce_synthesis(config=cfg)
    complete = dict(state.get("reduce_complete") or {})
    complete["synthesis"] = True
    return {
        "stage_outputs": {"reduce_synthesis": result},
        "reduce_complete": complete,
    }


def _reduce_compound(state: Phase1GraphState, config: RunnableConfig) -> dict:
    """REDUCE — P1C-LLM-02 COMPOUND EVENTS. No-op when synthesis cache absent."""
    orch = _orchestrator_from(config)
    cfg = _add_named_callback(
        config,
        "P1C-LLM-02 COMPOUND EVENTS",
        {"spec": "P1C-LLM-02", "stage": "REDUCE-COMPOUND"},
    )
    result = orch.reduce_compound(config=cfg)
    complete = dict(state.get("reduce_complete") or {})
    complete["compound"] = True
    return {
        "stage_outputs": {"reduce_compound": result},
        "reduce_complete": complete,
    }


# ─── OUTPUT nodes (live inside subphase_output sub-graph) ─────────────


_OUTPUT_NODE_NAMES: tuple[str, ...] = (
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
)


_OUTPUT_RUN_NAMES: dict[str, str] = {
    "doc_04_body": "OUTPUT 04 body",
    "doc_04a": "OUTPUT 04a Architecture & Data Inventory",
    "doc_04b": "OUTPUT 04b Security Posture",
    "doc_04c": "OUTPUT 04c Third-Party Landscape",
    "doc_04d": "OUTPUT 04d Roles & RACI",
    "doc_05": "OUTPUT 05 Regulatory Applicability",
    "doc_06": "OUTPUT 06 Clause Mapping Matrix",
    "doc_07": "OUTPUT 07 Structured Compliance Matrix",
    "doc_07b": "OUTPUT 07b Proportionality Profile",
    "xlsx": "OUTPUT xlsx Workbook",
}


def _output_method_for(node_name: str) -> str:
    """Return the orchestrator granular method name for an OUTPUT node."""
    return {
        "doc_04_body": "render_doc_04_body",
        "doc_04a": "render_doc_04a",
        "doc_04b": "render_doc_04b",
        "doc_04c": "render_doc_04c",
        "doc_04d": "render_doc_04d",
        "doc_05": "render_doc_05",
        "doc_06": "render_doc_06",
        "doc_07": "render_doc_07",
        "doc_07b": "render_doc_07b",
        "xlsx": "generate_xlsx_workbook",
    }[node_name]


def _make_output_node(node_name: str):
    """Factory: build a per-doc OUTPUT node.

    Each node invokes the orchestrator's granular render method (added in
    CORR-018b) with the ``config`` propagated so nested LLM calls name
    their GENERATION span after this node.
    """
    span_name = _OUTPUT_RUN_NAMES[node_name]
    method_name = _output_method_for(node_name)

    def node(state: Phase1GraphState, config: RunnableConfig) -> dict:
        orch = _orchestrator_from(config)
        cfg = _add_named_callback(
            config,
            span_name,
            {"doc": node_name, "stage": "OUTPUT"},
        )
        output_dir = state.get("output_dir", "output/phase1") or "output/phase1"
        method = getattr(orch, method_name)
        result = method(state, output_dir, config=cfg)
        complete = dict(state.get("output_complete") or {})
        complete[node_name] = True
        return {
            "stage_outputs": {node_name: result},
            "output_complete": complete,
        }

    node.__name__ = node_name
    return node


# ─── Catalogue helpers ─────────────────────────────────────────────────


def _domain_ids() -> list[str]:
    """Canonical D-01..D-10 catalogue (matches ``Phase1Orchestrator.map_domains``)."""
    return [f"D-{i:02d}" for i in range(1, 11)]


def _reg_ids() -> list[str]:
    """Phase 1B regulations covered in CORR-018a/b scope (GDPR + CRA)."""
    return ["GDPR", "CRA"]


# ─── Sub-graph builders (CORR-018b Change 1) ───────────────────────────


def build_subphase_map():
    """Build and **compile** the MAP sub-graph: 10 per-domain nodes.

    Returns a compiled ``StateGraph``. When invoked via
    ``sub_graph.invoke(state, config=inner_cfg)`` from a parent node, the
    sub-graph creates a nested ``CHAIN "LangGraph"`` span and each
    ``map_DXX`` node creates its own ``SPAN`` + nested ``GEN`` chain in
    Langfuse.
    """
    g = StateGraph(Phase1GraphState)
    for did in _domain_ids():
        g.add_node(f"map_{did.replace('-', '')}", _make_map_node(did))

    prev = START
    for did in _domain_ids():
        node_name = f"map_{did.replace('-', '')}"
        g.add_edge(prev, node_name)
        prev = node_name
    g.add_edge(prev, END)
    return g.compile()


def build_subphase_1b():
    """Build and **compile** the Phase 1B sub-graph: 4 per-reg nodes."""
    g = StateGraph(Phase1GraphState)
    for reg in _reg_ids():
        g.add_node(f"interp_{reg}", _p1b_interp_node(reg))
        g.add_node(f"rat_{reg}", _p1b_rationale_node(reg))

    prev = START
    for reg in _reg_ids():
        g.add_edge(prev, f"interp_{reg}")
        prev = f"interp_{reg}"
    for reg in _reg_ids():
        g.add_edge(prev, f"rat_{reg}")
        prev = f"rat_{reg}"
    g.add_edge(prev, END)
    return g.compile()


def build_subphase_reduce():
    """Build and **compile** the REDUCE sub-graph: 3 nodes (deterministic → synthesis → compound)."""
    g = StateGraph(Phase1GraphState)
    g.add_node("deterministic", _reduce_det)
    g.add_node("synthesis", _reduce_synthesis)
    g.add_node("compound", _reduce_compound)
    g.add_edge(START, "deterministic")
    g.add_edge("deterministic", "synthesis")
    g.add_edge("synthesis", "compound")
    g.add_edge("compound", END)
    return g.compile()


def build_subphase_output():
    """Build and **compile** the OUTPUT sub-graph: 10 per-doc nodes.

    New in CORR-018b. Order: 04 body → 04a..04d → 05 → 06 → 07 → 07b → xlsx.
    """
    g = StateGraph(Phase1GraphState)
    for node_name in _OUTPUT_NODE_NAMES:
        g.add_node(node_name, _make_output_node(node_name))

    prev = START
    for node_name in _OUTPUT_NODE_NAMES:
        g.add_edge(prev, node_name)
        prev = node_name
    g.add_edge(prev, END)
    return g.compile()


# ─── Sub-graph node factory (used by root graph) ──────────────────────


def _make_subgraph_node(
    sub_graph_compiled: Any,
    run_name: str,
    metadata: dict[str, Any],
):
    """Create a node function that invokes a compiled sub-graph with config propagated.

    LangGraph treats this as a CHAIN invocation — the sub-graph appears as a
    nested "LangGraph" span in the trace, with the supplied ``run_name``
    becoming its outer CHAIN span name (when callbacks honour it).
    """
    def node(state: Phase1GraphState, config: RunnableConfig) -> dict:
        inner_cfg = _add_named_callback(config, run_name, metadata)
        result = sub_graph_compiled.invoke(state, config=inner_cfg)
        if not isinstance(result, dict):
            logger.warning(
                "Subgraph %s returned non-dict result: %s",
                run_name,
                type(result).__name__,
            )
            return {}
        merged_outputs = _merge_stage_outputs(
            state.get("stage_outputs"), result.get("stage_outputs")
        )
        return {"stage_outputs": merged_outputs}

    node.__name__ = run_name.replace(" ", "_").lower()
    return node


# ─── Root graph builder (CORR-018b Change 1) ───────────────────────────


def build_phase1_graph() -> StateGraph:
    """Build (uncompiled) root ``StateGraph`` with 5 top-level nodes.

    Node order is linear:

        START → load_baseline → subphase_map → subphase_1b →
        subphase_reduce → subphase_output → END

    Each ``subphase_*`` node invokes a compiled sub-graph, which creates
    a nested CHAIN span in Langfuse. The root graph itself has exactly
    5 nodes (was 18 in CORR-018a).

    Returns:
        An uncompiled :class:`StateGraph`. Tests can introspect nodes;
        callers should chain :func:`compile_phase1_graph` for invocation.
    """
    g = StateGraph(Phase1GraphState)

    g.add_node("load_baseline", _load_baseline)

    map_compiled = build_subphase_map()
    p1b_compiled = build_subphase_1b()
    reduce_compiled = build_subphase_reduce()
    output_compiled = build_subphase_output()

    g.add_node(
        "subphase_map",
        _make_subgraph_node(
            map_compiled, "MAP Sub-Phase", {"subphase": "map"}
        ),
    )
    g.add_node(
        "subphase_1b",
        _make_subgraph_node(
            p1b_compiled, "P1B Sub-Phase", {"subphase": "1b"}
        ),
    )
    g.add_node(
        "subphase_reduce",
        _make_subgraph_node(
            reduce_compiled, "REDUCE Sub-Phase", {"subphase": "reduce"}
        ),
    )
    g.add_node(
        "subphase_output",
        _make_subgraph_node(
            output_compiled, "OUTPUT Sub-Phase", {"subphase": "output"}
        ),
    )

    g.add_edge(START, "load_baseline")
    g.add_edge("load_baseline", "subphase_map")
    g.add_edge("subphase_map", "subphase_1b")
    g.add_edge("subphase_1b", "subphase_reduce")
    g.add_edge("subphase_reduce", "subphase_output")
    g.add_edge("subphase_output", END)

    return g


def compile_phase1_graph():
    """Return the compiled root StateGraph (``.invoke(state, config=...)`` ready)."""
    return build_phase1_graph().compile()


def run_phase1_graph(
    orchestrator: Phase1Orchestrator,
    case_path: str,
    regulatory_baseline_path: str | None = None,
    output_dir: str = "output/phase1",
    *,
    callbacks: list[Any] | None = None,
    tags: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """High-level entry: build the 5-node root graph + 4 compiled sub-graphs,
    wire callbacks/tags, invoke.

    Args:
        orchestrator: Shared :class:`Phase1Orchestrator` instance. Its
            ``_langfuse_handler`` is the canonical callback source; pass it
            through ``callbacks=[...]`` if available.
        case_path: Absolute case directory path.
        regulatory_baseline_path: Optional regulatory baseline directory.
        output_dir: Output directory for generated artefacts.
        callbacks: Optional list of LangChain ``BaseCallbackHandler``
            instances (typically the Langfuse handler).
        tags: Optional Langfuse tags propagated via
            ``metadata.langfuse_tags`` (e.g. ``["phase:phase1", "case:..."]``).
            The 4 sub-phase tags (``subphase:map``, ``subphase:1b``,
            ``subphase:reduce``, ``subphase:output``) are added
            automatically on top of the caller's tags.
        extra_metadata: Additional run metadata merged into
            ``config["metadata"]``.

    Returns:
        The final :class:`Phase1GraphState` produced by LangGraph (a dict
        containing ``case_path``, ``output_dir``, and a populated
        ``stage_outputs`` with one entry per executed node across all
        sub-phases).
    """
    full_tags = list(tags or []) + [
        "subphase:map",
        "subphase:1b",
        "subphase:reduce",
        "subphase:output",
    ]

    run_config: dict[str, Any] = {
        "configurable": {"orchestrator": orchestrator},
        "run_name": "AEGIS Phase 1",
    }
    if callbacks:
        run_config["callbacks"] = callbacks
    if full_tags or extra_metadata:
        meta: dict[str, Any] = {"langfuse_tags": full_tags}
        if extra_metadata:
            meta.update(extra_metadata)
        run_config["metadata"] = meta

    initial: Phase1GraphState = {
        "case_path": case_path,
        "regulatory_baseline_path": regulatory_baseline_path,
        "output_dir": output_dir,
        "case_name": Path(case_path).name if case_path else "default",
        "stage_outputs": {},
        "map_complete": {},
        "p1b_complete": {},
        "reduce_complete": {},
        "output_complete": {},
    }

    graph = compile_phase1_graph()
    result_state = graph.invoke(initial, config=run_config)

    client, _handler = get_langfuse_callback()
    if client is not None:
        try:
            client.flush()
        except Exception:
            pass

    return result_state


__all__ = [
    "Phase1GraphState",
    "build_phase1_graph",
    "build_subphase_map",
    "build_subphase_1b",
    "build_subphase_reduce",
    "build_subphase_output",
    "compile_phase1_graph",
    "run_phase1_graph",
]
