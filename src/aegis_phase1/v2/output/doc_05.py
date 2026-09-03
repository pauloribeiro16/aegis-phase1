"""doc_05 — render 05_Regulatory_Applicability.md.

Per-regulation applicability assessment. Each section is produced
deterministically from the case ontology (``state.ontology.regulations``,
``state.ontology.applicability_assessments``) and the architecture
inventory. Narrative prose is composed programmatically from the
project data; no external methodology text is reproduced.

Sections produced:

1.  Purpose
2.  Applicable summary
3.  Per-regulation applicability (3.1 .. 3.5) — criteria / evidence /
    reasoning populated from the ontology assessments.
4.  Native vs inherited compliance — ``cloud_services`` from the
    architecture inventory plus ``applicability_assessments`` determine
    NATIVE / INHERITED labels per domain.
5.  Sub-domain coverage preliminary — derived from the 38-subdomain
    taxonomy and the applicable regulation set.
6.  Strategic implications — narrative produced by an optional
    ``llm_invoker``; deterministic fallback text is always emitted when
    the invoker is absent, fails, or ``MOCK_LLM`` is truthy.
7.  Regulatory gaps identified — union of ``tensions`` and the
    ``not_covered`` sub-domains.
8.  Input to Phase 2 — handover list.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from aegis_phase1.data.loader import get_regulation_summary
from aegis_phase1.v2.context.applicability_context import (
    ApplicabilityContext,
    build_applicability_context,
)
from aegis_phase1.v2.output._common import (
    doc_preamble,
    get_per_spec_markdown,
    markdown_table,
    render_per_spec_markdown_appendix,
    section_provenance_tag,
    write_output,
)
from aegis_phase1.v2.output._narrative import render_mandatory_narrative

# CORR-061 S3b: spec IDs that this doc consumes from
# ``state["per_spec_markdown"]``. Kept local to the doc so the
# spec-to-doc mapping is grep-friendly (see the S3b report for the
# full mapping table).
_SPEC_STRATEGIC = "P1C-LLM-03-STRATEGIC-SYNTHESIS"
_SPEC_RATIONALE = "P1B-LLM-02-RATIONALE"

logger = logging.getLogger(__name__)

_FILENAME = "05_Regulatory_Applicability.md"
_MAX_FRAGMENT_BYTES = 4000
_MOCK_TRUTHS = {"1", "true", "yes", "on"}


def _regulatory_summary(regulation: str) -> str:
    """Return the Phase 1 scope summary for a regulation from data/regulatory/."""
    try:
        return get_regulation_summary(regulation)
    except FileNotFoundError:
        return ""


def render_doc_05(
    state: dict[str, Any],
    output_dir: str,
    llm_invoker: Any | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render document 05 (per-regulation applicability).

    Args:
        state: Pipeline state (see :class:`aegis_phase1.v2.state.V2State`).
        output_dir: Directory in which the document is written.
        llm_invoker: Optional LLM invoker (``invoke(prompt) -> dict``).
            When ``None`` or when ``MOCK_LLM`` is truthy, deterministic
            fallback text is used for the §6 narrative.
        config: Optional Langfuse / LangChain runnable config threaded
            through to nested LLM calls so the GENERATION span is named
            after the LangGraph node.

    Returns:
        Mapping ``AEGIS-P1-05`` -> absolute file path.
    """
    ontology = state.get("ontology") or {}
    regs = state.get("regulations") or ontology.get("regulations", [])
    assessments = (
        ontology.get("applicability_assessments", []) if isinstance(ontology, Mapping) else []
    )
    assessment_by_reg = _index_assessments(assessments)
    subdomains = ontology.get("subdomains", {}) if isinstance(ontology, Mapping) else {}
    cloud_services = _cloud_services(state)
    inventory = state.get("architecture_inventory") or {}
    inventory_systems = list(inventory.get("systems") or []) if isinstance(inventory, Mapping) else []

    use_llm = _should_use_llm(llm_invoker)
    invoker = llm_invoker if use_llm else None

    parts: list[str] = []
    parts.append(doc_preamble(state))
    parts.append("# AEGIS-P1-05 Regulatory Applicability\n")

    # CORR-038-T3: ApplicabilityContext (v2 source of truth) — added as
    # a new §0 "Applicability Summary" before the existing §1 PURPOSE.
    # The remaining sections (§3-§8) still consume the v1 ontology for
    # detailed per-regulation assessments; §0 is the deterministic
    # summary derived from the v2 case profile.
    app_ctx: ApplicabilityContext = build_applicability_context(state)
    parts.extend(_section_0_applicability_summary(app_ctx))

    parts.extend(_section_1_purpose())
    parts.extend(_section_2_summary(regs, app_ctx=app_ctx))
    parts.extend(
        _section_3_per_regulation(regs, assessment_by_reg, ontology)
    )
    parts.extend(
        _section_4_native_vs_inherited(regs, cloud_services, inventory_systems)
    )
    parts.extend(
        _section_5_subdomain_coverage_preliminary(subdomains, regs)
    )
    parts.extend(_section_6_strategic_implications(state, regs, invoker, config=config))
    parts.append(_render_rationale_by_reg_section(state))
    parts.extend(
        _section_7_regulatory_gaps(ontology, subdomains)
    )
    parts.extend(_section_8_input_to_phase_2(state))

    # CORR-061 S3b: dump every captured per-spec markdown at the end
    # of the doc so reviewers can see the raw LLM output without
    # grepping the orchestrator state file. See
    # :func:`render_per_spec_markdown_appendix`.
    parts.extend(render_per_spec_markdown_appendix(state))

    body = "\n".join(parts)
    frontmatter = _build_frontmatter(state, regs)
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_05: wrote %s", path)
    return {"AEGIS-P1-05": path}


# ─────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────


def _section_1_purpose() -> list[str]:
    parts: list[str] = []
    parts.append("## 1. PURPOSE\n")
    parts.append(
        "Determine, per regulation, whether the company falls in scope "
        "of the EU regulations tracked by AEGIS — GDPR, CRA, NIS 2, "
        "DORA, and AI Act — and record the criteria, evidence, and "
        "reasoning that justify each determination. The output of this "
        "document is the canonical input for clause mapping (06) and "
        "for the coverage matrix (07).\n"
    )
    parts.append(
        "Three observable deliverables are produced downstream of this "
        "document:\n"
    )
    parts.append(
        "- a populated applicability table that names, for each "
        "regulation, the threshold that triggers applicability, the "
        "company's value against that threshold, and the result;\n"
        "- a Native-vs-Inherited split that separates obligations the "
        "company implements directly from obligations satisfied "
        "through suppliers and partners;\n"
        "- a forward handover record (§8) that captures the artefacts "
        "passed to Phase 2.\n"
    )
    return parts


def _section_0_applicability_summary(app_ctx: ApplicabilityContext) -> list[str]:
    """CORR-038-T3 NEW: deterministic applicability summary from v2.

    Produces a §0 with:
      - 5-row per-regulation table (GDPR/CRA/NIS2/DORA/AI_Act)
        with APPLICABLE / NOT APPLICABLE, obligated party, rationale
      - Declaration gaps table (PHASE1_STRATEGY §6: flag, never override)
      - Tier badge (LOW / MEDIUM / HIGH)
    """
    parts: list[str] = []
    parts.append("## 0. APPLICABILITY SUMMARY (CORR-038 — v2 source of truth)\n")
    parts.append(
        "The following table is the deterministic, v2-driven summary of "
        "regulatory applicability for this case. The data comes from the "
        ":class:`ApplicabilityContext` built by the v2 pipeline "
        "(:mod:`aegis_phase1.v2.context.applicability_context`).\n"
    )
    rows: list[tuple[str, str, str, str]] = []
    applicable_set = set(app_ctx.applicable_regs)
    declared_set = set(app_ctx.declared_applicable_regs)
    gap_regs = {g["regulation"] for g in app_ctx.declaration_gaps}
    for reg in ("GDPR", "CRA", "NIS2", "DORA", "AI_Act"):
        if reg in applicable_set:
            status = "✅ APPLICABLE"
        else:
            status = "❌ NOT APPLICABLE"
        if reg in gap_regs:
            status += "  ⚠ GAP"
        obligated = app_ctx.obligated_party_per_reg.get(reg, "") or "—"
        rationale = app_ctx.rationale_per_reg.get(reg, "—")
        rows.append((reg, status, obligated, rationale))
    parts.append(
        markdown_table(
            ["Regulation", "Status", "Obligated Party", "Rationale"],
            rows,
        )
    )
    parts.append("")
    # Tier badge
    parts.append(
        f"**Compliance Posture Tier:** `{app_ctx.tier}` "
        + (
            "(light-touch; MICRO/SMALL with 1-2 applicable regs)"
            if app_ctx.tier == "LOW"
            else "(elevated; ≥2 regs, or larger scale)"
        )
        + "\n"
    )
    parts.append("")
    # Declaration gaps
    if app_ctx.declaration_gaps:
        parts.append("**⚠ DECLARATION GAPS (review required by Compliance Lead):**")
        parts.append(
            markdown_table(
                ["Regulation", "Direction", "Computed", "Declared"],
                [
                    (
                        g["regulation"],
                        g["direction"],
                        "yes" if g["computed"] else "no",
                        "yes" if g["declared"] else "no",
                    )
                    for g in app_ctx.declaration_gaps
                ],
            )
        )
        parts.append("")
    else:
        parts.append("**Declaration gaps:** none — computed and declared are aligned.\n")
    parts.append("---\n")
    return parts


def _section_2_summary(
    regs: list[Any], app_ctx: ApplicabilityContext | None = None
) -> list[str]:
    """CORR-073: §2 APPLICABLE SUMMARY sources from app_ctx (CORR-038 truth).

    Pre-CORR-073 this section read ``state["regulations"]`` (legacy v1 list)
    which is empty in v2 — producing "(0) applicable regulations" output
    despite 5 regs being listed in the frontmatter. The fix: prefer
    ``app_ctx.applicable_regs`` + ``app_ctx.clause_count_per_reg`` when
    available; fall back to legacy ``regs`` (with ``clause_count``) so
    callers that don't pass ``app_ctx`` continue to work.

    ``regs`` is kept in the signature for backwards compatibility with
    tests + downstream consumers that pass the legacy list.
    """
    parts: list[str] = []
    parts.append("## 2. APPLICABLE SUMMARY\n")
    if app_ctx is not None and (app_ctx.applicable_regs or app_ctx.declared_applicable_regs):
        # CORR-073: source from canonical ApplicabilityContext.
        applicable = list(app_ctx.applicable_regs)
        declared = list(app_ctx.declared_applicable_regs)
        applicable_set = set(applicable)
        non_applicable = sorted(set(declared) - applicable_set)
        total_clauses = sum(int(c or 0) for c in app_ctx.clause_count_per_reg.values())
        parts.append(
            f"- **Applicable regulations ({len(applicable)}):** "
            + (", ".join(applicable) if applicable else "-")
        )
        parts.append(
            f"- **Non-applicable regulations ({len(non_applicable)}):** "
            + (", ".join(non_applicable) if non_applicable else "-")
        )
        parts.append(f"- **Total applicable clauses across the case:** {total_clauses}")
    else:
        # Legacy path — preserve behaviour for any caller that hasn't
        # passed app_ctx (e.g. legacy unit tests).
        applicable = [r for r in regs if isinstance(r, Mapping) and r.get("applicable")]
        not_applicable = [r for r in regs if isinstance(r, Mapping) and not r.get("applicable")]
        parts.append(
            f"- **Applicable regulations ({len(applicable)}):** "
            + (", ".join(_abbr(r) for r in applicable) if applicable else "-")
        )
        parts.append(
            f"- **Non-applicable regulations ({len(not_applicable)}):** "
            + (", ".join(_abbr(r) for r in not_applicable) if not_applicable else "-")
        )
        total_clauses = sum(
            int(r.get("clause_count", 0) or 0)
            for r in regs
            if isinstance(r, Mapping)
        )
        parts.append(f"- **Total applicable clauses across the case:** {total_clauses}")
    parts.append("")
    return parts


def _section_3_per_regulation(
    regs: list[Any],
    assessment_by_reg: dict[str, Mapping[str, Any]],
    ontology: Mapping[str, Any],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 3. PER-REGULATION APPLICABILITY\n")
    _tag = section_provenance_tag(
        "AEGIS-P1-05", "## 3. PER-REGULATION APPLICABILITY\n"
    )
    if _tag:
        parts.append(f"{_tag}\n")
    parts.append(
        "Each sub-section below follows a fixed shape: thresholds and "
        "criteria on the left, the company value on the right, and a "
        "result column. The evidence block lists the ontology fields "
        "that ground the determination; the reasoning block carries "
        "the natural-language rationale.\n"
    )
    for reg in regs:
        if not isinstance(reg, Mapping):
            continue
        reg_id = str(reg.get("id", ""))
        abbrev = _abbr(reg)
        assmt = assessment_by_reg.get(reg_id)
        applicable_flag = bool(reg.get("applicable"))
        parts.append(
            f"### 3.{_reg_index(regs, reg)} {abbrev} "
            f"({reg.get('name', '-')})\n"
        )
        parts.extend(_regulation_top_block(reg, applicable_flag, assmt))
        parts.append("")
        parts.append("#### CRITERIA\n")
        parts.append(
            markdown_table(["Criterion", "Value", "Threshold", "Result"], _criteria_rows(abbrev, applicable_flag, assmt))
        )
        parts.append("")
        parts.extend(_regulation_evidence_and_reasoning(reg, assmt))
        parts.append("---\n")
    return parts


def _regulation_top_block(
    reg: Mapping[str, Any],
    applicable_flag: bool,
    assmt: Mapping[str, Any] | None,
) -> list[str]:
    """Build the four-field summary block above the criteria table."""
    obligated = reg.get("obligated_party", "-")
    if isinstance(obligated, list):
        obligated = ", ".join(str(o) for o in obligated)
    lines = [
        f"- **Applicable:** {'YES' if applicable_flag else 'NO'}",
        f"- **EU reference:** {reg.get('eu_reference', '-')}",
        f"- **Obligated party:** {obligated}",
        f"- **Clause count (declared):** {reg.get('clause_count', 0)}",
    ]
    if assmt and isinstance(assmt, Mapping):
        lines.append(f"- **Confidence:** {assmt.get('confidence', '-')}")
        lines.append(
            f"- **Reason category:** "
            f"{assmt.get('reason', assmt.get('reasoning', '-'))}"
        )
    else:
        lines.append(f"- **Reason (from ontology):** {reg.get('reason', '-')}")
    return lines


def _regulation_evidence_and_reasoning(
    reg: Mapping[str, Any],
    assmt: Mapping[str, Any] | None,
) -> list[str]:
    parts: list[str] = []
    if assmt and isinstance(assmt, Mapping):
        evidence = assmt.get("evidence", []) or []
        if evidence:
            parts.append("#### EVIDENCE\n")
            for ev in evidence:
                parts.append(f"- {ev}")
            parts.append("")
        reasoning = assmt.get("reasoning")
        if reasoning:
            parts.append("#### REASONING\n")
            parts.append(str(reasoning) + "\n")
    elif reg.get("non_applicability_evidence"):
        parts.append("#### NON-APPLICABILITY EVIDENCE\n")
        for ev in reg.get("non_applicability_evidence", []):
            parts.append(f"- {ev}")
        parts.append("")
        reason = reg.get("reason")
        if reason:
            parts.append("#### EXCLUSION RATIONALE\n")
            parts.append(str(reason) + "\n")
    return parts


def _section_4_native_vs_inherited(
    regs: list[Any],
    cloud_services: list[dict],
    inventory_systems: list[Any],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 4. NATIVE VS INHERITED COMPLIANCE\n")
    parts.append(
        "The applicability table is augmented with a NATIVE / INHERITED "
        "annotation per regulation–domain pair. NATIVE means the "
        "company implements the control itself; INHERITED means the "
        "control is satisfied through a contractual relationship with a "
        "cloud or service provider that carries its own attestation "
        # NOTE (CORR-028, NIST_CSF_2.0_ONLY.md §2): "ISO 27001 / SOC 2"
        # below is a vendor attestation pattern, NOT a control framework.
        "(for example, an ISO 27001 or SOC 2 Type II report).\n"
    )
    rows = _native_inherited_rows(regs, cloud_services, inventory_systems)
    if not rows:
        parts.append(
            "_No architecture inventory available; this section is "
            "inheriting-agnostic._\n"
        )
    else:
        parts.append(
            markdown_table(
                ["Regulation", "Domain / Sub-domain", "Layer", "Justification"],
                rows,
            )
        )
    parts.append("")
    if cloud_services:
        parts.append("### 4.1 Provider Attestations\n")
        parts.append(
            markdown_table(
                ["Provider", "Service", "Region", "Attestation"],
                [(c.get("provider", "-"), c.get("service", "-"), c.get("region", "-"), "see DPA") for c in cloud_services],
            )
        )
        parts.append("")
    parts.append(
        "Compliance evidence for INHERITED rows must be filed in the "
        "working directory (typically under ``02_CASES/.../04_EVIDENCE/``) "
        "before Phase 2 begins.\n"
    )
    return parts


def _section_5_subdomain_coverage_preliminary(
    subdomains: Mapping[str, Any],
    regs: list[Any],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 5. SUB-DOMAIN COVERAGE PRELIMINARY\n")
    parts.append(
        "Coverage status per sub-domain is computed from the layer-0 "
        "ontology and the applicable regulation set. A sub-domain is "
        "**SUBSTANTIVE** when ≥ 2 applicable regulations cover it, "
        "**PARTIAL** when exactly one applies, and **NOT_ADDRESSED** "
        "when no applicable regulation intersects the company context.\n"
    )
    rows = _coverage_rows(subdomains, regs)
    if not rows:
        parts.append("_No sub-domain catalogue available._\n")
    else:
        parts.append(
            markdown_table(
                [
                    "Sub-domain",
                    "Name",
                    "Source Regs",
                    "Total",
                    "Status",
                ],
                rows,
            )
        )
    parts.append("")
    counts = _status_counts(rows)
    parts.append("### 5.1 Status Counts\n")
    parts.append(
        markdown_table(
            ["Status", "Count", "Percentage"],
            [
                (name, str(counts.get(name, 0)), f"{(counts.get(name, 0) * 100.0) / max(len(rows), 1):.1f}%")
                for name in ("SUBSTANTIVE", "PARTIAL", "NOT_ADDRESSED")
            ],
        )
    )
    parts.append("")
    return parts


def _section_6_strategic_implications(
    state: dict[str, Any],
    regs: list[Any],
    llm_invoker: Any | None,
    *,
    config: dict[str, Any] | None = None,
) -> list[str]:
    """§6 STRATEGIC IMPLICATIONS — CORR-061 S3b: now consumes P1C-LLM-03 markdown.

    S3a (and prior): the §6.1 Narrative was rendered via
    :func:`render_mandatory_narrative` (the legacy narrative invoker
    path) which has no direct spec mapping. S3b replaces this with a
    read from ``state["per_spec_markdown"]["P1C-LLM-03-STRATEGIC-SYNTHESIS"]``
    so the strategic narrative is sourced from the canonical 5-LLM
    pipeline. The deterministic implication table (§6) is unchanged
    (it is a heuristic over applicable_regs, not LLM-derived).

    When P1C-LLM-03 has not run (deterministic-only / mock / executor
    failure), a PENDING REVIEW marker is emitted so reviewers can
    identify the gap at a glance. The ``llm_invoker`` parameter is
    retained for backward compatibility with existing tests but is
    unused on the S3b happy path (P1C-LLM-03 is invoked by the
    executor, not by the renderer).
    """
    parts: list[str] = []
    parts.append("## 6. STRATEGIC IMPLICATIONS\n")
    _tag_6 = section_provenance_tag(
        "AEGIS-P1-05", "## 6. STRATEGIC IMPLICATIONS\n"
    )
    if _tag_6:
        parts.append(f"{_tag_6}\n")
    parts.append(
        "The applicability profile is condensed into a small set of "
        "implications that feed Phase 2 obligation derivation. Each "
        "implication names the trigger regulations, the affected "
        "architecture areas, and the priority with which Phase 2 must "
        "absorb the implication into obligation rows.\n"
    )
    rows = _strategic_rows(state, regs)
    parts.append(
        markdown_table(
            [
                "Implication ID",
                "Source Regulation(s)",
                "Description",
                "Architecture Impact",
                "Priority",
            ],
            rows,
        )
    )
    parts.append("")
    parts.append("### 6.1 Narrative\n")
    # CORR-061 S3b: consume P1C-LLM-03 raw markdown from
    # ``state["per_spec_markdown"]`` (wiring lives in
    # :meth:`Phase1LLMInvoker._capture_per_spec_markdown`).
    spec_md = get_per_spec_markdown(state, _SPEC_STRATEGIC)
    if spec_md:
        parts.append(spec_md.rstrip() + "\n")
    else:
        # Fallback to the legacy narrative invoker when the spec has
        # not been captured yet. The narrative invoker itself returns
        # a PENDING REVIEW marker when the LLM is unavailable, so the
        # net behaviour for a missing P1C-LLM-03 response is a
        # greppable PENDING block.
        narrative = render_mandatory_narrative(
            invoker=llm_invoker,
            prompt=_strategic_prompt(state, rows),
            section_id="doc_05.section_6.strategic_narrative",
            max_chars=_MAX_FRAGMENT_BYTES,
            config=config,
        )
        parts.append(narrative.rstrip() + "\n")
    return parts


def _render_rationale_by_reg_section(state: dict[str, Any]) -> str:
    """Render §6.1b 'Per-Regulation Rationale (LLM-02 RATIONALE)'.

    CORR-061 S3b: now reads from
    ``state["per_spec_markdown"]["P1B-LLM-02-RATIONALE"]`` instead of
    ``state["aggregated_data"]["rationale_by_reg"]``. The legacy
    typed-state read is preserved as a fallback so deterministic-only
    runs (where the executor is unavailable but the orchestrator
    previously populated the typed state) still render sensibly.

    Pre-S3b behaviour: parsed the structured
    ``{reg_code: synthesis_dict}`` payload, iterated per regulation,
    and rendered rationale + implications + gaps as labelled sections.

    S3b behaviour: dump the raw markdown response of P1B-LLM-02 (one
    call per applicable regulation, concatenated with ``---``) under
    the same §6.1b header. The structured-fields parsing path is
    removed because the markdown-only contract is the source of
    truth.
    """
    spec_md = get_per_spec_markdown(state, _SPEC_RATIONALE)
    if spec_md:
        parts: list[str] = []
        parts.append("\n### 6.1b Per-Regulation Rationale (LLM-02 RATIONALE)\n")
        parts.append(
            "Per-regulation rationale + implications + gaps. Generated by "
            "P1B-LLM-02 RATIONALE. Cross-references Doc 04 facts + "
            "Regulatory Baseline articles. NO boilerplate "
            "(per-validation invariant).\n"
        )
        parts.append(
            "*Source: P1B-LLM-02 RATIONALE | "
            "multi-call concat (one section per applicable regulation, "
            "separated by `---`)*\n\n"
        )
        parts.append(spec_md.rstrip() + "\n")
        return "".join(parts)

    # Fallback: legacy typed-state path. Kept for the case where the
    # executor populated ``state["aggregated_data"]["rationale_by_reg"]``
    # but the S3b wiring (P1B-LLM-02 → per_spec_markdown) did not
    # capture the raw response (e.g. older executor versions, mock
    # test paths).
    agg = state.get("aggregated_data")
    rationale_data = (
        agg.get("rationale_by_reg") if isinstance(agg, Mapping) else None
    )

    if not rationale_data or not isinstance(rationale_data, dict):
        return (
            "\n### 6.1b Per-Regulation Rationale (LLM-02 RATIONALE)\n\n"
            "> **[PENDING REVIEW — Phase 1B RATIONALE not yet computed]**\n"
            "> Section ID: `doc_05.section_6_1_b.per_regulation_rationale`\n"
            "> \n"
            "> This section requires P1B-LLM-02 (per-regulation rationale "
            "synthesis). Re-run the pipeline with a real LLM configured "
            "(`MOCK_LLM=false` and Ollama running) to populate this section.\n"
        )

    parts = []
    parts.append("\n### 6.1b Per-Regulation Rationale (LLM-02 RATIONALE) [legacy typed-state fallback]\n")
    parts.append(
        "Per-regulation rationale + implications + gaps. Generated by "
        "P1B-LLM-02 RATIONALE. Cross-references Doc 04 facts + "
        "Regulatory Baseline articles. NO boilerplate "
        "(per-validation invariant).\n"
    )

    for reg_code in sorted(rationale_data):
        reg_data = rationale_data[reg_code]
        if not isinstance(reg_data, dict):
            continue
        synthesis = (
            reg_data.get("synthesis")
            if isinstance(reg_data.get("synthesis"), dict)
            else {}
        )
        status = (
            reg_data.get("status")
            or synthesis.get("status")
            or "OK"
        )
        confidence = (
            reg_data.get("confidence")
            or synthesis.get("confidence")
            or "-"
        )

        parts.append(f"\n#### {reg_code}\n")
        parts.append(
            f"*Source: P1B-LLM-02 RATIONALE | status: {status} | "
            f"confidence: {confidence}*\n\n"
        )

        rationale_text = ""
        if isinstance(synthesis.get("rationale"), str):
            rationale_text = synthesis["rationale"].strip()
        elif isinstance(reg_data.get("rationale"), str):
            rationale_text = reg_data["rationale"].strip()
        if rationale_text:
            parts.append(f"{rationale_text}\n")
        else:
            parts.append("*No rationale produced.*\n")

        implications = (
            synthesis.get("implications") or reg_data.get("implications") or []
        )
        if isinstance(implications, list) and implications:
            parts.append("\n**Implications**:\n")
            for imp in implications:
                if not isinstance(imp, dict):
                    continue
                imp_id = imp.get("id", "?")
                desc = (imp.get("description") or "").strip()
                effort = imp.get("effort_estimate", "?")
                parts.append(f"- `{imp_id}` ({effort}): {desc}\n")

        gaps = synthesis.get("gaps") or reg_data.get("gaps") or []
        if isinstance(gaps, list) and gaps:
            parts.append("\n**Gaps**:\n")
            for gap in gaps:
                if not isinstance(gap, dict):
                    continue
                gap_id = gap.get("gap_id", "?")
                sub = gap.get("sub_domain_id", "?")
                risk = gap.get("risk_description", "")
                prio = gap.get("priority", "?")
                parts.append(f"- `{gap_id}` [{prio}] {sub}: {risk}\n")

    return "".join(parts)


def _section_7_regulatory_gaps(
    ontology: Mapping[str, Any],
    subdomains: Mapping[str, Any],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 7. REGULATORY GAPS IDENTIFIED\n")
    _tag = section_provenance_tag(
        "AEGIS-P1-05", "## 7. REGULATORY GAPS IDENTIFIED\n"
    )
    if _tag:
        parts.append(f"{_tag}\n")
    parts.append(
        "Gaps surfaced by the ontology tensions catalogue and by "
        "sub-domains whose sole authority is a regulation that does not "
        "apply to this company. The Type column distinguishes "
        "TENSION_DERIVED (tension between applicable regulations), "
        "SOLE_AUTHORITY (sub-domain in ``not_covered``), and "
        "DETERMINISTIC (annotated at the language-model layer).\n"
    )
    rows = _gap_rows(ontology, subdomains)
    if not rows:
        parts.append("_No gaps detected._\n")
    else:
        parts.append(
            markdown_table(
                ["Gap ID", "Type", "Sub-domain / Clause", "Severity", "Description"],
                rows,
            )
        )
    parts.append("")
    return parts


def _section_8_input_to_phase_2(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 8. INPUT TO PHASE 2\n")
    parts.append(
        "The following artefacts leave this document and travel to "
        "Phase 2 (obligation derivation, rules catalogue, allocation). "
        "Any change to this list requires a corresponding edit in the "
        "Phase-2 ingest contract.\n"
    )
    parts.append(
        markdown_table(
            ["Artefact", "Source Section", "Phase-2 Consumer"],
            [
                ("Applicable regulation set (YES/NO flags)", "§2", "Filter in 08_Obligation_Derivation.md"),
                ("Per-regulation criteria + evidence + reasoning", "§3", "Audit trail for compliance clauses"),
                ("Native / Inherited annotations", "§4", "Ownership annotation in 11_Rules_Catalog.md"),
                ("Sub-domain coverage preliminary", "§5", "Input for 07_Structured_Compliance_Matrix.md §3"),
                ("Strategic implications", "§6", "Trigger for strategic tension detection in Phase 2"),
                ("Regulatory gaps", "§7", "Priority input for rules catalog seed row"),
                ("Handover envelope (this section)", "§8", "Phase-2 ingest contract"),
            ],
        )
    )
    parts.append("")
    parts.append(
        "Sign-off: this document closes Phase 1 sub-task B (Regulatory "
        "Applicability). Phase 1 sub-task C (Structured Compliance "
        "Matrix) starts after this file is reviewed.\n"
    )
    return parts


# ─────────────────────────────────────────────────────────────────────
# Deterministic helpers for tables
# ─────────────────────────────────────────────────────────────────────


def _native_inherited_rows(
    regs: list[Any],
    cloud_services: list[dict],
    inventory_systems: list[Any],
) -> list[tuple[str, str, str, str]]:
    """Return the NATIVE / INHERITED split per regulation.

    The split is a heuristic based on whether the architecture inventory
    names a provider for the relevant control area. Real per-clause
    allocation lives in Doc 02 and Doc 06.
    """
    rows: list[tuple[str, str, str, str]] = []
    providers = sorted({c.get("provider", "") for c in cloud_services if c.get("provider")})
    provider_label = ", ".join(providers) if providers else "(no inventory)"
    applicable = [r for r in regs if isinstance(r, Mapping) and r.get("applicable")]
    if not applicable:
        return rows
    domain_map = {
        "GDPR": [
            ("D-01", "encryption in transit / at rest", "INHERITED", f"provider-controlled primitives ({provider_label})"),
            ("D-04", "incident detection", "NATIVE", "company-defined playbook"),
            ("D-05", "data lifecycle", "NATIVE", "company-owned schema constraints and APIs"),
            ("D-06", "vendor risk", "NATIVE", "DPA validation owned by Compliance Lead"),
            ("D-08", "awareness", "NATIVE", "company-run training cadence"),
            ("D-09", "governance", "NATIVE", "policy ownership internal to Compliance Lead"),
        ],
        "CRA": [
            ("D-01", "default configuration", "NATIVE", "secure defaults implemented in code"),
            ("D-02", "vulnerability handling", "NATIVE", "SBOM + scanner run by engineering"),
            ("D-07", "secure development", "NATIVE", "SDLC owned by Lead Developer"),
        ],
    }
    for reg in applicable:
        rows_for_reg = domain_map.get(_abbr(reg), [])
        if not rows_for_reg:
            rows_for_reg = [(f"D-XX (catch-all for {_abbr(reg)})", "all applicable clauses", "NATIVE", "no inheritance evidence found")]
        for sd_id, label, layer, just in rows_for_reg:
            rows.append((_abbr(reg), f"{sd_id} — {label}", layer, just))
    return rows


def _coverage_rows(
    subdomains: Mapping[str, Any],
    regs: list[Any],
) -> list[tuple[str, str, str, str, str]]:
    """Return one row per sub-domain with coverage status."""
    rows: list[tuple[str, str, str, str, str]] = []
    applicable = {str(r.get("abbreviation") or r.get("id") or "") for r in regs if isinstance(r, Mapping) and r.get("applicable")}
    if not subdomains:
        return rows
    for entry in subdomains.get("covered", []) or []:
        if not isinstance(entry, Mapping):
            continue
        sd_id = str(entry.get("id", "-"))
        name = str(entry.get("name", "-"))
        source = [s for s in (entry.get("source_regulations") or []) if s]
        intersect = [s for s in source if s in applicable]
        total = len(intersect)
        if total >= 2:
            status = "SUBSTANTIVE"
        elif total == 1:
            status = "PARTIAL"
        else:
            status = "NOT_ADDRESSED"
        rows.append((sd_id, name, ", ".join(source) or "-", str(total), status))
    for entry in subdomains.get("not_covered", []) or []:
        if not isinstance(entry, Mapping):
            continue
        rows.append(
            (
                str(entry.get("id", "-")),
                str(entry.get("name", "-")),
                str(entry.get("sole_authority_regulation", "-")),
                "0",
                "NOT_ADDRESSED",
            )
        )
    return rows


def _status_counts(rows: list[tuple[str, str, str, str, str]]) -> dict[str, int]:
    counts = {"SUBSTANTIVE": 0, "PARTIAL": 0, "NOT_ADDRESSED": 0}
    for r in rows:
        status = r[4]
        counts[status] = counts.get(status, 0) + 1
    return counts


def _strategic_rows(
    state: dict[str, Any],
    regs: list[Any],
) -> list[tuple[str, str, str, str, str]]:
    """Return the strategic-implications table rows."""
    applicable_abbrs = sorted(
        _abbr(r) for r in regs if isinstance(r, Mapping) and r.get("applicable")
    )
    if not applicable_abbrs:
        return [("SI-000", "—", "no applicable regulations", "—", "LOW")]
    applicable_label = " + ".join(applicable_abbrs)
    rows: list[tuple[str, str, str, str, str]] = []
    rows.append(
        (
            "SI-001",
            applicable_label,
            "Dual-role analysis: GDPR controller + processor obligations co-exist; CRA manufacturer obligations attach independently",
            "Phase 2 must allocate each clause to exactly one role and duplicate rows where the same clause binds both roles",
            "HIGH",
        )
    )
    if "GDPR" in applicable_abbrs:
        rows.append(
            (
                "SI-002",
                "GDPR",
                "Data-subject rights (erasure, portability, restriction) require customer-facing endpoints",
                "Add API endpoints / documented manual workflow in 14_Architectural_Nodes",
                "MEDIUM",
            )
        )
        rows.append(
            (
                "SI-003",
                "GDPR",
                "RoPA + security-of-processing documentation needed (Art. 30, Art. 32)",
                "Generate templates in 03_PHASE3_DECOMPOSITION / templates",
                "MEDIUM",
            )
        )
    if "CRA" in applicable_abbrs:
        rows.append(
            (
                "SI-004",
                "CRA",
                "SBOM, CVD page (security.txt), and patch cadence must be operationalised",
                "Insert CI/CD gates and `.well-known/security.txt` publication step",
                "HIGH",
            )
        )
        rows.append(
            (
                "SI-005",
                "CRA",
                "Coordinated vulnerability disclosure requires named contact + acknowledgement SLA",
                "Document SLA in 11_Rules_Catalog.md D-02.3 row",
                "MEDIUM",
            )
        )
    rows.append(
        (
            "SI-006",
            applicable_label,
            "Time-to-compliance for the case must be estimated against §6.1 narrative before kick-off of Phase 2",
            "Hand off to PM for scope-baseline ratification",
            "MEDIUM",
        )
    )
    return rows


def _gap_rows(
    ontology: Mapping[str, Any],
    subdomains: Mapping[str, Any],
) -> list[tuple[str, str, str, str, str]]:
    """Return the regulatory-gap rows derived from tensions + not_covered."""
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
                str(t.get("description", "-")),
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
                "SOLE_AUTHORITY",
                f"{entry.get('id', '-')} ({entry.get('name', '-')})",
                str(entry.get("gap_severity", "-")),
                str(entry.get("reason", "Sole authority is a non-applicable regulation")),
            )
        )
    return rows


# ─────────────────────────────────────────────────────────────────────
# Narrative prompts / fallbacks
# ─────────────────────────────────────────────────────────────────────


def _strategic_prompt(
    state: dict[str, Any],
    rows: list[tuple[str, str, str, str, str]],
) -> str:
    """LLM prompt for doc_05 §6.1 Strategic Narrative.

    Function vocabulary (ROLE_VOCABULARY): DPO, CISO, Engineering,
    Operations, Governance. Disclaimer: DO NOT name individuals.
    """
    from aegis_phase1.v2.output._functional_prompts import (
        build_functional_context,
        extract_tier_and_regs,
    )
    ctx = state.get("company_context")
    name = getattr(ctx, "company_name", "") if ctx else "the company"
    summary = "; ".join(f"{r[0]} ({r[1]}, {r[4]})" for r in rows)
    tier, regs = extract_tier_and_regs(state)
    fc_ctx = build_functional_context(tier, regs)
    body = (
        f"Compose a 3-5 sentence strategic narrative for the regulatory "
        f"applicability of {name}. Mention dual-role analysis, "
        f"time-to-compliance, and cost of compliance. Anchor the "
        f"narrative on these implications: {summary}"
    )
    return f"{fc_ctx}\n\n{body}" if fc_ctx else body


# ─────────────────────────────────────────────────────────────────────
# Criteria row builder
# ─────────────────────────────────────────────────────────────────────


def _criteria_rows(
    abbrev: str,
    applicable: bool,
    assmt: Mapping[str, Any] | None,
) -> list[tuple[str, str, str, str]]:
    """Per-regulation criteria table with a Threshold column added."""
    upper = abbrev.upper()
    rows: list[tuple[str, str, str, str]] = []

    def _add(criterion: str, value: str, threshold: str, result: str) -> None:
        rows.append((criterion, value, threshold, result))

    if upper.startswith("GDPR"):
        _add("processes_personal_data", "true", "any", "YES" if applicable else "NO")
        _add("eu_data_subjects", "true", "any", "YES" if applicable else "NO")
        _add("controller_role", "true" if applicable else "false", "Art. 4(7)", "met" if applicable else "n/a")
        _add("processor_role", "true" if applicable else "false", "Art. 4(8)", "met" if applicable else "n/a")
    if "CRA" in upper:
        _add("places_digital_products_eu", "true", "Art. 2", "YES" if applicable else "NO")
        _add("manufacturer_status", "true" if applicable else "false", "Art. 3(13)", "met" if applicable else "n/a")
    if "NIS" in upper:
        _add("nis2_sector", "tech (productivity)", "Annex I/II", "below_threshold" if not applicable else "applies")
        _add("size_employees", "≤ 50 (or actual)", "≥ 50 (medium)", "below" if not applicable else "met")
    if "DORA" in upper:
        _add("dora_financial_entity", "false", "Art. 2", "NO" if not applicable else "YES")
        _add("ict_third_party_provider", "false", "Art. 28(8)", "NO" if not applicable else "YES")
    if "AI" in upper:
        _add("aiact_high_risk_system", "false", "Annex III", "NO" if not applicable else "YES")
        _add("ai_system_provider", "false", "Art. 3(1)", "NO" if not applicable else "YES")
    if not rows and assmt:
        _add("evidence-based", "see evidence", "case-specific", "YES" if applicable else "NO")
    if not rows:
        _add("default", "n/a", "n/a", "YES" if applicable else "NO")
    return rows


# ─────────────────────────────────────────────────────────────────────
# General helpers
# ─────────────────────────────────────────────────────────────────────


def _abbr(reg: Mapping[str, Any]) -> str:
    return str(reg.get("abbreviation") or reg.get("id") or "?").upper()


def _reg_index(regs: list[Any], reg: Mapping[str, Any]) -> str:
    for i, r in enumerate(regs, 1):
        if isinstance(r, Mapping) and r.get("id") == reg.get("id"):
            return str(i)
    return "?"


def _index_assessments(assessments: list[Any]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for item in assessments or []:
        if isinstance(item, Mapping):
            rid = item.get("regulation_id")
            if rid:
                out[rid] = item
    return out


def _cloud_services(state: dict[str, Any]) -> list[dict]:
    inventory = state.get("architecture_inventory") or {}
    if not isinstance(inventory, Mapping):
        return []
    cs = list(inventory.get("cloud_services") or [])
    return [c for c in cs if isinstance(c, Mapping)]


def _should_use_llm(llm_invoker: Any | None) -> bool:
    if llm_invoker is None:
        return False
    return os.environ.get("MOCK_LLM", "").strip().lower() not in _MOCK_TRUTHS


# ─────────────────────────────────────────────────────────────────────
# Frontmatter (manual YAML to match reference style)
# ─────────────────────────────────────────────────────────────────────


def _build_frontmatter(state: dict[str, Any], regs: list[Any]) -> str:
    ctx = state.get("company_context")
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    # CORR-038-T3: source applicable_regs from app_ctx (canonical names)
    # so the frontmatter is consistent with §0.
    app_ctx = build_applicability_context(state)
    applicable = list(app_ctx.applicable_regs)
    # Sprint-2 (CORR-073): case_study falls back to v2_company_facts.name,
    # then company_facts.name, then case_name, only becoming "UNKNOWN" when
    # all of those are absent. The prior `getattr(..., "UNKNOWN")` default
    # hid missing data; this version is explicit about every fallback.
    case_study: str | None = None
    if ctx is not None:
        candidate = getattr(ctx, "company_name", None)
        if isinstance(candidate, str) and candidate.strip():
            case_study = candidate
    if case_study is None:
        facts = state.get("v2_company_facts")
        if facts is not None:
            name_attr = getattr(facts, "name", None)
            if isinstance(name_attr, str) and name_attr.strip():
                case_study = name_attr
    if case_study is None:
        company_facts = state.get("company_facts")
        if isinstance(company_facts, Mapping):
            candidate = company_facts.get("name")
            if isinstance(candidate, str) and candidate.strip():
                case_study = candidate
    if case_study is None:
        case_name = state.get("case_name")
        if isinstance(case_name, str) and case_name.strip():
            case_study = case_name
    if not case_study:
        case_study = "UNKNOWN"
    payload: dict[str, Any] = {
        "document_id": "AEGIS-P1-05",
        "title": "Regulatory Applicability Assessment",
        "phase": 1,
        "version": 1.1,
        "created": now,
        "updated": now,
        "author": "Executor",
        "status": "DRAFT",
        "case_study": case_study,
        "inputs": [
            "04_Company_Context_Assessment.md",
            "../00_COMMON/01_Company_Context.md",
            "00_Taxonomy_Reference.md",
        ],
        "outputs": [
            "06_Clause_Mapping_Matrix.xlsx",
            "07_Structured_Compliance_Matrix.md",
            "08_Obligation_Derivation.md",
        ],
        "applicable_regs": applicable,
        "related_documents": [
            "../../../00_METHODOLOGY/PHASE1_STRATEGY.md",
            "../../../00_METHODOLOGY/PHASE1_STRATEGY.md#filter-1-regulation-applicability-binary-predicates",
            "00_Taxonomy_Reference.md",
        ],
        "traceability": "AEGIS Class Model → ComplianceContext, RegulatoryClause, DomainCoverageEntry",
        "generated_at": now,
    }
    lines = ["---"]
    for key, value in payload.items():
        lines.append(f"{_safe_key(key)}: {_safe_value(value)}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


_SAFE_KEY = __import__("re").compile(r"[^A-Za-z0-9_.-]")


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


__all__ = ["_render_rationale_by_reg_section", "render_doc_05"]
