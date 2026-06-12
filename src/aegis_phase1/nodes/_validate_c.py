"""_validate_c — Validates SubPhase C outputs (all 4 documents produced)."""

import logging

from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _validate_c(state: Phase1State) -> dict:
    """Validate SubPhase C outputs.

    Checks that all 4 documents (Doc04-Doc07) are produced with content.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'errors' list (empty if all valid).
    """
    errors: list[str] = []

    # Complementarity analyses
    complementarity = state.get("complementarity_analyses", [])
    if not complementarity:
        errors.append("_validate_c: No complementarity_analyses produced")

    # Domain elaboration entries
    elaboration = state.get("domain_elaboration_entries", [])
    if not elaboration:
        errors.append("_validate_c: No domain_elaboration_entries produced")

    # Strategic implications
    strategic = state.get("strategic_implications", [])
    if not strategic:
        errors.append("_validate_c: No strategic_implications produced")

    # Regulatory obligations
    obligations = state.get("regulatory_obligations", [])
    if not obligations:
        errors.append("_validate_c: No regulatory_obligations produced")

    # Structured compliance matrix
    matrix = state.get("structured_compliance_matrix", {})
    if not matrix:
        errors.append("_validate_c: No structured_compliance_matrix produced")
    else:
        required_fields = ["matrixId", "version"]
        for field in required_fields:
            if field not in matrix:
                errors.append(f"_validate_c: matrix missing '{field}'")

    # Document paths
    doc_paths = state.get("doc_paths", {})
    if not doc_paths:
        errors.append("_validate_c: No document paths produced")
    else:
        expected = ["04_Company_Context_Assessment_filled.md"]
        for exp in expected:
            if not any(exp in k for k in doc_paths):
                errors.append(f"_validate_c: Missing document {exp}")

    if errors:
        logger.warning("[_validate_c] Validation failed: %d errors", len(errors))
    else:
        logger.info("[_validate_c] All SubPhase C outputs valid")

    return {"errors": errors}
