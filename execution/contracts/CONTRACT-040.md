# CORR-040 — SP-D: DomainActivationContext + P1C-LLM-01 (overlap classification) + Doc 07 + Track B

## Resumo

Quinto contract da estratégia faseada **CORR-036 → CORR-041**. Cria o
`DomainActivationContext` (fonte canónica da activação per-domínio),
faz o swap do legacy `LLM-A` (MAP-DOMAIN-ADAPT) para o canónico
**P1C-LLM-01-OVERLAP-CLASSIFICATION**, refactoriza `Doc 07`
(38×5 coverage matrix) e `Doc 07b` (Track B proportionality profile)
para lerem do novo contexto, e adiciona o CLI flag `--run-map` para
correr só o MAP stage.

> **Realidade do contracto anterior (CORR-039):** o orchestrator
> tem `map_domains()` que itera D-01..D-10 sequencialmente via
> `DomainProcessor.process()`, mas o `DomainProcessor` usa o
> **legacy** `LLM-A` prompt (`MAP-DOMAIN-ADAPT.md`). O canónico
> `P1C-LLM-01-OVERLAP-CLASSIFICATION` existe em
> `Phase1Executor.run_phase_1c_map` mas **não está wired** no
> orchestrator. Doc 07 (957 LOC) e Doc 07b (827 LOC) já existem e
> renderizam, mas lêem de `state['aggregated_data']` via shims
> v1-compat. **Não há fonte canónica única** para a activação
> per-domínio.

**Branch:** `feature/aegis-p1-corr-040`
**Data:** 2026-07-21
**Trigger:** SP-D da estratégia (ver `CORR-039-HANDOFF.md` §"Pós-CORR-039").

**Dependência upstream:** CORR-039 merged (PR #33). Branch baseado
em `feature/aegis-p1-corr-039` (`3fe7043`).

---

## Contexto (resumo da estratégia)

**O que existe (pós-CORR-039):**
- `DomainProcessor` (382 LOC) — MAP worker que renderiza legacy
  `MAP-DOMAIN-ADAPT.md` (LLM-A) e invoca Ollama
- `Phase1Executor.run_phase_1c_map` (60 LOC) — invoca canónico
  P1C-LLM-01 per domain mas **unreachable** via orchestrator
- `Doc 07` (957 LOC), `Doc 07b` (827 LOC) — renderizam mas
  via shims v1-compat
- `TrackB` (`prompts_v2/track_b.py`) + `apply_proportionality` —
  deterministic tier assignment
- `orchestrator.map_domains()` — loop sequencial D-01..D-10

**O que falta para SP-D:**
1. **`DomainActivationContext`** — Pydantic context que wraps
   P1C-LLM-01 output (per-domain lane output: sub_domain_activations,
   per_reg verdict, coverage_level)
2. **Swap LLM-A → P1C-LLM-01** — `DomainProcessor` passa a invocar
   `Phase1Executor.run_phase_1c_map` em vez de `render_prompt` legacy
3. **Doc 07 refactor** — ler de `DomainActivationContext` em vez de
   shims v1-compat
4. **Doc 07b refactor** — Track B passa a consumir
   `DomainActivationContext` directamente
5. **`--run-map` CLI flag** — corre só o MAP stage (10 chamadas
   P1C-LLM-01, com LLM)

---

## Decisão de produto

**1. `DomainActivationContext` é a fonte canónica da activação per-domínio.**

Pydantic model com:
- `lane_id` (D-01..D-10)
- `sub_domain_activations` (list[SubDomainActivation])
  - `sub_domain_id` (D-01.1)
  - `reg_pair` ([reg_a, reg_b])
  - `company_scope_verdict` (APPLICABLE / NOT_APPLICABLE / INDETERMINATE)
  - `regulatory_baseline_relationship` (SUBSTANTIVE / OVERLAPPING / etc.)
  - `layer0_refs` (file paths)
- `coverage_level` (FULL / PARTIAL / NOT_ADDRESSED)
- `llm_status` (OK / FAILED / SKIPPED)
- `latency_ms`

**2. Swap LLM-A → P1C-LLM-01 é backward-compatible.**

`DomainProcessor.process()` mantém a interface (recebe domain_id, state;
retorna DomainResult) mas internamente delega ao
`Phase1Executor.run_phase_1c_map` para invocar o canónico P1C-LLM-01.
Se o executor não está disponível (MOCK_LLM=true), fallback para o
legacy `render_prompt`. **Resultado:** Doc 07/07b continuam a
renderizar, agora com dados do P1C-LLM-01.

**3. Doc 07/07b são refactors, não rewrites.**

Mantêm a estrutura de 8 secções (Doc 07) e 5 atributos (Doc 07b).
Mudam só a fonte de dados. O `state['aggregated_data']` shim
continua a existir para backward-compat com consumers que ainda
não migraram (alguns doc_04*).

**4. Track B (Doc 07b) lê do novo contexto.**

`apply_proportionality` continua a existir; ganha um novo caller
`build_domain_activation_context(state)` que constrói o contexto
e popula `state['aggregated_data']['profile']` (input do Doc 07b).

---

## Tarefas

### T1 — NEW `src/aegis_phase1/v2/context/domain_activation_context.py` (~250 LOC)

**Responsabilidade:** wrappear o output do P1C-LLM-01 num Pydantic
context canónico + fornecer factory `build_domain_activation_context(state)`.

**API pública:**

```python
from aegis_phase1.v2.context.domain_activation_context import (
    DomainActivationContext,
    SubDomainActivation,
    CoverageLevel,
    build_domain_activation_context,
)

ctx = build_domain_activation_context(state)
# OR explicit
ctx = DomainActivationContext(
    lanes=[
        SubDomainActivation(
            lane_id="D-01",
            coverage_level=CoverageLevel.FULL,
            llm_status="OK",
            sub_domain_activations=[
                SubDomainActivation(
                    sub_domain_id="D-01.1",
                    reg_pair=("GDPR", "CRA"),
                    company_scope_verdict="APPLICABLE",
                    regulatory_baseline_relationship="SUBSTANTIVE",
                    layer0_refs=["SubDomains/D-01.1.md"],
                ),
                ...
            ],
            latency_ms=1234,
        ),
        ...  # 10 lanes D-01..D-10
    ],
    total_lanes=10,
    ok_lanes=8,
    failed_lanes=2,
    total_sub_domain_activations=222,
)

# Accessors
ctx.by_domain("D-04")              # SubDomainActivation for D-04
ctx.sub_domains_covered()          # set of D-XX.Y with APPLICABLE verdict
ctx.pairs_with_indeterminate()     # set of (D-XX.Y, (reg_a, reg_b)) INDETERMINATE
ctx.to_dict()                       # JSON-serializable
```

### T2 — Wire P1C-LLM-01 in DomainProcessor (~50 LOC diff)

`DomainProcessor.process(domain_id, state)`:
- Build inputs (igual)
- Try: `executor.run_phase_1c_map(...)[0]` for this domain
- If executor unavailable (MOCK_LLM=true ou skip_reduce_llms):
  fallback para legacy `render_prompt` + `OutputParserV3`
- Return `DomainResult` with adapted_subdomains_v3 populated

### T3 — REFACTOR `doc_07.py` (957 → ~970 LOC)

- Read from `build_domain_activation_context(state)` in addition
  to legacy shim (graceful merge)
- §3 Coverage matrix: 38 rows × applicable_regs
- §5.2 Compound events (P1C-LLM-02): surface from
  `state['aggregated_data']['compound_events']`
- §6.2 Strategic synthesis (P1C-LLM-03): surface from
  `state['aggregated_data']['synthesis']`

### T4 — REFACTOR `doc_07b.py` (827 → ~840 LOC)

- §3 Per-subdomain tier table: read from
  `apply_proportionality(state)` with the new context as input
- §4 5 attributes per subdomain: from TrackB._tier_attributes

### T5 — CLI flag `--run-map` (~30 LOC)

Mirror `--run-applicability` / `--run-clauses` pattern. Runs
`orch.map_domains()` (which now fires P1C-LLM-01 per domain) and
prints lane summaries.

### T6 — Tests `tests/unit/v2/test_domain_activation.py` (~300 LOC, 15 tests)

- 6 context tests (build, by_domain, sub_domains_covered, pairs_with_indeterminate, to_dict, empty)
- 4 doc_07 refactor tests (renders, 38 rows, per_reg match, surface synthesis/compound)
- 3 doc_07b refactor tests (renders, per-subdomain tier, 5 attributes)
- 2 CLI tests (--run-map fires, no-LLM fallback)

---

## Quality gates (8/8 PASS expected)

G0 pre-flight | G1 domain activation context | G2 doc_07 parity |
G3 doc_07b parity | G4 --run-map fires | G5 tests 15/15 |
G6 no regression (2131 + 15 = 2146) | G7 framework policy

---

## Pós-CORR-040

Strategy: SP-D closed. Next: **CORR-041** (SynthesisContext + P1C-LLM-03/02 + P1B-LLM-02 + Doc 04a-d + parity 9 outputs).

---

## Change log

- 2026-07-21: v1.0 — contract created after CORR-039 (PR #33 open).
  Branch `feature/aegis-p1-corr-040` to be based on CORR-039 tip.

---

## Verdict pós-execução (CORR-042, 2026-07-21)

**Status:** ⚠️ PARTIAL (P1C-LLM-01 canonical path deferred to CORR-043; legacy LLM-A fallback works)

**Evidence:**
- Run end-to-end REAL (sem MOCK_LLM) com Ollama gemma4:e2b
- Gates executados em: feature/aegis-p1-corr-042 @ commit de T7
- Parity report: logs/phase1/corr042_parity_report.md
- Run logs: logs/phase1/corr042_run_*.log
- Errors post-mortem: logs/phase1/corr042_errors.md
Parity 9/9 PASS. CORR-040 (DomainActivationContext + P1C-LLM-01 + --run-map) — 10/10 MAP lanes OK em 364s; legacy LLM-A loop (com inputs.py fix) usado como fallback. P1C-LLM-01 canonical path deferred to CORR-043 (input shape mismatch).
