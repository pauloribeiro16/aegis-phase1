"""b01_load_regulations — Read 00_regulations.csv and filter by applicable regulations."""

import logging

from aegis_phase1.models import Regulation
from aegis_phase1.prompts_v2 import get_invoker
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)

def b01_load_regulations(state: Phase1State) -> dict:
    """Load regulation metadata from CSV, filtered by applicable regulations.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'regulations' list to be merged into state.
    """
    raw_regulations = state.get("regulations", [])
    applicable = state.get("applicable_regulations", [])

    # If raw_regulations already loaded from n01, filter them
    if raw_regulations:
        filtered = []
        for row in raw_regulations:
            reg_id = row.get("regulationId", row.get("id", ""))
            if reg_id in applicable:
                try:
                    reg = Regulation.model_validate(row)
                    filtered.append(reg.model_dump(by_alias=True))
                except Exception:
                    logger.warning("[b01] Skipping invalid regulation: %s", row)
        logger.info(
            "[b01] Loaded %d regulations (filtered from %d)", len(filtered), len(raw_regulations)
        )
        return {"regulations": filtered, "errors": []}

    # Fallback: build minimal regulation dicts from applicable list
    regulations = [{"regulationId": r, "name": r} for r in applicable]
    logger.info("[b01] Built %d minimal regulation entries from applicable list", len(regulations))
    return {"regulations": regulations, "errors": []}

def b01_load_regulations_v2(state: dict) -> dict:
    """Phase 1B v1.2: invoke P1B-LLM-01-INTERPRETATION for each applicable regulation.

    Uses the new prompts_v2 invoker (JSON Schema validation + JSONL logging
    + robust parsing for gemma4:e2b). Aggregates interpretations and
    derogation activations across all applicable regulations.

    Args:
        state: Current Phase 1 workflow state dict.

    Returns:
        Dict with aggregate and per-regulation outputs ready to be merged
        into the LangGraph state.
    """
    invoker = get_invoker()

    case_id = state.get("case_id", "unknown_case")
    applicable = list(state.get("applicable_regulations", []))
    classification = state.get("classification") or {"role": "Controller", "tier": "LOW"}
    company_facts = state.get("company_facts") or {}
    layer0_catalog = state.get("layer0_catalog") or {}
    layer0_subdomain_refs = state.get("layer0_subdomain_refs") or []

    if not applicable:
        return {
            "b01_v2_status": "OK",
            "b01_v2_per_reg": {},
            "b01_v2_aggregated_interpretations": [],
            "b01_v2_aggregated_derogations": [],
            "b01_v2_total_latency_ms": 0.0,
        }

    per_reg: dict[str, dict] = {}
    aggregated_interpretations: list[dict] = []
    aggregated_derogations: list[dict] = []
    total_latency = 0.0
    aggregate_status = "OK"

    for reg in applicable:
        out = invoker.invoke(
            "P1B-LLM-01-INTERPRETATION",
            {
                "case_id": case_id,
                "lane_id": reg,
                "applicable_regs": [reg],
                "classification": classification,
                "company_facts": company_facts,
                "layer0_catalog": layer0_catalog,
                "layer0_subdomain_refs": layer0_subdomain_refs,
            },
            max_retries=2,
        )
        per_reg[reg] = out
        total_latency += float(out.get("total_latency_ms") or 0.0)
        status = out.get("status")
        if status != "OK":
            aggregate_status = status

        parsed = out.get("parsed_output") or {}
        if isinstance(parsed, dict):
            for entry in parsed.get("interpretations") or []:
                aggregated_interpretations.append(entry)
            for entry in parsed.get("derogations") or []:
                aggregated_derogations.append(entry)

    return {
        "b01_v2_status": aggregate_status,
        "b01_v2_per_reg": per_reg,
        "b01_v2_aggregated_interpretations": aggregated_interpretations,
        "b01_v2_aggregated_derogations": aggregated_derogations,
        "b01_v2_total_latency_ms": total_latency,
    }
