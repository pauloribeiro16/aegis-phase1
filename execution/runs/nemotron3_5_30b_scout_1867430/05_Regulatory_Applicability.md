---
document_id: AEGIS-P1-05
title: Regulatory Applicability Assessment
phase: 1
version: 1.1
created: "2026-09-02T04:15:19Z"
updated: "2026-09-02T04:15:19Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, ../00_COMMON/01_Company_Context.md, 00_Taxonomy_Reference.md]
outputs: [06_Clause_Mapping_Matrix.xlsx, 07_Structured_Compliance_Matrix.md, 08_Obligation_Derivation.md]
applicable_regs: [CRA, GDPR]
related_documents: [../../../00_METHODOLOGY/PHASE1_STRATEGY.md, "../../../00_METHODOLOGY/PHASE1_STRATEGY.md#filter-1-regulation-applicability-binary-predicates", 00_Taxonomy_Reference.md]
traceability: AEGIS Class Model → ComplianceContext, RegulatoryClause, DomainCoverageEntry
generated_at: "2026-09-02T04:15:19Z"
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

The DPO function within a consolidated role structure creates a dual-role dynamic that influences data protection prioritization alongside operational demands. Engineering delivers encryption-at-rest and in-transit controls per CAP-D01-001 and CAP-D01-002, while Operations manages data retention, deletion, and forensic evidence capture per CAP-D01-004 and CAP-D04-005. Governance drives regulator notification and liaison per CAP-D04-003, with CISO providing risk context. Role consolidation affects time-to-compliance, and shared function ownership shapes cost of compliance, positioning the framework within a SI-000 (—, LOW) impact baseline.


### 6.1b Per-Regulation Rationale (LLM-02 RATIONALE)
Per-regulation rationale + implications + gaps. Generated by P1B-LLM-02 RATIONALE. Cross-references Doc 04 facts + Regulatory Baseline articles. NO boilerplate (per-validation invariant).
*Source: P1B-LLM-02 RATIONALE | multi-call concat (one section per applicable regulation, separated by `---`)*

## Status
- applicable: YES
- confidence: HIGH

## Findings
- id: IMP-D-04.3-01
  description: CRA Art. 14(1) requires reporting to ENISA within 24h of awareness of actively exploited vulnerability (AEV). For TinyTask, this means implementing monitoring mechanisms to detect and report actively exploited vulnerabilities in CRA-classified products.
  effort_estimate: hours to days (MICRO tier)
  dependencies: []
  layer0_refs: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA
  company_fact_refs: DOC04:ARCH-01 systems, DOC04:SEC-01 security posture
- id: IMP-D-02.3-01
  description: CRA Art. 15 allows voluntary reporting to ENISA for vulnerabilities not yet actively exploited. If TinyTask runs active vulnerability management, they can/should report pre-exploitation vulnerabilities to ENISA.
  effort_estimate: hours to days (MICRO tier)
  dependencies: [IMP-D-04.3-01]
  layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO
  company_fact_refs: DOC04:SEC-02 vulnerability management, DOC04:ARCH-03 tech stack
- id: IMP-D-01.1-01
  description: CRA requires confidentiality of data at rest protected by encrypting relevant data using state-of-the-art mechanisms (Annex I Part I (2)(e)). For TinyTask's products storing personal data (STORE-01, STORE-02), encryption with appropriate key custody is required.
  effort_estimate: hours to days (MICRO tier)
  dependencies: []
  layer0_refs: SubDomains/D-01_Fundamental-Security-Objectives/D-01.1.md
  company_fact_refs: DOC04:ARCH-07 data stores, DOC04:SEC-03 encryption at rest
- id: IMP-D-01.2-01
  description: CRA requires confidentiality of data in transit protected by encrypting relevant data using state-of-the-art mechanisms, with attack-surface-limitation leg constraining exposed interfaces (Annex I Part I (2)(j)). For TinyTask's data flows (FLOW-01, FLOW-02, FLOW-03), TLS encryption and interface hardening are required.
  effort_estimate: hours to days (MICRO tier)
  dependencies: [IMP-D-01.1-01]
  layer0_refs: SubDomains/D-01_Fundamental-Security-Objectives/D-01.2.md
  company_fact_refs: DOC04:ARCH-01 data flows, DOC04:SEC-04 encryption in transit
- id: IMP-D-02.1-01
  description: CRA requires identifying and documenting vulnerabilities on a continuing basis, including via SBOM (Annex I Part I (2)(a) and Part II (1)). For TinyTask, this means maintaining a vulnerability register and SBOM for product components.
  effort_estimate: hours to days (MICRO tier)
  dependencies: [IMP-D-01.1-01, IMP-D-01.2-01]
  layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.1.md
  company_fact_refs: DOC04:SEC-05 SBOM status, DOC04:ARCH-03 tech stack
- gap: GAP-D-02.2-01, D-02.2, PARTIAL, "TinyTask may not have formal security update distribution processes. Unpatched vulnerabilities could persist, exposing users to known risks.", ["CRA Art. 13(6)-(9)"], "document and accept (MICRO tier: LOW)", P2, SubDomains/D-02_Vulnerability-Management/D-02.2.md
- gap: GAP-D-02.4-01, D-02.4, NOT_ADDRESSED, "TinyTask lacks formal threat-led penetration testing. Unknown security weaknesses in the product could remain undetected.", ["CRA Art. 13(7)-(8)", "Annex VIII Part II (8)"], "document and accept (MICRO tier: LOW)", P3, SubDomains/D-02_Vulnerability-Management/D-02.4.md
- gap: GAP-D-05.2-01, D-05.2, PARTIAL, "TinyTask may not have formal 10-year update-availability tail for security updates. Update artefacts beyond the support period may not be maintained.", ["CRA Art. 13(9)", "Art. 13(18)", "Art. 13(19)"], "document and accept (MICRO tier: LOW)", P3, SubDomains/D-05_Retention-and-Archiving/D-05.2.md
- gap: GAP-D-08.1-01, D-08.1, NOT_ADDRESSED, "TinyTask has not shipped detailed user-facing secure-use instructions with the product. Users may lack guidance on secure product operation.", ["CRA Annex II §8(a)-(f)", "Art. 13(18)"], "document and accept (MICRO tier: LOW)", P3, SubDomains/D-08_General-Security-Awareness/D-08.1.md

## Rationale
CRA applies to TinyTask Lda. because the company acts as a manufacturer placing products with digital elements on the EU market (CRA Art. 2). TinyTask's product portfolio includes a main SaaS application (SYS-01) and identity service (SYS-02) hosted on AWS eu-west-1, which qualify as products with digital elements under CRA Art. 2(1). The company's role as manufacturer is confirmed by role_matrix.cra.role = "manufacturer" and the declaration that TinyTask places digital products on the EU market. As a MICRO-scale enterprise with 8 employees (scale = "MICRO"), TinyTask must comply with CRA's essential cybersecurity requirements, though implementation should be proportionate to the company's size and resources. Key CRA obligations triggered include AEV notification under Art. 14(1) (24h to ENISA for actively exploited vulnerabilities) and voluntary vulnerability reporting under Art. 15. The company's architecture—AWS hosting, Auth0 identity management, Stripe payment processing—creates multiple CRA applicability points, particularly for data-at-rest encryption (Annex I Part I (2)(e)), data-in-transit encryption (Annex I Part I (2)(j)), and vulnerability identification (Annex I Part I (2)(a) and Part II (1)). DOC04 facts confirming applicability: company role as manufacturer (role_matrix.cra.role = "manufacturer"), placing digital products on EU market (applicable_regs includes CRA), and MICRO scale (employees = 8, scale = "MICRO").

---

## Status
- applicable: YES
- confidence: HIGH

## Findings

### Implications
- implication: IMP-GDPR-01
  description: GDPR Art. 32(1)(b) requires appropriate technical and organisational measures for security of processing, including encryption, pseudonymisation, and resilience of processing systems.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Foundational security measures
  layer0_refs: SubDomains/D-01.1.md §1 CRDA
  company_fact_refs: DOC04:ARCH-01 SYS-01 web application on AWS eu-west-1 with AES-256 encryption at rest

- implication: IMP-GDPR-02
  description: GDPR Art. 33(1) requires 72-hour notification to the supervisory authority upon becoming aware of a personal data breach.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Incident detection and reporting capability
  layer0_refs: SubDomains/D-04.1.md §1 CRDA
  company_fact_refs: DOC04:SEC-01 incident response capability (currently PARTIAL per implementation_readiness)

- implication: IMP-GDPR-03
  description: GDPR Art. 35(1) requires DPIA before processing likely to result in high risk to rights and freedoms of data subjects.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Identification of high-risk processing operations
  layer0_refs: SubDomains/D-04.3.md §1 CRDA
  company_fact_refs: DOC04:SEC-02 DPIA status (not yet conducted; gap identified in NA-02)

- implication: IMP-GDPR-04
  description: GDPR Art. 30(1) requires maintenance of RoPA with 7-item content list for controller, including writing/electronic form and on-supervisory-authority-request access.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Documentation setup and maintenance
  layer0_refs: SubDomains/D-09.4.md §1 CRDA
  company_fact_refs: DOC04:ARCH-03 RoPA status (not yet established; gap to be addressed)

- implication: IMP-GDPR-05
  description: GDPR Art. 5(1)(c) requires data minimisation - personal data limited to what is adequate, relevant, and necessary in relation to processing purposes.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Data category assessment and documentation
  layer0_refs: SubDomains/D-05.1.md §1 CRDA
  company_fact_refs: DOC04:DATA-01 data categories (email, name, password for SYS-01 registration; payment metadata for FLOW-03 Stripe processing)

- implication: IMP-GDPR-06
  description: GDPR Art. 25(1)/(2) requires privacy by design and by default in processing systems, including by-default minimal data collection, minimal access, minimal storage periods, and minimal scope of processing.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Architectural integration of privacy measures into SaaS platform
  layer0_refs: SubDomains/D-07.1.md §1 CRDA
  company_fact_refs: DOC04:ARCH-01 SYS-01 design, DOC04:ARCH-02 SYS-02 identity provider design with Auth0

- implication: IMP-GDPR-07
  description: GDPR Art. 39(1)(a)+(b) requires DPO to inform, advise controller/processor, and monitor compliance including awareness-raising and training of staff involved in processing.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: DPO appointment and operationalisation
  layer0_refs: SubDomains/D-08.1.md §1 CRDA
  company_fact_refs: DOC04:IMP-01 DPO status (currently NO per implementation_readiness; company has 8 employees, MICRO scale)

### Gaps
- gap: GAP-GDPR-DPIA
  gap_id: GAP-GDPR-DPIA
  sub_domain_id: D-04.3
  coverage_level: NOT_ADDRESSED
  risk_description: No DPIA conducted despite systematic large-scale monitoring of EU data subjects; severity HIGH per negative analysis NA-02
  covered_by_other_reg: []
  recommendation: document and accept (LOW tier proportionality)
  priority: P2
  layer0_refs: SubDomains/D-04.3.md §2 HSO

- gap: GAP-GDPR-SUBPROCESSOR
  gap_id: GAP-GDPR-SUBPROCESSOR
  sub_domain_id: D-06.1
  coverage_level: NOT_ADDRESSED
  risk_description: No formal sub-processor register despite 3 cloud providers (AWS, Stripe, Auth0) processing personal data; severity MEDIUM per negative analysis NA-03
  covered_by_other_reg: []
  recommendation: document and accept (LOW tier proportionality)
  priority: P3
  layer0_refs: SubDomains/D-06.1.md §1 CRDA

## Rationale
TinyTask Lda. is a MICRO-scale SaaS provider (8 employees, €2M revenue) incorporated as a Private Limited Company (Lda.) in Portugal (EU), operating in the Technology/Software sector. The company processes personal data as a GDPR controller through its SaaS platform (SYS-01, STORE-01, SYS-02), which include customer registration (FLOW-01: email, name, password), authentication (FLOW-02: email, password), payment processing (FLOW-03: payment metadata), and monitoring telemetry (FLOW-04: telemetry). The company's architecture consists of a main SaaS application on AWS eu-west-1 (SYS-01), an identity service using Auth0 (SYS-02), cloud infrastructure on AWS (SYS-03), a key management service using AWS KMS (SYS-04), and monitoring/logging via Datadog (SYS-05). Personal data is stored in STORE-01 (postgres, AWS RDS eu-west-1, AES-256 encryption, 2555-day retention) and STORE-02 (S3, AES-256 encryption, 90-day retention). As a GDPR controller with establishment in the EU (Portugal) processing EU data subjects' personal data, the regulation applies pursuant to Art. 3(1) territorial scope and Art. 3(2) material scope. The controller role triggers obligations under GDPR Art. 5(1) processing principles (lawfulness, fairness, transparency, purpose limitation, data minimisation, accuracy, storage limitation), Art. 32(1) security of processing, Art. 33(1) 72-hour breach notification to the supervisory authority, Art. 34(1) high-risk breach communication to data subjects, and Art. 30(1) maintenance of RoPA. The MICRO scale (8 employees) means proportionality applies per AEGIS methodology, with effort estimates scaled to hours-to-days rather than weeks or FTE-quarters. The company's negative analysis NA-02 identifies absence of DPIA despite systematic monitoring, and NA-03 identifies missing sub-processor register despite 3 cloud providers processing personal data, representing current compliance gaps.

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

## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-CRA-ART14-DUAL-FLOW, YES: Company is a manufacturer (role_matrix.cra.role = "manufacturer") placing digital products on the EU market; CRA Art. 14(1) requires 24h AEV reporting to ENISA upon awareness of actively exploited vulnerabilities, and Art. 14(2) requires user notification if material impact occurs. The company's architecture includes multiple systems (SaaS application, identity provider, cloud infrastructure, KMS, monitoring & logging) that could experience vulnerabilities requiring AEV reporting.
- TIPO2-CRA-ART15-VOLUNTARY, YES: Company places digital products on the EU market (places_digital_products_eu = true, per regulatory applicability_predicates); as a manufacturer, CRA Art. 15 allows voluntary reporting to ENISA for vulnerabilities not yet actively exploited. Given the company's partial vulnerability management readiness (security_fte = 0.85, vulnerability_management = PARTIAL), voluntary reporting under Art. 15 is relevant for identifying and addressing vulnerabilities before they become actively exploited.

## Derogations
- TIPO3-CRA-NON-PLACED, NOT_ACTIVATED: Company places digital products on the EU market (places_digital_products_eu = true), so CRA Art. 2 exclusion (products not placed on EU market) does not apply. TinyTask's SaaS application is clearly placed on the EU market as a commercial provider.
- TIPO3-CRA-OPEN-SOURCE, INDETERMINATE: Cannot evaluate predicate due to missing facts (software_licence and commercial_purpose not explicitly provided in Doc 04). Company operates as a commercial SaaS provider (Lda., private limited company), but without explicit documentation of the software licence (e.g., OSS, GPL, Apache-2.0, MIT) and whether commercial_purpose is True or False, the CRA Recital 18 exclusion for non-commercial open-source software cannot be confirmed or refuted. Per CRA Recital 18, commercial OSS (e.g., Red Hat model) is in scope while pure OSS without commercial purpose is out of scope.

## Rationale
TinyTask Lda. is a MICRO-scale technology/software company based in Portugal (EU), classified as a GDPR controller and CRA manufacturer. The company places digital products on the EU market including a SaaS application, identity service, cloud infrastructure, KMS, and monitoring & logging systems. The company processes EU personal data through its SaaS platform and has three cloud providers (AWS, Stripe, Auth0) processing personal data. Regarding Tipo 2 interpretations, TIPO2-CRA-ART14-DUAL-FLOW applies because the company's role for CRA is "manufacturer" (role_matrix.cra.role = "manufacturer"). As a manufacturer placing digital products on the EU market, CRA Art. 14(1) imposes a 24-hour AEV reporting obligation to ENISA upon awareness of actively exploited vulnerabilities, and Art. 14(2) requires user notification if material impact occurs. The company's architecture includes multiple systems (SaaS application, identity provider, cloud infrastructure, KMS, monitoring & logging) that could experience vulnerabilities requiring AEV reporting. TIPO2-CRA-ART15-VOLUNTARY applies because the company places digital products on the EU market, making CRA Art. 15's voluntary pre-exploitation vulnerability reporting applicable. Given the company's partial vulnerability management readiness (security_fte = 0.85, vulnerability_management = PARTIAL), voluntary reporting under Art. 15 is relevant for identifying and addressing vulnerabilities before they become actively exploited. Regarding Tipo 3 derogations, TIPO3-CRA-NON-PLACED is NOT_ACTIVATED because the company places digital products on the EU market (places_digital_products_eu = true). CRA Art. 2 excludes products not placed on the EU market, but TinyTask's SaaS application is clearly placed on the EU market. TIPO3-CRA-OPEN-SOURCE is INDETERMINATE because the software licence and commercial purpose fields are not explicitly provided in Doc 04. The company is a commercial SaaS provider (Lda., private limited company), but without explicit documentation of the software licence and whether commercial_purpose is True or False, the CRA Recital 18 exclusion for non-commercial open-source software cannot be confirmed or refuted. Per CRA Recital 18, commercial OSS (e.g., Red Hat model) is in scope while pure OSS without commercial purpose is out of scope.

---

## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-GDPR-RTS-DEADLINES (NO): The company's sector Technology/Software is not in the health/energy/transport/digital_infrastructure list required by the activation predicate "company_facts.sector in ['health', 'energy', 'transport', 'digital_infrastructure']"; company_facts.sector = "Technology/Software" evaluates to FALSE, so the interpretation does not activate.

## Derogations
- TIPO3-GDPR-HOUSEHOLD (NOT_ACTIVATED): TinyTask Lda. is a commercial SaaS provider in the Technology/Software sector, incorporated as a Private Limited Company (Lda.) in Portugal (EU) with 8 employees and €2M revenue. The company processes personal data as a GDPR controller through its SaaS platform (SYS-01, STORE-01, SYS-02), which is not a "purely personal or household" activity under GDPR Art. 2(2)(c). The activation predicate "company_facts.processing_scope == 'purely_personal_or_household'" evaluates to FALSE.

## Rationale

The company TinyTask Lda. operates as a commercial SaaS provider delivering a web application and identity service through AWS, Firebase, and Stripe infrastructure. As a GDPR controller (role_matrix.gdpr.role = "controller"), the company processes EU personal data through its primary SaaS application (SYS-01) storing customer data in PostgreSQL (STORE-01) and backups in S3 (STORE-02). The company's scale is MICRO with complexity tier LOW.

Regarding TIPO2-GDPR-RTS-DEADLINES, the activation predicate requires the company's sector to be among health, energy, transport, or digital_infrastructure. The company's sector is classified as "Technology/Software", which does not match any of the predicate values. While GDPR Art. 33(1) establishes the 72-hour breach notification deadline for all controllers regardless of sector, the Tipo 2 interpretation specifically gates applicability on the sector filter. Since the company's sector falls outside the predicate's scope, the interpretation is marked not applicable. The layer0_ref SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA confirms the CRDA cross-regulation deep analysis context for incident response obligations.

Regarding TIPO3-GDPR-HOUSEHOLD, the activation predicate checks whether processing_scope equals 'purely_personal_or_household'. GDPR Art. 2(2)(c) excludes processing by a natural person in the course of a purely personal or household activity from GDPR scope. TinyTask Lda., as a Private Limited Company operating in the Technology/Software sector with a commercial SaaS product, clearly does not conduct purely personal or household processing. The company's data flows (FLOW-01 through FLOW-05) involve customer registration, authentication, payment processing, monitoring telemetry, and backup operations all conducted on a commercial basis. The company's role as controller (role_matrix.gdpr.role = "controller") with inherited obligations including Article 30 records of processing, Article 32 security of processing, Article 33 breach notification, and Article 35 DPIA (when high-risk) further confirms commercial, not personal/household, data processing. The layer0_ref SubDomains/D-09_Governance-Documentation/D-09.1.md §2 HSO provides the governance documentation context for this household activity exclusion.

No other Tipo 2 or Tipo 3 entries apply to GDPR for this company, as the remaining entries are scoped to CRA, DORA, NIS2, or AI_Act, and the company's applicable_regs list contains only GDPR and CRA (with CRA analyzed separately).


### P1B-LLM-02-RATIONALE

## Status
- applicable: YES
- confidence: HIGH

## Findings
- id: IMP-D-04.3-01
  description: CRA Art. 14(1) requires reporting to ENISA within 24h of awareness of actively exploited vulnerability (AEV). For TinyTask, this means implementing monitoring mechanisms to detect and report actively exploited vulnerabilities in CRA-classified products.
  effort_estimate: hours to days (MICRO tier)
  dependencies: []
  layer0_refs: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA
  company_fact_refs: DOC04:ARCH-01 systems, DOC04:SEC-01 security posture
- id: IMP-D-02.3-01
  description: CRA Art. 15 allows voluntary reporting to ENISA for vulnerabilities not yet actively exploited. If TinyTask runs active vulnerability management, they can/should report pre-exploitation vulnerabilities to ENISA.
  effort_estimate: hours to days (MICRO tier)
  dependencies: [IMP-D-04.3-01]
  layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO
  company_fact_refs: DOC04:SEC-02 vulnerability management, DOC04:ARCH-03 tech stack
- id: IMP-D-01.1-01
  description: CRA requires confidentiality of data at rest protected by encrypting relevant data using state-of-the-art mechanisms (Annex I Part I (2)(e)). For TinyTask's products storing personal data (STORE-01, STORE-02), encryption with appropriate key custody is required.
  effort_estimate: hours to days (MICRO tier)
  dependencies: []
  layer0_refs: SubDomains/D-01_Fundamental-Security-Objectives/D-01.1.md
  company_fact_refs: DOC04:ARCH-07 data stores, DOC04:SEC-03 encryption at rest
- id: IMP-D-01.2-01
  description: CRA requires confidentiality of data in transit protected by encrypting relevant data using state-of-the-art mechanisms, with attack-surface-limitation leg constraining exposed interfaces (Annex I Part I (2)(j)). For TinyTask's data flows (FLOW-01, FLOW-02, FLOW-03), TLS encryption and interface hardening are required.
  effort_estimate: hours to days (MICRO tier)
  dependencies: [IMP-D-01.1-01]
  layer0_refs: SubDomains/D-01_Fundamental-Security-Objectives/D-01.2.md
  company_fact_refs: DOC04:ARCH-01 data flows, DOC04:SEC-04 encryption in transit
- id: IMP-D-02.1-01
  description: CRA requires identifying and documenting vulnerabilities on a continuing basis, including via SBOM (Annex I Part I (2)(a) and Part II (1)). For TinyTask, this means maintaining a vulnerability register and SBOM for product components.
  effort_estimate: hours to days (MICRO tier)
  dependencies: [IMP-D-01.1-01, IMP-D-01.2-01]
  layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.1.md
  company_fact_refs: DOC04:SEC-05 SBOM status, DOC04:ARCH-03 tech stack
- gap: GAP-D-02.2-01, D-02.2, PARTIAL, "TinyTask may not have formal security update distribution processes. Unpatched vulnerabilities could persist, exposing users to known risks.", ["CRA Art. 13(6)-(9)"], "document and accept (MICRO tier: LOW)", P2, SubDomains/D-02_Vulnerability-Management/D-02.2.md
- gap: GAP-D-02.4-01, D-02.4, NOT_ADDRESSED, "TinyTask lacks formal threat-led penetration testing. Unknown security weaknesses in the product could remain undetected.", ["CRA Art. 13(7)-(8)", "Annex VIII Part II (8)"], "document and accept (MICRO tier: LOW)", P3, SubDomains/D-02_Vulnerability-Management/D-02.4.md
- gap: GAP-D-05.2-01, D-05.2, PARTIAL, "TinyTask may not have formal 10-year update-availability tail for security updates. Update artefacts beyond the support period may not be maintained.", ["CRA Art. 13(9)", "Art. 13(18)", "Art. 13(19)"], "document and accept (MICRO tier: LOW)", P3, SubDomains/D-05_Retention-and-Archiving/D-05.2.md
- gap: GAP-D-08.1-01, D-08.1, NOT_ADDRESSED, "TinyTask has not shipped detailed user-facing secure-use instructions with the product. Users may lack guidance on secure product operation.", ["CRA Annex II §8(a)-(f)", "Art. 13(18)"], "document and accept (MICRO tier: LOW)", P3, SubDomains/D-08_General-Security-Awareness/D-08.1.md

## Rationale
CRA applies to TinyTask Lda. because the company acts as a manufacturer placing products with digital elements on the EU market (CRA Art. 2). TinyTask's product portfolio includes a main SaaS application (SYS-01) and identity service (SYS-02) hosted on AWS eu-west-1, which qualify as products with digital elements under CRA Art. 2(1). The company's role as manufacturer is confirmed by role_matrix.cra.role = "manufacturer" and the declaration that TinyTask places digital products on the EU market. As a MICRO-scale enterprise with 8 employees (scale = "MICRO"), TinyTask must comply with CRA's essential cybersecurity requirements, though implementation should be proportionate to the company's size and resources. Key CRA obligations triggered include AEV notification under Art. 14(1) (24h to ENISA for actively exploited vulnerabilities) and voluntary vulnerability reporting under Art. 15. The company's architecture—AWS hosting, Auth0 identity management, Stripe payment processing—creates multiple CRA applicability points, particularly for data-at-rest encryption (Annex I Part I (2)(e)), data-in-transit encryption (Annex I Part I (2)(j)), and vulnerability identification (Annex I Part I (2)(a) and Part II (1)). DOC04 facts confirming applicability: company role as manufacturer (role_matrix.cra.role = "manufacturer"), placing digital products on EU market (applicable_regs includes CRA), and MICRO scale (employees = 8, scale = "MICRO").

---

## Status
- applicable: YES
- confidence: HIGH

## Findings

### Implications
- implication: IMP-GDPR-01
  description: GDPR Art. 32(1)(b) requires appropriate technical and organisational measures for security of processing, including encryption, pseudonymisation, and resilience of processing systems.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Foundational security measures
  layer0_refs: SubDomains/D-01.1.md §1 CRDA
  company_fact_refs: DOC04:ARCH-01 SYS-01 web application on AWS eu-west-1 with AES-256 encryption at rest

- implication: IMP-GDPR-02
  description: GDPR Art. 33(1) requires 72-hour notification to the supervisory authority upon becoming aware of a personal data breach.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Incident detection and reporting capability
  layer0_refs: SubDomains/D-04.1.md §1 CRDA
  company_fact_refs: DOC04:SEC-01 incident response capability (currently PARTIAL per implementation_readiness)

- implication: IMP-GDPR-03
  description: GDPR Art. 35(1) requires DPIA before processing likely to result in high risk to rights and freedoms of data subjects.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Identification of high-risk processing operations
  layer0_refs: SubDomains/D-04.3.md §1 CRDA
  company_fact_refs: DOC04:SEC-02 DPIA status (not yet conducted; gap identified in NA-02)

- implication: IMP-GDPR-04
  description: GDPR Art. 30(1) requires maintenance of RoPA with 7-item content list for controller, including writing/electronic form and on-supervisory-authority-request access.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Documentation setup and maintenance
  layer0_refs: SubDomains/D-09.4.md §1 CRDA
  company_fact_refs: DOC04:ARCH-03 RoPA status (not yet established; gap to be addressed)

- implication: IMP-GDPR-05
  description: GDPR Art. 5(1)(c) requires data minimisation - personal data limited to what is adequate, relevant, and necessary in relation to processing purposes.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Data category assessment and documentation
  layer0_refs: SubDomains/D-05.1.md §1 CRDA
  company_fact_refs: DOC04:DATA-01 data categories (email, name, password for SYS-01 registration; payment metadata for FLOW-03 Stripe processing)

- implication: IMP-GDPR-06
  description: GDPR Art. 25(1)/(2) requires privacy by design and by default in processing systems, including by-default minimal data collection, minimal access, minimal storage periods, and minimal scope of processing.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: Architectural integration of privacy measures into SaaS platform
  layer0_refs: SubDomains/D-07.1.md §1 CRDA
  company_fact_refs: DOC04:ARCH-01 SYS-01 design, DOC04:ARCH-02 SYS-02 identity provider design with Auth0

- implication: IMP-GDPR-07
  description: GDPR Art. 39(1)(a)+(b) requires DPO to inform, advise controller/processor, and monitor compliance including awareness-raising and training of staff involved in processing.
  effort_estimate: hours to days (LOW tier, MICRO company)
  dependencies: DPO appointment and operationalisation
  layer0_refs: SubDomains/D-08.1.md §1 CRDA
  company_fact_refs: DOC04:IMP-01 DPO status (currently NO per implementation_readiness; company has 8 employees, MICRO scale)

### Gaps
- gap: GAP-GDPR-DPIA
  gap_id: GAP-GDPR-DPIA
  sub_domain_id: D-04.3
  coverage_level: NOT_ADDRESSED
  risk_description: No DPIA conducted despite systematic large-scale monitoring of EU data subjects; severity HIGH per negative analysis NA-02
  covered_by_other_reg: []
  recommendation: document and accept (LOW tier proportionality)
  priority: P2
  layer0_refs: SubDomains/D-04.3.md §2 HSO

- gap: GAP-GDPR-SUBPROCESSOR
  gap_id: GAP-GDPR-SUBPROCESSOR
  sub_domain_id: D-06.1
  coverage_level: NOT_ADDRESSED
  risk_description: No formal sub-processor register despite 3 cloud providers (AWS, Stripe, Auth0) processing personal data; severity MEDIUM per negative analysis NA-03
  covered_by_other_reg: []
  recommendation: document and accept (LOW tier proportionality)
  priority: P3
  layer0_refs: SubDomains/D-06.1.md §1 CRDA

## Rationale
TinyTask Lda. is a MICRO-scale SaaS provider (8 employees, €2M revenue) incorporated as a Private Limited Company (Lda.) in Portugal (EU), operating in the Technology/Software sector. The company processes personal data as a GDPR controller through its SaaS platform (SYS-01, STORE-01, SYS-02), which include customer registration (FLOW-01: email, name, password), authentication (FLOW-02: email, password), payment processing (FLOW-03: payment metadata), and monitoring telemetry (FLOW-04: telemetry). The company's architecture consists of a main SaaS application on AWS eu-west-1 (SYS-01), an identity service using Auth0 (SYS-02), cloud infrastructure on AWS (SYS-03), a key management service using AWS KMS (SYS-04), and monitoring/logging via Datadog (SYS-05). Personal data is stored in STORE-01 (postgres, AWS RDS eu-west-1, AES-256 encryption, 2555-day retention) and STORE-02 (S3, AES-256 encryption, 90-day retention). As a GDPR controller with establishment in the EU (Portugal) processing EU data subjects' personal data, the regulation applies pursuant to Art. 3(1) territorial scope and Art. 3(2) material scope. The controller role triggers obligations under GDPR Art. 5(1) processing principles (lawfulness, fairness, transparency, purpose limitation, data minimisation, accuracy, storage limitation), Art. 32(1) security of processing, Art. 33(1) 72-hour breach notification to the supervisory authority, Art. 34(1) high-risk breach communication to data subjects, and Art. 30(1) maintenance of RoPA. The MICRO scale (8 employees) means proportionality applies per AEGIS methodology, with effort estimates scaled to hours-to-days rather than weeks or FTE-quarters. The company's negative analysis NA-02 identifies absence of DPIA despite systematic monitoring, and NA-03 identifies missing sub-processor register despite 3 cloud providers processing personal data, representing current compliance gaps.


### P1C-LLM-01-OVERLAP-CLASSIFICATION

_(no LLM response for this spec)_


### P1C-LLM-02-COMPOUND-EVENT

_(no LLM response for this spec)_


### P1C-LLM-03-STRATEGIC-SYNTHESIS

_(no LLM response for this spec)_
