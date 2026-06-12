"""_validate_a — Validates all SubPhase A outputs are present and have required fields."""

import logging

from aegis_phase1.models import BusinessGoal, ComplianceContext, Stakeholder
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _validate_a(state: Phase1State) -> dict:
    """Validate SubPhase A outputs.

    Checks that stakeholders, business_goals, complexity_tier, and
    compliance_context are present and valid.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'errors' list (empty if all valid).
    """
    errors: list[str] = []

    # Stakeholders
    stakeholders = state.get("stakeholders", [])
    if not stakeholders:
        errors.append("_validate_a: No stakeholders produced")
    else:
        for i, s in enumerate(stakeholders):
            try:
                Stakeholder.model_validate(s)
            except Exception as e:
                errors.append(f"_validate_a: stakeholder[{i}] invalid: {e!s}")

    # Business goals
    business_goals = state.get("business_goals", [])
    if not business_goals:
        errors.append("_validate_a: No business goals produced")
    else:
        for i, g in enumerate(business_goals):
            try:
                BusinessGoal.model_validate(g)
            except Exception as e:
                errors.append(f"_validate_a: business_goal[{i}] invalid: {e!s}")

    # Complexity tier
    complexity_tier = state.get("complexity_tier", "")
    if complexity_tier not in ("LOW", "MEDIUM", "HIGH"):
        errors.append(f"_validate_a: Invalid complexity_tier: {complexity_tier!r}")

    # Compliance context
    compliance_context = state.get("compliance_context", {})
    if not compliance_context:
        errors.append("_validate_a: No compliance_context produced")
    else:
        try:
            ComplianceContext.model_validate(compliance_context)
        except Exception as e:
            errors.append(f"_validate_a: compliance_context invalid: {e!s}")

    # Applicable regulations
    applicable = state.get("applicable_regulations", [])
    if not applicable:
        errors.append("_validate_a: No applicable_regulations")

    if errors:
        logger.warning("[_validate_a] Validation failed: %d errors", len(errors))
    else:
        logger.info("[_validate_a] All SubPhase A outputs valid")

    return {"errors": errors}
