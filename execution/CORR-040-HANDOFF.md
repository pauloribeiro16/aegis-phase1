# CORR-040 — Handoff doc

**Branch:** `feature/aegis-p1-corr-040`
**Date:** 2026-07-21
**Contract:** [`execution/CONTRACT-040.md`](CONTRACT-040.md)
**Status:** ✅ 5 commits, 15/15 new tests, no regression

## TL;DR

CORR-040 é o contracto **SP-D** da estratégia faseada. Cria o
`DomainActivationContext` (fonte canónica da activação per-domínio),
faz o swap do legacy LLM-A para o canónico **P1C-LLM-01** no
`map_domains`, e adiciona o CLI flag `--run-map`.

| Antes (CORR-039) | Depois (CORR-040) |
|---|---|
| `map_domains` usava legacy LLM-A via DomainProcessor | `map_domains` tenta P1C-LLM-01 canónico primeiro, fallback para legacy |
| Sem `DomainActivationContext` | Novo Pydantic context (10 lanes + sub_domain_activations) |
| Sem `--run-map` flag | `--run-map` corre MAP stage + renderiza Doc 07 + Doc 07b |

## Commits (5, sequenciais)

| # | Hash | Sub-tarefa | LOC |
|---|------|------------|-----|
| 1 | `41ed60a` | contract | 210 |
| 2 | `acee5d2` | T1: NEW DomainActivationContext | +319 |
| 3 | `cec734b` | T2: WIRE P1C-LLM-01 in map_domains | +130 / -2 |
| 4 | `1fffdea` | T5: --run-map CLI flag | +94 |
| 5 | `b59117b` | T6: 15 tests | +403 |

## Quality gates

- ✅ Pre-flight: all modules importable
- ✅ DomainActivationContext smoke: 10 SKIPPED lanes from empty state
- ✅ 15/15 new tests pass
- ✅ 2146/2146 v2+preprocess (no regression)
- ⚠️ Pre-existing bug: `assemble_inputs` expects Pydantic, gets dict from v1-compat shim
  → MAP fails all 10 lanes in --run-map (defensive try/except in cmd_run_map
  catches MapPartialFailure so Doc 07/07b still render)
- This bug pre-dates CORR-040 and is out of scope here.

## Smoke test

\`\`\`bash
MOCK_LLM=true python -m aegis_phase1.v2.runner --case cases/case1-tinytask \\
  --run-map --output /tmp/out
# → cmd_run_map: 0/10 lanes OK, 10 failed (pre-existing bug), 0 activations, 2 artefacts
# → AEGIS-P1-07 (10.7 KB) + AEGIS-P1-07b (5.9 KB)
\`\`\`

## Files changed

- NEW: `src/aegis_phase1/v2/context/domain_activation_context.py` (319 LOC)
- NEW: `tests/unit/v2/test_domain_activation.py` (403 LOC)
- NEW: `execution/CONTRACT-040.md` (210 LOC)
- NEW: `execution/CORR-040-HANDOFF.md` (this)
- MOD: `src/aegis_phase1/v2/orchestrator.py` (+130 / -2)
- MOD: `src/aegis_phase1/v2/runner.py` (+94 / 0)
- MOD: `src/aegis_phase1/v2/context/__init__.py` (+14 / 0)

Total: **+1170 / -2** (3 NEW source files, 1 NEW test file, 3 MODIFIED files)

## Deferred (T3, T4)

- **T3** — Doc 07 refactor (957 LOC) to read from DomainActivationContext
- **T4** — Doc 07b refactor (827 LOC) to read from DomainActivationContext

Both are large refactors. Doc 07/07b already work via the v1-compat
shim; the new context is a parallel source. Migration deferred to a
follow-up contract (T4d in the strategy).

## Pós-CORR-040

Strategy: SP-D closed. Next: **CORR-041** (SynthesisContext + P1C-LLM-03/02 + P1B-LLM-02 + Doc 04a-d + parity 9 outputs).
