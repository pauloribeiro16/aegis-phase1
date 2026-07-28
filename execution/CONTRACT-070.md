# CORR-070 — P1B pipeline input bugs (A + B) fix

## Resumo

Contract **focado** (~30-40 min trabalho), resolve os 2 bugs
identificados na auditoria cross-case de payloads LLM
(`CROSS-CASE-LLM-PAYLOAD-AUDIT.md`).

**Bugs a corrigir (cross-case, 22/58 + 11/11 = 33/58 chamadas LLM afectadas):**

| # | Sev | Bug | Ficheiro | LOC | Chamadas afectadas |
|---|---|---|---|---|---|
| A | HIGH | CORR-049 cap (512KB) trunca `layer0_catalog` (tipo2+tipo3) + `# TASK` em todos os P1B-LLM-01/02 porque `layer0_subdomain_refs` (544K) é serializado **antes** do catalog (~25K) | `src/aegis_phase1/v2/orchestrator.py:1704-1723` (`run_p1b_single`) | ~1 (reorder) | 22/58 (38%) |
| B | MEDIUM | `P1B-LLM-02-RATIONALE` é chamado sem `p1b_llm_01_outputs` (resultado da chamada P1B-LLM-01 anterior), forçando o LLM a re-derivar interpretações do zero | `src/aegis_phase1/prompts_v2/phase1_executor.py:207-217` (per-reg loop) | ~1 (add kwarg) | 11/58 (19%) |

**Decisão do utilizador (2026-07-28):** documented no contract prompt; small focused contract.

**Branch:** `feature/aegis-p1-corr-069-pre-existing-test-failures` (mesma branch do CORR-069; **não criar nova branch** — AGENTS.md §10)
**Base:** HEAD do CORR-069 (commits no topo, contrato sequencial)
**Data:** 2026-07-28

---

## Contexto

Auditoria cross-case de payloads LLM
(`execution/CROSS-CASE-LLM-PAYLOAD-AUDIT.md`, 184 linhas, gerada em
2026-07-28) renderizou os **58 payloads** (5 specs × 3 casos) via
`PromptLoader.render()` e mediu onde o CORR-049 cap (508K bytes após
subtracção do system prompt) corta o user prompt. Verificou:

- **22/22 chamadas P1B-LLM-01/02 truncadas** — o tail (catalog +
  `# TASK`) é cortado a 508K, deixando o LLM com refs mas sem
  material para interpretar (catalog é exactamente o que P1B-LLM-01
  precisa para aplicar o spec "Look up all Tipo 2 / Tipo 3 entries
  that apply to this regulation and the company's profile").
- **11/11 chamadas P1B-LLM-02 sem `p1b_llm_01_outputs`** — o rationale
  spec manda basear-se no output da P1B-LLM-01, mas o executor
  (`phase1_executor.py:run_phase_1b`) não passa o `out_01` capturado
  para a chamada subsequente de `out_02`.

A auditoria documenta:

> "Recommendation: open a new contract (CORR-070 or similar) to
> address Bug A (catalog truncation) and Bug B (P1B-02 wiring). The
> fix for Bug B is straightforward (~5 LOC in `run_p1b_single`); Bug A
> requires prompt template work or cap adjustment."

**Detalhe dos bugs:**

- **Bug A (root cause):** em `run_p1b_single` (`orchestrator.py:1704-1723`)
  a kwargs dict do `executor.run_phase_1b(...)` lista
  `layer0_subdomain_refs` ANTES de `layer0_catalog`. Como
  `json.dumps` (chamado pelo `PromptLoader.render()`) preserva a
  ordem das keys, o catalog (pequeno, ~25K) acaba no **tail** e é
  cortado pelo cap. A spec template `P1B-LLM-01-INTERPRETATION.md`
  lista o catalog primeiro, mas o `run_p1b_single` inverte. A
  reordenação no orchestrator (não no template) é a mudança correcta
  porque mantém a spec intacta para outros call-sites.

- **Bug B (root cause):** em `phase1_executor.py:run_phase_1b`
  (per-reg loop, linhas 195-217) o `out_01` é capturado do
  `invoker.invoke(SPEC_INTERPRETATION, ...)` mas a chamada
  subsequente `invoker.invoke(SPEC_RATIONALE, ...)` constrói o
  kwargs dict sem incluir `p1b_llm_01_outputs=out_01.get("parsed_output")`.
  Logo o rationale spec não recebe o que o template
  `P1B-LLM-02-RATIONALE.md` espera.

**Validação pré-contract:**
- Branch limpa (0 ficheiros modificados)
- Imports OK (`Phase1Orchestrator`, `Phase1Executor`)
- 38 tests collected em `tests/unit/prompts_v2/test_pipeline_inputs.py`
- 1 pre-existing smoke_e2e fail (idêntico baseline, não relacionado)

---

## Phase 1 — Pre-flight check (AGENTS.md §10.1)

Já feito antes de escrever este contract. Output:

```text
Current branch: feature/aegis-p1-corr-069-pre-existing-test-failures
Uncommitted files: 0
Imports: OK
38 tests collected in tests/unit/prompts_v2/test_pipeline_inputs.py
```

**Conclusão:** base OK para implementar.

---

## Phase 2 — Write contract (este ficheiro)

Status: ✅ (este contract).

---

## Phase 3 — Implement Bug A (reorder inputs)

**File:** `src/aegis_phase1/v2/orchestrator.py`
**Function:** `Phase1Orchestrator.run_p1b_single` (lines 1704-1723)
**Change:** Mover `layer0_catalog=layer0_catalog` para ANTES de
`layer0_subdomain_refs=...` no kwargs dict do `executor.run_phase_1b(...)`.

```python
# OLD (lines 1711-1715):
            aggregated_activations=aggregated_activations,
            layer0_subdomain_refs=self._build_layer0_subdomain_refs(
                list((self.state.get("subdomains") or {}).keys())
            ),
            layer0_catalog=layer0_catalog,
            classification={

# NEW:
            aggregated_activations=aggregated_activations,
            layer0_catalog=layer0_catalog,                              # ← MOVED UP
            layer0_subdomain_refs=self._build_layer0_subdomain_refs(
                list((self.state.get("subdomains") or {}).keys())
            ),
            classification={
```

**Rationale:**

- `json.dumps` no `PromptLoader.render()` preserva key order (Python
  3.7+). O `len(user.encode("utf-8"))` é proporcional à ordem das
  keys no dict.
- `layer0_catalog` (~25K bytes) é 22× mais pequeno que
  `layer0_subdomain_refs` (~544K bytes). Mover o catalog para o head
  garante que sobrevive ao cap de 508K.
- Os sub-domain refs podem ser parcialmente truncados (a
  ordem é determinística por sub_domain_id, e o LLM tolera refs
  parciais melhor do que catalog zero — catalog é o que o P1B-LLM-01
  spec **instrui** explicitamente a usar para interpretação).
- Não há impacto no `run_phase_1c_map` (per-domain lane) que filtra
  refs por domain — não usa `layer0_catalog` (confirmado em
  `phase1_executor.py:248-324`).

**Risk:** dict key order é uma propriedade que pode ser alterada por
um futuro refactor. O reordering é no call-site, não na spec
template, então é mais robusto do que mover no markdown. Verificar
que o `PromptLoader.render()` ainda respeita a ordem — o teste
`test_inputs_size_within_budget` (drift) detecta se o tamanho
muda significativamente.

### Critérios P3

| # | Critério | Como verificar |
|---|---------|----------------|
| 1 | `layer0_catalog` aparece no kwargs **antes** de `layer0_subdomain_refs` no call-site | inspection of `orchestrator.py:1704-1723` |
| 2 | `run_phase_1c_map` (per-domain) não usa `layer0_catalog`; reordering é irrelevante para ele | inspection of `phase1_executor.py:248-324` |

---

## Phase 4 — Implement Bug B (wire P1B-01 outputs to P1B-02)

**File:** `src/aegis_phase1/prompts_v2/phase1_executor.py`
**Function:** `Phase1Executor.run_phase_1b` (per-reg loop, lines 207-217)
**Change:** Adicionar `p1b_llm_01_outputs: out_01.get("parsed_output") or {}`
ao kwargs dict da chamada `invoker.invoke(SPEC_RATIONALE, ...)`.

```python
# OLD (lines 207-217):
            out_02 = self.invoker.invoke(
                SPEC_RATIONALE,
                {
                    **inputs,
                    "case_id": case_id,
                    "lane_id": reg,
                    "applicable_regs": [reg],
                },
                config=config,
                state=state,
            )

# NEW:
            out_02 = self.invoker.invoke(
                SPEC_RATIONALE,
                {
                    **inputs,
                    "case_id": case_id,
                    "lane_id": reg,
                    "applicable_regs": [reg],
                    "p1b_llm_01_outputs": (out_01.get("parsed_output") or {}),  # NEW
                },
                config=config,
                state=state,
            )
```

**Rationale:**

- `out_01` é o resultado da chamada `SPEC_INTERPRETATION` imediatamente
  acima (line 196-206). `out_01.get("parsed_output")` é o dict que o
  P1B-LLM-01 produziu (interpretações + derrogações).
- O rationale spec `P1B-LLM-02-RATIONALE.md` espera
  `p1b_llm_01_outputs` como input — agora é wired correctamente.
- O fallback `or {}` é defensivo: se a chamada P1B-LLM-01 falhou
  (status != "OK", `parsed_output` None), o rationale ainda corre
  com dict vazio, em vez de crash.

**Side-effect no test:** o test
`tests/unit/prompts_v2/test_pipeline_inputs.py::TestPipelineInputsStructural::test_p1b_llm_02_structural`
já declara `p1b_llm_01_outputs` como **required** no schema. Antes
deste fix, o teste **espera a falha** (non-BUG-B missing checked
separately, BUG-B missing logged as warning). Depois do fix, o
test passa a verificar que `p1b_llm_01_outputs` está **presente** —
ver Phase 5.

### Critérios P4

| # | Critério | Como verificar |
|---|---------|----------------|
| 1 | `p1b_llm_01_outputs` aparece no kwargs do `invoker.invoke(SPEC_RATIONALE, ...)` | inspection of `phase1_executor.py:207-218` |
| 2 | Valor é `out_01.get("parsed_output") or {}` (defensivo contra None) | inspection |
| 3 | `out_01` é capturado no mesmo scope (linha 196-206) | inspection |

---

## Phase 5 — Re-capture payloads + verify

**Action:** Re-capturar os payloads P1B-LLM-01/02 para os 3 casos e
verificar:

1. `layer0_catalog` (tipo2 + tipo3 entries) aparece dentro dos
   primeiros 508K bytes do user prompt.
2. A string `# TASK` aparece dentro dos primeiros 508K bytes.
3. `layer0_subdomain_refs` pode estar parcialmente truncado
   (aceitável — catalog é mais crítico).

**Implementation:** Usar o script de captura do audit
(`/tmp/payload_capture4/` já tem os 58 ficheiros antigos). Vou
escrever um script de re-captura mínimo (em
`execution/CORR-070-payload-recapture.py`) que:

1. Constrói o inputs dict **exatamente** como `run_p1b_single` +
   `run_phase_1c_map` (após o fix de P3).
2. Renderiza via `PromptLoader.render(spec, inputs)`.
3. Mede `len(user.encode("utf-8"))` e a posição de
   `layer0_catalog` (procura `"layer0_catalog":` no user) e
   `# TASK` (procura a string literal).

**Output esperado após fix:**

| Payload | Pre-fix user bytes | Post-fix user bytes | catalog pos | TASK pos | catalog survives? | TASK survives? |
|---|---|---|---|---|---|---|
| case 1 P1B-01 GDPR | 571,559 | ~571,559* | <508K | <508K | YES | YES |
| case 1 P1B-01 CRA | 573,037 | ~573,037* | <508K | <508K | YES | YES |
| case 2 P1B-01 GDPR | 571,638 | ~571,638* | <508K | <508K | YES | YES |
| case 2 P1B-01 NIS2 | 572,436 | ~572,436* | <508K | <508K | YES | YES |
| ... (11 more) | | | | | | |

*Tamanho total não muda (os bytes são os mesmos), só a **ordem**
muda. Catalog passa de tail para head.

### Critérios P5

| # | Critério | Como verificar |
|---|---------|----------------|
| 1 | Re-capture script escrito e corre | run `python execution/CORR-070-payload-recapture.py` |
| 2 | Para todos os 11 P1B-LLM-01 + 11 P1B-LLM-02 payloads (cases 1/2/3): `layer0_catalog` aparece dentro dos primeiros 508K bytes | script output table |
| 3 | Para todos os 22 payloads: `# TASK` aparece dentro dos primeiros 508K bytes | script output table |
| 4 | `layer0_subdomain_refs` pode estar truncado (OK) | script output (warning, not failure) |

---

## Phase 6 — Run test suite

```bash
# CI gate
bash .hooks/ci-pipeline-inputs.sh

# After regenerating golden files:
PYTHONPATH=src pytest tests/unit/prompts_v2/ -v 2>&1 | tail -20

# Full suite
PYTHONPATH=src pytest tests/unit/ --skip-slow -q 2>&1 | tail -10
```

**After Bug B fix:** the drift test
`test_p1b_llm_02_structural` no longer logs BUG-B warning (the
`p1b_llm_01_outputs` key is now present in every P1B-LLM-02 golden
file).

**After Bug A fix:** the drift test `test_inputs_size_within_budget`
still warns (>524288), but the new behavior is that the catalog
survives — this is **expected**; the test was already marked
"soft pass" for this exact reason. No test failure.

### Critérios P6

| # | Critério | Como verificar |
|---|---------|----------------|
| 1 | `bash .hooks/ci-pipeline-inputs.sh` passa (structural) | exit code 0 |
| 2 | `tests/unit/prompts_v2/` passa | 0 fail |
| 3 | Full `tests/unit/` passa (2729+ tests, 1 pre-existing smoke_e2e fail OK) | pytest output |

---

## Phase 7 — Commit on current branch

```bash
git add execution/CONTRACT-070.md src/aegis_phase1/v2/orchestrator.py \
        src/aegis_phase1/prompts_v2/phase1_executor.py \
        tests/fixtures/pipeline_inputs_golden/_schema.json \
        tests/fixtures/pipeline_inputs_golden/ \
        execution/CORR-070-payload-recapture.py \
        execution/CORR-070-payload-recapture-output.md
git commit -m "fix(corr-070): wire P1B-01 outputs to P1B-02 (Bug B) + reorder inputs to preserve catalog (Bug A)"
```

**No branch switch** (per AGENTS.md §10 + this contract prompt).

---

## Ficheiros a alterar (estimativa)

| Ficheiro | P3 | P4 | P5/P6 | Total LOC |
|----------|----|----|-------|-----------|
| `src/aegis_phase1/v2/orchestrator.py` | x (reorder ~6 lines) | — | — | ~6 |
| `src/aegis_phase1/prompts_v2/phase1_executor.py` | — | x (1 line) | — | ~1 |
| `tests/fixtures/pipeline_inputs_golden/_schema.json` | — | (already correct) | — | 0 |
| `tests/fixtures/pipeline_inputs_golden/case1-tinytask/*.json` | (regen) | (regen) | — | regenerated |
| `tests/fixtures/pipeline_inputs_golden/case2-secureborder/*.json` | (regen) | (regen) | — | regenerated |
| `tests/fixtures/pipeline_inputs_golden/case3-omnibank/*.json` | (regen) | (regen) | — | regenerated |
| `execution/CONTRACT-070.md` | x | x | x | new |
| `execution/CORR-070-payload-recapture.py` | — | — | x | new |
| `execution/CORR-070-payload-recapture-output.md` | — | — | x | new |

**Estimativa total:** ~7 LOC código + 2 ficheiros novos + 58 golden
regenerated.

---

## Comandos de validação

```bash
# Phase 3+4: implement fixes (manually via edit tool)
# Phase 5: regenerate golden + re-capture payloads
python _regenerate_pipeline_inputs_golden.py
git diff tests/fixtures/pipeline_inputs_golden/   # review
python execution/CORR-070-payload-recapture.py    # capture
# inspect output, verify catalog + # TASK survive

# Phase 6: run tests
bash .hooks/ci-pipeline-inputs.sh
PYTHONPATH=src pytest tests/unit/prompts_v2/ -v
PYTHONPATH=src pytest tests/unit/ --skip-slow -q

# Phase 7: commit
git add ...
git commit -m "fix(corr-070): ..."
```

---

## Risco

- **P3 (reorder):** baixo. A spec template não é tocada. O
  `run_phase_1c_map` (per-domain) não usa `layer0_catalog` (confirmado
  em `phase1_executor.py:248-324`). O drift test
  `test_inputs_size_within_budget` já está marcado como "soft pass" —
  o tamanho total não muda, só a ordem das keys.
- **P4 (wire P1B-01 → P1B-02):** baixo. Adicionar uma key ao kwargs
  é a fix correcta. O rationale spec
  `P1B-LLM-02-RATIONALE.md` já documenta `p1b_llm_01_outputs` como
  input esperado. O fallback `or {}` evita crash se P1B-01 falhou.
- **P5 (re-capture):** baixo. Pure re-render. O script de captura é
  read-only — não muta state.
- **P6 (tests):** baixo. Drift test já é warning. Structural test
  passa porque o schema já declara `p1b_llm_01_outputs` required.
- **P7 (commit):** trivial. Sem branch switch, sem rebase, sem push.

---

## Não-objetivos (out of scope)

- Compactar `layer0_subdomain_refs` (audit sugere ~544K → ~50K, mas
  isso muda a forma como o LLM vê os sub-domains — não trivial)
- Bump do CORR-049 cap (audit sugere risco de gemma4:e2b degradation)
- Enviar catalog num pre-context separado (gemma4:e2b é single-prompt)
- Adicionar `--mock-llm` flag para P1B (já existe `MOCK_LLM` env var)
- Refactor do `run_phase_1b` per-reg loop para asyncio.gather (paralelismo
  é roadmap, não bug)
- Re-run E2E completo dos 3 casos (idem CORR-069 S4: user cancelou,
  é trabalho separado, deferred para contract futuro)

---

## Estado final esperado

| Aspecto | Pre-CORR-070 | Post-CORR-070 |
|---------|--------------|---------------|
| `layer0_catalog` pos em P1B user prompt | tail (~569K, trunc) | head (<508K, survives) |
| `# TASK` pos em P1B user prompt | tail (~571K, trunc) | head (<508K, survives) |
| `p1b_llm_01_outputs` no P1B-LLM-02 call | None | `out_01.get("parsed_output") or {}` |
| `tests/unit/prompts_v2/test_p1b_llm_02_structural` | BUG-B warning logged | clean (no warning) |
| `tests/unit/` full suite | 2729 pass, 1 pre-existing fail | 2729 pass, 1 pre-existing fail (no regression) |

**Sucesso = catalog + # TASK sobrevivem ao cap em todos os 22 P1B
payloads + `p1b_llm_01_outputs` está wired em todas as 11 chamadas
P1B-LLM-02 + zero regressões nos unit tests.**
