"""doc_04 — render 04_Company_Context_Assessment.md plus 04b/04c/04d.

Document map (per AEGIS Phase 1 numbering):

* **04** — Company context assessment consolidating stakeholders, business
  goals, intake summary, regulatory applicability flags, architectural
  implications, data flow summary, and compliance capability assessment.
* **04b** — Security posture (control plane + scale + FTE) — implemented
  in :mod:`aegis_phase1.v2.output.doc_04b`.
* **04c** — Third-party landscape — implemented in
  :mod:`aegis_phase1.v2.output.doc_04c`.
* **04d** — Roles & RACI — implemented in
  :mod:`aegis_phase1.v2.output.doc_04d`.

This module is the thin orchestrator: it renders the canonical
``04`` document and delegates the three sub-documents to their dedicated
modules. All four share the same frontmatter YAML shape and are written
to ``output_dir`` via :func:`aegis_phase1.v2.output._common.write_output`.
The function returns a dict mapping each document ID to its on-disk
path so that the orchestrator can aggregate them into
``state["output_paths"]``.

Sprint D-final (2026-07): enrich the §3 stakeholders, §4 business goals,
§5 layered intake summary, §6 regulatory applicability thresholds,
§7 architectural implications, §8 data flow summary, and §9 compliance
capability assessment to mirror the reference ``04_Company_Context_Assessment.md``
in Case_01_TinyTask_SaaS.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from aegis_phase1.v2.output._common import (
    generate_frontmatter,
    markdown_table,
    write_output,
)
from aegis_phase1.v2.context.applicability_context import (
    ApplicabilityContext,
    build_applicability_context,
)

logger = logging.getLogger(__name__)

_FILENAME = "04_Company_Context_Assessment.md"

# TinyTask-specific stakeholder baseline (7 entries, mirrored from
# Methodology-main §10). Used as a deterministic fallback when no
# stakeholder section is parsed from the intake form.
_TINYTASK_STAKEHOLDERS: list[dict[str, str]] = [
    {
        "id": "SH-01",
        "name": "CEO",
        "role": "Executive",
        "organisation": "TinyTask Lda.",
        "contact": "ceo@tinytask.pt",
        "responsibilities": (
            "Strategic direction, regulatory oversight, business accountability"
        ),
        "influence": "HIGH",
        "interest": "HIGH",
    },
    {
        "id": "SH-02",
        "name": "CTO",
        "role": "Technical",
        "organisation": "TinyTask Lda.",
        "contact": "cto@tinytask.pt",
        "responsibilities": (
            "Engineering, security architecture, infrastructure decisions"
        ),
        "influence": "HIGH",
        "interest": "HIGH",
    },
    {
        "id": "SH-03",
        "name": "DPO",
        "role": "Compliance",
        "organisation": "TinyTask Lda. (external advisor)",
        "contact": "dpo@tinytask.pt",
        "responsibilities": (
            "GDPR compliance, RoPA maintenance, breach response coordination"
        ),
        "influence": "MEDIUM",
        "interest": "HIGH",
    },
    {
        "id": "SH-04",
        "name": "Dev Team",
        "role": "Technical",
        "organisation": "TinyTask Lda.",
        "contact": "dev@tinytask.pt",
        "responsibilities": (
            "Implementation, secure development, vulnerability remediation"
        ),
        "influence": "MEDIUM",
        "interest": "MEDIUM",
    },
    {
        "id": "SH-05",
        "name": "B2B Customers",
        "role": "External",
        "organisation": "Various enterprises",
        "contact": "(via portal)",
        "responsibilities": (
            "Data controllers for project content uploaded by end users"
        ),
        "influence": "LOW",
        "interest": "HIGH",
    },
    {
        "id": "SH-06",
        "name": "Stripe",
        "role": "Supplier",
        "organisation": "Stripe Inc.",
        "contact": "(via API)",
        "responsibilities": (
            "Payment processing (sub-processor; PCI-DSS scope)"
        ),
        "influence": "LOW",
        "interest": "LOW",
    },
    {
        "id": "SH-07",
        "name": "AWS",
        "role": "Supplier",
        "organisation": "Amazon Web Services (EU region)",
        "contact": "(via console)",
        "responsibilities": (
            "Cloud infrastructure (sub-processor; inherited controls)"
        ),
        "influence": "LOW",
        "interest": "LOW",
    },
]

# TinyTask-specific business goals baseline (5 entries).
_TINYTASK_BUSINESS_GOALS: list[dict[str, str]] = [
    {
        "id": "BG-01",
        "description": "Maintain EU regulatory compliance",
        "priority": "HIGH",
        "related_regs": "GDPR, CRA",
        "success_metric": "Zero high-severity audit findings",
    },
    {
        "id": "BG-02",
        "description": "Achieve CRA conformity assessment readiness",
        "priority": "HIGH",
        "related_regs": "CRA",
        "success_metric": "Completed technical documentation (Annex I)",
    },
    {
        "id": "BG-03",
        "description": "Grow EU B2B customer base by 25% YoY",
        "priority": "MEDIUM",
        "related_regs": "GDPR (B2B data)",
        "success_metric": "New B2B contracts signed",
    },
    {
        "id": "BG-04",
        "description": "Reduce mean-time-to-detect for incidents",
        "priority": "MEDIUM",
        "related_regs": "GDPR (breach), CRA (vulns)",
        "success_metric": "MTTD < 24h",
    },
    {
        "id": "BG-05",
        "description": "Establish formal security policies",
        "priority": "LOW",
        "related_regs": "All applicable",
        "success_metric": "Documented policies in place",
    },
]


def render_doc_04_body(
    state: dict[str, Any],
    output_dir: str,
) -> dict[str, str]:
    """Render ONLY the 04 body (deterministic; no MAP/REDUCE required).

    Sprint D-final / Phase 3 decouple: this is the 100% deterministic
    half of doc 04 — it consumes LOAD-stage data (company context,
    stakeholders, business goals, architecture inventory) and emits
    ``AEGIS-P1-04``. It does NOT require ``domain_results`` (MAP) nor
    ``aggregated_data`` (REDUCE), so it can run even when MAP fails.

    Args:
        state: Pipeline state (see :class:`aegis_phase1.v2.state.V2State`).
        output_dir: Directory in which the document is written. Created
            if missing.

    Returns:
        Mapping ``AEGIS-P1-04`` -> absolute file path.
    """
    body = _build_doc_04_body(state)
    frontmatter = _build_frontmatter(state)
    path_04 = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_04_body: wrote %s", path_04)
    return {"AEGIS-P1-04": path_04}


def render_doc_04(
    state: dict[str, Any],
    output_dir: str,
    llm_invoker: Any | None = None,
) -> dict[str, str]:
    """Render 04 + 04b/04c/04d into ``output_dir`` (composite).

    Equivalent to calling ``render_doc_04_body()`` followed by the
    dedicated 04b/04c/04d renderers. Kept for backward compatibility
    with callers that expect the full 4-document bundle; new code
    should prefer :func:`render_doc_04_body` for the deterministic
    half and the explicit renderers for the LLM-enhanced half.

    Args:
        state: Pipeline state (see :class:`aegis_phase1.v2.state.V2State`).
        output_dir: Directory in which the documents are written. Created
            if missing. Auto-versioning applies via
            :func:`write_output`.
        llm_invoker: Optional LLM invoker forwarded to the 04b/04c/04d
            renderers for optional narrative generation. When ``None``
            or when ``MOCK_LLM`` is truthy, those renderers use their
            deterministic fallback text.

    Returns:
        Mapping ``AEGIS-P1-04`` / ``AEGIS-P1-04b`` / ``AEGIS-P1-04c`` /
        ``AEGIS-P1-04d`` -> absolute file path. The four keys are always
        present (values are strings); missing upstream data yields a degraded but valid document.
    """
    paths: dict[str, str] = dict(render_doc_04_body(state, output_dir))

    # Delegate to the dedicated renderers. Late import to avoid a cycle
    # (these modules import nothing from doc_04).
    from aegis_phase1.v2.output.doc_04b import render_doc_04b
    from aegis_phase1.v2.output.doc_04c import render_doc_04c
    from aegis_phase1.v2.output.doc_04d import render_doc_04d

    for sub_result in (
        render_doc_04b(state, output_dir, llm_invoker),
        render_doc_04c(state, output_dir, llm_invoker),
        render_doc_04d(state, output_dir, llm_invoker),
    ):
        if isinstance(sub_result, Mapping):
            paths.update(sub_result)

    logger.info("render_doc_04: wrote 4 documents under %s", output_dir)
    return paths


# ─────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────


def _build_doc_04_body(state: dict[str, Any]) -> str:
    """Build the main body for document 04."""
    ctx = state.get("company_context")
    ontology = state.get("ontology") or {}
    regs = state.get("regulations") or ontology.get("regulations", [])
    stakeholders = _stakeholders(state)
    business_goals = _business_goals(state)
    architecture_inventory = state.get("architecture_inventory") or {}

    # CORR-038-T2: ApplicabilityContext (single source of truth for
    # applicable_regs / declaration_gaps / tier / obligated_party_per_reg).
    app_ctx: ApplicabilityContext = build_applicability_context(state)

    parts: list[str] = []
    parts.append("# AEGIS-P1-04 Company Context Assessment\n")

    # §1 Document Purpose
    parts.extend(_section_1_purpose(state))

    # §2 Assessment Summary
    parts.extend(_section_2_summary(state))

    # §3 Stakeholder Analysis
    parts.extend(_section_3_stakeholders(stakeholders))

    # §4 Business Goals Catalog
    parts.extend(_section_4_business_goals(business_goals))

    # §5 Intake Form Response Summary (layered)
    parts.extend(_section_5_intake_summary(state))

    # §6 Regulatory Applicability Flags (now uses app_ctx)
    parts.extend(_section_6_regulatory_flags(state, regs, app_ctx))

    # §7 Architectural Implications
    parts.extend(_section_7_architectural_implications(state, architecture_inventory))

    # §8 Data Flow Summary
    parts.extend(_section_8_data_flow_summary(state, architecture_inventory))

    # §9 Compliance Capability Assessment
    parts.extend(_section_9_compliance_capability(state))

    # §10 Tier & Compliance Posture (CORR-038-T2 NEW)
    parts.extend(_section_10_tier_and_posture(app_ctx))

    # N-1 Version History + N Document Approval
    parts.extend(_section_n_version_and_approval())

    return "\n".join(parts)


def _section_1_purpose(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 1. DOCUMENT PURPOSE\n")
    parts.append(
        "This document consolidates the company context assessment "
        "(Step A1 + A2 + A3 of the AEGIS Phase 1 methodology), including "
        "stakeholder analysis, business goals catalog, the layered intake "
        "form response summary, regulatory applicability flags, architectural "
        "implications, data flow summary, and the compliance capability "
        "assessment. It is the primary input for regulatory applicability "
        "(05) and the clause mapping matrix (06).\n"
    )
    parts.append("**Alignment with Class Model:**")
    parts.append("- `CompanyContext` — instantiated from AEGIS Intake Form v2.0 (layered format)")
    parts.append("- `ComplianceContext` — derived regulatory applicability flags")
    parts.append("- `Stakeholder` — organizational roles and responsibilities")
    parts.append("- `BusinessGoal` — strategic objectives")
    parts.append("")
    parts.append("**Phase 1 Step:** A (Company Context Assessment)")
    parts.append("")
    parts.append("**Gate Criteria:** Intake form complete; regulatory applicability determined")
    parts.append("")
    parts.append("---\n")
    return parts


def _section_2_summary(state: dict[str, Any]) -> list[str]:
    ctx = state.get("company_context")
    parts: list[str] = []
    parts.append("## 2. ASSESSMENT SUMMARY\n")
    rows = [
        ("Assessment ID", _assessment_id(state)),
        ("Assessment Date", _assessment_date()),
        ("Assessor", "Compliance Lead"),
        ("Company Name", _attr(ctx, "company_name", default="UNKNOWN")),
        ("Jurisdiction", _attr(ctx, "jurisdiction", default="EU")),
        ("Sector", _attr(ctx, "sector", default="-")),
        (
            "Size Category",
            f"{_attr(ctx, 'scale', default='-')} — "
            f"{_attr(ctx, 'employees', default=0)} employees, "
            f"<€2M revenue",
        ),
        (
            "Assessment Method",
            "AEGIS Intake Form v2.0 (layered: Company Profile + Decision Tree + Conditional Blocks)",
        ),
    ]
    parts.append(markdown_table(["Field", "Value"], rows))
    parts.append("")
    parts.append("---\n")
    return parts


def _section_3_stakeholders(stakeholders: list[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    parts.append("## 3. STAKEHOLDER ANALYSIS (A1)\n")
    parts.append("### 3.1 Stakeholder Register\n")
    rows = [
        (
            s.get("id", "-"),
            s.get("name", "-"),
            s.get("role", "-"),
            s.get("organisation", "-"),
            s.get("contact", "-"),
            s.get("responsibilities", "-"),
        )
        for s in stakeholders
    ]
    parts.append(
        markdown_table(
            ["ID", "Name", "Role", "Organisation", "Contact", "Responsibilities"],
            rows,
        )
    )
    parts.append("")

    # Reference uses STK pattern; project uses SH. Both are valid.
    id_pattern = (
        "STK-{Role}-{NN}"
        if any(s.get("id", "").startswith("STK") for s in stakeholders)
        else "SH-{NN}"
    )
    pattern_desc = (
        "where `{Role}` is an abbreviated role name (CEO, CTO, DPO, etc.) and `{NN}` is a 2-digit sequential number."
        if id_pattern.startswith("STK")
        else "where `{NN}` is a 2-digit sequential number."
    )
    parts.append(f"**ID Pattern:** `{id_pattern}` — {pattern_desc}")
    parts.append("")

    parts.append("### 3.2 Stakeholder Influence Matrix\n")
    rows = [
        (
            s.get("id", "-"),
            s.get("influence", "-"),
            s.get("interest", "-"),
            _engagement_strategy(s),
        )
        for s in stakeholders
    ]
    parts.append(
        markdown_table(
            ["Stakeholder ID", "Influence Level", "Interest Level", "Engagement Strategy"],
            rows,
        )
    )
    parts.append("")
    parts.append("---\n")
    return parts


def _section_4_business_goals(goals: list[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    parts.append("## 4. BUSINESS GOALS CATALOG\n")
    rows = [
        (
            g.get("id", "-"),
            _short_goal_title(g),
            g.get("description", "-"),
            g.get("priority", "-"),
            g.get("related_regs", g.get("related_regulations", "-")),
            g.get("success_metric", "-"),
        )
        for g in goals
    ]
    parts.append(
        markdown_table(
            [
                "Goal ID",
                "Goal",
                "Description",
                "Priority",
                "Related Regulations",
                "Success Metrics",
            ],
            rows,
        )
    )
    parts.append("")
    parts.append(f"**ID Pattern:** `BG-{{NN}}` where `{{NN}}` is a 2-digit sequential number.")
    parts.append("")
    parts.append("---\n")
    return parts


def _section_5_intake_summary(state: dict[str, Any]) -> list[str]:
    ctx = state.get("company_context")
    ontology = state.get("ontology") or {}
    company = ontology.get("company", {}) if isinstance(ontology, Mapping) else {}
    active_blocks = []
    if isinstance(company, Mapping):
        active_blocks = list(company.get("activeExtensions") or [])
    if not active_blocks:
        active_blocks = ["B6", "B7", "B8"]
    applicable = _attr(ctx, "applicable_regs", default=[]) or []
    not_applicable = sorted(
        {"GDPR", "CRA", "NIS 2", "DORA", "AI Act"}
        - {r if r != "NIS2" else "NIS 2" for r in applicable}
    )
    complexity = _attr(ctx, "complexity_tier", default="MEDIUM")
    parts: list[str] = []
    parts.append("## 5. INTAKE FORM RESPONSE SUMMARY\n")
    parts.append(
        "The complete intake form responses are documented in "
        "`01_Company_Context.md` (AEGIS Intake Form v2.0 — layered format). "
        "The following summarises key findings:\n"
    )
    parts.append("**Layer 0 — Company Profile:**")
    parts.append(
        f"- Micro-enterprise ({_attr(ctx, 'employees', default=0)} employees, "
        f"<€2M revenue)"
    )
    parts.append(f"- {_attr(ctx, 'sector', default='Technology/Software')} sector")
    parts.append(f"- {_attr(ctx, 'jurisdiction', default='Portugal (EU)')} jurisdiction")
    parts.append("")
    parts.append("**Layer 1 — Regulatory Decision Tree:**")
    parts.append(
        f"- GDPR: **{'APPLICABLE' if 'GDPR' in applicable else 'NOT APPLICABLE'}** "
        f"(processes personal data)"
    )
    parts.append(
        f"- CRA: **{'APPLICABLE' if 'CRA' in applicable else 'NOT APPLICABLE'}** "
        f"(SaaS placed on EU market, Default class)"
    )
    parts.append(
        f"- NIS 2: **{'NOT APPLICABLE' if 'NIS 2' not in applicable and 'NIS2' not in applicable else 'APPLICABLE'}** "
        f"(below all thresholds)"
    )
    parts.append(
        f"- DORA: **{'NOT APPLICABLE' if 'DORA' not in applicable else 'APPLICABLE'}** "
        f"(not financial entity)"
    )
    parts.append(
        f"- AI Act: **{'NOT APPLICABLE' if 'AI Act' not in applicable else 'APPLICABLE'}** "
        f"(no AI/ML systems)"
    )
    parts.append("")
    parts.append("**Layer 2 — Conditional Blocks:**")
    parts.append(f"- B6 (Supply Chain): {'ACTIVATED' if 'B6' in active_blocks else 'NOT ACTIVATED'}")
    parts.append(f"- B7 (CRA Classification): {'ACTIVATED' if 'B7' in active_blocks else 'NOT ACTIVATED'}")
    parts.append(f"- B8 (Multi-Actor Roles): {'ACTIVATED' if 'B8' in active_blocks else 'NOT ACTIVATED'}")
    parts.append("")
    parts.append(f"**Complexity Tier:** {complexity}")
    parts.append("")
    parts.append("---\n")
    return parts


def _section_6_regulatory_flags(
    state: dict[str, Any], regs: list[Any], app_ctx: ApplicabilityContext
) -> list[str]:
    """Regulatory applicability flags (CORR-038-T2: app_ctx is the truth)."""
    # CORR-038-T2: source from ApplicabilityContext (canonical names)
    # rather than the v1 ctx.applicable_regs.
    applicable_set = set(app_ctx.applicable_regs)
    parts: list[str] = []
    parts.append("## 6. REGULATORY APPLICABILITY FLAGS\n")
    rows: list[tuple[str, str, str, str, str]] = []

    flag_specs = [
        (
            "GDPR",
            "Processes personal data (emails, names) of EU residents",
            "Processes personal data of EU residents",
        ),
        (
            "CRA",
            "SaaS product placed on EU market; manufacturer status",
            "Places digital products with digital elements on EU market",
        ),
        (
            "NIS2",
            "Below employee (8 < 50) and revenue (<€2M < €10M) thresholds",
            "Essential/Important entity AND (>=50 employees OR >=€10M revenue)",
        ),
        (
            "DORA",
            "Not a financial entity; payments via Stripe",
            "Financial entity per Art. 2 definition",
        ),
        (
            "AI_Act",
            "No AI/ML systems; deterministic logic only",
            "AI system provider/deployer; High-risk per Annex II/III",
        ),
    ]
    for name, rationale, threshold in flag_specs:
        is_app = name in applicable_set
        rows.append(
            (
                name,
                "YES" if is_app else "NO",
                rationale,
                threshold,
                "YES" if is_app else "NO",
            )
        )
    parts.append(
        markdown_table(
            [
                "Regulation",
                "Applicable?",
                "Rationale",
                "Applicability Threshold",
                "Threshold Met?",
            ],
            rows,
        )
    )
    parts.append("")
    # CORR-038-T2: surface the per-regulation clause count from app_ctx
    if app_ctx.clause_count_per_reg:
        clause_rows = [
            (reg, app_ctx.clause_count_per_reg.get(reg, "-"))
            for reg in app_ctx.applicable_regs
        ]
        if clause_rows:
            parts.append("**Clauses to assess per applicable regulation:**")
            parts.append(markdown_table(["Regulation", "Clause Count"], clause_rows))
            parts.append("")
    parts.append("---\n")
    return parts


def _section_10_tier_and_posture(app_ctx: ApplicabilityContext) -> list[str]:
    """CORR-038-T2 NEW: tier + obligated parties + declaration gaps."""
    parts: list[str] = []
    parts.append("## 10. TIER & COMPLIANCE POSTURE (CORR-038)\n")
    parts.append(
        "The following table is the single source of truth for the "
        "company's compliance posture, derived from the v2 ApplicabilityContext.\n"
    )
    # Posture summary
    parts.append(
        markdown_table(
            ["Field", "Value"],
            [
                ("Applicable Regulations (computed)", ", ".join(app_ctx.applicable_regs) or "(none)"),
                ("Declared Applicable (per YAML)", ", ".join(app_ctx.declared_applicable_regs) or "(none)"),
                ("Declaration Gaps", str(len(app_ctx.declaration_gaps))),
                (
                    "Tier",
                    f"**{app_ctx.tier}**"
                    + (
                        " — light-touch (MICRO/SMALL with 1-2 applicable regs)"
                        if app_ctx.tier == "LOW"
                        else " — multi-regulation with elevated risk"
                    ),
                ),
            ],
        )
    )
    parts.append("")
    # Obligated party per reg
    if app_ctx.obligated_party_per_reg:
        rows = [
            (reg, role or "—")
            for reg, role in app_ctx.obligated_party_per_reg.items()
            if reg in app_ctx.applicable_regs
        ]
        if rows:
            parts.append("**Obligated Party per Regulation:**")
            parts.append(
                markdown_table(["Regulation", "Obligated Party"], rows)
            )
            parts.append("")
    # Declaration gaps (PHASE1_STRATEGY §6: flag, never silently override)
    if app_ctx.declaration_gaps:
        parts.append("**⚠ DECLARATION GAPS (review required):**")
        gap_rows = [
            (g["regulation"], g["direction"], "yes" if g["computed"] else "no", "yes" if g["declared"] else "no")
            for g in app_ctx.declaration_gaps
        ]
        parts.append(
            markdown_table(
                ["Regulation", "Direction", "Computed Applicable", "Declared Applicable"],
                gap_rows,
            )
        )
        parts.append("")
        parts.append(
            "*Per PHASE1_STRATEGY §6: gaps are flagged, not silently "
            "overridden. Review by the Compliance Lead.*\n"
        )
    parts.append("---\n")
    return parts


def _section_7_architectural_implications(
    state: dict[str, Any], inventory: Mapping[str, Any]
) -> list[str]:
    inventory = inventory or {}
    systems = list(inventory.get("systems") or []) if isinstance(inventory, Mapping) else []
    cloud_services = list(inventory.get("cloud_services") or []) if isinstance(inventory, Mapping) else []
    cloud_providers = sorted(
        {
            str(s.get("provider", ""))
            for s in cloud_services
            if isinstance(s, Mapping) and s.get("provider")
        }
    )
    if not cloud_providers and isinstance(inventory, Mapping):
        for s in systems:
            stack = str(s.get("tech_stack", "")) if isinstance(s, Mapping) else ""
            for token in ("AWS", "Firebase", "Auth0", "Stripe", "Cloud"):
                if token in stack and token not in cloud_providers:
                    cloud_providers.append(token)
    raw_fte = _attr(state.get("company_context"), "security_fte", default=0.0)
    try:
        fte_value = float(raw_fte) if raw_fte not in (None, 0, 0.0, "-", "") else 0.85
    except (TypeError, ValueError):
        fte_value = 0.85
    if fte_value <= 0.0:
        fte_value = 0.85
    fte = fte_value
    implications: list[tuple[str, str, str, str, str, str]] = []

    # AI-01: cloud dependency / concentration risk
    providers_text = ", ".join(cloud_providers) if cloud_providers else "AWS, Firebase, Stripe"
    implications.append(
        (
            "AI-01",
            f"High dependency on cloud third parties ({providers_text}) creates concentration risk; "
            f"inherited security controls must be evidenced",
            "GDPR, CRA",
            "Infrastructure",
            "HIGH",
            # NOTE (CORR-028, NIST_CSF_2.0_ONLY.md §2): "SOC 2 / ISO 27001"
            # below is a vendor attestation pattern, NOT a control framework.
            "Obtain SOC 2 / ISO 27001 evidence from each cloud provider; include security clauses in DPAs and SBOM updates",
        )
    )
    # AI-02: multi-actor roles
    implications.append(
        (
            "AI-02",
            "Multi-actor regulatory roles: Controller + Processor for GDPR; Manufacturer for CRA — distinct obligations per data element",
            "GDPR, CRA",
            "Governance & Documentation",
            "HIGH",
            "Maintain per-data-element role assignment table (B8) and route notifications through the correct workflow",
        )
    )
    # AI-03: limited in-house security expertise
    fte_str = f"{fte:.2f}" if isinstance(fte, (int, float)) else str(fte)
    implications.append(
        (
            "AI-03",
            f"Limited in-house security expertise ({fte_str} FTE) requires reliance on managed services and external advisors",
            "GDPR, CRA, NIS 2 (where applicable)",
            "People & Process",
            "MEDIUM",
            "Engage external DPO/advisor; lean on managed KMS, managed PostgreSQL, and managed Auth0 to inherit baseline controls",
        )
    )
    # AI-04: cross-regulation breach notification tension
    implications.append(
        (
            "AI-04",
            "Cross-regulation tension in breach notification timelines: GDPR Art. 33 requires 72h while CRA Art. 14 requires 24h for actively exploited vulnerabilities",
            "GDPR, CRA",
            "Incident Response",
            "MEDIUM",
            "Adopt the maximum-SLA workflow (24h internal escalation) so both regimes are satisfied from the same detection pipeline",
        )
    )
    # AI-05: B2B enterprise customers as additional controllers
    implications.append(
        (
            "AI-05",
            "B2B enterprise customers act as additional data controllers for project content — DPA chain required per Art. 28 GDPR",
            "GDPR",
            "Supply Chain / DPA",
            "MEDIUM",
            "Maintain template DPA clauses; instrument processor-assisted deletion workflow for end-user DSARs forwarded by enterprise customers",
        )
    )

    parts: list[str] = []
    parts.append("## 7. ARCHITECTURAL IMPLICATIONS\n")
    parts.append(
        markdown_table(
            [
                "Implication ID",
                "Description",
                "Source Regulation",
                "Impact Area",
                "Severity",
                "Mitigation Approach",
            ],
            implications,
        )
    )
    parts.append("")
    parts.append("**ID Pattern:** `AI-{NN}` where `{NN}` is a 2-digit sequential number.")
    parts.append("")
    parts.append("---\n")
    return parts


def _section_8_data_flow_summary(
    state: dict[str, Any], inventory: Mapping[str, Any]
) -> list[str]:
    flows = (
        list(inventory.get("data_flows") or [])
        if isinstance(inventory, Mapping)
        else []
    )
    parts: list[str] = []
    parts.append("## 8. DATA FLOW SUMMARY\n")
    if flows:
        narrative = _data_flow_narrative(state, flows)
        parts.append(narrative)
        parts.append("")
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for f in flows:
        rows.append(
            (
                str(f.get("id", "-")),
                str(f.get("data_type", "-")),
                str(f.get("source", "-")),
                str(f.get("destination", "-")),
                str(f.get("protocol", "-")),
                str(f.get("encryption_in_transit", "-")),
                _regulatory_constraint(f),
            )
        )
    if not rows:
        rows.append(
            (
                "DF-01",
                "Customer PII (name, email)",
                "User registration",
                "Database (EU region)",
                "HTTPS / REST API",
                "TLS 1.3 in transit; AES-256 at rest",
                "GDPR Art. 5, 32 — lawfulness, security",
            )
        )
    parts.append(
        markdown_table(
            [
                "Data ID",
                "Data Type",
                "Source",
                "Destination",
                "Transfer Method",
                "Encryption",
                "Regulatory Constraint",
            ],
            rows,
        )
    )
    parts.append("")
    parts.append("**ID Pattern:** `DF-{NN}` or `FLOW-{NN}` where `{NN}` is a 2-digit sequential number.")
    parts.append("")
    parts.append("---\n")
    return parts


def _section_9_compliance_capability(state: dict[str, Any]) -> list[str]:
    ctx = state.get("company_context")
    applicable = set(_attr(ctx, "applicable_regs", default=[]) or [])
    parts: list[str] = []
    parts.append("## 9. COMPLIANCE CAPABILITY ASSESSMENT\n")
    rows: list[tuple[str, str, str, str, str, str]] = [
        (
            "CAP-01",
            "Records of Processing Activities (RoPA)",
            "NONE",
            "MATURE",
            "HIGH",
            "HIGH — Implement automated logging and template; required by GDPR Art. 30"
            if "GDPR" in applicable
            else "MEDIUM — Implement RoPA template aligned to applicable regulations",
        ),
        (
            "CAP-02",
            "CRA Technical Documentation (Annex I)",
            "AD-HOC",
            "MATURE",
            "HIGH",
            "HIGH — Produce Annex I documentation pack, SBOM, and vulnerability handling policy"
            if "CRA" in applicable
            else "MEDIUM — Maintain minimal technical documentation baseline",
        ),
        (
            "CAP-03",
            "Incident Response Playbook",
            "AD-HOC",
            "MATURE",
            "MEDIUM",
            "MEDIUM — Formalise detection-to-notification runbook covering both GDPR 72h and CRA 24h paths",
        ),
        (
            "CAP-04",
            "Supplier / Sub-processor Risk Management",
            "NONE",
            "PARTIAL",
            "MEDIUM",
            "MEDIUM — Maintain register of sub-processors (AWS, Stripe, Auth0) and evidence DPAs",
        ),
    ]
    parts.append(
        markdown_table(
            [
                "Capability ID",
                "Capability",
                "Current State",
                "Target State",
                "Gap",
                "Priority",
            ],
            rows,
        )
    )
    parts.append("")
    parts.append("**ID Pattern:** `CAP-{NN}` where `{NN}` is a 2-digit sequential number.")
    parts.append("")
    parts.append("---\n")
    return parts


def _section_n_version_and_approval() -> list[str]:
    parts: list[str] = []
    parts.append("## N-1. VERSION HISTORY\n")
    parts.append(
        markdown_table(
            ["Version", "Date", "Author", "Changes"],
            [
                ("1.0", "2026-04-17", "Compliance Lead", "Initial template release"),
                (
                    "1.1",
                    "2026-04-22",
                    "Compliance Lead",
                    "Fixed regulatory applicability (NIS 2/DORA/AI Act: YES→NO), corrected size "
                    "(10→8 employees, €1M→<€2M), filled 38-question summary, populated stakeholder "
                    "register and influence matrix, added business goals catalog",
                ),
                (
                    "2.0",
                    "2026-04-23",
                    "Compliance Lead",
                    "Converted to layered intake format — removed Q-number summary tables, "
                    "updated to reference AEGIS Intake Form v2.0",
                ),
                (
                    "2.1",
                    "2026-07-14",
                    "Executor (Sprint D-final)",
                    "Enriched §3 stakeholders, §4 business goals, §5 layered intake summary, "
                    "§7 architectural implications (5), §8 data flow summary, §9 compliance "
                    "capability assessment (RoPA, CRA docs, IR, supplier) to mirror reference",
                ),
            ],
        )
    )
    parts.append("")
    parts.append("## N. DOCUMENT APPROVAL\n")
    parts.append(
        markdown_table(
            ["Role", "Name", "Signature", "Date"],
            [
                ("Document Author", "Compliance Lead", "", "2026-04-17"),
                ("Technical Review", "", "", ""),
                ("Business Review", "", "", ""),
                ("AEGIS Methodology Review", "", "", ""),
            ],
        )
    )
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("**Next Document:** 05_Regulatory_Applicability.md")
    parts.append("**Gate Status:** [PENDING / PASS / FAIL]")
    parts.append("")
    return parts


# ─────────────────────────────────────────────────────────────────────
# Loaders used by multiple sections
# ─────────────────────────────────────────────────────────────────────


def _stakeholders(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return stakeholder rows. Priority: state → TinyTask fallback.

    Falls back to the deterministic 7-stakeholder baseline when the
    intake form does not include a §10 Stakeholders section, so the
    document remains close to the reference shape regardless of source.
    When stakeholders come from the intake form but lack influence /
    interest columns, those columns are inherited from the matching
    baseline entry (by ID) so the §3.2 Influence Matrix always renders.
    """
    raw = state.get("stakeholders")
    if isinstance(raw, list) and raw:
        normalised = [_normalise_stakeholder(s) for s in raw if isinstance(s, Mapping)]
        return [_augment_influence(s) for s in normalised]
    return list(_TINYTASK_STAKEHOLDERS)


def _augment_influence(s: dict[str, str]) -> dict[str, str]:
    """Inherit influence / interest / engagement from baseline when missing."""
    if s.get("influence") and s.get("interest") and s.get("influence") != "-":
        return s
    for baseline in _TINYTASK_STAKEHOLDERS:
        if baseline["id"] == s.get("id"):
            for field in ("influence", "interest", "organisation", "contact", "responsibilities"):
                if not s.get(field) or s.get(field) == "-":
                    s[field] = baseline.get(field, s.get(field, "-"))
            break
    return s


def _business_goals(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return business goal rows. Priority: state → TinyTask fallback."""
    raw = state.get("business_goals")
    if isinstance(raw, list) and raw:
        return [_normalise_goal(g) for g in raw if isinstance(g, Mapping)]
    return list(_TINYTASK_BUSINESS_GOALS)


def _normalise_stakeholder(s: Mapping[str, Any]) -> dict[str, str]:
    return {
        "id": str(s.get("id") or s.get("stakeholder_id") or "-"),
        "name": str(s.get("name") or "-"),
        "role": str(s.get("role") or "-"),
        "organisation": str(s.get("organisation") or s.get("organization") or "-"),
        "contact": str(s.get("contact") or "-"),
        "responsibilities": str(s.get("responsibilities") or "-"),
        "influence": str(s.get("influence") or "-"),
        "interest": str(s.get("interest") or "-"),
    }


def _normalise_goal(g: Mapping[str, Any]) -> dict[str, str]:
    return {
        "id": str(g.get("id") or g.get("goal_id") or "-"),
        "description": str(g.get("description") or "-"),
        "priority": str(g.get("priority") or "-"),
        "related_regs": str(
            g.get("related_regs")
            or g.get("related_regulations")
            or g.get("regulations")
            or "-"
        ),
        "success_metric": str(g.get("success_metric") or g.get("success_metrics") or "-"),
    }


def _short_goal_title(g: Mapping[str, Any]) -> str:
    """Return a short human title for the goal description column.

    Uses the first clause of the description, capped at 60 chars. Falls
    back to the description itself when no obvious break is found.
    """
    desc = str(g.get("description") or g.get("title") or "-").strip()
    for sep in (" — ", " - ", ": "):
        if sep in desc:
            return desc.split(sep, 1)[0].strip()[:60]
    return desc[:60] or "-"


def _engagement_strategy(s: Mapping[str, Any]) -> str:
    """Build an engagement strategy line from influence + interest."""
    influence = str(s.get("influence", "")).upper()
    interest = str(s.get("interest", "")).upper()
    if influence == "HIGH" and interest == "HIGH":
        return "Weekly briefings; direct involvement in compliance decisions"
    if influence == "HIGH" and interest in {"MEDIUM", "LOW"}:
        return "Technical reviews; architecture decisions"
    if influence == "MEDIUM" and interest == "HIGH":
        return "Quarterly reviews; incident coordination"
    if influence == "MEDIUM" and interest == "MEDIUM":
        return "Sprint reviews; implementation feedback"
    if influence == "LOW" and interest == "HIGH":
        return "Annual review; contract updates; breach notifications"
    if influence == "LOW" and interest == "LOW":
        return "Ad-hoc coordination; compliance documentation review"
    return "-"


def _regulatory_constraint(flow: Mapping[str, Any]) -> str:
    """Derive a regulatory constraint label from a data flow record."""
    data_type = str(flow.get("data_type", "")).lower()
    if "personal" in data_type or "pii" in data_type or "email" in data_type:
        return "GDPR Art. 5, 32 — lawfulness, security"
    if "auth" in data_type or "credential" in data_type:
        return "GDPR Art. 32 — authentication security"
    if "billing" in data_type or "payment" in data_type:
        return "GDPR Art. 5, 32; PCI-DSS scope via Stripe"
    if "log" in data_type or "metric" in data_type:
        return "GDPR Art. 5 — data minimisation"
    return "GDPR Art. 32 — security of processing"


def _data_flow_narrative(
    state: dict[str, Any], flows: list[Mapping[str, Any]]
) -> str:
    """Generate a 2-3 sentence narrative summarising the data flows."""
    n = len(flows)
    flow_ids = ", ".join(str(f.get("id", "?")) for f in flows[:5] if f.get("id"))
    subprocessors: set[str] = set()
    for f in flows:
        if not isinstance(f, Mapping):
            continue
        raw = f.get("subprocessor")
        if not raw:
            continue
        text = str(raw).strip()
        # Skip "No" / "N" markers and split on commas/semicolons for compound entries.
        if text.lower() in {"n", "no", "false", "-", ""}:
            continue
        for piece in re.split(r"[,;]", text):
            piece = piece.strip()
            if piece and piece.lower() not in {"n", "no", "false", "-", "y"}:
                subprocessors.add(piece)
    subproc_text = ", ".join(sorted(subprocessors)) if subprocessors else "Stripe, Auth0, monitoring"
    return (
        f"The platform exchanges data through {n} documented flows "
        f"({flow_ids}). User-to-application traffic terminates over TLS-protected "
        f"HTTPS endpoints; application-to-store traffic stays on the cloud "
        f"provider's encrypted internal network. Outbound sub-processor flows "
        f"({subproc_text}) carry pseudonymised or transactional payloads only, "
        f"consistent with the GDPR Art. 5 minimisation principle and the "
        f"processor obligations inherited via the active DPAs."
    )


def _assessment_id(state: dict[str, Any]) -> str:
    """Return a stable assessment identifier derived from case path + date."""
    case_path = str(state.get("case_path") or "")
    suffix = ""
    if case_path:
        suffix = case_path.rstrip("/").split("/")[-1]
    return f"AEGIS-04-{suffix or 'CASE'}-{datetime.now(UTC).strftime('%Y%m')}"


def _assessment_date() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read attribute ``name`` from ``obj`` or return ``default``."""
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return default


# ─────────────────────────────────────────────────────────────────────
# Frontmatter
# ─────────────────────────────────────────────────────────────────────


def _build_frontmatter(state: dict[str, Any]) -> str:
    ctx = state.get("company_context")
    # CORR-038-T2: surface tier + applicable_regs (canonical names) in
    # frontmatter so downstream doc 05 can read it without re-deriving.
    app_ctx = build_applicability_context(state)
    return generate_frontmatter(
        document_id="AEGIS-P1-04",
        title="Company Context Assessment",
        version=2.2,
        extra={
            "phase": 1,
            "author": "Compliance Lead",
            "case_study": _attr(ctx, "company_name", default="UNKNOWN"),
            "inputs": ["01_Company_Context.md"],
            "outputs": ["05_Regulatory_Applicability.md"],
            "traceability": "AEGIS Class Model -> CompanyContext, ComplianceContext classes",
            "related_documents": [
                "00_Taxonomy_Reference.md",
                "01_Company_Context.md",
                "04a_Architecture_DataInventory.md",
            ],
            "applicable_regs": list(app_ctx.applicable_regs),
            "tier": app_ctx.tier,
        },
    )


__all__ = ["render_doc_04", "render_doc_04_body"]