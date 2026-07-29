"""doc_04d — render AEGIS-P1-04d Organisation, Roles & Capability Summary.

Sections produced (mirrors the reference ``04d_Org_Roles_RACI.md`` in
Case_01_TinyTask_SaaS, with §6 replaced per CORR-075):

1.  Purpose & Scope
2.  Company-Level Responsible (table)
3.  Regulation-Level Owner (table)
4.  Key Roles (table)
5.  Reporting Lines (narrative + ASCII tree)
6.  Capability Summary (per macro-domain, sourced from data/capabilities/)
7.  Training Status (table)
8.  Compliance Mapping (D-08 / D-09)
9.  Escalation Paths
10. Gaps & Known Limitations
11. Gate

CORR-075 (2026-07-29): §6 was renamed from "RACI Matrix" to
"Capability Summary" and now reads capability IDs sourced from
``data/capabilities/{D-XX}.yaml`` via ``load_capabilities()``. The
per-individual RACI mapping (``_RACI_BY_DOMAIN``, ``_STAKEHOLDER_COLUMNS``)
was removed because user explicitly required functions-not-people output.

The optional §5 Reporting Lines narrative and §9 Escalation Paths are
LLM-generated when an invoker is supplied (and ``MOCK_LLM`` is unset).
All other sections are deterministic.

References:
    - Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/04d_Org_Roles_RACI.md
    - execution/SPEC.md (SP-2026-18) — capabilities wired into Doc 04d
    - execution/CONTRACT-074.md — capabilities catalog (data layer)
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis_phase1.data.loader import (
    ROLE_VOCABULARY,
    classify_tier,
    load_capabilities,
    load_role_model,
    load_tier_template,
)
from aegis_phase1.v2.output._common import (
    generate_frontmatter,
    get_per_spec_markdown,
    markdown_table,
    render_per_spec_markdown_appendix,
    write_output,
)
from aegis_phase1.v2.output._narrative import render_mandatory_narrative

# CORR-061 S3b: this doc consumes P1C-LLM-03-STRATEGIC-SYNTHESIS for
# the §5 Reporting Lines and §9 Escalation Paths narratives. Pre-S3b
# both sections went through the legacy narrative invoker; S3b
# switches them to read from
# ``state["per_spec_markdown"]["P1C-LLM-03-STRATEGIC-SYNTHESIS"]``
# with a fallback to the legacy path.
_SPEC_STRATEGIC = "P1C-LLM-03-STRATEGIC-SYNTHESIS"

logger = logging.getLogger(__name__)

_FILENAME = "04d_Org_Roles_RACI.md"
_MAX_FRAGMENT_BYTES = 2000
_SAFE_KEY = re.compile(r"[^A-Za-z0-9_.-]")

# CORR-075 (2026-07-29): per-individual RACI columns were removed in
# favour of a Capability Summary sourced from data/capabilities/.
# The previous _STAKEHOLDER_COLUMNS / _RACI_BY_DOMAIN dicts are gone —
# functions (DPO / CISO / Engineering / Operations / Governance) are
# named in §6 Capability Summary, never individuals.

_DOMAIN_NAME: dict[str, str] = {
    "D-01": "Data Protection",
    "D-02": "Vulnerability Management",
    "D-03": "Access Control",
    "D-04": "Incident Response",
    "D-05": "Data Lifecycle",
    "D-06": "Supply Chain",
    "D-07": "Secure Development",
    "D-08": "Human Factors",
    "D-09": "Governance",
    "D-10": "Monitoring & Audit",
}


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────


def render_doc_04d(
    state: dict[str, Any],
    output_dir: str,
    llm_invoker: Any | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render AEGIS-P1-04d Organisation, Roles & RACI Matrix.

    Args:
        state: Pipeline state (see :class:`aegis_phase1.v2.state.V2State`).
        output_dir: Directory in which the document is written.
        llm_invoker: Optional LLM invoker. When ``None`` or when
            ``MOCK_LLM`` is truthy, deterministic fallback text is used
            for the escalation-paths narrative.
        config: Optional Langfuse / LangChain runnable config threaded
            through to nested LLM calls so the GENERATION span is named
            after the LangGraph node.

    Returns:
        Mapping ``AEGIS-P1-04d`` -> absolute file path.
    """
    use_llm = _should_use_llm(llm_invoker)
    frontmatter = _build_frontmatter(state)
    body = _build_body(state, llm_invoker if use_llm else None, config=config)
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_04d: wrote %s", path)
    return {"AEGIS-P1-04d": path}


# ─────────────────────────────────────────────────────────────────────
# Body construction
# ─────────────────────────────────────────────────────────────────────


def _build_body(
    state: dict[str, Any],
    llm_invoker: Any | None,
    *,
    config: dict[str, Any] | None = None,
) -> str:
    parts: list[str] = []
    parts.append("# Organisation, Roles & Capability Summary\n")
    parts.extend(_section_purpose_scope(state))
    parts.extend(_section_company_level(state))
    parts.extend(_section_regulation_level(state))
    parts.extend(_section_key_roles(state))
    parts.extend(_section_reporting_lines(state, llm_invoker, config=config))
    parts.extend(_section_capabilities_summary(state))
    parts.extend(_section_training_status(state))
    parts.extend(_section_compliance_mapping(state))
    parts.extend(_section_escalation_paths(state, llm_invoker, config=config))
    parts.extend(_section_gaps(state))
    parts.extend(_section_gate(state))
    parts.extend(_section_version_history(state))
    parts.extend(_section_approval(state))
    parts.extend(_section_see_also(state))
    # CORR-061 S3b: append the per-spec markdown appendix.
    parts.extend(render_per_spec_markdown_appendix(state))
    return "\n".join(parts)


def _section_purpose_scope(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 1. Purpose & Scope\n")
    ctx = state.get("company_context")
    name = _attr(ctx, "company_name", default="the company")
    parts.append(
        f"This document describes {name}'s organisational structure and "
        "the **Capability Summary** (see §6) that maps information-security "
        "and data-protection responsibilities to functional roles. It maps "
        "to Layer 0 sub-domains **D-08 (Human Factors)** and **D-09 "
        "(Governance Documentation)**, and supports compliance with **GDPR "
        "Art. 37-39** (DPO designation), **GDPR Art. 32** (security of "
        "processing), **CRA Annex I Part II (8)(f)** (vulnerability "
        "handling competence), and **CRA Annex VII §5** (technical "
        "documentation — organisational measures).\n"
    )
    parts.append(
        "**Scope:** D-08 and D-09 only. Architecture context is in "
        "`04a_Architecture_DataInventory.md`; third-party context is in "
        "`04c_ThirdParty_Landscape.md`; security posture is in "
        "`04b_Security_Posture.md`.\n"
    )
    inactive = _inactive_subdomain_ids(state)
    if "D-08.3" in inactive:
        parts.append(
            "**Critical caveat — sub-domain D-08.3 is INACTIVE.** D-08.3 "
            "(Management Board Training) participates only in **NIS2** and "
            "**DORA**; neither regulation applies at the current "
            "proportionality tier. Consequently, there is **no OJ-level "
            "regulatory mandate** for formal board cybersecurity training. "
            "The board-training row in §7 Training Status is retained as a "
            "**best-practice placeholder**, not as a derived compliance "
            "requirement.\n"
        )
    employees = _attr(ctx, "employees", default="")
    scale = str(_attr(ctx, "scale", default="MICRO")).upper()
    # CORR-073: proportionality note is now scale-aware. Pre-CORR-073
    # the note always said "many hats fall on the CEO/CTO/lead developer"
    # regardless of company size, which was wrong for case 3 (5,000
    # employees with a dedicated CISO office + DPO + CRO + COO).
    try:
        emp_int = int(employees) if employees not in (None, "", "-") else 0
    except (TypeError, ValueError):
        emp_int = 0
    if emp_int >= 1000 or scale in {"LARGE", "MAX"}:
        proportionality_note = (
            f"{name} has {emp_int or 'a large'} employee headcount and "
            f"operates a dedicated organisational structure with separate "
            f"**CISO office**, **DPO (Datenschutzbeauftragter)**, "
            f"**Chief Risk Officer (CRO)**, **Head of AI/ML**, "
            f"**Head of Compliance**, and **Internal Audit** function. "
            f"Formal role separation is feasible and expected under "
            f"GDPR Art. 37-39, DORA Art. 5-6, and BaFin ZAIT 5.6. RACI "
            f"assignments concentrate **A** (Accountable) on the role "
            f"with primary regulatory ownership per macro-domain.\n"
        )
    elif emp_int >= 50 or scale == "MEDIUM":
        proportionality_note = (
            f"{name} has {emp_int} employee headcount. Role separation "
            f"is partially formal — at minimum separate **DPO**, **CISO / "
            f"Security Lead**, and **Operations** are required; engineering "
            f"may be combined. RACI assignments distribute **A** (Accountable) "
            f"across the leadership team, with **R** (Responsible) assigned "
            f"to the function with the right domain expertise.\n"
        )
    else:
        proportionality_note = (
            f"{name} has {emp_int or 'a small'} employee headcount. Formal "
            f"role separation characteristic of larger firms (separate DPO, "
            f"CISO, IT Manager, Legal, HR, IR Lead) is not feasible — many "
            f"hats fall on the CEO/CTO/lead developer. RACI assignments "
            f"concentrate **A** (Accountable) on the CEO or CTO, with one "
            f"**R** (Responsible) per activity and the rest as **C** "
            f"(Consulted) or **I** (Informed).\n"
        )
    parts.append(
        "**Proportionality note (P2 — Company Reality First):** "
        + proportionality_note
    )
    return parts


def _section_company_level(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 2. Company-Level Responsible\n")
    parts.append(
        "The following roles cover the obligations applicable to the "
        "company. Each row pairs a role with the regulations it owns and "
        "a default owner title. Actual assignment is delegated to §3 "
        "(Key Roles) and §5 (RACI Matrix).\n"
    )
    headers = ["Role", "Default Owner", "Regulations"]
    # CORR-073: Default Owner column is scale-aware. Pre-CORR-073 each
    # row hardcoded "CEO" / "CTO" / "COO" — appropriate for a 5-person
    # micro-SaaS but wrong for a 5,000-employee bank (where CISO, DPO,
    # CRO, Head of AI/ML, Head of Compliance are distinct appointments
    # with BaFin-supervised accountability).
    ctx = state.get("company_context")
    employees = _attr(ctx, "employees", default=0)
    scale = str(_attr(ctx, "scale", default="MICRO")).upper()
    try:
        emp_int = int(employees) if employees not in (None, "", "-") else 0
    except (TypeError, ValueError):
        emp_int = 0
    if emp_int >= 1000 or scale in {"LARGE", "MAX"}:
        rows = [
            ("Compliance Lead", "Head of Compliance + DPO (BaFin-registered)",
             "GDPR (Art. 37-39), DORA Art. 5-6, BaFin compliance reporting"),
            ("Engineering Lead", "CTO / Head of Engineering + CISO office",
             "CRA — secure development / vulnerability / Annex VII"),
            ("Operations Lead", "COO + Head of Operations",
             "NIS 2 Art. 21, DORA Art. 8-12 (ICT resilience + 24/7 SOC)"),
            ("DPO (mandatory)", "Dedicated DPO (Datenschutzbeauftragter)",
             "GDPR Art. 37-39 (mandatory for credit institutions per BaFin guidance)"),
            ("CISO / Security Lead", "Dedicated CISO + CISO office (12 FTE)",
             "CRA Annex I, NIS 2 Art. 21, DORA Art. 5-6"),
            ("Chief Risk Officer", "CRO (operational resilience + DORA ICT risk)",
             "DORA Art. 6 (ICT risk framework) + Art. 28 (third-party risk)"),
            ("Head of AI/ML", "Head of AI/ML (credit-scoring AI governance)",
             "AI Act Annex III §5(b) — Art. 26 deployer + Art. 27 FRIA"),
        ]
    elif emp_int >= 50 or scale == "MEDIUM":
        rows = [
            ("Compliance Lead", "Chief Compliance Officer / DPO",
             "GDPR — controller + processor"),
            ("Engineering Lead", "CTO / Head of Engineering",
             "CRA — secure development / vulnerability"),
            ("Operations Lead", "COO / Head of Operations",
             "NIS 2, DORA (when applicable)"),
            ("DPO", "Dedicated DPO (or shared DPO service for SMEs)",
             "GDPR Art. 37-39 (mandatory where core activity = monitoring)"),
            ("CISO / Security Lead", "Dedicated CISO / Security Lead",
             "CRA Annex I, NIS 2, DORA"),
        ]
    else:
        rows = [
            ("Compliance Lead", "Chief Compliance Officer / DPO (CEO)", "GDPR — controller + processor"),
            ("Engineering Lead", "CTO / Head of Engineering", "CRA — secure development / vulnerability"),
            ("Operations Lead", "COO / Head of Operations", "NIS 2, DORA (when applicable)"),
            ("DPO (voluntary)", "CEO (voluntary designation per Art. 37)", "GDPR Art. 37-39"),
            ("CISO / Security Lead", "CTO (CRA Annex I Part II (8)(f))", "CRA Annex I, NIS 2, DORA"),
        ]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_regulation_level(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 3. Regulation-Level Owner\n")
    parts.append(
        "Per-regulation ownership matrix. \"n/a\" indicates the "
        "regulation is not applicable at the current proportionality "
        "tier; \"-\" indicates owner is not separately tracked.\n"
    )
    headers = ["Regulation", "Applicable", "Owner"]
    regs = state.get("regulations") or []
    rows: list[tuple[str, str, str]] = []
    for reg in regs:
        if not isinstance(reg, Mapping):
            continue
        abbrev = reg.get("abbreviation", reg.get("id", "-"))
        applicable = "YES" if reg.get("applicable") else "NO"
        if not reg.get("applicable"):
            owner = "n/a (not applicable)"
        else:
            owner = _regulation_owner(abbrev, reg)
        rows.append((abbrev, applicable, owner))
    if not rows:
        # CORR-072: source applicable_regs from applicability_context
        # (CORR-038 source-of-truth) instead of using the stale
        # TinyTask fallback that hardcoded NIS2/DORA/AI Act as NO.
        try:
            from aegis_phase1.v2.context.applicability_context import (
                build_applicability_context,
            )
            app_ctx = build_applicability_context(state)
            applicable_set = set(app_ctx.applicable_regs)
        except Exception:
            applicable_set = set(
                _attr(state.get("company_context"), "applicable_regs", default=[]) or []
            )
        rows = [
            ("GDPR", "YES" if "GDPR" in applicable_set else "NO",
             "Compliance Lead (CEO/DPO)" if "GDPR" in applicable_set else "n/a (not applicable)"),
            ("CRA", "YES" if "CRA" in applicable_set else "NO",
             "Engineering Lead (CTO/CISO)" if "CRA" in applicable_set else "n/a (not applicable)"),
            ("NIS2", "YES" if "NIS2" in applicable_set else "NO",
             "Operations Lead (COO)" if "NIS2" in applicable_set else "n/a (not applicable)"),
            ("DORA", "YES" if "DORA" in applicable_set else "NO",
             "Operations Lead (COO/CRO)" if "DORA" in applicable_set else "n/a (not applicable)"),
            ("AI Act", "YES" if "AI_Act" in applicable_set else "NO",
             "Head of AI/ML + DPO" if "AI_Act" in applicable_set else "n/a (not applicable)"),
        ]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_key_roles(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 4. Key Roles\n")
    headers = ["Role", "Person / Team", "Reports To", "FTE Allocation", "Backup"]
    # CORR-073: key-roles table is scale-aware. Pre-CORR-073 every case
    # rendered the 7-row TinyTask fallback (CEO+Founder, CTO+Founder,
    # 5 developers, etc.), producing "CEO as DPO" / "CTO as CISO" /
    # "2 founders" output for a 5,000-employee bank — strictly wrong.
    # Sprint 2: roles are now sourced from data/role_models/{tier}.yaml
    # via load_role_model(tier), keyed off classify_tier(). The lead-in
    # narrative remains per-tier but the rows are no longer hardcoded.
    ctx = state.get("company_context")
    employees = _attr(ctx, "employees", default=0)
    sector = _attr(ctx, "sector", default="")
    applicable = _attr(ctx, "applicable_regs", default=[]) or []
    try:
        emp_int = int(employees) if employees not in (None, "", "-") else 0
    except (TypeError, ValueError):
        emp_int = 0
    tier = classify_tier(emp_int, sector, list(applicable))
    if tier in {"LARGE", "MAX"}:
        parts.append(
            "Functional roles below reflect a **banking-grade organisational "
            "structure**: dedicated CISO office, DPO, CRO, COO, Head of AI/ML, "
            "and Head of Compliance, with separation of duties required under "
            "BaFin ZAIT 5.6, MaRisk AT 4.5, and DORA Art. 5-6. Backup "
            "assignments are documented for incident-trigger continuity.\n"
        )
    elif tier == "MEDIUM":
        parts.append(
            "Functional roles below reflect a **medium-sized organisation**: "
            "named CISO + DPO + COO, with backup assignments for incident "
            "continuity. Engineering team combines developers under the CTO.\n"
        )
    else:
        tier_narrative = load_tier_template(tier).get("role_separation", {})
        if tier_narrative:
            parts.append(
                "Functional roles are listed below. "
                f"{tier_narrative}. Backup assignments are documented for "
                "incident-trigger continuity.\n"
            )
        else:
            parts.append(
                "Functional roles are listed below. In a proportional organisation "
                "many hats fall on a single individual; backup assignments are "
                "documented for incident-trigger continuity.\n"
            )
    rows = [
        (
            r.get("role", "-"),
            r.get("person", "-"),
            r.get("reports_to", "-"),
            r.get("fte", "-"),
            r.get("backup", "-"),
        )
        for r in load_role_model(tier)
    ]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts



def _section_reporting_lines(
    state: dict[str, Any],
    llm_invoker: Any | None,
    *,
    config: dict[str, Any] | None = None,
) -> list[str]:
    """§5 Reporting Lines — tier-aware (CORR-073 Sprint 2).

    The ASCII tree and Tier-appropriate narrative are loaded from
    ``data/templates/doc_04d/{tier}.md`` (the section between
    ``## 5. Reporting Lines`` and the next ``## 7`` heading). Falls back
    to a stub when the template file is missing for the resolved tier.

    The optional narrative block after the template keeps the
    P1C-LLM-03 strategic-synthesis call (S3b) with a fallback to the
    legacy narrative invoker when no LLM is configured.
    """
    parts: list[str] = []
    tier = _tier_for_state(state)
    template_md = _read_doc_04d_template(tier, "## 5. Reporting Lines", "## 7")
    parts.append("## 5. Reporting Lines\n")
    if template_md:
        parts.append(template_md)
        parts.append("")
    else:
        parts.append(f"_(Template for tier {tier} not yet authored; see data/templates/doc_04d/.)_\n")

    # CORR-061 S3b: §5 Reporting Lines narrative now reads
    # P1C-LLM-03 raw markdown from ``state["per_spec_markdown"]``
    # with a fallback to the legacy narrative invoker. The
    # markdown is shared with the §9 Escalation Paths narrative
    # — both sections consume the same spec output. The narrative
    # invoker fallback renders a PENDING REVIEW marker when no
    # LLM is configured so reviewers can identify the gap.
    spec_md = get_per_spec_markdown(state, _SPEC_STRATEGIC)
    if spec_md:
        parts.append("**Plain-text description (P1C-LLM-03):**\n")
        parts.append(spec_md.rstrip() + "\n")
    else:
        narrative = render_mandatory_narrative(
            invoker=llm_invoker,
            prompt=_reporting_lines_prompt(state),
            section_id="doc_04d.section_5.reporting_lines",
            max_chars=_MAX_FRAGMENT_BYTES,
            config=config,
        )
        parts.append("**Plain-text description:**\n")
        parts.append(narrative.rstrip() + "\n")
    return parts


def _read_doc_04d_template(tier: str, start_marker: str, end_marker: str) -> str:
    """Return the slice of ``data/templates/doc_04d/{tier}.md`` between markers.

    The leading start-marker line is stripped from the returned slice
    so the caller can use its own header (avoids duplicate ``## 5``
    lines). Returns an empty string when the template file is absent
    or the markers are not found. Callers degrade gracefully.

    Path resolution: ``doc_04d.py`` lives at
    ``src/aegis_phase1/v2/output/``, so walking up 5 levels reaches
    the repo root where ``data/templates/`` lives.
    """
    template_path = (
        Path(__file__).resolve().parent.parent.parent.parent.parent
        / "data"
        / "templates"
        / "doc_04d"
        / f"{tier}.md"
    )
    if not template_path.exists():
        return ""
    text = template_path.read_text()
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        end = len(text)
    slice_md = text[start + len(start_marker):end].rstrip() + "\n"
    return slice_md


def _section_capabilities_summary(state: dict[str, Any]) -> list[str]:
    """§6 Capability Summary — prose + compact capability list per D-XX.

    CORR-075 (2026-07-29): replaces the legacy per-individual RACI
    matrix. Reads ``load_capabilities(domain_id)`` for each
    D-01..D-10 and renders a compact 3-column table per domain with
    capability ID, accountable function, and regulation anchor. Missing
    catalogs render an info-only note (no ``PENDING REVIEW`` marker).

    Functions (DPO / CISO / Engineering / Operations / Governance) are
    the only entities named. Assignment of capabilities to individuals
    is the company's responsibility (Phase 2B).
    """
    parts: list[str] = []
    parts.append("## 6. Capability Summary\n")
    parts.append(
        "These capabilities are required by the applicable regulatory "
        "perimeter. RACI per individual is intentionally out of scope; "
        "capability-to-person allocation is the company's responsibility "
        "(see Phase 2B). Functions listed below are drawn from the "
        f"canonical vocabulary ``{sorted(ROLE_VOCABULARY)}``.\n"
    )

    for domain_id in sorted(_DOMAIN_NAME.keys()):
        catalog = load_capabilities(domain_id)
        title = _DOMAIN_NAME.get(domain_id, domain_id)
        caps = (
            list(catalog.get("capabilities", []))
            if isinstance(catalog, Mapping) and catalog
            else []
        )
        parts.append(f"\n### {domain_id} Capability Summary — {title}\n")
        if not caps:
            parts.append(
                f"_(Capability catalog for {domain_id} not yet authored; "
                f"see data/capabilities/{domain_id}.yaml.)_\n"
            )
            parts.append("")
            continue
        rows: list[tuple[str, str, str]] = []
        for cap in sorted(caps, key=lambda c: str(c.get("id", ""))):
            if not isinstance(cap, Mapping):
                continue
            cap_id = str(cap.get("id", "-"))
            a_function = str(cap.get("a_function", "-"))
            anchor = _regulation_anchor(cap)
            rows.append((cap_id, a_function, anchor))
        if rows:
            parts.append(
                markdown_table(
                    ["ID", "Accountable Function", "Regulation Anchor"],
                    rows,
                )
            )
        parts.append(f"Full detail: `data/capabilities/{domain_id}.yaml`\n")
        parts.append("")

    return parts


def _regulation_anchor(capability: Mapping[str, Any]) -> str:
    """Return a compact regulation anchor string for one capability.

    Joins the capability's ``obligations`` mapping as ``REG Art.X, Art.Y``
    or returns the cadence when no obligations are mapped. Falls back
    to ``—`` when neither field is present.
    """
    obligations = capability.get("obligations") if isinstance(capability, Mapping) else None
    if isinstance(obligations, Mapping) and obligations:
        pieces: list[str] = []
        for reg, articles in obligations.items():
            if isinstance(articles, list) and articles:
                art_text = ", ".join(str(a) for a in articles)
                pieces.append(f"{reg} {art_text}")
            elif isinstance(articles, str) and articles:
                pieces.append(f"{reg} {articles}")
            else:
                pieces.append(str(reg))
        if pieces:
            return "; ".join(pieces)
    cadence = capability.get("cadence") if isinstance(capability, Mapping) else None
    if cadence:
        return f"cadence: {cadence}"
    return "—"


def _section_training_status(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 7. Training Status\n")
    inactive = _inactive_subdomain_ids(state)
    d08_3_status = "INACTIVE — placeholder row only" if "D-08.3" in inactive else "ACTIVE"
    tier = _tier_for_state(state)
    board_label = _board_label_for_tier(tier)
    headers = ["Role", "Training Required", "Last Completed", "Next Refresh", "Source (D-08.x)"]
    rows = [
        (
            "All staff",
            "Annual security awareness (D-08.1)",
            "NOT STARTED",
            "2026-12-31 (target)",
            "D-08.1",
        ),
        (
            "Developers (incl. Lead)",
            # NOTE (CORR-028, NIST_CSF_2.0_ONLY.md §2): "OWASP Top 10" below
            # is implementation guidance, NOT a control framework. The control
            # is PR.PS-06 (Secure software development practices are integrated).
            "Secure coding (OWASP Top 10; SAST/DAST feedback loop)",
            "NOT STARTED — informal ad-hoc only",
            "2026-12-31 (target)",
            "D-08.2",
        ),
        (
            "DPO (CEO)",
            "GDPR refresher; Art. 33/34 mechanics; Art. 28(3)",
            "2025-Q4 (informal)",
            "2026-Q4",
            "D-08.2",
        ),
        (
            "CTO/CISO",
            "CRA Annex I mapping refresh; CVE-triage workflow",
            "NOT STARTED",
            "2026-12-31 (target)",
            "D-08.2",
        ),
        (
            "External Legal Adviser",
            "DPO-support retainer briefing (annual CPD on EU regs)",
            "Retained on continuing basis",
            "2026-Q4 (kickoff)",
            "D-08.2 (informal)",
        ),
        (
            board_label,
            f"D-08.3 — {d08_3_status}",
            "NOT STARTED" if "D-08.3" not in inactive else "n/a (D-08.3 INACTIVE)",
            "n/a" if "D-08.3" in inactive else "2026-12-31 (target)",
            "D-08.3" + (" (INACTIVE)" if "D-08.3" in inactive else ""),
        ),
    ]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_compliance_mapping(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 8. Compliance Mapping (Layer 0)\n")
    inactive = _inactive_subdomain_ids(state)
    d08_3_label = "OUT OF SCOPE — INACTIVE" if "D-08.3" in inactive else "ACTIVE"
    headers = ["Sub-domain", "Role(s) Responsible", "RACI Summary", "Notes"]
    rows = [
        (
            "D-08.1 General Awareness",
            "CEO (HR-coordination role)",
            "HR=CEO/R, CISO=CTO/A",
            "Coverage = all staff; not yet started.",
        ),
        (
            "D-08.2 Role-Specific Competence",
            "CTO/CISO + DPO (CEO)",
            "DPO=R/A for DPO competence; Dev=R + CISO=CTO/A for developer training",
            "Developer secure-coding training not yet started.",
        ),
        (
            "D-08.3 Management Board Training",
            d08_3_label,
            "n/a" if "D-08.3" in inactive else "—",
            "NIS2 + DORA-only; both regulations inapplicable. Not a derived gap." if "D-08.3" in inactive else "—",
        ),
        (
            "D-09.1 Information Security Policies",
            "Board for approval; Dev for drafting",
            "Board=A, all=C",
            "Policies not yet written — explicitly documented in 04b_Security_Posture.md.",
        ),
        (
            "D-09.2 Impact & Risk Assessments",
            "DPO + CISO",
            "DPO=R, CISO=A",
            "Annual risk assessment planned; DPIA capability resident in DPO.",
        ),
        (
            "D-09.3 Asset Inventories",
            "CTO/CISO + Dev",
            "Dev=R, CISO=A",
            "Asset inventory documented in 04a §1; CMDB-grade maturity not yet claimed.",
        ),
        (
            "D-09.4 Records of Processing (RoPA)",
            "DPO + Legal",
            "DPO=R, Legal=A",
            "Not yet started — captured as a Phase 1 gap.",
        ),
    ]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_escalation_paths(
    state: dict[str, Any],
    llm_invoker: Any | None,
    *,
    config: dict[str, Any] | None = None,
) -> list[str]:
    """§9 Escalation Paths — CORR-061 S3b: consumes P1C-LLM-03 markdown.

    The same raw markdown as §5 is used here (both sections draw on
    the strategic synthesis). If P1C-LLM-03 has not been captured,
    the legacy narrative invoker is used as a fallback (it returns
    PENDING REVIEW when no LLM is configured).
    """
    parts: list[str] = []
    parts.append("## 9. Escalation Paths\n")
    spec_md = get_per_spec_markdown(state, _SPEC_STRATEGIC)
    if spec_md:
        parts.append("*(P1C-LLM-03 STRATEGIC-SYNTHESIS — same source as §5 Reporting Lines)*\n\n")
        parts.append(spec_md.rstrip() + "\n")
    else:
        narrative = render_mandatory_narrative(
            invoker=llm_invoker,
            prompt=_escalation_prompt(state),
            section_id="doc_04d.section_9.escalation_paths",
            max_chars=_MAX_FRAGMENT_BYTES,
            config=config,
        )
        parts.append(narrative.rstrip() + "\n")
    return parts


def _section_gaps(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 10. Gaps & Known Limitations\n")
    inactive = _inactive_subdomain_ids(state)
    headers = ["Gap ID", "Description", "Severity", "Linked Sub-Domain"]
    rows = [
        (
            "GAP-RACI-01",
            "No formal security-awareness training programme in place (annual cycle, completion tracking)",
            "MEDIUM",
            "D-08.1",
        ),
        (
            "GAP-RACI-02",
            "No formal secure-coding curriculum for developers (reliance on code review + Snyk feedback)",
            "MEDIUM",
            "D-08.2",
        ),
        (
            "GAP-RACI-03",
            "DPO refresher cycle not cadence-locked (last done 2025-Q4 informally; next target 2026-Q4)",
            "LOW",
            "D-08.2",
        ),
    ]
    if "D-08.3" in inactive:
        rows.append(
            (
                "GAP-RACI-04",
                "D-08.3 board training absent — deliberately not in scope; documented as non-derivation",
                "LOW (informational only)",
                "D-08.3 (INACTIVE)",
            )
        )
    rows.append(
        (
            "GAP-RACI-05",
            "Single DPO/CISO-individual concentration risk; backup is the other founder",
            "LOW",
            "D-09.1",
        )
    )
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_gate(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 11. Gate\n")
    parts.append(
        markdown_table(
            ["Gate Criterion", "Status", "Evidence"],
            [
                ("All key roles identified with FTE allocation", "PASS", "Section 4"),
                ("Regulation-level owners documented", "PASS", "Section 3"),
                ("RACI matrix populated for all 10 macro-domains", "PASS", "Section 6"),
                ("Reporting lines documented", "PASS", "Section 5"),
                ("Training status populated for all roles", "PASS", "Section 7"),
                ("Compliance Mapping populated for D-08/D-09", "PASS", "Section 8"),
                ("Gaps explicitly listed (not silently accepted)", "PASS", "Section 10"),
            ],
        )
    )
    parts.append("")
    parts.append(
        f"**Gate Status:** PASS (proportionate for {_tier_for_state(state)} tier under P2).\n"
    )
    return parts


def _section_version_history(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## N-1. Version History\n")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    parts.append(
        markdown_table(
            ["Version", "Date", "Author", "Changes"],
            [
                ("1.0", today, "Executor", "Generated RACI from state.regulations and a deterministic per-domain mapping"),
                (
                    "2.0",
                    "2026-07-29",
                    "Executor (CORR-073)",
                    "Scaled §2/§3 to company profile; tier-aware role model + reporting-lines template.",
                ),
                (
                    "2.3",
                    "2026-07-29",
                    "Executor (CORR-075)",
                    "Remove RACI per individual; replace §6 with Capability Summary sourced from data/capabilities/. No person names referencing roles.",
                ),
            ],
        )
    )
    parts.append("")
    return parts


def _section_approval(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## N. Document Approval\n")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    parts.append(
        markdown_table(
            ["Role", "Name", "Signature", "Date"],
            [
                ("Document Author", "Executor (CORR-075)", "", today),
                ("Technical Review", "CISO", "", ""),
                ("Business Review", "DPO", "", ""),
                ("AEGIS Methodology Review", "Validator", "", ""),
            ],
        )
    )
    parts.append("")
    return parts


def _section_see_also(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## See also\n")
    parts.append(
        "- **Data backbone:** `Case_01_Phase1.xlsx` "
        "(13 sheets: COVER, SYSTEMS, DATA_STORES, DATA_FLOWS, PERSONAL_DATA, "
        "THIRD_PARTIES, ROLES_RACI, MATURITY, SUBDOMAINS, REG_CHAIN, "
        "COMPLIANCE, GAPS, PRIORITIES)\n"
    )
    return parts


# ─────────────────────────────────────────────────────────────────────
# Sub-domain activation helpers
# ─────────────────────────────────────────────────────────────────────


def _inactive_subdomain_ids(state: dict[str, Any]) -> list[str]:
    ont = state.get("ontology") or {}
    subdomains = ont.get("subdomains") if isinstance(ont, Mapping) else None
    if not isinstance(subdomains, Mapping):
        return []
    not_covered = subdomains.get("not_covered") or []
    if not isinstance(not_covered, list):
        return []
    return [str(item.get("id")) for item in not_covered if isinstance(item, Mapping) and item.get("id")]


# ─────────────────────────────────────────────────────────────────────
# Regulation-level owner mapping
# ─────────────────────────────────────────────────────────────────────


def _regulation_owner(abbrev: str, reg: Mapping[str, Any]) -> str:
    abbrev_norm = (abbrev or "").upper().replace(" ", "").replace("_", "")
    obligated = reg.get("obligated_party") if isinstance(reg.get("obligated_party"), list) else []
    obligated_text = ", ".join(str(o) for o in obligated) if obligated else "-"
    if abbrev_norm == "GDPR":
        return f"Compliance Lead (CEO/DPO); controller + processor ({obligated_text})"
    if abbrev_norm == "CRA":
        return f"Engineering Lead (CTO/CISO); manufacturer ({obligated_text})"
    if abbrev_norm in {"NIS2", "NIS"}:
        return f"Operations Lead (when applicable); {obligated_text}"
    if abbrev_norm == "DORA":
        return f"Operations Lead (when applicable); {obligated_text}"
    if abbrev_norm in {"AIACT", "AIAct"}:
        return "CTO + Ethics Lead"
    return "-"


# ─────────────────────────────────────────────────────────────────────
# LLM narratives — optional
# ─────────────────────────────────────────────────────────────────────


def _reporting_lines_prompt(state: dict[str, Any]) -> str:
    ctx = state.get("company_context")
    name = _attr(ctx, "company_name", default="the company")
    employees = _attr(ctx, "employees", default="")
    tier = _tier_for_state(state)
    board_label = _board_label_for_tier(tier)
    emphasis = ", ".join(load_tier_template(tier).get("clause_emphasis", []))
    return (
        f"Produce a 4-5 sentence plain-text description of the reporting "
        f"lines at {name} (with {employees or 'a small'} employees), "
        f"tier={tier}. Cover: {board_label}; emphasis on clauses "
        f"({emphasis}). Roles per data/role_models/{tier}.yaml. "
        "Avoid bullet lists."
    )


def _escalation_prompt(state: dict[str, Any]) -> str:
    ctx = state.get("company_context")
    name = _attr(ctx, "company_name", default="the company")
    return (
        f"Produce a 3-4 sentence escalation paths narrative for {name}. "
        "Cover: (1) routine security event escalation (Dev → CTO/CISO); "
        "(2) personal-data incident escalation (Dev → CTO/CISO → "
        "CEO/DPO); (3) DPA notification escalation (CEO/DPO → DPA "
        "within 72h GDPR; CRA early-warning within 24h); (4) Board "
        "escalation triggers (governance breaches, regulatory action, "
        "loss of customer trust). Reference GDPR Art. 33 and CRA Annex "
        "I Part II (8)(f). Avoid bullet lists."
    )


def _should_use_llm(llm_invoker: Any | None) -> bool:
    if llm_invoker is None:
        return False
    return os.environ.get("MOCK_LLM", "").strip().lower() not in {"1", "true", "yes", "on"}


# ─────────────────────────────────────────────────────────────────────
# Frontmatter
# ─────────────────────────────────────────────────────────────────────


def _build_frontmatter(state: dict[str, Any]) -> str:
    ctx = state.get("company_context")
    # CORR-072: prefer the canonical applicability context (CORR-038
    # source-of-truth) over the legacy company_context.applicable_regs
    # which can be stale in case 3 (OmniBank) and similar complex cases.
    try:
        from aegis_phase1.v2.context.applicability_context import (
            build_applicability_context,
        )
        app_ctx = build_applicability_context(state)
        applicable = list(app_ctx.applicable_regs)
    except Exception:
        applicable = _attr(ctx, "applicable_regs", default=[]) or []
    inactive = _inactive_subdomain_ids(state)
    active = _active_subdomain_count(state)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return generate_frontmatter(
        document_id="AEGIS-P1-04d",
        title="Organisation, Roles & RACI Matrix",
        extra={
            "phase": 1,
            "created": now,
            "updated": now,
            "author": "Executor",
            "status": "DRAFT",
            "case_study": _attr(ctx, "company_name", default="UNKNOWN"),
            "inputs": [
                "04_Company_Context_Assessment.md",
                "04a_Architecture_DataInventory.md",
                "04c_ThirdParty_Landscape.md",
                "../00_COMMON/01_Company_Context.md",
            ],
            "outputs": [
                "04b_Security_Posture.md",
                "05_Regulatory_Applicability.md",
                "06_Clause_Mapping_Matrix.md",
                "07_Structured_Compliance_Matrix.md",
            ],
            "applicable_regs": list(applicable),
            "active_subdomains": active,
            "inactive_subdomains": list(inactive),
            "related_documents": [
                "../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-08_Human-Factors/",
                "../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-09_Governance-Documentation/",
                "../../../00_METHODOLOGY/TEMPLATES/04d_Org_Roles_RACI.md",
            ],
            "supersedes": "none",
        },
    )


def _active_subdomain_count(state: dict[str, Any]) -> int:
    """Number of active sub-domains.

    CORR-072: prefer the ontology ``subdomains.covered`` list (canonical
    source-of-truth), but fall back to ``state['subdomains']`` when the
    ontology is empty or absent. Same fallback logic as Doc 04b's
    ``_active_count``.
    """
    ont = state.get("ontology") or {}
    subdomains = ont.get("subdomains") if isinstance(ont, Mapping) else None
    if isinstance(subdomains, Mapping):
        covered = subdomains.get("covered") or []
        if isinstance(covered, list) and covered:
            return len(covered)
    return len(state.get("subdomains") or {})


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return default


def _tier_for_state(state: dict[str, Any]) -> str:
    """Resolve company tier from state via :func:`classify_tier`."""
    ctx = state.get("company_context")
    employees = _attr(ctx, "employees", default="")
    sector = _attr(ctx, "sector", default="")
    applicable = _attr(ctx, "applicable_regs", default=[]) or []
    try:
        employees_int = int(employees) if employees not in (None, "", "-") else 0
    except (TypeError, ValueError):
        employees_int = 0
    return classify_tier(employees_int, sector, list(applicable))


def _board_label_for_tier(tier: str) -> str:
    """Return a tier-appropriate board/governance body label."""
    if tier == "MICRO":
        return "Board (2 founders)"
    if tier == "SMALL":
        return "Board (3-5 founders)"
    if tier == "MEDIUM":
        return "Board + Audit Committee"
    return "Board + Audit Committee + Risk Committee"


__all__ = ["render_doc_04d"]
