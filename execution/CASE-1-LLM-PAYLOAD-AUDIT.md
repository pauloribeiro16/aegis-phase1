# Case 1 (TinyTask) — LLM Payload Audit

**Date:** 2026-07-28
**Branch:** `feature/aegis-p1-corr-069-pre-existing-test-failures`
**Case:** TinyTask (MICRO SaaS, 2 applicable regs: GDPR + CRA)
**Methodology:** Render each spec via `PromptLoader.render(spec, inputs)` using inputs constructed exactly as `run_p1b_single` and `run_phase_1c_map` build them. **No HTTP calls** to MiniMax M3.
**Captured:** `/tmp/payload_capture4/case1-tinytask/` (16 JSON files = 2 + 2 + 10 + 1 + 1)

---

## Executive summary

| Spec | Calls | Adequate | Degraded | Notes |
|---|---|---|---|---|
| P1B-LLM-01 | 2 (GDPR, CRA) | 0 | 2 | ❌ Both calls **truncated** by CORR-049 cap; catalog + TASK lost |
| P1B-LLM-02 | 2 (GDPR, CRA) | 0 | 2 | ❌ Same + P1B-01 outputs **not wired** in `phase1_executor.run_phase_1b` (Bug B confirmed) |
| P1C-LLM-01 | 10 (D-01 to D-10) | 10 | 0 | ✅ All calls well under cap with full sub-domain metadata |
| P1C-LLM-02 | 1 (global) | 1 | 0 | ✅ All context present (40 aggregations + 40 sub-domains + c03_synthesis) |
| P1C-LLM-03 | 1 (global) | 1 | 0 | ✅ All context present |
| **TOTAL** | **16** | **12 (75%)** | **4 (25%)** | |

**12/16 calls (75%) are ADEQUATE.** The 4 degraded calls are all P1B-LLM-01/02 (2 each) — both bugs (A and B) affect them.

---

## Bug A confirmed in case 1: CORR-049 cap truncates P1B catalog

### Evidence (per P1B call)

| Call | User bytes | Cap budget | Truncated? | `layer0_catalog` pos | Last sub_domain_id | `# TASK` pos |
|---|---|---|---|---|---|---|
| P1B-01 GDPR | 571,559 | 508,459 | **YES** | 569,898 (TRUNC) | 544,654 (OK) | 571,414 (TRUNC) |
| P1B-01 CRA | 573,037 | 508,459 | **YES** | 569,896 (TRUNC) | 544,652 (OK) | 572,892 (TRUNC) |
| P1B-02 GDPR | 571,629 | 509,170 | **YES** | 569,893 (TRUNC) | 544,649 (OK) | 571,489 (TRUNC) |
| P1B-02 CRA | 573,107 | 509,170 | **YES** | 569,891 (TRUNC) | 544,647 (OK) | 572,967 (TRUNC) |

**4/4 P1B calls: catalog + task instructions are truncated.**

### What gets cut for case 1 (the catalog entries that get lost)

For **case 1 GDPR** (catalog tail truncated at byte 508K, catalog starts at byte 569K):
- **tipo2 (1 entry, LOST):** `TIPO2-GDPR-RTS-DEADLINES` — "GDPR Art. 33(1) 72h breach notification deadline; Art. 34(1) high-risk threshold." Activation predicate: `company_facts.sector in ['health', 'energy', 'transport', 'digital_infrastructure']`
- **tipo3 (1 entry, LOST):** `TIPO3-GDPR-HOUSEHOLD` — "GDPR Art. 2(2)(c) — processing by a natural person in the course of a purely personal or household activity is excluded from GDPR scope." Effect: "GDPR does not apply"

For **case 1 CRA** (catalog tail truncated, catalog starts at byte 569K):
- **tipo2 (2 entries, LOST):** `TIPO2-CRA-ART14-DUAL-FLOW` (ENISA 24h report), `TIPO2-CRA-ART15-VOLUNTARY` (voluntary vulnerability report)
- **tipo3 (2 entries, LOST):** `TIPO3-CRA-NON-PLACED` (CRA does not apply), `TIPO3-CRA-OPEN-SOURCE` (CRA does not apply for non-commercial OSS)

### Why case 1 is the most affected

**Case 1 (TinyTask MICRO) is exactly the scenario where tipo3 derogations matter most.** A micro-business is the textbook case for:
- "household activity" check (GDPR TIPO3-HOUSEHOLD)
- "non-commercial OSS" exclusion (CRA TIPO3-OPEN-SOURCE)
- "not placing on EU market" exclusion (CRA TIPO3-NON-PLACED)

The LLM is **supposed** to evaluate these predicates and decide whether the regulation even applies. Without the catalog, it has no material to make that decision — the P1B-01 spec explicitly says:
> "3. Look up all Tipo 3 (derogation) entries in tipo3_derogations.yaml that apply to this regulation **and** the company's profile (role, scale, sector, products)..."

### Severity: HIGH (case 1 is the worst case)

Case 1 is the most data-loss case because:
1. It has **2 regs** (smaller, not larger) — but the truncation is independent of # regs
2. The truncation happens because the 38 sub-domain refs alone are too big
3. The lost material (tipo2 + tipo3) is **exactly the material the LLM needs** to interpret regulations against a MICRO company profile

---

## Bug B confirmed in case 1: P1B-01 outputs not wired to P1B-02

### Evidence

**Code path in production (`src/aegis_phase1/prompts_v2/phase1_executor.py:195-217`):**

```python
for reg in applicable_regs:
    out_01 = self.invoker.invoke(SPEC_INTERPRETATION, {...})   # P1B-01
    out_02 = self.invoker.invoke(SPEC_RATIONALE, {
        **inputs,           # <-- no out_01 here!
        "case_id": case_id,
        "lane_id": reg,
        "applicable_regs": [reg],
    })
```

**P1B-01 output (`out_01`) is captured but never passed to P1B-02 as `p1b_llm_01_outputs`.**

### Impact

The rationale spec (P1B-LLM-02-RATIONALE.md) says:
> "Write a rationale **for each Tipo 2 interpretation and Tipo 3 derogation identified by P1B-LLM-01** for this regulation. **Ground each rationale in the prior P1B-01 interpretation output**..."

Without `p1b_llm_01_outputs`, the LLM must re-derive the interpretations from scratch. This means:
- P1B-01 and P1B-02 do **redundant work** (P1B-02 re-interprets what P1B-01 already decided)
- The rationale has no anchor to the interpretation stage
- The output is effectively a **second interpretation pass** masquerading as a rationale

### Fix (5 LOC, in `phase1_executor.py:207-217`)

```python
out_02 = self.invoker.invoke(
    SPEC_RATIONALE,
    {
        **inputs,
        "case_id": case_id,
        "lane_id": reg,
        "applicable_regs": [reg],
        "p1b_llm_01_outputs": out_01.get("parsed_output", {}),  # NEW
    },
    config=config,
    state=state,
)
```

This is **straightforward and high-value**.

---

## Spec-by-spec (case 1)

### Spec 1: P1B-LLM-01-INTERPRETATION (2 calls)

| Reg | User bytes | Trunc | layer0_catalog | tipo2 count | tipo3 count |
|---|---|---|---|---|---|
| GDPR | 571,559 | **YES** | TRUNC | 1 (LOST) | 1 (LOST) |
| CRA | 573,037 | **YES** | TRUNC | 2 (LOST) | 2 (LOST) |

**Verdict: ❌ DEGRADED (Bug A).** Both calls lose the catalog the LLM is supposed to consult.

### Spec 2: P1B-LLM-02-RATIONALE (2 calls)

| Reg | User bytes | Trunc | p1b_llm_01_outputs |
|---|---|---|---|
| GDPR | 571,629 | **YES** | placeholder (would be None in real production) |
| CRA | 573,107 | **YES** | placeholder (would be None in real production) |

**Verdict: ❌ DEGRADED (Bug A + Bug B).** Both bugs affect this spec.

### Spec 3: P1C-LLM-01-OVERLAP-CLASSIFICATION (10 calls)

| Domain | User bytes | Trunc | Sub-domain refs |
|---|---|---|---|
| D-01 | 30,127 | no | 4 |
| D-02 | 27,974 | no | 4 |
| D-03 | 55,665 | no | 4 |
| D-04 | 74,505 | no | 4 |
| D-05 | 40,035 | no | 4 |
| D-06 | 51,058 | no | 4 |
| D-07 | 69,443 | no | 4 |
| D-08 | 64,233 | no | 3 |
| D-09 | 97,224 | no | 4 |
| D-10 | 67,342 | no | 3 |

**Verdict: ✅ ADEQUATE.** All calls well under cap. Sub-domain refs (3-4 per domain) with full metadata. No bugs.

### Spec 4: P1C-LLM-02-COMPOUND-EVENT (1 call)

- User: 14,341B
- Inputs: `aggregated_activations` (40 entries), `doc07b_profile` (40 sub-domains), `c03_strategic_synthesis` (present), `sync_conflicts` (0)
- Trunc: no

**Verdict: ✅ ADEQUATE.**

### Spec 5: P1C-LLM-03-STRATEGIC-SYNTHESIS (1 call)

- User: 14,279B
- Inputs: `aggregated_activations` (40 entries), `doc07b_profile` (40 sub-domains), `sync_conflicts` (0)
- Trunc: no

**Verdict: ✅ ADEQUATE.**

---

## What works (positive findings for case 1)

1. **`company_facts` has all 12 keys** — name, sector, jurisdiction, scale, employees, role, obligated_party, complexity_tier, data_categories, products, role_obligations, applicable_regs
2. **`classification` is correct** — role: "controller", tier: "LOW" (MICRO), basis: "Doc 04 §5"
3. **`layer0_subdomain_refs` has 38 entries** with full metadata
4. **`layer0_catalog` is correctly filtered** — 1 GDPR tipo2 + 1 GDPR tipo3, 2 CRA tipo2 + 2 CRA tipo3
5. **P1C-LLM-01 (10 calls) is fully adequate** — 27K-97K bytes each, well under cap
6. **P1C-LLM-02 and P1C-LLM-03 are fully adequate** — 14K bytes each
7. **Tier assignment works** — MICRO → LOW tier correctly inferred from company.scale

---

## What doesn't work (case 1)

1. **Bug A: CORR-049 cap truncates 100% of P1B calls (4/4)**
   - Catalog (tipo2 + tipo3) is at byte 569K, well above the 508K cap budget
   - The 4 tipo3 entries that get cut are EXACTLY the derogation patterns that matter most for a MICRO SaaS (household activity, non-placed on market, open source)

2. **Bug B: P1B-01 outputs not wired to P1B-02**
   - `phase1_executor.py:207-217` calls P1B-02 with the same inputs as P1B-01 (no `p1b_llm_01_outputs`)
   - The LLM must re-interpret from scratch

---

## Recommendation for case 1 specifically

**Case 1 is the worst case for these bugs** because the MICRO profile is exactly where tipo3 derogations matter (the "is this regulation even applicable?" question). The LLM is supposed to evaluate the tipo3 predicates against `company_facts.sector`, `company_facts.scale`, `company_facts.products` and decide if GDPR/CRA apply. Without the catalog, the LLM can only guess.

**Open CORR-070 to fix:**
- **Bug B first (easy, high value):** 5 LOC fix in `phase1_executor.py:207-217` to wire `p1b_llm_01_outputs` from P1B-01 to P1B-02
- **Bug A (harder):** either compact sub-domain refs (~50K reduction possible) or reorder the prompt template so catalog appears BEFORE sub-domain refs (the catalog is much smaller and could fit before the cap)
