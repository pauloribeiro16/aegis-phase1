"""NIST CSF 1.1 → CSF 2.0 mapping builder (CORR-027).

Derives a 108-row mapping of all CSF 1.1 subcategories (NIST CSWP 41,
2018-04-16) to their CSF 2.0 destinations by combining four signals
from the csf2.xlsx Reference Tool (NIST CSWP 29, 2024-02-26):

1. **Active subcategory informative references** — the active row cites
   ``CSF v1.1: X.Y-N`` in its Informative References column.
2. **Withdrawn row informative references** — a v2.0 row that exists
   only as a withdrawal marker (e.g. ``PR.AC-01: [Withdrawn: ...]``)
   cites the v1.1 ID it represents; we then map the v1.1 ID to the
   parsed destinations in the tag.
3. **Withdrawn row id-strip** — the withdrawn row's own ID (e.g.
   ``PR.AC-01``) is in v2.0 form but represents a v1.1 ID with the
   same logical meaning (``PR.AC-1`` after stripping the leading
   zero). We use this as a second source of provenance.
4. **Category header references** — a v2.0 category header row (e.g.
   the ``## DE.AE`` description cell) may cite ``CSF v1.1: DE.DP-2``
   meaning the entire v2.0 category absorbed that v1.1 function.
   When the v1.1 ID is cited ONLY at the category level (not at any
   subcategory), we record a CATEGORY_LEVEL mapping.

The output is a deterministic JSON with provenance for every mapping,
plus special handling for the two known-fuzzy v1.1 IDs:

- ``DE.DP-2`` — only a category-level citation; recommend
  ``UNMAPPED_CSF`` in chain when no specific v2.0 subcategory captures
  the "detection process accountability" intent.
- ``RC.CO-2`` — withdrawn row says "Incorporated into RC.CO-04", but
  the active ``RC.CO-04`` does not cite ``RC.CO-2`` back. Flag as
  ``WITHDRAWN_DESTINATION_INCONSISTENT`` for human review.

Output schema: see ``preproc_out/global/csf_1_1_to_2_0_mapping.json``
(CORR-027 contract §4.1).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .csf_xlsx import parse_csf2

# CSF 1.1 official subcategory catalogue (NIST CSWP 41, 2018-04-16).
# 108 subcategories across 5 functions / 23 categories.
# The titles are taken verbatim from CSWP 41 §3.
_CSF_1_1_TITLES: dict[str, str] = {
    # ID.AM (6)
    "ID.AM-1": "Physical devices and systems within the organization are inventoried",
    "ID.AM-2": "Software platforms and applications within the organization are inventoried",
    "ID.AM-3": "Organizational communication and data flows are mapped",
    "ID.AM-4": "External information systems are catalogued",
    "ID.AM-5": "Resources (e.g., hardware, devices, data, time, people, and software) are prioritized based on their classification, criticality, and business value",
    "ID.AM-6": "Cybersecurity roles and responsibilities for the entire workforce and third-party stakeholders (e.g., suppliers, customers, partners) are established",
    # ID.BE (5)
    "ID.BE-1": "The organization's role in the supply chain is identified and communicated",
    "ID.BE-2": "The organization's place in critical infrastructure and its industry sector is identified and communicated",
    "ID.BE-3": "Priorities for organizational mission, objectives, and activities are established and communicated",
    "ID.BE-4": "Dependencies and critical functions for delivery of critical services are established",
    "ID.BE-5": "Resilience requirements to support delivery of critical services are established for all operating states (e.g., under duress/attack, during recovery, normal operations)",
    # ID.GV (4)
    "ID.GV-1": "Organizational cybersecurity policy is established and communicated",
    "ID.GV-2": "Cybersecurity roles and responsibilities are coordinated and aligned with internal roles and external partners",
    "ID.GV-3": "Legal and regulatory requirements regarding cybersecurity, including privacy and civil liberties obligations, are understood and managed",
    "ID.GV-4": "Governance and risk management processes address cybersecurity risks",
    # ID.RA (6)
    "ID.RA-1": "Asset vulnerabilities are identified, validated, and recorded",
    "ID.RA-2": "Cyber threat intelligence and vulnerability information is received from information sharing forums and sources",
    "ID.RA-3": "Threats, both internal and external, are identified and recorded",
    "ID.RA-4": "Potential business impacts and likelihoods of threats exploiting vulnerabilities are identified and recorded",
    "ID.RA-5": "Threats, vulnerabilities, likelihoods, and impacts are used to determine risk",
    "ID.RA-6": "Risk responses are identified, prioritized, and executed",
    # ID.RM (3)
    "ID.RM-1": "Risk management processes are established, managed, and agreed to by organizational stakeholders",
    "ID.RM-2": "Risk tolerance is determined and clearly expressed",
    "ID.RM-3": "The organization's determination of risk tolerance is informed by its role in critical infrastructure and sector-specific risk analysis",
    # ID.SC (5)
    "ID.SC-1": "Cyber supply chain risk management processes are identified, established, assessed, managed, and agreed to by organizational stakeholders",
    "ID.SC-2": "Suppliers and third-party partners of information systems, components, and services are identified, prioritized, and assessed using a cyber supply chain risk management process",
    "ID.SC-3": "Contracts with suppliers and third-party partners are used to implement appropriate measures designed to meet the objectives of an organization's cybersecurity program and Cyber Supply Chain Risk Management Plan",
    "ID.SC-4": "Suppliers and third-party partners are routinely assessed using audits, test results, or other forms of evaluation to confirm them meeting their contractual obligations",
    "ID.SC-5": "Response and recovery planning and testing are conducted with suppliers and third-party partners",
    # PR.AC (7)
    "PR.AC-1": "Identities and credentials are issued, managed, verified, revoked, and audited for authorized devices, users and processes",
    "PR.AC-2": "Physical access to assets is managed and protected",
    "PR.AC-3": "Logical access to assets is managed and protected",
    "PR.AC-4": "Access permissions and authorizations are managed, incorporating the principles of least privilege and separation of duties",
    "PR.AC-5": "Network integrity is protected (e.g., network segregation, network segmentation)",
    "PR.AC-6": "Users and devices are authenticated (e.g., multi-factor authentication) for access to organizational assets",
    "PR.AC-7": "Users, devices, and assets are authenticated (e.g., single-factor, multi-factor) commensurate with the risk of the transaction",
    # PR.AT (5)
    "PR.AT-1": "All users are informed and trained",
    "PR.AT-2": "Privileged users understand their roles and responsibilities",
    "PR.AT-3": "Third-party stakeholders (e.g., suppliers, customers, partners) understand their roles and responsibilities",
    "PR.AT-4": "Senior executives understand their roles and responsibilities",
    "PR.AT-5": "Physical and cybersecurity personnel understand their roles and responsibilities",
    # PR.DS (8)
    "PR.DS-1": "Data-at-rest is protected",
    "PR.DS-2": "Data-in-transit is protected",
    "PR.DS-3": "Assets are formally managed throughout removal, transfers, and disposition",
    "PR.DS-4": "Adequate resource capacity to ensure availability is maintained",
    "PR.DS-5": "Protections against data leaks are implemented",
    "PR.DS-6": "Integrity checking mechanisms are used to verify software, firmware, and information integrity",
    "PR.DS-7": "The development and testing environment(s) are separate from the production environment",
    "PR.DS-8": "Integrity checking mechanisms are used to verify hardware integrity",
    # PR.IP (12)
    "PR.IP-1": "A baseline configuration of information technology/industrial control systems is created and maintained incorporating appropriate security principles (e.g. concept of least functionality)",
    "PR.IP-2": "A System Development Life Cycle to manage systems is implemented",
    "PR.IP-3": "Configuration change control processes are in place",
    "PR.IP-4": "Backups of information are conducted, maintained, and tested periodically",
    "PR.IP-5": "Policy and regulations regarding the physical operating environment for organizational assets are met",
    "PR.IP-6": "Data is destroyed according to policy",
    "PR.IP-7": "Protection processes are improved",
    "PR.IP-8": "Effectiveness of protection processes is shared with appropriate parties",
    "PR.IP-9": "Response plans (Incident Response and Business Continuity) and recovery plans (Incident Recovery and Disaster Recovery) are in place and managed",
    "PR.IP-10": "Response and recovery plans are tested",
    "PR.IP-11": "Cybersecurity is included in human resources practices (e.g., deprovisioning, personnel screening)",
    "PR.IP-12": "A vulnerability management plan is developed and implemented",
    # PR.MA (2)
    "PR.MA-1": "Maintenance and repair of organizational assets are performed and logged, with approved and controlled tools",
    "PR.MA-2": "Remote maintenance of organizational assets is approved, logged, and performed in a manner that prevents unauthorized access",
    # PR.PT (5)
    "PR.PT-1": "Audit/log records are determined, documented, implemented, and reviewed in accordance with policy",
    "PR.PT-2": "Removable media is protected and its use restricted according to policy",
    "PR.PT-3": "The principle of least functionality is incorporated by configuring systems to provide only essential capabilities",
    "PR.PT-4": "Communications and control networks are protected",
    "PR.PT-5": "Mechanisms (e.g., failsafe, load balancing, hot swap) are implemented to achieve resilience requirements in normal and adverse situations",
    # DE.AE (5)
    "DE.AE-1": "A baseline of network operations and expected data flows for users and systems is established and managed",
    "DE.AE-2": "Detected events are analyzed to understand attack targets and methods",
    "DE.AE-3": "Event data are collected and correlated from multiple sources and sensors",
    "DE.AE-4": "Impact of events is determined",
    "DE.AE-5": "Incident alert thresholds are established",
    # DE.CM (8)
    "DE.CM-1": "The network is monitored to detect potential cybersecurity events",
    "DE.CM-2": "The physical environment is monitored to detect potential cybersecurity events",
    "DE.CM-3": "Personnel activity is monitored to detect potential cybersecurity events",
    "DE.CM-4": "Malicious code is detected",
    "DE.CM-5": "Unauthorized mobile code is detected",
    "DE.CM-6": "External service provider activity is monitored to detect potential cybersecurity events",
    "DE.CM-7": "Monitoring for unauthorized personnel, connections, devices, and software is performed",
    "DE.CM-8": "Vulnerability scans are performed",
    # DE.DP (5)
    "DE.DP-1": "Roles and responsibilities for detection are well defined to ensure accountability",
    "DE.DP-2": "Detection processes and procedures are understood and followed; detection information is communicated to ensure accountability",
    "DE.DP-3": "Detection processes and procedures are tested",
    "DE.DP-4": "Event detection information is communicated",
    "DE.DP-5": "Detection processes and procedures are improved",
    # RS.AN (5)
    "RS.AN-1": "Notifications from detection systems are investigated",
    "RS.AN-2": "The impact of the incident is understood",
    "RS.AN-3": "Forensics are performed",
    "RS.AN-4": "Incidents are categorized consistent with response plans",
    "RS.AN-5": "Processes are established to receive, analyze and respond to vulnerabilities disclosed to the organization from internal and external sources (e.g. internal testing, security bulletins, or security researchers)",
    # RS.CO (5)
    "RS.CO-1": "Personnel know their roles in order to support a response to an incident",
    "RS.CO-2": "Incidents are reported consistent with established criteria",
    "RS.CO-3": "Information is shared consistent with response plans",
    "RS.CO-4": "Coordination with stakeholders occurs consistent with response plans",
    "RS.CO-5": "Voluntary information sharing occurs with external stakeholders to achieve broader cybersecurity situational awareness",
    # RS.IM (2)
    "RS.IM-1": "Response plans incorporate lessons learned",
    "RS.IM-2": "Response strategies are updated",
    # RS.MI (3)
    "RS.MI-1": "Incidents are contained",
    "RS.MI-2": "Incidents are mitigated",
    "RS.MI-3": "Newly identified vulnerabilities are mitigated or documented as accepted risks",
    # RS.RP (1)
    "RS.RP-1": "Response plan is executed during or after an incident",
    # RC.CO (3)
    "RC.CO-1": "Public relations are managed",
    "RC.CO-2": "Reputation is repaired after an incident",
    "RC.CO-3": "Recovery activities are communicated to internal stakeholders and executives",
    # RC.IM (2)
    "RC.IM-1": "Recovery plans incorporate lessons learned",
    "RC.IM-2": "Recovery strategies are updated",
    # RC.RP (1)
    "RC.RP-1": "Recovery plan is executed during or after a cybersecurity incident",
}


def _v11_id_from_v20_id_strip(v20_id: str) -> str | None:
    """Convert a v2.0 ID like ``PR.AC-01`` to its v1.1 form ``PR.AC-1``.

    Returns ``None`` if the v2.0 ID is a category without a number, or
    if stripping the leading zero would yield an ID not in the
    official v1.1 catalogue.
    """
    m = re.match(r"^([A-Z]{2})\.([A-Z]{2})-(\d{2})$", v20_id)
    if not m:
        return None
    fn, cat, num = m.group(1), m.group(2), m.group(3)
    v11_id = f"{fn}.{cat}-{int(num)}"
    if v11_id in _CSF_1_1_TITLES:
        return v11_id
    return None


def _classify_mapping(dests: set[str], v11_id: str) -> str:
    """Classify a mapping into one of the canonical mapping_type values.

    See contract §4.1 for the enum.
    """
    if not dests:
        return "UNMAPPED"
    only_cat = all("-" not in d for d in dests)
    if only_cat:
        return "CATEGORY_LEVEL"
    dests_list = sorted(dests)
    if len(dests) == 1 and dests_list[0].endswith(v11_id.split("-")[1].zfill(2)):
        # Single destination whose number matches the v1.1 number (zfilled)
        return "IDENTITY_RENAME"
    if len(dests) == 1:
        return "SINGLE_INCORPORATED"
    return "MULTI_INCORPORATED"


def _detect_inconsistency(
    v11_id: str,
    primary_dests: set[str],
    active_dests: set[str],
) -> tuple[str, str | None]:
    """If a v1.1 ID has only withdrawn-destination mappings (no active
    subcategory citing it back), flag as WITHDRAWN_DESTINATION_INCONSISTENT.

    Two cases trigger the flag:
    1. ``active_dests`` is empty — no active v2.0 subcategory cites the
       v1.1 ID (all mapping comes from withdrawn-row tags or category
       headers).
    2. ``active_dests`` and ``primary_dests`` are non-empty but disjoint
       — the active v2.0 destinations cite different v1.1 IDs than the
       one we are mapping.
    """
    if not primary_dests:
        return "PRIMARY", None
    if not active_dests:
        return "WITHDRAWN_DESTINATION_INCONSISTENT", (
            f"v1.1 ID {v11_id} has no active v2.0 destination citing it "
            f"back — mapping comes only from withdrawn tags / category "
            f"headers (primary destinations: {sorted(primary_dests)}). "
            f"Recommend UNMAPPED_CSF or manual review."
        )
    if active_dests.isdisjoint(primary_dests):
        return "WITHDRAWN_DESTINATION_INCONSISTENT", (
            f"v1.1 ID {v11_id} maps to {sorted(primary_dests)} via "
            f"withdrawn tags, but the active v2.0 destination(s) cite "
            f"{sorted(active_dests)} instead — no bidirectional reference. "
            f"Recommend UNMAPPED_CSF or manual review."
        )
    return "PRIMARY", None


def _extract_v11_refs_from_cell(refs_raw: str | None) -> list[str]:
    """Pull all v1.1 IDs (e.g. ``PR.AC-1``) out of a free-text informative-references cell.

    Used for category-header rows where the ``CSF v1.1: X.Y-N`` token can
    appear on the same line as other text. Active subcategory rows use a
    per-line structure already handled by ``csf_xlsx._parse_references``;
    this helper is the category-level fallback.
    """
    if not refs_raw:
        return []
    return re.findall(r"[A-Z]{2}\.[A-Z]{2}-\d{1,2}", refs_raw)


def build_v11_to_v20_mapping(
    xlsx_path: Path,
    category_v11_refs: dict[str, list[tuple[int, str, list[str]]]] | None = None,
) -> dict[str, Any]:
    """Parse csf2.xlsx and return the full v1.1→v2.0 mapping JSON.

    Top-level keys: schema_version, source, csf_1_1_total, csf_2_0_active_total,
    unmapped_v1_1_ids, category_level_only, mappings.

    ``category_v11_refs`` is an optional pre-scanned dict keyed by v2.0
    category id (e.g. ``DE.AE``), with values ``(xlsx_row, category_text,
    [v11_ids...])``. The caller (the pipeline) gets this by walking the
    merged-cell Function/Category columns of the xlsx. When present, v1.1
    IDs cited only at the category level get a CATEGORY_LEVEL mapping
    (their destination is the category id, not a subcategory).
    """
    parsed = parse_csf2(xlsx_path)
    subcats = parsed["subcategories"]
    active_total = parsed["counts"]["subcategories"] - parsed["counts"]["withdrawn"]

    # Accumulate destinations and provenance per v1.1 ID.
    primary_dests: dict[str, set[str]] = defaultdict(set)
    active_dests: dict[str, set[str]] = defaultdict(set)
    provenance: dict[str, list[dict[str, Any]]] = defaultdict(list)
    # Track which v1.1 IDs are also cited at category level (so we can
    # distinguish "category_only" from "active_also")
    cat_level_cited: set[str] = set()

    for sc in subcats:
        xlsx_row = sc["source_locus"]["xlsx_row"]
        v20_id = sc["id"]
        is_withdrawn = sc["withdrawn"]
        wd_note = sc["withdrawal_note"]
        # Citations in informative references
        cited_v11: list[str] = []
        for ref in sc["informative_references"]:
            if ref["family"] != "CSF v1.1":
                continue
            cited_v11.append(ref["ref"])

        if is_withdrawn:
            # 1. Withdrawn row's own id-strip mapping
            v11_form = _v11_id_from_v20_id_strip(v20_id)
            if v11_form and wd_note:
                # Parse the destinations from the tag
                dests = re.split(r",\s*", wd_note)
                # Strip prefixes like "Incorporated into", "Moved to"
                clean_dests: list[str] = []
                for d in dests:
                    d = re.sub(
                        r"^(Incorporated\s+into\s+and\s+Moved\s+to|"
                        r"Incorporated\s+into|Moved\s+to)\s*",
                        "",
                        d,
                    ).strip()
                    if d:
                        clean_dests.append(d)
                for d in clean_dests:
                    primary_dests[v11_form].add(d)
                provenance[v11_form].append(
                    {
                        "row": xlsx_row,
                        "kind": "withdrawn_id_strip",
                        "csf2_id": v20_id,
                        "tag": wd_note,
                        "destinations": clean_dests,
                    }
                )
            # 2. Withdrawn row may also cite v1.1 IDs in its refs
            # (rare but happens — e.g. row 226 RC.CO-01 cites RC.CO-1)
            for c11 in cited_v11:
                # Use the tag destinations for the cited v1.1 ID too
                if wd_note:
                    dests = re.split(r",\s*", wd_note)
                    clean_dests = []
                    for d in dests:
                        d = re.sub(
                            r"^(Incorporated\s+into\s+and\s+Moved\s+to|"
                            r"Incorporated\s+into|Moved\s+to)\s*",
                            "",
                            d,
                        ).strip()
                        if d:
                            clean_dests.append(d)
                    for d in clean_dests:
                        primary_dests[c11].add(d)
                    provenance[c11].append(
                        {
                            "row": xlsx_row,
                            "kind": "withdrawn",
                            "csf2_id": v20_id,
                            "tag": wd_note,
                            "v11_ids_cited": cited_v11,
                        }
                    )
        else:
            # Active subcategory: v1.1 IDs in its informative references
            # map to this v2.0 subcategory.
            for c11 in cited_v11:
                primary_dests[c11].add(v20_id)
                active_dests[c11].add(v20_id)
                provenance[c11].append(
                    {
                        "row": xlsx_row,
                        "kind": "active_informative_ref",
                        "csf2_id": v20_id,
                    }
                )

    # Category-level v1.1 citations (4th signal): v1.1 IDs that appear
    # only in a v2.0 category header (not at subcategory level) get
    # mapped to the category id with CATEGORY_LEVEL type. If a v1.1 ID
    # is cited at BOTH the category header and a subcategory level, the
    # subcategory mapping wins (more specific).
    if category_v11_refs:
        for cat_id, entries in category_v11_refs.items():
            for row, _cat_text, v11_ids in entries:
                for c11 in v11_ids:
                    if c11 in _CSF_1_1_TITLES and c11 not in primary_dests:
                        primary_dests[c11].add(cat_id)
                        provenance[c11].append(
                            {
                                "row": row,
                                "kind": "category_header",
                                "csf2_id": cat_id,
                            }
                        )
                        cat_level_cited.add(c11)

    # Build per-v1.1-ID mapping entries
    mappings: list[dict[str, Any]] = []
    unmapped: list[str] = []
    cat_level_only: list[str] = []
    for v11_id in sorted(_CSF_1_1_TITLES.keys()):
        dests = sorted(primary_dests.get(v11_id, set()))
        mapping_type = _classify_mapping(set(dests), v11_id)
        active_only = set(active_dests.get(v11_id, set()))

        # Detect inconsistency (withdrawn tag cites a dest, but the active
        # dest doesn't cite this v1.1 ID back)
        if mapping_type not in ("UNMAPPED", "CATEGORY_LEVEL"):
            inconsistency, rationale = _detect_inconsistency(
                v11_id, set(dests), active_only
            )
            if inconsistency == "WITHDRAWN_DESTINATION_INCONSISTENT":
                mapping_type = "WITHDRAWN_DESTINATION_INCONSISTENT"
            else:
                rationale = None
        else:
            rationale = None

        # Special rationale notes for the two known-fuzzy v1.1 IDs
        if v11_id == "DE.DP-2":
            rationale = (
                "DE.DP category eliminated in v2.0; DE.AE category header "
                "in xlsx (row 169) cites 'CSF v1.1: DE.DP-2' as the only "
                "v1.1 ID absorbed at the category level. No specific v2.0 "
                "subcategory captures 'detection process accountability' — "
                "recommend UNMAPPED_CSF in chain for the 'process understood "
                "and followed' dimension."
            )
        if v11_id == "RC.CO-2":
            rationale = (
                "Withdrawn row RC.CO-02 (xlsx row 227) tag says 'Incorporated "
                "into RC.CO-04', but the active RC.CO-04 (xlsx row 229) cites "
                "v1.1: RC.CO-1 and RS.CO-2, NOT RC.CO-2. NIST's mapping for "
                "'reputation repair' is effectively dropped from CSF 2.0 — "
                "recommend UNMAPPED_CSF in chain for any SR touching this "
                "v1.1 control."
            )

        entry: dict[str, Any] = {
            "v11_id": v11_id,
            "v11_title": _CSF_1_1_TITLES[v11_id],
            "v20_destinations": dests,
            "mapping_type": mapping_type,
            "provenance": sorted(provenance.get(v11_id, []), key=lambda p: p["row"]),
        }
        if rationale:
            entry["rationale"] = rationale

        mappings.append(entry)
        if mapping_type == "UNMAPPED":
            unmapped.append(v11_id)
        elif mapping_type == "CATEGORY_LEVEL":
            cat_level_only.append(v11_id)

    return {
        "schema_version": "1.0",
        "source": "csf2.xlsx (NIST CSF 2.0 Reference Tool, 2024-02-26)",
        "csf_1_1_total": len(_CSF_1_1_TITLES),
        "csf_2_0_active_total": active_total,
        "unmapped_v1_1_ids": unmapped,
        "category_level_only": cat_level_only,
        "inconsistent_v1_1_ids": sorted(
            m["v11_id"] for m in mappings if m["mapping_type"] == "WITHDRAWN_DESTINATION_INCONSISTENT"
        ),
        "mappings": mappings,
    }
