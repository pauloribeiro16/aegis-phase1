"""c04_obligation_shells — Deterministic: creates RegulatoryObligation shells.

Phase 1 creates shells with obligationId, category, targetSubDomain only.
Phase 2 fills in description, obligationType, normativeIntensity.
"""

import logging

from aegis_phase1.models import RegulatoryObligation
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def c04_obligation_shells(state: Phase1State) -> dict:
    """Deterministically create regulatory obligation shells from strategic implications.

    Creates shell objects with:
    - obligationId
    - category (from strategic implication category or "GENERAL")
    - targetSubDomain (from regulation mapping)
    - description="" (Phase 2 fills this)
    - obligationType=None (Phase 2 fills this)
    - normativeIntensity=0.0 (Phase 2 fills this)

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'regulatory_obligations' list to be merged into state.
    """
    strategic = state.get("strategic_implications", [])
    clauses = state.get("regulatory_clauses", [])
    coverage = state.get("domain_coverage_entries", [])

    obligations: list[dict] = []
    idx = 0

    # Create obligation shells from strategic implications
    for si in strategic:
        idx += 1
        target_sd = si.get("targetSubDomain", "")
        category = si.get("category", "GENERAL")

        ob = RegulatoryObligation(
            obligationId=f"RO-{idx:03d}",
            description="",
            category=category,
            targetSubDomain=target_sd,
            obligationType=None,
            obligatedParty=[],
            normativeIntensity=0.0,
        )
        obligations.append(ob.model_dump(by_alias=True))

    # Also create shells from uncovered subdomains in coverage entries
    covered_sds = {c.get("subDomainId", "") for c in coverage}
    for ce in coverage:
        sd_id = ce.get("subDomainId", "")
        if sd_id and sd_id not in {o.get("targetSubDomain", "") for o in obligations}:
            idx += 1
            ob = RegulatoryObligation(
                obligationId=f"RO-{idx:03d}",
                description="",
                category="COVERAGE_GAP",
                targetSubDomain=sd_id,
                obligationType=None,
                obligatedParty=[],
                normativeIntensity=0.0,
            )
            obligations.append(ob.model_dump(by_alias=True))

    logger.info("[c04] Created %d obligation shells", len(obligations))

    return {
        "regulatory_obligations": obligations,
        "errors": [],
    }
