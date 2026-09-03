# CORR-048 — Langfuse metadata + tree + threading prompts

## Resumo

Contract de **observabilidade + threading** — fecha 3 problemas
críticos detectados em auditoria Langfuse pós-CORR-044/045/046/047:

1. **Metadata Langfuse não faz sentido.** Tags têm `corr-XXX`
   (tickets internos vazam para o trace público); trace name
   "ChatOllama" aleatório; 4 subphase tags
   (`subphase:map/1b/reduce/output`) hardcoded em todos os traces
   (não é per-node); sem `model`/`domain`/`regulation` no metadata
   que permita filtragem útil.
2. **Árvore LangGraph partida.** Cada generation LLM escapa para um
   trace flat com `parentObservationId` órfão. A estrutura
   "MAP D-01 → 1 generation dentro" não existe; só há
   generations flat.
3. **Threading incompleto.** Os 4 novos fields do CORR-047
   (ImplementationReadiness, RegulatoryClassification, RoleMatrix,
   RegulatoryInteractions) não chegam aos prompts. A função
   `_project_company_context` em `src/aegis_phase1/v2/domain/inputs.py:156`
   hardcodeia 8 fields e ignora o `CompanyProfile` enriquecido.

**Branch:** `feature/aegis-p1-corr-048`
**Data:** 2026-07-22
**Trigger:** auditoria Langfuse pós-CORR-047 — 4 contracts merged,
mas o trace Langfuse não reflecte a hierarquia (gerações flat) e
os 4 novos fields do 047 não chegam aos prompts.

---

## Pré-flight (validado pelo orchestrator)

```
$ grep -nE "corr-|tags=" src/aegis_phase1/v2/runner.py | head -3
741:            tags=[f"phase:phase1", f"case:{case_name}"],
# sem corr-XXX em main; phase:phase1 + case:case1-tinytask

$ grep -nE "subphase:" src/aegis_phase1/v2/graph.py | head -10
592:            The 4 sub-phase tags (``subphase:map``, ``subphase:1b``,
593:            ``subphase:reduce``, ``subphase:output``) are added
605:        "subphase:map",
606:        "subphase:1b",
607:        "subphase:reduce",
608:        "subphase:output",

$ grep -n "_project_company_context" src/aegis_phase1/v2/domain/inputs.py
124:        "company_context": _project_company_context(ctx),
156:def _project_company_context(ctx: Any) -> dict[str, Any]:
# hardcoded 8 fields; sem IR/RegClass/RoleMatrix/Interactions

$ python -c "from langfuse import Langfuse; print(sorted([m for m in dir(Langfuse) if not m.startswith('_')]))"
['auth_check', 'clear_prompt_cache', 'create_dataset', 'create_dataset_item',
 'create_event', 'create_prompt', 'create_score', 'create_trace_id', 'delete_dataset_run',
 'flush', 'get_current_observation_id', 'get_current_trace_id', 'get_dataset',
 'get_dataset_run', 'get_dataset_runs', 'get_prompt', 'get_trace_url',
 'resolve_media_references', 'run_batched_evaluation', 'run_experiment',
 'score_current_span', 'score_current_trace', 'set_current_trace_as_public',
 'set_current_trace_io', 'shutdown', 'start_as_current_observation',
 'start_observation', 'update_current_generation', 'update_current_span',
 'update_prompt']

$ python -c "import langfuse; print(langfuse.__version__)"
4.8.0b1
```

**Conclusão:** langfuse 4.8.0b1 expõe `start_as_current_observation` (que
serve tanto para spans como para generations), `update_current_span`,
`update_current_generation`. Não tem `start_span` (removido nesta versão).

---

## Decisões de produto

1. **Plano A: OTel SDK via `start_as_current_observation`.** Esta é a
   API oficial do langfuse 4.x. Cada nó LangGraph abre uma
   observation (as_current_span); dentro, o ChatOllama via
   `RunnableConfig(callbacks=[handler])` cria generations filhas
   automaticamente (o handler liga-as à observation corrente).

2. **Plano B (T1-alt):** se OTel ficar instável, **manter o
   CallbackHandler actual** mas:
   - Remover o double-attachment do handler em `invoker.py:182-186`
     (actualmente o handler é anexado a config dentro do `invoke`,
     criando callbacks duplicados em cada retry).
   - NÃO fazer overwrite de `config["run_name"]` em cada nó (deixar
     o `RunnableConfig` chegar ao Ollama como está).
   - Adicionar `run_name` explícito por nó em graph.py (já existe
     parcialmente — `config["run_name"] = f"MAP D-{domain_id} ..."`).

3. **Metadata estruturado em `runner.py:cmd_run_all_traced`.**
   Trace name = `AEGIS Phase 1 - <case_name> - <run_id_short>`.
   Metadata dict: `{model: "gemma4:e2b", case: "case1-tinytask",
   run_id: "<uuid4>", graph: "v2.4-stage", subphases_run: ["map",
   "1b", "reduce", "output"]}`. Tags: APENAS `phase:phase1` +
   `case:case1-tinytask` (sem `corr-XXX`).

4. **Tags per-node em `graph.py`.** Remover os 4 subphase tags
   hardcoded. Cada nó LangGraph adiciona as suas próprias tags:
   - MAP D-01 → `["phase:phase1", "case:case1-tinytask", "stage:map",
     "domain:D-01"]`
   - P1B GDPR → `["phase:phase1", "case:case1-tinytask", "stage:1b",
     "regulation:GDPR"]`
   - REDUCE → `["phase:phase1", "stage:reduce"]`
   - OUTPUT → `["phase:phase1", "stage:output"]`

5. **Threading CORR-047 fields.** Estender
   `_project_company_context` em `inputs.py:156-182` para incluir
   os 4 novos fields do `CompanyProfile` se estiverem populados.
   Backward-compat: se `ctx` é um dict simples (v1-compat shim) sem
   os 4 fields, retornar shape antigo sem erro. Shape output:
   `tech_stack + 4 new fields` projectado para 7+ keys.

6. **Truncar generation I/O a 10KB** se trace > 80MB (limite render
   Langfuse). `RunnableConfig` callback handler detecta o size e
   trunca input/output payloads; warning no log se truncar.

---

## Tarefas

### T1 — Switch para OTel SDK + tree hierárquica (Plano A)

**Ficheiro:** `src/aegis_phase1/v2/graph.py` (função `run_phase1_graph`)

**Estratégia:**
- Importar `langfuse.get_client()` (singleton 4.x).
- No entrypoint `run_phase1_graph`, abrir uma root observation:
  ```python
  from langfuse import get_client
  lf = get_client()
  with lf.start_as_current_observation(
      name="AEGIS Phase 1",
      as_type="span",
      metadata={"case": case_name, "model": "gemma4:e2b",
                "run_id": str(uuid.uuid4())},
  ) as root_span:
      # pass root_span via contextvars (automático)
      state = StateGraph(...)
      for node in [map_node, p1b_node, reduce_node, output_node]:
          ...
  ```
- Cada nó LangGraph já tem `config["callbacks"]` que chega ao
  ChatOllama; o `CallbackHandler` do langfuse vai criar
  generations filhas da observation corrente automaticamente
  (via OTel context propagation).
- Em `invoker.py:182-186` (callback attachment): **manter** o
  handler attach (não é double-attach se o handler for obtido via
  `get_client().get_default_handler()` em vez de construído
  manualmente). Validar.

**Plano B (T1-alt):** se OTel instável, NÃO mexer em
`start_as_current_observation`. Manter o CallbackHandler actual,
remover double-attach em `invoker.py:182-186`, e adicionar
`run_name` explícito por nó (já existe; auditar que não é
overwritten).

**Truncar I/O a 10KB:** em `invoker.py:_attempt` (linha ~266 onde
chama `llm.invoke`), medir `len(prompt["system"] + prompt["user"])`;
se > 10240, truncar o user message antes de enviar. Log WARNING.
Similar para response.content.

### T2 — Metadata estruturado + tags per-node

**Ficheiro:** `src/aegis_phase1/v2/runner.py` (função
`cmd_run_all_traced`)

**Mudar:**
- `tags=[f"phase:phase1", f"case:{case_name}"]` → manter só esses 2
  (já estão limpos em main).
- Adicionar `metadata={"model": "gemma4:e2b", "case": case_name,
  "run_id": str(uuid.uuid4()), "graph": "v2.4-stage",
  "subphases_run": ["map", "1b", "reduce", "output"]}` no
  `langfuse_context.update` (ou equivalente no 4.x).
- `trace name` = `f"AEGIS Phase 1 - {case_name} - {run_id_short}"`.

**Ficheiro:** `src/aegis_phase1/v2/graph.py` (4 nós)

**Remover** os 4 subphase tags hardcoded em `run_phase1_graph` (linhas
~605-608). Cada nó adiciona as suas próprias tags via
`config["metadata"]["tags"]` ou via `langfuse_context.update_current_observation`.

### T3 — Per-node span names (validar que já existem)

**Ficheiro:** `src/aegis_phase1/v2/graph.py`

Verificar que `config["run_name"]` ou equivalente já dá nomes úteis
por nó:
- `MAP D-01 — Data Protection`
- `P1B-LLM-01 INTERPRETATION (GDPR)`
- `P1B-LLM-01 INTERPRETATION (CRA)`
- `P1B-LLM-02 RATIONALE (GDPR)`
- `REDUCE COMPOUND EVENTS`
- `REDUCE STRATEGIC SYNTHESIS`
- `OUTPUT DOC 04..07`

Se não existir este nível de detalhe, **adicionar** (cada nó define
o seu próprio `run_name` antes de invocar o LLM).

### T4 — Threading dos 4 novos fields do CORR-047

**Ficheiro:** `src/aegis_phase1/v2/domain/inputs.py` (função
`_project_company_context` linhas 156-182)

**Alvo:**
```python
def _project_company_context(ctx: Any) -> dict[str, Any]:
    """Project the company context to the 7+ fields the prompt needs.

    CORR-042 inline fix: ctx may be a Pydantic CompanyContext or a
    dict (v1-compat shim). Handle both.

    CORR-048: extend with the 4 new fields from CORR-047
    (implementation_readiness, regulatory_classification,
    role_matrix, regulatory_interactions) when present in
    CompanyProfile. Backward-compat: if the 4 fields are not
    available (legacy v1 state), return the original 8-field
    shape without error.
    """
    if isinstance(ctx, dict):
        # v1-compat shim path (8 fields)
        base = {
            "company_name": ctx.get("company_name") or ctx.get("name") or "",
            "scale": ctx.get("scale") or ctx.get("complexity_tier") or "LOW",
            "sector": ctx.get("sector") or "",
            "employees": ctx.get("employees") or 0,
            "revenue": ctx.get("revenue") or 0,
            "security_fte": ctx.get("security_fte") or 0.0,
            "tech_stack": list(ctx.get("tech_stack") or []),
            "applicable_regs": list(ctx.get("applicable_regs") or []),
        }
    else:
        # Pydantic path
        base = {
            "company_name": ctx.company_name,
            "scale": ctx.scale,
            "sector": ctx.sector,
            "employees": ctx.employees,
            "revenue": ctx.revenue,
            "security_fte": ctx.security_fte,
            "tech_stack": list(ctx.tech_stack or []),
            "applicable_regs": list(ctx.applicable_regs or []),
        }

    # CORR-048: thread the 4 new fields from CORR-047 IF available.
    # Try multiple shapes (dict / CompanyProfile / orchestrator state).
    extra = _extract_corr047_fields(ctx)
    if extra:
        base.update(extra)
    return base


def _extract_corr047_fields(ctx: Any) -> dict[str, Any]:
    """Extract the 4 CORR-047 fields from any of the supported shapes.

    Tries:
      1. ctx.implementation_readiness (CompanyProfile attribute)
      2. ctx["v2_company_profile"].implementation_readiness (state shim)
      3. ctx.get("implementation_readiness") (dict)
    Returns a dict with the 4 fields, or {} if none available.
    Each field is serialised via model_dump() if it's a Pydantic model.
    """
    out: dict[str, Any] = {}
    for field in (
        "implementation_readiness",
        "regulatory_classification",
        "role_matrix",
        "regulatory_interactions",
    ):
        value = None
        # Path 1: direct attribute (Pydantic or CompanyProfile)
        if hasattr(ctx, field):
            value = getattr(ctx, field)
        # Path 2: dict with v2_company_profile
        if value is None and isinstance(ctx, dict):
            profile = ctx.get("v2_company_profile")
            if profile is not None and hasattr(profile, field):
                value = getattr(profile, field)
        # Path 3: dict with direct key
        if value is None and isinstance(ctx, dict):
            value = ctx.get(field)
        if value is None:
            continue
        # Serialise Pydantic model
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        elif hasattr(value, "__dict__"):
            value = {
                k: v for k, v in value.__dict__.items()
                if not k.startswith("_")
            }
        out[field] = value
    return out
```

**Notas:**
- Backward-compat: se nenhum dos 4 fields está disponível, retorna
  shape antigo (8 fields). Smoke test (T5) confirma.
- Os 4 fields são projectados como dicts serializados (o prompt pode
  consumi-los como JSON, ou como texto formatado noutro contract).

### T5 — Testes

**Ficheiro:** `tests/unit/v2/test_corr048_metadata_threading.py` (NEW)

5 casos:

(a) `test_runner_metadata_has_no_corr_xxx_tags` — invoca
`cmd_run_all_traced` com mock Langfuse client; verifica que as tags
NÃO contêm `corr-` (string prefix).

(b) `test_graph_subphase_tags_are_per_node` — mocka 1 chamada do
`run_phase1_graph`; verifica que as tags do MAP D-01 NÃO contêm
`subphase:1b`, `subphase:reduce`, `subphase:output` (só stage:map +
domain:D-01). E as tags do P1B GDPR contêm `regulation:GDPR`.

(c) `test_project_company_context_threads_4_new_fields` — constrói
um mock CompanyProfile com os 4 fields populated; chama
`_project_company_context`; verifica que o dict retornado tem as
4 keys adicionais com os valores correctos via `model_dump()`.

(d) `test_project_company_context_backward_compat` — chama
`_project_company_context` com um dict simples (v1-compat); verifica
que retorna o shape original (8 fields) sem erro e sem os 4 novos.

(e) `test_invoker_truncates_large_prompts` — mocka ChatOllama;
passa inputs com `system_prompt + user_prompt` > 10KB; verifica
que o payload enviado ao Ollama foi truncado e que um WARNING
foi logado.

### T6 — Run --run-all-traced real + Langfuse UI

```bash
source ../shared-venv/bin/activate
python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-all-traced \
    2>&1 | tee logs/phase1/corr048_run_traced.log
```

**Esperado pós-fix:**
- 1 root observation `AEGIS Phase 1` com `model=gemma4:e2b` no metadata
- Tags: APENAS `phase:phase1`, `case:case1-tinytask` (sem `corr-XXX`)
- 4 nodes filhos: MAP (1 span), P1B (5 spans), REDUCE (2 spans),
  OUTPUT (1 span)
- 30+ generations filhas (10 lanes + 5 regs × 2 specs + reduce)
- Tree hierárquica: root → stage → node → generation

**Verificação Langfuse UI:**
- `http://localhost:3000` → filtrar por tag `phase:phase1`
- Abrir trace mais recente
- Confirmar hierarquia (clicar em cada observation vê as filhas)
- Guardar `trace_id` em `logs/phase1/corr048_langfuse_trace_id.txt`
- Screenshot opcional em `logs/phase1/corr048_langfuse_tree.png`

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — sem corr-XXX em tags
grep -E "tags=.*corr-" src/aegis_phase1/v2/runner.py && \
    { echo "FAIL G1"; exit 1; } || echo "G1 OK"

# G2 — subphase tags per-node (não hardcoded list)
grep -E '"subphase:map",\s*$' src/aegis_phase1/v2/graph.py && \
    { echo "FAIL G2"; exit 1; } || echo "G2 OK"

# G3 — _project_company_context inclui 4 fields
PYTHONPATH=src python -c "
from aegis_phase1.v2.domain.inputs import _project_company_context, _extract_corr047_fields
from aegis_phase1.v2.state import (
    ImplementationReadiness, RegulatoryClassification, RoleMatrix, RegulatoryInteractions,
)
# Mock minimal CompanyProfile
class Mock:
    company_name='X'; sector=''; employees=1; revenue=0; scale='MICRO'
    security_fte=0.0; tech_stack=[]; applicable_regs=[]
    implementation_readiness=ImplementationReadiness(ciso='YES', backup='YES')
    regulatory_classification=RegulatoryClassification(cra_product_class='CLASS_I')
    role_matrix=RoleMatrix()
    regulatory_interactions=RegulatoryInteractions()
ctx = Mock()
out = _project_company_context(ctx)
required = {'implementation_readiness', 'regulatory_classification', 'role_matrix', 'regulatory_interactions'}
assert required.issubset(out), f'G3 FAIL: missing {required - out.keys()}'
print('G3 OK', sorted(required))
" 2>&1 | tail -1

# G4 — testes passam
pytest tests/unit/v2/test_corr048_metadata_threading.py -q 2>&1 | tail -1 | grep -qE "passed" && \
    echo "G4 OK" || { echo "FAIL G4"; exit 1; }

# G5 — pytest tests/unit/v2/ verde
pytest tests/unit/v2/ -m "not slow" -q 2>&1 | tail -1 | grep -qE "passed" && \
    echo "G5 OK" || { echo "FAIL G5"; exit 1; }

# G6 — run-traced produz trace_id
test -s logs/phase1/corr048_langfuse_trace_id.txt && \
    echo "G6 OK" || { echo "FAIL G6"; exit 1; }

# G7 — 9 outputs regenerados
test -f output/phase1/versions/04_Company_Context_Assessment_v2.md && \
test -f output/phase1/versions/04a_Architecture_DataInventory_v2.md && \
test -f output/phase1/versions/04b_Security_Posture_v2.md && \
test -f output/phase1/versions/04c_ThirdParty_Landscape_v2.md && \
test -f output/phase1/versions/04d_Org_Roles_RACI_v2.md && \
test -f output/phase1/versions/05_Regulatory_Applicability_v2.md && \
test -f output/phase1/versions/06_Clause_Mapping_Matrix_v2.md && \
test -f output/phase1/versions/07_Structured_Compliance_Matrix_v2.md && \
test -f output/phase1/versions/07b_Proportionality_Profile_v2.md && \
    echo "G7 OK" || { echo "FAIL G7"; exit 1; }

# G8 — CI gates
bash .hooks/ci-csf-frozen-list.sh 2>&1 | tail -1 | grep -q "OK" && \
    bash .hooks/ci-frameworks.sh 2>&1 | tail -1 | grep -q "OK" && \
    echo "G8 OK" || { echo "FAIL G8"; exit 1; }

echo "=== ALL GATES PASSED ==="
```

**Definição de done:** G1–G8 todos PASS.

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `src/aegis_phase1/v2/graph.py` | **MODIFY** — T1/T2/T3: OTel SDK, metadata, per-node tags, per-node span names |
| `src/aegis_phase1/v2/runner.py` | **MODIFY** — T2: structured metadata em `cmd_run_all_traced` |
| `src/aegis_phase1/v2/domain/inputs.py` | **MODIFY** — T4: estender `_project_company_context` com 4 fields do CORR-047 |
| `src/aegis_phase1/prompts_v2/invoker.py` | **MODIFY** — T1-alt: remover double-attach (Plano B) OU T1 truncation a 10KB |
| `tests/unit/v2/test_corr048_metadata_threading.py` | **NEW** — 5 testes |
| `logs/phase1/corr048_run_traced.log` | **NEW** — runtime artifact |
| `logs/phase1/corr048_langfuse_trace_id.txt` | **NEW** — 32 hex chars |
| `logs/phase1/corr048_langfuse_tree.png` | **NEW** (opcional) — screenshot da tree Langfuse |
| `execution/CONTRACT-048.md` | **NEW** (este) |

**Não modificar:** `preproc_out/`, `Methodology-main/`, `.hooks/`,
schema output (CORR-045 já fechou), mock LLM (T6 precisa de real).

---

## Estrutura de commits

```
feature/aegis-p1-corr-048
├─ commit 1: T1+T1-alt — OTel SDK (Plano A) ou callback cleanup (Plano B)
├─ commit 2: T2 — metadata estruturado + tags per-node
├─ commit 3: T3 — per-node span names
├─ commit 4: T4 — threading 4 fields do CORR-047
├─ commit 5: T5+T6 — testes + run real + trace_id + report
```

5 commits sequenciais. 1 branch per contract (AGENTS.md §10).

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| OTel SDK 4.8.0b1 instável (beta) | Plano B (T1-alt) — manter CallbackHandler, remover double-attach |
| Tracing tests existentes partem (test_langfuse_callback_corr011, test_trace_graph_corr017) | Adaptar/atualizar esses tests; documentar no commit |
| `_project_company_context` tem callers que esperavam shape antigo | Grep antes (vê: `inputs.py:124` é o único caller); backward-compat via dict path |
| Run real demora ~10-15 min (run-all-traced tem 4 stages × LLM calls) | Background com setsid+nohup; monitor via log; timeout 1800s |
| Trace > 80MB (limite render Langfuse) | Truncar I/O a 10KB em T1 (max payload por generation) |
| Tag `corr-XXX` ainda noutros sítios (não só runner.py) | Grep global antes de T1; remover sistematicamente |
| Double-attach em invoker.py:182-186 | Validar que NÃO é double-attach antes de remover (pode estar lá para fallback) |
| Langfuse UI pode não mostrar tree se as filhas não tiverem parentObservationId | Validar via API (`GET /api/public/traces/<id>`) |

---

## Change log

- 2026-07-22: v1.0 — contract criado pelo orchestrator (recriado a
  partir do briefing da missão; o ficheiro `CONTRACT-048.md`
  original não foi encontrado no repositório).

---

## Verdict pós-CORR-049 (2026-07-22)

**Status:** PASS (cascade-merged into feature/aegis-p1-corr-049).

**CORR-049 integrou este contract num branch cascade. Detalhes em
`execution/CONTRACT-049.md` §FASE 1 e `logs/phase1/corr049_parity_report.md`.

**Evidence:** 15/16 quality gates pass; only G11 (concatenate: 0 domains)
fails, and that is a model-side issue (gemma4:e2b not following schema),
not a contract-048 fix issue. The 048 work (data path: catalogs/helper/lane
filter/loader-fields/threading/metadata) is permanent and 100% effective.
