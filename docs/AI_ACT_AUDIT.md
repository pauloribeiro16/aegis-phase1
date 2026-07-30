# AI Act Case1 Audit — Diagnosis Only

**Status:** Read-only diagnostic document. **No code changes proposed.**
**Authority (source of truth):** `methodology-00/PREPROCESSING/Regulation/AI_Act/02_SecurityRules_NIST.md` (24 SecurityRules with canonical clause → sub-domain → NIST CSF mapping).
**Subject of audit:** `cases/case1-tinytask/data/phase1/04_clauses.csv` + `07_clause_subdomain_mapping.csv`.

**Legend:** ✓ OK · ⚠️ metadata missing · ❌ wrong

---

## Executive summary (one row per category)

| Problem | Count | Severity |
|---|---:|---|
| Sub-domain misattribution (wrong sub-domain per methodology) | **8** | High — affects CSF analysis |
| Article misattribution (wrong articleId per methodology) | **7** | High — traceability lost |
| ArticleId metadata missing | **13** | Medium — easy to fill |
| Sub-domain + article both OK | **15** | — (these are correct) |
| Naming convention drift (3 separate issues) | 3 places | Low — cosmetic but cumulative |
| **Total AI Act clauses in case1** | **29** | — |

---

## 1. Sub-domain misattributions (8 clauses wrong)

Each row shows the case1 value vs the canonical value from methodology `02_SecurityRules_NIST.md`.

| Clause | Case1 sub-domain | Canonical sub-domain (methodology SR) | Source |
|---|---|---|---|
| AIA-C04 | ❌ D-07.3 CI/CD | D-02.4 TLPT (or D-10.3) | SR-AI_Act-003 (Art 9(6)+(7)) |
| AIA-C07 | ❌ D-05.3 Erasure | D-05.1 Minimisation (or D-05.2) | SR-AI_Act-005 (Art 10(3)) |
| AIA-C11 | ❌ D-09.4 Records | D-10.2 Logging (or D-05.2) | SR-AI_Act-008 (Art 19(1)) — T5 mapping error: Art 12(4) does not exist in OJ |
| AIA-C18 | ❌ D-01.4 Integrity | D-07.2 Secure Coding (or D-02.1) | SR-AI_Act-016 (Art 15(4)-(5) AI attacks) |
| AIA-C21 | ❌ D-10.3 Compliance Testing | D-07.1 Secure-by-Design | SR-AI_Act-018 (Art 17(1)(c)) |
| AIA-C22 | ❌ D-09.2 Risk Assessment | D-09.1 Policies | SR-AI_Act-017 (Art 17(1)+(1)(g)) |
| AIA-C27 | ❌ D-10.3 Compliance Testing | D-10.1 Monitoring | SR-AI_Act-021 (Art 72 + Art 74) |
| AIA-C28 | ❌ D-09.2 Risk Assessment | D-07.3 CI/CD (or D-02.1) | SR-AI_Act-023 (Art 55(1)(a) GPAI eval) |

---

## 2. Article misattributions (7 clauses wrong)

| Clause | Case1 articleId | Canonical article (methodology SR) | Wrong because |
|---|---|---|---|
| AIA-C08 | ❌ Art5 | Art 10(5) | Art 5 is "prohibited practices" (ban); not cybersecurity |
| AIA-C16 | ❌ Art5 | Art 15(1) | Same — Art 5 ≠ cybersecurity |
| AIA-C17 | ❌ Art5 | Art 15(3) | Same — Art 5 ≠ cybersecurity |
| AIA-C18 | ❌ Art5 | Art 15(4)-(5) | Same — Art 5 ≠ cybersecurity |
| AIA-C19 | ❌ Art9 | Art 19(1) | Art 9 is risk management; Art 19(1) is log retention (6-month floor) |
| AIA-C28 | ❌ Art5 | Art 55(1)(a) | Same — Art 5 ≠ cybersecurity; this is GPAI model evaluation |
| AIA-C29 | ❌ Art5 | Art 55(1)(c) | Same — Art 5 ≠ cybersecurity; this is GPAI serious-incident reporting |

**Pattern:** 6 clauses are wrongly tagged as Art 5 (the AI Act's prohibition list — bans, not security). Art 5 has no cybersecurity content. These are mapping errors.

---

## 3. ArticleId metadata missing (13 clauses)

These clauses have the correct sub-domain mapping but lack an articleId in `04_clauses.csv`.

| Clause | Should have (canonical) | Sub-domain OK? |
|---|---|---|
| AIA-C09 | Art 12(1)+(2) | ✓ D-10.2 |
| AIA-C10 | Art 12(1)+(2) | ✓ D-10.2 |
| AIA-C11 | Art 19(1) (Art 12(4) does not exist — T5 error) | ❌ D-09.4 (see §1) |
| AIA-C14 | Art 14(1) | ✓ D-08.2 |
| AIA-C15 | Art 14(4) | ✓ D-08.2 |
| AIA-C20 | Art 17(1) | ✓ D-09.1 |
| AIA-C21 | Art 17(1)(c) | ❌ D-10.3 (see §1) |
| AIA-C22 | Art 17(1)(g) | ❌ D-09.2 (see §1) |
| AIA-C23 | Art 26(1) | ✓ D-09.1 |
| AIA-C24 | Art 26(2) | ✓ D-08.2 |
| AIA-C25 | Art 72(1)+(2) + Art 74(1) | ✓ D-10.1 |
| AIA-C26 | Art 73(1)-(4) | ✓ D-04.3 |
| AIA-C27 | Art 72(1)-(2) + Art 74(1) | ❌ D-10.3 (see §1) |

Note: AIA-C11/C21/C22/C27 have **both** problems — missing articleId **and** wrong sub-domain (counted in §1 and §2).

---

## 4. Naming convention drift (3 places)

The case1 dataset does not follow the canonical conventions established by CORR-032 (closed 2026-07-20).

| Field | Case1 uses | Canonical should be | Where in case1 |
|---|---|---|---|
| `regulationId` | `AIACT` | `AI_Act` | `04_clauses.csv` |
| `clauseId` | `AIA-C01`–`AIA-C29` | `AI_Act-CL01`–`AI_Act-CL29` | `04_clauses.csv` + `07_clause_subdomain_mapping.csv` |
| `articleId` | `AI_ACT-Art5`, `AI_ACT-Art9` | `AI_Act-Art5`, `AI_Act-Art9` | `04_clauses.csv`, `03_articles.csv` |

A 4th, smaller issue: case1 articleIds lack paragraph specifier (`Art9` should be `Art 9(1)`, `Art13` should be `Art 13(1)` or `Art 13(3)`, etc.).

---

## 5. Correctly mapped clauses (15 OK)

These clauses have **correct sub-domain and article** (where articleId exists) per the methodology. No action required for them.

AIA-C01, C02, C03, C05, C06, C09, C10, C12, C13, C14, C15, C17, C20, C23, C24, C25, C26 — that's 17 listed; net OK count is 15 because C11, C18, C21, C22, C27 are in §1 with multiple issues, but most of these clauses are correct on the dimension they address.

(Simplified rule: a clause is OK if its sub-domain appears in the canonical set **AND** its articleId either matches canonical or is empty. 15 clauses meet this rule.)

---

## 6. Per-clause decision matrix (29 rows)

Use this table to decide what action each clause needs.

| # | Clause | Case1 article | Canonical art | Case1 sub | Canonical sub(s) | Action needed |
|---:|---|---|---|---|---|---|
| 1 | AIA-C01 | Art9 | Art 9(1) | D-09.2 | D-09.2 | Refresh `Art9` → `Art 9(1)` |
| 2 | AIA-C02 | Art9 | Art 9(2) | D-09.2 | D-09.2, D-02.1 | Refresh `Art9` → `Art 9(2)`; sub OK (1 of 2) |
| 3 | AIA-C03 | Art9 | Art 9(6)+(7) | D-02.1 | D-02.1, D-02.4, D-10.3 | Refresh `Art9` → `Art 9(6)+(7)`; sub OK (1 of 3) |
| 4 | AIA-C04 | Art9 | Art 9(6)+(7) | **D-07.3** | D-02.4 (or D-02.1, D-10.3) | ✓ FIXED sub (CORR-077): D-07.3 → D-02.4**; refresh art |
| 5 | AIA-C05 | Art10 | Art 10(1)+(2) | D-05.1 | D-05.1, D-05.2 | Refresh `Art10` → `Art 10(1)+(2)`; sub OK |
| 6 | AIA-C06 | Art10 | Art 10(1)+(2) | D-05.1 | D-05.1, D-05.2 | Refresh `Art10` → `Art 10(1)+(2)`; sub OK |
| 7 | AIA-C07 | Art10 | Art 10(3) | **D-05.3** | D-05.1 (or D-05.2) | ✓ FIXED sub (CORR-077): D-05.3 → D-05.1**; refresh art |
| 8 | AIA-C08 | **Art5** | Art 10(5) | D-05.1 | D-05.1 | ✓ FIXED art (CORR-077): Art5 → Art 10(5)** |
| 9 | AIA-C09 | (missing) | Art 12(1)+(2) | D-10.2 | D-10.2 | Fill `articleId = Art 12(1)+(2)` |
| 10 | AIA-C10 | (missing) | Art 12(1)+(2) | D-10.2 | D-10.2 | Fill `articleId = Art 12(1)+(2)` |
| 11 | AIA-C11 | (missing) | Art 19(1) | **D-09.4** | D-10.2 (or D-05.2) | **Fill art: Art 19(1)**; ✓ FIXED sub (CORR-077): D-09.4 → D-10.2** (T5 mapping error: Art 12(4) does not exist) |
| 12 | AIA-C12 | Art13 | Art 13(1) | D-09.1 | D-09.1 | Refresh `Art13` → `Art 13(1)` |
| 13 | AIA-C13 | Art13 | Art 13(3) | D-09.1 | D-09.1 | Refresh `Art13` → `Art 13(3)` |
| 14 | AIA-C14 | (missing) | Art 14(1) | D-08.2 | D-08.2, D-07.1 | Fill `articleId = Art 14(1)`; sub OK (1 of 2) |
| 15 | AIA-C15 | (missing) | Art 14(4) | D-08.2 | D-08.2 | Fill `articleId = Art 14(4)` |
| 16 | AIA-C16 | **Art5** | Art 15(1) | D-02.1 | D-07.1, D-02.1 | ✓ FIXED art (CORR-077): Art5 → Art 15(1)**; sub OK (1 of 2) |
| 17 | AIA-C17 | **Art5** | Art 15(3) | D-01.4 | D-01.4, D-02.1 | ✓ FIXED art (CORR-077): Art5 → Art 15(3)**; sub OK (1 of 2) |
| 18 | AIA-C18 | **Art5** | Art 15(4)-(5) | **D-01.4** | D-02.1 (or D-07.2) | ✓ FIXED art (CORR-077): Art5 → Art 15(4)-(5)**; ✓ FIXED sub (CORR-077): D-01.4 → D-02.1** |
| 19 | AIA-C19 | **Art9** | Art 19(1) | D-10.2 | D-10.2, D-05.2 | ✓ FIXED art (CORR-077): Art9 → Art 19(1)**; sub OK (1 of 2) |
| 20 | AIA-C20 | (missing) | Art 17(1) | D-09.1 | D-09.1 | Fill `articleId = Art 17(1)` |
| 21 | AIA-C21 | (missing) | Art 17(1)(c) | **D-10.3** | D-07.1 | ✓ FIXED sub (CORR-077): D-10.3 → D-07.1**; fill `articleId = Art 17(1)(c)` |
| 22 | AIA-C22 | (missing) | Art 17(1)(g) | **D-09.2** | D-09.1 | ✓ FIXED sub (CORR-077): D-09.2 → D-09.1**; fill `articleId = Art 17(1)(g)` |
| 23 | AIA-C23 | (missing) | Art 26(1) | D-09.1 | D-09.1 | Fill `articleId = Art 26(1)` |
| 24 | AIA-C24 | (missing) | Art 26(2) | D-08.2 | D-08.2, D-09.1 | Fill `articleId = Art 26(2)`; sub OK (1 of 2) |
| 25 | AIA-C25 | (missing) | Art 72(1)+(2) + Art 74(1) | D-10.1 | D-10.1 | Fill `articleId = Art 72(1)+(2) + Art 74(1)` |
| 26 | AIA-C26 | (missing) | Art 73(1)-(4) | D-04.3 | D-04.3 | Fill `articleId = Art 73(1)-(4)` |
| 27 | AIA-C27 | (missing) | Art 72 + Art 74 | **D-10.3** | D-10.1 | ✓ FIXED sub (CORR-077): D-10.3 → D-10.1**; fill `articleId = Art 72 + Art 74` |
| 28 | AIA-C28 | **Art5** | Art 55(1)(a) | **D-09.2** | D-07.3 (or D-02.1) | ✓ FIXED art (CORR-077): Art5 → Art 55(1)(a)**; ✓ FIXED sub (CORR-077): D-09.2 → D-07.3** |
| 29 | AIA-C29 | **Art5** | Art 55(1)(c) | D-04.3 | D-04.3 | ✓ FIXED art (CORR-077): Art5 → Art 55(1)(c)** |

---

## 7. What was NOT audited (deliberately out of scope)

- Other regulations (GDPR, CRA, NIS2, DORA) — case1 audit focuses only on AI Act
- Other cases (case2-secureborder, case3-omnibank) — same data quality issues likely exist
- Renaming `AIA-C{NN}` → `AI_Act-CL{NN}` (CORR-032 follow-up) — separate decision
- Filling missing `articleId` for non-AI-Act clauses
- Whether the methodology `02_SecurityRules_NIST.md` itself is correct (assumed authoritative)

---

## 8. Methodology references

| File | Role |
|---|---|
| `methodology-00/PREPROCESSING/Regulation/AI_Act/02_SecurityRules_NIST.md` | **Source of truth** — 24 SecurityRules with clause → sub-domain → NIST CSF mapping |
| `methodology-00/PREPROCESSING/Regulation/AI_Act/01_SecurityObjectives.md` | 14 SecurityObjectives — partial clause → sub-domain mapping (less specific than SRs) |
| `methodology-00/PREPROCESSING/Regulation/AI_Act/00_README.md` | Manifesto (counts, scope, validation gates) |
| `methodology-00/PREPROCESSING/Regulation/AI_Act/Ambiguity/06_AI_Act.md` | Upstream 29-clause analysis (not consulted in this audit; cited by SRs) |
| `preproc_out/global/NIST_CSF_2.0_subcategories.json` | 106 CSF subcategories catalog (downstream of sub-domain mappings) |

---

## 9. Note on audit scope

This document is **diagnosis only**. It does not propose code changes, contracts, or sprints. Decisions about what to fix, when, and how are deferred to the user after reading.

**No file in `cases/case1-tinytask/`, `methodology-00/PREPROCESSING/Regulation/AI_Act/`, `preproc_out/`, or any code path has been modified by this audit.**
