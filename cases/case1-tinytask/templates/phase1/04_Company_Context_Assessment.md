---
document_id: AEGIS-P1-04
title: Company Context Assessment
phase: 1
version: 1.0
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: Compliance Lead
status: DRAFT
inputs: [01_Company_Context.md]
outputs: [05_Regulatory_Applicability.md]
traceability: AEGIS Class Model -> Stakeholder, BusinessGoal, CompanyContext, ComplianceContext, ComplexityTier, ConditionalExtension, RegulatoryInteraction classes
related_documents: [00_Taxonomy_Reference.md, 01_Company_Context.md]
---

# Company Context Assessment

## 1. DOCUMENT PURPOSE

This document consolidates the company context assessment (Step A1+A2+A3) including stakeholder analysis, business goals, and intake form responses. This is the primary input for regulatory applicability assessment.

**Alignment with Class Model:**
- `CompanyContext` - Instantiated from AEGIS Intake Form v2.0 (layered format)
- `ComplianceContext` - Derived regulatory applicability flags
- `Stakeholder` - Organizational roles and responsibilities
- `BusinessGoal` - Strategic objectives

**Phase 1 Step:** A (Company Context Assessment)

**Gate Criteria:** Intake form complete; regulatory applicability determined

---

## 2. ASSESSMENT SUMMARY

| Field | Value |
|-------|-------|
| Assessment ID | [assessment_id] |
| Assessment Date | YYYY-MM-DD |
| Assessor | Compliance Lead |
| Company Name | [company_name] |
| Jurisdiction | [jurisdiction] |
| Sector | [sector] |
| Size Category | [size_category] |
| Assessment Method | AEGIS Intake Form v2.0 (layered: Company Profile + Decision Tree + Conditional Blocks) |

---

## 3. STAKEHOLDER ANALYSIS (A1)

### 3.1 Stakeholder Register

| ID | Name | Role | Organization | Contact | Responsibilities |
|----|------|------|-------------|---------|-----------------|
| STK-CEO-01 | [stakeholder_ceo_name] | Internal | [company_name] | — | Business strategy, compliance accountability |
| STK-CTO-01 | [stakeholder_cto_name] | Internal | [company_name] | — | Technical leadership, security architecture |
| STK-DPO-01 | [stakeholder_dpo_name] | Internal | [company_name] | — | Data protection oversight, GDPR compliance |
| STK-DEVP-01 | [stakeholder_dev_name] | Internal | [company_name] | — | Secure development, implementation |
| [additional_stakeholders] |

**ID Pattern:** `STK-{Role}-{NN}` where `{Role}` is abbreviated role name (CEO, CTO, DPO, etc.) and `{NN}` is a 2-digit sequential number.

### 3.2 Stakeholder Influence Matrix

| Stakeholder ID | Influence Level | Interest Level | Engagement Strategy |
|----------------|----------------|----------------|-------------------|
| STK-CEO-01 | HIGH | HIGH | [engagement_strategy_ceo] |
| STK-CTO-01 | HIGH | HIGH | [engagement_strategy_cto] |
| STK-DPO-01 | MEDIUM | HIGH | [engagement_strategy_dpo] |
| STK-DEVP-01 | MEDIUM | MEDIUM | [engagement_strategy_dev] |

---

## 4. BUSINESS GOALS CATALOG

| Goal ID | Goal | Description | Priority | Related Regulations | Success Metrics |
|---------|------|-------------|----------|-------------------|-----------------|
| BG-01 | [goal_1_name] | [goal_1_description] | [goal_1_priority] | [goal_1_regulations] | [goal_1_metrics] |
| BG-02 | [goal_2_name] | [goal_2_description] | [goal_2_priority] | [goal_2_regulations] | [goal_2_metrics] |
| [additional_goals] |

**ID Pattern:** `BG-{NN}` where `{NN}` is a 2-digit sequential number.

---

## 5. INTAKE FORM RESPONSE SUMMARY

The complete intake form responses are documented in `01_Company_Context.md` (AEGIS Intake Form v2.0 — layered format). The following summarises key findings:

**Layer 0 — Company Profile:**
[intake_layer_0_summary]

**Layer 1 — Regulatory Decision Tree:**
[intake_layer_1_summary]

**Layer 2 — Conditional Blocks:**
[intake_layer_2_summary]

**Complexity Tier:** [complexity_tier]

---

## 6. REGULATORY APPLICABILITY FLAGS

| Regulation | Applicable? | Rationale | Applicability Threshold | Threshold Met? |
|------------|-------------|-----------|------------------------|----------------|
| GDPR | [gdpr_applicable] | [gdpr_rationale] | [gdpr_threshold] | [gdpr_met] |
| CRA | [cra_applicable] | [cra_rationale] | [cra_threshold] | [cra_met] |
| NIS 2 | [nis2_applicable] | [nis2_rationale] | [nis2_threshold] | [nis2_met] |
| DORA | [dora_applicable] | [dora_rationale] | [dora_threshold] | [dora_met] |
| AI Act | [aiact_applicable] | [aiact_rationale] | [aiact_threshold] | [aiact_met] |

---

## 7. ARCHITECTURAL IMPLICATIONS

| Implication ID | Description | Source Regulation | Impact Area | Severity | Mitigation Approach |
|----------------|-------------|-------------------|-------------|----------|-------------------|
| AI-01 | [implication_description] | [implication_regulation] | [implication_impact_area] | [implication_severity] | [implication_mitigation] |

**ID Pattern:** `AI-{NN}` where `{NN}` is a 2-digit sequential number.

---

## 8. DATA FLOW SUMMARY

| Data ID | Data Type | Source | Destination | Transfer Method | Encryption | Regulatory Constraint |
|---------|-----------|--------|-------------|-----------------|------------|----------------------|
| DF-01 | [data_type] | [data_source] | [data_destination] | [data_transfer_method] | [data_encryption] | [data_regulatory_constraint] |

**ID Pattern:** `DF-{NN}` where `{NN}` is a 2-digit sequential number.

---

## 9. COMPLIANCE CAPABILITY ASSESSMENT

| Capability ID | Capability | Current State | Target State | Gap | Priority |
|---------------|------------|---------------|--------------|-----|----------|
| CAP-01 | [capability_name] | [capability_current_state] | [capability_target_state] | [capability_gap] | [capability_priority] |

**ID Pattern:** `CAP-{NN}` where `{NN}` is a 2-digit sequential number.

---

## N-1. VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | YYYY-MM-DD | Compliance Lead | Initial template release |

## N. DOCUMENT APPROVAL

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Document Author | Compliance Lead | | YYYY-MM-DD |
| Technical Review | | | |
| Business Review | | | |
| AEGIS Methodology Review | | | |

---

**Next Document:** 05_Regulatory_Applicability.md
**Gate Status:** [PENDING / PASS / FAIL]
