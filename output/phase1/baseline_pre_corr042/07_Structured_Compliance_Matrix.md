---
document_id: AEGIS-P1-07
title: Structured Compliance Matrix
phase: 1
version: 1.0
created: "2026-07-14T11:17:25Z"
updated: "2026-07-14T11:17:25Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, 05_Regulatory_Applicability.md, 06_Clause_Mapping_Matrix.xlsx, 07b_Proportionality_Profile.md]
outputs: [08_Obligation_Derivation.md, 11_Rules_Catalog.md, 14_Architectural_Nodes.md, 15_Allocation.md]
applicable_regs: [CRA, GDPR]
traceability: AEGIS Class Model → ComplianceContext, DomainCoverageEntry
related_documents: [00_Taxonomy_Reference.md, ../../../00_METHODOLOGY/PHASE1_STRATEGY.md]
generated_at: "2026-07-14T11:17:25Z"
---
# AEGIS-P1-07 Structured Compliance Matrix

## 1. PURPOSE

Aggregate per-sub-domain coverage against each regulation, highlight complementarity and overlaps, surface sole-authority gaps, and ship a six-criterion gate-checklist confirming that Phase 1 is complete enough to proceed to Phase 2.

The matrix is the primary hand-off from Phase 1 to Phase 2 (obligation derivation, rules catalogue, allocation) and is indexed in the dependency graph as ``GATE-C``.

## 2. INPUTS

| Input | Source Document | Role in §3..§8 |
| --- | --- | --- |
| Company context | AEGIS-P1-04 | scale + applicability filter |
| Applicability assessments | AEGIS-P1-05 | applicable-yes column criterion |
| Clause mappings | AEGIS-P1-06 | per-cell normative-intensity aggregation |
| Sub-domain catalogue | 00_Taxonomy_Reference.md | row identity for the 38-row matrix |
| Architectural inventory | AEGIS-P1-04a | system references in §5 complementarity |
| Proportionality profile | AEGIS-P1-07b | tier annotation per row |

## 3. COVERAGE MATRIX

The matrix below contains one row per sub-domain (38 nominal). Each cell carries a regulation abbreviation when that regulation has at least one clause mapping onto the sub-domain, or "—" when not applicable. NI (normative intensity) is the mean of the ``normative_strength`` field across all clauses that map onto the cell, rounded to one decimal.

| Sub-domain | Name | GDPR | CRA | NIS2 | DORA | AI ACT | Total | Status | NI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D-01.1 | Data at Rest Encryption | GDPR | CRA | — | — | — | 2 | SUBSTANTIVE | 3.0 |
| D-01.2 | Data in Transit Encryption | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-01.3 | Cryptographic Key Management | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-01.4 | Data Integrity Mechanisms | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-02.1 | Vulnerability Identification | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-02.2 | Patch Management & Updates | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-02.3 | Coordinated Vuln. Disclosure | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-03.1 | Identity Lifecycle Management | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-03.2 | Multi-Factor Authentication | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-03.3 | Authorization & Least Privilege | GDPR | — | — | — | — | 1 | PARTIAL | 3.0 |
| D-03.4 | Secure System Defaults | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-04.1 | Incident Detection & Triage | — | CRA | — | — | — | 1 | PARTIAL | 2.0 |
| D-04.2 | Containment & Mitigation | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-04.3 | Regulatory Notification | GDPR | CRA | — | — | — | 2 | SUBSTANTIVE | 3.0 |
| D-04.4 | Data Restoration & Recovery | GDPR | CRA | — | — | — | 2 | SUBSTANTIVE | 3.0 |
| D-05.1 | Data Minimization | GDPR | — | — | — | — | 1 | PARTIAL | 2.8 |
| D-05.2 | Retention & Archiving | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-05.3 | Right to Erasure | GDPR | CRA | — | — | — | 2 | SUBSTANTIVE | 3.0 |
| D-05.4 | Data Portability | GDPR | — | — | — | — | 1 | PARTIAL | 3.0 |
| D-06.1 | Vendor Risk Assessment | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-06.2 | Software Bill of Materials (SBOM) | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-06.3 | Contractual Security Obligations | GDPR | CRA | — | — | — | 2 | SUBSTANTIVE | 3.0 |
| D-07.1 | Secure-by-Design Principles | GDPR | CRA | — | — | — | 2 | SUBSTANTIVE | 3.0 |
| D-08.1 | General Security Awareness | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-08.2 | Role-Specific Competence | GDPR | — | — | — | — | 1 | PARTIAL | 2.0 |
| D-09.1 | Information Security Policies | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-09.2 | Impact & Risk Assessments | GDPR | — | — | — | — | 1 | PARTIAL | 3.0 |
| D-09.4 | Records of Processing | GDPR | — | — | — | — | 1 | PARTIAL | 2.8 |
| D-10.1 | Continuous Security Monitoring | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-10.2 | Audit Logging & Traceability | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-10.3 | Compliance Testing | — | CRA | — | — | — | 1 | PARTIAL | 3.0 |
| D-02.4 | Threat-Led Penetration Testing | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-06.4 | Third-Party Boundary Management | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-07.2 | Secure Coding Practices | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-07.3 | CI/CD Pipeline Security | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-07.4 | Change Management | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-08.3 | Management Board Training | — | — | — | — | — | 0 | NOT_ADDRESSED | — |
| D-09.3 | Asset Inventories | — | — | — | — | — | 0 | NOT_ADDRESSED | — |

## 4. SUMMARY

| Coverage Level | Count |
| --- | --- |
| SUBSTANTIVE | 6 |
| PARTIAL | 20 |
| NOT_ADDRESSED | 7 |
| TOTAL | 38 |

- Total sub-domains in catalogue: **38**
- Substantive coverage (≥ 2 regs): **6** (15.8%)
- Partial coverage (1 reg): **20** (52.6%)
- Not addressed (0 regs): **7** (18.4%)
- Mean normative intensity: **2.93**
- Sole-authority gaps: **4**
- Total clause mappings: **54**

## 5. COMPLEMENTARITY

Cross-regulation overlaps are presented below. Section 5.1 expands each overlap into a table of shared sub-domains with the specific clauses that drive the overlap. Section 5.2 captures compound-event scenarios in which a single factual incident satisfies the trigger conditions of two or more regulations in the same sub-domain.

| Reg Pair | Shared Sub-domains | Count | Jaccard | Note |
| --- | --- | --- | --- | --- |
| GDPR+CRA | D-01.1 (Data at Rest Encryption); D-01.2 (Data in Transit Encryption); D-04.2 (Containment & Mitigation); D-04.3 (Regulatory Notification); D-05.3 (Right to Erasure); D-07.1 (Secure-by-Design Principles); D-10.3 (Compliance Testing) | 7 | 0.367 | GDPR and CRA share significant coverage in data protection, incident response, and secure development domains |
| GDPR+NIS2 | - | 0 | 0.0 | NIS2 not applicable to TinyTask |
| CRA+NIS2 | - | 0 |  | NIS2 not applicable to TinyTask |

### 5.1 Opportunities — Detail

| Opportunity ID | Sub-domain | Regulations | Description | Benefit |
| --- | --- | --- | --- | --- |
| CO-001 | D-01.1 Data at Rest Encryption | GDPR + CRA | GDPR and CRA share significant coverage in data protection, incident response, and secure development domains | single implementation satisfies both regulations |
| CO-002 | D-01.2 Data in Transit Encryption | GDPR + CRA | GDPR and CRA share significant coverage in data protection, incident response, and secure development domains | single implementation satisfies both regulations |
| CO-003 | D-04.2 Containment & Mitigation | GDPR + CRA | GDPR and CRA share significant coverage in data protection, incident response, and secure development domains | single implementation satisfies both regulations |
| CO-004 | D-04.3 Regulatory Notification | GDPR + CRA | GDPR and CRA share significant coverage in data protection, incident response, and secure development domains | single implementation satisfies both regulations |
| CO-005 | D-05.3 Right to Erasure | GDPR + CRA | GDPR and CRA share significant coverage in data protection, incident response, and secure development domains | single implementation satisfies both regulations |
| CO-006 | D-07.1 Secure-by-Design Principles | GDPR + CRA | GDPR and CRA share significant coverage in data protection, incident response, and secure development domains | single implementation satisfies both regulations |
| CO-007 | D-10.3 Compliance Testing | GDPR + CRA | GDPR and CRA share significant coverage in data protection, incident response, and secure development domains | single implementation satisfies both regulations |

### 5.2 Compound-Event Scenarios

| Event ID | Compound Description | Regulations Triggered | Sub-domain | Resolution Approach |
| --- | --- | --- | --- | --- |
| EVT-001 | Encryption baseline addressed by both frameworks | GDPR + CRA | D-01.1 | Single AES-256 managed-service primitive |
| EVT-002 | TLS baseline addressed by both frameworks | GDPR + CRA | D-01.2 | Managed certificate lifecycle satisfies both |
| EVT-003 | Containment action that also constitutes a data-minimisation decision | GDPR + CRA | D-04.2 | Unified containment playbook that documents both regulation triggers |
| EVT-004 | Attacker exploit + personal data breach (single incident touches both notification clocks) | GDPR + CRA | D-04.3 | max-SLA routing — pick the shorter clock (24 h) as the internal standard |
| EVT-005 | Data-subject erasure request + product-level data reset | GDPR + CRA | D-05.3 | Single endpoint satisfies both erasure rights; share the same audit log |
| EVT-006 | Design-time decision that satisfies both data-protection-by-design and security-by-default | GDPR + CRA | D-07.1 | Document the design choice once in both regulation contexts |
| EVT-007 | Compliance test that satisfies both conformity assessment and audit obligation | GDPR + CRA | D-10.3 | Single test plan evidence reused for both |

Compound events do not create permanent conflicts; they are operational moments where two trigger clocks fire together. Each row above carries the recommended routing that absorbs both clocks into a single workflow (max-SLA, unified doc, competency matrix, etc.).

## 6. STRATEGIC IMPLICATIONS

| Implication ID | Sub-domain / Clause | Source Regulation(s) | Description | Architecture Impact | Priority |
| --- | --- | --- | --- | --- | --- |
| SI-001 | D-01 | CRA + GDPR | Unified encryption baseline satisfies both regulations | Single AES-256 / TLS 1.3 primitive across storage and transport | HIGH |
| SI-002 | D-04.3 | CRA + GDPR | Joint notification workflow absorbs both clocks | Single incident process, max-SLA routing, single audit log | HIGH |
| SI-003 | D-09.2 | CRA + GDPR | Unified impact-and-risk assessment template | Single template, dual-output (DPIA + CRA risk assessment) | MEDIUM |
| SI-004 | D-06.2 | CRA | SBOM publication requirement independent of GDPR | Insert CycloneDX SBOM step in CI/CD pipeline | HIGH |
| SI-005 | D-02.3 | CRA | Coordinated-vulnerability-disclosure obligation | Publish security.txt and CVD acknowledgement SLA | MEDIUM |

### 6.1 Narrative

TinyTask Lda. operates at Micro-enterprise scale with 2 applicable regulations. The structured matrix confirms that the in-scope sub-domains are dominated by shared regulation pairs, which permits Phase-2 obligations to reuse a single control implementation across multiple clause references.

Of the 5 strategic implications surfaced, 3 carry HIGH priority and are scheduled for the first Phase-2 sprint; the remainder are sequenced after the compliance matrix reaches the next-tier gate review.

Complementarity opportunities collapse several sub-domains into single controls, materially reducing engineering effort. The compound-event scenarios in §5.2 require routing decisions before Phase 2 begins, otherwise they will surface repeatedly as audit findings during the first quarterly review.

Time-to-compliance depends on the closure of HIGH-priority implications first; the gap between applicability approval and gate-C approval is the dominant driver of the Phase-2 schedule.

## 7. GAPS

Gaps are surfaced from three sources and ranked by severity: (a) structural tensions recorded in ``state.ontology.tensions``; (b) sole-authority sub-domains in ``state.ontology.subdomains.not_covered``; (c) per-cell rating outcomes flagged during the v2 evaluation pass.

| Gap ID | Type | Sub-domain / Clause | Severity / Risk | Action / Mitigation |
| --- | --- | --- | --- | --- |
| GAP-T001 | TENSION_DERIVED | GDPR-C25 ↔ CRA-C20 | high | Use the most stringent timeline (24h) as the internal standard for all breach notifications |
| GAP-T002 | TENSION_DERIVED | GDPR-C21 ↔ CRA-C07 | medium | Single vendor risk assessment template that addresses both GDPR Art. 28 and CRA Art. 7 requirements |
| GAP-T003 | TENSION_DERIVED | GDPR-C13 ↔ CRA-C13 | medium | Maintain unified records system that satisfies both record-keeping requirements |
| GAP-T004 | TENSION_DERIVED | GDPR-C28 ↔ CRA-C21 | low | Define competency requirements that address both data protection and product security |
| GAP-S005 | SOLE_AUTHORITY | D-07.2 Secure Coding Practices | high | Apply CRA secure development principles as best practice |
| GAP-S006 | SOLE_AUTHORITY | D-07.3 CI/CD Pipeline Security | high | Implement basic CI/CD security controls (GitHub Actions best practices) |
| GAP-S007 | SOLE_AUTHORITY | D-07.4 Change Management | medium | Document change management process |
| GAP-S008 | SOLE_AUTHORITY | D-09.3 Asset Inventories | medium | Maintain asset inventory as part of general security hygiene |
| GAP-N009 | EXCLUDED_SUBDOMAIN | D-02.4 Threat-Led Penetration Testing | medium | DORA not applicable (not financial entity) |
| GAP-N010 | EXCLUDED_SUBDOMAIN | D-06.4 Third-Party Boundary Management | medium | DORA not applicable (not financial entity) |
| GAP-N011 | EXCLUDED_SUBDOMAIN | D-07.2 Secure Coding Practices | high | DORA not applicable (not financial entity) |
| GAP-N012 | EXCLUDED_SUBDOMAIN | D-07.3 CI/CD Pipeline Security | high | NIS 2 not applicable (below 50 employees) |
| GAP-N013 | EXCLUDED_SUBDOMAIN | D-07.4 Change Management | medium | DORA not applicable (not financial entity) |
| GAP-N014 | EXCLUDED_SUBDOMAIN | D-08.3 Management Board Training | low | NIS2 not applicable (below 50 employees) |
| GAP-N015 | EXCLUDED_SUBDOMAIN | D-09.3 Asset Inventories | medium | DORA not applicable (not financial entity) |

## 8. GATE CHECKLIST

Six criteria confirm that Phase 1 is shippable. Each row carries a PASS / FAIL / PARTIAL status, a one-line evidence anchor, and the source field or document where the evidence originates.

| # | Gate criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Company context loaded (04) | PASS | company_name = TinyTask Lda. |
| 2 | Sub-domain catalogue present | PASS | 31 active sub-domains |
| 3 | Clause mappings rendered | PASS | 54 clauses in 06 |
| 4 | Coverage matrix computed | PASS | 38 sub-domains in ontology |
| 5 | Proportionality computed (07b) | PASS | see AEGIS-P1-07b |
| 6 | Applicability assessments recorded (05) | PASS | 5 assessments |

Gate reviewers must sign the §9 sign-off block before any Phase-2 consumer ingests this document.
