"""c02_domain_elaboration — LLM per-domain elaboration from CSV."""

import json
import logging
import re

from aegis_phase1.llm.base import create_llm_client
from aegis_phase1.models import DomainElaborationEntry
from aegis_phase1.nodes._mock_data import is_mock_mode, mock_domain_elaboration_entries
from aegis_phase1.prompts.subphase_c import DOMAIN_ELABORATION_PROMPT
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def _parse_json_response(raw: str) -> dict | list:
    """Extract JSON from LLM response, tolerant of markdown, Cypher, prose.

    Tolerant parser: strips code fences, finds the first {…} or […] block,
    and tries to parse. Returns {} on any failure — NEVER raises.
    """
    if not raw or not raw.strip():
        return {}
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[_parse_json] Failed to parse LLM response as JSON: %.200s", raw)
        return {}


def c02_domain_elaboration(state: Phase1State) -> dict:
    """LLM per-domain elaboration from CSV data.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'domain_elaboration_entries' list to be merged into state.
    """
    if is_mock_mode():
        logger.info("[c02] MOCK_LLM=true — returning mock domain elaboration entries")
        return {"domain_elaboration_entries": mock_domain_elaboration_entries(), "errors": []}

    llm_config = state.get("case_config", {}).get(
        "llm", state.get("case_config", {}).get("ollama", {})
    )
    raw_data = state.get("domain_elaborations_data", [])
    complementarity = state.get("complementarity_analyses", [])
    coverage = state.get("domain_coverage_entries", [])

    if not raw_data:
        logger.info("[c02] No domain elaboration data from CSV")
        return {"domain_elaboration_entries": [], "errors": []}

    prompt = DOMAIN_ELABORATION_PROMPT.format(
        elaboration_data=json.dumps(raw_data, indent=2, ensure_ascii=False),
        complementarity_analyses=json.dumps(complementarity[:10], indent=2, ensure_ascii=False),
        coverage_entries=json.dumps(coverage[:20], indent=2, ensure_ascii=False),
    )

    errors: list[str] = []
    entries: list[dict] = []

    try:
        client = create_llm_client(config=llm_config)
        result = client.generate(
            prompt=prompt,
            system=(
                "You are a domain elaboration analyst for EU regulatory compliance. "
                "You MUST respond with a single valid JSON object and nothing else. "
                "Do NOT use Cypher, SQL, markdown, or any other format. "
                "Output ONLY the JSON object."
            ),
            task_name="c02_domain_elaboration",
            temperature=0.3,
            num_predict=2500,
        )

        if result.get("error"):
            errors.append(f"c02_domain_elaboration LLM error: {result['error']}")
            logger.warning("[c02] LLM error, falling back to raw CSV data")
        else:
            raw = result.get("raw", "")
            if not raw or not raw.strip():
                errors.append("c02_domain_elaboration: LLM returned empty response")
                logger.warning("[c02] Empty LLM response (tokens=%s)", result.get("tokens"))
            else:
                parsed = _parse_json_response(raw)
                items: list = []
                if isinstance(parsed, dict):
                    items = parsed.get("domain_elaboration_entries", [])
                elif isinstance(parsed, list):
                    items = parsed
                for item in items:
                    try:
                        de = DomainElaborationEntry.model_validate(item)
                        entries.append(de.model_dump(by_alias=True))
                    except Exception:
                        logger.warning("[c02] Invalid entry: %s", item)
                logger.info("[c02] Produced %d domain elaboration entries", len(entries))

        # Fallback: if LLM produced nothing, use raw CSV data
        if not entries:
            logger.info("[c02] Falling back to raw CSV data")
            for row in raw_data:
                try:
                    de = DomainElaborationEntry.model_validate(row)
                    entries.append(de.model_dump(by_alias=True))
                except Exception:
                    logger.warning("[c02] Skipping invalid row: %s", row)

    except Exception as e:
        errors.append(f"c02_domain_elaboration error: {e!s}")
        logger.exception("[c02] Unexpected error")
        for row in raw_data:
            try:
                de = DomainElaborationEntry.model_validate(row)
                entries.append(de.model_dump(by_alias=True))
            except Exception:
                logger.warning("[c02] Skipping invalid row in fallback: %s", row)

    return {
        "domain_elaboration_entries": entries,
        "errors": errors,
    }
