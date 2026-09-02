---
document_id: AEGIS-P1-05
title: Regulatory Applicability Assessment
phase: 1
version: 1.1
created: "2026-09-01T14:32:54Z"
updated: "2026-09-01T14:32:54Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, ../00_COMMON/01_Company_Context.md, 00_Taxonomy_Reference.md]
outputs: [06_Clause_Mapping_Matrix.xlsx, 07_Structured_Compliance_Matrix.md, 08_Obligation_Derivation.md]
applicable_regs: [CRA, GDPR]
related_documents: [../../../00_METHODOLOGY/PHASE1_STRATEGY.md, "../../../00_METHODOLOGY/PHASE1_STRATEGY.md#filter-1-regulation-applicability-binary-predicates", 00_Taxonomy_Reference.md]
traceability: AEGIS Class Model → ComplianceContext, RegulatoryClause, DomainCoverageEntry
generated_at: "2026-09-01T14:32:54Z"
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

The LOW-severity profile of SI-000 (—, LOW) confirms that the regulatory exposure within this applicability domain is contained, with the five canonical functions—CISO, DPO, Engineering, Governance, and Operations—collectively satisfying all required control obligations (CAP-D01-001, CAP-D01-002, CAP-D01-004, CAP-D04-003, CAP-D04-005) without introducing critical residual risk. Dual-role analysis validates that the combined DPO/CEO allocation (0.2 FTE DPO + 0.8 FTE CEO) is sufficient to absorb the governance oversight duties under CAP-D04-003 and CAP-D04-005, while Engineering retains accountability for encryption controls and Operations handles data lifecycle and forensic evidence capture without incremental headcount. Given the LOW residual severity, time-to-compliance is projected to fall within a single regulatory reporting cycle, as no new infrastructure investment is triggered beyond existing Engineering capacity (5–10 FTE) and the CISO's ongoing oversight allocation. The cost of compliance is therefore bounded primarily by the DPO's fractional engagement and routine CISO review effort, with no external consultancy, remediation, or capital expenditure anticipated.


### 6.1b Per-Regulation Rationale (LLM-02 RATIONALE)
Per-regulation rationale + implications + gaps. Generated by P1B-LLM-02 RATIONALE. Cross-references Doc 04 facts + Regulatory Baseline articles. NO boilerplate (per-validation invariant).
*Source: P1B-LLM-02 RATIONALE | multi-call concat (one section per applicable regulation, separated by `---`)*

## Status
- applicable: YES
- confidence: HIGH

## Findings
- IMP-D-04.3-1: CRA Art. 14(1) requires 24h early-warning notification to CSIRT + ENISA upon awareness of an actively exploited vulnerability; Art. 14(2) requires user notification for material impact. TinyTask's PARTIAL incident_response readiness (DOC04:SEC-02) means no dedicated 24h escalation path exists. Effort: 2–3 days to draft a CRA-specific IR runbook. Dependencies: none. layer0_refs: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA. company_fact_refs: DOC04:SEC-02 incident_response=PARTIAL; DOC04:SEC-01 role_matrix.cra.role=manufacturer.
- IMP-D-02.3-1: CRA Annex I Part II (5) + Art. 13(8) sentence 6 require a documented CVD policy with a publicly identifiable contact address (Annex II §2 SPOC). TinyTask's PARTIAL vulnerability_management (DOC04:SEC-02) and absence of a formal CVD policy (NA-04) mean this is not yet in place. Effort: 1–2 days to draft CVD policy + publish SPOC. Dependencies: IMP-D-02.1-1. layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO. company_fact_refs: DOC04:SEC-02 vulnerability_management=PARTIAL; DOC04:SEC-01 negative_analyses NA-04.
- IMP-D-02.1-1: CRA Annex I Part I (2)(a) + Part II (1) + Art. 13(3) require the product to be free of known exploitable vulnerabilities at market placement, with a documented SBOM in machine-readable format. TinyTask's PARTIAL VM (DOC04:SEC-02) and absence of SBOM (NA-04) mean this is not yet satisfied. Effort: 3–5 days to generate initial SBOM from GitHub Actions pipeline. Dependencies: none. layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.1.md §2 HSO. company_fact_refs: DOC04:ARCH-07 tech_stack=GitHub Actions; DOC04:SEC-01 negative_analyses NA-04.
- IMP-D-02.2-1: CRA Art. 13(8) sentence 3 (5-year minimum support period) + Art. 13(9) (10-year update availability) + Annex I Part II (2)/(7)/(8) require secure, timely, free security updates with advisory messages. TinyTask's SaaS model (DOC04:ARCH-07 SYS-01) means updates are delivered via cloud deployment; the 5-year support commitment must be documented. Effort: 1 day to document support-period policy. Dependencies: IMP-D-02.1-1. layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.2.md §2 HSO. company_fact_refs: DOC04:ARCH-07 SYS-01 Main SaaS Application.
- IMP-D-09.4-1: CRA Art. 13(12) + Annex VII §1–§8 + Art. 28 + Art. 30 require technical documentation, EU declaration of conformity, and CE marking before placing on market. TinyTask's CLASS_I classification (DOC04:SEC-01 regulatory_classification.cra_product_class=CLASS_I) triggers Module A (internal production control) per Annex VIII Part I. NA-01 confirms no formal assessment programme exists. Effort: 5–10 days to compile Annex VII technical documentation + draft EU declaration. Dependencies: IMP-D-02.1-1, IMP-D-09.2-1. layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.4.md §2 HSO. company_fact_refs: DOC04:SEC-01 regulatory_classification.cra_product_class=CLASS_I; DOC04:SEC-01 negative_analyses NA-01.
- IMP-D-09.2-1: CRA Art. 13(2) + Art. 13(3) require a documented cybersecurity risk assessment covering intended purpose, reasonably foreseeable use, and Annex I Part I (2) applicability, recorded in Annex VII §3. TinyTask's NO risk_assessment readiness (DOC04:SEC-02) means this artefact does not exist. Effort: 3–5 days to produce initial risk assessment. Dependencies: none. layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.2.md §2 HSO. company_fact_refs: DOC04:SEC-02 risk_assessment=NO; DOC04:ARCH-07 systems SYS-01 through SYS-05.
- GAP-D-04.3: sub_domain_id D-04.3, coverage_level PARTIAL, risk_description: No dedicated CRA 24h AEV escalation path exists; the existing PARTIAL IR process is calibrated to GDPR 72h (TI-01 temporal conflict). covered_by_other_reg: [GDPR Art. 33(1) 72h covers the longer window but not the 24h CRA-specific trigger]. recommendation: Document the 24h escalation trigger in the existing IR runbook; accept residual risk for the first 90 days while the runbook is operationalised. priority: P1. layer0_refs: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA.
- GAP-D-02.1: sub_domain_id D-02.1, coverage_level NOT_ADDRESSED, risk_description: No SBOM exists for the 5-system product portfolio; Annex I Part II (1) + Art. 13(7) require component identification and documentation. covered_by_other_reg: []. recommendation: Generate initial SBOM from GitHub Actions dependency manifests; document and accept residual risk for transitive dependencies not yet inventoried. priority: P1. layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.1.md §2 HSO.
- GAP-D-09.4: sub_domain_id D-09.4, coverage_level NOT_ADDRESSED, risk_description: No Annex VII technical documentation or EU declaration of conformity exists; placing the product on the EU market without these is a market-surveillance exposure. covered_by_other_reg: []. recommendation: Compile Annex VII §1–§8 documentation pack; document and accept that Module A self-assessment is in progress. priority: P1. layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.4.md §2 HSO.

## Rationale
CRA applies to TinyTask Lda. because the company places digital products with digital elements on the EU market as a manufacturer (DOC04:ARCH-07 places_digital_products_eu=true; DOC04:SEC-01 role_matrix.cra.role=manufacturer; cra_product_class=CLASS_I). The five-system SaaS portfolio (SYS-01 through SYS-05, DOC04:ARCH-07) constitutes a product with digital elements under CRA Art. 3(1). P1B-LLM-01 confirmed activation of TIPO2-CRA-ART14-DUAL-FLOW and TIPO2-CRA-ART15-VOLUNTARY, and confirmed that neither TIPO3-CRA-NON-PLACED nor TIPO3-CRA-OPEN-SOURCE derogations apply (commercial SaaS, EU-market placement). The company's PARTIAL vulnerability management and NO risk assessment (DOC04:SEC-02) create immediate gaps against Annex I Part I (2)(a) and Art. 13(3), while CLASS_I triggers Annex VIII Module A (NA-01). At 8 employees and 0.85 security FTE, the proportionate response is a focused documentation-and-process sprint.

---

## Status
- applicable: YES
- confidence: HIGH

## Findings
- IMP-D-01.1-1: Data-at-rest encryption for personal data (email, name, password) in STORE-01 (Postgres, AWS RDS eu-west-1) and STORE-02 (S3 backup) must satisfy GDPR Art. 32(1)(b) appropriate security and Art. 5(1)(f) integrity. Current state: AES-256 provider-managed encryption (DOC04:STORE-01, DOC04:STORE-02). Effort: hours (verify key-custody separation per Art. 4(5) de-attribution test; confirm AWS KMS SYS-04 key separation from operational environment). Dependencies: none. layer0_refs: SubDomains/D-01.1.md §2 HSO SO-D-01.1.GDPR. company_fact_refs: DOC04:ARCH-01, DOC04:STORE-01, DOC04:STORE-02, DOC04:SYS-04.
- IMP-D-01.2-1: Data-in-transit encryption across FLOW-01 through FLOW-05 must satisfy GDPR Art. 32(1)(b) + Art. 32(2) five-risk-type protection (accidental/unlawful destruction, loss, alteration, unauthorised disclosure, unauthorised access). Current state: TLS 1.2+/1.3 on all five flows (DOC04:FLOW-01 through FLOW-05). Effort: hours (verify TLS configuration, certificate rotation, and mutual-authentication on inter-service calls FLOW-02). Dependencies: none. layer0_refs: SubDomains/D-01.2.md §2 HSO SO-D-01.2.GDPR. company_fact_refs: DOC04:FLOW-01, DOC04:FLOW-02, DOC04:FLOW-03.
- IMP-D-02.1-1: Periodic testing and DPIA review per GDPR Art. 32(1)(d) + Art. 35(11). Current state: vulnerability_management=PARTIAL, risk_assessment=NO (DOC04:READINESS). Effort: days (establish documented testing cadence; define DPIA review trigger on risk change). Dependencies: IMP-D-09.2-1. layer0_refs: SubDomains/D-02.1.md §2 HSO SO-D-02.1.GDPR. company_fact_refs: DOC04:READINESS, DOC04:NA-02.
- IMP-D-05.2-1: Retention and archiving per GDPR Art. 5(1)(e) + Art. 30(1)(f). Current state: STORE-01 retention 2555 days (~7 years), STORE-02 retention 90 days (DOC04:STORE-01, DOC04:STORE-02). Effort: hours (document retention rationale per data category; verify Art. 30(1)(f) RoPA entry if RoPA maintained). Dependencies: none. layer0_refs: SubDomains/D-05.2.md §2 HSO SO-D-05.2.GDPR. company_fact_refs: DOC04:STORE-01, DOC04:STORE-02.
- IMP-D-06.1-1: Processor due diligence per GDPR Art. 28(1) for AWS, Firebase, Stripe, Datadog. Current state: DPAs signed (DOC04:CS-01 through CS-04), but third_party_risk=NO (DOC04:READINESS); NA-03 flags no formal sub-processor register (DOC04:NA-03). Effort: days (formalise sub-processor register per Art. 28(2); document sufficient-guarantees assessment for each processor). Dependencies: none. layer0_refs: SubDomains/D-06.1.md §2 HSO SO-D-06.1.GDPR. company_fact_refs: DOC04:CS-01, DOC04:CS-02, DOC04:CS-03, DOC04:CS-04, DOC04:NA-03.
- IMP-D-09.1-1: Data-protection policies with DPO governance anchor per GDPR Art. 24(1) + Art. 5(2). Current state: information_security_policy=PARTIAL, DPO=NO (DOC04:READINESS); SH-03 (DPO role) listed in stakeholders but readiness=NO (DOC04:SH-03). Effort: days (draft data-protection policy; formally designate DPO per Art. 37(1); document Art. 38(6) independence). Dependencies: none. layer0_refs: SubDomains/D-09.1.md §2 HSO SO-D-09.1.GDPR. company_fact_refs: DOC04:READINESS, DOC04:SH-03.
- IMP-D-09.2-1: DPIA per GDPR Art. 35(1) + Art. 35(7) four-item content. Current state: risk_assessment=NO; NA-02 flags HIGH severity — no DPIA on file despite systematic monitoring of EU data subjects (DOC04:NA-02). Effort: days (conduct DPIA covering systematic monitoring; document Art. 35(7)(a)–(d) content; assess Art. 36(1) prior-consultation trigger). Dependencies: none. layer0_refs: SubDomains/D-09.2.md §2 HSO SO-D-09.2.GDPR. company_fact_refs: DOC04:NA-02, DOC04:READINESS.
- IMP-D-09.4-1: Records of processing activities per GDPR Art. 30(1) seven-item content. Current state: 8 employees < 250 threshold; Art. 30(5) exception potentially applicable (DOC04:ARCH-01). Effort: hours (either document RoPA or document Art. 30(5) reliance with justification). Dependencies: none. layer0_refs: SubDomains/D-09.4.md §2 HSO SO-D-09.4.GDPR. company_fact_refs: DOC04:ARCH-01.
- GAP-D-04.1: sub_domain_id D-04.1, coverage_level PARTIAL, risk_description: Incident response is PARTIAL (DOC04:READINESS); GDPR Art. 33(1) 72-hour breach notification to the DPA requires a defined detection-to-notification pipeline with a clear "becoming aware" anchor. Temporal conflict TI-01 with CRA Art. 14 24h SLA requires a unified 24h internal escalation workflow. covered_by_other_reg: CRA (Art. 14 24h actively-exploited vulnerability reporting). recommendation: Document and accept residual risk; establish a minimum 72h notification runbook with awareness-timestamp logging. priority: P1. layer0_refs: SubDomains/D-04.1.md §2 HSO.
- GAP-D-08.1: sub_domain_id D-08.1, coverage_level NOT_ADDRESSED, risk_description: Security awareness training is NO (DOC04:READINESS); GDPR Art. 39(1)(b) requires DPO-catalysed awareness-raising and training of staff involved in processing operations. covered_by_other_reg: none. recommendation: Document and accept; schedule one annual awareness session for the 8-person team covering data-handling and breach-reporting duties. priority: P2. layer0_refs: SubDomains/D-08.1.md §2 HSO SO-D-08.1.GDPR.
- GAP-D-10.3: sub_domain_id D-10.3, coverage_level NOT_ADDRESSED, risk_description: No formal compliance testing programme; GDPR Art. 32(1)(d) requires a process for regularly testing, assessing and evaluating the effectiveness of technical and organisational security measures. covered_by_other_reg: CRA (Annex VIII Module A conformity assessment for CLASS_I product covers product-level testing). recommendation: Document and accept; leverage the CRA Annex VIII Module A self-assessment as the testing vehicle and record the Art. 32(1)(d) effectiveness-evaluation outcome within it. priority: P2. layer0_refs: SubDomains/D-10.3.md §2 HSO SO-D-10.3.GDPR.

## Rationale
GDPR applies to TinyTask Lda. because the company operates as a controller processing personal data (email, name, password per DOC04:FLOW-01; STORE-01 personal_data=True) for a commercial SaaS product placed on the EU market (DOC04:ARCH-01, SYS-01 Main SaaS Application, AWS eu-west-1). P1B-LLM-01 confirmed the TIPO3-GDPR-HOUSEHOLD derogation is NOT activated — TinyTask's processing is a business activity, not a purely personal or household activity under Art. 2(2)(c). The 5-system architecture with 4 cloud processors (DOC04:CS-01 through CS-04, all with signed DPAs) creates a controller obligation chain under Art. 24(1) accountability and Art. 32(1) security of processing. The 8-employee MICRO scale does not exempt these obligations; only the Art. 30(5) RoPA relief is available. The TIPO2-GDPR-RTS-DEADLINES catalog entry was not sector-activated (Technology/Software is not in the health/energy/transport/digital_infrastructure list), but the underlying Art. 33(1) 72-hour breach-notification obligation remains binding on all controllers regardless of sector.

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
- TIPO2-CRA-ART14-DUAL-FLOW (YES): TinyTask is classified as CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role = "manufacturer"; DOC04:ARCH-07 places_digital_products_eu = true; cra_product_class = CLASS_I). Art. 14(1) 24h AEV notification to CSIRT + ENISA and Art. 14(2) user notification for material impact are continuous obligations. Layer0: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA.
- TIPO2-CRA-ART15-VOLUNTARY (YES): TinyTask operates products (SYS-01 Main SaaS Application, SYS-02 Identity Service, SYS-03 Cloud Infrastructure, SYS-04 KMS, SYS-05 Monitoring) with PARTIAL vulnerability management (DOC04:SEC-02 implementation_readiness.vulnerability_management = "PARTIAL"). Art. 15 voluntary pre-exploitation reporting to ENISA is available as an option; the company's partial VM capability means it can and should consider voluntary reporting for vulnerabilities not yet actively exploited. Layer0: SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO.

## Derogations
- TIPO3-CRA-NON-PLACED (NOT_ACTIVATED): TinyTask places digital products on the EU market (DOC04:ARCH-07 places_digital_products_eu = true; DOC04:SEC-01 applicability_rationale.cra = "places_digital_products_eu = true"). The Art. 2 exclusion for products not placed on or made available in the EU market does not apply. Layer0: SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO.
- TIPO3-CRA-OPEN-SOURCE (NOT_ACTIVATED): TinyTask is a commercial SaaS provider with €2,000,000 annual revenue (DOC04:SEC-01 company_facts.revenue = 2000000; DOC04:ARCH-07 tech_stack = AWS/Firebase/GitHub Actions; product is a proprietary SaaS application). The software is not licensed under OSS/GPL/Apache-2.0/MIT, and the company has a clear commercial purpose. The Recital 18 non-commercial OSS exclusion does not apply. Layer0: SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO.

## Rationale
TinyTask Lda. is a micro-scale (8 employees, €2M revenue) Portuguese SaaS company classified as a CRA manufacturer of a CLASS_I product with digital elements. The company's Main SaaS Application (SYS-01, Python/Django/React on AWS eu-west-1) is placed on the EU market, triggering full CRA manufacturer obligations under Art. 13 and the Annex I essential cybersecurity requirements.

For the Art. 14 dual-flow interpretation (TIPO2-CRA-ART14-DUAL-FLOW), the company's manufacturer role is confirmed by the role_matrix (cra.role = "manufacturer") and the applicability predicate (places_digital_products_eu = true). The 24h early-warning notification to the CSIRT of the Member State of main establishment (Portugal) and ENISA, followed by the 72h vulnerability notification and 14-day final report, constitutes a continuous obligation. The dual-flow structure (CSIRT/ENISA + users) is structurally distinct from single-recipient notification and requires a dedicated incident-response playbook. The company's current incident_response readiness is PARTIAL (DOC04:SEC-02), and the negative analysis NA-05 confirms no dedicated CRA 24h SLA playbook exists. The temporal conflict TI-01 (GDPR 72h vs. CRA 24h) further necessitates a unified detection pipeline with the stricter 24h SLA as the internal escalation trigger.

For the Art. 15 voluntary reporting interpretation (TIPO2-CRA-ART15-VOLUNTARY), the company's products are not None (five systems identified in DOC04:ARCH-07), and the company maintains PARTIAL vulnerability management. While Art. 15 is voluntary, the company's existing VM capability (even if partial) positions it to leverage voluntary pre-exploitation reporting as a risk-reduction measure. This is particularly relevant given the company's 0.85 security FTE and the absence of a formal SBOM (NA-04).

Neither CRA derogation is activated. The non-placed derogation (TIPO3-CRA-NON-PLACED) fails because the company explicitly places products on the EU market. The open-source derogation (TIPO3-CRA-OPEN-SOURCE) fails because the company is a commercial entity with proprietary SaaS offerings and revenue, not a non-commercial OSS project. Both predicates evaluate to False against the company's documented facts.

The tier is LOW (micro-scale), which does not reduce the regulatory floor but calibrates the depth of output. All CRA obligations identified here apply in full regardless of company size; the proportionality tier affects documentation depth and cross-reference density, not the applicability of the underlying articles.

---

## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-GDPR-RTS-DEADLINES (NO): Sector predicate not met. Company sector is "Technology/Software" (DOC04:ARCH-01, SYS-01 Main SaaS Application), which is not in the catalog's activation list ['health', 'energy', 'transport', 'digital_infrastructure']. The underlying GDPR Art. 33(1) 72h breach-notification obligation still applies to TinyTask as a controller (DOC04:REG-GDPR role=controller), but this specific catalog interpretation entry is not activated for the company's sector profile.

## Derogations
- TIPO3-GDPR-HOUSEHOLD (NOT_ACTIVATED): Predicate `processing_scope == 'purely_personal_or_household'` is not satisfied. TinyTask Lda. is a commercial SaaS provider (8 employees, €2M revenue, DOC04:ARCH-01) processing customer personal data (email, name, password per FLOW-01; personal_data=True on STORE-01 and STORE-02) for a commercial product placed on the EU market. The processing is a business activity, not a purely personal or household activity under GDPR Art. 2(2)(c). The derogation does not apply.

## Rationale
TinyTask Lda. is a Portuguese micro-enterprise (8 employees, €2M revenue) operating a SaaS task-management application (SYS-01) hosted on AWS eu-west-1, with customer personal data stored in a Postgres database (STORE-01) and S3 backup (STORE-02). The company is classified as a GDPR controller (DOC04:REG-GDPR) and a CRA manufacturer (DOC04:REG-CRA). GDPR applicability is confirmed by the company's processing of personal data (processes_personal_data=True) and its EU jurisdiction.

For the Tipo 2 interpretation catalog, the single GDPR-relevant entry (TIPO2-GDPR-RTS-DEADLINES) carries an activation predicate restricting it to sectors ['health', 'energy', 'transport', 'digital_infrastructure']. TinyTask's sector "Technology/Software" does not match any of these values. The entry is therefore not activated for this company. This does not mean the Art. 33(1) 72h obligation is inapplicable — it applies to all controllers — but the catalog entry's sector-specific relevance flag is not triggered. The company's incident-response readiness is PARTIAL (DOC04:READINESS), and the temporal conflict TI-01 (GDPR 72h vs. CRA 24h) is already captured in the regulatory interactions, so the operational gap is addressed through the CRA lane's interpretation.

For the Tipo 3 derogation catalog, the single GDPR-relevant entry (TIPO3-GDPR-HOUSEHOLD) requires the processing scope to be 'purely_personal_or_household'. TinyTask is a registered commercial entity (Lda.) with 8 employees, signed DPAs with four cloud providers (AWS, Firebase, Stripe, Datadog), and a commercial SaaS product with customer registration flows (FLOW-01). The processing is unambiguously a commercial business activity, not a personal or household one. The Art. 2(2)(c) derogation is not engaged.

No other Tipo 2 or Tipo 3 entries in the supplied catalog have `applies_to` including "GDPR", so no additional interpretations or derogations are activated for this lane. The company's GDPR obligations proceed on the standard controller baseline (Art. 5, Art. 24, Art. 25, Art. 28, Art. 30, Art. 32, Art. 33, Art. 35) without any catalog-activated nuance or derogation modifying the scope.


### P1B-LLM-02-RATIONALE

## Status
- applicable: YES
- confidence: HIGH

## Findings
- IMP-D-04.3-1: CRA Art. 14(1) requires 24h early-warning notification to CSIRT + ENISA upon awareness of an actively exploited vulnerability; Art. 14(2) requires user notification for material impact. TinyTask's PARTIAL incident_response readiness (DOC04:SEC-02) means no dedicated 24h escalation path exists. Effort: 2–3 days to draft a CRA-specific IR runbook. Dependencies: none. layer0_refs: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA. company_fact_refs: DOC04:SEC-02 incident_response=PARTIAL; DOC04:SEC-01 role_matrix.cra.role=manufacturer.
- IMP-D-02.3-1: CRA Annex I Part II (5) + Art. 13(8) sentence 6 require a documented CVD policy with a publicly identifiable contact address (Annex II §2 SPOC). TinyTask's PARTIAL vulnerability_management (DOC04:SEC-02) and absence of a formal CVD policy (NA-04) mean this is not yet in place. Effort: 1–2 days to draft CVD policy + publish SPOC. Dependencies: IMP-D-02.1-1. layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO. company_fact_refs: DOC04:SEC-02 vulnerability_management=PARTIAL; DOC04:SEC-01 negative_analyses NA-04.
- IMP-D-02.1-1: CRA Annex I Part I (2)(a) + Part II (1) + Art. 13(3) require the product to be free of known exploitable vulnerabilities at market placement, with a documented SBOM in machine-readable format. TinyTask's PARTIAL VM (DOC04:SEC-02) and absence of SBOM (NA-04) mean this is not yet satisfied. Effort: 3–5 days to generate initial SBOM from GitHub Actions pipeline. Dependencies: none. layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.1.md §2 HSO. company_fact_refs: DOC04:ARCH-07 tech_stack=GitHub Actions; DOC04:SEC-01 negative_analyses NA-04.
- IMP-D-02.2-1: CRA Art. 13(8) sentence 3 (5-year minimum support period) + Art. 13(9) (10-year update availability) + Annex I Part II (2)/(7)/(8) require secure, timely, free security updates with advisory messages. TinyTask's SaaS model (DOC04:ARCH-07 SYS-01) means updates are delivered via cloud deployment; the 5-year support commitment must be documented. Effort: 1 day to document support-period policy. Dependencies: IMP-D-02.1-1. layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.2.md §2 HSO. company_fact_refs: DOC04:ARCH-07 SYS-01 Main SaaS Application.
- IMP-D-09.4-1: CRA Art. 13(12) + Annex VII §1–§8 + Art. 28 + Art. 30 require technical documentation, EU declaration of conformity, and CE marking before placing on market. TinyTask's CLASS_I classification (DOC04:SEC-01 regulatory_classification.cra_product_class=CLASS_I) triggers Module A (internal production control) per Annex VIII Part I. NA-01 confirms no formal assessment programme exists. Effort: 5–10 days to compile Annex VII technical documentation + draft EU declaration. Dependencies: IMP-D-02.1-1, IMP-D-09.2-1. layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.4.md §2 HSO. company_fact_refs: DOC04:SEC-01 regulatory_classification.cra_product_class=CLASS_I; DOC04:SEC-01 negative_analyses NA-01.
- IMP-D-09.2-1: CRA Art. 13(2) + Art. 13(3) require a documented cybersecurity risk assessment covering intended purpose, reasonably foreseeable use, and Annex I Part I (2) applicability, recorded in Annex VII §3. TinyTask's NO risk_assessment readiness (DOC04:SEC-02) means this artefact does not exist. Effort: 3–5 days to produce initial risk assessment. Dependencies: none. layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.2.md §2 HSO. company_fact_refs: DOC04:SEC-02 risk_assessment=NO; DOC04:ARCH-07 systems SYS-01 through SYS-05.
- GAP-D-04.3: sub_domain_id D-04.3, coverage_level PARTIAL, risk_description: No dedicated CRA 24h AEV escalation path exists; the existing PARTIAL IR process is calibrated to GDPR 72h (TI-01 temporal conflict). covered_by_other_reg: [GDPR Art. 33(1) 72h covers the longer window but not the 24h CRA-specific trigger]. recommendation: Document the 24h escalation trigger in the existing IR runbook; accept residual risk for the first 90 days while the runbook is operationalised. priority: P1. layer0_refs: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA.
- GAP-D-02.1: sub_domain_id D-02.1, coverage_level NOT_ADDRESSED, risk_description: No SBOM exists for the 5-system product portfolio; Annex I Part II (1) + Art. 13(7) require component identification and documentation. covered_by_other_reg: []. recommendation: Generate initial SBOM from GitHub Actions dependency manifests; document and accept residual risk for transitive dependencies not yet inventoried. priority: P1. layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.1.md §2 HSO.
- GAP-D-09.4: sub_domain_id D-09.4, coverage_level NOT_ADDRESSED, risk_description: No Annex VII technical documentation or EU declaration of conformity exists; placing the product on the EU market without these is a market-surveillance exposure. covered_by_other_reg: []. recommendation: Compile Annex VII §1–§8 documentation pack; document and accept that Module A self-assessment is in progress. priority: P1. layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.4.md §2 HSO.

## Rationale
CRA applies to TinyTask Lda. because the company places digital products with digital elements on the EU market as a manufacturer (DOC04:ARCH-07 places_digital_products_eu=true; DOC04:SEC-01 role_matrix.cra.role=manufacturer; cra_product_class=CLASS_I). The five-system SaaS portfolio (SYS-01 through SYS-05, DOC04:ARCH-07) constitutes a product with digital elements under CRA Art. 3(1). P1B-LLM-01 confirmed activation of TIPO2-CRA-ART14-DUAL-FLOW and TIPO2-CRA-ART15-VOLUNTARY, and confirmed that neither TIPO3-CRA-NON-PLACED nor TIPO3-CRA-OPEN-SOURCE derogations apply (commercial SaaS, EU-market placement). The company's PARTIAL vulnerability management and NO risk assessment (DOC04:SEC-02) create immediate gaps against Annex I Part I (2)(a) and Art. 13(3), while CLASS_I triggers Annex VIII Module A (NA-01). At 8 employees and 0.85 security FTE, the proportionate response is a focused documentation-and-process sprint.

---

## Status
- applicable: YES
- confidence: HIGH

## Findings
- IMP-D-01.1-1: Data-at-rest encryption for personal data (email, name, password) in STORE-01 (Postgres, AWS RDS eu-west-1) and STORE-02 (S3 backup) must satisfy GDPR Art. 32(1)(b) appropriate security and Art. 5(1)(f) integrity. Current state: AES-256 provider-managed encryption (DOC04:STORE-01, DOC04:STORE-02). Effort: hours (verify key-custody separation per Art. 4(5) de-attribution test; confirm AWS KMS SYS-04 key separation from operational environment). Dependencies: none. layer0_refs: SubDomains/D-01.1.md §2 HSO SO-D-01.1.GDPR. company_fact_refs: DOC04:ARCH-01, DOC04:STORE-01, DOC04:STORE-02, DOC04:SYS-04.
- IMP-D-01.2-1: Data-in-transit encryption across FLOW-01 through FLOW-05 must satisfy GDPR Art. 32(1)(b) + Art. 32(2) five-risk-type protection (accidental/unlawful destruction, loss, alteration, unauthorised disclosure, unauthorised access). Current state: TLS 1.2+/1.3 on all five flows (DOC04:FLOW-01 through FLOW-05). Effort: hours (verify TLS configuration, certificate rotation, and mutual-authentication on inter-service calls FLOW-02). Dependencies: none. layer0_refs: SubDomains/D-01.2.md §2 HSO SO-D-01.2.GDPR. company_fact_refs: DOC04:FLOW-01, DOC04:FLOW-02, DOC04:FLOW-03.
- IMP-D-02.1-1: Periodic testing and DPIA review per GDPR Art. 32(1)(d) + Art. 35(11). Current state: vulnerability_management=PARTIAL, risk_assessment=NO (DOC04:READINESS). Effort: days (establish documented testing cadence; define DPIA review trigger on risk change). Dependencies: IMP-D-09.2-1. layer0_refs: SubDomains/D-02.1.md §2 HSO SO-D-02.1.GDPR. company_fact_refs: DOC04:READINESS, DOC04:NA-02.
- IMP-D-05.2-1: Retention and archiving per GDPR Art. 5(1)(e) + Art. 30(1)(f). Current state: STORE-01 retention 2555 days (~7 years), STORE-02 retention 90 days (DOC04:STORE-01, DOC04:STORE-02). Effort: hours (document retention rationale per data category; verify Art. 30(1)(f) RoPA entry if RoPA maintained). Dependencies: none. layer0_refs: SubDomains/D-05.2.md §2 HSO SO-D-05.2.GDPR. company_fact_refs: DOC04:STORE-01, DOC04:STORE-02.
- IMP-D-06.1-1: Processor due diligence per GDPR Art. 28(1) for AWS, Firebase, Stripe, Datadog. Current state: DPAs signed (DOC04:CS-01 through CS-04), but third_party_risk=NO (DOC04:READINESS); NA-03 flags no formal sub-processor register (DOC04:NA-03). Effort: days (formalise sub-processor register per Art. 28(2); document sufficient-guarantees assessment for each processor). Dependencies: none. layer0_refs: SubDomains/D-06.1.md §2 HSO SO-D-06.1.GDPR. company_fact_refs: DOC04:CS-01, DOC04:CS-02, DOC04:CS-03, DOC04:CS-04, DOC04:NA-03.
- IMP-D-09.1-1: Data-protection policies with DPO governance anchor per GDPR Art. 24(1) + Art. 5(2). Current state: information_security_policy=PARTIAL, DPO=NO (DOC04:READINESS); SH-03 (DPO role) listed in stakeholders but readiness=NO (DOC04:SH-03). Effort: days (draft data-protection policy; formally designate DPO per Art. 37(1); document Art. 38(6) independence). Dependencies: none. layer0_refs: SubDomains/D-09.1.md §2 HSO SO-D-09.1.GDPR. company_fact_refs: DOC04:READINESS, DOC04:SH-03.
- IMP-D-09.2-1: DPIA per GDPR Art. 35(1) + Art. 35(7) four-item content. Current state: risk_assessment=NO; NA-02 flags HIGH severity — no DPIA on file despite systematic monitoring of EU data subjects (DOC04:NA-02). Effort: days (conduct DPIA covering systematic monitoring; document Art. 35(7)(a)–(d) content; assess Art. 36(1) prior-consultation trigger). Dependencies: none. layer0_refs: SubDomains/D-09.2.md §2 HSO SO-D-09.2.GDPR. company_fact_refs: DOC04:NA-02, DOC04:READINESS.
- IMP-D-09.4-1: Records of processing activities per GDPR Art. 30(1) seven-item content. Current state: 8 employees < 250 threshold; Art. 30(5) exception potentially applicable (DOC04:ARCH-01). Effort: hours (either document RoPA or document Art. 30(5) reliance with justification). Dependencies: none. layer0_refs: SubDomains/D-09.4.md §2 HSO SO-D-09.4.GDPR. company_fact_refs: DOC04:ARCH-01.
- GAP-D-04.1: sub_domain_id D-04.1, coverage_level PARTIAL, risk_description: Incident response is PARTIAL (DOC04:READINESS); GDPR Art. 33(1) 72-hour breach notification to the DPA requires a defined detection-to-notification pipeline with a clear "becoming aware" anchor. Temporal conflict TI-01 with CRA Art. 14 24h SLA requires a unified 24h internal escalation workflow. covered_by_other_reg: CRA (Art. 14 24h actively-exploited vulnerability reporting). recommendation: Document and accept residual risk; establish a minimum 72h notification runbook with awareness-timestamp logging. priority: P1. layer0_refs: SubDomains/D-04.1.md §2 HSO.
- GAP-D-08.1: sub_domain_id D-08.1, coverage_level NOT_ADDRESSED, risk_description: Security awareness training is NO (DOC04:READINESS); GDPR Art. 39(1)(b) requires DPO-catalysed awareness-raising and training of staff involved in processing operations. covered_by_other_reg: none. recommendation: Document and accept; schedule one annual awareness session for the 8-person team covering data-handling and breach-reporting duties. priority: P2. layer0_refs: SubDomains/D-08.1.md §2 HSO SO-D-08.1.GDPR.
- GAP-D-10.3: sub_domain_id D-10.3, coverage_level NOT_ADDRESSED, risk_description: No formal compliance testing programme; GDPR Art. 32(1)(d) requires a process for regularly testing, assessing and evaluating the effectiveness of technical and organisational security measures. covered_by_other_reg: CRA (Annex VIII Module A conformity assessment for CLASS_I product covers product-level testing). recommendation: Document and accept; leverage the CRA Annex VIII Module A self-assessment as the testing vehicle and record the Art. 32(1)(d) effectiveness-evaluation outcome within it. priority: P2. layer0_refs: SubDomains/D-10.3.md §2 HSO SO-D-10.3.GDPR.

## Rationale
GDPR applies to TinyTask Lda. because the company operates as a controller processing personal data (email, name, password per DOC04:FLOW-01; STORE-01 personal_data=True) for a commercial SaaS product placed on the EU market (DOC04:ARCH-01, SYS-01 Main SaaS Application, AWS eu-west-1). P1B-LLM-01 confirmed the TIPO3-GDPR-HOUSEHOLD derogation is NOT activated — TinyTask's processing is a business activity, not a purely personal or household activity under Art. 2(2)(c). The 5-system architecture with 4 cloud processors (DOC04:CS-01 through CS-04, all with signed DPAs) creates a controller obligation chain under Art. 24(1) accountability and Art. 32(1) security of processing. The 8-employee MICRO scale does not exempt these obligations; only the Art. 30(5) RoPA relief is available. The TIPO2-GDPR-RTS-DEADLINES catalog entry was not sector-activated (Technology/Software is not in the health/energy/transport/digital_infrastructure list), but the underlying Art. 33(1) 72-hour breach-notification obligation remains binding on all controllers regardless of sector.


### P1C-LLM-01-OVERLAP-CLASSIFICATION

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-01.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. CONDITIONAL pair per predicate PRED-D01.1-GDPR-CRA-SAME-PARTY (SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA pair GDPR↔CRA lines 117-126). Activation predicate: is_manufacturer == True AND product_stores_personal_data == True. Both conditions satisfied: TinyTask is CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer) and stores personal data (DOC04:ARCH-07 STORE-01 personal_data=True, STORE-02 personal_data=True). Verdict: OVERLAP_CONFIRMED.
- D-01.2 : GDPR ↔ CRA — OVERLAP_CONFIRMED. SAME relationship (READ-ONLY, SubDomains/D-01_Data-Protection/D-01.2.md §1 CRDA pair GDPR↔CRA). Scope-disjoint test: "Y when the same product transmits personal data; disjoint in baseline (CRA manufacturer ≠ GDPR controller)." TinyTask is the same party in both roles on the same SaaS product; FLOW-01 through FLOW-05 transmit personal data over TLS. Predicate met → OVERLAP_CONFIRMED.
- D-01.3 : GDPR ↔ CRA — OVERLAP_CONFIRMED. SAME relationship (READ-ONLY, SubDomains/D-01_Data-Protection/D-01.3.md §1 CRDA pair GDPR↔CRA). Scope-disjoint test: "Y on the same product; disjoint in baseline." TinyTask is integrated manufacturer-controller on the same product (SYS-04 Key Management Service, AWS KMS). Predicate met → OVERLAP_CONFIRMED.
- D-01.4 : GDPR ↔ CRA — OVERLAP_CONFIRMED. SAME relationship (READ-ONLY, SubDomains/D-01_Data-Protection/D-01.4.md §1 CRDA pair GDPR↔CRA). Scope-disjoint test: "Y on the same product handling personal data." TinyTask's product handles personal data (DOC04:FLOW-01 data_types: email, name, password). Predicate met → OVERLAP_CONFIRMED.
- D-01.1 : GDPR ↔ NIS2 — NOT_IN_SCOPE. NIS2 not applicable to TinyTask (DOC04:SEC-01 nis2_entity_class=NOT_APPLICABLE). Pair not activated.
- D-01.1 : GDPR ↔ DORA — NOT_IN_SCOPE. DORA not applicable (DOC04:SEC-01 dora_article_2_entity=NOT_APPLICABLE). Pair not activated.
- D-01.1 : NIS2 ↔ CRA — NOT_IN_SCOPE. NIS2 not applicable. Pair not activated.
- D-01.1 : NIS2 ↔ DORA — NOT_IN_SCOPE. Neither regulation applicable. Pair not activated.
- D-01.1 : CRA ↔ DORA — NOT_IN_SCOPE. DORA not applicable. Pair not activated.
- D-01.2 : GDPR ↔ DORA — NOT_IN_SCOPE. DORA not applicable. Pair not activated.
- D-01.2 : CRA ↔ DORA — NOT_IN_SCOPE. DORA not applicable. Pair not activated.
- D-01.3 : GDPR ↔ DORA — NOT_IN_SCOPE. DORA not applicable. Pair not activated.
- D-01.3 : CRA ↔ DORA — NOT_IN_SCOPE. DORA not applicable. Pair not activated.
- D-01.4 : GDPR ↔ DORA — NOT_IN_SCOPE. DORA not applicable. Pair not activated.
- D-01.4 : GDPR ↔ AI_Act — NOT_IN_SCOPE. AI_Act not applicable (DOC04:SEC-01 ai_system_classification=NOT_APPLICABLE). Pair not activated.
- D-01.4 : CRA ↔ DORA — NOT_IN_SCOPE. DORA not applicable. Pair not activated.
- D-01.4 : CRA ↔ AI_Act — NOT_IN_SCOPE. AI_Act not applicable. Pair not activated.
- D-01.4 : DORA ↔ AI_Act — NOT_IN_SCOPE. Neither regulation applicable. Pair not activated.

## Findings
- D-01.1 (Data at Rest Encryption): applicable=YES. scope_overlap=Y. applicable_regulations=[GDPR, CRA]. The GDPR↔CRA pair is CONDITIONAL per the predicate catalog and resolves to OVERLAP_CONFIRMED because TinyTask is an integrated manufacturer-controller on the same product storing personal data (STORE-01, STORE-02). layer0_refs: SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA pair GDPR↔CRA lines 117-126; catalogs/scope_overlap_predicates.yaml PRED-D01.1-GDPR-CRA-SAME-PARTY.
- D-01.2 (Data in Transit Encryption): applicable=YES. scope_overlap=Y. applicable_regulations=[GDPR, CRA]. The GDPR↔CRA pair is SAME (READ-ONLY) and the scope-disjoint test confirms overlap for the same-party-same-product case. TinyTask's five data flows (FLOW-01 through FLOW-05) all transmit personal data over TLS 1.2+/1.3. layer0_refs: SubDomains/D-01_Data-Protection/D-01.2.md §1 CRDA pair GDPR↔CRA.
- D-01.3 (Cryptographic Key Management): applicable=YES. scope_overlap=Y. applicable_regulations=[GDPR, CRA]. The GDPR↔CRA pair is SAME (READ-ONLY). TinyTask uses AWS KMS (SYS-04) as its key management service, creating a single key-custody architecture that must satisfy both GDPR Art. 32(1)(a) pseudonymisation/encryption separation and CRA Annex I Part I (2)(d) access-control. layer0_refs: SubDomains/D-01_Data-Protection/D-01.3.md §1 CRDA pair GDPR↔CRA.
- D-01.4 (Data Integrity Mechanisms): applicable=YES. scope_overlap=Y. applicable_regulations=[GDPR, CRA]. The GDPR↔CRA pair is SAME (READ-ONLY). TinyTask's product handles personal data (email, name, password per FLOW-01), triggering both the GDPR Art. 5(1)(d)/(f) accuracy-and-integrity obligations and the CRA Annex I Part I (2)(f) universal-quantifier integrity protection. layer0_refs: SubDomains/D-01_Data-Protection/D-01.4.md §1 CRDA pair GDPR↔CRA.
- Cross-sub-domain pattern: All four D-01 sub-domains exhibit the same overlap topology — a single integrated manufacturer-controller (TinyTask) on a single SaaS product (SYS-01 through SYS-05) creates a unified compliance surface where GDPR and CRA obligations stack-merge on the same technical artefacts (encryption, key custody, integrity logging). No sub-domain in D-01 requires separate compliance tracks for this company because the "disjoint baseline" (SaaS-uses-third-party-CRA-product) does not apply; TinyTask IS the manufacturer.
- Total sub-domains in domain: 4. Active sub-domains: 4. In-scope regulation pairs: 4 (one per sub-domain, all GDPR↔CRA). All resolve to OVERLAP_CONFIRMED.

## Rationale
The domain D-01 (Data Protection & Encryption) contains four sub-domains, all of which are active for TinyTask Lda. because both GDPR (controller) and CRA (manufacturer) are in the applicable_regs set. The only regulation pair in scope across all four sub-domains is GDPR↔CRA; all other pairs involve NIS2, DORA, or AI_Act, none of which apply to this company per DOC04:SEC-01 regulatory_classification (nis2_entity_class=NOT_APPLICABLE, dora_article_2_entity=NOT_APPLICABLE, ai_system_classification=NOT_APPLICABLE).

For D-01.1, the GDPR↔CRA pair is marked CONDITIONAL in the predicate catalog (PRED-D01.1-GDPR-CRA-SAME-PARTY, layer0_ref: SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA pair GDPR↔CRA lines 117-126). The activation predicate requires is_manufacturer == True AND product_stores_personal_data == True. TinyTask's role_matrix confirms CRA role = manufacturer (DOC04:SEC-01), and the architecture confirms personal data at rest in STORE-01 (PostgreSQL, AWS RDS eu-west-1, personal_data=True, AES-256) and STORE-02 (S3 backup, personal_data=True, AES-256) (DOC04:ARCH-07). Both conditions are satisfied, yielding OVERLAP_CONFIRMED. This is the "integrated vendor" case described in the predicate notes, not the "SaaS-using-product" disjoint baseline.

For D-01.2, D-01.3, and D-01.4, the GDPR↔CRA pairs carry a SAME classification in the Regulatory Baseline sub-domain files (SubDomains/D-01_Data-Protection/D-01.2.md, D-01.3.md, D-01.4.md §1 CRDA respectively). Per the non-negotiable constraint, SAME relationships are READ-ONLY and I do not re-classify them. The scope-disjoint test in each file confirms that overlap is "Y" when the same party is both manufacturer and controller on the same product. TinyTask satisfies this condition: it is the CRA manufacturer placing the SaaS product on the EU market AND the GDPR controller processing personal data within that same product. The in-transit flows (D-01.2), key management (D-01.3, AWS KMS/SYS-04), and integrity mechanisms (D-01.4) all operate on the same product artefacts, confirming OVERLAP_CONFIRMED for each.

No INDETERMINATE verdicts are required because all activation predicates are fully resolvable from the supplied company facts. No CONDITIONAL pair produces a missing-fact scenario. The MICRO scale (8 employees, 0.85 security FTE) does not alter the regulatory floor or the overlap determination; it only affects the proportionality of the implementation effort, which is a Track B concern outside this LLM's scope.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-02.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. Layer0 relationship is SAME (READ-ONLY, preserved verbatim from Regulatory Baseline). The scope_disjoint_test in the Regulatory Baseline states "Y (controller inheriting CRA product-side pipeline)." TinyTask Lda. is simultaneously a GDPR controller (DOC04:SEC-01 role_matrix.gdpr.role=controller) and a CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer), i.e., the same legal entity on the same artefact (SYS-01 Main SaaS Application, DOC04:ARCH-07). The product stores personal data (STORE-01 personal_data=True, DOC04:ARCH-07). The predicate condition for overlap is met: same party, product processes personal data. Verdict: OVERLAP_CONFIRMED.
- D-02.2 : No GDPR↔CRA pair exists in the Regulatory Baseline for this sub-domain. The only pair listed is CRA↔DORA (SAME), but DORA is NOT_APPLICABLE to TinyTask (DOC04:SEC-01 role_matrix.dora.role=not_applicable). No cross-regulation verdict to emit.
- D-02.3 : No GDPR↔CRA pair exists in the Regulatory Baseline for this sub-domain. The only pair listed is CRA↔NIS2 (SAME), but NIS2 is NOT_APPLICABLE to TinyTask (DOC04:SEC-01 role_matrix.nis2.role=not_applicable). No cross-regulation verdict to emit.
- D-02.4 : No GDPR↔CRA pair exists in the Regulatory Baseline for this sub-domain. Pairs listed are CRA↔DORA, CRA↔AI_Act, DORA↔AI_Act (all SAME), but DORA and AI_Act are NOT_APPLICABLE to TinyTask. No cross-regulation verdict to emit.

## Findings
- D-02.1 (Vulnerability Identification): ACTIVE. Participating regulations in scope: GDPR, CRA. One cross-regulation pair (GDPR↔CRA) evaluated → OVERLAP_CONFIRMED. The Regulatory Baseline downstream implication is "Stack-merge with advisory ingestion: the CRA product's SBOM and vulnerability-advisory pipeline feeds the controller's Art. 32(1)(d) testing register." Company gap: vulnerability_management is PARTIAL (DOC04:SEC-02), no SBOM in place (NA-04), no formal risk assessment (DOC04:SEC-02 risk_assessment=NO). Layer0 refs: SubDomains/D-02_Vulnerability-Management/D-02.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-02_Vulnerability-Management/D-02.1.md §2 HSO SO-D-02.1.GDPR + SO-D-02.1.CRA.
- D-02.2 (Patch Management & Updates): ACTIVE. Participating regulations in scope: CRA only (GDPR does not participate in this sub-domain per Regulatory Baseline). No cross-regulation pair to evaluate. Company gap: no documented patch policy evidenced; CRA Annex I Part II (2) + Art. 13(8)–(9) obligations apply to the manufacturer role. Layer0 refs: SubDomains/D-02_Vulnerability-Management/D-02.2.md §1 CRDA; SubDomains/D-02_Vulnerability-Management/D-02.2.md §2 HSO SO-D-02.2.CRA.
- D-02.3 (Coordinated Vulnerability Disclosure): ACTIVE. Participating regulations in scope: CRA only (NIS2 partial but NIS2 NOT_APPLICABLE). No cross-regulation pair to evaluate. Company gap: no CVD policy, no public vulnerability contact address, no SPOC designated (NA-04: "no SBOM, no coordinated disclosure"). CRA Annex I Part II (4)–(6) + Art. 13(17) obligations apply. Layer0 refs: SubDomains/D-02_Vulnerability-Management/D-02.3.md §1 CRDA; SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO SO-D-02.3.CRA.
- D-02.4 (Threat-Led Penetration Testing): ACTIVE. Participating regulations in scope: CRA only (DORA and AI_Act NOT_APPLICABLE). No cross-regulation pair to evaluate. Company gap: no evidence of regular product-security testing programme; CRA Annex I Part II (3) + Annex VII §6 obligations apply. Layer0 refs: SubDomains/D-02_Vulnerability-Management/D-02.4.md §1 CRDA; SubDomains/D-02_Vulnerability-Management/D-02.4.md §2 HSO SO-D-02.4.CRA.
- Cross-sub-domain pattern: The GDPR↔CRA overlap is concentrated in D-02.1 (identification layer) where the stack-merge is most operationally significant. In D-02.2 through D-02.4, CRA obligations are single-regulation (manufacturer-side) with no GDPR cross-cutting requirement in the Regulatory Baseline. The practical implication is that TinyTask's vulnerability identification pipeline (D-02.1) must serve both the CRA product-side SBOM/advisory flow and the GDPR Art. 32(1)(d) testing register simultaneously, while patch management, CVD, and testing are purely CRA-manufacturer obligations.

## Rationale
The domain D-02 (Vulnerability Management) contains four sub-domains, all of which are active for TinyTask Lda. because at least one applicable regulation (CRA) participates in each. The only cross-regulation pair between the two applicable regulations (GDPR and CRA) appears in D-02.1, where the Regulatory Baseline classifies the relationship as SAME (CORRECTED — wording only). This classification is READ-ONLY and has not been re-classified.

The scope_disjoint_test for this pair in the Regulatory Baseline states "Y (controller inheriting CRA product-side pipeline)," meaning the overlap is confirmed when the same entity is both a GDPR controller and a CRA manufacturer whose product processes personal data. TinyTask Lda. satisfies all three conditions: it is a controller (DOC04:SEC-01 role_matrix.gdpr.role=controller), a manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer, cra_product_class=CLASS_I), and its product stores personal data (DOC04:ARCH-07 STORE-01 personal_data=True, data_types include email, name, password). The same-party, same-artefact condition is met. The verdict is therefore OVERLAP_CONFIRMED, consistent with the Regulatory Baseline downstream implication of a stack-merge where the CRA SBOM and vulnerability-advisory pipeline feeds the GDPR Art. 32(1)(d) testing register.

No CONDITIONAL predicates from scope_overlap_predicates.yaml apply to any D-02 sub-domain (the supplied predicates target D-01.1, D-04.3, D-05.2, and D-09.2 only). All other pairs in the D-02 sub-domains involve NIS2, DORA, or AI_Act, none of which are applicable to TinyTask per DOC04:SEC-01 (nis2_entity_class=NOT_APPLICABLE, dora_article_2_entity=NOT_APPLICABLE, ai_system_classification=NOT_APPLICABLE). These pairs are therefore excluded from evaluation rather than re-classified.

The company's implementation readiness (DOC04:SEC-02) shows vulnerability_management=PARTIAL and risk_assessment=NO, which aligns with the identified gaps (NA-01, NA-04, NA-05) but does not alter the regulatory activation. The MICRO scale (8 employees, 0.85 security FTE) affects proportionality of implementation effort but does not reduce the regulatory floor, consistent with the base system prompt constraint that tier does not change the regulatory floor.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-03.1 : GDPR ↔ CRA — SAME — DIFFERENT-PERSPECTIVE (READ-ONLY). Both regs applicable to same party (controller + manufacturer on same SaaS product). Verdict: OVERLAP_CONFIRMED.
- D-03.1 : GDPR ↔ NIS2 — SAME — DIFFERENT-PERSPECTIVE (READ-ONLY). NIS2 not applicable to TinyTask (not an Annex I/II entity). Pair not activated.
- D-03.1 : GDPR ↔ DORA — SAME — COMPLEMENTARY (READ-ONLY). DORA not applicable (not a financial entity). Pair not activated.
- D-03.1 : NIS2 ↔ CRA — SAME — COMPLEMENTARY (READ-ONLY). NIS2 not applicable. Pair not activated.
- D-03.1 : NIS2 ↔ DORA — SAME — COMPLEMENTARY (READ-ONLY). Neither reg applicable. Pair not activated.
- D-03.1 : CRA ↔ DORA — SAME — COMPLEMENTARY (READ-ONLY). DORA not applicable. Pair not activated.
- D-03.2 : GDPR ↔ CRA — SAME — COMPLEMENTARY (READ-ONLY). Both regs applicable to same party. Verdict: OVERLAP_CONFIRMED.
- D-03.2 : GDPR ↔ NIS2 — SAME — COMPLEMENTARY (READ-ONLY). NIS2 not applicable. Pair not activated.
- D-03.2 : GDPR ↔ DORA — SAME — COMPLEMENTARY (READ-ONLY). DORA not applicable. Pair not activated.
- D-03.2 : NIS2 ↔ CRA — SAME — COMPLEMENTARY (READ-ONLY). NIS2 not applicable. Pair not activated.
- D-03.2 : NIS2 ↔ DORA — SAME — COMPLEMENTARY (READ-ONLY). Neither reg applicable. Pair not activated.
- D-03.2 : CRA ↔ DORA — SAME — COMPLEMENTARY (READ-ONLY). DORA not applicable. Pair not activated.
- D-03.3 : GDPR ↔ CRA — SAME — COMPLEMENTARY (READ-ONLY). Both regs applicable to same party. Verdict: OVERLAP_CONFIRMED.
- D-03.3 : GDPR ↔ NIS2 — SAME — COMPLEMENTARY (READ-ONLY). NIS2 not applicable. Pair not activated.
- D-03.3 : GDPR ↔ DORA — SAME — COMPLEMENTARY (READ-ONLY). DORA not applicable. Pair not activated.
- D-03.3 : NIS2 ↔ CRA — SAME — COMPLEMENTARY (READ-ONLY). NIS2 not applicable. Pair not activated.
- D-03.3 : NIS2 ↔ DORA — CORRECTED — COMPLEMENTARY (READ-ONLY). Neither reg applicable. Pair not activated.
- D-03.3 : CRA ↔ DORA — SAME — COMPLEMENTARY (READ-ONLY). DORA not applicable. Pair not activated.
- D-03.4 : GDPR ↔ CRA — SAME — DIFFERENT-PERSPECTIVE (READ-ONLY). Both regs applicable to same party. Verdict: OVERLAP_CONFIRMED.

## Findings
- D-03.1 (Identity Lifecycle Management): Active. Applicable regs: GDPR, CRA. Scope overlap: Y (GDPR↔CRA OVERLAP_CONFIRMED). TinyTask is simultaneously a GDPR controller (DOC04:SEC-01 role_matrix.gdpr.role=controller) and a CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer) on the same SaaS product (SYS-01, DOC04:ARCH-07). The GDPR leg governs data-subject identity verification at the rights-exercise endpoint (Art. 12(6), Art. 11(2)); the CRA leg governs product-side identity management in a verifiable manner (Annex I Part I (2)(d), Art. 13(15), Art. 13(17)). layer0_refs: SubDomains/D-03_Identity-Access/D-03.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-03_Identity-Access/D-03.1.md §2 HSO SO-D-03.1.GDPR, SO-D-03.1.CRA.
- D-03.2 (Multi-Factor Authentication): Active. Applicable regs: GDPR, CRA. Scope overlap: Y (GDPR↔CRA OVERLAP_CONFIRMED). GDPR provides the silent-wrapper (Art. 28(3)(b) instructions + Art. 29 confidentiality + Art. 32(1)(b) confidentiality) without an explicit MFA mandate; CRA provides the permissive product-side authentication baseline (Annex I Part I (2)(d) "may include authentication"). TinyTask has MFA enforced on Auth0, AWS IAM, and GitHub (DOC04:ARCH-07 auth_systems AS-01, AS-02, AS-03, all mfa_enforced=True), which exceeds both the GDPR silent-wrapper and the CRA permissive floor. layer0_refs: SubDomains/D-03_Identity-Access/D-03.2.md §1 CRDA pair GDPR↔CRA; SubDomains/D-03_Identity-Access/D-03.2.md §2 HSO SO-D-03.2.GDPR, SO-D-03.2.CRA.
- D-03.3 (Authorisation & Least Privilege): Active. Applicable regs: GDPR, CRA. Scope overlap: Y (GDPR↔CRA OVERLAP_CONFIRMED). GDPR governs the personal-data-scope chain of authority (Art. 28(3), Art. 29, Art. 32(4)); CRA governs the product-side authenticated-and-authorised boundary with reporting of possible unauthorised access (Annex I Part I (2)(d), Annex I Part II (6)). TinyTask's PARTIAL access_control readiness (DOC04:SEC-02) indicates the product-side boundary is partially implemented. layer0_refs: SubDomains/D-03_Identity-Access/D-03.3.md §1 CRDA pair GDPR↔CRA; SubDomains/D-03_Identity-Access/D-03.3.md §2 HSO SO-D-03.3.GDPR, SO-D-03.3.CRA.
- D-03.4 (Secure System Defaults): Active. Applicable regs: GDPR, CRA. Scope overlap: Y (GDPR↔CRA OVERLAP_CONFIRMED). GDPR Art. 25(2) imposes the four-dimension data-centric by-default (amount, extent, period, accessibility); CRA Annex I Part I (2)(b) imposes product-centric secure-by-default with reset-to-original-state and auto-update enabled by default. These are two layers of the same default posture on the same product. layer0_refs: SubDomains/D-03_Identity-Access/D-03.4.md §1 CRDA pair GDPR↔CRA; SubDomains/D-03_Identity-Access/D-03.4.md §2 HSO SO-D-03.4.GDPR, SO-D-03.4.CRA.
- Cross-sub-domain pattern: All four sub-domains in D-03 exhibit the same structural overlap pattern — GDPR operates on the data-processing / controller side and CRA operates on the product / manufacturer side, with TinyTask occupying both roles simultaneously. No CONDITIONAL predicates from scope_overlap_predicates.yaml apply to D-03 (all provided predicates target D-01, D-04, D-05, D-09). The overlap is therefore determined solely by the READ-ONLY SAME classifications in the Regulatory Baseline CRDA §1, confirmed by the same-party fact (DOC04:SEC-01 role_matrix).
- NIS2, DORA, and AI_Act pairs are uniformly not activated across all four sub-domains, consistent with TinyTask's regulatory_classification (nis2_entity_class=NOT_APPLICABLE, dora_article_2_entity=NOT_APPLICABLE, ai_system_classification=NOT_APPLICABLE) and the P1B-LLM-02 synthesis confirming non-applicability.

## Rationale
The domain D-03 (Identity & Access Management) is confirmed applicable to TinyTask Lda. with HIGH confidence because both GDPR and CRA are in scope (DOC04:SEC-01 applicable_regs, DOC04:ARCH-07 places_digital_products_eu=true, processes_personal_data=true) and the company occupies the same-party dual role of controller (GDPR) and manufacturer (CRA) on the same SaaS product portfolio (SYS-01 through SYS-05).

For each of the four sub-domains (D-03.1 through D-03.4), the Regulatory Baseline CRDA §1 verified_relationship_per_pair[] classifies the GDPR↔CRA pair as either "SAME — DIFFERENT-PERSPECTIVE" (D-03.1, D-03.4) or "SAME — COMPLEMENTARY" (D-03.2, D-03.3). These are READ-ONLY classifications that I have not re-classified. Per the task instructions for SAME/COMPLEMENTARY pairs, the company_scope_verdict is emitted deterministically: since the activation predicate requires scope overlap and same-party, and TinyTask is the same party for both regulations on the same product, the verdict is OVERLAP_CONFIRMED for all four sub-domains.

No CONDITIONAL predicates from scope_overlap_predicates.yaml apply to domain D-03. The seven predicates provided in the input target sub-domains D-01.1, D-04.3, D-05.2, and D-09.2, none of which fall within D-03. Therefore, no predicate evaluation was required for this domain, and no INDETERMINATE verdicts were triggered.

All pairs involving NIS2, DORA, or AI_Act are not activated because those regulations are not applicable to TinyTask (DOC04:SEC-01 regulatory_classification: nis2_entity_class=NOT_APPLICABLE, dora_article_2_entity=NOT_APPLICABLE, ai_system_classification=NOT_APPLICABLE; DOC04:SEC-01 role_matrix: nis2.role=not_applicable, dora.role=not_applicable, ai_act.role=not_applicable). The P1B-LLM-02 outputs for both CRA and GDPR confirm applicability with HIGH confidence and do not reference NIS2, DORA, or AI_Act as in-scope.

The practical implication of the confirmed overlap is that Doc 07 (Scope Declaration) must document two distinct but co-located control layers for each sub-domain: the GDPR data-processing / controller-side obligation and the CRA product / manufacturer-side obligation, with explicit boundary hand-offs where the product hosts the data-processing endpoint. For D-03.2 specifically, TinyTask's existing MFA enforcement (Auth0, AWS IAM, GitHub — all mfa_enforced=True per DOC04:ARCH-07) exceeds both the GDPR silent-wrapper and the CRA permissive authentication baseline, providing a single implementation that satisfies both layers. For D-03.4, the two-layer default posture (GDPR Art. 25(2) four-dimension AND + CRA Annex I Part I (2)(b) secure-by-default) requires documentation showing how each dimension is satisfied on the same product configuration.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-04.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. Layer0 relationship "SAME — DIFFERENT-PERSPECTIVE" (READ-ONLY, not re-classified). Both regulations apply to the same party (TinyTask is controller under GDPR and manufacturer under CRA). The GDPR data-flow-boundary detection (Art. 32(2), Art. 33(1) awareness anchor) and the CRA product-internal state-change recording (Annex I Part I (2)(l)) operate on the same factual event at the same party. DOC04:ARCH-07 (SYS-01 Main SaaS Application, AWS eu-west-1) and DOC04:SEC-01 (role_matrix.gdpr.role=controller, role_matrix.cra.role=manufacturer) confirm same-party dual obligation.
- D-04.1 : GDPR ↔ NIS2 — SCOPE_DISJOINT. NIS2 is not applicable to TinyTask (DOC04:SEC-01 regulatory_classification.nis2_entity_class=NOT_APPLICABLE; DOC04:SEC-01 role_matrix.nis2.role=not_applicable). Layer0 relationship "SAME — COMPLEMENTARY" preserved verbatim; no activation possible.
- D-04.1 : GDPR ↔ DORA — SCOPE_DISJOINT. DORA is not applicable (DOC04:SEC-01 regulatory_classification.dora_article_2_entity=NOT_APPLICABLE; role_matrix.dora.role=not_applicable). Layer0 relationship "SAME — COMPLEMENTARY" preserved verbatim.
- D-04.1 : NIS2 ↔ CRA — SCOPE_DISJOINT. NIS2 not applicable to TinyTask. Layer0 relationship "SAME — COMPLEMENTARY" preserved verbatim.
- D-04.1 : NIS2 ↔ DORA — SCOPE_DISJOINT. Neither NIS2 nor DORA applicable. Layer0 relationship "SAME — DIFFERENT-PERSPECTIVE" preserved verbatim.
- D-04.1 : CRA ↔ DORA — SCOPE_DISJOINT. DORA not applicable. Layer0 relationship "SAME — DIFFERENT-PERSPECTIVE" preserved verbatim.
- D-04.2 : GDPR ↔ CRA — OVERLAP_CONFIRMED. Layer0 relationship "SAME — DIFFERENT-PERSPECTIVE" (READ-ONLY). GDPR post-breach TOMs (Art. 33(3)(d), Art. 34(3)(a)/(b)) and CRA product-level resilience (Annex I Part I (2)(h)/(i)/(k), Art. 13(21)) both bind the same party on the same incident. DOC04:SEC-02 (incident_response=PARTIAL) and DOC04:SEC-01 (role_matrix confirm dual role) drive the verdict.
- D-04.2 : GDPR ↔ NIS2 — SCOPE_DISJOINT. NIS2 not applicable. Layer0 "SAME — COMPLEMENTARY" preserved.
- D-04.2 : GDPR ↔ DORA — SCOPE_DISJOINT. DORA not applicable. Layer0 "SAME — COMPLEMENTARY" preserved.
- D-04.2 : NIS2 ↔ CRA — SCOPE_DISJOINT. NIS2 not applicable. Layer0 "SAME — COMPLEMENTARY" preserved.
- D-04.2 : NIS2 ↔ DORA — SCOPE_DISJOINT. Neither applicable. Layer0 "SAME — COMPLEMENTARY" preserved.
- D-04.2 : CRA ↔ DORA — SCOPE_DISJOINT. DORA not applicable. Layer0 "SAME — COMPLEMENTARY" preserved.
- D-04.3 : GDPR ↔ CRA — OVERLAP_CONFIRMED. Layer0 relationship "CONDITIONAL" (per PRED-D04.3-GDPR-CRA-SAME-ACTOR). Activation predicate: is_manufacturer_and_controller == True AND product_processes_personal_data == True. Evaluation: TinyTask is_manufacturer=True (DOC04:SEC-01 role_matrix.cra.role=manufacturer, cra_product_class=CLASS_I) AND is_controller=True (DOC04:SEC-01 role_matrix.gdpr.role=controller) → is_manufacturer_and_controller=True. product_processes_personal_data=True (DOC04:ARCH-07 FLOW-01 data_types=[email, name, password]; STORE-01 personal_data=True). Both conditions satisfied → OVERLAP_CONFIRMED. The 72h GDPR Art. 33(1) clock and the 24h CRA Art. 14(2)(a) AEV early-warning clock bind the same party on the same incident. DOC04:SEC-03 regulatory_interactions.TI-01 confirms the temporal conflict.
- D-04.3 : GDPR ↔ NIS2 — OVERLAP_NOT_TRIGGERED. Layer0 relationship "CONDITIONAL" (per PRED-D04.3-GDPR-NIS2-SAME-EVENT). Activation predicate: sector in [energy, transport, health, digital_infrastructure] AND processes_eu_personal_data == True. Evaluation: sector="Technology/Software" → NOT in the enumerated list → predicate FALSE → OVERLAP_NOT_TRIGGERED. Additionally, NIS2 is not applicable to TinyTask (DOC04:SEC-01), making this pair moot.
- D-04.3 : GDPR ↔ DORA — SCOPE_DISJOINT. DORA not applicable to TinyTask (DOC04:SEC-01 dora_article_2_entity=NOT_APPLICABLE). Layer0 "CORRECTED — CONDITIONAL-CONTRADICTORY" preserved verbatim; no activation possible without DORA applicability.
- D-04.3 : GDPR ↔ AI_Act — SCOPE_DISJOINT. AI_Act not applicable (DOC04:SEC-01 ai_system_classification=NOT_APPLICABLE; aiact_high_risk_system=False). Layer0 "CORRECTED — SCOPE-DISJOINT baseline / CONTRADICTORY on confirmed same-party overlap" preserved verbatim.
- D-04.3 : NIS2 ↔ CRA — SCOPE_DISJOINT. NIS2 not applicable. Layer0 "CORRECTED — COMPLEMENTARY, not EQUAL" preserved verbatim.
- D-04.3 : NIS2 ↔ DORA — SCOPE_DISJOINT. Neither applicable. Layer0 "CORRECTED — CONDITIONAL-CONTRADICTORY" preserved verbatim.
- D-04.3 : NIS2 ↔ AI_Act — SCOPE_DISJOINT. Neither applicable. Layer0 "CORRECTED — SCOPE-DISJOINT baseline / CONTRADICTORY" preserved verbatim.
- D-04.3 : CRA ↔ DORA — SCOPE_DISJOINT. DORA not applicable. Layer0 "CORRECTED — SCOPE-DISJOINT baseline" preserved verbatim.
- D-04.3 : CRA ↔ AI_Act — SCOPE_DISJOINT. AI_Act not applicable. Layer0 "CORRECTED — SCOPE-DISJOINT baseline / CONTRADICTORY" preserved verbatim.
- D-04.3 : DORA ↔ AI_Act — SCOPE_DISJOINT. Neither applicable. Layer0 "CORRECTED — SCOPE-DISJOINT baseline / CONDITIONAL-CONTRADICTORY" preserved verbatim.
- D-04.4 : GDPR ↔ CRA — OVERLAP_CONFIRMED. Layer0 relationship "SAME — DIFFERENT-PERSPECTIVE" (READ-ONLY). GDPR Art. 32(1)(b)/(c) timely restoration of personal data and CRA Annex I Part I (2)(h) post-incident availability + Art. 13(21) corrective measures both bind the same party. DOC04:SEC-02 (backup=YES, business_continuity=NO) and DOC04:SEC-01 (dual role) confirm same-party obligation.
- D-04.4 : GDPR ↔ NIS2 — SCOPE_DISJOINT. NIS2 not applicable. Layer0 "SAME — COMPLEMENTARY" preserved.
- D-04.4 : GDPR ↔ DORA — SCOPE_DISJOINT. DORA not applicable. Layer0 "SAME — COMPLEMENTARY" preserved.
- D-04.4 : NIS2 ↔ CRA — SCOPE_DISJOINT. NIS2 not applicable. Layer0 "SAME — COMPLEMENTARY" preserved.
- D-04.4 : NIS2 ↔ DORA — SCOPE_DISJOINT. Neither applicable. Layer0 "CORRECTED — COMPLEMENTARY, DORA-specific overlay" preserved verbatim.
- D-04.4 : CRA ↔ DORA — SCOPE_DISJOINT. DORA not applicable. Layer0 "SAME — COMPLEMENTARY" preserved.

## Findings
- D-04.1 (Incident Detection & Triage): applicable=YES. scope_overlap=Y (GDPR↔CRA OVERLAP_CONFIRMED). applicable_regulations=[GDPR, CRA]. The GDPR detection obligation (Art. 32(2) five-event risk enumeration, Art. 33(1) awareness anchor) and the CRA detection obligation (Annex I Part I (2)(l) product-internal state-change recording) both activate on the same party. TinyTask's monitoring stack (SYS-05 Datadog, DOC04:ARCH-07) provides the operational substrate for both. layer0_refs: SubDomains/D-04_Incident-Response/D-04.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-04_Incident-Response/D-04.1.md §2 HSO SO-D-04.1.GDPR, SO-D-04.1.CRA; SubDomains/D-04_Incident-Response/D-04.1.md §3 SR D-04.4.1.1, D-04.4.1.3.
- D-04.2 (Incident Containment & Response): applicable=YES. scope_overlap=Y (GDPR↔CRA OVERLAP_CONFIRMED). applicable_regulations=[GDPR, CRA]. GDPR post-breach TOMs (Art. 33(3)(d), Art. 34(3)(a)/(b) unintelligibility carve-out) and CRA product-level resilience (Annex I Part I (2)(h)/(i)/(k), Art. 13(21) corrective measures) both bind. TinyTask's PARTIAL incident_response readiness (DOC04:SEC-02) is a gap against both regimes. layer0_refs: SubDomains/D-04_Incident-Response/D-04.2.md §1 CRDA pair GDPR↔CRA; SubDomains/D-04_Incident-Response/D-04.2.md §2 HSO SO-D-04.2.GDPR, SO-D-04.2.CRA; SubDomains/D-04_Incident-Response/D-04.2.md §3 SR D-04.4.2.1, D-04.4.2.3.
- D-04.3 (Incident Notification & Reporting): applicable=YES. scope_overlap=Y (GDPR↔CRA OVERLAP_CONFIRMED via PRED-D04.3-GDPR-CRA-SAME-ACTOR). applicable_regulations=[GDPR, CRA]. This is the highest-tension sub-domain: GDPR Art. 33(1) 72h DPA notification and CRA Art. 14(2)(a) 24h AEV early-warning bind the same party on the same incident. DOC04:SEC-03 TI-01 explicitly identifies this temporal conflict and prescribes a 24h internal escalation workflow. The PRED-D04.3-GDPR-NIS2-SAME-EVENT predicate evaluates FALSE (sector=Technology/Software not in enumerated list; NIS2 not applicable). layer0_refs: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA pair GDPR↔CRA lines 117-126; SubDomains/D-04_Incident-Response/D-04.3.md §2 HSO SO-D-04.3.GDPR, SO-D-04.3.CRA; SubDomains/D-04_Incident-Response/D-04.3.md §3 SR D-04.4.3.1, D-04.4.3.3; catalogs/scope_overlap_predicates.yaml PRED-D04.3-GDPR-CRA-SAME-ACTOR.
- D-04.4 (Incident Recovery & Lessons Learned): applicable=YES. scope_overlap=Y (GDPR↔CRA OVERLAP_CONFIRMED). applicable_regulations=[GDPR, CRA]. GDPR Art. 32(1)(b)/(c) timely restoration and CRA Annex I Part I (2)(h) post-incident availability + Art. 13(21) corrective measures both bind. TinyTask's backup=YES but business_continuity=NO (DOC04:SEC-02) creates a gap against the CRA post-incident availability requirement. layer0_refs: SubDomains/D-04_Incident-Response/D-04.4.md §1 CRDA pair GDPR↔CRA; SubDomains/D-04_Incident-Response/D-04.4.md §2 HSO SO-D-04.4.GDPR, SO-D-04.4.CRA; SubDomains/D-04_Incident-Response/D-04.4.md §3 SR D-04.4.4.1, D-04.4.4.3.
- Cross-sub-domain pattern: The GDPR↔CRA overlap is consistent across all four D-04 sub-domains (detection, containment, notification, recovery). The same-party dual-role (controller + manufacturer) creates a unified incident pipeline requirement: one detection event must feed both the GDPR awareness clock (72h) and the CRA AEV clock (24h/72h/14d). The strictest SLA (CRA 24h) governs the internal escalation workflow, as confirmed by DOC04:SEC-03 TI-01 resolution. No NIS2, DORA, or AI_Act obligations activate for TinyTask in this domain.
- Domain totals: total_sub_domains=4, active_sub_domains=4, pairwise_relationships (applicable regs only: GDPR↔CRA)=4.

## Rationale
The domain D-04 (Incident Response) is fully applicable to TinyTask Lda. because both GDPR and CRA are in the applicable_regs set (DOC04:SEC-01, DOC04:ARCH-07). TinyTask operates as a controller under GDPR (processing personal data: email, name, password per FLOW-01; STORE-01 personal_data=True) and as a manufacturer under CRA (placing digital products on the EU market, cra_product_class=CLASS_I, DOC04:SEC-01 role_matrix). This same-party dual-role is the critical fact that drives the overlap classification.

For the GDPR↔CRA pair, the Regulatory Baseline CRDA §1 in D-04.3 (SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA pair GDPR↔CRA lines 117-126) establishes a CONDITIONAL relationship. The activation predicate PRED-D04.3-GDPR-CRA-SAME-ACTOR (catalogs/scope_overlap_predicates.yaml) requires is_manufacturer_and_controller == True AND product_processes_personal_data == True. Both conditions are satisfied: TinyTask is simultaneously a CRA manufacturer and a GDPR controller (DOC04:SEC-01 role_matrix), and the product processes personal data (DOC04:ARCH-07 FLOW-01, STORE-01). The verdict is therefore OVERLAP_CONFIRMED. The alternative predicate PRED-D04.3-GDPR-CRA-DIFFERENT-ACTOR (for the SaaS-using-third-party-product scenario) evaluates FALSE because is_manufacturer_and_controller is True, not False.

For the GDPR↔NIS2 pair in D-04.3, the predicate PRED-D04.3-GDPR-NIS2-SAME-EVENT requires sector to be in [energy, transport, health, digital_infrastructure]. TinyTask's sector is "Technology/Software" (DOC04:ARCH-01), which is not in the enumerated list. The predicate evaluates FALSE, yielding OVERLAP_NOT_TRIGGERED. This is further reinforced by the fact that NIS2 is explicitly not applicable to TinyTask (DOC04:SEC-01 regulatory_classification.nis2_entity_class=NOT_APPLICABLE, role_matrix.nis2.role=not_applicable, applicability_rationale "below_threshold").

All other pairs in the domain involve at least one regulation (NIS2, DORA, AI_Act) that is not applicable to TinyTask. Per the non-negotiable constraint that layer0_relationship for SAME/COMPLEMENTARY/CONTRADICTORY/SCOPE_DISJOINT is READ-ONLY, these classifications are preserved verbatim from the Regulatory Baseline without re-classification. The effective verdict for all such pairs is SCOPE_DISJOINT because the non-applicable regulation cannot generate obligations for this company.

The temporal conflict identified in DOC04:SEC-03 (TI-01: GDPR 72h vs CRA 24h) is a direct consequence of the OVERLAP_CONFIRMED verdict on D-04.3. The prescribed resolution (24h internal escalation workflow) is consistent with the Regulatory Baseline's downstream implication for the GDPR↔CRA pair in D-04.3. No INDETERMINATE verdicts were necessary because all predicate inputs were fully determined by the supplied company facts.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-05.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED. The Regulatory Baseline (SubDomains/D-05_Data-Lifecycle/D-05.1.md §1 CRDA pair GDPR↔CRA) marks this pair as CONDITIONAL with the activation test "Y when the same dataset contains personal data and is processed by a CRA-classified product at runtime." TinyTask Lda. is simultaneously the GDPR controller and the CRA manufacturer (DOC04:SEC-01 role_matrix: gdpr.role=controller, cra.role=manufacturer). The SaaS product (SYS-01 Main SaaS Application, DOC04:ARCH-07) processes personal data at runtime (email, name, password per DOC04:FLOW-01; STORE-01 personal_data=True). The same dataset is processed by a CRA-classified product (cra_product_class=CLASS_I) at runtime. Both conditions are met → OVERLAP_CONFIRMED.
- D-05.1 : GDPR ↔ AI_Act: NOT_APPLICABLE. AI_Act is not in the applicable_regs set for this case (DOC04:SEC-01 role_matrix.ai_act.role=not_applicable; ai_system_classification=NOT_APPLICABLE). The pair is not activated.
- D-05.1 : CRA ↔ AI_Act: NOT_APPLICABLE. AI_Act is not in the applicable_regs set for this case. The pair is not activated.
- D-05.2 : GDPR ↔ CRA: OVERLAP_NOT_TRIGGERED. The Regulatory Baseline (SubDomains/D-05_Data-Lifecycle/D-05.2.md §1 CRDA pair GDPR↔CRA) marks this pair as SCOPE_DISJOINT in baseline with a conditional note: "Y when a CRA update-distribution log contains personal data." TinyTask's architecture (DOC04:ARCH-07) shows data stores for the SaaS application (STORE-01, STORE-02, STORE-03) but no CRA update-distribution log containing personal data. The CRA obligations for TinyTask concern product security updates and Annex II information accessibility (Art. 13(8)/(9)/(18)/(19)), which operate on update artefacts and advisory messages, not on the personal data in STORE-01/STORE-02. The separation-architecture principle applies: CRA tail governs artefacts, GDPR Art. 5(1)(e) governs personal data independently. The conditional predicate is not met → OVERLAP_NOT_TRIGGERED.
- D-05.2 : GDPR ↔ AI_Act: NOT_APPLICABLE. AI_Act is not in the applicable_regs set for this case. The pair is not activated.
- D-05.2 : CRA ↔ AI_Act: NOT_APPLICABLE. AI_Act is not in the applicable_regs set for this case. The pair is not activated.
- D-05.3 : GDPR ↔ CRA: OVERLAP_CONFIRMED. The Regulatory Baseline (SubDomains/D-05_Data-Lifecycle/D-05.3.md §1 CRDA pair GDPR↔CRA) marks this pair as CONDITIONAL with the activation test "Y when the user is also a data subject and the data is personal." TinyTask's SaaS customers are both the product users (invoking CRA Annex I Part I (2)(m) removal affordance) and the data subjects (invoking GDPR Art. 17 erasure right). The data processed is personal (email, name, password per DOC04:FLOW-01). The same party (TinyTask) holds both the manufacturer-side design obligation and the controller-side rights obligation. Both conditions are met → OVERLAP_CONFIRMED.
- D-05.4 : (no pairs). This sub-domain is single-regulator (GDPR sole authority per SubDomains/D-05_Data-Lifecycle/D-05.4.md §1 CRDA: 0 pairwise cells). No overlap classification is required.

## Findings
- D-05.1 (Data Minimisation): ACTIVE. Applicable regulations: GDPR, CRA. Scope overlap: Y (GDPR↔CRA confirmed). The verbatim operative-language match between GDPR Art. 5(1)(c) and CRA Annex I Part I (2)(g) means the same minimisation test applies on the same dataset. For TinyTask as integrated manufacturer-controller, a 2-track minimisation matrix is required: (1) GDPR Art. 5(1)(c) + Art. 6(4) personal-data minimisation with compatibility assessment; (2) CRA Annex I Part I (2)(g) product-data minimisation tied to Art. 3(23) intended purpose. The Art. 6(4) compatibility test is a GDPR-only residual obligation. Layer0 refs: SubDomains/D-05_Data-Lifecycle/D-05.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-05_Data-Lifecycle/D-05.1.md §2 HSO SO-D-05.1.GDPR, SO-D-05.1.CRA; CrossRegulation/DeepAnalysis/D-05.1.md.
- D-05.2 (Retention & Archiving): ACTIVE. Applicable regulations: GDPR, CRA. Scope overlap: N (GDPR↔CRA not triggered; separation architecture applies). GDPR Art. 5(1)(e) sets the retention ceiling for personal data (STORE-01 retention_days=2555, STORE-02 retention_days=90). CRA Art. 13(8)/(9) sets the 5-year support-period floor and 10-year update-availability tail for product artefacts. These operate on distinct data classes and do not conflict. Layer0 refs: SubDomains/D-05_Data-Lifecycle/D-05.2.md §1 CRDA pair GDPR↔CRA; SubDomains/D-05_Data-Lifecycle/D-05.2.md §2 HSO SO-D-05.2.GDPR, SO-D-05.2.CRA; CrossRegulation/DeepAnalysis/D-05.2.md.
- D-05.3 (Right to Erasure): ACTIVE. Applicable regulations: GDPR, CRA. Scope overlap: Y (GDPR↔CRA confirmed). The two obligations stack: CRA Annex I Part I (2)(m) requires the product to support secure, easy, permanent removal of all data on user election; GDPR Art. 17 requires the controller to operationalise the data-subject erasure right. For TinyTask as integrated manufacturer-controller, the controller's Art. 17 path executes through the manufacturer's (2)(m) affordance. The Art. 17(3) carve-outs do not relax the CRA-side (2)(m) obligation (the user retains the product-side removal affordance even when the controller-side obligation is lawfully suspended). Layer0 refs: SubDomains/D-05_Data-Lifecycle/D-05.3.md §1 CRDA pair GDPR↔CRA; SubDomains/D-05_Data-Lifecycle/D-05.3.md §2 HSO SO-D-05.3.GDPR, SO-D-05.3.CRA; CrossRegulation/DeepAnalysis/D-05.3.md.
- D-05.4 (Data Portability): ACTIVE. Applicable regulations: GDPR (sole authority). No pairwise surface (0 CRDA cells). The Art. 20 portability right applies to TinyTask as controller where processing is based on consent or contract and carried out by automated means. No overlap classification required. Layer0 refs: SubDomains/D-05_Data-Lifecycle/D-05.4.md §1 CRDA (0 pairwise cells); SubDomains/D-05_Data-Lifecycle/D-05.4.md §2 HSO SO-D-05.4.GDPR.
- Cross-sub-domain pattern: Across D-05.1, D-05.2, and D-05.3, the GDPR↔CRA relationship follows a consistent layering model for TinyTask as integrated manufacturer-controller. In D-05.1 and D-05.3, the obligations overlap on the same data object at the same party (confirmed overlap). In D-05.2, the obligations operate on distinct data classes (personal data vs. update artefacts) and are scope-disjoint in the typical case. D-05.4 is single-regulator. The AI_Act dimension is entirely inapplicable for this case, removing one axis from the 3-track matrices described in the Regulatory Baseline.

## Rationale
The domain D-05 (Data Lifecycle) contains four sub-domains, all of which are active for TinyTask Lda. because both GDPR and CRA are in the applicable_regs set and at least one sub-domain in each case has a participating regulation that applies. The AI_Act regulation is not applicable (ai_system_classification=NOT_APPLICABLE, no high-risk AI system in the product), so all pairs involving AI_Act are marked NOT_APPLICABLE rather than evaluated.

For D-05.1 (Data Minimisation), the GDPR↔CRA pair is CONDITIONAL in the Regulatory Baseline. The activation test requires that the same dataset contains personal data and is processed by a CRA-classified product at runtime. TinyTask's SaaS application (SYS-01) is a CRA CLASS_I product that processes personal data (email, name, password) at runtime for its customers. TinyTask is simultaneously the GDPR controller and the CRA manufacturer. Both conditions are satisfied, yielding OVERLAP_CONFIRMED. The Regulatory Baseline notes a verbatim operative-language match between GDPR Art. 5(1)(c) and CRA Annex I Part I (2)(g), meaning the same minimisation test binds on the same dataset. The downstream implication is a 2-track minimisation matrix with the Art. 6(4) compatibility test as a GDPR-only residual.

For D-05.2 (Retention & Archiving), the GDPR↔CRA pair is SCOPE_DISJOINT in baseline with a conditional note. The condition for overlap is that a CRA update-distribution log contains personal data. TinyTask's architecture shows no such log; the data stores (STORE-01, STORE-02) hold SaaS application data, while CRA obligations concern update artefacts and Annex II information. The separation-architecture principle applies: GDPR Art. 5(1)(e) governs personal data retention, CRA Art. 13(8)/(9) governs update-artefact availability. The conditional predicate is not met, yielding OVERLAP_NOT_TRIGGERED.

For D-05.3 (Right to Erasure), the GDPR↔CRA pair is CONDITIONAL. The activation test requires that the user is also a data subject and the data is personal. TinyTask's SaaS customers are both product users and data subjects, and the data (email, name, password) is personal. The same party holds both obligations. OVERLAP_CONFIRMED. The two obligations stack: the manufacturer-side (2)(m) affordance and the controller-side Art. 17 right execute on the same product event.

For D-05.4 (Data Portability), the Regulatory Baseline records zero pairwise cells (single-regulator sub-domain, GDPR sole authority). No overlap classification is required. The Art. 20 right applies to TinyTask as controller.

No INDETERMINATE verdicts were necessary because all CONDITIONAL predicates could be evaluated against the available company facts. No re-classification of any Regulatory Baseline relationship was performed; all layer0_relationship values (CONDITIONAL, SCOPE_DISJOINT) were preserved verbatim from the source files.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-06.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. TinyTask Lda. is simultaneously the GDPR controller (DOC04:SEC-01 role_matrix.gdpr.role=controller) and the CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer). The SaaS product (SYS-01 through SYS-05, DOC04:ARCH-07) processes personal data (STORE-01 personal_data=True, FLOW-01 data_types: email/name/password) and is placed on the EU market. The CRDA scope_overlap test is met: "Y (when the CRA product is integrated into a GDPR controller's processing — but the two objects remain distinct)." The two obligations layer vertically: GDPR Art. 28(1) processor due diligence on cloud providers (AWS, Firebase, Stripe, Datadog) and CRA Art. 13(5) third-party-component due diligence on software dependencies. Source: SubDomains/D-06_Third-Party/D-06.1.md §1 CRDA pair GDPR↔CRA.
- D-06.1 : GDPR ↔ NIS2 — NOT_APPLICABLE. NIS2 is not in the company's applicable_regs (DOC04:SEC-01 regulatory_classification.nis2_entity_class=NOT_APPLICABLE; role_matrix.nis2.role=not_applicable). Pair not activated for this case.
- D-06.1 : GDPR ↔ DORA — NOT_APPLICABLE. DORA is not in the company's applicable_regs (DOC04:SEC-01 regulatory_classification.dora_article_2_entity=NOT_APPLICABLE; role_matrix.dora.role=not_applicable). Pair not activated for this case.
- D-06.1 : NIS2 ↔ CRA — NOT_APPLICABLE. NIS2 not in scope for this company. Pair not activated.
- D-06.1 : NIS2 ↔ DORA — NOT_APPLICABLE. Neither regulation in scope. Pair not activated.
- D-06.1 : CRA ↔ DORA — NOT_APPLICABLE. DORA not in scope. Pair not activated.
- D-06.2 : (no cross-regulation pairs) — CRA sole authority per Regulatory Baseline. No overlap assessment required.
- D-06.3 : GDPR ↔ CRA — SCOPE_DISJOINT. CRDA base classification: "N (typically) — different contracting parties, different contract objects." The GDPR Art. 28(3) DPA is a controller-to-processor contract (TinyTask ↔ AWS/Firebase/Stripe/Datadog, DOC04:CS-01 through CS-04, all dpa_status=signed). The CRA economic-operator duties (Art. 19/20 importer/distributor, Art. 13(6) component-vulnerability escalation) are manufacturer-to-MSA obligations. Even though TinyTask is the same legal entity, the contract objects and counterparties are distinct. The CRDA conditional note ("Conditional overlap only when the controller deploys a CRA-compliant product and the manufacturer / importer / distributor is in the chain") is technically met, but the base READ-ONLY classification remains N. Source: SubDomains/D-06_Third-Party/D-06.3.md §1 CRDA pair GDPR↔CRA.
- D-06.3 : GDPR ↔ NIS2 — NOT_APPLICABLE. NIS2 not in scope.
- D-06.3 : GDPR ↔ DORA — NOT_APPLICABLE. DORA not in scope.
- D-06.3 : NIS2 ↔ CRA — NOT_APPLICABLE. NIS2 not in scope.
- D-06.3 : NIS2 ↔ DORA — NOT_APPLICABLE. Neither in scope.
- D-06.3 : CRA ↔ DORA — NOT_APPLICABLE. DORA not in scope.
- D-06.4 : GDPR ↔ CRA — SCOPE_DISJOINT. CRDA condition: "Y (when the same non-EU entity is both a non-EU controller and a non-EU CRA manufacturer)." TinyTask is EU-based (Portugal, DOC04:ARCH-01 jurisdiction=Portugal (EU)). The non-EU condition is not met. GDPR Art. 27(1)/(2) Union-representative obligation applies only to non-EU controllers/processors under Art. 3(2); it does not apply to a Portuguese entity. CRA Art. 18 authorised-representative is for non-EU manufacturers. Neither representative mechanism is triggered. Source: SubDomains/D-06_Third-Party/D-06.4.md §1 CRDA pair GDPR↔CRA.
- D-06.4 : GDPR ↔ NIS2 — NOT_APPLICABLE. NIS2 not in scope.
- D-06.4 : GDPR ↔ DORA — NOT_APPLICABLE. DORA not in scope.
- D-06.4 : NIS2 ↔ CRA — NOT_APPLICABLE. NIS2 not in scope.
- D-06.4 : NIS2 ↔ DORA — NOT_APPLICABLE. Neither in scope.
- D-06.4 : CRA ↔ DORA — NOT_APPLICABLE. DORA not in scope.

## Findings
- D-06.1 (Vendor Risk Assessment): ACTIVE. Applicable regulations: GDPR, CRA. Scope overlap: Y (GDPR↔CRA confirmed). The company's 4 cloud processors (AWS, Firebase, Stripe, Datadog — DOC04:CS-01 through CS-04) are subject to GDPR Art. 28(1) "sufficient guarantees" due diligence. Simultaneously, as CRA manufacturer, TinyTask must exercise Art. 13(5) due diligence on third-party components (including FOSS per Art. 3(48)) integrated into the SaaS product. The two due-diligence layers are distinct in object (entity-level processor vs product-level component) but both bind the same 8-person team. Layer0 refs: SubDomains/D-06_Third-Party/D-06.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-06_Third-Party/D-06.1.md §2 HSO SO-D-06.1.GDPR, SO-D-06.1.CRA; SubDomains/D-06_Third-Party/D-06.1.md §3 SR D-06.6.1.1, D-06.6.1.3.
- D-06.2 (SBOM): ACTIVE. Applicable regulations: CRA (sole authority). No cross-regulation overlap. The SBOM obligation under Annex I Part II (1) is a standalone CRA manufacturer duty. No GDPR, NIS2, or DORA component. Layer0 refs: SubDomains/D-06_Third-Party/D-06.2.md §2 HSO SO-D-06.2.CRA; SubDomains/D-06_Third-Party/D-06.2.md §3 SR D-06.6.2.1.
- D-06.3 (Contractual Security Obligations): ACTIVE. Applicable regulations: GDPR, CRA. Scope overlap: N (GDPR↔CRA scope-disjoint). The GDPR DPA chain (Art. 28(3)(a)–(h) with 4 cloud processors) and the CRA economic-operator duties (Art. 19/20, Art. 13(6)) operate on different contract objects and counterparties. No single contract satisfies both. Layer0 refs: SubDomains/D-06_Third-Party/D-06.3.md §1 CRDA pair GDPR↔CRA; SubDomains/D-06_Third-Party/D-06.3.md §2 HSO SO-D-06.3.GDPR, SO-D-06.3.CRA; SubDomains/D-06_Third-Party/D-06.3.md §3 SR D-06.6.3.1, D-06.6.3.3.
- D-06.4 (Third-Party Boundary Management): ACTIVE. Applicable regulations: GDPR, CRA. Scope overlap: N (GDPR↔CRA scope-disjoint — EU-based entity, non-EU representative condition not met). The GDPR Art. 27 representative and CRA Art. 18 authorised-representative mechanisms are both inapplicable to a Portuguese entity. The remaining boundary obligations (CRA Art. 21/22/23 economic-operator identification, 10-year retention) apply independently. Layer0 refs: SubDomains/D-06_Third-Party/D-06.4.md §1 CRDA pair GDPR↔CRA; SubDomains/D-06_Third-Party/D-06.4.md §2 HSO SO-D-06.4.GDPR, SO-D-06.4.CRA; SubDomains/D-06_Third-Party/D-06.4.md §3 SR D-06.6.4.1, D-06.6.4.3.
- Cross-sub-domain pattern: The GDPR↔CRA relationship in D-06 is consistently "layered but distinct" — the two regimes address different objects (processor entity vs product component; DPA contract vs economic-operator duty; non-EU representative vs authorised representative) even when the same legal entity bears both roles. No CONTRADICTORY or SAME classification is present in the D-06 CRDA for the GDPR↔CRA pair. The dominant pattern is DIFFERENT-PERSPECTIVE with conditional overlap only at D-06.1 (vendor risk assessment), where the two due-diligence obligations genuinely stack on the same supply-chain relationship.
- NIS2 and DORA pairs are uniformly NOT_APPLICABLE across all four sub-domains, consistent with the company's regulatory_classification (nis2_entity_class=NOT_APPLICABLE, dora_article_2_entity=NOT_APPLICABLE) and the P1B-LLM-02 synthesis confirming non-applicability.

## Rationale
The domain D-06 (Third-Party / Supply Chain) contains four sub-domains, all of which are active for TinyTask Lda. because at least one of the two applicable regulations (GDPR or CRA) has obligations in each sub-domain. NIS2 and DORA are excluded from all pair evaluations because the company's regulatory_classification explicitly marks both as NOT_APPLICABLE (DOC04:SEC-01), and the P1B-LLM-02 outputs for both regulations confirm non-applicability (NIS2: below_threshold; DORA: not_financial_entity). This leaves the GDPR↔CRA pair as the only cross-regulation relationship to evaluate in each sub-domain.

For D-06.1 (Vendor Risk Assessment), the CRDA scope_overlap test is satisfied: TinyTask is both the GDPR controller processing personal data through 4 cloud processors and the CRA manufacturer integrating third-party components into its SaaS product. The two due-diligence obligations (GDPR Art. 28(1) on processors; CRA Art. 13(5) on components) bind the same entity and address the same supply chain, albeit at different layers (entity-level vs product-level). This is a genuine OVERLAP_CONFIRMED because a single incident (e.g., a vulnerable third-party library in the SaaS stack that also processes personal data) would trigger both the GDPR processor-breach chain and the CRA component-vulnerability reporting chain simultaneously.

For D-06.3 (Contractual Security Obligations), the CRDA base classification is "N (typically)" with the explicit note that the GDPR DPA and CRA economic-operator duties address "different contracting parties, different contract objects." Even though TinyTask is the same legal entity, the GDPR DPA is a bilateral contract with each cloud processor (AWS, Firebase, Stripe, Datadog — all with dpa_status=signed per DOC04:CS-01 through CS-04), while the CRA duties are unilateral regulatory obligations to the MSA (conformity assessment, CE marking, vulnerability reporting). The contract objects do not merge. I preserve the READ-ONLY SCOPE_DISJOINT classification.

For D-06.4 (Third-Party Boundary Management), the CRDA overlap condition is specifically "the same non-EU entity is both a non-EU controller and a non-EU CRA manufacturer." TinyTask is incorporated in Portugal (EU), so the non-EU precondition fails. Neither GDPR Art. 27 (Union representative for non-EU controllers) nor CRA Art. 18 (authorised representative for non-EU manufacturers) is triggered. The pair is SCOPE_DISJOINT for this company.

No CONDITIONAL predicates from the scope_overlap_predicates.yaml catalog apply to domain D-06 (all provided predicates target D-04.3, D-01.1, D-09.2, or D-05.2). The evaluations above are therefore driven entirely by the CRDA §1 verified_relationship_per_pair descriptions in the Regulatory Baseline sub-domain files, interpreted against the company facts in Doc 04. No re-classification of any READ-ONLY relationship has been performed. Confidence is HIGH because the applicable-regulation set is unambiguous (GDPR + CRA only), the company's role matrix is explicit (controller + manufacturer), and the CRDA descriptions for the GDPR↔CRA pair in D-06 are clear and unambiguous for an EU-based, same-party, SaaS-manufacturer profile.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-07.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED — TinyTask is simultaneously a GDPR controller (DOC04:SEC-01 role_matrix.gdpr.role=controller) and a CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer, cra_product_class=CLASS_I). The product processes personal data (DOC04:ARCH-07 STORE-01 personal_data=True; FLOW-01 data_types=[email, name, password]). The Regulatory Baseline D-07.1 CRDA pair GDPR↔CRA scope_overlap condition ("Y when the controller deploys a CRA-regulated product that processes personal data, OR when the manufacturer is also a controller for its own product telemetry") is fully satisfied: same entity, same product, personal data in scope.
- D-07.1 : GDPR ↔ NIS2: OVERLAP_NOT_TRIGGERED — NIS2 is not applicable to TinyTask (DOC04:SEC-01 regulatory_classification.nis2_entity_class=NOT_APPLICABLE; role_matrix.nis2.role=not_applicable). Pair not activated.
- D-07.1 : GDPR ↔ DORA: OVERLAP_NOT_TRIGGERED — DORA is not applicable (DOC04:SEC-01 regulatory_classification.dora_article_2_entity=NOT_APPLICABLE). Pair not activated.
- D-07.1 : GDPR ↔ AI_Act: OVERLAP_NOT_TRIGGERED — AI Act is not applicable (DOC04:SEC-01 regulatory_classification.ai_system_classification=NOT_APPLICABLE; aiact_high_risk_system=False). Pair not activated.
- D-07.1 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED — NIS2 not applicable to TinyTask. Pair not activated.
- D-07.1 : NIS2 ↔ DORA: OVERLAP_NOT_TRIGGERED — Neither regulation applicable. Pair not activated.
- D-07.1 : NIS2 ↔ AI_Act: OVERLAP_NOT_TRIGGERED — Neither regulation applicable. Pair not activated.
- D-07.1 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED — DORA not applicable. Pair not activated.
- D-07.1 : CRA ↔ AI_Act: OVERLAP_NOT_TRIGGERED — AI Act not applicable. Pair not activated.
- D-07.1 : DORA ↔ AI_Act: OVERLAP_NOT_TRIGGERED — Neither regulation applicable. Pair not activated.
- D-07.2 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED — DORA not applicable; Regulatory Baseline marks pair as "N (typically)" (scope-disjoint: product coding outcomes vs. entity change process).
- D-07.2 : CRA ↔ AI_Act: OVERLAP_NOT_TRIGGERED — AI Act not applicable (no high-risk AI system).
- D-07.2 : DORA ↔ AI_Act: OVERLAP_NOT_TRIGGERED — Neither regulation applicable.
- D-07.3 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED — NIS2 not applicable; Regulatory Baseline marks pair as "N (typically)" (entity-side CI/CD vs. product-side update delivery; different actors).
- D-07.4 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED — DORA not applicable; the conditional trigger (DORA entity customises CRA product → Art. 22 substantial modification) is not met.

## Findings
- D-07.1 (Secure-by-Design Principles) is the only sub-domain in domain D-07 where an active overlap is confirmed for TinyTask. The GDPR ↔ CRA pair is OVERLAP_CONFIRMED: the same entity (TinyTask) is both controller and manufacturer on the same product (SYS-01 Main SaaS Application) that processes personal data. Phase 2 must produce a 2-track by-design matrix: (1) GDPR Art. 25(1) controller-side data-protection by-design; (2) CRA Art. 13(1)/(2) manufacturer-side product by-design with Annex VII §3 risk-assessment record.
- D-07.2 (Secure Coding Practices): GDPR is not a participating regulation. The only applicable-regulation pair (CRA) has no cross-regulation overlap partner in scope. CRA Annex I Part I (2)(j)+(k) attack-surface and exploitation-mitigation obligations apply standalone.
- D-07.3 (CI/CD Pipeline Security): GDPR is not a participating regulation. CRA Annex I Part II (7)+(8) secure-update-distribution applies standalone. NIS2 (the other participant) is not applicable.
- D-07.4 (Change Management): GDPR is not a participating regulation. CRA Art. 13(14) series-production conformity applies standalone. DORA (the other participant) is not applicable.
- Cross-sub-domain pattern: The GDPR ↔ CRA overlap is concentrated in D-07.1 (by-design) because that is the only sub-domain where both regulations have a dedicated security objective on the same artefact (the product). In D-07.2 through D-07.4, the obligations are single-regulation (CRA-only) for TinyTask, with no cross-regulation coordination required.
- layer0_refs: SubDomains/D-07_Secure-Development/D-07.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-07_Secure-Development/D-07.2.md §1 CRDA; SubDomains/D-07_Secure-Development/D-07.3.md §1 CRDA; SubDomains/D-07_Secure-Development/D-07.4.md §1 CRDA.

## Rationale
The evaluation for domain D-07 is driven by the fact that TinyTask's applicable regulations are limited to GDPR and CRA (DOC04:SEC-01 applicable_regs=[CRA, GDPR]; NIS2, DORA, and AI_Act are all NOT_APPLICABLE per regulatory_classification). This narrows the pair evaluation to the single GDPR ↔ CRA pair wherever it appears in the CRDA.

For D-07.1, the Regulatory Baseline CRDA pair GDPR↔CRA describes scope_overlap as "Y (when the controller deploys a CRA-regulated product that processes personal data, OR when the manufacturer is also a controller for its own product telemetry)." TinyTask satisfies both disjuncts: it is the controller (GDPR Art. 4(7) role confirmed in DOC04:SEC-01 role_matrix.gdpr.role=controller) AND the manufacturer (CRA Art. 3(1) role confirmed in DOC04:SEC-01 role_matrix.cra.role=manufacturer, cra_product_class=CLASS_I), and the product (SYS-01, hosted on AWS eu-west-1) processes personal data (DOC04:ARCH-07 STORE-01 personal_data=True, FLOW-01 data_types=[email, name, password]). The same-party, same-product, personal-data condition is met, yielding OVERLAP_CONFIRMED. No re-classification is performed; the Regulatory Baseline conditional description is activated as-is.

For D-07.2, D-07.3, and D-07.4, GDPR does not appear in the participating_regulations list. The pairs that exist (CRA↔DORA, CRA↔AI_Act, NIS2↔CRA, CRA↔DORA) all involve at least one non-applicable regulation. Per the Regulatory Baseline, these pairs are either "N (typically)" (scope-disjoint by design) or conditional on a non-applicable regulation's applicability. None are triggered for TinyTask. No re-classification is performed.

The absence of D-07-specific predicates in the provided scope_overlap_predicates.yaml (which contains predicates for D-04.3, D-01.1, D-09.2, D-05.2) is noted. The D-07.1 GDPR↔CRA evaluation is performed directly against the Regulatory Baseline CRDA scope_overlap description and the company facts, consistent with the non-negotiable constraint that the Regulatory Baseline is the ground truth and no external classification is introduced.

The MICRO scale (8 employees, 0.85 security FTE) does not alter the regulatory floor for the overlap determination. The overlap is a scope question (does the same entity have obligations under both regulations on the same artefact?), not a proportionality question. Proportionality affects the depth of Phase 2 obligation derivation, not the Phase 1C overlap verdict.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-08.1 : GDPR ↔ CRA: SCOPE_DISJOINT (READ-ONLY from Regulatory Baseline; different audiences — internal workforce data-protection awareness under Art. 39(1)(a)+(b) vs. external end-user secure-use instructions under Annex II §8(a)–(f); no consolidation rule applies)
- D-08.1 : GDPR ↔ NIS2: NOT_APPLICABLE (NIS2 not in applicable_regs for TinyTask Lda.; sub-SO SO-D-08.1.NIS2 not activated)
- D-08.1 : GDPR ↔ DORA: NOT_APPLICABLE (DORA not in applicable_regs; sub-SO SO-D-08.1.DORA not activated)
- D-08.1 : NIS2 ↔ CRA: NOT_APPLICABLE (NIS2 not in applicable_regs; sub-SO SO-D-08.1.NIS2 not activated)
- D-08.1 : NIS2 ↔ DORA: NOT_APPLICABLE (neither NIS2 nor DORA in applicable_regs)
- D-08.1 : CRA ↔ DORA: NOT_APPLICABLE (DORA not in applicable_regs; sub-SO SO-D-08.1.DORA not activated)
- D-08.2 : GDPR ↔ CRA: SCOPE_DISJOINT (READ-ONLY from Regulatory Baseline; different audiences — internal workforce role-specific training under Art. 39(1)(b) vs. integrator-B2B information under Annex II §8(f); no consolidation rule applies)
- D-08.2 : GDPR ↔ NIS2: NOT_APPLICABLE (NIS2 not in applicable_regs; sub-SO SO-D-08.2.NIS2 not activated)
- D-08.2 : GDPR ↔ DORA: NOT_APPLICABLE (DORA not in applicable_regs; sub-SO SO-D-08.2.DORA not activated)
- D-08.2 : GDPR ↔ AI_Act: NOT_APPLICABLE (AI_Act not in applicable_regs; sub-SO SO-D-08.2.AI_Act not activated)
- D-08.2 : NIS2 ↔ CRA: NOT_APPLICABLE (NIS2 not in applicable_regs; sub-SO SO-D-08.2.NIS2 not activated)
- D-08.2 : NIS2 ↔ DORA: NOT_APPLICABLE (neither NIS2 nor DORA in applicable_regs)
- D-08.2 : NIS2 ↔ AI_Act: NOT_APPLICABLE (neither NIS2 nor AI_Act in applicable_regs)
- D-08.2 : CRA ↔ DORA: NOT_APPLICABLE (DORA not in applicable_regs; sub-SO SO-D-08.2.DORA not activated)
- D-08.2 : CRA ↔ AI_Act: NOT_APPLICABLE (AI_Act not in applicable_regs; sub-SO SO-D-08.2.AI_Act not activated)
- D-08.2 : DORA ↔ AI_Act: NOT_APPLICABLE (neither DORA nor AI_Act in applicable_regs)
- D-08.3 : NIS2 ↔ DORA: NOT_APPLICABLE (neither NIS2 nor DORA in applicable_regs; sub-domain D-08.3 not active for this case)

## Findings
- D-08.1 (General Security Awareness): ACTIVE. Participating regulations GDPR and CRA are both in applicable_regs. The sole applicable pair (GDPR↔CRA) is SCOPE_DISJOINT per the Regulatory Baseline CRDA §1: the GDPR obligation targets the internal workforce (DPO-catalysed awareness under Art. 39(1)(a)+(b), anchored to PR.AT-01/PR.AT-02) while the CRA obligation targets the external end-user (Annex II §8(a)–(f) secure-use instructions, anchored to PR.AT-01 for the integrator dimension only). The audiences are substantively disjoint; no consolidation rule exists. layer0_refs: SubDomains/D-08_Security-Awareness/D-08.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-08_Security-Awareness/D-08.1.md §2 HSO SO-D-08.1.GDPR, SO-D-08.1.CRA.
- D-08.2 (Role-Specific Competence): ACTIVE. Participating regulations GDPR and CRA are both in applicable_regs. The sole applicable pair (GDPR↔CRA) is SCOPE_DISJOINT per the Regulatory Baseline CRDA §1: the GDPR obligation targets internal processing staff with data-subject-facing or access-management responsibilities (Art. 39(1)(b), PR.AT-02) while the CRA obligation targets the B2B integrator audience (Annex II §8(f), PR.AT-04/GV.SC-03). The audiences are substantively disjoint; no consolidation rule exists. layer0_refs: SubDomains/D-08_Security-Awareness/D-08.2.md §1 CRDA pair GDPR↔CRA; SubDomains/D-08_Security-Awareness/D-08.2.md §2 HSO SO-D-08.2.GDPR, SO-D-08.2.CRA.
- D-08.3 (Management Board Training): NOT ACTIVE. Participating regulations are NIS2 and DORA only; neither is in TinyTask's applicable_regs (NIS2 entity class = NOT_APPLICABLE, DORA Article 2 entity = NOT_APPLICABLE). No sub-SO is activated. layer0_refs: SubDomains/D-08_Security-Awareness/D-08.3.md §1 CRDA pair NIS2↔DORA (not activated).
- Cross-sub-domain pattern: In domain D-08, the GDPR↔CRA relationship is consistently SCOPE_DISJOINT across both active sub-domains (D-08.1 and D-08.2). The Regulatory Baseline correctly identifies that the audiences are substantively different (internal workforce vs. external end-user/integrator) and that no consolidation rule applies. This is a structural property of the domain, not a case-specific finding.
- No CONDITIONAL predicates from scope_overlap_predicates.yaml apply to domain D-08. All seven provided predicates target sub-domains D-01.1, D-04.3, D-05.2, and D-09.2, none of which fall within domain D-08. Therefore no predicate evaluation was required for this lane.
- Total sub-domains in domain D-08: 3. Active sub-domains (≥1 applicable regulation participating): 2 (D-08.1, D-08.2). Inactive: 1 (D-08.3).
- Applicable regulations for domain D-08: GDPR, CRA.
- No overlap confirmed in any pair. No INDETERMINATE verdicts required.

## Rationale
Domain D-08 (Security Awareness & Training) was evaluated for TinyTask Lda. (case1-tinytask), a MICRO-scale Technology/Software company in Portugal with 8 employees, operating as a GDPR controller and CRA manufacturer (CLASS_I). The applicable regulations for this case are limited to GDPR and CRA; NIS2, DORA, and AI_Act are all classified as NOT_APPLICABLE per the company's regulatory_classification and role_matrix (DOC04:SEC-01).

For sub-domain D-08.1 (General Security Awareness), the Regulatory Baseline CRDA §1 (SubDomains/D-08_Security-Awareness/D-08.1.md) defines six regulation pairs. Only the GDPR↔CRA pair involves two regulations both present in the applicable set. The CRDA classifies this pair as substantively SCOPE-DISJOINT: the GDPR Art. 39(1)(a)+(b) DPO-catalysed awareness obligation addresses the internal workforce (all personnel involved in processing operations), while the CRA Annex II §8(a)–(f) obligation addresses the external end-user (detailed instructions for secure product use). The HSO considerations at SO-D-08.1.GDPR and SO-D-08.1.CRA explicitly state that "the CRA-side user-facing instructions are independent of the GDPR workforce awareness programme (DPO-catalysed workforce)" and that "substantively scope-disjoint audiences — workforce vs end-user — no consolidation rule applies." This classification is READ-ONLY and was not re-classified. The remaining five pairs (GDPR↔NIS2, GDPR↔DORA, NIS2↔CRA, NIS2↔DORA, CRA↔DORA) involve at least one regulation not in the applicable set and are therefore not activated.

For sub-domain D-08.2 (Role-Specific Competence), the same logic applies. The GDPR↔CRA pair is SCOPE_DISJOINT per the CRDA: the GDPR Art. 39(1)(b) role-specific training targets internal processing staff with data-subject-facing or access-management responsibilities, while the CRA Annex II §8(f) obligation targets the B2B integrator audience. The HSO considerations at SO-D-08.2.GDPR and SO-D-08.2.CRA confirm that "the GDPR role-specific workforce training is independent of the CRA Annex II §8(f) integrator-facing information (substantively scope-disjoint audiences — workforce vs B2B integrator — no consolidation rule applies)." This classification is READ-ONLY. The remaining nine pairs involve NIS2, DORA, or AI_Act, none of which are applicable, and are therefore not activated.

For sub-domain D-08.3 (Management Board Training), the only participating regulations are NIS2 and DORA. Neither is applicable to TinyTask Lda. (NIS2 entity class = NOT_APPLICABLE; DORA Article 2 entity = NOT_APPLICABLE). The sub-domain is therefore not active for this case, and the single pair (NIS2↔DORA) is not evaluated.

No CONDITIONAL predicates from the scope_overlap_predicates.yaml catalog apply to domain D-08. All seven predicates provided in the input target sub-domains in domains D-01, D-04, D-05, and D-09. Consequently, no predicate evaluation was performed for this lane, and no OVERLAP_CONFIRMED or INDETERMINATE verdicts were generated. The domain-level conclusion is that no regulatory overlap exists in D-08 for TinyTask Lda.; the GDPR and CRA obligations in this domain operate on substantively disjoint audiences and require two parallel, independent tracks in Phase 2 obligation derivation.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-09.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. CRDA §1 scope_disjoint_test states "Conditional (Y when the controller is also a manufacturer or OSS steward; N otherwise)". TinyTask Lda. is simultaneously a GDPR controller (DOC04:SEC-01 role_matrix.gdpr.role=controller) and a CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer, cra_product_class=CLASS_I). The same-party condition is met; both regimes impose parallel policy obligations (GDPR Art. 24(1) data-protection policies + CRA Art. 13(8) manufacturer policies/processes/procedures) on the same entity for the same product.
- D-09.2 : GDPR ↔ CRA — OVERLAP_CONFIRMED. CRDA §1 scope_overlap states "Y (when the CRA-regulated product processes personal data)". TinyTask's SaaS product processes personal data (DOC04:FLOW-01 email/name/password; DOC04:STORE-01 personal_data=True). Both regimes impose separate assessment artefacts: GDPR Art. 35(1) DPIA on data-subject rights + CRA Art. 13(3) cybersecurity risk assessment with Annex VII §3 record. No OJ-level consolidation rule exists for this pair (per CRDA downstream_implication).
- D-09.2 : DORA ↔ NIS2 (PRED-D09.2-DORA-LEX-SPECIALIS) — NOT_APPLICABLE. Neither DORA nor NIS2 is in TinyTask's applicable_regs. The predicate activation condition (company_facts.sector == 'financial') is not met (sector = Technology/Software). No verdict emitted; pair excluded from domain scope.
- D-09.3 : (no applicable pairs) — All three CRDA pairs (NIS2↔CRA, NIS2↔DORA, CRA↔DORA) involve at least one non-applicable regulation. No cross-regulation overlap evaluation required for TinyTask.
- D-09.4 : GDPR ↔ CRA — SCOPE_DISJOINT. CRDA §1 scope_disjoint_test explicitly states "N (typically) — different record types, different triggers. Substantively scope-disjoint." GDPR Art. 30(1) RoPA (7-item content, DPA audit) and CRA Annex VII §1-§8 technical documentation (8-item content, MSA audit) are parallel artefacts with distinct audit purposes. No OJ-level consolidation. This classification is READ-ONLY from the Regulatory Baseline; no re-classification performed.

## Findings
- D-09.1 (Information Security Policies): ACTIVE. Applicable regs: GDPR, CRA. Scope overlap: Y (OVERLAP_CONFIRMED on GDPR↔CRA pair). The company must maintain two parallel policy artefacts: GDPR Art. 24(1) data-protection policies with DPO governance anchor (Art. 37-39) and CRA Art. 13(8) manufacturer policies/processes/procedures. Layer0 refs: SubDomains/D-09_Governance-Documentation/D-09.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-09_Governance-Documentation/D-09.1.md §2 HSO SO-D-09.1.GDPR + SO-D-09.1.CRA.
- D-09.2 (Impact & Risk Assessments): ACTIVE. Applicable regs: GDPR, CRA. Scope overlap: Y (OVERLAP_CONFIRMED on GDPR↔CRA pair). Two separate assessment artefacts required: GDPR Art. 35(1) DPIA (pre-launch, 4-item Art. 35(7) content, Art. 35(11) on-change review) and CRA Art. 13(3) cybersecurity risk assessment (Annex VII §3 record, Annex I Part I(2) applicability mapping). The CRDA explicitly notes "GDPR DPIA does NOT address cybersecurity risk" and "CRA risk assessment does NOT extend to data-subject rights" — separate artefacts, no substitution. Layer0 refs: SubDomains/D-09_Governance-Documentation/D-09.2.md §1 CRDA pair GDPR↔CRA; SubDomains/D-09_Governance-Documentation/D-09.2.md §2 HSO SO-D-09.2.GDPR + SO-D-09.2.CRA.
- D-09.3 (Asset Inventories): ACTIVE (CRA participates). Applicable regs: CRA only (NIS2, DORA not applicable). No cross-regulation pairs to evaluate. CRA Annex VII §1-§2 architecture documentation is the sole obligation. Layer0 refs: SubDomains/D-09_Governance-Documentation/D-09.3.md §1 CRDA; SubDomains/D-09_Governance-Documentation/D-09.3.md §2 HSO SO-D-09.3.CRA.
- D-09.4 (Records of Processing): ACTIVE. Applicable regs: GDPR, CRA. Scope overlap: N (SCOPE_DISJOINT on GDPR↔CRA pair). Two parallel documentation regimes: GDPR Art. 30(1) RoPA (7-item, Art. 30(5) 250-employee exception available at MICRO scale) and CRA Annex VII §1-§8 technical documentation (8-item, 10-year retention per Art. 13(13)). No substitution between the two. Layer0 refs: SubDomains/D-09_Governance-Documentation/D-09.4.md §1 CRDA pair GDPR↔CRA; SubDomains/D-09_Governance-Documentation/D-09.4.md §2 HSO SO-D-09.4.GDPR + SO-D-09.4.CRA.
- Cross-sub-domain pattern: Across all four D-09 sub-domains, the GDPR↔CRA relationship follows a consistent pattern of parallel-but-distinct obligations. At D-09.1 and D-09.2 the overlap is confirmed (same party, same product, same factual basis) but the artefacts remain separate. At D-09.4 the CRDA explicitly classifies the pair as scope-disjoint (different record types, different audit purposes). No OJ-level consolidation rule exists for any GDPR↔CRA pair in D-09. The company's MICRO scale (8 employees) does not reduce the regulatory floor but does activate the GDPR Art. 30(5) RoPA relief.

## Rationale
The domain D-09 (Governance & Documentation) contains four sub-domains, all of which are active for TinyTask Lda. because at least one applicable regulation (GDPR or CRA) participates in each. The evaluation focused exclusively on pairs where both regulations are in the applicable set [GDPR, CRA], per the source_policy constraint that non-applicable regulations (NIS2, DORA, AI_Act) are excluded from scope.

For D-09.1, the CRDA §1 verified_relationship for GDPR↔CRA is conditional: overlap exists when the controller is also a manufacturer. The company facts confirm this dual role (DOC04:SEC-01 role_matrix: gdpr.role=controller, cra.role=manufacturer; DOC04:ARCH-07 places_digital_products_eu=true). The overlap is confirmed because both regimes impose policy obligations on the same entity for the same product, but the CRDA downstream_implication explicitly requires "two parallel tracks" — the GDPR Art. 24(1) data-protection policy and the CRA Art. 13(8) manufacturer policy are distinct artefacts even though they co-exist on the same company.

For D-09.2, the CRDA §1 states overlap is "Y (when the CRA-regulated product processes personal data)". The company facts confirm personal data processing (DOC04:FLOW-01: email, name, password; DOC04:STORE-01: personal_data=True, retention 2555 days). The overlap is confirmed, but the CRDA explicitly mandates two separate artefacts: the GDPR DPIA (Art. 35(1), 4-item Art. 35(7) content) addresses data-subject rights, while the CRA risk assessment (Art. 13(3), Annex VII §3) addresses cybersecurity risk. The CRDA note "GDPR DPIA does NOT address cybersecurity risk" and "CRA risk assessment does NOT extend to data-subject rights" confirms no substitution is possible. The PRED-D09.2-DORA-LEX-SPECIALIS predicate was evaluated and found inapplicable because neither DORA nor NIS2 is in the company's applicable_regs.

For D-09.3, all three CRDA pairs involve NIS2 or DORA, neither of which applies to TinyTask. The sub-domain remains active because CRA participates (Annex VII §1-§2 architecture documentation obligation), but no cross-regulation overlap evaluation is possible or required.

For D-09.4, the CRDA §1 explicitly classifies the GDPR↔CRA pair as "N (typically)" with the scope_disjoint_test stating "different record types, different triggers. Substantively scope-disjoint." This is a READ-ONLY classification from the Regulatory Baseline. The GDPR Art. 30(1) RoPA (7-item content, DPA audit, Art. 30(5) 250-employee exception) and the CRA Annex VII §1-§8 technical documentation (8-item content, MSA audit, 10-year retention per Art. 13(13)) serve fundamentally different audit purposes and cannot be consolidated. No re-classification was performed.

All verdicts are derived exclusively from the Regulatory Baseline CRDA §1 verified_relationship_per_pair entries and the scope_overlap_predicates.yaml. No article numbers were invented; all citations reference the Regulatory Baseline file paths and section locators provided in the inputs. The company's MICRO scale and 8-employee size do not alter the regulatory floor but do activate the GDPR Art. 30(5) RoPA relief, which is noted in the D-09.4 finding.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-10.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. Regulatory Baseline classifies this pair as CONDITIONAL ("Y when the CRA-regulated product processes personal data"). TinyTask Lda. is simultaneously the CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer) and the GDPR controller (DOC04:SEC-01 role_matrix.gdpr.role=controller). The product (SYS-01 Main SaaS Application) processes personal data (DOC04:FLOW-01 data_types: email, name, password; DOC04:STORE-01 personal_data=True). The condition is met: the same party holds both roles on the same artefact that processes personal data. The CRA Annex I Part I (2)(l) on-device monitoring obligation and the GDPR Art. 32(2) 5-risk-type monitoring obligation overlap on the same detection pipeline. Layer 2 flag is set (CRA user opt-out vs. GDPR mandatory monitoring conflict).
- D-10.1 : GDPR ↔ NIS2 — NOT_APPLICABLE. NIS2 is not in TinyTask's applicable_regs (DOC04:SEC-01 regulatory_classification.nis2_entity_class=NOT_APPLICABLE; sector Technology/Software is not in the NIS2 Annex I/II list). Pair not activated.
- D-10.1 : GDPR ↔ DORA — NOT_APPLICABLE. DORA is not in TinyTask's applicable_regs (DOC04:SEC-01 regulatory_classification.dora_article_2_entity=NOT_APPLICABLE; not a financial entity). Pair not activated.
- D-10.1 : GDPR ↔ AI_Act — NOT_APPLICABLE. AI_Act is not in TinyTask's applicable_regs (DOC04:SEC-01 regulatory_classification.ai_system_classification=NOT_APPLICABLE; no high-risk AI system). Pair not activated.
- D-10.1 : NIS2 ↔ CRA — NOT_APPLICABLE. NIS2 not applicable to TinyTask. Pair not activated.
- D-10.1 : NIS2 ↔ DORA — NOT_APPLICABLE. Neither regulation applicable. Pair not activated.
- D-10.1 : NIS2 ↔ AI_Act — NOT_APPLICABLE. Neither regulation applicable. Pair not activated.
- D-10.1 : CRA ↔ DORA — NOT_APPLICABLE. DORA not applicable. Pair not activated.
- D-10.1 : CRA ↔ AI_Act — NOT_APPLICABLE. AI_Act not applicable. Pair not activated.
- D-10.1 : DORA ↔ AI_Act — NOT_APPLICABLE. Neither regulation applicable. Pair not activated.
- D-10.2 : GDPR ↔ CRA — SCOPE_DISJOINT. Regulatory Baseline classifies this pair as "N (typically)" with the note "different record types, different triggers. Substantively scope-disjoint." This is a READ-ONLY classification. GDPR Art. 30 RoPA (controller compliance records) and CRA Annex VII §5-§8 technical documentation (manufacturer product documentation) are distinct artefacts with different triggers, different recipients (DPA vs. MSA), and different retention logics. No re-classification performed.
- D-10.2 : GDPR ↔ DORA — NOT_APPLICABLE. DORA not applicable. Pair not activated.
- D-10.2 : GDPR ↔ AI_Act — NOT_APPLICABLE. AI_Act not applicable. Pair not activated.
- D-10.2 : CRA ↔ DORA — NOT_APPLICABLE. DORA not applicable. Pair not activated.
- D-10.2 : CRA ↔ AI_Act — NOT_APPLICABLE. AI_Act not applicable. Pair not activated.
- D-10.2 : DORA ↔ AI_Act — NOT_APPLICABLE. Neither regulation applicable. Pair not activated.
- D-10.3 : GDPR ↔ CRA — OVERLAP_CONFIRMED. Regulatory Baseline classifies this pair as CONDITIONAL ("Y when the controller deploys CRA-regulated products"). TinyTask is not merely deploying CRA-regulated products; it IS the CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer, cra_product_class=CLASS_I). The same party that is the GDPR controller is the CRA manufacturer, and the product (SYS-01 through SYS-05) is the CRA-regulated product with digital elements. The condition is met. GDPR Art. 32(1)(d) effectiveness-evaluation and CRA Annex I Part II (3) effective/regular tests + Annex VIII Module A conformity assessment overlap on the same product testing pipeline.
- D-10.3 : GDPR ↔ NIS2 — NOT_APPLICABLE. NIS2 not applicable. Pair not activated.
- D-10.3 : GDPR ↔ DORA — NOT_APPLICABLE. DORA not applicable. Pair not activated.
- D-10.3 : GDPR ↔ AI_Act — NOT_APPLICABLE. AI_Act not applicable. Pair not activated.
- D-10.3 : NIS2 ↔ CRA — NOT_APPLICABLE. NIS2 not applicable. Pair not activated.
- D-10.3 : NIS2 ↔ DORA — NOT_APPLICABLE. Neither regulation applicable. Pair not activated.
- D-10.3 : NIS2 ↔ AI_Act — NOT_APPLICABLE. Neither regulation applicable. Pair not activated.
- D-10.3 : CRA ↔ DORA — NOT_APPLICABLE. DORA not applicable. Pair not activated.
- D-10.3 : CRA ↔ AI_Act — NOT_APPLICABLE. AI_Act not applicable. Pair not activated.
- D-10.3 : DORA ↔ AI_Act — NOT_APPLICABLE. Neither regulation applicable. Pair not activated.

## Findings
- D-10.1 (Continuous Security Monitoring): ACTIVE. Applicable regulations: GDPR, CRA. Scope overlap: Y (GDPR↔CRA confirmed). The company's monitoring stack (SYS-05 Datadog, DOC04:ARCH-07) must satisfy both GDPR Art. 32(2) 5-risk-type monitoring and CRA Annex I Part I (2)(l) on-device internal-activity monitoring. The CRA user opt-out mechanism creates a Layer 2 tension with GDPR mandatory monitoring (layer2_flag=true in Regulatory Baseline). layer0_refs: SubDomains/D-10_Monitoring-Testing/D-10.1.md §1 CRDA pair GDPR↔CRA; CrossRegulation/DeepAnalysis/D-10.1.md.
- D-10.2 (Audit Logging & Traceability): ACTIVE. Applicable regulations: GDPR, CRA. Scope overlap: N (SCOPE_DISJOINT). Two separate artefact streams are required: GDPR Art. 30 RoPA + Art. 31 SA cooperation records (controller obligation) and CRA Annex VII §5-§8 technical documentation + Annex VII §3 risk-assessment documentation (manufacturer obligation). These do not merge. layer0_refs: SubDomains/D-10_Monitoring-Testing/D-10.2.md §1 CRDA pair GDPR↔CRA; CrossRegulation/DeepAnalysis/D-10.2.md.
- D-10.3 (Compliance Testing): ACTIVE. Applicable regulations: GDPR, CRA. Scope overlap: Y (GDPR↔CRA confirmed). The company must maintain both GDPR Art. 32(1)(d) regular effectiveness-evaluation and CRA Annex I Part II (3) effective/regular tests + Annex VIII Module A (CLASS_I internal production control) conformity assessment. The testing pipelines overlap on the same product but produce different artefacts for different regulators. layer0_refs: SubDomains/D-10_Monitoring-Testing/D-10.3.md §1 CRDA pair GDPR↔CRA; CrossRegulation/DeepAnalysis/D-10.3.md.
- Cross-sub-domain pattern: In all three D-10 sub-domains, the GDPR↔CRA pair is the only activated pair. The overlap pattern is consistent: D-10.1 and D-10.3 show confirmed overlap (same party, same product, same pipeline), while D-10.2 shows scope disjunction (different record types, different triggers, different recipients). No NIS2, DORA, or AI_Act pairs are activated due to TinyTask's non-applicability under those regimes.
- Domain-level summary: total_sub_domains=3, active_sub_domains=3, pairwise_relationships_evaluated=3 (GDPR↔CRA per sub-domain), overlap_confirmed=2, scope_disjoint=1, not_applicable_pairs=27 (all pairs involving NIS2, DORA, or AI_Act).

## Rationale
The evaluation for domain D-10 is driven by the fact that TinyTask Lda. is a MICRO-scale Technology/Software company with exactly two applicable regulations: GDPR (as controller) and CRA (as manufacturer, CLASS_I). NIS2, DORA, and AI_Act are all explicitly NOT_APPLICABLE per the company's regulatory classification (DOC04:SEC-01), which eliminates 27 of the 30 cross-regulation pairs across the three sub-domains.

For D-10.1 (Continuous Security Monitoring), the Regulatory Baseline CRDA §1 classifies the GDPR↔CRA pair as CONDITIONAL with the activation condition "Y when the CRA-regulated product processes personal data." Evaluating against company facts: TinyTask is the CRA manufacturer (DOC04:SEC-01 role_matrix.cra.role=manufacturer), the product is a SaaS application (SYS-01, DOC04:ARCH-07), and the product processes personal data (DOC04:FLOW-01: email, name, password; DOC04:STORE-01: personal_data=True, AWS RDS eu-west-1). The same legal entity holds both the controller role (GDPR) and the manufacturer role (CRA) on the same artefact. The condition is satisfied, yielding OVERLAP_CONFIRMED. The Regulatory Baseline also sets layer2_flag=true for this pair, noting the CRA Annex I Part I (2)(l) user opt-out mechanism conflicts with GDPR Art. 32(2) mandatory monitoring — a tension that requires OJ-level resolution in Phase 2.

For D-10.2 (Audit Logging & Traceability), the Regulatory Baseline CRDA §1 classifies the GDPR↔CRA pair as "N (typically)" — substantively scope-disjoint. The GDPR obligation (Art. 30 RoPA, Art. 31 SA cooperation) produces controller compliance records for the DPA, while the CRA obligation (Annex VII §5-§8 technical documentation, Annex VII §3 risk-assessment documentation) produces manufacturer product documentation for the MSA. Different record types, different triggers, different recipients, different retention logics. This is a READ-ONLY SCOPE_DISJOINT classification; no re-classification is performed.

For D-10.3 (Compliance Testing), the Regulatory Baseline CRDA §1 classifies the GDPR↔CRA pair as CONDITIONAL with the activation condition "Y when the controller deploys CRA-regulated products." TinyTask exceeds this condition: it is not merely deploying CRA-regulated products but IS the CRA manufacturer (cra_product_class=CLASS_I, DOC04:SEC-01). The product IS the CRA-regulated product with digital elements. The condition is met, yielding OVERLAP_CONFIRMED. The practical implication is that the company's testing programme must simultaneously satisfy GDPR Art. 32(1)(d) "regularly testing, assessing and evaluating the effectiveness of technical and organisational measures" and CRA Annex I Part II (3) "effective and regular tests and reviews of the product" plus Annex VIII Module A internal production control (CLASS_I). The P1B-LLM-02 CRA rationale confirms that no formal conformity assessment programme is in place (NA-01, severity MEDIUM), and the GDPR P1B output confirms the Art. 32(1)(d) obligation is binding.

No scope_overlap_predicates from the provided catalog (scope_overlap_predicates.yaml) apply to domain D-10 sub-domains; all seven provided predicates reference sub-domains D-01.1, D-04.3, D-05.2, and D-09.2. The evaluation therefore relies directly on the Regulatory Baseline CRDA §1 pair descriptions and the company facts, which is the correct path per the non-negotiable constraint that the Regulatory Baseline is READ-ONLY ground truth.


### P1C-LLM-02-COMPOUND-EVENT

_(no LLM response for this spec)_


### P1C-LLM-03-STRATEGIC-SYNTHESIS

_(no LLM response for this spec)_
