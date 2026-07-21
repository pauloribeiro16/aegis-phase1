---
document_id: AEGIS-P1-04d
title: Organisation, Roles & RACI Matrix
version: 1.0
status: DRAFT
generated_at: "2026-07-14T11:03:01Z"
phase: 1
created: "2026-07-14T11:03:01Z"
updated: "2026-07-14T11:03:01Z"
author: Executor
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, 04a_Architecture_DataInventory.md, 04c_ThirdParty_Landscape.md, ../00_COMMON/01_Company_Context.md]
outputs: [04b_Security_Posture.md, 05_Regulatory_Applicability.md, 06_Clause_Mapping_Matrix.md, 07_Structured_Compliance_Matrix.md]
applicable_regs: [GDPR, CRA]
active_subdomains: 31
inactive_subdomains: [D-02.4, D-06.4, D-07.2, D-07.3, D-07.4, D-08.3, D-09.3]
related_documents: [../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-08_Human-Factors/, ../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-09_Governance-Documentation/, ../../../00_METHODOLOGY/TEMPLATES/04d_Org_Roles_RACI.md]
supersedes: none
---
# Organisation, Roles & RACI Matrix

## 1. Purpose & Scope

This document describes TinyTask Lda.'s organisational structure and the per-activity RACI matrix that allocates information-security and data-protection responsibilities. It maps to Layer 0 sub-domains **D-08 (Human Factors)** and **D-09 (Governance Documentation)**, and supports compliance with **GDPR Art. 37-39** (DPO designation), **GDPR Art. 32** (security of processing), **CRA Annex I Part II (8)(f)** (vulnerability handling competence), and **CRA Annex VII §5** (technical documentation — organisational measures).

**Scope:** D-08 and D-09 only. Architecture context is in `04a_Architecture_DataInventory.md`; third-party context is in `04c_ThirdParty_Landscape.md`; security posture is in `04b_Security_Posture.md`.

**Critical caveat — sub-domain D-08.3 is INACTIVE.** D-08.3 (Management Board Training) participates only in **NIS2** and **DORA**; neither regulation applies at the current proportionality tier. Consequently, there is **no OJ-level regulatory mandate** for formal board cybersecurity training. The board-training row in the RACI matrix is retained as a **best-practice placeholder**, not as a derived compliance requirement.

**Proportionality note (P2 — Company Reality First):** TinyTask Lda. has 8 employee headcount. Formal role separation characteristic of larger firms (separate DPO, CISO, IT Manager, Legal, HR, IR Lead) is not feasible — many hats fall on the CEO/CTO/lead developer. RACI assignments concentrate **A** (Accountable) on the CEO or CTO, with one **R** (Responsible) per activity and the rest as **C** (Consulted) or **I** (Informed).

## 2. Company-Level Responsible

The following roles cover the obligations applicable to the company. Each row pairs a role with the regulations it owns and a default owner title. Actual assignment is delegated to §3 (Key Roles) and §5 (RACI Matrix).

| Role | Default Owner | Regulations |
| --- | --- | --- |
| Compliance Lead | Chief Compliance Officer / DPO (CEO) | GDPR — controller + processor |
| Engineering Lead | CTO / Head of Engineering | CRA — secure development / vulnerability |
| Operations Lead | COO / Head of Operations | NIS 2, DORA (when applicable) |
| DPO (voluntary) | CEO (voluntary designation per Art. 37) | GDPR Art. 37-39 |
| CISO / Security Lead | CTO (CRA Annex I Part II (8)(f)) | CRA Annex I, NIS 2, DORA |

## 3. Regulation-Level Owner

Per-regulation ownership matrix. "n/a" indicates the regulation is not applicable at the current proportionality tier; "-" indicates owner is not separately tracked.

| Regulation | Applicable | Owner |
| --- | --- | --- |
| GDPR | YES | Compliance Lead (CEO/DPO); controller + processor (controller, processor) |
| CRA | YES | Engineering Lead (CTO/CISO); manufacturer (-) |
| NIS2 | NO | n/a (not applicable) |
| DORA | NO | n/a (not applicable) |
| AI Act | NO | n/a (not applicable) |

## 4. Key Roles

Functional roles are listed below. In a low-tier organisation many hats fall on a single individual; backup assignments are documented for incident-trigger continuity.

| Role | Person / Team | Reports To | FTE Allocation | Backup |
| --- | --- | --- | --- | --- |
| CEO (also DPO) | Founder #1 | Board (2 founders) | 0.2 DPO + 0.8 CEO (combined 1.0) | CTO (acting DPO) |
| CTO (also CISO) | Founder #2 | Board (2 founders) | 0.3 CISO + 0.7 CTO (combined 1.0) | CEO (acting CISO) |
| Lead Developer | Senior engineer — most-tenured non-founder | CTO | 1.0 (full developer; ~0.1 on security tasks via CI/CD and patching) | CTO for code-related security tasks |
| Developers × 5 | 5 full-stack developers | CTO | 5 × 1.0 across product development, secure coding, CI/CD maintenance, on-call rotation | Peer developers |
| External Legal Adviser | External law firm (retainer) | CEO | 0 (retainer; ad-hoc consultation) | None — single retainer |
| Management Board | 2 founders (CEO + CTO) | — | — | n/a — board is the board |
| IR Lead | CTO in CISO capacity | n/a (rotational developer on-call) | Same as CTO/CISO; on-call rotation across developers | CEO |

## 5. Reporting Lines

The following ASCII tree and narrative describe the reporting structure.

```

                            ┌─────────────────────────────┐
                            │       Management Board       │
                            │   (2 founders — CEO + CTO)    │
                            └──────────────┬────────────────┘
                                           │
               ┌───────────────────────────┼────────────────────────┐
               │                                                         │
        ┌──────▼─────────┐                                       ┌──────▼─────────┐
        │      CEO       │                                       │      CTO       │
        │ 0.2 FTE DPO    │                                       │ 0.3 FTE CISO   │
        │ + founder ops  │                                       │ + founder tech │
        └──┬─────────────┘                                       └──┬─────────────┘
           │                       ┌─────────────────┐              │
           │                       │ External Legal  │              │
           │                       │   (DPO Support) │              │
           │                       └─────────────────┘              │
           │                                                        │
           └────────────────────┬───────────────────────────────────┘
                                │
                   ┌────────────▼────────────┐
                   │     Lead Developer       │
                   │    (senior engineer)     │
                   └────────────┬─────────────┘
                                │
             ┌──────────────────┴──────────────────┐
             │                                      │
    ┌────────▼────────┐                  ┌─────────▼───────┐
    │ Developers × 5  │                  │  (Developers on │
    │  (full-time)    │                  │   security rota)│
    └────────────────┘                  └────────────────┘

```

**Plain-text description:**

The **Management Board** consists of the two founders (CEO and CTO); it has final accountability for security and compliance posture. The **CEO** holds the voluntary **DPO** hat (~0.2 FTE) and reports to the Board. The **CTO** holds the **CISO** hat (~0.3 FTE) and reports to the Board. The **Lead Developer** reports to the CTO and is the single point of accountability for day-to-day code-level and CI/CD-level security controls. The **5 developers** report to the CTO; they form the on-call rotation for security alarms and execute patching / vulnerability remediation under CTO direction. The **External Legal Adviser** is on retainer; reports to the CEO; consults on DPA template updates and breach-notification decisions. There is **no separate HR function**; people-ops (onboarding, training coordination) is part of the CEO 0.2 FTE. **No IT Manager role** exists; cloud-managed services are configured and reviewed by the CTO/CISO and lead developer.

## 6. RACI Matrix

**Legend:** **R** = Responsible, **A** = Accountable (single sign-off; one A per row), **C** = Consulted, **I** = Informed, **—** = Not involved.

**Column abbreviations** (people are listed once each; in a small team, multiple hats are worn):
- **DPO** = CEO acting as voluntary Data Protection Officer
- **CISO** = CTO acting as Security Lead / CISO
- **Dev** = Lead Developer + developer team
- **Legal** = External Legal Adviser (retainer)
- **HR** = CEO in HR-coordination role
- **Board** = 2 founders (CEO + CTO)

### 6.1 Data Protection (sub-domain D-01.1, D-01.2, D-01.3, D-01.4)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Encrypt personal data at rest | C | A | R | I | — | I |
| Manage encryption keys | C | A | R | I | — | I |
| Notify DPA within 72h (Art. 33 GDPR) | R | A | C | C | — | I |
| Conduct DPIA (Art. 35 GDPR) | R | C | C | A | — | I |

### 6.2 Vulnerability Management (sub-domain D-02.1, D-02.2, D-02.3, D-02.4)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Run vulnerability scans (Snyk, dependency review) | I | A | R | — | — | I |
| Apply critical patches (CRA Annex I Part I (2)(f)) | I | A | R | — | — | I |
| Annual penetration testing | I | A | R | I | — | I |
| Operate CVD / security.txt (CRA Art. 14) | C | A | R | I | — | I |

### 6.3 Access Control (sub-domain D-03.1, D-03.2, D-03.3, D-03.4)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Manage IAM (Auth0 + cloud IAM) | C | A | R | I | — | I |
| Enforce MFA (admins; future customer MFA) | C | A | R | — | — | I |
| Quarterly access review | C | A | R | I | — | I |
| Offboarding (revoke access within 24h) | C | A | R | I | C | I |

### 6.4 Incident Response (sub-domain D-04.1, D-04.2, D-04.3, D-04.4)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Detect incident | I | A | R | — | — | I |
| Contain incident | I | A | R | C | — | I |
| Notify authorities (72h GDPR / 24h CRA) | R | A | C | C | — | I |
| Notify controllers (Art. 33(2) processor→controller) | R | A | C | C | — | I |
| Recover systems (RPO / RTO targets) | I | A | R | I | — | I |
| Post-incident review | C | A | R | I | — | I |

### 6.5 Data Lifecycle (sub-domain D-05.1, D-05.2, D-05.3, D-05.4)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Enforce data minimisation | R | A | C | C | — | I |
| Manage retention policies | R | A | C | C | — | I |
| Process erasure requests (Art. 17 GDPR) | R | C | A | C | — | I |
| Process portability requests (Art. 20 GDPR) | R | C | A | C | — | I |

### 6.6 Supply Chain (sub-domain D-06.1, D-06.2, D-06.3, D-06.4)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Assess vendor security (annual review) | C | A | R | C | — | I |
| Maintain SBOM (CRA Annex I Part II (1)) | I | A | R | — | — | I |
| Manage DPA contracts with B2B controllers | R | C | I | A | — | I |
| Manage DPA acceptance from subprocessor vendors | R | A | I | C | — | I |

### 6.7 Secure Development (sub-domain D-07.1, D-07.2, D-07.3, D-07.4)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Threat model per feature | C | C | R/A | I | — | I |
| Code review | I | C | R/A | — | — | I |
| Security testing in CI/CD (SAST/DAST/SCA) | I | A | R | — | — | I |
| Change approval (CAB) for production releases | I | C | R | I | — | A |

### 6.8 Human Factors (sub-domain D-08.1, D-08.2; D-08.3 inactive)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Annual security awareness training (D-08.1) | C | A | I | I | R | I |
| Role-specific training — secure coding (D-08.2) | C | A | R | — | I | I |
| Role-specific training — DPO competence refresh (D-08.2) | R/A | C | — | C | I | I |

### 6.9 Governance (sub-domain D-09.1, D-09.2, D-09.3, D-09.4)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Approve security policies | C | C | C | C | C | A |
| Conduct risk assessments (annual + per-feature) | R | A | C | C | I | I |
| Maintain asset inventory | C | A | R | I | — | I |
| Maintain RoPA (Art. 30 GDPR) | R | A | C | C | — | I |
| Maintain CRA Annex VII technical documentation | C | A | R | C | — | I |

### 6.10 Monitoring & Audit (sub-domain D-10.1, D-10.2, D-10.3)

| Activity | DPO (CEO) | CISO (CTO) | Dev | Legal | HR | Board |
| --- | --- | --- | --- | --- | --- | --- |
| Continuous security monitoring (Datadog; SIEM-light) | I | A | R | — | — | I |
| Audit-log retention | C | A | R | I | — | I |
| Annual compliance testing | C | A | R | I | — | I |

**Reading note:** Rows that place both **CISO = A** and **Dev = R** mirror the standard "RACI for small teams" pattern — the CTO/CISO owns the outcome; the lead developer (with the rotating developer team) does the work. Where the activity is data-protection-specific (e.g., Art. 17 erasure), **DPO = A** holds the legal accountability per Art. 28(3); implementation **R** swaps to Dev. Board rows are predominantly **I** operationally and **A** for governance-level approvals.

## 7. Training Status

| Role | Training Required | Last Completed | Next Refresh | Source (D-08.x) |
| --- | --- | --- | --- | --- |
| All staff | Annual security awareness (D-08.1) | NOT STARTED | 2026-12-31 (target) | D-08.1 |
| Developers (incl. Lead) | Secure coding (OWASP Top 10; SAST/DAST feedback loop) | NOT STARTED — informal ad-hoc only | 2026-12-31 (target) | D-08.2 |
| DPO (CEO) | GDPR refresher; Art. 33/34 mechanics; Art. 28(3) | 2025-Q4 (informal) | 2026-Q4 | D-08.2 |
| CTO/CISO | CRA Annex I mapping refresh; CVE-triage workflow | NOT STARTED | 2026-12-31 (target) | D-08.2 |
| External Legal Adviser | DPO-support retainer briefing (annual CPD on EU regs) | Retained on continuing basis | 2026-Q4 (kickoff) | D-08.2 (informal) |
| Management Board (2 founders) | D-08.3 — INACTIVE — placeholder row only | n/a (D-08.3 INACTIVE) | n/a | D-08.3 (INACTIVE) |

## 8. Compliance Mapping (Layer 0)

| Sub-domain | Role(s) Responsible | RACI Summary | Notes |
| --- | --- | --- | --- |
| D-08.1 General Awareness | CEO (HR-coordination role) | HR=CEO/R, CISO=CTO/A | Coverage = all staff; not yet started. |
| D-08.2 Role-Specific Competence | CTO/CISO + DPO (CEO) | DPO=R/A for DPO competence; Dev=R + CISO=CTO/A for developer training | Developer secure-coding training not yet started. |
| D-08.3 Management Board Training | OUT OF SCOPE — INACTIVE | n/a | NIS2 + DORA-only; both regulations inapplicable. Not a derived gap. |
| D-09.1 Information Security Policies | Board for approval; Dev for drafting | Board=A, all=C | Policies not yet written — explicitly documented in 04b_Security_Posture.md. |
| D-09.2 Impact & Risk Assessments | DPO + CISO | DPO=R, CISO=A | Annual risk assessment planned; DPIA capability resident in DPO. |
| D-09.3 Asset Inventories | CTO/CISO + Dev | Dev=R, CISO=A | Asset inventory documented in 04a §1; CMDB-grade maturity not yet claimed. |
| D-09.4 Records of Processing (RoPA) | DPO + Legal | DPO=R, Legal=A | Not yet started — captured as a Phase 1 gap. |

## 9. Escalation Paths

Routine security events escalate from the on-call developer to the CTO/CISO; data-protection incidents additionally escalate to the CEO/DPO for the 72-hour GDPR Art. 33 personal-data breach clock and the 24-hour CRA early-warning notification. External Legal Adviser is consulted at the notification decision step. Board escalation triggers are: (a) any governance policy breach, (b) regulatory action or inquiry, (c) a security event with material customer-trust impact, (d) a deliberate deviation from the proportionality target. CRA Annex I Part II (8)(f) competence requirements apply: the CISO must be able to evidence vulnerability handling competence at the moment of escalation. Single-individual concentration risk is mitigated by documenting CEO/CTO cross-coverage in §4.

## 10. Gaps & Known Limitations

| Gap ID | Description | Severity | Linked Sub-Domain |
| --- | --- | --- | --- |
| GAP-RACI-01 | No formal security-awareness training programme in place (annual cycle, completion tracking) | MEDIUM | D-08.1 |
| GAP-RACI-02 | No formal secure-coding curriculum for developers (reliance on code review + Snyk feedback) | MEDIUM | D-08.2 |
| GAP-RACI-03 | DPO refresher cycle not cadence-locked (last done 2025-Q4 informally; next target 2026-Q4) | LOW | D-08.2 |
| GAP-RACI-04 | D-08.3 board training absent — deliberately not in scope; documented as non-derivation | LOW (informational only) | D-08.3 (INACTIVE) |
| GAP-RACI-05 | Single DPO/CISO-individual concentration risk; backup is the other founder | LOW | D-09.1 |

## 11. Gate

| Gate Criterion | Status | Evidence |
| --- | --- | --- |
| All key roles identified with FTE allocation | PASS | Section 4 |
| Regulation-level owners documented | PASS | Section 3 |
| RACI matrix populated for all 10 macro-domains | PASS | Section 6 |
| Reporting lines documented | PASS | Section 5 |
| Training status populated for all roles | PASS | Section 7 |
| Compliance Mapping populated for D-08/D-09 | PASS | Section 8 |
| Gaps explicitly listed (not silently accepted) | PASS | Section 10 |

**Gate Status:** PASS (proportionate for LOW-tier micro SaaS under P2).

## N-1. Version History

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 1.0 | 2026-07-14 | Executor | Generated RACI from state.regulations and a deterministic per-domain mapping |

## N. Document Approval

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Document Author | Executor |  | 2026-07-14 |
| Technical Review | CTO |  |  |
| Business Review | CEO |  |  |
| AEGIS Methodology Review | Validator |  |  |

## See also

- **Data backbone:** `Case_01_Phase1.xlsx` (13 sheets: COVER, SYSTEMS, DATA_STORES, DATA_FLOWS, PERSONAL_DATA, THIRD_PARTIES, ROLES_RACI, MATURITY, SUBDOMAINS, REG_CHAIN, COMPLIANCE, GAPS, PRIORITIES)
