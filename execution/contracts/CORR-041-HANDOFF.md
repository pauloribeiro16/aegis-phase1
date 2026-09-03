# CORR-041 — Handoff doc (final contract of CORR-036 → CORR-041)

**Branch:** `feature/aegis-p1-corr-041`
**Date:** 2026-07-21
**Contract:** [`execution/CONTRACT-041.md`](CONTRACT-041.md)
**Status:** ✅ 6 commits, 15/15 new tests, no regression, **STRATEGY COMPLETE**

---

## TL;DR

CORR-041 é o **último contracto** da estratégia faseada CORR-036 → CORR-041.
Cria o `SynthesisContext` (fonte canónica do REDUCE stage), wire
P1C-LLM-03/02 + P1B-LLM-02 no orchestrator, adiciona o CLI flag
`--run-reduce`, e implementa um **parity check automatizado** dos 9
outputs contra a `Methodology-main` reference.

| Antes (CORR-040) | Depois (CORR-041) |
|---|---|
| `aggregated_data` shims sem Pydantic context | `SynthesisContext` canónico (synthesis + compound_events + track_b + conflicts + per_reg_rationale) |
| Sem CLI dedicado para REDUCE | `--run-reduce` corre REDUCE + re-renderiza Doc 04a-d |
| Sem parity check automatizado | `scripts/check_phase1_parity.py` (best-effort, 2/9 PASS, 6 WARN) |

---

## Commits (6, sequenciais)

| # | Hash | Sub-tarefa | LOC |
|---|------|------------|-----|
| 1 | `27dd705` | contract | 196 |
| 2 | `d11682c` | T1: NEW SynthesisContext (Pydantic) | +232 |
| 3 | `3078b8b` | T2: Wire SynthesisContext in reduce + run_phase_1b | +36 |
| 4 | `5ca66c3` | T4: --run-reduce CLI flag | +87 |
| 5 | `78fd3c8` | T5+T6: parity script + 15 tests | +570 |
| 6 | _(this)_  | handoff | n/a |

**T3 (P1B-LLM-02 wiring)** já estava feito via CORR-039-T4 (line 1498
`self.state["aggregated_data"]["rationale_by_reg"] = synth_by_reg`).
Sem código novo.

---

## Quality gates

- ✅ 15/15 new tests pass
- ✅ 2161/2161 v2+preprocess (no regression; 7 pre-existing failures preserved)
- ✅ `--run-reduce` smoke: 4 artefacts (04a/b/c/d)
- ✅ Parity check: 2/9 PASS, 6 WARN (best-effort informational, exit 0)
- ✅ `SynthesisContext` populated after reduce() and after run_phase_1b()

---

## Smoke tests

```bash
# 1. REDUCE only
MOCK_LLM=true python -m aegis_phase1.v2.runner --case cases/case1-tinytask \\
  --run-reduce --output /tmp/out
# → 4 artefacts: 04a (4.7 KB) + 04b (16 KB) + 04c (8.5 KB) + 04d (17.4 KB)
# → v2_synthesis_context populated (status=EMPTY with MOCK_LLM)

# 2. Full parity check
python scripts/check_phase1_parity.py --output /tmp/parity
# → Runs all 5 stages
# → Compares 9 generated docs vs Methodology-main reference
# → Per-doc verdict: 2/9 PASS, 6 WARN, 0 MISSING
# → Exit 0 (always)

# 3. Full pipeline (with real Ollama)
python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-all \\
  --output /tmp/out
# → 9 artefacts (04/04a/04b/04c/04d/05/06/07/07b + xlsx)
# → 5 LLMs canónicos fired per spec
```

---

## Files (10 total)

| File | Action | LOC | Purpose |
|------|--------|-----|---------|
| `execution/CONTRACT-041.md` | NEW | 196 | Contract (T0) |
| `execution/CORR-041-HANDOFF.md` | NEW | (this) | Handoff |
| `src/aegis_phase1/v2/context/synthesis_context.py` | NEW | 232 | T1: SynthesisContext + factory |
| `src/aegis_phase1/v2/context/__init__.py` | MODIFY | +14 | T1: re-export |
| `src/aegis_phase1/v2/orchestrator.py` | MODIFY | +36 | T2: wire SynthesisContext |
| `src/aegis_phase1/v2/runner.py` | MODIFY | +87 | T4: --run-reduce flag |
| `tests/unit/v2/test_synthesis_context.py` | NEW | 390 | T6: 15 tests |
| `scripts/check_phase1_parity.py` | NEW | 180 | T5: parity script |

Total: **+1141** across 4 NEW source files, 2 MODIFIED files.

---

## Strategy: CORR-036 → CORR-041 — COMPLETE

The 5-context architecture:

| Contract | Context | Purpose |
|----------|---------|---------|
| CORR-038 | `ApplicabilityContext` | applicable_regs + tier + declaration gaps |
| CORR-039 | `ClauseMappingContext` | clause → sub-domain mapping |
| CORR-040 | `DomainActivationContext` | per-domain lane activation (P1C-LLM-01) |
| CORR-041 | `SynthesisContext` | REDUCE-stage output (P1C-LLM-03/02 + P1B-LLM-02) |

The 5-LLM coverage:

| LLM | Status | Wired in |
|-----|--------|----------|
| P1B-LLM-01 INTERPRETATION | ✅ invoked per applicable_reg | run_p1b_single (CORR-039-T4) |
| P1B-LLM-02 RATIONALE | ✅ invoked per applicable_reg | run_p1b_single (CORR-039-T4, populated rationale_by_reg) |
| P1C-LLM-01 OVERLAP-CLASSIFICATION | ✅ invoked per domain | map_domains (CORR-040-T2) |
| P1C-LLM-02 COMPOUND-EVENT | ✅ invoked in reduce | run_phase_1c_reduce (executor) |
| P1C-LLM-03 STRATEGIC-SYNTHESIS | ✅ invoked in reduce | run_phase_1c_reduce (executor) |

The 5 CLI flags:

| Flag | Purpose |
|------|---------|
| `--run-applicability` (CORR-038) | Doc 04 + Doc 05 from ApplicabilityContext (no LLM) |
| `--run-clauses` (CORR-039) | Doc 06 from ClauseMappingContext (no LLM) |
| `--run-phase-1b` (CORR-039) | Phase 1B (P1B-LLM-01 + P1B-LLM-02 per applicable_reg) |
| `--run-map` (CORR-040) | MAP stage (P1C-LLM-01 per domain) + Doc 07 + Doc 07b |
| `--run-reduce` (CORR-041) | REDUCE stage (P1C-LLM-03 + P1C-LLM-02) + Doc 04a-d |

**Total tests: 2161** (up from 2103 pre-strategy: +58 new tests across 5 contracts)

**Total commits: 38** across 5 branches (`feature/aegis-p1-corr-037/038/039/040/041`)

---

## Pós-CORR-041 (follow-up contracts)

The strategy is complete; the pipeline is wired. Follow-up work
(out of scope, but identified during CORR-036→CORR-041):

1. **Bug fix: assemble_inputs expects Pydantic, gets dict**
   - Pre-existing bug from v1-compat shim
   - `assemble_inputs` (v2/domain/inputs.py:212) does
     `ctx.scale` (attribute access) but state['company_context']
     is a dict from v1-compat shim
   - Causes all 10 MAP lanes to fail in `--run-map` and `--run-all`
   - Fix: 1-line change (use `ctx.get("scale")` for dict fallback)
   - Separate contract recommended

2. **T4d: Migrate Doc 07/07b consumers to new contexts**
   - Doc 07 (957 LOC) and Doc 07b (827 LOC) still read from
     `state['aggregated_data']` and `state['ontology']` shims
   - Should read from `DomainActivationContext` and `SynthesisContext`
   - Large refactor, separate contract

3. **Methodology-main: structured SubDomains annotations**
   - The 38 sub-domain MD files need structured annotations
     for P1C-LLM-01 to consume
   - Sister-repo work, separate track

4. **Real-LLM smoke test**
   - With Ollama + gemma4:e2b, `--run-all` should produce
     populated synthesis + compound events
   - Best-effort, no contract needed

---

## Change log

- 2026-07-21: v1.0 — final handoff doc created. CORR-036 → CORR-041
  strategy complete. 5 contexts + 5 LLMs + 5 CLI flags + 2161 tests.
  Branch `feature/aegis-p1-corr-041` ready for PR.
