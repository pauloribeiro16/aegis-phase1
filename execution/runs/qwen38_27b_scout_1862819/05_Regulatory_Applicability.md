---
document_id: AEGIS-P1-05
title: Regulatory Applicability Assessment
phase: 1
version: 1.1
created: "2026-09-01T13:51:50Z"
updated: "2026-09-01T13:51:50Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, ../00_COMMON/01_Company_Context.md, 00_Taxonomy_Reference.md]
outputs: [06_Clause_Mapping_Matrix.xlsx, 07_Structured_Compliance_Matrix.md, 08_Obligation_Derivation.md]
applicable_regs: [CRA, GDPR]
related_documents: [../../../00_METHODOLOGY/PHASE1_STRATEGY.md, "../../../00_METHODOLOGY/PHASE1_STRATEGY.md#filter-1-regulation-applicability-binary-predicates", 00_Taxonomy_Reference.md]
traceability: AEGIS Class Model → ComplianceContext, RegulatoryClause, DomainCoverageEntry
generated_at: "2026-09-01T13:51:50Z"
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

The dual-role analysis reveals that the DPO function is consolidated into a single executive FTE allocation (0.2), while the CISO and Operations functions—cited as required accountable or responsible parties across CAP-D01-001 through CAP-D04-005—have no dedicated headcount among the four available role allocations, creating a structural gap between the five canonical functions and the existing staffing model. Time-to-compliance is consequently governed not by the Engineering function's technical throughput but by the extent to which the Governance and Operations obligations (notification, regulator liaison, forensic capture, retention) can be absorbed into residual capacity, realistically stretching the compliance window beyond a single sprint cycle. Cost of compliance, anchored on implication SI-000 (—, LOW), indicates minimal regulatory exposure in both severity and likelihood, permitting a proportional resourcing posture in which the DPO's 0.2 FTE and the Engineering function's existing bandwidth suffice to satisfy the encryption and data-handling obligations without incremental hiring. Strategic prioritisation should therefore leverage the existing dual-role structure and CTO-directed Engineering capacity rather than expanding the headcount budget, as the LOW-rated SI-000 implication does not justify a dedicated CISO or Operations hire within the current compliance cycle.


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

_(no LLM response for this spec)_


### P1C-LLM-02-COMPOUND-EVENT

_(no LLM response for this spec)_


### P1C-LLM-03-STRATEGIC-SYNTHESIS

_(no LLM response for this spec)_
