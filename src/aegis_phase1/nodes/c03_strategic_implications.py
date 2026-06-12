"""c03_strategic_implications — Reads strategic implications from 11_strategic_implications.csv."""

import csv
import logging
from pathlib import Path

from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _load_strategic_implications_from_csv(case_path: str, case_name: str = "case1") -> list[dict]:
    """Load strategic implications from 11_strategic_implications.csv."""
    csv_path = Path(case_path) / "data" / "phase1" / "11_strategic_implications.csv"
    if not csv_path.exists():
        logger.warning("[c03] %s not found, returning empty list", csv_path)
        return []
    items: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("case", "") != case_name:
                continue
            items.append(
                {
                    "implicationId": row.get("implicationId", ""),
                    "subDomain": row.get("subDomain", ""),
                    "sourceRegulations": row.get("sourceRegulations", ""),
                    "description": row.get("description", ""),
                    "architecturalImpact": row.get("architecturalImpact", ""),
                    "priority": row.get("priority", "MEDIUM"),
                    "businessImpact": "Impact: " + row.get("architecturalImpact", ""),
                    "complianceRisk": row.get("priority", "MEDIUM"),
                }
            )
    return items


def c03_strategic_implications(state: Phase1State) -> dict:
    """Read strategic implications from 11_strategic_implications.csv.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'strategic_implications' list to be merged into state.
    """
    case_path = state.get("case_path", "")
    current_case = state.get("case", "case1")
    implications = _load_strategic_implications_from_csv(case_path, current_case)
    logger.info(
        "[c03] Loaded %d strategic implications from 11_strategic_implications.csv",
        len(implications),
    )
    return {
        "strategic_implications": implications,
        "errors": [],
    }
