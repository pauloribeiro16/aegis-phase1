---
document_id: AEGIS-P1-04
title: Company Context Assessment
version: 2.1
status: DRAFT
generated_at: "2026-07-14T11:25:30Z"
phase: 1
author: Compliance Lead
case_study: TinyTask Lda.
inputs: [01_Company_Context.md]
outputs: [05_Regulatory_Applicability.md]
traceability: AEGIS Class Model -> CompanyContext, ComplianceContext classes
related_documents: [00_Taxonomy_Reference.md, 01_Company_Context.md, 04a_Architecture_DataInventory.md]
applicable_regs: [GDPR, CRA]
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
| Assessment ID | AEGIS-04-Case_01_TinyTask_SaaS-202607 |
| Assessment Date | 2026-07-14 |
| Assessor | Compliance Lead |
| Company Name | TinyTask Lda. |
| Jurisdiction | Portugal (EU) |
| Sector | Technology / Software |
| Size Category | Micro-enterprise — 8 employees, <€2M revenue |
| Assessment Method | AEGIS Intake Form v2.0 (layered: Company Profile + Decision Tree + Conditional Blocks) |

---

## 3. STAKEHOLDER ANALYSIS (A1)

### 3.1 Stakeholder Register

| ID | Name | Role | Organisation | Contact | Responsibilities |
| --- | --- | --- | --- | --- | --- |
| SH-01 | CEO | Executive | TinyTask Lda. | ceo@tinytask.pt | Strategic direction, regulatory oversight, business accountability |
| SH-02 | CTO | Technical | TinyTask Lda. | cto@tinytask.pt | Engineering, security architecture, infrastructure decisions |
| SH-03 | DPO | Compliance | TinyTask Lda. (external advisor) | dpo@tinytask.pt | GDPR compliance, RoPA maintenance, breach response coordination |
| SH-04 | Dev Team | Technical | TinyTask Lda. | dev@tinytask.pt | Implementation, secure development, vulnerability remediation |
| SH-05 | B2B Customers | External | Various enterprises | (via portal) | Data controllers for project content uploaded by end users |
| SH-06 | Stripe | Supplier | Stripe Inc. | (via API) | Payment processing (sub-processor; PCI-DSS scope) |
| SH-07 | AWS | Supplier | Amazon Web Services (EU region) | (via console) | Cloud infrastructure (sub-processor; inherited controls) |

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
| BG-01 | Maintain EU regulatory compliance | Maintain EU regulatory compliance | HIGH | GDPR, CRA | Zero high-severity audit findings |
| BG-02 | Achieve CRA conformity assessment readiness | Achieve CRA conformity assessment readiness | HIGH | CRA | Completed technical documentation (Annex I) |
| BG-03 | Grow EU B2B customer base by 25% YoY | Grow EU B2B customer base by 25% YoY | MEDIUM | GDPR (B2B data) | New B2B contracts signed |
| BG-04 | Reduce mean-time-to-detect for incidents | Reduce mean-time-to-detect for incidents | MEDIUM | GDPR (breach), CRA (vulns) | MTTD < 24h |
| BG-05 | Establish formal security policies | Establish formal security policies | LOW | All applicable | Documented policies in place |

**ID Pattern:** `BG-{NN}` where `{NN}` is a 2-digit sequential number.

---

## 5. INTAKE FORM RESPONSE SUMMARY

The complete intake form responses are documented in `01_Company_Context.md` (AEGIS Intake Form v2.0 — layered format). The following summarises key findings:

**Layer 0 — Company Profile:**
- Micro-enterprise (8 employees, <€2M revenue)
- Technology / Software sector
- Portugal (EU) jurisdiction

**Layer 1 — Regulatory Decision Tree:**
- GDPR: **APPLICABLE** (processes personal data)
- CRA: **APPLICABLE** (SaaS placed on EU market, Default class)
- NIS 2: **NOT APPLICABLE** (below all thresholds)
- DORA: **NOT APPLICABLE** (not financial entity)
- AI Act: **NOT APPLICABLE** (no AI/ML systems)

**Layer 2 — Conditional Blocks:**
- B6 (Supply Chain): ACTIVATED
- B7 (CRA Classification): ACTIVATED
- B8 (Multi-Actor Roles): ACTIVATED

**Complexity Tier:** MEDIUM

---

## 6. REGULATORY APPLICABILITY FLAGS

| Regulation | Applicable? | Rationale | Applicability Threshold | Threshold Met? |
| --- | --- | --- | --- | --- |
| GDPR | YES | Processes personal data (emails, names) of EU residents | Processes personal data of EU residents | YES |
| CRA | YES | SaaS product placed on EU market; manufacturer status | Places digital products with digital elements on EU market | YES |
| NIS 2 | NO | Below employee (8 < 50) and revenue (<€2M < €10M) thresholds | Essential/Important entity AND (>=50 employees OR >=€10M revenue) | NO |
| DORA | NO | Not a financial entity; payments via Stripe | Financial entity per Art. 2 definition | NO |
| AI Act | NO | No AI/ML systems; deterministic logic only | AI system provider/deployer; High-risk per Annex II/III | NO |

---

## 7. ARCHITECTURAL IMPLICATIONS

| Implication ID | Description | Source Regulation | Impact Area | Severity | Mitigation Approach |
| --- | --- | --- | --- | --- | --- |
| AI-01 | High dependency on cloud third parties (AWS or equivalent EU cloud provider, Auth0, Datadog or equivalent, Stripe) creates concentration risk; inherited security controls must be evidenced | GDPR, CRA | Infrastructure | HIGH | Obtain SOC 2 / ISO 27001 evidence from each cloud provider; include security clauses in DPAs and SBOM updates |
| AI-02 | Multi-actor regulatory roles: Controller + Processor for GDPR; Manufacturer for CRA — distinct obligations per data element | GDPR, CRA | Governance & Documentation | HIGH | Maintain per-data-element role assignment table (B8) and route notifications through the correct workflow |
| AI-03 | Limited in-house security expertise (0.85 FTE) requires reliance on managed services and external advisors | GDPR, CRA, NIS 2 (where applicable) | People & Process | MEDIUM | Engage external DPO/advisor; lean on managed KMS, managed PostgreSQL, and managed Auth0 to inherit baseline controls |
| AI-04 | Cross-regulation tension in breach notification timelines: GDPR Art. 33 requires 72h while CRA Art. 14 requires 24h for actively exploited vulnerabilities | GDPR, CRA | Incident Response | MEDIUM | Adopt the maximum-SLA workflow (24h internal escalation) so both regimes are satisfied from the same detection pipeline |
| AI-05 | B2B enterprise customers act as additional data controllers for project content — DPA chain required per Art. 28 GDPR | GDPR | Supply Chain / DPA | MEDIUM | Maintain template DPA clauses; instrument processor-assisted deletion workflow for end-user DSARs forwarded by enterprise customers |

**ID Pattern:** `AI-{NN}` where `{NN}` is a 2-digit sequential number.

---

## 8. DATA FLOW SUMMARY

The platform exchanges data through 5 documented flows (FLOW-01, FLOW-02, FLOW-03, FLOW-04, FLOW-05). User-to-application traffic terminates over TLS-protected HTTPS endpoints; application-to-store traffic stays on the cloud provider's encrypted internal network. Outbound sub-processor flows (Auth0, Datadog or equivalent, Stripe) carry pseudonymised or transactional payloads only, consistent with the GDPR Art. 5 minimisation principle and the processor obligations inherited via the active DPAs.

| Data ID | Data Type | Source | Destination | Transfer Method | Encryption | Regulatory Constraint |
| --- | --- | --- | --- | --- | --- | --- |
| FLOW-01 | Account data and project data | Web client | SYS-01 Main SaaS Application | HTTPS REST | Y, TLS 1.3 | GDPR Art. 32 — security of processing |
| FLOW-02 | Customer accounts, project data, audit metadata | SYS-01 Main SaaS Application | STORE-01 Main PostgreSQL | PostgreSQL TLS | Y, encrypted internal database transport | GDPR Art. 32 — security of processing |
| FLOW-03 | Pseudonymised events, request metadata, error traces | SYS-01 Main SaaS Application | STORE-03 Logs and analytics | HTTPS agent/API | Y, TLS 1.2 or higher | GDPR Art. 32 — security of processing |
| FLOW-04 | Authentication credentials, email identifier, OIDC tokens | Web client | SYS-02 Auth Service | OAuth 2.0/OIDC over HTTPS | Y, TLS 1.3 | GDPR Art. 5, 32 — lawfulness, security |
| FLOW-05 | Billing metadata and hosted-checkout redirect; no card PAN stored by TinyTask | SYS-01 Main SaaS Application | Stripe | HTTPS API | Y, TLS 1.2 or higher | GDPR Art. 5, 32; PCI-DSS scope via Stripe |

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

## N-1. VERSION HISTORY

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 1.0 | 2026-04-17 | Compliance Lead | Initial template release |
| 1.1 | 2026-04-22 | Compliance Lead | Fixed regulatory applicability (NIS 2/DORA/AI Act: YES→NO), corrected size (10→8 employees, €1M→<€2M), filled 38-question summary, populated stakeholder register and influence matrix, added business goals catalog |
| 2.0 | 2026-04-23 | Compliance Lead | Converted to layered intake format — removed Q-number summary tables, updated to reference AEGIS Intake Form v2.0 |
| 2.1 | 2026-07-14 | Executor (Sprint D-final) | Enriched §3 stakeholders, §4 business goals, §5 layered intake summary, §7 architectural implications (5), §8 data flow summary, §9 compliance capability assessment (RoPA, CRA docs, IR, supplier) to mirror reference |

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
