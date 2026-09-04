# AEGIS-P1-CORR-028 — NIST CSF 2.0 ONLY cleanup (orfaços, lineage, documentação canónica)

**Branch:** `feature/aegis-p1-corr-028-csf-2.0-only-cleanup`
**Predecessor:** CORR-027 (merged — 106 frozen list + v1.1→v2.0 lineage captured)
**Status:** DRAFT — pending user approval
**Trials:** 1 (deterministic data fix + docs — no LLM variance)
**Pre-flight:** branch `feature/aegis-p1-corr-027-csf-frozen-list` clean, 732 tests collectable, 3 critical modules import OK.

---

## 1. Context (user-stated problem, 2026-07-20)

User asked three things in one message:

1. **"Quero que todos tenham apenas os 106 controlos oficiais, mais nada"** — clean CSF 2.0 set everywhere
2. **"Como posso mapear todos os controlos NIST CSF 2.0 para os domínios e subdomínios?"** — check if the reverse index (CSF → subdomain) is complete
3. **"Deve estar bem explícito em todo o lado que só vamos usar o NIST CSF 2.0"** — declare "NIST CSF 2.0 ONLY" canonically

Investigation produced the following findings (this contract addresses 1 + 3; item 2 is **DEFERRED** per user decision):

| Finding | Evidence | Decision in this contract |
|---|---|---|
| 5 subdomains contain orphan CSF IDs (PR.DS-12, RS.CO-04) not in 106 | `preproc_out/audit/csf_mapping_report.json` verdict_counts `{OK:1, SPARSE:32, BROKEN:5}` | **A1: remove orphans** |
| `csf_1_1_to_2_0_mapping.json` (108 mappings, 17 tests, CORR-027 lineage) still in active path | `scripts/preprocess/pipeline.py:267` writes it; `tests/unit/preprocess/test_csf_v11_to_v20_mapping.py` tests it | **A2: archive to `archive/csf_v11_v20_mapping/`** |
| Global JSON `categories` field has 34 entries (incl. withdrawn-only); MD says 22 active | `preproc_out/global/NIST_CSF_2.0_subcategories.json` first cat: `DE.AE` with `withdrawn_count: 2` | **A3: filter JSON categories to 22 active** |
| 50 of 106 controlos uncovered by any subdomain (reverse index gap) | reverse index: 0 subdomains for 50 IDs | **DEFERRED to future contract (user said "esquece o mapeamento para ja")** |
| `AGENTS.md` + `MANIFESTO.md` don't say "NIST CSF 2.0 ONLY" | text-grep negative | **C1-C4: canonical declaration** |
| Output code (`doc_04*.py`, `track_b.py`) references ISO 27001, SOC 2, OWASP as if they were control frameworks | `grep -n "ISO 27001\|OWASP" src/aegis_phase1/v2/output/` returns 7 hits | **C5: separate "control framework" (CSF 2.0) from "attestation pattern" (SOC 2/ISO/OWASP)** |
| No CI gate prevents re-introducing other control frameworks | `.hooks/` has no frameworks check | **C6: new CI gate** |

---

## 2. Scope

### 2.1 Files to change

| File | Action | Contract criterion |
|---|---|---|
| `execution/CONTRACT-028.md` | create | (this file) |
| `archive/csf_v11_v20_mapping/README.md` | create | A2-1 |
| `archive/csf_v11_v20_mapping/csf_1_1_to_2_0_mapping.json` | create (snapshot) | A2-2 |
| `archive/csf_v11_v20_mapping/csf_mapping.py` | create (snapshot) | A2-3 |
| `archive/csf_v11_v20_mapping/test_csf_v11_to_v20_mapping.py` | create (snapshot) | A2-4 |
| `scripts/preprocess/pipeline.py` | modify (drop writer for archived file) | A2-5 |
| `tests/unit/preprocess/test_csf_v11_to_v20_mapping.py` | delete | A2-6 |
| `preproc_out/entities/subdomains/D-04.3.json` | modify (remove RS.CO-04) | A1-1 |
| `preproc_out/entities/subdomains/D-05.1.json` | modify (remove PR.DS-12) | A1-2 |
| `preproc_out/entities/subdomains/D-05.2.json` | modify (remove PR.DS-12) | A1-3 |
| `preproc_out/entities/subdomains/D-05.3.json` | modify (remove PR.DS-12) | A1-4 |
| `preproc_out/entities/subdomains/D-05.4.json` | modify (remove PR.DS-12) | A1-5 |
| `preproc_out/global/NIST_CSF_2.0_subcategories.json` | modify (filter `categories` to 22 active) | A3-1 |
| `scripts/preprocess/parsers/entities/csf_xlsx.py` | modify (filter categories output) | A3-2 |
| `docs/NIST_CSF_2.0_ONLY.md` | create | C1-1 |
| `AGENTS.md` | modify (add Framework policy section) | C2-1 |
| `methodology-00/MANIFESTO.md` | modify (add NIST CSF 2.0 ONLY banner) | C3-1 |
| `methodology-00/REFERENCE/related_frameworks.md` | modify (mark as "excluídos desta fase") | C4-1 |
| `src/aegis_phase1/v2/output/doc_04c.py` | modify (annotate ISO 27001/SOC 2 as attestation) | C5-1 |
| `src/aegis_phase1/v2/output/doc_04.py` | modify (annotate) | C5-2 |
| `src/aegis_phase1/v2/output/doc_04b.py` | modify (annotate OWASP as guidance, not control framework) | C5-3 |
| `src/aegis_phase1/v2/output/doc_04d.py` | modify (annotate OWASP) | C5-4 |
| `src/aegis_phase1/v2/output/doc_05.py` | modify (annotate ISO 27001) | C5-5 |
| `src/aegis_phase1/prompts_v2/track_b.py` | modify (annotate ISO 27001) | C5-6 |
| `.hooks/ci-frameworks.sh` | create | C6-1 |
| `tests/unit/hooks/test_ci_frameworks.py` | create | C6-2 |

### 2.2 NOT in scope (deferred to future contracts)

- **CORR-029**: LLM-assisted mapping of 50 uncovered CSF controlos to subdomains (DEFERRED per user)
- **Phase 2/3**: ISO 27001, NIST 800-53, OWASP as control frameworks (excluded from this phase per `related_frameworks.md`)

---

## 3. Output Criteria (what was produced)

| # | Criterion | Weight | Result |
|---|-----------|--------|--------|
| A1-1 | `grep "PR\.DS-12\|RS\.CO-04" preproc_out/entities/subdomains/D-{04.3,05.1,05.2,05.3,05.4}.json` returns empty | MUST | — |
| A1-2 | `python -m scripts.preprocess.audit_csf_mapping` reports `verdict_counts.BROKEN == 0` | MUST | — |
| A2-1 | `archive/csf_v11_v20_mapping/` exists with README explaining the archival | MUST | — |
| A2-2 | `archive/csf_v11_v20_mapping/csf_1_1_to_2_0_mapping.json` is byte-identical to the pre-contract file | MUST | — |
| A2-3 | `scripts/preprocess/pipeline.py` no longer writes `csf_1_1_to_2_0_mapping.json` | MUST | — |
| A2-4 | `tests/unit/preprocess/test_csf_v11_to_v20_mapping.py` is removed (and test count drops by 17) | MUST | — |
| A2-5 | `pytest tests/unit/ --co -q` collects `732 - 17 = 715` tests, no import errors | MUST | — |
| A3-1 | `python -c "import json; d=json.load(open('preproc_out/global/NIST_CSF_2.0_subcategories.json')); print(len(d['categories']))"` prints 22 | MUST | — |
| A3-2 | The 12 filtered categories all have `withdrawn_count == 0` and `subcategory_count > 0` of active subs | MUST | — |
| C1-1 | `docs/NIST_CSF_2.0_ONLY.md` exists with: scope, in-scope (CSF 2.0), out-of-scope (ISO 27001, NIST 800-53, OWASP, CSF 1.1), exceptions (vendor attestation SOC 2/ISO 27001 explicitly allowed) | MUST | — |
| C2-1 | `grep -A5 "## Framework" AGENTS.md` shows explicit "NIST CSF 2.0 ONLY" policy | MUST | — |
| C3-1 | `head -20 methodology-00/MANIFESTO.md` contains "Framework: NIST CSF 2.0 (ONLY)" banner | MUST | — |
| C4-1 | `methodology-00/REFERENCE/related_frameworks.md` first table cell says "Out of Phase 1 scope" for ISO 27001, NIST 800-53, OWASP, NIST SSDF | MUST | — |
| C5-1 | `grep -n "ISO 27001\|SOC 2" src/aegis_phase1/v2/output/doc_04c.py` shows each match annotated with `# attestation pattern, NOT control framework (per NIST_CSF_2.0_ONLY.md C5)` | MUST | — |
| C5-2 to C5-6 | Same pattern for the other 5 source files | MUST | — |
| C6-1 | `.hooks/ci-frameworks.sh` exits 0 when run on a clean tree, and exits 1 if a forbidden control framework is added without an allowlist annotation | MUST | — |
| C6-2 | `tests/unit/hooks/test_ci_frameworks.py` covers: (a) clean passes, (b) unannotated mention fails, (c) annotated mention passes | MUST | — |

---

## 4. Outcome Criteria (system state after)

| # | Criterion | Weight | Result |
|---|-----------|--------|--------|
| O1 | `preproc_out/` contains zero orphan CSF IDs in subdomains (audit BROKEN=0) | MUST | — |
| O2 | `preproc_out/global/NIST_CSF_2.0_subcategories.json` has 22 categories (active) + 106 subcategories (active) | MUST | — |
| O3 | Documentation is self-consistent: AGENTS.md, MANIFESTO.md, related_frameworks.md, NIST_CSF_2.0_ONLY.md all say CSF 2.0 is the only control framework | MUST | — |
| O4 | CI gate prevents regression: any new doc/code claiming another framework as a control framework is rejected | MUST | — |
| O5 | All 715+ unit tests pass | MUST | — |
| O6 | The 50 uncovered CSF controlos are documented in `docs/NIST_CSF_2.0_ONLY.md` §"Known gaps" with the note "DEFERRED to CORR-029" | SHOULD | — |
| O7 | `git log --oneline -10` shows 4-8 commits on `feature/aegis-p1-corr-028-csf-2.0-only-cleanup` | MUST | — |

---

## 5. Validation Commands

| What | Command | Expected |
|------|---------|----------|
| Tests pass | `PYTHONPATH=src pytest tests/unit/ -v --tb=short` | 715+ passed |
| Lint clean | `ruff check src/ tests/ scripts/ .hooks/` | 0 errors |
| CSF audit | `python -m scripts.preprocess build && python -m scripts.preprocess.audit_csf_mapping` | BROKEN=0 |
| Categories count | `python -c "import json; d=json.load(open('preproc_out/global/NIST_CSF_2.0_subcategories.json')); print(len(d['categories']))"` | 22 |
| CI frameworks | `bash .hooks/ci-frameworks.sh` | exit 0 |
| CI frameworks test | `PYTHONPATH=src pytest tests/unit/hooks/test_ci_frameworks.py -v` | 3 passed |
| Pre-commit | `pre-commit run --all-files` | all pass |
| No orphan CSF | `grep -rn "PR\.DS-12\|RS\.CO-04" preproc_out/entities/subdomains/` | empty |
| No v1.1 mapping writes | `grep -n "csf_1_1_to_2_0" scripts/preprocess/pipeline.py` | empty (or only archive reference) |

---

## 6. Quality Dimensions

| Dimension | Threshold |
|-----------|-----------|
| Correctness | 100% (no orphan IDs in 5 subdomains; categories=22) |
| Pattern Compliance | ≥3/4 (project conventions, snake_case, type hints) |
| No Regressions | 100% (715/715 tests pass) |
| Data Integrity | 100% (preproc_out rebuilds identical except for the documented changes) |
| Documentation Completeness | 100% (every reference to a framework in output code is annotated) |

---

## 7. Files to Change (summary)

| Action | Count |
|---|---|
| create | 6 (contract, archive dir + 4 files, NIST_CSF_2.0_ONLY.md, ci-frameworks.sh, test_ci_frameworks.py) |
| modify | 14 (5 subdomains, 1 pipeline.py, 1 csf_xlsx.py, 1 JSON, AGENTS.md, MANIFESTO.md, related_frameworks.md, 5 output .py + track_b.py) |
| delete | 1 (test_csf_v11_to_v20_mapping.py) |
| **Total** | **21 file operations** |

---

## 8. Correction Loop

- Max 3 cycles per criterion
- After 3 failures: STOP and ask user
- All MUST criteria must pass for the contract to succeed
- SHOULD criteria (O6) contribute to score but don't block
