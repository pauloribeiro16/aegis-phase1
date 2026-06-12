"""b03_map_clause_domain — Maps RegulatoryClause to SecurityControlDomain.

Uses clause_subdomain_mapping.csv for known mappings, LLM fallback for unmapped.
"""

import json
import logging
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from aegis_phase1.nodes._mock_data import is_mock_mode
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


def b03_map_clause_domain(state: Phase1State) -> dict:
    """Map each regulatory clause to a security control subdomain.

    Uses the clause_subdomain_mapping CSV for known mappings.  Falls back to
    LLM for clauses without a known mapping.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'regulatory_clauses' list (with subDomainId added) to be merged.
    """
    llm_config = state.get("case_config", {}).get(
        "llm", state.get("case_config", {}).get("ollama", {})
    )
    clauses = list(state.get("regulatory_clauses", []))
    mapping_data = state.get("clause_subdomain_mapping", [])
    security_domains = state.get("security_control_domains", [])
    applicable = state.get("applicable_regulations", [])

    csv_lookup: dict[str, str] = {}
    for row in mapping_data:
        clause_id = row.get("clauseId", row.get("clause_id", ""))
        subdomain_id = row.get("subDomainId", row.get("subDomainId", row.get("subdomainId", "")))
        if clause_id and subdomain_id:
            csv_lookup[clause_id] = subdomain_id

    valid_subdomains = {
        sd.get("subDomainId", sd.get("sub_domain_id", "")) for sd in security_domains
    }
    applicable_upper = {a.upper() for a in applicable}

    unmapped_clauses: list[dict] = []
    mapped_clauses: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    for clause in clauses:
        clause_id = clause.get("clauseId", clause.get("clause_id", ""))
        reg_id = clause.get("regulationId", clause.get("regulation_id", ""))

        if reg_id.upper() not in applicable_upper:
            continue

        # Deduplicate by (clauseId, regulationId) — LangGraph fan-out may duplicate
        key = (clause_id, reg_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        if clause_id in csv_lookup:
            clause["subDomainId"] = csv_lookup[clause_id]
            mapped_clauses.append(clause)
        else:
            unmapped_clauses.append(clause)

    logger.info("[b03] %d mapped via CSV, %d unmapped", len(mapped_clauses), len(unmapped_clauses))

    if unmapped_clauses and is_mock_mode():
        logger.info(
            "[b03] MOCK_LLM=true — assigning D-UNMAPPED to %d clauses", len(unmapped_clauses)
        )
        for clause in unmapped_clauses:
            clause["subDomainId"] = "D-UNMAPPED"
            mapped_clauses.append(clause)
    elif unmapped_clauses and valid_subdomains:
        subdomain_list = sorted(valid_subdomains)[:50]
        prompt = (
            "Map each regulatory clause to the most appropriate security control subdomain.\n\n"
            f"Valid subdomains: {json.dumps(subdomain_list)}\n\n"
            "Clauses:\n"
            f"{json.dumps(unmapped_clauses[:30], indent=2, ensure_ascii=False)}\n\n"
            'Return JSON: {"mappings": [{"clauseId": "...", "subDomainId": "..."}]}'
        )

        llm_lookup: dict[str, str] = {}
        try:
            base_url = llm_config.get("base_url", "http://localhost:11434")
            model = llm_config.get("model", os.getenv("OLLAMA_MODEL", "gemma4:e4b"))
            llm = ChatOllama(model=model, base_url=base_url, temperature=0.1)
            messages = [
                SystemMessage(
                    content=(
                        "You are a clause-to-domain mapping specialist. "
                        "You MUST respond with a single valid JSON object. "
                        "Output ONLY the JSON object."
                    )
                ),
                HumanMessage(content=prompt),
            ]
            response = llm.invoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            parsed = _parse_json_response(raw)

            mappings: list[dict] = []
            if isinstance(parsed, dict):
                mappings = parsed.get("mappings") or parsed.get("items") or []
            elif isinstance(parsed, list):
                mappings = parsed

            for m in mappings:
                cid = m.get("clauseId", "")
                sid = m.get("subDomainId", "")
                if cid and sid and sid in valid_subdomains:
                    llm_lookup[cid] = sid
        except Exception as e:
            logger.exception("[b03] LLM fallback failed: %s", e)

        for clause in unmapped_clauses:
            clause_id = clause.get("clauseId", clause.get("clause_id", ""))
            clause["subDomainId"] = llm_lookup.get(clause_id, "D-UNMAPPED")
            mapped_clauses.append(clause)
    else:
        for clause in unmapped_clauses:
            clause["subDomainId"] = "D-UNMAPPED"
            mapped_clauses.append(clause)

    logger.info("[b03] Total mapped clauses: %d", len(mapped_clauses))

    return {
        "regulatory_clauses": mapped_clauses,
        "errors": [],
    }
