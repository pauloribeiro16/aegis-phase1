"""a04_complexity_tier — Deterministic complexity classification."""

import logging

from aegis_phase1.models import ComplexityTier
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)

# Regulation combinations that always trigger HIGH complexity
_HIGH_RISK_COMBO = {"DORA", "AIACT", "NIS2"}


def a04_complexity_tier(state: Phase1State) -> dict:
    """Deterministic classification of company complexity tier.

    Rules:
    - LOW: <= 1 applicable regulation
    - MEDIUM: 2-3 applicable regulations
    - HIGH: 4+ applicable regulations OR (DORA + AI Act + NIS2 all present)

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'complexity_tier' string to be merged into state.
    """
    applicable = state.get("applicable_regulations", [])
    count = len(applicable)
    applicable_set = set(r.upper() for r in applicable)

    if count >= 4 or _HIGH_RISK_COMBO.issubset(applicable_set):
        tier = ComplexityTier.HIGH.value
    elif count >= 2:
        tier = ComplexityTier.MEDIUM.value
    else:
        tier = ComplexityTier.LOW.value

    logger.info("[a04] Complexity tier=%s (regulations=%d: %s)", tier, count, applicable)

    return {
        "complexity_tier": tier,
        "errors": [],
    }
