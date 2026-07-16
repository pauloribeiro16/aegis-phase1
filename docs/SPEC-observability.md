# SPEC — AEGIS-P1-OBS: Observabilidade Langfuse + Unificação de Invokers

**Versão:** 1.0
**Data:** 2026-07-16
**Autor:** Orchestrator (AEGIS)
**Strategy:** A — observabilidade-only (sem rewrite do orchestrator)
**Deploy:** Langfuse self-hosted (`localhost:3000`)
**Sucessor de:** [AEGIS-P1-CORR-008](../docs/CONTRACTS.md#corr-008)
**Decomposição:** 7 contracts (CORR-009 → CORR-015)

---

## 1. Contexto e problema

O `aegis-phase1` foi extraído do monólito `aegis-kg` (que tem Langfuse v4 + LangChain + LangGraph + token tracking correcto). Na extracção, a observabilidade **regrediu** porque a v2 construiu invokers próprios que não portaram o callback threading nem a extracção de tokens. Sintomas do utilizador:

- *"os logs estão uma merda, não sei o que cada chamada ao Ollama faz"*
- *"muitas coisas com tokens a 0"*

### Causas-raiz (4, verificadas por auditoria)

| # | Causa | Evidência | Impacto |
|---|-------|-----------|---------|
| C1 | 3 invokers paralelos fragmentados, sem logger partilhado | Layer A `prompts_v2/invoker.py`, Layer B `v2/llm.py:OllamaInvoker`, Layer C `llm/ollama.py:OllamaClient` (legacy, correcto mas não usado) | "Não sei o que cada chamada faz" |
| C2 | `_extract_usage` lê keys erradas (procura `token_usage`/`usage` formato OpenAI; Ollama usa `prompt_eval_count`/`eval_count`) | `prompts_v2/invoker.py:315,322`; 60/60 events com `total_tokens=0` | "Tokens a 0" |
| C3 | Nenhum callback Langfuse chega ao código activo — Layer A e B chamam `chat.invoke(msgs)` sem `config={"callbacks":[...]}` | `prompts_v2/invoker.py:167`, `v2/llm.py:119` | Sem traces no Langfuse |
| C4 | 788/848 linhas de log são ruído (retries de P1C-LLM-03 enquanto Ollama em baixo) | `llm-calls.jsonl` | "Logs são uma merda" |

### Padrão correcto já existente (a portar do aegis-kg)

| Item | Localização | O que faz |
|------|-------------|-----------|
| Token extraction correcto | `aegis-kg/core/agent/llm/ollama.py:142-162` | Lê `prompt_eval_count`/`eval_count` de `response_metadata` |
| Langfuse client + master switch | `aegis-kg/core/agent/tracing.py:179-215` | `get_langfuse_client()` gated por `LANGFUSE_ENABLED` |
| Callback inject no LangGraph | `aegis-kg/core/workflow/phase1/graph.py:270-272` | `run_config["callbacks"] = [handler]` |
| Self-hosted stack | `aegis-kg/docker-compose.yml` | Langfuse + worker + ClickHouse + Postgres + Redis + MinIO |

---

## 2. Objetivos e não-objetivos

### Objetivos

- **O1.** Todas as chamadas LLM da v2 (5 canónicas + MAP + 11 narrativas = 13 sites) aparecem no Langfuse UI com prompt + completion + tokens + latência.
- **O2.** `llm-calls.jsonl` mostra `total_tokens > 0` em 100% dos events de sucesso.
- **O3.** Um único invoker LLM no repo (sem fragmentação A/B/C).
- **O4.** Com `LANGFUSE_ENABLED=false`, a pipeline comporta-se identicamente a hoje (zero regressão).
- **O5.** Ruído de retries suprimido (≤1 error/spec quando Ollama down).

### Não-objetivos (explícitos — fora de scope)

- **N1.** Não reescrever o orchestrator como LangGraph (v2 mantém-se flat LOAD→MAP→REDUCE→OUTPUT). [User escolheu A sobre B.]
- **N2.** Não adicionar gates/fix-loops/interrupts do aegis-kg.
- **N3.** Não migrar para Langfuse Cloud (fica self-hosted).
- **N4.** Não portar o budget tracker do aegis-kg (deferred — contract futuro).
- **N5.** Não mexer nos prompts/templates (vivem no `Methodology-main`).

---

## 3. Arquitetura alvo

### 3.1 Componentes

```
┌─────────────────────────────────────────────────────────────┐
│  v2 Pipeline (NÃO mudar — orchestrator flat)                │
│  LOAD → MAP → 1B → REDUCE → OUTPUT                          │
└───────────────┬─────────────────────────────────────────────┘
                │ usa
                ▼
┌─────────────────────────────────────────────────────────────┐
│  UnifiedInvoker (NOVO — 1 classe, 2 métodos públicos)       │
│  ├─ .invoke_spec(spec_id, inputs)  → dict  (5 LLMs canónicos)│
│  └─ .invoke_raw(prompt, **kw)      → dict  (MAP + narrativas)│
│                                                              │
│  Ambos:                                                      │
│   • envolvem ChatOllama (já usado)                          │
│   • chamam llm.invoke(messages, config=config)  ← C3 fix    │
│   • extraem prompt_eval_count/eval_count         ← C2 fix   │
│   • respeitam MOCK_LLM branch                                │
└───────────────┬─────────────────────────────────────────────┘
                │ config=RunnableConfig(callbacks=[handler])
                ▼
┌─────────────────────────────────────────────────────────────┐
│  Langfuse CallbackHandler (quando LANGFUSE_ENABLED=true)    │
│  → envia traces para localhost:3000                          │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Design do UnifiedInvoker

```python
class UnifiedInvoker:
    """Single LLM invoker for all v2 LLM calls.

    Replaces Phase1LLMInvoker (Layer A) + OllamaInvoker (Layer B).
    Two public methods:
      - invoke_spec(spec_id, inputs): structured (5 canonical P1?-LLM-* LLMs)
      - invoke_raw(prompt, **kw): free-text (MAP domains + narratives)

    Both thread `config` (Langfuse) and extract Ollama tokens.
    """
    def __init__(self, model: str, prompts_root: Path | None = None,
                 langfuse_handler: CallbackHandler | None = None): ...

    def invoke_spec(self, spec_id: str, inputs: dict,
                    config: RunnableConfig | None = None) -> dict: ...
        # heavy: load prompt, render, invoke, robust parse, validate, log JSONL, retry

    def invoke_raw(self, prompt: str, *,
                   system: str | None = None,
                   config: RunnableConfig | None = None) -> dict: ...
        # light: build messages, invoke, return {raw, usage, latency_ms, status}
```

**Racional 2 métodos:** os 5 LLMs canónicos precisam de prompt-loading + parse + validate + JSONL log (lógica pesada do `Phase1LLMInvoker` actual). MAP + narrativas só precisam de chat→raw (lógica leve do `OllamaInvoker`). Colapsar tudo num só método forçaria os callers leves a passar por parsing desnecessário.

### 3.3 `config` threading

`RunnableConfig` é o mecanismo standard do LangChain para propagar callbacks. Thread do orchestrator → DomainProcessor/narratives → invoker. Quando `LANGFUSE_ENABLED=false`, `config` é `None` ou sem callbacks — zero overhead.

### 3.4 Master switch

`LANGFUSE_ENABLED` (default `false`). Lido em `get_langfuse_callback()` (portado de `aegis-kg/core/agent/tracing.py:179-215`). Quando `false`, devolve `(None, None)` — pipeline idêntico a hoje.

---

## 4. Mapeamento de call sites (inventário completo)

| Caller | Ficheiro:linha | Invoker actual | Método alvo | Notas |
|--------|----------------|----------------|-------------|-------|
| P1B-LLM-01 INTERPRETATION | `prompts_v2/phase1_executor.py:182` | Phase1LLMInvoker | `invoke_spec` | per-regulation |
| P1B-LLM-02 RATIONALE | `prompts_v2/phase1_executor.py:191` | Phase1LLMInvoker | `invoke_spec` | per-regulation |
| P1C-LLM-01 OVERLAP | `prompts_v2/phase1_executor.py:246` | Phase1LLMInvoker | `invoke_spec` | per-domain-lane |
| P1C-LLM-03 SYNTHESIS | `prompts_v2/phase1_executor.py:365` | Phase1LLMInvoker | `invoke_spec` | global reduce |
| P1C-LLM-02 COMPOUND | `prompts_v2/phase1_executor.py:379` | Phase1LLMInvoker | `invoke_spec` | global reduce |
| MAP D-XX | `v2/domain/processor.py:123` | OllamaInvoker | `invoke_raw` | 10 domains × ≤3 retries |
| Narrativa 04a (×2) | `v2/output/doc_04a.py:113,126` | OllamaInvoker via `_narrative.py:87` | `invoke_raw` | |
| Narrativa 04b | `v2/output/doc_04b.py:795` | OllamaInvoker via `_narrative.py:87` | `invoke_raw` | per-domain |
| Narrativa 04c | `v2/output/doc_04c.py:318` | OllamaInvoker via `_narrative.py:87` | `invoke_raw` | |
| Narrativa 04d (×2) | `v2/output/doc_04d.py:404,568` | OllamaInvoker via `_narrative.py:87` | `invoke_raw` | |
| Narrativa 05 | `v2/output/doc_05.py:413` | OllamaInvoker via `_narrative.py:87` | `invoke_raw` | §6 |
| Narrativa 07 | `v2/output/doc_07.py:348` | OllamaInvoker via `_narrative.py:87` | `invoke_raw` | |
| Narrativa 07b | `v2/output/doc_07b.py:269` | OllamaInvoker via `_narrative.py:87` | `invoke_raw` | |

**Total: 13 call sites** (5 spec + 1 MAP + 7 narrative files via 1 chokepoint `_narrative.py:87`).

---

## 5. Estratégia de migração (strangler pattern)

O utilizador quer: **coexistir durante o desenvolvimento, remover o velho só no fim quando testado**. Aplicado:

1. **Fases 1-3**: ambos os invokers (A+B) coexistem, ambos instrumentados independentemente. Risk baixo.
2. **Phase 4a**: criar `UnifiedInvoker` com ambas interfaces; migrar callers um-a-um (cada caller passa a usar UnifiedInvoker; os velhos continuam presentes mas não chamados).
3. **Phase 4b**: após tudo verde + Langfuse a mostrar traces unificadas, **deletar** `Phase1LLMInvoker` + `OllamaInvoker` + `OllamaClient` legado. Commit isolado, facilmente reversível.

---

## 6. Fases (7 contracts)

| Contract | Fase | Risk | Dep | Gate principal |
|----------|------|------|-----|----------------|
| **CORR-009** | 0 — Langfuse bring-up (docker + .env) | Mínimo | — | UI acessível em `localhost:3000` |
| **CORR-010** | 1 — Fix `_extract_usage` tokens=0 | Baixo | — | `total_tokens>0` em 100% events + unit test |
| **CORR-011** | 2 — Callback Layer A (5 LLMs) | Baixo-médio | 0,1 | Langfuse UI mostra 5 LLMs com tokens |
| **CORR-012** | 3 — Callback Layer B + tokens (MAP + narrativas) | Médio | 0,2 | Langfuse UI mostra MAP + narrativas |
| **CORR-013** | 4a — Criar UnifiedInvoker + migrar callers | Alto | 1,2,3 | Tudo verde; traces unificadas |
| **CORR-014** | 4b — Remover invokers velhos | Médio | 4a | Repo tem 1 invoker só; testes verdes |
| **CORR-015** | 5 — Suprimir retry-storm (C4) | Baixo | 1 | Ollama down → ≤1 error/spec |

Cada contract: branch própria (`feature/aegis-p1-corr-NNN`), 1 bug por contract, fast-forward merge, smoke gate via `scripts/test-quick.sh` (adaptado se necessário).

### Princípios transversais

- **Langfuse OFF por defeito** até CORR-011 estar mergeado e verificado.
- **Nenhum teste invoca Ollama real** — todos usam `MagicMock` com fixture `response_metadata` realista.
- **Cada fase prova o seu efeito** via gate negativo (Houdini-style): reverte o fix → teste falha → restaurar → passa.
- **Cada fase deixa `scripts/test-quick.sh` verde** (222+ passed).

---

## 7. Acceptance criteria (SPEC-level)

| AC | Descrição | Como verificar |
|----|-----------|----------------|
| AC1 | Run real (`MOCK_LLM` off, `LANGFUSE_ENABLED=true`) produz traces no Langfuse UI para **todos** os 13 call sites | Contar generations no UI da trace root; ≥13 |
| AC2 | `llm-calls.jsonl` pós-run mostra `total_tokens > 0` em 100% dos events sucesso | `grep total_tokens logs/phase1/llm-calls.jsonl \| grep -v ": 0}" \| wc -l` == total events sucesso |
| AC3 | Com `LANGFUSE_ENABLED=false`, `scripts/test-quick.sh` verde + diff de output idêntico a pré-migration | Comparar `output/phase1/*.md` com baseline |
| AC4 | Ollama em baixo → ≤1 `python_error` por spec em log (não 788) | Desligar Ollama, correr 1 spec, contar errors |
| AC5 | Repo tem **1** classe invoker LLM (sem Phase1LLMInvoker, OllamaInvoker, OllamaClient) | `grep -rE "class (Phase1LLMInvoker\|OllamaInvoker\|OllamaClient)" src/` → 0 matches |
| AC6 | Nenhum teste dispara Ollama real | `grep -rE "ChatOllama\|localhost:11434" tests/` → só em mocks/fixtures |
| AC7 | Todos os callers (13 sites) usam `UnifiedInvoker` | `grep -rE "Phase1LLMInvoker\|OllamaInvoker\|OllamaClient" src/` → 0 matches em callers |

---

## 8. Riscos e mitigações

| Risco | Prob | Impacto | Mitigação |
|-------|------|---------|-----------|
| Langfuse callback quebra LangChain (incompatibilidade versão) | Médio | Alto | `LANGFUSE_ENABLED=false` default; testar com mock primeiro; pin de versão |
| Token extraction diferente entre Ollama versões | Baixo | Médio | Usar ambos `response_metadata` + `usage_metadata` com fallback |
| UnifiedInvoker quebra parsing robusto do Phase1LLMInvoker | Médio | Alto | Strangler: migrar callers um-a-um com testes por caller; nunca big-bang |
| Docker compose do aegis-kg não arranca neste host | Baixa | Médio | Verificar portos (3000, 5432, 8123); `LANGFUSE_ENABLED=false` permite trabalhar sem |
| Narrativas param de renderizar se invoke_raw mudar contrato | Médio | Médio | `_narrative.py:87` chokepoint único — fácil de validar |
| Tests existentes partem-se ao mudar invoker | Médio | Médio | Mocks já cobrem; cada fase roda 222+ tests |

---

## 9. Configuração / env vars

```bash
# .env (a criar em CORR-009)
LANGFUSE_ENABLED=false                              # master switch (default off)
LANGFUSE_PUBLIC_KEY=pk-lf-...                       # do aegis-kg/.env
LANGFUSE_SECRET_KEY=sk-lf-...                       # do aegis-kg/.env
LANGFUSE_BASE_URL=http://localhost:3000             # self-hosted
```

`langfuse` promovido de `[tracing]` extra para dependência core em `pyproject.toml` (CORR-011).

---

## 10. Entregáveis finais

- `src/aegis_phase1/v2/llm.py` reescrito com `UnifiedInvoker` (1 classe).
- `src/aegis_phase1/prompts_v2/invoker.py` — `_extract_usage` corrigido; delega para UnifiedInvoker.
- `src/aegis_phase1/llm/tracing.py` — `get_langfuse_callback()` portado do aegis-kg com master switch.
- `src/aegis_phase1/v2/domain/processor.py` + `v2/output/_narrative.py` — thread `config`.
- `.env` + `.env.example` actualizados (em CORR-009).
- `pyproject.toml` — `langfuse` promovido a core dep (em CORR-011).
- `docs/CONTRACTS.md` — 7 novas entradas (CORR-009 → 015).
- `docs/OBSERVABILITY.md` (novo) — doc operacional: como ligar Langfuse, ler traces, interpretar tokens.

---

## 11. Estado

**APPROVED 2026-07-16.** Phase 0 (CORR-009) em curso.

---

## See also

- [`docs/CONTRACTS.md`](./CONTRACTS.md) — índice de contracts, follow-up de CORR-008.
- `AGENTS.md §10` — Branch Policy + Pre-flight Check.
- `aegis-kg/core/agent/tracing.py` — referência da implementação Langfuse.
- `aegis-kg/core/agent/llm/ollama.py:142-162` — referência da extracção de tokens.
- `aegis-kg/docker-compose.yml` — stack Langfuse self-hosted.
