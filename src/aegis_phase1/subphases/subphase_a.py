# WARNING: Human review is disabled by default. Set skip_interrupt=False to enable.
"""subphase_a — Wires the 8 SubPhase A nodes in linear sequence."""

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from aegis_phase1.nodes._validate_a import _validate_a
from aegis_phase1.nodes.a02_stakeholders import a02_stakeholders
from aegis_phase1.nodes.a03_business_goals import a03_business_goals
from aegis_phase1.nodes.a04_complexity_tier import a04_complexity_tier
from aegis_phase1.nodes.a05_conditional_extensions import a05_conditional_extensions
from aegis_phase1.nodes.a06_regulatory_interactions import a06_regulatory_interactions
from aegis_phase1.nodes.a07_compliance_context import a07_compliance_context
from aegis_phase1.nodes.n01_parse_inputs import n01_parse_inputs
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def build_subphase_a(skip_interrupt: bool = True):
    """Build the SubPhase A LangGraph.

    Flow: parse_inputs -> stakeholders -> business_goals -> complexity_tier
          -> conditional_extensions -> regulatory_interactions -> compliance_context
          -> validate_a -> END

    Args:
        skip_interrupt: If True, skip human review interrupt.

    Returns:
        Compiled LangGraph.
    """
    checkpointer = MemorySaver()
    graph = StateGraph(Phase1State)

    # ── Nodes ────────────────────────────────────────────────────────
    graph.add_node("n01_parse_inputs", n01_parse_inputs)
    graph.add_node("a02_stakeholders", a02_stakeholders)
    graph.add_node("a03_business_goals", a03_business_goals)
    graph.add_node("a04_complexity_tier", a04_complexity_tier)
    graph.add_node("a05_conditional_extensions", a05_conditional_extensions)
    graph.add_node("a06_regulatory_interactions", a06_regulatory_interactions)
    graph.add_node("a07_compliance_context", a07_compliance_context)
    graph.add_node("_validate_a", _validate_a)

    # ── Edges (linear sequence) ──────────────────────────────────────
    graph.add_edge(START, "n01_parse_inputs")
    graph.add_edge("n01_parse_inputs", "a02_stakeholders")
    graph.add_edge("a02_stakeholders", "a03_business_goals")
    graph.add_edge("a03_business_goals", "a04_complexity_tier")
    graph.add_edge("a04_complexity_tier", "a05_conditional_extensions")
    graph.add_edge("a05_conditional_extensions", "a06_regulatory_interactions")
    graph.add_edge("a06_regulatory_interactions", "a07_compliance_context")
    graph.add_edge("a07_compliance_context", "_validate_a")
    graph.add_edge("_validate_a", END)

    interrupt_before = [] if skip_interrupt else ["_validate_a"]
    return graph.compile(interrupt_before=interrupt_before, checkpointer=checkpointer)
