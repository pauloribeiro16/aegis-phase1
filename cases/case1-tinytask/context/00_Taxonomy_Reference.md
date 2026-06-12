---
document_id: AEGIS-COMMON-00
title: Security Control Domain Taxonomy Reference
phase: Common
version: 1.0
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: [AEGIS Research Team]
status: DRAFT
inputs: []
outputs: [01_Company_Context.md, 02_Regulatory_Mapping_Master.xlsx]
traceability: AEGIS Class Model → SecurityControlDomain
related_documents: [01_Company_Context.md, 02_Regulatory_Mapping_Master.md]
---

# Security Control Domain Taxonomy Reference

## 1. DOCUMENT PURPOSE

This document establishes the canonical 10x38 Sub-Domain taxonomy used throughout all AEGIS phases. It serves as the common vocabulary between regulations (GDPR, CRA, NIS 2, DORA, AI Act) and implementation artifacts.

**Alignment with Class Model:** This document defines instances of the `SecurityControlDomain` class.

**Phase Usage:**
- Phase 1: Regulatory coverage mapping (T6)
- Phase 2: Rules Catalog organization
- Phase 3: Functional Node allocation

**Gate Criteria:**
- [ ] All 38 sub-domains listed with unique IDs
- [ ] Each sub-domain has at least one regulatory driver
- [ ] Sole authority sub-domains identified
- [ ] Normative Intensity scale defined

---

## 2. TAXONOMY STRUCTURE (10 Domains x 38 Sub-Domains)

| Domain ID | Domain Name | Sub-Domains Count | Primary Regulations |
|-----------|-------------|-------------------|---------------------|
| D-01 | Data Protection & Encryption | 4 | GDPR, CRA |
| D-02 | Vulnerability Management | 4 | CRA, DORA |
| D-03 | Access Control | 4 | GDPR, NIS 2 |
| D-04 | Incident Response | 4 | GDPR, NIS 2, CRA |
| D-05 | Data Lifecycle | 4 | GDPR, AI Act |
| D-06 | Supply Chain | 4 | DORA, CRA |
| D-07 | Secure Development | 4 | CRA, NIS 2, DORA |
| D-08 | Human Factors | 3 | NIS 2, DORA, GDPR |
| D-09 | Governance & Documentation | 4 | All regulations |
| D-10 | Monitoring & Audit | 3 | DORA, AI Act |
| **TOTAL** | **All Domains** | **38** | **5 regulations** |

---

## 3. SUB-DOMAIN CATALOG (38 Entries)

### D-01: Data Protection & Encryption

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-01.1 | Data at Rest Encryption | [Description of encryption-at-rest requirements] | GDPR-C04/C14, CRA-C07, DORA-C09 | No | 3.000 |
| D-01.2 | Data in Transit Encryption | [Description of encryption-in-transit requirements] | GDPR-C15, CRA-C08, DORA-C10 | No | 3.000 |
| D-01.3 | Cryptographic Key Management | [Description of key lifecycle management] | CRA-C15, DORA-C17, NIS2-C18 | No | 3.000 |
| D-01.4 | Data Integrity Mechanisms | [Description of integrity verification] | GDPR-C05, CRA-C09, AI-C17/C18 | No | 3.000 |

### D-02: Vulnerability Management

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-02.1 | Vulnerability Identification | [Description of vuln identification processes] | CRA-C01/C17, DORA-C08, AI-C03/C16 | No | 3.000 |
| D-02.2 | Patch Management & Updates | [Description of patching processes] | CRA-C04/C19, DORA-C13/C26 | No | 3.000 |
| D-02.3 | Coordinated Vuln. Disclosure | [Description of CVD policy requirements] | CRA-C21/C26 | **Yes (CRA)** | 3.000 |
| D-02.4 | Threat-Led Penetration Testing | [Description of TLPT requirements] | DORA-C34, AI-C04 | No | 3.000 |

### D-03: Access Control

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-03.1 | Identity Lifecycle Management | [Description of identity provisioning/deprovisioning] | CRA-C05, DORA-C15, NIS2-C19 | No | 3.000 |
| D-03.2 | Multi-Factor Authentication | [Description of MFA requirements] | CRA-C06, DORA-C16, NIS2-C21 | No | 3.000 |
| D-03.3 | Authorization & Least Privilege | [Description of RBAC and least privilege] | GDPR-C10/C17, DORA-C14, NIS2-C20 | No | 3.000 |
| D-03.4 | Secure System Defaults | [Description of secure-by-default configuration] | CRA-C03 | **Yes (CRA)** | 3.000 |

### D-04: Incident Response

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-04.1 | Incident Detection & Triage | [Description of detection and triage processes] | CRA-C13, DORA-C21/C30, NIS2-C28/C29 | No | 3.000 |
| D-04.2 | Containment & Mitigation | [Description of containment procedures] | GDPR-C18, CRA-C11, DORA-C22/C24, NIS2-C05 | No | 3.000 |
| D-04.3 | Regulatory Notification | [Description of notification timelines and recipients] | GDPR-C21/C23, CRA-C25, DORA-C29/C31, NIS2-C25/C26/C27, AI-C26/C29 | No | 3.000 |
| D-04.4 | Data Restoration & Recovery | [Description of backup and recovery requirements] | GDPR-C16, DORA-C23/C25, NIS2-C06/C07 | No | 3.000 |

### D-05: Data Lifecycle

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-05.1 | Data Minimization | [Description of data minimization principles] | GDPR-C01, CRA-C10, AI-C05/C06/C08 | No | 3.000 |
| D-05.2 | Retention & Archiving | [Description of retention schedule requirements] | GDPR-C02/C03, AI-C07 | No | 3.000 |
| D-05.3 | Right to Erasure | [Description of erasure/deletion procedures] | GDPR-C06, CRA-C16 | No | 3.000 |
| D-05.4 | Data Portability | [Description of data export/portability] | GDPR-C07 | **Yes (GDPR)** | 3.000 |

### D-06: Supply Chain

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-06.1 | Vendor Risk Assessment | [Description of third-party risk evaluation] | GDPR-C11, DORA-C35/C36, NIS2-C08/C23 | No | 3.000 |
| D-06.2 | Software Bill of Materials (SBOM) | [Description of SBOM requirements] | CRA-C18 | **Yes (CRA)** | 3.000 |
| D-06.3 | Contractual Security Obligations | [Description of contract-based security clauses] | GDPR-C12, DORA-C37, NIS2-C09 | No | 3.000 |
| D-06.4 | Third-Party Boundary Management | [Description of boundary security for third parties] | DORA-C38, NIS2-C24 | No | 3.000 |

### D-07: Secure Development

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-07.1 | Secure-by-Design Principles | [Description of secure design principles] | GDPR-C09, CRA-C02/C22, DORA-C18, NIS2-C10 | No | 3.000 |
| D-07.2 | Secure Coding Practices | [Description of secure coding standards] | DORA-C19 | **Yes (DORA)** | 3.000 |
| D-07.3 | CI/CD Pipeline Security | [Description of pipeline security controls] | NIS2-C11 | **Yes (NIS 2)** | 3.000 |
| D-07.4 | Change Management | [Description of change management processes] | DORA-C06 | **Yes (DORA)** | 3.000 |

### D-08: Human Factors

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-08.1 | General Security Awareness | [Description of awareness training programs] | GDPR-C27, DORA-C27, NIS2-C14 | No | 3.000 |
| D-08.2 | Role-Specific Competence | [Description of role-based training requirements] | GDPR-C28, DORA-C28, NIS2-C15, AI-C14/C15/C24 | No | 3.000 |
| D-08.3 | Management Board Training | [Description of executive-level training] | DORA-C02, NIS2-C02 | No | 3.000 |

### D-09: Governance & Documentation

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-09.1 | Information Security Policies | [Description of policy framework requirements] | GDPR-C08/C25/C26, CRA-C24, DORA-C01/C03, NIS2-C01/C03, AI-C12/C13/C20/C23 | No | 3.000 |
| D-09.2 | Impact & Risk Assessments | [Description of DPIA/risk assessment requirements] | GDPR-C20/C24, CRA-C23, DORA-C04, NIS2-C04, AI-C01/C02/C22/C28 | No | 3.000 |
| D-09.3 | Asset Inventories | [Description of asset register requirements] | DORA-C05 | **Yes (DORA)** | 3.000 |
| D-09.4 | Records of Processing | [Description of RoPA requirements] | GDPR-C13/C22, AI-C11 | No | 3.000 |

### D-10: Monitoring & Audit

| Sub-Domain ID | Sub-Domain Name | Description | Regulatory Driver | Sole Authority | Normative Intensity |
|---------------|-----------------|-------------|-------------------|----------------|---------------------|
| D-10.1 | Continuous Security Monitoring | [Description of continuous monitoring requirements] | CRA-C12, DORA-C07/C20, NIS2-C29, AI-C25 | No | 3.000 |
| D-10.2 | Audit Logging & Traceability | [Description of audit log requirements] | CRA-C14, DORA-C12, NIS2-C22, AI-C09/C10/C19 | No | 3.000 |
| D-10.3 | Compliance Testing | [Description of compliance testing/validation] | GDPR-C19, CRA-C20, DORA-C32/C33, NIS2-C13, AI-C21/C27 | No | 3.000 |

---

## 4. SOLE AUTHORITY SUMMARY

### 4.1 Global Sole Authority (All 5 Regulations)

| Sub-Domain | Sole Authority Regulation | Justification |
|------------|---------------------------|---------------|
| D-02.3 | CRA | Only CRA mandates coordinated vulnerability disclosure |
| D-03.4 | CRA | Only CRA requires secure system defaults |
| D-05.4 | GDPR | Only GDPR establishes data portability rights |
| D-06.2 | CRA | Only CRA requires SBOM for digital products |
| D-07.2 | DORA | Only DORA mandates secure coding practices for financial entities |
| D-07.3 | NIS 2 | Only NIS 2 specifies CI/CD pipeline security |
| D-07.4 | DORA | Only DORA formalizes change management processes |
| D-09.3 | DORA | Only DORA requires formal asset inventories |

**Total:** 8/38 sub-domains (21.1%) have sole authority

### 4.2 Sole Authority Risk Assessment

When a sole authority regulation is NOT applicable to a case study, the corresponding sub-domain has zero regulatory mandate, creating a coverage gap.

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| Sole authority regulation not applicable | Sub-domain becomes optional (no mandate) | Reference level 2 frameworks (ISO 27001, NIST CSF) |
| Sole authority regulation applicable | Sub-domain is covered | Proceed with normal clause mapping |
| Multiple regulations cover sub-domain | Redundant coverage (complementary) | Select highest normative intensity |

---

## 5. NORMATIVE INTENSITY REFERENCE (T9)

### 5.1 T9 Scale Definition

| Level | Definition | Keyword | Example |
|-------|------------|---------|---------|
| T1 | Informational | May | "Organizations may consider..." |
| T2 | Advisory | Should | "Operators should implement..." |
| T3 | Recommended | Should (strong) | "Providers should ensure..." |
| T4 | Expected | Expected to | "Entities are expected to..." |
| T5 | Conditional Mandatory | Shall (if condition met) | "Shall implement when..." |
| T6 | Contextual Mandatory | Shall (context-dependent) | "Shall ensure for high-risk..." |
| T7 | Strong Mandatory | Shall | "Controllers shall implement..." |
| T8 | Absolute Mandatory | Shall (no exceptions) | "Shall without delay..." |
| T9 | Critical Mandatory | Shall + penalty | "Shall... subject to penalties" |

### 5.2 Regulation-Level Normative Intensity Summary

| Regulation | Mean NI | Weight 3 % | Weight 2 % | Weight 1 % | Total Clauses |
|------------|---------|------------|------------|------------|---------------|
| DORA | 3.000 | 100.0% | 0.0% | 0.0% | 38 |
| CRA | 2.923 | 92.3% | 7.7% | 0.0% | 26 |
| NIS 2 | 2.862 | 89.7% | 10.3% | 0.0% | 29 |
| AI Act | 2.793 | 82.8% | 17.2% | 0.0% | 29 |
| GDPR | 2.714 | 71.4% | 28.6% | 0.0% | 28 |
| **COMBINED** | **2.858** | **88.0%** | **12.0%** | **0.0%** | **150** |

### 5.3 Case-Specific Normative Intensity

When a case study is instantiated, calculate the normative intensity based only on applicable regulations.

| Regulation | Applicable? | Mean NI | Sub-Domains Covered | Clause Count |
|------------|-------------|---------|---------------------|--------------|
| GDPR | [Yes/No] | [Value] | [N]/38 | [Count] |
| CRA | [Yes/No] | [Value] | [N]/38 | [Count] |
| NIS 2 | [Yes/No] | [Value] | [N]/38 | [Count] |
| DORA | [Yes/No] | [Value] | [N]/38 | [Count] |
| AI Act | [Yes/No] | [Value] | [N]/38 | [Count] |
| **COMBINED** | **—** | **[Value]** | **[N]/38** | **[Count]** |

---

## N-1. VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | YYYY-MM-DD | [AEGIS Research Team] | Initial template release |

## N. DOCUMENT APPROVAL

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Document Author | [AEGIS Research Team] | | |
| AEGIS Methodology Review | | | |
| Technical Review | | | |
| Business Review | | | |
