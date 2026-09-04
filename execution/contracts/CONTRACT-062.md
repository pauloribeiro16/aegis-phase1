# CORR-062 — Close the loop: real-model end-to-end (Option A)

## Resumo

Contract **pequeno e focado** (4 sprints, ~1-2 dias), sequência natural
do CORR-061. O objectivo é testar a pipeline markdown-only com o **modelo
real** (`gemma4:e2b`), analizar os gaps vs reference, iterar se houver
ganhos óbvios, e fechar o ciclo (push da branch).

**Sprints:**
- **S0** — Cleanups pendentes do CORR-061 (langchain + S1.1 + base_system_prompt)
- **S1** — Real-model end-to-end run com gemma4:e2b (collect output + raw)
- **S2** — Gap analysis (per-doc similarity, categorizar problemas)
- **S3** — Iterate (prompts OU renderers, consoante os gaps); validação final

**Decisão do utilizador (2026-07-24):** "vamos planear o proximo contrato
o que sugeres?" → escolhida Opção A. "Isto não é para fazer
xlsx_generator migrar para markdown, é para fazer o xlxs" → xlsx fica
intocado (continua a ler typed state, decisão arquitectural fechada).

**Branch:** `feature/aegis-p1-corr-062-real-model-loop`
**Base:** `feature/aegis-p1-corr-061-markdown-only-phase1` (commit `4608f2e`)
**Data:** 2026-07-24

---

## Contexto

- O CORR-061 construiu a pipeline markdown-only (5 prompts, ContentValidator,
  8 renderers reescritos, raw capture). Sprint 5 validou com **mock LLM**
  e mostrou alignment MEDIUM-HIGH com reference (`Methodology-main/.../01_PHASE1_CONTEXT/`).
- **Falta o test natural:** correr com o modelo real `gemma4:e2b` (o
  hard constraint do utilizador) e ver o que sai. Mock LLM não exercita
  o caminho real do Ollama nem a variabilidade do modelo.
- 3 follow-ups do CORR-061 ainda abertos (cleanups) — incluídos em S0
  para fechar tudo de uma vez.
- O `xlsx_generator` foi explicitamente **excluído** deste contract:
  fica como está (typed state, não markdown). Decisão de design fechada.

---

## Design (norte)

O contract não muda arquitectura — só **opera** o que está construído e
**fecha os loops abertos**. Nenhuma decisão nova de design (a menos que
S2/S3 revele um blocker que force).

Se S2 mostrar que `gemma4:e2b` produz output **bem estruturado** (com
`## Status / ## Findings / ## Rationale` parseable), podemos avançar
para uma versão futura tipo Opção B (parsear markdown e injectar no
doc body). Se produzir **lixo**, sabemos que prompts precisam de mais
trabalho antes de mexer nos renderers.

---

## Sprint plan (4 sprints sequenciais)

### Sprint 0 — Cleanups (fecha follow-ups do CORR-061)

| | |
|---|---|
| **Objectivo** | Fechar os 3 follow-ups não-bloqueantes do CORR-061 S5 report |
| **Executor tasks** | (a) `pip install langchain langchain-core` em `../shared-venv/` (Langfuse tracing). (b) S1.1 cleanup: aplicar a rewrite do `## Post-generation Validation` (de "JSON Schema validation" para "Markdown parsing / Pydantic validation") aos 4 prompts que ficaram de fora do S1: `P1B-LLM-02-RATIONALE.md`, `P1C-LLM-01-OVERLAP-CLASSIFICATION.md`, `P1C-LLM-02-COMPOUND-EVENT.md`, `P1C-LLM-03-STRATEGIC-SYNTHESIS.md`. O gold reference é `P1B-LLM-01-INTERPRETATION.md` linhas 172-181. (c) Commit a working-tree change em `Methodology-main/00_METHODOLOGY/PROMPTS/base_system_prompt.md` (8 ins / 2 del, format-agnostic). (d) Verificar que `langfuse==4.14.1` e `langchain` ambos disponíveis no venv canónico. |
| **Validator tasks** | (a) `from langchain` resolves sem ImportError. (b) Mock LLM run mostra Langfuse callback wired (no "langfuse not installed, skipping" log). (c) `grep -E "JSON Schema validation" Methodology-main/00_METHODOLOGY/PROMPTS/P1*-LLM-*.md` → empty. (d) `git log` no `Methodology-main` mostra 5 novos commits (S1.1 cleanup) + 1 commit (base_system_prompt.md). (e) Tests no aegis-phase1 ainda passam. |
| **Deliverable** | Langchain instalado, S1.1 cleanup committed, base_system_prompt.md committed, Langfuse tracing funcional. ~1 commit no aegis-phase1 (config) + 5 commits no Methodology-main (S1.1) + 1 commit no Methodology-main (base_system_prompt). |
| **Tempo** | ~2h |

### Sprint 1 — Real-model end-to-end run

| | |
|---|---|
| **Objectivo** | Correr a pipeline completa com `gemma4:e2b` real e capturar todos os outputs |
| **Pré-requisito** | Ollama a correr (`ollama serve &` se necessário), `gemma4:e2b` pulled (já está, per preflight). |
| **Executor tasks** | (a) `rm -rf output/phase1` para run limpo. (b) `PYTHONPATH=src python -m aegis_phase1.v2.runner --case "$(pwd)/cases/case1-tinytask" --run-all-traced --model gemma4:e2b 2>&1 \| tee /tmp/corr062_run.log`. (c) Capture exit code, end-time, list de docs produced, count de raw files. (d) `tail -100 logs/phase1/gemma4_e2b/v2/pipeline_gemma4_e2b.log` para warnings/errors. (e) Se exit != 0, reportar e tentar re-correr com flags de recovery (ex: `--run-applicability` para Doc 04/05 só, depois `--run-map` para 06/07). |
| **Validator tasks** | (a) Verificar exit code 0 (ou aceitável se parcial). (b) Confirmar 5+ LLM call raw files em `output/phase1/raw/<spec>/`. (c) Confirmar 9 docs (04, 04a-d, 05, 06, 07, 07b) + 1 xlsx. (d) Inspect 3-5 raw `.md` files (1 por spec) para verificar se output segue o template `## Status / ## Findings / ## Rationale`. (e) Inspect `llm-calls.jsonl` para contagem de success/failure por spec. |
| **Deliverable** | 1 commit (validation report parcial em `execution/CORR-062-S1-RUN-LOG.md` com exit code, doc count, raw file count, sample raw outputs). Tempo real: ~10-20 min (a correr) + 30 min (analysis). |
| **Tempo** | ~1h wall time |

### Sprint 2 — Gap analysis

| | |
|---|---|
| **Objectivo** | Categorizar os gaps entre o que `gemma4:e2b` produziu e a reference |
| **Executor tasks** | Para cada um dos 9 docs produzidos: (a) Identificar o reference correspondente em `Methodology-main/.../01_PHASE1_CONTEXT/`. (b) Diff estrutural (head/tail de cada um, comparar secções). (c) Categorizar gaps em: **M**issing section (secção esperada não existe), **P**artial content (secção existe mas vazia/curta), **F**ormat issue (markdown mal-formado), **S**tructural diff (template diverge), **N**o issue (alinha bem). (d) Para cada gap, severity: HIGH (afecta a utilidade do doc), MED (cosmético), LOW (nit). (e) Agregar num relatório `execution/CORR-062-S2-GAP-ANALYSIS.md` com tabela per-doc. |
| **Validator tasks** | (a) Confirmar que cada um dos 9 docs tem um gap category assigned. (b) Confirmar que ≥ 5 docs são categorized com pelo menos 1 issue (não pode ser tudo "no issue" — a mock run mostrou gaps). (c) Sumário estatístico: contagem de gaps por category e por severity. |
| **Deliverable** | `execution/CORR-062-S2-GAP-ANALYSIS.md` com tabela per-doc. 1 commit. |
| **Tempo** | ~3-4h |

### Sprint 3 — Iterate + final validation

| | |
|---|---|
| **Objectivo** | Iterar com base nos gaps; validar que o loop está fechado |
| **Decisão** | Baseado no gap analysis: (a) Se gaps são **prompt-driven** (modelo não segue o template, emite JSON em vez de markdown, etc.) → ajustar prompts, re-run, re-analyse. (b) Se gaps são **renderer-driven** (LLM produziu OK mas o renderer não usa) → ajustar renderers para parsear o markdown. (c) Se gaps são **irreconciláveis** (e2b simplesmente não consegue) → documentar limitação, fechar contract com status "partial", abrir contract futuro (CORR-063) para explorar modelo maior. |
| **Executor tasks** | Variam. (a) Prompt iteration: editar 1-2 prompts, commit, re-run S1-style. (b) Renderer iteration: ajustar 1-2 renderers para extrair informação do markdown. (c) Documentation: `execution/CORR-062-CLOSING-REPORT.md` com o que foi feito, o que ficou, próximos passos. |
| **Validator tasks** | (a) Confirmar que exit code 0 no run final. (b) Confirmar que ≥ 50% dos gaps HIGH foram addressed. (c) Verificar Langfuse trace presente no UI (manual check pelo user; ou log inspection). (d) Test suite ainda verde. |
| **Deliverable** | N commits de iteração + `execution/CORR-062-CLOSING-REPORT.md` (1 commit). Branch pronta para push. |
| **Tempo** | ~4-6h (variável) |

**Total estimado:** ~10-13h wall time, distribuídos em 4 sprints.

---

## Validação

### Pré-flight (Sprint 0)

```bash
# 1. Working tree limpo (no aegis-phase1)
git status --short
# Esperado: clean (após merge de 061 — se for em branch separada, este contract começa em tree limpa)

# 2. Working tree do Methodology-main (pode ter working-tree changes pendentes)
cd /home/epmq-cyber/Área\ de\ Trabalho/projects/Methodology-main
git status --short
# Esperado: 1 file modified (base_system_prompt.md) — exactamente o que vamos committar

# 3. Módulos críticos importáveis (aegis-phase1)
source ../shared-venv/bin/activate
PYTHONPATH=src python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('OK')"

# 4. venv canónico (AGENTS.md §2)
which python
# Esperado: /media/.../venvs/epmq/shared-venv/bin/python

# 5. Ollama + gemma4:e2b disponível
ollama list | grep "gemma4:e2b"
# Esperado: 1 linha (já está pulled)
```

### Pós-flight (Sprint 3 — closing)

```bash
# (a) Exit 0 no run final
python -m aegis_phase1.v2.runner --case "$(pwd)/cases/case1-tinytask" --run-all-traced --model gemma4:e2b
echo $?  # esperado: 0

# (b) Raw files = N LLM calls
find output/phase1/raw/ -name '*.md' | wc -l
# esperado: ≥ N

# (c) Langfuse trace (manual)
# Open Langfuse UI, find trace for this run (tags phase:phase1, case:case1-tinytask)

# (d) Langchain integration now works
grep "langfuse not installed" logs/phase1/gemma4_e2b/v2/pipeline_gemma4_e2b.log | head -3
# esperado: empty
```

---

## Não-objectivos (intencionalmente fora)

- **Não migro xlsx_generator para markdown.** Decisão do utilizador: xlsx
  fica como está, lê typed state. Nenhuma alteração a xlsx_generator.py
  ou à sua chamada.
- **Não re-arquitecturo os renderers** para parsear markdown. Se S2
  mostrar que faz sentido, isso vai para um contract futuro (CORR-063+).
- **Não mudo o modelo.** `gemma4:e2b` é hard constraint.
- **Não mexo nos 4 Phase 1B/C prompts** (S1 já os reescreveu; S1.1 só
  faz cleanup do Post-gen Validation).
- **Não faço push da branch.** Commits ficam local; o utilizador
  faz push quando decidir.

---

## Riscos & mitigações

| Risco | Mitigação |
|---|---|
| `gemma4:e2b` produz output muito degradado e a iteração é longa | S3 aceita "partial" como outcome; documenta limitação |
| Langchain install quebra outras deps do venv | `pip install` em venv isolado (já é); rollback se tests falharem |
| Real-model run demora mais de 20 min | timeout 1200s no comando; reportar partial output |
| Working tree de Methodology-main tem mais changes do que o expected | Sprint 0 reporta e o user decide commit-by-commit |
| S3 prompt iteration não melhora similarity (e2b hard cap) | Documentar; propor Opção B como próximo contract |

---

## Métricas de fecho

| Métrica | Alvo |
|---|---|
| Exit code do run real | 0 |
| Docs gerados (de 5: 04, 05, 06, 07, 07b) | 5+ |
| Raw files escritos | ≥ N LLM calls |
| Langfuse trace presente | sim |
| Gaps HIGH addressed | ≥ 50% |
| Test suite passa | sim |
| Branch | `feature/aegis-p1-corr-062-real-model-loop` |
| Commits totais | 8-15 (1 contract + 1 S0 config + 4-5 S1.1 prompts + 1 base + S2 report + S3 iterations + S3 closing) |

---

## Subagentes — orquestração

Mesma estrutura que CORR-061:
- Cada sprint: 1 executor + 1 validator (via `task` tool; `mavis team plan`
  CLI não está disponível neste environment).
- Pre-flight antes de cada dispatch.
- Validator faz independent verification (re-derive, não trust).

**Sequência**: S0 (executor) → S0 (validator) → S1 (executor) → S1 (validator) → ... → S3 (validator).

**Comunicação entre sprints**: cada executor lê o output do sprint
anterior (commits, relatórios) e age em conformidade.
