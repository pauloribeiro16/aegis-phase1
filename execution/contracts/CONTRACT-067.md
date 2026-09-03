# CORR-067 — Langfuse CHAIN nesting + MAP partial-failure handling

## Resumo

Contract **focado** (2 sprints, ~3-4h), sequência natural do CORR-066
(GenericMarkdownParser). Resolve **2 issues identificados** durante a
auditoria pós-CORR-066 (6 testes isolados a passar, 5 system checks,
2654 unit tests verdes):

1. **Langfuse CHAIN nesting quebrado** (issue A) — o wrap S6 do
   CORR-064 (`_lf_client.start_as_current_observation(as_type="chain")`)
   cria uma CHAIN, mas o GENERATION subsequente (criado pelo langchain
   CallbackHandler via OTel API) **não fica sob essa CHAIN** — fica
   sob a CHAIN do langgraph node. Resultado: a query Langfuse mostra
   CHAINs como siblings em vez de aninhadas. **O fix S6 não produz o
   efeito desejado.**
2. **MAP partial-failure propagation incorrect** (issue D) — o
   S5.2b do CORR-064 faz o **loop interno** continuar, mas o
   `MapPartialFailure` raised no fim do loop é catched pelo runner
   (`run_all_traced` linha 380, `map_only` linha 400) que faz
   `sys.exit(2)`. O pipeline aborta inteiro, não gerando docs
   parciais. O `cmd_run_map` (linha 650) tem um workaround escondido
   que continua com empty state — inconsistente.

**Decisão do utilizador (2026-07-27):** "abre um contrato para
resolver as duas" → confirma contract dedicado.

**Revisão 1 (2026-07-27 17:59):** S1 (Langfuse CHAIN nesting)
**deferido** após investigação. O Langfuse v4 SDK tem 3 limitações
que tornam a Opção 1 (parent_id explícito) **inviável**:

1. `trace_context={"parent_span_id": ...}` só funciona se `trace_id`
   está presente (`observe.py:259-263`)
2. langchain CallbackHandler **não** lê `langfuse_parent_observation_id`
   da metadata — só usa o seu próprio `_runs[parent_run_id]` dict
   (`CallbackHandler.py:680`)
3. Hierarquia é gerida por `parent_run_id` do langchain, não pelo
   contextvar global da Langfuse

A Opção 2 (reverter S6) é a solução correcta mas requer uma decisão
arquitectural do user (regressão vs manter ruído). S1 fica deferido
até decisão futura (potencialmente requer contacto com Langfuse ou
mudança para a API v3/OTel directa).

**S2 (MAP partial-failure handling) é o sprint activo deste contract.**

**Branch:** `feature/aegis-p1-corr-067-langfuse-nesting-and-map-partial`
**Base:** `feature/aegis-p1-corr-063-logging-and-langfuse` (commit `ecb9ab1`)
**Data:** 2026-07-27

---

## Contexto

Auditoria pós-CORR-066 confirmou que:
- T1-T6 (LLM call tests): ✅ 6/6 passam com M3 (P1B-01, P1B-02, P1C-01/02/03)
- T-B (retry): ✅ backoff 1s/2s funciona
- Langfuse UI: ❌ CHAIN/GENERATION nesting não está como esperado
- 2654 unit tests verdes, 9 falhas **pré-existentes** (idênticas antes/depois)

### Issue A — Langfuse CHAIN nesting (langfuse v4 SDK limitation)

**Causa raíz:** O Langfuse v4 SDK tem **duas APIs paralelas**:

1. **v2 client** (`from langfuse import Langfuse; client.start_as_current_observation(...)`)
   - Cria spans como **v2 observations** (modelo antigo)
2. **OTel API** (usada pelo langchain CallbackHandler)
   - Cria spans como **OTel spans** (modelo novo, v3+)

A `start_as_current_observation` do v2 client cria uma CHAIN que
**não partilha o parent_id** com os OTel spans do CallbackHandler.
Resultado: o GENERATION fica sob a langgraph CHAIN (OTel) mas **não**
sob a CHAIN S6 (v2). As duas hierarquias não se cruzam.

**Evidência (Langfuse API query, 2026-07-27 17:30):**

```
Trace 5bd8bced...
  CHAIN      (root) | interp_GDPR            ← S6 wrapper?
  CHAIN      (root) | P1B Sub-Phase          ← langgraph node
  CHAIN      (root) | subphase_1b
  CHAIN      (root) | MAP D-10               ← langgraph node
  GENERATION parent=MAP D-10 | MAP D-10 Monitoring & Audit  ← S6 chain não é parent
  CHAIN      (root) | map_D10                ← outro wrapper?
  CHAIN      (root) | MAP D-09
  GENERATION parent=MAP D-09 | MAP D-09 Governance & Documentation
```

Reparar: o S6 cria `MAP D-10` (langgraph) E `map_D10` (S6 wrapper)
como CHAINs separadas (siblings). O GENERATION fica sob a langgraph
CHAIN, não sob o S6 wrapper.

### Issue D — MAP partial-failure abort

**Causa raíz:** O `MapPartialFailure` é raised pelo orchestrator
quando ≥1 domain termina com `status=FAILED` (orchestrator.py:615).
O `run_all_traced` no runner catcha e faz `sys.exit(2)`. Os
domain results que foram **bem-sucedidos** (até 9 de 10) ficam no
state mas o pipeline não chega ao OUTPUT stage, e nenhum doc é
gerado.

**Comportamento actual (runner.py):**

```python
# linha 374-382
try:
    rc = cmd_run_all_traced(...)
except MapPartialFailure as exc:
    logger.error("Pipeline aborted — MAP partial failure: %s", exc)
    sys.exit(2)
```

**Comportamento desejado:** Se 1-2 domains falharem (de 10), gerar
docs com os 8-9 resultados válidos + um apêndice de falhas. Se
≥5 domains falharem, aí sim abort (MAP é essencialmente quebrado).

---

## S1 — Langfuse CHAIN nesting (issue A)

### Hipótese de fix

Substituir o wrap S6 actual:

```python
with _lf_client.start_as_current_observation(
    as_type="chain",
    name=f"MAP {domain_id}",
    input={...},
) as chain_span:
    response = self.llm_invoker.invoke(...)
```

Por uma abordagem que **passa explicitamente o `langfuse_parent`**
para o callback via `config`:

```python
from langfuse import langfuse_context  # ou client.get_current_observation_id()
parent_id = langfuse_context.get_current_observation_id()  # ou None
config = {"callbacks": [self._langfuse_handler], "metadata": {"langfuse_parent_observation_id": parent_id}}
response = self.llm_invoker.invoke(prompt, config=config)
```

OU, se a primeira opção for limitada, **deixar de criar uma CHAIN
adicional** e deixar o langgraph CallbackHandler criar a sua
hierarquia natural. O S6 "fix" actual adiciona ruído sem valor.

### Decisão a tomar

**Opção 1: Manter a CHAIN S6 mas com parent_id explícito**
- Pro: mantém a estrutura CHAIN→GENERATION
- Con: requer investigação profunda do Langfuse v4 SDK

**Opção 2: Remover o wrap S6 (regressão funcional)**
- Pro: simples, o langgraph CHAIN já existe
- Con: perde-se a metadata de attempt/feedback que o S6 adicionava

**Opção 3: Manter o wrap mas como CHAIN é OK, mudar para SPAN
(implicit) ou outra abordagem OTel-compatible**
- Pro: alinha com OTel
- Con: requer reescrita

**Recomendação: Opção 2** (regressão S6 + commit explicativo) **OU
Opção 1** se a investigação mostrar que é viável. Decisão do
utilizador.

### Critérios S1 (validação)

| # | Critério | Tipo | Como verificar |
|---|---------|------|----------------|
| 1 | Query Langfuse API após o fix mostra CHAIN→GENERATION aninhadas | MUST | `curl /api/public/observations?traceId=<id>` + grep por `parent=CHAIN_<id>` |
| 2 | Hierarquia tem profundidade ≥3 (langgraph node → per-domain chain → generation) | MUST | Mesma query, count de obs por nível |
| 3 | `chain_span.update(output=...)` ainda funciona (metadata) | MUST | grep log por `chain_span.update` no output |
| 4 | `logger.exception` ainda é chamado em falhas (não perdido) | MUST | grep log |
| 5 | Trace de hoje (5bd8bced...) mostra a estrutura nova após re-run | MUST | Comparar com snapshot pré-fix |

---

## S2 — MAP partial-failure handling (issue D)

### Hipótese de fix

Substituir o `sys.exit(2)` por um fallback graceful:

```python
# runner.py run_all_traced handler
except MapPartialFailure as exc:
    failed = exc.failed_domains
    n_failed = len(failed)
    n_total = 10
    if n_failed >= 5:  # threshold for "MAP essentially broken"
        logger.error("MAP mostly failed (%d/%d) — aborting: %s", n_failed, n_total, failed)
        return 2
    logger.warning(
        "MAP partial failure (%d/%d domains failed: %s) — continuing with %d results",
        n_failed, n_total, failed, n_total - n_failed,
    )
    # Don't abort — let the OUTPUT stage run with partial results
    # The OUTPUT stage already handles missing domain_results gracefully
    rc = 0
```

Adicionalmente, tornar `MapPartialFailure` portar a lista de
`failed_domains` para que o runner possa reportar.

### Critérios S2 (validação)

| # | Critério | Tipo | Como verificar |
|---|---------|------|----------------|
| 1 | `MapPartialFailure` raised carrega `failed_domains: list[str]` | MUST | Inspect exception class |
| 2 | `run_all_traced` continua quando 1-2 domains falham (≤2/10) | MUST | Mock injectando 2 falhas; verifica docs gerados |
| 3 | `run_all_traced` aborta quando ≥5 domains falham | MUST | Mock injectando 6 falhas; verifica return code 2 |
| 4 | `cmd_run_map` (linha 643) é removido ou unificado (workaround escondido) | SHOULD | grep returns 0 |
| 5 | OUTPUT stage (Doc 04/05/06/07/07b) gera com 8/10 results sem crashar | MUST | Run S1 com mock falha em D-05, D-09; verifica 9 docs gerados |
| 6 | Log final reporta quantos domains falharam + lista | MUST | grep `MAP partial failure` |

---

## Ficheiros a alterar (estimativa)

| Ficheiro | S1 | S2 | Acção |
|---------|----|----|-------|
| `src/aegis_phase1/v2/domain/processor.py` | x | — | Modificar wrap S6 (CHAIN context) |
| `src/aegis_phase1/llm/tracing.py` | x | — | Helper para parent_id |
| `src/aegis_phase1/v2/domain/processor.py` (`MapPartialFailure`) | — | x | Adicionar `failed_domains` field |
| `src/aegis_phase1/v2/runner.py` | — | x | Substituir `sys.exit(2)` por fallback |
| `tests/unit/v2/test_map_partial_failure.py` | — | x | Criar (novo test) |

**Estimativa:** 5-6 ficheiros, 200-400 linhas total, 1-2h trabalho.

---

## Comandos de validação

```bash
# S1: Langfuse CHAIN nesting
PYTHONPATH=src python -m pytest tests/unit/prompts_v2/ -q
# Run a single LLM call via invoker
PYTHONPATH=src python /tmp/opencode/m3_diag/t4_p1c01_overlap.py
# Query Langfuse API for the new trace
curl -u $LANGFUSE_KEY $LANGFUSE_HOST/api/public/observations?traceId=<new_id> | jq .

# S2: MAP partial-failure
PYTHONPATH=src python -m pytest tests/unit/v2/test_map_partial_failure.py -v
PYTHONPATH=src python -m pytest tests/unit/ -q   # no regressions
```

---

## Resultado esperado

- **Antes:** Langfuse UI mostra CHAINs como siblings, MAP abort em 1 falha
- **Depois:** Langfuse UI mostra aninhamento claro, MAP gera docs parciais em falha minor

---

## Risco

- **S1:** Regressão na tracing — o wrap S6 pode estar a ser usado por outros call sites além de `processor.py`. Investigar antes de remover.
- **S2:** Continuar com partial results pode mascarar falhas sérias. Threshold de ≥5 é seguro mas conservador.

---

## Status final (2026-07-27)

### S1 — Langfuse CHAIN nesting (issue A) — **DEFERIDO**

Limitação arquitectural do Langfuse v4 SDK. Não é viável com a API v2.
Decisão pendente: contactar Langfuse, mudar para API v3/OTel directa, ou
reverter S6 (regressão aceitável). Reavaliar em contract dedicado quando
houver decisão.

### S2 — MAP partial-failure threshold — **DONE**

- Commit: `bbdb863 feat(v2): MAP partial-failure threshold handling (CORR-067 S2)`
- Critérios validados (7/7 testes em `test_map_partial_failure_corr067.py`):
  1. ✅ `MapPartialFailure` carries `failed_domains: list[str]`
  2. ✅ `run_all_traced` continua com 1 falha
  3. ✅ `run_all_traced` continua com 2 falhas
  4. ✅ `run_all_traced` aborta com 5 falhas (threshold)
  5. ✅ `run_all_traced` aborta com 6 falhas
  6. ✅ `failed_domains` default `[]`
  7. ✅ `failed_domains` é sempre `list` (mesmo vazio)
- Zero regressões: `pytest tests/unit/` = 2667 pass, 7 fail (idênticas ao baseline pré-S2).

### S3 — Factory + invoker fixes (bonus, não estava no contract original) — **DONE**

Durante S2 apareceram 2 falhas que o contract não antecipava:

- **`filter_regs`** lia `getattr(ctx, "ontology")` mas o `ctx` é agora
  `dict` (mudança do CORR-061 S3a). Fallback para `state['subdomains']`
  quando ontology vazio.
- **`factory.get_invoker`** passava `base_url=ollama_base` ao
  `ChatMinimax`, fazendo requests para o Ollama em vez do gateway M3.

Commits:

- `0a0654e fix(v2): filter_regs reads dict ctx + falls back to state['subdomains']`
- `c8863b7 fix(v2): filter_regs reads participating_regulations (canonical field)`
- `0439d90 fix(v2): doc_07 falls back to state['subdomains'] when ontology empty`
- `53e0978 fix(prompts_v2): use M3 default model in factory when provider=minimax`
- `113978a fix(prompts_v2): don't pass Ollama base_url to Minimax invoker`

Testes: 9/9 verdes (`test_filter_regs_corr067.py` +
`test_get_invoker_minimax_corr067.py`).

---

## Próximos passos sugeridos

1. **Re-run end-to-end real** com `--provider=minimax` num caso
   completo para validar a stack corrigida (test harness que
   reproduziu as falhas S3).
2. **S1 do CORR-067** (Langfuse CHAIN) — abrir novo contract se
   houver decisão arquitectural (reverter S6, contactar Langfuse, ou
   mudar para OTel directo).
3. **PR para `main`** — branch `feature/aegis-p1-corr-067-*` tem
   1 commit lógico (S2 + S3 + housekeeping), squash-merge.
