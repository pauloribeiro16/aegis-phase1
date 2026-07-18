# AEGIS-P1-CORR-023 — Generalize MAP adaptation to D-01..D-09

**Branch:** `feature/aegis-p1-corr-023`
**Predecessor:** CORR-022 (D-10 MAP v1.3 — 9/9 gates PASS for D-10.1/.2/.3, merged via PR #27)
**Status:** APPROVED → IMPLEMENTING

---

## 1. Context

CORR-022 closed D-10 (whole domain: D-10.1/.2/.3) as proof-of-concept that
`gemma4:e2b` produces regulation-centric, OJ-anchored adapted objectives in
the v1.3 format (3 blocos × 5 campos per sub-domain). The architecture is
already domain-parameterized: `domain_id` flows end-to-end through the
orchestrator, processor, prompt builder, parser V3, and `doc_04b` renderer.

**The blocker for D-01..D-09 is content coverage**, not architecture. Two
hardcoded catalogs are empty for 7 of 10 domains, a path is hardcoded to one
machine, and three gates are D-10-specific.

### Scope cut

- **IN:** D-01, D-02, D-03, D-05, D-06, D-07, D-08, D-09 (8 domains — D-04 and
  D-10 already have populated catalogs).
- **OUT:** W1 (anchors in Adapted prose), W2 (CRDA-stats leak into HL Generic
  Original), W4 (HL Considerations under-extraction) — deferred to CORR-024+.
- **OUT:** Cases other than TinyTask (the pipeline is case-parameterized via
  `Phase1Orchestrator.load`, but no second case exists yet).

---

## 2. Diagnosis (current state, post-CORR-022)

| Layer | State for D-10 | State for D-01..D-09 |
|---|---|---|
| `domain_id` threading | ✅ parameterized | ✅ parameterized |
| Sub-domain corpus (38 `D-*.md`) | ✅ present | ✅ present |
| `filter_regs` fallback | ✅ works | ✅ works |
| `article_loader.DOMAIN_ARTICLES` | ✅ D-10 populated (also D-01, D-04 partial) | ❌ D-02/03/05/06/07/08/09 empty → §3 renders empty |
| `ambiguity_loader._DOMAIN_CLAUSE_FILTER` | ✅ D-10 populated (also D-01, D-04) | ❌ others fall through → all ~280 cards (>160 KB) |
| Filter preprocessing path | hardcoded `/home/.../Methodology-main/...` | same — portability blocker |
| Gates (G1 audit-kw, G3 GDPR∧CRA, G9 `≥3 blocks`) | ⚠️ D-10-specific | ❌ will misfire for other regs / domain themes |

---

## 3. Phases

### Phase A — De-hardcode the preprocessing path (portability)

**Files:**
- `src/aegis_phase1/v2/domain/filters/articles.py:14-16`
- `src/aegis_phase1/v2/domain/filters/ambiguities.py:14-16`

**Change:** replace the module-level `_OJ_BASE_PATH` / `_AMBIGUITY_BASE_PATH`
constants with `Path(state["preprocessing_path"])` read inside the filter
function. The orchestrator already sets this at `orchestrator.py:154`
(`self.state["preprocessing_path"] = regulatory_baseline_path`).

**Risk:** touches existing D-10 behaviour. Mitigated by Phase D regression
test and by re-running D-10 smoke in Phase E.

### Phase B — Curate content catalogs (the bulk of the work)

For each of D-02, D-03, D-05, D-06, D-07, D-08, D-09:

**B1 — `DOMAIN_ARTICLES`** (`src/aegis_phase1/v2/loader/article_loader.py:22-58`):
read `Methodology-main/00_METHODOLOGY/PREPROCESSING/SubDomains/D-XX_*.md` and
extract `source_clauses` references per per-regulation sub-objective. Map
each clause → its `article_ref`. Populate the dict mirroring D-10's structure:
```python
"D-09": {
    "GDPR": ["Art. 30", "Art. 5", ...],
    "CRA":  ["Annex VII §...", ...],
    "NIS2": [], "DORA": [], "AI_Act": [],
},
```
NIS2/DORA/AI_Act slots stay empty for TinyTask (GDPR+CRA only) — correct,
they're filtered out by `applicable_regs` downstream.

**B2 — `_DOMAIN_CLAUSE_FILTER`** (`src/aegis_phase1/v2/loader/ambiguity_loader.py:48-96`):
same source. List `(regulation, clause_id_prefix, [], False)` tuples for every
clause referenced in the per-reg SOs. This is what keeps §6 KNOWN AMBIGUITIES
under the prompt budget — without it, `_entry_matches_domain` returns `True`
for all ~280 cards (ambiguity_loader.py:6-10 docstring warning).

### Phase C — Parameterize gates

Refactor `scripts/d10_2_experiment.py` → `scripts/domain_adapt_experiment.py`
taking `--domain D-XX` (default D-10 for backward compat). Per-domain output
dir `logs/phase1/v2/<domain_slug>/runs/`.

| Gate | Change |
|---|---|
| **G1** (`_gate_audit_theme`) | **Drop** — domain-affinity probe redundant with G4 + G7 + G9. meta.json keeps key set `true` for legacy run comparability. |
| **G3** (`_gate_gdpr_cra`) → `g3_all_applicable_regs_present` | Take `applicable_regs` from `inputs["applicable_regs"]`, check each appears in the V3 haystack. TinyTask still checks GDPR∧CRA. |
| **G5** (`_gate_no_furthermore`) | Align `CONNECTIVE_PROHIBITIONS` with the prompt's full 7-item list (`prompt.py:161-163`). Currently only checks 3 of 7. |
| **G9** (`_gate_g9_v3_structure:332`) | Replace `len(sub.blocks) < 3` with `len(sub.blocks) < len(applicable_regs) + 1`. |
| G2/G4/G6/G7/G8 | Unchanged (already domain- and regulation-agnostic). |

### Phase D — Tests

- `tests/unit/v2/loader/test_article_loader_catalog.py` (NEW) — parametrized
  over D-01..D-10, each asserts ≥1 article mapped for ≥1 applicable reg.
- `tests/unit/v2/loader/test_ambiguity_loader_catalog.py` (NEW) — parametrized
  over D-01..D-10, each asserts a `_DOMAIN_CLAUSE_FILTER` entry exists (so the
  all-cards fallthrough cannot trigger).
- `tests/unit/v2/domain/filters/test_filters_use_state_path.py` (NEW) — assert
  `filter_articles` / `filter_ambiguities` read from `state["preprocessing_path"]`,
  not the hardcoded constant (regression guard for Phase A).

### Phase E — Per-domain smoke test

For each domain D-01..D-10, run
`scripts/domain_adapt_experiment.py --domain D-XX --model gemma4:e2b`.
Capture per-domain: prompt_chars (≤ ~35 K budget), parse success, gate
pass-rate. Write `logs/phase1/v2/generalization_summary.md` table.

**Expected friction points** (will surface here, not blocking):
- **D-08 Human Factors** — sub-domains are NIS2-soleAuthority; for TinyTask
  (GDPR+CRA) per-reg SOs may be sparse → some sub-domains produce only Generic
  + 1 reg block. Generalized G9 handles this correctly.
- **D-06 Supply Chain** — primaryRegulatoryDriver is DORA/DPA; TinyTask only
  has GDPR+CRA. May render thin.

---

## 4. Acceptance criteria

| ID | Criterion | Verification |
|---|---|---|
| C1 | Each of D-01..D-10 has ≥1 article in `DOMAIN_ARTICLES` for ≥1 applicable reg (TinyTask: GDPR or CRA) | `test_article_loader_catalog.py` parametrized PASS |
| C2 | Each of D-01..D-10 has a `_DOMAIN_CLAUSE_FILTER` entry | `test_ambiguity_loader_catalog.py` parametrized PASS |
| C3 | `filter_articles` / `filter_ambiguities` read from `state["preprocessing_path"]` | `test_filters_use_state_path.py` PASS |
| C4 | `scripts/domain_adapt_experiment.py --domain D-XX` accepts any D-01..D-10 | manual smoke |
| C5 | G3 / G9 parameterized on `applicable_regs` | gate code review + D-10 regression smoke |
| C6 | `pytest tests/unit/v2/ -v` ≥ 331 + new tests, 0 failures | CI |
| C7 | Collection-integrity (AGENTS.md §10.2) clean | `pytest tests/unit/v2/ --co -q \| grep -E "ERROR\|ModuleNotFoundError"` empty |
| C8 | D-10 regression: smoke still 9/9 PASS | `--domain D-10` run |
| C9 | Each of D-01..D-09 produces a parseable V3 output (G7 PASS) | per-domain smoke |

---

## 5. Sign-off

| Role | Status |
|---|---|
| user_approved | pending |
| generator_implemented | pending |
| evaluator_verified | pending |
| quality_log_updated | pending |

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| Phase A path rewire silently breaks D-10 | Phase D regression test + D-10 smoke in Phase E (C8) |
| Phase B curation misreads a clause → bad anchor mapping | Phase D test asserts ≥1 article per domain; G8 (anchor validation) catches any fabrication in the smoke runs |
| Domain with no applicable-reg SOs (e.g. D-08 NIS2-only for TinyTask) renders only Generic block | Generalized G9 (`< len(applicable_regs)+1`) handles; document thin-render in summary |
| Curated clause_ids don't exist in ambiguity corpus (typos) | `_entry_matches_domain` falls through to all-cards if no prefix matches — observable as §6 bloat in smoke run; easy to spot |
| D-06 primary driver is DORA (not applicable to TinyTask) | Will render thin but not fail; document in summary |

---

## 7. Execution plan

1. **Pre-flight:** confirm main tip = CORR-022 merge (e62c3f1), 331 tests green.
2. **Phase A:** de-hardcode the two filter paths + test.
3. **Phase B1+B2:** curate catalogs for the 7 empty domains (largest effort).
4. **Phase C:** gate parameterization + script rename.
5. **Phase D:** add the three test files.
6. **Phase E:** per-domain smoke (10 runs); write summary.
7. **Sign-off + commit + PR #28.**
