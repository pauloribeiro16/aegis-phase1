---
document_id: AEGIS-P1-06
title: Clause Mapping Matrix
phase: 1
version: 1.0
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: Compliance Lead
status: DRAFT
inputs: [04_Company_Context_Assessment.md, 05_Regulatory_Applicability.md]
outputs: [07_Structured_Compliance_Matrix.md]
traceability: AEGIS Class Model → RegulatoryClause (full), DomainCoverageEntry classes
related_documents: [00_Taxonomy_Reference.md, 05_Regulatory_Applicability.md]
---

# Clause Mapping Matrix

## 1. DOCUMENT PURPOSE

This document specifies the Excel-based Clause Mapping Matrix (Step B2), mapping regulatory clauses to the 10×38 taxonomy with Normative Intensity and gap analysis.

**Note:** The actual matrix is maintained in Excel format (`06_Clause_Mapping_Matrix.xlsx`). This document provides the specification and summary.

**Phase 1 Step:** B (Clause Mapping)

**Gate Criteria:** All applicable clauses mapped to sub-domains with Normative Intensity scores

---

## 2. EXCEL STRUCTURE (7 Sheets)

### Sheet 1: COVER

| Field | Value |
|-------|-------|
| Document ID | AEGIS-P1-06 |
| Title | Clause Mapping Matrix - [company_name] |
| Version | 1.0 |
| Created | YYYY-MM-DD |
| Author | Compliance Lead |
| Applicable Regulations | [applicable_regulations_list] |

### Sheet 2: GDPR_MAPPING (T1)

**Columns:** Clause ID | Article | Sub-Domain ID | Sub-Domain Name | Description | obligatedParty | obligationType | Normative Weight | Justification | [company_name] Relevance | normativeStrength | isAtomic | parentClauseId | sanctionReference

**Summary for [company_name]:**

| Metric | Value |
|--------|-------|
| Total GDPR Clauses | [gdpr_total_clauses] |
| Applicable to [company_name] | [gdpr_applicable_clauses] |
| Weight 3 (Mandatory) | [gdpr_weight_3_count] ([gdpr_weight_3_pct]%) |
| Weight 2 (Recommended) | [gdpr_weight_2_count] ([gdpr_weight_2_pct]%) |
| Mean NI | [gdpr_mean_ni] |

### Sheet 3: CRA_MAPPING (T2)

**Columns:** Clause ID | Article/Annex | Sub-Domain ID | Sub-Domain Name | Description | obligatedParty | obligationType | Normative Weight | Justification | [company_name] Relevance | normativeStrength | isAtomic | parentClauseId | sanctionReference

**Summary for [company_name]:**

| Metric | Value |
|--------|-------|
| Total CRA Clauses | [cra_total_clauses] |
| Applicable to [company_name] | [cra_applicable_clauses] |
| Weight 3 (Mandatory) | [cra_weight_3_count] ([cra_weight_3_pct]%) |
| Weight 2 (Recommended) | [cra_weight_2_count] ([cra_weight_2_pct]%) |
| Mean NI | [cra_mean_ni] |

### Sheets 4-6: NIS2, DORA, AIACT

**Status:** Not applicable for [company_name] (see 05_Regulatory_Applicability.md)

### Sheet 7: CONSOLIDATED_VIEW (T6 + T9)

**Pivot Table:** Sub-Domain coverage across applicable regulations

### Sheet 8: DOMAIN_COVERAGE

**Columns:** regulationId | subDomainId | coverageLevel | clauseCount | granularityLevel | obligatedPartyDist | obligationTypeDist

**Purpose:** Per-regulation, per-subdomain coverage summary. Each row represents the coverage depth of one regulation in one sub-domain.

| Field | Description |
|-------|-------------|
| regulationId | Regulation identifier (e.g., GDPR, CRA) |
| subDomainId | Sub-domain identifier (e.g., D-01.1) |
| coverageLevel | COMPREHENSIVE / PARTIAL / MINIMAL / NOT_ADDRESSED |
| clauseCount | Number of clauses mapped to this sub-domain |
| granularityLevel | CLAUSE / ARTICLE / ANNEX / SECTION |
| obligatedPartyDist | Distribution of obligated parties (e.g., CONTROLLER:80%,PROCESSOR:20%) |
| obligationTypeDist | Distribution of obligation types (e.g., CONTINUOUS:60%,TRIGGERED:40%) |

---

## 3. CLAUSE-TO-SUB-DOMAIN MAPPING SUMMARY

### GDPR Mapping ([gdpr_total_clauses] clauses → 10×38 taxonomy)

| Sub-Domain | Clause Count | Clauses |
|------------|--------------|---------|
| D-01 (Encryption) | [gdpr_d01_count] | [gdpr_d01_clauses] |
| D-03 (Access Control) | [gdpr_d03_count] | [gdpr_d03_clauses] |
| D-04 (Incident Response) | [gdpr_d04_count] | [gdpr_d04_clauses] |
| D-05 (Data Lifecycle) | [gdpr_d05_count] | [gdpr_d05_clauses] |
| D-09 (Governance) | [gdpr_d09_count] | [gdpr_d09_clauses] |
| D-10 (Monitoring) | [gdpr_d10_count] | [gdpr_d10_clauses] |

### CRA Mapping ([cra_total_clauses] clauses → 10×38 taxonomy)

| Sub-Domain | Clause Count | Clauses |
|------------|--------------|---------|
| D-01 (Encryption) | [cra_d01_count] | [cra_d01_clauses] |
| D-02 (Vuln Management) | [cra_d02_count] | [cra_d02_clauses] |
| D-03 (Access Control) | [cra_d03_count] | [cra_d03_clauses] |
| D-06 (Supply Chain) | [cra_d06_count] | [cra_d06_clauses] |
| D-07 (Secure Development) | [cra_d07_count] | [cra_d07_clauses] |

---

## 4. GAP ANALYSIS SUMMARY

| Gap ID | Sub-Domain | Regulation | Clause | Gap Description | Risk Level |
|--------|------------|------------|--------|-----------------|------------|
| GAP-001 | [gap_1_subdomain] | [gap_1_regulation] | [gap_1_clause] | [gap_1_description] | [gap_1_risk] |
| [additional_gaps] |

---

## 5. NORMATIVE INTENSITY SUMMARY (T9)

| Regulation | Mean NI | Weight 3 % | Weight 2 % | Weight 1 % |
|------------|---------|------------|------------|------------|
| GDPR | [gdpr_mean_ni] | [gdpr_weight_3_pct]% | [gdpr_weight_2_pct]% | [gdpr_weight_1_pct]% |
| CRA | [cra_mean_ni] | [cra_weight_3_pct]% | [cra_weight_2_pct]% | [cra_weight_1_pct]% |
| **COMBINED ([company_name])** | **[combined_mean_ni]** | **[combined_weight_3_pct]%** | **[combined_weight_2_pct]%** | **[combined_weight_1_pct]%** |

---

## 6. VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | YYYY-MM-DD | Compliance Lead | Initial template release |

---

## 7. DOCUMENT APPROVAL

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Document Author | Compliance Lead | | YYYY-MM-DD |
| Technical Review | | | |
| AEGIS Methodology Review | | | |

---

**Next Document:** 07_Structured_Compliance_Matrix.md
**Gate Status:** [PENDING / PASS / FAIL]
