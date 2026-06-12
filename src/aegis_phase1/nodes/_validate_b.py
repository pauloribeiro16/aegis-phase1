"""_validate_b — Validates SubPhase B clause mappings and outputs."""

import logging

from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _validate_b(state: Phase1State) -> dict:
    """Validate SubPhase B outputs.

    Checks that regulations, regulatory_clauses, and clause mappings have
    valid subDomainId references.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'errors' list (empty if all valid).
    """
    errors: list[str] = []

    # Regulations
    regulations = state.get("regulations", [])
    if not regulations:
        errors.append("_validate_b: No regulations loaded")

    # Regulatory clauses
    clauses = state.get("regulatory_clauses", [])
    if not clauses:
        errors.append("_validate_b: No regulatory_clauses produced")
    else:
        for i, c in enumerate(clauses):
            if not c.get("clauseId") and not c.get("clause_id"):
                errors.append(f"_validate_b: clause[{i}] missing clauseId")
            if not c.get("subDomainId") and not c.get("sub_domain_id"):
                errors.append(f"_validate_b: clause[{i}] missing subDomainId")

    # Domain coverage entries
    coverage = state.get("domain_coverage_entries", [])
    if not coverage:
        errors.append("_validate_b: No domain_coverage_entries produced")

    # Responsibility entries
    responsibility = state.get("responsibility_entries", [])
    if not responsibility:
        errors.append("_validate_b: No responsibility_entries produced")

    if errors:
        logger.warning("[_validate_b] Validation failed: %d errors", len(errors))
    else:
        logger.info("[_validate_b] All SubPhase B outputs valid")

    return {"errors": errors}
