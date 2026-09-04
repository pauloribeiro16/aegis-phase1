---
contract: CONTRACT-109
title: CORR-109 — Doc 05 §9 Per-Article Breakdown (gold-aligned, deterministic)
status: ACTIVE
created: 2026-09-02
author: opencode (MiniMax-M3)
branch: feature/aegis-p1-corr-109-doc05-section-9
scope: 1 source file + 1 case YAML + 1 model + 2 test files + 1 contract
depends_on: CORR-108 (parser), Methodology-main (gold clause_mappings)
problem: |
  The gold Doc 05 (Methodology-main/02_CASES/Case_01_TinyTask_SaaS/
  01_PHASE1_CONTEXT_RICH/05_Regulatory_Applicability.md §9) contains
  a 54-row per-article table (GDPR-C01..C28 + CRA-C01..C26) mapping
  every clause to its sub-domain, obligated party, verification
  criteria, evidence type, risk if not met, and maturity (cur → tgt).

  The v2 pipeline never produced this table:
    * The v2 PreprocCatalogLoader builds a derived clause_mappings
      list without per-article detail (article, description,
      obligated_party).
    * The Doc 05 renderer reads from state['ontology']['clause_mappings']
      and emits nothing for §9.
  Reviewers comparing the pipeline-produced Doc 05 against the gold
  flagged "missing content" because §9 was absent.

approach: |
  1. CASE-TASK-OWNED DATA: 54 gold rows ported from
     Methodology-main/02_CASES/Case_01_TinyTask_SaaS/00_COMMON/phase1_ontology.yaml
     into cases/case1-tinytask/context/phase1_ontology.yaml under
     the ``clause_mappings`` key. The case-team owns this file (gold
     read-only), so the canonical source moves with the case.

  2. WIRING: Phase1Orchestrator gains `_load_clause_mappings_from_case`
     that reads cases/<case>/{context,00_COMMON}/phase1_ontology.yaml
     and stashes the rows under `state['raw_clause_mappings']`. The
     v1 ontology shim (`_build_ontology_shim`) now exposes the same
     key for legacy consumers. Missing YAML or missing key produces
     an empty list (graceful).

  3. RENDERER: Doc 05 picks up `_section_9_per_article_breakdown`
     between §7 and §8. Deterministic, no LLM call. Renders 4
     source-grade columns (Article / Topic / Sub-Domains / Obligated
     Party), a per-regulation stats summary, and a footnote pointing
     to the methodology-owned 07c Appendix A for the derived
     SSDF/SAMM columns. Empty state emits a one-line notice instead
     of a broken empty table.

  4. SORT: Within each regulation, articles sort numerically. The
     regulation order is GDPR → CRA → NIS2 → DORA → AI Act (matches
     the §3.1..§3.5 layout).

files_added:
  - src/aegis_phase1/v2/output/doc_05.py::_section_9_per_article_breakdown
  - src/aegis_phase1/v2/orchestrator.py::_load_clause_mappings_from_case
  - tests/unit/v2/output/test_doc_05_section_9.py (7 tests)
  - tests/unit/v2/test_raw_clause_mappings_wiring.py (2 tests)
  - execution/contracts/CONTRACT-109.md
files_modified:
  - cases/case1-tinytask/context/phase1_ontology.yaml (54 clause_mappings)
  - src/aegis_phase1/v2/output/doc_05.py (section list in `render_doc_05`)
  - src/aegis_phase1/v2/orchestrator.py (`load()` + `_build_ontology_shim`)
accept: |
  * tests/unit/v2/output/test_doc_05_section_9.py: 7/7 PASS
  * tests/unit/v2/test_raw_clause_mappings_wiring.py: 2/2 PASS
  * tests/unit/ -m "not slow": 0 regressions
  * ruff check (changed files): All checks passed
  * smoke run deterministic-only: §9 renders 54 rows in /tmp/p1-runall
risks: |
  * §9 deliberately does NOT synthesise Verification Criteria,
    Evidence Type, Risk, Maturity columns because those live in the
    methodology-authored Doc 07c Appendix A (human SSDF/SAMM
    assessment). The renderer footnote names Doc 07c as the source.
  * If cases lose the clause_mappings key, §9 emits a one-line
    "_no per-article data_" notice instead of a broken table.
  * The sort key `_REG_NAME_FROM_ID` is alphabetised by short
    name (GDPR before CRA). If a new regulation gets a new
    prefix (e.g. "REG-DGA"), the helper needs an entry there.
---

# CORR-109 — Doc 05 §9 Per-Article Breakdown (gold-aligned, deterministic)

> See YAML frontmatter for the scope, files, and acceptance criteria.

## What changed (plain language)

* The 54-article table that the gold Doc 05 §9 shows for **Case 01
  TinyTask** now renders from the pipeline too. The data lives in
  the case-owned YAML (``cases/case1-tinytask/context/phase1_ontology.yaml``);
  the renderer reads it during the LOAD stage.

* **§9 columns**: Article, Topic, Sub-Domains, Obligated Party —
  the four columns whose source is the case YAML. The other two
  columns from the gold (Verification Criteria, Evidence Type,
  Risk, Maturity) come from Doc 07c, which the pipeline does not
  generate; §9 shows `—` for those + a footnote pointing reviewers
  to Doc 07c.

* **Missing data**: if the case YAML lacks ``clause_mappings``,
  §9 emits a one-line notice — no broken empty table.

* **Run-all on Deucalion** (next step, user-authorised): the
  clusterside code needs the new doc_05.py + orchestrator.py +
  case ontology before the next run; we will `scp` the three
  files and submit `examples/deucalion/run-qwen38-full.sbatch`
  with `qwen3.8:27b`.
