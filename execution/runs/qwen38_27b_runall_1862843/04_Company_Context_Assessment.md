---
document_id: AEGIS-P1-04
title: Company Context Assessment
version: 2.2
status: DRAFT
generated_at: "2026-09-01T14:30:55Z"
phase: 1
author: Compliance Lead
case_study: TinyTask Lda.
inputs: [01_Company_Context.md]
outputs: [05_Regulatory_Applicability.md]
traceability: AEGIS Class Model -> CompanyContext, ComplianceContext classes
related_documents: [00_Taxonomy_Reference.md, 01_Company_Context.md, 04a_Architecture_DataInventory.md]
applicable_regs: [CRA, GDPR]
tier: LOW
---
# AEGIS-P1-04 Company Context Assessment

## 1. DOCUMENT PURPOSE

This document consolidates the company context assessment (Step A1 + A2 + A3 of the AEGIS Phase 1 methodology), including stakeholder analysis, business goals catalog, the layered intake form response summary, regulatory applicability flags, architectural implications, data flow summary, and the compliance capability assessment. It is the primary input for regulatory applicability (05) and the clause mapping matrix (06).

**Alignment with Class Model:**
- `CompanyContext` — instantiated from AEGIS Intake Form v2.0 (layered format)
- `ComplianceContext` — derived regulatory applicability flags
- `Stakeholder` — organizational roles and responsibilities
- `BusinessGoal` — strategic objectives

**Phase 1 Step:** A (Company Context Assessment)

**Gate Criteria:** Intake form complete; regulatory applicability determined

---

## 2. ASSESSMENT SUMMARY

| Field | Value |
| --- | --- |
| Assessment ID | AEGIS-04-case1-tinytask-202609 |
| Assessment Date | 2026-09-01 |
| Assessor | Compliance Lead |
| Company Name | TinyTask Lda. |
| Jurisdiction | Portugal (EU) |
| Sector | Technology/Software |
| Size Category | MICRO — 8 employees, <€2M revenue |
| Assessment Method | AEGIS Intake Form v2.0 (layered: Company Profile + Decision Tree + Conditional Blocks) |

---

## 3. STAKEHOLDER ANALYSIS (A1)

### 3.1 Stakeholder Register

| ID | Name | Role | Organisation | Contact | Responsibilities |
| --- | --- | --- | --- | --- | --- |
| SH-01 | - | Chief Executive Officer (CEO) | - | - | ['executive_sponsor', 'accountability'] |
| SH-02 | - | Chief Technology Officer (CTO) | - | - | ['engineering_lead', 'security_champion', 'incident_lead'] |
| SH-03 | - | Data Protection Officer (DPO) | - | - | ['gdpr_compliance', 'privacy_oversight'] |
| SH-04 | - | Compliance Lead | - | - | ['regulatory_compliance', 'documentation'] |
| SH-05 | - | Engineering Team | - | - | ['implementation', 'secure_development'] |
| SH-06 | - | Customer Support | - | - | ['user_data_handling'] |
| SH-07 | - | External Auditor | - | - | ['annual_review', 'certification'] |

**ID Pattern:** `SH-{NN}` — where `{NN}` is a 2-digit sequential number.

### 3.2 Stakeholder Influence Matrix

| Stakeholder ID | Influence Level | Interest Level | Engagement Strategy |
| --- | --- | --- | --- |
| SH-01 | HIGH | HIGH | Weekly briefings; direct involvement in compliance decisions |
| SH-02 | HIGH | HIGH | Weekly briefings; direct involvement in compliance decisions |
| SH-03 | MEDIUM | HIGH | Quarterly reviews; incident coordination |
| SH-04 | MEDIUM | MEDIUM | Sprint reviews; implementation feedback |
| SH-05 | LOW | HIGH | Annual review; contract updates; breach notifications |
| SH-06 | LOW | LOW | Ad-hoc coordination; compliance documentation review |
| SH-07 | LOW | LOW | Ad-hoc coordination; compliance documentation review |

---

## 4. BUSINESS GOALS CATALOG

| Goal ID | Goal | Description | Priority | Related Regulations | Success Metrics |
| --- | --- | --- | --- | --- | --- |
| BG-01 | GDPR-compliant data processing | GDPR-compliant data processing | HIGH | - | - |
| BG-02 | CRA-conformant product | CRA-conformant product | HIGH | - | - |
| BG-03 | Customer trust through security transparency | Customer trust through security transparency | MEDIUM | - | - |
| BG-04 | Operational efficiency via managed services | Operational efficiency via managed services | MEDIUM | - | - |
| BG-05 | EU market expansion readiness | EU market expansion readiness | LOW | - | - |

**ID Pattern:** `BG-{NN}` where `{NN}` is a 2-digit sequential number.

---

## 5. INTAKE FORM RESPONSE SUMMARY

The complete intake form responses are documented in `01_Company_Context.md` (AEGIS Intake Form v2.0 — layered format). The following summarises key findings:

**Layer 0 — Company Profile:**
- Micro-enterprise (8 employees, <€2M revenue)
- Technology/Software sector
- Portugal (EU) jurisdiction

**Layer 1 — Regulatory Decision Tree:**
- GDPR: **APPLICABLE** (processes personal data of EU data subjects (controller or processor obligations))
- CRA: **APPLICABLE** (SaaS placed on EU market, Default class)
- NIS 2: **NOT APPLICABLE** (below all thresholds (8 < 50 employees))
- DORA: **NOT APPLICABLE** (not a financial entity (no DORA Art. 2(1) activity))
- AI Act: **NOT APPLICABLE** (no AI/ML systems in scope (or only non-Annex III use cases))

**Layer 2 — Conditional Blocks:**
- B6 (Supply Chain): ACTIVATED
- B7 (CRA Classification): ACTIVATED
- B8 (Multi-Actor Roles): ACTIVATED

**Complexity Tier:** LOW

---

## 6. REGULATORY APPLICABILITY FLAGS

| Regulation | Applicable? | Rationale | Applicability Threshold | Threshold Met? |
| --- | --- | --- | --- | --- |
| GDPR | YES | Processes personal data of eu data subjects (controller or processor obligations) | Processes personal data of EU residents | YES |
| CRA | YES | Saas placed on eu market, default class | Places digital products with digital elements on EU market | YES |
| NIS2 | NO | Below all thresholds (8 < 50 employees) | Essential/Important entity AND (>=50 employees OR >=€10M revenue) | NO |
| DORA | NO | Not a financial entity (no dora art. 2(1) activity) | Financial entity per Art. 2 definition | NO |
| AI_Act | NO | No ai/ml systems in scope (or only non-annex iii use cases) | AI system provider/deployer; High-risk per Annex II/III | NO |

**Clauses to assess per applicable regulation:**
| Regulation | Clause Count |
| --- | --- |
| CRA | 26 |
| GDPR | 28 |

---

## 7. ARCHITECTURAL IMPLICATIONS

| Implication ID | Description | Source Regulation | Impact Area | Severity | Mitigation Approach |
| --- | --- | --- | --- | --- | --- |
| AI-01 | High dependency on cloud third parties (AWS, Firebase, Stripe) creates concentration risk; inherited security controls must be evidenced | GDPR, CRA | Infrastructure | HIGH | Obtain SOC 2 / ISO 27001 evidence from each cloud provider; include security clauses in DPAs and SBOM updates |
| AI-02 | Multi-actor regulatory roles: Controller + Processor for GDPR; Manufacturer for CRA — distinct obligations per data element | GDPR, CRA | Governance & Documentation | HIGH | Maintain per-data-element role assignment table (B8) and route notifications through the correct workflow |
| AI-03 | Limited in-house security expertise (0.85 FTE) requires reliance on managed services and external advisors | GDPR, CRA, NIS 2 (where applicable) | People & Process | MEDIUM | Engage external DPO/advisor; lean on managed KMS, managed PostgreSQL, and managed Auth0 to inherit baseline controls |
| AI-04 | Cross-regulation tension in breach notification timelines: GDPR Art. 33 requires 72h while CRA Art. 14 requires 24h for actively exploited vulnerabilities | CRA, GDPR | Incident Response | MEDIUM | Adopt the maximum-SLA workflow (24h internal escalation) so both regimes are satisfied from the same detection pipeline |
| AI-05 | B2B enterprise customers act as additional data controllers for project content — DPA chain required per Art. 28 GDPR | GDPR | Supply Chain / DPA | MEDIUM | Maintain template DPA clauses; instrument processor-assisted deletion workflow for end-user DSARs forwarded by enterprise customers |

**ID Pattern:** `AI-{NN}` where `{NN}` is a 2-digit sequential number.

---

## 8. DATA FLOW SUMMARY

| Data ID | Data Type | Source | Destination | Transfer Method | Encryption | Regulatory Constraint |
| --- | --- | --- | --- | --- | --- | --- |
| DF-01 | Customer PII (name, email) | User registration | Database (EU region) | HTTPS / REST API | TLS 1.3 in transit; AES-256 at rest | GDPR Art. 5, 32 — lawfulness, security |

**ID Pattern:** `DF-{NN}` or `FLOW-{NN}` where `{NN}` is a 2-digit sequential number.

---

## 9. COMPLIANCE CAPABILITY ASSESSMENT

| Capability ID | Capability | Current State | Target State | Gap | Priority |
| --- | --- | --- | --- | --- | --- |
| CAP-01 | Records of Processing Activities (RoPA) | NONE | MATURE | HIGH | HIGH — Implement automated logging and template; required by GDPR Art. 30 |
| CAP-02 | CRA Technical Documentation (Annex I) | AD-HOC | MATURE | HIGH | HIGH — Produce Annex I documentation pack, SBOM, and vulnerability handling policy |
| CAP-03 | Incident Response Playbook | AD-HOC | MATURE | MEDIUM | MEDIUM — Formalise detection-to-notification runbook covering both GDPR 72h and CRA 24h paths |
| CAP-04 | Supplier / Sub-processor Risk Management | NONE | PARTIAL | MEDIUM | MEDIUM — Maintain register of sub-processors (AWS, Stripe, Auth0) and evidence DPAs |

**ID Pattern:** `CAP-{NN}` where `{NN}` is a 2-digit sequential number.

---

## 10. TIER & COMPLIANCE POSTURE (CORR-038)

The following table is the single source of truth for the company's compliance posture, derived from the v2 ApplicabilityContext.

| Field | Value |
| --- | --- |
| Applicable Regulations (computed) | CRA, GDPR |
| Declared Applicable (per YAML) | CRA, GDPR |
| Declaration Gaps | 0 |
| Tier | **LOW** — light-touch (MICRO/SMALL with 1-2 applicable regs) |

**Obligated Party per Regulation:**
| Regulation | Obligated Party |
| --- | --- |
| GDPR | controller |
| CRA | manufacturer |

---

## N-1. VERSION HISTORY

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 1.0 | 2026-04-17 | Compliance Lead | Initial template release |
| 1.1 | 2026-04-22 | Compliance Lead | Fixed regulatory applicability (NIS 2/DORA/AI Act: YES→NO), corrected size category to reflect the as-measured company profile, filled 38-question summary, populated stakeholder register and influence matrix, added business goals catalog |
| 2.0 | 2026-04-23 | Compliance Lead | Converted to layered intake format — removed Q-number summary tables, updated to reference AEGIS Intake Form v2.0 |
| 2.1 | 2026-07-14 | Executor (Sprint D-final) | Enriched §3 stakeholders, §4 business goals, §5 layered intake summary, §7 architectural implications (5), §8 data flow summary, §9 compliance capability assessment (RoPA, CRA docs, IR, supplier) to mirror reference |
| 2.2 | 2026-07-28 | Executor (CORR-073) | Scaled §2/§5/§6 prose to company profile (no more hardcoded Micro-enterprise/<€2M/TinyTask-shaped rationales). Doc 05 §2 now sources from ApplicabilityContext (CORR-038 truth). |

## N. DOCUMENT APPROVAL

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Document Author | Compliance Lead |  | 2026-04-17 |
| Technical Review |  |  |  |
| Business Review |  |  |  |
| AEGIS Methodology Review |  |  |  |

---

**Next Document:** 05_Regulatory_Applicability.md
**Gate Status:** [PENDING / PASS / FAIL]
