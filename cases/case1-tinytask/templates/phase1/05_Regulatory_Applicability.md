---
document_id: AEGIS-P1-05
title: Regulatory Applicability Assessment
phase: 1
version: 1.0
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: Compliance Lead
status: DRAFT
inputs: [04_Company_Context_Assessment.md]
outputs: [06_Clause_Mapping_Matrix.xlsx]
traceability: AEGIS Class Model → ComplianceContext, RegulatoryClause, ConditionalExtension, RegulatoryInteraction classes
related_documents: [00_Taxonomy_Reference.md, 04_Company_Context_Assessment.md]
---

# Regulatory Applicability Assessment

## 1. DOCUMENT PURPOSE

This document consolidates the regulatory applicability assessment (Step B1+B3), determining which regulations apply to the company context and establishing the Native vs. Inherited compliance boundaries.

**Alignment with Class Model:**
- `ComplianceContext` - Applicable regulations and applicability scores
- `RegulatoryClause` - Filtered clauses based on applicability
- `DomainCoverageEntry` - Initial domain coverage assessment

**Phase 1 Step:** B (Regulatory Applicability)

**Gate Criteria:** Clear applicability determination for all 5 regulations with documented rationale

---

## 2. APPLICABILITY ASSESSMENT METADATA

| Attribute | Value |
|-----------|-------|
| complianceContextId | [compliance_context_id] |
| assessmentDate | YYYY-MM-DD |
| basedOnCompanyContext | [company_context_id] |
| assessedBy | Compliance Lead |
| reviewedBy | Legal Counsel (pending) |

---

## 3. REGULATION-BY-REGULATION APPLICABILITY ANALYSIS

### 3.1 GDPR (General Data Protection Regulation)

| Criterion | Company Context Value | Threshold | Met? |
|-----------|----------------------|-----------|------|
| processes_personal_data | [gdpr_processes_personal_data] | ANY | [gdpr_process_met] |
| EU data subjects | [gdpr_eu_data_subjects] | ANY | [gdpr_eu_met] |
| Special category data | [gdpr_special_category] | ANY | N/A |

**Applicability Result:** [gdpr_applicability_text]

**Rationale:** [gdpr_rationale]

**Obligated Party:** [gdpr_obligated_party]

**Multi-Actor Note:** [gdpr_multi_actor_note]

**Key Clauses in Scope:** [gdpr_key_clauses]

**Nuance:** [gdpr_nuance]

---

### 3.2 CRA (Cyber Resilience Act)

| Criterion | Company Context Value | Threshold | Met? |
|-----------|----------------------|-----------|------|
| places_digital_products_eu | [cra_places_products_eu] | TRUE | [cra_places_met] |
| Digital element | [cra_digital_element] | YES/NO | [cra_digital_met] |
| Manufacturer status | [cra_manufacturer_status] | YES/NO | [cra_manufacturer_met] |

**Applicability Result:** [cra_applicability_text]

**Rationale:** [cra_rationale]

**Key Clauses in Scope:** [cra_key_clauses]

**Quantitative Thresholds:** [cra_quantitative_thresholds]

---

### 3.3 NIS 2 (Network and Information Systems Directive)

| Criterion | Company Context Value | Threshold | Met? |
|-----------|----------------------|-----------|------|
| nis2_sector | [nis2_sector] | Essential/Important | [nis2_sector_met] |
| size (employees) | [nis2_employees] | ≥50 (medium) / ≥250 (large) | [nis2_employees_met] |
| size (revenue) | [nis2_revenue] | ≥€10M / ≥€50M | [nis2_revenue_met] |
| Critical entity status | [nis2_critical_status] | YES/NO | [nis2_critical_met] |

**Applicability Result:** [nis2_applicability_text]

**Rationale:** [nis2_rationale]

**Key Clauses in Scope:** N/A

---

### 3.4 DORA (Digital Operational Resilience Act)

| Criterion | Company Context Value | Threshold | Met? |
|-----------|----------------------|-----------|------|
| dora_financial_entity | [dora_financial_entity] | TRUE | [dora_financial_met] |
| Financial sector classification | [dora_financial_classification] | Credit institution, Investment firm, etc. | [dora_classification_met] |
| ICT third-party provider | [dora_ict_provider] | YES/NO | [dora_ict_met] |

**Applicability Result:** [dora_applicability_text]

**Rationale:** [dora_rationale]

**Key Clauses in Scope:** N/A

---

### 3.5 AI Act (Artificial Intelligence Regulation)

| Criterion | Company Context Value | Threshold | Met? |
|-----------|----------------------|-----------|------|
| aiact_high_risk_system | [aiact_high_risk_system] | TRUE | [aiact_high_risk_met] |
| AI system provider | [aiact_provider_status] | YES/NO | [aiact_provider_met] |
| AI system deployer | [aiact_deployer_status] | YES/NO | [aiact_deployer_met] |
| High-risk use case | [aiact_high_risk_use_case] | Annex III listing | [aiact_use_case_met] |

**Applicability Result:** [aiact_applicability_text]

**Rationale:** [aiact_rationale]

**Key Clauses in Scope:** N/A

---

## 4. APPLICABILITY MATRIX SUMMARY

| Regulation | Applicable? | Confidence | Key Driver | Exclusion Reason (if applicable) |
|------------|-------------|------------|------------|----------------------------------|
| GDPR | [gdpr_summary_applicable] | [gdpr_summary_confidence] | [gdpr_summary_driver] | [gdpr_summary_exclusion] |
| CRA | [cra_summary_applicable] | [cra_summary_confidence] | [cra_summary_driver] | [cra_summary_exclusion] |
| NIS 2 | [nis2_summary_applicable] | [nis2_summary_confidence] | [nis2_summary_driver] | [nis2_summary_exclusion] |
| DORA | [dora_summary_applicable] | [dora_summary_confidence] | [dora_summary_driver] | [dora_summary_exclusion] |
| AI Act | [aiact_summary_applicable] | [aiact_summary_confidence] | [aiact_summary_driver] | [aiact_summary_exclusion] |

---

## 5. NATIVE VS. INHERITED COMPLIANCE

### 5.1 Native Compliance Requirements

Compliance obligations that [company_name] must implement directly:

| Regulation | Domain | Obligation | Actor Capacity | Implementation Responsibility |
|------------|--------|------------|----------------|-------------------------------|
| [native_reg_1] | [native_domain_1] | [native_obligation_1] | [native_actor_1] | [native_responsibility_1] |
| [additional_native] |

### 5.2 Inherited Compliance Requirements

Compliance obligations inherited from suppliers/partners:

| Regulation | Domain | Obligation | Source (Supplier/Partner) | Evidence Required |
|------------|--------|------------|---------------------------|-------------------|
| [inherited_reg_1] | [inherited_domain_1] | [inherited_obligation_1] | [inherited_source_1] | [inherited_evidence_1] |
| [additional_inherited] |

### 5.3 Compliance Boundary Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    [COMPANY_NAME] BOUNDARY                    │
│                                                              │
│   ┌─────────────────┐         ┌─────────────────┐           │
│   │  NATIVE         │         │  INHERITED      │           │
│   │  Compliance     │         │  Compliance     │           │
│   │  (Direct)       │         │  (Via contracts)│           │
│   │                 │         │                 │           │
│   │ • [native_1]   │         │ • [inherited_1] │           │
│   │ • [native_2]   │         │ • [inherited_2] │           │
│   └─────────────────┘         └─────────────────┘           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         ▲                               ▲
         │                               │
    Direct implementation          Supplier/Partner
    within [company_name]          compliance evidence
```

---

## 6. SUB-DOMAIN COVERAGE PRELIMINARY ASSESSMENT

Based on applicable regulations ([applicable_regulations_list]):

| Sub-Domain ID | Sub-Domain Name | [reg_1] | [reg_2] | Total | Coverage Level |
|---------------|-----------------|---------|---------|-------|----------------|
| [sd_1_id] | [sd_1_name] | [sd_1_reg_1] | [sd_1_reg_2] | [sd_1_total] | [sd_1_level] |
| [additional_subdomains] |

**Coverage Summary:**
- Substantive Coverage (≥2 regulations): [substantive_count] sub-domains
- Partial Coverage (1 regulation): [partial_count] sub-domains
- No Coverage (0 regulations): [not_addressed_count] sub-domains ([non_applicable_regs] exclusive)

---

## 7. STRATEGIC IMPLICATIONS

| Implication ID | Source Regulation | Description | Impact on Architecture | Priority |
|----------------|-------------------|-------------|------------------------|----------|
| SI-001 | [si_1_regulation] | [si_1_description] | [si_1_impact] | [si_1_priority] |
| [additional_implications] |

---

## 8. REGULATORY GAPS IDENTIFIED

| Gap ID | Regulation | Clause | Sub-Domain | Gap Description | Risk Level |
|--------|------------|--------|------------|-----------------|------------|
| GAP-001 | [gap_1_regulation] | [gap_1_clause] | [gap_1_subdomain] | [gap_1_description] | [gap_1_risk] |
| [additional_gaps] |

---

## 9. VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | YYYY-MM-DD | Compliance Lead | Initial template release |

---

## 10. DOCUMENT APPROVAL

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Document Author | Compliance Lead | | YYYY-MM-DD |
| Legal Counsel Review | | | |
| Technical Review (CTO) | | | |
| AEGIS Methodology Review | | | |

---

**Next Document:** 06_Clause_Mapping_Matrix.xlsx
**Gate Status:** [PENDING / PASS / FAIL]
