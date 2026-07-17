"""Thin LangGraph wrapper around Phase1Orchestrator (AEGIS-P1-CORR-017).

DEPRECATED — superseded by the proper 18-node StateGraph in
:mod:`aegis_phase1.v2.graph` (AEGIS-P1-CORR-018a S2). This module is kept as
a back-compat shim so:

- ``from aegis_phase1.v2.trace_graph import build_orchestrator_graph`` and
  friends continue to work for any consumer that has not yet migrated.
- The ``-W error::DeprecationWarning`` smoke check still fires the warning.
- ``tests/unit/v2/test_trace_graph_corr017.py`` (legacy test file) keeps
  validating the original 5-node behaviour.

New code should import from :mod:`aegis_phase1.v2.graph`.

Mirrors the aegis-kg pattern from ``core/workflow/phase1/graph.py:121-282``.
Does NOT rewrite :class:`Phase1Orchestrator` internals; instead wraps each
pipeline stage as a graph node that calls the existing method on a shared
orchestrator instance.

State schema (:class:`OrchestratorRunState`) carries the case/baseline/output
paths and a snapshot of ``orch.state``. The orchestrator mutates its own
internal ``state`` dict; each node round-trips a shallow copy through
``state["v2_state"]`` so LangGraph's reducer bookkeeping is exercised
end-to-end and the trace UI sees a per-stage snapshot.

When invoked with ``config={"callbacks":[handler]}``:

- Each node becomes a chain span in Langfuse (named after the node).
- Every LLM call inside the orchestrator method nests under the node's span.
- Result: ONE root trace → 5 stage spans → nested LLM generations with tokens.

This file must NOT instantiate ChatOllama at import time — only when the
graph is invoked, so test setup can mock the LLM freely.

NOTE: ``from __future__ import annotations`` is intentionally NOT used here.
LangGraph's ``RunnableCallable`` inspects parameter annotations at runtime
to decide whether to inject the ``config`` kwarg; PEP-563 string annotations
defeat that introspection and silently drop ``config`` to its default
``None`` inside every node, breaking the orchestrator handoff.
"""

import warnings

warnings.warn(
    "aegis_phase1.v2.trace_graph is deprecated; use aegis_phase1.v2.graph "
    "(AEGIS-P1-CORR-018a S2). The 5-node thin wrapper was replaced by the "
    "18-node StateGraph on 2026-07-16. This shim emits DeprecationWarning "
    "on import and will be removed in a follow-up contract.",
    DeprecationWarning,
    stacklevel=2,
)

from pathlib import Path  # noqa: E402 — placed after deprecation warning
from typing import Any, Optional, TypedDict  # noqa: E402

from langchain_core.runnables import RunnableConfig  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402

from aegis_phase1.v2.domain.processor import (  # noqa: E402
    MapPartialFailure,
    OllamaUnreachable,
)
from aegis_phase1.v2.graph import (  # noqa: E402,F401 — re-export new names
    Phase1GraphState,
    build_phase1_graph,
    compile_phase1_graph,
    run_phase1_graph,
)
from aegis_phase1.v2.orchestrator import Phase1Orchestrator  # noqa: E402,F401


class OrchestratorRunState(TypedDict, total=False):
    """Per-run state carried through the trace graph.

    Attributes:
        case_path: Absolute path to the case directory.
        regulatory_baseline_path: Absolute path to the regulatory baseline
            directory (canonical, replaces deprecated ``preprocessing_path``).
        output_dir: Output directory for generated artefacts.
        v2_state: Shallow snapshot of ``orch.state`` after each node — useful
            for trace inspection and for tests that introspect intermediate
            stages. The canonical state lives on the orchestrator instance.
    """

    case_path: str
    regulatory_baseline_path: str | None
    output_dir: str
    v2_state: dict[str, Any]


def _orchestrator_from(config: RunnableConfig) -> Phase1Orchestrator:
    """Pull the shared orchestrator out of ``config["configurable"]``."""
    if config is None:
        raise RuntimeError(
            "Trace graph nodes require a RunnableConfig carrying the "
            "orchestrator under config['configurable']['orchestrator']."
        )
    configurable = config.get("configurable") or {}
    orch = configurable.get("orchestrator")
    if orch is None:
        raise RuntimeError(
            "config['configurable']['orchestrator'] is required for "
            "trace graph execution."
        )
    return orch  # type: ignore[no-any-return]


def _load(
    state: OrchestratorRunState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Stage 0 — LOAD. Calls ``orchestrator.load(case_path, baseline)``."""
    orch = _orchestrator_from(config)
    orch.load(state["case_path"], state.get("regulatory_baseline_path"))
    return {"v2_state": dict(orch.state)}


def _map(
    state: OrchestratorRunState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Stage 1 — MAP. Calls ``orchestrator.map_domains()``."""
    orch = _orchestrator_from(config)
    orch.map_domains()
    return {"v2_state": dict(orch.state)}


def _phase_1b(
    state: OrchestratorRunState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Stage 1B — per-regulation P1B-LLM-02 RATIONALE.

    Calls ``orchestrator.run_phase_1b()``. Failures are swallowed by
    ``run_phase_1b`` itself (logged + persisted) so the pipeline continues;
    the graph does not need to handle them.
    """
    orch = _orchestrator_from(config)
    orch.run_phase_1b()
    return {"v2_state": dict(orch.state)}


def _reduce(
    state: OrchestratorRunState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Stage 2 — REDUCE. Calls ``orchestrator.reduce()``."""
    orch = _orchestrator_from(config)
    orch.reduce()
    return {"v2_state": dict(orch.state)}


def _output(
    state: OrchestratorRunState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Stage 3 — OUTPUT. Calls ``orchestrator.generate_outputs(output_dir)``."""
    orch = _orchestrator_from(config)
    orch.generate_outputs(state.get("output_dir", "output/phase1"))
    return {"v2_state": dict(orch.state)}


def build_orchestrator_graph() -> StateGraph:
    """Construct (but do NOT compile) the 5-stage LangGraph.

    Stages chain linearly: ``load → map → phase_1b → reduce → output → END``.
    No conditional edges (intentionally simple; the orchestrator raises on
    exceptions that the runner handles).

    Returns an uncompiled :class:`StateGraph` so tests can introspect it
    (e.g. add a fake node, list nodes, etc.). :func:`compile_orchestrator_graph`
    produces the runtime artifact.
    """
    g = StateGraph(OrchestratorRunState)
    g.add_node("load", _load)
    g.add_node("map", _map)
    g.add_node("phase_1b", _phase_1b)
    g.add_node("reduce", _reduce)
    g.add_node("output", _output)
    g.add_edge(START, "load")
    g.add_edge("load", "map")
    g.add_edge("map", "phase_1b")
    g.add_edge("phase_1b", "reduce")
    g.add_edge("reduce", "output")
    g.add_edge("output", END)
    return g


def compile_orchestrator_graph():
    """Return the compiled graph ready to ``.invoke(state, config=...)``."""
    return build_orchestrator_graph().compile()


def run_orchestrator_graph(
    orchestrator: Phase1Orchestrator,
    case_path: str,
    regulatory_baseline_path: str | None = None,
    output_dir: str = "output/phase1",
    *,
    callbacks: list[Any] | None = None,
    tags: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """High-level entry: build the graph, wire callbacks/tags, invoke, flush.

    Args:
        orchestrator: Shared :class:`Phase1Orchestrator` instance whose
            methods the nodes invoke. The caller is responsible for having
            already loaded ``orch._langfuse_handler`` (if any) — see
            :meth:`Phase1Orchestrator.__init__` which auto-attaches it.
        case_path: Absolute case directory path.
        regulatory_baseline_path: Optional regulatory baseline directory
            (canonical; replaces deprecated ``preprocessing_path``).
        output_dir: Output directory for generated artefacts.
        callbacks: Optional list of LangChain ``BaseCallbackHandler``
            instances (typically a Langfuse ``CallbackHandler``).
        tags: Optional Langfuse tags propagated via ``metadata.langfuse_tags``.
        extra_metadata: Additional run metadata merged into
            ``config["metadata"]``.

    Returns:
        The final :class:`OrchestratorRunState` produced by LangGraph.

    Raises:
        OllamaUnreachable: When the LLM is unreachable during MAP.
        MapPartialFailure: When ≥1 domain ends with status FAILED after
            retries (same semantics as :meth:`Phase1Orchestrator.run_all`).
    """
    from aegis_phase1.llm.tracing import get_langfuse_callback

    run_config: dict[str, Any] = {
        "configurable": {"orchestrator": orchestrator},
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

    initial: OrchestratorRunState = {
        "case_path": case_path,
        "regulatory_baseline_path": regulatory_baseline_path,
        "output_dir": output_dir,
        "v2_state": {},
    }

    graph = compile_orchestrator_graph()
    result_state = graph.invoke(initial, config=run_config)

    client, _handler = get_langfuse_callback()
    if client is not None:
        try:
            client.flush()
        except Exception:
            pass

    return result_state


__all__ = [
    "OrchestratorRunState",
    "build_orchestrator_graph",
    "compile_orchestrator_graph",
    "run_orchestrator_graph",
    "Phase1GraphState",
    "build_phase1_graph",
    "compile_phase1_graph",
    "run_phase1_graph",
]
