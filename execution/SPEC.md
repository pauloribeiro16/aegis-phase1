# SPEC — Wire all ambiguity analyses into the entity graph + fix §2/§3 rendering

**Spec ID:** SP-2026-20
**Date:** 2026-07-30
**Author:** Planner (opencode / MiniMax-M3)
**Status:** DRAFT
**Level:** spec-first
**Sprint contract:** [`execution/contracts/SC-2026-20.json`](contracts/SC-2026-20.json)
**Predecessor contracts:**
- [CORR-077](CORR-077.md) — AI_Act case1 CSV audit corrections
- [CORR-076](CONTRACT-076.md) — LLM prompts rewritten in functional vocabulary (no person names)
- [CORR-074](CONTRACT-074.md) — capabilities catalog

---

## Context

### Problem Statement

The visualization at `docs/visualization/regulation_chain.html` shows three data-quality issues that the user reported on 2026-07-30:

1. **§2 Articles table (140 articles):** Many AI_Act articles (24 total) appear without security objectives from `AI_Act Art. 3 — SecurityObjectives & SecurityRules`. Some are referenced only to reinforce other articles' decisions — they are NOT articles from which security objectives were derived. They should not appear in §2 with empty `#SOs`.
2. **§3 Clauses table (498 clauses, many skeleton):** The `Type` column shows `—` for many clauses. The methodology's `Instance — VAG/POLY/COORD/SCOPE-Q — S<n> — \`term\`` blocks are not being captured by the preprocessor parsers.
3. **§3 GDPR rows appear empty:** 86 rows render, but 84 of them have `type=""`, `title="Verbatim (with highlighting)"`, `instances=[]`. Visually indistinguishable from "no rows".

User follow-up (2026-07-30, plan mode): *"Eu quero todas as analises de ambiguidade disponiveis aqui conectadas com as coisas que existem aqui."* — every Instance analysis in the MD source must reach the JSON entities and be rendered in §2/§3.

### Diagnosis (3 parallel subagents, 2026-07-30)

| # | Symptom | Root cause | Layer |
|---|---|---|---|
| A | §2 `#SOs = 0` for 24/24 AI_Act articles | `build_regulation_chain.py:145` reads only top-level `security_objectives[]`, ignores `security_rules[].linked_objectives` | Build script |
| B | JSON shows `security_objectives: []` even when MD has rows | Regex `r"SO-[A-Z_0-9]+-\d{3}"` in `pipeline.py:1513` + `security_objectives.py:62` rejects mixed-case IDs `SO-AI_Act-XXX` (lowercase `c`/`t`) | Preprocessor |
| C | 24 AI_Act articles listed; only 13 are in-scope T5 per `00_README.md:56` | No `source_role` flag in MD/JSON; no filter in build script | Source MD + preprocessor |
| D | §3 `Type` shows `—` for 295+ clauses | `instances[]` empty — parsers fail: `_AI_ACT_H3_RE` only matches `AIA-Cxx`; `_INSTANCE_RE` only matches em-dash (not GDPR slash); `_extract_clauses_gdpr_style` expects yaml-block (MD has pipe-separated) | Preprocessor |
| E | §3 GDPR rows look empty | Same as D — 84/86 GDPR clauses have empty structured fields | Preprocessor |
| F | No separate `Ambiguity`/`Vagueness`/`Poly` columns | UX choice, not data bug | Build script (optional) |

**Summary:** Root cause is **D + B** (parsers silently drop data). **A** is a minor build-script bug that becomes moot once B is fixed. **C** requires a new flag (or computed value). **F** is a UX decision.

### User-approved decisions (2026-07-30)

1. **Out-of-scope articles** (WS2): **Filter** from §2 entirely. They will still have `source_role: "out_of_scope"` in JSON for downstream lookup, but will not render in the table.
2. **Contract scope:** **One large CORR-NNN** (4 workstreams as sequential commits on the same branch).
3. **§3 Type column:** **4 separate columns VAG / POLY / COORD / SCOPE-Q** with checkbox-style indicators driven by `types_found[]` and `instances[].label`.
4. **GDPR ambiguity:** **Keep chapter-level structure** (5 chapter MD files), but enrich the chapter-level JSON with `instances[]` so §3 can render.

### Current State

- `preproc_out/regulation/AI_Act/articles/Art_*.json` — 24 files, all with `security_objectives: []` top-level; `security_rules[i].linked_objectives` populated (inner).
- `preproc_out/regulation/AI_Act/clauses/*.json` — 9 file-level shards with `intra_clause_sections[]` carrying raw markdown.
- `preproc_out/entities/clauses/_root/AI_Act/AI_Act-CL*.json` — 29 clause shards, ALL with `instances: []`, `is_skeleton: true` (no R1/R2/R3 readings captured).
- `preproc_out/entities/clauses/_root/GDPR/GDPR-*.json` — 86 clause shards, 84/86 with `type: ""`, `title: "Verbatim (with highlighting)"`, `instances: []`.
- `preproc_out/entities/articles/AI_Act/AI_Act_Art_ *.json` — 24 article shards, same SO union issue as `regulation/...`.
- Source MD consistently carries the data:
  - AI_Act `Ambiguity/*.md` — 8 per-article files with 132 total `Instance — CAT — S<n> — \`term\`` markers (per subagent count).
  - GDPR `Ambiguity/*.md` — 5 chapter files with 109 total Instance markers (per subagent count).
  - AI_Act `00_README.md:56` — enumerates 13 in-scope T5 articles.

### Target State

- **§2 Articles table** shows only articles whose `source_role != "out_of_scope"`. The 13 in-scope AI_Act articles render with `#SOs > 0`. The 11 out-of-scope citations (Art_3.md, Art_4.md, Art_5.md, Art_21.md, Art_23.md, Art_27.md, Art_33.md, Art_43.md, Art_64.md, Art_83.md, Art_99.md) are hidden. `#SOs` is computed as the union of top-level `security_objectives[]` and inner `security_rules[].linked_objectives`.
- **§3 Clauses table** shows 4 columns VAG/POLY/COORD/SCOPE-Q with cell indicators (`✓` or filled/empty icon) driven by `types_found[]` and `instances[].label`. Each cell is populated for all 498 clauses where the MD source has Instance blocks.
- **GDPR rows in §3** show real values: `type="data-subject-facing"` (etc. from `**Clause:** line`), `title="Transparency modalities"` (from H4, not H3), `instances=[]` populated with at least the Instance labels parsed from the slash-separated format.
- **JSON entities** carry the full Berry analysis: `instances[] = [{label, severity, token, readings: [{id, text, disambiguation_source}], commentary}]`.
- **Golden fixtures** at `tests/fixtures/pipeline_inputs_golden/` regenerated with evidence captured in `execution/CORR-078-RUN-LOG.md`.

---

## Requirements

### Functional Requirements

| # | Requirement | Priority | Rationale |
|---|-------------|----------|-----------|
| FR-1 | Regex `_SO_ID_RE` in `pipeline.py:1513` and `security_objectives.py:62` accepts mixed-case IDs (`SO-AI_Act-013`, etc.) | MUST | Fixes B |
| FR-2 | Regex `_AI_ACT_H3_RE` in `clause.py:100-103` accepts `AI_Act-CLxx`, `AIA-Cxx`, `AIACT-Cxx` | MUST | Fixes D (AI_Act clauses) |
| FR-3 | Regex `_INSTANCE_RE` in `clause.py:110-112` accepts both em-dash `**Instance N — LABEL — S<n> — \`token\`**` AND slash `**Instance N — LABEL / S<n> / \`token\`**` | MUST | Fixes D (GDPR instances) |
| FR-4 | `_extract_clauses_gdpr_style` in `clause.py:250-311` parses pipe-separated metadata `**Clause: GDPR-RT01** \| type: … \| obligatedParty: … \| obligationType: …` and uses H4 (`#### Art. … — Title`) as clause title | MUST | Fixes E |
| FR-5 | Regex `_V01_H3_CLAUSE_RE` in `clause.py:72-75` accepts 1 OR 2 em-dashes | MUST | Fixes D (GDPR v0.1) |
| FR-6 | Each `regulation/<REG>/articles/Art_*.json` carries a `source_role` field ∈ {`primary_source`, `supporting_citation`, `out_of_scope`}, computed by the preprocessor reading the in-scope list from `00_README.md` | MUST | Fixes C |
| FR-7 | `build_regulation_chain.py:130-148` (`load_articles`) computes `securityObjectives` as the union of top-level `security_objectives[]` and inner `security_rules[].linked_objectives` | MUST | Fixes A |
| FR-8 | `build_regulation_chain.py` filters articles with `source_role == "out_of_scope"` from §2 rendering | MUST | User decision 1 |
| FR-9 | `build_regulation_chain.py:854-871,1218-1235` replaces single `Type` column with 4 separate boolean columns `VAG`, `POLY`, `COORD`, `SCOPE-Q` | MUST | User decision 3 |
| FR-10 | Each `entities/clauses/_root/<REG>/*.json` carries enriched `instances[]` with `{label, severity, token, readings: [...], commentary}` | MUST | Wire all ambiguity analyses |
| FR-11 | New unit tests for each parser fix (regression coverage) | MUST | Verify D, E fixes without breaking CRA/DORA/NIS2 |
| FR-12 | Golden fixtures regenerated; `execution/CORR-078-RUN-LOG.md` records diff vs pre-CORR-078 state | MUST | CORR-058 gate |

### Non-Functional Requirements

| # | Requirement | Priority | Rationale |
|---|-------------|----------|-----------|
| NFR-1 | Preprocessor regex changes MUST NOT regress CRA/DORA/NIS2 parsers (currently working) | MUST | Backwards compatibility |
| NFR-2 | Build script fix MUST NOT break §3 for CRA/DORA/NIS2 rows | MUST | Backwards compatibility |
| NFR-3 | Schema addition (`source_role`) MUST be backwards compatible — old consumers reading `regulation/<REG>/articles/Art_*.json` continue to work | MUST | CORR-073 dependency |
| NFR-4 | All touchpoints must respect project conventions (per `project-conventions` skill): type hints, logger usage, no `except: pass` | MUST | Code quality |
| NFR-5 | `ruff check` baseline stays at 27 errors (no new ones introduced) | MUST | CI gate |
| NFR-6 | Full unit suite: ≤28 pre-existing infra failures tolerated; zero new failures in `tests/unit/v2/output/`, `tests/unit/data/`, `tests/unit/scripts/` | MUST | CI gate |

### Constraints

- **No MD changes** in `Methodology-main/00_METHODOLOGY/PREPROCESSING/` — `source_role` is computed by the preprocessor, not stored in frontmatter.
- **GDPR chapter-level structure preserved** — do not split MD into per-article files.
- **1 contract, 4 sequential commits** on branch `feature/aegis-p1-corr-078-ambiguity-wiring`.
- **Golden regen** is a CORR-058 gate — requires `execution/CORR-078-RUN-LOG.md` with diff evidence.

---

## Architecture Decisions

### Decision 1: How to compute `source_role`

- **Context:** The methodology has a clear in-scope list per regulation (e.g., AI_Act `00_README.md:56` enumerates 13 T5 articles). The preprocessor needs to attach this scope to each per-article JSON.
- **Options:**
  - **Option A (data-driven):** Preprocessor reads `00_README.md` per regulation, extracts the "Articles in scope" enumeration, then for each `Art_*.md` sets `source_role` based on (a) whether the filename's article number is in the in-scope list and (b) whether the SR's `article_ref` matches the filename.
  - **Option B (MD-edit):** Manually add `source_role: primary_source|supporting_citation|out_of_scope` to each `Art_*.md` frontmatter.
- **Decision:** **Option A.** Non-invasive (no MD changes), deterministic, scales automatically when `00_README.md` is updated.
- **Consequences:** Preprocessor depends on `00_README.md` parsing. If the README format changes (e.g., table vs list), the preprocessor breaks. Mitigated by adding parser unit tests.

### Decision 2: How to enrich GDPR clauses

- **Context:** GDPR `Ambiguity/*.md` files use a different format than AI_Act:
  - Pipe-separated metadata: `**Clause: GDPR-RT01** \| type: data-subject-facing \| obligatedParty: CONTROLLER \| obligationType: PER-INTERACTION`
  - Slash-separated Instance labels: `**Instance 1 — VAG / S3 / \`token\`**`
  - H4 (`####`) headings for clause titles.
- **Options:**
  - **Option A (parser fix):** Extend `_extract_clauses_gdpr_style` to parse these formats.
  - **Option B (MD rewrites):** Rewrite GDPR MDs to match AI_Act format.
- **Decision:** **Option A.** MD rewrites are intrusive and risk losing data.
- **Consequences:** Parser regex `_INSTANCE_RE` must accept both em-dash and slash variants.

### Decision 3: Schema for `instances[]`

- **Context:** Each Instance block in MD source carries: label, severity, term, multiple readings (R1, R2, R3...) each with disambiguation source.
- **Schema:** Each instance is `{"label": "POLY", "severity": "S2", "token": "risk management system", "commentary": "free text", "readings": [{"id": "R1", "text": "...", "disambiguation_source": "ISO 31000"}]}`.
- **Decision:** Use this schema for both per-clause shards (`entities/clauses/_root/<REG>/*.json`) AND the file-level shards (`regulation/<REG>/clauses/<FILE>.json`).
- **Consequences:** Both representations carry the same data, but the per-clause shards are smaller (one Instance set per clause ID).

---

## Data Model

### Article entity (`regulation/<REG>/articles/Art_NN.json`)

```
Article
├── id: str                          # e.g., "AI_Act_Art_ 3" (existing)
├── regulation: str                  # e.g., "AI_Act" (existing)
├── article_ref: str                 # e.g., "Art. 3" (existing)
├── title: str                       # (existing)
├── status: str                      # (existing)
├── source_role: Literal["primary_source","supporting_citation","out_of_scope"]  # NEW (FR-6)
├── in_scope_articles_referenced: list[str]  # NEW (FR-6) — articles this file actually cites
├── security_objectives: list[str]   # top-level SO IDs (populated after FR-1 fix)
└── security_rules: list[SecurityRule]
    ├── sr_id: str
    ├── title: str
    ├── nist_csf: list[str]
    ├── source_clauses: list[dict]   # article_ref, sub_domain
    └── linked_objectives: list[str]  # SO IDs — survives current pipeline (FR-7 unions with top-level)
```

### Clause entity (`entities/clauses/_root/<REG>/<CL>.json`)

```
Clause
├── id: str                          # e.g., "GDPR-RT01" (existing)
├── regulation: str                  # (existing)
├── section_ref: str                 # (existing; FR-4 populates from H4 for GDPR)
├── title: str                       # (existing; FR-4 replaces "Verbatim (with highlighting)")
├── type: str                        # (existing; FR-4 populates for GDPR)
├── types_found: list[str]           # (existing; FR-4 populates for GDPR)
├── sub_domain: str                  # (existing)
├── obligated_party: str | None      # (existing; FR-4 populates for GDPR)
├── obligation_type: str | None      # (existing; FR-4 populates for GDPR)
├── source_locus: str                # (existing)
├── instances: list[Instance]        # (existing but empty; FR-2/3/4/5 populate)
│   └── Instance
│       ├── label: Literal["VAG","POLY","COORD","SCOPE-Q","Compound","Independent"]
│       ├── severity: Literal["S1","S2","S3"]
│       ├── token: str               # the ambiguous term
│       ├── commentary: str          # free text explanation
│       └── readings: list[Reading]
│           └── Reading
│               ├── id: str          # "R1", "R2", ...
│               ├── text: str        # the reading interpretation
│               └── disambiguation_source: str  # where this reading comes from
├── intra_section_notes: list[dict]  # (existing)
├── berry_anchors: list[str]         # (existing)
└── is_skeleton: bool                # (existing; set true when MD has no Instance blocks)
```

### Build script data flow (`build_regulation_chain.py`)

```
load_articles():
    for each Art_*.json in preproc_out/entities/articles/AI_Act_Art_ *.json:
        securityObjectives = union(
            top_level = d.get("security_objectives", []),
            inner     = [so for sr in d.get("security_rules", []) for so in sr.get("linked_objectives", [])]
        )
        IF source_role == "out_of_scope": SKIP from §2 (FR-8)

load_clauses():
    for each *_CL*.json in preproc_out/entities/clauses/_root/<REG>/*.json:
        vag     = "VAG"     in (d.get("types_found", []) + [i.get("label") for i in d.get("instances", [])])
        poly    = "POLY"    in (...)
        coord   = "COORD"   in (...)
        scope_q = "SCOPE-Q" in (...)
        row = {id, reg, sectionRef, title, vag, poly, coord, scope_q, severity, isSkeleton}

renderArticles(): filters out rows with source_role=="out_of_scope" (already filtered at load)
renderClauses(): renders 4 columns VAG/POLY/COORD/SCOPE-Q with ✓/○ indicators
```

---

## File changes

| File | Action | Why |
|---|---|---|
| `scripts/preprocess/pipeline.py:1513` | modify regex | FR-1 |
| `scripts/preprocess/parsers/aggregated/security_objectives.py:62` | modify regex | FR-1 |
| `scripts/preprocess/parsers/entities/clause.py:100-103` | modify `_AI_ACT_H3_RE` | FR-2 |
| `scripts/preprocess/parsers/entities/clause.py:110-112` | modify `_INSTANCE_RE` | FR-3 |
| `scripts/preprocess/parsers/entities/clause.py:250-311` | rewrite `_extract_clauses_gdpr_style` | FR-4 |
| `scripts/preprocess/parsers/entities/clause.py:72-75` | modify `_V01_H3_CLAUSE_RE` | FR-5 |
| `scripts/preprocess/parsers/entities/clause.py` (new function) | add `compute_source_role(article_json, in_scope_articles)` | FR-6 |
| `scripts/preprocess/pipeline.py` (new function) | read `00_README.md` per regulation, extract in-scope list, call `compute_source_role` | FR-6 |
| `docs/visualization/build_regulation_chain.py:130-148` | union SOs | FR-7 |
| `docs/visualization/build_regulation_chain.py` | filter `out_of_scope` articles | FR-8 |
| `docs/visualization/build_regulation_chain.py:854-871,1218-1235` | split Type column into 4 | FR-9 |
| `tests/unit/scripts/preprocess/test_clause_parsers.py` | new tests for each parser fix | FR-11 |
| `tests/unit/scripts/preprocess/test_source_role.py` | new tests for `source_role` computation | FR-11 |
| `tests/unit/v2/visualization/test_regulation_chain.py` | new tests for HTML rendering changes | FR-11 |
| `tests/fixtures/pipeline_inputs_golden/` | regenerate | FR-12 |
| `execution/CORR-078.md` | new contract doc | process |
| `execution/CORR-078-RUN-LOG.md` | new run log with golden diff | process |
| `execution/SPEC.md` | this file | process |
| `execution/contracts/SC-2026-20.json` | new sprint contract JSON | process |

---

## Phasing (4 sequential commits on `feature/aegis-p1-corr-078-ambiguity-wiring`)

1. **Commit 1 — WS1 (parsers):** Fix 5 regex bugs + GDPR style parser + populate `instances[]`. Add unit tests. **Critical:** regression test for CRA/DORA/NIS2 parsers.
2. **Commit 2 — WS2 (source_role):** Add `compute_source_role` reading `00_README.md`. Write `source_role` to each article JSON. New unit test asserting in-scope counts match README.
3. **Commit 3 — WS3 (build script):** Fix SO union + filter `out_of_scope` + split Type into 4 columns. New tests on HTML output.
4. **Commit 4 — WS4 (golden regen):** Run full preprocess, diff golden, capture evidence in `execution/CORR-078-RUN-LOG.md`, update `QUALITY_LOG.md`.

Each commit runs: `ruff check <touched>` + targeted pytest + full unit suite (baseline check).

---

## Test plan

### Unit tests (new)
- `test_clause_parsers.py`: positive + negative cases for each regex (`_SO_ID_RE`, `_AI_ACT_H3_RE`, `_INSTANCE_RE`, `_V01_H3_CLAUSE_RE`); `_extract_clauses_gdpr_style` parses pipe-separated metadata + H4 title.
- `test_source_role.py`: `compute_source_role("AI_Act", "Art_9")` returns `"primary_source"`; `("AI_Act", "Art_3")` returns `"out_of_scope"`; `("AI_Act", "Art_55")` with SR-AI_Act-022 (Art. 73) returns `"supporting_citation"`. In-scope count for AI_Act == 13, GDPR == 41, CRA matches `00_README.md`, etc.
- `test_regulation_chain.py`: HTML output §2 filters out_of_scope; §2 #SOs > 0 for AI_Act articles; §3 has 4 columns VAG/POLY/COORD/SCOPE-Q; §3 cells populated for AI_Act and GDPR clauses.

### Regression tests
- CRA `Art13_Manufacturers.md` still parses to 37 clauses with `instances[0].label="POLY"` for CRA-CL14.
- DORA clauses still populate `instances[]` (73 clauses had instances pre-CORR-078).
- NIS2 clauses still parse (53 clauses).

### Integration
- Run `PYTHONPATH=src python -m scripts.preprocess build` from scratch.
- Verify `preproc_out/regulation/AI_Act/articles/Art_3.json` has `source_role="out_of_scope"` and `security_objectives=["SO-AI_Act-013"]` (via top-level OR inner union).
- Verify `preproc_out/entities/clauses/_root/GDPR/GDPR-RT01.json` has `type="data-subject-facing"`, `title="Transparency modalities"`, `instances[0].label="VAG"`.
- Verify `docs/visualization/regulation_chain.html` §2 has ~13 AI_Act rows with `#SOs > 0`; §3 has 4 columns with populated cells.

### CI gates
- `bash .hooks/ci-pipeline-inputs.sh`
- `bash .hooks/ci-frameworks.sh`
- `ruff check src/ tests/` → 27 errors (baseline)
- `pytest tests/unit/ -m "not slow" -n auto` → 28 failures (baseline infra), no new failures

---

## Risks + Rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| Regex changes break CRA/DORA/NIS2 parsers | Add regression tests BEFORE changing parsers (C13/C14 in contract) | `git revert` commit 1 |
| Schema change (`source_role`) breaks downstream consumers | Field is additive; consumers ignoring unknown fields continue to work | N/A |
| Golden regen breaks pipelines depending on golden fixtures | CORR-058 gate + run log with diff | Revert `tests/fixtures/pipeline_inputs_golden/` |
| `out_of_scope` filter hides useful cross-reference info | `source_role` still in JSON; only §2 rendering filters | Remove filter in build script (commit 3) |
| 4-column UX change breaks user expectations | Document change in CORR-078.md; renderer emits both single-Type (legacy) and 4-boolean if needed | Restore single column |
| `_extract_clauses_gdpr_style` rewrite loses existing data | Add test asserting GDPR clauses have `type`, `obligated_party`, `obligation_type` populated AND ≥1 instance with label | `git revert` commit 1 |

---

## Out of scope

- Renaming `AIA-Cxx` → `AI_Act-CLxx` IDs (per CORR-077 §Out of scope).
- Auditing CRA/DORA/NIS2 case CSV files.
- Rewriting `Methodology-main/00_METHODOLOGY/PREPROCESSING/` MD files.
- Migrating `regulation/<REG>/articles/Art_*.json` (per-article shards) — only `entities/articles/<REG>_Art_ *.json` is consumed by build script.
- Refreshing `taxonomy_chain.html` (separate visualization).
- LLM prompt changes.

---

**Status:** DRAFT → user approval → ANCHORED → Generator implementation begins.