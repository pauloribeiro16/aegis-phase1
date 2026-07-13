"""b02_load_clauses_batch — LLM batch enrichment: ALL clauses of ONE regulation in ONE call."""

import contextlib
import json
import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from aegis_phase1.models import RegulatoryClause
from aegis_phase1.nodes._mock_data import is_mock_mode
from aegis_phase1.parsers.json_utils import parse_json_response
from aegis_phase1.prompts.subphase_b import CLAUSE_BATCH_ENRICHMENT_PROMPT
from aegis_phase1.prompts_v2 import get_invoker
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)

# Allowed enum values (from class diagram) — used to coerce LLM output
_NORMATIVE_STRENGTHS = {"MANDATORY_UNCONDITIONAL", "MANDATORY_CONDITIONAL", "GUIDANCE"}
_OBLIGATED_PARTIES = {
    "CONTROLLER",
    "PROCESSOR",
    "MANUFACTURER",
    "IMPORTER",
    "DISTRIBUTOR",
    "ESSENTIAL_OR_IMPORTANT_ENTITY",
    "FINANCIAL_ENTITY",
    "PROVIDER",
    "DEPLOYER",
}
_OBLIGATION_TYPES = {"CONTINUOUS", "PERIODIC", "TRIGGERED", "ONE_TIME"}

def _coerce_normative_strength(value) -> str:
    """Coerce LLM output to a valid NormativeStrength enum value."""
    if not value:
        return "GUIDANCE"
    v = str(value).upper().replace(" ", "_").replace("-", "_")
    if v in _NORMATIVE_STRENGTHS:
        return v
    mapping = {
        "MANDATORY": "MANDATORY_UNCONDITIONAL",
        "MUST": "MANDATORY_UNCONDITIONAL",
        "REQUIRED": "MANDATORY_UNCONDITIONAL",
        "SHALL": "MANDATORY_UNCONDITIONAL",
        "CONDITIONAL": "MANDATORY_CONDITIONAL",
        "IF": "MANDATORY_CONDITIONAL",
        "RECOMMENDATION": "GUIDANCE",
        "MAY": "GUIDANCE",
        "SHOULD": "GUIDANCE",
        "OPTIONAL": "GUIDANCE",
    }
    for key, val in mapping.items():
        if key in v:
            return val
    return "GUIDANCE"

def _coerce_obligated_party(values) -> list[str]:
    """Coerce LLM output to a list of valid ObligatedPartyType values."""
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    result = []
    for v in values:
        if not v:
            continue
        s = str(v).upper().replace(" ", "_").replace("-", "_")
        if s in _OBLIGATED_PARTIES:
            result.append(s)
            continue
        mapping = {
            "DATA_CONTROLLER": "CONTROLLER",
            "DATA_PROCESSOR": "PROCESSOR",
            "MAKER": "MANUFACTURER",
            "PRODUCER": "MANUFACTURER",
            "RESELLER": "DISTRIBUTOR",
            "ENTITY": "ESSENTIAL_OR_IMPORTANT_ENTITY",
            "ESSENTIAL": "ESSENTIAL_OR_IMPORTANT_ENTITY",
            "FINANCIAL": "FINANCIAL_ENTITY",
        }
        for key, val in mapping.items():
            if key in s:
                result.append(val)
                break
    return list(dict.fromkeys(result))  # dedupe, preserve order

def _coerce_obligation_type(value) -> str:
    """Coerce LLM output to a valid ObligationType enum value."""
    if not value:
        return "CONTINUOUS"
    v = str(value).upper().replace(" ", "_").replace("-", "_")
    if v in _OBLIGATION_TYPES:
        return v
    mapping = {
        "ONGOING": "CONTINUOUS",
        "ALWAYS": "CONTINUOUS",
        "PERMANENT": "CONTINUOUS",
        "ANNUAL": "PERIODIC",
        "YEARLY": "PERIODIC",
        "REGULAR": "PERIODIC",
        "EVENT": "TRIGGERED",
        "INCIDENT": "TRIGGERED",
        "ONCE": "ONE_TIME",
        "INITIAL": "ONE_TIME",
    }
    for key, val in mapping.items():
        if key in v:
            return val
    return "CONTINUOUS"

def _validate_enriched_clause(item: dict, original: dict) -> dict:
    """Validate and coerce a single enriched clause from LLM output.

    Falls back to original values when LLM output is invalid or missing.
    """
    if not isinstance(item, dict):
        return dict(original)
    result = dict(original)
    cid = item.get("clauseId") or item.get("clause_id") or original.get("clauseId", "")
    if cid:
        result["clauseId"] = cid
    result["normativeStrength"] = _coerce_normative_strength(
        item.get("normativeStrength") or item.get("normative_strength")
    )
    result["obligatedParty"] = _coerce_obligated_party(
        item.get("obligatedParty") or item.get("obligated_party")
    )
    result["obligationType"] = _coerce_obligation_type(
        item.get("obligationType") or item.get("obligation_type")
    )
    is_atomic = item.get("isAtomic")
    if is_atomic is None:
        is_atomic = item.get("is_atomic", True)
    if isinstance(is_atomic, str):
        is_atomic = is_atomic.lower() in ("true", "1", "yes")
    result["isAtomic"] = bool(is_atomic)
    nw = item.get("normativeWeight") or item.get("normative_weight")
    if nw is not None:
        with contextlib.suppress(TypeError, ValueError):
            result["normativeWeight"] = int(float(nw))
    return result

def b02_load_clauses_batch(state: Phase1State) -> dict:
    """Batch-enrich ALL clauses of each applicable regulation in a SINGLE LLM call.

    Iterates over applicable regulations and sends ALL clauses for each in
    one prompt.  This is the key optimization: 1 LLM call per regulation,
    NOT per clause.

    The LLM is tolerant of failures: when the LLM returns invalid JSON or
    out-of-enum values, the node coerces/fills with sensible defaults so the
    pipeline never crashes on LLM issues.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'regulatory_clauses' list to be merged into state.
    """
    if is_mock_mode():
        logger.info("[b02] MOCK_LLM=true — passing through CSV clauses (no LLM enrichment)")
        raw_clauses = state.get("raw_clauses", state.get("regulatory_clauses", []))
        applicable = state.get("applicable_regulations", [])
        enriched: list[dict] = []
        for clause in raw_clauses:
            reg_id = clause.get("regulationId", "")
            if reg_id not in applicable:
                continue
            clause = dict(clause)
            if not clause.get("normativeStrength", "").strip():
                clause["normativeStrength"] = "MANDATORY_UNCONDITIONAL"
            if not clause.get("isAtomic", "").strip():
                clause["isAtomic"] = "True"
            if not clause.get("obligatedParty", "").strip():
                clause["obligatedParty"] = "CONTROLLER"
            if not clause.get("obligationType", "").strip():
                clause["obligationType"] = "CONTINUOUS"
            try:
                rc = RegulatoryClause.model_validate(clause)
                dumped = rc.model_dump(by_alias=True)
                dumped["regulationId"] = reg_id
                enriched.append(dumped)
            except Exception:
                clause["subDomainId"] = "D-UNMAPPED"
                clause["regulationId"] = reg_id
                enriched.append(clause)
        if not enriched and raw_clauses:
            for clause in raw_clauses:
                enriched.append(clause)
        return {"regulatory_clauses": enriched, "errors": []}

    llm_config = state.get("case_config", {}).get(
        "llm", state.get("case_config", {}).get("ollama", {})
    )
    raw_clauses = state.get("raw_clauses", state.get("regulatory_clauses", []))
    applicable = state.get("applicable_regulations", [])
    company_context = state.get("company_context", {})

    if not raw_clauses:
        logger.info("[b02] No clauses to enrich")
        return {"regulatory_clauses": [], "errors": []}

    clauses_by_reg: dict[str, list[dict]] = {}
    for clause in raw_clauses:
        reg_id = clause.get("regulationId", "")
        if reg_id in applicable:
            clauses_by_reg.setdefault(reg_id, []).append(clause)

    enriched_clauses: list[dict] = []
    errors: list[str] = []
    enrichment_count = 0

    for reg_id, clauses in clauses_by_reg.items():
        if not clauses:
            continue

        already_enriched = all(
            c.get("normativeStrength") and c.get("obligatedParty") and c.get("obligationType")
            for c in clauses
        )
        if already_enriched:
            logger.info("[b02] Clauses for %s already enriched, skipping LLM", reg_id)
            for c in clauses:
                try:
                    rc = RegulatoryClause.model_validate(c)
                    enriched_item = rc.model_dump(by_alias=True)
                    enriched_item["regulationId"] = c.get("regulationId", reg_id)
                    enriched_clauses.append(enriched_item)
                except Exception:
                    enriched_clauses.append(c)
            continue

        logger.info("[b02] Enriching %d clauses for %s", len(clauses), reg_id)

        # Truncate to keep LLM context manageable
        clauses_for_llm = clauses[:30] if len(clauses) > 30 else clauses
        if len(clauses) > 30:
            logger.warning(
                "[b02] Truncating %s from %d to 30 clauses for LLM", reg_id, len(clauses)
            )

        prompt = CLAUSE_BATCH_ENRICHMENT_PROMPT.format(
            regulation_id=reg_id,
            clauses_json=json.dumps(clauses_for_llm, indent=2, ensure_ascii=False),
            company_context=json.dumps(company_context, indent=2, ensure_ascii=False),
        )

        llm_items: list[dict] = []
        try:
            base_url = llm_config.get("base_url", "http://localhost:11434")
            model = llm_config.get("model", os.getenv("OLLAMA_MODEL", "gemma4:e4b"))
            temperature = llm_config.get("temperature", 0.2)

            llm = ChatOllama(model=model, base_url=base_url, temperature=temperature)
            messages = [
                SystemMessage(
                    content=(
                        "You are a regulatory clause enrichment specialist. "
                        "You MUST respond with a single valid JSON object and nothing else. "
                        "Do NOT use Cypher, SQL, markdown, or any other format. "
                        "Output ONLY the JSON object."
                    )
                ),
                HumanMessage(content=prompt),
            ]
            logger.info("[b02] Calling LLM for regulation %s...", reg_id)
            response = llm.invoke(messages)
            enrichment_count += 1
            raw = str(response.content) if hasattr(response, "content") else str(response)
            parsed = parse_json_response(raw)

            if isinstance(parsed, dict):
                llm_items = (
                    parsed.get("enriched_clauses")
                    or parsed.get("clauses")
                    or parsed.get("items")
                    or []
                )
            elif isinstance(parsed, list):
                llm_items = parsed

            if not llm_items:
                logger.warning(
                    "[b02] LLM returned no items for %s (raw len=%d)", reg_id, len(raw or "")
                )
            else:
                logger.info("[b02] LLM returned %d items for %s", len(llm_items), reg_id)

        except json.JSONDecodeError as e:
            errors.append(f"b02 JSON parse error for {reg_id}: {e!s}")
            logger.exception("[b02] JSON parse error for %s", reg_id)
        except Exception as e:
            errors.append(f"b02 LLM error for {reg_id}: {e!s}")
            logger.exception("[b02] LLM error for %s", reg_id)

        llm_by_id: dict[str, dict] = {}
        for item in llm_items:
            cid = item.get("clauseId") or item.get("clause_id", "")
            if cid:
                llm_by_id[cid] = item

        for original in clauses:
            cid = original.get("clauseId", "")
            llm_item = llm_by_id.get(cid)
            merged = _validate_enriched_clause(llm_item, original) if llm_item else dict(original)
            # Always ensure required fields have valid values (even if already present as empty strings)
            ns = merged.get("normativeStrength")
            if not ns or ns not in _NORMATIVE_STRENGTHS:
                merged["normativeStrength"] = _coerce_normative_strength(ns)
            op = merged.get("obligatedParty")
            if not op or not isinstance(op, list):
                merged["obligatedParty"] = _coerce_obligated_party(op or [])
            ot = merged.get("obligationType")
            if not ot or ot not in _OBLIGATION_TYPES:
                merged["obligationType"] = _coerce_obligation_type(ot)
            ia = merged.get("isAtomic")
            if not isinstance(ia, bool):
                if isinstance(ia, str):
                    merged["isAtomic"] = ia.lower() in ("true", "1", "yes")
                else:
                    merged["isAtomic"] = bool(ia) if ia is not None else True
            nw = merged.get("normativeWeight")
            if nw is None or nw == "":
                ni = merged.get("normativeIntensity", 0) or 0
                try:
                    merged["normativeWeight"] = int(float(ni))
                except (TypeError, ValueError):
                    merged["normativeWeight"] = 0
            else:
                try:
                    merged["normativeWeight"] = int(float(nw))
                except (TypeError, ValueError):
                    merged["normativeWeight"] = 0
            try:
                rc = RegulatoryClause.model_validate(merged)
                enriched_item = rc.model_dump(by_alias=True)
                enriched_item["regulationId"] = merged.get("regulationId", "")
                enriched_clauses.append(enriched_item)
            except Exception as e:
                logger.warning("[b02] Could not validate clause %s: %s", cid, e)
                enriched_clauses.append(merged)

    logger.info(
        "[b02] Total enriched clauses: %d, LLM calls: %d", len(enriched_clauses), enrichment_count
    )

    return {
        "regulatory_clauses": enriched_clauses,
        "errors": errors,
    }

def b02_load_clauses_batch_v2(state: dict) -> dict:
    """Phase 1B v1.2: invoke P1B-LLM-02-RATIONALE for each applicable regulation.

    Consolidates per-regulation rationale, implications and gaps into a
    single LLM call per regulation. Aggregates results across all
    applicable regulations.

    Args:
        state: Current Phase 1 workflow state dict.

    Returns:
        Dict with aggregate and per-regulation synthesis outputs ready to
        be merged into the LangGraph state.
    """
    invoker = get_invoker()

    case_id = state.get("case_id", "unknown_case")
    applicable = list(state.get("applicable_regulations", []))
    company_facts = state.get("company_facts") or {}
    classification = state.get("classification") or {"role": "Controller", "tier": "LOW"}

    if not applicable:
        return {
            "b02_v2_status": "OK",
            "b02_v2_per_reg_synthesis": {},
            "b02_v2_aggregated_synthesis": {},
            "b02_v2_total_latency_ms": 0.0,
        }

    regulations = state.get("regulations") or state.get("clauses") or {}

    def _clauses_for(reg: str) -> list:
        if isinstance(regulations, dict):
            value = regulations.get(reg)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [value]
            return []
        if isinstance(regulations, list):
            matches = []
            for row in regulations:
                if isinstance(row, dict) and row.get("regulationId") == reg:
                    matches.append(row)
            return matches
        return []

    per_reg: dict[str, dict] = {}
    aggregated_synthesis: dict[str, list] = {
        "rationale": [],
        "implications": [],
        "gaps": [],
    }
    total_latency = 0.0
    aggregate_status = "OK"

    for reg in applicable:
        clauses = _clauses_for(reg)
        out = invoker.invoke(
            "P1B-LLM-02-RATIONALE",
            {
                "case_id": case_id,
                "lane_id": reg,
                "applicable_regs": [reg],
                "classification": classification,
                "company_facts": company_facts,
                "synthesis_inputs": {
                    "clauses": clauses,
                    "regulation": reg,
                },
                "layer0_subdomain_refs": state.get("layer0_subdomain_refs") or [],
            },
            max_retries=2,
        )
        per_reg[reg] = out
        total_latency += float(out.get("total_latency_ms") or 0.0)
        status = out.get("status")
        if status != "OK":
            aggregate_status = status

        parsed = out.get("parsed_output") or {}
        synthesis = parsed.get("synthesis") if isinstance(parsed, dict) else None
        if isinstance(synthesis, dict):
            rationale = synthesis.get("rationale")
            if rationale:
                aggregated_synthesis["rationale"].append(
                    {"regulation": reg, "rationale": rationale}
                )
            implications = synthesis.get("implications") or []
            if isinstance(implications, list):
                for imp in implications:
                    if isinstance(imp, dict):
                        imp["regulation"] = reg
                    aggregated_synthesis["implications"].append(imp)
            gaps = synthesis.get("gaps") or []
            if isinstance(gaps, list):
                for gap in gaps:
                    if isinstance(gap, dict):
                        gap["regulation"] = reg
                    aggregated_synthesis["gaps"].append(gap)

    return {
        "b02_v2_status": aggregate_status,
        "b02_v2_per_reg_synthesis": per_reg,
        "b02_v2_aggregated_synthesis": aggregated_synthesis,
        "b02_v2_total_latency_ms": total_latency,
    }
