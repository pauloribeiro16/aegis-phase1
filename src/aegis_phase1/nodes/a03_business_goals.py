"""a03_business_goals — Reads business goals from 10_business_goals.csv (deterministic, no LLM)."""

import csv
import logging
from pathlib import Path

from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _load_business_goals_from_csv(case_path: str, case_name: str = "case1") -> list[dict]:
    """Load business goals from 10_business_goals.csv."""
    csv_path = Path(case_path) / "data" / "phase1" / "10_business_goals.csv"
    if not csv_path.exists():
        logger.warning("[a03] %s not found, returning empty list", csv_path)
        return []
    goals: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("case", "") != case_name:
                continue
            goals.append(
                {
                    "goalId": row.get("goalId", ""),
                    "description": row.get("description", ""),
                    "goal": row.get("goal", ""),
                    "priority": row.get("priority", "MEDIUM"),
                    "relatedRegulations": row.get("relatedRegulations", ""),
                    "successMetrics": row.get("successMetrics", ""),
                    "strategicAlignment": "Compliance with " + row.get("relatedRegulations", ""),
                }
            )
    return goals


def a03_business_goals(state: Phase1State) -> dict:
    """Read business goals from 10_business_goals.csv.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'business_goals' list to be merged into state.
    """
    case_path = str(state.get("case_path", ""))
    current_case = str(state.get("case", "case1"))
    goals = _load_business_goals_from_csv(case_path, current_case)
    logger.info("[a03] Loaded %d business goals from 10_business_goals.csv", len(goals))
    return {
        "business_goals": goals,
        "errors": [],
        "degraded": False,
    }
