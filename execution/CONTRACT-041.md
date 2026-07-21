# CORR-041 — SP-E: SynthesisContext + P1C-LLM-03/02 + P1B-LLM-02 + Doc 04a-d + parity 9 outputs

## Resumo

Sexto e último contracto da estratégia faseada **CORR-036 → CORR-041**.
Fecha o ciclo de outputs do Phase 1 v2: cria o `SynthesisContext` (fonte
canónica do REDUCE stage), wire **P1C-LLM-03** (strategic synthesis),
**P1C-LLM-02** (compound events) e **P1B-LLM-02** (per-reg rationale
merge), e adiciona o CLI flag `--run-reduce` para correr só a fase
final.

> **Realidade do contracto anterior (CORR-040):** a pipeline v2 agora
> tem `map_domains` que (com executor) invoca P1C-LLM-01 per domain.
> O `run_phase_1c_reduce` (no executor) já invoca P1C-LLM-03 e
> P1C-LLM-02 sequencialmente, mas **só reachable via `run_all`**, não
> tem CLI dedicated, e o seu output é guardado em
> `state['aggregated_data']['synthesis']` / `['compound_events']`
> sem um Pydantic context que os Doc 04a-d / 07b possam consumir
> directamente. **Não há parity check 9 outputs** — não há
> comparação automatizada com a `Methodology-main` reference.

**Branch:** `feature/aegis-p1-corr-041`
**Data:** 2026-07-21
**Trigger:** SP-E da estratégia (contracto final da sequência
CORR-036 → CORR-041).

**Dependência upstream:** CORR-040 merged (PR open). Branch baseado em
`feature/aegis-p1-corr-040` (`d13f418`).

---

## Contexto (resumo da estratégia)

**O que existe (pós-CORR-040):**
- `Phase1Executor.run_phase_1c_reduce` (60 LOC) — invoca P1C-LLM-03
  + P1C-LLM-02 sequencialmente, escreve em
  `state['aggregated_data']['synthesis']` + `['compound_events']`
- `orchestrator.reduce()` — concat / merge / conflicts / proportionality
  + delegação a `reduce_synthesis` + `reduce_compound`
- Doc 04a-d (687-1200 LOC) — já renderizam
- Doc 07b (827 LOC) — já renderiza Track B
- 2146 unit tests passam

**O que falta para o contracto final (SP-E):**
1. **`SynthesisContext`** — Pydantic context canónico que wraps
   `synthesis` + `compound_events` + `track_b_profile` num único
   objecto tipado
2. **Wire P1C-LLM-03/02** no orchestrator — `reduce_synthesis` /
   `reduce_compound` populam o `SynthesisContext` (paralelo aos
   shims v1)
3. **Wire P1B-LLM-02** — completar o per-reg rationale invocando
   P1B-LLM-02 (que CORR-039 só preparou a entrada, não a chamada)
4. **CLI flag `--run-reduce`** — corre só o REDUCE stage, renderiza
   Doc 07 §5.2 (compound events) + §6.2 (strategic synthesis) +
   Doc 04a-d enhancements
5. **Parity check** — diff semântico dos 9 outputs contra
   `Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`

---

## Decisão de produto

**1. `SynthesisContext` é a fonte canónica do REDUCE stage.**

Pydantic model com:
- `synthesis` (dict from P1C-LLM-03 — strategic synthesis prose)
- `compound_events` (list[dict] from P1C-LLM-02)
- `track_b_profile` (dict from apply_proportionality)
- `conflicts` (list[dict] from resolve_conflicts)
- `per_reg_rationale` (dict[reg → dict] from P1B-LLM-02)
- `status` ("OK" | "MIXED" | "FAILED")

**2. Wire P1C-LLM-03/02 no orchestrator é backward-compatible.**

`reduce_synthesis` / `reduce_compound` mantêm a escrita nos
shims v1 (`state['aggregated_data']['synthesis']` etc) E
adicionalmente constroem um `SynthesisContext` para consumers
que o prefiram.

**3. P1B-LLM-02 é wired no `run_phase_1b`.**

Já existe a chamada (CORR-039-T4) que passa os inputs; falta
efectivamente invocar P1B-LLM-02 (o executor do P1B já o faz
internamente, mas a saída é só a synthesis dict). Para CORR-041
populamos `state['aggregated_data']['rationale_by_reg']` directamente.

**4. Parity check é best-effort.**

Os 9 outputs (04/04a/04b/04c/04d/05/06/07/07b) são diff'd contra a
reference. Diff métrico (palavras-chave, secções presentes, contagens).
Não blocking — só logging.

---

## Tarefas

### T1 — NEW `src/aegis_phase1/v2/context/synthesis_context.py` (~200 LOC)

Pydantic context canónico do REDUCE stage.

```python
from aegis_phase1.v2.context import (
    SynthesisContext,
    CompoundEvent,
    StrategicSynthesis,
    build_synthesis_context,
)

ctx = build_synthesis_context(state)
# state['aggregated_data'] é a fonte primária;
# fallback para state['domain_results'] se aplicável

ctx.synthesis                  # StrategicSynthesis (prose + insights)
ctx.compound_events            # list[CompoundEvent]
ctx.track_b_profile            # per-subdomain tier + 5 attrs
ctx.conflicts                  # list of INDETERMINATE (D-XX.Y, (reg_a, reg_b))
ctx.per_reg_rationale          # dict[reg → P1B-LLM-02 dict]
ctx.to_dict()                  # JSON-serializable
```

### T2 — Wire `SynthesisContext` in `reduce_synthesis` + `reduce_compound` (~50 LOC)

`reduce_synthesis` constrói `SynthesisContext` e popula
`state['v2_synthesis_context']`. Idem para `reduce_compound`.
Backward-compatible: shims v1 mantêm-se.

### T3 — Wire P1B-LLM-02 in `run_phase_1b` (~30 LOC)

`run_phase_1b` já invoca o executor (CORR-039-T4). Adicionar
população de `state['aggregated_data']['rationale_by_reg']` a partir
do `aggregated_synthesis` retornado.

### T4 — CLI flag `--run-reduce` (~50 LOC)

Mirror dos outros flags. Corre `orch.reduce()` + `orch.run_phase_1b()`,
re-renderiza Doc 04a-d + Doc 05 §6.1b + Doc 07 §5.2/§6.2.

### T5 — Parity check `tests/integration/test_phase1_parity.py` (~200 LOC)

Diff semântico:
- 9 outputs gerados vs 9 reference docs em
  `Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`
- Métricas: presence of canonical keywords, section count, total_clauses
  match, per_reg_count match, etc.
- Output: PASS/FAIL por doc + overall summary.
- **Best-effort**: não blocking, só INFO/WARN.

### T6 — Tests `tests/unit/v2/test_synthesis_context.py` (~250 LOC, 15 tests)

- 6 SynthesisContext tests
- 3 P1B-LLM-02 wiring tests
- 3 --run-reduce CLI tests
- 3 parity check tests (1 per category)

### T7 — Handoff doc + push

---

## Quality gates (7/7 PASS expected)

G0 pre-flight | G1 SynthesisContext populates | G2 P1B-LLM-02 wired |
G3 --run-reduce produces 9 outputs | G4 tests 15/15 | G5 no regression
(2146 + 15 = 2161) | G6 framework policy

---

## Pós-CORR-041

**Fim da estratégia faseada CORR-036 → CORR-041.**

Critério de sucesso global: `python -m aegis_phase1.v2.runner --run-all
cases/case1-tinytask` produz 9 outputs (04/04a/04b/04c/04d/05/06/07/07b
+ xlsx) com diff semântico ≤ threshold contra a reference.

Estado pós-CORR-041:
- 5 contextos canónicos: ApplicabilityContext, ClauseMappingContext,
  DomainActivationContext, **SynthesisContext** + (build_* factories)
- 5 LLMs canónicos wired (P1B-LLM-01/02 + P1C-LLM-01/02/03)
- 4 CLI flags (--run-applicability, --run-clauses, --run-phase-1b,
  --run-map, **--run-reduce**)
- 9 outputs gerados
- Parity check automatizado
- ~2161 tests passam

Próximos contracts (pós-sprint):
- T4d: Migrar Doc 07/07b consumers para os novos contextos
  (DomainActivationContext, SynthesisContext)
- Bug fix: assemble_inputs expects Pydantic (pre-CORR-040)
- Methodology-main: 38 docs de SubDomains em formato estruturado
  para consumo por Map stage annotations

---

## Change log

- 2026-07-21: v1.0 — contract final da estratégia CORR-036 → CORR-041.
