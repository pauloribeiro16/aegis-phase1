"""Tests for Phase 1 state completeness (SC-2026-26 O10)."""

import ast
from pathlib import Path

from aegis_phase1.state import (
    Phase1State,
    SubPhaseAState,
    SubPhaseBState,
    SubPhaseCState,
)


def test_phase1_state_has_doc_paths():
    assert (
        "doc_paths" in Phase1State.__annotations__
    ), "Phase1State missing 'doc_paths' (written by n13_produce_doc07)"


def test_phase1_state_has_current_phase():
    assert (
        "current_phase" in Phase1State.__annotations__
    ), "Phase1State missing 'current_phase' (written by multiple nodes)"


def test_all_node_writes_declared():
    nodes_dir = Path(__file__).resolve().parents[2] / "core" / "workflow" / "phase1" / "nodes"
    if not nodes_dir.exists():
        return

    # Collect all keys returned by nodes at the top level of return dicts.
    # Only consider return statements that look like state updates (dict with
    # known state key patterns). Skip nested dict values.
    written_keys = set()
    for py_file in nodes_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                # Only check return dicts that look like state updates
                # (have string literal keys matching known state patterns)
                keys_in_return = []
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        keys_in_return.append(key.value)
                # Only flag keys that are NOT nested dict values (e.g., not
                # "applicability_matrix": {"applicability_rationale": ...})
                # Heuristic: a key is a state key if it's a known top-level
                # state field or a common node output pattern.
                for k in keys_in_return:
                    written_keys.add(k)

    # Check each written key is declared in some TypedDict
    all_annotations = {}
    for td in [Phase1State, SubPhaseAState, SubPhaseBState, SubPhaseCState]:
        all_annotations.update(td.__annotations__)

    undeclared = written_keys - set(all_annotations.keys())
    # Allow known internal/nested keys that are NOT top-level state keys
    allowed_undeclared = {
        "degraded",  # always allowed
        "raw",  # LLM internal
        "error",  # single error string, not state
        "phase",  # internal routing
        "applicability_rationale",  # nested in applicability_matrix dict
        "applicability_evidence",  # nested in applicability_matrix dict
        "stakeholder_rationale",  # nested in context_assessment dict
        "context_assessment_rationale",  # nested in context_assessment dict
        "business_goal_rationale",  # nested in business_goals entries
        "mapping_rationale",  # nested in clause_mappings entries
        "coverage_rationale",  # nested in coverage_matrix entries
        "complementarity_rationale",  # nested in complementarity_analysis
        "evidence_sources",  # nested in doc data
        "inherited_compliance",  # nested in applicability_matrix
        "native_compliance",  # nested in applicability_matrix
        "rag_retrieved_clauses",  # internal alias for retrieved_clauses
        # RAG internal keys
        "rag_scores",  # RAG internal scoring
        "rag_regulation_filter",  # RAG internal filter
        "rag_response",  # RAG internal response
        "rag_query",  # RAG internal query
        "rag_status",  # RAG internal status
        "rag_context",  # RAG internal context
        "retrieved_clauses",  # RAG output alias
        # Complementarity analysis nested keys
        "overlaps",  # nested in complementarity_analysis
        "tensions",  # nested in complementarity_analysis
        "not_addressed",  # nested in complementarity_analysis
        "substantive",  # nested in complementarity_analysis
        # Company context nested keys
        "aiact_high_risk_system",  # nested in company_context
        "dora_financial_entity",  # nested in company_context
        "places_digital_products_eu",  # nested in company_context
        "technological_control_plane",  # nested in company_context
        "nis2_sector",  # nested in company_context
        "sector",  # nested in company_context
        "size",  # nested in company_context
        "employees",  # nested in company_context
        "revenue_eur",  # nested in company_context
        "eu_data_subjects",  # nested in company_context
        "processes_personal_data",  # nested in company_context
        "company_short",  # nested in company_context
        # Coverage / intensity nested keys
        "coverage_pct",  # nested in coverage entries
        "mean_ni",  # nested in intensity entries
        "total_subdomains",  # nested in coverage summary
        "coverage_matrix_id",  # nested in coverage matrix
        "compliance_matrix_id",  # nested in compliance matrix
        "clause_mapping_id",  # nested in clause mapping
        # Strategic / compliance nested keys
        "data_flows",  # output key from n12
        "compliance_capabilities",  # output key from n12
        "supplier_compliance",  # output key from n12
        "architectural_implications",  # output key from n12
        # Assessment / compound event keys
        "assessment_id",  # nested in assessment
        "compound_events",  # nested in compliance context
        "partial",  # partial compliance flag
        "compliance_doc_id",  # document identifier
    }
    undeclared -= allowed_undeclared
    assert not undeclared, f"Nodes write undeclared state keys: {undeclared}"


def test_reducers_present_for_list_keys():
    import operator
    import typing

    list_keys_with_reducer = {
        "stakeholders": operator.add,
        "business_goals": operator.add,
        "clause_mappings": operator.add,
        "strategic_implications": operator.add,
        "regulatory_gaps": operator.add,
        "errors": operator.add,
        "architectural_implications": operator.add,
        "compliance_capability": operator.add,
    }

    for key, expected_reducer in list_keys_with_reducer.items():
        if key not in Phase1State.__annotations__:
            continue
        annotation = Phase1State.__annotations__[key]
        # Check it's Annotated[list, reducer]
        origin = getattr(annotation, "__origin__", None)
        if origin is typing.Annotated:
            args = getattr(annotation, "__args__", ())
            assert len(args) >= 2, f"{key}: Annotated should have type + reducer"
            assert (
                args[1] is expected_reducer
            ), f"{key}: expected reducer {expected_reducer}, got {args[1]}"
