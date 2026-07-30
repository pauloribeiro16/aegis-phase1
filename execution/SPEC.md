# SPEC — Sidebar 4 tabs with all methodology information

**Spec ID:** SP-2026-21
**Date:** 2026-07-30
**Author:** Planner (opencode / MiniMax-M3)
**Status:** DRAFT
**Level:** spec-first
**Sprint contract:** [`execution/contracts/SC-2026-21.json`](contracts/SC-2026-21.json)
**Predecessor contracts:**
- [CORR-078](CORR-078.md) — wire all ambiguity analyses into the entity graph + fix §2/§3 rendering
- [CORR-077](CORR-077.md) — AI Act case1 CSV audit corrections
- [CORR-076](CONTRACT-076.md) — LLM prompts rewritten in functional vocabulary (no person names)

---

## Context

### Problem Statement

The visualization at `docs/visualization/regulation_chain.html` exposes only a fraction of the methodology data living in `Methodology-main/00_METHODOLOGY/PREPROCESSING/`. The user explicitly asked (2026-07-30):

> *"Quero meter mais informação, toda a informação que existe nessa pasta de forma organizada."*

The current detail sidebar (`renderFields` at line 1374 of `build_regulation_chain.py`) renders JSON keys recursively, but:
- **Python loaders strip data** before embedding: Articles lose 4 fields (`security_rules[]`, `security_objectives[]`, `source`, `in_scope_articles_referenced`); Clauses lose 2 (`obligated_party`, `obligation_type`); Regulations lose 3 (`schema_version`, `source`, `chain_version`) + aggregated SOs/SRs.
- **No access to original methodology MDs**: ~3MB of `.md` files in the methodology folder (per-article analyses, per-clause Berry analyses, validation reports, audit trails, aggregated SOs/SRs) are never surfaced.

The user wants **4 organized tabs** in the detail sidebar so every entity exposes its full data + its source MD + related methodology files.

### Current State (per UX audit subagent 2026-07-30)

- Detail sidebar layout: 3-column grid `240px | 1fr | 420px` (line 499).
- Sidebar content: generic `<dl>` grid from `renderField(val, key, depth)` (line 1345), depth limit 3, strings > 600 chars truncated with `…`, `LONG_FIELDS` (18 keys) wrapped in `<details class="narrative">` with 240px scroll cap.
- **Dead CSS** (defined but unused): `.expand-toggle` (L718), `.raw-json` (L865).
- Loaders strip the heaviest fields to keep HTML small (3.6MB).
- Per entity, MD source files exist but are not embedded:

| Entity | MD source file | Size |
|---|---|---|
| Regulation | `Regulation/<REG>/00_README.md` | 2-5 KB |
| Regulation | `01_SecurityObjectives.md`, `02_SecurityRules_NIST.md`, `03_validation_report.md`, `04_deduction_audit.md` | 5-30 KB each |
| Article | `Regulation/<REG>/Articles/Art_NN.md` | 5-30 KB |
| Clause | `Regulation/<REG>/Ambiguity/*.md` (file-level, extract per-clause block) | 10-30 KB per file, ~2-5 KB per clause |
| SO | row in `01_SecurityObjectives.md` + 2 lines context | ~1 KB |
| SR | `raw_md` already embedded (CORR-078) | varies |

### Target State

Detail sidebar gains 4 tabs:

| Tab | Content | Loader changes? |
|---|---|---|
| **Rendered** | Current view (recursive JSON renderer, depth limits, narrative details) | None |
| **JSON** | Raw JSON with ALL fields (incl. previously stripped) | YES — loaders must preserve |
| **Markdown** | Source MD for this entity, rendered client-side via `mdToHtml()` | YES — loaders embed MD |
| **Context** | Related methodology files + cross-references | YES — loaders embed MD + cross-refs pre-computed |

HTML grows from 3.6 MB → ~6.6 MB. Tabs render on click (content present in DOM but hidden via CSS until activated).

### User-approved decisions (2026-07-30, plan mode)

1. **4 tabs** (Recommended): Rendered / JSON / Markdown / Context
2. **Embed all** (Recommended): no lazy fetch, all data upfront in DOM. Trade-off: 6.6 MB HTML for zero latency on tab switch.
3. **MD renderer**: pure JS regex (~80 lines, no external deps). Covers H1-H6, bold/italic, code, code blocks, lists, GFM tables, blockquotes, links, horizontal rules.
4. **Cross-refs**: simple regex search in embedded JSON. List "Mentioned in: SO-XXX, SR-XXX, CL-XXX" without semantic parsing.
5. **Tab persistence**: `STATE.activeDetailTab` remembers active tab across item clicks.
6. **Process**: formal CORR-079 contract with Evaluator subagent (separate from Generator).

---

## Requirements

### Functional Requirements

| # | Requirement | Priority | Rationale |
|---|-------------|----------|-----------|
| FR-1 | `load_regulations()` loads and embeds `00_README.md` → `rawReadme` field | MUST | User wants methodology MD accessible |
| FR-2 | `load_regulations()` embeds `01_SecurityObjectives.md`, `02_SecurityRules_NIST.md`, `03_validation_report.md`, `04_deduction_audit.md` → `raw01`, `raw02`, `rawValidation`, `rawAudit` | MUST | All 5 top-level MDs per regulation |
| FR-3 | `load_regulations()` adds `aggregatedSos[]` (list of full SO dicts for this reg) and `aggregatedSrs[]` (list of full SR dicts) | MUST | Currently only counts |
| FR-4 | `load_articles()` preserves `security_rules[]` (full SR dicts with rationale, ambiguity_notes) | MUST | Currently stripped, replaced with `securityRuleIds` |
| FR-5 | `load_articles()` preserves `security_objectives[]` (full SO dicts with description, source_clauses, sub_domains) | MUST | Currently stripped |
| FR-6 | `load_articles()` preserves `source` (path) and `in_scope_articles_referenced` | MUST | Useful for traceability |
| FR-7 | `load_articles()` loads `Articles/Art_NN.md` → `rawMd` field | MUST | User's main request |
| FR-8 | `load_clauses()` preserves `obligated_party` and `obligation_type` fields | MUST | Currently stripped (CORR-078 added `types_found` but not these) |
| FR-9 | `load_clauses()` extracts per-clause block from `Ambiguity/*.md` → `rawMd` field | MUST | Per-clause MD context |
| FR-10 | `load_sos()` extracts row + 2 lines context from `01_SecurityObjectives.md` → `rawRow` field | MUST | SO source MD |
| FR-11 | `load_srs()` verifies `raw_md` already preserved (CORR-078) | MUST | Regression check |
| FR-12 | HTML template adds `<div class="detail-tabs">` with 4 buttons (Rendered, JSON, Markdown, Context) | MUST | Tab UI |
| FR-13 | CSS for `.detail-tabs`, `.detail-tab-btn`, `.tab-pane` (reuses existing `.tab-btn` pattern) | MUST | Visual styling |
| FR-14 | JS `renderDetailTabs(kind, id)` populates 4 `<div class="tab-pane">` containers | MUST | Tab content |
| FR-15 | JS `mdToHtml(md)` markdown renderer: H1-H6, bold/italic, inline code, code blocks, ordered/unordered lists, GFM tables, blockquotes, links, horizontal rules | MUST | Markdown tab |
| FR-16 | Markdown tab uses `mdToHtml()` to render the entity's `rawMd` / `rawRow` / `raw_md` field | MUST | Tab content |
| FR-17 | Context tab (Regulation): lists 5 top-level MDs (filename + size) with click-to-open | MUST | Context navigation |
| FR-18 | Context tab (Article): cross-reference search — list SOs/SRs/clauses that mention this `article_ref` (regex in embedded JSON) | MUST | Cross-navigation |
| FR-19 | Context tab (Clause): link to containing `Ambiguity/*.md` file (path embedded in `rawMd` parent reference) | MUST | File context |
| FR-20 | `STATE.activeDetailTab` persists across item clicks; default `Rendered` | MUST | UX continuity |

### Non-Functional Requirements

| # | Requirement | Priority | Rationale |
|---|-------------|----------|-----------|
| NFR-1 | HTML final size ≤ 7 MB (current 3.6 + ~3 MB MD) | MUST | Browser performance |
| NFR-2 | MD renderer ≤ 100 lines of JS | MUST | Maintainability |
| NFR-3 | Zero regressions on CORR-078 criteria C1-C18 (entity data integrity preserved) | MUST | Don't break previous contract |
| NFR-4 | Cross-ref search pre-computed at build time (not runtime) — store as field per entity | MUST | Runtime perf |
| NFR-5 | All paths handle missing files gracefully (`Methodology-main/` may not be symlinked) | MUST | Robustness |
| NFR-6 | `ruff check` on touched files (only test files since build script is gitignored) → 0 new errors vs baseline 27 | MUST | Lint gate |
| NFR-7 | All CORR-078 regression tests still pass: `test_clause_parsers.py`, `test_source_role.py`, `test_regulation_chain.py` | MUST | Don't regress |

### Constraints

- **No MD edits** to `Methodology-main/00_METHODOLOGY/PREPROCESSING/`
- **No new dependencies** (no `marked.js`, no other MD lib) — pure JS regex
- **1 contract, 4 sequential commits** on branch `feature/aegis-p1-corr-079-rich-sidebars`
- **Build script is gitignored** — `docs/visualization/build_regulation_chain.py` and `.html` files are NOT committed. Backup to `/tmp/corr078_viz_backup/`.
- **Embed all** decision: no lazy fetch, no per-entity HTML files

---

## Architecture Decisions

### Decision 1: Markdown renderer approach

- **Context:** Markdown tab needs a JS renderer. Three options:
  - **A. Pure JS regex** (~80 lines, no deps, covers subset)
  - **B. `marked.js` embedded** (~50 KB minified, full CommonMark + GFM)
  - **C. Server-side render at build time** (HTML strings embedded, no runtime render)
- **Options evaluated:**
  - A: zero deps, sufficient for 95% of MDs (headings, lists, tables, code, blockquotes)
  - B: best coverage but adds 50 KB; methodology MDs are simple enough that A suffices
  - C: shifts work to Python (more code there), but loses interactive feel (no live preview)
- **Decision:** **A** (pure JS regex). Justification: methodology MDs are well-structured; edge cases handled by graceful fallback (`<pre>` plain).
- **Consequences:** Renderer covers subset of Markdown. Tables, code blocks, lists, headings all work. Nested edge cases fall back to `<pre>`.

### Decision 2: Cross-reference extraction strategy

- **Context:** Context tab for an Article should list SOs/SRs/clauses that mention `Art. NN`. Options:
  - **A. Pre-compute at build time:** for each article, scan all embedded SOs/SRs/clauses, build inverse index
  - **B. Runtime regex search:** search `DATA.sos`, `DATA.srs`, `DATA.clauses` on tab open
- **Options evaluated:**
  - A: O(n*m) at build time but instant tab open. Each entity has a `crossRefs: {sos: [...], srs: [...], clauses: [...]}` field
  - B: O(n*m) per tab open. Slow with 1500+ entities
- **Decision:** **A** (pre-compute). Justification: 1500 entities × 1500 cross-refs ≈ 2.25M comparisons, but done once at build vs every tab click.
- **Consequences:** Each entity dict grows by ~1-5 KB (cross-ref lists). Total HTML grows by ~1-2 MB. Acceptable for embed-all approach.

### Decision 3: Tab state persistence

- **Context:** When user clicks row A → opens sidebar with Rendered tab → switches to JSON tab → clicks row B → should B open with JSON tab or Rendered?
- **Options:**
  - **A. Reset to default** (Rendered) on every click — predictable but annoying
  - **B. Persist active tab** — user-friendly but surprising for first-time use
- **Decision:** **B with `STATE.activeDetailTab`** (global state). Justification: power users expect this; first-time users won't notice since default = Rendered.
- **Consequences:** JS state object grows by one field. No impact on data flow.

---

## Data Model

### Detail sidebar tab structure (HTML)

```html
<aside class="detail" id="detail">
  <div class="detail-tabs">
    <button class="detail-tab-btn active" data-tab="rendered">Rendered</button>
    <button class="detail-tab-btn" data-tab="json">JSON</button>
    <button class="detail-tab-btn" data-tab="markdown">Markdown</button>
    <button class="detail-tab-btn" data-tab="context">Context</button>
  </div>
  <div class="detail-tab-body">
    <div class="tab-pane" data-pane="rendered">... renderFields() output ...</div>
    <div class="tab-pane" data-pane="json" hidden><pre class="raw-json">{...}</pre></div>
    <div class="tab-pane" data-pane="markdown" hidden>... mdToHtml(rawMd) ...</div>
    <div class="tab-pane" data-pane="context" hidden>... cross-refs list ...</div>
  </div>
</aside>
```

### Per-entity fields added by loaders

```
Regulation
├── rawReadme: str            # NEW — content of 00_README.md
├── raw01: str                # NEW — content of 01_SecurityObjectives.md
├── raw02: str                # NEW — content of 02_SecurityRules_NIST.md
├── rawValidation: str        # NEW — content of 03_validation_report.md
├── rawAudit: str             # NEW — content of 04_deduction_audit.md
├── aggregatedSos: list[dict] # NEW — full SO dicts for this reg (from raw01)
├── aggregatedSrs: list[dict] # NEW — full SR dicts for this reg (from raw02)
└── crossRefs: dict           # NEW — {sos: [], srs: [], clauses: []} for cross-refs

Article
├── securityRules: list[dict] # NEW — full SR dicts (was stripped, only IDs survived)
├── securityObjectivesFull: list[dict] # NEW — full SO dicts
├── source: str               # NEW — path to MD
├── inScopeArticlesReferenced: list[int]  # NEW
├── rawMd: str                # NEW — content of Articles/Art_NN.md
└── crossRefs: dict           # NEW

Clause
├── obligatedParty: str       # NEW (CORR-078 populated but not embedded)
├── obligationType: str       # NEW
├── rawMd: str                # NEW — block from Ambiguity/*.md matching this clause ID
└── crossRefs: dict           # NEW

SO
├── rawRow: str               # NEW — row + 2 lines context from 01_SecurityObjectives.md
└── crossRefs: dict           # NEW — list SOs/SRs that reference this SO

SR
├── raw_md: str               # EXISTS (CORR-078) — verify preserved
└── crossRefs: dict           # NEW
```

### `mdToHtml(md: string): string`

Converts Markdown subset to HTML:
- `# H1` … `###### H6` → `<h1>` … `<h6>`
- `**bold**` → `<strong>`, `*italic*` → `<em>`
- `` `inline code` `` → `<code>`
- ` ```lang\n...\n``` ` → `<pre><code class="language-lang">`
- `- item` / `* item` → `<ul><li>...</li></ul>`
- `1. item` → `<ol><li>...</li></ol>`
- `| col1 | col2 |\n| --- | --- |\n| a | b |` → `<table>`
- `> quote` → `<blockquote>`
- `[text](url)` → `<a href="url">text</a>`
- `---` → `<hr>`
- Plain lines → `<p>`

Fallback: unrecognized syntax → wrap in `<pre>`.

---

## File changes

| File | Action | Why |
|---|---|---|
| `docs/visualization/build_regulation_chain.py` | modify — extend 5 loaders + add tabs UI + add `mdToHtml()` | FR-1 to FR-20 |
| `tests/unit/v2/visualization/test_regulation_chain.py` | modify — add 7+ new tests | NFR-3, validation |
| `execution/SPEC.md` | update — SP-2026-21 (this file) | process |
| `execution/CORR-079.md` | create — contract prose doc | process |
| `execution/CORR-079-RUN-LOG.md` | create — run log evidence | process |
| `execution/contracts/SC-2026-21.json` | create — sprint contract JSON | process |
| `execution/QUALITY_LOG.md` | modify — add CORR-079 entry | process |

**Gitignored artifacts (NOT committed):**
- `docs/visualization/build_regulation_chain.py` modifications → backup to `/tmp/corr078_viz_backup/`
- `docs/visualization/regulation_chain.html` regenerated → backup same location

---

## Phasing — 4 sequential commits

### Commit 1 — Loaders preserve raw data + MD
- Extend `load_regulations` (line 73+) to embed 5 top-level MDs + aggregated SOs/SRs
- Extend `load_articles` (line 117+) to preserve `security_rules[]`, `security_objectives[]`, `source`, `inScopeArticlesReferenced`, `rawMd`
- Extend `load_clauses` (line 155+) to preserve `obligatedParty`, `obligationType`, `rawMd` (block from Ambiguity)
- Extend `load_sos` (line 211+) to embed `rawRow` (row + context from 01)
- Verify `load_srs` preserves `raw_md`
- Add `crossRefs` field to all entities (pre-computed at build time)
- Add loader tests in `test_regulation_chain.py`

### Commit 2 — Tab UI in sidebar detail
- HTML template: replace single `<div class="detail" id="detail">` with tabbed structure
- CSS for `.detail-tabs`, `.detail-tab-btn`, `.tab-pane`
- JS `renderDetailTabs(kind, id)` populates 4 panes
- `STATE.activeDetailTab` for persistence
- Tests: HTML has 4 tab buttons; clicking switches pane visibility

### Commit 3 — Markdown renderer
- JS `mdToHtml(md)` function (~80 lines, pure regex)
- Unit tests with fixtures (headings, lists, tables, code blocks, blockquotes)
- Apply to Markdown tab content
- Test: rendered HTML matches expected output for each fixture

### Commit 4 — Context tab + cross-refs
- For Regulation: Context tab lists 5 top-level MDs (filename + size) with click handler
- For Article: cross-ref search pre-computed in loader (Commit 1), Context tab renders list
- For Clause: link to containing Ambiguity file
- Tests: Context tab content per entity type

Each commit: `ruff check` + targeted pytest + visual check (regenerate HTML, verify tabs render).

---

## Test plan

### Loader tests (Commit 1)
- `test_articles_have_rawMd`: ≥95% articles have `rawMd` non-empty
- `test_articles_have_securityRules`: all articles have `securityRules[]` array
- `test_articles_have_securityObjectivesFull`: all articles have `securityObjectivesFull[]` array
- `test_clauses_have_rawMd`: ≥80% clauses have `rawMd` (per-clause extraction)
- `test_clauses_have_obligatedParty`: ≥80% clauses have `obligatedParty` populated
- `test_regulations_have_5_top_md`: each of 5 regs has all 5 MD fields populated
- `test_regulations_have_aggregated_sos`: each reg has `aggregatedSos[]` with length matching raw01 row count
- `test_sos_have_rawRow`: all SOs have `rawRow` non-empty

### UI tests (Commit 2)
- `test_html_has_4_detail_tabs`: HTML contains "Rendered", "JSON", "Markdown", "Context" button text in detail area
- `test_html_has_4_tab_panes`: 4 `<div class="tab-pane">` containers
- `test_STATE_active_detail_tab`: JS state includes `activeDetailTab` field

### Markdown renderer tests (Commit 3)
- `test_mdToHtml_renders_headings`: `# H1` → `<h1>H1</h1>`, etc. (6 cases)
- `test_mdToHtml_renders_bold_italic`: `**b**` → `<strong>b</strong>`, `*i*` → `<em>i</em>`
- `test_mdToHtml_renders_code_block`: triple-backtick block → `<pre><code>`
- `test_mdToHtml_renders_unordered_list`: `- a\n- b` → `<ul><li>a</li><li>b</li></ul>`
- `test_mdToHtml_renders_ordered_list`: `1. a\n2. b` → `<ol>`
- `test_mdToHtml_renders_table`: GFM table → `<table>`
- `test_mdToHtml_renders_blockquote`: `> q` → `<blockquote>`
- `test_mdToHtml_renders_link`: `[t](u)` → `<a href="u">t</a>`
- `test_mdToHtml_fallback_for_unknown`: weird syntax → `<pre>`

### Context tab tests (Commit 4)
- `test_context_tab_regulation_lists_5_mds`: for reg GDPR, Context shows 5 MD filenames
- `test_context_tab_article_lists_cross_refs`: for an Article with SOs/SRs referencing it, Context shows them
- `test_context_tab_clause_links_to_ambiguity_file`: for a clause, Context shows link to containing Ambiguity file

### Regression tests (all commits)
- All CORR-078 tests still pass (C1-C18 equivalent unit tests)
- `test_regulation_chain.py` existing tests: 5 passed / 5 total
- Full suite: 2665 passed, 0 new failures

---

## Risks + Rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| HTML size 3.6 → 6.6 MB exceeds 7 MB target | Lazy: tabs render on click (content in DOM but display:none until tab active). Profile with sample entity. | `--allow-empty` revert commit 1 |
| MD renderer edge cases (nested tables, escaped chars) | Subset of MD syntax + 9 fixture tests; fallback to `<pre>` plain for unknown | Replace `mdToHtml` with `<pre>` plain (one-line swap) |
| Cross-ref pre-computation slow at build time | O(n*m) ≈ 2.25M comparisons; ~1-2s build time acceptable | Remove `crossRefs` field; Context tab shows "not available" |
| Missing `Methodology-main/` symlink | Try/except + "MD not available" message in tab | Defensive: silent fallback |
| Browser can't handle 6.6 MB HTML | Test in target browser; consider gzip transfer (server-side) | Reduce embedded MDs (drop audit/validation, keep only raw01/raw02) |

---

## Out of scope

- Renaming entities
- Refreshing preproc_out (already done in CORR-078)
- Filtering / sorting changes (user explicitly said "só por-item")
- New JSON fields in preproc_out (CORR-078 already added `source_role`, `instances`, `types_found`)
- Touching `Methodology-main/` MDs
- `taxonomy_chain.html` (different viz, not in scope)

---

**Status:** DRAFT → user approval → ANCHORED → Generator implementation begins.