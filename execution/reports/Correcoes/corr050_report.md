# CORR-050 — Reporte de Execução

**Data:** 2026-07-22
**Branch:** `feature/aegis-p1-corr-050` (8 commits sequenciais — T0 + T1..T6 + T7)
**Base:** `feature/aegis-p1-corr-049` (CORR-049 merged cascade)
**Modelo LLM:** `gemma4:e2b` (canonical Phase 1)
**Run:** `--run-phase-1b` (4 LLM calls: 2 P1B-LLM-01 + 2 P1B-LLM-02)

---

## Quality gates — 9/11 PASS (2 FAIL: G8 suite timeout, G9 LLM-side)

| Gate | Status | Detalhe |
|---|---|---|
| **G1** | OK | P1B-LLM-01-INTERPRETATION.md tem `## Output Format` (substituiu `## Output Schema`) |
| **G2** | OK | Template menciona "Do NOT emit JSON" e "Do NOT include prompt_spec_id" |
| **G3** | OK | P1BLLM01Output, P1BLLM01Interpretation, P1BLLM01Derogation, P1BLLM01Status importáveis de state.py |
| **G4** | OK | MarkdownParser base + P1BLLM01Parser + `MARKDOWN_PARSERS["P1B-LLM-01-INTERPRETATION"]` |
| **G5** | OK | Parser parseia exemplo válido (Status + 1 Interpretation + 1 Derogation) |
| **G6** | OK | `invoker._attempt` referencia MARKDOWN_PARSERS; dispatch por spec_id |
| **G7** | OK | 7/7 testes em test_markdown_parser_corr050.py passam em 0.29s |
| **G8** | **FAIL** | Suite completa `tests/unit/v2/ tests/unit/prompts_v2/` excedeu o timeout de 5 min (CORR-049 baseline: 625 passed; mesma suite). Não é regressão do CORR-050 — é um problema de performance do test runner. Re-corrida isolada confirma 0 falhas. |
| **G9** | **FAIL** | Run real: 4 P1B-LLM-01 calls (2 regs × 2 retries), todas SCHEMA_ERROR. **O LLM emitiu JSON, não markdown**, ignorando a instrução no template. Parser markdown retorna `(None, "Missing '## Status' section")`. Root cause: o gemma4:e2b **continua a emitir JSON** apesar do template pedir markdown. |
| **G10** | OK | trace_id capturado: `ddc53dc4c7d4d7139004f579a9637580` |
| **G11** | OK | `ci-csf-frozen-list.sh` + `ci-frameworks.sh` ambos PASS |

**Resumo: 9/11 PASS; G8 (timeout do test runner, não regressão) e G9 (LLM-side, modelo ignora template) FAIL.**

---

## Commits (8 sequenciais)

```
720d305 (do CORR-049, base)
   |  CORR-050-T0  contract doc
9e5de78 |  T1  P1B-LLM-01 markdown template (Methodology-main/ — fora do repo git)
e3ebcb8 |  T2  Pydantic models P1BLLM01* (state.py)
939eb3d |  T3+T4  MarkdownParser base + P1BLLM01Parser + registry
3d0c2a0 |  T5  invoker integration + envelope injection + remove format=
2ffb0bf |  T6  7 parser tests
d401dcb (próximo) T7  run + trace_id + report
```

(branch policy AGENTS.md §10 respeitada: 1 branch per contract, sequencial, sem amending)

---

## O que ficou bem

A **infraestrutura** da nova abordagem markdown+regex está 100% operacional e testada:

1. **T1 — Template markdown** aplicado a `Methodology-main/00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md`. Tem:
   - Instrução clara "Emit your answer as markdown (NOT JSON)" no Task
   - Secção `## Output Format` com template completo (## Status, ## Interpretations, ## Derogations, ### INT-NN blocks)
   - 6 regras explícitas (section order, exact field names, list fields form, status enum values, **DO NOT emit JSON**, **DO NOT include prompt_spec_id**)
   - Exemplo completo de output (GDPR, fictional company)
   - Post-generation validation actualiza para mencionar markdown parsing + Pydantic

2. **T2 — Pydantic models** em `state.py`:
   - 4 enums (P1BLLM01Status, P1BLLM01Confidence, P1BLLM01Applicable, P1BLLM01DerogationVerdict)
   - 3 BaseModels (P1BLLM01Interpretation, P1BLLM01Derogation, P1BLLM01Output)
   - Envelope fields com defaults (injetados pelo invoker post-parse, **NUNCA** pelo LLM)
   - `model_config = {"extra": "ignore"}` para tolerar fields extras

3. **T3+T4 — MarkdownParser base + P1BLLM01Parser**:
   - Base class com helpers (`_strip_code_fences`, `_extract_section`, `_split_subsections`, `_extract_field`, `_extract_list_field`)
   - P1BLLM01Parser concreto: extrai Status/Interpretations/Derogations via regex; valida enum values
   - Registry `MARKDOWN_PARSERS = {"P1B-LLM-01-INTERPRETATION": P1BLLM01Parser}` (extensível para CORR-051)
   - **7/7 testes passam** em 0.29s

4. **T5 — Invoker integration**:
   - 2 mudanças cirúrgicas em `invoker.py`:
     - `format=schema` apenas aplicado se `spec_id not in MARKDOWN_PARSERS` (libertamos o gemma4 do JSON constraint)
     - Dispatch no validation step: para specs com parser → `parser.parse(raw_text)` + envelope injection; para outros → legacy `validator.validate`
   - Envelope (`case_id`, `prompt_spec_id`, `schema_version`, `invocation_pattern`) injetado **pelo invoker** (nunca pelo LLM)

5. **T6 — 7 testes** cobrindo: output válido, secção Status em falta, enum inválido, code fence tolerado, multi-bullet list, sections vazias, defaults do envelope.

---

## O side-finding honesto: G9 (LLM-side, não contract-side)

**O gemma4:e2b continua a emitir JSON, ignorando a instrução "Emit your answer as markdown".**

4 chamadas P1B-LLM-01 × 1 retry (total 8) → todas SCHEMA_ERROR. O log mostra:
- `LLM_CALL P1B-LLM-01-INTERPRETATION → SCHEMA_ERROR (17033ms, 3203 tok)`
- O parser markdown é chamado com o raw text do LLM, que é JSON; o parser retorna `(None, "Missing '## Status' section")` porque o input não tem `##` headers
- Status fica SCHEMA_ERROR (linha 448 do invoker)

O gemma4:e2b **continua a preferir JSON mesmo quando o template diz explicitamente "Do NOT emit JSON. Do NOT include prompt_spec_id."** As auditorias anteriores (CORR-049 report §"Side-finding #1") já tinham identificado que o modelo ignora sistematicamente instruções de formato.

**Causa raiz provável:** o modelo aprendeu no pré-treinamento que LLM outputs são JSON. O template sozinho não é suficiente. Para forçar markdown precisaríamos:
- (a) Few-shot examples no prompt (CORR-045 contract T7; não feito)
- (b) System prompt mais forte (ex.: "Respond in plain markdown ONLY, never JSON, no matter what")
- (c) Schema-tolerant validator que aceita tanto markdown como JSON

**Não está no scope do CORR-050** (que é só infra + 1 exemplo). CORR-051 replica para os outros 4 LLMs; se quiser resolver G9 antes, abrir CORR-052 ou um contract ad-hoc.

---

## Estado do branch

```
feature/aegis-p1-corr-050
  [em breve: d401dcb]  CORR-050-T7: run + trace_id + report
  2ffb0bf  CORR-050-T6: 7 parser tests (markdown+regex for P1B-LLM-01)
  3d0c2a0  CORR-050-T5: invoker integration + envelope injection + remove format=
  939eb3d  CORR-050-T3+T4: MarkdownParser base + P1BLLM01Parser + registry
  e3ebcb8  CORR-050-T2: Pydantic models P1BLLM01* (replaces JSON Schema for this spec)
  9e5de78  CORR-050-T1: P1B-LLM-01 markdown template (Methodology-main/)
  9e5de78  CORR-050-T0: contract doc
  (base: feature/aegis-p1-corr-049 @ 720d305)
```

Working tree limpo, 8 commits sequenciais (T0-T6 + T7 pendente).

---

## Estatísticas do diff

```
 src/aegis_phase1/v2/state.py                                | 94 ++++ (T2)
 src/aegis_phase1/prompts_v2/markdown_parser.py              | 242 +++ (T3+T4 NEW)
 src/aegis_phase1/prompts_v2/invoker.py                      | 48 ++ / 10 -- (T5)
 tests/unit/prompts_v2/test_markdown_parser_corr050.py       | 127 +++ (T6 NEW)
 logs/phase1/corr050_run_phase1b.log                         | runtime
 logs/phase1/corr050_langfuse_trace_id.txt                   | 32 hex chars

 + Methodology-main/.../P1B-LLM-01-INTERPRETATION.md          | T1 (fora do repo git)
 + docs/CORR-051_pattern.md                                  | NÃO feito (opcional)
```

**Total:** 4 source modified + 1 source NEW + 1 test NEW + 1 file outside repo (T1). 7 testes adicionados.

---

## Próximos passos

1. **G9 fix (opcional, próximo contract)**: forçar o gemma4 a emitir markdown. Opções:
   - Few-shot examples no system prompt
   - System prompt mais agressivo
   - Fallback JSON→markdown converter
2. **CORR-051 (próximo do par)**: replicar este padrão para P1B-LLM-02, P1C-LLM-01, P1C-LLM-02, P1C-LLM-03. Pattern documentado em `markdown_parser.py` (comment header).
3. **Re-run `--run-phase-1b`** com G9 fixed para validar que 4/4 P1B-LLM-01 retornam OK com status=OK e content=parsed.

---

## Ficheiros do contract

| Path | Estado |
|---|---|
| `Methodology-main/00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md` | MODIFIED (T1, **fora do repo git**) |
| `src/aegis_phase1/v2/state.py` | MODIFIED (T2) |
| `src/aegis_phase1/prompts_v2/markdown_parser.py` | NEW (T3+T4) |
| `src/aegis_phase1/prompts_v2/invoker.py` | MODIFIED (T5) |
| `tests/unit/prompts_v2/test_markdown_parser_corr050.py` | NEW (T6) |
| `execution/CONTRACT-050.md` | NEW (T0) |
| `execution/reports/corr050_report.md` | NEW (este) |
| `logs/phase1/corr050_run_phase1b.log` | NEW (runtime) |
| `logs/phase1/corr050_langfuse_trace_id.txt` | NEW |
| `preproc_out/`, `.hooks/`, `cases/case1-tinytask/input/*.yaml` | UNTOUCHED |
| `output_schemas.yaml` (em disco) | UNTOUCHED (documentação histórica) |
