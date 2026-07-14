---
document_id: AEGIS-COMMON-03
title: Design Decisions Log
version: 1.0
created: 2026-03-26
updated: 2026-03-26
author: [AEGIS Research Team]
status: DRAFT
traceability: AEGIS Class Model decision notes (drawio.xml)
inputs: [01_Company_Context.md, 04_Company_Context_Assessment.md, 05_Regulatory_Applicability.md]
outputs: [Design decision records stored in this document]
related_documents: [01_Company_Context.md, 07_Structured_Compliance_Matrix.md]
---

# Design Decisions Log

## 1. DOCUMENT PURPOSE

This document captures all design decisions made throughout all AEGIS phases. Each decision is recorded with its rationale, alternatives considered, and traceability to AEGIS class model attributes.

**Alignment with Class Model:** This document supports decision notes annotated in the AEGIS Class Model diagrams (Phase 1, 2, and 3).

**Phase Usage:**
- Phase 1: CompanyContext, RegulatoryClause, ComplianceContext decisions
- Phase 2: RegulatoryObligation, StrategicTension, RulesCatalog decisions
- Phase 3: ArchitecturalNode, FunctionalNode, ComplianceGate decisions

---

## 2. DECISION LOG STRUCTURE

Each decision is recorded using the following template:

| Field | Description |
|-------|-------------|
| Decision ID | Unique identifier (D-XXX) |
| Decision Date | Date decision was made |
| Decision Maker | Role/person who made the decision |
| Decision Statement | Clear statement of what was decided |
| Alternatives Considered | Other options that were evaluated |
| Rationale | Why this decision was made |
| Class Model Reference | Link to class model element |
| Impact Assessment | Downstream effects of this decision |
| Review Date | When decision should be re-evaluated |
| Status | ✅ APPROVED / ⚠️ CONDITIONAL / ❌ REJECTED |

---

## 3. DECISION REGISTER

### 3.1 PHASE 1 DECISIONS (Company Context & Regulatory Inference)

| Decision ID | D-001 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team + CTO |
| Decision Statement | Keep CompanyContext as monolithic entity (8 attributes + 30 derived) — do NOT decompose into RegulatoryApplicability + OperationalProfile |
| Alternatives Considered | 1. Decomposed: Split into RegulatoryApplicability (5 boolean flags) + OperationalProfile (30 operational attributes)<br>2. Monolithic (Selected): Single entity with all attributes |
| Rationale | 1. Simplicity over premature optimization: Attributes are manageable<br>2. Class Model annotation: Decision note explicitly states "Manter monolítico"<br>3. Phase 1 scope: CompanyContext is input artifact, not analytical construct<br>4. Traceability: All attributes map directly to T8.4 ComplianceContext Applicability Conditions |
| Class Model Reference | CompanyContext class + Decision Note |
| Impact Assessment | - Positive: Simpler Document 04 structure; easier to populate<br>- Negative: If Phase 2 requires separate regulatory vs. operational analysis, may need refactoring<br>- Mitigation: Document attribute groupings in 04 for future extraction |
| Review Date | Phase 2 Gate Review |
| Status | ✅ APPROVED |

---

| Decision ID | D-002 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team + CEO |
| Decision Statement | TinyTask NIS 2 classification: Technology sector BUT below employee threshold (8 < 50) = NOT APPLICABLE |
| Alternatives Considered | 1. Apply NIS 2: Treat as "Important Entity" despite size<br>2. Exclude NIS 2 (Selected): Below threshold per Art. 21<br>3. Voluntary Compliance: Adopt NIS 2 controls as best practice |
| Rationale | 1. T8.4 ComplianceContext: nis2_sector = "Technology" BUT size = 8 employees (< 50 threshold)<br>2. Legal accuracy: NIS 2 Art. 21 explicitly sets 50 employee threshold for medium enterprises<br>3. Resource efficiency: No regulatory mandate = no compliance debt<br>4. AEGIS principle: Only analyze applicable regulations in Phase 1 |
| Class Model Reference | ComplianceContext.applicable_regulations |
| Impact Assessment | - Positive: Reduces Phase 1 analysis from 5 to 2 regulations (GDPR + CRA)<br>- Negative: Sub-domains with NIS 2 sole authority (D-07.3 CI/CD) become optional<br>- Mitigation: Document as best practice in 00_Taxonomy_Reference.md |
| Review Date | Annual (if employee count approaches 50) |
| Status | ✅ APPROVED |

---

| Decision ID | D-003 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team + CTO |
| Decision Statement | TinyTask AI Act classification: No AI/ML systems (aiact_high_risk_system = FALSE) = NOT APPLICABLE |
| Alternatives Considered | 1. Apply AI Act: Assume future AI features will trigger applicability<br>2. Exclude AI Act (Selected): Current system has no AI/ML<br>3. Conditional Applicability: Flag for re-evaluation if AI features proceed |
| Rationale | 1. T8.4 ComplianceContext: aiact_high_risk_system = FALSE (Layer 0 attribute)<br>2. AEGIS principle: Phase 1 analyzes CURRENT state, not hypothetical futures<br>3. C3 Strategic Implication: AI Act blocker documented; requires executive decision before any AI feature development |
| Class Model Reference | CompanyContext.aiact_high_risk_system + StrategicImplication |
| Impact Assessment | - Positive: Reduces Phase 1 analysis scope<br>- Negative: If AI features added later, Phase 1 must be re-run<br>- Mitigation: Flagged as Phase 1 Gate Blocker in 07_Structured_Compliance_Matrix.md |
| Review Date | Before any AI feature development |
| Status | ⚠️ CONDITIONAL — Pending CEO decision |

---

| Decision ID | D-004 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team |
| Decision Statement | Include ALL Nuances (1-3) in RegulatoryClause class — do NOT simplify |
| Alternatives Considered | 1. Nuance 1 only: isAtomic, parentClauseId, siblingClauseIds<br>2. Nuance 2 only: obligationType<br>3. Nuance 3 only: obligatedParty[]<br>4. All Nuances (Selected): Include all three nuance layers |
| Rationale | 1. Class Model annotation: Decision note explicitly states "Incluir todas as Nuances (1-3)"<br>2. T1-T5 Regulatory Mapping: All three nuances are required for complete clause characterization<br>3. Phase 2 preparation: Nuance 2 (obligationType) and Nuance 3 (obligatedParty) are critical for Strategic Tension Analysis<br>4. Traceability: Nuance 1 supports clause decomposition; Nuance 2 supports obligationType conflict detection (T7.5); Nuance 3 supports Native/Inherited classification |
| Class Model Reference | RegulatoryClause class + Decision Note |
| Impact Assessment | - Positive: Complete clause characterization; supports all Phase 2 analyses<br>- Negative: Increased Document 06 complexity (54 clauses × 3 nuances each)<br>- Mitigation: Use structured tables in 06 for clarity |
| Review Date | Phase 2 Gate Review |
| Status | ✅ APPROVED |

---

| Decision ID | D-005 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team |
| Decision Statement | Normative Weight (T9) assigned at clause level — NOT at sub-domain level |
| Alternatives Considered | 1. Sub-Domain Level: Assign single weight per sub-domain<br>2. Clause Level (Selected): Assign weight per individual clause<br>3. Regulation Level: Assign single weight per regulation |
| Rationale | 1. T9 Normative Intensity Matrix: Explicitly assigns weights at clause level (150 clauses × 5 regulations)<br>2. Precision: Different clauses in same sub-domain may have different normative strength<br>3. Weighted Score accuracy: T9.3 Weighted Score Matrix requires clause-level weights for accurate calculation<br>4. AEGIS principle: Granularity enables precise Strategic Tension detection |
| Class Model Reference | RegulatoryClause.normativeWeight attribute |
| Impact Assessment | - Positive: Precise normative intensity calculation; accurate weighted scores<br>- Negative: Increased 06 documentation effort (54 clause weight assignments)<br>- Mitigation: Use T9.1 tables as reference; copy weights directly |
| Review Date | Phase 2 Gate Review |
| Status | ✅ APPROVED |

---

| Decision ID | D-006 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team |
| Decision Statement | ComplementarityAnalysis is PERSISTENT entity — NOT a derived query |
| Alternatives Considered | 1. Derived Query: Calculate SharedScope/ComplementarityIndex on-demand<br>2. Persistent Entity (Selected): Store as versioned artifact with audit trail |
| Rationale | 1. Class Model annotation: Decision note explicitly states "Entidade persistente — Versionamento + auditoria para tese (T7 metrics)"<br>2. Traceability: Phase 1 outputs must be auditable for thesis validation<br>3. Reproducibility: Persistent entity enables re-running Phase 1 with same inputs to verify consistency<br>4. T7 Metrics: SharedScope, ComplementarityIndex, StructuralConnectedness require documented calculation basis |
| Class Model Reference | ComplementarityAnalysis class + Decision Note |
| Impact Assessment | - Positive: Audit trail for thesis; reproducible analysis<br>- Negative: Additional storage and versioning overhead<br>- Mitigation: Store as Document 08 with version control |
| Review Date | Thesis Defense |
| Status | ✅ APPROVED |

---

| Decision ID | D-007 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team |
| Decision Statement | ImplementationMapping INCLUDED in Phase 1 — NOT deferred to Phase 3 |
| Alternatives Considered | 1. Phase 3 Only: Move ImplementationMapping to Functional Decomposition phase<br>2. Phase 1 Inclusion (Selected): Include traceability Sub-Domain → Framework in Phase 1 |
| Rationale | 1. Class Model annotation: Decision note explicitly states "Manter na Fase 1 — Rastreabilidade Sub-Domain → Framework — Evita refatorização na Fase 3"<br>2. Traceability: Early mapping prevents refactoring when Phase 3 begins<br>3. Framework selection: NIST CSF, ISO 27001, SOC 2 mappings inform Phase 2 Rules Catalog consolidation<br>4. AEGIS principle: Traceability from regulation → sub-domain → framework → control |
| Class Model Reference | ImplementationMapping class + Decision Note |
| Impact Assessment | - Positive: Prevents Phase 3 refactoring; enables framework selection in Phase 2<br>- Negative: Increased Phase 1 effort (framework mapping for 31 covered sub-domains)<br>- Mitigation: Use WP1 Taxonomy Crosswalk for efficient mapping |
| Review Date | Phase 2 Gate Review |
| Status | ✅ APPROVED |

---

| Decision ID | D-008 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team |
| Decision Statement | Taxonomy: 10 Domains × 38 Sub-Domains — FIXED for Phase 1 |
| Alternatives Considered | 1. Dynamic Taxonomy: Allow sub-domain additions during Phase 1 analysis<br>2. Fixed Taxonomy (Selected): Lock 38 sub-domains from 00_Taxonomy_Reference.md<br>3. Regulation-Specific Taxonomy: Separate taxonomy per regulation |
| Rationale | 1. Class Model annotation: Decision note explicitly states "Taxonomia: 10 Domains × 38 Sub-Domains — Vocabulário comum entre regulamentos e implementação"<br>2. Common vocabulary: Single taxonomy enables cross-regulation comparison (T6 Domain Coverage Matrix)<br>3. Traceability: Fixed taxonomy enables consistent Sub-Domain ID references across all documents<br>4. AEGIS principle: Taxonomy is the "common language" between regulations and implementation |
| Class Model Reference | SecurityControlDomain class + Decision Note |
| Impact Assessment | - Positive: Consistent references across all Phase 1 documents; enables T6/T7 analysis<br>- Negative: If new sub-domains discovered, requires taxonomy update and re-analysis<br>- Mitigation: Document gaps in 07_Structured_Compliance_Matrix.md; propose taxonomy extensions for Phase 2 |
| Review Date | Phase 2 Gate Review |
| Status | ✅ APPROVED |

---

| Decision ID | D-009 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team |
| Decision Statement | RelationType (Overlap/CumulativeReinforcement/Conflict/Gap) distinguishes overlap types — Nuance 5 |
| Alternatives Considered | 1. Binary Overlap: Simple "overlaps/doesn't overlap" classification<br>2. RelationType (Selected): Four distinct relation types per T7 |
| Rationale | 1. Class Model annotation: Decision note explicitly states "Nuance 5: relationType distingue Overlap vs Reinforcement vs Conflict vs Gap — Suporta deteção de StrategicTension (Fase 2)"<br>2. T7.5 Conflict Detection: Different relation types trigger different Phase 2 resolution strategies<br>3. Strategic Tension preparation: Conflict relationType directly feeds SI derivation in 07<br>4. AEGIS principle: Not all overlaps are equal — some are synergistic (Reinforcement), some are problematic (Conflict) |
| Class Model Reference | DomainCoverageEntry.relationType + RelationType enumeration + Decision Note |
| Impact Assessment | - Positive: Enables precise Strategic Tension detection in 07<br>- Negative: Increased 07 analysis complexity (11 overlaps × 4 relation types)<br>- Mitigation: Use T7.5 obligationType Conflict Detection table as reference |
| Review Date | Phase 2 Gate Review |
| Status | ✅ APPROVED |

---

| Decision ID | D-010 |
|-------------|-------|
| Decision Date | 2026-04-01 |
| Decision Maker | AEGIS Research Team |
| Decision Statement | RegulatoryObligation RENAMED from "AbstractNFR" — semantically correct |
| Alternatives Considered | 1. AbstractNFR: Original class name<br>2. RegulatoryObligation (Selected): Renamed for semantic accuracy |
| Rationale | 1. Class Model annotation: Decision note explicitly states "RENOMEADO: Antes 'AbstractNFR' — Agora semanticamente correto"<br>2. Semantic accuracy: These ARE regulatory obligations, NOT technical NFRs (those come in Phase 3)<br>3. Phase boundary clarity: Prevents confusion between Phase 1 (regulatory) and Phase 3 (technical NFRs)<br>4. Traceability: Clear derivation path: RegulatoryClause → RegulatoryObligation → Privacy/Security Goal (Phase 2) |
| Class Model Reference | RegulatoryObligation class + Decision Note |
| Impact Assessment | - Positive: Clear semantic distinction; prevents Phase 1/Phase 3 confusion<br>- Negative: Requires updating any legacy references to "AbstractNFR"<br>- Mitigation: Document rename in this Decision Log; update all Phase 1 documents |
| Review Date | Phase 2 Gate Review |
| Status | ✅ APPROVED |

---

### 3.2 PHASE 2 DECISIONS (Elaboration & Secure Design)

*To be completed during Phase 2 implementation*

---

### 3.3 PHASE 3 DECISIONS (Decomposition & Risk)

*To be completed during Phase 3 implementation*

---

## 4. DECISION SUMMARY DASHBOARD

| Decision ID | Decision Statement | Phase | Status | Review Date |
|-------------|-------------------|-------|--------|-------------|
| D-001 | CompanyContext monolithic (8 attributes + 30 derived) | Phase 1 | ✅ APPROVED | Phase 2 Gate |
| D-002 | NIS 2 NOT APPLICABLE (below 50 employee threshold) | Phase 1 | ✅ APPROVED | Annual |
| D-003 | AI Act NOT APPLICABLE (no AI/ML systems) | Phase 1 | ⚠️ CONDITIONAL | Before AI features |
| D-004 | Include ALL Nuances (1-3) in RegulatoryClause | Phase 1 | ✅ APPROVED | Phase 2 Gate |
| D-005 | Normative Weight at clause level | Phase 1 | ✅ APPROVED | Phase 2 Gate |
| D-006 | ComplementarityAnalysis is persistent entity | Phase 1 | ✅ APPROVED | Thesis Defense |
| D-007 | ImplementationMapping in Phase 1 | Phase 1 | ✅ APPROVED | Phase 2 Gate |
| D-008 | Taxonomy fixed (10×38) | Phase 1 | ✅ APPROVED | Phase 2 Gate |
| D-009 | RelationType distinguishes overlap types | Phase 1 | ✅ APPROVED | Phase 2 Gate |
| D-010 | RegulatoryObligation renamed from AbstractNFR | Phase 1 | ✅ APPROVED | Phase 2 Gate |

**Total Decisions:** 10  
**Approved:** 9 (90%)  
**Conditional:** 1 (10%) — D-003 (AI Act applicability)  
**Rejected:** 0

---

## 5. DECISION TRACEABILITY MATRIX

| Decision ID | Related Document | Related Class | Related T-Table | Phase 2 Impact |
|-------------|------------------|---------------|-----------------|----------------|
| D-001 | 01_Company_Context.md | CompanyContext | T8.4 | CompanyContext structure |
| D-002 | 05_Regulatory_Applicability.md | ComplianceContext | T8.4 | Regulation scope (GDPR+CRA only) |
| D-003 | 07_Structured_Compliance_Matrix.md | StrategicImplication | SI-007 | AI Act blocker |
| D-004 | 06_Clause_Mapping_Matrix.xlsx | RegulatoryClause | T1-T5 | Clause characterization |
| D-005 | 06_Clause_Mapping_Matrix.xlsx | RegulatoryClause | T9 | Normative Intensity calculation |
| D-006 | 08_Complementarity_Analysis.md | ComplementarityAnalysis | T7 | Audit trail for thesis |
| D-007 | 07_Structured_Compliance_Matrix.md | ImplementationMapping | T6 | Framework traceability |
| D-008 | All Phase 1 documents | SecurityControlDomain | Taxonomia.txt | Common vocabulary |
| D-009 | 08_Complementarity_Analysis.md | DomainCoverageEntry | T7.5 | Strategic Tension detection |
| D-010 | All Phase 1-3 documents | RegulatoryObligation | N/A | Semantic clarity |

---

## 6. DECISION PATTERNS & LESSONS LEARNED

### 6.1 Recurring Decision Themes

| Theme | Frequency | Pattern | Recommendation |
|-------|-----------|---------|----------------|
| Monolithic vs. Decomposed | 2 (D-001, D-008) | Keep simple for Phase 1 | Defer optimization until Phase 3 |
| Phase Inclusion vs. Deferral | 2 (D-003, D-007) | Include traceability early | Prevents refactoring |
| Naming Conventions | 1 (D-010) | Semantic accuracy over legacy | Rename early |
| Persistence vs. Derived | 1 (D-006) | Persistent for audit trail | Thesis requirement |
| Granularity Level | 1 (D-005) | Fine granularity | Enables precision |

### 6.2 Lessons Learned

| Lesson | Phase | Impact | Future Application |
|--------|-------|--------|-------------------|
| Taxonomy as common vocabulary | Phase 1 | Enabled cross-regulation comparison | Use in all future cases |
| Early traceability prevents rework | Phase 1 | ImplementationMapping saved Phase 3 refactoring | Standard practice |
| Conditional decisions need triggers | Phase 1 | D-003 requires AI feature trigger | Document triggers explicitly |
| Persistent entities for thesis | Phase 1 | Audit trail for research | Required for academic validation |

---

## 7. VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-01 | AEGIS Research Team | Initial release - TinyTask SaaS case (10 decisions) |

---

## 8. DOCUMENT APPROVAL

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Document Author | AEGIS Research Team | | 2026-04-01 |
| AEGIS Methodology Review | | | |
| Technical Review (CTO) | | | |
| Business Review (CEO) | | | |

---

**Next Document:** 08_Obligation_Derivation.md  
**Dependency:** None (foundational governance artifact)  
**Case Study:** TinyTask SaaS (Low Complexity)  
**Total Decisions Logged:** 10
