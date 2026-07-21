# Baseline snapshot — pre-CORR-036

This directory captures the state of `output/phase1/` BEFORE the strategy-fased
refactor of the v2 pipeline begins (CORR-036 → CORR-041). It is a regression
baseline, not a "good" output snapshot.

## What is in this directory

Copied from `output/phase1/` on 2026-07-21 (commit `ad1dacd`, branch
`feature/aegis-p1-corr-036`):

- `04_Company_Context_Assessment.md`
- `04a_Architecture_DataInventory.md`
- `04b_Security_Posture.md`
- `04c_ThirdParty_Landscape.md`
- `04d_Org_Roles_RACI.md`
- `05_Regulatory_Applicability.md`
- `06_Clause_Mapping_Matrix.md`
- `07_Structured_Compliance_Matrix.md`
- `07b_Proportionality_Profile.md`
- `Case_01_Phase1.xlsx`

These files were last regenerated on 2026-07-14 by the **legacy v1 pipeline**
(`src/aegis_phase1/{graph.py, subphases/, nodes/}`). They reflect the canonical
inputs in `cases/case1-tinytask/input/company/classification.yaml` (8 employees,
2M EUR, MICRO scale) — the v1 pipeline was always reading classification.yaml
correctly. The `phase1_ontology.yaml` drift (50/5M) was a stale-data bug that
only affected human reviewers and metadata cross-checks, not the actual output
generation (which read classification.yaml directly).

## Why this baseline is useful

The v2 pipeline (`src/aegis_phase1/v2/runner.py`) is currently degraded:
the MAP stage fails with "ontology empty for domain" because the v2 loaders
do not yet honor the legacy `phase1_ontology.yaml` location used by v1
(`cases/<case>/00_COMMON/phase1_ontology.yaml`). This is **expected** — it is
the very thing CORR-037 (SP-A) is going to fix.

When CORR-037+ refactor the v2 loaders to read `preproc_out/` JSON directly
and use canonical wiring, the outputs they generate should be **semantically
equivalent** to this baseline (against the reference at
`Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`). This
snapshot provides a measurable regression target for that diff.

## What about the MOCK_LLM v2 run?

`logs/phase1/baseline_corr036_run.log` records the attempt:

```
MOCK_LLM=true python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-all
```

Outcome: STAGE 1 (MAP) aborted — 10/10 domains failed with
"ontology empty for domain, falling back to company_context.applicable_regs".
No stage 1b/1c outputs were produced. This is the v2 degraded state and is
the reason this baseline contains v1 outputs (not v2 outputs) — v2 is
incapable of producing outputs at this commit.

## How to use this baseline for future diffs

```bash
# After CORR-041 (final contract in the strategy), once v2 produces real
# outputs again, compare semantic content:
diff -ru \
  output/phase1/baseline_pre_corr036/ \
  output/phase1/ \
  | head -200
# Expected: small semantic deltas (phrasing, ordering) — but no factual
# changes to applicability, clauses, or compliance assignments.
```

## Limitations

- The xlsx (`Case_01_Phase1.xlsx`) is a binary snapshot; semantic diff must
  be done at the YAML/MD level, not the xlsx level.
- The legacy v1 outputs were generated against a different prompt set
  (PROMETH) and a different case-context loader. The semantic delta against
  the v2-prompted outputs in CORR-041 may be larger than expected purely
  from the prompt/library migration, not from the data-correction
  introduced in CORR-036.
- This snapshot should be considered a **transitional artifact**, not a
  long-lived reference. Once CORR-041 lands and v2 produces stable outputs,
  this directory can be archived or removed.
