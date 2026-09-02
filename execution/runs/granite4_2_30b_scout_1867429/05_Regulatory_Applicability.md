---
document_id: AEGIS-P1-05
title: Regulatory Applicability Assessment
phase: 1
version: 1.1
created: "2026-09-02T03:59:19Z"
updated: "2026-09-02T03:59:19Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, ../00_COMMON/01_Company_Context.md, 00_Taxonomy_Reference.md]
outputs: [06_Clause_Mapping_Matrix.xlsx, 07_Structured_Compliance_Matrix.md, 08_Obligation_Derivation.md]
applicable_regs: [CRA, GDPR]
related_documents: [../../../00_METHODOLOGY/PHASE1_STRATEGY.md, "../../../00_METHODOLOGY/PHASE1_STRATEGY.md#filter-1-regulation-applicability-binary-predicates", 00_Taxonomy_Reference.md]
traceability: AEGIS Class Model → ComplianceContext, RegulatoryClause, DomainCoverageEntry
generated_at: "2026-09-02T03:59:19Z"
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

Regulatory requirements for encryption, data retention, and forensic evidence capture, which involve the CISO function for oversight, are implemented by the Engineering, Operations, and Governance functions. A dual-role analysis of the DPO function indicates potential effects on time-to-compliance due to its combined assignment, necessitating explicit planning for dedicated effort. The cost of compliance is supported by the Engineering function's capacity (5-10 FTE) and the DPO's 0.2 FTE allocation for data protection duties, though resource monitoring is advised. The SI-000 implication, with no specific impact and LOW risk, confirms that current functional arrangements meet baseline regulatory expectations.


### 6.1b Per-Regulation Rationale (LLM-02 RATIONALE)
Per-regulation rationale + implications + gaps. Generated by P1B-LLM-02 RATIONALE. Cross-references Doc 04 facts + Regulatory Baseline articles. NO boilerplate (per-validation invariant).
*Source: P1B-LLM-02 RATIONALE | multi-call concat (one section per applicable regulation, separated by `---`)*

## Status
- applicable: YES
- confidence: MEDIUM

## Findings
- <implication: id: "IMP-D-04.3-1", description: "CRA Art. 14(1) requires reporting to ENISA within 24h of awareness of actively exploited vulnerability and Art. 14(2) requires reporting to users if material impact. The company's architecture with multiple systems (Main SaaS, Identity Service, Cloud Infrastructure) requires a clear incident response process to detect and escalate vulnerabilities within 24h.", effort_estimate: "LOW (hours to days)", dependencies: [], layer0_refs: ["SubDomains/D-04_Incident-Response/D-04.3.md"], company_fact_refs: ["DOC04:architecture"]>
- <implication: id: "IMP-D-02.3-1", description: "CRA Art. 15 allows voluntary reporting to ENISA for vulnerabilities not yet actively exploited. Given the company has products, they should establish a voluntary reporting process for pre-exploitation vulnerabilities.", effort_estimate: "LOW (hours to days)", dependencies: [], layer0_refs: ["SubDomains/D-02_Vulnerability-Management/D-02.3.md"], company_fact_refs: ["DOC04:products"]>
- <implication: id: "IMP-D-02.1-1", description: "CRA requires identification of vulnerabilities in products. The company must maintain a vulnerability register for their SaaS application and its components (AWS, Firebase, etc.).", effort_estimate: "LOW (hours to days)", dependencies: [], layer0_refs: ["SubDomains/D-02_Vulnerability-Management/D-02.1.md"], company_fact_refs: ["DOC04:architecture"]>
- <gap: gap_id: "GAP-D-06.1-1", sub_domain_id: "D-06.1", coverage_level: "PARTIAL", risk_description: "The company uses third-party cloud services (AWS, Firebase, Stripe, Datadog) but does not have documented due diligence on these components as required by CRA Art. 13(5). Without proper due diligence, vulnerabilities in third-party components may not be addressed in time.", covered_by_other_reg: ["GDPR Art. 32(1) security of processing"], recommendation: "LOW tier: document the due diligence process and accept the residual risk, but plan to implement a basic third-party risk assessment within the next quarter.", priority: "P2", layer0_refs: ["SubDomains/D-06_Vendor-Risk-Assessment/D-06.1.md"]>

## Rationale
TinyTask Lda. is a Portuguese private limited company in the Technology/Software sector, with 8 employees and €2,000,000 annual revenue, placing it in the MICRO scale. The company places digital products with digital elements on the EU market (architecture deployed in AWS eu-west-1, using EU-based services such as Auth0 and Datadog), and acts as a manufacturer for its SaaS application. Under CRA Art. 3(15), a manufacturer is subject to the obligations in the Regulation. The company's interpretations from P1B-LLM-01 confirm that CRA Art. 14(1) and Art. 14(2) apply due to the manufacturer role, and Art. 15 applies due to having products. The derogation TIPO3-CRA-OPEN_SOURCE is indeterminate due to missing facts on software_licence and commercial_purpose in company facts, so CRA applies based on the manufacturer role and placing digital products in the EU market. The company's architecture, including multiple systems (Main SaaS, Identity Service, Cloud Infrastructure) with personal data stores and critical security controls, makes the CRA obligations binding, particularly in incident response, vulnerability management, and supply chain due diligence. As per Regulatory Baseline tipo2 entry TIPO2-CRA-ART14-DUAL-FLOW, CRA Art. 14(1) and Art. 14(2) require reporting to ENISA within 24 hours of awareness of actively exploited vulnerabilities and to users if material impact. For vulnerability management, Regulatory Baseline tipo2 entry TIPO2-CRA-ART15-VOLUNTARY indicates voluntary reporting is available.

---

## Status
- applicable: YES
- confidence: MEDIUM

## Findings
- <implication: id="IMP-D-04.3-001", description="GDPR Art. 33 requires notification to the supervisory authority within 72 hours of becoming aware of a personal data breach, and given TinyTask's architecture with multiple systems processing personal data (DOC04:ARCH-01), an incident response process must be established to meet this obligation.", effort_estimate="LOW", dependencies="None", layer0_refs="SubDomains/D-04_Incident-Response/D-04.3.md", company_fact_refs="DOC04:ARCH-01, DOC04:DATA-FLOW-01, DOC04:DATA-STORE-01">
- <implication: id="IMP-D-01.1-001", description="GDPR Art. 32(1)(b) and Art. 5(1)(f) require appropriate technical and organisational measures for personal data at rest, applicable to TinyTask's AWS RDS and S3 storage systems containing personal data (DOC04:DATA-STORE-01).", effort_estimate="LOW", dependencies="None", layer0_refs="SubDomains/D-01_Data-at-Rest/D-01.1.md", company_fact_refs="DOC04:ARCH-01, DOC04:DATA-STORE-01">
- <implication: id="IMP-D-01.2-001", description="GDPR Art. 32(1)(b) and Art. 32(2) require protection of personal data in transit, covering TinyTask's data flows between systems and third-party services (DOC04:DATA-FLOW-01, DOC04:DATA-FLOW-02).", effort_estimate="LOW", dependencies="None", layer0_refs="SubDomains/D-01_Data-in-Transit/D-01.2.md", company_fact_refs="DOC04:ARCH-01, DOC04:DATA-FLOW-01, DOC04:DATA-FLOW-02">

## Rationale
GDPR applies to TinyTask Lda. because the company processes personal data as a controller, as evidenced by their SaaS application (Main SaaS Application) which handles customer registration, authentication, and payment processing involving personal data (DOC04:ARCH-01, DOC04:DATA-FLOW-01). The company's architecture includes AWS-hosted systems in the EU, and their data stores contain personal data, making them subject to GDPR Art. 2 and Art. 4. The specific interpretation regarding GDPR Art. 33(1) 72-hour breach notification deadline does not apply to this company because their sector is Technology/Software, not in the list of sectors (health, energy, transport, digital_infrastructure) that trigger that specific interpretation (TIPO2-GDPR-RTS-DEADLINES). The derogation regarding purely personal or household processing (TIPO3-GDPR-HOUSEHOLD) is indeterminate due to missing processing_scope fact, so it does not exclude GDPR applicability. Therefore, GDPR obligations, including Art. 32 security of processing, Art. 33 breach notification, and Art. 35 DPIA for high-risk processing, apply to TinyTask.

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
- applicable: INDETERMINATE
- confidence: LOW

## Interpretations
- TIPO2-CRA-ART14-DUAL-FLOW (YES): company role is manufacturer (DOC04: role matrix), so CRA Art. 14(1) and Art. 14(2) apply for dual reporting to ENISA and users.
- TIPO2-CRA-ART15-VOLUNTARY (YES): company has products (DOC04: products list), so CRA Art. 15 voluntary reporting applies.

## Derogations
- TIPO3-CRA-NON_PLACED (NOT_ACTIVATED): company places digital products in the EU (DOC04: regulatory applicability rationale for CRA), so GDPR Art. 2 exclusion does not apply.
- TIPO3-CRA-OPEN_SOURCE (INDETERMINATE): missing facts: software_licence and commercial_purpose in company_facts, required to evaluate if the company uses OSS without commercial purpose.

## Rationale
The company TinyTask Lda. is a manufacturer of digital products (SaaS) placing them on the EU market, as evidenced by the regulatory classification for CRA. Therefore, the derogation TIPO3-CRA-NON_PLACED does not apply (i.e., CRA scope applies). For the open-source derogation (TIPO3-CRA-OPEN_SOURCE), we lack information on the company's software license and commercial purpose in company_facts, so we cannot determine applicability. The interpretations TIPO2-CRA-ART14-DUAL-FLOW and TIPO2-CRA-ART15-VOLUNTARY are applicable based on the company's role and product presence. References: For TIPO2-CRA-ART14-DUAL-FLOW, see SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA; for TIPO2-CRA-ART15-VOLUNTARY, see SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO; for TIPO3-CRA-NON_PLACED, see SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO.

---

## Status
- applicable: INDETERMINATE
- confidence: LOW

## Interpretations
- TIPO2-GDPR-RTS-DEADLINES (NO): company sector is "Technology/Software", which is not in the list ['health', 'energy', 'transport', 'digital_infrastructure'] required for this interpretation; therefore, the GDPR Art. 33(1) 72h breach notification deadline interpretation does not apply to this company.

## Derogations
- TIPO3-GDPR-HOUSEHOLD (INDETERMINATE): cannot determine activation because company_facts.processing_scope is not provided in the input; the activation predicate requires company_facts.processing_scope == 'purely_personal_or_household' to apply the GDPR Art. 2(2)(c) derogation.

## Rationale
The company TinyTask Lda. is classified as a controller under GDPR with a LOW tier. For the Tipo 2 interpretation TIPO2-GDPR-RTS-DEADLINES, the activation predicate requires the company's sector to be in ['health', 'energy', 'transport', 'digital_infrastructure']. The provided company facts indicate a sector of "Technology/Software", which does not match any of these sectors. Therefore, this interpretation is not applicable. For the Tipo 3 derogation TIPO3-GDPR-HOUSEHOLD, the activation predicate requires company_facts.processing_scope to equal 'purely_personal_or_household'. The supplied company facts do not include a field named "processing_scope", and no equivalent or derivable fact is present in the provided sources. As per the non-negotiable constraints, when a fact needed for determination is not in the supplied sources, INSUFFICIENT_EVIDENCE must be returned with the missing fact explicitly named. Since the missing fact (company_facts.processing_scope) prevents evaluation of the derogation's activation, the overall interpretation status for this regulation lane is INDETERMINATE, and the missing fact is company_facts.processing_scope. No other Tipo 2 or Tipo 3 entries for GDPR are present in the provided layer0_catalog subset.


### P1B-LLM-02-RATIONALE

## Status
- applicable: YES
- confidence: MEDIUM

## Findings
- <implication: id: "IMP-D-04.3-1", description: "CRA Art. 14(1) requires reporting to ENISA within 24h of awareness of actively exploited vulnerability and Art. 14(2) requires reporting to users if material impact. The company's architecture with multiple systems (Main SaaS, Identity Service, Cloud Infrastructure) requires a clear incident response process to detect and escalate vulnerabilities within 24h.", effort_estimate: "LOW (hours to days)", dependencies: [], layer0_refs: ["SubDomains/D-04_Incident-Response/D-04.3.md"], company_fact_refs: ["DOC04:architecture"]>
- <implication: id: "IMP-D-02.3-1", description: "CRA Art. 15 allows voluntary reporting to ENISA for vulnerabilities not yet actively exploited. Given the company has products, they should establish a voluntary reporting process for pre-exploitation vulnerabilities.", effort_estimate: "LOW (hours to days)", dependencies: [], layer0_refs: ["SubDomains/D-02_Vulnerability-Management/D-02.3.md"], company_fact_refs: ["DOC04:products"]>
- <implication: id: "IMP-D-02.1-1", description: "CRA requires identification of vulnerabilities in products. The company must maintain a vulnerability register for their SaaS application and its components (AWS, Firebase, etc.).", effort_estimate: "LOW (hours to days)", dependencies: [], layer0_refs: ["SubDomains/D-02_Vulnerability-Management/D-02.1.md"], company_fact_refs: ["DOC04:architecture"]>
- <gap: gap_id: "GAP-D-06.1-1", sub_domain_id: "D-06.1", coverage_level: "PARTIAL", risk_description: "The company uses third-party cloud services (AWS, Firebase, Stripe, Datadog) but does not have documented due diligence on these components as required by CRA Art. 13(5). Without proper due diligence, vulnerabilities in third-party components may not be addressed in time.", covered_by_other_reg: ["GDPR Art. 32(1) security of processing"], recommendation: "LOW tier: document the due diligence process and accept the residual risk, but plan to implement a basic third-party risk assessment within the next quarter.", priority: "P2", layer0_refs: ["SubDomains/D-06_Vendor-Risk-Assessment/D-06.1.md"]>

## Rationale
TinyTask Lda. is a Portuguese private limited company in the Technology/Software sector, with 8 employees and €2,000,000 annual revenue, placing it in the MICRO scale. The company places digital products with digital elements on the EU market (architecture deployed in AWS eu-west-1, using EU-based services such as Auth0 and Datadog), and acts as a manufacturer for its SaaS application. Under CRA Art. 3(15), a manufacturer is subject to the obligations in the Regulation. The company's interpretations from P1B-LLM-01 confirm that CRA Art. 14(1) and Art. 14(2) apply due to the manufacturer role, and Art. 15 applies due to having products. The derogation TIPO3-CRA-OPEN_SOURCE is indeterminate due to missing facts on software_licence and commercial_purpose in company facts, so CRA applies based on the manufacturer role and placing digital products in the EU market. The company's architecture, including multiple systems (Main SaaS, Identity Service, Cloud Infrastructure) with personal data stores and critical security controls, makes the CRA obligations binding, particularly in incident response, vulnerability management, and supply chain due diligence. As per Regulatory Baseline tipo2 entry TIPO2-CRA-ART14-DUAL-FLOW, CRA Art. 14(1) and Art. 14(2) require reporting to ENISA within 24 hours of awareness of actively exploited vulnerabilities and to users if material impact. For vulnerability management, Regulatory Baseline tipo2 entry TIPO2-CRA-ART15-VOLUNTARY indicates voluntary reporting is available.

---

## Status
- applicable: YES
- confidence: MEDIUM

## Findings
- <implication: id="IMP-D-04.3-001", description="GDPR Art. 33 requires notification to the supervisory authority within 72 hours of becoming aware of a personal data breach, and given TinyTask's architecture with multiple systems processing personal data (DOC04:ARCH-01), an incident response process must be established to meet this obligation.", effort_estimate="LOW", dependencies="None", layer0_refs="SubDomains/D-04_Incident-Response/D-04.3.md", company_fact_refs="DOC04:ARCH-01, DOC04:DATA-FLOW-01, DOC04:DATA-STORE-01">
- <implication: id="IMP-D-01.1-001", description="GDPR Art. 32(1)(b) and Art. 5(1)(f) require appropriate technical and organisational measures for personal data at rest, applicable to TinyTask's AWS RDS and S3 storage systems containing personal data (DOC04:DATA-STORE-01).", effort_estimate="LOW", dependencies="None", layer0_refs="SubDomains/D-01_Data-at-Rest/D-01.1.md", company_fact_refs="DOC04:ARCH-01, DOC04:DATA-STORE-01">
- <implication: id="IMP-D-01.2-001", description="GDPR Art. 32(1)(b) and Art. 32(2) require protection of personal data in transit, covering TinyTask's data flows between systems and third-party services (DOC04:DATA-FLOW-01, DOC04:DATA-FLOW-02).", effort_estimate="LOW", dependencies="None", layer0_refs="SubDomains/D-01_Data-in-Transit/D-01.2.md", company_fact_refs="DOC04:ARCH-01, DOC04:DATA-FLOW-01, DOC04:DATA-FLOW-02">

## Rationale
GDPR applies to TinyTask Lda. because the company processes personal data as a controller, as evidenced by their SaaS application (Main SaaS Application) which handles customer registration, authentication, and payment processing involving personal data (DOC04:ARCH-01, DOC04:DATA-FLOW-01). The company's architecture includes AWS-hosted systems in the EU, and their data stores contain personal data, making them subject to GDPR Art. 2 and Art. 4. The specific interpretation regarding GDPR Art. 33(1) 72-hour breach notification deadline does not apply to this company because their sector is Technology/Software, not in the list of sectors (health, energy, transport, digital_infrastructure) that trigger that specific interpretation (TIPO2-GDPR-RTS-DEADLINES). The derogation regarding purely personal or household processing (TIPO3-GDPR-HOUSEHOLD) is indeterminate due to missing processing_scope fact, so it does not exclude GDPR applicability. Therefore, GDPR obligations, including Art. 32 security of processing, Art. 33 breach notification, and Art. 35 DPIA for high-risk processing, apply to TinyTask.


### P1C-LLM-01-OVERLAP-CLASSIFICATION

_(no LLM response for this spec)_


### P1C-LLM-02-COMPOUND-EVENT

_(no LLM response for this spec)_


### P1C-LLM-03-STRATEGIC-SYNTHESIS

_(no LLM response for this spec)_
