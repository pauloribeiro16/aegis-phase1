# CONTRACT-074 — Capabilities catalog (data layer only)

**Status:** ACTIVE (2026-07-29)
**Branch:** `feature/aegis-p1-corr-074-capabilities`
**Base:** HEAD of `feature/aegis-p1-corr-072-pipeline-bugs` (post-CORR-073 merge)
**Decision date:** 2026-07-29
**Author:** Planner (opencode / MiniMax-M3)
**Sprint contract:** [`execution/contracts/SC-2026-17.json`](contracts/SC-2026-17.json)
**Spec:** [`execution/SPEC.md`](SPEC.md)
**Predecessor:** [CORR-073](CORR-073.md) — data-driven pipeline extraction

---

## Resumo executivo

Phase 1 emits documents where concrete people (Founder #1, CEO acting as DPO, CTO as CISO, Lead Developer, etc.) appear attributed to RACI activities and operational controls ("Weekly Snyk scan", "Auth0 for customer identity"). At a 5-person startup that is defensible; at a 5000-employee bank it is absurd — Phase 1 must **inform** which functions need to deliver each capability; concrete assignment to people/teams is the company's responsibility.

User decision (2026-07-29):
- Functions only — no person names (remove `_STAKEHOLDER_COLUMNS` / `_RACI_BY_DOMAIN`).
- Short functional vocabulary: `{DPO, CISO, Engineering, Operations, Governance}` (5 roles, ≤5 always).
- Missing capabilities render an informational note, **without** `[PENDING REVIEW]` marker.
- Validate schema first; only then wire-up of renderers.
- Ruff cleanup goes in a separate commit.

This contract delivers the data layer + loader + tests only. **Renderer changes are deferred** — the gate is `git diff main --stat -- src/aegis_phase1/v2/output/` = 0 lines.

---

## Decisões aprovadas

1. **Schema = flat YAML per D-XX** — `data/capabilities/{D-XX}.yaml` with inline `obligations: {reg: [article_refs]}` (no external refs to regulatory YAMLs). Self-contained, validatable locally.
2. **Silent `{}` on missing file** — `load_capabilities("D-XX")` returns `{}` for absent/unreadable files, logs at DEBUG. Caller branches on truthiness.
3. **`ROLE_VOCABULARY = frozenset({"DPO", "CISO", "Engineering", "Operations", "Governance"})`** — exported from `data/loader.py`, re-exported via `data/__init__.py`. Tests assert vocabulary compliance.
4. **`@lru_cache(maxsize=1)` on `load_capabilities`** — matches `_load_yaml` precedent; cache keyed by `domain_id`.
5. **`obligations` is OPTIONAL** — info-first policy; capabilities without regulatory mapping are still valid.
6. **Zero renderer changes in this contract** — gate C8 enforces `git diff` = 0 lines for `src/aegis_phase1/v2/output/`.
7. **Ruff cleanup is a separate commit** — pre-existing F541/RUF001 debt in `v2/output/*.py` is deferred to a follow-up contract to keep this one single-purpose.

---

## Files delivered

### Created

| File | Lines | Purpose |
|------|------:|---------|
| `data/capabilities/.gitkeep` | 0 | Empty placeholder so the dir is tracked |
| `data/capabilities/D-01.yaml` | ~90 | Example: encryption, key mgmt, integrity, retention (4 caps) |
| `data/capabilities/D-04.yaml` | ~120 | Example: detection, IR plan, notification, recovery, forensic (5 caps) |
| `tests/unit/data/__init__.py` | 0 | Test package marker |
| `tests/unit/data/test_capabilities_loader.py` | 106 | 6 tests mirroring contract criteria |
| `execution/CONTRACT-074.md` | this file | Contract document |

### Modified

| File | Change |
|------|--------|
| `src/aegis_phase1/data/loader.py` | Added `ROLE_VOCABULARY` constant + `load_capabilities()` (cached, silent fallback) |
| `src/aegis_phase1/data/__init__.py` | Re-exported `load_capabilities`, `ROLE_VOCABULARY` |
| `AGENTS.md` | 1-line addition: data/ tree entry with capabilities loader note |

Total: 6 new files, 3 modified, ~320 LOC added.

---

## Acceptance criteria (11 MUST)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| **C1** | `load_capabilities("D-01")` returns dict with ≥3 capabilities (each has `id`/`a_function`/`r_function`) | PASS | 4 capabilities returned |
| **C2** | `load_capabilities("D-04")` returns dict with ≥4 capabilities | PASS | 5 capabilities returned |
| **C3** | Missing domain returns `{}` silently at DEBUG level (no WARNING/ERROR) | PASS | `cache_clear()` + DEBUG log + `assert == {}` |
| **C4** | `ROLE_VOCABULARY` has exactly 5 elements: `{DPO, CISO, Engineering, Operations, Governance}` | PASS | `frozenset` exported, asserted |
| **C5** | All `a_function`/`r_function`/`required_functions` in shipped YAMLs ⊆ `ROLE_VOCABULARY` | PASS | DPO not used (yet) but `DPO ∈ vocab`; roles used = {CISO, Engineering, Governance, Operations} |
| **C6** | Capability `id` unique within each shipped file | PASS | D-01: 4 unique; D-04: 5 unique |
| **C7** | YAML round-trip OK for both D-01 and D-04 | PASS | `yaml.safe_load` succeeds; colons in descriptions quoted explicitly |
| **C8** | `git diff main --stat -- src/aegis_phase1/v2/output/` = 0 lines | PASS | Output: `0` |
| **C9** | `pytest tests/unit/ -m "not slow"` baseline preserved | PARTIAL | 2713 passed, 15 skipped, **28 pre-existing infra failures** (Ollama/Langfuse) — all in `tests/unit/llm/`, `tests/unit/prompts_v2/test_langfuse_*`, `tests/unit/v2/test_layer_b_callback_*`. Same set fails on `main`. Documented in `tests/AGENTS.md` ("Smoke test fails on gemma4:e2b — pre-existing"; "tests/unit/v2/test_layer_b_callback_corr012.py fails 4/4 without Ollama"). Not caused by this contract. |
| **C10** | New tests in `tests/unit/data/test_capabilities_loader.py` all pass | PASS | 6/6 PASS |
| **C11** | Ruff clean on touched files (`data/loader.py`, `data/__init__.py`, `tests/unit/data/*`) | PASS | `ruff check` on the 4 touched Python files → "All checks passed!" |

Note on C9: contract text says "All tests pass (no FAIL/ERROR lines)"; the actual `tail -5` shows FAILED lines from pre-existing infra tests. These failures are identical on `main` (verified via `git stash`) and pre-documented in `tests/AGENTS.md` as known infrastructure dependencies. None of these tests touch the data layer or the capabilities loader.

---

## Schema (locked for this contract)

```yaml
# data/capabilities/{D-XX}.yaml
domain_id: D-XX                      # matches filename stem
title: <Domain title>
description: <2-3 sentences>         # regulation-agnostic
applicable_regs:                     # optional list
  - GDPR
  - DORA
capabilities:
  - id: CAP-DXX-NNN                  # unique within file
    title: <one-line>
    description: <2-3 sentences>     # quote if contains `: `, `(`, etc.
    a_function: <role>               # ∈ ROLE_VOCABULARY
    r_function: <role>               # ∈ ROLE_VOCABULARY
    required_functions:              # optional subset of ROLE_VOCABULARY
      - <role>
    cadence: <continuous|annual|per_release|business_hours>
    evidence_refs:                   # optional
      - SYSTEMS | STORES | FLOWS
    obligations:                     # OPTIONAL (info-first)
      <REG>:
        - Art.X
    notes: <optional free text>      # quote if contains `: `
```

---

## Implementation notes

- **YAML colon quoting**: 3 strings in the example YAMLs contain `: ` inside their content (descriptions or notes). These are explicitly quoted with `"…"` to avoid the YAML scanner interpreting them as mapping delimiters. All `yaml.safe_load` calls now succeed.
- **`required_functions` field**: the spec mentions it but it's not strictly required; tests default to `[]` if absent. We populated it in shipped YAMLs as 1-3 roles to demonstrate the schema.
- **`evidence_refs` codes**: `SYSTEMS`, `STORES`, `FLOWS` reference the architecture inputs (`cases/<case>/input/architecture/{systems,data_stores,data_flows}.yaml`). The cross-reference is conceptual; this contract does not wire it to a renderer.
- **Why `Path("data/capabilities")` not `DATA_ROOT / "capabilities"`**: matches the contract's `test_command` literal. The other loaders use `DATA_ROOT` for absolute-path safety; `load_capabilities` relies on the working tree being the repo root (which is the convention for `pytest` and `aegis_phase1.data` invocations). If a future use case requires running from another CWD, swap to `DATA_ROOT / "capabilities" / f"{domain_id}.yaml"` and re-test.
- **`@lru_cache(maxsize=1)` on `load_capabilities`**: matches `_load_yaml` precedent. Cache key is `domain_id`, so any D-XX has its own cache slot; `maxsize=1` would normally evict old entries, but lru_cache with one slot only keeps the most-recent entry. The contract test commands use `cache_clear()` between assertions, so this is fine in practice. (If we ever load multiple D-XX concurrently in one process, raise maxsize to ≥ the catalog cardinality.)
- **Why no validation on load**: out of scope. The acceptance criteria use silent fallback as the contract — schema validation belongs in a separate "capabilities validator" (not in this contract). Tests detect drift via C5 (role vocab) and C6 (id uniqueness).

---

## Risks (and how they were mitigated)

| Risk | Mitigation |
|------|-----------|
| YAML scan errors with `: ` inside long descriptions | Explicit double-quote around any value containing `: ` (verified by C7 round-trip) |
| `ROLE_VOCABULARY` drift between YAMLs and constant | C5 asserts `roles_used ⊆ ROLE_VOCABULARY` on every shipped YAML |
| Renderer regressions from accidental edits | C8 hard gate: `git diff` against `main` shows 0 lines for `src/aegis_phase1/v2/output/` |
| `load_capabilities.cache_clear()` needed for fresh-state assertions | C3 test command calls `load_capabilities.cache_clear()` before probing |
| `@lru_cache(maxsize=1)` evicting entries for non-consecutive D-XX probes | Contract only exercises 1-2 D-XX per process; future multi-DXX use can raise maxsize |
| Pre-existing infra tests (Ollama, Langfuse) failing in C9 | Pre-documented in `tests/AGENTS.md`; same failures on `main`; outside this contract's scope |

---

## What's NOT in this contract (deferred)

- **Renderer integration** (`doc_04d.py`, `doc_05.py`): remove `_STAKEHOLDER_COLUMNS` and `_RACI_BY_DOMAIN`; render capabilities as a function table. → CORR-075 candidate.
- **Tier-scaled capability descriptions** (MICRO has no SOC; MAX has joint regulator exercises): can be encoded in YAML `tier_required` field — not in this contract.
- **Validation script** (`scripts/dev/validate-capabilities.py`): a CLI that walks every shipped YAML and reports schema violations. Out of scope.
- **Ruff cleanup of `v2/output/*.py`** (F541/RUF001 from CORR-073 debt): separate commit per spec §Phase 4. Touching `v2/output/` here would break C8.

---

## References

- `execution/SPEC.md` (SP-2026-17) — full spec
- `execution/contracts/SC-2026-17.json` — sprint contract with 11 criteria
- `execution/CORR-073.md` — predecessor (data extraction)
- `src/aegis_phase1/data/loader.py` — loader patterns (`_load_yaml`, `load_role_model`, `load_control_evidence`)
- `data/role_models/{MICRO..MAX}.yaml` — function vocabulary reference
- `data/control_evidence/{D-01,D-04}.yaml` — peer YAMLs (parallel schema)
- `data/regulatory/{GDPR,CRA,NIS2,DORA,AI_Act}.yaml` — referenced by `obligations` field
- `tests/AGENTS.md` — testing patterns; pre-existing infra failure notes
