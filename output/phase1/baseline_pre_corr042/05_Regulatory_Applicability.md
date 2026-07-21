---
document_id: AEGIS-P1-05
title: Regulatory Applicability Assessment
phase: 1
version: 1.0
created: "2026-07-14T11:17:25Z"
updated: "2026-07-14T11:17:25Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, ../00_COMMON/01_Company_Context.md, 00_Taxonomy_Reference.md]
outputs: [06_Clause_Mapping_Matrix.xlsx, 07_Structured_Compliance_Matrix.md, 08_Obligation_Derivation.md]
applicable_regs: [CRA, GDPR]
related_documents: [../../../00_METHODOLOGY/PHASE1_STRATEGY.md, "../../../00_METHODOLOGY/PHASE1_STRATEGY.md#filter-1-regulation-applicability-binary-predicates", 00_Taxonomy_Reference.md]
traceability: AEGIS Class Model → ComplianceContext, RegulatoryClause, DomainCoverageEntry
generated_at: "2026-07-14T11:17:25Z"
---
# AEGIS-P1-05 Regulatory Applicability

## 1. PURPOSE

Determine, per regulation, whether the company falls in scope of the EU regulations tracked by AEGIS — GDPR, CRA, NIS 2, DORA, and AI Act — and record the criteria, evidence, and reasoning that justify each determination. The output of this document is the canonical input for clause mapping (06) and for the coverage matrix (07).

Three observable deliverables are produced downstream of this document:

- a populated applicability table that names, for each regulation, the threshold that triggers applicability, the company's value against that threshold, and the result;
- a Native-vs-Inherited split that separates obligations the company implements directly from obligations satisfied through suppliers and partners;
- a forward handover record (§8) that captures the artefacts passed to Phase 2.

## 2. APPLICABLE SUMMARY

- **Applicable regulations (2):** GDPR, CRA
- **Non-applicable regulations (3):** NIS2, DORA, AI ACT
- **Total applicable clauses across the case:** 54

## 3. PER-REGULATION APPLICABILITY

Each sub-section below follows a fixed shape: thresholds and criteria on the left, the company value on the right, and a result column. The evidence block lists the ontology fields that ground the determination; the reasoning block carries the natural-language rationale.

### 3.1 GDPR (General Data Protection Regulation)

- **Applicable:** YES
- **EU reference:** Regulation (EU) 2016/679
- **Obligated party:** controller, processor
- **Clause count (declared):** 28
- **Confidence:** high
- **Reason category:** TinyTask processes personal data of EU data subjects as a B2B SaaS provider. GDPR applies fully as data CONTROLLER for account/billing/employee data and as PROCESSOR for B2B client content (Art. 28). Per-clause allocation is recorded in the clause_mappings below; see also 02_Regulatory_Mapping_Master.md §GDPR PER-CLAUSE OBLIGATED PARTY ALLOCATION. PROCESSOR role is the corrective change for audit finding 2026-07-03 (hardcoded subset bug — root cause: data validation enum restricted to CONTROLLER only).

#### CRITERIA

| Criterion | Value | Threshold | Result |
| --- | --- | --- | --- |
| processes_personal_data | true | any | YES |
| eu_data_subjects | true | any | YES |
| controller_role | true | Art. 4(7) | met |
| processor_role | true | Art. 4(8) | met |

#### EVIDENCE

- Q22: processes personal data (email, name, password)
- Q1: EU jurisdiction
- Q27: IP addresses in server logs
- Q57: B2B SaaS — clients upload personal data of their end-users to the platform (Art. 28(3) PROCESSOR role)

#### REASONING

TinyTask processes personal data of EU data subjects as a B2B SaaS provider. GDPR applies fully as data CONTROLLER for account/billing/employee data and as PROCESSOR for B2B client content (Art. 28). Per-clause allocation is recorded in the clause_mappings below; see also 02_Regulatory_Mapping_Master.md §GDPR PER-CLAUSE OBLIGATED PARTY ALLOCATION. PROCESSOR role is the corrective change for audit finding 2026-07-03 (hardcoded subset bug — root cause: data validation enum restricted to CONTROLLER only).

---

### 3.2 CRA (Cyber Resilience Act)

- **Applicable:** YES
- **EU reference:** Regulation (EU) 2024/2847
- **Obligated party:** manufacturer
- **Clause count (declared):** 26
- **Confidence:** high
- **Reason category:** TinyTask manufactures and places digital products (SaaS) on the EU market. CRA applies as manufacturer.

#### CRITERIA

| Criterion | Value | Threshold | Result |
| --- | --- | --- | --- |
| places_digital_products_eu | true | Art. 2 | YES |
| manufacturer_status | true | Art. 3(13) | met |

#### EVIDENCE

- Q1: EU customers
- Q7: SaaS product placed on EU market
- Q60: digital product classification

#### REASONING

TinyTask manufactures and places digital products (SaaS) on the EU market. CRA applies as manufacturer.

---

### 3.3 NIS2 (Network and Information Systems Directive 2)

- **Applicable:** NO
- **EU reference:** Directive (EU) 2022/2555
- **Obligated party:** -
- **Clause count (declared):** 0
- **Confidence:** high
- **Reason category:** below_threshold

#### CRITERIA

| Criterion | Value | Threshold | Result |
| --- | --- | --- | --- |
| nis2_sector | tech (productivity) | Annex I/II | below_threshold |
| size_employees | ≤ 50 (or actual) | ≥ 50 (medium) | below |

#### EVIDENCE

- Q2: 8 employees (below 50 employee threshold)
- Q4: Technology sector

#### REASONING

Micro-enterprise below NIS 2 threshold (fewer than 50 employees).

---

### 3.4 DORA (Digital Operational Resilience Act)

- **Applicable:** NO
- **EU reference:** Regulation (EU) 2022/2554
- **Obligated party:** -
- **Clause count (declared):** 0
- **Confidence:** high
- **Reason category:** not_financial_entity

#### CRITERIA

| Criterion | Value | Threshold | Result |
| --- | --- | --- | --- |
| dora_financial_entity | false | Art. 2 | NO |
| ict_third_party_provider | false | Art. 28(8) | NO |

#### EVIDENCE

- Q6: No regulated financial operations
- Q18: Payment data handled by Stripe

#### REASONING

Not a financial entity as defined by DORA. Payments processed by Stripe.

---

### 3.5 AI ACT (Artificial Intelligence Act)

- **Applicable:** NO
- **EU reference:** Regulation (EU) 2024/1689
- **Obligated party:** -
- **Clause count (declared):** 0
- **Confidence:** high
- **Reason category:** no_ai_systems

#### CRITERIA

| Criterion | Value | Threshold | Result |
| --- | --- | --- | --- |
| aiact_high_risk_system | false | Annex III | NO |
| ai_system_provider | false | Art. 3(1) | NO |

#### EVIDENCE

- Q8: No AI/ML systems

#### REASONING

No high-risk AI systems deployed. Deterministic task management app only.

---

## 4. NATIVE VS INHERITED COMPLIANCE

The applicability table is augmented with a NATIVE / INHERITED annotation per regulation–domain pair. NATIVE means the company implements the control itself; INHERITED means the control is satisfied through a contractual relationship with a cloud or service provider that carries its own attestation (for example, an ISO 27001 or SOC 2 Type II report).

| Regulation | Domain / Sub-domain | Layer | Justification |
| --- | --- | --- | --- |
| GDPR | D-01 — encryption in transit / at rest | INHERITED | provider-controlled primitives (AWS or equivalent EU cloud provider, Auth0, Datadog or equivalent, Stripe) |
| GDPR | D-04 — incident detection | NATIVE | company-defined playbook |
| GDPR | D-05 — data lifecycle | NATIVE | company-owned schema constraints and APIs |
| GDPR | D-06 — vendor risk | NATIVE | DPA validation owned by Compliance Lead |
| GDPR | D-08 — awareness | NATIVE | company-run training cadence |
| GDPR | D-09 — governance | NATIVE | policy ownership internal to Compliance Lead |
| CRA | D-01 — default configuration | NATIVE | secure defaults implemented in code |
| CRA | D-02 — vulnerability handling | NATIVE | SBOM + scanner run by engineering |
| CRA | D-07 — secure development | NATIVE | SDLC owned by Lead Developer |

### 4.1 Provider Attestations

| Provider | Service | Region | Attestation |
| --- | --- | --- | --- |
| AWS or equivalent EU cloud provider | PostgreSQL managed database | eu-west-1 or equivalent EU region | see DPA |
| AWS or equivalent EU cloud provider | S3-compatible object storage | eu-west-1 or equivalent EU region | see DPA |
| AWS or equivalent EU cloud provider | Cloud KMS | EU region | see DPA |
| Auth0 | Authentication and identity | EU tenant where available | see DPA |
| Stripe | Payment processing | Stripe controlled processing locations | see DPA |
| Datadog or equivalent | Logs and analytics | EU site where available | see DPA |

Compliance evidence for INHERITED rows must be filed in the working directory (typically under ``02_CASES/.../04_EVIDENCE/``) before Phase 2 begins.

## 5. SUB-DOMAIN COVERAGE PRELIMINARY

Coverage status per sub-domain is computed from the layer-0 ontology and the applicable regulation set. A sub-domain is **SUBSTANTIVE** when ≥ 2 applicable regulations cover it, **PARTIAL** when exactly one applies, and **NOT_ADDRESSED** when no applicable regulation intersects the company context.

| Sub-domain | Name | Source Regs | Total | Status |
| --- | --- | --- | --- | --- |
| D-01.1 | Data at Rest Encryption | GDPR, CRA | 2 | SUBSTANTIVE |
| D-01.2 | Data in Transit Encryption | GDPR, CRA | 2 | SUBSTANTIVE |
| D-01.3 | Cryptographic Key Management | CRA | 1 | PARTIAL |
| D-01.4 | Data Integrity Mechanisms | GDPR, CRA | 2 | SUBSTANTIVE |
| D-02.1 | Vulnerability Identification | CRA | 1 | PARTIAL |
| D-02.2 | Patch Management & Updates | CRA | 1 | PARTIAL |
| D-02.3 | Coordinated Vuln. Disclosure | CRA | 1 | PARTIAL |
| D-03.1 | Identity Lifecycle Management | CRA | 1 | PARTIAL |
| D-03.2 | Multi-Factor Authentication | CRA | 1 | PARTIAL |
| D-03.3 | Authorization & Least Privilege | GDPR | 1 | PARTIAL |
| D-03.4 | Secure System Defaults | CRA | 1 | PARTIAL |
| D-04.1 | Incident Detection & Triage | CRA | 1 | PARTIAL |
| D-04.2 | Containment & Mitigation | GDPR, CRA | 2 | SUBSTANTIVE |
| D-04.3 | Regulatory Notification | GDPR, CRA | 2 | SUBSTANTIVE |
| D-04.4 | Data Restoration & Recovery | GDPR | 1 | PARTIAL |
| D-05.1 | Data Minimization | GDPR | 1 | PARTIAL |
| D-05.2 | Retention & Archiving | GDPR | 1 | PARTIAL |
| D-05.3 | Right to Erasure | GDPR | 1 | PARTIAL |
| D-05.4 | Data Portability | GDPR | 1 | PARTIAL |
| D-06.1 | Vendor Risk Assessment | GDPR | 1 | PARTIAL |
| D-06.2 | Software Bill of Materials (SBOM) | CRA | 1 | PARTIAL |
| D-06.3 | Contractual Security Obligations | GDPR | 1 | PARTIAL |
| D-07.1 | Secure-by-Design Principles | CRA | 1 | PARTIAL |
| D-08.1 | General Security Awareness | GDPR | 1 | PARTIAL |
| D-08.2 | Role-Specific Competence | GDPR | 1 | PARTIAL |
| D-09.1 | Information Security Policies | GDPR, CRA | 2 | SUBSTANTIVE |
| D-09.2 | Impact & Risk Assessments | GDPR | 1 | PARTIAL |
| D-09.4 | Records of Processing | GDPR | 1 | PARTIAL |
| D-10.1 | Continuous Security Monitoring | CRA | 1 | PARTIAL |
| D-10.2 | Audit Logging & Traceability | CRA | 1 | PARTIAL |
| D-10.3 | Compliance Testing | GDPR, CRA | 2 | SUBSTANTIVE |
| D-02.4 | Threat-Led Penetration Testing | DORA | 0 | NOT_ADDRESSED |
| D-06.4 | Third-Party Boundary Management | DORA | 0 | NOT_ADDRESSED |
| D-07.2 | Secure Coding Practices | DORA | 0 | NOT_ADDRESSED |
| D-07.3 | CI/CD Pipeline Security | NIS2 | 0 | NOT_ADDRESSED |
| D-07.4 | Change Management | DORA | 0 | NOT_ADDRESSED |
| D-08.3 | Management Board Training | NIS2 | 0 | NOT_ADDRESSED |
| D-09.3 | Asset Inventories | DORA | 0 | NOT_ADDRESSED |

### 5.1 Status Counts

| Status | Count | Percentage |
| --- | --- | --- |
| SUBSTANTIVE | 7 | 18.4% |
| PARTIAL | 24 | 63.2% |
| NOT_ADDRESSED | 7 | 18.4% |

## 6. STRATEGIC IMPLICATIONS

The applicability profile is condensed into a small set of implications that feed Phase 2 obligation derivation. Each implication names the trigger regulations, the affected architecture areas, and the priority with which Phase 2 must absorb the implication into obligation rows.

| Implication ID | Source Regulation(s) | Description | Architecture Impact | Priority |
| --- | --- | --- | --- | --- |
| SI-001 | CRA + GDPR | Dual-role analysis: GDPR controller + processor obligations co-exist; CRA manufacturer obligations attach independently | Phase 2 must allocate each clause to exactly one role and duplicate rows where the same clause binds both roles | HIGH |
| SI-002 | GDPR | Data-subject rights (erasure, portability, restriction) require customer-facing endpoints | Add API endpoints / documented manual workflow in 14_Architectural_Nodes | MEDIUM |
| SI-003 | GDPR | RoPA + security-of-processing documentation needed (Art. 30, Art. 32) | Generate templates in 03_PHASE3_DECOMPOSITION / templates | MEDIUM |
| SI-004 | CRA | SBOM, CVD page (security.txt), and patch cadence must be operationalised | Insert CI/CD gates and `.well-known/security.txt` publication step | HIGH |
| SI-005 | CRA | Coordinated vulnerability disclosure requires named contact + acknowledgement SLA | Document SLA in 11_Rules_Catalog.md D-02.3 row | MEDIUM |
| SI-006 | CRA + GDPR | Time-to-compliance for the case must be estimated against §6.1 narrative before kick-off of Phase 2 | Hand off to PM for scope-baseline ratification | MEDIUM |

### 6.1 Narrative

TinyTask Lda. is a Micro-enterprise business with 8 employees whose applicable regulation set reduces to 2 primary instruments after the threshold check.

Two consequences follow: (a) the obligation derivation must route clauses through both controller and processor lenses for GDPR when the company acts as a B2B SaaS provider, and (b) the engineering roadmap must absorb CRA-only obligations such as SBOM publication, secure defaults, and coordinated vulnerability disclosure.

The Phase-2 backlog is therefore sized around 6 strategic implications, of which 2 carry HIGH priority; the remaining MEDIUM-priority items are sequenced after Phase-2 obligation derivation has cleared the feasibility gate.

Time-to-compliance for the case should be measured from the moment the obligations matrix is signed off, not from the moment the applicability is approved; the gap is typically two to four weeks for a MICRO/SMALL entity.

## 7. REGULATORY GAPS IDENTIFIED

Gaps surfaced by the ontology tensions catalogue and by sub-domains whose sole authority is a regulation that does not apply to this company. The Type column distinguishes TENSION_DERIVED (tension between applicable regulations), SOLE_AUTHORITY (sub-domain in ``not_covered``), and DETERMINISTIC (annotated at the language-model layer).

| Gap ID | Type | Sub-domain / Clause | Severity | Description |
| --- | --- | --- | --- | --- |
| GAP-T001 | TENSION_DERIVED | GDPR-C25 ↔ CRA-C20 | high | Breach notification timing mismatch |
| GAP-T002 | TENSION_DERIVED | GDPR-C21 ↔ CRA-C07 | medium | Processor vs Manufacturer obligations |
| GAP-T003 | TENSION_DERIVED | GDPR-C13 ↔ CRA-C13 | medium | Records documentation overlap |
| GAP-T004 | TENSION_DERIVED | GDPR-C28 ↔ CRA-C21 | low | DPO vs Security team competence |
| GAP-N005 | SOLE_AUTHORITY | D-02.4 (Threat-Led Penetration Testing) | medium | DORA not applicable (not financial entity) |
| GAP-N006 | SOLE_AUTHORITY | D-06.4 (Third-Party Boundary Management) | medium | DORA not applicable (not financial entity) |
| GAP-N007 | SOLE_AUTHORITY | D-07.2 (Secure Coding Practices) | high | DORA not applicable (not financial entity) |
| GAP-N008 | SOLE_AUTHORITY | D-07.3 (CI/CD Pipeline Security) | high | NIS 2 not applicable (below 50 employees) |
| GAP-N009 | SOLE_AUTHORITY | D-07.4 (Change Management) | medium | DORA not applicable (not financial entity) |
| GAP-N010 | SOLE_AUTHORITY | D-08.3 (Management Board Training) | low | NIS2 not applicable (below 50 employees) |
| GAP-N011 | SOLE_AUTHORITY | D-09.3 (Asset Inventories) | medium | DORA not applicable (not financial entity) |

## 8. INPUT TO PHASE 2

The following artefacts leave this document and travel to Phase 2 (obligation derivation, rules catalogue, allocation). Any change to this list requires a corresponding edit in the Phase-2 ingest contract.

| Artefact | Source Section | Phase-2 Consumer |
| --- | --- | --- |
| Applicable regulation set (YES/NO flags) | §2 | Filter in 08_Obligation_Derivation.md |
| Per-regulation criteria + evidence + reasoning | §3 | Audit trail for compliance clauses |
| Native / Inherited annotations | §4 | Ownership annotation in 11_Rules_Catalog.md |
| Sub-domain coverage preliminary | §5 | Input for 07_Structured_Compliance_Matrix.md §3 |
| Strategic implications | §6 | Trigger for strategic tension detection in Phase 2 |
| Regulatory gaps | §7 | Priority input for rules catalog seed row |
| Handover envelope (this section) | §8 | Phase-2 ingest contract |

Sign-off: this document closes Phase 1 sub-task B (Regulatory Applicability). Phase 1 sub-task C (Structured Compliance Matrix) starts after this file is reviewed.
