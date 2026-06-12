"""c05_matrix — Deterministic: assembles StructuredComplianceMatrix with all elements."""

import logging
from datetime import date, datetime
from typing import Any

from aegis_phase1.models import StructuredComplianceMatrix
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Recursively convert non-JSON-serializable values (date, datetime) to strings."""
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def c05_matrix(state: Phase1State) -> dict:
    """Deterministically assemble the final StructuredComplianceMatrix.

    Combines all Phase 1 outputs into the compliance matrix document.
    All values are converted to JSON-safe types (date → ISO string) so
    LangGraph can serialize the state between nodes.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'structured_compliance_matrix' dict to be merged into state.
    """
    matrix = StructuredComplianceMatrix(
        matrixId="SCM-P1-001",
        analysisDate=date.today(),
        version="1.0",
    )

    matrix_dict = matrix.model_dump(by_alias=True)
    matrix_dict["analysisDate"] = date.today().isoformat()

    matrix_dict["companyContext"] = _json_safe(state.get("company_context", {}))
    matrix_dict["complianceContext"] = _json_safe(state.get("compliance_context", {}))
    matrix_dict["complexityTier"] = state.get("complexity_tier", "")
    matrix_dict["stakeholders"] = _json_safe(state.get("stakeholders", []))
    matrix_dict["businessGoals"] = _json_safe(state.get("business_goals", []))
    matrix_dict["regulations"] = _json_safe(state.get("regulations", []))
    matrix_dict["regulatoryClauses"] = _json_safe(state.get("regulatory_clauses", []))
    matrix_dict["domainCoverageEntries"] = _json_safe(state.get("domain_coverage_entries", []))
    matrix_dict["responsibilityEntries"] = _json_safe(state.get("responsibility_entries", []))
    matrix_dict["complementarityAnalyses"] = _json_safe(state.get("complementarity_analyses", []))
    matrix_dict["domainElaborationEntries"] = _json_safe(
        state.get("domain_elaboration_entries", [])
    )
    matrix_dict["strategicImplications"] = _json_safe(state.get("strategic_implications", []))
    matrix_dict["regulatoryObligations"] = _json_safe(state.get("regulatory_obligations", []))
    matrix_dict["implementationMappings"] = _json_safe(state.get("implementation_mappings", []))
    matrix_dict["conditionalExtensions"] = _json_safe(state.get("conditional_extensions", []))
    matrix_dict["regulatoryInteractions"] = _json_safe(state.get("regulatory_interactions", []))

    matrix_dict["supplierCompliance"] = _json_safe(state.get("supplier_compliance", []))
    matrix_dict["dataFlows"] = _json_safe(state.get("data_flows", []))
    matrix_dict["complianceCapabilities"] = _json_safe(state.get("compliance_capabilities", []))
    matrix_dict["architecturalImplications"] = _json_safe(
        state.get("architectural_implications", [])
    )
    matrix_dict["regulatoryGaps"] = _json_safe(state.get("regulatory_gaps", []))

    logger.info("[c05] Assembled matrix %s v%s", matrix.matrix_id, matrix.version)

    return {
        "structured_compliance_matrix": matrix_dict,
        "errors": [],
    }
