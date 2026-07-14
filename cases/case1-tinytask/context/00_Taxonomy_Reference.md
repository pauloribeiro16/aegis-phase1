---
document_id: AEGIS-COMMON-00
title: Security Control Domain Taxonomy Reference
version: 1.0
created: 2026-03-26
updated: 2026-03-26
author: [AEGIS Research Team]
status: DRAFT
source: Taxonomia.txt + Regulatory_Complementary_Mapping_Updated.txt (T6)
traceability: PhD Thesis Chapter 5, Section 5.7
inputs: []
outputs: [01_Company_Context.md]
---

# Security Control Domain Taxonomy Reference

## 1. DOCUMENT PURPOSE

This document establishes the canonical 10×38 Sub-Domain taxonomy used throughout all AEGIS phases. It serves as the common vocabulary between regulations (GDPR, CRA, NIS 2, DORA, AI Act) and implementation artifacts.

**Alignment with Class Model:** This document defines instances of the `SecurityControlDomain` class.

**Phase Usage:**
- Phase 1: Regulatory coverage mapping (T6)
- Phase 2: Rules Catalog organization
- Phase 3: Functional Node allocation

---

## 2. TAXONOMY STRUCTURE

| Domain ID | Domain Name | Sub-Domain Count | Primary Regulatory Driver |
|-----------|-------------|------------------|---------------------------|
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

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-01.1 | Data at Rest Encryption | GDPR-C04/C14, CRA-C07, DORA-C09 | 3.000 | No |
| D-01.2 | Data in Transit Encryption | GDPR-C15, CRA-C08, DORA-C10 | 3.000 | No |
| D-01.3 | Cryptographic Key Management | CRA-C15, DORA-C17, NIS2-C18 | 3.000 | No |
| D-01.4 | Data Integrity Mechanisms | GDPR-C05, CRA-C09, AI-C17/C18 | 3.000 | No |

### D-02: Vulnerability Management

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-02.1 | Vulnerability Identification | CRA-C01/C17, DORA-C08, AI-C03/C16 | 3.000 | No |
| D-02.2 | Patch Management & Updates | CRA-C04/C19, DORA-C13/C26 | 3.000 | No |
| D-02.3 | Coordinated Vuln. Disclosure | CRA-C21/C26 | 3.000 | **Yes (CRA)** |
| D-02.4 | Threat-Led Penetration Testing | DORA-C34, AI-C04 | 3.000 | No |

### D-03: Access Control

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-03.1 | Identity Lifecycle Management | CRA-C05, DORA-C15, NIS2-C19 | 3.000 | No |
| D-03.2 | Multi-Factor Authentication | CRA-C06, DORA-C16, NIS2-C21 | 3.000 | No |
| D-03.3 | Authorization & Least Privilege | GDPR-C10/C17, DORA-C14, NIS2-C20 | 3.000 | No |
| D-03.4 | Secure System Defaults | CRA-C03 | 3.000 | **Yes (CRA)** |

### D-04: Incident Response

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-04.1 | Incident Detection & Triage | CRA-C13, DORA-C21/C30, NIS2-C28/C29 | 3.000 | No |
| D-04.2 | Containment & Mitigation | GDPR-C18, CRA-C11, DORA-C22/C24, NIS2-C05 | 3.000 | No |
| D-04.3 | Regulatory Notification | GDPR-C21/C23, CRA-C25, DORA-C29/C31, NIS2-C25/C26/C27, AI-C26/C29 | 3.000 | No |
| D-04.4 | Data Restoration & Recovery | GDPR-C16, DORA-C23/C25, NIS2-C06/C07 | 3.000 | No |

### D-05: Data Lifecycle

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-05.1 | Data Minimization | GDPR-C01, CRA-C10, AI-C05/C06/C08 | 3.000 | No |
| D-05.2 | Retention & Archiving | GDPR-C02/C03, AI-C07 | 3.000 | No |
| D-05.3 | Right to Erasure | GDPR-C06, CRA-C16 | 3.000 | No |
| D-05.4 | Data Portability | GDPR-C07 | 3.000 | **Yes (GDPR)** |

### D-06: Supply Chain

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-06.1 | Vendor Risk Assessment | GDPR-C11, DORA-C35/C36, NIS2-C08/C23 | 3.000 | No |
| D-06.2 | Software Bill of Materials (SBOM) | CRA-C18 | 3.000 | **Yes (CRA)** |
| D-06.3 | Contractual Security Obligations | GDPR-C12, DORA-C37, NIS2-C09 | 3.000 | No |
| D-06.4 | Third-Party Boundary Management | DORA-C38, NIS2-C24 | 3.000 | No |

### D-07: Secure Development

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-07.1 | Secure-by-Design Principles | GDPR-C09, CRA-C02/C22, DORA-C18, NIS2-C10 | 3.000 | No |
| D-07.2 | Secure Coding Practices | DORA-C19 | 3.000 | **Yes (DORA)** |
| D-07.3 | CI/CD Pipeline Security | NIS2-C11 | 3.000 | **Yes (NIS 2)** |
| D-07.4 | Change Management | DORA-C06 | 3.000 | **Yes (DORA)** |

### D-08: Human Factors

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-08.1 | General Security Awareness | GDPR-C27, DORA-C27, NIS2-C14 | 3.000 | No |
| D-08.2 | Role-Specific Competence | GDPR-C28, DORA-C28, NIS2-C15, AI-C14/C15/C24 | 3.000 | No |
| D-08.3 | Management Board Training | DORA-C02, NIS2-C02 | 3.000 | No |

### D-09: Governance & Documentation

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-09.1 | Information Security Policies | GDPR-C08/C25/C26, CRA-C24, DORA-C01/C03, NIS2-C01/C03, AI-C12/C13/C20/C23 | 3.000 | No |
| D-09.2 | Impact & Risk Assessments | GDPR-C20/C24, CRA-C23, DORA-C04, NIS2-C04, AI-C01/C02/C22/C28 | 3.000 | No |
| D-09.3 | Asset Inventories | DORA-C05 | 3.000 | **Yes (DORA)** |
| D-09.4 | Records of Processing | GDPR-C13/C22, AI-C11 | 3.000 | No |

### D-10: Monitoring & Audit

| Sub-Domain ID | Sub-Domain Name | Regulatory Driver | Normative Intensity (Max) | Sole Authority? |
|---------------|-----------------|-------------------|---------------------------|-----------------|
| D-10.1 | Continuous Security Monitoring | CRA-C12, DORA-C07/C20, NIS2-C29, AI-C25 | 3.000 | No |
| D-10.2 | Audit Logging & Traceability | CRA-C14, DORA-C12, NIS2-C22, AI-C09/C10/C19 | 3.000 | No |
| D-10.3 | Compliance Testing | GDPR-C19, CRA-C20, DORA-C32/C33, NIS2-C13, AI-C21/C27 | 3.000 | No |

---

## 4. SOLE AUTHORITY SUMMARY

### 4.1 Global Sole Authority (All 5 Regulations)

| Sub-Domain | Sole Authority Regulation | Risk if Regulation Not Applicable |
|------------|---------------------------|-----------------------------------|
| D-02.3 | CRA | Zero regulatory mandate |
| D-03.4 | CRA | Zero regulatory mandate |
| D-05.4 | GDPR | Zero regulatory mandate |
| D-06.2 | CRA | Zero regulatory mandate |
| D-07.2 | DORA | Zero regulatory mandate |
| D-07.3 | NIS 2 | Zero regulatory mandate |
| D-07.4 | DORA | Zero regulatory mandate |
| D-09.3 | DORA | Zero regulatory mandate |

**Total:** 8/38 sub-domains (21.1%) have sole authority

### 4.2 TinyTask-Specific Sole Authority (GDPR + CRA Only)

Since TinyTask SaaS only has **GDPR** and **CRA** applicable, the sole authority gaps are:

| Sub-Domain | Sole Authority | TinyTask Status | Gap Risk |
|------------|----------------|-----------------|----------|
| D-02.3 | CRA | ✅ APPLICABLE | **COVERED** |
| D-03.4 | CRA | ✅ APPLICABLE | **COVERED** |
| D-05.4 | GDPR | ✅ APPLICABLE | **COVERED** |
| D-06.2 | CRA | ✅ APPLICABLE | **COVERED** |
| D-07.2 | DORA | ❌ NOT APPLICABLE | ⚠️ **GAP** (no mandate) |
| D-07.3 | NIS 2 | ❌ NOT APPLICABLE | ⚠️ **GAP** (no mandate) |
| D-07.4 | DORA | ❌ NOT APPLICABLE | ⚠️ **GAP** (no mandate) |
| D-09.3 | DORA | ❌ NOT APPLICABLE | ⚠️ **GAP** (no mandate) |

**TinyTask Coverage:** 4/8 sole authority sub-domains covered (50%)  
**TinyTask Gaps:** 4/8 sole authority sub-domains uncovered (D-07.2, D-07.3, D-07.4, D-09.3)

**Mitigation:** Level 2 frameworks (ISO 27001, NIST CSF) recommended for D-07 Secure Development domain.

---

## 5. NORMATIVE INTENSITY REFERENCE (T9)

### 5.1 Global Normative Intensity (All 5 Regulations)

| Regulation | Mean NI | Weight 3 % | Weight 2 % | Weight 1 % | Total Clauses |
|------------|---------|------------|------------|------------|---------------|
| DORA | 3.000 | 100.0% | 0.0% | 0.0% | 38 |
| CRA | 2.923 | 92.3% | 7.7% | 0.0% | 26 |
| NIS 2 | 2.862 | 89.7% | 10.3% | 0.0% | 29 |
| AI Act | 2.793 | 82.8% | 17.2% | 0.0% | 29 |
| GDPR | 2.714 | 71.4% | 28.6% | 0.0% | 28 |
| **COMBINED** | **2.858** | **88.0%** | **12.0%** | **0.0%** | **150** |

### 5.2 TinyTask-Specific Normative Intensity (GDPR + CRA Only)

| Regulation | Mean NI | Weight 3 % | Weight 2 % | Weight 1 % | Total Clauses | Sub-Domains Covered |
|------------|---------|------------|------------|------------|---------------|---------------------|
| **GDPR** | 2.714 | 71.4% | 28.6% | 0.0% | 28 | 19/38 (50.0%) |
| **CRA** | 2.923 | 92.3% | 7.7% | 0.0% | 26 | 22/38 (57.9%) |
| **TINYTASK COMBINED** | **2.778** | **81.5%** | **18.5%** | **0.0%** | **54** | **31/38 (81.6%)** |

**Key Insights for TinyTask:**
- Higher NI than global average (2.778 vs 2.858) due to DORA exclusion (100% W3)
- 81.5% of obligations are unconditional (Weight 3)
- CRA drives prescriptiveness (92.3% W3) vs GDPR flexibility (71.4% W3)

---

## 6. VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-01 | AEGIS Research Team | Initial release - TinyTask SaaS case |

---

## 7. DOCUMENT APPROVAL

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Document Author | AEGIS Research Team | | 2026-04-01 |
| AEGIS Methodology Review | | | |
| Technical Review (CTO) | | | |
| Business Review (CEO) | | | |

---

**Next Document:** 01_Company_Context.md  
**Dependency:** None (foundational reference)  
**Case Study:** TinyTask SaaS (Low Complexity)
