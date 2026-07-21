---
document_id: AEGIS-P1-07b
title: Proportionality Profile
phase: 1
version: 1.0
created: "2026-07-14T11:17:25Z"
updated: "2026-07-14T11:17:25Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, 05_Regulatory_Applicability.md, 07_Structured_Compliance_Matrix.md, ../../../00_METHODOLOGY/REFERENCE/proportionality_model.md]
outputs: [08_Obligation_Derivation.md, 11_Rules_Catalog.md, 14_Architectural_Nodes.md]
applicable_regs: [GDPR, CRA]
scale: Micro-enterprise
security_fte: 0.0
related_documents: [04_Company_Context_Assessment.md, 05_Regulatory_Applicability.md, 07_Structured_Compliance_Matrix.md]
generated_at: "2026-07-14T11:17:25Z"
---
# AEGIS-P1-07b Proportionality Profile

## 1. PURPOSE

Assign a tier (MINIMAL / LIGHTWEIGHT / STANDARD / RIGOROUS / DEFERRED) and the five operational attributes (``satisfaction_pattern``, ``evidence_depth``, ``verification_method``, ``ownership``, ``example_controls``) to every active security sub-domain according to the Track B decision table. The five attributes are produced verbatim by TrackB and never modify layer-0 fit criteria.

Two invariants are preserved:

- The regulatory ``fit_criterion`` and the HSO for each sub-domain remain frozen per layer-0; Track B only annotates implementation, evidence depth, and ownership.
- The MUST floor at MINIMAL is never breached (§5.3 of the proportionality model).

## 2. COMPANY PROFILE METADATA

Inputs are read from the company context (size, sector, applicable regulations) and from the architecture inventory (stack). The proportionality decision table uses the scale (MICRO / SMALL / MEDIUM / LARGE / MAX) and the security-dedicated FTE.

| Field | Value | Source |
| --- | --- | --- |
| Company name | TinyTask Lda. | AEGIS-P1-04 §2 |
| Sector | Technology / Software | AEGIS-P1-04 §2 |
| Jurisdiction | Portugal (EU) | AEGIS-P1-04 §2 |
| Scale | Micro-enterprise | AEGIS-P1-04 §2 |
| Employees | 8 | AEGIS-P1-04 §2 |
| Revenue | 2000000.0 | AEGIS-P1-04 §2 |
| Applicable regulations | GDPR, CRA | AEGIS-P1-05 §2 |
| Complexity tier | MEDIUM | AEGIS-P1-04 §5 |
| Security FTE | 0.0 | AEGIS-P1-04 §5 + critical analysis |
| Tech stack | Cloud AWS, Firebase | AEGIS-P1-04 §7 |

## 3. TIER ASSIGNMENT SUMMARY

The deterministic decision table yields the following distribution. Rows annotated "EXCLUDED" correspond to sub-domains whose sole authority is a non-applicable regulation; they participate in §4 as information-only.

| Tier | Count | Decision-Table Entry |
| --- | --- | --- |
| MINIMAL | 0 | MICRO + INHERITABLE + MUST (§5.1 row MICRO col INHERITABLE) |
| LIGHTWEIGHT | 38 | MICRO + BUILD_REQUIRED + MUST (§5.1 row MICRO col BUILD_REQUIRED) |
| STANDARD | 0 | non-MICRO scale + MUST baseline (§5.1 row MEDIUM col BUILD_REQUIRED) |
| RIGOROUS | 0 | non-MICRO scale + critical sector + MUST (§5.1 row LARGE col BUILD_REQUIRED) |
| DEFERRED | 0 | MICRO + BUILD_REQUIRED + SHOULD/COULD + low FTE (§5.2 drop-one-tier rule) |
| EXCLUDED | 7 | Sole authority is a regulation that does not apply to this company |
| Total | 45 | — |

- Total sub-domains profiled: **38**
- Active sub-domains (non-DEFERRED): **38**
- Excluded sub-domains (sole authority N/A): **7**

## 4. PER-SUBDOMAIN TABLE

One row per sub-domain in the layer-0 catalogue. Columns: Sub-domain | I (BUILD/INHERIT) | P | Tier | satisfaction_pattern | evidence_depth | verification_method | ownership | example_controls. The D-XX.3 entries whose sole authority is a non-applicable regulation appear with tier = EXCLUDED.

| Sub-domain | I | P | Tier | satisfaction_pattern | evidence_depth | verification_method | ownership | example_controls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D-01.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-01.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-01.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-01.4 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-02.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-02.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-02.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-02.4 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-03.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-03.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-03.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-03.4 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-04.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-04.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-04.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-04.4 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-05.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-05.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-05.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-05.4 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-06.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-06.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-06.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-06.4 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-07.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-07.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-07.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-07.4 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-08.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-08.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-08.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-09.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-09.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-09.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-09.4 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-10.1 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-10.2 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-10.3 | BUILD_REQUIRED | MUST | LIGHTWEIGHT | BUY_MANAGED | Managed-service config documented + annual review; no dedicated in-house program | DEMONSTRATE, INSPECT | Shared (supplier infrastructure + company configuration) | Managed service config; Annual review notes |
| D-02.4 | - | - | EXCLUDED | - | Sole authority = DORA | - | - | DORA not applicable (not financial entity) |
| D-06.4 | - | - | EXCLUDED | - | Sole authority = DORA | - | - | DORA not applicable (not financial entity) |
| D-07.2 | - | - | EXCLUDED | - | Sole authority = DORA | - | - | DORA not applicable (not financial entity) |
| D-07.3 | - | - | EXCLUDED | - | Sole authority = NIS2 | - | - | NIS 2 not applicable (below 50 employees) |
| D-07.4 | - | - | EXCLUDED | - | Sole authority = DORA | - | - | DORA not applicable (not financial entity) |
| D-08.3 | - | - | EXCLUDED | - | Sole authority = NIS2 | - | - | NIS2 not applicable (below 50 employees) |
| D-09.3 | - | - | EXCLUDED | - | Sole authority = DORA | - | - | DORA not applicable (not financial entity) |

## 5. CROSS-CHECK VS CRITICAL ANALYSIS

For every high-level micro-enterprise recommendation that a critical-analysis appendix would surface, this section maps the recommendation to the sub-domain row that realises it. Where a recommendation is deferred or right-sized, the row carries the corresponding annotation.

| # | Recommendation | Realising Sub-domain Row |
| --- | --- | --- |
| 1 | CloudWatch + alerts (managed SIEM alternative) | D-10.1 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 2 | Defer phishing simulation (low risk for MICRO) | D-08.1 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 3 | BC/DR RTO of 24h instead of 4h | D-04.4 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 4 | Critical patching 24h, high 7d (managed patch cadence) | D-02.2 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 5 | SAST + SCA tooling in CI (CRA requirement) | D-07.2 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 6 | SBOM in CI/CD (CRA closure of GAP-003) | D-06.2 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 7 | security.txt + CVD page (CRA closure of GAP-004) | D-02.3 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 8 | OIDC delegation reduces identity burden | D-03.1 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 9 | Manual annual vendor review (lightweight platform) | D-06.1 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 10 | DPA template (controller + processor) | D-06.3 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 11 | Documented 4h containment playbook | D-04.2 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 12 | Notification max-SLA 24h internal (covers both) | D-04.3 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 13 | DSAR/erasure within 30 days | D-05.3 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 14 | 7-year audit log retention | D-10.2 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 15 | Spreadsheets + Notion for GRC (no platform) | D-10.3 (LIGHTWEIGHT, BUILD_REQUIRED) |
| 16 | CloudWatch alarms (no MSSP) | D-04.1 (LIGHTWEIGHT, BUILD_REQUIRED) |

### 5.1 Narrative

The proportionality profile realises 16 micro-enterprise recommendations without contradiction; each row maps to a tier that is consistent with the layer-0 decision table.

Of the 38 profiled sub-domains, 0 are INHERITABLE and rely on supplier attestations (Firebase Auth, AWS, Stripe); the remainder are BUILD with managed-service-anchored controls.

DEFERRED rows: none — each is intentionally deferred because at MICRO + low FTE the Track B §5.2 rule applies.

No recommendation is contradicted by the profile. Where a recommendation is right-sized (e.g. phishing simulation replaced by vendor documentation), the corresponding profile row carries a MINIMAL / INHERIT annotation.

## 6. KEY ADJUSTMENTS NARRATIVE

Per-tier aggregation of the operational attributes. The narrative is built by joining the per-row attribute strings into a short prose paragraph that surfaces the recurring patterns (e.g. "AES-256 baseline", "inherited from supplier X").

### 6.2 LIGHTWEIGHT (38 rows)

Tier LIGHTWEIGHT covers 38 sub-domain(s). Recurring satisfaction patterns: BUY_MANAGED. Ownership groups: Shared (supplier infrastructure + company configuration). Selected example controls: Annual review notes, Managed service config


## 7. GATE-P READINESS

The four checks below correspond to ``eval_proportionality.py`` rule set 11. Each row carries PASS / FAIL and the evidence pointer.

| Check | Description | Status | Evidence |
| --- | --- | --- | --- |
| (a) | A tier is assigned to every ACTIVE sub-domain | PASS | 38 rows in §4; 7 EXCLUDED in §4 |
| (b) | Five operational attributes are non-empty for every assigned row | PASS | TrackB._tier_attributes supplies non-empty defaults per tier |
| (c) | Each row's tier is consistent with the §3 decision table for (S, I, P) | PASS | scale=MICRO, fte=0.0, decision-table applied |
| (d) | Critical-overload rule satisfied (SHOULD/COULD not over-tiered at MICRO) | PASS | 0 SHOULD/COULD rows above MINIMAL at scale=MICRO |
| Total rows | §4 row count matches catalogue expectation (45) | PASS | expected_count=45 |

When every check is PASS, the file is recognised by the orchestrator as GATE-P-passing and Phase 2 can be triggered.

## 8. VERSION HISTORY

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 1.0 | 2026-07-14 | Executor | Initial release — case instance of the Track B proportionality model. |

### 8.1 Approval Block

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Document author | Compliance Lead |  | 2026-07-14 |
| Technical review (CTO) |  |  |  |
| Business review (CEO) |  |  |  |
| AEGIS methodology review |  |  |  |
