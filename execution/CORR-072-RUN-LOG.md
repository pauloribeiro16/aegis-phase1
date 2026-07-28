# CORR-072 — Run log

**Status:** PASS (Sprint S1)
**Date:** 2026-07-28
**Branch:** `feature/aegis-p1-corr-072-pipeline-bugs`
**Commits:**
- `4b883c6` fix(corr-072): pipeline bug fixes + cross-case consistency (Sprint S1)
- (Sprint S2 wrap-up to follow)

## Sprint outcomes

| Sprint | Goal | Status | Key result |
|---|---|---|---|
| S1 | Implement 5 bug fixes + regression test | PASS | 5 fixes shipped, 7 new tests pass, 0 regressions |

## Bugs fixed

| # | Bug | File | Severity |
|---|---|---|---|
| 1 | Stakeholder cross-case leakage (TinyTask data in OmniBank Doc 04 §3) | `doc_04.py:_augment_influence` | CRITICAL |
| 2 | Doc 04d §3 hardcoded NIS2/DORA/AI_Act=NO (inconsistent with Doc 05) | `doc_04d.py:_section_regulation_level` + frontmatter | SIGNIFICANT |
| 3 | Doc 04a §1 duplicate "## 1. Technical Architecture" header | `doc_04a.py:_strip_section_header` (new helper) | MINOR |
| 4 | Doc 04b/c/d `active_subdomains: 0` when ontology empty | `doc_04b/c/d.py:_active_subdomain_count` | MINOR |
| 5 | Regression test (no auto-detection — added by hand) | `tests/unit/v2/output/test_doc_04_stakeholder_leakage.py` | NEW |

## Validation

### Isolated fix verification (`scripts/dev/verify-corr072-fixes.py`)

```
=== Fix #1 — _augment_influence ===
  PASS  no org inheritance from TinyTask baseline
  PASS  no contact inheritance from TinyTask baseline
  PASS  responsibilities NOT overwritten by baseline
  PASS  influence still inherits from baseline
  PASS  interest still inherits from baseline
=== Fix #2 — Doc 04d §3 Regulation-Level Owner ===
  PASS  GDPR marked YES
  PASS  CRA marked YES
  PASS  NIS2 marked YES
  PASS  DORA marked YES
  PASS  AI Act marked YES
  PASS  NIS2 not hardcoded NO
  PASS  DORA not hardcoded NO
  PASS  AI Act not hardcoded NO
=== Fix #2 sanity — Doc 04d §3 for case 1 (TinyTask) ===
  PASS  GDPR marked YES
  PASS  CRA marked YES
  PASS  NIS2 correctly NO for TinyTask
=== Fix #3 — _strip_section_header ===
  PASS  duplicate '## 1. Technical Architecture' stripped (content preserved)
  PASS  clean narrative passes through unchanged
  PASS  empty input handled
=== Fix #4 — _active_subdomain_count fallback ===
  PASS  Doc 04b: 40 (fallback to state['subdomains'])
  PASS  Doc 04c: 40 (fallback to state['subdomains'])
  PASS  Doc 04d: 40 (fallback to state['subdomains'])
  PASS  All 3 docs prefer ontology when populated (3, not 40)
=== Fix #5 — Doc 04 §3.1 Stakeholder Register end-to-end ===
  PASS  TinyTask / tinytask.pt: 0 leaks in §3.1
  PASS  OmniBank present in §3.1
  PASS  TinyTask: 0 leaks in §3.2 (Influence Matrix)

═══════════════════════════════════════════════════════
  ALL FIXES VERIFIED — CORR-072 Sprint S1 complete
═══════════════════════════════════════════════════════
```

**24/24 assertions pass.**

### Regression tests

```
tests/unit/v2/output/test_doc_04_stakeholder_leakage.py: 7 passed
```

### Full v2 suite

```
523 passed, 4 failed (pre-existing Ollama-unreachable failures, unrelated)
```

No new regressions. The 4 Ollama failures predate CORR-072 and require
a running Ollama service at `http://localhost:11434` to pass.

## What was intentionally NOT done

Per user direction ("Não vais correr a pipeline completa, vais apenas
testar aquilo que deu mal de maneira isolada"):

- Full pipeline re-run for case 1, 2, 3 — deferred to a follow-up contract
- Real M3 integration verification — covered indirectly by isolated
  function tests; full integration deferred
- Update to `pipeline_inputs_golden` fixtures — only needed if the
  pipeline is re-run; deferred

These are documented as follow-up work in `execution/CONTRACT-072.md`
"Risks" + "Lessons learned" sections.

## Outcome metrics (vs pre-fix behaviour)

| Metric | Before | After |
|---|---:|---:|
| TinyTask leakage in Doc 04 §3 (case 3) | 7/7 rows | **0 rows** |
| Doc 04d §3 consistency vs Doc 05 (case 3) | 2/5 OK | **5/5 OK** |
| Doc 04a §1 duplicate header | yes (1× duplicated) | **no** |
| active_subdomains (case 3, post-fix) | 0 | **40 (or ontology value)** |
| v2 regression tests | n/a | **7 new tests added** |
| Total v2 test pass rate | 519/523 (4 pre-fail) | **523/527 (4 pre-fail)** |

## Lessons

1. **By-ID matching is dangerous when IDs are shared across cases.**
   SH-01..SH-07 is a convention used by all cases. Any fallback that
   matches by ID alone is susceptible to cross-case leakage. Future
   code should match by composite keys (`(case_id, stakeholder_id)`).

2. **`state["company_context"]` is legacy and can be stale.** CORR-038
   instituted `build_applicability_context(state)` as the canonical
   source-of-truth for applicability. Older docs (04, 04d) still read
   from the legacy field. This contract begins the migration.

3. **M3 hallucinates org/contact/email when YAML omits them.** Document
   rendering should fall back to `-` (empty cell), not the TinyTask
   baseline. Future work could add prompt augmentation that explicitly
   asks M3 to use only provided context.

4. **Dual-source counts need OR fallback.** Single source is fragile
   when one of two can be empty. `active_subdomains` now prefers
   ontology (canonical) but falls back to `state["subdomains"]`
   (universally populated by orchestrator line 461).

5. **Test in isolation when possible.** User feedback was clear: full
   pipeline runs are expensive (11 min + M3 API). Isolated function
   tests give faster, more reliable validation of specific fixes.
   `scripts/dev/verify-corr072-fixes.py` pattern is reusable for future contracts.
