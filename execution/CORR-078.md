# CORR-078 — Wire all ambiguity analyses into the entity graph + fix §2/§3 rendering

**Status:** DRAFT (2026-07-30)
**Branch:** `feature/aegis-p1-corr-078-ambiguity-wiring`
**Decision date:** 2026-07-30
**Author:** Planner (opencode / MiniMax-M3)
**Sprint contract:** [`execution/contracts/SC-2026-20.json`](contracts/SC-2026-20.json)
**Spec:** [`execution/SPEC.md`](SPEC.md) (SP-2026-20)
**Predecessor contracts:**
- [CORR-077](CORR-077.md) — AI Act case1 CSV audit corrections
- [CORR-076](CONTRACT-076.md) — LLM prompts rewritten in functional vocabulary (no person names)
- [CORR-074](CONTRACT-074.md) — capabilities catalog (data layer + loader + tests)
- [CORR-073](CORR-073.md) — tier-aware content via `data/` templates

---

## Resumo executivo

User reported 3 data-quality issues in `docs/visualization/regulation_chain.html` on 2026-07-30:

1. §2 Articles (140 articles, includes many out-of-scope citations) — many AI_Act articles have `#SOs = 0` even though SOs are derivable from inner `security_rules[].linked_objectives`.
2. §3 Clauses (498 clauses, many skeleton) — `Type` column shows `—` for 295+ clauses because parsers fail to capture the Instance-by-Instance Berry analysis.
3. §3 GDPR rows look empty (84/86 rows are placeholders) because `_extract_clauses_gdpr_style` expects a yaml-block format that GDPR MDs don't use.

Three parallel subagents (HTML-builder audit, preprocessor audit, methodology-source audit) identified the root causes:

| Layer | Bug | Effect |
|---|---|---|
| Build script | `build_regulation_chain.py:145` reads only top-level `security_objectives[]` | AI_Act #SOs=0 for all 24 articles |
| Preprocessor | `pipeline.py:1513` regex `r"SO-[A-Z_0-9]+-\d{3}"` rejects mixed-case IDs | All `SO-AI_Act-XXX` rejected; aggregate AI_Act SO list = 0 |
| Preprocessor | `clause.py:100-103` `_AI_ACT_H3_RE` only matches `AIA-Cxx` | 29/29 AI_Act clauses fall back to skeleton |
| Preprocessor | `clause.py:110-112` `_INSTANCE_RE` only matches em-dash | GDPR slash-separated Instance labels not captured |
| Preprocessor | `clause.py:250-311` GDPR style parser expects yaml-block | 84/86 GDPR clauses have `type=""`, `title="Verbatim (with highlighting)"`, `instances=[]` |
| Preprocessor | `clause.py:72-75` `_V01_H3_CLAUSE_RE` requires 2 em-dashes | GDPR v0.1 cross-article clauses skeleton-only |
| Source MD | No `source_role` flag distinguishing in-scope vs cited-only | §2 lists 24 AI_Act articles (11 out-of-scope) |
| Build script | No filter for `out_of_scope` articles | Out-of-scope articles render in §2 |
| Build script | §3 has single `Type` column instead of 4 boolean columns | Hard to scan Berry categories visually |

User explicit follow-up (2026-07-30, plan mode): *"Eu quero todas as analises de ambiguidade disponiveis aqui conectadas com as coisas que existem aqui."* — every Instance in the MD source must reach the JSON entities.

This contract fixes 5 preprocessor bugs + 3 build-script gaps + adds the `source_role` schema field (computed by preprocessor from `00_README.md`, not stored in MD) + regenerates golden fixtures. No MD changes. No methodology-main repo edits.

---

## Decisões aprovadas

1. **Scope:** 1 contract grande, 4 workstreams sequenciais (mesma branch, 4 commits).
2. **WS2 (out-of-scope):** Filtrar artigos com `source_role == "out_of_scope"` da §2. `source_role` continua no JSON para lookup downstream.
3. **WS3-F (colunas §3):** Substituir coluna única `Type` por 4 colunas booleanas VAG / POLY / COORD / SCOPE-Q com indicador `✓`/`—`.
4. **GDPR:** Manter estrutura chapter-level (5 ficheiros MD). Pré-processador enriquece cada chapter JSON com `instances[]` parseados do formato slash-separated.
5. **Schema `source_role`:** Computado pelo pré-processador a partir de `00_README.md` in-scope list (não editado em MD frontmatter). Field é `Literal["primary_source","supporting_citation","out_of_scope"]`.
6. **Backwards compat:** CRA/DORA/NIS2 parsers que funcionam hoje continuam a funcionar (C13/C14 verificação obrigatória).
7. **Test infrastructure:** Novas suites em `tests/unit/scripts/preprocess/test_clause_parsers.py`, `test_source_role.py`, `tests/unit/v2/visualization/test_regulation_chain.py`.
8. **Golden regen:** `tests/fixtures/pipeline_inputs_golden/` regenerado em commit 4 com diff capturado em `execution/CORR-078-RUN-LOG.md`.

---

## Acceptance criteria (18 MUST, default-FAIL)

All criteria are Tier 3 (behavioral) — must pass T3 validation, not just syntax.

### WS1 — Preprocessor parser fixes

| # | Criterion | Validation command (excerpt) |
|---|---|---|
| **C1** | Regex `_SO_ID_RE` accepts `SO-AI_Act-013` (mixed-case) | `python -c "from scripts.preprocess.pipeline import _SO_ID_RE; assert _SO_ID_RE.fullmatch('SO-AI_Act-013')"` |
| **C2** | `parse_article_split('Art_3.md')` returns ≥1 `security_objectives` | Run on `Methodology-main/.../Art_3.md`; assert `len(result['security_objectives']) >= 1` |
| **C3** | `parse_ambiguity_file('01_AI_Act_Art9_RiskMgmt.md')` returns clauses with non-empty `instances[]` | Run on AI_Act ambiguity file; assert at least one clause has `instances[0].label` non-empty |
| **C4** | `parse_ambiguity_file('03_GDPR_Ch3_Rights.md')` returns `GDPR-RT01` with `instances[0].label == "VAG"` (or any Berry label) | Run on GDPR Ch3 file; assert `GDPR-RT01.instances` non-empty |
| **C5** | GDPR clauses have populated `type`, `obligated_party`, `obligation_type` | `GDPR-RT01.type` non-empty (e.g., `"data-subject-facing"`) |
| **C6** | GDPR clauses use H4 title (not "Verbatim (with highlighting)") | `GDPR-RT01.title` contains clause-relevant substring (e.g., "Transparency modalities") |
| **C13** | **Regression:** CRA `parse_ambiguity_file('03_CRA_Art13_Manufacturers.md')` still produces clauses with `instances[0].label="POLY"` for CRA-CL14 | Pre/post diff: instance labels preserved for CRA-CL14 |
| **C14** | **Regression:** DORA and NIS2 parsers still populate `instances[]` for their clauses | At least 73 DORA clauses still have `instances[]` populated; NIS2 clauses parse without exception |

### WS2 — `source_role` flag

| # | Criterion | Validation command (excerpt) |
|---|---|---|
| **C7** | Each `regulation/<REG>/articles/Art_*.json` has `source_role` ∈ {`primary_source`, `supporting_citation`, `out_of_scope`} | Walk all 140 article JSONs; assert field exists and value is one of 3 literals |
| **C8** | In-scope count matches `00_README.md` enumeration per regulation | AI_Act: 13 `primary_source`; CRA/DORA/NIS2/GDPR match README in-scope counts |

### WS3 — Build script fixes

| # | Criterion | Validation command (excerpt) |
|---|---|---|
| **C9** | Build script filters `out_of_scope` articles from §2 | HTML embedded JSON has `<tr>` only for `primary_source` + `supporting_citation` (zero `out_of_scope` rows) |
| **C10** | Build script computes `securityObjectives` as union of top-level + `security_rules[].linked_objectives` | HTML `#SOs` column for AI_Act articles > 0 (was 0) |
| **C11** | §3 table has 4 columns `VAG`, `POLY`, `COORD`, `SCOPE-Q` | HTML table contains `<th>VAG</th>`, `<th>POLY</th>`, `<th>COORD</th>`, `<th>SCOPE-Q</th>` |
| **C12** | §3 cells populated (not `—`) for AI_Act and GDPR clauses | AI_Act-CL01 cells VAG=`✓`, POLY=`✓` (from `types_found=["VAG","POLY","COORD"]`); ≥50/86 GDPR clauses have ≥1 cell with indicator |

### WS4 — Golden regen + CI

| # | Criterion | Validation command (excerpt) |
|---|---|---|
| **C15** | Golden fixtures regenerated; diff captured in `execution/CORR-078-RUN-LOG.md` | `ls tests/fixtures/pipeline_inputs_golden/` has updated files; run log exists |
| **C16** | `ruff check src/ tests/` → ≤27 errors (baseline) | No new errors introduced |
| **C17** | Full unit suite: ≤28 pre-existing failures, zero NEW failures | `pytest tests/unit/ -m "not slow" -n auto` |
| **C18** | CI gates pass | `bash .hooks/ci-pipeline-inputs.sh && bash .hooks/ci-frameworks.sh` exit 0 |

---

## Implementation notes

### Phasing (4 sequential commits)

**Commit 1 — WS1 (parsers):**
- Modify 5 regexes (C1, C2, C3, C4, C5, C6).
- Rewrite `_extract_clauses_gdpr_style` to parse pipe-separated metadata + H4 title.
- Add `tests/unit/scripts/preprocess/test_clause_parsers.py` with positive + regression cases.
- Run `pytest tests/unit/scripts/ tests/unit/v2/output/ -n auto` — must not regress.

**Commit 2 — WS2 (source_role):**
- Add `compute_source_role(article_json, in_scope_articles)` in `scripts/preprocess/parsers/entities/clause.py` (or new module `source_role.py`).
- Modify `pipeline.py:_process_regulation` to read `00_README.md`, extract in-scope list, call `compute_source_role` per article.
- Add `tests/unit/scripts/preprocess/test_source_role.py` with all 3 literal values tested.

**Commit 3 — WS3 (build script):**
- Modify `build_regulation_chain.py:130-148` to union SOs.
- Add filter for `source_role == "out_of_scope"` in §2.
- Replace `Type` column with 4 boolean columns in §3 table HTML template (lines 854-871) and `renderClauses()` JS (lines 1218-1235).
- Add `tests/unit/v2/visualization/test_regulation_chain.py` verifying HTML output.

**Commit 4 — WS4 (golden regen):**
- Run full preprocess: `PYTHONPATH=src python -m scripts.preprocess build`.
- Diff `tests/fixtures/pipeline_inputs_golden/` vs git HEAD.
- Capture diff summary in `execution/CORR-078-RUN-LOG.md`.
- Update `QUALITY_LOG.md` with CORR-078 entry.

### Why Option A for source_role (not Option B)

- Option A: preprocessor reads `00_README.md` per regulation, computes `source_role` deterministically. No MD changes.
- Option B: add `source_role: …` to each `Art_*.md` frontmatter manually. 140 files × manual edits × risk of inconsistency.
- AGENTS.md §6 marks MD changes as "Ask first" (touches Methodology-main, separate repo). Option A avoids this entirely.

### Why 4 boolean columns (not 3 ambiguity/vagueness/poly)

- User originally asked for "ambiguidade vageness e poly" — but the methodology uses Berry classification with 4 categories: VAG (vagueness), POLY (polyvalency), COORD (coordination), SCOPE-Q (scope quantification). Adding only 3 columns loses COORD data.
- Decision: 4 columns preserves all Berry categories; methodology-driven taxonomy wins over natural-language intuition.

### Risk: regex change breaks working parsers

CRA, NIS2, DORA per-article parsers currently work. The regex changes (C1, C2, C3, C4, C5) are additive (accept more variants), not destructive (reject existing matches). C13/C14 regression tests verify this before merge.

### Risk: GDPR rewrite loses existing data

The GDPR `_extract_clauses_gdpr_style` currently extracts 0 fields correctly (per C5/C6 failure). The rewrite populates fields that are currently empty. Strict superset — no data loss. C5/C6 verify populated state.

---

## Pre-flight (per AGENTS.md §5)

Already executed (2026-07-30):
- ✅ `PYTHONPATH=src ../shared-venv-root/bin/python -c "from aegis_phase1.v2.runner import main; print('OK')"` → OK
- ✅ Branch created: `feature/aegis-p1-corr-078-ambiguity-wiring`
- ⚠️  `pytest --co` not in PATH (will use `../shared-venv-root/bin/python -m pytest` during implementation)

---

## Cross-references

- Diagnosis subagent reports: 3 reports stored in conversation history 2026-07-30 (HTML builder audit, preprocessor audit, methodology-source audit). Cite file_path:line_number throughout.
- Affected source MD (no edits): `Methodology-main/00_METHODOLOGY/PREPROCESSING/Regulation/AI_Act/{Articles,Ambiguity,00_README.md}` and 4 other regulations.
- Affected preprocessor: `scripts/preprocess/{pipeline.py,parsers/entities/clause.py,parsers/aggregated/security_objectives.py}`.
- Affected build script: `docs/visualization/build_regulation_chain.py`.
- Affected golden: `tests/fixtures/pipeline_inputs_golden/`.

---

**Status:** DRAFT → user approval → Generator implementation → Evaluator verification → VALIDATED → commit.