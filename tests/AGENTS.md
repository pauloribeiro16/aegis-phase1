# AGENTS.md — tests/

**Purpose:** Guidance for AI agents writing/running tests.
**Nearest file wins:** this file overrides `../AGENTS.md` for anything
in `tests/`. The src/ sub-AGENTS files (especially `v2/`) cover
code-specific guidance.
**Last Updated:** 2026-07-28 (post-CORR-072 hierarchical split)

---

## Quick context

```
tests/
├── conftest.py                  # Shared fixtures (minimal_state, case1_path, mock_llm)
├── unit/                        # AAA pattern, fast, no services
│   ├── v2/                      # orchestrator + output renderers
│   ├── prompts_v2/              # PROMPTS library
│   ├── preprocess/              # ID normalization, CSF audit
│   └── workflow/, nodes/        # v1 legacy (read-only)
├── integration/                 # End-to-end (skipped without services)
└── fixtures/
    └── pipeline_inputs_golden/  # CORR-070 input contract
        ├── _schema.json
        └── case{1,2,3}-*/      # per-case golden files
```

## Critical rules (specific to this folder)

- **AAA pattern (Arrange-Act-Assert), dict-based state.** No fixtures
  that return Pydantic models — use plain dicts so v1/v2 compat is easy.
- **`mock_llm` fixture from `conftest.py`** handles MockInvoker + script
  payloads. For a new spec, add a script entry to `_default_ok_response`
  in `src/aegis_phase1/v2/llm.py`.
- **Don't mock what you don't own.** Mock `invoker.invoke`, not
  `ChatOllama`/`ChatMinimax` directly.
- **Regression tests are mandatory** for any bug fix. CORR-072 added
  `tests/unit/v2/output/test_doc_04_stakeholder_leakage.py` — it caught
  the cross-case stakeholder leakage.
- **`test_inputs_size_within_budget` is soft-warn only.** Don't add hard
  asserts on payload size (per user preference: no ornamental thresholds).

## File-scoped commands

```bash
# Test this folder only (file-scoped, fast feedback first)
PYTHONPATH=src python -m pytest tests/unit/v2/output/test_doc_04_stakeholder_leakage.py -v

# Full unit suite (skip slow markers via -m "not slow")
PYTHONPATH=src python -m pytest tests/unit/ -m "not slow" -q

# v1.2 smoke test (requires Ollama with gemma4:e2b — pre-existing failure)
PYTHONPATH=src python -m pytest tests/unit/prompts_v2/test_smoke_e2e.py -v

# Verify test COLLECTION (not just execution summary — see Validator Integrity Rule in root AGENTS.md)
PYTHONPATH=src python -m pytest tests/unit/v2/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError"

# Pipeline input contract gate
bash .hooks/ci-pipeline-inputs.sh

# Regenerate pipeline_inputs_golden (when contract changes intentionally)
python scripts/dev/regenerate-pipeline-inputs-golden.py
```

## Common pitfalls

- **`pyproject.toml` `--timeout=30` killer** is missing in
  `shared-venv-root/`. Use `-o "addopts=-ra --tb=short"` to override
  in that env, or activate `../shared-venv/bin/activate` if available.
- **Smoke test fails on `gemma4:e2b`** with `markdown_parse_error` —
  this is the model, not the test. Pre-existing.
- **`tests/unit/v2/test_layer_b_callback_corr012.py`** fails 4/4
  without Ollama. Pre-existing infra dependency.
- **`case1_path` fixture** points to `cases/case1-tinytask/`. New tests
  should use `case1_path` / `case2_path` rather than hardcoding.

## Patterns to follow

**GOOD — regression test for a fix:**

```python
def test_omnibank_stakeholder_does_not_inherit_organisation() -> None:
    """CORR-072 regression: TinyTask org must NOT leak into case 3."""
    sh = {"id": "SH-01", "role": "CEO", "organisation": "-", "contact": "-",
          "influence": "-", "interest": "-"}
    out = _augment_influence(dict(sh))
    assert out["organisation"] == "-"
```

**BAD — testing implementation details (brittle):**

```python
# Anti-pattern: asserts on private helpers rather than observable output
assert _augment_influence.__name__ == "_augment_influence"
```

## Skills (Activate on Demand)

| Skill | When to use in this folder |
|-------|------|
| `sprint-contract` | When adding a test contract (e.g. regression suite for a bug fix) |
| `code-review` | Before merging a new test contract or parametrized sweep |
| `python-best-practices` | When refactoring test patterns (AAA, fixtures, parametrize) |
| `context-checkpoint` | Context >70% during long test refactor sessions |
| `agents-md-writer` | Only when updating this very file |

## See also

- `../AGENTS.md` (root) — git workflow, branch policy, NIST CSF
- `src/aegis_phase1/v2/AGENTS.md` — orchestrator + output renderers
- `src/aegis_phase1/prompts_v2/AGENTS.md` — PROMPTS library tested here
- `tests/fixtures/pipeline_inputs_golden/_schema.json` — input contract
- `execution/CORR-072-RUN-LOG.md` — `scripts/dev/verify-corr072-fixes.py` (pattern for isolated testing)
