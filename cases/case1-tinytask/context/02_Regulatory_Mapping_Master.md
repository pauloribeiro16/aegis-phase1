---
document_id: AEGIS-COMMON-02
title: Regulatory Mapping Master
version: 1.0
created: 2026-04-01
updated: 2026-04-01
author: Compliance Lead
status: DRAFT
traceability: Regulatory_Complementary_Mapping_Updated.txt
inputs: [00_Taxonomy_Reference.md, 01_Company_Context.md]
outputs: [04_Company_Context_Assessment.md, 05_Regulatory_Applicability.md, 06_Clause_Mapping_Matrix.xlsx]
related_documents: [00_Taxonomy_Reference.md, 01_Company_Context.md]
---

# Regulatory Mapping Master

## 1. DOCUMENT PURPOSE

This document specifies the Excel-based Regulatory Mapping Master (T1-T5), consolidating regulatory clause mapping across all 5 EU regulations (GDPR, CRA, NIS 2, DORA, AI Act) with T6-T9 metrics.

**Phase 1 Step:** B (Regulatory Mapping)

**Gate Criteria:**
- ✅ All applicable regulations mapped to 10×38 taxonomy
- ✅ Normative Intensity calculated per clause
- ✅ Sole Authority analysis complete

---

## 2. EXCEL FILE LOCATION
================================================================================
File: 06_Clause_Mapping_Matrix.xlsx
Path: `02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`
Created: 2026-04-01
Sheets: 7 (COVER, GDPR_MAPPING, CRA_MAPPING, CONSOLIDATED_VIEW, COMPLEMENTARITY_ANALYSIS, APPLICABILITY_CONDITIONS, NORMATIVE_INTENSITY)

TINYTASK APPLICABILITY CONTEXT
================================================================================
| Regulation | Applicable? | obligatedParty | Clause Count | Sub-Domains Covered |
|------------|-------------|----------------|--------------|---------------------|
| GDPR | YES | CONTROLLER | 28 | 19/38 (50.0%) |
| CRA | YES | MANUFACTURER | 26 | 22/38 (57.9%) |
| NIS 2 | NO | N/A | 0 | 0/38 |
| DORA | NO | N/A | 0 | 0/38 |
| AI Act | NO | N/A | 0 | 0/38 |
| **TOTAL** | **2/5** | **—** | **54** | **31/38 (81.6%)** |

SHEET STRUCTURE (7 Sheets)
================================================================================

SHEET 1: COVER
--------------------------------------------------------------------------------
| Field | Value |
|-------|-------|
| Document ID | AEGIS-COMMON-02 |
| Title | Regulatory Mapping Master |
| Version | 1.0 |
| Created | 2026-04-01 |
| Author | Compliance Lead |
| Source | Regulatory_Complementary_Mapping_Updated.txt (T1-T5) |
| Case Study | TinyTask Lda. |
| Applicable Regulations | GDPR, CRA |

SHEET 2: GDPR_MAPPING (T1)
--------------------------------------------------------------------------------
Columns:
| Clause ID | Article | Sub-Domain ID | Sub-Domain Name | Description |
| obligatedParty | obligationType | Normative Weight | Justification |
| TinyTask Relevance | Company Context Reference |

Data Validation:
- Sub-Domain ID: Dropdown (D-01.1 to D-10.3 from 00_Taxonomy_Reference.md)
- obligatedParty: CONTROLLER
- obligationType: CONTINUOUS, PERIODIC, ONE_TIME, TRIGGERED
- Normative Weight: 1, 2, 3 (per T9)

Summary Row:
| Total Clauses | Weight 3 Count | Weight 2 Count | Mean NI | Sub-Domains Covered |

SHEET 3: CRA_MAPPING (T2)
--------------------------------------------------------------------------------
Columns:
| Clause ID | Article/Annex | Sub-Domain ID | Sub-Domain Name | Description |
| obligatedParty | obligationType | Normative Weight | Justification |
| TinyTask Relevance | Company Context Reference |

Data Validation:
- obligatedParty: MANUFACTURER
- obligationType: CONTINUOUS, PERIODIC, ONE_TIME, TRIGGERED
- Normative Weight: 1, 2, 3 (per T9)

Summary Row:
| Total Clauses | Weight 3 Count | Weight 2 Count | Mean NI | Sub-Domains Covered |

SHEET 4: NIS2_MAPPING (T3)
--------------------------------------------------------------------------------
Columns:
| Clause ID | Article | Sub-Domain ID | Sub-Domain Name | Description |
| obligatedParty | obligationType | Normative Weight | Justification |
| TinyTask Relevance | Company Context Reference |

Data Validation:
- obligatedParty: ESSENTIAL_OR_IMPORTANT_ENTITY
- obligationType: CONTINUOUS, PERIODIC, TRIGGERED (NIS 2 has 0% ONE_TIME)

Summary Row:
| Total Clauses | Weight 3 Count | Weight 2 Count | Mean NI | Sub-Domains Covered |

SHEET 5: DORA_MAPPING (T4)
--------------------------------------------------------------------------------
Columns:
| Clause ID | Article | Sub-Domain ID | Sub-Domain Name | Description |
| obligatedParty | obligationType | Normative Weight | Justification |
| TinyTask Relevance | Company Context Reference |

Data Validation:
- obligatedParty: FINANCIAL_ENTITY
- Normative Weight: All 3 (DORA is 100% Weight 3)

Summary Row:
| Total Clauses | Weight 3 Count | Weight 2 Count | Mean NI | Sub-Domains Covered |

SHEET 6: AIACT_MAPPING (T5)
--------------------------------------------------------------------------------
Columns:
| Clause ID | Article | Sub-Domain ID | Sub-Domain Name | Description |
| obligatedParty | obligationType | Normative Weight | Justification |
| TinyTask Relevance | Company Context Reference |

Data Validation:
- obligatedParty: PROVIDER, DEPLOYER
- obligationType: CONTINUOUS, PERIODIC, ONE_TIME, TRIGGERED

Summary Row:
| Total Clauses | Weight 3 Count | Weight 2 Count | Mean NI | Sub-Domains Covered |

SHEET 7: CONSOLIDATED_VIEW (T6 + T9)
--------------------------------------------------------------------------------
Pivot Table View:

| Sub-Domain ID | Sub-Domain Name | GDPR | CRA | NIS 2 | DORA | AI Act |
| Total Clauses | Combined NI | Sole Authority? | Coverage Level |

Formulas:
- Combined NI: AVERAGE of applicable regulation NI for this sub-domain
- Sole Authority?: IF(COUNTA(GDPR:CRA:NIS2:DORA:AIACT)=1, "Yes", "No")
- Coverage Level: IF(Total Clauses >= 2, "SUBSTANTIVE", IF(Total Clauses = 1, "PARTIAL", "NOT_ADDRESSED"))

Summary Dashboard:
| Metric | Value | Formula |
|--------|-------|---------|
| Total Sub-Domains | 38 | Fixed |
| Covered Sub-Domains | =COUNTIF(Coverage Level, "<>NOT_ADDRESSED") | |
| Coverage % | =Covered/38 | |
| Total Clauses (All Regulations) | =SUM(GDPR:CRA:NIS2:DORA:AIACT) | |
| Average Normative Intensity | =AVERAGE(Combined NI) | |
| Sole Authority Gaps | =COUNTIF(Sole Authority?, "Yes") | |

================================================================================
AUTOMATED CALCULATIONS
================================================================================

1. Normative Intensity per Regulation:
   =AVERAGEIF(Normative Weight Range, ">0")

2. Weight 3 Percentage:
   =COUNTIF(Normative Weight Range, 3) / COUNTA(Normative Weight Range)

3. Sub-Domain Coverage per Regulation:
   =COUNTA(UNIQUE(Sub-Domain ID Range)) / 38

4. Cross-Regulation Overlap (Shared Scope):
   =COUNTIF(AND(GDPR<>"", CRA<>""), 1) / COUNTIF(OR(GDPR<>"", CRA<>""), 1)

================================================================================
VERSION HISTORY
================================================================================
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-01 | AEGIS Research Team | Initial release - TinyTask SaaS case |

================================================================================
DOCUMENT APPROVAL
================================================================================
| Role | Name | Signature | Date |
|------|------|-----------|------|
| Document Author | AEGIS Research Team | | 2026-04-01 |
| Technical Review | | | |
| AEGIS Methodology Review | | | |

================================================================================
TINYTASK METRICS SUMMARY (from 06_Clause_Mapping_Matrix.xlsx)
================================================================================

**Shared Scope (Jaccard Index):** 0.367 (36.7%)  
**Complementarity Index:** 0.633 (63.3%)  
**Overlap:** 11 sub-domains covered by both GDPR and CRA  
**Strategic Tensions:** 1 (D-04.3: 72h GDPR vs 24h CRA)

**Normative Intensity:**
- GDPR Mean NI: 2.714 (71.4% Weight 3)
- CRA Mean NI: 2.923 (92.3% Weight 3)
- Combined Mean NI: 2.778 (81.5% Weight 3)

**Coverage:**
- Total Sub-Domains: 38
- Covered: 31 (81.6%)
- Not Covered: 7 (D-02.4, D-06.4, D-07.2, D-07.3, D-07.4, D-08.3, D-09.3)
- Sole Authority Gaps: 4 (D-07.2, D-07.3, D-07.4, D-09.3 — all DORA/NIS 2 exclusive)

---

## 11. VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-01 | Compliance Lead | Initial regulatory mapping master specification |
