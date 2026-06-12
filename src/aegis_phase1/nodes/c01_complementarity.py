"""c01_complementarity — LLM enriches complementarity analyses from CSV."""

import json
import logging

from aegis_phase1.llm.base import create_llm_client
from aegis_phase1.models import ComplementarityAnalysis
from aegis_phase1.nodes._mock_data import is_mock_mode
from aegis_phase1.parsers.json_utils import parse_json_response
from aegis_phase1.prompts.subphase_c import COMPLEMENTARITY_PROMPT
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def c01_complementarity(state: Phase1State) -> dict:
    """LLM enrichment of complementarity analyses.

    Reads CSV complementarity data and uses LLM to enrich with
    sharedScope and structuralConnectedness.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'complementarity_analyses' list to be merged into state.
    """
    if is_mock_mode():
        logger.info("[c01] MOCK_LLM=true — passing through CSV complementarity data")
        raw_data = state.get(
            "complementarity_analyses_data", state.get("complementarity_analyses", [])
        )
        return {"complementarity_analyses": raw_data, "errors": []}

    llm_config = state.get("case_config", {}).get(
        "llm", state.get("case_config", {}).get("ollama", {})
    )
    raw_data = state.get("complementarity_analyses_data", [])
    applicable = state.get("applicable_regulations", [])
    coverage_entries = state.get("domain_coverage_entries", [])

    if not raw_data:
        logger.info("[c01] No complementarity data from CSV")
        return {"complementarity_analyses": [], "errors": []}

    prompt = COMPLEMENTARITY_PROMPT.format(
        complementarity_data=json.dumps(raw_data, indent=2, ensure_ascii=False),
        applicable_regulations=json.dumps(applicable, indent=2),
        coverage_entries=json.dumps(coverage_entries[:20], indent=2, ensure_ascii=False),
    )

    errors: list[str] = []
    analyses: list[dict] = []

    try:
        client = create_llm_client(config=llm_config)
        result = client.generate(
            prompt=prompt,
            system=(
                "You are a regulatory complementarity analyst. "
                "You MUST respond with a single valid JSON object and nothing else. "
                "Do NOT use Cypher, SQL, markdown, or any other format. "
                "Output ONLY the JSON object."
            ),
            task_name="c01_complementarity",
            temperature=0.3,
            num_predict=2500,
        )

        if result.get("error"):
            errors.append(f"c01_complementarity LLM error: {result['error']}")
            logger.warning("[c01] LLM error, falling back to raw CSV data")
        else:
            raw = result.get("raw", "")
            if not raw or not raw.strip():
                errors.append("c01_complementarity: LLM returned empty response")
                logger.warning("[c01] Empty LLM response (tokens=%s)", result.get("tokens"))
            else:
                parsed = parse_json_response(raw)
                # Handle both dict and list responses
                items: list = []
                if isinstance(parsed, dict):
                    items = parsed.get("complementarity_analyses", [])
                elif isinstance(parsed, list):
                    items = parsed
                for item in items:
                    try:
                        ca = ComplementarityAnalysis.model_validate(item)
                        analyses.append(ca.model_dump(by_alias=True))
                    except Exception:
                        logger.warning("[c01] Invalid analysis: %s", item)
                logger.info("[c01] Enriched %d complementarity analyses", len(analyses))

        # Fallback: if LLM produced nothing, use raw CSV data
        if not analyses:
            logger.info("[c01] Falling back to raw CSV data")
            for row in raw_data:
                try:
                    ca = ComplementarityAnalysis.model_validate(row)
                    analyses.append(ca.model_dump(by_alias=True))
                except Exception:
                    logger.warning("[c01] Skipping invalid row: %s", row)

    except Exception as e:
        errors.append(f"c01_complementarity error: {e!s}")
        logger.exception("[c01] Unexpected error")
        for row in raw_data:
            try:
                ca = ComplementarityAnalysis.model_validate(row)
                analyses.append(ca.model_dump(by_alias=True))
            except Exception:
                logger.warning("[c01] Skipping invalid row in fallback: %s", row)

    return {
        "complementarity_analyses": analyses,
        "errors": errors,
    }
