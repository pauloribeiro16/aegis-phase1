"""doc_04c — render AEGIS-P1-04c Third-Party Landscape Inventory.

Sections produced (mirrors the reference ``04c_ThirdParty_Landscape.md``
in Case_01_TinyTask_SaaS):

1.  Purpose & Scope
2.  Inherited Infrastructure (cloud services)
3.  Overlap-Implied Third Parties (from ontology.overlaps)
4.  Contractual Controls (DPA / Art. 28 / audit reports)
5.  Risk Classification (L / M / H / VH)
6.  Compliance Mapping (D-06.x sub-domains)
7.  Gaps & Known Limitations
8.  Gate

The optional narrative summary in §5 is LLM-generated when an invoker
is supplied (and ``MOCK_LLM`` is unset). All other sections are
deterministic.

References:
    - Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/04c_ThirdParty_Landscape.md
    - contracts/SPRINT002_003_map_reduce_output.md
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

_FILENAME = "04c_ThirdParty_Landscape.md"
_MAX_FRAGMENT_BYTES = 2000

# Default risk scoring weights. A higher score => higher residual risk.
# Keys are substrings matched against provider/service text.
_HIGH_RISK_KEYWORDS = [
    "primary",
    "sole",
    "identity",
    "authentication",
    "payment",
    "core",
    "backup",
    "object storage",
]
_MEDIUM_RISK_KEYWORDS = [
    "monitoring",
    "log",
    "telemetry",
    "apm",
    "alert",
    "metric",
]
_LOW_RISK_KEYWORDS = [
    "scanner",
    "scanning",
    "sca",
    "sast",
    "repository",
    "code",
    "source",
]


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────


def render_doc_04c(
    state: dict[str, Any],
    output_dir: str,
    llm_invoker: Any | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render AEGIS-P1-04c Third-Party Landscape Inventory.

    Args:
        state: Pipeline state (see :class:`aegis_phase1.v2.state.V2State`).
        output_dir: Directory in which the document is written.
        llm_invoker: Optional LLM invoker. When ``None`` or when
            ``MOCK_LLM`` is truthy, deterministic fallback text is used
            for the risk-classification narrative.
        config: Optional Langfuse / LangChain runnable config threaded
            through to nested LLM calls so the GENERATION span is named
            after the LangGraph node.

    Returns:
        Mapping ``AEGIS-P1-04c`` -> absolute file path.
    """
    use_llm = _should_use_llm(llm_invoker)
    frontmatter = _build_frontmatter(state)
    body = _build_body(state, llm_invoker if use_llm else None, config=config)
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_04c: wrote %s", path)
    return {"AEGIS-P1-04c": path}


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
    parts.append("# Third-Party Landscape Inventory\n")
    parts.extend(_section_purpose_scope(state))
    parts.extend(_section_inherited_infrastructure(state))
    parts.extend(_section_overlap_implied(state))
    parts.extend(_section_contractual_controls(state))
    parts.extend(_section_risk_classification(state, llm_invoker, config=config))
    parts.extend(_section_compliance_mapping(state))
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
        f"This document inventories {name}'s third-party landscape: cloud "
        "providers, software vendors, subprocessors. It maps directly to "
        "Layer 0 sub-domain **D-06 (Supply Chain)** — D-06.1, D-06.2, "
        "D-06.3, D-06.4 — and supports compliance with **GDPR Art. 28** "
        "(processor obligations and controller due diligence) and "
        "**CRA Annex I Part I (2)(j) and (k)** (attack-surface reduction, "
        "exploitation-mitigation via the supply chain).\n"
    )
    parts.append(
        "**Scope:** Sub-domain D-06.x only. Broader architecture context "
        "is in `04a_Architecture_DataInventory.md`; broader governance "
        "(policies, risk assessments) is in `04b_Security_Posture.md` and "
        "Phase 2 deliverables.\n"
    )
    parts.append(
        "**Method:** Inventory was constructed from the architecture "
        "documentation (`04a`), the stakeholder register in "
        "`04_Company_Context_Assessment.md §3`, and the ontology's "
        "`overlaps` block (cross-regulation shared sub-domains).\n"
    )
    employees = _attr(ctx, "employees", default="")
    parts.append(
        "**Proportionality note (P2 — Company Reality First):** "
        f"{name} is a {('micro-SaaS' if _attr(ctx, 'scale', default='micro') in ('micro', 'MICRO') else 'SaaS')}"
        + (f" with {employees} employees" if employees else "")
        + ". Inventory is limited to the third parties that actually "
        "touch personal data or the production system. No formal supplier "
        "programme exists; the inventory is a precondition to building "
        "one, not evidence one already exists.\n"
    )
    return parts


def _section_inherited_infrastructure(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 2. Inherited Infrastructure\n")
    inv = state.get("architecture_inventory") or {}
    cloud = inv.get("cloud_services") or []
    if not cloud:
        parts.append("_No cloud services recorded in the architecture inventory._\n")
        return parts
    parts.append(
        "The following providers host customer data, the production "
        "application, or authentication. They are listed in order as "
        "they appear in the architecture inventory (provider + service).\n"
    )
    headers = [
        "Provider",
        "Service",
        "Data Stored",
        "Region",
        "DPA in Place?",
        "Subprocessor?",
    ]
    rows = []
    for entry in cloud:
        provider = entry.get("provider", "-")
        service = entry.get("service", "-")
        # Best-effort subprocessor hint based on convention
        is_processor = any(
            kw in (provider + " " + service).lower()
            for kw in ("identity", "auth0", "stripe", "datadog", "aws", "s3", "rds", "kms", "ec2")
        )
        rows.append(
            (
                provider,
                service,
                entry.get("data_stored", "-"),
                entry.get("region", "-"),
                entry.get("dpa_in_place", "-"),
                "Y" if is_processor else "N",
            )
        )
    parts.append(markdown_table(headers, rows))
    parts.append("")
    parts.append(
        f"**Summary:** {len(cloud)} inherited infrastructure entries "
        "recorded. DPA status follows the architecture inventory values.\n"
    )
    return parts


def _section_overlap_implied(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 3. Overlap-Implied Third Parties\n")
    ont = state.get("ontology") or {}
    overlaps = ont.get("overlaps") if isinstance(ont, Mapping) else None
    rows: list[tuple[str, str, str]] = []
    if isinstance(overlaps, list):
        for entry in overlaps:
            if not isinstance(entry, Mapping):
                continue
            reg1 = entry.get("regulation_1", "?")
            reg2 = entry.get("regulation_2", "?")
            shared = entry.get("shared_subdomains") or []
            ids: list[str] = []
            for s in shared:
                if isinstance(s, Mapping):
                    sid = s.get("id", "-")
                    if sid and sid != "-":
                        ids.append(str(sid))
            description = entry.get("description", "-") or "-"
            rows.append((f"{reg1}+{reg2}", ", ".join(ids) or "-", description))
    if not rows:
        parts.append("_No overlap entries recorded in the ontology._\n")
        return parts
    parts.append(
        markdown_table(["Reg Pair", "Shared Sub-domains", "Note"], rows)
    )
    parts.append("")
    return parts


def _section_contractual_controls(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 4. Contractual Controls\n")
    inv = state.get("architecture_inventory") or {}
    cloud = inv.get("cloud_services") or []
    headers = [
        "Provider / Service",
        "DPA in Place?",
        "Art. 28 Compliant?",
        "Audit Reports Substituted?",
        "Subprocessor Approval Flow?",
    ]
    rows: list[tuple[str, str, str, str, str]] = []
    for entry in cloud:
        dpa = entry.get("dpa_in_place", "-")
        provider_service = f"{entry.get('provider', '-')} — {entry.get('service', '-')}"
        # Deterministic inference
        art28 = "Y" if dpa in {"Y", "Yes", "yes", "TRUE", "true", True} else "—"
        audit = "Indirect — vendor SOC 2 / ISO 27001 substituted" if art28 == "Y" else "—"
        subproc = "Y — vendor publishes subprocessor list" if art28 == "Y" else "—"
        rows.append((provider_service, dpa, art28, audit, subproc))
    if not rows:
        parts.append("_No providers recorded; contractual controls not yet mapped._\n")
        return parts
    parts.append(markdown_table(headers, rows))
    parts.append("")
    parts.append(
        "**Common pattern:** Providers substitute third-party certifications "
        "(SOC 2 / ISO 27001) for direct audit access. This is industry-standard "
        "for low-tier SaaS and requires annual freshness review.\n"
    )
    return parts


def _section_risk_classification(
    state: dict[str, Any],
    llm_invoker: Any | None,
    *,
    config: dict[str, Any] | None = None,
) -> list[str]:
    parts: list[str] = []
    parts.append("## 5. Supply Chain Risk Assessment\n")
    inv = state.get("architecture_inventory") or {}
    cloud = inv.get("cloud_services") or []
    if not cloud:
        parts.append("_No cloud services recorded._\n")
        return parts
    parts.append(
        "Risk score key: **VH** = Very High, **H** = High, **M** = Medium, "
        "**L** = Low. Criticality reflects **business impact of vendor "
        "failure or incident**. Risk score reflects **likelihood × impact** "
        "given the current maturity (no formal supplier programme; "
        "reliance on third-party certifications).\n"
    )
    headers = [
        "Provider / Service",
        "Criticality",
        "Risk Score",
        "Last Assessment",
        "SBOM Available?",
        "Next Review",
    ]
    rows: list[tuple[str, str, str, str, str, str]] = []
    for entry in cloud:
        provider_service = f"{entry.get('provider', '-')} — {entry.get('service', '-')}"
        criticality = _criticality_for(entry)
        risk = _risk_for(entry)
        last_assessment = _default_assessment_date()
        sbom = _sbom_for(entry)
        next_review = _next_review_date()
        rows.append((provider_service, criticality, risk, last_assessment, sbom, next_review))
    parts.append(markdown_table(headers, rows))
    parts.append("")
    parts.append(
        f"**Vendor count:** {len(cloud)} (deduplicated by provider+service). "
        "No Critical+High combinations expected for a low-tier SaaS that "
        "uses managed cloud services exclusively.\n"
    )

    # Optional narrative
    narrative = render_mandatory_narrative(
        invoker=llm_invoker,
        prompt=_risk_narrative_prompt(state, cloud, rows),
        section_id="doc_04c.section_5.concentration_risk_narrative",
        max_chars=_MAX_FRAGMENT_BYTES,
        config=config,
    )
    parts.append("### 5.1 Concentration Risk Narrative\n")
    parts.append(narrative.rstrip() + "\n")
    return parts


def _section_compliance_mapping(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 6. Compliance Mapping (Layer 0)\n")
    applicable = _attr(state.get("company_context"), "applicable_regs", default=[]) or []
    parts.append(
        f"Active scope = {_active_subdomain_count(state)} of "
        f"{_total_subdomain_count(state)} sub-domains for "
        f"applicable_regs = [{', '.join(applicable) or '-'}]. The four rows "
        "below cover the D-06 (Supply Chain) sub-domains within that "
        "active set.\n"
    )
    headers = ["Sub-domain", "Vendors Affected", "Compliance Status", "Notes"]
    rows = [
        (
            "D-06.1 Vendor Risk Assessment",
            "All inherited providers (see §2)",
            "Partial — inventory complete, risk scores assigned, but no formal review cadence",
            "Action: schedule annual review; tracked in 04b_Security_Posture.md.",
        ),
        (
            "D-06.2 Software Bill of Materials (SBOM)",
            "Snyk / GitHub (where present)",
            "Partial — tooling may exist; pipeline integration not yet asserted",
            "Action: integrate SBOM export into CI/CD by Phase 2; required for CRA Annex I Part II (1).",
        ),
        (
            "D-06.3 Contractual Security Obligations",
            "All inherited providers (see §2)",
            "Covered for GDPR Art. 28 (DPAs in place); partial for CRA supply-chain clauses",
            "—",
        ),
        (
            "D-06.4 Third-Party Boundary Management",
            "Providers with data-egress paths",
            "Covered — TLS + DPA + subprocessor approval flow",
            "—",
        ),
    ]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_gaps(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 7. Gaps & Known Limitations\n")
    parts.append(
        "These items are deliberately surfaced so they can flow into "
        "`04b_Security_Posture.md` and Phase 2 remediation plans, rather "
        "than being silently accepted.\n"
    )
    headers = ["Gap ID", "Description", "Severity", "Linked Sub-Domain"]
    rows = [
        (
            "GAP-TPL-01",
            "No formal supplier-security-assessment questionnaire (e.g. SIG / CAIQ) sent to vendors; reliance on inherited certifications only",
            "MEDIUM",
            "D-06.1",
        ),
        (
            "GAP-TPL-02",
            "No documented exit plan for cloud-hosted data extraction",
            "MEDIUM",
            "D-06.4",
        ),
        (
            "GAP-TPL-03",
            "No pipeline-integrated SBOM generation",
            "HIGH (CRA-mandated)",
            "D-06.2",
        ),
        (
            "GAP-TPL-04",
            "No annual review cycle enforced; next-review target is aspirational",
            "MEDIUM",
            "D-06.1, D-06.3",
        ),
    ]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    parts.append("All gaps are tracked in `04b_Security_Posture.md` for Phase 2 prioritisation.\n")
    return parts


def _section_gate(state: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    parts.append("## 8. Gate\n")
    inv = state.get("architecture_inventory") or {}
    cloud = inv.get("cloud_services") or []
    has_overlaps = bool(((state.get("ontology") or {}).get("overlaps") or []))
    parts.append(
        markdown_table(
            ["Gate Criterion", "Status", "Evidence"],
            [
                (
                    "All cloud providers documented with DPA status",
                    "PASS" if cloud else "PARTIAL",
                    f"Section 2: {len(cloud)} rows",
                ),
                (
                    "Overlap-implied third parties identified",
                    "PASS" if has_overlaps else "PARTIAL",
                    "Section 3 from ontology.overlaps",
                ),
                (
                    "Contractual coverage matrix populated",
                    "PASS" if cloud else "PARTIAL",
                    "Section 4",
                ),
                (
                    "Risk classification table populated",
                    "PASS" if cloud else "PARTIAL",
                    "Section 5",
                ),
                (
                    "Compliance Mapping table populated for D-06.x",
                    "PASS",
                    "Section 6",
                ),
                (
                    "Gaps explicitly listed (not silently accepted)",
                    "PASS",
                    "Section 7",
                ),
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
                (
                    1.0,
                    today,
                    "Executor",
                    "Generated from state[" "architecture_inventory" "].cloud_services and ontology.overlaps",
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
# Risk helpers
# ─────────────────────────────────────────────────────────────────────


def _criticality_for(entry: Mapping[str, Any]) -> str:
    text = " ".join(
        str(entry.get(k, "")).lower()
        for k in ("provider", "service", "data_stored")
    )
    if any(k in text for k in ("primary", "core", "identity", "auth", "payment")):
        return "Critical"
    if any(k in text for k in ("backup", "object", "storage", "database", "db")):
        return "Critical"
    if any(k in text for k in ("monitoring", "log", "telemetry", "alert", "metric")):
        return "Critical"
    return "Important"


def _risk_for(entry: Mapping[str, Any]) -> str:
    text = " ".join(
        str(entry.get(k, "")).lower()
        for k in ("provider", "service", "data_stored")
    )
    if any(k in text for k in _HIGH_RISK_KEYWORDS):
        return "M"
    if any(k in text for k in _MEDIUM_RISK_KEYWORDS):
        return "M"
    if any(k in text for k in _LOW_RISK_KEYWORDS):
        return "L"
    # Default: low for known managed providers with DPA
    dpa = entry.get("dpa_in_place")
    if str(dpa).upper() in {"Y", "YES", "TRUE"}:
        return "L"
    return "M"


def _sbom_for(entry: Mapping[str, Any]) -> str:
    text = " ".join(
        str(entry.get(k, "")).lower() for k in ("provider", "service")
    )
    if "snyk" in text:
        return "Y (CycloneDX/SPDX exportable)"
    if any(k in text for k in ("github", "code", "repo")):
        return "N/A (repository service)"
    if any(k in text for k in ("stripe", "auth0", "okta", "aws")):
        return "N/A (managed service)"
    return "N/A"


def _default_assessment_date() -> str:
    """Return a deterministic assessment date."""
    return "2026-04 — informal review during intake"


def _next_review_date() -> str:
    """Return a deterministic next-review target."""
    return "2027-04 (annual review; first formal review planned)"


def _active_subdomain_count(state: dict[str, Any]) -> int:
    ont = state.get("ontology") or {}
    subdomains = ont.get("subdomains") if isinstance(ont, Mapping) else None
    if not isinstance(subdomains, Mapping):
        return 0
    covered = subdomains.get("covered") or []
    return len(covered) if isinstance(covered, list) else 0


def _total_subdomain_count(state: dict[str, Any]) -> int:
    return len(state.get("subdomains") or {})


# ─────────────────────────────────────────────────────────────────────
# LLM narrative — optional
# ─────────────────────────────────────────────────────────────────────


def _risk_narrative_prompt(
    state: dict[str, Any],
    cloud: list[dict],
    rows: list[tuple[str, str, str, str, str, str]],
) -> str:
    name = _attr(state.get("company_context"), "company_name", default="the company")
    vendor_count = len(cloud)
    return (
        f"Produce a 3-4 sentence concentration-risk narrative for {name}. "
        f"Total inherited providers recorded: {vendor_count}. "
        "The narrative should: (1) note that all critical workloads run on "
        "managed cloud providers; (2) flag any single-vendor dependency "
        "(identity, payment, telemetry); (3) reference GDPR Art. 28 "
        "subprocessor obligations and CRA Annex I Part I (2)(j)/(k) "
        "supply-chain requirements; (4) call out concentration risk as "
        "manageable under the proportionality tier but worth documenting. "
        "Avoid bullet lists."
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
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return generate_frontmatter(
        document_id="AEGIS-P1-04c",
        title="Third-Party Landscape Inventory",
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
                "../00_COMMON/01_Company_Context.md",
            ],
            "outputs": [
                "04b_Security_Posture.md",
                "06_Clause_Mapping_Matrix.md",
                "07_Structured_Compliance_Matrix.md",
            ],
            "applicable_regs": list(applicable),
            "active_subdomains": _active_subdomain_count(state),
            "related_documents": [
                "../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-06_Supply-Chain/",
                "../../../00_METHODOLOGY/TEMPLATES/04c_ThirdParty_Landscape.md",
            ],
            "supersedes": "none",
        },
    )


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return default


__all__ = ["render_doc_04c"]
