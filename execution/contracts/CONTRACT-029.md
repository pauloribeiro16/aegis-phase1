# AEGIS-P1-CORR-029 — SO↔SR structural coherence (fix YAML parser, resolve orphans, audit)

**Branch:** `feature/aegis-p1-corr-029-so-sr-coherence`
**Predecessor:** CORR-028 (merged — 106 CSF frozen + 22 active categories + framework policy)
**Status:** DRAFT — pending user approval
**Trials:** 1 (deterministic data fix + parser extension — no LLM variance)

---

## 1. Context (user-stated problem, 2026-07-20)

User invoked a structural-coherence audit on `00_METHODOLOGY/PREPROCESSING/` and found 3 problems:

1. **AI Act with 15 orphan sub-domains** (SRs without SOs)
2. **~50 SRs with sub-domains outside the union of their linked SOs**
3. **Bi-directional gaps** (SOs without SRs; SRs without SOs)

User asked to: (a) validate the findings, (b) explain the problems, (c) propose how to fix them.

### 1.1 Validation results (pre-contract investigation, 2026-07-20)

| Claim | Original report | Investigation | Disposition |
|---|---|---|---|
| AI Act has 15 orphan sub-domains | 15 | **0** — AI Act has SOs in 14/15 sub-domains where it has SRs. Only 1 orphan (D-07.3) | Original report **inaccurate** (used wrong counting unit). Real orphans: **4** total (1 AI_Act + 2 CRA + 1 NIS2) |
| ~50 SRs with extra sub-domains | 50 | **282 SRs all appear to have extras** because the `inherits_from` bridge is **broken in the parser** (returns `None` for 601/602 references) | Original report is a **symptom**; root cause is the YAML parser |
| Bi-directional gaps | minor | **8 SOs without SRs** (CRA D-03.2/D-07.3/D-09.3, DORA D-07.2/D-09.4, GDPR D-03.2, AI_Act D-09.4, NIS2 D-07.3) + **4 SRs without SOs** (AI_Act D-07.3, CRA D-08.1/D-08.2, NIS2 D-01.2) | **Real** gaps to resolve |

### 1.2 Root cause

The MD source files contain `inherits_from: SO-AIACT-001` (the regulatory ID) inside a YAML block. The block also contains a `verified_relationship` value with `()`, `:`, `,`, `**` characters that break `yaml.safe_load()`. The parser at `scripts/preprocess/parsers/entities/subdomain.py:223` reads `inherits_from` from the parsed YAML, but the YAML parse fails → `inherits_from = None` in the JSON output.

**Result**: the SO↔SR index is broken. The `linked_objectives` field in regulation-aggregated SRs uses the regulatory ID (e.g. `SO-AIACT-001`), but the `hso_per_reg[].id` in subdomains uses the local ID (e.g. `SO-D-09.2.AI_Act`). Without `inherits_from` populated, there is no bridge.

---

## 2. Scope

### 2.1 Files to change

| File | Action | Contract criterion |
|---|---|---|
| `execution/CONTRACT-029.md` | create | (this file) |
| `scripts/preprocess/parsers/entities/subdomain.py` | modify (B.1: add `_parse_yaml_block_strict` that pre-extracts key fields by regex) | B1-1 |
| `scripts/preprocess/parsers/entities/subdomain.py` | modify (B.1: add `_extract_sub_so_field` helper for `inherits_from`, `source_SR`, `id`) | B1-2 |
| `scripts/preprocess/parsers/entities/subdomain.py` | add tests (parse robustness) | B1-3 |
| `scripts/preprocess/audit_so_sr_coherence.py` | create (B.5: standalone audit tool) | B5-1 |
| `preproc_out/audit/so_sr_coherence_report.json` | regenerate (B.5: deterministic from preproc_out) | B5-2 |
| `preproc_out/entities/subdomains/D-07.3.json` (AI_Act) | modify (B.4: add SO or justify orphan) | B4-1 |
| `preproc_out/entities/subdomains/D-08.1.json` (CRA) | modify (B.4) | B4-2 |
| `preproc_out/entities/subdomains/D-08.2.json` (CRA) | modify (B.4) | B4-3 |
| `preproc_out/entities/subdomains/D-01.2.json` (NIS2) | modify (B.4) | B4-4 |
| `tests/unit/preprocess/test_so_sr_coherence.py` | create (B.3: regression test) | B3-1 |
| `tests/unit/preprocess/test_subdomain_parser_robustness.py` | create (B.1: parser robustness) | B1-3 |
| `execution/CONTRACTS.md` | modify (add entry for CORR-029) | contract closure |
| `AGENTS.md` | modify (mention CORR-029 audit script) | docs |

### 2.2 NOT in scope (deferred)

- **8 SOs without SRs** (CRA D-03.2/D-07.3/D-09.3, DORA D-07.2/D-09.4, GDPR D-03.2, AI_Act D-09.4, NIS2 D-07.3) — deferred to **CORR-030** (may be intentional: "framework coverage without specific obligations")
- **50 of 106 CSF 2.0 uncovered** — deferred per CORR-028 §4 (user decision)

---

## 3. Output Criteria (what was produced)

| # | Criterion | Weight | Result |
|---|-----------|--------|--------|
| B1-1 | `inherits_from` field is non-None in 100% of `hso_per_reg[]` entries across all 38 subdomains (was: ~0%) | MUST | — |
| B1-2 | Parser handles YAML blocks with `verified_relationship` containing `:`, `(`, `,`, `**` without failing | MUST | — |
| B1-3 | New test `test_subdomain_parser_robustness.py` covers: (a) well-formed YAML, (b) YAML with unquoted special chars, (c) YAML with multi-line values, (d) YAML with comments | MUST | — |
| B2-1 | `python -m scripts.preprocess build` succeeds with parser fix | MUST | — |
| B2-2 | Re-built `preproc_out/entities/subdomains/*.json` have `inherits_from` populated (spot-check ≥5 subdomains) | MUST | — |
| B3-1 | New test `test_so_sr_coherence.py` validates: for each SR, `sub_domain ⊆ ∪(hso.subdomain_id for hso in reg if hso.inherits_from ∈ SR.linked_objectives)` | MUST | — |
| B3-2 | Coherence test reports zero false orphans (the 4 real orphans + 0 false positives) | MUST | — |
| B4-1 | D-07.3 AI_Act: orphan SR justified or SO added (with `## Decisions (CORR-029)` section in source MD) | MUST | — |
| B4-2 | D-08.1 CRA: same | MUST | — |
| B4-3 | D-08.2 CRA: same | MUST | — |
| B4-4 | D-01.2 NIS2: same | MUST | — |
| B5-1 | `python -m scripts.preprocess.audit_so_sr_coherence` produces a structured report at `preproc_out/audit/so_sr_coherence_report.json` | MUST | — |
| B5-2 | The report includes: SO-without-SR count, SR-without-SO count, full bridge resolution rate, list of orphans with metadata | MUST | — |
| B5-3 | `preproc_out/audit/so_sr_coherence_report.json` is committed to git (.gitignore updated) | MUST | — |

---

## 4. Outcome Criteria (system state after)

| # | Criterion | Weight | Result |
|---|-----------|--------|--------|
| O1 | `inherits_from` is non-None in ≥95% of hso_per_reg entries | MUST | — |
| O2 | SO↔SR bridge resolution rate ≥95% (was 0.2%) | MUST | — |
| O3 | All 4 orphan (reg, sub) pairs have either an SO or a documented justification | MUST | — |
| O4 | All 8 SO-without-SR pairs documented in `preproc_out/audit/so_sr_coherence_report.json` §"known gaps" (deferred to CORR-030) | SHOULD | — |
| O5 | All 718+ existing tests pass + new tests pass | MUST | — |
| O6 | `git log --oneline -10` shows 4-8 commits on `feature/aegis-p1-corr-029-so-sr-coherence` | MUST | — |

---

## 5. Validation Commands

| What | Command | Expected |
|------|---------|----------|
| Parser robustness | `PYTHONPATH=src pytest tests/unit/preprocess/test_subdomain_parser_robustness.py -v` | all pass |
| Coherence | `PYTHONPATH=src pytest tests/unit/preprocess/test_so_sr_coherence.py -v` | all pass |
| Build | `python -m scripts.preprocess build` | exit 0 |
| Audit | `python -m scripts.preprocess.audit_so_sr_coherence` | exit 0; report written |
| Bridge resolution | `python3 -c "import json,glob; from collections import defaultdict; d=defaultdict(int); [d.update({...}) for ...]"` (inline check) | ≥95% |
| Existing tests | `PYTHONPATH=src pytest tests/unit/ -q --tb=line` | ≥718 pass + new |
| Pre-commit | `pre-commit run --all-files` | all pass |
| CSF frozen list | `bash .hooks/ci-csf-frozen-list.sh` | OK (no regression) |
| Framework CI | `bash .hooks/ci-frameworks.sh` | OK (no regression) |

---

## 6. Quality Dimensions

| Dimension | Threshold |
|-----------|-----------|
| Correctness | 100% (inherits_from populated; orphan resolution documented) |
| Pattern Compliance | ≥3/4 (project conventions, type hints, AAA tests) |
| No Regressions | 100% (all 718+ tests pass) |
| Data Integrity | 100% (no spurious SO/SR created) |
| Documentation | 100% (each orphan has a justification) |

---

## 7. Correction Loop

- Max 3 cycles per criterion
- After 3 failures: STOP and ask user
- All MUST criteria must pass for contract success
- O4 (SHOULD) does not block
