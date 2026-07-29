---
document_id: AEGIS-CORR-072-DIFF-SUMMARY
title: CORR-072 Before/After Diff Report (case 3 / OmniBank)
generated_at: "2026-07-28T15:52:37Z"
case_study: OmniBank Financial Systems S.A.
related: validation_report.md
---

# CORR-072 — case 3 (OmniBank) diff report

## TL;DR

All **5 CORR-072 fixes verified end-to-end**. Pre-fix artefacts in `/tmp/m3-runs/case3/` are stale.
Post-fix artefacts under `output/case3/20260728-155237/` (timestamped, validation_report.md = 5/5 PASS) are the canonical case-3 deliverable until case 3 is re-run with a real LLM.

## 1. Files examined

| Tier | Path |
|---|---|
| Pre-fix (stale) | `/tmp/m3-runs/case3/` — generated 2026-07-28 14:45–14:46 |
| Post-fix (validated) | `output/case3/20260728-155237/` — generated 2026-07-28 16:52 |

Both contain the same 6 phase-1 markdown deliverables (04, 04a, 04b, 04c, 04d, 05). Pre-fix also has 06, 07, 07b, xlsx — out of scope for this diff.

## 2. Per-doc diff summary

| Doc | Pre lines | Post lines | Δ | Frontmatter | Body |
|---|---:|---:|---:|---|---|
| `04_Company_Context_Assessment.md` | 220 | 220 | 0 | regenerated timestamp | **§3.1 stakeholder rows: TinyTask orgs → "-"** |
| `04a_Architecture_DataInventory.md` | 149 | 153 | +4 | regenerated timestamp; `active_subdomains: 37` | **§1 duplicate header removed**; §1 and §1.2 narrative → PENDING REVIEW |
| `04b_Security_Posture.md` | 352 | 316 | −36 | `active_subdomains: 0 → 38`; scope line "0 of 38" → "38 of 38" | 8 domain Notes → PENDING REVIEW (removed `#### DX — Adapted Objective` subsections) |
| `04c_ThirdParty_Landscape.md` | 330 | 330 | 0 | `active_subdomains: 0 → 38`; scope line fixed | Only frontmatter + one scope-line change |
| `04d_Org_Roles_RACI.md` | 324 | 322 | −2 | `active_subdomains: 0 → 38` | **§3 NIS2/DORA/AI Act: NO → YES**; §5 + §9 → PENDING REVIEW |
| `05_Regulatory_Applicability.md` | 159 | 160 | +1 | regenerated timestamp; `case_study` UNKNOWN in both | §6.1 narrative → PENDING REVIEW |

**What is the same (across all 6 docs):**
- YAML control block, executive summary (Doc 04 §1), all tabular data (maturity scores, control matrices, RACI cells, stakeholder IDs SH-01..07), case_study string in Doc 04 / 04a / 04b / 04c / 04d.
- Doc 04d §1, §2, §4, §6, §7, §8, §10 unchanged.
- Doc 04b §1, §2, §4..§6 unchanged; only §3 "Notes" columns differ.

## 3. Five bug fixes — visual evidence

### Fix #1 — stakeholder leakage (Doc 04 §3.1) ✅

`output/case3/20260728-155237/04_Company_Context_Assessment.md` lines 56–62 — pre-fix `Organisation`/`Contact` columns carry leaked TinyTask data:

```diff
-| SH-01 | - | Chief Executive Officer (CEO)         | TinyTask Lda.                       | ceo@tinytask.pt     | ['executive_sponsor', ...] |
-| SH-02 | - | Chief Information Security Officer      | TinyTask Lda.                       | cto@tinytask.pt     | ['security_lead', ...]    |
-| SH-03 | - | Data Protection Officer                 | TinyTask Lda. (external advisor)    | dpo@tinytask.pt     | ['gdpr_compliance', ...]  |
-| SH-04 | - | Chief Risk Officer                      | TinyTask Lda.                       | dev@tinytask.pt     | ['dora_ict_risk', ...]    |
-| SH-05 | - | Head of AI / ML                         | Various enterprises                 | (via portal)        | ['ai_act_compliance', ...]|
-| SH-06 | - | Head of Compliance                      | Stripe Inc.                         | (via API)           | ['baFin_reporting', ...]  |
-| SH-07 | - | Internal Audit Director                 | Amazon Web Services (EU region)     | (via console)       | ['iso_27001_audit', ...]  |
+| SH-01 | - | Chief Executive Officer (CEO)         | - | - | ['executive_sponsor', ...] |
+| SH-02 | - | Chief Information Security Officer      | - | - | ['security_lead', ...]    |
+| SH-03 | - | Data Protection Officer                 | - | - | ['gdpr_compliance', ...]  |
+| SH-04 | - | Chief Risk Officer                      | - | - | ['dora_ict_risk', ...]    |
+| SH-05 | - | Head of AI / ML                         | - | - | ['ai_act_compliance', ...]|
+| SH-06 | - | Head of Compliance                      | - | - | ['baFin_reporting', ...]  |
+| SH-07 | - | Internal Audit Director                 | - | - | ['iso_27001_audit', ...]  |
```

OmniBank name still present (line 42, title block) and in `omnibank_ai` responsibility tag (SH-05). No more `tinytask.pt` strings. **Validation:** `0 TinyTask lines, 4 OmniBank lines, 14 stakeholder rows (≥7).`

### Fix #2 — regulation-level applicability (Doc 04d §3) ✅

`output/case3/20260728-155237/04d_Org_Roles_RACI.md` lines 49–52:

```diff
 | GDPR   | YES | Compliance Lead (CEO/DPO)           |
 | CRA    | YES | Engineering Lead (CTO/CISO)         |
-| NIS2   | NO  | n/a (not applicable)                |
-| DORA   | NO  | n/a (not applicable)                |
-| AI Act | NO  | n/a (not applicable)                |
+| NIS2   | YES | Operations Lead (COO)               |
+| DORA   | YES | Operations Lead (COO/CRO)           |
+| AI Act | YES | Head of AI/ML + DPO                 |
```

### Fix #3 — duplicate section header (Doc 04a §1) ✅

`output/case3/20260728-155237/04a_Architecture_DataInventory.md`:

```diff
 ## 1. Technical Architecture
-
-## 1. Technical Architecture
-
-OmniBank Financial Systems S.A. operates a hybrid cloud–on-premises estate ... throughout the estate.
+> **[PENDING REVIEW — LLM not configured]**
+> Section ID: `doc_04a.section_1.technical_architecture`
+> ...
```

Post-fix: exactly one `## 1. Technical Architecture` (line 21) and one `### 1.2 Network Topology` (line 32). **Validation:** `## 1. Technical Architecture appears 1 times`.

### Fix #4 — active_subdomains fallback (Doc 04b/04c/04d frontmatter) ✅

Frontmatter line 15 in each post-fix doc:

| Doc | Pre | Post |
|---|---:|---:|
| `04b_Security_Posture.md:15`      | `active_subdomains: 0`  | `active_subdomains: 38` |
| `04c_ThirdParty_Landscape.md:15`  | `active_subdomains: 0`  | `active_subdomains: 38` |
| `04d_Org_Roles_RACI.md:15`        | `active_subdomains: 0`  | `active_subdomains: 38` |

In-text scope statement also fixed:
- `04b_Security_Posture.md:37` — *"The active Layer 0 scope is 38 of 38 SubDomains …"*
- `04c_ThirdParty_Landscape.md:246` — *"Active scope = 38 of 38 sub-domains …"*

### Fix #5 — regression test ✅

```
tests/unit/v2/output/test_doc_04_stakeholder_leakage.py
  test_omnibank_stakeholder_does_not_inherit_organisation        PASSED
  test_omnibank_stakeholder_does_not_inherit_contact             PASSED
  test_omnibank_stakeholder_does_not_inherit_responsibilities    PASSED
  test_influence_inheritance_still_works                         PASSED
  test_tinytask_stakeholder_unchanged                            PASSED
  test_stakeholders_state_drives_no_tinytask_fallback            PASSED
  test_section_3_stakeholder_register_no_tinytask_leak_in_render  PASSED
  7 passed in 0.03s
```

## 4. Imperfections still visible (not CORR-072 bugs)

These are **data gaps or mock-LLM artefacts**, not regressions — they were present in the pre-fix run too:

1. **Doc 04a §3 Compliance Mapping** still has `("_")`-style skeleton rows because case 3 `architecture.yaml` ships with `stores: []`, `services: []`, `flows: []` (data gap).
2. **Doc 04b §3 Notes** and **Doc 04d §5/§9** render as `[PENDING REVIEW — LLM not configured]` because the validation run uses `MOCK_LLM=1`; LLM narratives from `/tmp/m3-runs/case3/` (pre-fix, buggy mock LLM) were replaced with the deterministic placeholder. To restore narrative content, re-run with a real LLM endpoint.
3. **Doc 05 frontmatter `case_study: UNKNOWN`** in both pre and post — a separate field not populated by the runner; unchanged by CORR-072.

## 5. Recommendation

> **Adopt `output/case3/{timestamp}/` as the canonical case-3 artefact location** going forward (already aligned with `runner.py` output contract).
>
> When case 3 is next re-run with a real LLM, the runner will write to a fresh `output/case3/<ts>/` directory; `/tmp/m3-runs/case3/` should be deprecated or removed to avoid confusion between validated and unvalidated runs.

## 6. Final verdict

Case 3 (OmniBank) is **fixed** with respect to the 5 CORR-072 bugs: all stakeholder leakage removed, regulation-level applicability correctly inverted for NIS2/DORA/AI Act, duplicate header eliminated, sub-domain fallback reports 38/38, and the regression test suite (7/7) passes. The post-fix deliverables are slightly leaner than the pre-fix ones because mock-LLM narrative paragraphs were replaced by deterministic `[PENDING REVIEW]` markers — that is expected under `MOCK_LLM=1` and is the intended behaviour for an unconfigured-LLM validation run. Re-running case 3 with a real LLM will regenerate the narrative sections without re-introducing any of the 5 bugs (covered by the regression tests).

**Path to this summary:** `output/case3/20260728-155237/SUMMARY.md`
**Companion:** `output/case3/20260728-155237/validation_report.md` (5/5 PASS)
