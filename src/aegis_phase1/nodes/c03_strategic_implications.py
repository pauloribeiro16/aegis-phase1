"""c03_strategic_implications — Reads strategic implications from 11_strategic_implications.csv."""

import csv
import logging
from pathlib import Path

from aegis_phase1.prompts_v2 import get_invoker
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
    case_path = str(state.get("case_path", ""))
    current_case = str(state.get("case", "case1"))
    implications = _load_strategic_implications_from_csv(case_path, current_case)
    logger.info(
        "[c03] Loaded %d strategic implications from 11_strategic_implications.csv",
        len(implications),
    )
    return {
        "strategic_implications": implications,
        "errors": [],
    }

def c03_strategic_implications_v2(state: dict) -> dict:
    """Phase 1C v1.2: invoke P1C-LLM-03-STRATEGIC-SYNTHESIS (global_reduce, runs 1st).

    Cross-lane strategic implication synthesis. Consumes the per-lane
    outputs and Track B (Doc 07b) deterministic profile as a constraint.

    Args:
        state: Current Phase 1 workflow state dict. Upstream inputs may be
            absent during incremental wiring; the function still drives the
            invoker so the upstream is exercised end-to-end when present.

    Returns:
        Dict with implications list and timing metadata.
    """
    invoker = get_invoker()

    case_id = state.get("case_id", "unknown_case")
    applicable = list(state.get("applicable_regulations", []))
    aggregated_activations = state.get("aggregated_activations") or []
    doc07b_profile = state.get("doc07b_profile") or {}
    business_goals = state.get("business_goals") or []

    out = invoker.invoke(
        "P1C-LLM-03-STRATEGIC-SYNTHESIS",
        {
            "case_id": case_id,
            "lane_id": "global",
            "applicable_regs": applicable,
            "aggregated_activations": aggregated_activations,
            "doc07b_profile": doc07b_profile,
            "business_goals": business_goals,
        },
        max_retries=2,
    )

    parsed = out.get("parsed_output") or {}
    if not isinstance(parsed, dict):
        parsed = {}

    return {
        "c03_v2_status": out.get("status"),
        "c03_v2_implications": parsed.get("implications", []) or [],
        "c03_v2_parsed_output": parsed,
        "c03_v2_total_latency_ms": out.get("total_latency_ms"),
    }
