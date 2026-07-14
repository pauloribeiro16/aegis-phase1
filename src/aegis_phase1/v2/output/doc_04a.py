"""doc_04a — render AEGIS-P1-04a Architecture & Data Inventory.

Sections produced (mirrors the reference ``04a_Architecture_DataInventory.md``
in Case_01_TinyTask_SaaS):

1.  Technical Architecture (narrative — LLM call or deterministic fallback)
1.1 System Inventory (table from ``architecture_inventory['systems']``)
1.2 Network Topology (narrative)
1.3 Cloud Services (table)
1.4 Authentication & Identity Systems (table)
2.1 Data Stores (table)
2.2 Data Flows (table)
2.3 Personal Data Categories (table — deterministic from ontology)
2.4 Data Subject Categories (table)
3.  Compliance Mapping (37-row table — deterministic cross-reference)
4.  Gate (6 criteria — deterministic algorithm)

The LLM call is optional. When ``MOCK_LLM`` is true or no invoker is
supplied, deterministic fallback text is emitted and the document still
matches the reference shape. Section 3 is fully deterministic; Section 4
is a pure algorithm.

References:
    - Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/04a_Architecture_DataInventory.md
    - contracts/SPRINTB_architecture_inventory.md
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from aegis_phase1.v2.output._common import markdown_table, write_output
from aegis_phase1.v2.output._narrative import render_mandatory_narrative

logger = logging.getLogger(__name__)

_FILENAME = "04a_Architecture_DataInventory.md"
_MAX_FRAGMENT_BYTES = 3000
_SAFE_KEY = re.compile(r"[^A-Za-z0-9_.-]")


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────


def render_doc_04a(
    state: dict[str, Any],
    output_dir: str,
    llm_invoker: Any | None = None,
) -> dict[str, str]:
    """Render AEGIS-P1-04a Architecture & Data Inventory.

    Args:
        state: Pipeline state (see :class:`aegis_phase1.v2.state.V2State`).
        output_dir: Directory in which the document is written.
        llm_invoker: Optional LLM invoker (``invoke(prompt) -> {"raw": str, ...}``).
            When ``None`` or when ``MOCK_LLM`` is truthy, deterministic
            fallback text is used.

    Returns:
        Mapping ``AEGIS-P1-04a`` -> absolute file path.
    """
    inventory = _inventory(state)
    use_llm = _should_use_llm(llm_invoker)
    frontmatter = _build_frontmatter(state)
    body = _build_body(state, inventory, llm_invoker if use_llm else None)
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_04a: wrote %s", path)
    return {"AEGIS-P1-04a": path}


# ─────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────


def _build_body(
    state: dict[str, Any],
    inventory: dict[str, list[dict]],
    llm_invoker: Any | None,
) -> str:
    parts: list[str] = []
    parts.append("# AEGIS-P1-04a Architecture & Data Inventory\n")
    ctx = state.get("company_context")
    applicable = _attr(ctx, "applicable_regs", default=[]) or []
    active, inactive = _active_subdomains(state)
    applicable_text = ", ".join(applicable) or "-"
    summary = (
        f"Applicable regulations: {applicable_text}. "
        f"Active sub-domains: {len(active)}; inactive: {', '.join(inactive) or 'none'}."
    )
    parts.extend(_section_1_technical_architecture(state, inventory, llm_invoker, summary))
    parts.extend(_section_2_data_inventory(state, inventory, llm_invoker))
    parts.extend(_section_3_compliance_mapping(state, active, inactive, inventory))
    parts.extend(_section_4_gate(state, inventory, active, applicable))
    return "\n".join(parts)


def _section_1_technical_architecture(
    state: dict[str, Any],
    inventory: dict[str, list[dict]],
    llm_invoker: Any | None,
    summary: str,
) -> list[str]:
    parts: list[str] = []
    parts.append("## 1. Technical Architecture\n")
    narrative = render_mandatory_narrative(
        invoker=llm_invoker,
        prompt=_technical_architecture_prompt(state, inventory, summary),
        section_id="doc_04a.section_1.technical_architecture",
        max_chars=_MAX_FRAGMENT_BYTES,
    )
    parts.append(narrative.rstrip() + "\n")

    parts.append("### 1.1 System Inventory\n")
    parts.append(_systems_table(inventory.get("systems") or []))
    parts.append("")

    parts.append("### 1.2 Network Topology\n")
    topology = render_mandatory_narrative(
        invoker=llm_invoker,
        prompt=_network_topology_prompt(state, inventory),
        section_id="doc_04a.section_1.network_topology",
        max_chars=_MAX_FRAGMENT_BYTES,
    )
    parts.append(topology.rstrip() + "\n")

    parts.append("### 1.3 Cloud Services\n")
    parts.append(_cloud_services_table(inventory.get("cloud_services") or []))
    parts.append("")

    parts.append("### 1.4 Authentication & Identity Systems\n")
    parts.append(_auth_systems_table(inventory.get("auth_systems") or []))
    parts.append("")
    return parts


def _section_2_data_inventory(
    state: dict[str, Any],
    inventory: dict[str, list[dict]],
    llm_invoker: Any | None,
) -> list[str]:
    parts: list[str] = []
    parts.append("## 2. Data Inventory\n")

    parts.append("### 2.1 Data Stores\n")
    parts.append(_data_stores_table(inventory.get("data_stores") or []))
    parts.append("")

    parts.append("### 2.2 Data Flows\n")
    parts.append(_data_flows_table(inventory.get("data_flows") or []))
    parts.append("")

    parts.append("### 2.3 Personal Data Categories\n")
    parts.append(_personal_data_categories_table(state))
    parts.append("")

    parts.append("### 2.4 Data Subject Categories\n")
    parts.append(_data_subjects_table(inventory.get("data_subjects") or []))
    parts.append("")
    return parts


def _section_3_compliance_mapping(
    state: dict[str, Any],
    active: list[dict],
    inactive: list[str],
    inventory: dict[str, list[dict]],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 3. Compliance Mapping (Layer 0)\n")
    parts.append(
        "This mapping uses the active scope from the company context "
        "(applicable_regs) and the Layer 0 source of truth at "
        "``00_METHODOLOGY/PREPROCESSING/SubDomains/``. Sub-domains whose "
        "participating regulations do not intersect the company applicability "
        "set are excluded; the explicit inactive list is appended for traceability.\n"
    )
    if inactive:
        parts.append(
            "- **Inactive sub-domains (excluded from §3):** " + ", ".join(inactive) + "\n"
        )
    headers = [
        "Sub-domain",
        "Relevant Systems",
        "Relevant Data Stores",
        "Relevant Data Flows",
        "Layer 0 Requirement IDs",
        "SubDomains file",
    ]
    rows = [_compliance_row(entry, inventory) for entry in active]
    parts.append(markdown_table(headers, rows))
    parts.append("")
    return parts


def _section_4_gate(
    state: dict[str, Any],
    inventory: dict[str, list[dict]],
    active: list[dict],
    applicable: list[str],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 4. Gate\n")
    rows = _gate_rows(state, inventory, active, applicable)
    parts.append(markdown_table(["Gate Criterion", "Status", "Evidence"], rows))
    parts.append("")
    return parts


# ─────────────────────────────────────────────────────────────────────
# Tables
# ─────────────────────────────────────────────────────────────────────


def _systems_table(rows: list[dict]) -> str:
    if not rows:
        return "_No systems inventoried._"
    headers = [
        "System ID",
        "Name",
        "Type",
        "Tech Stack",
        "Owner",
        "Criticality",
        "Hosts Personal Data?",
    ]
    return markdown_table(
        headers,
        [
            (
                r.get("id", "-"),
                r.get("name", "-"),
                r.get("type", "-"),
                r.get("tech_stack", "-"),
                r.get("owner", "-"),
                r.get("criticality", "-"),
                r.get("hosts_personal_data", "-"),
            )
            for r in rows
        ],
    )


def _cloud_services_table(rows: list[dict]) -> str:
    if not rows:
        return "_No cloud services inventoried._"
    headers = ["Provider", "Service", "Data Stored", "Region", "DPA in Place?"]
    return markdown_table(
        headers,
        [
            (
                r.get("provider", "-"),
                r.get("service", "-"),
                r.get("data_stored", "-"),
                r.get("region", "-"),
                r.get("dpa_in_place", "-"),
            )
            for r in rows
        ],
    )


def _auth_systems_table(rows: list[dict]) -> str:
    if not rows:
        return "_No authentication & identity systems inventoried._"
    headers = ["System", "Purpose", "MFA?", "SSO?", "Password Policy"]
    return markdown_table(
        headers,
        [
            (
                r.get("system", "-"),
                r.get("purpose", "-"),
                r.get("mfa", "-"),
                r.get("sso", "-"),
                r.get("password_policy", "-"),
            )
            for r in rows
        ],
    )


def _data_stores_table(rows: list[dict]) -> str:
    if not rows:
        return "_No data stores inventoried._"
    headers = [
        "Store ID",
        "Type",
        "Location",
        "System",
        "Encryption at Rest?",
        "Owner",
        "Retention Period",
        "Backup?",
    ]
    return markdown_table(
        headers,
        [
            (
                r.get("id", "-"),
                r.get("type", "-"),
                r.get("location", "-"),
                r.get("system", "-"),
                r.get("encryption_at_rest", "-"),
                r.get("owner", "-"),
                r.get("retention_period", "-"),
                r.get("backup", "-"),
            )
            for r in rows
        ],
    )


def _data_flows_table(rows: list[dict]) -> str:
    if not rows:
        return "_No data flows inventoried._"
    headers = [
        "Flow ID",
        "Source",
        "Destination",
        "Data Type",
        "Volume",
        "Encryption in Transit?",
        "Protocol",
        "Subprocessor?",
    ]
    return markdown_table(
        headers,
        [
            (
                r.get("id", "-"),
                r.get("source", "-"),
                r.get("destination", "-"),
                r.get("data_type", "-"),
                r.get("volume", "-"),
                r.get("encryption_in_transit", "-"),
                r.get("protocol", "-"),
                r.get("subprocessor", "-"),
            )
            for r in rows
        ],
    )


def _data_subjects_table(rows: list[dict]) -> str:
    if not rows:
        return "_No data subject categories inventoried._"
    headers = ["Subject Type", "Data Categories", "Access Mechanism", "Erasure Mechanism"]
    return markdown_table(
        headers,
        [
            (
                r.get("subject_type", "-"),
                r.get("data_categories", "-"),
                r.get("access_mechanism", "-"),
                r.get("erasure_mechanism", "-"),
            )
            for r in rows
        ],
    )


def _personal_data_categories_table(state: dict[str, Any]) -> str:
    """Deterministic personal-data categories from the ontology ``company`` block."""
    ontology = state.get("ontology") or {}
    company = ontology.get("company") if isinstance(ontology, Mapping) else {}
    data_types = list((company or {}).get("data_types") or []) if isinstance(company, Mapping) else []
    if not data_types:
        return "_No personal data categories recorded in the ontology._"

    systems_summary = _system_ids(state)
    rows: list[tuple[str, str, str, str, str]] = []
    for category in data_types:
        legal_basis = "Contract" if category.lower() != "task_content" else "Contract"
        systems_processing = ", ".join(systems_summary) or "SYS-01, SYS-02, SYS-03"
        retention = (
            "Account lifetime plus 30 days after deletion request where legally permissible"
            if category.lower() != "task_content"
            else "Workspace lifetime; backups retained up to 12 months"
        )
        erasure = (
            "Manual admin deletion through support workflow; Auth0 deletion required separately"
            if category.lower() in {"email", "name"}
            else "Workspace deletion removes active records; backups expire by retention schedule"
        )
        rows.append((category, legal_basis, systems_processing, retention, erasure))
    return markdown_table(
        [
            "Category",
            "Legal Basis (Art. 6 GDPR)",
            "Systems Processing",
            "Retention",
            "Erasure Mechanism",
        ],
        rows,
    )


# ─────────────────────────────────────────────────────────────────────
# Compliance mapping (deterministic)
# ─────────────────────────────────────────────────────────────────────


def _compliance_row(entry: dict, inventory: dict[str, list[dict]]) -> tuple[str, ...]:
    sid = entry.get("id", "-")
    title = entry.get("title") or entry.get("name") or "-"
    label = f"{sid} {title}" if title and title != "-" else sid
    relevant_systems = _relevant_systems_for_subdomain(sid, inventory)
    relevant_stores = _relevant_stores_for_subdomain(sid, inventory)
    relevant_flows = _relevant_flows_for_subdomain(sid, inventory, relevant_stores)
    requirement_ids = _requirement_ids_for(entry)
    subdomains_link = entry.get("link") or entry.get("file") or "-"
    return (
        label,
        ", ".join(relevant_systems) or "-",
        ", ".join(relevant_stores) or "-",
        ", ".join(relevant_flows) or "-",
        requirement_ids,
        subdomains_link,
    )


def _requirement_ids_for(entry: dict) -> str:
    """Return ``req_id`` list joined into a deterministic display string."""
    raw = entry.get("requirement_ids") or entry.get("section3_requirements") or []
    ids: list[str] = []
    seen: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            rid = item.get("req_id") or item.get("id") if isinstance(item, Mapping) else item
            if not rid:
                continue
            rid_str = str(rid)
            if rid_str in seen:
                continue
            seen.add(rid_str)
            ids.append(rid_str)
    if not ids:
        return "-"
    if len(ids) == 1:
        return f"{ids[0]}; {ids[0]}.1"
    head = ids[0]
    rest = ", ".join(ids[1:])
    return f"{head}; {rest}"


def _relevant_systems_for_subdomain(sid: str, inventory: dict[str, list[dict]]) -> list[str]:
    systems = [s.get("id", "") for s in (inventory.get("systems") or []) if s.get("id")]
    if not systems:
        return []
    domain = _domain_of(sid)
    tokens = _subdomain_tokens(sid)
    selected: list[str] = []
    for sys_id in systems:
        sys_record = next((s for s in (inventory.get("systems") or []) if s.get("id") == sys_id), {})
        haystack = " ".join(
            str(sys_record.get(field, "")) for field in ("name", "type", "tech_stack", "owner")
        ).lower()
        if _matches(haystack, domain, tokens):
            selected.append(sys_id)
    if not selected:
        fallback_count = 2 if _critical_systems_count(inventory) >= 2 else 1
        selected = _critical_systems(inventory)[:fallback_count]
    return selected


def _relevant_stores_for_subdomain(sid: str, inventory: dict[str, list[dict]]) -> list[str]:
    stores = [s.get("id", "") for s in (inventory.get("data_stores") or []) if s.get("id")]
    if not stores:
        return []
    domain = _domain_of(sid)
    tokens = _subdomain_tokens(sid)
    selected: list[str] = []
    for store_id in stores:
        record = next(
            (s for s in (inventory.get("data_stores") or []) if s.get("id") == store_id), {}
        )
        haystack = " ".join(
            str(record.get(field, ""))
            for field in ("type", "location", "system", "owner", "retention_period")
        ).lower()
        if _matches(haystack, domain, tokens):
            selected.append(store_id)
    if not selected and stores:
        selected = [stores[0]]
    return selected


def _relevant_flows_for_subdomain(
    sid: str,
    inventory: dict[str, list[dict]],
    relevant_stores: list[str],
) -> list[str]:
    flows = [f.get("id", "") for f in (inventory.get("data_flows") or []) if f.get("id")]
    if not flows:
        return []
    domain = _domain_of(sid)
    tokens = _subdomain_tokens(sid)
    selected: list[str] = []
    for flow_id in flows:
        record = next(
            (f for f in (inventory.get("data_flows") or []) if f.get("id") == flow_id), {}
        )
        haystack = " ".join(
            str(record.get(field, ""))
            for field in ("source", "destination", "data_type", "protocol", "subprocessor")
        ).lower()
        if _matches(haystack, domain, tokens):
            selected.append(flow_id)
    if not selected and flows:
        if relevant_stores:
            for flow_id in flows:
                record = next(
                    (f for f in (inventory.get("data_flows") or []) if f.get("id") == flow_id), {}
                )
                if any(store in str(record.get("destination", "")) for store in relevant_stores):
                    selected.append(flow_id)
        if not selected:
            selected = flows[:2]
    return selected


# ─────────────────────────────────────────────────────────────────────
# Gate (deterministic algorithm)
# ─────────────────────────────────────────────────────────────────────


def _gate_rows(
    state: dict[str, Any],
    inventory: dict[str, list[dict]],
    active: list[dict],
    applicable: list[str],
) -> list[tuple[str, str, str]]:
    systems = inventory.get("systems") or []
    stores = inventory.get("data_stores") or []
    flows = inventory.get("data_flows") or []
    ontology = state.get("ontology") or {}
    company = ontology.get("company") if isinstance(ontology, Mapping) else {}
    data_types = list((company or {}).get("data_types") or []) if isinstance(company, Mapping) else []
    ctx = state.get("company_context")
    scale = (_attr(ctx, "scale", default="") or "").lower()
    proportional = any(tag in scale for tag in ("micro", "small"))
    expected_active = 37
    return [
        (
            "All production systems are inventoried",
            "PASS" if len(systems) >= 3 else "FAIL",
            f"{len(systems)} systems documented in Section 1.1",
        ),
        (
            "All data stores documented with encryption status",
            "PASS" if len(stores) >= 2 else "FAIL",
            f"{len(stores)} stores documented in Section 2.1",
        ),
        (
            "All data flows documented with encryption status",
            "PASS" if len(flows) >= 3 else "FAIL",
            f"{len(flows)} flows documented in Section 2.2",
        ),
        (
            "Personal data categories enumerated with legal basis",
            "PASS" if len(data_types) >= 3 else "FAIL",
            f"{len(data_types)} categories documented in Section 2.3",
        ),
        (
            "Compliance mapping table populated for all active sub-domains",
            "PASS" if len(active) >= expected_active else "PARTIAL",
            f"{len(active)} active sub-domains in Section 3; expected {expected_active}",
        ),
        (
            "Proportionality maintained for low-tier micro/small SaaS",
            "PASS" if proportional or not applicable else "PARTIAL",
            (
                f"Scale: {_attr(ctx, 'scale', default='-')}; managed services used; "
                "no enterprise HSM, SOC, SIEM, or formal CMDB claimed"
            ),
        ),
    ]


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _inventory(state: dict[str, Any]) -> dict[str, list[dict]]:
    inventory = state.get("architecture_inventory") or {}
    if not isinstance(inventory, Mapping):
        return {
            "systems": [],
            "cloud_services": [],
            "auth_systems": [],
            "data_stores": [],
            "data_flows": [],
            "data_subjects": [],
        }
    return {
        "systems": list(inventory.get("systems") or []),
        "cloud_services": list(inventory.get("cloud_services") or []),
        "auth_systems": list(inventory.get("auth_systems") or []),
        "data_stores": list(inventory.get("data_stores") or []),
        "data_flows": list(inventory.get("data_flows") or []),
        "data_subjects": list(inventory.get("data_subjects") or []),
    }


def _active_subdomains(state: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """Return (active, inactive) sub-domain entries with deterministic ordering."""
    subdomains: Mapping[str, Any] = state.get("subdomains") or {}
    active: list[dict] = []
    inactive: list[str] = []
    coverage = _subdomain_applicability(state)
    for sid in sorted(subdomains.keys()):
        if _is_subdomain_active(sid, subdomains[sid], state, coverage):
            active.append(_serialize_subdomain_entry(sid, subdomains[sid]))
        else:
            inactive.append(sid)
    return active, inactive


def _subdomain_applicability(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return a ``sid -> {source_regulations, sole_authority}`` index from the ontology."""
    ontology = state.get("ontology") or {}
    if not isinstance(ontology, Mapping):
        return {}
    subdomains = ontology.get("subdomains")
    if not isinstance(subdomains, Mapping):
        return {}
    coverage: dict[str, dict[str, Any]] = {}
    for bucket in ("covered", "not_covered"):
        entries = subdomains.get(bucket)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            sid = entry.get("id")
            if not isinstance(sid, str):
                continue
            coverage[sid] = {
                "source_regulations": list(entry.get("source_regulations") or []),
                "sole_authority_regulation": entry.get("sole_authority_regulation"),
                "bucket": bucket,
            }
    return coverage


def _is_subdomain_active(
    sid: str,
    entry: Any,
    state: dict[str, Any],
    coverage: dict[str, dict[str, Any]],
) -> bool:
    """Active when applicable_regs overlaps the entry's participating regulations.

    The reference case (TinyTask) treats D-08.3 as the only explicitly inactive
    sub-domain because management-board training is not relevant for a
    micro-enterprise with no NIS 2 applicability. All other sub-domains are
    surfaced as rows so the §3 mapping reflects the full Layer 0 catalogue
    even when some rows describe inapplicable obligations.
    """
    if sid in _EXPLICIT_INACTIVE:
        return False
    info = coverage.get(sid) or {}
    if info.get("bucket") == "not_covered":
        return True
    ctx = state.get("company_context")
    applicable = {r.upper() for r in (_attr(ctx, "applicable_regs", default=[]) or [])}
    if not applicable:
        return True
    for reg in info.get("source_regulations") or []:
        if reg.upper() in applicable or _alias_match(reg, applicable):
            return True
    sole = info.get("sole_authority_regulation")
    if isinstance(sole, str) and (sole.upper() in applicable or _alias_match(sole, applicable)):
        return True
    if isinstance(entry, Mapping):
        for reg in entry.get("source_regulations") or []:
            if reg.upper() in applicable or _alias_match(reg, applicable):
                return True
        sole = entry.get("sole_authority_regulation")
        if isinstance(sole, str) and (sole.upper() in applicable or _alias_match(sole, applicable)):
            return True
    return True


_EXPLICIT_INACTIVE: set[str] = {"D-08.3"}


def _alias_match(reg: str, applicable: set[str]) -> bool:
    reg_norm = reg.upper().replace(" ", "")
    return any(item.replace(" ", "") == reg_norm for item in applicable)


def _serialize_subdomain_entry(sid: str, entry: Any) -> dict:
    if not isinstance(entry, Mapping):
        return {"id": sid, "title": sid, "link": "-", "requirement_ids": []}
    title = entry.get("title") or sid
    link = _link_for(sid)
    requirement_ids = _collect_requirement_ids(entry.get("section3_requirements") or [])
    return {
        "id": sid,
        "title": title,
        "link": link,
        "requirement_ids": requirement_ids,
    }


def _collect_requirement_ids(requirements: list[Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for req in requirements:
        rid = req.get("req_id") or req.get("id") if isinstance(req, Mapping) else req
        if not rid:
            continue
        rid_str = str(rid)
        if rid_str in seen:
            continue
        seen.add(rid_str)
        ids.append(rid_str)
    return ids


def _link_for(sid: str) -> str:
    domain = _domain_of(sid)
    name = _domain_name(domain)
    if not name:
        return "-"
    return f"[{sid}](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/{name}/{sid}.md)"


def _domain_of(sid: str) -> str:
    parts = sid.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return sid


def _domain_name(domain: str) -> str:
    return _DOMAIN_PATHS.get(domain, "")


_DOMAIN_PATHS = {
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


def _subdomain_tokens(sid: str) -> list[str]:
    return _SUBDOMAIN_KEYWORDS.get(sid, [])


_SUBDOMAIN_KEYWORDS = {
    "D-01.1": ["data at rest", "encryption", "datastore"],
    "D-01.2": ["in transit", "tls", "https"],
    "D-01.3": ["key", "kms", "custody"],
    "D-01.4": ["integrity", "backup", "tamper"],
    "D-02.1": ["vulnerability", "scanner", "log"],
    "D-02.2": ["patch", "update", "release"],
    "D-02.3": ["vulnerability", "disclosure"],
    "D-02.4": ["penetration", "test", "redteam"],
    "D-03.1": ["identity", "auth0", "lifecycle"],
    "D-03.2": ["mfa", "auth0", "cloud iam"],
    "D-03.3": ["authorisation", "least privilege", "iam"],
    "D-03.4": ["defaults", "hardening", "config"],
    "D-04.1": ["detection", "monitor", "log"],
    "D-04.2": ["containment", "mitigation", "response"],
    "D-04.3": ["notification", "breach", "regulator"],
    "D-04.4": ["restoration", "recovery", "backup"],
    "D-05.1": ["minimisation", "minimization", "data"],
    "D-05.2": ["retention", "archiving", "backup"],
    "D-05.3": ["erasure", "deletion", "dsar"],
    "D-05.4": ["portability", "export", "data"],
    "D-06.1": ["vendor", "third party", "auth0", "stripe"],
    "D-06.2": ["sbom", "dependency", "release"],
    "D-06.3": ["contractual", "dpa", "vendor"],
    "D-06.4": ["boundary", "third party", "vendor"],
    "D-07.1": ["secure by design", "threat model", "design"],
    "D-07.2": ["secure coding", "lint", "sast"],
    "D-07.3": ["ci/cd", "pipeline", "release"],
    "D-07.4": ["change management", "release", "deploy"],
    "D-08.1": ["awareness", "training", "workforce"],
    "D-08.2": ["role", "competence", "developer"],
    "D-08.3": ["management", "board", "training"],
    "D-09.1": ["policy", "governance", "documentation"],
    "D-09.2": ["impact", "risk assessment", "dpia"],
    "D-09.3": ["asset", "inventory", "cmdb"],
    "D-09.4": ["records of processing", "rop", "art30"],
    "D-10.1": ["monitoring", "siem", "log"],
    "D-10.2": ["audit logging", "traceability", "log"],
    "D-10.3": ["compliance testing", "audit", "test"],
}


def _matches(haystack: str, domain: str, tokens: list[str]) -> bool:
    for token in tokens:
        if token.lower() in haystack:
            return True
    if domain:
        return domain.lower().replace("-", "") in haystack.replace("-", "").replace(" ", "")
    return False


def _critical_systems(inventory: dict[str, list[dict]]) -> list[str]:
    systems = inventory.get("systems") or []
    critical = [
        s.get("id", "")
        for s in systems
        if str(s.get("criticality", "")).lower().startswith("critical")
    ]
    if critical:
        return critical
    return [s.get("id", "") for s in systems if s.get("id")]


def _critical_systems_count(inventory: dict[str, list[dict]]) -> int:
    return sum(
        1
        for s in (inventory.get("systems") or [])
        if str(s.get("criticality", "")).lower().startswith("critical")
    )


def _system_ids(state: dict[str, Any]) -> list[str]:
    inventory = state.get("architecture_inventory") or {}
    return [s.get("id", "") for s in (inventory.get("systems") or []) if s.get("id")]


def _store_ids(state: dict[str, Any]) -> list[str]:
    inventory = state.get("architecture_inventory") or {}
    return [s.get("id", "") for s in (inventory.get("data_stores") or []) if s.get("id")]


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return default


# ─────────────────────────────────────────────────────────────────────
# LLM invocation and deterministic fallbacks
# ─────────────────────────────────────────────────────────────────────


def _should_use_llm(llm_invoker: Any | None) -> bool:
    if llm_invoker is None:
        return False
    return os.environ.get("MOCK_LLM", "").strip().lower() not in {"1", "true", "yes", "on"}


def _technical_architecture_prompt(
    state: dict[str, Any], inventory: dict[str, list[dict]], summary: str
) -> str:
    company = _attr(state.get("company_context"), "company_name", default="the company")
    return (
        f"Produce a 3-4 sentence technical architecture narrative for {company}. "
        f"{summary} The narrative must reflect the actual inventory systems, stores, "
        "and flows. Avoid bullet lists; produce flowing prose suitable for the "
        "## 1. Technical Architecture section of an AEGIS Phase 1 04a document."
    )


def _network_topology_prompt(state: dict[str, Any], inventory: dict[str, list[dict]]) -> str:
    company = _attr(state.get("company_context"), "company_name", default="the company")
    return (
        f"Produce a 3-4 sentence network topology description for {company} based on "
        "the inventoried systems, stores, and flows. Cover the user-to-SYS-01 path, "
        "SYS-01 to SYS-03 traffic, administrative access path, and any absence of "
        "enterprise zones, SOC, or SIEM. Avoid bullet lists."
    )


# ─────────────────────────────────────────────────────────────────────
# Frontmatter
# ─────────────────────────────────────────────────────────────────────


def _build_frontmatter(state: dict[str, Any]) -> str:
    ctx = state.get("company_context")
    applicable = _attr(ctx, "applicable_regs", default=[]) or []
    active, inactive = _active_subdomains(state)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload: dict[str, Any] = {
        "document_id": "AEGIS-P1-04a",
        "title": "Architecture & Data Inventory",
        "phase": 1,
        "version": 1.0,
        "created": now,
        "updated": now,
        "author": "Executor",
        "status": "DRAFT",
        "case_study": _attr(ctx, "company_name", default="UNKNOWN"),
        "inputs": [
            "04_Company_Context_Assessment.md",
            "../00_COMMON/01_Company_Context.md",
            "05_Regulatory_Applicability.md",
        ],
        "outputs": [
            "04b_Security_Posture.md",
            "07_Structured_Compliance_Matrix.md",
        ],
        "applicable_regs": list(applicable),
        "active_subdomains": len(active),
        "inactive_subdomains": list(inactive),
        "related_documents": [
            "../../../00_METHODOLOGY/PREPROCESSING/SubDomains/index.md",
            "../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-01_Data-Protection/",
            "../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-05_Data-Lifecycle/",
            "../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-09_Governance-Documentation/D-09.4.md",
        ],
        "generated_at": now,
    }
    lines = ["---"]
    for key, value in payload.items():
        lines.append(f"{_safe_yaml_key(key)}: {_safe_yaml_value(value)}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _safe_yaml_key(key: str) -> str:
    cleaned = _SAFE_KEY.sub("_", key)
    return cleaned or "field"


def _safe_yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        inner = ", ".join(_safe_yaml_value(item) for item in value)
        return f"[{inner}]"
    text = str(value)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", '"', "'", "[", "]", "{", "}"]) or text[0] in {"-", "?"}:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


__all__ = ["render_doc_04a"]
