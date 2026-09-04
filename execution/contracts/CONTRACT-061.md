# CORR-061 — Markdown-only Phase 1 v2 (1 contract, 5 sprints)

## Resumo

Contract grande, dividido em **5 sprints sequenciais**, cada um com par
**executor + validator** (subagentes). Substitui a arquitectura actual de
**5 LLM specs (4 JSON + 1 markdown)** por **5 specs (todos markdown-only)**,
com:

- **Prompts** reescritos para produzirem **só markdown** (zero JSON, zero envelope).
- **Validator** substituído por **content-check** ("produziu algo ou não").
- **State** muda de `dict` tipado para **markdown acumulado por spec**.
- **Renderers** passam a **compor markdown** (em vez de renderizar dicts tipados).
- **Capture** de cada chamada LLM em `output/phase1/raw/<spec>/<ts>__attempt<N>.{md,json}`.
- **Langfuse** já fica activo (venv fix anterior).
- **Modelo canónico:** `gemma4:e2b` (hard constraint, conforme decisão do utilizador).

**Decisão do utilizador (2026-07-24):** "deves mudar os prompts de forma a eles
produzirem markdown apenas e nada de json" + "quero que detestes apenas se ele
não produziu nada" + "deve ser o modelo gemma4 e2B" + "1 contract, várias
sprints com subagentes validadores e executores".

**Branch:** `feature/aegis-p1-corr-061-markdown-only-phase1`
**Base:** `feature/aegis-p1-corr-060-multi-model-eval` (commit `8feaf40`)
**Data:** 2026-07-24

---

## Contexto

- A pipeline actual (5 specs, 4 JSON + 1 markdown) foi desenhada com 3
  camadas de strictness que se reforçam: `RobustParser` (8 estratégias JSON)
  + `MarkdownParser` (só para P1B-LLM-01) + `Phase1Validator` (Draft-7
  hand-rolled). Resultado: 31% OK / 23% SCHEMA_ERROR / 46% empty response
  no último run real (ver CORR-056 final report).
- A contradição schema↔prompt (schema exige envelope, prompt proíbe) +
  `minLength: 200` em `synthesis.rationale` + `minItems: 1` em
  `sub_domain_activations` são **wishes aspiracionais**, não justificáveis
  pelo que `gemma4:e2b` consegue produzir.
- O `gemma4:e2b` (2B efectivos) é **hard constraint** — o GPU disponível
  não aguenta mais, e o utilizador confirmou `deve ser o modelo gemma4 e2B`.
- O output dos 9 doc renderers (Doc 04a-d, 05, 06, 07, 07b) já é markdown.
  A "tipagem" intermédia (JSON state) é overhead — o modelo pode produzir
  directamente o que o renderer consome.
- A referência de comparação fica em
  `Methodology-main/.../Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/` (docs
  finais do case 1, em markdown).

---

## Design novo (north star)

```
ANTES:  5 LLM specs (4 JSON + 1 markdown)
        → RobustParser (8 estratégias JSON) + MarkdownParser (1 spec)
        → Phase1Validator (JSON Schema, required/minLength hand-rolled)
        → state tipado (dict)
        → 9 doc renderers (consomem dict)

DEPOIS: 5 LLM specs (todos markdown-only)
        → ContentValidator (só "produziu algo ou não", ≥ 50 chars)
        → state markdown acumulado (`per_spec_markdown: {spec_id: md_text}`)
        → 9 doc renderers (comõem markdown)
        → output/phase1/raw/<spec>/<ts>__attempt<N>.{md,json}
        → Langfuse live trace
```

**Princípio:** menos strictness, mais observabilidade. Aceitar o que o modelo
produz (parcial, messy) e tornar visível.

---

## Sprint plan (5 sprints sequenciais)

Cada sprint: 1 executor (implementa) + 1 validator (verifica independentemente).
**1 contract cobre tudo** — sprints são sub-divisões lógicas, não contracts separados.

### Sprint 0 — Archive legacy + bootstrap nova estrutura

| | |
|---|---|
| **Objectivo** | Mover a implementação actual de 5-spec-JSON para `archive/`; criar a nova estrutura de directórios |
| **Executor tasks** | (a) Mover `prompts_v2/robust_parser.py`, `prompts_v2/validator.py`, `prompts_v2/markdown_parser.py`, `prompts_v2/output_schemas.yaml` para `src/aegis_phase1/_archive/corr061/` (preservar git history via `git mv`). (b) Criar directórios vazios: `src/aegis_phase1/prompts_v2/markdown/`, `src/aegis_phase1/validator/`, `src/aegis_phase1/state_markdown/`, `src/aegis_phase1/v2/output_markdown/`. (c) Não tocar em código activo ainda — só estrutura. |
| **Validator tasks** | (a) Verificar que o `archive/` tem os 4 ficheiros movidos e git-tracked. (b) Verificar que os 4 directórios novos existem. (c) `pytest tests/unit/ --co -q` — collection ainda funciona (não há mudanças em código activo, mas confirma). |
| **Deliverable** | Estrutura nova vazia mas pronta; código antigo preservado em `archive/`. |
| **Tempo** | ~1h |

### Sprint 1 — Markdown-only prompts (5 specs)

| | |
|---|---|
| **Objectivo** | Reescrever os 5 prompts (`P1B-LLM-01`, `P1B-LLM-02`, `P1C-LLM-01`, `P1C-LLM-02`, `P1C-LLM-03`) para produzirem **só markdown** |
| **Template markdown proposto** | `## Status` (applicable + confidence), `## Findings` (lista bullets), `## Rationale` (texto ≥ 1 parágrafo) — validação do utilizador já obtida |
| **Executor tasks** | Para cada um dos 5 prompts: (a) Abrir o `P1*-LLM-*.md` em `Methodology-main/00_METHODOLOGY/PROMPTS/`. (b) Reescrever o `<output_contract>` para markdown template (acima). (c) Remover todas as referências a JSON, `prompt_spec_id`, `schema_version`, envelope. (d) Manter as `<role>`, `<inputs>`, `<instructions>` intactas. (e) Commit por prompt (5 commits ou 1 batch — decisão do executor). |
| **Validator tasks** | (a) `grep -l 'JSON\|json\|prompt_spec_id' Methodology-main/00_METHODOLOGY/PROMPTS/P1*-LLM-*.md` — esperado: empty (ou apenas "no JSON output" como instrução negativa). (b) `grep -c '## ' Methodology-main/00_METHODOLOGY/PROMPTS/P1*-LLM-*.md` — esperado: ≥ 3 (Status, Findings, Rationale). (c) Dry-run **opcional** com 1 chamada e2b (se Ollama up): confirmar output é markdown. |
| **Deliverable** | 5 prompts novos em `Methodology-main/00_METHODOLOGY/PROMPTS/P1*-LLM-*.md`, todos markdown-only. |
| **Tempo** | ~2-3h |

### Sprint 2 — Content-only validator (substitui JSON Schema)

| | |
|---|---|
| **Objectivo** | Substituir `Phase1Validator` (JSON Schema) por `ContentValidator` ("tem conteúdo ou não") |
| **Executor tasks** | (a) Criar `src/aegis_phase1/validator/content_check.py` com classe `ContentValidator` que retorna `OK` se `len(raw.strip()) >= 50` chars, `INSUFFICIENT_EVIDENCE` caso contrário. (b) Actualizar `prompts_v2/invoker.py:__init__` para aceitar `validator` opcional (default = `ContentValidator`). (c) Manter o `Phase1Validator` em `_archive/corr061/` (não apagar). (d) Adicionar `tests/unit/validator/test_content_check.py` (3-5 testes: empty, whitespace, short prose, full markdown, long prose). |
| **Validator tasks** | (a) `pytest tests/unit/validator/test_content_check.py -v` — esperado: 3-5 passed. (b) Confirmar que `Phase1Validator` ainda está em `_archive/` (não foi apagado). (c) `grep -rn 'Phase1Validator' src/aegis_phase1/prompts_v2/` — esperado: apenas em imports do archive, não no path activo. |
| **Deliverable** | `ContentValidator` activo; `Phase1Validator` arquivado. |
| **Tempo** | ~1h |

### Sprint 3 — Markdown state + renderers (com auditoria de tolerance Q3)

| | |
|---|---|
| **Objectivo** | Reescrever 9 doc renderers para consumirem markdown; **auditar tolerance** dos renderers (pergunta Q3 do plano) |
| **Q3 audit (corre dentro do sprint)** | Antes de reescrever renderers, o **executor** corre `python -c "from aegis_phase1.v2.output.doc_05 import render_doc_05; help(render_doc_05)"` e inspecciona o código para classificar cada renderer: (a) **strict** — falha se campo em falta; (b) **best-effort** — placeholder se em falta. Reporta o resultado como parte do sprint deliverable. |
| **Executor tasks** | (a) Adicionar `state["per_spec_markdown"] = {spec_id: md_text}` ao `orchestrator.py:load()`. (b) Reescrever cada um dos 9 renderers (`doc_04a`, `doc_04b`, `doc_04c`, `doc_04d`, `doc_05`, `doc_06`, `doc_07`, `doc_07b`, e `xlsx_generator`) para consumir `state["per_spec_markdown"]` em vez do state tipado. (c) Manter o template de cada doc (placeholders, structure) — só mudar a fonte de dados. (d) Commit por renderer. |
| **Validator tasks** | (a) `python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-applicability --mock-llm` (fast deterministic path) — esperado: exit 0. (b) `python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-clauses --mock-llm` — esperado: exit 0. (c) Comparar output com `Methodology-main/.../Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/*.md` — esperado: estrutura preserved, dados parciais onde LLM mock não preenche. (d) Reportar Q3 audit (tolerance classificação). |
| **Deliverable** | 9 renderers reescritos; Q3 audit publicado. |
| **Tempo** | ~3-4h (incluindo Q3 audit) |

### Sprint 4 — Folder capture (raw markdown por chamada)

| | |
|---|---|
| **Objectivo** | Cada chamada LLM escreve o seu output markdown + metadata num ficheiro em `output/phase1/raw/` |
| **Executor tasks** | (a) Adicionar método `_persist_raw_call(spec_id, attempt, prompt_system, prompt_user, raw_response, parsed_output, status, latency_ms, model)` a `prompts_v2/invoker.py`. (b) Escreve `output/phase1/raw/<spec_id>/<YYYY-MM-DDTHH-MM-SS>__attempt<N>.md` com o raw_response markdown + um cabeçalho YAML com metadata. Escreve também `<same>__attempt<N>.json` com metadata estruturada. (c) Invocar em **todo** o attempt (sucesso ou falha), antes de retornar. (d) Configurável via env `AEGIS_RAW_OUTPUT_DIR` (default `output/phase1/raw`). (e) Adicionar `tests/unit/prompts_v2/test_raw_capture.py` (2-3 testes: file created, content matches, JSON valid). |
| **Validator tasks** | (a) `pytest tests/unit/prompts_v2/test_raw_capture.py -v` — esperado: 2-3 passed. (b) Run smoke (`--run-applicability --mock-llm`); `find output/phase1/raw/ -name '*.md' | wc -l` — esperado: ≥ N (N = número de LLM calls). (c) `head -1` de um dos `.md` deve mostrar YAML header com `spec_id`, `attempt`, `model`. |
| **Deliverable** | Captura raw em `output/phase1/raw/<spec>/<ts>__attempt<N>.{md,json}`. |
| **Tempo** | ~1h |

### Sprint 5 — Validação end-to-end + reference comparison (validator-only)

| | |
|---|---|
| **Objectivo** | Validar sucesso: (c) pipeline end-to-end + (d) reference comparison |
| **Tasks** | (a) `python -m aegis_phase1.v2.runner --case "$(pwd)/cases/case1-tinytask" --run-all --model gemma4:e2b` — esperado: exit 0, todos os 9 docs escritos. (b) Comparar `output/phase1/AEGIS-P1-*.md` com `Methodology-main/.../Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/*.md` usando **similarity score** (Levenshtein ratio ou sentence-embeddings cosine) — alvo: ≥ 70% em prose, exact match em cabeçalhos/templated structure. (c) Verificar que `output/phase1/raw/<spec>/` tem 1 ficheiro por LLM call. (d) Verificar que Langfuse UI mostra 1 trace por run (se `.env` tem keys). (e) Reportar gaps num `CORR-061-VALIDATION-REPORT.md`. |
| **Sucesso = sim se** | (a) exit 0, (b) similarity ≥ 70%, (c) raw files = N calls, (d) Langfuse trace presente. |
| **Se sucesso** | Contract done. |
| **Se gaps** | Iterar com sprint adicional (S6?) ou aceitar gaps documentados. |
| **Tempo** | ~1-2h |

**Total estimado:** ~10-12h, distribuídos em 5 sprints.

---

## Validação

### Pré-flight (antes do Sprint 0)

```bash
# 1. Working tree deve estar limpo (excepto AGENTS.md que já está staged para commit)
git status --short
# Esperado: " M AGENTS.md" (1 file modified)

# 2. Branch actual
git branch --show-current
# Esperado: feature/aegis-p1-corr-061-markdown-only-phase1 (após criação)

# 3. Módulos críticos importáveis
python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('orchestrator OK')"
python -c "from aegis_phase1.v2.runner import main; print('runner OK')"
python -c "from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker; print('invoker OK')"

# 4. Test collection ainda funciona
pytest tests/unit/ --co -q 2>&1 | tail -3
# Esperado: "N tests collected" sem ERROR

# 5. venv canónico activo (linha AGENTS.md §2)
source ../shared-venv/bin/activate
which python
# Esperado: /media/.../venvs/epmq/shared-venv/bin/python
```

### Pós-flight (Sprint 5 — success criteria)

```bash
# (a) Pipeline end-to-end
python -m aegis_phase1.v2.runner --case "$(pwd)/cases/case1-tinytask" --run-all --model gemma4:e2b
echo $?  # esperado: 0

# (b) Reference comparison
for doc in output/phase1/AEGIS-P1-04.md output/phase1/AEGIS-P1-05.md output/phase1/AEGIS-P1-06.md output/phase1/AEGIS-P1-07.md output/phase1/AEGIS-P1-07b.md; do
    echo "=== $doc ==="
    diff <(head -50 "$doc") <(head -50 "Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/$(basename $doc | sed 's/AEGIS-P1-//;s/^/0/;s/^00//').md" 2>/dev/null) | head -10
done
# Esperado: estrutura preserved, dados parciais onde LLM não preencheu

# (c) Raw capture
find output/phase1/raw/ -name '*.md' | wc -l
# Esperado: ≥ N (número total de LLM calls do run)

# (d) Langfuse (se .env configurado)
grep "LANGFUSE_ENABLED" src/.env
# Esperado: LANGFUSE_ENABLED=true (opcional; se false, ok também)
```

---

## Não-objectivos (intencionalmente fora)

- **Não re-escrevo prompts além dos 5 P1*-LLM-***. Outros prompts
  (Phase 2, Phase 3, base_system_prompt) ficam intactos.
- **Não melhoro o modelo.** `gemma4:e2b` é hard constraint.
- **Não crio error budgets, Pydantic models novos, ou modo strict.** O
  schema-aspirational vai para arquivo.
- **Não mexo em tooling downstream** (Neo4j, ETL Phase 2/3) — o utilizador
  confirmou para ignorar.
- **Não altero o case.yaml ou os inputs** — trabalho é só no pipeline.
- **Não crio tests além dos 1-2 por sprint** (smoke tests apenas).
- **Não commito em `main`** — sempre na branch do contract (AGENTS.md §10).

---

## Riscos & mitigações

| Risco | Mitigação |
|---|---|
| Archive dos ficheiros parte o `git blame` / `git log --follow` | Usar `git mv` (preserva history). Documentar no commit message. |
| Renderers reescritos introduzem bugs subtis em docs não testados | Sprint 3 + Sprint 5 têm comparação com reference; gaps são documentados. |
| `gemma4:e2b` é muito fraco e produz markdown degenerado | ContentValidator aceita o que vier; raw capture torna visível; S5 reporta gaps. |
| Tempo real > 12h (subestimámos) | Sprints são independentes; podem ser pausados a meio. Cada sprint é commit-able. |
| Conflitos com outros contracts (059, 060) em curso | Branch dedicada (AGENTS.md §10). Merge para main só após S5. |

---

## Métricas de fecho

| Métrica | Alvo |
|---|---|
| Exit code do pipeline end-to-end | 0 |
| Docs gerados (de 5: 04, 05, 06, 07, 07b) | 5 |
| Similarity vs reference (prose) | ≥ 70% |
| Raw files escritos | = N LLM calls |
| Test suite passa | sim |
| Commits no contract | ≥ 8 (1-2 por sprint) |
| Branch | `feature/aegis-p1-corr-061-markdown-only-phase1` |

---

## Subagentes — orquestração

Cada sprint usa **2 subagentes** (executor + validator), lançados sequencialmente:

- **Executor:** prompt detalhado com o scope do sprint, ficheiros a tocar, constraints, deliverables.
- **Validator:** prompt detalhado com os critérios de validação do sprint, expectations, fall-through test instructions.

Orquestração: **mavis team plan** (skill carregada no início do Sprint 0).

**Pre-flight antes de cada subagent dispatch** (AGENTS.md §10.1):
- working tree limpo
- módulos críticos importáveis
- `pytest --co -q` sem ERROR
- branch certa

**Validator integrity rule** (AGENTS.md §10.2): cada validator verifica
**test COLLECTION** (não só summary) e reporta gaps explicitamente.
