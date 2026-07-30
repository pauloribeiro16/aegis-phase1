# CORR-079 — Sidebar 4 tabs with all methodology information

**Status:** DRAFT (2026-07-30)
**Branch:** `feature/aegis-p1-corr-079-rich-sidebars`
**Decision date:** 2026-07-30
**Author:** Planner (opencode / MiniMax-M3)
**Sprint contract:** [`execution/contracts/SC-2026-21.json`](contracts/SC-2026-21.json)
**Spec:** [`execution/SPEC.md`](SPEC.md) (SP-2026-21)
**Predecessor contracts:**
- [CORR-078](CORR-078.md) — wire all ambiguity analyses into the entity graph + fix §2/§3 rendering
- [CORR-077](CORR-077.md) — AI Act case1 CSV audit corrections
- [CORR-076](CONTRACT-076.md) — LLM prompts rewritten in functional vocabulary

---

## Resumo executivo

User explicit request (2026-07-30, plan mode):

> *"Quero meter mais informação, toda a informação que existe nessa pasta [`Methodology-main/00_METHODOLOGY/PREPROCESSING/`] de forma organizada."*

Current detail sidebar (`docs/visualization/regulation_chain.html` 3.6 MB) shows ~13 JSON keys per entity, but:
- **Python loaders strip data**: Articles lose 4 fields (`security_rules[]`, `security_objectives[]`, `source`, `in_scope_articles_referenced`); Clauses lose 2 (`obligated_party`, `obligation_type`); Regulations lose 3 + aggregated SOs/SRs.
- **No access to methodology MDs**: ~3 MB of `.md` files in the methodology folder (per-article analyses, per-clause Berry analyses, validation reports, audit trails, aggregated SOs/SRs) are never surfaced.

This contract adds 4 organized tabs to the detail sidebar so every entity exposes its full data + its source MD + related methodology files + cross-references.

### User-approved decisions (2026-07-30)

1. **4 tabs**: Rendered / JSON / Markdown / Context (Recommended)
2. **Embed all**: HTML grows from 3.6 MB → ~6.6 MB. No lazy fetch, no per-entity HTML files (Recommended)
3. **MD renderer**: pure JS regex (~80 lines, no external deps)
4. **Cross-refs**: pre-computed at build time, stored per entity
5. **Tab persistence**: `STATE.activeDetailTab` remembers active tab across item clicks
6. **Process**: formal contract with Evaluator subagent (fresh context)

---

## Decisões aprovadas

1. **Tabs:** 4 organized tabs (Rendered / JSON / Markdown / Context).
2. **HTML size:** Embed all (~6.6 MB acceptable).
3. **MD renderer:** Pure JS regex, no external library, ≤100 lines.
4. **Cross-refs:** Pre-computed inverse index per entity, stored as field.
5. **Tab state:** `STATE.activeDetailTab` global, default Rendered.
6. **Loader strategy:** Read directly from `Methodology-main/00_METHODOLOGY/PREPROCESSING/` (the symlink in repo root).
7. **Backward compat:** All CORR-078 criteria C1-C18 still pass (data integrity preserved).
8. **Build script gitignored:** Modifications to `build_regulation_chain.py` and regenerated `regulation_chain.html` are NOT committed. Backup to `/tmp/corr078_viz_backup/`.
9. **Test infrastructure:** Extend `tests/unit/v2/visualization/test_regulation_chain.py` with 7+ new tests.
10. **CI gates:** `ruff check` baseline 27 → no new errors; `pytest tests/unit/ -m "not slow"` → no new failures.

---

## Acceptance criteria (18 MUST, default-FAIL)

All criteria are Tier 3 (behavioral) — must pass T3 validation, not just syntax.

### WS1 — Loaders preserve raw data + MD

| # | Criterion | Validation command (excerpt) |
|---|---|---|
| **C1** | `load_articles()` populates `securityRules[]` (full SR dicts, not just IDs) for ≥95% articles | Walk `preproc_out/entities/articles/AI_Act_Art_*.json` after rebuild; assert `securityRules[0].sr_id` non-empty |
| **C2** | `load_articles()` populates `securityObjectivesFull[]` (full SO dicts) for ≥95% articles | Same walk; assert `securityObjectivesFull[0].so_id` non-empty |
| **C3** | `load_articles()` populates `rawMd` (content of Articles/Art_NN.md) for ≥95% articles | Same walk; assert `len(rawMd) > 100` (file content) |
| **C4** | `load_clauses()` populates `obligatedParty` and `obligationType` for ≥80% clauses | Walk `preproc_out/entities/clauses/_root/GDPR/*.json`; assert ≥80% have `obligated_party` non-empty |
| **C5** | `load_clauses()` populates `rawMd` (per-clause block from Ambiguity) for ≥80% clauses | Walk `preproc_out/entities/clauses/_root/GDPR/*.json`; assert `len(rawMd) > 50` |
| **C6** | `load_regulations()` populates `rawReadme`, `raw01`, `raw02`, `rawValidation`, `rawAudit` for all 5 regs | Walk `preproc_out/regulation/*/00_README.md` parent; assert 25 fields populated (5 regs × 5 MDs) |
| **C7** | `load_regulations()` populates `aggregatedSos[]` and `aggregatedSrs[]` lists | For GDPR, `len(aggregatedSos) > 50` (84 SOs in methodology) |
| **C8** | `load_sos()` populates `rawRow` for ≥95% SOs | Walk `preproc_out/entities/sos/*/*.json`; assert ≥95% have `rawRow` non-empty |
| **C9** | `load_srs()` preserves `raw_md` (CORR-078 verification, no regression) | Walk `preproc_out/entities/srs/*/*.json`; assert all have `raw_md` non-empty |
| **C10** | All entities have `crossRefs` field (pre-computed inverse index) | Walk all entities; assert `crossRefs` is dict with keys `sos`, `srs`, `clauses` |

### WS2 — Tab UI in sidebar detail

| # | Criterion | Validation command (excerpt) |
|---|---|---|
| **C11** | HTML output contains `<div class="detail-tabs">` with 4 `<button>` elements | grep `<button class="detail-tab-btn"` count >= 4 |
| **C12** | HTML output contains 4 `<div class="tab-pane">` containers | grep `class="tab-pane"` count >= 4 |
| **C13** | JS `STATE.activeDetailTab` field exists and defaults to `'rendered'` | Read embedded JS; grep `activeDetailTab` |
| **C14** | Clicking a tab button calls `switchDetailTab(name)` and toggles `hidden` attribute | Unit test on extracted function |

### WS3 — Markdown renderer

| # | Criterion | Validation command (excerpt) |
|---|---|---|
| **C15** | `mdToHtml("# H1")` returns `<h1>H1</h1>` (and variants for H2-H6) | Unit test with 6 fixtures |
| **C16** | `mdToHtml("**bold** *italic*")` returns `<strong>bold</strong> <em>italic</em>` | Unit test |
| **C17** | `mdToHtml("- a\n- b")` returns `<ul><li>a</li><li>b</li></ul>` | Unit test with 3 list variants |
| **C18** | `mdToHtml("| h1 \| h2 \|\n\| --- \| --- \|\n\| a \| b \|")` returns `<table>` | Unit test for GFM tables |

### WS4 — Context tab + cross-refs (deferred to subsequent contract if needed)

Not in this contract. C18 finishes with WS3 — Context tab is a small follow-up that can be CORR-080 if scope creep becomes a concern. The Generator will document in RUN-LOG whether Context tab data is captured by C10 (crossRefs) and a basic Context tab rendering is included.

### Regression

| # | Criterion | Validation command (excerpt) |
|---|---|---|
| **C-REG1** | All CORR-078 unit tests still pass | `pytest tests/unit/scripts/preprocess/test_clause_parsers.py tests/unit/scripts/preprocess/test_source_role.py tests/unit/v2/visualization/test_regulation_chain.py -v` → all pass |
| **C-REG2** | Full unit suite: 0 new failures vs main | `pytest tests/unit/ -m "not slow" -n auto` → failure count ≤ 69 (baseline) |
| **C-REG3** | `ruff check tests/unit/v2/visualization/` → 0 new errors | exit 0 |

---

## Implementation notes

### Phasing (4 sequential commits)

**Commit 1 — WS1 (loaders preserve raw data + MD):**
- Modify 5 loader functions in `build_regulation_chain.py` (lines 73-330)
- Read directly from `ROOT/methodology-00/PREPROCESSING/Regulation/<REG>/{00_README,01,02,03,04}.md` (resolve symlink via `Path(__file__).resolve()`)
- For each article: load `Articles/Art_NN.md`, embed as `rawMd`
- For each clause: load parent `Ambiguity/*.md`, extract per-clause block by matching clause_id, embed as `rawMd`
- Pre-compute `crossRefs` per entity: scan all embedded SOs/SRs/clauses for `article_ref` matches
- New tests: 10 loader tests in `test_regulation_chain.py`
- Empty commit message: **MUST** be `--allow-empty` since build script is gitignored

**Commit 2 — WS2 (tab UI):**
- Modify HTML template (line 393+): replace single `.detail` body with `<div class="detail-tabs">` + 4 `<div class="tab-pane">` containers
- Add CSS for tabs (reuses `.tab-btn` pattern from §2-§5)
- JS `renderDetailTabs(kind, id)` populates each pane from corresponding field
- `STATE.activeDetailTab` for persistence
- New tests: 4 UI tests

**Commit 3 — WS3 (MD renderer):**
- New JS function `mdToHtml(md)` (~80 lines pure regex)
- Tests with 9 fixtures (headings, bold, italic, code, lists, table, blockquote, link, fallback)
- Apply `mdToHtml()` to Markdown tab content

**Commit 4 — WS4 (Context tab basics):**
- Context tab shows `crossRefs` data for each entity (pre-computed in Commit 1)
- Basic rendering: list of SOs/SRs/clauses with click-to-navigate
- Defer full Context tab features (link to Ambiguity file, MD file browser) to CORR-080 if needed

### Why pure JS regex (not marked.js)

- Methodology MDs are well-structured: headings, lists, tables, code blocks. No exotic syntax (no nested HTML, no inline LaTeX, no footnotes).
- 80 lines of regex covers 95% of use cases.
- Zero dependencies = zero supply chain risk, zero extra KB.
- Graceful fallback to `<pre>` for unknown syntax.

### Why pre-compute crossRefs (not runtime search)

- 1500 entities × 1500 candidates = 2.25M comparisons.
- Build time: ~1-2s once. Runtime: instant.
- Each entity gets `crossRefs: {sos: [ids], srs: [ids], clauses: [ids]}` field (~1-5 KB per entity).
- Total HTML growth: ~1-2 MB. Within 7 MB target.

### Why backup build script to /tmp/corr078_viz_backup/

- Build script + HTML are gitignored (per repo `.gitignore`).
- User's workflow depends on these files being present in worktree.
- Backup ensures recovery if worktree auto-clean deletes them (observed earlier in this session).
- Generator must copy modified `build_regulation_chain.py` to backup after each commit.

---

## Pre-flight (per AGENTS.md §5)

- ✅ Branch: `feature/aegis-p1-corr-079-rich-sidebars` created from main
- ✅ Runner imports OK: `PYTHONPATH=src ../shared-venv-root/bin/python -c "from aegis_phase1.v2.runner import main; print('OK')"` → OK
- ⚠️ pytest not in PATH (use `../shared-venv-root/bin/python -m pytest` during implementation)

---

## Cross-references

- Spec: [`execution/SPEC.md`](SPEC.md) (SP-2026-21)
- Sprint contract: [`execution/contracts/SC-2026-21.json`](contracts/SC-2026-21.json)
- Diagnosis subagent report (UX audit): embedded in plan-mode discussion 2026-07-30
- Affected files (NOT committed): `docs/visualization/build_regulation_chain.py`, `docs/visualization/regulation_chain.html`
- Affected files (committed): `tests/unit/v2/visualization/test_regulation_chain.py`, `execution/SPEC.md`, `execution/CORR-079.md`, `execution/CORR-079-RUN-LOG.md`, `execution/contracts/SC-2026-21.json`, `execution/QUALITY_LOG.md`

---

**Status:** DRAFT → user approval → Generator implementation → Evaluator verification → VALIDATED → commit.