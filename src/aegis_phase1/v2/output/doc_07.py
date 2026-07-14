"""doc_07 — render 07_Structured_Compliance_Matrix.md.

The structured compliance matrix is the canonical Phase 1 output. It
aggregates the per-sub-domain coverage against each applicable
regulation, surfaces complementarity opportunities and strategic
tensions, lists sole-authority gaps, and ships an eight-criterion gate
checklist that confirms Phase 1 is shippable.

Sections produced:

1. Purpose
2. Inputs
3. Coverage matrix — 38 sub-domain rows × applicable regulations, with
   total / coverage level / normative-intensity field. The 38 rows are
   derived from the layer-0 taxonomy and the ontology's ``covered`` /
   ``not_covered`` split (entries present in the ontology are merged
   with missing catalogue entries rendered as "-").
4. Summary dashboard — coverage counts, percentages, normative-intensity
   mean, gap count.
5. Complementarity — overlaps table, opportunities detail (§5.1),
   compound events produced by REDUCE-LLM P1C-LLM-02 (§5.2).
6. Strategic implications — table (§6), narrative (§6.1), strategic
   synthesis produced by REDUCE-LLM P1C-LLM-03 (§6.2).
7. Gaps — derived from ``ontology.tensions`` and ``not_covered``.
8. Gate checklist — 8 criteria with PASS / FAIL and evidence.

The implementation is deterministic by default; no external methodology
text is reproduced. Optional LLM invocation is provided for narrative
sections only.

Contract: AEGIS-P1-CORR-002 added §5.2 (REDUCE-LLM P1C-LLM-02 compound
events) and §6.2 (REDUCE-LLM P1C-LLM-03 strategic synthesis), plus two
new gate criteria (rows 7 and 8).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from aegis_phase1.v2.output._common import (
    generate_frontmatter,
    markdown_table,
    write_output,
)
from aegis_phase1.v2.output._narrative import render_mandatory_narrative

logger = logging.getLogger(__name__)

_FILENAME = "07_Structured_Compliance_Matrix.md"
_MAX_FRAGMENT_BYTES = 4000
_MOCK_TRUTHS = {"1", "true", "yes", "on"}


def render_doc_07(
    state: dict[str, Any],
    output_dir: str,
    llm_invoker: Any | None = None,
) -> dict[str, str]:
    """Render document 07 (structured compliance matrix).

    Args:
        state: Pipeline state.
        output_dir: Output directory.
        llm_invoker: Optional LLM invoker for the §6 strategic
            narrative. Falls back to deterministic prose when None or
            ``MOCK_LLM`` is truthy.

    Returns:
        Mapping ``AEGIS-P1-07`` -> absolute file path.
    """
    ontology = state.get("ontology") or {}
    regs = state.get("regulations") or ontology.get("regulations", [])
    subdomains = ontology.get("subdomains", {}) if isinstance(ontology, Mapping) else {}
    coverage_summary = ontology.get("coverage_summary", {}) if isinstance(ontology, Mapping) else {}
    overlaps = ontology.get("overlaps", []) if isinstance(ontology, Mapping) else []
    clauses = ontology.get("clause_mappings", []) if isinstance(ontology, Mapping) else []

    use_llm = _should_use_llm(llm_invoker)
    invoker = llm_invoker if use_llm else None

    parts: list[str] = []
    parts.append("# AEGIS-P1-07 Structured Compliance Matrix\n")
    parts.extend(_section_1_purpose())
    parts.extend(_section_2_inputs())
    parts.extend(_section_3_coverage_matrix(subdomains, clauses, regs))
    parts.extend(_section_4_summary(subdomains, clauses, regs, coverage_summary))
    parts.extend(_section_5_complementarity(overlaps, state))
    parts.extend(_section_6_strategic_implications(state, regs, invoker))
    parts.extend(_section_7_gaps(ontology, subdomains))
    parts.extend(_section_8_gate_checklist(state, ontology))

    body = "\n".join(parts)
    frontmatter = _build_frontmatter(state, regs)
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_07: wrote %s", path)
    return {"AEGIS-P1-07": path}


# ─────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────


def _section_1_purpose() -> list[str]:
    parts: list[str] = []
    parts.append("## 1. PURPOSE\n")
    parts.append(
        "Aggregate per-sub-domain coverage against each regulation, "
        "highlight complementarity and overlaps, surface sole-authority "
        "gaps, and ship a six-criterion gate-checklist confirming that "
        "Phase 1 is complete enough to proceed to Phase 2.\n"
    )
    parts.append(
        "The matrix is the primary hand-off from Phase 1 to Phase 2 "
        "(obligation derivation, rules catalogue, allocation) and is "
        "indexed in the dependency graph as ``GATE-C``.\n"
    )
    return parts


def _section_2_inputs() -> list[str]:
    parts: list[str] = []
    parts.append("## 2. INPUTS\n")
    parts.append(
        markdown_table(
            ["Input", "Source Document", "Role in §3..§8"],
            [
                ("Company context", "AEGIS-P1-04", "scale + applicability filter"),
                ("Applicability assessments", "AEGIS-P1-05", "applicable-yes column criterion"),
                ("Clause mappings", "AEGIS-P1-06", "per-cell normative-intensity aggregation"),
                ("Sub-domain catalogue", "00_Taxonomy_Reference.md", "row identity for the 38-row matrix"),
                ("Architectural inventory", "AEGIS-P1-04a", "system references in §5 complementarity"),
                ("Proportionality profile", "AEGIS-P1-07b", "tier annotation per row"),
            ],
        )
    )
    parts.append("")
    return parts


def _section_3_coverage_matrix(
    subdomains: Mapping[str, Any],
    clauses: list[Any],
    regs: list[Any],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 3. COVERAGE MATRIX\n")
    parts.append(
        "The matrix below contains one row per sub-domain (38 nominal). "
        "Each cell carries a regulation abbreviation when that "
        "regulation has at least one clause mapping onto the sub-domain, "
        "or \"—\" when not applicable. NI (normative intensity) is the "
        "mean of the ``normative_strength`` field across all clauses that "
        "map onto the cell, rounded to one decimal.\n"
    )
    rows = _matrix_rows(subdomains, clauses, regs)
    if not rows:
        parts.append("_No coverage data available — ontology is empty._\n")
    else:
        headers = ["Sub-domain", "Name"]
        regulations = [r for r in regs if isinstance(r, Mapping)]
        headers.extend(_abbr(r) for r in regulations)
        headers.extend(["Total", "Status", "NI"])
        parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_4_summary(
    subdomains: Mapping[str, Any],
    clauses: list[Any],
    regs: list[Any],
    coverage_summary: Mapping[str, Any],
) -> list[str]:
    parts: list[str] = []
    counts = _coverage_counts(subdomains, clauses, regs)
    ni_mean = _normative_intensity_mean(clauses)
    sole_auth_gaps = (coverage_summary or {}).get("sole_authority_gaps", {}) if isinstance(coverage_summary, Mapping) else {}
    gap_count = 0
    if isinstance(sole_auth_gaps, Mapping):
        gap_count = int(sole_auth_gaps.get("count", 0) or 0)
    parts.append("## 4. SUMMARY\n")
    parts.append(
        markdown_table(
            ["Coverage Level", "Count"],
            [(name, str(counts[name])) for name in counts],
        )
    )
    parts.append("")
    total_count = counts["TOTAL"]
    parts.append(
        f"- Total sub-domains in catalogue: **{total_count}**\n"
        f"- Substantive coverage (≥ 2 regs): **{counts['SUBSTANTIVE']}** "
        f"({(counts['SUBSTANTIVE'] * 100.0) / max(total_count, 1):.1f}%)\n"
        f"- Partial coverage (1 reg): **{counts['PARTIAL']}** "
        f"({(counts['PARTIAL'] * 100.0) / max(total_count, 1):.1f}%)\n"
        f"- Not addressed (0 regs): **{counts['NOT_ADDRESSED']}** "
        f"({(counts['NOT_ADDRESSED'] * 100.0) / max(total_count, 1):.1f}%)\n"
        f"- Mean normative intensity: **{ni_mean:.2f}**\n"
        f"- Sole-authority gaps: **{gap_count}**\n"
        f"- Total clause mappings: **{len(clauses) if isinstance(clauses, list) else 0}**"
    )
    parts.append("")
    return parts


def _section_5_complementarity(overlaps: list[Any], state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 5. COMPLEMENTARITY\n")
    parts.append(
        "Cross-regulation overlaps are presented below. Section 5.1 "
        "expands each overlap into a table of shared sub-domains with "
        "the specific clauses that drive the overlap. Section 5.2 "
        "captures compound-event scenarios detected by the REDUCE-LLM "
        "P1C-LLM-02 stage, in which a single factual incident "
        "simultaneously triggers incompatible obligations from "
        "multiple regulations.\n"
    )
    if not overlaps:
        parts.append("_No overlap data in state.ontology.overlaps._\n")
    else:
        parts.append(
            markdown_table(
                ["Reg Pair", "Shared Sub-domains", "Count", "Jaccard", "Note"],
                [_overlap_row(o) for o in overlaps if isinstance(o, Mapping)],
            )
        )
    parts.append("")
    parts.extend(_section_5_1_opportunities_detail(overlaps))
    parts.extend(_render_compound_events_section(state))
    return parts


def _section_5_1_opportunities_detail(overlaps: list[Any]) -> list[str]:
    parts: list[str] = []
    parts.append("### 5.1 Opportunities — Detail\n")
    opps = _opportunity_rows(overlaps)
    if not opps:
        parts.append("_No synergy opportunities to surface._\n")
    else:
        parts.append(
            markdown_table(
                ["Opportunity ID", "Sub-domain", "Regulations", "Description", "Benefit"],
                opps,
            )
        )
    parts.append("")
    return parts


def _render_compound_events_section(state: dict[str, Any]) -> list[str]:
    """Render §5.2 'Compound Events (LLM-02)' from REDUCE-stage P1C-LLM-02 output.

    Reads ``state["aggregated_data"]["compound_events"]`` — produced by
    ``Phase1Executor.run_phase_1c_reduce()``. When absent (mock mode, no
    invoker, or executor failure), emits a ``PENDING REVIEW`` marker so
    reviewers can identify the gap at a glance.
    """
    parts: list[str] = []
    parts.append("### 5.2 Compound Events (LLM-02)\n")
    parts.append(
        "Cross-domain factual events that simultaneously trigger "
        "incompatible obligations from multiple regulations. Detected "
        "by REDUCE-LLM P1C-LLM-02 against the Regulatory Baseline "
        "``event_templates.yaml`` catalog. Resolution design lives in "
        "Phase 2B and is not produced here.\n"
    )
    ce = state.get("aggregated_data", {}).get("compound_events") if isinstance(state, Mapping) else None
    if not ce or not isinstance(ce, Mapping):
        parts.append(
            "> **[PENDING REVIEW — REDUCE synthesis not yet computed]**\n"
            "> Section ID: `doc_07.section_5_2.compound_events`\n"
            "> \n"
            "> This section requires P1C-LLM-02 (compound event detection). "
            "Re-run the pipeline with a real LLM configured "
            "(`MOCK_LLM=false` and Ollama running) to populate this section. "
            "Or check the run-phase-1c-reduce logs for failure details.\n"
        )
        return parts

    positive = ce.get("positive_events") or []
    negative = ce.get("negative_events") or []

    if positive:
        parts.append("\n#### Confirmed compound events\n")
        parts.append(
            "| Event ID | Description | Sub-domains | Regulations | Tension | Severity | layer0_refs |\n"
            "|---|---|---|---|---|---|---|\n"
        )
        for ev in positive:
            if not isinstance(ev, Mapping):
                continue
            ev_id = str(ev.get("event_id", "?"))
            desc = str(ev.get("description") or "").replace("|", "\\|").replace("\n", " ")[:120]
            subs = ", ".join(str(s) for s in (ev.get("sub_domains") or []))
            regs = ", ".join(str(r) for r in (ev.get("regulations_triggered") or []))
            tension = str(ev.get("tension_type", "?"))
            severity = str(ev.get("severity", "?"))
            refs = ", ".join(str(r) for r in (ev.get("layer0_refs") or []))
            parts.append(f"| {ev_id} | {desc} | {subs} | {regs} | {tension} | {severity} | {refs} |\n")
    else:
        parts.append("\n*No positive compound events detected for this company.*\n")

    if negative:
        parts.append("\n#### Apparent but NOT compound (negative calibration)\n\n")
        for ev in negative:
            if not isinstance(ev, Mapping):
                continue
            scenario = str(ev.get("scenario", "?"))
            regs = ", ".join(str(r) for r in (ev.get("regulations_checked") or []))
            reason = str(ev.get("why_not_compound") or "").replace("|", "\\|").replace("\n", " ")
            parts.append(f"- **{scenario}** — checked {regs}: {reason}\n")

    status = str(ce.get("status", "?"))
    confidence = str(ce.get("confidence", "?"))
    parts.append(
        f"\n*Source: P1C-LLM-02 REDUCE-LLM | status: {status} | confidence: {confidence}*\n"
    )
    return parts


def _section_6_strategic_implications(
    state: dict[str, Any],
    regs: list[Any],
    llm_invoker: Any | None,
) -> list[str]:
    parts: list[str] = []
    parts.append("## 6. STRATEGIC IMPLICATIONS\n")
    rows = _strategic_implication_rows(state, regs)
    parts.append(
        markdown_table(
            [
                "Implication ID",
                "Sub-domain / Clause",
                "Source Regulation(s)",
                "Description",
                "Architecture Impact",
                "Priority",
            ],
            rows,
        )
    )
    parts.append("")
    narrative = render_mandatory_narrative(
        invoker=llm_invoker,
        prompt=_strategic_prompt(state, rows),
        section_id="doc_07.section_6.strategic_narrative",
        max_chars=_MAX_FRAGMENT_BYTES,
    )
    parts.append("### 6.1 Narrative\n")
    parts.append(narrative.rstrip() + "\n")
    parts.extend(_render_strategic_synthesis_section(state))
    return parts


def _section_7_gaps(
    ontology: Mapping[str, Any],
    subdomains: Mapping[str, Any],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 7. GAPS\n")
    parts.append(
        "Gaps are surfaced from three sources and ranked by severity: "
        "(a) structural tensions recorded in ``state.ontology.tensions``; "
        "(b) sole-authority sub-domains in ``state.ontology.subdomains."
        "not_covered``; (c) per-cell rating outcomes flagged during the "
        "v2 evaluation pass.\n"
    )
    rows = _gap_rows(ontology, subdomains)
    if not rows:
        parts.append("_No gaps detected — every cell has either a clause mapping or an explicit non-applicability record._\n")
    else:
        parts.append(
            markdown_table(
                [
                    "Gap ID",
                    "Type",
                    "Sub-domain / Clause",
                    "Severity / Risk",
                    "Action / Mitigation",
                ],
                rows,
            )
        )
    parts.append("")
    return parts


def _section_8_gate_checklist(
    state: dict[str, Any],
    ontology: Mapping[str, Any],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 8. GATE CHECKLIST\n")
    parts.append(
        "Six criteria confirm that Phase 1 is shippable. Each row "
        "carries a PASS / FAIL / PARTIAL status, a one-line evidence "
        "anchor, and the source field or document where the evidence "
        "originates.\n"
    )
    rows = _gate_rows(state, ontology)
    parts.append(
        markdown_table(
            ["#", "Gate criterion", "Status", "Evidence"],
            rows,
        )
    )
    parts.append("")
    parts.append(
        "Gate reviewers must sign the §9 sign-off block before any "
        "Phase-2 consumer ingests this document.\n"
    )
    return parts


# ─────────────────────────────────────────────────────────────────────
# Deterministic data helpers
# ─────────────────────────────────────────────────────────────────────


def _matrix_rows(
    subdomains: Mapping[str, Any],
    clauses: list[Any],
    regs: list[Any],
) -> list[tuple[str, ...]]:
    """Build the 38-row coverage matrix as tuples."""
    covered = (subdomains.get("covered") or []) if isinstance(subdomains, Mapping) else []
    not_covered = (subdomains.get("not_covered") or []) if isinstance(subdomains, Mapping) else []
    regulations = [r for r in regs if isinstance(r, Mapping)]
    regulation_abbrs = [_abbr(r) for r in regulations]

    cell_index = _build_clause_cell_index(clauses, regulation_abbrs)
    rows: list[tuple[str, ...]] = []

    for entry in covered:
        if not isinstance(entry, Mapping):
            continue
        sd_id = str(entry.get("id", "-"))
        name = str(entry.get("name", "-"))
        total = 0
        cells: list[str] = []
        intensity_sums: list[float] = []
        for abbr in regulation_abbrs:
            cell = cell_index.get((sd_id, abbr))
            if cell:
                cells.append(abbr)
                intensity_sums.append(cell["mean"])
                total += 1
            else:
                cells.append("—")
        if total >= 2:
            status = "SUBSTANTIVE"
        elif total == 1:
            status = "PARTIAL"
        else:
            status = "NOT_ADDRESSED"
        ni = (sum(intensity_sums) / len(intensity_sums)) if intensity_sums else None
        ni_str = f"{ni:.1f}" if ni is not None else "—"
        rows.append((sd_id, name, *cells, str(total), status, ni_str))

    for entry in not_covered:
        if not isinstance(entry, Mapping):
            continue
        sd_id = str(entry.get("id", "-"))
        name = str(entry.get("name", "-"))
        rows.append(
            (sd_id, name, *["—"] * len(regulation_abbrs), "0", "NOT_ADDRESSED", "—")
        )
    return rows


def _build_clause_cell_index(
    clauses: list[Any],
    regulation_abbrs: list[str],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Map ``(subdomain_id, regulation_abbr)`` to {count, mean}."""
    index: dict[tuple[str, str], dict[str, Any]] = {}
    if not isinstance(clauses, list):
        return index
    abbr_by_reg_id: dict[str, str] = {}
    for clause in clauses:
        if not isinstance(clause, Mapping):
            continue
        sd_id = str(clause.get("maps_to_subdomain") or "-")
        reg_id = str(clause.get("regulation_id") or "-")
        norm = clause.get("normative_strength")
        if norm is None:
            norm = 0
        try:
            norm_f = float(norm)
        except (TypeError, ValueError):
            continue
        abbr = abbr_by_reg_id.get(reg_id)
        if abbr is None:
            for candidate in regulation_abbrs:
                if reg_id.endswith(candidate) or candidate in reg_id:
                    abbr = candidate
                    break
        if abbr is None:
            continue
        abbr_by_reg_id.setdefault(reg_id, abbr)
        key = (sd_id, abbr)
        cell = index.setdefault(key, {"sum": 0.0, "count": 0})
        cell["sum"] += norm_f
        cell["count"] += 1
    return {
        k: {"mean": v["sum"] / v["count"], "count": v["count"]}
        for k, v in index.items()
    }


def _coverage_counts(
    subdomains: Mapping[str, Any],
    clauses: list[Any],
    regs: list[Any],
) -> dict[str, int]:
    covered = (subdomains.get("covered") or []) if isinstance(subdomains, Mapping) else []
    not_covered = (subdomains.get("not_covered") or []) if isinstance(subdomains, Mapping) else []
    regulation_abbrs = {_abbr(r) for r in regs if isinstance(r, Mapping)}
    clauses = clauses if isinstance(clauses, list) else []
    applied: dict[str, set[str]] = {sd.get("id", ""): set() for sd in covered if isinstance(sd, Mapping)}
    for clause in clauses:
        if not isinstance(clause, Mapping):
            continue
        sd_id = str(clause.get("maps_to_subdomain") or "")
        if sd_id not in applied:
            continue
        reg_id = str(clause.get("regulation_id") or "")
        for abbr in regulation_abbrs:
            if abbr in reg_id or reg_id.endswith(abbr):
                applied[sd_id].add(abbr)
                break
    substantive = sum(1 for regs_for in applied.values() if len(regs_for) >= 2)
    partial = sum(1 for regs_for in applied.values() if len(regs_for) == 1)
    return {
        "SUBSTANTIVE": substantive,
        "PARTIAL": partial,
        "NOT_ADDRESSED": len(not_covered),
        "TOTAL": len(covered) + len(not_covered),
    }


def _normative_intensity_mean(clauses: list[Any]) -> float:
    if not isinstance(clauses, list) or not clauses:
        return 0.0
    strengths: list[float] = []
    for clause in clauses:
        if not isinstance(clause, Mapping):
            continue
        norm = clause.get("normative_strength")
        if norm is None:
            continue
        try:
            strengths.append(float(norm))
        except (TypeError, ValueError):
            continue
    return (sum(strengths) / len(strengths)) if strengths else 0.0


def _overlap_row(entry: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    r1 = str(entry.get("regulation_1", "-"))
    r2 = str(entry.get("regulation_2", "-"))
    shared = entry.get("shared_subdomains") or []
    rendered = "; ".join(
        f"{s.get('id', '-')} ({s.get('name', '-')})"
        for s in shared
        if isinstance(s, Mapping)
    )
    n = entry.get("shared_count", 0)
    jacc = entry.get("jaccard_index", "")
    note = str(entry.get("note", "") or entry.get("description", "") or "-")
    return (f"{r1}+{r2}", rendered or "-", str(n), str(jacc), note)


def _opportunity_rows(overlaps: list[Any]) -> list[tuple[str, str, str, str, str]]:
    """Synthesise explicit opportunity IDs from the overlap entries."""
    rows: list[tuple[str, str, str, str, str]] = []
    seq = 0
    for entry in overlaps:
        if not isinstance(entry, Mapping):
            continue
        r1 = str(entry.get("regulation_1", "?"))
        r2 = str(entry.get("regulation_2", "?"))
        for s in entry.get("shared_subdomains") or []:
            if not isinstance(s, Mapping):
                continue
            seq += 1
            sid = str(s.get("id", "-"))
            name = str(s.get("name", "-"))
            description = str(entry.get("description", "") or "shared coverage")
            rows.append(
                (
                    f"CO-{seq:03d}",
                    f"{sid} {name}",
                    f"{r1} + {r2}",
                    description,
                    "single implementation satisfies both regulations",
                )
            )
    return rows


def _strategic_implication_rows(
    state: dict[str, Any],
    regs: list[Any],
) -> list[tuple[str, str, str, str, str, str]]:
    applicable = sorted(_abbr(r) for r in regs if isinstance(r, Mapping) and r.get("applicable"))
    rows: list[tuple[str, str, str, str, str, str]] = []
    if not applicable:
        return [("SI-000", "—", "—", "No applicable regulations", "—", "LOW")]
    label = " + ".join(applicable)
    rows.append(
        (
            "SI-001",
            "D-01",
            label,
            "Unified encryption baseline satisfies both regulations",
            "Single AES-256 / TLS 1.3 primitive across storage and transport",
            "HIGH",
        )
    )
    rows.append(
        (
            "SI-002",
            "D-04.3",
            label,
            "Joint notification workflow absorbs both clocks",
            "Single incident process, max-SLA routing, single audit log",
            "HIGH",
        )
    )
    rows.append(
        (
            "SI-003",
            "D-09.2",
            label,
            "Unified impact-and-risk assessment template",
            "Single template, dual-output (DPIA + CRA risk assessment)",
            "MEDIUM",
        )
    )
    rows.append(
        (
            "SI-004",
            "D-06.2",
            "CRA",
            "SBOM publication requirement independent of GDPR",
            "Insert CycloneDX SBOM step in CI/CD pipeline",
            "HIGH",
        )
    )
    rows.append(
        (
            "SI-005",
            "D-02.3",
            "CRA",
            "Coordinated-vulnerability-disclosure obligation",
            "Publish security.txt and CVD acknowledgement SLA",
            "MEDIUM",
        )
    )
    return rows


def _strategic_prompt(
    state: dict[str, Any],
    rows: list[tuple[str, str, str, str, str, str]],
) -> str:
    ctx = state.get("company_context")
    name = getattr(ctx, "company_name", "") if ctx else "the company"
    summary = "; ".join(
        f"{r[0]} | {r[2]} -> {r[1]} ({r[5]})"
        for r in rows
    )
    return (
        f"Compose a 3-5 sentence strategic narrative for the structured "
        f"compliance matrix of {name}. Mention complementarity, gaps, "
        f"and time-to-compliance. Anchor the narrative on these "
        f"implications: {summary}"
    )


def _gap_rows(
    ontology: Mapping[str, Any],
    subdomains: Mapping[str, Any],
) -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    seq = 0
    tensions = ontology.get("tensions", []) if isinstance(ontology, Mapping) else []
    for t in tensions:
        if not isinstance(t, Mapping):
            continue
        seq += 1
        rows.append(
            (
                f"GAP-T{seq:03d}",
                "TENSION_DERIVED",
                f"{t.get('clause_1', '-')} ↔ {t.get('clause_2', '-')}",
                str(t.get("severity", "-")),
                str((t.get("resolution") or {}).get("description", "-") if isinstance(t.get("resolution"), Mapping) else "see tensions catalogue"),
            )
        )

    coverage_summary = ontology.get("coverage_summary", {}) if isinstance(ontology, Mapping) else {}
    sole_authority = (
        coverage_summary.get("sole_authority_gaps", {})
        if isinstance(coverage_summary, Mapping)
        else {}
    )
    if isinstance(sole_authority, Mapping):
        gaps = sole_authority.get("subdomains", []) or []
        for entry in gaps:
            if not isinstance(entry, Mapping):
                continue
            seq += 1
            rows.append(
                (
                    f"GAP-S{seq:03d}",
                    "SOLE_AUTHORITY",
                    f"{entry.get('id', '-')} {entry.get('name', '-')}",
                    str(entry.get("risk", "-")),
                    str(entry.get("mitigation", "-")),
                )
            )

    not_covered = subdomains.get("not_covered", []) if isinstance(subdomains, Mapping) else []
    for entry in not_covered:
        if not isinstance(entry, Mapping):
            continue
        seq += 1
        rows.append(
            (
                f"GAP-N{seq:03d}",
                "EXCLUDED_SUBDOMAIN",
                f"{entry.get('id', '-')} {entry.get('name', '-')}",
                str(entry.get("gap_severity", "-")),
                str(entry.get("reason", "excluded by applicable_regulations filter")),
            )
        )
    return rows


def _render_strategic_synthesis_section(state: dict[str, Any]) -> list[str]:
    """Render §6.2 'Strategic Implications (LLM-03)' from REDUCE-LLM P1C-LLM-03.

    Reads ``state["aggregated_data"]["synthesis"]`` — produced by
    ``Phase1Executor.run_phase_1c_reduce()``. When absent (mock mode,
    no invoker, or executor failure), emits a ``PENDING REVIEW`` marker
    so reviewers can identify the gap at a glance. This section does
    NOT propose controls or change tier assignments; Doc 07b (Track B)
    is the authoritative constraint.
    """
    parts: list[str] = []
    parts.append("### 6.2 Strategic Implications (LLM-03)\n")
    parts.append(
        "Cross-lane implications that emerge ONLY when viewing multiple "
        "sub-domains together. Pattern detection across architecture, "
        "ownership, evidence, and supplier boundaries. Doc 07b (Track "
        "B) is the authoritative constraint; this section does NOT "
        "propose controls or change tier assignments.\n"
    )
    synth = state.get("aggregated_data", {}).get("synthesis") if isinstance(state, Mapping) else None
    if not synth or not isinstance(synth, Mapping):
        parts.append(
            "> **[PENDING REVIEW — REDUCE synthesis not yet computed]**\n"
            "> Section ID: `doc_07.section_6_2.strategic_implications`\n"
            "> \n"
            "> This section requires P1C-LLM-03 (strategic synthesis). "
            "Re-run the pipeline with a real LLM configured "
            "(`MOCK_LLM=false` and Ollama running) to populate this section.\n"
        )
        return parts

    implications = synth.get("implications") or []
    if implications:
        parts.append(
            "| ID | Description | Sub-domains | Regulations | Arch. Impact | Risk | doc07b_refs |\n"
            "|---|---|---|---|---|---|---|\n"
        )
        for imp in implications:
            if not isinstance(imp, Mapping):
                continue
            imp_id = str(imp.get("id", "?"))
            desc = str(imp.get("description") or "").replace("|", "\\|").replace("\n", " ")[:140]
            subs = ", ".join(str(s) for s in (imp.get("affected_sub_domains") or []))
            regs = ", ".join(str(r) for r in (imp.get("regulations") or []))
            arch = str(imp.get("architectural_impact") or "")[:80]
            risk = str(imp.get("risk_level", "?"))
            refs = ", ".join(str(r) for r in (imp.get("doc07b_refs") or []))
            parts.append(f"| {imp_id} | {desc} | {subs} | {regs} | {arch} | {risk} | {refs} |\n")
    else:
        parts.append("\n*No strategic implications produced.*\n")

    status = str(synth.get("status", "?"))
    confidence = str(synth.get("confidence", "?"))
    parts.append(
        f"\n*Source: P1C-LLM-03 REDUCE-LLM | status: {status} | confidence: {confidence}*\n"
    )
    return parts


def _gate_rows(
    state: dict[str, Any],
    ontology: Mapping[str, Any],
) -> list[tuple[str, str, str, str]]:
    ctx = state.get("company_context")
    has_ctx = ctx is not None
    has_subdomains = bool(ontology.get("subdomains"))
    clauses = ontology.get("clause_mappings", [])
    has_clauses = isinstance(clauses, list) and len(clauses) > 0
    coverage_summary = ontology.get("coverage_summary", {}) if isinstance(ontology, Mapping) else {}
    total = int((coverage_summary or {}).get("total_subdomains", 0) or 0)
    has_coverage = total > 0
    agg = state.get("aggregated_data")
    has_proportionality = isinstance(agg, Mapping) and bool(agg.get("profile"))
    assessments = ontology.get("applicability_assessments", []) if isinstance(ontology, Mapping) else []
    has_assessments = bool(assessments)

    def _status(flag: bool) -> str:
        return "PASS" if flag else "FAIL"

    sub_count = (
        len((ontology.get("subdomains") or {}).get("covered", []))
        if isinstance(ontology.get("subdomains"), Mapping)
        else 0
    )
    clause_count = len(clauses) if isinstance(clauses, list) else 0

    return [
        ("1", "Company context loaded (04)", _status(has_ctx), f"company_name = {getattr(ctx, 'company_name', '-') if ctx else '-'}"),
        ("2", "Sub-domain catalogue present", _status(has_subdomains), f"{sub_count} active sub-domains"),
        ("3", "Clause mappings rendered", _status(has_clauses), f"{clause_count} clauses in 06"),
        ("4", "Coverage matrix computed", _status(has_coverage), f"{total} sub-domains in ontology"),
        ("5", "Proportionality computed (07b)", _status(bool(has_proportionality)), "see AEGIS-P1-07b"),
        ("6", "Applicability assessments recorded (05)", _status(has_assessments), f"{len(assessments) if isinstance(assessments, list) else 0} assessments"),
        (
            "7",
            "Compound events computed (LLM-02)",
            _status(bool(state.get("aggregated_data", {}).get("compound_events"))),
            "REDUCE-LLM: P1C-LLM-02 run; see §5.2",
        ),
        (
            "8",
            "Strategic synthesis computed (LLM-03)",
            _status(bool(state.get("aggregated_data", {}).get("synthesis"))),
            "REDUCE-LLM: P1C-LLM-03 run; see §6.2",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _abbr(reg: Mapping[str, Any]) -> str:
    raw = reg.get("abbreviation") or reg.get("id") or "?"
    text = str(raw)
    if "/" in text:
        return text.split("/")[-1].upper()
    return text.upper()


def _should_use_llm(llm_invoker: Any | None) -> bool:
    if llm_invoker is None:
        return False
    return os.environ.get("MOCK_LLM", "").strip().lower() not in _MOCK_TRUTHS


# ─────────────────────────────────────────────────────────────────────
# Frontmatter
# ─────────────────────────────────────────────────────────────────────


def _build_frontmatter(state: dict[str, Any], regs: list[Any]) -> str:
    ctx = state.get("company_context")
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    applicable = sorted(_abbr(r) for r in regs if isinstance(r, Mapping) and r.get("applicable"))
    payload: dict[str, Any] = {
        "document_id": "AEGIS-P1-07",
        "title": "Structured Compliance Matrix",
        "phase": 1,
        "version": 1.0,
        "created": now,
        "updated": now,
        "author": "Executor",
        "status": "DRAFT",
        "case_study": getattr(ctx, "company_name", "UNKNOWN") if ctx else "UNKNOWN",
        "inputs": [
            "04_Company_Context_Assessment.md",
            "05_Regulatory_Applicability.md",
            "06_Clause_Mapping_Matrix.xlsx",
            "07b_Proportionality_Profile.md",
        ],
        "outputs": [
            "08_Obligation_Derivation.md",
            "11_Rules_Catalog.md",
            "14_Architectural_Nodes.md",
            "15_Allocation.md",
        ],
        "applicable_regs": applicable,
        "traceability": "AEGIS Class Model → ComplianceContext, DomainCoverageEntry",
        "related_documents": [
            "00_Taxonomy_Reference.md",
            "../../../00_METHODOLOGY/PHASE1_STRATEGY.md",
        ],
        "generated_at": now,
    }
    lines = ["---"]
    for key, value in payload.items():
        lines.append(f"{_safe_key(key)}: {_safe_value(value)}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


import re as _re

_SAFE_KEY = _re.compile(r"[^A-Za-z0-9_.-]")


def _safe_key(key: str) -> str:
    return _SAFE_KEY.sub("_", key) or "field"


def _safe_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        return "[" + ", ".join(_safe_value(v) for v in value) + "]"
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", '"', "'", "[", "]", "{", "}"]) or text[0] in {"-", "?"}:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


__all__ = ["render_doc_07"]
