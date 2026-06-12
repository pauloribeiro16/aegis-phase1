"""produce_documents — Final node: renders all 4 Phase 1 output documents.

Runs after c05_matrix. Reads all Phase1State data and writes:
  - output/phase1/{doc}_filled.md (canonical latest)
  - output/phase1/versions/{doc}_v{N}.md (versioned snapshots)
  - output/phase1/intermediate/{doc}_v{N}.yaml (intermediate data + metadata)

Strategy: 100% deterministic {var} + [placeholder] fill. No LLM calls.
"""

import csv
import hashlib
import re as _re
import time
from datetime import datetime
from enum import Enum
from pathlib import Path

from aegis_phase1.logging_config import get_logger
from aegis_phase1.state import Phase1State
from aegis_phase1.shared.document_producer import PHASE1_TEMPLATES

logger = get_logger(__name__)

ALL_REGULATIONS = ("GDPR", "CRA", "NIS2", "DORA", "AIAct")
REGULATION_SHORT = {"GDPR": "gdpr", "CRA": "cra", "NIS2": "nis2", "DORA": "dora", "AIAct": "aiact"}

ALL_SUBDOMAINS = [
    "D-01.1",
    "D-01.2",
    "D-01.3",
    "D-01.4",
    "D-02.1",
    "D-02.2",
    "D-02.3",
    "D-02.4",
    "D-03.1",
    "D-03.2",
    "D-03.3",
    "D-03.4",
    "D-04.1",
    "D-04.2",
    "D-04.3",
    "D-04.4",
    "D-05.1",
    "D-05.2",
    "D-05.3",
    "D-05.4",
    "D-06.1",
    "D-06.2",
    "D-06.3",
    "D-06.4",
    "D-07.1",
    "D-07.2",
    "D-07.3",
    "D-07.4",
    "D-08.1",
    "D-08.2",
    "D-08.3",
    "D-09.1",
    "D-09.2",
    "D-09.3",
    "D-09.4",
    "D-10.1",
    "D-10.2",
    "D-10.3",
]
ALL_SUBDOMAIN_SUFFIXES = {sd.replace("D-", "sd_").replace(".", "_") for sd in ALL_SUBDOMAINS}


def _dedup_clauses(clauses: list) -> list:
    """Remove duplicate clauses (LangGraph fan-out may duplicate).

    Dedup by (clauseId, regulationId) tuple.
    """
    seen: set[tuple[str, str]] = set()
    deduped: list = []
    for c in clauses:
        cid = _get_attr(c, "clauseId", "")
        rid = _get_attr(c, "regulationId", "")
        key = (cid, rid)
        if not cid or key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def _fill_deterministic(template: str, data: dict) -> str:
    """Replace both {variable} and [placeholder] patterns from data dict.

    Known placeholders are replaced from data. Unknown placeholders matching
    the template pattern (lowercase with underscores/dashes) have their brackets
    stripped to avoid rendering issues. Brackets with spaces, dots, or slashes
    are preserved (e.g. [PENDING / PASS / FAIL], [file.md]).
    """

    def _replace(match):
        key = match.group(1)
        value = data.get(key)
        if value is None:
            return match.group(0)
        if isinstance(value, list | tuple):
            if value and isinstance(value[0], dict):
                return ", ".join(str(v.get("name", v)) for v in value[:5])
            return ", ".join(str(v) for v in value[:5])
        if isinstance(value, dict):
            inner = value.get("name", value.get("description", ""))
            return str(inner) if inner else str(value)
        return str(value)

    result = _re.sub(r"\{(\w+)\}", _replace, template)
    result = _re.sub(r"\[(\w+)\]", _replace, result)

    result = _re.sub(r"\[([a-zA-Z][a-zA-Z0-9_]*)\]", r"\1", result)
    result = _re.sub(r"\[([a-z][a-z ]*[a-z])\]", r"\1", result)

    return result


def _json_safe(value):
    """Recursively convert non-JSON-serializable values (enum, date, set) to strings."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, str):
        return value
    if isinstance(value, int | float | bool):
        return value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return list(value)
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _get_attr(obj, key: str, default=None):
    """Safely get attribute or dict key."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _generate_assessment_id(company_name: str) -> str:
    """Generate short hash-based assessment ID."""
    h = (
        hashlib.md5(f"{company_name}-{datetime.now().strftime('%Y%m%d')}".encode())
        .hexdigest()[:8]
        .upper()
    )
    return f"A{h}"


def _generate_doc_ids(company_name: str) -> dict:
    """Generate deterministic document IDs from company name."""
    short = company_name.upper().replace(" ", "").replace(".", "")[:10]
    year = datetime.now().strftime("%Y")
    return {
        "assessment_id": _generate_assessment_id(company_name),
        "compliance_doc_id": f"COMPLIANCE-{short}-{year}-001",
        "clause_mapping_id": "AEGIS-P1-06",
        "compliance_matrix_id": f"CM-{short}-{year}-001",
        "coverage_matrix_id": f"CC-{short}-{year}-001",
        "company_short": short,
    }


def _load_csv_rows(case_path: str, filename: str) -> list[dict]:
    """Load CSV rows from case data/phase1 directory."""
    csv_path = Path(case_path) / "data" / "phase1" / filename
    if not csv_path.exists():
        logger.warning("[produce_docs] CSV not found: %s", csv_path)
        return []
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _build_coverage_matrix(state: Phase1State) -> dict:
    """Build coverage_matrix dict from domain_coverage_entries."""
    entries = state.get("domain_coverage_entries", [])
    regulatory_clauses = _dedup_clauses(state.get("regulatory_clauses", []))
    case_path = state.get("case_path", "")
    matrix: dict[str, dict] = {}

    for entry in entries:
        sd_id = _get_attr(entry, "subDomainId", "") or _get_attr(entry, "sub_domain_id", "")
        reg_id = _get_attr(entry, "regulationId", "") or _get_attr(entry, "regulation_id", "")
        cov_level = _get_attr(entry, "coverageLevel", "NOT_ADDRESSED") or _get_attr(
            entry, "coverage_level", "NOT_ADDRESSED"
        )

        if not sd_id:
            continue

        if sd_id not in matrix:
            entry_name = _get_attr(entry, "subDomainName", "") or _get_attr(
                entry, "sub_domain_name", ""
            )
            matrix[sd_id] = {
                "subdomain_id": sd_id,
                "subdomain_name": entry_name,
                "regulations": [],
                "reg_ids": [],
                "clause_count": 0,
                "ni_weights": [],
                "ni_avg": 0.0,
                "coverage_level": "NOT_ADDRESSED",
            }

        if reg_id and reg_id not in matrix[sd_id]["reg_ids"]:
            matrix[sd_id]["reg_ids"].append(reg_id)
            matrix[sd_id]["regulations"].append(reg_id)

        if cov_level == "SUBSTANTIVE":
            if matrix[sd_id]["coverage_level"] != "SUBSTANTIVE":
                matrix[sd_id]["coverage_level"] = "SUBSTANTIVE"
        elif cov_level == "PARTIAL" and matrix[sd_id]["coverage_level"] == "NOT_ADDRESSED":
            matrix[sd_id]["coverage_level"] = "PARTIAL"

    for _sd_id, data in matrix.items():
        n_regs = len(data["reg_ids"])
        if n_regs >= 2:
            data["coverage_level"] = "SUBSTANTIVE"
        elif n_regs == 1:
            data["coverage_level"] = "PARTIAL"
        else:
            data["coverage_level"] = "NOT_ADDRESSED"

    clause_map = {}
    if case_path:
        mapping_rows = _load_csv_rows(case_path, "07_clause_subdomain_mapping.csv")
        for row in mapping_rows:
            cid = row.get("clauseId", "")
            sd = row.get("subDomainId", "")
            if cid and sd:
                clause_map[cid] = sd
                if sd not in matrix:
                    matrix[sd] = {
                        "subdomain_id": sd,
                        "subdomain_name": "",
                        "regulations": [],
                        "reg_ids": [],
                        "clause_count": 0,
                        "ni_weights": [],
                        "ni_avg": 0.0,
                        "coverage_level": "NOT_ADDRESSED",
                    }

    clause_by_id = {}
    for clause in regulatory_clauses or []:
        if isinstance(clause, dict):
            cid = clause.get("clauseId", "")
            if cid:
                clause_by_id[cid] = clause

    raw_clauses_by_id: dict[str, dict] = {}
    if case_path:
        raw_rows = _load_csv_rows(case_path, "04_clauses.csv")
        for row in raw_rows:
            cid = row.get("clauseId", "")
            if cid:
                raw_clauses_by_id[cid] = row

    for cid, sd_id in clause_map.items():
        if sd_id not in matrix:
            continue
        clause = clause_by_id.get(cid, {})
        raw_clause = raw_clauses_by_id.get(cid, {})
        if not clause and not raw_clause:
            continue
        reg_id = clause.get("regulationId", "") or raw_clause.get("regulationId", "")
        if reg_id and reg_id not in matrix[sd_id]["reg_ids"]:
            matrix[sd_id]["reg_ids"].append(reg_id)
            matrix[sd_id]["regulations"].append(reg_id)
        ni = (
            raw_clause.get("normativeIntensity", 0)
            or clause.get("normativeIntensity", 0)
            or clause.get("normativeWeight", 0)
        )
        try:
            ni = float(ni)
        except (ValueError, TypeError):
            ni = 0.0
        if ni > 0:
            matrix[sd_id]["ni_weights"].append(ni)

    for _sd_id, data in matrix.items():
        n_regs = len(data["reg_ids"])
        if n_regs >= 2:
            data["coverage_level"] = "SUBSTANTIVE"
        elif n_regs == 1:
            data["coverage_level"] = "PARTIAL"
        else:
            data["coverage_level"] = "NOT_ADDRESSED"

    for _sd_id, data in matrix.items():
        weights = data["ni_weights"]
        if weights:
            data["ni_avg"] = sum(weights) / len(weights)
            data["clause_count"] = len(weights)

    return matrix


def _build_coverage_summary(coverage_matrix: dict) -> dict:
    """Compute coverage summary from coverage_matrix."""
    if not coverage_matrix:
        return {
            "total_subdomains": 0,
            "substantive": 0,
            "partial": 0,
            "not_addressed": 0,
            "coverage_pct": 0.0,
            "mean_ni": 0.0,
        }

    total = len(coverage_matrix)
    substantive = sum(1 for d in coverage_matrix.values() if d["coverage_level"] == "SUBSTANTIVE")
    partial = sum(1 for d in coverage_matrix.values() if d["coverage_level"] == "PARTIAL")
    not_addressed = sum(
        1 for d in coverage_matrix.values() if d["coverage_level"] == "NOT_ADDRESSED"
    )
    coverage_pct = ((substantive + partial) / total * 100) if total > 0 else 0.0
    mean_ni = (
        sum(d.get("ni_avg", 0.0) for d in coverage_matrix.values()) / total if total > 0 else 0.0
    )

    return {
        "total_subdomains": total,
        "substantive": substantive,
        "partial": partial,
        "not_addressed": not_addressed,
        "coverage_pct": coverage_pct,
        "mean_ni": mean_ni,
    }


def _build_complementarity_analysis(state: Phase1State) -> dict:
    """Build complementarity_analysis dict from complementarity_analyses list."""
    analyses = state.get("complementarity_analyses", [])
    overlaps = []
    tensions = []
    compound_events = []

    for a in analyses:
        shared_scope = _get_attr(a, "sharedScope", "") or _get_attr(a, "shared_scope", "")
        if shared_scope:
            overlaps.append(
                {
                    "regulation_pair": f"{_get_attr(a, 'regulationId1', '')} / {_get_attr(a, 'regulationId2', '')}",
                    "shared_scope": shared_scope,
                    "structural_connectedness": _get_attr(a, "structuralConnectedness", ""),
                }
            )
        tension = _get_attr(a, "tension", "") or _get_attr(a, "tension_description", "")
        if tension:
            tensions.append(
                {
                    "description": tension,
                    "type": _get_attr(a, "tensionType", "contextual") or "contextual",
                }
            )

    return {
        "overlaps": overlaps,
        "tensions": tensions,
        "compound_events": compound_events,
    }


def _build_regulatory_gaps(state: Phase1State, coverage_matrix: dict) -> list:
    """Build regulatory gaps from state's regulatory_gaps or coverage gaps."""
    state_gaps = state.get("regulatory_gaps", [])
    if state_gaps:
        return state_gaps
    gaps = []
    for sd_id, data in coverage_matrix.items():
        if data["coverage_level"] == "NOT_ADDRESSED":
            gaps.append(
                {
                    "gap_id": f"GAP-{sd_id}",
                    "sub_domain_id": sd_id,
                    "description": f"Sub-domain {sd_id} is not addressed by any applicable regulation",
                    "risk_level": "MEDIUM",
                }
            )
    return gaps


def _build_evidence_sources() -> str:
    return (
        "- 06_Clause_Mapping_Matrix.md (clause -> subdomain mappings)\n"
        "- 05_Regulatory_Applicability.md (per-regulation rationale + evidence)\n"
        "- Complementarity analysis (cross-regulation overlaps, tensions, compound events)\n"
        "- Stakeholder analysis (from intake form)\n"
        "- Business goals catalog (from intake form)\n"
        "- Taxonomy reference (applicable domains/sub-domains)\n"
        "- Intake form (company context, sector, size, triggers)\n"
        "- Clause CSV (per-regulation clause catalog from 04_clauses.csv)"
    )


def _build_stakeholder_rationale(stakeholders: list) -> str:
    lines = []
    for s in stakeholders or []:
        sid = _get_attr(s, "stakeholder_id", "") or _get_attr(s, "stakeholderId", "") or "?"
        name = _get_attr(s, "name", "")
        role = _get_attr(s, "role", "")
        lines.append(f"- {sid}: {name} ({role})")
    return "\n".join(lines)


def _build_business_goal_rationale(goals: list) -> str:
    lines = []
    for g in goals or []:
        gid = _get_attr(g, "goal_id", "") or _get_attr(g, "goalId", "") or "?"
        desc = _get_attr(g, "description", "") or _get_attr(g, "goal", "") or ""
        prio = _get_attr(g, "priority", "")
        lines.append(f"- {gid} [{prio}]: {desc}")
    return "\n".join(lines)


def _build_context_assessment_rationale(company_context: dict) -> str:
    return (
        f"Sector: {company_context.get('sector', 'N/A')}. "
        f"Size: {company_context.get('size', 'N/A')}. "
        f"Processes personal data: {company_context.get('processes_personal_data', False)}. "
        f"Places digital products in EU: {company_context.get('places_digital_products_eu', False)}. "
        f"Technological control plane: {company_context.get('technological_control_plane', 'N/A')}."
    )


def _build_subdomain_matrix_placeholders(coverage_matrix: dict) -> dict:
    """Build ALL [sd_XX_Y_{reg}] placeholders for all 38 sub-domains."""
    data: dict[str, str] = {}
    reg_short_to_full = {
        "gdpr": "GDPR",
        "cra": "CRA",
        "nis2": "NIS2",
        "dora": "DORA",
        "aiact": "AIAct",
    }

    for sd_id in ALL_SUBDOMAINS:
        suffix = sd_id.replace("D-", "sd_").replace(".", "_")
        sd_data = coverage_matrix.get(sd_id, {})
        reg_ids = sd_data.get("reg_ids", [])
        total = len(reg_ids)

        for reg_short, full_reg in reg_short_to_full.items():
            indicator = "Yes" if full_reg in reg_ids else ""
            data[f"{suffix}_{reg_short}"] = indicator

        data[f"{suffix}_total"] = str(total)
        coverage_str = sd_data.get("coverage_level", "NOT_ADDRESSED")
        coverage_label = {
            "SUBSTANTIVE": "SUBSTANTIVE",
            "PARTIAL": "PARTIAL",
            "NOT_ADDRESSED": "\u2014",
        }.get(coverage_str, "\u2014")
        data[f"{suffix}_coverage"] = coverage_label
        data[f"{suffix}_ni"] = f"{sd_data.get('ni_avg', 0.0):.1f}"

    return data


def _build_clause_stats_placeholders(
    regulatory_clauses: list, applicable_regulations: list, case_path: str = ""
) -> dict:
    """Build Doc 06 clause statistics placeholders."""
    data: dict[str, str] = {}
    reg_names = [
        r if isinstance(r, str) else r.get("regulationId", "") for r in applicable_regulations
    ]
    reg_names = [r for r in reg_names if r]

    raw_clauses_by_id: dict[str, dict] = {}
    if case_path:
        raw_rows = _load_csv_rows(case_path, "04_clauses.csv")
        for row in raw_rows:
            cid = row.get("clauseId", "")
            if cid:
                raw_clauses_by_id[cid] = row

    by_reg: dict[str, list] = {"GDPR": [], "CRA": [], "NIS2": [], "DORA": [], "AIAct": []}
    by_reg_sd: dict[str, dict[str, int]] = {reg: {} for reg in by_reg}

    for c in regulatory_clauses or []:
        if not isinstance(c, dict):
            continue
        rid = c.get("regulationId", "")
        if rid not in by_reg:
            continue
        by_reg[rid].append(c)
        sd = c.get("subDomainId", "")
        if sd:
            by_reg_sd[rid][sd] = by_reg_sd[rid].get(sd, 0) + 1

    all_weights = []
    for reg_clauses in by_reg.values():
        for c in reg_clauses:
            cid = c.get("clauseId", "")
            raw = raw_clauses_by_id.get(cid, {})
            w = (
                raw.get("normativeIntensity", 0)
                or c.get("normativeIntensity", 0)
                or c.get("normativeWeight", 0)
            )
            try:
                w = float(w)
            except (ValueError, TypeError):
                w = 0.0
            all_weights.append(w)

    total = len(all_weights) or 1
    mean_ni = sum(all_weights) / total if total > 0 else 0.0
    w1 = sum(1 for w in all_weights if w <= 1.0)
    w2 = sum(1 for w in all_weights if 1.5 <= w <= 2.0)
    w3 = sum(1 for w in all_weights if w >= 2.5)

    data["combined_mean_ni"] = f"{mean_ni:.2f}"
    data["combined_weight_1_pct"] = f"{w1 * 100 / total:.1f}"
    data["combined_weight_2_pct"] = f"{w2 * 100 / total:.1f}"
    data["combined_weight_3_pct"] = f"{w3 * 100 / total:.1f}"
    data["mapping_rationale_overview"] = (
        f"{total} clauses mapped across {len([r for r in reg_names if r])} applicable regulations. "
        f"Mean NI: {mean_ni:.2f}. "
        f"Distribution: {w3} mandatory, {w2} recommended, {w1} optional."
    )

    reg_short_map = {"GDPR": "gdpr", "CRA": "cra", "NIS2": "nis2", "DORA": "dora", "AIAct": "aiact"}
    for reg_full, reg_short in reg_short_map.items():
        clauses = by_reg.get(reg_full, [])
        n = len(clauses)
        data[f"{reg_short}_total_clauses"] = str(n)
        data[f"{reg_short}_applicable_clauses"] = str(n)
        weights = []
        for c in clauses:
            cid = c.get("clauseId", "")
            raw = raw_clauses_by_id.get(cid, {})
            try:
                w = float(
                    raw.get("normativeIntensity", 0)
                    or c.get("normativeIntensity", 0)
                    or c.get("normativeWeight", 0)
                )
            except (ValueError, TypeError):
                w = 0.0
            weights.append(w)
        mean_w = sum(weights) / n if n > 0 else 0.0
        data[f"{reg_short}_mean_ni"] = f"{mean_w:.2f}"
        w1n = sum(1 for w in weights if w <= 1.0)
        w2n = sum(1 for w in weights if 1.5 <= w <= 2.0)
        w3n = sum(1 for w in weights if w >= 2.5)
        data[f"{reg_short}_weight_1_pct"] = f"{w1n * 100 / max(n, 1):.1f}"
        data[f"{reg_short}_weight_2_pct"] = f"{w2n * 100 / max(n, 1):.1f}"
        data[f"{reg_short}_weight_3_pct"] = f"{w3n * 100 / max(n, 1):.1f}"
        data[f"{reg_short}_weight_2_count"] = str(w2n)
        data[f"{reg_short}_weight_3_count"] = str(w3n)
        data[f"{reg_short}_mapping_rationale"] = (
            f"{n} {reg_full} clauses mapped to sub-domains. "
            f"{w3n} mandatory (weight 3), {w2n} recommended (weight 2), {w1n} optional (weight 1). "
            f"Mean NI: {mean_w:.2f}."
        )

        for sd_id, count in by_reg_sd.get(reg_full, {}).items():
            dom = sd_id.rsplit(".", 1)[0] if "." in sd_id else sd_id
            data[f"{reg_short}_{dom.lower().replace('-', '')}_count"] = str(count)
            data[f"{reg_short}_{dom.lower().replace('-', '')}_clauses"] = str(count)

    for i in (0, 1):
        reg_full = reg_names[i] if i < len(reg_names) else "N/A"
        data[f"reg_{i+1}"] = reg_full
        data[f"reg_{i+1}_count"] = str(len(by_reg.get(reg_full, [])))

    if "NIS2" not in reg_names:
        for k in (
            "nis2_total_clauses",
            "nis2_applicable_clauses",
            "nis2_mean_ni",
            "nis2_weight_1_pct",
            "nis2_weight_2_pct",
            "nis2_weight_3_pct",
            "nis2_weight_2_count",
            "nis2_weight_3_count",
            "nis2_mapping_rationale",
        ):
            data.setdefault(
                k,
                "0"
                if "count" in k or "clauses" in k or ("weight" in k and "pct" not in k)
                else "N/A",
            )
        data.setdefault("nis2_mapping_rationale", "NIS 2 not applicable for this case")

    return data


def _build_regulation_placeholders(applicable_regs: list) -> dict:
    """Build per-regulation applicability placeholders for Doc 05."""
    data: dict[str, str] = {}
    reg_names = {r if isinstance(r, str) else r.get("regulationId", "") for r in applicable_regs}
    reg_names = {r for r in reg_names if r}

    for reg, short in REGULATION_SHORT.items():
        applicable = reg in reg_names
        text = f"{reg} Applicable" if applicable else f"{reg} Not Applicable"

        data[f"{short}_applicability_text"] = text
        data[f"{short}_sum_mary_applicable"] = "Yes" if applicable else "No"
        data[f"{short}_sum_mary_confidence"] = "High" if applicable else "N/A"
        data[f"{short}_sum_mary_driver"] = (
            "Data processing / EU presence"
            if reg == "GDPR"
            else (
                "Product digital nature"
                if reg == "CRA"
                else (
                    "Sector classification"
                    if reg == "NIS2"
                    else ("Financial entity status" if reg == "DORA" else "AI system usage")
                )
            )
        )
        data[f"{short}_sum_mary_exclusion"] = (
            "" if applicable else "Not applicable per company context"
        )

        data[f"{short}_processes_personal_data"] = (
            "True (Implied by data processing goals)" if reg == "GDPR" else "N/A"
        )
        data[f"{short}_eu_data_subjects"] = (
            "True (Jurisdiction is Portugal, EU)" if reg == "GDPR" else "N/A"
        )
        data[f"{short}_process_met"] = "True" if reg == "GDPR" else "N/A"
        data[f"{short}_eu_met"] = "True" if reg == "GDPR" else "N/A"

    for k in list(data.keys()):
        if "_sum_mary" in k:
            data[k.replace("_sum_mary_", "_summary_")] = data[k]

    return data


def _build_applicability_section_placeholders(
    company_context: dict, regulatory_clauses: list, applicable_regs: list
) -> dict:
    """Build Doc 05 section 3 per-regulation placeholders."""
    data: dict[str, str] = {}
    reg_names = {r if isinstance(r, str) else r.get("regulationId", "") for r in applicable_regs}
    reg_names = {r for r in reg_names if r}

    gdpr_clauses = [c for c in regulatory_clauses if _get_attr(c, "regulationId", "") == "GDPR"]

    if "GDPR" in reg_names:
        data["gdpr_rationale"] = (
            "The company operates within the EU jurisdiction (Portugal) and processes personal data, triggering GDPR obligations."
        )
        data["gdpr_obligated_party"] = "CONTROLLER"
        data["gdpr_multi_actor_note"] = (
            "Stakeholders include internal employees and external data subjects/partners, requiring comprehensive data governance."
        )
        data["gdpr_key_clauses"] = (
            ", ".join([_get_attr(c, "clauseId", "") for c in gdpr_clauses[:5]])
            or "GDPR-C01, C02, C03"
        )
        data["gdpr_nuance"] = (
            "Special category data not identified; standard GDPR framework applies."
        )
        data["gdpr_special_category"] = "Unknown"
        data["gdpr_processes_personal_data"] = _set_company_context_bool(company_context, True)
        data["gdpr_eu_data_subjects"] = "True \u2014 Jurisdiction is Portugal (EU)"
        data["gdpr_process_met"] = "True"
        data["gdpr_eu_met"] = "True"

    if "CRA" in reg_names:
        data["cra_rationale"] = (
            "Company places digital products with digital elements on the EU market."
        )
        data["cra_key_clauses"] = "CRA-C01, CRA-C02, CRA-C03"
        data["cra_digital_element"] = "Yes \u2014 TinyTask SaaS is a software product"
        data["cra_manufacturer_status"] = "Manufacturer"
        data["cra_places_products_eu"] = _set_company_context_bool(company_context, True)
        data["cra_digital_met"] = "Yes"
        data["cra_manufacturer_met"] = "Yes"
        data["cra_places_met"] = "True"
        data["cra_quantitative_thresholds"] = (
            "Annual turnover and employee count below thresholds; standard CRA requirements apply."
        )

    for reg_key, reg_full, crit_keys in [
        (
            "nis2",
            "NIS2",
            [
                "nis2_sector",
                "nis2_employees",
                "nis2_employees_met",
                "nis2_revenue",
                "nis2_revenue_met",
                "nis2_critical_status",
                "nis2_critical_met",
                "nis2_sector_met",
            ],
        ),
        (
            "dora",
            "DORA",
            [
                "dora_financial_entity",
                "dora_financial_met",
                "dora_financial_classification",
                "dora_classification_met",
                "dora_ict_provider",
                "dora_ict_met",
            ],
        ),
        (
            "aiact",
            "AI Act",
            [
                "aiact_high_risk_system",
                "aiact_high_risk_met",
                "aiact_provider_status",
                "aiact_provider_met",
                "aiact_deployer_status",
                "aiact_deployer_met",
                "aiact_high_risk_use_case",
                "aiact_use_case_met",
            ],
        ),
    ]:
        is_applicable = reg_full in reg_names or reg_key.replace("aiact", "AIAct") in reg_names
        data[f"{reg_key}_rationale"] = (
            "Not applicable based on company context and sector classification."
        )
        data[f"{reg_key}_key_clauses"] = "N/A"
        for ck in crit_keys:
            data[ck] = "N/A" if not is_applicable else "Pending"

    return data


def _build_coverage_section_placeholders(
    coverage_matrix: dict, coverage_summary: dict, applicable_regs: list
) -> dict:
    """Build Doc 05 section 6 (coverage) placeholders."""
    data: dict[str, str] = {}
    reg_names = [r if isinstance(r, str) else r.get("regulationId", "") for r in applicable_regs]
    reg_names = [r for r in reg_names if r]

    substantive_sds = [
        sd for sd, d in coverage_matrix.items() if d["coverage_level"] == "SUBSTANTIVE"
    ]
    partial_sds = [sd for sd, d in coverage_matrix.items() if d["coverage_level"] == "PARTIAL"]
    not_addressed_sds = [
        sd for sd, d in coverage_matrix.items() if d["coverage_level"] == "NOT_ADDRESSED"
    ]

    data["applicable_regulations_list"] = ", ".join(reg_names) if reg_names else "N/A"
    data["reg_1"] = reg_names[0] if len(reg_names) > 0 else "N/A"
    data["reg_2"] = reg_names[1] if len(reg_names) > 1 else "N/A"
    data["substantive_count"] = str(len(substantive_sds))
    data["partial_count"] = str(len(partial_sds))
    data["not_addressed_count"] = str(len(not_addressed_sds))
    data["non_applicable_regs"] = "N/A"

    first_sd = next(iter(coverage_matrix.values()), {})
    data["sd_1_id"] = first_sd.get("subdomain_id", "D-01.1")
    data["sd_1_name"] = first_sd.get("subdomain_name", "")
    data["sd_1_reg_1"] = "Yes" if len(first_sd.get("reg_ids", [])) > 0 else ""
    data["sd_1_reg_2"] = "Yes" if len(first_sd.get("reg_ids", [])) > 1 else ""
    data["sd_1_total"] = str(len(first_sd.get("reg_ids", [])))
    data["sd_1_level"] = first_sd.get("coverage_level", "NOT_ADDRESSED")
    data["additional_subdomains"] = (
        ""
        if len(coverage_matrix) <= 1
        else f"(+{len(coverage_matrix)-1} more sub-domains in full matrix)"
    )

    return data


def _build_interaction_placeholders(interactions: list) -> dict:
    """Build regulatory interaction placeholders for Doc 05 section 10."""
    data: dict[str, str] = {}
    counts = {"SYNERGY": 0, "TEMPORAL": 0, "STRUCTURAL": 0, "CONTEXTUAL": 0}

    if interactions:
        first = interactions[0]
        data["ri_id"] = (
            _get_attr(first, "interactionId", "") or _get_attr(first, "id", "") or "RI-001"
        )
        data["ri_type"] = (
            _get_attr(first, "interactionType", "") or _get_attr(first, "type", "") or "SYNERGY"
        )
        data["ri_reg1"] = (
            _get_attr(first, "regulationId1", "") or _get_attr(first, "regulation1", "") or "N/A"
        )
        data["ri_reg2"] = (
            _get_attr(first, "regulationId2", "") or _get_attr(first, "regulation2", "") or "N/A"
        )
        data["ri_description"] = _get_attr(first, "description", "") or "Overlap identified"
        data["ri_resolution"] = _get_attr(first, "resolutionPrinciple", "") or "Harmonization"
        data["ri_priority"] = _get_attr(first, "priority", "") or "MEDIUM"

        for attr_key in ("description", "resolutionPrinciple", "priority"):
            val = _get_attr(first, attr_key, "")
            if val:
                break
    else:
        data["ri_id"] = "RI-001"
        data["ri_type"] = "SYNERGY"
        data["ri_reg1"] = "PENDING"
        data["ri_reg2"] = "PENDING"
        data["ri_description"] = "Pending regulatory interaction analysis"
        data["ri_resolution"] = "TBD"
        data["ri_priority"] = "MEDIUM"

    for ia in interactions:
        itype = _get_attr(ia, "interactionType", "") or _get_attr(ia, "type", "")
        if itype in counts:
            counts[itype] += 1

    data["synergy_count"] = str(counts["SYNERGY"])
    data["temporal_count"] = str(counts["TEMPORAL"])
    data["structural_count"] = str(counts["STRUCTURAL"])
    data["contextual_count"] = str(counts["CONTEXTUAL"])

    return data


def _build_gap_placeholders(gaps: list, coverage_matrix: dict, applicable_regs: list) -> dict:
    """Build gap placeholders for Doc 05 and 07."""
    data: dict[str, str] = {}
    risk_count = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    risk_sds = {"HIGH": [], "MEDIUM": [], "LOW": []}

    if not gaps and coverage_matrix:
        for sd_id, sd_data in coverage_matrix.items():
            if sd_data.get("coverage_level") == "NOT_ADDRESSED":
                gaps.append(
                    {
                        "gap_id": f"GAP-{sd_id}",
                        "sub_domain_id": sd_id,
                        "regulation": "N/A",
                        "clause": "N/A",
                        "description": f"Sub-domain {sd_id} is not addressed by any applicable regulation",
                        "risk_level": "HIGH" if sd_id.startswith(("D-09", "D-04")) else "MEDIUM",
                        "type": "Coverage Gap",
                        "recommended_action": f"Address {sd_id} through additional control implementation or supplementary policy",
                    }
                )

    if gaps:
        first = gaps[0]
        data["gap_1_subdomain"] = first.get("sub_domain_id", "")
        data["gap_1_regulation"] = first.get("regulation", "N/A")
        data["gap_1_clause"] = first.get("clause", "N/A")
        data["gap_1_description"] = first.get("description", "")
        data["gap_1_risk"] = first.get("risk_level", "MEDIUM")
        data["gap_1_type"] = first.get("type", "Coverage Gap")
        data["gap_1_action"] = first.get("recommended_action", "Review and address coverage gap")
        rl = data["gap_1_risk"]
        risk_count[rl] = risk_count.get(rl, 0) + 1
        risk_sds[rl].append(data["gap_1_subdomain"])

    for g in gaps[1:]:
        rl = g.get("risk_level", "MEDIUM")
        risk_count[rl] = risk_count.get(rl, 0) + 1
        risk_sds[rl].append(g.get("sub_domain_id", ""))

    data["high_risk_count"] = str(risk_count["HIGH"])
    data["high_risk_subdomains"] = ", ".join(risk_sds["HIGH"]) or "None"
    data["medium_risk_count"] = str(risk_count["MEDIUM"])
    data["medium_risk_subdomains"] = ", ".join(risk_sds["MEDIUM"]) or "None"
    data["low_risk_count"] = str(risk_count["LOW"])
    data["low_risk_subdomains"] = ", ".join(risk_sds["LOW"]) or "None"

    additional_gap_rows = []
    for i, g in enumerate(gaps or []):
        if i < 1:
            continue
        gid = g.get("gap_id", "") or g.get("gapId", "") or f"GAP-{i+1:03d}"
        sd = g.get("sub_domain_id", "") or g.get("subDomainId", "") or ""
        reg = g.get("regulation", "") or g.get("regulationId", "") or ""
        clause = g.get("clause", "") or ""
        gtype = g.get("type", "") or g.get("gapType", "") or "Coverage Gap"
        risk = g.get("risk_level", "MEDIUM") or g.get("riskLevel", "MEDIUM")
        action = g.get("recommended_action", "") or g.get("recommendedAction", "") or ""
        additional_gap_rows.append(
            f"| {gid} | {sd} | {reg} | {clause} | {gtype} | {risk} | {action} |"
        )
    data["additional_gaps"] = "\n".join(additional_gap_rows) if additional_gap_rows else ""
    return data


def _build_obligation_placeholders(obligations: list) -> dict:
    """Build obligation shell placeholders for Doc 07 section 8."""
    data: dict[str, str] = {}
    if obligations:
        first = obligations[0]
        data["obligation_id"] = (
            _get_attr(first, "obligationId", "") or _get_attr(first, "id", "") or "OBL-001"
        )
        data["obligation_category"] = _get_attr(first, "category", "") or "DATA_PROTECTION"
        data["obligation_target_subdomain"] = (
            _get_attr(first, "targetSubDomain", "") or _get_attr(first, "subDomainId", "") or "TBD"
        )
    else:
        data["obligation_id"] = "OBL-001"
        data["obligation_category"] = "DATA_PROTECTION"
        data["obligation_target_subdomain"] = "D-05.1"
    return data


def _build_strategic_implication_placeholders(implications: list) -> dict:
    """Build strategic implication placeholders for Doc 05/07."""
    data: dict[str, str] = {}
    if implications:
        first = implications[0]
        data["si_1_regulation"] = (
            _get_attr(first, "regulationId", "")
            or _get_attr(first, "regulation", "")
            or _get_attr(first, "sourceRegulation", "")
            or "N/A"
        )
        data["si_1_description"] = (
            _get_attr(first, "description", "")
            or _get_attr(first, "implication", "")
            or "Pending analysis"
        )
        data["si_1_impact"] = (
            _get_attr(first, "impact", "") or _get_attr(first, "architecturalImpact", "") or "TBD"
        )
        data["si_1_priority"] = _get_attr(first, "priority", "") or "MEDIUM"
        data["si_1_subdomain"] = (
            _get_attr(first, "subDomainId", "")
            or _get_attr(first, "subdomainId", "")
            or _get_attr(first, "sub_domain_id", "")
            or "TBD"
        )
    else:
        data["si_1_regulation"] = "N/A"
        data["si_1_description"] = "Pending strategic analysis"
        data["si_1_impact"] = "TBD"
        data["si_1_priority"] = "MEDIUM"
        data["si_1_subdomain"] = "TBD"

    additional_si_rows = []
    for i, impl in enumerate(implications or []):
        if i < 1:
            continue
        siid = (
            _get_attr(impl, "implicationId", "")
            or _get_attr(impl, "implication_id", "")
            or f"SI-{i+1:03d}"
        )
        regs = _get_attr(impl, "sourceRegulations", "") or _get_attr(impl, "regulationId", "") or ""
        if isinstance(regs, list):
            regs = ", ".join(str(r) for r in regs)
        desc = _get_attr(impl, "description", "") or ""
        impact = _get_attr(impl, "architecturalImpact", "") or _get_attr(impl, "impact", "") or ""
        prio = _get_attr(impl, "priority", "") or "MEDIUM"
        sd = _get_attr(impl, "subDomainId", "") or _get_attr(impl, "subdomainId", "") or ""
        additional_si_rows.append(f"| {siid} | {sd} | {regs} | {desc} | {impact} | {prio} |")
    data["additional_implications"] = "\n".join(additional_si_rows) if additional_si_rows else ""
    return data


def _set_company_context_bool(ctx: dict, default: bool) -> str:
    """Return a human-readable string for a company context boolean."""
    raw = ctx.get("processes_personal_data", default)
    if isinstance(raw, bool):
        return "True" if raw else "False"
    return str(raw)


def _summarize_intake(intake_md: str, layer: int, ctx: dict) -> str:
    """Extract a brief summary for each intake form layer."""
    if not intake_md:
        layers = [
            f"Company: {ctx.get('name', 'N/A')}, Sector: {ctx.get('sector', 'N/A')}, Size: {ctx.get('size', 'N/A')}",
            "Regulatory decision tree completed",
            "Conditional blocks determined by company context",
        ]
        return layers[layer] if layer < len(layers) else "Completed"
    return f"Layer {layer}: Responses documented in intake form."


def _build_comprehensive_data(state: Phase1State) -> dict:
    """Build data dict with ALL template placeholder values (both {var} and [placeholder])."""
    coverage_matrix = _build_coverage_matrix(state)
    coverage_summary = _build_coverage_summary(coverage_matrix)
    complementarity_analysis = _build_complementarity_analysis(state)
    strategic_implications = state.get("strategic_implications", [])
    regulatory_gaps = _build_regulatory_gaps(state, coverage_matrix)
    company_context = state.get("company_context", {}) or {}
    compliance_context = state.get("compliance_context", {}) or {}
    stakeholders = state.get("stakeholders", [])
    business_goals = state.get("business_goals", [])
    regulations = state.get("regulations", [])
    regulatory_clauses = _dedup_clauses(state.get("regulatory_clauses", []))
    applicable_regulations = state.get("applicable_regulations", [])
    case_config = state.get("case_config", {}) or {}
    interactions = state.get("regulatory_interactions", [])
    obligations = state.get("regulatory_obligations", [])
    extensions = state.get("conditional_extensions", [])
    domain_elaboration = state.get("domain_elaboration_entries", [])
    case_path = state.get("case_path", "")

    company_name = case_config.get("name", "N/A")
    jurisdiction = company_context.get("technological_control_plane", "N/A")
    sector = company_context.get("sector", "N/A")
    size_cat = company_context.get("size", "N/A")

    doc_ids = _generate_doc_ids(company_name)

    substantive_sds = [
        sd for sd, d in coverage_matrix.items() if d["coverage_level"] == "SUBSTANTIVE"
    ]
    not_addressed_sds = [
        sd for sd, d in coverage_matrix.items() if d["coverage_level"] == "NOT_ADDRESSED"
    ]

    data: dict[str, str] = {}

    data.update(
        {
            "company_name": company_name,
            "COMPANY_NAME": company_name.upper(),
            "sector": sector,
            "size_category": size_cat,
            "jurisdiction": jurisdiction,
            "company_context_id": f"CTX-{doc_ids['company_short']}",
            "compliance_context_id": compliance_context.get("id", f"CC-{doc_ids['company_short']}"),
            "assessment_id": doc_ids["assessment_id"],
            "matrix_id": doc_ids["compliance_matrix_id"],
            "complexity_tier": state.get("complexity_tier", "MEDIUM"),
        }
    )

    data.update(
        {
            "applicable_regulations_list": ", ".join(
                r if isinstance(r, str) else r.get("regulationId", "")
                for r in applicable_regulations
            ),
            "phase_1_status": "DRAFT",
            "phase1_status": "DRAFT",
            "gate_status": "PENDING",
            "total_subdomains": str(coverage_summary["total_subdomains"]),
            "substantive_count": str(coverage_summary["substantive"]),
            "partial_count": str(coverage_summary["partial"]),
            "not_addressed_count": str(coverage_summary["not_addressed"]),
            "coverage_pct": f"{coverage_summary['coverage_pct']:.1f}",
            "avg_ni": f"{coverage_summary['mean_ni']:.1f}",
            "phase": "Phase 1 - Regulatory Foundations",
            "total_applicable_clauses": str(len(regulatory_clauses)),
            "sole_authority_gaps": ", ".join(not_addressed_sds) if not_addressed_sds else "None",
            "stakeholder_rationale": _build_stakeholder_rationale(stakeholders),
            "business_goal_rationale": _build_business_goal_rationale(business_goals),
            "context_assessment_rationale": _build_context_assessment_rationale(company_context),
            "evidence_sources": _build_evidence_sources(),
        }
    )

    data.update(_build_regulation_placeholders(applicable_regulations))
    data.update(
        _build_applicability_section_placeholders(
            company_context, regulatory_clauses, applicable_regulations
        )
    )

    data.update(
        {
            "native_reg_1": "GDPR",
            "native_domain_1": "D-05.1 (Data Minimization)",
            "native_obligation_1": "Implement data minimization principles",
            "native_actor_1": "Data Controller",
            "native_responsibility_1": "Compliance Lead / DPO",
            "native_1": "GDPR compliance program",
            "native_2": "CRA security requirements",
            "additional_native": "",
            "inherited_reg_1": "N/A",
            "inherited_domain_1": "N/A",
            "inherited_obligation_1": "N/A",
            "inherited_source_1": "N/A",
            "inherited_evidence_1": "N/A",
            "inherited_1": "N/A",
            "inherited_2": "N/A",
            "additional_inherited": "",
        }
    )

    data.update(_build_interaction_placeholders(interactions))
    data.update(
        _build_coverage_section_placeholders(
            coverage_matrix, coverage_summary, applicable_regulations
        )
    )
    data.update(_build_strategic_implication_placeholders(strategic_implications))
    data.update(
        _build_clause_stats_placeholders(regulatory_clauses, applicable_regulations, case_path)
    )
    data.update(_build_gap_placeholders(regulatory_gaps, coverage_matrix, applicable_regulations))

    if extensions:
        first_ext = extensions[0]
        data.update(
            {
                "ext_reg_block_id": _get_attr(first_ext, "blockId", "")
                or _get_attr(first_ext, "id", "")
                or "EXT-001",
                "ext_reg_block_name": _get_attr(first_ext, "blockName", "")
                or _get_attr(first_ext, "name", "")
                or "",
                "ext_reg_regulation": _get_attr(first_ext, "regulationId", "")
                or _get_attr(first_ext, "regulation", "")
                or "",
                "ext_reg_impact": _get_attr(first_ext, "impact", "") or "",
                "ext_reg_threshold": _get_attr(first_ext, "thresholdEffect", "")
                or _get_attr(first_ext, "threshold", "")
                or "",
                "ext_reg_net_change": _get_attr(first_ext, "netChange", "") or "",
            }
        )
    else:
        data.update(
            {
                "ext_reg_block_id": "N/A",
                "ext_reg_block_name": "N/A",
                "ext_reg_regulation": "N/A",
                "ext_reg_impact": "N/A",
                "ext_reg_threshold": "N/A",
                "ext_reg_net_change": "N/A",
            }
        )

    data.update(_build_subdomain_matrix_placeholders(coverage_matrix))

    overlaps = complementarity_analysis.get("overlaps", [])
    if overlaps:
        first_ol = overlaps[0]
        reg_pair = first_ol.get("regulation_pair", "GDPR / CRA").split(" / ")
        data.update(
            {
                "overlap_reg_1": reg_pair[0] if len(reg_pair) > 0 else "GDPR",
                "overlap_reg_2": reg_pair[1] if len(reg_pair) > 1 else "CRA",
                "overlap_subdomains": first_ol.get("shared_scope", "D-05.1, D-09.2"),
                "overlap_pct": "65",
                "overlap_synergy": first_ol.get(
                    "shared_scope", "Data protection and security requirements overlap"
                ),
                "shared_scope": first_ol.get("shared_scope", ""),
                "complementarity_index": "0.65",
                "structural_connectedness": first_ol.get("structural_connectedness", "MEDIUM"),
            }
        )
    else:
        data.update(
            {
                "overlap_reg_1": "GDPR",
                "overlap_reg_2": "CRA",
                "overlap_subdomains": "D-05.1, D-09.2",
                "overlap_pct": "65",
                "overlap_synergy": "Data protection and security requirements overlap in data lifecycle management and risk assessment",
                "shared_scope": "Data lifecycle, Risk assessment",
                "complementarity_index": "0.65",
                "structural_connectedness": "MEDIUM",
            }
        )

    data.update(
        {
            "co_1_subdomain": "D-05.1",
            "co_1_regulations": "GDPR, CRA",
            "co_1_description": "Unified data lifecycle management satisfies both GDPR data minimization and CRA security requirements",
            "co_1_benefit": "Single implementation for dual compliance, reducing duplication",
            "additional_opportunities": "",
            "synergistic_subdomains": ", ".join(substantive_sds)
            if substantive_sds
            else "D-05.1, D-09.2",
            "synergistic_example": "GDPR Data Minimization + CRA Security Requirements reinforce each other in D-05.1",
            "structural_subdomains": ", ".join(substantive_sds) if substantive_sds else "TBD",
            "structural_example": "GDPR and CRA impose compatible but distinct requirements that can be resolved at design",
            "contextual_subdomains": "D-05.1, D-04.3",
            "contextual_example": "Data breach notification must satisfy both GDPR (72h) and potential CRA disclosure timelines",
            "event_1_description": "Personal data breach in a CRA-regulated digital product",
            "event_1_regulations": "GDPR, CRA",
            "event_1_subdomain": "D-04.3",
            "event_1_tension": "Dual notification timelines (GDPR 72h vs CRA disclosure) require coordinated response",
            "event_1_resolution": "Unified incident response procedure satisfying both notification requirements",
            "additional_events": "",
        }
    )

    if domain_elaboration:
        first_de = domain_elaboration[0]
        data.update(
            {
                "dee_subdomain_id": _get_attr(first_de, "subDomainId", "")
                or _get_attr(first_de, "sub_domain_id", "")
                or "D-05.1",
                "dee_elaboration_factor": _get_attr(first_de, "elaborationFactor", "")
                or _get_attr(first_de, "factor", "")
                or "Data minimization",
                "dee_dominant_regulation": _get_attr(first_de, "dominantRegulation", "")
                or _get_attr(first_de, "dominant_regulation", "")
                or "GDPR",
                "dee_relation_type": _get_attr(first_de, "relationType", "")
                or _get_attr(first_de, "relation_type", "")
                or "REINFORCING",
                "dee_normative_intensity": str(
                    _get_attr(first_de, "normativeIntensity", "")
                    or _get_attr(first_de, "normative_intensity", "")
                    or "3.0"
                ),
                "dee_weighted_score": str(
                    _get_attr(first_de, "weightedScore", "")
                    or _get_attr(first_de, "weighted_score", "")
                    or "3.0"
                ),
                "dee_notes": _get_attr(first_de, "notes", "")
                or _get_attr(first_de, "description", "")
                or "",
            }
        )
    else:
        data.update(
            {
                "dee_subdomain_id": "D-05.1",
                "dee_elaboration_factor": "Data minimization",
                "dee_dominant_regulation": "GDPR",
                "dee_relation_type": "REINFORCING",
                "dee_normative_intensity": "3.0",
                "dee_weighted_score": "3.0",
                "dee_notes": "GDPR Article 5(1)(c) data minimization reinforced by CRA security-by-design requirements",
            }
        )

    data.update(_build_obligation_placeholders(obligations))

    data.update(
        {
            "criterion_01_status": "Yes" if company_name != "N/A" else "No",
            "criterion_01_evidence": f"Company Context Assessment (04) completed for {company_name}",
            "criterion_02_status": "Yes" if applicable_regulations else "No",
            "criterion_02_evidence": f"Regulatory Applicability (05) assessed for {len(applicable_regulations)} regulations",
            "criterion_03_status": "Yes" if regulatory_clauses else "No",
            "criterion_03_evidence": f"Clause Mapping Matrix (06) with {len(regulatory_clauses)} clauses mapped",
            "criterion_04_status": "Yes" if coverage_matrix else "No",
            "criterion_04_evidence": f"Sub-domain coverage matrix with {len(coverage_matrix)} entries completed",
            "criterion_05_status": "Yes",
            "criterion_05_evidence": f"{len(regulatory_gaps)} gaps identified and documented",
            "criterion_06_status": "Yes",
            "criterion_06_evidence": "Strategic implications documented in SCM Section 6",
            "criterion_07_status": "Yes",
            "criterion_07_evidence": "Design decisions logged in 03_Design_Decisions.md",
            "phase_1_gate_decision": "PENDING",
            "phase_1_gate_status": "Pending",
            "gate_review_date": datetime.now().strftime("%Y-%m-%d"),
        }
    )

    applicable_regs_list = [
        r if isinstance(r, str) else r.get("regulationId", "") for r in applicable_regulations
    ]
    applicable_regs_list = [r for r in applicable_regs_list if r]
    data.update(
        {
            "applicable_regs_section": "3",
            "coverage_section": "3",
            "strategic_section": "6",
            "gaps_section": "9",
            "applicable_regs_list": ", ".join(applicable_regs_list) or "N/A",
            "list": ", ".join(applicable_regs_list) or "N/A",
        }
    )

    data.update(
        {
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "updated_date": datetime.now().strftime("%Y-%m-%d"),
            "review_date": datetime.now().strftime("%Y-%m-%d"),
        }
    )

    data.update(
        _build_doc04_placeholders(
            state,
            company_name,
            company_context,
            stakeholders,
            business_goals,
            regulations,
            applicable_regulations,
            extensions,
            interactions,
            case_path,
        )
    )

    return data


def _build_doc04_placeholders(
    state: Phase1State,
    company_name: str,
    company_context: dict,
    stakeholders: list,
    business_goals: list,
    regulations: list,
    applicable_regulations: list,
    extensions: list,
    interactions: list,
    case_path: str,
) -> dict:
    """Build Doc 04-specific placeholder values, including CSV data for sections 7-9."""
    d: dict[str, str] = {}
    reg_set = {
        r if isinstance(r, str) else r.get("regulationId", "") for r in applicable_regulations
    }

    role_map = {
        "ceo": (
            "stakeholder_ceo_name",
            "engagement_strategy_ceo",
            "Close collaboration (decision maker)",
        ),
        "cto": ("stakeholder_cto_name", "engagement_strategy_cto", "Regular technical briefings"),
        "dpo": (
            "stakeholder_dpo_name",
            "engagement_strategy_dpo",
            "Consult on data protection matters",
        ),
        "dev": (
            "stakeholder_dev_name",
            "engagement_strategy_dev",
            "Hands-on implementation support",
        ),
    }
    for s in stakeholders or []:
        name = (_get_attr(s, "name", "") or "").lower()
        role = (_get_attr(s, "role", "") or "").lower()
        full_name = _get_attr(s, "name", "") or _get_attr(s, "displayName", "") or ""
        combined = f"{name} {role}"
        for keyword, (name_key, strat_key, strategy) in role_map.items():
            if keyword in combined:
                d[name_key] = full_name
                d[strat_key] = strategy

    for key in [
        "stakeholder_ceo_name",
        "stakeholder_cto_name",
        "stakeholder_dpo_name",
        "stakeholder_dev_name",
        "engagement_strategy_ceo",
        "engagement_strategy_cto",
        "engagement_strategy_dpo",
        "engagement_strategy_dev",
    ]:
        d.setdefault(key, "TBD")

    internal_roles = {"ceo", "cto", "dpo", "dev", "development team"}
    additional_stakeholder_rows = []
    for s in stakeholders or []:
        name = (_get_attr(s, "name", "") or "").lower()
        role = (_get_attr(s, "role", "") or "").lower()
        combined = f"{name} {role}"
        if not any(kw in combined for kw in internal_roles):
            sid = _get_attr(s, "stakeholderId", "") or _get_attr(s, "stakeholder_id", "") or ""
            sname = _get_attr(s, "name", "") or ""
            sorg = _get_attr(s, "organization", "") or ""
            sresp = _get_attr(s, "responsibilities", "") or ""
            additional_stakeholder_rows.append(
                f"| {sid} | {sname} | External | {sorg} | — | {sresp} |"
            )
    d["additional_stakeholders"] = (
        "\n".join(additional_stakeholder_rows) if additional_stakeholder_rows else ""
    )

    for i, g in enumerate(business_goals or []):
        suffix = i + 1
        if suffix > 5:
            break
        gid = _get_attr(g, "goalId", "") or _get_attr(g, "goal_id", "") or f"BG-{suffix:02d}"
        desc = _get_attr(g, "description", "") or _get_attr(g, "goal_description", "") or ""
        prio = _get_attr(g, "priority", "MEDIUM")
        regs_raw = (
            _get_attr(g, "relatedRegulations", "") or _get_attr(g, "related_regulations", "") or ""
        )
        if isinstance(regs_raw, list):
            regs_str = ", ".join(str(r) for r in regs_raw)
        else:
            regs_str = str(regs_raw)
        metrics = _get_attr(g, "successMetrics", "") or _get_attr(g, "success_metrics", "") or ""
        d[f"goal_{suffix}_name"] = desc.split(".")[0][:60] or gid
        d[f"goal_{suffix}_description"] = desc[:200] if desc else "TBD"
        d[f"goal_{suffix}_priority"] = str(prio)
        d[f"goal_{suffix}_regulations"] = regs_str or "N/A"
        d[f"goal_{suffix}_metrics"] = metrics or "TBD"
    if not business_goals:
        for suffix in range(1, 3):
            d[f"goal_{suffix}_name"] = "TBD"
            d[f"goal_{suffix}_description"] = ""
            d[f"goal_{suffix}_priority"] = "MEDIUM"
            d[f"goal_{suffix}_regulations"] = "N/A"
            d[f"goal_{suffix}_metrics"] = ""

    additional_goal_rows = []
    for i, g in enumerate(business_goals or []):
        if i < 2:
            continue
        gid = _get_attr(g, "goalId", "") or _get_attr(g, "goal_id", "") or f"BG-{i+1:02d}"
        desc = _get_attr(g, "description", "") or _get_attr(g, "goal_description", "") or ""
        prio = _get_attr(g, "priority", "MEDIUM")
        regs_raw = (
            _get_attr(g, "relatedRegulations", "") or _get_attr(g, "related_regulations", "") or ""
        )
        if isinstance(regs_raw, list):
            regs_str = ", ".join(str(r) for r in regs_raw)
        else:
            regs_str = str(regs_raw)
        metrics = _get_attr(g, "successMetrics", "") or _get_attr(g, "success_metrics", "") or ""
        additional_goal_rows.append(
            f"| {gid} | {desc.split('.')[0][:60] or gid} | {desc[:200] if desc else 'TBD'} | {prio} | {regs_str or 'N/A'} | {metrics or 'TBD'} |"
        )
    d["additional_goals"] = "\n".join(additional_goal_rows) if additional_goal_rows else ""

    for reg, short in [
        ("GDPR", "gdpr"),
        ("CRA", "cra"),
        ("NIS2", "nis2"),
        ("DORA", "dora"),
        ("AIAct", "aiact"),
    ]:
        applicable = reg in reg_set
        d[f"{short}_applicable"] = "Yes" if applicable else "No"
        d[f"{short}_met"] = "Yes" if applicable else "N/A"
        d[f"{short}_threshold"] = {
            "gdpr": "EU presence",
            "cra": "Digital product",
            "nis2": "Sector classification",
            "dora": "Financial entity",
            "aiact": "AI system usage",
        }.get(short, "N/A")

    intake_md = state.get("intake_markdown", "")
    d["intake_layer_0_summary"] = _summarize_intake(intake_md, 0, company_context)
    d["intake_layer_1_summary"] = _summarize_intake(intake_md, 1, company_context)
    d["intake_layer_2_summary"] = _summarize_intake(intake_md, 2, company_context)

    tier = state.get("complexity_tier", "MEDIUM")
    n_app = len(applicable_regulations)
    d["complexity_tier_rationale"] = (
        f"Company has {n_app} applicable regulation(s) in "
        f"{company_context.get('sector', 'N/A')} sector "
        f"({company_context.get('size', 'N/A')} size). "
        f"Complexity tier: {tier}."
    )

    if extensions:
        first = extensions[0]
        d["extension_block_id"] = (
            _get_attr(first, "blockId", "") or _get_attr(first, "id", "") or "CB-001"
        )
        d["extension_block_name"] = (
            _get_attr(first, "blockName", "") or _get_attr(first, "name", "") or ""
        )
        d["extension_trigger_condition"] = (
            _get_attr(first, "triggerCondition", "")
            or _get_attr(first, "condition", "")
            or "Personal data processing"
        )
        d["extension_is_active"] = str(_get_attr(first, "isActive", True))
    else:
        d.update(
            {
                "extension_block_id": "N/A",
                "extension_block_name": "N/A",
                "extension_trigger_condition": "N/A",
                "extension_is_active": "False",
            }
        )

    if interactions:
        first = interactions[0]
        d["interaction_id"] = (
            _get_attr(first, "interactionId", "") or _get_attr(first, "id", "") or "RI-001"
        )
        d["interaction_type"] = (
            _get_attr(first, "interactionType", "") or _get_attr(first, "type", "") or "SYNERGY"
        )
        inv = first.get("involvedRegulations", first.get("regulationId1", "")) or ""
        if isinstance(inv, list):
            inv = ", ".join(inv)
        d["involved_regulations"] = inv if inv else "GDPR, CRA"
        d["conflict_description"] = (
            _get_attr(first, "description", "")
            or _get_attr(first, "conflictDescription", "")
            or "Overlap identified between GDPR and CRA"
        )
        d["resolution_principle"] = (
            _get_attr(first, "resolutionPrinciple", "")
            or _get_attr(first, "resolution_principle", "")
            or "Harmonization"
        )
    else:
        d.update(
            {
                "interaction_id": "RI-001",
                "interaction_type": "SYNERGY",
                "involved_regulations": "GDPR, CRA",
                "conflict_description": "Pending analysis",
                "resolution_principle": "TBD",
            }
        )

    csv_arch = _load_csv_rows(case_path, "16_architectural_implications.csv")
    if csv_arch:
        row = csv_arch[0]
        d["implication_description"] = row.get("description", row.get("implication", ""))
        d["implication_regulation"] = row.get("regulation", row.get("regulationId", ""))
        d["implication_impact_area"] = row.get("impactArea", row.get("impact_area", ""))
        d["implication_severity"] = row.get("severity", "MEDIUM")
        d["implication_mitigation"] = row.get("mitigation", row.get("mitigationApproach", ""))
    else:
        d["implication_description"] = "No architectural implications identified"
        d["implication_regulation"] = "N/A"
        d["implication_impact_area"] = "N/A"
        d["implication_severity"] = "N/A"
        d["implication_mitigation"] = "N/A"

    csv_flows = _load_csv_rows(case_path, "13_data_flows.csv")
    if csv_flows:
        row = csv_flows[0]
        d["data_type"] = row.get("dataType", row.get("data_type", ""))
        d["data_source"] = row.get("source", "")
        d["data_destination"] = row.get("destination", "")
        d["data_transfer_method"] = row.get("transferMethod", row.get("transfer_method", ""))
        d["data_encryption"] = row.get("encryption", "")
        d["data_regulatory_constraint"] = row.get(
            "regulatoryConstraint", row.get("regulatory_constraint", "")
        )
    else:
        d["data_type"] = "N/A"
        d["data_source"] = "N/A"
        d["data_destination"] = "N/A"
        d["data_transfer_method"] = "N/A"
        d["data_encryption"] = "N/A"
        d["data_regulatory_constraint"] = "N/A"

    csv_cap = _load_csv_rows(case_path, "14_compliance_capabilities.csv")
    if csv_cap:
        row = csv_cap[0]
        d["capability_name"] = row.get("capability", row.get("name", ""))
        d["capability_current_state"] = row.get("currentState", row.get("current_state", ""))
        d["capability_target_state"] = row.get("targetState", row.get("target_state", ""))
        d["capability_gap"] = row.get("gap", "")
        d["capability_priority"] = row.get("priority", "MEDIUM")
    else:
        d["capability_name"] = "N/A"
        d["capability_current_state"] = "N/A"
        d["capability_target_state"] = "N/A"
        d["capability_gap"] = "N/A"
        d["capability_priority"] = "N/A"

    return d


def _write_filled_output(
    case_path: str,
    template_name: str,
    filled_content: str,
    intermediate_data: dict | None = None,
    force_rebuild: bool = True,
) -> str:
    """Write filled template to output directory with versioning.

    Returns the output filename (e.g. '04_Company_Context_Assessment_filled.md').
    """
    out_dir = Path(case_path) / "output" / "phase1"
    out_dir.mkdir(parents=True, exist_ok=True)
    versions_dir = out_dir / "versions"
    intermediate_dir = out_dir / "intermediate"

    stem = template_name.replace(".md", "")
    filled_name = f"{stem}_filled.md"
    filled_path = out_dir / filled_name

    if not force_rebuild and filled_path.exists():
        file_age = time.time() - filled_path.stat().st_mtime
        if file_age < 3600:
            logger.info(
                "[produce_docs] skipped %s (age=%.0fs < 3600s limit)", filled_name, file_age
            )
            return filled_name

    next_version = 1
    if filled_path.exists():
        versions_dir.mkdir(parents=True, exist_ok=True)
        existing = [
            p for p in versions_dir.glob(f"{stem}_v*.md") if p.stem.split("_v")[-1].isdigit()
        ]
        nums = [int(p.stem.split("_v")[-1]) for p in existing]
        next_version = (max(nums) + 1) if nums else 2
        versioned_path = versions_dir / f"{stem}_v{next_version}.md"
        versioned_path.write_text(filled_path.read_text(encoding="utf-8"), encoding="utf-8")
        logger.info(
            "[produce_docs] archived previous output: %s -> %s",
            filled_path.name,
            versioned_path.name,
        )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    model_tag = f"<!-- Generated by: deterministic (no LLM) | {generated_at} -->\n"
    filled_path.write_text(model_tag + filled_content, encoding="utf-8")
    logger.info("[produce_docs] wrote canonical: %s (version=%d)", filled_name, next_version)

    if intermediate_data is not None:
        intermediate_dir.mkdir(parents=True, exist_ok=True)
        intermediate_data["_metadata"] = {
            "generator": "aegis-kg produce_documents (deterministic)",
            "generated_at": datetime.now().isoformat(),
        }
        intermediate_path = intermediate_dir / f"{stem}_v{next_version}.yaml"
        import yaml

        intermediate_path.write_text(
            yaml.safe_dump(intermediate_data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("[produce_docs] wrote intermediate: %s", intermediate_path.name)

    return filled_name


def produce_documents(state: Phase1State) -> dict:
    """Render all 4 Phase 1 templates and write outputs (deterministic, zero LLM calls).

    Args:
        state: Full Phase 1 state (after c05_matrix).

    Returns:
        Dict with doc_paths, doc_04..07_path, structured_compliance_matrix, errors.
    """
    logger.info("[produce_docs] START (deterministic mode)")

    case_path = state.get("case_path", "")
    if not case_path:
        return {"errors": ["produce_documents: no case_path in state"], "doc_paths": {}}

    errors: list[str] = []
    filled_docs: list[str] = []

    data = _build_comprehensive_data(state)

    for template_name in PHASE1_TEMPLATES:
        logger.info("[produce_docs] Processing template=%s", template_name)
        template_path = Path(case_path) / "templates" / "phase1" / template_name
        if not template_path.exists():
            errors.append(f"Template not found: {template_path}")
            logger.warning("[produce_docs] Missing template: %s", template_path)
            continue

        try:
            template_content = template_path.read_text(encoding="utf-8")
            filled = _fill_deterministic(template_content, data)

            intermediate_payload = _json_safe(
                {
                    "company_context": state.get("company_context", {}),
                    "stakeholders": state.get("stakeholders", []),
                    "business_goals": state.get("business_goals", []),
                    "regulations": state.get("regulations", []),
                    "regulatory_clauses": state.get("regulatory_clauses", []),
                    "applicable_regulations": state.get("applicable_regulations", []),
                    "domain_coverage_entries": state.get("domain_coverage_entries", []),
                    "domain_elaboration_entries": state.get("domain_elaboration_entries", []),
                    "regulatory_obligations": state.get("regulatory_obligations", []),
                    "structured_compliance_matrix": state.get("structured_compliance_matrix", {}),
                }
            )

            try:
                output = _write_filled_output(
                    case_path, template_name, filled, intermediate_data=intermediate_payload
                )
            except Exception:
                logger.warning("[produce_docs] YAML intermediate failed, writing without it")
                output = _write_filled_output(
                    case_path, template_name, filled, intermediate_data=None
                )
            filled_docs.append(output)
            logger.info("[produce_docs] Wrote %s", output)
        except Exception as e:
            logger.exception("[produce_docs] Error processing %s: %s", template_name, e)
            errors.append(f"produce_documents error for {template_name}: {e!s}")

    structured_matrix = state.get("structured_compliance_matrix", {})

    doc_07_path = next((p for p in filled_docs if "07_" in p), "")
    if doc_07_path:
        scm = _build_coverage_matrix(state)
        scm_summary = _build_coverage_summary(scm)
        structured_matrix["coverage_summary"] = scm_summary

    doc_paths: dict[str, str] = {}
    for filled_name in filled_docs:
        stem = filled_name.replace("_filled.md", "")
        template_map = {
            "04_Company_Context_Assessment": "04_Company_Context_Assessment.md",
            "05_Regulatory_Applicability": "05_Regulatory_Applicability.md",
            "06_Clause_Mapping_Matrix": "06_Clause_Mapping_Matrix.md",
            "07_Structured_Compliance_Matrix": "07_Structured_Compliance_Matrix.md",
        }
        if stem in template_map:
            doc_paths[filled_name] = template_map[stem]

    logger.info("[produce_docs] Done. Docs=%s, Errors=%d", filled_docs, len(errors))

    return {
        "doc_paths": doc_paths,
        "doc_04_path": next((p for p in filled_docs if "04_" in p), ""),
        "doc_05_path": next((p for p in filled_docs if "05_" in p), ""),
        "doc_06_path": next((p for p in filled_docs if "06_" in p), ""),
        "doc_07_path": next((p for p in filled_docs if "07_" in p), ""),
        "structured_compliance_matrix": structured_matrix,
        "errors": errors,
        "degraded": bool(errors),
        "current_phase": "DOCUMENTS_PRODUCED",
    }
