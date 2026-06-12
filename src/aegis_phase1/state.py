"""state — TypedDict definitions for Phase 1 workflow state."""

import logging
import operator
from typing import Annotated, TypedDict

# ─── Module logger (MANDATORY) ───────────────────────────────────────
logger = logging.getLogger(__name__)


class Phase1State(TypedDict):
    case_config: dict
    ontology: dict
    intake_markdown: str
    taxonomy_markdown: str

    stakeholders: Annotated[list, operator.add]
    business_goals: Annotated[list, operator.add]
    company_context: dict
    complexity_tier: str
    conditional_extensions: Annotated[list, operator.add]
    regulatory_interactions: Annotated[list, operator.add]
    compliance_context: dict

    context_assessment: dict
    regulatory_flags: dict

    applicable_regulations: list
    applicability_matrix: dict
    clause_mappings: Annotated[list, operator.add]
    normative_intensities: dict
    extension_blocks: dict

    regulations: list
    regulatory_clauses: Annotated[list, operator.add]
    security_control_domains: list
    domain_coverage_entries: list
    responsibility_entries: Annotated[list, operator.add]
    implementation_mappings: list

    coverage_matrix: dict
    coverage_summary: dict
    complementarity_analysis: dict
    complementarity_analyses: Annotated[list, operator.add]
    domain_elaboration_entries: Annotated[list, operator.add]
    strategic_implications: Annotated[list, operator.add]
    regulatory_gaps: Annotated[list, operator.add]
    regulatory_obligations: Annotated[list, operator.add]
    structured_compliance_matrix: dict

    human_feedback: str
    current_subphase: str
    case_path: str
    errors: Annotated[list, operator.add]
    degraded: Annotated[bool, operator.or_]
    retry_count: Annotated[int, operator.add]

    doc_04_path: str
    doc_05_path: str
    doc_06_path: str
    doc_07_path: str
    doc_paths: dict
    current_phase: str

    regulation_id: str
    clauses: list

    # ─── Raw CSV data (loaded by n01, consumed by subphase nodes) ───
    # These fields MUST be declared here so LangGraph doesn't drop them
    # between node invocations.
    clause_subdomain_mapping: list
    conditional_extensions_data: list
    regulatory_interactions_data: list
    complementarity_analyses_data: list
    domain_coverages_data: list
    domain_elaborations_data: list
    implementation_mappings_data: list
    raw_clauses: list  # Used by b02 to seed enrichment without polluting regulatory_clauses


class Phase1Output(TypedDict):
    doc_04_path: str
    doc_05_path: str
    doc_06_path: str
    doc_07_path: str
    clause_mappings: list
    coverage_summary: dict
    complementarity_analysis: dict
    strategic_implications: list
    regulatory_gaps: list
    structured_compliance_matrix: dict
    errors: list
    degraded: bool


class SubPhaseAState(TypedDict):
    company_context: dict
    stakeholders: Annotated[list, operator.add]
    business_goals: Annotated[list, operator.add]
    complexity_tier: str
    conditional_extensions: Annotated[list, operator.add]
    regulatory_interactions: Annotated[list, operator.add]
    compliance_context: dict


class SubPhaseBState(TypedDict):
    regulations: list
    regulatory_clauses: Annotated[list, operator.add]
    security_control_domains: list
    domain_coverage_entries: list
    responsibility_entries: Annotated[list, operator.add]
    implementation_mappings: list


class SubPhaseCState(TypedDict):
    complementarity_analyses: Annotated[list, operator.add]
    domain_elaboration_entries: Annotated[list, operator.add]
    strategic_implications: Annotated[list, operator.add]
    regulatory_obligations: Annotated[list, operator.add]
    structured_compliance_matrix: dict


# ─── Output TypedDicts (backward compat — used by subphase graphs) ───


class SubPhaseAOutput(TypedDict):
    stakeholders: list
    business_goals: list
    company_context: dict
    context_assessment: dict
    regulatory_flags: dict
    architectural_implications: list
    compliance_capability: list
    errors: list


class SubPhaseBOutput(TypedDict):
    applicable_regulations: list
    applicability_matrix: dict
    clause_mappings: list
    normative_intensities: dict
    extension_blocks: dict
    coverage_matrix: dict
    coverage_summary: dict


class SubPhaseCOutput(TypedDict):
    coverage_matrix: dict
    coverage_summary: dict
    complementarity_analysis: dict
    strategic_implications: list
    regulatory_gaps: list
    structured_compliance_matrix: dict
    doc_paths: dict
