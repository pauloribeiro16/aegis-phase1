# WARNING: Human review is disabled by default. Set skip_interrupt=False to enable.
"""subphase_c — Wires the 6 SubPhase C nodes."""

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from aegis_phase1.nodes._validate_c import _validate_c
from aegis_phase1.nodes.c01_complementarity import c01_complementarity
from aegis_phase1.nodes.c02_domain_elaboration import c02_domain_elaboration
from aegis_phase1.nodes.c03_strategic_implications import c03_strategic_implications
from aegis_phase1.nodes.c04_obligation_shells import c04_obligation_shells
from aegis_phase1.nodes.c05_matrix import c05_matrix
from aegis_phase1.nodes.produce_documents import produce_documents
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def build_subphase_c(skip_interrupt: bool = True):
    """Build the SubPhase C LangGraph.

    Flow: complementarity -> domain_elaboration -> strategic_implications
          -> obligation_shells -> matrix -> validate_c -> END

    Args:
        skip_interrupt: If True, skip human review interrupt.

    Returns:
        Compiled LangGraph.
    """
    checkpointer = MemorySaver()
    graph = StateGraph(Phase1State)

    # ── Nodes ────────────────────────────────────────────────────────
    graph.add_node("c01_complementarity", c01_complementarity)
    graph.add_node("c02_domain_elaboration", c02_domain_elaboration)
    graph.add_node("c03_strategic_implications", c03_strategic_implications)
    graph.add_node("c04_obligation_shells", c04_obligation_shells)
    graph.add_node("c05_matrix", c05_matrix)
    graph.add_node("produce_documents", produce_documents)
    graph.add_node("_validate_c", _validate_c)

    # ── Edges (linear sequence) ──────────────────────────────────────
    graph.add_edge(START, "c01_complementarity")
    graph.add_edge("c01_complementarity", "c02_domain_elaboration")
    graph.add_edge("c02_domain_elaboration", "c03_strategic_implications")
    graph.add_edge("c03_strategic_implications", "c04_obligation_shells")
    graph.add_edge("c04_obligation_shells", "c05_matrix")
    graph.add_edge("c05_matrix", "produce_documents")
    graph.add_edge("produce_documents", "_validate_c")
    graph.add_edge("_validate_c", END)

    interrupt_before = [] if skip_interrupt else ["_validate_c"]
    return graph.compile(interrupt_before=interrupt_before, checkpointer=checkpointer)
