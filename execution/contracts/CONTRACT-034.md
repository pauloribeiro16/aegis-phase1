# CONTRACT — AEGIS-P1-CORR-034: DomainAnalysis pair granularity (D-XX.Y parity with DeepAnalysis)

**Contract ID:** AEGIS-P1-CORR-034
**Date:** 2026-07-21
**Planner:** Orchestrator (AEGIS) + user
**Status:** APPROVED → IMPLEMENTING → VALIDATED
**Branch:** `feature/aegis-p1-corr-034`
**Trials:** 1 (deterministic regex-driven parser enrichment + new test file)

---

## Context

CORR-033 introduced DeepAnalysis pair granularity (oj_quotes_verbatim, 5 comparison axes,
scope_disjoint_test, downstream_implication, p0_notes, sr_ids_per_pair — see
`tests/unit/preprocess/test_deep_analysis_granularity.py`, 764 tests × 38 files).

The DomainAnalysis files (the **higher-level synthesis** sitting on top of DeepAnalysis) still
parsed with the v10 form: a single `block_text_raw` blob + a few legacy fields. Downstream
consumers could not query the 38 DA files with the same predicates they used on the 38 Deep
files. This contract closes that gap so both file kinds are queryable uniformly.

## Scope

Enrich the `parse_crossregulation_subdomain(...)` output for `sub_kind="domain_analysis"` with
the same per-pair granularity fields that DeepAnalysis has. Add 3 new top-level fields. Add a
20-test parametrized suite over the 38 DA files. Fix 1 latent bug surfaced by the new test
(`audit_csf_mapping.py` was using a non-recursive `glob` against a path the pipeline writes
recursively into — `preproc_out/entities/subdomains/D-XX/D-XX.Y.json`).

### Files to change

- `scripts/preprocess/parsers/narrative.py` — **extend**:
  - New helpers (CORR-PILOT-DA section, before `parse_crossregulation_subdomain`):
    - `_canonicalize_classification(raw)` — folds 5 source variants
      (`complementary` / `Complementary` / `equal` / `Equal` /
      `different-perspective` / `Different perspective` / `contradictory`)
      into 4 canonical labels.
    - `_extract_why_metadata(block_text)` — splits `**Why CLASS (qualifier)**`
      headers into (canonical_classification, qualifier, note, raw_header).
      Handles 3 separator styles: `(...)`, ` + ...`, ` for|with|when|...`.
    - `_extract_oj_quotes_from_table(block_text)` — extracts 2 per-reg rows
      from the DA pair table (col 0 = `**REG** (citation)`, col 1 = description,
      col 2 = scope). Returns list of {regulation, citation_raw, sr_id, article,
      annex, description, scope}.
    - `_extract_comparison_sections_domain(block_text, reg_a, reg_b)` — builds
      a 2-axis comparison: `obligation` (col 1) + `scope` (col 2).
  - Extend `parse_crossregulation_subdomain` pair-extraction block to call
    the new helpers and add the per-pair fields:
    `why_qualifier`, `why_note`, `oj_quotes_verbatim`, `comparison_sections`,
    `scope_disjoint_test`, `downstream_implication`, `p0_notes`, `sr_ids_per_pair`.
  - Add top-level fields: `classification_distribution` (Counter of the 4
    canonical labels), `downstream_implication_top` (H4 "Downstream
    implication" section), `sr_cross_validation` (H4 "SR cross-validation"
    section).
  - Add `_extract_h4_section` helper for H4-section extraction (the
    Downstream implication and SR cross-validation are H4 sections, not
    bold-inline lines like in Deep).
  - Update `enrich_pair_entity` to copy the 6 new DA fields into the
    enriched pair entity.
- `tests/unit/preprocess/test_domain_analysis_granularity.py` — **NEW**:
  20 parametrized tests × 38 DA files = 760 tests + 9 fixture tests
  (sole-authority, high-density, contradiction sanity) = **846 total tests
  pass**.
- `scripts/preprocess/audit_csf_mapping.py` — **fix 1-line bug**:
  `subdomains_dir.glob("D-*.json")` → `subdomains_dir.rglob("D-*.json")`
  (the pipeline writes shards in sub-dirs `preproc_out/entities/subdomains/D-XX/`,
  not flat; the audit was returning 0 subdomains after the build).

### Why the canonicalization matters

The MD source uses **6 different spellings** of the 4 valid verdicts:

| Source spelling              | Canonical form            |
|------------------------------|---------------------------|
| `complementary`              | `Complementary`           |
| `Complementary`              | `Complementary`           |
| `equal`                      | `Equal`                   |
| `Equal`                      | `Equal`                   |
| `different-perspective`      | `Different perspective`   |
| `Different perspective`      | `Different perspective`   |
| `contradictory`              | `Contradictory`           |

`scripts/preprocess.parsers.narrative._DA_CLASS_CANONICAL` is the source of
truth. Any new verdict format added to source MDs must update this map.

### Why the scope_disjoint verdict is derived

DA files do not have a dedicated `**Scope-disjoint test:**` section (Deep does).
The verdict is **derived** from the canonical classification via this map:

| Classification        | Scope-disjoint verdict | Note                                                 |
|-----------------------|------------------------|------------------------------------------------------|
| Complementary         | Y                      | They co-exist in scope                                |
| Equal                 | Y                      | Same scope                                            |
| Different perspective | N                      | Scope-disjoint by definition                          |
| Contradictory         | Conditional            | Scope overlaps but obligation conflicts — binding-procedure applies |

## Decisions

- **Reuse the DeepAnalysis field names verbatim** so consumers can read both
  file kinds with the same predicates. (Deep has 5 axes; DA has 2 — that's the
  only structural difference, and it's expected: DA is a higher-level synthesis
  without the 5-axis breakdown that DeepAnalysis has.)
- **Scope-disjoint verdict is derived, not extracted.** No dedicated
  section in DA — the classification IS the verdict source.
- **`oj_quotes_verbatim.verbatim`** holds the description cell (synthesized
  OJ quote), not a blockquote. DA files have no blockquoted articles —
  the table description IS the synthesis.
- **`comparison_sections` has 2 axes (`obligation`, `scope`)** not 5
  (DeepAnalysis has `scope`, `trigger`, `threshold_timeline`, `recipient`,
  `content_template`). The DA pair table has only 2 data columns, so 2
  axes is the maximum that can be mechanically extracted.

## Quality gates (all PASS)

- `pytest tests/unit/preprocess/test_domain_analysis_granularity.py` →
  **846/846 passed** (20 × 38 = 760 parametrized + 9 fixture + 9 standalone
  = 846, including D-05.4 and D-06.2 sole-authority cases)
- `pytest tests/unit/preprocess/test_deep_analysis_granularity.py` → 764/764 (zero regression)
- `pytest tests/unit/preprocess/ tests/unit/workflow/ tests/unit/nodes/`
  → **1797/1797 passed**
- `python -m scripts.preprocess build` → **BUILD OK** (1082 shards)
- `python -m scripts.preprocess.audit_csf_mapping` → 38 subdomains, 0 BROKEN
  (was 0 subdomains, 0 BROKEN before the rglob fix)
- `python -m scripts.preprocess.audit_so_sr_coherence` → Coverage
  **full=282, partial=0, unresolved=0** (CORR-030 invariant preserved)
- `bash .hooks/ci-frameworks.sh` → OK
- `bash .hooks/ci-csf-frozen-list.sh` → OK (106 CSF 2.0 subcategories)

## Stats

- **38 DA files** processed (10 macro-domains; D-08 and D-10 have 3 sub-domains each).
- **186 pairs** total (canonicalized) — distribution:
  - Complementary: 125 (incl. lowercase variants)
  - Contradictory: 12
  - Equal: 16 (incl. lowercase)
  - Different perspective: 33
  - (D-05.4, D-06.2: 0 pairs each — sole-authority)
- **372 verbatim OJ quotes** extracted (2 per pair × 186 pairs).
- **372 comparison sections** (2 axes × 186 pairs).
- **186 scope_disjoint_test** entries (derived from classification).
- **186 downstream_implication** entries (per-pair Why note snippet).
- **38 file-level `classification_distribution` counters** (top-level).
- **38 file-level `downstream_implication_top`** (H4 sections).
- **38 file-level `sr_cross_validation`** (H4 sections).

## What was NOT done

- **No Layer 2/3 reasoning** — this is mechanical regex-driven extraction,
  not LLM synthesis. The `why_meta.note` text is preserved verbatim
  (zero-loss invariant).
- **No file `TEMPLATE_crossreg_brief.md`** was touched.
- **No other parser** was enriched — only the cross-regulation DA path.
