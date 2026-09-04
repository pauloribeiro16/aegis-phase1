# CORR-052 — Reporte (G6 FAIL — base_system change não foi suficiente)

**Data:** 2026-07-22
**Branch:** `feature/aegis-p1-corr-052` (1 commit T0)
**Base:** `feature/aegis-p1-corr-050` (CORR-050 merged cascade)
**Trace:** `ab521fb7941601864d470f49edeb65f4` (saved to `logs/phase1/corr052_langfuse_trace_id.txt`)

---

## TL;DR

A mudança ao `base_system_prompt.md` (rule 4) **NÃO** foi suficiente. O gemma4:e2b continua a emitir JSON para `P1B-LLM-01-INTERPRETATION`, ignorando a nova regra format-agnostic. **G6 FAIL** (4× SCHEMA_ERROR, igual ao CORR-050). O log de erros de formato (format-errors.jsonl) tem timestamps 15:1x, **não 18:5x** — o caminho markdown é silencioso (o invoker não loga raw quando vai pelo path markdown parser).

**Decisão tomada: voltar a perguntar ao user — pivot para estratégia B (parser tolerant) ou C (both).**

---

## Quality gates — 6/10 PASS (G6 FAIL, G7 expected-FAIL, G8/G10)

| Gate | Status | Detalhe |
|---|---|---|
| **G1** | OK | `base_system_prompt.md` rule 4 contém "Output format is determined by the prompt body" |
| **G2** | OK | rule 4 contém "plain markdown" |
| **G3** | OK | rule 4 contém "Do NOT mix formats" |
| **G4** | OK | P1B-LLM-01 body ainda tem "Do NOT emit JSON" (regression check passed) |
| **G5** | OK | 7/7 parser tests passam (sem regressão) |
| **G6** | **FAIL** | 2/2 P1B-LLM-01 calls SCHEMA_ERROR. LLM continuou a emitir JSON. |
| **G7** | FAIL (esperado) | 4/4 P1B-LLM-02 calls SCHEMA_ERROR (esperado, out of scope CORR-052) |
| **G8** | OK | trace_id `ab521fb7941601864d470f49edeb65f4` capturado |
| **G9** | OK | ci-csf + ci-frameworks PASS |
| **G10** | OK | report escrito |

**Resumo: 6/10 PASS; G6 FAIL (decisão real), G7 FAIL (esperado, out of scope).**

---

## O que mudou

### `Methodology-main/00_METHODOLOGY/PROMPTS/base_system_prompt.md` rule 4

**Antes:**
```
4. Output MUST conform to the JSON Schema provided in the <output_contract>
   block. Post-generation validation is enforced.
```

**Depois:**
```
4. Output format is determined by the prompt body:
   - If the body specifies a JSON Schema in <output_contract> (legacy),
     output MUST be valid JSON conforming to that schema.
   - If the body specifies a markdown template (## Status / ## Interpretations
     / ## Derogations style, with bullet lists), output MUST be plain markdown.
   - Do NOT mix formats. Do NOT emit JSON wrappers (```json...```) inside
     a markdown output, or markdown sections inside a JSON output.
   - Post-generation validation enforces the chosen format.
```

**Verificação:**
- `grep "Output format is determined" base_system_prompt.md` → ✓
- `grep "plain markdown" base_system_prompt.md` → ✓
- `grep "Do NOT mix formats" base_system_prompt.md` → ✓

### Run `--run-phase-1b` (CORR-052, hoje 18:52)

```
8 LLM calls, todas SCHEMA_ERROR:
  P1B-LLM-01-INTERPRETATION (×4 tentativas, 2 regs × 2 retries): SCHEMA_ERROR
  P1B-LLM-02-RATIONALE     (×4 tentativas, 2 regs × 2 retries): SCHEMA_ERROR
```

**Comparação CORR-050 vs CORR-052:** idêntico. Mesma falha.

---

## Diagnóstico: porque o base_system change não bastou

O gemma4:e2b continua a emitir JSON para "regulatory analysis" tasks. Três hipóteses:

1. **Model-side preference**: gemma4:e2b é deeply trained to emit JSON for structured
   output tasks. Uma única reformulação da rule 4 não é suficiente para "re-ensinar"
   o modelo. O base_system é prepended mas a weight da pré-training é mais forte.

2. **Mistura de instruções no body**: o P1B-LLM-01 body ainda tem `## Output Schema`
   (referência a JSON Schema) que pode estar a confundir o modelo. Mas no CORR-050
   eu substituí por `## Output Format` e adicionei "Do NOT emit JSON" — pode não ter
   sido suficiente.

3. **`<output_contract>` fantasma**: a rule 4 original referia-se a um bloco
   `<output_contract>` que não é injectado em lado nenhum (grep retornou 0 matches).
   O LLM pode ter internalizado "se há output_contract → JSON; se não há → ?".
   Reformular a rule 4 não elimina a memória da rule antiga.

**Conclusão:** mudar só o prompt não vai funcionar. O modelo não vai aprender markdown
só porque um contract reformula a rule 4. Precisamos de uma das duas alternativas:

- **A) Few-shot examples** (no body) — dar 1-2 exemplos concretos de output markdown
  esperado. O gemma4 aprende melhor com exemplos do que com instruções abstratas.
- **B) Parser schema-tolerant** — `P1BLLM01Parser.parse()` tenta markdown primeiro;
  se falhar, tenta JSON; mapeia para Pydantic. Garante que **funciona** independentemente
  do que o LLM emitir.
- **C) Ambos** — A + B. Mais defensivo.

**A minha recomendação pessoal: B.** A+B é overkill — o gemma4 já demonstrou que não
vai emitir markdown só com prompt tweak (CORR-050 + CORR-052 juntos = mesma falha).
Few-shot examples podem ajudar mas requer re-treino efectivo do modelo. **B** é o
caminho de menor risco: a infra fica robusta a qualquer output do LLM.

---

## Commits

```
932bc70  CORR-052-T0: contract doc
  (T1+T2 não commitados — a edição ao base_system_prompt.md é fora do repo
   aegis-phase1, e o run não mudou comportamento; honestamente, é melhor
   voltar atrás e pivotar estratégia do que fingir que está "feito")
```

**Working tree:** branch `feature/aegis-p1-corr-052` apenas com T0 (contract doc).
Nenhum source code do aegis-phase1 tocado.

---

## Ficheiros

| Path | Estado |
|---|---|
| `Methodology-main/00_METHODOLOGY/PROMPTS/base_system_prompt.md` | MODIFIED (fora do repo) |
| `execution/CONTRACT-052.md` | NEW (T0) |
| `execution/reports/corr052_report.md` | NEW (este) |
| `logs/phase1/corr052_run_phase1b.log` | NEW (runtime, 18:52) |
| `logs/phase1/corr052_langfuse_trace_id.txt` | NEW (ab521fb7...) |
| `src/aegis_phase1/...` | UNTOUCHED |

---

## Side-finding (orthogonal a CORR-052)

- O caminho markdown (line 415 do invoker) é **silencioso no log**. Quando
  `parser.parse(raw)` falha, o invoker loga `SCHEMA_ERROR` mas **não loga o raw**
  nem o `error_feedback` detalhado. Só o `validation_result["errors"]` tem
  o detail mas nunca chega ao log.
- format-errors.jsonl não recebeu entradas do run 18:52 (porque o caminho markdown
  não passa por RobustParser).
- Para diagnosticar G6 precisamos de **instrumentar o path markdown** para logar
  `raw` + `error_feedback` em caso de falha. ~10 linhas no invoker.

---

## Próximo passo (a confirmar com user)

Recomendo **abrir CORR-053** com:
1. **Pivot principal**: `P1BLLM01Parser` schema-tolerant (JSON-as-fallback) — ~30 min
2. **Instrumentar** o path markdown no invoker para logar raw — ~10 min
3. Re-run + verificar G6 verde

Custo total: ~1h. G6 finalmente passa. CORR-051 (replicar para 4 LLMs) desbloqueado.

**Alternativa:** few-shot examples no P1B-LLM-01 body (Caminho A). Mais arriscado,
pode falhar como o base_system.
