"""b04_coverage_entries — Deterministic aggregation of clause mappings into DomainCoverageEntry[].

coverageLevel: SUBSTANTIVE if 2+ regs map to same subDomain, PARTIAL if 1 reg.
"""

import logging
from collections import defaultdict

from aegis_phase1.models import CoverageLevel, DomainCoverageEntry, GranularityLevel
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def b04_coverage_entries(state: Phase1State) -> dict:
    """Deterministically aggregate clause mappings into domain coverage entries.

    Groups clauses by (regulationId, subDomainId) and determines coverage level:
    - SUBSTANTIVE: 2+ regulations cover the same subdomain
    - PARTIAL: only 1 regulation covers the subdomain
    - NOT_ADDRESSED: subdomain has no clauses mapped

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'domain_coverage_entries' list to be merged into state.
    """
    clauses = state.get("regulatory_clauses", [])

    # Group clauses by (regulationId, subDomainId)
    group_map: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for clause in clauses:
        reg_id = clause.get("regulationId", clause.get("regulation_id", ""))
        sd_id = clause.get("subDomainId", clause.get("sub_domain_id", ""))
        if reg_id and sd_id:
            group_map[(reg_id, sd_id)].append(clause)

    # Group by subDomainId to count regulations per subdomain
    regs_per_sd: dict[str, set[str]] = defaultdict(set)
    for (reg_id, sd_id), _clauses in group_map.items():
        regs_per_sd[sd_id].add(reg_id)

    # Build coverage entries
    entries: list[dict] = []

    for entry_idx, ((reg_id, sd_id), group_clauses) in enumerate(group_map.items(), start=1):
        num_regs = len(regs_per_sd[sd_id])

        if num_regs >= 2:
            coverage_level = CoverageLevel.SUBSTANTIVE.value
        else:
            coverage_level = CoverageLevel.PARTIAL.value

        # Determine granularity: ATOMIC if all clauses are atomic, else ARTICLE
        all_atomic = all(c.get("isAtomic", True) for c in group_clauses)
        granularity = (
            GranularityLevel.ATOMIC.value if all_atomic else GranularityLevel.ARTICLE.value
        )

        # Compute obligated party distribution
        obligated_dist: dict[str, int] = defaultdict(int)
        obligation_type_dist: dict[str, int] = defaultdict(int)
        for c in group_clauses:
            op = c.get("obligatedParty", [])
            if isinstance(op, str):
                op = [p.strip() for p in op.split(",") if p.strip()]
            for p in op:
                obligated_dist[p] += 1

            ot = c.get("obligationType", "")
            if ot:
                obligation_type_dist[ot] += 1

        entry = DomainCoverageEntry(
            entryId=f"DCE-{entry_idx:03d}",
            regulationId=reg_id,
            subDomainId=sd_id,
            coverageLevel=coverage_level,
            clauseCount=len(group_clauses),
            granularityLevel=granularity,
            obligatedPartyDist=dict(obligated_dist),
            obligationTypeDist=dict(obligation_type_dist),
        )
        entries.append(entry.model_dump(by_alias=True))

    logger.info("[b04] Created %d coverage entries", len(entries))

    return {
        "domain_coverage_entries": entries,
        "errors": [],
    }
