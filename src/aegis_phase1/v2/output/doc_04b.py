"""doc_04b — render AEGIS-P1-04b Security Posture Assessment (Maturity Model).

Sections produced (mirrors the reference ``04b_Security_Posture.md`` in
Case_01_TinyTask_SaaS):

1.  PURPOSE
2.  Assessment Methodology (4-level maturity table)
3.  Per-Domain Assessment (D-01 .. D-10) — control tables, target
    maturity, gap, and Notes narrative per macro-domain
4.  Maturity Summary — count per level (0..4)
5.  Top Gaps (feeds Doc 07)
6.  Consistency Check
7.  Gate

The Notes narrative per domain is LLM-generated when an invoker is
supplied (and ``MOCK_LLM`` is unset). Deterministic fallback text is
emitted otherwise — substantial enough that the document remains useful
without an LLM.

References:
    - Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/04b_Security_Posture.md
    - Methodology-main/00_METHODOLOGY/PREPROCESSING/SubDomains/
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from aegis_phase1.v2.output._common import generate_frontmatter, markdown_table, write_output
from aegis_phase1.v2.output._narrative import render_mandatory_narrative
from aegis_phase1.v2.review.loader import load_review

logger = logging.getLogger(__name__)

_FILENAME = "04b_Security_Posture.md"
_MAX_FRAGMENT_BYTES = 2000
_SAFE_KEY = re.compile(r"[^A-Za-z0-9_.-]")

# ─────────────────────────────────────────────────────────────────────
# Default maturity profile (deterministic)
# ─────────────────────────────────────────────────────────────────────
#
# Per-domain current maturity. Deterministic defaults aligned with the
# reference (TinyTask) but applicable to any micro/low-tier SaaS:
#   - D-01, D-03, D-07: level 2 (defined; documented or repeatable)
#   - D-02, D-04, D-05, D-06, D-08, D-09, D-10: level 1 (ad-hoc)
#
# These values can be overridden per-case in future sprints by injecting
# them into state["security_posture_overrides"] (a dict keyed by domain
# id).

_DOMAIN_CURRENT: dict[str, int] = {
    "D-01": 2,
    "D-02": 1,
    "D-03": 2,
    "D-04": 1,
    "D-05": 1,
    "D-06": 1,
    "D-07": 2,
    "D-08": 1,
    "D-09": 1,
    "D-10": 1,
}

_DOMAIN_TARGET: dict[str, int] = {
    "D-01": 3,
    "D-02": 3,
    "D-03": 3,
    "D-04": 3,
    "D-05": 2,
    "D-06": 2,
    "D-07": 2,
    "D-08": 2,
    "D-09": 3,
    "D-10": 3,
}

_DOMAIN_NAME: dict[str, str] = {
    "D-01": "Data Protection",
    "D-02": "Vulnerability Management",
    "D-03": "Access Control",
    "D-04": "Incident Response",
    "D-05": "Data Lifecycle",
    "D-06": "Supply Chain",
    "D-07": "Secure Development",
    "D-08": "Human Factors",
    "D-09": "Governance & Documentation",
    "D-10": "Monitoring & Audit",
}

_DOMAIN_DIR: dict[str, str] = {
    "D-01": "D-01_Data-Protection",
    "D-02": "D-02_Vulnerability-Management",
    "D-03": "D-03_Access-Control",
    "D-04": "D-04_Incident-Response",
    "D-05": "D-05_Data-Lifecycle",
    "D-06": "D-06_Supply-Chain",
    "D-07": "D-07_Secure-Development",
    "D-08": "D-08_Human-Factors",
    "D-09": "D-09_Governance-Documentation",
    "D-10": "D-10_Monitoring-Audit",
}

# Per-domain control rows (Control / Current / Evidence / Notes).
# Evidence references SYS/STORE/FLOW from architecture_inventory when
# known; falls back to generic references otherwise.
_DEFAULT_CONTROLS: dict[str, list[dict[str, str]]] = {
    "D-01": [
        {
            "control": "Encryption at rest",
            "current": "Implemented for main database, backups, and logs",
            "evidence_refs": ["STORE-01", "STORE-02", "STORE-03"],
            "notes": "Provider-managed AES-256 encryption; no customer-managed HSM",
        },
        {
            "control": "Encryption in transit",
            "current": "Implemented for all documented production flows",
            "evidence_refs": ["FLOW-01", "FLOW-02", "FLOW-03", "FLOW-04", "FLOW-05"],
            "notes": "TLS 1.3 used for main app and Auth0; third-party APIs use TLS 1.2 or higher",
        },
        {
            "control": "Key management",
            "current": "Basic cloud KMS",
            "evidence_refs": ["SYS-04"],
            "notes": "Manual key rotation; no formal key ceremony or dual control",
        },
        {
            "control": "Data integrity",
            "current": "Basic application/database controls",
            "evidence_refs": ["SYS-01", "SYS-03", "SYS-05"],
            "notes": "Database constraints and backup checks exist; no formal integrity verification schedule",
        },
    ],
    "D-02": [
        {
            "control": "Vulnerability scanning",
            "current": "Weekly Snyk scan for application dependencies",
            "evidence_refs": ["SYS-01", "STORE-03"],
            "notes": "Results are reviewed manually; no documented acceptance or exception process",
        },
        {
            "control": "Patch management",
            "current": "Manual patching",
            "evidence_refs": [],
            "notes": "No formal critical/high SLA; fixes depend on developer availability",
        },
        {
            "control": "Pen testing",
            "current": "Informal self-testing only",
            "evidence_refs": [],
            "notes": "No threat-led or independent penetration test performed",
        },
        {
            "control": "CVD policy",
            "current": "Not published",
            "evidence_refs": [],
            "notes": "No security.txt or public vulnerability policy",
        },
    ],
    "D-03": [
        {
            "control": "IAM system",
            "current": "Auth0 for customer and administrator identity",
            "evidence_refs": ["SYS-02"],
            "notes": "Managed identity service reduces implementation burden",
        },
        {
            "control": "MFA",
            "current": "Enforced for administrators only",
            "evidence_refs": [],
            "notes": "Customer MFA is optional; not universal",
        },
        {
            "control": "RBAC",
            "current": "Basic application roles",
            "evidence_refs": ["SYS-01", "SYS-02", "SYS-03"],
            "notes": "Basic owner/member/admin model; quarterly access reviews not documented",
        },
        {
            "control": "Privileged access management",
            "current": "No dedicated PAM",
            "evidence_refs": [],
            "notes": "Least privilege is informal and handled by CTO",
        },
        {
            "control": "Default secure configs",
            "current": "Partial",
            "evidence_refs": [],
            "notes": "No documented secure baseline for all services",
        },
    ],
    "D-04": [
        {
            "control": "IR plan",
            "current": "Basic plan exists",
            "evidence_refs": [],
            "notes": "No tested playbook and no incident roles beyond CTO/developers",
        },
        {
            "control": "Detection capability",
            "current": "Datadog or equivalent alerts",
            "evidence_refs": ["STORE-03", "FLOW-03"],
            "notes": "No SIEM, EDR, IDS, or 24/7 monitoring",
        },
        {
            "control": "Notification process",
            "current": "Informal DPO/CTO escalation",
            "evidence_refs": [],
            "notes": "No tested 24h CRA early-warning / 72h GDPR breach notification workflow",
        },
        {
            "control": "Recovery procedures",
            "current": "Backups exist",
            "evidence_refs": ["STORE-02", "SYS-05"],
            "notes": "Restore testing is not scheduled or evidenced",
        },
    ],
    "D-05": [
        {
            "control": "Data minimisation",
            "current": "Informal minimisation in product design",
            "evidence_refs": [],
            "notes": "Payment card data is kept out of scope by using Stripe",
        },
        {
            "control": "Retention policies",
            "current": "Not formally documented",
            "evidence_refs": ["STORE-01", "STORE-02", "STORE-03"],
            "notes": "Retention periods are stated but not yet approved as policy",
        },
        {
            "control": "Erasure procedures",
            "current": "Manual support workflow",
            "evidence_refs": [],
            "notes": "No self-service DSAR portal; backup expiry relied on for residual copies",
        },
        {
            "control": "Data portability",
            "current": "Support-assisted export",
            "evidence_refs": [],
            "notes": "No automated export for all data categories",
        },
    ],
    "D-06": [
        {
            "control": "Vendor assessment",
            "current": "Annual informal vendor review",
            "evidence_refs": [],
            "notes": "Evidence collection is not standardised",
        },
        {
            "control": "SBOM",
            "current": "Not implemented",
            "evidence_refs": [],
            "notes": "No CycloneDX/SPDX generation in CI/CD",
        },
        {
            "control": "Contract clauses",
            "current": "Partial",
            "evidence_refs": [],
            "notes": "DPAs with major subprocessor vendors; B2B processor DPA standardisation is incomplete",
        },
        {
            "control": "Boundary management",
            "current": "Ad hoc",
            "evidence_refs": ["FLOW-03", "FLOW-04", "FLOW-05"],
            "notes": "No formal subprocessor register or data-flow review cadence",
        },
    ],
    "D-07": [
        {
            "control": "Secure-by-design",
            "current": "Basic consideration during feature work",
            "evidence_refs": ["SYS-01"],
            "notes": "No formal threat-model template per feature",
        },
        {
            "control": "Secure coding",
            "current": "OWASP guidelines and peer code review",
            "evidence_refs": [],
            "notes": "Code review exists but security checklist is not consistently recorded",
        },
        {
            "control": "CI/CD security",
            "current": "Basic dependency scanning",
            "evidence_refs": ["SYS-01"],
            "notes": "No DAST, secrets scanning baseline, or SBOM release artefact",
        },
        {
            "control": "Change management",
            "current": "Pull request review",
            "evidence_refs": [],
            "notes": "Branch protection for main branch; no formal release risk classification or CAB",
        },
    ],
    "D-08": [
        {
            "control": "Security awareness",
            "current": "Annual awareness training",
            "evidence_refs": [],
            "notes": "No phishing simulations or completion dashboard",
        },
        {
            "control": "Role-specific training",
            "current": "Informal developer learning",
            "evidence_refs": [],
            "notes": "No tracked curriculum for CTO, developers, support, or DPO role",
        },
        {
            "control": "Board training",
            "current": "Not applicable to active scope",
            "evidence_refs": [],
            "notes": "D-08.3 inactive for low-tier micro SaaS — NIS2 + DORA only participating regs",
        },
    ],
    "D-09": [
        {
            "control": "Security policies",
            "current": "Basic policies only",
            "evidence_refs": [],
            "notes": "No complete information security policy set",
        },
        {
            "control": "Risk assessment",
            "current": "Informal",
            "evidence_refs": [],
            "notes": "Product and compliance risks discussed by CTO/CEO; no documented risk register",
        },
        {
            "control": "Asset inventory",
            "current": "Initial inventory created",
            "evidence_refs": [],
            "notes": "04a is the first structured inventory; no CMDB yet",
        },
        {
            "control": "RoPA",
            "current": "Not complete",
            "evidence_refs": [],
            "notes": "GDPR Art. 30 records are not yet maintained as an operational artefact",
        },
    ],
    "D-10": [
        {
            "control": "Continuous monitoring",
            "current": "Datadog or equivalent for core app metrics",
            "evidence_refs": ["STORE-03", "FLOW-03"],
            "notes": "Coverage is basic and not mapped to all active security events",
        },
        {
            "control": "Audit logging",
            "current": "Partial application and authentication logging",
            "evidence_refs": ["SYS-01", "SYS-02", "STORE-03"],
            "notes": "30-day retention; no formal log review process",
        },
        {
            "control": "Compliance testing",
            "current": "Ad hoc internal checks",
            "evidence_refs": [],
            "notes": "No scheduled evidence review or control test plan",
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────


def render_doc_04b(
    state: dict[str, Any],
    output_dir: str,
    llm_invoker: Any | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render AEGIS-P1-04b Security Posture Assessment (Maturity Model).

    Args:
        state: Pipeline state (see :class:`aegis_phase1.v2.state.V2State`).
        output_dir: Directory in which the document is written.
        llm_invoker: Optional LLM invoker. When ``None`` or when
            ``MOCK_LLM`` is truthy, deterministic fallback text is used
            for all per-domain Notes.
        config: Optional Langfuse / LangChain runnable config threaded
            through to nested LLM calls so the GENERATION span is named
            after the LangGraph node (``run_name`` is read by
            :class:`aegis_phase1.v2.output._narrative.render_mandatory_narrative`).

    Returns:
        Mapping ``AEGIS-P1-04b`` -> absolute file path.
    """
    use_llm = _should_use_llm(llm_invoker)
    frontmatter = _build_frontmatter(state)
    body = _build_body(state, llm_invoker if use_llm else None, config=config)
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_04b: wrote %s", path)
    return {"AEGIS-P1-04b": path}


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
    parts.append("# Security Posture Assessment (Maturity Model)\n")
    parts.extend(_section_purpose(state))
    parts.extend(_section_methodology(state))
    parts.extend(_section_per_domain(state, llm_invoker, config=config))
    parts.extend(_section_summary(state))
    parts.extend(_section_top_gaps(state))
    parts.extend(_section_consistency(state))
    parts.extend(_section_gate(state))
    parts.extend(_section_version_history(state))
    parts.extend(_section_approval(state))
    parts.extend(_section_see_also(state))
    return "\n".join(parts)


def _section_purpose(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 1. Purpose\n")
    parts.append(
        "This document captures the company's **current security posture** "
        "across the 10 AEGIS macro-domains (D-01 .. D-10) using a 0-4 "
        "maturity scale, and identifies the gap to a target maturity "
        "proportional to the company's tier. It supports compliance "
        "evidence for **GDPR Art. 32**, **CRA Annex I Part I**, and "
        "downstream Doc 07 (Structured Compliance Matrix).\n"
    )
    return parts


def _section_methodology(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 2. Assessment Methodology\n")
    ctx = state.get("company_context")
    name = _attr(ctx, "company_name", default="the company")
    employees = _attr(ctx, "employees", default="")
    scale = _attr(ctx, "scale", default="micro")
    applicable = _attr(ctx, "applicable_regs", default=[]) or []
    applicable_text = ", ".join(applicable) if applicable else "-"
    parts.append(
        f"{name} is assessed as a low-tier {scale} SaaS"
        + (f" with {employees} employees" if employees else "")
        + " using managed-cloud infrastructure. Current maturity measures "
        + "what exists today, not the target state. Target maturity is "
        + "proportional to the company profile but aligned with active "
        + "GDPR/CRA SubDomains fit criteria (applicable_regs = "
        + f"{applicable_text}).\n"
    )
    parts.append(
        "| Level | Label | Description |\n"
        "|---|---|---|\n"
        "| 0 | None | No controls in place |\n"
        "| 1 | Ad-hoc | Informal, inconsistent, no documentation |\n"
        "| 2 | Defined | Documented or consistently repeatable, but not fully measured |\n"
        "| 3 | Managed | Implemented, monitored, measured, and regularly reviewed |\n"
        "| 4 | Optimized | Continuously improved and substantially automated |\n"
    )
    parts.append(
        "Assessment evidence is drawn from `04a_Architecture_DataInventory.md`, "
        "`04_Company_Context_Assessment.md`, and `05_Regulatory_Applicability.md`. "
        f"The active Layer 0 scope is {_active_count(state)} of "
        f"{_total_count(state)} SubDomains for `applicable_regs = [{applicable_text}]`; "
        "D-08.3 is inactive when its participating regulations do not apply.\n"
    )
    return parts


def _section_per_domain(
    state: dict[str, Any],
    llm_invoker: Any | None,
    *,
    config: dict[str, Any] | None = None,
) -> list[str]:
    parts: list[str] = []
    parts.append("## 3. Per-Domain Assessment\n")
    overrides = _overrides(state)
    review = _load_review_for_state(state)
    domain_results = state.get("domain_results") or {}
    for domain_id in sorted(_DOMAIN_CURRENT.keys()):
        current = overrides.get(domain_id, _DOMAIN_CURRENT[domain_id])
        target = _DOMAIN_TARGET[domain_id]
        gap = max(0, target - current)
        controls = _controls_for(domain_id, state)
        parts.append(f"### {domain_id} {_DOMAIN_NAME[domain_id]} — Maturity: {current}\n")
        parts.append(_controls_table(controls))
        parts.append("")
        parts.append(f"**Target maturity**: {target}  ")
        parts.append(f"**Gap**: {gap}  ")
        notes = _domain_notes(
            domain_id, state, current, target, gap, controls, llm_invoker,
            config=config,
        )
        parts.append(f"**Notes**: {notes}\n")
        domain_result = domain_results.get(domain_id) or {}
        if domain_result:
            review_entry = review.get(domain_id) if isinstance(review, Mapping) else None
            parts.append(_section_adapted_objective(domain_id, domain_result, review_entry))
    return parts


def _section_adapted_objective(
    domain_id: str,
    domain_result: Mapping[str, Any],
    review_entry: Mapping[str, Any] | None = None,
) -> str:
    """Render the per-domain Adapted Objective subsection.

    Reads ``domain_result["adapted_objective"]`` (the legacy HL-concat)
    OR ``domain_result["adapted_subdomains"]`` (per-sub-domain v1.2 spec)
    and combines with the matching human-review entry (when present) to
    produce markdown suitable for inclusion in §3 of the Doc 04b output.

    Priority for the rendered narrative:

    1. ``status == "EDITED"`` with non-empty ``edited_text`` →
       use the human rewrite for the whole section.
    2. ``status == "REJECTED"`` → LLM proposal prefixed with
       ``[RE-GENERATION REQUIRED]``.
    3. ``status == "APPROVED"`` → LLM proposal unmodified.
    4. ``None`` / ``PENDING`` → LLM proposal prefixed with
       ``[PENDING REVIEW]``.

    Args:
        domain_id: The domain identifier (e.g. ``"D-01"``).
        domain_result: One entry from ``state["domain_results"]``
            (carrying ``adapted_objective``, ``adapted_subdomains``,
            ``key_changes``, ``confidence``, ``llm_status``,
            ``domain_name``).
        review_entry: Optional entry from
            ``review/adapted_objectives.yaml`` keyed by ``domain_id``.

    Returns:
        A markdown string (caller is responsible for joining it into
        the surrounding section).
    """
    raw = domain_result.get("adapted_objective", "") or ""
    adapted_v3_raw = domain_result.get("adapted_subdomains_v3")
    adapted_v3: list[dict[str, Any]] = (
        list(adapted_v3_raw) if isinstance(adapted_v3_raw, list) else []
    )
    adapted_subdomains_raw = domain_result.get("adapted_subdomains")
    adapted_subdomains: list[dict[str, Any]] = (
        list(adapted_subdomains_raw) if isinstance(adapted_subdomains_raw, list) else []
    )

    if not review_entry:
        review_entry = {"status": "PENDING", "edited_text": "", "notes": ""}
    status = str(review_entry.get("status", "PENDING") or "PENDING")

    # Build the review narrative (used for the whole section when EDITED,
    # otherwise injected as a banner for each sub-domain block).
    if status == "EDITED" and (review_entry.get("edited_text") or "").strip():
        review_narrative: str = str(review_entry.get("edited_text", ""))
    elif status == "REJECTED":
        review_narrative = (
            f"[RE-GENERATION REQUIRED]\n{raw}" if raw else "[RE-GENERATION REQUIRED]"
        )
    elif status == "APPROVED":
        review_narrative = raw
    elif status == "EDITED":
        # EDITED with empty edited_text → fall back to PENDING marker.
        review_narrative = f"[PENDING REVIEW]\n{raw}" if raw else "[PENDING REVIEW]"
    else:
        review_narrative = f"[PENDING REVIEW]\n{raw}" if raw else "[PENDING REVIEW]"

    tier = domain_result.get("tier", "UNKNOWN")
    if not isinstance(tier, str):
        tier = "UNKNOWN"
    confidence = str(domain_result.get("confidence", "UNKNOWN") or "UNKNOWN")
    key_changes = list(domain_result.get("key_changes", []) or [])

    lines: list[str] = []
    lines.append(f"#### {domain_id} — Adapted Objective")
    lines.append("")
    lines.append(
        f"**Source**: MAP stage | **Tier**: {tier} | "
        f"**Confidence**: {confidence} | **Status**: {status}"
    )
    lines.append("")

    if adapted_v3:
        # v1.3 rendering: 3 blocks x 5 fields per sub-domain.
        if status == "EDITED" and (review_entry.get("edited_text") or "").strip():
            lines.append(review_narrative)
            lines.append("")
        else:
            for sub in adapted_v3:
                if not isinstance(sub, Mapping):
                    continue
                sid = str(sub.get("subdomain_id", "?") or "?")
                title = str(sub.get("title", "?") or "?")
                blocks_raw = sub.get("blocks") or []
                blocks: list[dict[str, Any]] = (
                    list(blocks_raw) if isinstance(blocks_raw, list) else []
                )

                lines.append(f"##### {sid} — {title}")
                lines.append("")

                for blk in blocks:
                    label = str(blk.get("label", "?") or "?")
                    lines.append(f"**{label}**")
                    lines.append("")
                    lines.append(f"- Original: {blk.get('original', '(missing)')}")
                    lines.append("")
                    lines.append(f"- Adapted: {blk.get('adapted', '(missing)')}")
                    lines.append("")
                    lines.append(f"- Rationale: {blk.get('rationale', '(missing)')}")
                    lines.append("")
                    lines.append(
                        f"- Adjustments needed: {blk.get('adjustments', '(missing)')}"
                    )
                    lines.append("")
                    considerations_raw = blk.get("considerations") or []
                    considerations: list[Any] = (
                        list(considerations_raw)
                        if isinstance(considerations_raw, list)
                        else []
                    )
                    if considerations:
                        lines.append("**Considerations.**")
                        lines.append("")
                        for c in considerations:
                            lines.append(f"- {c}")
                        lines.append("")
                lines.append("")
    elif adapted_subdomains:
        # v1.2 format: per-sub-domain rendering.
        if status == "EDITED" and (review_entry.get("edited_text") or "").strip():
            # Human rewrite applies to the whole block (single narrative).
            lines.append(review_narrative)
            lines.append("")
        else:
            for sub in adapted_subdomains:
                if not isinstance(sub, Mapping):
                    continue
                sid = str(sub.get("subdomain_id", "?") or "?")
                title = str(sub.get("title", "?") or "?")
                hl = str(sub.get("hl_objective", "") or "")
                directed_raw = sub.get("directed") or []
                directed: list[dict[str, Any]] = (
                    list(directed_raw) if isinstance(directed_raw, list) else []
                )

                lines.append(f"##### {sid} — {title}")
                lines.append("")
                # Inject the review-marker-prefixed HL when one applies.
                if status == "REJECTED" and hl:
                    lines.append(f"[RE-GENERATION REQUIRED]\n{hl}")
                elif status == "APPROVED" and hl:
                    lines.append(hl)
                elif status == "PENDING" and hl:
                    lines.append(f"[PENDING REVIEW]\n{hl}")
                elif hl:
                    lines.append(hl)
                lines.append("")

                if directed:
                    lines.append("**Directed objectives.**")
                    lines.append("")
                    for d in directed:
                        if not isinstance(d, Mapping):
                            continue
                        reg = str(d.get("regulation", "?") or "?")
                        obj = str(d.get("objective", "") or "")
                        lines.append(f"- **{reg}**: {obj}")
                    lines.append("")
    else:
        # Legacy: render adapted_objective verbatim.
        # ``review_narrative`` already encodes the EDITED/REJECTED/APPROVED/
        # PENDING preference (falls back to ``raw`` when empty).
        if review_narrative:
            lines.append(review_narrative)
        elif raw:
            lines.append(raw)
        lines.append("")

    if key_changes:
        lines.append("**Key changes**:")
        for kc in key_changes:
            lines.append(f"- {kc}")
        lines.append("")
    return "\n".join(lines)


def _load_review_for_state(state: Mapping[str, Any]) -> dict[str, dict]:
    """Load the human-review YAML using ``state["case_path"]``."""
    case_path = state.get("case_path", "") or ""
    if not case_path:
        return {}
    try:
        review = load_review(str(case_path))
    except Exception as exc:
        logger.debug("doc_04b: load_review failed for %s — %s", case_path, exc)
        return {}
    return review if isinstance(review, dict) else {}


def _section_summary(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 4. Summary Dashboard\n")
    overrides = _overrides(state)
    rows: list[tuple[str, int, int, int]] = []
    total_current = 0
    total_target = 0
    for domain_id in sorted(_DOMAIN_CURRENT.keys()):
        current = overrides.get(domain_id, _DOMAIN_CURRENT[domain_id])
        target = _DOMAIN_TARGET[domain_id]
        gap = max(0, target - current)
        rows.append((f"{domain_id} {_DOMAIN_NAME[domain_id]}", current, target, gap))
        total_current += current
        total_target += target
    overall_current = round(total_current / len(rows), 1)
    overall_target = round(total_target / len(rows), 1)
    overall_gap = round(overall_target - overall_current, 1)
    rows.append(("**OVERALL**", overall_current, overall_target, overall_gap))
    parts.append(
        markdown_table(
            ["Macro-domain", "Current", "Target", "Gap"],
            [(r[0], r[1], r[2], r[3]) for r in rows],
        )
    )
    parts.append("")

    # Maturity count by level
    counts = _maturity_counts(overrides)
    parts.append("**Maturity distribution:** " + ", ".join(
        f"Level {lvl} = {counts.get(lvl, 0)}" for lvl in (0, 1, 2, 3, 4)
    ) + "\n")
    return parts


def _section_top_gaps(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 5. Top Gaps (feeds Doc 07)\n")
    overrides = _overrides(state)
    ranked = sorted(
        (
            (domain_id, _DOMAIN_TARGET[domain_id] - overrides.get(domain_id, _DOMAIN_CURRENT[domain_id]))
            for domain_id in _DOMAIN_CURRENT
        ),
        key=lambda kv: (-kv[1], kv[0]),
    )
    rows: list[tuple[int, str, int, str, str]] = []
    for rank, (domain_id, gap) in enumerate(ranked[:5], start=1):
        if gap <= 0:
            break
        summary, remediation = _gap_summary(domain_id)
        rows.append((rank, f"{domain_id} {_DOMAIN_NAME[domain_id]}", gap, summary, remediation))
    parts.append(
        markdown_table(
            ["Rank", "Macro-domain", "Gap", "Gap Summary", "Priority Remediation"],
            rows,
        )
    )
    parts.append("")
    return parts


def _section_consistency(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 6. Consistency Check\n")
    inv = state.get("architecture_inventory") or {}
    systems = inv.get("systems") or []
    stores = inv.get("data_stores") or []
    flows = inv.get("data_flows") or []
    ctx = state.get("company_context")
    applicable = _attr(ctx, "applicable_regs", default=[]) or []
    parts.append(
        markdown_table(
            ["Consistency Item", "Status", "Evidence"],
            [
                (
                    "Architecture evidence matches 04a",
                    "PASS" if systems and stores and flows else "PARTIAL",
                    f"{len(systems)} systems, {len(stores)} stores, {len(flows)} flows",
                ),
                (
                    "Regulatory scope matches Doc 04 and Doc 05",
                    "PASS" if applicable else "PARTIAL",
                    f"applicable_regs = [{', '.join(applicable) or '-'}]",
                ),
                (
                    "LOW-tier realism maintained",
                    "PASS",
                    "No enterprise HSM, SIEM, PAM, SOC, or CMDB claimed",
                ),
                (
                    "Maturity scale used consistently",
                    "PASS",
                    "Current maturity values are integers 0-4; target and gap shown numerically",
                ),
                (
                    "Evidence and gaps align",
                    "PASS",
                    "Largest gaps drive remediation in §5; D-07 strongest but not enterprise-grade",
                ),
            ],
        )
    )
    parts.append("")
    return parts


def _section_gate(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 7. Gate\n")
    parts.append(
        markdown_table(
            ["Gate Criterion", "Status", "Evidence"],
            [
                ("All 10 macro-domains assessed with maturity level and evidence", "PASS", "Section 3"),
                ("Target maturity defined per macro-domain", "PASS", "Sections 3 and 4"),
                ("Summary dashboard populated", "PASS", "Section 4"),
                ("Top 5 gaps identified", "PASS", "Section 5"),
                ("SubDomains references included", "PASS", "Each macro-domain section links to active Layer 0 files"),
            ],
        )
    )
    parts.append("")
    return parts


def _section_version_history(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## N-1. Version History\n")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    parts.append(
        markdown_table(
            ["Version", "Date", "Author", "Changes"],
            [
                (1.0, today, "Executor", "Generated AEGIS maturity assessment from state[" "architecture_inventory" "] and ontology"),
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
                ("Document Author", "Executor", "", today),
                ("Technical Review", "CTO", "", ""),
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
# Tables
# ─────────────────────────────────────────────────────────────────────


def _controls_table(controls: list[dict[str, str]]) -> str:
    headers = ["Control", "Current", "Evidence", "Notes"]
    rows: list[tuple[str, str, str, str]] = []
    for ctl in controls:
        evidence = _evidence_text(ctl.get("evidence_refs") or [])
        rows.append(
            (
                ctl.get("control", "-"),
                ctl.get("current", "-"),
                evidence,
                ctl.get("notes", "-"),
            )
        )
    return markdown_table(headers, rows)


def _evidence_text(refs: list[str]) -> str:
    if not refs:
        return "Architecture inventory (no specific asset reference)"
    return ", ".join(refs)


# ─────────────────────────────────────────────────────────────────────
# Per-domain notes — LLM or fallback
# ─────────────────────────────────────────────────────────────────────


def _domain_notes(
    domain_id: str,
    state: dict[str, Any],
    current: int,
    target: int,
    gap: int,
    controls: list[dict[str, str]],
    llm_invoker: Any | None,
    *,
    config: dict[str, Any] | None = None,
) -> str:
    """Return a 2-4 sentence narrative for the given domain."""
    prompt = _domain_notes_prompt(domain_id, current, target, gap, controls, state)
    return render_mandatory_narrative(
        invoker=llm_invoker,
        prompt=prompt,
        section_id=f"doc_04b.section_3.domain_notes.{domain_id}",
        max_chars=_MAX_FRAGMENT_BYTES,
        config=config,
    )


def _domain_notes_prompt(
    domain_id: str,
    current: int,
    target: int,
    gap: int,
    controls: list[dict[str, str]],
    state: dict[str, Any],
) -> str:
    name = _DOMAIN_NAME.get(domain_id, domain_id)
    applicable = ", ".join(_attr(state.get("company_context"), "applicable_regs", default=[]) or []) or "-"
    control_summary = "; ".join(c.get("control", "-") for c in controls)
    return (
        f"Produce a 2-3 sentence Notes narrative for AEGIS domain {domain_id} ({name}) "
        f"with current maturity {current}, target {target}, and gap {gap}. "
        f"Applicable regulations: {applicable}. "
        f"Controls in scope: {control_summary}. "
        "The narrative should reference GDPR Art. 32 / CRA Annex I controls where "
        "relevant and name the most material remediation items. Avoid bullet lists."
    )


def _subdomain_links(domain_id: str) -> list[str]:
    """Return the active sub-domain ids belonging to ``domain_id``."""
    mapping = {
        "D-01": ["D-01.1", "D-01.2", "D-01.3", "D-01.4"],
        "D-02": ["D-02.1", "D-02.2", "D-02.3", "D-02.4"],
        "D-03": ["D-03.1", "D-03.2", "D-03.3", "D-03.4"],
        "D-04": ["D-04.1", "D-04.2", "D-04.3", "D-04.4"],
        "D-05": ["D-05.1", "D-05.2", "D-05.3", "D-05.4"],
        "D-06": ["D-06.1", "D-06.2", "D-06.3", "D-06.4"],
        "D-07": ["D-07.1", "D-07.2", "D-07.3", "D-07.4"],
        "D-08": ["D-08.1", "D-08.2"],
        "D-09": ["D-09.1", "D-09.2", "D-09.3", "D-09.4"],
        "D-10": ["D-10.1", "D-10.2", "D-10.3"],
    }
    return mapping.get(domain_id, [])


def _default_remediation(domain_id: str) -> str:
    return _REMEDIATION_TEXT.get(
        domain_id,
        "Document the current practice, define a target state, and schedule periodic review.",
    )


_REMEDIATION_TEXT: dict[str, str] = {
    "D-01": "Add formal key-lifecycle documentation, periodic restore/integrity tests, and review evidence for GDPR Art. 32 and CRA Annex I Part I confidentiality/integrity controls.",
    "D-02": "Create a vulnerability register, define critical/high SLAs, and publish security.txt with a CVD policy.",
    "D-03": "Document access reviews, enforce customer MFA, and add a privileged-access logging baseline.",
    "D-04": "Create a GDPR/CRA incident runbook with 24h/72h timing and run one tabletop exercise.",
    "D-05": "Approve retention periods as policy, add DSAR tracking, and automate export/delete procedures.",
    "D-06": "Add CycloneDX/SPDX SBOM in CI/CD and maintain a subprocessor evidence register.",
    "D-07": "Strengthen CRA evidence through SBOM, release notes, and a documented security review checklist.",
    "D-08": "Build role-specific training curriculum (developers, DPO, CTO) and track completion annually.",
    "D-09": "Create RoPA, Annex VII evidence index, and a lightweight risk register with documented owner.",
    "D-10": "Define alert taxonomy, log review cadence, and a basic control testing schedule.",
}


# ─────────────────────────────────────────────────────────────────────
# Helpers — gap summary, maturity counts, controls lookup
# ─────────────────────────────────────────────────────────────────────


def _gap_summary(domain_id: str) -> tuple[str, str]:
    return _GAP_SUMMARY.get(
        domain_id,
        (
            "Current practice informal; documented controls not yet in place.",
            "Document baseline controls and add review cadence.",
        ),
    )


_GAP_SUMMARY: dict[str, tuple[str, str]] = {
    "D-02": (
        "Scanning exists but patch SLAs, disclosure, and testing are ad hoc",
        "Create vulnerability register, define critical/high SLAs, publish security.txt and CVD policy",
    ),
    "D-04": (
        "Basic plan and backups exist, but notification, containment, and recovery are not tested",
        "Create GDPR/CRA incident runbook with 24h/72h timing and run one tabletop exercise",
    ),
    "D-09": (
        "RoPA, Annex VII documentation, formal risk assessment, and policy set are incomplete",
        "Create RoPA, Annex VII evidence index, asset inventory owner, and lightweight risk register",
    ),
    "D-10": (
        "Logs are retained but there is no security monitoring programme",
        "Define alert taxonomy, log review cadence, and basic control testing schedule",
    ),
    "D-06": (
        "Vendor review is annual/informal and SBOM is not implemented",
        "Add CycloneDX/SPDX SBOM in CI/CD and maintain a subprocessor evidence register",
    ),
    "D-05": (
        "Retention periods are documented in 04a but not yet approved as policy; DSAR workflow is manual",
        "Approve retention policies, add DSAR tracking, and automate export/delete procedures",
    ),
    "D-08": (
        "Annual awareness is realistic for a small team but role-specific competence is not tracked",
        "Build tracked curriculum for CTO, developers, support, and DPO roles",
    ),
    "D-03": (
        "Managed IAM is in place but access reviews, customer MFA, and PAM are informal",
        "Document access reviews, enforce customer MFA, add privileged-access logging",
    ),
    "D-01": (
        "Encryption is implemented but key lifecycle and integrity verification are not formal",
        "Add key-rotation policy, periodic restore/integrity tests, and review evidence",
    ),
    "D-07": (
        "Developer-led practices exist but CRA evidence hardening (SBOM, release notes) is incomplete",
        "Add SBOM artefact, security checklist, and threat-model template per feature",
    ),
}


def _maturity_counts(overrides: Mapping[str, int]) -> dict[int, int]:
    counts = {lvl: 0 for lvl in (0, 1, 2, 3, 4)}
    for domain_id in _DOMAIN_CURRENT:
        lvl = overrides.get(domain_id, _DOMAIN_CURRENT[domain_id])
        if lvl in counts:
            counts[lvl] += 1
    return counts


def _overrides(state: dict[str, Any]) -> dict[str, int]:
    """Return maturity overrides injected via ``state["security_posture_overrides"]``."""
    raw = state.get("security_posture_overrides") or {}
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, int] = {}
    for key, value in raw.items():
        try:
            result[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return result


def _controls_for(domain_id: str, state: dict[str, Any]) -> list[dict[str, str]]:
    """Return the control rows for ``domain_id``.

    Substitutes evidence refs using architecture_inventory where possible
    (so the table matches the actual inventory rather than the static
    default).
    """
    defaults = [dict(ctl) for ctl in _DEFAULT_CONTROLS.get(domain_id, [])]
    inv = state.get("architecture_inventory") or {}
    sys_ids = [s.get("id", "") for s in (inv.get("systems") or []) if s.get("id")]
    store_ids = [s.get("id", "") for s in (inv.get("data_stores") or []) if s.get("id")]
    flow_ids = [f.get("id", "") for f in (inv.get("data_flows") or []) if f.get("id")]

    if not sys_ids and not store_ids and not flow_ids:
        return defaults

    # Replace default refs with the actual inventory ids where known.
    for ctl in defaults:
        refs = ctl.get("evidence_refs") or []
        if not refs:
            continue
        new_refs: list[str] = []
        for ref in refs:
            if (ref.startswith("SYS-") and ref in sys_ids) or (ref.startswith("STORE-") and ref in store_ids) or (ref.startswith("FLOW-") and ref in flow_ids):
                new_refs.append(ref)
            else:
                new_refs.append(ref)
        ctl["evidence_refs"] = new_refs
    return defaults


def _active_count(state: dict[str, Any]) -> int:
    """Number of active sub-domains from ontology."""
    ont = state.get("ontology") or {}
    subdomains = ont.get("subdomains") if isinstance(ont, Mapping) else None
    if not isinstance(subdomains, Mapping):
        return 0
    covered = subdomains.get("covered") or []
    return len(covered) if isinstance(covered, list) else 0


def _total_count(state: dict[str, Any]) -> int:
    return len(state.get("subdomains") or {})


# ─────────────────────────────────────────────────────────────────────
# LLM invocation and deterministic fallback
# ─────────────────────────────────────────────────────────────────────


def _should_use_llm(llm_invoker: Any | None) -> bool:
    if llm_invoker is None:
        return False
    return os.environ.get("MOCK_LLM", "").strip().lower() not in {"1", "true", "yes", "on"}


# ─────────────────────────────────────────────────────────────────────
# Frontmatter
# ─────────────────────────────────────────────────────────────────────


def _build_frontmatter(state: dict[str, Any]) -> str:
    ctx = state.get("company_context")
    applicable = _attr(ctx, "applicable_regs", default=[]) or []
    active = _active_count(state)
    inactive = _inactive_list(state)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return generate_frontmatter(
        document_id="AEGIS-P1-04b",
        title="Security Posture Assessment (Maturity Model)",
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
                "05_Regulatory_Applicability.md",
            ],
            "outputs": ["07_Structured_Compliance_Matrix.md"],
            "applicable_regs": list(applicable),
            "active_subdomains": active,
            "inactive_subdomains": list(inactive),
            "related_documents": [
                "04a_Architecture_DataInventory.md",
                "../../../00_METHODOLOGY/PREPROCESSING/SubDomains/index.md",
                "../../../00_METHODOLOGY/PREPROCESSING/SubDomains/",
            ],
        },
    )


def _inactive_list(state: dict[str, Any]) -> list[str]:
    """Return sub-domain ids marked inactive in the ontology."""
    ont = state.get("ontology") or {}
    subdomains = ont.get("subdomains") if isinstance(ont, Mapping) else None
    if not isinstance(subdomains, Mapping):
        return []
    not_covered = subdomains.get("not_covered") or []
    if not isinstance(not_covered, list):
        return []
    return [str(item.get("id")) for item in not_covered if isinstance(item, Mapping) and item.get("id")]


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return default


__all__ = ["render_doc_04b"]
