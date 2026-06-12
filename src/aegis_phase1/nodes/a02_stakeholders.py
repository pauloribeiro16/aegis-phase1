"""a02_stakeholders — Reads stakeholders from 09_stakeholders.csv (deterministic, no LLM)."""

import csv
import logging
from pathlib import Path

from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _load_stakeholders_from_csv(case_path: str, case_name: str = "case1") -> list[dict]:
    """Load stakeholders from 09_stakeholders.csv."""
    csv_path = Path(case_path) / "data" / "phase1" / "09_stakeholders.csv"
    if not csv_path.exists():
        logger.warning("[a02] %s not found, returning empty list", csv_path)
        return []
    stakeholders: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("case", "") != case_name:
                continue
            stakeholders.append(
                {
                    "stakeholderId": row.get("stakeholderId", ""),
                    "name": row.get("name", ""),
                    "role": row.get("role", ""),
                    "stakeholderType": "internal"
                    if row.get("internal", "").upper() == "TRUE"
                    else "external",
                    "department": row.get("organization", ""),
                    "accessLevel": row.get("influenceLevel", "MEDIUM"),
                    "organization": row.get("organization", ""),
                    "contact": row.get("contact", ""),
                    "responsibilities": row.get("responsibilities", ""),
                    "influenceLevel": row.get("influenceLevel", ""),
                    "interestLevel": row.get("interestLevel", ""),
                    "engagementStrategy": row.get("engagementStrategy", ""),
                }
            )
    return stakeholders


def a02_stakeholders(state: Phase1State) -> dict:
    """Read stakeholders from 09_stakeholders.csv.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'stakeholders' list to be merged into state.
    """
    case_path = state.get("case_path", "")
    current_case = state.get("case", "case1")
    stakeholders = _load_stakeholders_from_csv(case_path, current_case)
    logger.info("[a02] Loaded %d stakeholders from 09_stakeholders.csv", len(stakeholders))
    return {
        "stakeholders": stakeholders,
        "errors": [],
    }
