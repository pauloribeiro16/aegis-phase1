---
document_id: AEGIS-P1-04b
title: Security Posture Assessment (Maturity Model)
version: 1.0
status: DRAFT
generated_at: "2026-07-14T11:03:01Z"
phase: 1
created: "2026-07-14T11:03:01Z"
updated: "2026-07-14T11:03:01Z"
author: Executor
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, 04a_Architecture_DataInventory.md, 05_Regulatory_Applicability.md]
outputs: [07_Structured_Compliance_Matrix.md]
applicable_regs: [GDPR, CRA]
active_subdomains: 31
inactive_subdomains: [D-02.4, D-06.4, D-07.2, D-07.3, D-07.4, D-08.3, D-09.3]
related_documents: [04a_Architecture_DataInventory.md, ../../../00_METHODOLOGY/PREPROCESSING/SubDomains/index.md, ../../../00_METHODOLOGY/PREPROCESSING/SubDomains/]
---
# Security Posture Assessment (Maturity Model)

## 1. Purpose

This document captures the company's **current security posture** across the 10 AEGIS macro-domains (D-01 .. D-10) using a 0-4 maturity scale, and identifies the gap to a target maturity proportional to the company's tier. It supports compliance evidence for **GDPR Art. 32**, **CRA Annex I Part I**, and downstream Doc 07 (Structured Compliance Matrix).

## 2. Assessment Methodology

TinyTask Lda. is assessed as a low-tier Micro-enterprise SaaS with 8 employees using managed-cloud infrastructure. Current maturity measures what exists today, not the target state. Target maturity is proportional to the company profile but aligned with active GDPR/CRA SubDomains fit criteria (applicable_regs = GDPR, CRA).

| Level | Label | Description |
|---|---|---|
| 0 | None | No controls in place |
| 1 | Ad-hoc | Informal, inconsistent, no documentation |
| 2 | Defined | Documented or consistently repeatable, but not fully measured |
| 3 | Managed | Implemented, monitored, measured, and regularly reviewed |
| 4 | Optimized | Continuously improved and substantially automated |

Assessment evidence is drawn from `04a_Architecture_DataInventory.md`, `04_Company_Context_Assessment.md`, and `05_Regulatory_Applicability.md`. The active Layer 0 scope is 31 of 38 SubDomains for `applicable_regs = [GDPR, CRA]`; D-08.3 is inactive when its participating regulations do not apply.

## 3. Per-Domain Assessment

### D-01 Data Protection — Maturity: 2

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| Encryption at rest | Implemented for main database, backups, and logs | STORE-01, STORE-02, STORE-03 | Provider-managed AES-256 encryption; no customer-managed HSM |
| Encryption in transit | Implemented for all documented production flows | FLOW-01, FLOW-02, FLOW-03, FLOW-04, FLOW-05 | TLS 1.3 used for main app and Auth0; third-party APIs use TLS 1.2 or higher |
| Key management | Basic cloud KMS | SYS-04 | Manual key rotation; no formal key ceremony or dual control |
| Data integrity | Basic application/database controls | SYS-01, SYS-03, SYS-05 | Database constraints and backup checks exist; no formal integrity verification schedule |

**Target maturity**: 3  
**Gap**: 1  
**Notes**: Current evidence supports the bulk of data protection controls; the 1-step gap is documented formalisation. Add formal key-lifecycle documentation, periodic restore/integrity tests, and review evidence for GDPR Art. 32 and CRA Annex I Part I confidentiality/integrity controls. Relevant Layer 0 files: [D-01.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-01_Data-Protection/D-01.1.md), [D-01.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-01_Data-Protection/D-01.2.md), [D-01.3](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-01_Data-Protection/D-01.3.md), [D-01.4](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-01_Data-Protection/D-01.4.md).

### D-02 Vulnerability Management — Maturity: 1

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| Vulnerability scanning | Weekly Snyk scan for application dependencies | SYS-01, STORE-03 | Results are reviewed manually; no documented acceptance or exception process |
| Patch management | Manual patching | Architecture inventory (no specific asset reference) | No formal critical/high SLA; fixes depend on developer availability |
| Pen testing | Informal self-testing only | Architecture inventory (no specific asset reference) | No threat-led or independent penetration test performed |
| CVD policy | Not published | Architecture inventory (no specific asset reference) | No security.txt or public vulnerability policy |

**Target maturity**: 3  
**Gap**: 2  
**Notes**: Vulnerability Management is the largest gap (current 1, target 3); controls exist informally but lack evidence artefacts and review cycles. Create a vulnerability register, define critical/high SLAs, and publish security.txt with a CVD policy. Relevant Layer 0 files: [D-02.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-02_Vulnerability-Management/D-02.1.md), [D-02.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-02_Vulnerability-Management/D-02.2.md), [D-02.3](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-02_Vulnerability-Management/D-02.3.md), [D-02.4](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-02_Vulnerability-Management/D-02.4.md).

### D-03 Access Control — Maturity: 2

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| IAM system | Auth0 for customer and administrator identity | SYS-02 | Managed identity service reduces implementation burden |
| MFA | Enforced for administrators only | Architecture inventory (no specific asset reference) | Customer MFA is optional; not universal |
| RBAC | Basic application roles | SYS-01, SYS-02, SYS-03 | Basic owner/member/admin model; quarterly access reviews not documented |
| Privileged access management | No dedicated PAM | Architecture inventory (no specific asset reference) | Least privilege is informal and handled by CTO |
| Default secure configs | Partial | Architecture inventory (no specific asset reference) | No documented secure baseline for all services |

**Target maturity**: 3  
**Gap**: 1  
**Notes**: Current evidence supports the bulk of access control controls; the 1-step gap is documented formalisation. Document access reviews, enforce customer MFA, and add a privileged-access logging baseline. Relevant Layer 0 files: [D-03.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-03_Access-Control/D-03.1.md), [D-03.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-03_Access-Control/D-03.2.md), [D-03.3](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-03_Access-Control/D-03.3.md), [D-03.4](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-03_Access-Control/D-03.4.md).

### D-04 Incident Response — Maturity: 1

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| IR plan | Basic plan exists | Architecture inventory (no specific asset reference) | No tested playbook and no incident roles beyond CTO/developers |
| Detection capability | Datadog or equivalent alerts | STORE-03, FLOW-03 | No SIEM, EDR, IDS, or 24/7 monitoring |
| Notification process | Informal DPO/CTO escalation | Architecture inventory (no specific asset reference) | No tested 24h CRA early-warning / 72h GDPR breach notification workflow |
| Recovery procedures | Backups exist | STORE-02, SYS-05 | Restore testing is not scheduled or evidenced |

**Target maturity**: 3  
**Gap**: 2  
**Notes**: Incident Response is the largest gap (current 1, target 3); controls exist informally but lack evidence artefacts and review cycles. Create a GDPR/CRA incident runbook with 24h/72h timing and run one tabletop exercise. Relevant Layer 0 files: [D-04.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-04_Incident-Response/D-04.1.md), [D-04.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-04_Incident-Response/D-04.2.md), [D-04.3](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-04_Incident-Response/D-04.3.md), [D-04.4](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-04_Incident-Response/D-04.4.md).

### D-05 Data Lifecycle — Maturity: 1

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| Data minimisation | Informal minimisation in product design | Architecture inventory (no specific asset reference) | Payment card data is kept out of scope by using Stripe |
| Retention policies | Not formally documented | STORE-01, STORE-02, STORE-03 | Retention periods are stated but not yet approved as policy |
| Erasure procedures | Manual support workflow | Architecture inventory (no specific asset reference) | No self-service DSAR portal; backup expiry relied on for residual copies |
| Data portability | Support-assisted export | Architecture inventory (no specific asset reference) | No automated export for all data categories |

**Target maturity**: 2  
**Gap**: 1  
**Notes**: Current evidence supports the bulk of data lifecycle controls; the 1-step gap is documented formalisation. Approve retention periods as policy, add DSAR tracking, and automate export/delete procedures. Relevant Layer 0 files: [D-05.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-05_Data-Lifecycle/D-05.1.md), [D-05.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-05_Data-Lifecycle/D-05.2.md), [D-05.3](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-05_Data-Lifecycle/D-05.3.md), [D-05.4](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-05_Data-Lifecycle/D-05.4.md).

### D-06 Supply Chain — Maturity: 1

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| Vendor assessment | Annual informal vendor review | Architecture inventory (no specific asset reference) | Evidence collection is not standardised |
| SBOM | Not implemented | Architecture inventory (no specific asset reference) | No CycloneDX/SPDX generation in CI/CD |
| Contract clauses | Partial | Architecture inventory (no specific asset reference) | DPAs with major subprocessor vendors; B2B processor DPA standardisation is incomplete |
| Boundary management | Ad hoc | FLOW-03, FLOW-04, FLOW-05 | No formal subprocessor register or data-flow review cadence |

**Target maturity**: 2  
**Gap**: 1  
**Notes**: Current evidence supports the bulk of supply chain controls; the 1-step gap is documented formalisation. Add CycloneDX/SPDX SBOM in CI/CD and maintain a subprocessor evidence register. Relevant Layer 0 files: [D-06.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-06_Supply-Chain/D-06.1.md), [D-06.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-06_Supply-Chain/D-06.2.md), [D-06.3](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-06_Supply-Chain/D-06.3.md), [D-06.4](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-06_Supply-Chain/D-06.4.md).

### D-07 Secure Development — Maturity: 2

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| Secure-by-design | Basic consideration during feature work | SYS-01 | No formal threat-model template per feature |
| Secure coding | OWASP guidelines and peer code review | Architecture inventory (no specific asset reference) | Code review exists but security checklist is not consistently recorded |
| CI/CD security | Basic dependency scanning | SYS-01 | No DAST, secrets scanning baseline, or SBOM release artefact |
| Change management | Pull request review | Architecture inventory (no specific asset reference) | Branch protection for main branch; no formal release risk classification or CAB |

**Target maturity**: 2  
**Gap**: 0  
**Notes**: Secure Development meets the proportional target for a low-tier SaaS. Strengthen CRA evidence through SBOM, release notes, and a documented security review checklist. Relevant Layer 0 files: [D-07.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-07_Secure-Development/D-07.1.md), [D-07.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-07_Secure-Development/D-07.2.md), [D-07.3](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-07_Secure-Development/D-07.3.md), [D-07.4](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-07_Secure-Development/D-07.4.md).

### D-08 Human Factors — Maturity: 1

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| Security awareness | Annual awareness training | Architecture inventory (no specific asset reference) | No phishing simulations or completion dashboard |
| Role-specific training | Informal developer learning | Architecture inventory (no specific asset reference) | No tracked curriculum for CTO, developers, support, or DPO role |
| Board training | Not applicable to active scope | Architecture inventory (no specific asset reference) | D-08.3 inactive for low-tier micro SaaS — NIS2 + DORA only participating regs |

**Target maturity**: 2  
**Gap**: 1  
**Notes**: Current evidence supports the bulk of human factors controls; the 1-step gap is documented formalisation. Build role-specific training curriculum (developers, DPO, CTO) and track completion annually. Relevant Layer 0 files: [D-08.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-08_Human-Factors/D-08.1.md), [D-08.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-08_Human-Factors/D-08.2.md).

### D-09 Governance & Documentation — Maturity: 1

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| Security policies | Basic policies only | Architecture inventory (no specific asset reference) | No complete information security policy set |
| Risk assessment | Informal | Architecture inventory (no specific asset reference) | Product and compliance risks discussed by CTO/CEO; no documented risk register |
| Asset inventory | Initial inventory created | Architecture inventory (no specific asset reference) | 04a is the first structured inventory; no CMDB yet |
| RoPA | Not complete | Architecture inventory (no specific asset reference) | GDPR Art. 30 records are not yet maintained as an operational artefact |

**Target maturity**: 3  
**Gap**: 2  
**Notes**: Governance & Documentation is the largest gap (current 1, target 3); controls exist informally but lack evidence artefacts and review cycles. Create RoPA, Annex VII evidence index, and a lightweight risk register with documented owner. Relevant Layer 0 files: [D-09.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-09_Governance-Documentation/D-09.1.md), [D-09.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-09_Governance-Documentation/D-09.2.md), [D-09.3](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-09_Governance-Documentation/D-09.3.md), [D-09.4](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-09_Governance-Documentation/D-09.4.md).

### D-10 Monitoring & Audit — Maturity: 1

| Control | Current | Evidence | Notes |
| --- | --- | --- | --- |
| Continuous monitoring | Datadog or equivalent for core app metrics | STORE-03, FLOW-03 | Coverage is basic and not mapped to all active security events |
| Audit logging | Partial application and authentication logging | SYS-01, SYS-02, STORE-03 | 30-day retention; no formal log review process |
| Compliance testing | Ad hoc internal checks | Architecture inventory (no specific asset reference) | No scheduled evidence review or control test plan |

**Target maturity**: 3  
**Gap**: 2  
**Notes**: Monitoring & Audit is the largest gap (current 1, target 3); controls exist informally but lack evidence artefacts and review cycles. Define alert taxonomy, log review cadence, and a basic control testing schedule. Relevant Layer 0 files: [D-10.1](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-10_Monitoring-Audit/D-10.1.md), [D-10.2](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-10_Monitoring-Audit/D-10.2.md), [D-10.3](../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-10_Monitoring-Audit/D-10.3.md).

## 4. Summary Dashboard

| Macro-domain | Current | Target | Gap |
| --- | --- | --- | --- |
| D-01 Data Protection | 2 | 3 | 1 |
| D-02 Vulnerability Management | 1 | 3 | 2 |
| D-03 Access Control | 2 | 3 | 1 |
| D-04 Incident Response | 1 | 3 | 2 |
| D-05 Data Lifecycle | 1 | 2 | 1 |
| D-06 Supply Chain | 1 | 2 | 1 |
| D-07 Secure Development | 2 | 2 | 0 |
| D-08 Human Factors | 1 | 2 | 1 |
| D-09 Governance & Documentation | 1 | 3 | 2 |
| D-10 Monitoring & Audit | 1 | 3 | 2 |
| **OVERALL** | 1.3 | 2.6 | 1.3 |

**Maturity distribution:** Level 0 = 0, Level 1 = 7, Level 2 = 3, Level 3 = 0, Level 4 = 0

## 5. Top Gaps (feeds Doc 07)

| Rank | Macro-domain | Gap | Gap Summary | Priority Remediation |
| --- | --- | --- | --- | --- |
| 1 | D-02 Vulnerability Management | 2 | Scanning exists but patch SLAs, disclosure, and testing are ad hoc | Create vulnerability register, define critical/high SLAs, publish security.txt and CVD policy |
| 2 | D-04 Incident Response | 2 | Basic plan and backups exist, but notification, containment, and recovery are not tested | Create GDPR/CRA incident runbook with 24h/72h timing and run one tabletop exercise |
| 3 | D-09 Governance & Documentation | 2 | RoPA, Annex VII documentation, formal risk assessment, and policy set are incomplete | Create RoPA, Annex VII evidence index, asset inventory owner, and lightweight risk register |
| 4 | D-10 Monitoring & Audit | 2 | Logs are retained but there is no security monitoring programme | Define alert taxonomy, log review cadence, and basic control testing schedule |
| 5 | D-01 Data Protection | 1 | Encryption is implemented but key lifecycle and integrity verification are not formal | Add key-rotation policy, periodic restore/integrity tests, and review evidence |

## 6. Consistency Check

| Consistency Item | Status | Evidence |
| --- | --- | --- |
| Architecture evidence matches 04a | PASS | 5 systems, 3 stores, 5 flows |
| Regulatory scope matches Doc 04 and Doc 05 | PASS | applicable_regs = [GDPR, CRA] |
| LOW-tier realism maintained | PASS | No enterprise HSM, SIEM, PAM, SOC, or CMDB claimed |
| Maturity scale used consistently | PASS | Current maturity values are integers 0-4; target and gap shown numerically |
| Evidence and gaps align | PASS | Largest gaps drive remediation in §5; D-07 strongest but not enterprise-grade |

## 7. Gate

| Gate Criterion | Status | Evidence |
| --- | --- | --- |
| All 10 macro-domains assessed with maturity level and evidence | PASS | Section 3 |
| Target maturity defined per macro-domain | PASS | Sections 3 and 4 |
| Summary dashboard populated | PASS | Section 4 |
| Top 5 gaps identified | PASS | Section 5 |
| SubDomains references included | PASS | Each macro-domain section links to active Layer 0 files |

## N-1. Version History

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 1.0 | 2026-07-14 | Executor | Generated AEGIS maturity assessment from state[architecture_inventory] and ontology |

## N. Document Approval

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Document Author | Executor |  | 2026-07-14 |
| Technical Review | CTO |  |  |
| AEGIS Methodology Review | Validator |  |  |

## See also

- **Data backbone:** `Case_01_Phase1.xlsx` (13 sheets: COVER, SYSTEMS, DATA_STORES, DATA_FLOWS, PERSONAL_DATA, THIRD_PARTIES, ROLES_RACI, MATURITY, SUBDOMAINS, REG_CHAIN, COMPLIANCE, GAPS, PRIORITIES)
