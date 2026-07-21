---
document_id: AEGIS-P1-04c
title: Third-Party Landscape Inventory
version: 1.0
status: DRAFT
generated_at: "2026-07-14T11:03:01Z"
phase: 1
created: "2026-07-14T11:03:01Z"
updated: "2026-07-14T11:03:01Z"
author: Executor
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, 04a_Architecture_DataInventory.md, ../00_COMMON/01_Company_Context.md]
outputs: [04b_Security_Posture.md, 06_Clause_Mapping_Matrix.md, 07_Structured_Compliance_Matrix.md]
applicable_regs: [GDPR, CRA]
active_subdomains: 31
related_documents: [../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-06_Supply-Chain/, ../../../00_METHODOLOGY/TEMPLATES/04c_ThirdParty_Landscape.md]
supersedes: none
---
# Third-Party Landscape Inventory

## 1. Purpose & Scope

This document inventories TinyTask Lda.'s third-party landscape: cloud providers, software vendors, subprocessors. It maps directly to Layer 0 sub-domain **D-06 (Supply Chain)** — D-06.1, D-06.2, D-06.3, D-06.4 — and supports compliance with **GDPR Art. 28** (processor obligations and controller due diligence) and **CRA Annex I Part I (2)(j) and (k)** (attack-surface reduction, exploitation-mitigation via the supply chain).

**Scope:** Sub-domain D-06.x only. Broader architecture context is in `04a_Architecture_DataInventory.md`; broader governance (policies, risk assessments) is in `04b_Security_Posture.md` and Phase 2 deliverables.

**Method:** Inventory was constructed from the architecture documentation (`04a`), the stakeholder register in `04_Company_Context_Assessment.md §3`, and the ontology's `overlaps` block (cross-regulation shared sub-domains).

**Proportionality note (P2 — Company Reality First):** TinyTask Lda. is a SaaS with 8 employees. Inventory is limited to the third parties that actually touch personal data or the production system. No formal supplier programme exists; the inventory is a precondition to building one, not evidence one already exists.

## 2. Inherited Infrastructure

The following providers host customer data, the production application, or authentication. They are listed in order as they appear in the architecture inventory (provider + service).

| Provider | Service | Data Stored | Region | DPA in Place? | Subprocessor? |
| --- | --- | --- | --- | --- | --- |
| AWS or equivalent EU cloud provider | PostgreSQL managed database | Customer accounts, project metadata, B2B project content | eu-west-1 or equivalent EU region | Y | Y |
| AWS or equivalent EU cloud provider | S3-compatible object storage | Encrypted database backups | eu-west-1 or equivalent EU region | Y | Y |
| AWS or equivalent EU cloud provider | Cloud KMS | Encryption keys and key metadata | EU region | Y | Y |
| Auth0 | Authentication and identity | Email identifiers, authentication metadata, session metadata | EU tenant where available | Y | Y |
| Stripe | Payment processing | Card/payment data, billing contact metadata | Stripe controlled processing locations | Y | Y |
| Datadog or equivalent | Logs and analytics | Pseudonymised event logs and operational metrics | EU site where available | Y | Y |

**Summary:** 6 inherited infrastructure entries recorded. DPA status follows the architecture inventory values.

## 3. Overlap-Implied Third Parties

| Reg Pair | Shared Sub-domains | Note |
| --- | --- | --- |
| GDPR+CRA | D-01.1, D-01.2, D-04.2, D-04.3, D-05.3, D-07.1, D-10.3 | GDPR and CRA share significant coverage in data protection, incident response, and secure development domains |
| GDPR+NIS2 | - | - |
| CRA+NIS2 | - | - |

## 4. Contractual Controls

| Provider / Service | DPA in Place? | Art. 28 Compliant? | Audit Reports Substituted? | Subprocessor Approval Flow? |
| --- | --- | --- | --- | --- |
| AWS or equivalent EU cloud provider — PostgreSQL managed database | Y | Y | Indirect — vendor SOC 2 / ISO 27001 substituted | Y — vendor publishes subprocessor list |
| AWS or equivalent EU cloud provider — S3-compatible object storage | Y | Y | Indirect — vendor SOC 2 / ISO 27001 substituted | Y — vendor publishes subprocessor list |
| AWS or equivalent EU cloud provider — Cloud KMS | Y | Y | Indirect — vendor SOC 2 / ISO 27001 substituted | Y — vendor publishes subprocessor list |
| Auth0 — Authentication and identity | Y | Y | Indirect — vendor SOC 2 / ISO 27001 substituted | Y — vendor publishes subprocessor list |
| Stripe — Payment processing | Y | Y | Indirect — vendor SOC 2 / ISO 27001 substituted | Y — vendor publishes subprocessor list |
| Datadog or equivalent — Logs and analytics | Y | Y | Indirect — vendor SOC 2 / ISO 27001 substituted | Y — vendor publishes subprocessor list |

**Common pattern:** Providers substitute third-party certifications (SOC 2 / ISO 27001) for direct audit access. This is industry-standard for low-tier SaaS and requires annual freshness review.

## 5. Supply Chain Risk Assessment

Risk score key: **VH** = Very High, **H** = High, **M** = Medium, **L** = Low. Criticality reflects **business impact of vendor failure or incident**. Risk score reflects **likelihood × impact** given the current maturity (no formal supplier programme; reliance on third-party certifications).

| Provider / Service | Criticality | Risk Score | Last Assessment | SBOM Available? | Next Review |
| --- | --- | --- | --- | --- | --- |
| AWS or equivalent EU cloud provider — PostgreSQL managed database | Critical | L | 2026-04 — informal review during intake | N/A (managed service) | 2027-04 (annual review; first formal review planned) |
| AWS or equivalent EU cloud provider — S3-compatible object storage | Critical | M | 2026-04 — informal review during intake | N/A (managed service) | 2027-04 (annual review; first formal review planned) |
| AWS or equivalent EU cloud provider — Cloud KMS | Important | L | 2026-04 — informal review during intake | N/A (managed service) | 2027-04 (annual review; first formal review planned) |
| Auth0 — Authentication and identity | Critical | M | 2026-04 — informal review during intake | N/A (managed service) | 2027-04 (annual review; first formal review planned) |
| Stripe — Payment processing | Critical | M | 2026-04 — informal review during intake | N/A (managed service) | 2027-04 (annual review; first formal review planned) |
| Datadog or equivalent — Logs and analytics | Critical | M | 2026-04 — informal review during intake | N/A | 2027-04 (annual review; first formal review planned) |

**Vendor count:** 6 (deduplicated by provider+service). No Critical+High combinations expected for a low-tier SaaS that uses managed cloud services exclusively.

### 5.1 Concentration Risk Narrative

TinyTask Lda. runs all production workloads on managed cloud providers; 6 providers are inventoried, of which 5 are marked Critical. The dominant concentration point is the identity and authentication provider (sole login / MFA dependency) followed by the cloud platform and payment processor. Under GDPR Art. 28 the controller remains accountable for subprocessor selection; under CRA Annex I Part I (2)(j) and (k) the supply chain is part of the attack surface and must be tracked. Concentration risk is manageable under the proportionality tier but is documented here so it propagates to Phase 2 (4 medium-risk vendors flagged for annual review).

## 6. Compliance Mapping (Layer 0)

Active scope = 31 of 38 sub-domains for applicable_regs = [GDPR, CRA]. The four rows below cover the D-06 (Supply Chain) sub-domains within that active set.

| Sub-domain | Vendors Affected | Compliance Status | Notes |
| --- | --- | --- | --- |
| D-06.1 Vendor Risk Assessment | All inherited providers (see §2) | Partial — inventory complete, risk scores assigned, but no formal review cadence | Action: schedule annual review; tracked in 04b_Security_Posture.md. |
| D-06.2 Software Bill of Materials (SBOM) | Snyk / GitHub (where present) | Partial — tooling may exist; pipeline integration not yet asserted | Action: integrate SBOM export into CI/CD by Phase 2; required for CRA Annex I Part II (1). |
| D-06.3 Contractual Security Obligations | All inherited providers (see §2) | Covered for GDPR Art. 28 (DPAs in place); partial for CRA supply-chain clauses | — |
| D-06.4 Third-Party Boundary Management | Providers with data-egress paths | Covered — TLS + DPA + subprocessor approval flow | — |

## 7. Gaps & Known Limitations

These items are deliberately surfaced so they can flow into `04b_Security_Posture.md` and Phase 2 remediation plans, rather than being silently accepted.

| Gap ID | Description | Severity | Linked Sub-Domain |
| --- | --- | --- | --- |
| GAP-TPL-01 | No formal supplier-security-assessment questionnaire (e.g. SIG / CAIQ) sent to vendors; reliance on inherited certifications only | MEDIUM | D-06.1 |
| GAP-TPL-02 | No documented exit plan for cloud-hosted data extraction | MEDIUM | D-06.4 |
| GAP-TPL-03 | No pipeline-integrated SBOM generation | HIGH (CRA-mandated) | D-06.2 |
| GAP-TPL-04 | No annual review cycle enforced; next-review target is aspirational | MEDIUM | D-06.1, D-06.3 |

All gaps are tracked in `04b_Security_Posture.md` for Phase 2 prioritisation.

## 8. Gate

| Gate Criterion | Status | Evidence |
| --- | --- | --- |
| All cloud providers documented with DPA status | PASS | Section 2: 6 rows |
| Overlap-implied third parties identified | PASS | Section 3 from ontology.overlaps |
| Contractual coverage matrix populated | PASS | Section 4 |
| Risk classification table populated | PASS | Section 5 |
| Compliance Mapping table populated for D-06.x | PASS | Section 6 |
| Gaps explicitly listed (not silently accepted) | PASS | Section 7 |

**Gate Status:** PASS (proportionate for LOW-tier micro SaaS under P2).

## N-1. Version History

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 1.0 | 2026-07-14 | Executor | Generated from state[architecture_inventory].cloud_services and ontology.overlaps |

## N. Document Approval

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Document Author | Executor |  | 2026-07-14 |
| Technical Review | CTO |  |  |
| AEGIS Methodology Review | Validator |  |  |

## See also

- **Data backbone:** `Case_01_Phase1.xlsx` (13 sheets: COVER, SYSTEMS, DATA_STORES, DATA_FLOWS, PERSONAL_DATA, THIRD_PARTIES, ROLES_RACI, MATURITY, SUBDOMAINS, REG_CHAIN, COMPLIANCE, GAPS, PRIORITIES)
