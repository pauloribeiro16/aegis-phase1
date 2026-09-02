---
document_id: AEGIS-P1-05
title: Regulatory Applicability Assessment
phase: 1
version: 1.1
created: "2026-09-01T16:13:55Z"
updated: "2026-09-01T16:13:55Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, ../00_COMMON/01_Company_Context.md, 00_Taxonomy_Reference.md]
outputs: [06_Clause_Mapping_Matrix.xlsx, 07_Structured_Compliance_Matrix.md, 08_Obligation_Derivation.md]
applicable_regs: [CRA, GDPR]
related_documents: [../../../00_METHODOLOGY/PHASE1_STRATEGY.md, "../../../00_METHODOLOGY/PHASE1_STRATEGY.md#filter-1-regulation-applicability-binary-predicates", 00_Taxonomy_Reference.md]
traceability: AEGIS Class Model → ComplianceContext, RegulatoryClause, DomainCoverageEntry
generated_at: "2026-09-01T16:13:55Z"
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

Control SI-000, while rated LOW and unassigned to any single canonical function, warrants dual-role analysis because its foundational nature implies overlapping ownership across Governance, Operations, Engineering, CISO, and DPO—each of which must validate distinct compliance artifacts for the same control baseline. Time-to-compliance should be prioritized in a phased sequence: Governance establishes the policy framework first, followed by Engineering implementing technical baselines, with CISO validating cryptographic posture before DPO attests to data protection alignment. The cost of compliance is disproportionately low relative to high-priority controls, yet deferring implementation carries latent regulatory risk if SI-000 represents a prerequisite dependency for higher-tier requirements such as CAP-D01-series obligations. Given its cross-functional applicability and LOW severity rating, the strategic recommendation is to treat SI-000 as an enabling control rather than a standalone deliverable, integrating it into existing operational workflows to avoid siloed investment while ensuring no downstream governance gap emerges when higher-rated controls activate.


### 6.1b Per-Regulation Rationale (LLM-02 RATIONALE)
Per-regulation rationale + implications + gaps. Generated by P1B-LLM-02 RATIONALE. Cross-references Doc 04 facts + Regulatory Baseline articles. NO boilerplate (per-validation invariant).
*Source: P1B-LLM-02 RATIONALE | multi-call concat (one section per applicable regulation, separated by `---`)*

## Status
- applicable: YES
- confidence: HIGH

## Findings
- **implication**: id=IMP-CRA-ART14-DUAL-FLOW, description=CRA Art. 14(1) requires the manufacturer to notify ENISA within 24 hours of awareness of an actively exploited vulnerability; CRA Art. 14(2) additionally requires user notification in machine-readable format when material impact exists on users or third parties. TinyTask must operate a dual-reporting pipeline: internal detection → 24h escalation → parallel reporting to ENISA (via single platform per Art. 16) and, where material impact is confirmed, direct user notification. effort_estimate=hours-to-days, dependencies=[NA-05 no CRA incident response playbook], layer0_refs=["SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA"], company_fact_refs=["DOC04:ARCH-07 product processes EU personal data", "DOC04:SEC-NN manufacturer role"]
- **implication**: id=IMP-CRA-ART15-VOLUNTARY, description=CRA Art. 15 allows voluntary reporting of pre-exploitation vulnerabilities to ENISA/CSIRT via the single platform; TinyTask may choose to report discovered-but-not-yet-exploited vulnerabilities proactively. This is optional but recommended as a trust-building measure with no liability exposure (Art. 17(4) shield). effort_estimate=hours, dependencies=[], layer0_refs=["SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO"], company_fact_refs=["DOC04:ARCH-07 product processes EU personal data"]
- **gap**: gap_id=GAP-CRA-CONFORMITY-ASSESSMENT, sub_domain_id=D-09.1, coverage_level=NOT_ADDRESSED, risk_description=CRA Annex VIII requires conformity assessment (Module B+C or H for Class I products) with technical documentation per Annex VII §2–§8 before placing on the market; no formal programme is in place at TinyTask. This is a HIGH-severity gap (NA-01). effort_estimate=months, dependencies=[], layer0_refs=["SubDomains/D-09_Governance-Documentation/D-09.1.md §2 HSO"]
- **gap**: gap_id=GAP-CRA-TECHNICAL-DOC, sub_domain_id=D-09.4, coverage_level=NOT_ADDRESSED, risk_description=CRA Art. 36 requires technical documentation (general description, architecture, SBOM, CVD policy, test reports) to be drawn up before market placement and retained for 10 years or support period; no such documentation exists at TinyTask currently. effort_estimate=weeks-to-months, dependencies=[GAP-CRA-CONFORMITY-ASSESSMENT], layer0_refs=["SubDomains/D-09_Governance-Documentation/D-09.4.md §2 HSO"]
- **gap**: gap_id=GAP-CRA-CE-MARKING, sub_domain_id=D-09.4, coverage_level=NOT_ADDRESSED, risk_description=CRA Art. 30 requires CE marking affixed visibly and legibly before placing on the market; for software products this may be on declaration or website per Art. 30(1). No CE marking process is documented at TinyTask. effort_estimate=days-to-weeks, dependencies=[GAP-CRA-TECHNICAL-DOC], layer0_refs=["SubDomains/D-09_Governance-Documentation/D-09.4.md §2 HSO"]
- **gap**: gap_id=GAP-CRA-SUPPORT-PERIOD, sub_domain_id=D-02.2, coverage_level=NOT_ADDRESSED, risk_description=CRA Art. 13(8) requires a minimum 5-year support period with vulnerability handling throughout; Art. 13(9) extends update availability for 10 years from issue date or remainder of support period whichever is longer. TinyTask has no documented support-period determination factors per Annex II §7. effort_estimate=days-to-weeks, dependencies=[], layer0_refs=["SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO"]

## Rationale
TinyTask Lda. is a MICRO-scale Portuguese software company (8 employees, €2M revenue) operating as both GDPR controller and CRA manufacturer for its SaaS products placed on the EU market. The company's architecture—built on AWS eu-west-1 with Auth0 identity management, Stripe payments, and Datadog observability—processes personal data of EU customers through customer registration, authentication, payment processing, monitoring telemetry, and backup operations flows.

The CRA dual-flow interpretation (Art. 14(1) + Art. 14(2)) is directly binding because TinyTask places digital products on the EU market as manufacturer. When an actively exploited vulnerability is detected in any of its five systems (Main SaaS Application, Identity Service, Cloud Infrastructure, Key Management Service, or Monitoring & Logging), the company must notify ENISA within 24 hours via the single reporting platform established under Art. 16. If material impact on users exists—such as a compromise affecting customer authentication through Auth0 or payment processing through Stripe—the manufacturer also has an obligation to notify affected users in machine-readable format per Art. 14(8). The temporal conflict between GDPR's 72-hour breach notification (Art. 33) and CRA's 24-hour vulnerability reporting creates a practical tension: the company must adopt a maximum-SLA workflow where internal escalation within 24 hours satisfies both regimes from a single detection pipeline, as noted in regulatory interaction TI-01.

The voluntary reporting mechanism under CRA Art. 15 is available to TinyTask but not mandatory—it allows proactive disclosure of pre-exploitation vulnerabilities discovered through vulnerability management (currently PARTIAL readiness). Given the company's small team and limited security FTEs (0.85), voluntary reporting can be a strategic trust-building measure with no liability exposure, since Art. 17(4) provides a shield against increased liability for mere notification.

However, several significant gaps remain uncovered by these interpretations. The conformity assessment procedure under CRA Annex VIII is NOT_ADDRESSED: TinyTask has no formal programme in place for Class I products (which require Module B+C or H evaluation), and this represents the highest-severity gap (NA-01). Without a documented technical documentation package per Annex VII §2–§8—including general description, architecture details, SBOM, CVD policy, test reports, and risk-assessment records—the company cannot legally place products on the EU market. The CE marking obligation under Art. 30 is also NOT_ADDRESSED: for software products, this may be affixed to the declaration or website rather than physical media, but no process exists at TinyTask.

The support-period determination (Art. 13(8) minimum 5 years + Art. 13(9) 10-year update tail) is another NOT_ADDRESSED gap: TinyTask has not documented how it will determine the end-date of its support period or communicate this to customers at purchase time per Annex II §7. This affects long-term customer trust and regulatory compliance posture.

These gaps are substantial for a MICRO-scale company but manageable given the existing security readiness (backup=YES, access control=PARTIAL, audit logging=PARTIAL). The effort is tier-appropriate: hours-to-days for operational implications like dual-flow reporting setup, weeks-to-months for documentation buildout, and months for full conformity assessment programme establishment.

---

## Status
- applicable: YES
- confidence: HIGH

## Findings
- **implication**: id=IMP-D-01.1-1, description=Personal data at rest in AWS RDS (AES-256 provider-managed) and S3 backups must be protected against unauthorised access through encryption with appropriate key custody; the controller's Art. 32(1)(b) obligation requires that personal data stored in STORE-01 (primary database, retention 2555 days) and STORE-02 (backup storage, retention 90 days) are processed in a manner ensuring appropriate security including protection against unauthorised or unlawful processing and accidental loss, destruction or damage; the controller must ensure ongoing confidentiality, integrity, availability and resilience of processing systems and services per Art. 32(1)(b); layer0_refs=[SubDomains/D-01.1.md], company_fact_refs=DOC04:ARCH-01 SYS-01, DOC04:ARCH-03 STORE-01
- **implication**: id=IMP-D-01.2-1, description=Personal data transmitted across network paths (customer registration via TLS 1.3, authentication via TLS 1.2+, payment processing via Stripe) must be protected against unauthorised disclosure and alteration through cryptographic confidentiality and integrity controls including mutual authentication; the controller's Art. 32(1)(b)/(2) obligation covers accidental or unlawful destruction, loss, alteration, unauthorised disclosure of, or access to personal data transmitted per the five-event risk enumeration; layer0_refs=[SubDomains/D-01.2.md], company_fact_refs=DOC04:ARCH-05 FLOW-01 through FLOW-03
- **implication**: id=IMP-D-01.3-1, description=Cryptographic keys used for data at rest and in transit must be managed with separation of roles such that possession of key material is not bundled with possession of the operational environment; the controller-side Art. 4(5) de-attribution test requires that additional information required to re-identify data subjects (the cryptographic key, mapping table, or tokenisation seed) is kept separately and subject to appropriate technical and organisational measures preventing attribution per Art. 34(3)(a); layer0_refs=[SubDomains/D-01.3.md], company_fact_refs=DOC04:ARCH-04 SYS-04 AWS KMS
- **implication**: id=IMP-D-01.4-1, description=Personal data must be accurate and where necessary kept up to date; every reasonable step taken to ensure inaccurate personal data is erased or rectified without delay per Art. 5(1)(d); integrity of stored data must be preserved against unauthorised modification across the data lifecycle with corruption detected, logged and reported; layer0_refs=[SubDomains/D-01.4.md], company_fact_refs=DOC04:ARCH-03 STORE-01
- **implication**: id=IMP-D-05.1-1, description=Personal data collected or otherwise acquired must be limited to what is adequate, relevant and necessary in relation to the purpose for which it is processed per Art. 5(1)(c); further processing must be compatible with original purposes per Art. 6(4) compatibility test; special-category data requires an Art. 9(2) basis subject to Art. 9(1) prohibition; by-design and by-default minimisation applied per Art. 25(1)/(2); layer0_refs=[SubDomains/D-05.1.md], company_fact_refs=DOC04:ARCH-01 SYS-01, DOC04:SEC-NN data categories
- **implication**: id=IMP-D-05.3-1, description=Personal data must be erased without undue delay on the data subject's Art. 17(1) request where one of six grounds applies (no longer necessary for original purposes, consent withdrawn with no other basis, objection under Art. 21(1)/(2), unlawful processing, legal-obligation erasure, or information-society-service to a child); on processor contract end the processor must delete or return all personal data per Art. 28(3)(g); layer0_refs=[SubDomains/D-05.3.md], company_fact_refs=DOC04:ARCH-01 SYS-01
- **implication**: id=IMP-D-06.1-1, description=The controller must engage only processors providing sufficient guarantees to implement appropriate technical and organisational measures per Art. 28(1); the four-factor EDPB Guidelines 07/2020 reading (knowledge + reliability of resources + compliance track-record + financial stability) operationalises the sufficient guarantees threshold; sub-processor authorisation chain under Art. 28(2) is material to due diligence; layer0_refs=[SubDomains/D-06.1.md], company_fact_refs=DOC04:ARCH-03 CS-01 AWS, DOC04:ARCH-03 CS-02 Firebase, DOC04:ARCH-03 CS-03 Stripe
- **implication**: id=IMP-D-06.3-1, description=Controller/processor contracts must include the Art. 28(3)(a)-(h) eight-element DPA floor including instruction-bound processing, sub-processor authorisation and change-notification, processor security-measure commitments, audit/inspection access, and contract-end return/deletion; Art. 46 appropriate-safeguards mechanism and Art. 48 international-agreement filter apply where personal data leaves the EEA or is exposed to third-country legal-process pressure; layer0_refs=[SubDomains/D-06.3.md], company_fact_refs=DOC04:ARCH-03 CS-01 through CS-04
- **implication**: id=IMP-D-07.1-1, description=The controller must implement appropriate technical and organisational measures such as pseudonymisation designed to implement data-protection principles in an effective manner per Art. 25(1); by default only personal data necessary for each specific purpose are processed per Art. 25(2); the design anchor is four-factor qualitative proportionality (state of the art, cost of implementation, nature/scope/context/purposes, risks of varying likelihood and severity) per Art. 25(1); layer0_refs=[SubDomains/D-07.1.md], company_fact_refs=DOC04:ARCH-01 SYS-01 through SYS-05
- **implication**: id=IMP-D-09.1-1, description=The controller must implement appropriate technical and organisational measures including policies designed to implement data-protection principles in an effective manner per Art. 24(1); the DPO is the governance anchor (Art. 37-39) with Art. 5(2) accountability burden; management-body approval/oversight/liability architecture applies; layer0_refs=[SubDomains/D-09.1.md], company_fact_refs=DOC04:SEC-NN implementation_readiness information_security_policy=PARTIAL
- **implication**: id=IMP-D-09.4-1, description=Each controller and processor must maintain a record of processing activities under its responsibility per Art. 30(1) in writing or electronic form containing the seven-item content list; records made available to supervisory authority on request per Art. 30(4); subject to Art. 30(5) 250-employee exception (not applicable here as company has 8 employees); layer0_refs=[SubDomains/D-09.4.md], company_fact_refs=DOC04:SEC-NN implementation_readiness audit_logging=PARTIAL
- **implication**: id=IMP-D-10.1-1, description=The controller must implement appropriate technical and organisational measures to ensure ongoing confidentiality, integrity, availability and resilience of processing systems and services per Art. 32(1)(b); personal-data processing systems monitored for five Art. 32(2) risk types; clear definition of moment of becoming aware of a breach anchors the Art. 33(1) 72-hour notification clock; layer0_refs=[SubDomains/D-10.1.md], company_fact_refs=DOC04:ARCH-05 FLOW-04 monitoring telemetry
- **implication**: id=IMP-D-10.2-1, description=Compliance records maintained in writing or electronic form with integrity and traceability sufficient to demonstrate compliance and support supervisory-authority inspections per Art. 30(3) + Art. 5(2); includes records of processing activities, consent records, processor contract records, breach notification records, and DPIA records; layer0_refs=[SubDomains/D-10.2.md], company_fact_refs=DOC04:SEC-NN implementation_readiness audit_logging=PARTIAL
- **implication**: id=IMP-D-10.3-1, description=The controller must implement appropriate technical and organisational measures including a process for regularly testing, assessing and evaluating the effectiveness of technical and organisational measures per Art. 32(1)(d); DPIA reviewed at least when there is change of risk represented by processing operations per Art. 35(11); layer0_refs=[SubDomains/D-10.3.md], company_fact_refs=DOC04:SEC-NN implementation_readiness vulnerability_management=PARTIAL

## Gaps
- **gap**: gap_id=GAP-D-05.2, sub_domain_id=D-05.2, coverage_level=PARTIAL, risk_description=Retention period for application logs (STORE-03) is 30 days; GDPR Art. 5(1)(e) requires personal data kept in identifiable form only as long as necessary for processing purposes; the RoPA must document envisaged time limits for erasure of different categories of data per Art. 30(1)(f); current retention policy may not align with documented necessity assessments, creating a compliance gap where logs containing personal data (if any) are retained beyond what is necessary without documented justification; covered_by_other_reg=[], recommendation=LOW: document and accept the 30-day retention for non-personal application logs while ensuring any personal data in logs is subject to Art. 5(1)(e) necessity boundary with documented retention rationale, priority=P2, layer0_refs=[SubDomains/D-05.2.md]
- **gap**: gap_id=GAP-D-08.1, sub_domain_id=D-08.1, coverage_level=NOT_ADDRESSED, risk_description=No general security awareness training programme is in place; GDPR Art. 39(1)(b) requires the DPO to monitor compliance including awareness-raising and training of staff involved in processing operations; with no CISO (ciso=NO), no DPO (dpo=NO), and no documented security_awareness readiness, there is no evidence that any workforce data-protection awareness programme has been operationally exercised or recorded; covered_by_other_reg=[], recommendation=MEDIUM: address if high risk — establish a minimum baseline training programme covering GDPR obligations for all personnel involved in processing operations with DPO-catalysed governance per Art. 39(1)(a)+(b), priority=P2, layer0_refs=[SubDomains/D-08.1.md]
- **gap**: gap_id=GAP-D-09.2, sub_domain_id=D-09.2, coverage_level=NOT_ADDRESSED, risk_description=No Data Protection Impact Assessment (DPIA) on file despite systematic large-scale monitoring of EU data subjects; GDPR Art. 35(1) requires a DPIA prior to processing likely resulting in high risk to rights and freedoms of natural persons; the company's architecture processes customer personal data through multiple systems with cloud providers, which may constitute systematic large-scale monitoring per EDPB Guidelines; covered_by_other_reg=[], recommendation=MEDIUM: address if high risk — conduct a DPIA covering the four Art. 35(7) content items (nature/scope/context/purposes of processing, assessment of necessity and proportionality, assessment of risks to rights and freedoms, measures envisaged to address risks) per Art. 35(7), priority=P1, layer0_refs=[SubDomains/D-09.2.md]
- **gap**: gap_id=GAP-D-06.4, sub_domain_id=D-06.4, coverage_level=NOT_ADDRESSED, risk_description=No formal sub-processor register despite 3 cloud providers (AWS, Stripe, Auth0) processing personal data; GDPR Art. 28(1) requires controller due diligence on processors with sufficient guarantees; the absence of a documented processor register means there is no evidence that Art. 28(3)(a)-(h) obligations have been formally negotiated and recorded for each provider relationship; covered_by_other_reg=[], recommendation=MEDIUM: address if high risk — establish a formal sub-processor register documenting each cloud provider's role, the Art. 28(1) sufficient guarantees assessment, and the Art. 28(3)(a)-(h) contractual security obligations per provider, priority=P2, layer0_refs=[SubDomains/D-06.4.md]

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
- TIPO2-CRA-ART14-DUAL-FLOW (YES): company is a manufacturer placing digital products on the EU market; CRA Art. 14(1) requires reporting to ENISA within 24h of awareness of actively exploited vulnerability, and Art. 14(2) requires user notification if material impact exists.
- TIPO2-CRA-ART15-VOLUNTARY (YES): company has active products; CRA Art. 15 voluntary reporting to ENISA for vulnerabilities not yet actively exploited applies when the manufacturer maintains active vulnerability management practices.

## Derogations
- TIPO3-CRA-NON-PLACED (NOT_ACTIVATED): company places digital products on the EU market as a manufacturer; CRA Art. 2 exclusion does not apply because the product is placed and made available in the EU.
- TIPO3-CRA-OPEN-SOURCE (NOT_ACTIVATED): company operates commercially as a SaaS provider with commercial purpose; CRA Recital 18 non-commercial OSS exclusion does not apply.

## Rationale
The TinyTask Lda. case qualifies under both Tipo 2 interpretations for the CRA lane. The company's role matrix explicitly identifies it as a "manufacturer" placing digital products on the EU market, which directly activates TIPO2-CRA-ART14-DUAL-FLOW — this interpretation requires dual reporting to ENISA (within 24h) and users when an actively exploited vulnerability is discovered. Additionally, TIPO2-CRA-ART15-VOLUNTARY applies because the company maintains active products; Art. 15 voluntary reporting allows manufacturers with active vulnerability management to proactively report pre-exploitation vulnerabilities to ENISA.

Both derogations are correctly NOT activated: TIPO3-CRA-NON-PLACED requires both `placing_on_eu_market == False` and `making_available_in_eu == False`, but the company's CRA applicability confirms it places products on the EU market. TIPO3-CRA-OPEN-SOURCE requires non-commercial OSS licensing, which contradicts the company's commercial SaaS business model. The layer0_catalog confirms no additional CRA-specific interpretations or derogations exist beyond these two entries for the CRA lane.

---

## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-GDPR-RTS-DEADLINES (NO): company sector is Technology/Software, not in ['health', 'energy', 'transport', 'digital_infrastructure']; GDPR Art. 33(1) 72h breach notification deadline applies to all controllers regardless of sector — this interpretation's sector-specific predicate does not activate for TinyTask Lda., but the underlying obligation (Art. 33(1)) remains in force as a continuous controller duty.

## Derogations
- TIPO3-GDPR-HOUSEHOLD (NOT_ACTIVATED): company is a commercial SaaS provider with 8 employees, €2M revenue, and documented architecture processing customer data through AWS/Firebase/Stripe; activity is not purely personal or household — GDPR Art. 2(2)(c) derogation does not apply.

## Rationale
TinyTask Lda. qualifies as a GDPR controller for its admin dataset (5000 EU data subjects) and as a data processor for customer data routed through its SaaS platform. As a result, GDPR's continuous obligations — Art. 33(1) breach notification, Art. 30 records of processing, Art. 24(1) policies — apply without tier discount. The household-activity derogation under Art. 2(2)(c) is not engaged because the company's processing is a commercial SaaS activity, not a personal or household one.

The sector-specific interpretation TIPO2-GDPR-RTS-DEADLINES does not activate for TinyTask Lda. because its sector (Technology/Software) is not in ['health', 'energy', 'transport', 'digital_infrastructure']. However, this does not diminish the underlying GDPR Art. 33(1) obligation — the 72-hour breach notification deadline applies to all controllers regardless of sector. The interpretation's predicate simply gates a specific nuance about whether additional sector-specific obligations layer on top; for TinyTask Lda., only the baseline controller obligations apply.

The household derogation TIPO3-GDPR-HOUSEHOLD is definitively not activated: TinyTask Lda.'s architecture (AWS eu-west-1, Auth0 identity service, Stripe payment processing, Datadog monitoring) and its documented data flows (customer registration, authentication, payment processing, telemetry) confirm a commercial business operation. The company's 8 employees, €2M revenue, and structured cloud infrastructure with signed DPAs across AWS, Firebase, Stripe, and Datadog all point to a professional service provider — far from the "purely personal or household" threshold that would exclude GDPR applicability entirely.


### P1B-LLM-02-RATIONALE

## Status
- applicable: YES
- confidence: HIGH

## Findings
- **implication**: id=IMP-CRA-ART14-DUAL-FLOW, description=CRA Art. 14(1) requires the manufacturer to notify ENISA within 24 hours of awareness of an actively exploited vulnerability; CRA Art. 14(2) additionally requires user notification in machine-readable format when material impact exists on users or third parties. TinyTask must operate a dual-reporting pipeline: internal detection → 24h escalation → parallel reporting to ENISA (via single platform per Art. 16) and, where material impact is confirmed, direct user notification. effort_estimate=hours-to-days, dependencies=[NA-05 no CRA incident response playbook], layer0_refs=["SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA"], company_fact_refs=["DOC04:ARCH-07 product processes EU personal data", "DOC04:SEC-NN manufacturer role"]
- **implication**: id=IMP-CRA-ART15-VOLUNTARY, description=CRA Art. 15 allows voluntary reporting of pre-exploitation vulnerabilities to ENISA/CSIRT via the single platform; TinyTask may choose to report discovered-but-not-yet-exploited vulnerabilities proactively. This is optional but recommended as a trust-building measure with no liability exposure (Art. 17(4) shield). effort_estimate=hours, dependencies=[], layer0_refs=["SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO"], company_fact_refs=["DOC04:ARCH-07 product processes EU personal data"]
- **gap**: gap_id=GAP-CRA-CONFORMITY-ASSESSMENT, sub_domain_id=D-09.1, coverage_level=NOT_ADDRESSED, risk_description=CRA Annex VIII requires conformity assessment (Module B+C or H for Class I products) with technical documentation per Annex VII §2–§8 before placing on the market; no formal programme is in place at TinyTask. This is a HIGH-severity gap (NA-01). effort_estimate=months, dependencies=[], layer0_refs=["SubDomains/D-09_Governance-Documentation/D-09.1.md §2 HSO"]
- **gap**: gap_id=GAP-CRA-TECHNICAL-DOC, sub_domain_id=D-09.4, coverage_level=NOT_ADDRESSED, risk_description=CRA Art. 36 requires technical documentation (general description, architecture, SBOM, CVD policy, test reports) to be drawn up before market placement and retained for 10 years or support period; no such documentation exists at TinyTask currently. effort_estimate=weeks-to-months, dependencies=[GAP-CRA-CONFORMITY-ASSESSMENT], layer0_refs=["SubDomains/D-09_Governance-Documentation/D-09.4.md §2 HSO"]
- **gap**: gap_id=GAP-CRA-CE-MARKING, sub_domain_id=D-09.4, coverage_level=NOT_ADDRESSED, risk_description=CRA Art. 30 requires CE marking affixed visibly and legibly before placing on the market; for software products this may be on declaration or website per Art. 30(1). No CE marking process is documented at TinyTask. effort_estimate=days-to-weeks, dependencies=[GAP-CRA-TECHNICAL-DOC], layer0_refs=["SubDomains/D-09_Governance-Documentation/D-09.4.md §2 HSO"]
- **gap**: gap_id=GAP-CRA-SUPPORT-PERIOD, sub_domain_id=D-02.2, coverage_level=NOT_ADDRESSED, risk_description=CRA Art. 13(8) requires a minimum 5-year support period with vulnerability handling throughout; Art. 13(9) extends update availability for 10 years from issue date or remainder of support period whichever is longer. TinyTask has no documented support-period determination factors per Annex II §7. effort_estimate=days-to-weeks, dependencies=[], layer0_refs=["SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO"]

## Rationale
TinyTask Lda. is a MICRO-scale Portuguese software company (8 employees, €2M revenue) operating as both GDPR controller and CRA manufacturer for its SaaS products placed on the EU market. The company's architecture—built on AWS eu-west-1 with Auth0 identity management, Stripe payments, and Datadog observability—processes personal data of EU customers through customer registration, authentication, payment processing, monitoring telemetry, and backup operations flows.

The CRA dual-flow interpretation (Art. 14(1) + Art. 14(2)) is directly binding because TinyTask places digital products on the EU market as manufacturer. When an actively exploited vulnerability is detected in any of its five systems (Main SaaS Application, Identity Service, Cloud Infrastructure, Key Management Service, or Monitoring & Logging), the company must notify ENISA within 24 hours via the single reporting platform established under Art. 16. If material impact on users exists—such as a compromise affecting customer authentication through Auth0 or payment processing through Stripe—the manufacturer also has an obligation to notify affected users in machine-readable format per Art. 14(8). The temporal conflict between GDPR's 72-hour breach notification (Art. 33) and CRA's 24-hour vulnerability reporting creates a practical tension: the company must adopt a maximum-SLA workflow where internal escalation within 24 hours satisfies both regimes from a single detection pipeline, as noted in regulatory interaction TI-01.

The voluntary reporting mechanism under CRA Art. 15 is available to TinyTask but not mandatory—it allows proactive disclosure of pre-exploitation vulnerabilities discovered through vulnerability management (currently PARTIAL readiness). Given the company's small team and limited security FTEs (0.85), voluntary reporting can be a strategic trust-building measure with no liability exposure, since Art. 17(4) provides a shield against increased liability for mere notification.

However, several significant gaps remain uncovered by these interpretations. The conformity assessment procedure under CRA Annex VIII is NOT_ADDRESSED: TinyTask has no formal programme in place for Class I products (which require Module B+C or H evaluation), and this represents the highest-severity gap (NA-01). Without a documented technical documentation package per Annex VII §2–§8—including general description, architecture details, SBOM, CVD policy, test reports, and risk-assessment records—the company cannot legally place products on the EU market. The CE marking obligation under Art. 30 is also NOT_ADDRESSED: for software products, this may be affixed to the declaration or website rather than physical media, but no process exists at TinyTask.

The support-period determination (Art. 13(8) minimum 5 years + Art. 13(9) 10-year update tail) is another NOT_ADDRESSED gap: TinyTask has not documented how it will determine the end-date of its support period or communicate this to customers at purchase time per Annex II §7. This affects long-term customer trust and regulatory compliance posture.

These gaps are substantial for a MICRO-scale company but manageable given the existing security readiness (backup=YES, access control=PARTIAL, audit logging=PARTIAL). The effort is tier-appropriate: hours-to-days for operational implications like dual-flow reporting setup, weeks-to-months for documentation buildout, and months for full conformity assessment programme establishment.

---

## Status
- applicable: YES
- confidence: HIGH

## Findings
- **implication**: id=IMP-D-01.1-1, description=Personal data at rest in AWS RDS (AES-256 provider-managed) and S3 backups must be protected against unauthorised access through encryption with appropriate key custody; the controller's Art. 32(1)(b) obligation requires that personal data stored in STORE-01 (primary database, retention 2555 days) and STORE-02 (backup storage, retention 90 days) are processed in a manner ensuring appropriate security including protection against unauthorised or unlawful processing and accidental loss, destruction or damage; the controller must ensure ongoing confidentiality, integrity, availability and resilience of processing systems and services per Art. 32(1)(b); layer0_refs=[SubDomains/D-01.1.md], company_fact_refs=DOC04:ARCH-01 SYS-01, DOC04:ARCH-03 STORE-01
- **implication**: id=IMP-D-01.2-1, description=Personal data transmitted across network paths (customer registration via TLS 1.3, authentication via TLS 1.2+, payment processing via Stripe) must be protected against unauthorised disclosure and alteration through cryptographic confidentiality and integrity controls including mutual authentication; the controller's Art. 32(1)(b)/(2) obligation covers accidental or unlawful destruction, loss, alteration, unauthorised disclosure of, or access to personal data transmitted per the five-event risk enumeration; layer0_refs=[SubDomains/D-01.2.md], company_fact_refs=DOC04:ARCH-05 FLOW-01 through FLOW-03
- **implication**: id=IMP-D-01.3-1, description=Cryptographic keys used for data at rest and in transit must be managed with separation of roles such that possession of key material is not bundled with possession of the operational environment; the controller-side Art. 4(5) de-attribution test requires that additional information required to re-identify data subjects (the cryptographic key, mapping table, or tokenisation seed) is kept separately and subject to appropriate technical and organisational measures preventing attribution per Art. 34(3)(a); layer0_refs=[SubDomains/D-01.3.md], company_fact_refs=DOC04:ARCH-04 SYS-04 AWS KMS
- **implication**: id=IMP-D-01.4-1, description=Personal data must be accurate and where necessary kept up to date; every reasonable step taken to ensure inaccurate personal data is erased or rectified without delay per Art. 5(1)(d); integrity of stored data must be preserved against unauthorised modification across the data lifecycle with corruption detected, logged and reported; layer0_refs=[SubDomains/D-01.4.md], company_fact_refs=DOC04:ARCH-03 STORE-01
- **implication**: id=IMP-D-05.1-1, description=Personal data collected or otherwise acquired must be limited to what is adequate, relevant and necessary in relation to the purpose for which it is processed per Art. 5(1)(c); further processing must be compatible with original purposes per Art. 6(4) compatibility test; special-category data requires an Art. 9(2) basis subject to Art. 9(1) prohibition; by-design and by-default minimisation applied per Art. 25(1)/(2); layer0_refs=[SubDomains/D-05.1.md], company_fact_refs=DOC04:ARCH-01 SYS-01, DOC04:SEC-NN data categories
- **implication**: id=IMP-D-05.3-1, description=Personal data must be erased without undue delay on the data subject's Art. 17(1) request where one of six grounds applies (no longer necessary for original purposes, consent withdrawn with no other basis, objection under Art. 21(1)/(2), unlawful processing, legal-obligation erasure, or information-society-service to a child); on processor contract end the processor must delete or return all personal data per Art. 28(3)(g); layer0_refs=[SubDomains/D-05.3.md], company_fact_refs=DOC04:ARCH-01 SYS-01
- **implication**: id=IMP-D-06.1-1, description=The controller must engage only processors providing sufficient guarantees to implement appropriate technical and organisational measures per Art. 28(1); the four-factor EDPB Guidelines 07/2020 reading (knowledge + reliability of resources + compliance track-record + financial stability) operationalises the sufficient guarantees threshold; sub-processor authorisation chain under Art. 28(2) is material to due diligence; layer0_refs=[SubDomains/D-06.1.md], company_fact_refs=DOC04:ARCH-03 CS-01 AWS, DOC04:ARCH-03 CS-02 Firebase, DOC04:ARCH-03 CS-03 Stripe
- **implication**: id=IMP-D-06.3-1, description=Controller/processor contracts must include the Art. 28(3)(a)-(h) eight-element DPA floor including instruction-bound processing, sub-processor authorisation and change-notification, processor security-measure commitments, audit/inspection access, and contract-end return/deletion; Art. 46 appropriate-safeguards mechanism and Art. 48 international-agreement filter apply where personal data leaves the EEA or is exposed to third-country legal-process pressure; layer0_refs=[SubDomains/D-06.3.md], company_fact_refs=DOC04:ARCH-03 CS-01 through CS-04
- **implication**: id=IMP-D-07.1-1, description=The controller must implement appropriate technical and organisational measures such as pseudonymisation designed to implement data-protection principles in an effective manner per Art. 25(1); by default only personal data necessary for each specific purpose are processed per Art. 25(2); the design anchor is four-factor qualitative proportionality (state of the art, cost of implementation, nature/scope/context/purposes, risks of varying likelihood and severity) per Art. 25(1); layer0_refs=[SubDomains/D-07.1.md], company_fact_refs=DOC04:ARCH-01 SYS-01 through SYS-05
- **implication**: id=IMP-D-09.1-1, description=The controller must implement appropriate technical and organisational measures including policies designed to implement data-protection principles in an effective manner per Art. 24(1); the DPO is the governance anchor (Art. 37-39) with Art. 5(2) accountability burden; management-body approval/oversight/liability architecture applies; layer0_refs=[SubDomains/D-09.1.md], company_fact_refs=DOC04:SEC-NN implementation_readiness information_security_policy=PARTIAL
- **implication**: id=IMP-D-09.4-1, description=Each controller and processor must maintain a record of processing activities under its responsibility per Art. 30(1) in writing or electronic form containing the seven-item content list; records made available to supervisory authority on request per Art. 30(4); subject to Art. 30(5) 250-employee exception (not applicable here as company has 8 employees); layer0_refs=[SubDomains/D-09.4.md], company_fact_refs=DOC04:SEC-NN implementation_readiness audit_logging=PARTIAL
- **implication**: id=IMP-D-10.1-1, description=The controller must implement appropriate technical and organisational measures to ensure ongoing confidentiality, integrity, availability and resilience of processing systems and services per Art. 32(1)(b); personal-data processing systems monitored for five Art. 32(2) risk types; clear definition of moment of becoming aware of a breach anchors the Art. 33(1) 72-hour notification clock; layer0_refs=[SubDomains/D-10.1.md], company_fact_refs=DOC04:ARCH-05 FLOW-04 monitoring telemetry
- **implication**: id=IMP-D-10.2-1, description=Compliance records maintained in writing or electronic form with integrity and traceability sufficient to demonstrate compliance and support supervisory-authority inspections per Art. 30(3) + Art. 5(2); includes records of processing activities, consent records, processor contract records, breach notification records, and DPIA records; layer0_refs=[SubDomains/D-10.2.md], company_fact_refs=DOC04:SEC-NN implementation_readiness audit_logging=PARTIAL
- **implication**: id=IMP-D-10.3-1, description=The controller must implement appropriate technical and organisational measures including a process for regularly testing, assessing and evaluating the effectiveness of technical and organisational measures per Art. 32(1)(d); DPIA reviewed at least when there is change of risk represented by processing operations per Art. 35(11); layer0_refs=[SubDomains/D-10.3.md], company_fact_refs=DOC04:SEC-NN implementation_readiness vulnerability_management=PARTIAL

## Gaps
- **gap**: gap_id=GAP-D-05.2, sub_domain_id=D-05.2, coverage_level=PARTIAL, risk_description=Retention period for application logs (STORE-03) is 30 days; GDPR Art. 5(1)(e) requires personal data kept in identifiable form only as long as necessary for processing purposes; the RoPA must document envisaged time limits for erasure of different categories of data per Art. 30(1)(f); current retention policy may not align with documented necessity assessments, creating a compliance gap where logs containing personal data (if any) are retained beyond what is necessary without documented justification; covered_by_other_reg=[], recommendation=LOW: document and accept the 30-day retention for non-personal application logs while ensuring any personal data in logs is subject to Art. 5(1)(e) necessity boundary with documented retention rationale, priority=P2, layer0_refs=[SubDomains/D-05.2.md]
- **gap**: gap_id=GAP-D-08.1, sub_domain_id=D-08.1, coverage_level=NOT_ADDRESSED, risk_description=No general security awareness training programme is in place; GDPR Art. 39(1)(b) requires the DPO to monitor compliance including awareness-raising and training of staff involved in processing operations; with no CISO (ciso=NO), no DPO (dpo=NO), and no documented security_awareness readiness, there is no evidence that any workforce data-protection awareness programme has been operationally exercised or recorded; covered_by_other_reg=[], recommendation=MEDIUM: address if high risk — establish a minimum baseline training programme covering GDPR obligations for all personnel involved in processing operations with DPO-catalysed governance per Art. 39(1)(a)+(b), priority=P2, layer0_refs=[SubDomains/D-08.1.md]
- **gap**: gap_id=GAP-D-09.2, sub_domain_id=D-09.2, coverage_level=NOT_ADDRESSED, risk_description=No Data Protection Impact Assessment (DPIA) on file despite systematic large-scale monitoring of EU data subjects; GDPR Art. 35(1) requires a DPIA prior to processing likely resulting in high risk to rights and freedoms of natural persons; the company's architecture processes customer personal data through multiple systems with cloud providers, which may constitute systematic large-scale monitoring per EDPB Guidelines; covered_by_other_reg=[], recommendation=MEDIUM: address if high risk — conduct a DPIA covering the four Art. 35(7) content items (nature/scope/context/purposes of processing, assessment of necessity and proportionality, assessment of risks to rights and freedoms, measures envisaged to address risks) per Art. 35(7), priority=P1, layer0_refs=[SubDomains/D-09.2.md]
- **gap**: gap_id=GAP-D-06.4, sub_domain_id=D-06.4, coverage_level=NOT_ADDRESSED, risk_description=No formal sub-processor register despite 3 cloud providers (AWS, Stripe, Auth0) processing personal data; GDPR Art. 28(1) requires controller due diligence on processors with sufficient guarantees; the absence of a documented processor register means there is no evidence that Art. 28(3)(a)-(h) obligations have been formally negotiated and recorded for each provider relationship; covered_by_other_reg=[], recommendation=MEDIUM: address if high risk — establish a formal sub-processor register documenting each cloud provider's role, the Art. 28(1) sufficient guarantees assessment, and the Art. 28(3)(a)-(h) contractual security obligations per provider, priority=P2, layer0_refs=[SubDomains/D-06.4.md]


### P1C-LLM-01-OVERLAP-CLASSIFICATION

_(no LLM response for this spec)_


### P1C-LLM-02-COMPOUND-EVENT

_(no LLM response for this spec)_


### P1C-LLM-03-STRATEGIC-SYNTHESIS

_(no LLM response for this spec)_
