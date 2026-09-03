# CORR-071 — Run log

**Status:** PASS (3/3 sprints)
**Date:** 2026-07-28
**Branch:** `feature/aegis-p1-corr-069-pre-existing-test-failures`
**Commits:**
- `4d3dd20` S1 — per-reg filter in `run_phase_1b`
- `9d87660` S2 — remove BUG-A reorder + regen goldens
- `0e29041` S3 — hard semantic guard

## Sprint outcomes

| Sprint | Goal | Status | Key result |
|---|---|---|---|
| S1 | Add per-reg filter in `run_phase_1b` | PASS | 38 → 12-27 refs/lane; payload 575K → 116-190K |
| S2 | Remove BUG-A reorder + regen goldens | PASS | Reorder gone; 58 goldens regenerated; schema known_issues updated |
| S3 | Hard semantic guard | PASS | 1 test (`TestRunPhase1BPerRegFilter`); schema docs only |

## Pre-existing issues NOT in scope (carried over)

- `test_smoke_p1b_llm_01_gdpr` fails on `gemma4:e4b` (env model mismatch — contract expects `e2b`). Reproducible on baseline before S1.
- Pre-existing ruff errors at `orchestrator.py:121, 132, 518, 1631` — unrelated to CORR-071.
- Pre-existing `ruff format --check` issues at `test_phase1_executor.py:12, 704-707` — unrelated.
- Size budget test constant (`> 524288`) is now higher than actual max size (~190K post-S2). Schema declares `user_prompt_max_bytes: 200000` but test uses the old 524288. Informational; soft-warn, no assert. Follow-up alignment is non-blocking.

## Outcome metrics

| Metric | Before | After |
|---|---|---|
| P1B-01/02 user prompt size (case1 GDPR) | 575K | 167K (−71%) |
| P1B-01/02 user prompt size (case3 AI_Act) | 575K | 116K (−80%) |
| P1B-01/02 user prompt size (max across cases) | 575K | 191K (−67%) |
| BUG-A truncation in user prompt | Yes (catalog + # TASK cut) | No |
| Refs per P1B lane | 38 (all) | 12-27 (filtered) |
| Reorder workaround in orchestrator | Yes (lines 1704-1712) | No (removed) |
| Regression guard for filter | None | `TestRunPhase1BPerRegFilter` (hard assert) |

## Lessons

1. **Pattern reuse is high-leverage.** CORR-045's per-lane filter was a one-shot pattern that applied cleanly to per-regulation. ~15 LOC total for S1.
2. **Two-fixes anti-pattern avoided.** Removing the CORR-070 reorder workaround in the same contract prevents "which fix is canonical?" ambiguity later.
3. **Hard semantic guard > rigid max_count.** The user's guidance "não é para colocar coisa à toa" led to one sharp invariant test, not an arbitrary threshold. The test catches the actual regression (filter removed/loosened) with 7 distinct invariant violations.
4. **Schema documentation vs enforcement.** `per_reg_filter_required: true` is doc-only; runtime enforcement is in the executor + the new test. This keeps structural tests focused on key-presence while the semantic invariant lives where it belongs.
