"""a06_regulatory_interactions — LLM enriches interactions from CSV."""

import json
import logging
import re

from aegis_phase1.llm.base import create_llm_client
from aegis_phase1.models import RegulatoryInteraction
from aegis_phase1.nodes._mock_data import is_mock_mode, mock_regulatory_interactions
from aegis_phase1.prompts.subphase_a import REGULATORY_INTERACTIONS_PROMPT
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _parse_json_response(raw: str) -> dict | list:
    """Extract JSON from LLM response, tolerant to fences and prose."""
    if not raw or not raw.strip():
        return {}
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    obj_match = re.search(r"\{[\s\S]*\}", text)
    arr_match = re.search(r"\[[\s\S]*\]", text)
    candidates = [m.group(0) for m in (obj_match, arr_match) if m]
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return {}


def _normalize_interaction_row(row: dict) -> dict:
    """Normalize CSV row to RegulatoryInteraction fields.

    The CSV uses ``regulation1Id`` and ``regulation2Id``; the model expects
    ``involvedRegulations`` (a list). This function bridges the two schemas.
    """
    out = dict(row)
    if "involvedRegulations" not in out and "involved_regulations" not in out:
        regs = []
        r1 = row.get("regulation1Id", row.get("regulation_1_id", ""))
        r2 = row.get("regulation2Id", row.get("regulation_2_id", ""))
        if r1:
            regs.append(r1)
        if r2:
            regs.append(r2)
        out["involvedRegulations"] = regs
    return out


def a06_regulatory_interactions(state: Phase1State) -> dict:
    """LLM call to enrich regulatory interactions with conflict descriptions.

    Reads raw interactions from CSV and uses LLM to add conflictDescription
    and resolutionPrinciple fields.  Falls back to raw CSV data when the LLM
    fails or is not in mock mode without Ollama.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'regulatory_interactions' list to be merged into state.
    """
    if is_mock_mode():
        logger.info("[a06] MOCK_LLM=true — returning mock regulatory interactions")
        return {"regulatory_interactions": mock_regulatory_interactions(), "errors": []}

    llm_config = state.get("case_config", {}).get(
        "llm", state.get("case_config", {}).get("ollama", {})
    )
    raw_interactions = state.get("regulatory_interactions_data", [])
    applicable = state.get("applicable_regulations", [])

    if not raw_interactions:
        logger.info("[a06] No regulatory interactions to enrich")
        return {"regulatory_interactions": [], "errors": []}

    applicable_upper = {a.upper() for a in applicable}
    filtered: list[dict] = []
    for row in raw_interactions:
        norm = _normalize_interaction_row(row)
        regs = norm.get("involvedRegulations", [])
        if isinstance(regs, str):
            regs = [r.strip() for r in regs.split(",") if r.strip()]
        if any(r.upper() in applicable_upper for r in regs):
            filtered.append(norm)

    if not filtered:
        logger.info(
            "[a06] No interactions match applicable regulations (applicable=%s)", applicable
        )
        return {"regulatory_interactions": [], "errors": []}

    prompt = REGULATORY_INTERACTIONS_PROMPT.format(
        company_context=json.dumps(state.get("company_context", {}), indent=2, ensure_ascii=False),
        interactions=json.dumps(filtered, indent=2, ensure_ascii=False),
        applicable_regulations=json.dumps(applicable, indent=2),
    )

    errors: list[str] = []
    interactions: list[dict] = []

    # Default: use the raw CSV data (it already has conflictDescription and resolutionPrinciple)
    for row in filtered:
        try:
            ri = RegulatoryInteraction.model_validate(row)
            interactions.append(ri.model_dump(by_alias=True))
        except Exception:
            logger.warning("[a06] Skipping invalid interaction: %s", row)

    try:
        client = create_llm_client(config=llm_config)
        result = client.generate(
            prompt=prompt,
            system=(
                "You are a regulatory interaction analyst for EU compliance. "
                "You MUST respond with a single valid JSON object. "
                "Do NOT use Cypher, markdown, or any other format. "
                "Output ONLY the JSON object."
            ),
            task_name="a06_regulatory_interactions",
            temperature=0.2,
            num_predict=2500,
        )

        if not result.get("error") and result.get("raw", "").strip():
            parsed = _parse_json_response(result["raw"])
            items = []
            if isinstance(parsed, dict):
                items = parsed.get("interactions") or parsed.get("items") or []
            elif isinstance(parsed, list):
                items = parsed
            if items:
                # Replace interactions list with LLM-enriched versions
                llm_by_id = {
                    it.get("interactionId", ""): it for it in items if it.get("interactionId")
                }
                merged: list[dict] = []
                for row in filtered:
                    cid = row.get("interactionId", "")
                    if cid in llm_by_id:
                        try:
                            ri = RegulatoryInteraction.model_validate(llm_by_id[cid])
                            merged.append(ri.model_dump(by_alias=True))
                            continue
                        except Exception:
                            pass
                    try:
                        ri = RegulatoryInteraction.model_validate(row)
                        merged.append(ri.model_dump(by_alias=True))
                    except Exception:
                        merged.append(row)
                interactions = merged
                logger.info("[a06] Enriched %d interactions via LLM", len(interactions))
            else:
                logger.info("[a06] LLM returned no items; using CSV data")

    except Exception as e:
        errors.append(f"a06_regulatory_interactions error: {e!s}")
        logger.exception("[a06] Unexpected error")

    return {
        "regulatory_interactions": interactions,
        "errors": errors,
    }
