# AGENTS.md — src/aegis_phase1/prompts_v2/

**Purpose:** Guidance for AI agents working in the PROMPTS library.
**Nearest file wins:** this file overrides `../AGENTS.md` for anything
in `prompts_v2/`. The v2/ directory uses us heavily.
**Last Updated:** 2026-07-28 (post-CORR-072 hierarchical split)

---

## Quick context

This directory implements the **PROMPTS library** for Phase 1 v1.2
(CORR-039). It consumes PROMPTS/*.md and catalogs/*.yaml from
`Methodology-main/00_METHODOLOGY/` and exposes:

```python
from aegis_phase1.prompts_v2 import (
    PromptLoader,            # Load PROMPTS/*.md + extract YAML frontmatter
    CatalogLoader,           # Load YAML catalogs (tipo2, tipo3) + eval predicates
    Phase1LLMInvoker,        # prompt → invoke → parse → validate
    Phase1Validator,         # JSON Schema + Layer 0 citation + no-reclass check
    JSONLLogger,             # Structured logging
    RobustParser,            # 5-strategy JSON parser (handles gemma4 format)
    LLM_SPECS,               # Registry of 5 Phase 1 LLMs
)
```

The 5 canonical LLMs are:
- `P1B-LLM-01-INTERPRETATION` (per_regulation, Phase 1B)
- `P1B-LLM-02-RATIONALE` (per_regulation, Phase 1B)
- `P1C-LLM-01-OVERLAP-CLASSIFICATION` (per_domain_lane, Map)
- `P1C-LLM-02-COMPOUND-EVENT` (global_reduce, Reduce)
- `P1C-LLM-03-STRATEGIC-SYNTHESIS` (global_reduce, Reduce)

LLM-H (gap aggregation) was removed — out of Phase 1 scope (Phase 2/3).

## Critical rules (specific to this folder)

- **C1B input contract (CORR-070):** `run_p1b_single` / `run_phase_1c_map`
  / `run_phase_1c_reduce` MUST build inputs that satisfy the structural
  contract in `tests/fixtures/pipeline_inputs_golden/_schema.json`. CI
  gate: `bash .hooks/ci-pipeline-inputs.sh`.
- **Per-reg filter (CORR-071):** `run_phase_1b` applies
  `participating_regulations contains reg` before passing refs to the
  invoker. Adding a new entity? Mirror the filter pattern in
  `domain/filters/subdomains.py`.
- **RobustParser is the fallback for non-conforming output.** When
  Ollama/MiniMax produces non-JSON-Schema output, do NOT modify specs —
  extend the parser (5 strategies: json_strict, extract_markdown_block,
  extract_first_object, extract_first_array, repair_common_errors).
- **PromptLoad YAML frontmatter is the registry.** Don't add new
  `invocation_pattern` values without updating
  `Methodology-main/PROMPTS/base_system_prompt.md` enumeration.

## File-scoped commands

```bash
# Test this folder (mock LLM, fast)
PYTHONPATH=src python -m pytest tests/unit/prompts_v2/ -v

# Test semantic guard for P1B filter (CORR-071)
PYTHONPATH=src python -m pytest tests/unit/prompts_v2/test_phase1_executor.py::TestRunPhase1BPerRegFilter -v

# Verify all 5 schema loaded
PYTHONPATH=src python -c "
from aegis_phase1.prompts_v2 import LLM_SPECS
print('LLM_SPECS:', list(LLM_SPECS.keys()))
"

# Lint
ruff check src/aegis_phase1/prompts_v2/

# Regenerate pipeline-inputs golden (when contract changes intentionally)
python _regenerate_pipeline_inputs_golden.py
```

## Common pitfalls

- **`run_phase_1b` was filtering refs incorrectly before CORR-071.**
  The old code passed all 38 sub-domain refs to every LLM call,
  causing the 524KB cap to truncate catalog + # TASK. If you see
  `truncation_marker` in logs, the filter is broken.
- **`p1b_llm_01_outputs` must be wired to P1B-02** (CORR-070 Bug B).
  Forgetting this makes P1B-02 re-derive interpretations from scratch.
- **gemma4:e2b produces non-Schema output** at high rate. This is a
  pre-existing model issue, not a spec issue.

## Patterns to follow

**GOOD — per-reg filter (CORR-071):**

```python
lane_refs = [r for r in all_refs
             if isinstance(r, dict)
             and reg in (r.get("participating_regulations") or [])]
out_01 = self.invoker.invoke(SPEC_INTERPRETATION, {**inputs, "layer0_subdomain_refs": lane_refs, ...})
```

**BAD — passing all refs to every lane:**

```python
# Anti-pattern (pre-CORR-071) — payload blew past 524KB cap
out_01 = self.invoker.invoke(SPEC_INTERPRETATION, {**inputs, "layer0_subdomain_refs": all_refs, ...})
```

## Skills (Activate on Demand)

| Skill | When to use in this folder |
|-------|------|
| `sprint-contract` | When planning changes to PROMPTS spec (this folder is contract-driven) |
| `code-review` | Before merging changes to spec prompts or YAML frontmatter |
| `python-best-practices` | When refactoring the LLM invoker chain (Phase1LLMInvoker, Phase1Validator, RobustParser) |
| `project-conventions` | When adding a new LLM spec to LLM_SPECS, mirror in `Methodology-main/00_METHODOLOGY/PROMPTS/` |
| `context-checkpoint` | Context >70% during JSON Schema validation debugging |
| `agents-md-writer` | Only when updating this very file |

## See also

- `../../AGENTS.md` (root)
- `../v2/AGENTS.md` — primary consumer of PROMPTS library
- `tests/AGENTS.md` — pipeline_inputs_golden fixture conventions
- `tests/fixtures/pipeline_inputs_golden/_schema.json` — input contract schema
- `execution/CONTRACT-071.md` — CORR-071 (per-reg filter) and CORR-070 (input contract)
