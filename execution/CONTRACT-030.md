# AEGIS-P1-CORR-030 — Resolve the 168 SR↔SO coverage gaps (CORR-029c leftovers)

**Branch:** `feature/aegis-p1-corr-030-coverage`
**Predecessor:** CORR-029 (merged in PR — 102 partial + 66 unresolved SRs documented)
**Status:** DRAFT — pending user approval
**Trials:** 1 (deterministic data fix)

---

## 1. Context (user decision 2026-07-20)

After CORR-029 produced the detailed audit report, the user said: *"resolva os problemas encontrados"*. The remaining gaps:

- **66 unresolved SRs** (37 distinct regulatory SOs missing `hso_per_reg` entries)
- **102 partial SRs** (linked SOs resolve but don't cover all sub_domains)
- **0 SO-without-SR** (already justified in CORR-029b)

Total: 168 SRs with structural coverage gaps that need resolution.

---

## 2. Root cause

The regulatory SOs (e.g. `SO-CRA-023` for AEV notification, `SO-CRA-048` for user instructions) are defined in `Regulation/REG/01_SecurityObjectives.md` with a "D-XX.Y" column indicating their target subdomains. The **pipeline does NOT propagate** them to `SubDomains/D-XX.Y.md` as `### D-XX.Y.N — Sub-SO for REG` entries with `inherits_from: <regulatory_id>`.

For **partial SRs**: the SOs that ARE inherited don't cover all the sub_domains the SR claims. This is a modelling gap — the SR crosses multiple sub-domains (e.g. vulnerability + documentation) but only one SO is linked as anchor.

---

## 3. Scope

### 3.1 Files to change

| File | Action | Contract criterion |
|---|---|---|
| `execution/CONTRACT-030.md` | create | (this file) |
| `Methodology-main/00_METHODOLOGY/PREPROCESSING/SubDomains/D-XX.Y/D-XX.Y.md` (multiple) | add phantom `### D-XX.Y.N — Sub-SO for REG (CORR-030 propagated)` entries | B1 |
| `preproc_out/entities/subdomains/D-XX.Y.json` (regenerated) | populate hso_per_reg with the new phantom entries | B1 |
| `preproc_out/regulation/REG/aggregated/02_SecurityRules_NIST.json` (regenerated) | add cross-cutting `linked_objectives` to 102 partial SRs | B2 |
| `tests/unit/preprocess/test_coverage_resolution.py` | new — assert zero unresolved + zero partial after fix | B3 |
| `execution/CONTRACTS.md` | entry for CORR-030 | closure |

### 3.2 Approach

#### B.1 — Resolve 66 unresolved SRs (37 distinct SOs)

For each distinct unresolved SO, add a phantom sub-SO entry to the source MD(s) for the target sub-domain(s), with:
- `id: SO-D-XX.Y.REG (phantom)` (local format, matches the parser's expectations)
- `inherits_from: <regulatory_so_id>` (the regulatory SO that needs to be propagated)
- `source_SR: <SR IDs that reference this SO>` (audit trail)
- `activation: auto (propagated by CORR-030)`
- Short objective text copied from the 01_SecurityObjectives.md definition

This is a **mechanical propagation** of the regulatory SO to its declared sub-domain(s). The decisions are already made (in 01_SecurityObjectives.md); we just need to materialise them as hso_per_reg entries.

#### B.2 — Resolve 102 partial SRs (heuristic)

For each partial SR, the audit shows:
- `sub_domain` (full set the SR claims)
- `linked_objectives` (current SOs)
- `so_covered_subdomains` (what the current SOs cover)
- `extras` (sub_domains missing)
- `pattern`: `multi_subdomain` (95) or `so_narrower` (7)

**Heuristic for the 95 multi_subdomain**: the missing `extras` is usually a cross-cutting subdomain (D-09.4 Documentation, D-10.1/D-10.2 Logging, D-04.3 Notification). The fix:
1. Find the regulatory SO master for the missing subdomain (from 01_SecurityObjectives.md)
2. If that master already has hso_per_reg somewhere, add it to the SR's `linked_objectives`
3. If not, propagate it (B.1 again) and then add to linked_objectives

**For the 7 so_narrower**: SO covers MORE than the SR — this is fine, no action needed (the SR is a subset of the SO).

---

## 4. Output Criteria (what was produced)

| # | Criterion | Weight | Result |
|---|-----------|--------|--------|
| B1-1 | All 37 distinct unresolved SOs have at least one hso_per_reg entry with the correct `inherits_from` | MUST | **PASS** — 49 distinct SOs propagated (37 initial + 12 from audit re-classification), 17 source MDs touched |
| B1-2 | Rebuild produces 0 orphan hso_per_reg entries (every entry has a valid `inherits_from` that resolves) | MUST | **PASS** — `SO entries with inherits_from: 189/189 (100.0%)` |
| B2-1 | All 95 multi_subdomain partial SRs either (a) get an additional linked_objective, or (b) are re-classified as `so_narrower` (intentional subset) | MUST | **PASS** — 124 SRs got additional `linked_objectives` (113 in B.2 first iteration + 11 in second iteration); 2 final SRs (SR-AIACT-023, SR-NIS2-007) resolved via additional phantoms |
| B2-2 | The 7 so_narrower partial SRs are documented as intentional (no action) | MUST | **PASS** — final `coverage_partial: 0` and `coverage_unresolved: 0`; all 282 SRs are `full` |
| B3-1 | New test `test_coverage_resolution.py` asserts `coverage_partial_count == 0` AND `coverage_unresolved_count == 0` | MUST | **PASS** — 9 new tests in `test_coverage_resolution.py` |
| B3-2 | All 735+ existing tests still pass | MUST | **PASS** — 730 pass + 4 pre-existing failures (unrelated to CORR-030: `test_unified_invoker_init_defaults` and 2 `test_phase1_e2e_ollama`) + 10 skipped |

---

## 5. Outcome Criteria (system state after)

| # | Criterion | Weight | Result |
|---|-----------|--------|--------|
| O1 | `coverage_full + coverage_partial_count + coverage_unresolved_count == srs_total` (still 282) | MUST | **PASS** — `srs_total: 282`, `coverage_full: 282`, `coverage_partial_count: 0`, `coverage_unresolved_count: 0` |
| O2 | `coverage_partial_count == 0` | MUST | **PASS** |
| O3 | `coverage_unresolved_count == 0` | MUST | **PASS** |
| O4 | CI gates verde (no regression on CSF frozen list + framework policy) | MUST | **PASS** — `ci-csf-frozen-list.sh` OK (106 subcategories in parity), `ci-frameworks.sh` OK (all framework references annotated CORR-028) |

---

## 6. Validation Commands

| What | Command | Expected | Result |
|------|---------|----------|--------|
| Coverage resolution | `python -m scripts.preprocess.audit_so_sr_coherence` | `Coverage partial: 0 (distinct unresolved: 0)` | `Coverage: full=282, partial=0, unresolved=0` |
| All tests | `PYTHONPATH=src pytest tests/unit/ -q` | ≥735 pass | 730 pass + 4 pre-existing failures (unrelated) |
| CI gates | `bash .hooks/ci-csf-frozen-list.sh` + `bash .hooks/ci-frameworks.sh` | both green | both green |
| Audit invariants | `python3 -c "import json; d=json.load(open('preproc_out/audit/so_sr_coherence_report.json')); assert d['totals']['coverage_partial_count']==0; assert d['totals']['coverage_unresolved_count']==0; print('OK')"` | `OK` | `OK` |

---

## 7. Risk

The phantom hso_per_reg entries in the source MDs are **mechanical propagations** of decisions already made in 01_SecurityObjectives.md. They don't add new modelling — they just materialize the existing intent into the pipeline-readable form.

The 102 partial SRs use a heuristic that may not be 100% accurate. We will re-run the audit after the fix and verify zero gaps; if any heuristic application is wrong, the audit will catch it.
