---
document_id: AEGIS-P1-05
title: Regulatory Applicability Assessment
phase: 1
version: 1.1
created: "2026-09-01T16:09:27Z"
updated: "2026-09-01T16:09:27Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, ../00_COMMON/01_Company_Context.md, 00_Taxonomy_Reference.md]
outputs: [06_Clause_Mapping_Matrix.xlsx, 07_Structured_Compliance_Matrix.md, 08_Obligation_Derivation.md]
applicable_regs: [CRA, GDPR]
related_documents: [../../../00_METHODOLOGY/PHASE1_STRATEGY.md, "../../../00_METHODOLOGY/PHASE1_STRATEGY.md#filter-1-regulation-applicability-binary-predicates", 00_Taxonomy_Reference.md]
traceability: AEGIS Class Model → ComplianceContext, RegulatoryClause, DomainCoverageEntry
generated_at: "2026-09-01T16:09:27Z"
---
# AEGIS-P1-05 Regulatory Applicability

## 0. APPLICABILITY SUMMARY (CORR-038 — v2 source of truth)

The following table is the deterministic, v2-driven summary of regulatory applicability for this case. The data comes from the :class:`ApplicabilityContext` built by the v2 pipeline (:mod:`aegis_phase1.v2.context.applicability_context`).

| Regulation | Status | Obligated Party | Rationale |
| --- | --- | --- | --- |
| GDPR | ✅ APPLICABLE | controller | processes_personal_data = true |
| CRA | ✅ APPLICABLE | manufacturer | places_digital_products_eu = true |
| NIS2 | ❌ NOT APPLICABLE | — | below_threshold |
| DORA | ❌ NOT APPLICABLE | — | not_financial_entity |
| AI_Act | ❌ NOT APPLICABLE | — | no_high_risk_ai_system |

**Compliance Posture Tier:** `LOW` (light-touch; MICRO/SMALL with 1-2 applicable regs)


**Declaration gaps:** none — computed and declared are aligned.

---

## 1. PURPOSE

Determine, per regulation, whether the company falls in scope of the EU regulations tracked by AEGIS — GDPR, CRA, NIS 2, DORA, and AI Act — and record the criteria, evidence, and reasoning that justify each determination. The output of this document is the canonical input for clause mapping (06) and for the coverage matrix (07).

Three observable deliverables are produced downstream of this document:

- a populated applicability table that names, for each regulation, the threshold that triggers applicability, the company's value against that threshold, and the result;
- a Native-vs-Inherited split that separates obligations the company implements directly from obligations satisfied through suppliers and partners;
- a forward handover record (§8) that captures the artefacts passed to Phase 2.

## 2. APPLICABLE SUMMARY

- **Applicable regulations (2):** CRA, GDPR
- **Non-applicable regulations (0):** -
- **Total applicable clauses across the case:** 54

## 3. PER-REGULATION APPLICABILITY

Each sub-section below follows a fixed shape: thresholds and criteria on the left, the company value on the right, and a result column. The evidence block lists the ontology fields that ground the determination; the reasoning block carries the natural-language rationale.

## 4. NATIVE VS INHERITED COMPLIANCE

The applicability table is augmented with a NATIVE / INHERITED annotation per regulation–domain pair. NATIVE means the company implements the control itself; INHERITED means the control is satisfied through a contractual relationship with a cloud or service provider that carries its own attestation (for example, an ISO 27001 or SOC 2 Type II report).

_No architecture inventory available; this section is inheriting-agnostic._


Compliance evidence for INHERITED rows must be filed in the working directory (typically under ``02_CASES/.../04_EVIDENCE/``) before Phase 2 begins.

## 5. SUB-DOMAIN COVERAGE PRELIMINARY

Coverage status per sub-domain is computed from the layer-0 ontology and the applicable regulation set. A sub-domain is **SUBSTANTIVE** when ≥ 2 applicable regulations cover it, **PARTIAL** when exactly one applies, and **NOT_ADDRESSED** when no applicable regulation intersects the company context.

_No sub-domain catalogue available._


### 5.1 Status Counts

| Status | Count | Percentage |
| --- | --- | --- |
| SUBSTANTIVE | 0 | 0.0% |
| PARTIAL | 0 | 0.0% |
| NOT_ADDRESSED | 0 | 0.0% |

## 6. STRATEGIC IMPLICATIONS

The applicability profile is condensed into a small set of implications that feed Phase 2 obligation derivation. Each implication names the trigger regulations, the affected architecture areas, and the priority with which Phase 2 must absorb the implication into obligation rows.

| Implication ID | Source Regulation(s) | Description | Architecture Impact | Priority |
| --- | --- | --- | --- | --- |
| SI-000 | — | no applicable regulations | — | LOW |

### 6.1 Narrative

The regulatory applicability assessment, anchored on the low-impact implication SI-000, evaluates how the Engineering, CISO, Operations, and Governance functions manage their respective control obligations. Through a dual-role analysis, the framework integrates the DPO function's oversight into the broader compliance structure to ensure accountability. This strategic approach is designed to minimize time-to-compliance and optimize the total cost of compliance across all functional domains.


### 6.1b Per-Regulation Rationale (LLM-02 RATIONALE)
Per-regulation rationale + implications + gaps. Generated by P1B-LLM-02 RATIONALE. Cross-references Doc 04 facts + Regulatory Baseline articles. NO boilerplate (per-validation invariant).
*Source: P1B-LLM-02 RATIONALE | multi-call concat (one section per applicable regulation, separated by `---`)*

## Status
- applicable: YES
- confidence: HIGH

## Findings
- <implication: id="IMP-D-02.3-01", description="Establish a Coordinated Vulnerability Disclosure (CVD) policy and a public contact point for reporting vulnerabilities as required by CRA Art. 14.", effort_estimate="hours to days", dependencies=[], layer0_refs=["SubDomains/D-02.3.md §2 HSO"], company_fact_refs=["DOC04:ARCH-07"]>
- <implication: id="IMP-D-07.1-01", description="Conduct a cybersecurity risk assessment for the SaaS product to satisfy Art. 13(2) requirements.", effort_estimate="hours to days", dependencies=[], layer0_refs=["SubDomains/D-07.1.md §1 CRDA"], company_fact_refs=["DOC04:ARCH-07"]>
- <implication: id="IMP-D-09.4-01", description="Prepare technical documentation and EU declaration of conformity for the product to satisfy Art. 13(12) requirements.", effort_estimate="weeks", dependencies=[], layer0_refs=["SubDomains/D-09.4.md §1 CRDA"], company_fact_refs=["DOC04:ARCH-07"]>
- <gap: gap_id="GAP-D-07.2", sub_domain_id="D-07.2", coverage_level="PARTIAL", risk_description="Lack of documented evidence regarding exploitation mitigation techniques (e.g., ASLR, stack canaries) for the Django/React stack.", covered_by_other_reg=[], recommendation="Document and accept as part of the technical documentation process.", priority="P3", layer0_refs=["SubHM/D-07.2.md §1 CRDA"]>

## Rationale
TinyTask Lda. is subject to the Cyber Resilience Act (CRA) because it acts as a manufacturer of digital products placed on the EU market, as evidenced by its architecture and product deployment strategy (`DOC04:ARCH-07`). The company's role as a 'manufacturer' triggers essential cybersecurity requirements under Annex I, specifically regarding vulnerability handling (Art. 14) and secure design (Art. 13). This applicability is further supported by the P1B-LLM-01 interpretation confirming the manufacturer status.

---

## Status
- applicable: YES
- confidence: HIGH

## Findings
- <implication: IMP-D-01.1-1, Requirement to ensure encryption of personal data at rest within AWS RDS and S3 buckets to satisfy Art. 32(1)(b), effort_estimate: hours to days, dependencies: [], layer0_refs: [SubDomains/D-01.1.md §1 CRDA], company_fact_refs: [DOC04:STORE-01]>
- <implication: IMP-D-01.2-1, Requirement to maintain TLS 1.2+ for all data in transit between the web application and external services like Stripe or Auth0, effort_estimate: hours, dependencies: [], layer0_refs: [SubDomains/D-01.2.md §1 HSO], company_fact_refs: [DOC04:FLOW-01, DOC04:CS-03]>
- <implication: IMP-D-06.1-1, Requirement to perform due diligence and maintain records of sufficient guarantees for third-party processors including AWS, Firebase, and Auth0, effort_estimate: days, dependencies: [], layer0_refs: [SubDomains/D-06.1.md §1 HSO], company_fact_refs: [DOC04:CS-01]>
- <implication: IMP-D-09.4-1, Requirement to maintain a Record of Processing Activities (RoPA) covering the identified data flows for customer registration and authentication, effort_estimate: days, dependencies: [], layer0_refs: [SubDomains/D-09.4.md §1 HSO], company_fact_refs: [DOC04:FLOW-01]>
- <gap (if any): GAP-D-09.2, sub_domain_id: D-09.2, coverage_level: PARTIAL, risk_description: No Data Protection Impact Assessment (DPIA) is currently on file despite the processing of personal data via cloud infrastructure, covered_by_other_reg: [], recommendation: address if high risk, priority: P1, layer0_refs: [SubDomains/D-09.2.md §1 HSO]>
- <gap (if any): GAP-D-06.1, sub_domain_id: D-06.1, coverage_level: PARTIAL, risk_description: Lack of a formal sub-processor register for active cloud providers (AWS, Firebase, Auth0), covered_by_other_reg: [], recommendation: address if high risk, priority: P2, layer0_refs: [SubDomains/D-06.1.md §1 HSO]>

## Rationale
GDPR applies to TinyTask Lda. because the company acts as a controller processing personal data (specifically email, name, and password) within the EU jurisdiction (Portugal). The processing occurs via established architectural flows, such as Customer Registration (DOC04:FLOW-01), which utilizes AWS and Firebase infrastructure (DOC04:ARCH-07). Under GDPR Art. 3, the company's presence in the Union and its processing of identifiers for EU data subjects trigger full regulatory obligations. While the company is a micro-enterprise (8 employees), it must implement appropriate technical and organisational measures, such as encryption at rest (D-01.1) and in transit (D-01.2), to satisfy Art. 32 requirements. The applicability is further confirmed by the lack of any active derogations, such as the household exemption (TIPO3-GDPR-HOUSEHOLD), as the company operates a commercial SaaS application.

## 7. REGULATORY GAPS IDENTIFIED

Gaps surfaced by the ontology tensions catalogue and by sub-domains whose sole authority is a regulation that does not apply to this company. The Type column distinguishes TENSION_DERIVED (tension between applicable regulations), SOLE_AUTHORITY (sub-domain in ``not_covered``), and DETERMINISTIC (annotated at the language-model layer).

_No gaps detected._


## 8. INPUT TO PHASE 2

The following artefacts leave this document and travel to Phase 2 (obligation derivation, rules catalogue, allocation). Any change to this list requires a corresponding edit in the Phase-2 ingest contract.

| Artefact | Source Section | Phase-2 Consumer |
| --- | --- | --- |
| Applicable regulation set (YES/NO flags) | §2 | Filter in 08_Obligation_Derivation.md |
| Per-regulation criteria + evidence + reasoning | §3 | Audit trail for compliance clauses |
| Native / Inherited annotations | §4 | Ownership annotation in 11_Rules_Catalog.md |
| Sub-domain coverage preliminary | §5 | Input for 07_Structured_Compliance_Matrix.md §3 |
| Strategic implications | §6 | Trigger for strategic tension detection in Phase 2 |
| Regulatory gaps | §7 | Priority input for rules catalog seed row |
| Handover envelope (this section) | §8 | Phase-2 ingest contract |

Sign-off: this document closes Phase 1 sub-task B (Regulatory Applicability). Phase 1 sub-task C (Structured Compliance Matrix) starts after this file is reviewed.


## Appendix: Source LLM Responses

Raw markdown responses captured by the S3b invoker wiring. Each subsection corresponds to one of the 5 canonical Phase 1 LLM specs. Multi-call specs (P1B-LLM-01/02 per regulation, P1C-LLM-01 per domain) are concatenated with a horizontal rule (``---``) between calls. When a spec did not run (mock mode, deterministic-only, or invoker failure) the section shows a ``(no LLM response)`` placeholder.


### P1B-LLM-01-INTERPRETATION

---
## Status
- applicable: INDETERMINATE
- confidence: LOW
- status_detail: INSUFFICIENT_EVIDENCE (missing fact: company_facts.software_licence)

## Interpretations
- TIPO2-CRA-ART14-DUAL-FLOW (YES): The company's role is explicitly identified as 'manufacturer' in the regulatory classification.
- TIPO2-CRA-ART15-VOLUNTARY (YES): The company maintains products (SaaS application) which triggers the voluntary reporting mechanism.

## Derogations
- TIPO3-CRA-NON-PLACED (NOT_ACTIVATED): The company places digital products in the EU market, as indicated by `places_digital_products_eu: True`.
- TIPO3-CRA-OPEN-SOURCE (INDETERMINATE): Evaluation is impossible because the `company_facts.software_licence` attribute is not provided in the input data.

## Rationale
The company, TinyTask Lda., is classified as a manufacturer under the CRA framework, which activates the dual-flow reporting obligations (Art. 14) and the voluntary vulnerability reporting mechanism (Art. 15) due to its product availability. The derogation for products not placed on the EU market does not apply because the company's profile confirms it places digital products in the EU. However, the activation of the open-source software derogation (TIPO3-CRA-OPEN-SOURCE) cannot be determined because the required `software_licence` fact is missing from the provided company facts.

---

## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-GDPR-RTS-DEADLINES (NO): The company's sector ("Technology/Software") does not match the required sectors for this interpretation (health, energy, transport, or digital_infrastructure).

## Derogations
- TIPO3-GDPR-HOUSEHOLD (NOT_ACTIVATED): The company operates a commercial SaaS application and does not engage in processing limited to purely personal or household activities.

## Rationale
The GDPR is applicable to TinyTask Lda. as the company processes personal data through its SaaS architecture. However, the specific interpretation TIPO2-GDPR-RTS-DEADLINES is not activated because the company's sector (Technology/Software) falls outside the scope defined in the activation predicate (health, energy, transport, or digital_infrastructure). The derogation TIPO3-GDPR-HOUSEHOLD is not activated because the company's processing activities are commercial in nature, as evidenced by its SaaS business model and customer data flows, which precludes the "purely personal or household" classification required for this exclusion.


### P1B-LLM-02-RATIONALE

## Status
- applicable: YES
- confidence: HIGH

## Findings
- <implication: id="IMP-D-02.3-01", description="Establish a Coordinated Vulnerability Disclosure (CVD) policy and a public contact point for reporting vulnerabilities as required by CRA Art. 14.", effort_estimate="hours to days", dependencies=[], layer0_refs=["SubDomains/D-02.3.md §2 HSO"], company_fact_refs=["DOC04:ARCH-07"]>
- <implication: id="IMP-D-07.1-01", description="Conduct a cybersecurity risk assessment for the SaaS product to satisfy Art. 13(2) requirements.", effort_estimate="hours to days", dependencies=[], layer0_refs=["SubDomains/D-07.1.md §1 CRDA"], company_fact_refs=["DOC04:ARCH-07"]>
- <implication: id="IMP-D-09.4-01", description="Prepare technical documentation and EU declaration of conformity for the product to satisfy Art. 13(12) requirements.", effort_estimate="weeks", dependencies=[], layer0_refs=["SubDomains/D-09.4.md §1 CRDA"], company_fact_refs=["DOC04:ARCH-07"]>
- <gap: gap_id="GAP-D-07.2", sub_domain_id="D-07.2", coverage_level="PARTIAL", risk_description="Lack of documented evidence regarding exploitation mitigation techniques (e.g., ASLR, stack canaries) for the Django/React stack.", covered_by_other_reg=[], recommendation="Document and accept as part of the technical documentation process.", priority="P3", layer0_refs=["SubHM/D-07.2.md §1 CRDA"]>

## Rationale
TinyTask Lda. is subject to the Cyber Resilience Act (CRA) because it acts as a manufacturer of digital products placed on the EU market, as evidenced by its architecture and product deployment strategy (`DOC04:ARCH-07`). The company's role as a 'manufacturer' triggers essential cybersecurity requirements under Annex I, specifically regarding vulnerability handling (Art. 14) and secure design (Art. 13). This applicability is further supported by the P1B-LLM-01 interpretation confirming the manufacturer status.

---

## Status
- applicable: YES
- confidence: HIGH

## Findings
- <implication: IMP-D-01.1-1, Requirement to ensure encryption of personal data at rest within AWS RDS and S3 buckets to satisfy Art. 32(1)(b), effort_estimate: hours to days, dependencies: [], layer0_refs: [SubDomains/D-01.1.md §1 CRDA], company_fact_refs: [DOC04:STORE-01]>
- <implication: IMP-D-01.2-1, Requirement to maintain TLS 1.2+ for all data in transit between the web application and external services like Stripe or Auth0, effort_estimate: hours, dependencies: [], layer0_refs: [SubDomains/D-01.2.md §1 HSO], company_fact_refs: [DOC04:FLOW-01, DOC04:CS-03]>
- <implication: IMP-D-06.1-1, Requirement to perform due diligence and maintain records of sufficient guarantees for third-party processors including AWS, Firebase, and Auth0, effort_estimate: days, dependencies: [], layer0_refs: [SubDomains/D-06.1.md §1 HSO], company_fact_refs: [DOC04:CS-01]>
- <implication: IMP-D-09.4-1, Requirement to maintain a Record of Processing Activities (RoPA) covering the identified data flows for customer registration and authentication, effort_estimate: days, dependencies: [], layer0_refs: [SubDomains/D-09.4.md §1 HSO], company_fact_refs: [DOC04:FLOW-01]>
- <gap (if any): GAP-D-09.2, sub_domain_id: D-09.2, coverage_level: PARTIAL, risk_description: No Data Protection Impact Assessment (DPIA) is currently on file despite the processing of personal data via cloud infrastructure, covered_by_other_reg: [], recommendation: address if high risk, priority: P1, layer0_refs: [SubDomains/D-09.2.md §1 HSO]>
- <gap (if any): GAP-D-06.1, sub_domain_id: D-06.1, coverage_level: PARTIAL, risk_description: Lack of a formal sub-processor register for active cloud providers (AWS, Firebase, Auth0), covered_by_other_reg: [], recommendation: address if high risk, priority: P2, layer0_refs: [SubDomains/D-06.1.md §1 HSO]>

## Rationale
GDPR applies to TinyTask Lda. because the company acts as a controller processing personal data (specifically email, name, and password) within the EU jurisdiction (Portugal). The processing occurs via established architectural flows, such as Customer Registration (DOC04:FLOW-01), which utilizes AWS and Firebase infrastructure (DOC04:ARCH-07). Under GDPR Art. 3, the company's presence in the Union and its processing of identifiers for EU data subjects trigger full regulatory obligations. While the company is a micro-enterprise (8 employees), it must implement appropriate technical and organisational measures, such as encryption at rest (D-01.1) and in transit (D-01.2), to satisfy Art. 32 requirements. The applicability is further confirmed by the lack of any active derogations, such as the household exemption (TIPO3-GDPR-HOUSEHOLD), as the company operates a commercial SaaS application.


### P1C-LLM-01-OVERLAP-CLASSIFICATION

_(no LLM response for this spec)_


### P1C-LLM-02-COMPOUND-EVENT

_(no LLM response for this spec)_


### P1C-LLM-03-STRATEGIC-SYNTHESIS

_(no LLM response for this spec)_
