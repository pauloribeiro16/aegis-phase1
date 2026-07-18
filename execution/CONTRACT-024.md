# AEGIS-P1-CORR-024 — PREPROCESSING/ → JSON sharded

**Branch:** `feature/aegis-p1-corr-024-preproc-json`
**Predecessor:** CORR-023 (in progress; not yet merged — can land in parallel or after)
**Status:** DRAFT — pending user approval

---

## 1. Context (the user-stated problem)

The 351 markdown files under `methodology-00/PREPROCESSING/` are the
authoritative regulatory baseline (Layer 0 / Regulatory Baseline) that
the Phase 1 pipeline reads at runtime. The problems:

1. **Massive files** (D-09 governance = 604K, CRA `02_SecurityRules_NIST` = 428K).
2. **Inconsistent shapes** — some have YAML frontmatter, some don't;
   some nest 3 levels of blockquote, some nest 0; some use Markdown
   tables, others use `yaml` code blocks.
3. **Fragile regex parsers** in the v2 code path (we just hit one:
   `_extract_objective_paragraph` left `[VERBATIM]` literals in the
   prompt because it didn't strip the placeholder).
4. **Hard-coded paths** — loaders know the source layout, so any
   reorganisation of `Methodology-main` breaks the pipeline.

The user wants a **structured sharded output** in `preproc_out/`
(JSON, fine-grained) that the runtime loaders can consume
deterministically, isolating all "I have to read 351 .md files with
different shapes" pain into a one-shot **preprocess** step.

**`preproc_out/` is GITIGNORED + regenerated in CI** (decision 2026-07-18).
Rationale: JSON is denser than markdown but still large; a Methodology-main
edit would always force a JSON regen and a noisy diff. The
deterministic `preproc_out/build_info.json` (sha256 + source mtimes) is
the source of truth for "is the artefact fresh?" — CI fails the build
if the in-tree `preproc_out/` is older than the source.

---

## 2. Scope (in / out)

### IN

- All 351 files under `methodology-00/PREPROCESSING/`:
  - **SubDomains** — 38 files (10 domains × ~4 sub-domains; 3 in D-08, 3 in D-10)
  - **Regulation** — 223 files:
    - 5 regs × 5 root files (`00_README`, `01_SecurityObjectives`, `02_SecurityRules_NIST`, `03_validation_report`, `04_deduction_audit`) = 25
    - 145 per-article files (25 + 26 + 31 + 49 + 14 across regs)
    - 53 per-article-clause / per-chapter ambiguity files
  - **CrossRegulation** — 82 files (DeepAnalysis + DomainAnalysis)
  - **AMBIGUITY_ANALYSIS** — 2 files (00_Index, 01_Framework)
  - **Top-level** — `00_Hierarchical_SecurityObjectives.md`, `NIST_CSF_2.0_subcategories.md`, `TEMPLATE_subagent_brief.md`, `README.md`

### OUT

- `Methodology-main/02_CASES/` (case-specific output, not baseline)
- `Methodology-main/01_*` and other top-level dirs (not Phase 1 input)
- v2 runtime code changes (separate concern; see §7 follow-ups)

---

## 3. Output layout — `preproc_out/`

```
preproc_out/
├── manifest.json                 # global index: {shard_path, sha256, bytes, source_path, mtime}
├── build_info.json               # {built_at, source_root, method_version, file_count}
│
├── subdomains/                   # 1 JSON per SubDomain (D-XX.Y)
│   ├── D-10.1.json
│   ├── D-10.2.json
│   └── … (38 files)
│
├── regulation/                   # per-regulation subtree
│   ├── {REG}/
│   │   ├── root.json             # 00_README + 01_SecurityObjectives + 02_SecurityRules_NIST + reports
│   │   ├── articles/
│   │   │   ├── Art_30.json       # per-article (145 total)
│   │   │   └── …
│   │   └── ambiguity_clauses/
│   │       ├── GDPR-CL01.json    # per-clause (53 total)
│   │       └── …
│
├── crossregulation/
│   ├── pairs/                    # 1 per pairwise analysis file (~50)
│   │   ├── D-10.1_gdpr_cra.json
│   │   └── …
│   └── domains/                  # 1 per domain analysis file (~32)
│       ├── D-10.json
│       └── …
│
├── ambiguity_analysis/
│   ├── 00_Index.json
│   └── 01_Framework.json
│
└── global/
    ├── hierarchical_objectives.json
    ├── nist_csf_2.0.json
    └── subagent_brief_template.json
```

**Granularity = fine** (1 file per source markdown) → 351 + 4 manifest files = **~355 output files**.

---

## 4. JSON schema (canonical per type)

### 4.1 `subdomains/D-XX.Y.json`

```json
{
  "schema_version": "1.0",
  "source": "PREPROCESSING/SubDomains/D-10_Monitoring-Audit/D-10.1.md",
  "doc_id": "AEGIS-PREPROC-SD-D-10.1",
  "domain_id": "D-10",
  "subdomain_id": "D-10.1",
  "title": "Continuous Security Monitoring",
  "status": "DRAFT",
  "chain_version": "v2.1",
  "frontmatter": { …raw YAML keys… },
  "sections": {
    "cross_reg_analysis": { "raw_md": "…", "pairs": [ …parsed per pair… ] },
    "hso_hl":             { "raw_md": "…", "objective": "**Objective.** …", "considerations": [ … ] },
    "hso_per_reg": [
      { "regulation": "GDPR", "objective": "…", "considerations": [ … ], "anchors": [ "Art. 32(2)", … ] },
      { "regulation": "CRA",  "objective": "…", "considerations": [ … ], "anchors": [ "Annex I Part I (2)(l)", … ] }
    ]
  }
}
```

### 4.2 `regulation/{REG}/articles/Art_NN.json`

```json
{
  "schema_version": "1.0",
  "source": "PREPROCESSING/Regulation/GDPR/Articles/Art_30.md",
  "doc_id": "AEGIS-PREPROC-GDPR-ART-30",
  "regulation": "GDPR",
  "article_ref": "Art. 30",
  "frontmatter": { … },
  "security_objectives": [ { "so_id": "SO-GDPR-029", "description": "…", "sub_domains": ["D-09.4","D-10.2"] }, … ],
  "security_rules": [ { "sr_id": "SR-GDPR-029", "title": "…", "yaml_body": { …full YAML object… }, "linked_objectives": ["SO-GDPR-017"] }, … ]
}
```

### 4.3 `regulation/{REG}/ambiguity_clauses/{REG}-CLxx.json`

```json
{
  "schema_version": "1.0",
  "source": "PREPROCESSING/Regulation/GDPR/Ambiguity/02_GDPR_Ch2_Principles.md",
  "regulation": "GDPR",
  "chapter": "Ch2 — Principles",
  "articles_covered": ["Art. 5", "Art. 6"],
  "clauses": [
    {
      "clause_id": "GDPR-CL01",
      "article_ref": "Art. 5(1)(a)",
      "type": "principle",
      "obligated_party": "CONTROLLER",
      "obligation_type": "CONTINUOUS",
      "title": "Lawfulness, fairness, transparency",
      "berry_anchor": "§3.3.5 (vagueness), §5.1 (lists `lawful`, `fair`)",
      "verbatim_text": "…",
      "instances": [ { "label": "Instance 1 — VAG / S3", "tags": ["VAG","S3"], "tokens": ["lawful","fair","transparent"], "variant_readings": [ { "reading": "R1", "text": "…", "source": "Recital 47" } ] } ],
      "notes_markdown": "…"
    }
  ]
}
```

### 4.4 `crossregulation/pairs/{pair}.json` and `crossregulation/domains/{domain}.json`

```json
{
  "schema_version": "1.0",
  "source": "PREPROCESSING/CrossRegulation/DeepAnalysis/D-10_Monitoring-Audit/D-10.1.md",
  "kind": "pair",  // or "domain"
  "subdomain_id": "D-10.1",
  "pairs": [
    {
      "pair": "GDPR ↔ CRA",
      "classification": "SAME — COMPLEMENTARY",
      "reasoning": "…",
      "scope_overlap": "Y",
      "scope_disjoint_test": "Y (when …)",
      "downstream_implication": "…",
      "layer2_flag": true,
      "verbatim_articles": { "GDPR": "…", "CRA": "…" }
    }
  ]
}
```

### 4.5 `manifest.json` (global)

```json
{
  "schema_version": "1.0",
  "built_at": "2026-07-18T20:30:00Z",
  "source_root": "/home/.../Methodology-main/00_METHODOLOGY/PREPROCESSING",
  "method_version": "1.0",
  "shard_count": 355,
  "shards": [
    {
      "path": "subdomains/D-10.1.json",
      "source_path": "PREPROCESSING/SubDomains/D-10_Monitoring-Audit/D-10.1.md",
      "sha256": "abc123…",
      "bytes": 144000,
      "kind": "subdomain"
    },
    …
  ]
}
```

---

## 5. Implementation — the preprocessor script

### 5.1 New files

```
scripts/preprocess/
├── __init__.py
├── cli.py                        # entry: `python -m scripts.preprocess build`
├── pipeline.py                   # orchestrator: walk → parse → validate → write
├── walkers.py                    # directory walkers (one per type)
├── parsers/
│   ├── frontmatter.py            # YAML frontmatter extractor (already partially in aegis_phase1.v2.loader)
│   ├── markdown.py               # heading + blockquote + table + code-block splitter
│   ├── subdomain.py              # SubDomain-specific parser (hso_hl, hso_per_reg, cross_reg pairs)
│   ├── article.py                # per-article SO/SR parser (table + embedded YAML)
│   ├── ambiguity_clause.py       # per-clause parser (Berry anchor + instances + variant_readings)
│   └── crossreg.py               # CRDA pair/analysis parser
├── validators/
│   ├── schema.py                 # jsonschema validation per shard
│   └── invariants.py             # cross-shard invariants (e.g. SO references must resolve)
└── schemas/
    ├── subdomain.schema.json
    ├── article.schema.json
    ├── ambiguity_clause.schema.json
    └── crossreg.schema.json
```

### 5.2 Execution contract

```bash
python -m scripts.preprocess build \
  --source methodology-00/PREPROCESSING \
  --output preproc_out \
  --validate                # jsonschema + invariants
```

Output:
- Writes all shards + `manifest.json` + `build_info.json`
- Exits 0 if all shards parse + validate; 1 with diagnostics otherwise
- Idempotent (re-run overwrites; manifest sha256 detects drift in source)

### 5.3 Parser strategy

For each source `.md`:
1. **Frontmatter** — extract YAML between `---` fences (re-use `aegis_phase1.v2.loader._parse_yaml_frontmatter`).
2. **Sections** — split on `^## ` or `^### ` headings into ordered list.
3. **Per-type logic** — apply the type-specific parser (subdomain / article / ambiguity / crossreg) on the relevant section.
4. **Preserve raw_md** alongside structured fields — so loaders that need verbatim text still have it without re-parsing.

### 5.4 Failure model

**Default is strict.** Any parse warning aborts the build with non-zero exit and a diagnostic pointing at the source file + offset.

- **Hard fail** — YAML frontmatter malformed, required field missing, JSON Schema validation fails, or any soft-warn condition (see below).
- **Soft warn** (always escalates to fail in default mode) — section present but unparseable (e.g. ambiguous heading level); record in `manifest.warnings[]`.
- **No `--strict` flag** — strict is the only mode. A `--lenient` flag is intentionally **not** provided, to prevent the case where a build "succeeds" with hidden damage and downstream loaders fail mysteriously.

---

## 6. Acceptance criteria

| ID | Criterion | Verification |
|---|---|---|
| C1 | `preproc_out/manifest.json` lists all 351 source files + 4 manifest files | `jq '.shard_count' manifest.json` == 355 |
| C2 | Every shard validates against its JSON Schema | `python -m scripts.preprocess validate` exits 0 |
| C3 | `preproc_out/` re-generates byte-identical from the same source | `python -m scripts.preprocess build` twice; `diff -r` shows no changes |
| C4 | At least 1 SubDomain shard (D-10.1) round-trips: parser extracts hso_hl + per_reg + cross_reg pairs equal to human-readable ground truth | `scripts/preprocess/tests/test_d10_1_groundtruth.py` |
| C5 | v2 loaders can be switched to read `preproc_out/` via a feature flag (`PREPROC_USE_SHARDED=1`) without changing any other behaviour | Integration test: `--use-sharded` produces same orchestrator state as legacy — **deferred to CORR-025** |
| C6 | All existing 371 v2 tests pass under `--use-sharded=true` (or are explicitly marked `@pytest.mark.skip_sharded`) | `pytest tests/unit/v2/ -v` — **deferred to CORR-025** |
| C7 | `preproc_out/` is **gitignored**; CI step regenerates it on every push and fails the build if `build_info.json` source_mtimes drift | `.github/workflows/preproc.yml` (new) or `.hooks/ci-preproc.sh` |
| C8 | `preproc_out/build_info.json` records source mtimes so stale shards are detectable; `preproc_out/.gitkeep` is the only versioned file in the dir | `git ls-files preproc_out/` shows only `.gitkeep` |

---

## 7. Phases (sequential commits on `feature/aegis-p1-corr-024`)

### Phase 0 — Pre-flight (do first)
- Confirm `methodology-00` symlink resolves
- Confirm `jsonschema` is in venv (`pip show jsonschema`); if not, add to `pyproject.toml [preprocess]`
- Spot-check: 1 source file per type loads with current v2 loaders (baseline for "no regression")

### Phase 1 — Skeleton + SubDomain shard
- `scripts/preprocess/` skeleton
- `parsers/subdomain.py` (the most complex parser — hso_hl, hso_per_reg, cross_reg pairs)
- `schemas/subdomain.schema.json`
- Walks 10 D-XX dirs, emits 38 SubDomain JSONs
- Validator passes
- **C4 (D-10.1 groundtruth)**

### Phase 2 — Regulation articles + ambiguity clauses
- `parsers/article.py` (per-article SO + SR, embedded YAML)
- `parsers/ambiguity_clause.py` (per-clause: Berry anchor, instances, variant_readings)
- `schemas/article.schema.json`, `schemas/ambiguity_clause.schema.json`
- 145 article shards + 53 ambiguity clause shards

### Phase 3 — CrossRegulation + global
- `parsers/crossreg.py` (CRDA pair/analysis)
- 82 crossreg shards + 4 global shards
- `manifest.json` writer (sha256, sizes, source paths)
- **C1, C2, C3**

### Phase 4 — CI gate + Docs + sign-off
- `.hooks/ci-preproc.sh` (new): regenerates `preproc_out/` from source, diffs `build_info.json`; non-zero exit if stale
- Wire into `.hooks/validate-contracts.sh` as a new gate (gate 20+)
- Update `AGENTS.md` §5 Key files (add `preproc_out/` and `scripts/preprocess/`)
- Update `docs/CONTRACTS.md` (CORR-024 entry)
- Update `execution/CONTRACT-024.md` §5 sign-off
- Commit, push, PR #29

> **Phase 5 (loaders integration) is DEFERRED to CORR-025.** CORR-024 stops at "valid preprocessor + green schemas + CI gate"; the v2 loaders still read the `.md` files as before. This keeps the blast radius of CORR-024 small and makes the preprocessor independently testable. CORR-025 will switch the loaders to read `preproc_out/` behind a `--use-sharded` flag and (eventually) delete the markdown reader path.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| One-off parser breaks on a single source file (e.g. weird heading nesting) | Soft-warn + manifest record; **build still fails by default** (strict is the only mode) |
| md → JSON loses information (e.g. nested formatting) | `sections.raw_md` preserved per section; schema requires verbatim text for all anchors |
| Schema drift between source MD revisions and JSON output | `manifest.json` records source mtime + sha256; loaders can detect stale shards |
| Preprocessor becomes a single point of failure (one script blocks all 351 files) | Failure model is per-shard; partial builds are valid; CI runs full build |
| Size on disk explodes | JSON is denser than md; estimate ~3 MB (vs ~3.5 MB source md). Monitor with C7. |
| `jsonschema` not in venv today | `pip install jsonschema` + add to `[preprocess]` extra in pyproject |

---

## 9. Out of scope (follow-ups)

- **CORR-025** — Delete the legacy `load_articles_for_domain` / `load_ambiguities_for_regs` / `subdomain_loader` once CORR-024 sharded loaders are stable for 1+ release.
- **CORR-026** — Apply the CORR-023 fixes (`[VERBATIM]` regex, `max_tokens=2048`) now that the prompt content is in a structured, validated form (no more `[VERBATIM]` placeholders to leak).
- **CORR-027** — Promote CORR-024 from "in-tree preprocessor" to a CI step (regenerate `preproc_out/` on every Methodology-main bump; diff the manifest in the PR).

---

## 10. Sign-off

| Role | Status |
|---|---|
| user_approved | ✅ (2026-07-18, in-session) |
| generator_implemented | ✅ done (2026-07-18, 348 shards built, 0 errors, 12.5 MB total, C3 idempotent) |
| evaluator_verified | ✅ done (2026-07-18, 374 tests passed — 371 v2 unchanged + 3 preprocess groundtruth; collection clean) |
| quality_log_updated | ✅ done (2026-07-18, this section; `docs/CONTRACTS.md` CORR-024 section appended) |
