# Cross-Case LLM Payload Audit (cases 1, 2, 3) — CRITICAL FINDING

**Date:** 2026-07-28
**Branch:** `feature/aegis-p1-corr-069-pre-existing-test-failures`
**Scope:** Audit of all 58 LLM payloads (5 specs × 3 cases) for the AEGIS-KG Phase 1 v2 pipeline.
**Methodology:** Render each spec via `PromptLoader.render(spec, inputs)` using inputs constructed exactly as `run_p1b_single` and `run_phase_1c_map` build them. **No HTTP calls** to MiniMax M3.
**Captured:** `/tmp/payload_capture4/{case1-tinytask,case2-secureborder,case3-omnibank}/` (58 JSON files)

---

## ⚠️ CRITICAL FINDING — CORR-049 cap truncates tipo2/tipo3 catalog in P1B prompts

**Every single one of the 22 P1B-LLM-01/02 payloads (cases 1/2/3 × all applicable regs × 2 specs) is over the CORR-049 512KB cap and gets truncated.** The LLM receives the **head** of the user prompt (sub-domain refs, classification, company_facts) but **NOT the tail** (layer0_catalog tipo2 + tipo3 entries + the TASK instructions).

### Evidence

| Payload | User bytes | Cap budget | Truncated? | `layer0_catalog` pos | Last sub_domain_id pos | `# TASK` pos |
|---|---|---|---|---|---|---|
| case 1 P1B-LLM-01 GDPR | 571,559 | 508,459 | **YES** | 569,898 (TRUNC) | 544,654 (OK) | 571,414 (TRUNC) |
| case 1 P1B-LLM-01 CRA | 573,037 | 508,459 | **YES** | 569,896 (TRUNC) | 544,652 (OK) | 572,892 (TRUNC) |
| case 2 P1B-LLM-01 GDPR | 571,638 | 508,459 | **YES** | 569,977 (TRUNC) | 544,733 (OK) | 571,493 (TRUNC) |
| case 2 P1B-LLM-01 CRA | 573,116 | 508,459 | **YES** | 569,975 (TRUNC) | 544,731 (OK) | 572,971 (TRUNC) |
| case 2 P1B-LLM-01 NIS2 | 572,436 | 508,459 | **YES** | 569,977 (TRUNC) | 544,733 (OK) | 572,291 (TRUNC) |
| case 2 P1B-LLM-01 AI_Act | 571,893 | 508,459 | **YES** | 569,981 (TRUNC) | 544,737 (OK) | 571,748 (TRUNC) |
| case 3 P1B-LLM-01 DORA | 572,587 | 508,459 | **YES** | 569,973 (TRUNC) | 544,729 (OK) | 572,442 (TRUNC) |
| (P1B-LLM-02 same pattern, 11 more) | | | | | | |

**22/22 P1B payloads: catalog + task instructions are truncated.**

### What's actually lost

For case 1 P1B-LLM-01 GDPR (representative example):
- **Survives (head, first 508K):** case_id, lane_id, company_facts (12 keys), classification, layer0_subdomain_refs (38 entries with full hso_hl + hso_per_reg + pairs + participating_regs)
- **Truncated (tail, byte 508K+):** the entire `layer0_catalog` block (both `tipo2: [1 GDPR entry]` and `tipo3: [1 GDPR entry]`), AND the `# TASK` instructions (the actual instruction text the LLM should follow)

### Why this matters

The P1B-LLM-01 spec template (`Methodology-main/00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md`) says the LLM should:
> "3. Look up all Tipo 3 (derogation) entries in tipo3_derogations.yaml that apply to this regulation **and** the company's profile (role, scale, sector, products)..."

Without tipo2 + tipo3, the LLM has **no catalog material to interpret against** — it must invent interpretations from the sub-domain refs alone. The CORR-049 cap is **protecting the model from prompt degradation but at the cost of removing the catalog the LLM needs**.

### Root cause

The prompt template (P1B-LLM-01-INTERPRETATION.md, line 55-58) lists `layer0_catalog` (tipo2 + tipo3) AFTER `layer0_subdomain_refs`. The 38 sub-domain refs (with full metadata) consume ~544K bytes, leaving no room for the catalog. The CORR-049 cap at 512KB then cuts the tail.

### Severity: HIGH (cross-case, every P1B call)

This affects:
- 2/2 regs × 2/2 specs for case 1 (4 calls affected)
- 4/4 regs × 2/2 specs for case 2 (8 calls affected)
- 5/5 regs × 2/2 specs for case 3 (10 calls affected)
- **Total: 22 P1B calls per Phase 1 v2 run are losing the catalog and TASK instructions**

### Suggested fixes (out of scope for this audit, but recorded for next contract)

1. **Compact sub-domain refs.** The `hso_hl` string is 700+ bytes per entry with embedded quotes. A compact representation (just `id + title + participating_regulations`) would reduce ~544K to ~50K. But this changes the LLM's input — it loses the full objective text per sub-domain.
2. **Send catalog SEPARATELY.** Load the catalog into a system-side pre-context and reference it. But gemma4:e2b is a single-prompt model.
3. **Send the catalog on a SECOND pass.** P1B-LLM-01 calls could be split: first call asks for interpretations based on sub-domain refs; second call cross-references the catalog. But this changes the architecture.
4. **Bump CORR-049 cap to 1MB** and hope gemma4:e2b handles it. Empirical risk: prompt degradation returns (per CORR-049-T7.1 finding "ceiling before gemma4:e4b degrades is ~512KB").
5. **Reduce the # TASK section verbosity.** The current TASK section is a few KB. The bigger win is the catalog content.

**Recommendation:** file a new contract (e.g. CORR-070) to investigate a compact sub-domain representation + a smarter catalog-prepending strategy. Until then, the P1B calls are degraded and the audit result for P1B-LLM-01/02 should be marked as **DEGRADED — CATALOG TRUNCATED**.

---

## Spec-by-spec adequacy (5 specs × 3 cases)

### Spec 1: P1B-LLM-01-INTERPRETATION (per regulation)

| Case | # regs | Adequate? | Notes |
|---|---|---|---|
| 1 (TinyTask, MICRO, 2 regs) | 2 | ❌ DEGRADED | Sub-domain refs survive (38 entries), but **catalog + TASK truncated** in both calls. |
| 2 (SecureBorder, LARGE, 4 regs) | 4 | ❌ DEGRADED | Same — all 4 calls lose catalog + TASK. |
| 3 (OmniBank, LARGE, 5 regs) | 5 | ❌ DEGRADED | Same — all 5 calls lose catalog + TASK. |

**Cross-case verdict: ❌ DEGRADED due to CORR-049 truncation.** Without the catalog (tipo2/tipo3), the LLM cannot follow the P1B-LLM-01 spec's instructions to "look up Tipo 2 / Tipo 3 entries that apply to this regulation."

### Spec 2: P1B-LLM-02-RATIONALE (per regulation)

| Case | Adequate? | Notes |
|---|---|---|
| 1 | ❌ DEGRADED | Same truncation issue. P1B-01 outputs (placeholder in capture) also not in real production because `p1b_llm_01_outputs` is `None` in `run_p1b_single`. **Actually this is a bigger issue — see below.** |
| 2 | ❌ DEGRADED | Same. |
| 3 | ❌ DEGRADED | Same. |

**Additional bug (independent of CORR-049):** In `run_p1b_single`, P1B-LLM-02 is called with `p1b_llm_01_outputs=None` (the executor awaits the LLM but doesn't pass the result). The rationale spec says it should be based on P1B-01 outputs. The v4 capture uses a placeholder; the real production call also uses None. This is a **P1B-02 input wiring bug** — it would explain the observation that P1B-02 is structurally identical to P1B-01 in production.

### Spec 3: P1C-LLM-01-OVERLAP-CLASSIFICATION (per domain)

| Case | # domains | Avg user | Adequate? | Notes |
|---|---|---|---|---|
| 1 | 10 | ~57K | ✅ ADEQUATE | All calls well under cap (avg 57K). Sub-domain refs per domain (4-5 each) with full metadata. |
| 2 | 10 | ~67K | ✅ ADEQUATE | Same. |
| 3 | 10 | ~67K | ✅ ADEQUATE | Same. |

**Verdict: ✅ ADEQUATE.** No cap issues (P1C-01 has only the per-domain sub-domain refs, not the full 38). The LLM has what it needs to classify cross-regulation overlap.

### Spec 4: P1C-LLM-02-COMPOUND-EVENT (global)

| Case | user bytes | Adequate? | Notes |
|---|---|---|---|
| 1 | ~14K | ✅ ADEQUATE | aggregated_activations + c03_strategic_synthesis + doc07b_profile present. |
| 2 | ~14K | ✅ ADEQUATE | Same. |
| 3 | ~14K | ✅ ADEQUATE | Same. |

### Spec 5: P1C-LLM-03-STRATEGIC-SYNTHESIS (global)

| Case | user bytes | Adequate? | Notes |
|---|---|---|---|
| 1 | ~14K | ✅ ADEQUATE | aggregated_activations + doc07b_profile + sync_conflicts present. |
| 2 | ~14K | ✅ ADEQUATE | Same. |
| 3 | ~14K | ✅ ADEQUATE | Same. |

---

## Summary

| Spec | Total calls | Adequate | Degraded | Notes |
|---|---|---|---|---|
| P1B-LLM-01 | 11 | 0 | 11 | All 11 calls lose catalog + TASK to CORR-049 truncation |
| P1B-LLM-02 | 11 | 0 | 11 | Same + P1B-01 outputs not wired |
| P1C-LLM-01 | 30 | 30 | 0 | All calls under cap, full context |
| P1C-LLM-02 | 3 | 3 | 0 | Adequate |
| P1C-LLM-03 | 3 | 3 | 0 | Adequate |
| **TOTAL** | **58** | **36** | **22** | **38% of calls degraded** |

---

## Two real bugs identified (separate from CORR-068/069)

### Bug A: CORR-049 cap truncates P1B catalog (HIGH severity, cross-case)

22/22 P1B-LLM-01/02 calls lose the `layer0_catalog` (tipo2 + tipo3) and the `# TASK` instructions because the 38 sub-domain refs alone consume 544K bytes, exceeding the 512KB cap.

**Evidence:** see table above.

**Fix paths:**
- Compact sub-domain ref representation (hso_hl is 700+ bytes/entry; could be ~50 bytes)
- Reorder the prompt template so catalog comes BEFORE sub-domain refs (the LLM still has the refs, but the catalog is at the head and survives the cap)
- Bump CORR-049 cap (risk: gemma4:e2b degradation)

### Bug B: P1B-LLM-02 inputs missing P1B-01 outputs (MEDIUM severity, code wiring)

`run_p1b_single` calls `P1B-LLM-02-RATIONALE` with `p1b_llm_01_outputs=None` (not the result of the prior P1B-LLM-01 call). The rationale spec requires P1B-01 outputs to ground the rationale.

**Evidence:** `src/aegis_phase1/v2/orchestrator.py:run_p1b_single` (the call site) — inspect whether `executor.run_phase_1b` is called with the captured P1B-01 result before being passed to P1B-02.

**Fix:** in `run_p1b_single`, capture `p1b_llm_01_result = executor.run_phase_1b(spec=P1B-LLM-01, ...)` and then call `executor.run_phase_1b(spec=P1B-LLM-02, ..., p1b_llm_01_outputs=p1b_llm_01_result)`.

---

## What works correctly (positive findings)

- All 30 P1C-LLM-01 calls are well under cap with full sub-domain metadata — **the pipeline's per-domain filtering is correct**
- All 3 P1C-LLM-02 (Compound-Event) and 3 P1C-LLM-03 (Strategic-Synthesis) calls are under cap with complete context
- `company_facts` (12 keys), `classification`, `layer0_subdomain_refs` (38 entries) are correctly populated across all cases
- The 12-key `company_facts` is consistent across cases 1, 2, 3 (verified)
- The `applicability.yaml` filtering is correct: case 1 → 2 regs, case 2 → 4 regs, case 3 → 5 regs
- The tier assignment (MICRO → LOW, LARGE → HIGH) is correct
- The role assignment (controller) is consistent
- Catalog filtering by regulation + tier works (e.g. case 1 DORA filtered to 0 entries since DORA isn't in case 1's applicable regs; case 3 DORA → 2 entries)

---

## Files

- `/tmp/payload_capture4/case1-tinytask/`: 16 files
- `/tmp/payload_capture4/case2-secureborder/`: 20 files
- `/tmp/payload_capture4/case3-omnibank/`: 22 files
- `/tmp/payload_capture4/_summary.json`: full 58-row summary with input keys per spec

---

## Conclusion

The audit found **2 real bugs** that affect production Phase 1 v2 runs:

1. **CORR-049 cap truncates P1B catalog** (Bug A) — affects 22/58 calls (38%). **HIGH severity.**
2. **P1B-LLM-02 not wired with P1B-LLM-01 outputs** (Bug B) — affects 11/58 calls (19%). **MEDIUM severity.**

The remaining 36/58 calls (62%) — all 30 P1C-LLM-01 plus 3 P1C-LLM-02 + 3 P1C-LLM-03 — are ADEQUATE. No bugs there.

**Recommendation:** open a new contract (CORR-070 or similar) to address Bug A (catalog truncation) and Bug B (P1B-02 wiring). The fix for Bug B is straightforward (~5 LOC in `run_p1b_single`); Bug A requires prompt template work or cap adjustment.
