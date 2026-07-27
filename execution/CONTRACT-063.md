# CORR-063 — Logging best practices + Langfuse organisation

## Resumo

Contract **focado** (4 sprints, ~3-4h), sequência natural do CORR-062
S2 (M3 integration). O objectivo é resolver **3 problemas concretos**
identificados durante a análise do S1 (PID 3033454):

1. **S1 crash silencioso** — o pipeline aborta sem traceback no log,
   impossível diagnosticar sem re-correr com mais verbosidade.
2. **`print()` em vez de `logger`** — mensagens de erro hardcoded
   ("Ollama not reachable") que não passam por handler, não têm
   nível, não vão para ficheiro.
3. **Langfuse sem grouping** — 18 traces por run sem `session_id`,
   impossível filtrar por run na UI.

**Decisão do utilizador (2026-07-27):** "implementa isso tudo com um
contrato de implementação executor e validador" → confirma
implementação dos blocos A-E do plano combinado.

**Branch:** `feature/aegis-p1-corr-063-logging-and-langfuse`
**Base:** `feature/aegis-p1-corr-062-real-model-loop` (commit `ae5251b`)
**Data:** 2026-07-27

---

## Contexto

- CORR-062 S2 fechou o M3 integration (5 fixes, 21 calls M3 com
  sucesso). Mas o S1 final correu sem output porque crashou
  silenciosamente após a call #21, com um único 529 transient no log.
- A mensagem `"Ollama not reachable at https://api.minimax.io/anthropic"`
  no fim do log mostra que o código lança `OllamaUnreachableError`
  mesmo quando o provider é MiniMax — herança do desenho Ollama-only.
- O Langfuse UI tem 18 traces por run sem agrupamento. Cada node
  LangGraph cria trace próprio com nomes diferentes (CHAIN
  `map_D08` vs GENERATION `MAP D-08 Human Factors`) que confundem
  a navegação.
- A refactorisation para logging centralizado é um **investimento
  único** que paga em todos os contracts futuros: diagnosticar crashes
  sem adivinhar, ligar DEBUG quando preciso, ler logs de ficheiro
  sem `tail -f` infinito.

---

## Design (norte)

O contract não muda arquitectura do pipeline. É **infraestrutura de
observabilidade** — logging + tracing. Nenhuma decisão nova de design
na pipeline em si.

**Princípios:**
1. **Single source of truth** — uma função `setup_logging()` chamada
   uma vez no `main()`. Idempotente.
2. **Levels via flag** — `--log-level DEBUG|INFO|WARNING|ERROR`.
   Default `INFO`. DEBUG só quando diagnostico.
3. **Console sempre, ficheiro opcional** — `--log-file logs/run.log`
   para guardar o log completo de um run. Sem ficheiro → só stdout.
4. **`print()` é forbidden** — qualquer mensagem de erro usa
   `logger.error()` (com `exc_info=True` para traceback).
5. **Langfuse grouping** — `session_id = run_id` (UUID por run)
   + `user_id = case_name` agrupa os 18 traces na UI.

```
ANTES:
  Mixed logger/print, sem flag verbose, Langfuse com 18 traces soltos
DEPOIS:
  Centralized setup + --log-level flag, top-level try/except,
  Langfuse com session_id=user_id por run
```

---

## Sprint plan (4 sprints sequenciais)

### Sprint 1 — Logging infrastructure (Bloco A + B)

| | |
|---|---|
| **Objectivo** | Setup centralizado + flag CLI + substituir `print()` por `logger` |
| **Executor tasks** | (a) Criar `src/aegis_phase1/utils/logging.py` com `setup_logging(level, log_file)` idempotente. Formato: `%(asctime)s \| %(levelname)-7s \| %(name)-30s \| %(message)s`. (b) Adicionar `--log-level` e `--log-file` ao argparse do `runner.py`. (c) Chamar `setup_logging(args.log_level, args.log_file)` no `main()`. (d) Substituir `print(f"⚠ Ollama not reachable...")` por `logger.error(..., exc_info=False)` em `runner.py:489-491` e `runner.py:808-811`. (e) Smoke test: `from aegis_phase1.utils.logging import setup_logging; setup_logging("DEBUG", "/tmp/test.log")` não raise. |
| **Validator tasks** | (a) `python -m pytest tests/unit/` passa (sem regressões). (b) `--help` mostra as duas novas flags. (c) Inspecção manual: o ficheiro de log tem timestamps reais e format consistente. (d) Confirmar que as 2 mensagens hardcoded de "Ollama not reachable" deixam de ser `print()` (grep no source). |
| **Deliverable** | 1 commit (logging infra). ~80 LOC em 2 ficheiros (1 novo + 1 modificado). |
| **Tempo** | ~45 min |

### Sprint 2 — Stage transitions + top-level try/except (Bloco C)

| | |
|---|---|
| **Objectivo** | Diagnóstico do S1 — saber onde crasha |
| **Executor tasks** | (a) Adicionar `logger.info("STAGE N: <name>")` antes de cada stage (LOAD, MAP, 1B, REDUCE, OUTPUT) no `orchestrator.py`. (b) Adicionar `logger.info("<stage> complete: N/M items (%.1fs)")` depois. (c) Wrap o `graph.invoke(...)` no `runner.py:782` (e 689, 691) com `try/except` que chama `logger.exception("graph.invoke raised — pipeline aborted")` e re-raise. (d) Smoke test: kill o processo via `Ctrl+C` (SIGINT) e ver que o handler apanha e loga. (e) Forçar uma excepção (mock) num node e confirmar que aparece no log. |
| **Validator tasks** | (a) Run com `--mock-llm` (MOCK_LLM=true) mostra os 5 stage logs na ordem correcta. (b) Inserir `raise RuntimeError("test")` num node de teste, correr, confirmar que aparece no log. (c) Confirmar que o pipeline continua a produzir os mesmos docs (sem regressão funcional). |
| **Deliverable** | 1 commit (stage transitions). ~30 LOC em 2 ficheiros. |
| **Tempo** | ~45 min |

### Sprint 3 — DEBUG logs (Bloco D)

| | |
|---|---|
| **Objectivo** | Verbose mode funcional — HTTP req/res e LLM I/O visíveis com `--log-level DEBUG` |
| **Executor tasks** | (a) `chat_minimax._generate`: `logger.debug(...)` da request (URL, model, max_tokens, messages count, system length) ANTES do POST. `logger.debug(...)` da response (status, latency, input/output tokens) DEPOIS. (b) `unified.invoke_raw`: `logger.debug("invoke_raw called: prompt_len=%d, feedback=%r")` e `logger.debug("invoke_raw result: status=%s, raw_len=%d")`. (c) `unified.invoke_spec`: idem para heavy path. (d) Nenhum dos DEBUG logs inclui `Authorization` header, `x-api-key`, ou conteúdo de `system` prompt (privacidade). (e) Smoke test: chamar `--log-level DEBUG` num run mock e confirmar que aparecem os logs detalhados. |
| **Validator tasks** | (a) Grep nos DEBUG logs: nenhum match para `sk-cp-` ou `Authorization`. (b) Run com `--log-level INFO` (default) NÃO mostra os DEBUG logs (filtrados pelo level). (c) Latência adicional do logging < 5% num run com 30 calls (overhead aceitável). |
| **Deliverable** | 1 commit (DEBUG logs). ~25 LOC em 2 ficheiros. |
| **Tempo** | ~30 min |

### Sprint 4 — Langfuse session_id + user_id (Bloco E)

| | |
|---|---|
| **Objectivo** | Os 18 traces de um S1 run ficam agrupáveis na UI via filtro `session_id` |
| **Executor tasks** | (a) `tracing.py:get_langfuse_callback`: aceitar `run_id` param, devolver UUID fresh se None. Adicionar `session_id=effective_run_id`, `user_id=case_name` ao `trace_context`. (b) `tracing.py`: tag `run:<8-char-prefix>` adicionado a `handler.tags`. (c) `runner.py:main()`: gerar `run_id = uuid.uuid4()` no início, passar para o orchestrator. (d) `orchestrator.py`: passar `run_id` para `get_langfuse_callback(run_id=...)`. (e) Não quebrar callers existentes — default de `run_id=None` mantém comportamento actual. |
| **Validator tasks** | (a) Inspecção API Langfuse: o trace mais recente tem `sessionId` e `userId` não-nulos. (b) Filtrar traces por `sessionId=<run_id>` no UI Langfuse devolve os 18 nodes do run (verificação manual). (c) Run mock (MOCK_LLM=true) também passa o run_id. (d) Cache key em `_langfuse_cache` inclui `run_id` — duas runs paralelas não partilham handler. |
| **Deliverable** | 1 commit (Langfuse grouping). ~15 LOC em 3 ficheiros. |
| **Tempo** | ~30 min |

**Total estimado:** ~2.5-3h wall time, distribuídos em 4 sprints.

---

## Validação

### Pré-flight (Sprint 1)

```bash
# 1. Working tree (pode ter deletions pendentes do CORR-062 S2)
git status -s
# Esperado: D output/phase1/baseline_pre_corr036/* (pode ser ignorado)

# 2. Módulos críticos importáveis
PYTHONPATH=src ../shared-venv/bin/python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('OK')"

# 3. Test suite verde antes
PYTHONPATH=src ../shared-venv/bin/python -m pytest tests/unit/llm/ tests/unit/prompts_v2/ --no-header | tail -3
# Esperado: 248 passed, 7 failed (pre-existing), 10 skipped
```

### Pós-flight (Sprint 4)

```bash
# (a) --log-level flag funciona
python -m aegis_phase1.v2.runner --help 2>&1 | grep -E "log-level|log-file"
# Esperado: 2 flags listadas

# (b) Log file tem formato consistente
head -5 logs/s1_m3_debug.log
# Esperado: 5 linhas formato "2026-07-27 16:00:00 | INFO    | logger_name | message"

# (c) DEBUG logs aparecem só com --log-level DEBUG
grep "DEBUG" logs/s1_m3_debug.log | head -3
# Esperado: vários matches (request/response, timings)

# (d) Sem credenciais no log
grep -E "sk-cp|Authorization|x-api-key" logs/s1_m3_debug.log
# Esperado: empty

# (e) Langfuse: run_id + case_name aparecem em sessionId/userId
curl -s -H "Authorization: Basic <b64>" "http://localhost:3000/api/public/traces?limit=1" | python3 -c "
import sys, json
t = json.load(sys.stdin)['data'][0]
print('sessionId:', t.get('sessionId'))
print('userId:', t.get('userId'))
print('name:', t.get('name'))
"
# Esperado: sessionId = UUID, userId = case1-tinytask, name = AEGIS Phase 1 ...
```

### S1 validation run (manual, after all sprints)

```bash
# Re-lançar S1 com M3 + verbose
nohup /tmp/run_s1_m3.sh > /tmp/s1_m3_v2.log 2>&1 &
# Log file:
PYTHONPATH=src /home/epmq-cyber/Área\ de\ Trabalho/projects/shared-venv/bin/python \
  -m aegis_phase1.v2.runner --case "$(pwd)/cases/case1-tinytask" \
  --run-all-traced --provider minimax --model minimax/MiniMax-M3 \
  --log-level DEBUG --log-file logs/s1_m3_debug.log

# Verificar:
# - Exit code 0 ou output docs gerados (5+)
# - Log file tem stage transitions visíveis
# - Sem tracebacks
# - Top-level try/except não disparou
```

---

## Não-objectivos (intencionalmente fora)

- **Não migro xlsx_generator nem os renderers.** Foco é observability.
- **Não re-arquitecturo o pipeline.** Mantém-se a estrutura LangGraph.
- **Não mudo o modelo.** M3 continua como referência.
- **Não faço push da branch.** Commits locais; user decide.
- **Não implemento JSON structured logs** (Camada 5 do plano) — só
  se for explicitamente pedido. Para já, formato texto legível.
- **Não removo o `OllamaUnreachableError` legacy code** — só os
  catches do runner. Domain processor mantém o nome (re-arquitectura
  maior fica para contract futuro).

---

## Riscos & mitigações

| Risco | Mitigação |
|---|---|
| Mudar logging config quebra outros módulos que dependem do setup existente | Idempotente (`setup_logging` verifica se já há handlers). Test suite valida. |
| `--log-file` em path sem permissão | Path criado com `mkdir -p` no setup. Erro claro se não conseguir. |
| DEBUG logs vazam credenciais | Contract diz "nenhum DEBUG log inclui Authorization/x-api-key". Validator faz grep. |
| Langfuse session_id grouping confunde runs paralelas | Cache key inclui `run_id` — cada run tem o seu handler. |
| S1 ainda crasha mesmo com o try/except top-level | Se o handler não apanhar, o stacktrace aparece no log. Aí decidimos próximo passo. |

---

## Métricas de fecho

| Métrica | Alvo |
|---|---|
| Test suite passa | sim (sem regressões) |
| Linhas modificadas | ~150 LOC em ~5 ficheiros |
| Commits totais | 4 (1 por sprint) |
| New flag `--log-level` | funciona, validado |
| New flag `--log-file` | funciona, validado |
| Langfuse `sessionId` não-nulo | sim, para o run mais recente |
| Top-level try/except no runner | sim, com logger.exception |
| S1 re-run com verbose produz output ou traceback claro | sim |

---

## Subagentes — orquestração

Mesma estrutura que CORR-061/062:
- Cada sprint: 1 executor (implementa) + 1 validator (verifica independentemente).
- Pre-flight antes de cada dispatch (AGENTS.md §10.1).
- Validator faz independent verification (re-derive, não trust).

**Sequência**: S1 (executor) → S1 (validator) → S2 (executor) → S2 (validator) → ... → S4 (validator).

**Comunicação entre sprints**: cada executor lê o output do sprint
anterior (commits) e age em conformidade.

Para este contract, **eu próprio (Mavis/M3) faço os 4 sprints** —
é pequeno (~3h) e a iteração é rápida. Validators são Mavis também
mas com prompt de "verify independently" + checagens concretas.
