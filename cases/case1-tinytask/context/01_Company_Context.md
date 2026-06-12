---
document_id: AEGIS-COMMON-01
title: AEGIS Intake Form — Company Context Assessment
phase: Common
version: 2.0
created: YYYY-MM-DD
updated: 2026-04-22
author: Compliance Lead
status: DRAFT
inputs: []
outputs: [04_Company_Context_Assessment.md]
traceability: AEGIS Class Model → CompanyContext, ComplianceContext
related_documents: [00_Taxonomy_Reference.md]
supersedes: 01_Company_Context.md (old 38-question format)
---

# AEGIS Intake Form — Company Context Assessment

## CHANGELOG

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2026-04-22 | Added Section 6 — Implementation Readiness Preview with client declaration vs system verification + 12 cross-cutting areas |
| 2.0 | 2026-04-22 | Complete redesign — layered intake with decision tree, explicit block activation, regulatory interaction scans |
| 1.0 | YYYY-MM-DD | Initial template release (deprecated) |

---

## 1. PURPOSE

This document is the **structured intake form** for AEGIS Phase 1. It replaces the old 38-question monolithic approach with a **layered, conditional** structure that:

1. Captures company facts through a **Regulatory Decision Tree** (Layer 1)
2. Activates **only relevant conditional questions** (Layer 2)
3. Requires **Regulatory Interaction Scans** when 2+ regulations apply (Layer 3)
4. Makes **Multi-Role** analysis explicit per regulation
5. Derives **Complexity Tier** automatically from applicable regulations

**7 Simplifications Resolved:**

| # | Old Problem | New Solution |
|---|-------------|--------------|
| 1 | Doc 04 empty shell ("See 01") | This form IS the filled intake — Doc 04 consolidates |
| 2 | 38+37 questions never answered | Layered questions activated by decision tree |
| 3 | Interaction Assessment never used | Layer 3 — mandatory when 2+ regulations |
| 4 | Multi-role stays in Doc 05 | Section 5 — Role Matrix per regulation |
| 5 | Regulatory flags generic | Section 4 — threshold calculation per flag |
| 6 | Block activation implicit | Section 3 — explicit "ACTIVATED/NOT APPLICABLE" per block |
| 7 | No implementation check before Phase 2 | Section 6 — client declaration vs system verification + 12 readiness areas |

---

## 2. LAYER 0 — COMPANY PROFILE (Static Facts)

**Purpose:** Capture foundational company facts that determine regulatory applicability.

### 2.1 Basic Information

| Field | Value | Notes |
|-------|-------|-------|
| Company Legal Name | | |
| Registration Country | | |
| HQ Location | | |
| Legal Structure | | |
| Website / Contact | | |

### 2.2 Size Classification

| Field | Value | Threshold Check |
|-------|-------|------------------|
| Number of Employees | | >250 = Large, >50 = Medium, ≤50 = Small |
| Annual Revenue (EUR) | | >€50M = Large, >€10M = Medium, ≤€10M = Small |
| EU Size Classification | | Derived: Micro / Small / Medium / Large |

### 2.3 Business Sector

| Field | Value | Regulatory Relevance |
|-------|-------|---------------------|
| Primary Industry Sector | | NIS 2 Annex I/II classification |
| Secondary Sectors (if any) | | |
| Service Criticality | | Critical / Important / Non-critical |

---

## 3. LAYER 1 — REGULATORY DECISION TREE

**Purpose:** Determine which regulations apply through branching logic.

### 3.1 GDPR Applicability

```
START: Does the company process personal data of EU residents?
├── YES ──────────────────┐
│                        │
│  Is the processing      │
│  purely local/household│
│  activity?             │
│  ├── YES → GDPR: NOT  │
│  │     APPLICABLE     │
│  └── NO ──────────────→ GDPR: APPLICABLE
│
└── NO → GDPR: NOT APPLICABLE
```

| Decision Point | Answer | GDPR Applicable? |
|----------------|--------|-----------------|
| Processes EU resident personal data? | YES/NO | |
| Any exemption (household/individual)? | YES/NO | |

**GDPR Roles (circle applicable):**
- CONTROLLER (decides purposes/means)
- PROCESSOR (processes on behalf of controller)
- BOTH (mixed controller/processor)

### 3.2 CRA Applicability

```
START: Does the company place products on the EU market?
├── YES ──────────────────┐
│                        │
│  Does the product      │
│  have digital         │
│  elements?            │
│  ├── NO → CRA: NOT   │
│  │     APPLICABLE    │
│  └── YES ───────────→ CRA: APPLICABLE
│                        │
│  Product Class?        │
│  ├── Default          │
│  ├── Important Class I│
│  ├── Important Class II│
│  └── Critical         │
│
└── NO → CRA: NOT APPLICABLE
```

| Decision Point | Answer | CRA Applicable? |
|----------------|--------|-----------------|
| Places products on EU market? | YES/NO | |
| Product has digital elements? | YES/NO | |
| Product Class | Default / I / II / Critical | |

### 3.3 NIS 2 Applicability

```
START: Is the company in a NIS 2 sector?
├── YES ──────────────────┐
│                        │
│  Annex I sector?       │
│  (energy, transport,   │
│   health, finance,     │
│   water, digital infra)│
│  ├── YES → Check size │
│  └── NO → Annex II?   │
│       (cloud, DC, CDN, │
│        MSP, marketplace,│
│        search, social)  │
│       ├── YES → Check  │
│       │    size        │
│       └── NO → NIS 2: │
│            NOT APPLIC. │
│
│  SIZE THRESHOLDS:      │
│  ├── ≥50 employees OR │
│  ├── ≥€10M revenue    │
│  └── ANY → NIS 2:    │
│       APPLICABLE      │
│
└── NO → NIS 2: NOT APPLICABLE
```

| Decision Point | Answer | NIS 2 Applicable? |
|----------------|--------|-------------------|
| NIS 2 Sector (Annex I or II)? | YES/NO | |
| Employees ≥50? | YES/NO | |
| Revenue ≥€10M? | YES/NO | |
| Entity Type | Essential / Important / Supplier / Not classified | |

### 3.4 DORA Applicability

```
START: Is the company a financial entity?
├── YES ──────────────────┐
│                        │
│  Art. 2(1) entity?     │
│  (bank, investment,    │
│   insurance, payment,  │
│   crypto, UCITS, AIFM) │
│  ├── YES → DORA:     │
│  │    APPLICABLE      │
│  └── NO → ICT third   │
│       party to finance?│
│       ├── YES → DORA: │
│       │    APPLICABLE │
│       └── NO → DORA:  │
│            NOT APPLIC. │
│
└── NO → DORA: NOT APPLICABLE
```

| Decision Point | Answer | DORA Applicable? |
|----------------|--------|-----------------|
| Financial entity per Art. 2? | YES/NO | |
| ICT provider to financial entities? | YES/NO | |

### 3.5 AI Act Applicability

```
START: Does the company develop/deploy/use AI systems?
├── YES ──────────────────┐
│                        │
│  Annex II product?     │
│  (AI-enabled products) │
│  ├── YES → High-risk  │
│  │    PROVIDER        │
│  └── NO → Annex III  │
│       use case?        │
│       (biometric,      │
│        critical infra, │
│        education,      │
│        employment,     │
│        essential svc,  │
│        law enforcement, │
│        border control, │
│        democracy)      │
│       ├── YES → High  │
│       │    -risk      │
│       │    DEPLOYER   │
│       └── NO → Check  │
│            prohibited? │
│            (Art. 5)   │
│            ├── YES →  │
│            │    PROHI-│
│            │    BITED │
│            └── NO →   │
│                 Limited│
│                 /Min-  │
│                 imal   │
│                 risk   │
│
└── NO → AI Act: NOT APPLICABLE
```

| Decision Point | Answer | AI Act Applicable? |
|----------------|--------|---------------------|
| AI system present? | YES/NO | |
| Annex II product? | YES/NO | High-risk PROVIDER |
| Annex III use case? | YES/NO | High-risk DEPLOYER |
| Art. 5 prohibited? | YES/NO | PROHIBITED |

### 3.6 APPLICABILITY SUMMARY

| Regulation | Applicable | Confidence | Role(s) | Notes |
|------------|------------|------------|---------|-------|
| GDPR | YES / NO | HIGH/MEDIUM/LOW | CONTROLLER / PROCESSOR / BOTH | |
| CRA | YES / NO | HIGH/MEDIUM/LOW | MANUFACTURER / DISTRIBUTOR / IMPORTER | Product class: |
| NIS 2 | YES / NO | HIGH/MEDIUM/LOW | ESSENTIAL / IMPORTANT / SUPPLIER | |
| DORA | YES / NO | HIGH/MEDIUM/LOW | FINANCIAL_ENTITY / ICT_THIRD_PARTY | |
| AI Act | YES / NO | HIGH/MEDIUM/LOW | PROVIDER / DEPLOYER / PROHIBITED | AI system: |

**Complexity Tier:**

| Tier | Criteria | Regulations | Intake Depth |
|------|----------|-------------|--------------|
| **LOW** | 1-2 regulations | | ~10-15 questions |
| **MEDIUM** | 3-4 regulations | | ~25-30 questions |
| **HIGH** | 5 regulations | | ~35-40 questions + all scans |

Derived Tier: ___________

---

## 4. LAYER 2 — CONDITIONAL QUESTIONS

**Purpose:** Capture additional context based on applicable regulations.

### 4.1 Block Activation Matrix

| Block ID | Trigger Condition | Applicable? | Questions |
|----------|------------------|-------------|-----------|
| B1: AI Governance | AI Act applicable | ACTIVATED / NOT APPLICABLE | Q39-Q46 |
| B2: NIS 2 / SOC | NIS 2 applicable | ACTIVATED / NOT APPLICABLE | Q47-Q52 |
| B3: DORA Financial | DORA applicable | ACTIVATED / NOT APPLICABLE | Q53-Q56 |
| B4: Security Org | size ≥50 OR maturity ≥Managed | ACTIVATED / NOT APPLICABLE | Q57-Q61 |
| B5: Special Category Data | GDPR + special category data | ACTIVATED / NOT APPLICABLE | Q62-Q65 |
| B6: Supply Chain | supply chain visibility = Low OR hardware | ACTIVATED / NOT APPLICABLE | Q66-Q68 |
| B7: CRA Classification | CRA applicable | ACTIVATED / NOT APPLICABLE | Q69-Q72 |
| B8: Multi-Actor Roles | 2+ regulations OR mixed roles | ACTIVATED / NOT APPLICABLE | Q73-Q75 |

**Block Activation Statement:**

> Block B1: ACTIVATED — AI Act applicable (credit scoring Annex III)
> Block B3: NOT APPLICABLE — DORA not applicable
> (etc.)

---

### 4.2 Conditional Questions by Block

#### BLOCK B1: AI Governance Extension
**Trigger:** AI Act applicable
**Activated:** YES / NO

| Question | Response | Notes |
|----------|----------|-------|
| Q39: AI System Classification | Annex II product / Annex III use case / Not classified | |
| Q40: Verification vs Identification | 1:1 verification / 1:many identification / N/A | |
| Q41: Conformity Assessment Procedure | Self-assessment / Notified body / Pending | |
| Q42: Human Oversight Mechanisms | Description | |
| Q43: Post-Market Monitoring Plan | Defined / Planned / Not started | |
| Q44: Prohibited Practices Check (Art. 5) | Confirmed not applicable / Requires analysis / Potentially applicable | |
| Q45: Downstream Provider Risk (Art. 25) | No modifications expected / May modify / Unknown | |
| Q46: AI Risk Management System | Defined / Partial / None | |

---

#### BLOCK B2: NIS 2 / SOC Extension
**Trigger:** NIS 2 applicable
**Activated:** YES / NO

| Question | Response | Notes |
|----------|----------|-------|
| Q47: Entity Classification | Essential / Important / Supplier to essential / Not classified | |
| Q48: Incident Response Capability | Dedicated team / Outsourced SOC / No formal | |
| Q49: Business Continuity Plan | Documented+tested / Documented / Not formalized | |
| Q50: Supply Chain Security Management | Formal program / Ad-hoc / None | |
| Q51: Crisis Communication Procedures | Defined / Partial / None | |
| Q52: Security Operations Center | In-house SOC / MSSP / Virtual SOC / None | |

---

#### BLOCK B3: DORA Financial Extension
**Trigger:** DORA applicable
**Activated:** YES / NO

| Question | Response | Notes |
|----------|----------|-------|
| Q53: ICT Risk Management Framework | Documented / Partial / None | |
| Q54: Third-Party ICT Provider Register | Maintained / In progress / Not started | |
| Q55: Digital Operational Resilience Testing | TLPT / Standard testing / Not started | |
| Q56: Information Sharing Arrangements | ISAC member / Bilateral / None | |

---

#### BLOCK B4: Security Organization Maturity
**Trigger:** size ≥50 employees OR securityMaturity ≥ Managed
**Activated:** YES / NO

| Question | Response | Notes |
|----------|----------|-------|
| Q57: CISO Appointment | Appointed / Planned / Not applicable | |
| Q58: DPO Appointment | Mandatory / Voluntary / Not applicable | |
| Q59: ISO 27001 Scope | Certified / In progress / Planned / Not applicable | |
| Q60: Security Training Program | Formal program / Ad-hoc / None | |
| Q61: Internal Audit Function | Dedicated / External / None | |

---

#### BLOCK B5: Special Category Data Extension
**Trigger:** GDPR applicable + special category data present
**Activated:** YES / NO

| Question | Response | Notes |
|----------|----------|-------|
| Q62: Art. 9(2) Legal Basis | Sub-paragraph + description | |
| Q63: DPIA Requirement | Mandatory by statute / Required by assessment / Not required | |
| Q64: Consent Feasibility | Feasible / Not feasible / N/A | |
| Q65: Data Protection Measures | Description | |

---

#### BLOCK B6: Supply Chain Extension
**Trigger:** supplyChainVisibility = Low OR productType includes hardware
**Activated:** YES / NO

| Question | Response | Notes |
|----------|----------|-------|
| Q66: SBOM Practices | Generated+maintained / Planned / Not started | |
| Q67: Supplier Security Assessment | Formal process / Ad-hoc / None | |
| Q68: Component Vulnerability Management | Automated / Manual / None | |

---

#### BLOCK B7: CRA Classification Extension
**Trigger:** CRA applicable
**Activated:** YES / NO

| Question | Response | Notes |
|----------|----------|-------|
| Q69: CRA Product Class | Default / Important I / Important II / Critical | |
| Q70: Conformity Assessment Regime | Self-assessment / Notified body / Pending | |
| Q71: Art. 24 Exclusion Check | Confirmed not excluded / Requires analysis / Potentially excluded | |
| Q72: EU Certification Scheme Availability | Exists / No scheme / Pending | |

---

#### BLOCK B8: Multi-Actor Role Resolution Extension
**Trigger:** 2+ regulations applicable OR dataRole = Mixed
**Activated:** YES / NO

| Question | Response | Notes |
|----------|----------|-------|
| Q73: Per-Data-Element Role Assignment | Table: data element → controller/processor/both | |
| Q74: Cross-Regulation Role Implications | Description | |
| Q75: Processor Native Compliance | YES — direct obligations / NO — inherited only | |

---

## 5. LAYER 3 — REGULATORY INTERACTION SCANS

**Purpose:** Identify conflicts and tensions when 2+ regulations apply.
**Required when:** 2+ regulations applicable
**Skip when:** Only 1 regulation applicable

### 5.1 Scan 1: Temporal Conflict Scan

Identify conflicts in notification/reporting deadlines.

| Conflict ID | Regulation A | Deadline A | Regulation B | Deadline B | Conflict Type | Resolution Principle |
|-------------|-------------|------------|-------------|------------|---------------|---------------------|
| TC-001 | [Reg] | [Xh/days] | [Reg] | [Yh/days] | Same event, different deadlines | Max-SLA: use strictest |
| TC-002 | | | | | | |
| TC-003 | | | | | | |

**Common Temporal Conflicts Reference:**

| Regulation Pair | Conflict | Typical Resolution |
|-----------------|----------|-------------------|
| CRA Art.14(2) vs GDPR Art.33 | 72h (CRA vuln) vs 72h (GDPR breach) | CRA vuln triggers GDPR breach if personal data |
| NIS 2 Art.23 vs GDPR Art.33 | 24h early warning (NIS 2) vs 72h (GDPR) | 24h first, then 72h to SA |
| DORA Art.19 vs GDPR Art.33 | 4h/24h (DORA ICT) vs 72h (GDPR) | DORA is lex specialis for financial |
| AI Act Art.73 vs NIS 2 Art.23 | 15d/2d/10d (AI Act) vs 24h/72h (NIS 2) | Separate triggers — different events |

---

### 5.2 Scan 2: Requirement Conflict Scan

Identify regulatory requirements that contradict or constrain each other.

| Conflict ID | Regulation A | Requirement A | Regulation B | Requirement B | Conflict Type | Resolution |
|-------------|-------------|--------------|-------------|--------------|---------------|------------|
| RC-001 | [Reg] | [Req] | [Reg] | [Req] | Contradictory / Constraining | |
| RC-002 | | | | | | |

**Common Requirement Conflicts Reference:**

| Conflict | Regulations | Description | Resolution |
|----------|------------|-------------|------------|
| Erasure vs Logs | GDPR Art.17 vs DORA Art.17 | Right to erasure vs immutable logs | Erasure applies to personal data; logs may retain anonymized |
| Minimization vs Logging | GDPR Art.5(1)(c) vs NIS 2 Art.21 | Data minimization vs incident logging | Minimization is principle; logging is exception |
| Privacy by Design vs Security Updates | GDPR Art.25 vs CRA Art.13 | PbD vs update obligations | Integrate PbD into update process |

---

### 5.3 Scan 3: Trigger Mismatch Scan

Identify similar assessments with different triggers across regulations.

| Conflict ID | Assessment Type | Trigger A (Regulation) | Trigger B (Regulation) | Mismatch | Resolution |
|-------------|----------------|------------------------|------------------------|----------|------------|
| TM-001 | DPIA / FRIA / Risk assessment | [Reg] — [trigger] | [Reg] — [trigger] | [Mismatch] | |
| TM-002 | | | | | |

**Common Trigger Mismatches Reference:**

| Assessment | GDPR Trigger | AI Act Trigger | DORA Trigger | NIS 2 Trigger |
|------------|-------------|----------------|--------------|---------------|
| DPIA | Art.35 — large-scale, special category, systematic monitoring | Art.27 FRIA — high-risk AI | Art.45 ICT risk assessment | Art.21 risk analysis |
| Incident Reporting | Art.33 — personal data breach | Art.73 — serious AI incident | Art.17-19 — ICT major incident | Art.23 — significant incident |
| Testing | N/A | Art.17 post-market testing | Art.24-27 TLPT | Art.21 security testing |

---

### 5.4 Scan 4: Negative Analysis Checklist

Confirm non-applicability of specific regulatory provisions.

| Item | Regulation | Provision | Non-Applicability Confirmed? | Rationale |
|------|-----------|-----------|------------------------------|-----------|
| NA-001 | AI Act | Art. 5 (Prohibited practices) | YES / NO / REQUIRES ANALYSIS | |
| NA-002 | CRA | Art. 24 (Exclusions) | YES / NO / REQUIRES ANALYSIS | |
| NA-003 | AI Act | Art. 25 (Downstream provider) | YES / NO / REQUIRES ANALYSIS | |
| NA-004 | GDPR | Art. 37 (DPO mandatory) | YES / NO / UNDETERMINED | |
| NA-005 | NIS 2 | Art. 3 (Entity classification) | Essential / Important / Not | |

---

## 5.5 INTERACTION SUMMARY

| Metric | Value |
|--------|-------|
| Applicable Regulations | [X/5] |
| Active Conditional Blocks | [List: B1, B2, ...] |
| Temporal Conflicts Identified | [X] |
| Requirement Conflicts Identified | [X] |
| Trigger Mismatches Identified | [X] |
| Negative Analyses Completed | [X/5] |
| **Complexity Tier (Final)** | LOW / MEDIUM / HIGH |

---

## 6. IMPLEMENTATION READINESS PREVIEW

**Purpose:** Capture client's current implementation state across areas that cut across all applicable regulations. This provides a preliminary gap view BEFORE Phase 2 derives specific obligations.

**Trigger:** This section is completed after Section 3 (Applicability Summary) confirms which regulations apply.

### 6.1 Client Declaration vs System Verification

The client declares which regulations they believe apply, and the system verifies against threshold criteria.

| Regulation | Client Declaration | System Check | Final Applicable | Confidence |
|------------|-------------------|--------------|------------------|------------|
| GDPR | YES / NO / UNCERTAIN | Threshold met? | YES / NO | HIGH / MEDIUM / LOW |
| CRA | YES / NO / UNCERTAIN | Digital product + thresholds? | YES / NO | HIGH / MEDIUM / LOW |
| NIS 2 | YES / NO / UNCERTAIN | Sector + size thresholds? | YES / NO | HIGH / MEDIUM / LOW |
| DORA | YES / NO / UNCERTAIN | Financial entity per Art. 2? | YES / NO | HIGH / MEDIUM / LOW |
| AI Act | YES / NO / UNCERTAIN | AI system present? Annex II/III? | YES / NO | HIGH / MEDIUM / LOW |

**Confidence Scale:**
- HIGH = Client declaration matches system verification with clear evidence
- MEDIUM = Partial match or ambiguous evidence
- LOW = Client declaration contradicts system check — requires further analysis

### 6.2 Implementation Readiness Areas

Assess current state across 6 cross-cutting implementation areas. These apply regardless of which specific regulations are applicable.

| Area | Question | Response | Evidence / Notes |
|------|----------|----------|------------------|
| **IR-01: Governance** | Is there a named individual responsible for security governance (CISO or equivalent)? | YES / NO / PARTIAL | |
| **IR-02: DPO** | Is a Data Protection Officer appointed or required? | YES / NO / NOT REQUIRED | Art. 37 GDPR assessment |
| **IR-03: Incident Response** | Is there a documented incident response capability? | YES / NO / PARTIAL | Team, process, contact |
| **IR-04: Business Continuity** | Is there a documented business continuity plan? | YES / NO / PARTIAL | Tested / Documented only |
| **IR-05: Data Processing Register** | Is there a record of processing activities (Art. 30 GDPR)? | YES / NO / PARTIAL | Register location |
| **IR-06: Supplier Register** | Is there a register of critical suppliers / third-party providers? | YES / NO / PARTIAL | Number of suppliers tracked |
| **IR-07: Security Policies** | Are there documented security policies? | YES / NO / PARTIAL | Scope, last review |
| **IR-08: Training** | Is there a security awareness / training program? | YES / NO / PARTIAL | Frequency, audience |
| **IR-09: Access Control** | Is there a formal access control policy? | YES / NO / PARTIAL | RBAC, MFA, reviews |
| **IR-10: Data Classification** | Is there a data classification scheme? | YES / NO / PARTIAL | Categories defined |
| **IR-11: Asset Inventory** | Is there a current inventory of IT assets? | YES / NO / PARTIAL | CMDB, asset list |
| **IR-12: Risk Management** | Is there a documented risk management process? | YES / NO / PARTIAL | Methodology, last assessment |

### 6.3 Implementation Readiness Summary

| Metric | Count |
|--------|-------|
| Total Areas Assessed | 12 |
| Fully Implemented (YES) | [X] |
| Partially Implemented | [X] |
| Not Implemented (NO) | [X] |
| **Readiness Score** | [X/12] — [LOW / MEDIUM / HIGH] |

**Readiness Score Thresholds:**
- HIGH: ≥9 areas implemented
- MEDIUM: 5-8 areas implemented
- LOW: <5 areas implemented

**Note:** This score is a preliminary indicator. The actual gap analysis against specific obligations is performed in Phase 2 (Doc 11 — Rules Catalog) and verified in Doc 07 (Compliance Matrix).

---

## 7. ROLE MATRIX

**Purpose:** Document which roles the company holds per applicable regulation.

| Regulation | Role(s) | Native Obligations | Inherited Obligations | Notes |
|------------|---------|-------------------|----------------------|-------|
| GDPR | CONTROLLER / PROCESSOR / BOTH | Art. 32 security, Art. 33 breach notification | Via DPA from processors | |
| CRA | MANUFACTURER / DISTRIBUTOR / IMPORTER | Annex I essential requirements, Art. 13-14 reporting | Via contracts from suppliers | Product class: |
| NIS 2 | ESSENTIAL / IMPORTANT / SUPPLIER | Art. 21 risk management, Art. 23 incident notification | Via DPA from processors | 24h early warning |
| DORA | FINANCIAL_ENTITY / ICT_THIRD_PARTY | Art. 5-16 ICT risk framework, Art. 17-19 incident reporting | Via contracts from CTPPs | |
| AI Act | PROVIDER / DEPLOYER / PROHIBITED | Art. 9-15 high-risk requirements, Art. 72 post-market | Via Art. 25 agreements | |

---

## 8. COMPLEXITY TIER DERIVATION

| Criterion | Threshold | Result |
|-----------|-----------|--------|
| Number of applicable regulations | ≥4 | HIGH |
| | 2-3 | MEDIUM |
| | 1 | LOW |
| Active conditional blocks | ≥4 | HIGH |
| | 2-3 | MEDIUM |
| | 0-1 | LOW |
| Regulatory interactions (conflicts + mismatches) | ≥3 | HIGH |
| | 1-2 | MEDIUM |
| | 0 | LOW |

**Final Complexity Tier:** ___________

---

## 9. GATE CRITERIA

### LOW Complexity Tier
- [ ] Layer 0 (Company Profile) complete
- [ ] GDPR applicability determined
- [ ] Section 6.1: Client declaration vs system check (1 regulation)
- [ ] Layer 2: No conditional blocks activated (or 1)
- [ ] Layer 3: Not required (only 1 regulation)

### MEDIUM Complexity Tier
- [ ] Layer 0 complete
- [ ] At least 2 regulations applicable
- [ ] Section 6.1: Client declaration vs system check for each regulation
- [ ] Section 6.2: Implementation Readiness (≥6 of 12 areas responded)
- [ ] Layer 1 decision tree completed
- [ ] Layer 2: At least 2 conditional blocks activated
- [ ] Layer 3: Temporal Conflict Scan + Negative Analysis required
- [ ] Role Matrix completed

### HIGH Complexity Tier
- [ ] Layer 0 complete
- [ ] All 5 regulations assessed
- [ ] Section 6.1: Client declaration vs system check (all 5 regulations)
- [ ] Section 6.2: Implementation Readiness (all 12 areas responded)
- [ ] Section 6.3: Readiness Summary calculated
- [ ] Layer 1 decision tree completed
- [ ] Layer 2: All applicable blocks activated
- [ ] Layer 3: All 4 scans required
- [ ] Role Matrix with all applicable regulations
- [ ] Complexity Tier derived and justified

---

## N. DOCUMENT APPROVAL

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Document Author | Compliance Lead | | |
| Technical Review | | | |
| Business Review | | | |
| AEGIS Methodology Review | | | |

---

**Supersedes:** `01_Company_Context.md` (old 38-question format)
**Next Document:** `04_Company_Context_Assessment.md` (consolidation)
