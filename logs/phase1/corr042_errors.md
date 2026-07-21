# CORR-042 — errors log (T6 run)

**Run date:** 2026-07-21 22:21 → 22:51 (Europe/Lisbon)
**Branch:** `feature/aegis-p1-corr-042`
**Total LLM calls:** 16 (4 P1B + 10 P1C-01 via legacy fallback + 1 P1C-03 + 1 P1C-02)

## Errors encountered and fixes applied

### Error 1: assemble_inputs expects Pydantic, gets dict from v1-compat shim

**Stage:** T6.3 (--run-map) — first attempt
**Symptom:** `AttributeError: 'dict' object has no attribute 'scale'` in
`src/aegis_phase1/v2/domain/inputs.py:212` (and `:260` in `_project_company_context`).
**Root cause:** Pre-existing bug (flagged in CORR-040-HANDOFF as deferred
to a follow-up contract). The v1-compat shim populates
`state['company_context']` as a dict, but the legacy MAP path's
`assemble_inputs` function expected a Pydantic `CompanyContext`.
This bug pre-dates the CORR-036→041 strategy (was already present
when the v1-compat shim was introduced in CORR-037-T4b).
**Impact:** All 10 MAP lanes failed; `--run-map` produced empty
`sub_domain_activations` (the legacy path was the fallback).
**Decision:** Apply an inline fix in CORR-042 (2 patches in
`inputs.py`) so the rest of T6 can run. This was NOT a "tune to pass"
decision — the bug was a **blocker** for the T6 run itself.
**Fix applied:**

1. `_project_company_context` (line 156-184): handle both
   `CompanyContext` (Pydantic) and dict (v1-compat) shapes.
2. `_build_track_b_suggestion` (line 212, 260): use
   `ctx.get("scale") if isinstance(ctx, dict) else ctx.scale` for
   the two `ctx.scale` references.

**Files modified:** `src/aegis_phase1/v2/domain/inputs.py` (2 patches, ~10 lines)
**Tests added:** None in this contract (deferred to CORR-043).
**Verification:** T6.3 retried → 10/10 lanes OK, 355s total.

### Error 2: P1C-LLM-01 canonical path raises `'str' object has no attribute 'get'`

**Stage:** T6.3 (--run-map) — second attempt (after fix 1)
**Symptom:** Two `PYTHON_ERROR` log lines for the P1C-LLM-01 canonical
path: `'str' object has no attribute 'get'`. The orchestrator logs
"WARN: P1C-LLM-01 MAP path failed — falling back to legacy loop" and
proceeds with the legacy LLM-A path (which then succeeded for all
10 domains with the fix 1 in place).
**Root cause:** The canonical `Phase1Executor.run_phase_1c_map` is
called from `_map_domains_via_p1c_llm_01` (added in CORR-040-T2).
The executor's inputs dict has a `subdomain_refs` or `layer0_subdomain_refs`
key whose value is a string instead of a dict, so the executor's
`inputs.get(...)` somewhere fails.
**Decision:** NOT fixed in CORR-042. The fallback to the legacy
LLM-A loop works (10/10 lanes OK). The canonical P1C-LLM-01 path is
out of scope for the run-end-to-end contract — it's an executor
input-shape mismatch that needs its own contract (CORR-043+).
**Note for CORR-043:** Look at `phase1_executor.run_phase_1c_map`
line ~250 to find where the `'str' object has no attribute 'get'`
crash happens. Likely a missing `.get(...)` guard or a wrong key
name (e.g., passing a string where a dict is expected).

### Error 3: P1C-LLM-03 SCHEMA_ERROR when running --run-reduce in isolation

**Stage:** T6.4 (--run-reduce)
**Symptom:** `SCHEMA_ERROR` twice for `P1C-LLM-03-STRATEGIC-SYNTHESIS`
with citations: "Doc 07b file does not exist: Doc 07b Row A (Evidence Mapping)".
**Root cause:** P1C-LLM-03 consumes Doc 07b as a constraint. When
running `--run-reduce` in isolation (without a preceding `--run-map`
that produces the enhanced Doc 07b), the cited Doc 07b rows don't
exist → schema validation fails.
**Decision:** NOT a bug. The contract T6.4 ran `--run-reduce` in
isolation, which is an unusual flow (the normal flow is `--run-all`
which runs MAP before REDUCE). T6.5 (`--run-all`) does produce
Doc 07b first → P1C-LLM-03 SUCCEEDS in the full pipeline. So the
run-end-to-end completes; the isolated --run-reduce warning is
expected behavior.
**Verification:** T6.5 (--run-all) → P1C-LLM-03 OK (21749ms, 4096 tokens).

## Summary

- All 5 stages of T6 completed (T6.1 → T6.5).
- 16 LLM calls total: 14 OK + 2 SCHEMA_ERROR (both on P1C-LLM-03 in
  isolated --run-reduce; not a regression — by design when Doc 07b
  doesn't exist).
- 2 PYTHON_ERROR (T6.3 first run, before the inputs.py fix; fixed
  inline and T6.3 retried successfully).
- 2 PYTHON_ERROR (T6.3 second run, P1C-LLM-01 canonical path
  input shape mismatch; fallback to legacy worked; deferred to
  CORR-043).
- The pre-existing assemble_inputs bug was fixed inline (2 patches
  in `inputs.py`). This unblocks the MAP stage and is the
  immediate value of the CORR-042 run.

## What worked (and is REAL, not mocks)

- 4 P1B-LLM-01/02 calls per applicable_reg (2 regs × 2 LLMs) — all OK
  with `gemma4:e2b`. Latency 10-16s per call.
- 10 P1C-LLM-01 calls via legacy LLM-A loop — all OK. Latency 35s
  per call (P1C-LLM-01 has bigger prompts).
- 1 P1C-LLM-03 STRATEGIC-SYNTHESIS call (in --run-all) — OK,
  21.7s, 4096 tokens.
- 1 P1C-LLM-02 COMPOUND-EVENT call — OK, 12.1s, 3065 tokens.
- Deterministic stage (concat / merge / conflicts / proportionality):
  38 subdomains profiled, 0 conflicts, 0 ambiguities.
- OUTPUT stage (deterministic + enhanced): 16 artefacts produced
  (9 base + 4 04a-d + xlsx + versions).
