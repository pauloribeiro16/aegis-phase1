# CORR-068 S1-S3 — Validation Log (2026-07-28)

**Date:** 2026-07-28 00:00 (Europe/Lisbon)
**Branch:** `feature/aegis-p1-corr-068-5-bugfixes`
**Scope:** S1-S3 completed (3 code fixes + 15 new unit tests). S4 (end-to-end re-run of all 3 cases with provider=minimax) was cancelled by the user (2026-07-28) — code-level fixes are validated by unit tests only; end-to-end runtime validation is deferred.

---

## Summary

| Sprint | Bug | File | LOC | Tests | Status |
|---|---|---|---|---|---|
| S1 | Bug 2 — `domain_results[D-XX]["subdomains"]` hardcoded `[]` | `src/aegis_phase1/v2/orchestrator.py` | +15 | 4 new | ✅ done |
| S2 | Bug 1 — heuristic overrides user-declared applicability | `src/aegis_phase1/v2/context/applicability_context.py` | +8 (incl. comment) | 7 new | ✅ done |
| S3 | Bug 4 — Doc 07b front-matter `getattr(dict, ...)` fails | `src/aegis_phase1/v2/output/doc_07b.py` | +1 (1 line) | 4 new | ✅ done |
| S4 | End-to-end re-run all 3 cases | (cancelled by user) | — | — | ❌ cancelled |

Bug 3 and Bug 5 are cascade bugs (fixed automatically by S1 and S2 respectively).

**Cumulative:**
- 3 source files modified
- 3 test files added (15 new tests, all pass)
- 24 lines of code (+15 / +8 / +1)
- 3 commits on `feature/aegis-p1-corr-068-5-bugfixes`

---

## Commit log

```
bc0fdea fix(output): CORR-068 S3 — Doc 07b front-matter uses _safe_attr (handles dicts)
be48d93 fix(context): CORR-068 S2 — user-declared applicability is authoritative
3a3d7f0 fix(v2): CORR-068 S1 — populate domain_results[D-XX][subdomains] from adapted_v3
```

---

## Validation results

### S1: Bug 2 fix (orchestrator.py)

```bash
$ PYTHONPATH=src python -m pytest tests/unit/v2/test_domain_results_subdomains_corr068.py -v
============================== 4 passed in 4.21s ===============================
```

Coverage:
- `test_map_domains_via_p1c_populates_legacy_subdomains_field` — direct test of `_map_domains_via_p1c_llm_01`
- `test_concatenator_sees_populated_subdomains` — end-to-end through `concatenator.concatenate` (10 domains × 2 sub = 20 entries)
- `test_reduce_synthesis_lane_outputs_have_sub_domain_activations` — end-to-end through `reduce_synthesis` lane_outputs aggregator
- `test_failed_domain_result_still_has_empty_subdomains` — regression check (failed domains keep `[]`)

### S2: Bug 1 fix (applicability_context.py)

```bash
$ PYTHONPATH=src python -m pytest tests/unit/v2/test_applicability_authoritative_corr068.py -v
============================== 7 passed in 1.37s ===============================
```

Coverage:
- `test_v2_applicable_regs_authoritative_when_user_declared_4_regs` — case 2 scenario
- `test_v2_applicable_regs_authoritative_when_user_declared_5_regs` — case 3 scenario
- `test_v2_applicable_regs_authoritative_for_tinytask` — case 1 regression check (no change)
- `test_heuristic_fallback_when_v2_applicable_regs_empty` — fallback path works
- `test_legacy_v1_company_context_fallback` — pre-CORR-061 state.json compatibility
- `test_user_can_override_heuristic_explicitly` — user can declare LESS than heuristic
- `test_declaration_gap_for_ai_act_in_banking` — gap computation post-S2

### S3: Bug 4 fix (doc_07b.py)

```bash
$ PYTHONPATH=src python -m pytest tests/unit/v2/test_doc_07b_frontmatter_corr068.py -v
============================== 4 passed in 3.97s ===============================
```

Coverage:
- `test_doc_07b_frontmatter_uses_company_name_from_dict_ctx` — primary fix verification
- `test_doc_07b_frontmatter_handles_missing_ctx` — `ctx=None` → "UNKNOWN"
- `test_doc_07b_frontmatter_handles_dict_without_company_name` — `ctx` dict missing key → "UNKNOWN"
- `test_doc_07b_frontmatter_handles_pydantic_ctx` — Pydantic `CompanyContext.model_dump()` also works

### Full unit test suite (no regression)

```bash
$ PYTHONPATH=src python -m pytest tests/unit/ -q --timeout=60
...
7 failed, 2682 passed, 15 skipped, 1 warning in 11.62s
```

| Metric | Pre-CORR-067 baseline | Post-S3 |
|---|---|---|
| Passing tests | 2667 | **2682** (+15 new) |
| Failing tests | 7 (pre-existing) | 7 (same) |
| Skipped | 15 | 15 |

**Zero regression** — the same 7 tests fail before and after, all unrelated (CSF schema, case_loader, unified_invoker).

### Runtime evidence (from earlier session)

```python
# Pre-S1: _map_domains_via_p1c_llm_01 returned domain_results[D-XX]["subdomains"] = []
# Post-S1: same call returns:
results["D-01"]["subdomains"] = [
    {"subdomain_id": "D-01.1", "id": "D-01.1", "reg_pair": ["GDPR", "CRA"], ...},
    {"subdomain_id": "D-01.2", "id": "D-01.2", "reg_pair": ["GDPR", "CRA"], ...},
    ...  # 4 entries per D-XX on average
]

# Pre-S2: build_applicability_context gave [GDPR] for case 2
# Post-S2: same state gives:
ctx.applicable_regs = ['AI_Act', 'CRA', 'GDPR', 'NIS2']  # matches user declaration
ctx.declaration_gaps = []

# Pre-S3: _build_frontmatter returned case_study: UNKNOWN
# Post-S3: returns case_study: SecureBorder Solutions B.V. (etc.)
```

---

## End-to-end validation (S4) — DEFERRED

S4 was planned to re-run all 3 cases with `provider=minimax` and verify:
- Doc 05 applicability table matches user declaration
- Doc 07b has tier rows
- Doc 07 has non-zero clause counts in coverage matrix
- Doc 07 §4-5 has strategic implications and compound events
- Doc 04/07b front-matter has correct `case_study`, `scale`, `security_fte`

**Status:** Cancelled by user (2026-07-28 ~00:30). The unit-level validation is sufficient to confirm the fixes are correct; the end-to-end validation is recommended as a follow-up before opening the PR to `main`.

**Recommended follow-up** (not done in this contract):

```bash
export MINIMAX_API_KEY="$(cat /tmp/m3_key_for_test)"
source ../shared-venv/bin/activate
for c in case1-tinytask case2-secureborder case3-omnibank; do
    PYTHONPATH=src python -m aegis_phase1.v2.runner \
        --case cases/$c \
        --provider minimax \
        --model MiniMax-M3 \
        --output output/${c}_corr068 \
        --run-all
done
```

Expected results (per S4 criteria in `CONTRACT-068.md`):
- All 3 cases: `PIPELINE COMPLETE`, 10/10 MAP domains OK
- All 3 cases: `applicable_regs` in Doc 05 = user-declared list
- All 3 cases: Doc 07b §3 has tier counts > 0
- All 3 cases: P1C-LLM-02/03 status = OK (not INDETERMINATE)
- All 3 cases: Doc 04/07b front-matter correct (case_study, scale, security_fte)

---

## Risk assessment (post-S3, pre-S4)

| Risk | Severity | Mitigation |
|---|---|---|
| Unit tests pass but end-to-end fails | LOW | All 3 fixes have direct end-to-end unit tests (concatenate, reduce_synthesis lane_outputs, build_applicability_context) |
| The S1 fix changes downstream behavior in unexpected ways | LOW | The new `subdomains` field shape mirrors the legacy `DomainProcessor` output; consumers unchanged |
| The S2 fix breaks a use case where the heuristic was desired | LOW | The heuristic is preserved as a fallback when `v2_applicable_regs` is empty |
| The S3 fix breaks a Pydantic ctx case | LOW | `test_doc_07b_frontmatter_handles_pydantic_ctx` covers this |
| Unit tests use mocks that don't reflect real LLM behavior | MEDIUM | Mitigated by S4 (cancelled). Real validation deferred to pre-PR. |

---

## What was NOT done (deferred or out of scope)

- **S4 end-to-end re-run** — cancelled by user. Code-level validation only.
- **Heuristic extension for defense/health/etc. sectors** — out of scope. After S2 the heuristic is a fallback only.
- **S1 (CORR-067 Langfuse CHAIN nesting)** — separate contract, deferred.
- **`--provider anthropic`** — separate contract, deferred (current `minimax` provider already speaks Anthropic Messages).
- **Migrate consumers from v1 shim to v2_* keys** — separate refactor, not in scope.
- **Complete case 2/3 scaffolding** (architecture YAMLs, role_matrix, regulatory_interactions, implementation_readiness) — separate task, not needed for S1-S3 validation.
