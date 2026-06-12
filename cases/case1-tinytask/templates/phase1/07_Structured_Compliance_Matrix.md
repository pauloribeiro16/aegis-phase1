---
document_id: AEGIS-P1-07
title: Structured Compliance Matrix
phase: 1
version: 1.0
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: Compliance Lead
status: DRAFT
inputs: [04_Company_Context_Assessment.md, 05_Regulatory_Applicability.md, 06_Clause_Mapping_Matrix.xlsx]
outputs: [08_Obligation_Derivation.md]
traceability: AEGIS Class Model → ComplianceContext, DomainCoverageEntry, StructuredComplianceMatrix, DomainElaborationEntry, RegulatoryObligation classes
related_documents: [00_Taxonomy_Reference.md]
---

# Structured Compliance Matrix

## 1. DOCUMENT PURPOSE

This document presents the final Phase 1 output (Step C1+C2+C3), consolidating the compliance matrix with complementarity analysis and strategic implications. This is the primary output of Phase 1 and input to Phase 2.

**Alignment with Class Model:**
- `ComplianceContext` - Final applicable regulations with coverage scores
- `DomainCoverageEntry` - Complete 38 sub-domain coverage matrix
- `RegulatoryClause` - Filtered and mapped clauses

**Phase 1 Step:** C (Structured Compliance Matrix)

**Phase 1 Gate:** [gate_status] COMPLETE when this document is approved

---

## 2. COMPLIANCE MATRIX METADATA

| Attribute | Value |
|-----------|-------|
| complianceMatrixId | [matrix_id] |
| completionDate | YYYY-MM-DD |
| basedOnCompanyContext | [company_context_id] |
| basedOnApplicability | [compliance_context_id] |
| basedOnClauseMapping | AEGIS-P1-06 |
| phase1Status | [phase1_status] |

---

## 3. SUB-DOMAIN COVERAGE MATRIX (38 Entries)

### D-01: Data Protection & Encryption

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-01.1 Data at Rest Encryption | [sd_01_1_gdpr] | [sd_01_1_cra] | [sd_01_1_nis2] | [sd_01_1_dora] | [sd_01_1_aiact] | [sd_01_1_total] | [sd_01_1_coverage] | [sd_01_1_ni] |
| D-01.2 Data in Transit Encryption | [sd_01_2_gdpr] | [sd_01_2_cra] | [sd_01_2_nis2] | [sd_01_2_dora] | [sd_01_2_aiact] | [sd_01_2_total] | [sd_01_2_coverage] | [sd_01_2_ni] |
| D-01.3 Cryptographic Key Management | [sd_01_3_gdpr] | [sd_01_3_cra] | [sd_01_3_nis2] | [sd_01_3_dora] | [sd_01_3_aiact] | [sd_01_3_total] | [sd_01_3_coverage] | [sd_01_3_ni] |
| D-01.4 Data Integrity Mechanisms | [sd_01_4_gdpr] | [sd_01_4_cra] | [sd_01_4_nis2] | [sd_01_4_dora] | [sd_01_4_aiact] | [sd_01_4_total] | [sd_01_4_coverage] | [sd_01_4_ni] |

### D-02: Vulnerability Management

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-02.1 Vulnerability Identification | [sd_02_1_gdpr] | [sd_02_1_cra] | [sd_02_1_nis2] | [sd_02_1_dora] | [sd_02_1_aiact] | [sd_02_1_total] | [sd_02_1_coverage] | [sd_02_1_ni] |
| D-02.2 Patch Management & Updates | [sd_02_2_gdpr] | [sd_02_2_cra] | [sd_02_2_nis2] | [sd_02_2_dora] | [sd_02_2_aiact] | [sd_02_2_total] | [sd_02_2_coverage] | [sd_02_2_ni] |
| D-02.3 Coordinated Vuln. Disclosure | [sd_02_3_gdpr] | [sd_02_3_cra] | [sd_02_3_nis2] | [sd_02_3_dora] | [sd_02_3_aiact] | [sd_02_3_total] | [sd_02_3_coverage] | [sd_02_3_ni] |
| D-02.4 Threat-Led Penetration Testing | [sd_02_4_gdpr] | [sd_02_4_cra] | [sd_02_4_nis2] | [sd_02_4_dora] | [sd_02_4_aiact] | [sd_02_4_total] | [sd_02_4_coverage] | [sd_02_4_ni] |

### D-03: Access Control

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-03.1 Identity Lifecycle Management | [sd_03_1_gdpr] | [sd_03_1_cra] | [sd_03_1_nis2] | [sd_03_1_dora] | [sd_03_1_aiact] | [sd_03_1_total] | [sd_03_1_coverage] | [sd_03_1_ni] |
| D-03.2 Multi-Factor Authentication | [sd_03_2_gdpr] | [sd_03_2_cra] | [sd_03_2_nis2] | [sd_03_2_dora] | [sd_03_2_aiact] | [sd_03_2_total] | [sd_03_2_coverage] | [sd_03_2_ni] |
| D-03.3 Authorization & Least Privilege | [sd_03_3_gdpr] | [sd_03_3_cra] | [sd_03_3_nis2] | [sd_03_3_dora] | [sd_03_3_aiact] | [sd_03_3_total] | [sd_03_3_coverage] | [sd_03_3_ni] |
| D-03.4 Secure System Defaults | [sd_03_4_gdpr] | [sd_03_4_cra] | [sd_03_4_nis2] | [sd_03_4_dora] | [sd_03_4_aiact] | [sd_03_4_total] | [sd_03_4_coverage] | [sd_03_4_ni] |

### D-04: Incident Response

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-04.1 Incident Detection & Triage | [sd_04_1_gdpr] | [sd_04_1_cra] | [sd_04_1_nis2] | [sd_04_1_dora] | [sd_04_1_aiact] | [sd_04_1_total] | [sd_04_1_coverage] | [sd_04_1_ni] |
| D-04.2 Containment & Mitigation | [sd_04_2_gdpr] | [sd_04_2_cra] | [sd_04_2_nis2] | [sd_04_2_dora] | [sd_04_2_aiact] | [sd_04_2_total] | [sd_04_2_coverage] | [sd_04_2_ni] |
| D-04.3 Regulatory Notification | [sd_04_3_gdpr] | [sd_04_3_cra] | [sd_04_3_nis2] | [sd_04_3_dora] | [sd_04_3_aiact] | [sd_04_3_total] | [sd_04_3_coverage] | [sd_04_3_ni] |
| D-04.4 Data Restoration & Recovery | [sd_04_4_gdpr] | [sd_04_4_cra] | [sd_04_4_nis2] | [sd_04_4_dora] | [sd_04_4_aiact] | [sd_04_4_total] | [sd_04_4_coverage] | [sd_04_4_ni] |

### D-05: Data Lifecycle

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-05.1 Data Minimization | [sd_05_1_gdpr] | [sd_05_1_cra] | [sd_05_1_nis2] | [sd_05_1_dora] | [sd_05_1_aiact] | [sd_05_1_total] | [sd_05_1_coverage] | [sd_05_1_ni] |
| D-05.2 Retention & Archiving | [sd_05_2_gdpr] | [sd_05_2_cra] | [sd_05_2_nis2] | [sd_05_2_dora] | [sd_05_2_aiact] | [sd_05_2_total] | [sd_05_2_coverage] | [sd_05_2_ni] |
| D-05.3 Right to Erasure | [sd_05_3_gdpr] | [sd_05_3_cra] | [sd_05_3_nis2] | [sd_05_3_dora] | [sd_05_3_aiact] | [sd_05_3_total] | [sd_05_3_coverage] | [sd_05_3_ni] |
| D-05.4 Data Portability | [sd_05_4_gdpr] | [sd_05_4_cra] | [sd_05_4_nis2] | [sd_05_4_dora] | [sd_05_4_aiact] | [sd_05_4_total] | [sd_05_4_coverage] | [sd_05_4_ni] |

### D-06: Supply Chain

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-06.1 Vendor Risk Assessment | [sd_06_1_gdpr] | [sd_06_1_cra] | [sd_06_1_nis2] | [sd_06_1_dora] | [sd_06_1_aiact] | [sd_06_1_total] | [sd_06_1_coverage] | [sd_06_1_ni] |
| D-06.2 Software Bill of Materials (SBOM) | [sd_06_2_gdpr] | [sd_06_2_cra] | [sd_06_2_nis2] | [sd_06_2_dora] | [sd_06_2_aiact] | [sd_06_2_total] | [sd_06_2_coverage] | [sd_06_2_ni] |
| D-06.3 Contractual Security Obligations | [sd_06_3_gdpr] | [sd_06_3_cra] | [sd_06_3_nis2] | [sd_06_3_dora] | [sd_06_3_aiact] | [sd_06_3_total] | [sd_06_3_coverage] | [sd_06_3_ni] |
| D-06.4 Third-Party Boundary Management | [sd_06_4_gdpr] | [sd_06_4_cra] | [sd_06_4_nis2] | [sd_06_4_dora] | [sd_06_4_aiact] | [sd_06_4_total] | [sd_06_4_coverage] | [sd_06_4_ni] |

### D-07: Secure Development

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-07.1 Secure-by-Design Principles | [sd_07_1_gdpr] | [sd_07_1_cra] | [sd_07_1_nis2] | [sd_07_1_dora] | [sd_07_1_aiact] | [sd_07_1_total] | [sd_07_1_coverage] | [sd_07_1_ni] |
| D-07.2 Secure Coding Practices | [sd_07_2_gdpr] | [sd_07_2_cra] | [sd_07_2_nis2] | [sd_07_2_dora] | [sd_07_2_aiact] | [sd_07_2_total] | [sd_07_2_coverage] | [sd_07_2_ni] |
| D-07.3 CI/CD Pipeline Security | [sd_07_3_gdpr] | [sd_07_3_cra] | [sd_07_3_nis2] | [sd_07_3_dora] | [sd_07_3_aiact] | [sd_07_3_total] | [sd_07_3_coverage] | [sd_07_3_ni] |
| D-07.4 Change Management | [sd_07_4_gdpr] | [sd_07_4_cra] | [sd_07_4_nis2] | [sd_07_4_dora] | [sd_07_4_aiact] | [sd_07_4_total] | [sd_07_4_coverage] | [sd_07_4_ni] |

### D-08: Human Factors

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-08.1 General Security Awareness | [sd_08_1_gdpr] | [sd_08_1_cra] | [sd_08_1_nis2] | [sd_08_1_dora] | [sd_08_1_aiact] | [sd_08_1_total] | [sd_08_1_coverage] | [sd_08_1_ni] |
| D-08.2 Role-Specific Competence | [sd_08_2_gdpr] | [sd_08_2_cra] | [sd_08_2_nis2] | [sd_08_2_dora] | [sd_08_2_aiact] | [sd_08_2_total] | [sd_08_2_coverage] | [sd_08_2_ni] |
| D-08.3 Management Board Training | [sd_08_3_gdpr] | [sd_08_3_cra] | [sd_08_3_nis2] | [sd_08_3_dora] | [sd_08_3_aiact] | [sd_08_3_total] | [sd_08_3_coverage] | [sd_08_3_ni] |

### D-09: Governance & Documentation

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-09.1 Information Security Policies | [sd_09_1_gdpr] | [sd_09_1_cra] | [sd_09_1_nis2] | [sd_09_1_dora] | [sd_09_1_aiact] | [sd_09_1_total] | [sd_09_1_coverage] | [sd_09_1_ni] |
| D-09.2 Impact & Risk Assessments | [sd_09_2_gdpr] | [sd_09_2_cra] | [sd_09_2_nis2] | [sd_09_2_dora] | [sd_09_2_aiact] | [sd_09_2_total] | [sd_09_2_coverage] | [sd_09_2_ni] |
| D-09.3 Asset Inventories | [sd_09_3_gdpr] | [sd_09_3_cra] | [sd_09_3_nis2] | [sd_09_3_dora] | [sd_09_3_aiact] | [sd_09_3_total] | [sd_09_3_coverage] | [sd_09_3_ni] |
| D-09.4 Records of Processing | [sd_09_4_gdpr] | [sd_09_4_cra] | [sd_09_4_nis2] | [sd_09_4_dora] | [sd_09_4_aiact] | [sd_09_4_total] | [sd_09_4_coverage] | [sd_09_4_ni] |

### D-10: Monitoring & Audit

| Sub-Domain | GDPR | CRA | NIS 2 | DORA | AI Act | Total | Coverage | NI |
|------------|------|-----|-------|------|--------|-------|----------|-----|
| D-10.1 Continuous Security Monitoring | [sd_10_1_gdpr] | [sd_10_1_cra] | [sd_10_1_nis2] | [sd_10_1_dora] | [sd_10_1_aiact] | [sd_10_1_total] | [sd_10_1_coverage] | [sd_10_1_ni] |
| D-10.2 Audit Logging & Traceability | [sd_10_2_gdpr] | [sd_10_2_cra] | [sd_10_2_nis2] | [sd_10_2_dora] | [sd_10_2_aiact] | [sd_10_2_total] | [sd_10_2_coverage] | [sd_10_2_ni] |
| D-10.3 Compliance Testing | [sd_10_3_gdpr] | [sd_10_3_cra] | [sd_10_3_nis2] | [sd_10_3_dora] | [sd_10_3_aiact] | [sd_10_3_total] | [sd_10_3_coverage] | [sd_10_3_ni] |

---

## 4. COVERAGE SUMMARY DASHBOARD

| Metric | Value | Formula |
|--------|-------|---------|
| Total Sub-Domains | [total_subdomains] | Fixed |
| Substantive Coverage (≥2 regs) | [substantive_count] | COUNTIF(Coverage, "SUBSTANTIVE") |
| Partial Coverage (1 reg) | [partial_count] | COUNTIF(Coverage, "PARTIAL") |
| Not Addressed (0 regs) | [not_addressed_count] | COUNTIF(Coverage, "NOT_ADDRESSED") |
| Coverage Percentage | [coverage_pct]% | (Substantive + Partial) / 38 |
| Total Applicable Clauses | [total_applicable_clauses] | [reg_1] ([reg_1_count]) + [reg_2] ([reg_2_count]) |
| Average Normative Intensity | [avg_ni] | AVERAGE(NI column) |
| Sole Authority Gaps | [sole_authority_gaps] | [list of subdomains] |

---

## 5. COMPLEMENTARITY ANALYSIS (C2)

### 5.1 Cross-Regulation Overlap

| Regulation Pair | Shared Sub-Domains | Overlap % | Synergy Opportunities | sharedScope | complementarityIndex | structuralConnectedness |
|-----------------|-------------------|-----------|----------------------|-------------|---------------------|------------------------|
| [overlap_reg_1] + [overlap_reg_2] | [overlap_subdomains] | [overlap_pct]% | [overlap_synergy] | [shared_scope] | [complementarity_index] | [structural_connectedness] |

### 5.2 Complementarity Opportunities

| Opportunity ID | Sub-Domain | Regulations Involved | Description | Implementation Benefit |
|----------------|------------|---------------------|-------------|------------------------|
| CO-001 | [co_1_subdomain] | [co_1_regulations] | [co_1_description] | [co_1_benefit] |
| [additional_opportunities] |

### 5.3 Conflict Classification (Structural vs Contextual)

| Relationship Type | Definition | Sub-Domains | Example |
|-------------------|-----------|-------------|---------|
| **Synergistic** (Complementarity) | Two regulations reinforce each other with compatible requirements | [synergistic_subdomains] | [synergistic_example] |
| **Structural Tension** | Two regulations apply permanently with differing requirements; resolved once at design level | [structural_subdomains] | [structural_example] |
| **Contextual Tension** | Two regulations may conflict only when the same factual event triggers both; resolved per-event | [contextual_subdomains] | [contextual_example] |

### 5.4 Compound Event Scenarios

| Event ID | Compound Event Description | Regulations Triggered | Sub-Domain | Tension Created | Resolution Required |
|----------|--------------------------|----------------------|------------|-----------------|-------------------|
| EVT-001 | [event_1_description] | [event_1_regulations] | [event_1_subdomain] | [event_1_tension] | [event_1_resolution] |
| [additional_events] |

---

## 6. STRATEGIC IMPLICATIONS (C3)

| Implication ID | Sub-Domain | Source Regulation(s) | Description | Architectural Impact | Priority |
|----------------|------------|---------------------|-------------|---------------------|----------|
| SI-001 | [si_1_subdomain] | [si_1_regulation] | [si_1_description] | [si_1_impact] | [si_1_priority] |
| [additional_implications] |

---

## 7. IDENTIFIED GAPS SUMMARY

| Gap ID | Sub-Domain | Regulation | Clause | Gap Type | Risk Level | Recommended Action |
|--------|------------|------------|--------|----------|------------|-------------------|
| GAP-001 | [gap_1_subdomain] | [gap_1_regulation] | [gap_1_clause] | [gap_1_type] | [gap_1_risk] | [gap_1_action] |
| [additional_gaps] |

**Gap Summary:**
- HIGH Risk Gaps: [high_risk_count] ([high_risk_subdomains])
- MEDIUM Risk Gaps: [medium_risk_count] ([medium_risk_subdomains])
- LOW Risk Gaps: [low_risk_count] ([low_risk_subdomains])

---

## 8. PHASE 1 GATE CRITERIA CHECKLIST

| Criterion | Status | Evidence |
|-----------|--------|----------|
| All 38 questions answered (04) | [criterion_01_status] | [criterion_01_evidence] |
| All 5 regulations assessed (05) | [criterion_02_status] | [criterion_02_evidence] |
| Clause mapping complete (06) | [criterion_03_status] | [criterion_03_evidence] |
| Sub-domain coverage complete | [criterion_04_status] | [criterion_04_evidence] |
| Gaps identified and prioritized | [criterion_05_status] | [criterion_05_evidence] |
| Strategic implications documented | [criterion_06_status] | [criterion_06_evidence] |
| Design decisions logged (03) | [criterion_07_status] | [criterion_07_evidence] |

**Phase 1 Gate Decision:** [phase_1_gate_decision] [phase_1_gate_status]

**Gate Review Date:** [gate_review_date]

**Gate Reviewers:**
- Compliance Lead: _________________
- Technical Review (CTO): _________________
- AEGIS Methodology Review: _________________

---

## 9. INPUT TO PHASE 2

The following artifacts are passed to Phase 2:

| Artifact | Document Reference | Purpose in Phase 2 |
|----------|-------------------|-------------------|
| Applicable Regulations | Section [applicable_regs_section] | Filter for obligation derivation ([applicable_regs_list]) |
| Sub-Domain Coverage Matrix | Section [coverage_section] | Rules Catalog organization |
| Clause Mapping | 06_Clause_Mapping_Matrix.xlsx | Source for AbstractNFR derivation |
| Strategic Implications | Section [strategic_section] | Input for Strategic Tension detection |
| Identified Gaps | Section [gaps_section] | Priority input for Rules Catalog |

---

## 10. VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | YYYY-MM-DD | Compliance Lead | Initial template release |

---

## 11. DOCUMENT APPROVAL

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Document Author | Compliance Lead | | YYYY-MM-DD |
| Technical Review (CTO) | | | |
| Business Review (CEO) | | | |
| AEGIS Methodology Review | | | |

---

**Phase 1 Status:** [phase_1_status]
**Next Phase:** 02_PHASE2_RULES → 08_Obligation_Derivation.md
