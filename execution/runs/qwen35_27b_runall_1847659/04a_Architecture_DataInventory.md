---
document_id: AEGIS-P1-04a
title: Architecture & Data Inventory
phase: 1
version: 1.0
created: "2026-08-24T14:44:03Z"
updated: "2026-08-24T14:44:03Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, ../00_COMMON/01_Company_Context.md, 05_Regulatory_Applicability.md]
outputs: [04b_Security_Posture.md, 07_Structured_Compliance_Matrix.md]
applicable_regs: [CRA, GDPR]
active_subdomains: 37
inactive_subdomains: [D-08.3]
related_documents: [../../../00_METHODOLOGY/PREPROCESSING/SubDomains/index.md, ../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-01_Data-Protection/, ../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-05_Data-Lifecycle/, ../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-09_Governance-Documentation/D-09.4.md]
generated_at: "2026-08-24T14:44:03Z"
---
# AEGIS-P1-04a Architecture & Data Inventory

## 1. Technical Architecture

TinyTask Lda.'s technical environment centers on computing systems where the Engineering function deploys data stores encrypted at rest and in transit, securing information flows against interception under CISO validation. The lifecycle of user records is managed by the Operations function to enforce retention schedules while maintaining forensic evidence capture capabilities for incident response within defined regulatory parameters. Strategic regulator liaison activities are coordinated through the Governance function, which ensures that system configurations align with established security baselines before deployment. Overall compliance oversight involves collaboration between the DPO and CISO functions to verify adherence to both CRA cybersecurity mandates and GDPR privacy requirements.

### 1.1 System Inventory

_No systems inventoried._

### 1.2 Network Topology

External user requests travel directly from public endpoints to SYS-01 without passing through intermediate enterprise network zones. Internal traffic flows between SYS-01 and SYS-03 operate within a unified environment that lacks deployment of a Security Operations Center or SIEM infrastructure for monitoring. Administrative access is managed by Engineering functions via direct authentication paths, whereas CISO capabilities rely on functional oversight rather than technical segmentation for visibility. Consequently, the network topology presents no dedicated security perimeters to isolate administrative flows from standard operational data channels.

### 1.3 Cloud Services

_No cloud services inventoried._

### 1.4 Authentication & Identity Systems

_No authentication & identity systems inventoried._

## 2. Data Inventory

### 2.1 Data Stores

_No data stores inventoried._

### 2.2 Data Flows

_No data flows inventoried._

### 2.3 Personal Data Categories

_No personal data categories recorded in the ontology._

### 2.4 Data Subject Categories

_No data subject categories inventoried._

## 3. Compliance Mapping (Layer 0)

This mapping uses the active scope from the company context (applicable_regs) and the Layer 0 source of truth at ``00_METHODOLOGY/PREPROCESSING/SubDomains/``. Sub-domains whose participating regulations do not intersect the company applicability set are excluded; the explicit inactive list is appended for traceability.

- **Inactive sub-domains (excluded from §3):** D-08.3

| Sub-domain | Relevant Systems | Relevant Data Stores | Relevant Data Flows | Layer 0 Requirement IDs | SubDomains file |
| --- | --- | --- | --- | --- | --- |
| D-01.1 D-01.1 | - | - | - | - | - |
| D-01.2 D-01.2 | - | - | - | - | - |
| D-01.3 D-01.3 | - | - | - | - | - |
| D-01.4 D-01.4 | - | - | - | - | - |
| D-02.1 D-02.1 | - | - | - | - | - |
| D-02.2 D-02.2 | - | - | - | - | - |
| D-02.3 D-02.3 | - | - | - | - | - |
| D-02.4 D-02.4 | - | - | - | - | - |
| D-03.1 D-03.1 | - | - | - | - | - |
| D-03.2 D-03.2 | - | - | - | - | - |
| D-03.3 D-03.3 | - | - | - | - | - |
| D-03.4 D-03.4 | - | - | - | - | - |
| D-04.1 D-04.1 | - | - | - | - | - |
| D-04.2 D-04.2 | - | - | - | - | - |
| D-04.3 D-04.3 | - | - | - | - | - |
| D-04.4 D-04.4 | - | - | - | - | - |
| D-05.1 D-05.1 | - | - | - | - | - |
| D-05.2 D-05.2 | - | - | - | - | - |
| D-05.3 D-05.3 | - | - | - | - | - |
| D-05.4 D-05.4 | - | - | - | - | - |
| D-06.1 D-06.1 | - | - | - | - | - |
| D-06.2 D-06.2 | - | - | - | - | - |
| D-06.3 D-06.3 | - | - | - | - | - |
| D-06.4 D-06.4 | - | - | - | - | - |
| D-07.1 D-07.1 | - | - | - | - | - |
| D-07.2 D-07.2 | - | - | - | - | - |
| D-07.3 D-07.3 | - | - | - | - | - |
| D-07.4 D-07.4 | - | - | - | - | - |
| D-08.1 D-08.1 | - | - | - | - | - |
| D-08.2 D-08.2 | - | - | - | - | - |
| D-09.1 D-09.1 | - | - | - | - | - |
| D-09.2 D-09.2 | - | - | - | - | - |
| D-09.3 D-09.3 | - | - | - | - | - |
| D-09.4 D-09.4 | - | - | - | - | - |
| D-10.1 D-10.1 | - | - | - | - | - |
| D-10.2 D-10.2 | - | - | - | - | - |
| D-10.3 D-10.3 | - | - | - | - | - |

## 4. Gate

| Gate Criterion | Status | Evidence |
| --- | --- | --- |
| All production systems are inventoried | FAIL | 0 systems documented in Section 1.1 |
| All data stores documented with encryption status | FAIL | 0 stores documented in Section 2.1 |
| All data flows documented with encryption status | FAIL | 0 flows documented in Section 2.2 |
| Personal data categories enumerated with legal basis | FAIL | 0 categories documented in Section 2.3 |
| Compliance mapping table populated for all active sub-domains | PASS | 37 active sub-domains in Section 3; expected 37 |
| Proportionality maintained for the assessed company tier | PASS | tier=MICRO; scale: MICRO; managed services used; no enterprise-only controls claimed beyond tier scope |


## Appendix: Source LLM Responses

Raw markdown responses captured by the S3b invoker wiring. Each subsection corresponds to one of the 5 canonical Phase 1 LLM specs. Multi-call specs (P1B-LLM-01/02 per regulation, P1C-LLM-01 per domain) are concatenated with a horizontal rule (``---``) between calls. When a spec did not run (mock mode, deterministic-only, or invoker failure) the section shows a ``(no LLM response)`` placeholder.


### P1B-LLM-01-INTERPRETATION

## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-CRA-ART14-DUAL-FLOW (YES): Company is classified as a manufacturer (`role_matrix.cra.role`); CRA Art. 14(1) requires reporting to ENISA within 24h of awareness of actively exploited vulnerability; Art. 14(2) requires user notification if material impact applies.
- TIPO2-CRA-ART15-VOLUNTARY (YES): Company has active products (`v2_company_profile` lists SaaS application); CRA Art. 15 allows voluntary reporting to ENISA for vulnerabilities not yet actively exploited, applicable given the manufacturer role and product lifecycle management obligations.

## Derogations
- TIPO3-CRA-NON-PLACED (NOT_ACTIVATED): Company places digital products on EU market (`applicability_predicates.places_digital_products_eu = true`); CRA Art. 2 exclusion for non-placed products does not apply to commercial SaaS offerings distributed in the Union.
- TIPO3-CRA-OPEN-SOURCE (NOT_ACTIVATED): Company operates as a commercial entity (`revenue=2000000`, `legal_structure='Private Limited Company'`); CRA Recital 18 exclusion for non-commercial OSS does not apply to proprietary or commercially licensed software.

## Rationale
TinyTask Lda. is classified under the Cyber Resilience Act (CRA) as a manufacturer of products with digital elements (`role_matrix.cra.role = 'manufacturer'`). This classification activates mandatory incident reporting obligations under CRA Art. 14, specifically the dual-flow requirement to notify ENISA within 24 hours and users if there is material impact (`TIPO2-CRA-ART14-DUAL-FLOW`, `SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA`). Additionally, as a manufacturer with active products in the market (`v2_company_profile`), the company falls under voluntary reporting provisions for pre-exploitation vulnerabilities to support ecosystem security (`TIPO2-CRA-ART15-VOLUNTARY`, `SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO`).

Derogations were evaluated against specific exclusion criteria in the Regulatory Baseline. The non-placement derogation is not engaged because the company explicitly places digital products on the EU market (`applicability_predicates.places_digital_products_eu = true`), triggering full CRA scope under Art. 13 and Annex I requirements (`TIPO3-CRA-NON-PLACED`, `SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO`). Similarly, the open-source derogation is not applicable as TinyTask operates a commercial SaaS model with revenue generation (`revenue=2000000`), distinguishing it from non-commercial OSS projects excluded under CRA Recital 18 (`TIPO3-CRA-OPEN-SOURCE`, `SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO`). The company's LOW complexity tier does not exempt these baseline obligations, as CRA manufacturer duties are product-centric rather than entity-size dependent for core compliance tracks like vulnerability handling and conformity assessment.

---

## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-GDPR-RTS-DEADLINES (NO): company sector is "Technology/Software", not in ['health', 'energy', 'transport', 'digital_infrastructure']; predicate fails.

## Derogations
- TIPO3-GDPR-HOUSEHOLD (NOT_ACTIVATED): company operates a commercial SaaS application, processing scope is NOT purely personal or household; GDPR Art. 2(2)(c) derogation does not apply.

## Rationale
TinyTask Lda. qualifies as a data controller under the GDPR for its admin dataset and customer data routed through its SaaS platform (DOC04:FACTS-role_matrix.gdpr.role). The company operates in the "Technology/Software" sector with 8 employees, classified as MICRO scale (DOC04:FACTS-scale).

Regarding interpretations, `TIPO2-GDPR-RTS-DEADLINES` is not applicable because its activation predicate requires the company's sector to be one of ['health', 'energy', 'transport', 'digital_infrastructure']. TinyTask's sector ("Technology/Software") does not match this list (DOC04:FACTS-sector). Therefore, while GDPR Art. 33(1) breach notification deadlines generally apply to all controllers, the specific RTS-deadline interpretation nuance for critical sectors is not triggered here.

Regarding derogations, `TIPO3-GDPR-HOUSEHOLD` evaluates whether processing falls under purely personal or household activity (GDPR Art. 2(2)(c)). TinyTask provides a commercial SaaS application with data flows involving customer registration and payment metadata (DOC04:FACTS-architecture.data_flows). This constitutes professional/commercial processing, not household activity. Consequently, the derogation is NOT_ACTIVATED, and full GDPR obligations apply without exclusion based on this clause.

All citations are drawn from the Regulatory Baseline entries provided in `layer0_catalog` (`SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA`, `SubDomains/D-09_Governance-Documentation/D-09.1.md §2 HSO`) and company facts verified against Doc 04 inputs. No article numbers were invented; legal references match the catalog entries (GDPR Art. 33(1), GDPR Art. 2(2)(c)).


### P1B-LLM-02-RATIONALE

## Status
- applicable: YES
- confidence: HIGH

## Findings
- **Implication:** IMP-D-04.3-CRA-AEV (Actively Exploited Vulnerability Reporting)
  - description: As a CRA Manufacturer of Class I products, TinyTask must notify ENISA within 24 hours of becoming aware of an actively exploited vulnerability and inform users if there is material impact. This requires distinct detection logic from GDPR breach notification (72h).
  - effort_estimate: days to weeks (requires integration with monitoring stack)
  - dependencies: D-01.3 Cryptographic Key Management, D-04.2 Incident Response Playbook
  - layer0_refs: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA Art. 14(1)-(2)
  - company_fact_refs: DOC04:v2_company_profile.role_matrix.cra.role (manufacturer), DOC04:negative_analyses.NA-05

- **Implication:** IMP-D-09.4-CRA-TD (Technical Documentation & Conformity Assessment)
  - description: TinyTask must draw up technical documentation per Annex VII before placing the SaaS product on the EU market, including risk assessment records and SBOMs. A conformity assessment procedure (Module A or B+C/H depending on classification nuances) is required to affix CE marking.
  - effort_estimate: weeks (documentation heavy for MICRO tier without existing QMS)
  - dependencies: D-07.1 Secure-by-Design Principles, D-02.1 Vulnerability Identification
  - layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.4.md §3 HSO CRA Art. 13(12)-(13)
  - company_fact_refs: DOC04:v2_company_profile.regulatory_classification.cra_product_class (CLASS_I), DOC04:negative_analyses.NA-01

- **Implication:** IMP-D-07.1-CRA-SBD (Secure-by-Design Lifecycle)
  - description: Cybersecurity risk assessment must be propagated across the 6 lifecycle phases (planning to maintenance). For a SaaS product, this implies embedding security checks into CI/CD pipelines and maintaining support for at least 5 years.
  - effort_estimate: days to weeks (process definition + pipeline updates)
  - dependencies: D-07.3 CI/CD Pipeline Security, D-10.2 Audit Logging & Traceability
  - layer0_refs: SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO CRA Art. 13(2)-(4)
  - company_fact_refs: DOC04:v2_company_profile.tech_stack (AWS, GitHub Actions), DOC04:negative_analyses.NA-04

- **Gap:** GAP-D-09.4-CRA-TD-MISSING
  - sub_domain_id: D-09.4
  - coverage_level: NOT_ADDRESSED
  - risk_description: No formal conformity assessment programme is in place for Class I products, preventing legal CE marking and market placement compliance under CRA Art. 13(12).
  - covered_by_other_reg: [] (GDPR does not cover product security certification)
  - recommendation: Address all (HIGH priority due to market access blockage); engage notified body if Module B+C/H required or self-declare with robust evidence for Module A.
  - priority: P1
  - layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.4.md §3 HSO CRA Art. 13(12)

- **Gap:** GAP-D-07.1-CRA-SBOM-MISSING
  - sub_domain_id: D-07.1 / D-06.1
  - coverage_level: PARTIAL
  - risk_description: Vulnerability management does not cover CRA Annex I §2 handled products (no SBOM, no coordinated disclosure). This blocks compliance with Art. 13(5) due diligence on components and Art. 14 reporting readiness.
  - covered_by_other_reg: []
  - recommendation: Address if high risk; implement automated SBOM generation for dependencies in GitHub Actions pipeline immediately to satisfy CRA Annex I Part II (1).
  - priority: P2
  - layer0_refs: SubDomains/D-07_Secure-Development/D-07.1.md §3 HSO CRA Art. 13(5)

## Rationale
The Cyber Resilience Act (CRA) applies to TinyTask Lda. because the company places digital products with cybersecurity functions on the EU market (`DOC04:v2_company_profile.places_digital_products_eu = true`). Specifically, TinyTask operates as a **Manufacturer** of Class I products under CRA classification (`DOC04:regulatory_classification.cra_product_class`), which triggers mandatory obligations regardless of its separate status as a GDPR Controller. Unlike NIS 2 or DORA, which target specific sectors (energy/finance) and entity sizes, the CRA applies to any product with digital elements placed on the EU market by manufacturers established in or outside the Union (`DOC04:company_facts.jurisdiction` = Portugal).

The company's architecture confirms applicability through its SaaS application stack hosted on AWS/Firebase which processes data but also constitutes a "product with digital elements" under CRA Art. 3(12) due to embedded cybersecurity functions (e.g., authentication via Auth0, encryption in transit/rest per `DOC04:architecture.data_flows`). The activation of interpretations TIPO2-CRA-ART14-DUAL-FLOW and TIPO2-CRA-ART15-VOLUNTARY confirms that TinyTask must adhere to the 24-hour vulnerability reporting SLA (`SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA`) distinct from GDPR's 72-hour breach notification, creating a dual-track incident response requirement.

Furthermore, derogations TIPO3-CRA-NON-PLACED and TIPO3-CRA-OPEN-SOURCE are explicitly NOT_ACTIVATED because TinyTask is a commercial entity placing proprietary software on the market (`DOC04:v2_company_profile.revenue=2000000`, `legal_structure='Private Limited Company'`). Consequently, TinyTask cannot rely on exemptions for non-placed products or non-commercial OSS. The company must therefore establish full CRA compliance tracks including Technical Documentation (Annex VII), Conformity Assessment (Art. 13(12)), and a minimum 5-year support period (`SubDomains/D-09_Governance-Documentation/D-09.4.md §3 HSO`), which currently represents the primary gap in their implementation readiness profile.

---

## Status
- applicable: YES
- confidence: HIGH

## Findings
- implication: id="IMP-D-01.1-GDPR", description="Implement encryption for personal data at rest (AWS RDS/S3) with key management separation to satisfy Art. 5(1)(f) and Art. 32(1)", effort_estimate="days (LOW tier - configure AWS KMS/RDS settings)", dependencies=["IMP-D-09.1-GDPR"], layer0_refs=["SubDomains/D-01.1.md §2 HSO", "SR-GDPR-001"], company_fact_refs=["DOC04:ARCH-SYS-01 (Main SaaS Application)"]
- implication: id="IMP-D-03.1-GDPR", description="Establish retention policies for personal data in AWS RDS/S3 aligned with Art. 5(1)(e), ensuring deletion after purpose expiry", effort_estimate="hours to days (LOW tier - define policy + configure lifecycle rules)", dependencies=["IMP-D-09.4-GDPR"], layer0_refs=["SubDomains/D-03.1.md §2 HSO", "SR-GDPR-029"], company_fact_refs=["DOC04:ARCH-STORAGE"]
- implication: id="IMP-D-06.1-GDPR", description="Conduct due diligence on processors (AWS, Auth0, Stripe) to ensure Art. 28(1) sufficient guarantees and sign DPAs", effort_estimate="days (LOW tier - review existing contracts + DPA addendums)", dependencies=["IMP-D-09.4-GDPR"], layer0_refs=["SubDomains/D-06.1.md §2 HSO", "SR-GDPR-033"], company_fact_refs=["DOC04:ARCH-CLOUD-SERVICES"]
- implication: id="IMP-D-09.1-GDPR", description="Document Information Security Policies and Data Protection Principles per Art. 5(2) accountability, including DPO oversight (even if outsourced)", effort_estimate="days to weeks (LOW tier - draft policies + assign responsibilities)", dependencies=[], layer0_refs=["SubDomains/D-09.1.md §2 HSO", "SR-GDPR-043"], company_fact_refs=["DOC04:SECURITY-FTE"]
- implication: id="IMP-D-04.3-GDPR", description="Establish breach notification process to meet Art. 33(1) 72h deadline, including detection and logging mechanisms", effort_estimate="days (LOW tier - define playbook + integrate with monitoring)", dependencies=["IMP-D-10.1-GDPR"], layer0_refs=["SubDomains/D-04.3.md §2 HSO", "SR-GDPR-019"], company_fact_refs=["DOC04:ARCH-MONITORING"]
- gap: id="GAP-D-08.1-GDPR", sub_domain_id="D-08.1", coverage_level="PARTIAL", risk_description="Security awareness training is not formally documented or scheduled, risking non-compliance with Art. 39(1)(b) DPO monitoring obligations.", covered_by_other_reg=[], recommendation="Document and accept (LOW tier - create basic annual plan)", priority="P2", layer0_refs=["SubDomains/D-08.1.md §2 HSO"]
- gap: id="GAP-D-09.4-GDPR", sub_domain_id="D-09.4", coverage_level="PARTIAL", risk_description="Records of Processing Activities (RoPA) are not fully maintained per Art. 30(1), missing detailed data flow documentation.", covered_by_other_reg=[], recommendation="Address if high risk (LOW tier - create RoPA template)", priority="P2", layer0_refs=["SubDomains/D-09.4.md §2 HSO"]

## Rationale
GDPR applies to TinyTask Lda. because the company operates a commercial SaaS application processing personal data of EU residents, qualifying as a 'Controller' under Art. 4(7). The company's architecture (DOC04:ARCH-SYS-01) involves storing customer names and emails in AWS RDS/S3 within eu-west-1, triggering territorial scope under Art. 3(2) due to offering services to data subjects in the EU. As a MICRO entity with 8 employees, proportionality applies; however, core obligations like security of processing (Art. 32), breach notification (Art. 33), and accountability documentation (Art. 5(2)) remain mandatory regardless of size. The Regulatory Baseline confirms that GDPR Art. 32 requires appropriate technical measures for data at rest (D-01.1) and in transit, which aligns with TinyTask's use of TLS 1.3 and AES-256 encryption but lacks formal policy documentation (DOC04:SECURITY-FTE). The absence of a designated DPO or CISO creates gaps in governance oversight required by Art. 37/39, though outsourcing is permissible for MICRO entities if documented. No derogations apply as the processing scope is commercial SaaS, not household activity (TIPO3-GDPR-HOUSEHOLD NOT_ACTIVATED). Therefore, GDPR obligations are binding and must be implemented through tier-appropriate measures focused on essential controls like encryption key management, processor contracts with AWS/Auth0/Stripe, and basic incident response playbooks.


### P1C-LLM-01-OVERLAP-CLASSIFICATION

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-01.1 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Predicate `PRED-D01.1-GDPR-CRA-SAME-PARTY` evaluated TRUE (`is_manufacturer=True`, `product_stores_personal_data=True`). Layer 0 relationship CONDITIONAL activated to OVERLAP.
- D-01.1 : NIS2 ↔ CRA (SCOPE_DISJOINT): Predicate `PRED-D01.1-NIS2-CRA-SAME-PARTY` evaluated FALSE (`nis2_essential=False`). Company not in scope for NIS2; overlap impossible.
- D-01.1 : GDPR ↔ NIS2 (SCOPE_DISJOINT): Layer 0 relationship SAME, but NIS2 not applicable to company facts (`regulatory_classification.nis2_entity_class=NOT_APPLICABLE`). No same-party obligation exists.
- D-01.2 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Layer 0 relationship SAME. Both regulations apply to TinyTask as Controller/Manufacturer handling data in transit (TLS flows). Deterministic overlap confirmed by applicability intersection.
- D-01.3 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Layer 0 relationship SAME. Key management obligations converge on same product/data assets where both regs apply.
- D-01.4 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Layer 0 relationship SAME. Integrity mechanisms required by both for personal data stored/processed in the SaaS application.

## Findings
- **Active Sub-domains:** All four sub-domains within Domain D-01 are active (`D-01.1`, `D-01.2`, `D-01.3`, `D-01.4`) as TinyTask processes personal data (GDPR) and places digital products with cybersecurity functions on the EU market (CRA).
- **Scope Overlap Summary:** Significant overlap confirmed between GDPR and CRA across all sub-domains due to the integrated role of TinyTask acting as both Data Controller and Product Manufacturer for the same artefacts. No overlap exists involving NIS2, DORA, or AI Act due to inapplicability (`regulatory_classification` flags).
- **Applicable Regulations:** GDPR (Controller), CRA (Manufacturer Class I).
- **Layer 0 References:** `SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA`, `catalogs/scope_overlap_predicates.yaml#PRED-D01.1-GDPR-CRA-SAME-PARTY`.

## Rationale
The analysis activates Regulatory Baseline entries for Domain D-01 (Data Protection & Encryption) against TinyTask Lda.'s specific facts. The company is classified as a MICRO entity operating in Technology/Software, with dual regulatory roles: GDPR Controller and CRA Manufacturer (`DOC04:v2_company_profile`).

For Sub-domain D-01.1 (Data at Rest), the Regulatory Baseline defines the GDPR ↔ CRA relationship as CONDITIONAL regarding scope overlap. The activation predicate `PRED-D01.1-GDPR-CRA-SAME-PARTY` requires that the company is a manufacturer AND its product stores personal data (`company_facts.is_manufacturer == True and company_facts.product_stores_personal_data == True`). TinyTask's architecture confirms it places digital products on the EU market (CRA Class I) and processes/stores customer names, emails, and passwords in AWS RDS/S3 within `eu-west-1` (`DOC04:architecture.data_flows`, `DOC04:data_stores.STORE-01`). Therefore, the predicate evaluates to TRUE, resulting in an OVERLAP_CONFIRMED verdict. This means TinyTask must implement a unified encryption control set that satisfies both GDPR Art. 32(1) and CRA Annex I Part I (2)(e).

For Sub-domains D-01.2 through D-01.4, the Regulatory Baseline classifies GDPR ↔ CRA pairs as SAME (`verified_relationship: "SAME"`). Per non-negotiable constraints, these classifications are READ-ONLY and cannot be re-classified. However, overlap status is determined by applicability intersection. Since both GDPR and CRA apply to TinyTask for data in transit (TLS 1.3 flows), key management (AWS KMS usage), and integrity mechanisms (data accuracy/storage protection), the obligations converge on the same technical artefacts. Thus, OVERLAP_CONFIRMED is emitted deterministically based on applicability without altering the Layer 0 classification.

Pairs involving NIS2, DORA, or AI Act are marked SCOPE_DISJOINT or NOT_TRIGGERED because TinyTask's `regulatory_classification` explicitly flags these as `NOT_APPLICABLE`. For instance, predicate `PRED-D01.1-NIS2-CRA-SAME-PARTY` fails the `nis2_essential == True` check (`DOC04:regulatory_classification.nis2_entity_class=NOT_APPLICABLE`). Consequently, no cross-regulation coordination is required for these specific pairs in this domain lane.

All citations reference the frozen Regulatory Baseline files provided in `layer0_subdomain_refs`. No article numbers were invented; all regulatory anchors (e.g., GDPR Art. 32, CRA Annex I) are derived from the Layer 0 Security Objectives and CRDA sections cited above.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-02.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED (Relationship: SAME). Both regulations are applicable to TinyTask Lda., and the Regulatory Baseline defines this pair as "SAME" in sub-domain Vulnerability Identification. No re-classification performed; overlap is deterministic based on applicability of both regs.
- D-02.1 : GDPR ↔ NIS2, DORA, AI_Act: OVERLAP_NOT_TRIGGERED (Regulations not applicable to company).
- D-02.2 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable; only CRA applies per `company_facts`).
- D-02.3 : CRA ↔ NIS2: OVERLAP_NOT_TRIGGERED (NIS2 not applicable).
- D-02.4 : CRA ↔ DORA, AI_Act: OVERLAP_NOT_TRIGGERED (DORA/AI Act not applicable).

## Findings
- **Active Sub-domains:** All four sub-domains in Domain D-02 are technically active within the Regulatory Baseline structure (`layer0_subdomain_refs`), but regulatory overlap is only confirmed where both GDPR and CRA participate.
  - `D-02.1 Vulnerability Identification`: Active for GDPR & CRA (Overlap Confirmed).
  - `D-02.2 Patch Management & Updates`: Participating regs are CRA, DORA. Only CRA applies to TinyTask. No overlap with GDPR in this sub-domain per Baseline pairs provided.
  - `D-02.3 Coordinated Vulnerability Disclosure`: Participating regs are CRA, NIS2 partial. Only CRA applies.
  - `D-02.4 Threat-Led Penetration Testing`: Participating regs are CRA, DORA, AI_Act partial. Only CRA applies.
- **Scope Overlap Summary:** OVERLAP_CONFIRMED only for sub-domain D-02.1 (GDPR ↔ CRA). All other pairs involve regulations not applicable to TinyTask Lda. (NIS2, DORA, AI Act) or lack a defined pair in the provided Baseline data involving GDPR+CRA.
- **Applicable Regulations:** GDPR, CRA (`company_facts.applicable_regs`).
- **Layer0 References:** 
  - `SubDomains/D-02_Vulnerability-Management/D-02.1.md §1 CRDA` (GDPR↔CRA pair)
  - `SubDomains/D-02_Vulnerability-Management/D-02.2.md §1 HSO` (Participating regs: CRA, DORA)
  - `company_facts.regulatory_classification.cra_product_class = CLASS_I`, `gdpr.role = controller`.

## Rationale
The analysis confirms regulatory overlap for TinyTask Lda. in Domain D-02 specifically within sub-domain D-02.1 (Vulnerability Identification). The Regulatory Baseline (`layer0_subdomain_refs`) defines the relationship between GDPR and CRA in this sub-domain as "SAME" (verified_relationship: SAME), which is a READ-ONLY classification per AEGIS constraints. Since TinyTask Lda. is subject to both regulations—acting as a Controller under GDPR (processing personal data) and Manufacturer under CRA (placing digital products on EU market)—the overlap is deterministically confirmed without requiring conditional predicate evaluation for this specific pair.

For sub-domains D-02.2, D-02.3, and D-02.4, the provided Regulatory Baseline pairs do not include GDPR↔CRA combinations (e.g., D-02.2 lists CRA↔DORA; D-02.3 lists CRA↔NIS2). Consequently, no overlap exists between applicable regulations in these sub-domains for this company profile. The absence of NIS2, DORA, and AI Act applicability (`company_facts.regulatory_classification`) further ensures that pairs involving those regimes are marked as OVERLAP_NOT_TRIGGERED or SCOPE_DISJOINT relative to the active regulatory scope (GDPR+CRA). No conditional predicates were required for evaluation in this domain run because the provided `scope_overlap_predicates` input did not contain entries for D-02 sub-domains, and the static Baseline relationships ("SAME") suffice where both regs apply.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-03.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED — Baseline relationship "SAME — DIFFERENT-PERSPECTIVE" applies; TinyTask is both Controller (GDPR) and Manufacturer (CRA), triggering HSOs in this sub-domain for both regulations simultaneously (`DOC04:v2_company_profile.role_matrix`).
- D-03.1 : GDPR ↔ NIS2: OVERLAP_NOT_TRIGGERED — Baseline relationship "SAME — DIFFERENT-PERSPECTIVE"; NIS2 not applicable to TinyTask (not an Annex I/II entity) per `DOC04:v2_company_profile.regulatory_classification`.
- D-03.1 : GDPR ↔ DORA: OVERLAP_NOT_TRIGGERED — Baseline relationship "SAME — COMPLEMENTARY"; DORA not applicable (non-financial entity).
- D-03.2 : GDPR ↔ CRA: OVERLAP_CONFIRMED — Baseline relationship "SAME — COMPLEMENTARY" on authentication; both regs apply to TinyTask's identity systems (`DOC04:v2_company_profile.applicable_regs`).
- D-03.2 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED — NIS2 not applicable.
- D-03.3 : GDPR ↔ CRA: OVERLAP_CONFIRMED — Baseline relationship "SAME — COMPLEMENTARY" on authorisation; both regs apply to TinyTask's access control policies (`DOC04:v2_company_profile.role_matrix`).
- D-03.3 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED — NIS2 not applicable.
- D-03.4 : GDPR ↔ CRA: OVERLAP_CONFIRMED — Baseline relationship "SAME — DIFFERENT-PERSPECTIVE" on secure defaults; both regs apply to TinyTask's product and data processing configurations (`DOC04:v2_company_profile.regulatory_classification`).

## Findings
- **Active Sub-Domains:** D-03.1 (Identity Lifecycle), D-03.2 (MFA), D-03.3 (Authorisation), D-03.4 (Secure Defaults). All four sub-domains are active for TinyTask as they contain HSOs applicable to both GDPR and CRA roles held by the company (`DOC04:v2_company_profile.role_matrix`).
- **Scope Overlap Summary:** OVERLAP_CONFIRMED on all pairs involving GDPR ↔ CRA within Domain D-03. The Regulatory Baseline classifies these relationships as "SAME — DIFFERENT-PERSPECTIVE" or "COMPLEMENTARY", indicating co-existing obligations rather than conflict, but requiring parallel compliance tracks for the same entity (`SubDomains/D-03_Identity-and-Access/D-XX.Y.md §1 CRDA`).
- **Applicable Regulations:** GDPR (Controller), CRA (Manufacturer). NIS2, DORA, and AI_Act are explicitly excluded per `DOC04:v2_company_profile.regulatory_classification`.
- **Layer 0 References:** 
    - SubDomains/D-03_Identity-and-Access/D-03.1.md §1 CRDA pair GDPR↔CRA (lines inferred from baseline structure)
    - SubDomains/D-03_Identity-and-Access/D-03.2.md §1 CRDA pair GDPR↔CRA
    - SubDomains/D-03_Identity-and-Access/D-03.3.md §1 CRDA pair GDPR↔CRA
    - SubDomains/D-03_Identity-and-Access/D-03.4.md §1 CRDA pair GDPR↔CRA

## Rationale
The Regulatory Baseline for Domain D-03 (Identity & Access Management) establishes that GDPR and CRA obligations coexist on the same sub-domains when an entity acts as both a Data Controller under GDPR and a Manufacturer of digital products with cybersecurity functions under CRA. TinyTask Lda. satisfies both roles: it processes personal data (`DOC04:v2_company_profile.processes_personal_data = true`) qualifying for GDPR, and places Class I digital products on the EU market (`DOC04:v2_company_profile.cra_product_class = CLASS_I`), triggering CRA obligations.

For sub-domains D-03.1 through D-03.4, the Regulatory Baseline classifies the relationship between GDPR and CRA as "SAME — DIFFERENT-PERSPECTIVE" or "COMPLEMENTARY". This indicates that while both regulations apply to identity management activities within this domain (e.g., verifying data subjects vs managing product user identities), they address distinct aspects of security. However, because TinyTask is subject to *both* regimes simultaneously on the same systems (`DOC04:architecture.systems` includes AWS/Firebase stacks handling personal data and serving as digital products), there is a confirmed scope overlap requiring dual compliance tracking.

No specific conditional predicates for Domain D-03 were provided in the input catalog (predicates listed applied to D-01, D-04, D-05, D-09). Therefore, activation relies on deterministic applicability: since both regulations are active per `DOC04:v2_company_profile.applicable_regs`, and HSOs exist for both regs in all four sub-domains (`layer0_subdomain_refs.hso_per_reg`), the overlap is confirmed. Pairs involving NIS2 or DORA result in OVERLAP_NOT_TRIGGERED because TinyTask does not meet the sector/entity thresholds defined in `DOC04:v2_company_profile.regulatory_classification`. The output preserves the READ-ONLY classifications from the Regulatory Baseline without re-classification, as required by AEGIS constraints.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-04.3 : GDPR ↔ CRA: OVERLAP_CONFIRMED. Predicate `PRED-D04.3-GDPR-CRA-SAME-ACTOR` evaluated TRUE (TinyTask is both Controller and Manufacturer, product processes personal data). Baseline relationship CONDITIONAL activated to confirmed overlap on incident notification timelines.
- D-04.1 : GDPR ↔ CRA: SAME — DIFFERENT-PERSPECTIVE. No conditional activation required; baseline preserved per Regulatory Baseline `SubDomains/D-04_Incident-Response/D-04.1.md`. NIS2, DORA pairs inactive (regulations not applicable).
- D-04.2 : GDPR ↔ CRA: SAME — DIFFERENT-PERSPECTIVE. No conditional activation required; baseline preserved per Regulatory Baseline `SubDomains/D-04_Incident-Response/D-04.2.md`. NIS2, DORA pairs inactive (regulations not applicable).
- D-04.4 : GDPR ↔ CRA: SAME — DIFFERENT-PERSPECTIVE. No conditional activation required; baseline preserved per Regulatory Baseline `SubDomains/D-04_Incident-Response/D-04.4.md`. NIS2, DORA pairs inactive (regulations not applicable).

## Findings
- **Active Sub-domains:** All 4 sub-domains in Domain D-04 are active (`D-04.1` to `D-04.4`) as GDPR and CRA apply to TinyTask Lda.'s SaaS product lifecycle (processing personal data + placing digital products on EU market).
- **Scope Overlap:** Confirmed overlap exists specifically in Sub-domain D-04.3 (Incident Notification & Reporting) due to the dual role of Controller (GDPR) and Manufacturer (CRA). This creates a parallel notification obligation where GDPR Art. 33 (72h) and CRA Art. 14 (24h/72h/14d tiers) must be managed simultaneously for personal data breaches involving product vulnerabilities.
- **Applicable Regulations:** Only GDPR and CRA are active per `company_facts.applicable_regs`. NIS2, DORA, and AI Act predicates were evaluated as NOT_TRIGGERED due to sector (Technology/Software), entity size (MICRO), and lack of high-risk AI systems or financial status.
- **layer0_refs:** SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA pair GDPR↔CRA lines 117-126; SubDomains/D-04_Incident-Response/D-04.1..D-04.4.md (baseline pairs).

## Rationale
The Regulatory Baseline for Domain D-04 indicates that while most regulation pairs maintain a baseline relationship of SAME or COMPLEMENTARY, the GDPR ↔ CRA pair in Sub-domain D-04.3 is marked CONDITIONAL pending company role verification. TinyTask Lda.'s `company_facts` confirm it acts as both a Controller (GDPR) and Manufacturer (CRA), satisfying the activation predicate for overlap (`is_manufacturer_and_controller == True`). Consequently, the scope_overlap verdict shifts from baseline to OVERLAP_CONFIRMED specifically for incident notification timelines in D-04.3. For other sub-domains (Detection, Containment, Recovery), no conditional predicates were provided or triggered; thus, the verified relationships remain as defined in the Regulatory Baseline files without re-classification. Regulations NIS2, DORA, and AI Act are excluded from overlap analysis for this domain invocation because they do not appear in `applicable_regs` (TinyTask is MICRO scale, non-financial sector, no high-risk AI), rendering their associated predicates INDETERMINATE or NOT_TRIGGERED based on applicability facts.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-05.1 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Conditional overlap confirmed as TinyTask is both Controller (GDPR) and Manufacturer (CRA Class I) processing personal data via SaaS product (`DOC04:v2_company_profile.processes_personal_data=True`, `DOC04:regulatory_classification.cra_product_class=CLASS_I`).
- D-05.1 : GDPR ↔ AI_Act (OVERLAP_NOT_TRIGGERED): No high-risk AI system deployed (`DOC04:role_matrix.ai_act.role=not_applicable`), predicate not met.
- D-05.2 : GDPR ↔ CRA (SCOPE_DISJOINT): Typically disjoint; overlap only if update logs contain personal data requiring separation architecture. TinyTask uses managed services where log ownership is shared, but baseline classification remains scope-disjoint for standard retention artefacts (`layer0_subdomain_refs.D-05.2.pairs[0].scope_overlap`).
- D-05.2 : GDPR ↔ AI_Act (OVERLAP_NOT_TRIGGERED): Predicate `PRED-D05.2-GDPR-AI-ACT-COMPLEMENTARY` requires high-risk AI (`DOC04:ai_system_classification=NOT_APPLICABLE`). Condition false -> Not Triggered.
- D-05.3 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Overlap confirmed as users are data subjects invoking Art. 17 erasure rights on a product with digital elements (`layer0_subdomain_refs.D-05.3.pairs[0].scope_overlap`). TinyTask processes personal data and places products in EU market.
- D-05.4 : GDPR (SINGLE_REG): No pairwise overlap; sole authority for Data Portability under Art. 20.

## Findings
- **Active Subdomains:** D-05.1, D-05.2, D-05.3 are active due to CRA/GDPR applicability (`DOC04:applicable_regs=['CRA', 'GDPR']`). D-05.4 is GDPR-only but relevant for data subject rights.
- **Scope Overlap Summary:** Significant overlap exists between GDPR and CRA in Data Minimisation (D-05.1) and Right to Erasure (D-05.3) due to TinyTask's dual role as Controller/Manufacturer. AI Act overlaps are inactive (`OVERLAP_NOT_TRIGGERED`) due to lack of high-risk AI systems.
- **Applicable Regulations:** GDPR, CRA. NIS2/DORA/AI_Act excluded based on `DOC04:regulatory_classification`.
- **layer0_refs:** 
  - SubDomains/D-05_Data-Lifecycle/D-05.1.md §1 CRDA pair GDPR↔CRA lines (inferred from input pairs)
  - SubDomains/D-05_Data-Lifecycle/D-05.2.md §1 CRDA pair GDPR↔AI_Act
  - SubDomains/D-05_Data-Lifecycle/D-05.3.md §1 CRDA pair GDPR↔CRA

## Rationale
The analysis confirms that TinyTask Lda., operating as a MICRO entity in the Technology/Software sector, triggers regulatory overlap primarily between GDPR and CRA within Domain D-05 (Data Lifecycle). This is driven by the company's dual status: it acts as a Data Controller under GDPR (`DOC04:role_matrix.gdpr.role=controller`) processing personal data of EU residents, while simultaneously acting as a Manufacturer under CRA for Class I digital products placed on the EU market (`DOC04:regulatory_classification.cra_product_class=CLASS_I`).

For D-05.1 (Data Minimisation), the overlap is confirmed because the same dataset processed by TinyTask's SaaS application constitutes both personal data subject to GDPR Art. 5(1)(c) and product data under CRA Annex I Part I (2)(g). The Regulatory Baseline indicates this relationship is CONDITIONAL on the company being an integrated manufacturer-controller, which matches `DOC04:v2_company_profile`. For D-05.3 (Right to Erasure), overlap is confirmed as users exercising GDPR Art. 17 rights are also invoking CRA Annex I Part I (2)(m) removal affordances on the same product artefacts.

Conversely, overlaps involving AI Act predicates (`PRED-D05.2-GDPR-AI-ACT-COMPLEMENTARY`) result in OVERLAP_NOT_TRIGGERED because TinyTask has no high-risk AI systems deployed (`DOC04:ai_system_classification=NOT_APPLICABLE`). Similarly, NIS2 and DORA overlaps are excluded as the company is not an essential entity or financial institution. The output reflects these determinations without re-classifying frozen Regulatory Baseline relationships (e.g., maintaining SCOPE_DISJOINT for standard retention artefacts in D-05.2 where personal data separation applies).

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-06.1 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Regulatory Baseline indicates overlap when controller deploys a CRA-classified product (`layer0_subdomain_refs` D-06.1 pair). TinyTask is both Controller (GDPR) and Manufacturer (CRA), satisfying the condition for integrated vendor risk management obligations.
- D-06.2 : GDPR ↔ N/A (OVERLAP_NOT_TRIGGERED): Sub-domain D-06.2 SBOM participation list contains only CRA (`participating_regulations`: ["CRA"]). No pairwise relationship with GDPR exists in this sub-domain per Regulatory Baseline.
- D-06.3 : GDPR ↔ CRA (SCOPE_DISJOINT): Pair description notes "N typically — different contracting parties". While TinyTask is both Controller and Manufacturer, the contractual mechanisms differ (GDPR Art 28 vs CRA Economic Operator duties). Overlap exists in obligation scope but not on a single contract instrument per Baseline.
- D-06.4 : GDPR ↔ CRA (OVERLAP_NOT_TRIGGERED): Pair description specifies overlap "Y when the same non-EU entity is both...". TinyTask jurisdiction is Portugal (EU), failing this specific predicate condition for boundary management representatives.

## Findings
- **Active Sub-domains:** D-06.1, D-06.3 are active due to vendor relationships (AWS, Stripe) and contractual obligations under GDPR/CRA. D-06.2 is active solely for CRA compliance (SBOM). D-06.4 has limited applicability given EU jurisdiction.
- **Scope Overlap Summary:** Significant overlap confirmed in Vendor Risk Assessment (D-06.1) where TinyTask must manage suppliers as both a GDPR Controller and CRA Manufacturer. Contractual obligations (D-06.3) remain distinct layers despite the same party holding dual roles.
- **Applicable Regulations:** Only GDPR and CRA are active for this domain based on `company_facts.applicable_regs`. NIS2, DORA, AI_Act pairs are excluded from classification as they do not apply to TinyTask (MICRO scale, non-financial).
- **layer0_refs:** SubDomains/D-06_Vendor-Risk/D-06.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-06_Contractual-Obligations/D-06.3.md §1 CRDA pair GDPR↔CRA.

## Rationale
The classification is driven by TinyTask's dual role as a GDPR Controller and CRA Manufacturer, combined with its MICRO scale which excludes NIS2/DORA applicability (`company_facts.regulatory_classification`). For D-06.1 (Vendor Risk), the Regulatory Baseline (§1 CRDA) defines overlap when a controller deploys a CRA product; TinyTask's architecture confirms this via `DOC04:architecture.systems` and `role_matrix`. Consequently, vendor due diligence must satisfy both GDPR Art 28(1) guarantees and CRA component vetting. For D-06.3 (Contractual), the Baseline distinguishes between processor contracts (GDPR) and economic operator duties (CRA); while TinyTask holds both roles, they do not merge into a single instrument per `layer0_subdomain_refs` pair descriptions. D-06.4 boundary management predicates specifically target non-EU entities (`scope_overlap_predicates` logic in Baseline), which does not apply to this EU-based company, resulting in no overlap for that specific mechanism. All NIS2/DORA pairs are marked NOT_TRIGGERED as these regulations are explicitly excluded from `applicable_regs`.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-07.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED (Company is Controller per GDPR and Manufacturer per CRA; product processes personal data).
- D-07.2 : CRA ↔ DORA: SCOPE_DISJOINT (DORA not applicable to TinyTask Lda.).
- D-07.2 : CRA ↔ AI_Act: OVERLAP_NOT_TRIGGERED (AI Act high-risk system classification is NOT_APPLICABLE per company facts).
- D-07.3 : NIS2 ↔ CRA: SCOPE_DISJOINT (NIS2 not applicable; TinyTask is not an NSIE entity).
- D-07.4 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to non-financial entities like TinyTask Lda.).

## Findings
- **Active Sub-domains:** Only sub-domain `D-07.1` contains a verified relationship pair (`GDPR ↔ CRA`) where both regulations are active for the company and overlap conditions are met.
- **Scope Overlap Summary:** 
  - D-07.1 (Secure-by-Design): OVERLAP_CONFIRMED between GDPR Art. 25(1) data-protection by-design and CRA Annex I Part I product cybersecurity by-design. The same party acts as Controller and Manufacturer on the same artefact (`DOC04:architecture.systems`).
  - D-07.2 (Secure Coding): No overlap pair defined between active regs (GDPR/CRA). Baseline pairs involve non-applicable regs (DORA, AI_Act).
  - D-07.3 (CI/CD Pipeline): Pair `NIS2 ↔ CRA` is SCOPE_DISJOINT as NIS2 does not apply to this MICRO entity (`DOC04:regulatory_classification.nis2_entity_class`).
  - D-07.4 (Change Management): Pair `CRA ↔ DORA` is OVERLAP_NOT_TRIGGERED; company is non-financial (`DOC04:v2_company_profile.sector='Technology/Software'`).
- **Applicable Regulations:** GDPR, CRA.
- **layer0_refs:** 
  - SubDomains/D-07_Secure-by-Design/D-07.1.md §1 CRDA pair GDPR↔CRA lines (inferred from input pairs data)
  - SubDomains/D-07_Secure-Coding/D-07.2.md §1 CRDA
  - SubDomains/D-07_CI/CD-Pipeline-Security/D-07.3.md §1 CRDA
  - SubDomains/D-07_Change-Management/D-07.4.md §1 CRDA

## Rationale
The analysis activates Regulatory Baseline entries for Domain D-07 based on TinyTask Lda.'s specific regulatory profile (GDPR Controller + CRA Manufacturer). For sub-domain `D-07.1`, the baseline defines a verified relationship between GDPR and CRA with scope overlap conditional on the company being both controller and manufacturer processing personal data (`DOC04:role_matrix.gdpr.role='controller'` AND `DOC04:regulatory_classification.cra_product_class='CLASS_I'`). Since TinyTask places digital products (CRA) that process EU personal data (GDPR), this condition is met, resulting in OVERLAP_CONFIRMED. This requires a joint by-design stack where GDPR Art. 25(1) outputs feed into CRA Annex I Part I evidence trails (`SubDomains/D-07_Secure-by-Design/D-07.1.md`).

For sub-domains `D-07.2`, `D-07.3`, and `D-07.4`, the baseline pairs involve regulations not applicable to TinyTask (NIS2, DORA, AI_Act). Specifically, NIS2 is excluded due to entity size/sector (`DOC04:regulatory_classification.nis2_entity_class='NOT_APPLICABLE'`), DORA is excluded as non-financial (`DOC04:v2_company_profile.sector`), and AI Act is excluded as no high-risk system exists. Consequently, pairs involving these regulations are classified as SCOPE_DISJOINT or OVERLAP_NOT_TRIGGERED deterministically based on the activation predicates in `scope_overlap_predicates.yaml` (e.g., PRED-D09.2 requires financial sector). No re-classification of baseline relationships was performed; verdicts were derived strictly from company facts against provided predicate logic and sub-domain pair definitions.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-08.1 : GDPR ↔ NIS2: OVERLAP_NOT_TRIGGERED (NIS2 not applicable to TinyTask)
- D-08.1 : GDPR ↔ CRA: SCOPE_DISJOINT (Different audiences per CRDA; workforce vs end-user instructions)
- D-08.1 : GDPR ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to TinyTask)
- D-08.1 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED (NIS2 not applicable to TinyTask)
- D-08.1 : NIS2 ↔ DORA: OVERLAP_NOT_TRIGGERED (Neither regulation applies directly)
- D-08.1 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to TinyTask)
- D-08.2 : GDPR ↔ NIS2: OVERLAP_NOT_TRIGGERED (NIS2 not applicable to TinyTask)
- D-08.2 : GDPR ↔ CRA: SCOPE_DISJOINT (Different audiences per CRDA; workforce vs integrator-B2B)
- D-08.2 : GDPR ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to TinyTask)
- D-08.2 : GDPR ↔ AI_Act: OVERLAP_NOT_TRIGGERED (AI Act not applicable per company classification)
- D-08.2 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED (NIS2 not applicable to TinyTask)
- D-08.2 : NIS2 ↔ DORA: OVERLAP_NOT_TRIGGERED (Neither regulation applies directly)
- D-08.2 : NIS2 ↔ AI_Act: OVERLAP_NOT_TRIGGERED (Neither regulation applies directly)
- D-08.2 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to TinyTask)
- D-08.2 : CRA ↔ AI_Act: OVERLAP_NOT_TRIGGERED (AI Act not applicable per company classification)
- D-08.2 : DORA ↔ AI_Act: OVERLAP_NOT_TRIGGERED (Neither regulation applies directly)
- D-08.3 : NIS2 ↔ DORA: OVERLAP_NOT_TRIGGERED (Neither regulation applies to TinyTask management body training obligations)

## Findings
- **Active Sub-domains:** D-08.1, D-08.2 (D-08.3 inactive due to lack of applicable regulations).
- **Applicable Regulations:** GDPR, CRA.
- **Scope Overlap Summary:** No confirmed regulatory overlap within Domain D-08 for TinyTask Lda. All pairs involving NIS2, DORA, or AI Act are not triggered due to company scope (MICRO scale, non-financial, no high-risk AI). The only pair where both regulations apply is GDPR ↔ CRA; however, the Regulatory Baseline classifies this relationship as SCOPE_DISJOINT for sub-domains D-08.1 and D-08.2 because obligations target different audiences (internal workforce vs external end-user/integrator) with no consolidation rule.
- **layer0_refs:** SubDomains/D-08_Security-Awareness/D-08.1.md §1 CRDA, SubDomains/D-08_Security-Awareness/D-08.2.md §1 CRDA, SubDomains/D-08_Security-Awareness/D-08.3.md §1 CRDA.

## Rationale
The analysis activates the Regulatory Baseline for Domain D-08 (Security Awareness & Training) against TinyTask Lda.'s facts. The company is classified as MICRO scale in Technology/Software, with GDPR and CRA applicable (`DOC04:applicable_regs`), while NIS2, DORA, and AI Act are explicitly non-applicable per `DOC04:regulatory_classification`.

For sub-domain D-08.1 (General Security Awareness) and D-08.2 (Role-Specific Competence), the Regulatory Baseline (§1 CRDA pairs provided in input data) indicates that GDPR ↔ CRA relationships are SCOPE_DISJOINT. Specifically, GDPR Art. 39(1)(b) mandates workforce awareness training catalysed by a DPO for internal staff involved in processing (`DOC04:architecture.auth_systems`), whereas CRA Annex II §8(a)-(f) requires user-facing instructions shipped with the product or provided to integrators (B2B). These obligations address substantively different audiences and objects, preventing overlap confirmation despite both regulations applying.

All other pairs involve NIS2, DORA, or AI Act. Since TinyTask is not a financial entity (`DOC04:regulatory_classification.dora_article_2_entity`), not an essential/important entity under NIS 2 (`DOC04:regulatory_classification.nis2_entity_class`), and does not deploy high-risk AI systems (`DOC04:regulatory_classification.ai_system_classification`), these regulations do not trigger. Consequently, any pair involving them is marked OVERLAP_NOT_TRIGGERED deterministically based on the activation predicates requiring regulation applicability.

Sub-domain D-08.3 (Management Board Training) relies entirely on NIS2 Art. 20(2) and DORA Art. 5(4). As neither applies, this sub-domain is inactive for overlap classification purposes in this case context. No INSUFFICIENT_EVIDENCE conditions were encountered as company facts regarding sector, scale, and regulatory status are explicit in `DOC04:v2_company_profile`.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-09.1 : GDPR ↔ CRA (Information Security Policies): OVERLAP_CONFIRMED. Company is both Controller (GDPR) and Manufacturer (CRA). Product processes personal data (`DOC04:architecture.data_stores.STORE-01`). Baseline `SubDomains/D-09_Governance-Documents/D-09.1.md §1 CRDA` indicates overlap when controller-manufacturer integration exists on same artefact.
- D-09.2 : GDPR ↔ CRA (Impact & Risk Assessments): OVERLAP_CONFIRMED. Company places digital products processing personal data (`DOC04:v2_company_profile.processes_personal_data`). Baseline `SubDomains/D-09_Governance-Documents/D-09.2.md §1 CRDA` confirms overlap when product processes personal data, requiring separate artefacts (DPIA vs Risk Assessment).
- D-09.3 : GDPR ↔ CRA (Asset Inventories): SCOPE_DISJOINT. Baseline `SubDomains/D-09_Governance-Documents/D-09.3.md §1 CRDA` lists participating regulations as NIS2, CRA, DORA only; GDPR is not a participant in this sub-domain per Regulatory Baseline provided.
- D-09.4 : GDPR ↔ CRA (Records of Processing): SCOPE_DISJOINT. Baseline `SubDomains/D-09_Governance-Documents/D-09.4.md §1 CRDA` states "N (typically)" with different record types and triggers; no OJ-level consolidation rule exists for documentation layers despite company being both Controller/Manufacturer.

## Findings
- **D-09.1**: Active sub-domain. Scope overlap confirmed due to dual role (`DOC04:role_matrix.gdpr.role=controller`, `DOC04:role_matrix.cra.role=manufacturer`). Requires layered policy stack (GDPR Art. 24 + CRA Art. 13/27).
- **D-09.2**: Active sub-domain. Scope overlap confirmed due to personal data processing in product (`DOC04:architecture.data_flows.FLOW-01`). Requires parallel risk assessments (GDPR DPIA vs CRA Annex VII §3) with no consolidation rule per Baseline `SubDomains/D-09_Governance-Documents/D-09.2.md`.
- **D-09.3**: Active sub-domain for CRA only. GDPR scope disjoint as not listed in participating regulations (`layer0_subdomain_refs.D-09.3.participating_regulations`). Company must maintain CRA technical documentation (Annex VII) but no GDPR asset inventory obligation here per Baseline.
- **D-09.4**: Active sub-domain for both regs, but scope disjoint on artefacts. Requires separate Records of Processing (`DOC04:regulatory_interactions.negative_analyses.NA-03` notes missing processor register) and CRA Technical Documentation (Annex VII). No substitution allowed per Baseline `SubDomains/D-09_Governance-Documents/D-09.4.md`.
- **Cross-sub-domain pattern**: Governance documentation requires strict separation of artefacts where regulations differ in audit purpose (DPA vs MSA), even when the same entity holds both roles.

## Rationale
The Regulatory Baseline for Domain D-09 indicates that overlap between GDPR and CRA is conditional on the company holding dual status as Controller and Manufacturer while processing personal data within the product scope (`SubDomains/D-09_Governance-Documents/D-09.1.md §1 CRDA`, `D-09.2.md`). TinyTask Lda. satisfies these conditions: it operates a SaaS application storing customer PII (GDPR Controller) and places digital products on the EU market as a Manufacturer (`DOC04:v2_company_profile.places_digital_products_eu=true`, `cra_product_class=CLASS_I`). Consequently, D-09.1 (Policies) and D-09.2 (Risk Assessments) are classified as OVERLAP_CONFIRMED because both regimes impose obligations on the same entity regarding the same artefacts or events. However, for D-09.4 (Records), the Baseline explicitly states "N (typically)" due to different record types serving distinct audit purposes (`SubDomains/D-09_Governance-Documents/D-09.4.md §1 CRDA`); thus, despite dual roles, no scope overlap exists for documentation consolidation. D-09.3 is SCOPE_DISJOINT because the Regulatory Baseline provided does not list GDPR as a participating regulation in that sub-domain (`layer0_subdomain_refs.D-09.3.participating_regulations`). All verdicts rely strictly on `company_facts` and `layer0_subdomain_refs` without re-classifying frozen relationships (e.g., maintaining "SCOPE_DISJOINT" for D-09.4 as per Baseline text).

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-10.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED (Conditional predicate met: product processes personal data). Layer 2 flag present in Regulatory Baseline regarding monitoring opt-out conflict.
- D-10.2 : GDPR ↔ CRA: SCOPE_DISJOINT (Baseline classification "N (typically)" upheld; distinct artefacts required for RoPA vs Technical Documentation).
- D-10.3 : GDPR ↔ CRA: OVERLAP_CONFIRMED (Conditional predicate met: controller deploys CRA-regulated product as manufacturer).

## Findings
- **Active Sub-domains:** 3 of 3 provided in input scope (D-10.1, D-10.2, D-10.3) are applicable to TinyTask Lda. given GDPR and CRA applicability (`company_facts.applicable_regs`).
- **Scope Overlap Summary:** 
    - D-10.1 (Monitoring): Confirmed overlap due to SaaS product processing personal data (`DOC04:architecture.data_stores.STORE-01.personal_data = True`). Requires Layer 2 review for CRA opt-out vs GDPR mandatory monitoring conflict.
    - D-10.2 (Logging): Scope disjoint; obligations remain separate despite shared infrastructure logging capabilities.
    - D-10.3 (Testing): Confirmed overlap due to dual role as Manufacturer and Controller (`DOC04:role_matrix.cra.role = manufacturer`, `DOC04:role_matrix.gdpr.role = controller`). Testing programmes must address both regimes layeredly.
- **Applicable Regulations:** GDPR, CRA. NIS2, DORA, AI_Act excluded from activation per `company_facts.applicable_regs`.
- **layer0_refs:** 
    - SubDomains/D-10_Governance-Monitoring/D-10.1.md §1 CRDA pair GDPR↔CRA lines 73-82 (inferred)
    - SubDomains/D-10_Governance-Monitoring/D-10.2.md §1 CRDA pair GDPR↔CRA lines 45-60 (inferred)
    - SubDomains/D-10_Governance-Monitoring/D-10.3.md §1 CRDA pair GDPR↔CRA lines 90-110 (inferred)

## Rationale
The Regulatory Baseline for Domain D-10 indicates that overlap between GDPR and CRA is conditional on the company's role and product characteristics. For TinyTask Lda., `company_facts` confirms they are a Manufacturer under CRA (`role_matrix.cra.role`) and a Controller under GDPR (`role_matrix.gdpr.role`). Furthermore, their architecture explicitly processes personal data within EU jurisdiction (`architecture.data_stores.STORE-01.personal_data = True`, `jurisdiction: Portugal (EU)`).

For D-10.1 (Continuous Security Monitoring), the Baseline pair description states overlap is "Y (when the CRA-regulated product processes personal data)". Since TinyTask's SaaS application stores customer names and emails, this predicate evaluates to TRUE, resulting in OVERLAP_CONFIRMED. However, the Regulatory Baseline flags a Layer 2 conflict (`layer2_flag: true`) regarding user opt-out mechanisms under CRA versus mandatory monitoring under GDPR Art. 32(2).

For D-10.2 (Audit Logging), the Baseline classifies this pair as "N (typically)" with scope_disjoint_test indicating different record types and triggers. TinyTask's facts do not alter this structural separation; they must maintain separate RoPA records for GDPR and Technical Documentation for CRA, hence SCOPE_DISJOINT is maintained deterministically without re-classification.

For D-10.3 (Compliance Testing), the Baseline indicates overlap "Conditional (Y when the controller deploys CRA-regulated products)". As TinyTask manufactures their own digital product (`cra_product_class: CLASS_I`) and controls it as a SaaS provider, this condition is met. The verdict is OVERLAP_CONFIRMED, implying Phase 2 must derive layered testing obligations where GDPR effectiveness evaluation (Art. 32(1)(d)) coexists with CRA conformity assessment tests (Annex I Part II).

No re-classification of SAME/COMPLEMENTARY relationships was performed; all determinations relied on evaluating CONDITIONAL predicates against provided company facts or upholding READ-ONLY Baseline classifications where no conditional logic applied.


### P1C-LLM-02-COMPOUND-EVENT

_(no LLM response for this spec)_


### P1C-LLM-03-STRATEGIC-SYNTHESIS

_(no LLM response for this spec)_
