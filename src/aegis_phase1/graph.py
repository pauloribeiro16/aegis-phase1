"""graph — Phase 1 LangGraph orchestration.

Flow: START -> parse_inputs -> subphase_a -> subphase_b -> subphase_c -> END
"""

import logging
import os

from langgraph.graph import END, START, StateGraph

from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _run_subphase_a(state: Phase1State, config=None) -> dict:
    """Run SubPhase A as a compiled sub-graph."""
    from aegis_phase1.subphase_a import build_subphase_a

    configurable = config.get("configurable", {}) if config else {}
    skip_interrupt = configurable.get("skip_interrupt", True)
    logger.debug("[graph] Running SubPhase A (skip_interrupt=%s)", skip_interrupt)

    sub_graph = build_subphase_a(skip_interrupt=skip_interrupt)
    result = sub_graph.invoke(state, config=config)

    logger.info("[graph] SubPhase A complete")
    return {
        "stakeholders": result.get("stakeholders", []),
        "business_goals": result.get("business_goals", []),
        "company_context": result.get("company_context", {}),
        "complexity_tier": result.get("complexity_tier", ""),
        "conditional_extensions": result.get("conditional_extensions", []),
        "regulatory_interactions": result.get("regulatory_interactions", []),
        "compliance_context": result.get("compliance_context", {}),
        "applicable_regulations": result.get("applicable_regulations", []),
        "regulations": result.get("regulations", []),
        "regulatory_clauses": result.get("regulatory_clauses", []),
        "security_control_domains": result.get("security_control_domains", []),
        "clause_subdomain_mapping": result.get("clause_subdomain_mapping", []),
        "complementarity_analyses_data": result.get("complementarity_analyses_data", []),
        "domain_coverages_data": result.get("domain_coverages_data", []),
        "domain_elaborations_data": result.get("domain_elaborations_data", []),
        "implementation_mappings_data": result.get("implementation_mappings_data", []),
        "conditional_extensions_data": result.get("conditional_extensions_data", []),
        "regulatory_interactions_data": result.get("regulatory_interactions_data", []),
        "current_subphase": "A_COMPLETE",
        "errors": result.get("errors", []),
    }


def _run_subphase_b(state: Phase1State, config=None) -> dict:
    """Run SubPhase B as a compiled sub-graph."""
    from aegis_phase1.subphase_b import build_subphase_b

    configurable = config.get("configurable", {}) if config else {}
    skip_interrupt = configurable.get("skip_interrupt", True)
    logger.debug("[graph] Running SubPhase B (skip_interrupt=%s)", skip_interrupt)

    sub_graph = build_subphase_b(skip_interrupt=skip_interrupt)
    result = sub_graph.invoke(state, config=config)

    logger.info("[graph] SubPhase B complete")
    return {
        "regulations": result.get("regulations", []),
        "regulatory_clauses": result.get("regulatory_clauses", []),
        "domain_coverage_entries": result.get("domain_coverage_entries", []),
        "responsibility_entries": result.get("responsibility_entries", []),
        "implementation_mappings": result.get("implementation_mappings", []),
        "current_subphase": "B_COMPLETE",
        "errors": result.get("errors", []),
    }


def _run_subphase_c(state: Phase1State, config=None) -> dict:
    """Run SubPhase C as a compiled sub-graph."""
    from aegis_phase1.subphase_c import build_subphase_c

    configurable = config.get("configurable", {}) if config else {}
    skip_interrupt = configurable.get("skip_interrupt", True)
    logger.debug("[graph] Running SubPhase C (skip_interrupt=%s)", skip_interrupt)

    sub_graph = build_subphase_c(skip_interrupt=skip_interrupt)
    result = sub_graph.invoke(state, config=config)

    logger.info("[graph] SubPhase C complete")
    return {
        "complementarity_analyses": result.get("complementarity_analyses", []),
        "domain_elaboration_entries": result.get("domain_elaboration_entries", []),
        "strategic_implications": result.get("strategic_implications", []),
        "regulatory_obligations": result.get("regulatory_obligations", []),
        "structured_compliance_matrix": result.get("structured_compliance_matrix", {}),
        "doc_paths": result.get("doc_paths", {}),
        "doc_04_path": result.get("doc_04_path", ""),
        "doc_05_path": result.get("doc_05_path", ""),
        "doc_06_path": result.get("doc_06_path", ""),
        "doc_07_path": result.get("doc_07_path", ""),
        "current_subphase": "C_COMPLETE",
        "errors": result.get("errors", []),
    }


def build_phase1_graph():
    """Build the Phase 1 LangGraph.

    Flow: START -> parse_inputs -> subphase_a -> subphase_b -> subphase_c -> END

    Returns:
        Compiled StateGraph.
    """
    graph = StateGraph(Phase1State)

    graph.add_node("parse_inputs", _parse_inputs)
    graph.add_node("subphase_a", _run_subphase_a)
    graph.add_node("subphase_b", _run_subphase_b)
    graph.add_node("subphase_c", _run_subphase_c)

    graph.add_edge(START, "parse_inputs")
    graph.add_edge("parse_inputs", "subphase_a")
    graph.add_edge("subphase_a", "subphase_b")
    graph.add_edge("subphase_b", "subphase_c")
    graph.add_edge("subphase_c", END)

    return graph.compile()


def _parse_inputs(state: Phase1State, config=None) -> dict:
    """Top-level parse_inputs that delegates to the node function."""
    from aegis_phase1.nodes.n01_parse_inputs import n01_parse_inputs

    return n01_parse_inputs(state)


def run_phase1(
    case_path: str, verbose: bool = False, skip_interrupt: bool = True, mock_llm: bool = False
) -> dict:
    """Run the full Phase 1 pipeline.

    Args:
        case_path: Path to the case directory.
        verbose: If True, enable DEBUG logging.
        skip_interrupt: If True, skip human review interrupts.
        mock_llm: If True, use mock data instead of real LLM calls (for testing).

    Returns:
        Final state dict with all Phase 1 outputs.
    """
    if mock_llm:
        os.environ["MOCK_LLM"] = "true"
    from aegis_phase1.logging_config import configure_logging

    configure_logging(level="DEBUG" if verbose else "INFO", force=True)

    # Load case config
    from aegis_phase1.config.case_loader import load_case_yaml

    try:
        case_config = load_case_yaml(case_path)
    except Exception:
        logger.exception("[workflow] Failed to load case config from %s", case_path)
        case_config = {"case": "unknown"}

    case_name = case_config.get("case", case_config.get("name", "unknown"))

    # Langfuse (opt-in)
    try:
        from aegis_phase1.llm.tracing import get_langfuse_callback

        langfuse, handler = get_langfuse_callback(case_name=case_name, phase="phase1")
    except Exception:
        langfuse, handler = None, None

    if handler:
        logger.info("[workflow] Langfuse enabled phase=phase1 case=%s", case_name)
    else:
        logger.info("[workflow] Langfuse not available or disabled")

    # Check for MOCK_LLM
    mock_llm = os.environ.get("MOCK_LLM", "").lower() in ("true", "1", "yes")
    if mock_llm:
        logger.info("[workflow] MOCK_LLM enabled — LLM calls will return mock data")

    initial_state: dict = {
        "case_config": case_config,
        "ontology": {},
        "intake_markdown": "",
        "taxonomy_markdown": "",
        "stakeholders": [],
        "business_goals": [],
        "company_context": {},
        "complexity_tier": "",
        "conditional_extensions": [],
        "regulatory_interactions": [],
        "compliance_context": {},
        "context_assessment": {},
        "regulatory_flags": {},
        "applicable_regulations": [],
        "applicability_matrix": {},
        "regulations": [],
        "regulatory_clauses": [],
        "security_control_domains": [],
        "clause_subdomain_mapping": [],
        "domain_coverage_entries": [],
        "responsibility_entries": [],
        "implementation_mappings": [],
        "complementarity_analyses": [],
        "domain_elaboration_entries": [],
        "strategic_implications": [],
        "regulatory_obligations": [],
        "structured_compliance_matrix": {},
        "human_feedback": "",
        "current_subphase": "",
        "case_path": case_path,
        "errors": [],
        "degraded": False,
        "retry_count": 0,
    }

    run_config: dict = {
        "configurable": {
            "case_path": case_path,
            "case_config": case_config,
            "skip_interrupt": skip_interrupt,
        }
    }

    if handler:
        run_config["callbacks"] = [handler]
        run_config["metadata"] = {"langfuse_tags": ["phase:phase1", f"case:{case_name}"]}

    graph = build_phase1_graph()

    logger.info("[workflow] Running Phase 1 full pipeline for case: %s", case_name)

    try:
        result = graph.invoke(initial_state, config=run_config)
    except Exception as e:
        logger.error("[workflow] Error: %s", str(e))
        return {"error": str(e), "errors": [str(e)]}

    if langfuse:
        try:
            langfuse.flush()
        except Exception:
            logger.warning("[workflow] flush error", exc_info=True)

    logger.info("[workflow] Phase 1 complete. Keys: %s", list(result.keys())[:20])
    return result
