# WARNING: Human review is disabled by default. Set skip_interrupt=False to enable.
"""subphase_b — Wires the 7 SubPhase B nodes."""

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from aegis_phase1.nodes._validate_b import _validate_b
from aegis_phase1.nodes.b01_load_regulations import b01_load_regulations
from aegis_phase1.nodes.b02_load_clauses_batch import b02_load_clauses_batch
from aegis_phase1.nodes.b03_map_clause_domain import b03_map_clause_domain
from aegis_phase1.nodes.b04_coverage_entries import b04_coverage_entries
from aegis_phase1.nodes.b05_responsibility import b05_responsibility
from aegis_phase1.nodes.b06_implementation_mapping import b06_implementation_mapping
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def build_subphase_b(skip_interrupt: bool = True):
    """Build the SubPhase B LangGraph.

    Flow: load_regulations -> load_clauses_batch -> map_clause_domain
          -> coverage_entries -> responsibility -> implementation_mapping
          -> validate_b -> END

    Args:
        skip_interrupt: If True, skip human review interrupt.

    Returns:
        Compiled LangGraph.
    """
    checkpointer = MemorySaver()
    graph = StateGraph(Phase1State)

    # ── Nodes ────────────────────────────────────────────────────────
    graph.add_node("b01_load_regulations", b01_load_regulations)
    graph.add_node("b02_load_clauses_batch", b02_load_clauses_batch)
    graph.add_node("b03_map_clause_domain", b03_map_clause_domain)
    graph.add_node("b04_coverage_entries", b04_coverage_entries)
    graph.add_node("b05_responsibility", b05_responsibility)
    graph.add_node("b06_implementation_mapping", b06_implementation_mapping)
    graph.add_node("_validate_b", _validate_b)

    # ── Edges (linear sequence) ──────────────────────────────────────
    graph.add_edge(START, "b01_load_regulations")
    graph.add_edge("b01_load_regulations", "b02_load_clauses_batch")
    graph.add_edge("b02_load_clauses_batch", "b03_map_clause_domain")
    graph.add_edge("b03_map_clause_domain", "b04_coverage_entries")
    graph.add_edge("b04_coverage_entries", "b05_responsibility")
    graph.add_edge("b05_responsibility", "b06_implementation_mapping")
    graph.add_edge("b06_implementation_mapping", "_validate_b")
    graph.add_edge("_validate_b", END)

    interrupt_before = [] if skip_interrupt else ["_validate_b"]
    return graph.compile(interrupt_before=interrupt_before, checkpointer=checkpointer)
