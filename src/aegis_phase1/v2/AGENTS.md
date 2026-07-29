# AGENTS.md — src/aegis_phase1/v2/

**Purpose:** Guidance for AI agents working in the v2 pipeline directory.
**Nearest file wins:** this file overrides `../AGENTS.md` for anything
in `v2/`. The root file still applies to cross-cutting rules (NIST CSF,
branch policy, boundaries).
**Last Updated:** 2026-07-28 (post-CORR-072 hierarchical split)

---

## Quick context

`src/aegis_phase1/v2/` is the production pipeline (CORR-037+). It contains:

```
v2/
  orchestrator.py     # Phase1Orchestrator + run_p1b_single, run_phase_1c_map/reduce
  runner.py           # CLI entry point
  llm.py              # build_llm_invoker factory
  loader/             # PreprocCatalogLoader, CaseProfileLoader
  domain/             # per-domain filtering (CORR-040)
  reduce/             # concatenation, merge, conflict resolution
  output/             # doc_04/05/06/07/07b renderers
  context/            # ApplicabilityContext (CORR-038 source-of-truth)
  graph.py            # 18-node LangGraph StateGraph (replaces legacy v1)
```

The v1 legacy is in `src/aegis_phase1/_archive/` — read-only, do not edit.

## Critical rules (specific to this folder)

- **CORR-038 source-of-truth:** use `build_applicability_context(state)`
  (not `state.get("company_context").get("applicable_regs")` which can
  be stale — see CORR-072-2 fix in `doc_04d.py`).
- **Filters must mirror Layer 0:** `domain/filters/regs.py` and
  `domain/filters/subdomains.py` are the canonical sub-reg filters; do
  not re-implement filtering inline.
- **Output renderers are pure functions:** `output/doc_XX.py` reads
  from `state` and writes to disk. No hidden side effects.
- **LangGraph state machine:** `graph.py` is the only entry point that
  mutates `state` between phases; elsewhere treat state as read-only.
- **Sub-AGENTS applicability:** when adding fields to the
  `ApplicabilityContext` Pydantic model, also update
  `Methodology-main/00_METHODOLOGY/PREPROCESSING/` consumers (separate repo).

## File-scoped commands

```bash
# Test this folder only (fast feedback, mock LLM)
PYTHONPATH=src python -m pytest tests/unit/v2/ -v

# Test a single file
PYTHONPATH=src python -m pytest tests/unit/v2/output/test_doc_04_stakeholder_leakage.py -v

# Lint this folder
ruff check src/aegis_phase1/v2/

# Verify orchestrator/runner/llm importable
PYTHONPATH=src python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('OK')"

# Full v1.2 smoke test (requires Ollama running with gemma4:e2b — pre-existing failure)
PYTHONPATH=src pytest tests/unit/prompts_v2/test_smoke_e2e.py -v
```

## Common pitfalls

- **State mutations outside graph.py** create silent inconsistencies. Use
  helpers in `v2/context/` to add fields; never mutate state dict keys
  directly outside `orchestrator.py`.
- **`_normalize_stakeholder` returns a dict** but downstream code in
  `doc_04.py` calls `.get(field)` — passing a string crashes (see test
  `test_section_3_stakeholder_register_no_tinytask_leak_in_render`).
- **`build_applicability_context` raises if predicates are missing.**
  Wrap in try/except and fall back to `state["company_context"]` (see
  `doc_04d.py:_section_regulation_level` after CORR-072).

## Patterns to follow

**GOOD — consistent reading of applicable_regs:**

```python
from aegis_phase1.v2.context.applicability_context import build_applicability_context
app_ctx = build_applicability_context(state)
applicable = list(app_ctx.applicable_regs)
```

**BAD — reading from stale legacy field:**

```python
ctx = state.get("company_context") or {}
applicable = _attr(ctx, "applicable_regs", default=[]) or []  # can be stale
```

## Skills (Activate on Demand)

| Skill | When to use in this folder |
|-------|------|
| `sprint-contract` | When planning/refactoring v2 contracts (this folder is contract-driven) |
| `code-review` | Before merging changes touching output/ renderers (output quality matters) |
| `python-best-practices` | When refactoring Python in orchestrator.py / domain/ / reduce/ |
| `project-conventions` | When adding new domain entities (SubDomain, SO, SR), see `Methodology-main/00_METHODOLOGY/PREPROCESSING/` |
| `context-checkpoint` | Context >70% during long refactor sessions in this folder |
| `agents-md-writer` | Only when updating this very file |

## See also

- `../../AGENTS.md` (root) — NIST CSF policy, branch policy, boundaries, skills activation
- `../prompts_v2/AGENTS.md` — 5 LLM specs, PromptLoader/CatalogLoader (consumed here)
- `tests/AGENTS.md` — testing patterns, mock_llm fixture
- `execution/CONTRACT-072.md` — most recent contract affecting this folder (5 bug fixes + regression test)
- `execution/CORR-072-RUN-LOG.md` — validation log
