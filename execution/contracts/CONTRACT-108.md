---
contract: CONTRACT-108
title: CORR-108 — Parser P1C-01 dual-shape (unblock REDUCE-LLM end-to-end)
status: ACTIVE
created: 2026-09-02
author: opencode (MiniMax-M3)
branch: feature/aegis-p1-corr-108-p1c01-parser
scope: 1 source file + 1 model + 1 test file + 1 fixture
depends_on: CORR-074 (parser registry), CORR-105 (eval framework)
---

# CORR-108 — Parser P1C-01 dual-shape

## Problem (confirmed across 4 scout runs + qwen3.8 run-all)

Every non-M3 model produces substantive P1C-01 content (qwen3.5/3.8,
granite, nemotron, muse all emit pair verdicts with predicates and
references), but the code cannot extract it into the structured
`sub_domain_activations` shape that the downstream `_parse_sub_domain_activations`
needs to populate `aggregated_activations`. As a result, REDUCE-LLM gets
an empty input and skips; the pipeline dies after MAP.

Two observed output shapes:

**Shape A (M3 canonical, never observed in non-M3):**
```
## Sub-domain Activations
### D-01.1
- sub_domain_id: D-01.1
- reg_pair: [GDPR, CRA]
- company_scope_verdict: APPLICABLE
- regulatory_baseline_relationship: SAME
- layer0_refs: [SubDomains/D-01_.../D-01.1.md §1 CRDA]
```

**Shape B (qwen3.5/3.8, granite, nemotron, muse — consistent across runs):**
```
## Pair classifications
- D-01.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. ... (predicate text)

## Findings
- D-01.1 (Data at Rest Encryption): applicable=YES. scope_overlap=Y.
  applicable_regulations=[GDPR, CRA]. (...) layer0_refs: SubDomains/D-01...
```

The existing `GenericMarkdownParser` accepts ANY `## Section` headers,
so it returns OK, but the orchestrator reads `parsed["sub_domain_activations"]`
which is empty — Shape B never produces that key.

## Fix (code only — Methodology-main untouched)

1. **`P1CLLM01Output`** (new Pydantic model in `state.py`): envelope +
   `## Status` + `## Sub-domain Activations` + raw `sections` blob.
2. **`P1CLLM01Parser`** in `_archive/corr061/markdown_parser.py`: reads
   Shape A directly AND Shape B by:
   - parsing `## Pair classifications` bullets (regex `- D-XX.Y : REG ↔ REG`)
     into `(sub_domain_id, reg_pair, verdict_text)`
   - parsing `## Findings` bullets (regex `- D-XX.Y (…): applicable=YES…`)
     to lift `layer0_refs`, `applicable_regulations`, predicate
   - merge by `sub_domain_id` → emit canonical `sub_domain_activations`
   - verdict mapping: `OVERLAP_CONFIRMED/YES` → APPLICABLE;
     `NOT_IN_SCOPE/NO` → NOT_APPLICABLE; else INDETERMINATE
3. Register in `MARKDOWN_PARSERS` (replace generic for P1C-01).
4. Tests: stdlib-only; one fixture from the real qwen3.8 run-all section
   + one canonical fixture; assert count + ids + veredicto + refs.

## Acceptance

1. `pytest tests/unit/scripts/test_corr108_p1c01_parser.py` → 6+ tests PASS.
2. Running the new parser over `tests/fixtures/p1c01/qwen38_section.md`
   extracts 10+ `SubDomainActivation` records (was 0).
3. The downstream `_parse_sub_domain_activations` accepts the new parser's
   output shape unchanged (no consumer changes).
4. `bash .hooks/ci-frameworks.sh` OK; ruff clean.

## Out of scope

- Methodology-main (stable pin)
- Changing REDUCE-LLM skip behaviour for transformers (CORR-106 separate)
- Renderers (they already work on raw markdown via `sections` dict)
- Full run-all on Deucalion for the 4 models (user's choice)

## Risks

| Risk | Mitigation |
|---|---|
| Shape B parsing is brittle if a model changes its bullet style | Tests assert on the canonical Shape A AND the observed qwen3.8 Shape B; if a 5th model emits a new style, the test suite catches it before any production run breaks |
| Adding a 6th section model (P1C-02/03) needs a similar parser | Deferred — same approach (one section-specific parser per spec); not in this contract |
| Orchestrator cache key changes break consumer | Don't change shape of `sub_domain_activations` returned by the parser — only add fields downstream code already handles |