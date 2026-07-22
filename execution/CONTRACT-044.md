# CORR-044 — SP-G.1 Wiring MAP→state["domain_results"] (fase 1 de 2)

## Resumo

Contract de **fix bloqueador** do bug que produz outputs vazios quando
o pipeline corre com `--run-all-traced`. É a **fase 1 de 2** — fase
minimal que desbloqueia outputs + tracing básico. A fase 2
(CORR-045, refactor canónico per-domain) fica para depois.

**Bug:** `--run-all-traced` usa o caminho LangGraph (`graph.py`), onde
cada nó MAP chama `orch.map_single_domain(domain_id)` mas **nunca
escreve o resultado em `orch.state["domain_results"]`**. Quando o
REDUCE corre `concatenate(state)`, lê `domain_results={}` → produz
0 subdomains → todos os outputs downstream ficam vazios.

**Sintoma visível no log do utilizador (2026-07-22 00:03-13):**
```
filter_regs(D-01): ontology empty for domain, falling back to applicable_regs=['CRA', 'GDPR']
[repeats D-02..D-10]
[8 P1B calls + 2 P1C-03/02 calls = 10 total, expected 16]
concatenate: 0 domains -> 0 subdomains, 0 adapted_objectives
merge_requirements: 0 subdomains merged
apply_proportionality: 0 subdomains profiled
clause_mapping_context: no applicable_regs — returning empty context
Pipeline complete
```

**Causa raiz (pre-existing do CORR-018b, commit `60ecf73`):** o
LangGraph MAP sub-graph foi desenhado para paralelismo + tracing
per-domain, mas faltou o wiring de fan-in: cada nó escreve só em
`stage_outputs[f"map_{domain_id}"]` (estado interno LangGraph), não
em `orch.state["domain_results"]` (estado que o REDUCE lê).

**CORR-043 não causou a regressão** — só a **expôs** ao mandar validar
com `--run-all-traced`. Em `--run-all`/`--map-only` o bug não aparece
porque esses chamam `orch.map_domains()` que escreve `domain_results`
em `orchestrator.py:481,543`.

**Branch:** `feature/aegis-p1-corr-044`
**Data:** 2026-07-22
**Trigger:** utilizador correu `--run-all-traced` e viu outputs vazios.

---

## Pré-flight (validado pelo orchestrator)

```
$ git branch --show-current
feature/aegis-p1-corr-043       # ← executor cria corr-044 a partir de main

$ grep -c "domain_results" src/aegis_phase1/v2/graph.py
0                               # ← confirma o bug: graph nunca escreve domain_results

$ grep -n "domain_results" src/aegis_phase1/v2/orchestrator.py | head -5
480:        self.state["domain_results"] = results       # ← caminho canónico
529:            self.state["domain_results"] = ...       # ← caminho legacy (parcial)
543:        self.state["domain_results"] = results       # ← caminho legacy (final)

# Repro determinístico (mock, não precisa de Ollama):
$ MOCK_LLM=true python -m aegis_phase1.v2.runner --case cases/case1-tinytask --map-only 2>&1 | tail -5
MAP complete: 10 domains — statuses={'FAILED': 10}      # mock artifact, não é o bug
# Para ver o bug real precisa de --run-all-traced com Ollama:
$ python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-all-traced 2>&1 | grep "concatenate:"
concatenate: 0 domains -> 0 subdomains                   # ← o bug
```

---

## Decisão de produto (porque é que isto é fase 1 de 2)

A opção "Refactor total canónico" (CORR-045 futuro) exige:
- Refactorizar `Phase1Executor.run_phase_1c_map` (batch) para expor
  `run_phase_1c_map_single(domain_id)` (1 call P1C-LLM-01).
- Novo `map_single_domain_canonical` no orchestrator.
- Graph nó chama este em vez de `map_single_domain`.
- ~150 LOC + 5+ testes.

**Para já**, a prioridade é **desbloquear outputs + ter tracing básico**.
O wiring minimal (~5 linhas em `graph.py`) resolve o bug de "0 domains"
preservando a topologia LangGraph (10 nós MAP paralelos) e o tracing
Langfuse por-categoria (10 spans MAP + generations P1B/P1C-03/02).

**Trade-off aceite:** as 10 calls P1C-LLM-01 canónicas continuam a
**NÃO disparar** no caminho `--run-all-traced` (o graph usa legacy
LLM-A via `map_single_domain`). Em vez disso, o legacy loop interno do
`map_single_domain` faz 1 call LLM-A por domínio. Isto produz output
(não vazio) mas usa o caminho legacy em vez do canónico. O CORR-045
fecha este gap.

**Quando usar cada caminho pós-CORR-044:**
- `--run-all` (caminho orchestrator canónico): 10 P1C-LLM-01 calls,
  sem árvore LangGraph, mas Langfuse handlers wired (16 generations
  sob 1 trace_id).
- `--run-all-traced` (caminho LangGraph): 10 LLM-A legacy calls +
  árvore LangGraph (10 spans MAP paralelos) + Langfuse. **Usa este
  para observar na UI; outputs são equivalentes em estrutura.**

---

## Tarefas

### T1 — Wiring: graph MAP node escreve em `state["domain_results"]`

**Ficheiro:** `src/aegis_phase1/v2/graph.py`

**Localização:** `_make_map_node` em `graph.py:162-202`. Após a linha
`result = orch.map_single_domain(domain_id, config=cfg)` (line ~179),
adicionar a escrita no estado partilhado:

```python
def _make_map_node(domain_id: str):
    """Build a MAP node for one domain (legacy LLM-A path via map_single_domain).

    CORR-044: writes the result into orch.state["domain_results"] so that
    the downstream REDUCE sub-graph (reduce_deterministic → concatenate)
    sees the populated dict. Without this write, REDUCE reads {} and
    produces 0 subdomains.
    """
    span_name = f"MAP {domain_id}"

    def node(state, config):
        cfg = _add_named_callback(config, span_name, {"domain_id": domain_id})
        orch = _orchestrator_from(config)
        try:
            result = orch.map_single_domain(domain_id, config=cfg)
            # CORR-044: fan-in to shared state so REDUCE can read it.
            # Orchestrator instance is shared across all nodes
            # (config["configurable"]["orchestrator"]), so this mutation
            # is visible to the downstream _reduce_det node.
            orch.state.setdefault("domain_results", {})[domain_id] = result
            logger.info(
                "MAP node %s: wrote domain_results[%s] (status=%s)",
                domain_id, domain_id, result.get("llm_status"),
            )
            return {"stage_outputs": {f"map_{domain_id}": result}, "map_complete": {domain_id: True}}
        except Exception as exc:
            logger.exception("MAP node %s failed", domain_id)
            failure = {
                "domain_id": domain_id,
                "llm_status": "FAILED",
                "error_reason": str(exc),
            }
            # CORR-044: write the failure too, so REDUCE has full picture.
            orch.state.setdefault("domain_results", {})[domain_id] = failure
            return {"stage_outputs": {f"map_{domain_id}": failure}, "map_complete": {domain_id: True}}

    return node
```

**Notas:**
- `result.get("llm_status")` — confirmar que a key existe no shape
  devolvido por `map_single_domain` (ver `orchestrator.py:624-638`,
  tem `llm_status`). Se faltar, adicionar.
- O `except` também escreve o failure em `domain_results` — assim o
  REDUCE sabe que o domínio falhou (em vez de estar simplesmente
  ausente).
- O `orch` é obtido via `_orchestrator_from(config)` — confirmar que
  este helper existe e retorna a mesma instância partilhada por todos
  os nós (deve sim, ver graph.py imports).

### T2 — Teste de regressão do wiring

**Ficheiro:** `tests/unit/v2/test_graph_corr044.py` (NEW)

Casos:
- (a) `test_map_node_writes_domain_results` — mock do `map_single_domain`
  para retornar `{"domain_id": "D-01", "llm_status": "OK", "subdomains": [...]}`,
  correr o nó MAP para D-01, validar que `orch.state["domain_results"]["D-01"]`
  tem o resultado.
- (b) `test_map_node_writes_failure_on_exception` — mock levanta
  `RuntimeError`, correr o nó, validar que
  `domain_results["D-01"]["llm_status"] == "FAILED"`.
- (c) `test_reduce_det_sees_populated_domain_results_after_map` — teste
  de integração mínimo: correr os 10 nós MAP (com mock) + o nó REDUCE,
  validar que `concatenate` vê 10 dominios (não 0).

Para o teste (c), pode ser preciso mockar o `Phase1Executor` ou usar
`MOCK_LLM=true` — o objectivo é validar o **wiring**, não o output do
LLM.

### T3 — Validação end-to-end com Ollama real

```bash
source ../shared-venv/bin/activate

# Snapshot baseline (pós-CORR-043, antes deste fix)
mkdir -p output/phase1/baseline_pre_corr044/
cp output/phase1/*.md output/phase1/*.xlsx output/phase1/baseline_pre_corr044/ 2>/dev/null

# Run com tracing (este é o teste chave — antes produzia 0 domains)
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --run-all-traced \
    2>&1 | tee logs/phase1/corr044_run_traced.log
```

**Esperado pós-fix:**
- `concatenate: 10 domains -> N subdomains` (N > 0; tipicamente 30-38)
- `apply_proportionality: N subdomains profiled`
- **Sem** `clause_mapping_context: no applicable_regs` warning
- 9 outputs regenerados com mtime > hoje
- Langfuse trace com 10 spans MAP (D-01..D-10) + generations P1B/P1C-03/02

**Atenção:** o output pode divergir do `output/phase1/baseline_pre_corr044/`
(pós-CORR-043) — agora tem conteúdo real. Reportar a diferença.

### T4 — Verificação Langfuse (árvore hierárquica)

Após o run T3, abrir `http://localhost:3000`:

1. **Traces** → filtrar por tag `case1-tinytask` (e idealmente
   `corr-044` se conseguirmos adicionar).
2. Abrir o root trace `phase1_run_all_traced`.
3. Validar a árvore:
   - **1 span root** (`phase1_run_all_traced`)
   - **sub-spans por sub-fase**: `load_baseline`, `subphase_map`,
     `subphase_1b`, `subphase_reduce`, `subphase_output`
   - **dentro de `subphase_map`**: 10 spans `MAP D-01`..`MAP D-10`
   - **dentro de `subphase_1b`**: generations P1B-LLM-01/02 (4 calls)
   - **dentro de `subphase_reduce`**: generations P1C-LLM-03 + P1C-LLM-02
4. Guardar `trace_id` (URL `/trace/<uuid>`) em
   `logs/phase1/corr044_langfuse_trace_id.txt`.

Se a árvore não aparecer hierárquica (todos os spans planos), é bug
de wiring do callback no graph — investigar `_add_named_callback`.

### T5 — Adicionar tag `corr-044` ao trace (opcional, nice-to-have)

Em `cmd_run_all_traced` (`runner.py:735-743`), adicionar `corr-044`
à lista de tags para facilitar a filtragem na UI Langfuse:

```python
run_phase1_graph(
    orchestrator=orch,
    callbacks=callbacks,
    tags=["phase1", "case1-tinytask", "corr-044"],  # ← adicionar tag
    extra_metadata={...},
)
```

Isto é opcional — se preferires não mexer no runner, pular.

### T6 — Parity re-check + diff vs baseline

Re-executar a verificação de paridade (mesma função `normalize()` do
CORR-042-T7) contra a referência
`Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`.

Reportar em `logs/phase1/corr044_parity_report.md`.

**Importante:** comparar também contra `baseline_pre_corr044/` — o
output agora **deve** ter conteúdo real (não vazio). Se ainda estiver
vazio, o fix T1 falhou.

### T7 — Atualizar verdict em CONTRACT-043

Em `execution/CONTRACT-043.md`, na secção "Verdict pós-execução" ou
no rodapé, adicionar nota:
```
**Update CORR-044 (2026-07-22):** o fix canónico de CORR-043-T1 só
funciona no caminho `orch.map_domains()` (--run-all/--map-only). O
caminho LangGraph (--run-all-traced) tem bug pre-existing (CORR-018b)
que faz o MAP não escrever em state["domain_results"]. CORR-044 aplica
wiring minimal para desbloquear; o refactor canónico per-domain fica
para CORR-045.
```

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — graph.py escreve domain_results (wiring aplicado)
COUNT=$(grep -c "domain_results" src/aegis_phase1/v2/graph.py)
[ "$COUNT" -ge 1 ] && echo "G1 OK" || { echo "FAIL G1: graph.py still doesn't write domain_results"; exit 1; }

# G2 — testes de wiring passam
pytest tests/unit/v2/test_graph_corr044.py -q 2>&1 | tail -1 | grep -qE "passed" && echo "G2 OK" || { echo "FAIL G2"; exit 1; }

# G3 — suite v2 completa verde (sem regressões)
pytest tests/unit/v2/ -q 2>&1 | tail -3 | grep -qE "passed" && echo "G3 OK" || { echo "FAIL G3: unit suite has failures"; exit 1; }

# G4 — run-traced produz outputs não-vazios (o bug original)
test -f logs/phase1/corr044_run_traced.log && \
    ! grep -q "concatenate: 0 domains" logs/phase1/corr044_run_traced.log && echo "G4 OK" || { echo "FAIL G4: MAP still producing 0 domains"; exit 1; }

# G5 — 9 outputs com mtime > hoje
TODAY=$(date +%Y-%m-%d)
for doc in 04_Company_Context_Assessment 05_Regulatory_Applicability 06_Clause_Mapping_Matrix 07_Structured_Compliance_Matrix 07b_Proportionality_Profile 04a_Architecture_DataInventory 04b_Security_Posture 04c_ThirdParty_Landscape 04d_Org_Roles_RACI; do
    stat -c '%y' "output/phase1/${doc}.md" 2>/dev/null | grep -q "$TODAY" || { echo "FAIL G5: $doc.md not regenerated today"; exit 1; }
done
echo "G5 OK"

# G6 — Langfuse trace_id capturado
test -s logs/phase1/corr044_langfuse_trace_id.txt && echo "G6 OK (manual verify Langfuse UI)" || echo "G6 WARN: trace_id file empty"

# G7 — paridade sem ❌ (vs referência Methodology-main)
test -f logs/phase1/corr044_parity_report.md && ! grep -q "❌" logs/phase1/corr044_parity_report.md && echo "G7 OK" || { echo "FAIL G7: parity outside thresholds"; exit 1; }

# G8 — Doc 07 tem rows de subdomain (não vazio)
COUNT=$(grep -cE "^\| D-[0-9]+\.[0-9]+" output/phase1/07_Structured_Compliance_Matrix.md 2>/dev/null || echo 0)
[ "$COUNT" -ge 30 ] && echo "G8 OK ($COUNT subdomain rows)" || { echo "FAIL G8: only $COUNT subdomain rows (expected ≥30)"; exit 1; }

# G9 — CI gates
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G9 OK" || { echo "FAIL G9: CI gate failed"; exit 1; }

echo "=== ALL 9 GATES PASSED ==="
```

**Definição de done:** G1–G9 todos PASS.

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `src/aegis_phase1/v2/graph.py` | **MODIFY** — `_make_map_node` escreve em `orch.state["domain_results"][domain_id]` (sucesso + falha) |
| `tests/unit/v2/test_graph_corr044.py` | **NEW** — 3 testes (a/b/c) |
| `src/aegis_phase1/v2/runner.py` | **MODIFY (opcional T5)** — adicionar tag `corr-044` ao traced run |
| `output/phase1/baseline_pre_corr044/` | **NEW** — snapshot pós-CORR-043 |
| `output/phase1/*.md` + `*.xlsx` | **REGENERATED** — por T3 |
| `logs/phase1/corr044_run_traced.log` | **NEW** |
| `logs/phase1/corr044_langfuse_trace_id.txt` | **NEW** |
| `logs/phase1/corr044_parity_report.md` | **NEW** |
| `execution/CONTRACT-043.md` | **MODIFY** — nota sobre bug pre-existing + wiring CORR-044 |
| `execution/CONTRACT-044.md` | **NEW** (este) |

**Não modificar:** `preproc_out/`, `Methodology-main/`, `.hooks/`,
`src/aegis_phase1/v2/orchestrator.py` (o fix é no graph, não no orchestrator),
`src/aegis_phase1/prompts_v2/phase1_executor.py` (refactor canónico fica
para CORR-045).

---

## Estrutura de commits

```
feature/aegis-p1-corr-044
├─ commit 1: T1 wiring graph.py _make_map_node domain_results write
├─ commit 2: T2 test_graph_corr044.py (3 testes)
├─ commit 3: T3+T4 run-all-traced com Ollama + outputs regenerados + langfuse trace_id
├─ commit 4: T6 parity report
└─ commit 5: T7 nota em CONTRACT-043 + (opcional T5 tag runner.py)
```

**Convenção AGENTS.md §10:** 1 branch por contract, commits sequenciais,
sem amending.

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| `orch = _orchestrator_from(config)` retorna instância diferente por nó (não partilhada) | Verificar antes: `grep -n "_orchestrator_from\|configurable.*orchestrator" src/aegis_phase1/v2/graph.py`. Se não partilhada, o wiring não funciona — precisa de mecanismo alternativo (e.g. accumular em `state["stage_outputs"]` e fazer fan-in no REDUCE). |
| `result.get("llm_status")` não existe no shape devolvido por `map_single_domain` | Ver `orchestrator.py:624-638` — tem `llm_status`. Confirmar com `MOCK_LLM=true python -m ... --map-only` antes do fix. |
| Output diverge muito do baseline_pre_corr044 (que tinha conteúdo parcial do legacy fallback) | Esperado — agora o REDUCE tem dados completos. Reportar melhoria. |
| 10 spans MAP não aparecem hierárquicos na Langfuse UI | Verificar `_add_named_callback` em graph.py:173-177. Se o callback não estiver a criar child spans, investigar — pode ser bug no helper. |
| `--run-all-traced` demora > 20 min | Tempo esperado ~10-15 min (10 LLM-A legacy + 8 P1B + 2 P1C). Se > 30 min, abortar e reportar. |
| Mock LLM nos testes T2 não cobre o caminho real | Aceitável — T3 com Ollama real valida o caminho production. |

---

## Pós-CORR-044

**Se G1–G9 passarem:** bug de "MAP vazio" resolvido. Outputs
regenerados com conteúdo. Langfuse trace com árvore hierárquica
(10 spans MAP). Próximo passo: **CORR-045 (refactor canónico
per-domain)** — substituir `map_single_domain` (legacy) por
`map_single_domain_canonical` no graph, para que cada span MAP tenha
1 generation P1C-LLM-01 canónica (em vez de LLM-A legacy).

**Se G4 falhar** (ainda "concatenate: 0 domains"): o wiring T1 não
funcionou. Investigar:
1. `_orchestrator_from(config)` retorna a mesma instância em todos
   os nós? (Se não, o estado não é partilhado.)
2. O nó REDUCE lê `state["domain_results"]` via `orch.state` ou via
   LangGraph state? (Se for via LangGraph state, precisa de fan-in
   diferente.)

**Se G8 falhar** (Doc 07 com < 30 rows): o REDUCE produziu dados mas
o renderer não os converteu. Investigar `concatenate` output shape.

---

## Change log

- 2026-07-22: v1.0 — contract inicial criado pelo orchestrator após
  diagnóstico do bug "MAP vazio em --run-all-traced" (causa raiz:
  graph.py não escreve em state["domain_results"]; pre-existing do
  CORR-018b, exposto pelo CORR-043 que mandou validar com traced run).
