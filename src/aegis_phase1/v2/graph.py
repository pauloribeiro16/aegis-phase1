"""AEGIS Phase 1 full LangGraph (CORR-018a).

Replaces the CORR-017 thin wrapper. Provides ONE root trace in Langfuse with 18
named spans (load_baseline, map_D01..map_D10, p1b_interp_GDPR, p1b_interp_CRA,
p1b_rat_GDPR, p1b_rat_CRA, reduce_det, reduce_synthesis, reduce_compound).

The graph wraps granular orchestrator methods (added in S1) WITHOUT rewriting
the orchestrator internals. State is passed through the existing orchestrator
instance via config["configurable"]["orchestrator"].

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
    """Per-run state carried through the 18-node Phase 1 graph.

    Attributes:
        case_path: Absolute case directory path.
        regulatory_baseline_path: Optional regulatory baseline directory.
        output_dir: Output directory for generated artefacts.
        case_name: Derived case identifier (for trace tags).
        stage_outputs: Per-node result aggregator keyed by node id; useful
            for tests that introspect intermediate stages. The canonical
            pipeline state lives on the orchestrator instance.
        map_complete: Completion flags for the MAP stage (reserved for
            conditional edges in future contracts; not consumed by S2).
        p1b_complete: Completion flags for the Phase 1B stage (reserved).
        reduce_complete: Completion flags for the REDUCE stage (reserved).
    """

    case_path: str
    regulatory_baseline_path: str | None
    output_dir: str
    case_name: str
    stage_outputs: dict[str, Any]
    map_complete: dict[str, bool]
    p1b_complete: dict[str, bool]
    reduce_complete: dict[str, bool]


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


def _load_baseline(state: Phase1GraphState, config: RunnableConfig) -> dict:
    """Stage 0 — LOAD. Delegates to ``orch.load(case_path, baseline)``."""
    orch = _orchestrator_from(config)
    orch.load(state["case_path"], state.get("regulatory_baseline_path"))
    return {"stage_outputs": {"load": dict(orch.state)}}


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
        del cfg  # reserved for a future run_p1b-style propagation hook
        try:
            result = orch.map_single_domain(domain_id)
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
        _add_named_callback(
            config,
            span_name,
            {"spec": "P1B-LLM-01", "regulation": reg_id, "stage": "P1B"},
        )
        result = orch.run_p1b_single("P1B-LLM-01-INTERPRETATION", reg_id)
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
        _add_named_callback(
            config,
            span_name,
            {"spec": "P1B-LLM-02", "regulation": reg_id, "stage": "P1B"},
        )
        result = orch.run_p1b_single("P1B-LLM-02-RATIONALE", reg_id)
        complete = dict(state.get("p1b_complete") or {})
        complete[f"rat_{reg_id}"] = True
        return {
            "stage_outputs": {f"p1b_rat_{reg_id}": result},
            "p1b_complete": complete,
        }

    return node


def _reduce_det(state: Phase1GraphState, config: RunnableConfig) -> dict:
    """REDUCE — Deterministic. Always runs (no LLM)."""
    orch = _orchestrator_from(config)
    _add_named_callback(config, "REDUCE Deterministic", {"stage": "REDUCE-DET"})
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
    _add_named_callback(
        config,
        "P1C-LLM-03 STRATEGIC SYNTHESIS",
        {"spec": "P1C-LLM-03", "stage": "REDUCE-SYNTH"},
    )
    result = orch.reduce_synthesis()
    complete = dict(state.get("reduce_complete") or {})
    complete["synthesis"] = True
    return {
        "stage_outputs": {"reduce_synthesis": result},
        "reduce_complete": complete,
    }


def _reduce_compound(state: Phase1GraphState, config: RunnableConfig) -> dict:
    """REDUCE — P1C-LLM-02 COMPOUND EVENTS. No-op when synthesis cache absent."""
    orch = _orchestrator_from(config)
    _add_named_callback(
        config,
        "P1C-LLM-02 COMPOUND EVENTS",
        {"spec": "P1C-LLM-02", "stage": "REDUCE-COMPOUND"},
    )
    result = orch.reduce_compound()
    complete = dict(state.get("reduce_complete") or {})
    complete["compound"] = True
    return {
        "stage_outputs": {"reduce_compound": result},
        "reduce_complete": complete,
    }


def _domain_ids() -> list[str]:
    """Canonical D-01..D-10 catalogue (matches ``Phase1Orchestrator.map_domains``)."""
    return [f"D-{i:02d}" for i in range(1, 11)]


def _reg_ids() -> list[str]:
    """Phase 1B regulations covered in CORR-018a S2 scope (GDPR + CRA)."""
    return ["GDPR", "CRA"]


def build_phase1_graph() -> StateGraph:
    """Build (uncompiled) StateGraph with 18 nodes for MAP + 1B + REDUCE.

    Node order is linear:

        load_baseline → map_D01 → … → map_D10 → p1b_interp_GDPR →
        p1b_interp_CRA → p1b_rat_GDPR → p1b_rat_CRA → reduce_det →
        reduce_synthesis → reduce_compound → END

    Returns:
        An uncompiled :class:`StateGraph`. Tests can introspect nodes;
        callers should chain :func:`compile_phase1_graph` for invocation.
    """
    g = StateGraph(Phase1GraphState)

    g.add_node("load_baseline", _load_baseline)

    for did in _domain_ids():
        g.add_node(f"map_{did.replace('-', '')}", _make_map_node(did))

    for reg in _reg_ids():
        g.add_node(f"p1b_interp_{reg}", _p1b_interp_node(reg))
        g.add_node(f"p1b_rat_{reg}", _p1b_rationale_node(reg))

    g.add_node("reduce_det", _reduce_det)
    g.add_node("reduce_synthesis", _reduce_synthesis)
    g.add_node("reduce_compound", _reduce_compound)

    g.add_edge(START, "load_baseline")

    prev = "load_baseline"
    for did in _domain_ids():
        node_name = f"map_{did.replace('-', '')}"
        g.add_edge(prev, node_name)
        prev = node_name

    for reg in _reg_ids():
        g.add_edge(prev, f"p1b_interp_{reg}")
        prev = f"p1b_interp_{reg}"
    for reg in _reg_ids():
        g.add_edge(prev, f"p1b_rat_{reg}")
        prev = f"p1b_rat_{reg}"

    g.add_edge(prev, "reduce_det")
    g.add_edge("reduce_det", "reduce_synthesis")
    g.add_edge("reduce_synthesis", "reduce_compound")
    g.add_edge("reduce_compound", END)

    return g


def compile_phase1_graph():
    """Return the compiled StateGraph (``.invoke(state, config=...)`` ready)."""
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
    """High-level entry: build the 18-node graph, wire callbacks/tags, invoke.

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
        extra_metadata: Additional run metadata merged into
            ``config["metadata"]``.

    Returns:
        The final :class:`Phase1GraphState` produced by LangGraph (a dict
        containing ``case_path``, ``output_dir``, and a populated
        ``stage_outputs`` with one entry per executed node).
    """
    run_config: dict[str, Any] = {
        "configurable": {"orchestrator": orchestrator},
        "run_name": "AEGIS Phase 1",
    }
    if callbacks:
        run_config["callbacks"] = callbacks
    if tags or extra_metadata:
        meta: dict[str, Any] = {}
        if tags:
            meta["langfuse_tags"] = list(tags)
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
    "compile_phase1_graph",
    "run_phase1_graph",
]
