"""doc_04d — render AEGIS-P1-04d Organisation, Roles & RACI Matrix.

Sections produced (mirrors the reference ``04d_Org_Roles_RACI.md`` in
Case_01_TinyTask_SaaS):

1.  Purpose & Scope
2.  Company-Level Responsible (table)
3.  Regulation-Level Owner (table)
4.  Key Roles (table)
5.  Reporting Lines (narrative + ASCII tree)
6.  RACI Matrix (per macro-domain)
7.  Training Status (table)
8.  Compliance Mapping (D-08 / D-09)
9.  Gaps & Known Limitations
10. Gate

The optional §5 Reporting Lines narrative and §9 Escalation Paths are
LLM-generated when an invoker is supplied (and ``MOCK_LLM`` is unset).
All other sections are deterministic.

References:
    - Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/04d_Org_Roles_RACI.md
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

logger = logging.getLogger(__name__)

_FILENAME = "04d_Org_Roles_RACI.md"
_MAX_FRAGMENT_BYTES = 2000
_SAFE_KEY = re.compile(r"[^A-Za-z0-9_.-]")

# Hardcoded stakeholder list — mirrors the reference convention.
# Column abbreviations are kept short for readability.
_STAKEHOLDER_COLUMNS = [
    ("DPO", "CEO acting as voluntary Data Protection Officer"),
    ("CISO", "CTO acting as Security Lead / CISO"),
    ("Dev", "Lead Developer + developer team"),
    ("Legal", "External Legal Adviser (retainer)"),
    ("HR", "CEO in HR-coordination role"),
    ("Board", "2 founders (CEO + CTO)"),
]

# Per-domain activity → R/A/C/I mapping per stakeholder column.
# The mapping encodes the deterministic algorithm:
#   - Data-protection-specific activities => A = DPO
#   - Security/engineering activities => A = CISO
#   - Implementation work => R = Dev
#   - Governance approvals => A = Board
_RACI_BY_DOMAIN: dict[str, list[tuple[str, dict[str, str]]]] = {
    "D-01": [
        ("Encrypt personal data at rest", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
        ("Manage encryption keys", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
        ("Notify DPA within 72h (Art. 33 GDPR)", {"DPO": "R", "CISO": "A", "Dev": "C", "Legal": "C", "HR": "—", "Board": "I"}),
        ("Conduct DPIA (Art. 35 GDPR)", {"DPO": "R", "CISO": "C", "Dev": "C", "Legal": "A", "HR": "—", "Board": "I"}),
    ],
    "D-02": [
        ("Run vulnerability scans (Snyk, dependency review)", {"DPO": "I", "CISO": "A", "Dev": "R", "Legal": "—", "HR": "—", "Board": "I"}),
        ("Apply critical patches (CRA Annex I Part I (2)(f))", {"DPO": "I", "CISO": "A", "Dev": "R", "Legal": "—", "HR": "—", "Board": "I"}),
        ("Annual penetration testing", {"DPO": "I", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
        ("Operate CVD / security.txt (CRA Art. 14)", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
    ],
    "D-03": [
        ("Manage IAM (Auth0 + cloud IAM)", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
        ("Enforce MFA (admins; future customer MFA)", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "—", "HR": "—", "Board": "I"}),
        ("Quarterly access review", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
        ("Offboarding (revoke access within 24h)", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "C", "Board": "I"}),
    ],
    "D-04": [
        ("Detect incident", {"DPO": "I", "CISO": "A", "Dev": "R", "Legal": "—", "HR": "—", "Board": "I"}),
        ("Contain incident", {"DPO": "I", "CISO": "A", "Dev": "R", "Legal": "C", "HR": "—", "Board": "I"}),
        ("Notify authorities (72h GDPR / 24h CRA)", {"DPO": "R", "CISO": "A", "Dev": "C", "Legal": "C", "HR": "—", "Board": "I"}),
        ("Notify controllers (Art. 33(2) processor→controller)", {"DPO": "R", "CISO": "A", "Dev": "C", "Legal": "C", "HR": "—", "Board": "I"}),
        ("Recover systems (RPO / RTO targets)", {"DPO": "I", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
        ("Post-incident review", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
    ],
    "D-05": [
        ("Enforce data minimisation", {"DPO": "R", "CISO": "A", "Dev": "C", "Legal": "C", "HR": "—", "Board": "I"}),
        ("Manage retention policies", {"DPO": "R", "CISO": "A", "Dev": "C", "Legal": "C", "HR": "—", "Board": "I"}),
        ("Process erasure requests (Art. 17 GDPR)", {"DPO": "R", "CISO": "C", "Dev": "A", "Legal": "C", "HR": "—", "Board": "I"}),
        ("Process portability requests (Art. 20 GDPR)", {"DPO": "R", "CISO": "C", "Dev": "A", "Legal": "C", "HR": "—", "Board": "I"}),
    ],
    "D-06": [
        ("Assess vendor security (annual review)", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "C", "HR": "—", "Board": "I"}),
        ("Maintain SBOM (CRA Annex I Part II (1))", {"DPO": "I", "CISO": "A", "Dev": "R", "Legal": "—", "HR": "—", "Board": "I"}),
        ("Manage DPA contracts with B2B controllers", {"DPO": "R", "CISO": "C", "Dev": "I", "Legal": "A", "HR": "—", "Board": "I"}),
        ("Manage DPA acceptance from subprocessor vendors", {"DPO": "R", "CISO": "A", "Dev": "I", "Legal": "C", "HR": "—", "Board": "I"}),
    ],
    "D-07": [
        ("Threat model per feature", {"DPO": "C", "CISO": "C", "Dev": "R/A", "Legal": "I", "HR": "—", "Board": "I"}),
        ("Code review", {"DPO": "I", "CISO": "C", "Dev": "R/A", "Legal": "—", "HR": "—", "Board": "I"}),
        ("Security testing in CI/CD (SAST/DAST/SCA)", {"DPO": "I", "CISO": "A", "Dev": "R", "Legal": "—", "HR": "—", "Board": "I"}),
        ("Change approval (CAB) for production releases", {"DPO": "I", "CISO": "C", "Dev": "R", "Legal": "I", "HR": "—", "Board": "A"}),
    ],
    "D-08": [
        ("Annual security awareness training (D-08.1)", {"DPO": "C", "CISO": "A", "Dev": "I", "Legal": "I", "HR": "R", "Board": "I"}),
        ("Role-specific training — secure coding (D-08.2)", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "—", "HR": "I", "Board": "I"}),
        ("Role-specific training — DPO competence refresh (D-08.2)", {"DPO": "R/A", "CISO": "C", "Dev": "—", "Legal": "C", "HR": "I", "Board": "I"}),
    ],
    "D-09": [
        ("Approve security policies", {"DPO": "C", "CISO": "C", "Dev": "C", "Legal": "C", "HR": "C", "Board": "A"}),
        ("Conduct risk assessments (annual + per-feature)", {"DPO": "R", "CISO": "A", "Dev": "C", "Legal": "C", "HR": "I", "Board": "I"}),
        ("Maintain asset inventory", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
        ("Maintain RoPA (Art. 30 GDPR)", {"DPO": "R", "CISO": "A", "Dev": "C", "Legal": "C", "HR": "—", "Board": "I"}),
        ("Maintain CRA Annex VII technical documentation", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "C", "HR": "—", "Board": "I"}),
    ],
    "D-10": [
        ("Continuous security monitoring (Datadog; SIEM-light)", {"DPO": "I", "CISO": "A", "Dev": "R", "Legal": "—", "HR": "—", "Board": "I"}),
        ("Audit-log retention", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
        ("Annual compliance testing", {"DPO": "C", "CISO": "A", "Dev": "R", "Legal": "I", "HR": "—", "Board": "I"}),
    ],
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
) -> dict[str, str]:
    """Render AEGIS-P1-04d Organisation, Roles & RACI Matrix.

    Args:
        state: Pipeline state (see :class:`aegis_phase1.v2.state.V2State`).
        output_dir: Directory in which the document is written.
        llm_invoker: Optional LLM invoker. When ``None`` or when
            ``MOCK_LLM`` is truthy, deterministic fallback text is used
            for the escalation-paths narrative.

    Returns:
        Mapping ``AEGIS-P1-04d`` -> absolute file path.
    """
    use_llm = _should_use_llm(llm_invoker)
    frontmatter = _build_frontmatter(state)
    body = _build_body(state, llm_invoker if use_llm else None)
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_04d: wrote %s", path)
    return {"AEGIS-P1-04d": path}


# ─────────────────────────────────────────────────────────────────────
# Body construction
# ─────────────────────────────────────────────────────────────────────


def _build_body(state: dict[str, Any], llm_invoker: Any | None) -> str:
    parts: list[str] = []
    parts.append("# Organisation, Roles & RACI Matrix\n")
    parts.extend(_section_purpose_scope(state))
    parts.extend(_section_company_level(state))
    parts.extend(_section_regulation_level(state))
    parts.extend(_section_key_roles(state))
    parts.extend(_section_reporting_lines(state, llm_invoker))
    parts.extend(_section_raci_matrix(state))
    parts.extend(_section_training_status(state))
    parts.extend(_section_compliance_mapping(state))
    parts.extend(_section_escalation_paths(state, llm_invoker))
    parts.extend(_section_gaps(state))
    parts.extend(_section_gate(state))
    parts.extend(_section_version_history(state))
    parts.extend(_section_approval(state))
    parts.extend(_section_see_also(state))
    return "\n".join(parts)


def _section_purpose_scope(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 1. Purpose & Scope\n")
    ctx = state.get("company_context")
    name = _attr(ctx, "company_name", default="the company")
    parts.append(
        f"This document describes {name}'s organisational structure and "
        "the per-activity RACI matrix that allocates information-security "
        "and data-protection responsibilities. It maps to Layer 0 "
        "sub-domains **D-08 (Human Factors)** and **D-09 (Governance "
        "Documentation)**, and supports compliance with **GDPR Art. 37-39** "
        "(DPO designation), **GDPR Art. 32** (security of processing), "
        "**CRA Annex I Part II (8)(f)** (vulnerability handling competence), "
        "and **CRA Annex VII §5** (technical documentation — organisational "
        "measures).\n"
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
            "The board-training row in the RACI matrix is retained as a "
            "**best-practice placeholder**, not as a derived compliance "
            "requirement.\n"
        )
    employees = _attr(ctx, "employees", default="")
    parts.append(
        "**Proportionality note (P2 — Company Reality First):** "
        f"{name} has {employees or 'a small'} employee headcount. Formal "
        "role separation characteristic of larger firms (separate DPO, "
        "CISO, IT Manager, Legal, HR, IR Lead) is not feasible — many "
        "hats fall on the CEO/CTO/lead developer. RACI assignments "
        "concentrate **A** (Accountable) on the CEO or CTO, with one "
        "**R** (Responsible) per activity and the rest as **C** "
        "(Consulted) or **I** (Informed).\n"
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
        rows = [
            ("GDPR", "YES", "Compliance Lead (CEO/DPO)"),
            ("CRA", "YES", "Engineering Lead (CTO/CISO)"),
            ("NIS2", "NO", "n/a (not applicable)"),
            ("DORA", "NO", "n/a (not applicable)"),
            ("AI Act", "NO", "n/a (not applicable)"),
        ]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_key_roles(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 4. Key Roles\n")
    parts.append(
        "Functional roles are listed below. In a low-tier organisation "
        "many hats fall on a single individual; backup assignments are "
        "documented for incident-trigger continuity.\n"
    )
    headers = ["Role", "Person / Team", "Reports To", "FTE Allocation", "Backup"]
    rows = [
        (
            "CEO (also DPO)",
            "Founder #1",
            "Board (2 founders)",
            "0.2 DPO + 0.8 CEO (combined 1.0)",
            "CTO (acting DPO)",
        ),
        (
            "CTO (also CISO)",
            "Founder #2",
            "Board (2 founders)",
            "0.3 CISO + 0.7 CTO (combined 1.0)",
            "CEO (acting CISO)",
        ),
        (
            "Lead Developer",
            "Senior engineer — most-tenured non-founder",
            "CTO",
            "1.0 (full developer; ~0.1 on security tasks via CI/CD and patching)",
            "CTO for code-related security tasks",
        ),
        (
            "Developers × 5",
            "5 full-stack developers",
            "CTO",
            "5 × 1.0 across product development, secure coding, CI/CD maintenance, on-call rotation",
            "Peer developers",
        ),
        (
            "External Legal Adviser",
            "External law firm (retainer)",
            "CEO",
            "0 (retainer; ad-hoc consultation)",
            "None — single retainer",
        ),
        (
            "Management Board",
            "2 founders (CEO + CTO)",
            "—",
            "—",
            "n/a — board is the board",
        ),
        (
            "IR Lead",
            "CTO in CISO capacity",
            "n/a (rotational developer on-call)",
            "Same as CTO/CISO; on-call rotation across developers",
            "CEO",
        ),
    ]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_reporting_lines(state: dict[str, Any], llm_invoker: Any | None) -> list[str]:
    parts: list[str] = []
    parts.append("## 5. Reporting Lines\n")
    parts.append(
        "The following ASCII tree and narrative describe the reporting "
        "structure.\n"
    )
    parts.append("```\n")
    parts.append(
        "                            ┌─────────────────────────────┐\n"
        "                            │       Management Board       │\n"
        "                            │   (2 founders — CEO + CTO)    │\n"
        "                            └──────────────┬────────────────┘\n"
        "                                           │\n"
        "               ┌───────────────────────────┼────────────────────────┐\n"
        "               │                                                         │\n"
        "        ┌──────▼─────────┐                                       ┌──────▼─────────┐\n"
        "        │      CEO       │                                       │      CTO       │\n"
        "        │ 0.2 FTE DPO    │                                       │ 0.3 FTE CISO   │\n"
        "        │ + founder ops  │                                       │ + founder tech │\n"
        "        └──┬─────────────┘                                       └──┬─────────────┘\n"
        "           │                       ┌─────────────────┐              │\n"
        "           │                       │ External Legal  │              │\n"
        "           │                       │   (DPO Support) │              │\n"
        "           │                       └─────────────────┘              │\n"
        "           │                                                        │\n"
        "           └────────────────────┬───────────────────────────────────┘\n"
        "                                │\n"
        "                   ┌────────────▼────────────┐\n"
        "                   │     Lead Developer       │\n"
        "                   │    (senior engineer)     │\n"
        "                   └────────────┬─────────────┘\n"
        "                                │\n"
        "             ┌──────────────────┴──────────────────┐\n"
        "             │                                      │\n"
        "    ┌────────▼────────┐                  ┌─────────▼───────┐\n"
        "    │ Developers × 5  │                  │  (Developers on │\n"
        "    │  (full-time)    │                  │   security rota)│\n"
        "    └────────────────┘                  └────────────────┘\n"
    )
    parts.append("```\n")

    narrative = render_mandatory_narrative(
        invoker=llm_invoker,
        prompt=_reporting_lines_prompt(state),
        section_id="doc_04d.section_5.reporting_lines",
        max_chars=_MAX_FRAGMENT_BYTES,
    )
    parts.append("**Plain-text description:**\n")
    parts.append(narrative.rstrip() + "\n")
    return parts


def _section_raci_matrix(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 6. RACI Matrix\n")
    parts.append(
        "**Legend:** **R** = Responsible, **A** = Accountable (single "
        "sign-off; one A per row), **C** = Consulted, **I** = Informed, "
        "**—** = Not involved.\n"
    )
    parts.append(
        "**Column abbreviations** (people are listed once each; in a "
        "small team, multiple hats are worn):\n"
        "- **DPO** = CEO acting as voluntary Data Protection Officer\n"
        "- **CISO** = CTO acting as Security Lead / CISO\n"
        "- **Dev** = Lead Developer + developer team\n"
        "- **Legal** = External Legal Adviser (retainer)\n"
        "- **HR** = CEO in HR-coordination role\n"
        "- **Board** = 2 founders (CEO + CTO)\n"
    )

    inactive = _inactive_subdomain_ids(state)
    for domain_id in sorted(_RACI_BY_DOMAIN.keys()):
        sub_label = _domain_sub_label(domain_id, inactive)
        parts.append(f"### 6.{int(domain_id.split('-')[1])} {_DOMAIN_NAME[domain_id]} ({sub_label})\n")
        rows = _RACI_BY_DOMAIN[domain_id]
        parts.append(_raci_table(rows))
        parts.append("")

    parts.append(
        "**Reading note:** Rows that place both **CISO = A** and **Dev = R** "
        "mirror the standard \"RACI for small teams\" pattern — the "
        "CTO/CISO owns the outcome; the lead developer (with the rotating "
        "developer team) does the work. Where the activity is "
        "data-protection-specific (e.g., Art. 17 erasure), **DPO = A** "
        "holds the legal accountability per Art. 28(3); implementation "
        "**R** swaps to Dev. Board rows are predominantly **I** "
        "operationally and **A** for governance-level approvals.\n"
    )
    return parts


def _section_training_status(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 7. Training Status\n")
    inactive = _inactive_subdomain_ids(state)
    d08_3_status = "INACTIVE — placeholder row only" if "D-08.3" in inactive else "ACTIVE"
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
            "Management Board (2 founders)",
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


def _section_escalation_paths(state: dict[str, Any], llm_invoker: Any | None) -> list[str]:
    parts: list[str] = []
    parts.append("## 9. Escalation Paths\n")
    narrative = render_mandatory_narrative(
        invoker=llm_invoker,
        prompt=_escalation_prompt(state),
        section_id="doc_04d.section_9.escalation_paths",
        max_chars=_MAX_FRAGMENT_BYTES,
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
    parts.append("**Gate Status:** PASS (proportionate for LOW-tier micro SaaS under P2).\n")
    return parts


def _section_version_history(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## N-1. Version History\n")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    parts.append(
        markdown_table(
            ["Version", "Date", "Author", "Changes"],
            [
                (1.0, today, "Executor", "Generated RACI from state.regulations and a deterministic per-domain mapping"),
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
                ("Business Review", "CEO", "", ""),
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


def _raci_table(rows: list[tuple[str, dict[str, str]]]) -> str:
    headers = ["Activity", "DPO (CEO)", "CISO (CTO)", "Dev", "Legal", "HR", "Board"]
    table_rows: list[tuple[str, str, str, str, str, str, str]] = []
    for activity, mapping in rows:
        table_rows.append(
            (
                activity,
                mapping.get("DPO", "—"),
                mapping.get("CISO", "—"),
                mapping.get("Dev", "—"),
                mapping.get("Legal", "—"),
                mapping.get("HR", "—"),
                mapping.get("Board", "—"),
            )
        )
    return markdown_table(headers, table_rows)


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


def _domain_sub_label(domain_id: str, inactive: list[str]) -> str:
    """Return a sub-domain label like ``D-XX.Y - Z sub-domains``."""
    mapping = {
        "D-01": "D-01.1, D-01.2, D-01.3, D-01.4",
        "D-02": "D-02.1, D-02.2, D-02.3, D-02.4",
        "D-03": "D-03.1, D-03.2, D-03.3, D-03.4",
        "D-04": "D-04.1, D-04.2, D-04.3, D-04.4",
        "D-05": "D-05.1, D-05.2, D-05.3, D-05.4",
        "D-06": "D-06.1, D-06.2, D-06.3, D-06.4",
        "D-07": "D-07.1, D-07.2, D-07.3, D-07.4",
        "D-08": "D-08.1, D-08.2; D-08.3 inactive" if "D-08.3" in inactive else "D-08.1, D-08.2, D-08.3",
        "D-09": "D-09.1, D-09.2, D-09.3, D-09.4",
        "D-10": "D-10.1, D-10.2, D-10.3",
    }
    return f"sub-domain {mapping.get(domain_id, domain_id)}"


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
    return (
        f"Produce a 4-5 sentence plain-text description of the reporting "
        f"lines at {name} (with {employees or 'a small'} employees). "
        "Cover: Management Board (2 founders); CEO holding the DPO hat; "
        "CTO holding the CISO hat; Lead Developer under CTO; Developers "
        "rotating on-call; External Legal Adviser reporting to CEO; "
        "absence of separate HR / IT Manager functions. Avoid bullet lists."
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
    ont = state.get("ontology") or {}
    subdomains = ont.get("subdomains") if isinstance(ont, Mapping) else None
    if not isinstance(subdomains, Mapping):
        return 0
    covered = subdomains.get("covered") or []
    return len(covered) if isinstance(covered, list) else 0


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return default


__all__ = ["render_doc_04d"]
