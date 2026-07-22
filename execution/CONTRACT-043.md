# CORR-043 — Pós-CORR-042 fixes + Langfuse traced workflow

## Resumo

Contract de **fixes** dos 4 issues identificados no post-mortem do
CORR-042 (ver `logs/phase1/corr042_errors.md` e §"Issues encontrados"
no `CONTRACT-042.md`) + adição do workflow traced (Langfuse) que não
foi exercitado no CORR-042.

**CORR-042 fechou a estratégia principal** (9/9 outputs regenerados
com Ollama real, paridade 9/9 PASS, 5/6 contracts PASS). Restam **5
fixes pontuais** (não bloqueadores para case1, mas bloqueadores para
generalização SecureBorder/OmniBank em CORR-044+):

1. **P1C-LLM-01 canonical path crashes** (`'str' object has no
   attribute 'get'`) — o orchestrator passa `layer0_subdomain_refs`
   como `list[str]` quando o executor espera `list[dict]`. A run
   CORR-042 caiu no fallback legacy LLM-A (funciona, mas o caminho
   canónico está morto).
2. **`_build_company_context` retorna `dict` em vez de `CompanyContext`**
   — obriga a um shim `isinstance(ctx, dict)` em `inputs.py` (aplicado
   inline em CORR-042, sem tipagem nem testes).
3. **`--run-reduce` isolado não tem precondition guard** — quando
   Doc 07b falta, produz SCHEMA_ERROR noise em vez de abortar limpo.
4. **Workflow não usa `--run-all-traced`** — o flag existe e Langfuse
   está wired, mas CORR-042 só usou `--run-all`. Para observar as 16
   LLM generations na UI Langfuse, precisa de exercitar o traced.
5. **Testes P1C-LLM-01 canonical** — CORR-040 declarou "15 tests" mas
   estas não cobrem o path canónico `_map_domains_via_p1c_llm_01`
   (testam o legacy fallback). Quando o fix 1 for aplicado, adicionar
   teste que valide que o path canónico não crasha.

**Branch:** `feature/aegis-p1-corr-043`
**Data:** 2026-07-21
**Trigger:** post-mortem CORR-042 — "5/6 contracts PASS, 1/6 PARTIAL
with documented deferral to CORR-043 (canonical P1C-LLM-01 path fix)".

---

## Pré-flight (validado pelo orchestrator)

```
$ git branch --show-current
feature/aegis-p1-corr-042       # ← executor cria corr-043 a partir de main

$ git status --short
(vazio)                          # working tree clean

$ grep OLLAMA_MODEL .env src/.env
.env:8:OLLAMA_MODEL=gemma4:e2b   # ✓ alinhado (CORR-042-T4)
src/.env:8:OLLAMA_MODEL=gemma4:e2b

$ ls execution/CONTRACT-043.md
ls: cannot access ...           # ✓ não existe ainda

$ ls logs/phase1/corr042_errors.md
(existe — ver §"Root causes" abaixo)
```

---

## Root causes (proveniência dos fixes)

### Fix 1 — P1C-LLM-01 canonical path crash

**Sintoma (CORR-042-T6.3):** 2 PYTHON_ERROR `'str' object has no
attribute 'get'`; orchestrator WARN "P1C-LLM-01 MAP path failed —
falling back to legacy loop".

**Localização:**
- `_map_domains_via_p1c_llm_01` em `src/aegis_phase1/v2/orchestrator.py:560-595`
  (chama o executor em `:590`).
- `run_phase_1c_map` em `src/aegis_phase1/prompts_v2/phase1_executor.py:234-276`
  (o `.get()` que crasha não está aqui dentro — linhas 250-275 todas
  guardadas com `isinstance`; o crash é **dentro** do `invoker.invoke`
  ao consumir o `inputs` dict).
- **Causa raiz:** `orchestrator.py:594` constrói
  `layer0_subdomain_refs` como `list((self.state.get("subdomains") or {}).keys())`
  → **`list[str]`** de subdomain IDs (e.g. `["SD-D02-01", ...]`). O
  executor/invoker spec espera `list[dict]` onde cada dict tem metadados
  do subdomain (objective, pairs, anchors, etc.).
- **Mesma shape** repetida em `orchestrator.py:956` e `:1598` — todas
  as 3 callers precisam do fix.

**Decisão:** em `_map_domains_via_p1c_llm_01` (e nos 2 outros callers),
construir `layer0_subdomain_refs` a partir do **`PreprocCatalogLoader`**
(em vez de só `state["subdomains"].keys()`). Para cada subdomain ID,
carregar o dict de metadados via `preproc_catalog.load_subdomains()`
(já cached in-memory desde CORR-037). O shape deve ser:

```python
layer0_subdomain_refs = [
    {
        "sub_domain_id": sd.id,                 # "D-01.1"
        "title": sd.title,
        "participating_regulations": sd.participating_regulations,
        "hso_hl_objective": sd.hso_hl.objective if sd.hso_hl else None,
        "objective": sd.hso_hl.objective if sd.hso_hl else None,
        "pairs": sd.pairs,                      # list com downstream_implication
        "anchors": [a for sr in sd.security_requirements for a in sr.anchors],
        "csf": sd.csf_hint,
    }
    for sd in applicable_subdomains
]
```

O schema exato deve ser confirmado lendo o spec
`Methodology-main/00_METHODOLOGY/PROMPTS/P1C-LLM-01-OVERLAP-CLASSIFICATION.md`
§Inputs (campo `layer0_subdomain_files`). Se o spec aceitar schema
mais simples, adaptar — não inventar campos que o spec não pede.

### Fix 2 — CompanyContext typing

**Localização:**
- `_build_company_context` em `src/aegis_phase1/v2/orchestrator.py:273`
  retorna `dict[str, Any]` (construído a partir de `CompanyFacts`).
- Type canónico existe: `CompanyContext` Pydantic em
  `src/aegis_phase1/v2/state.py:21` (importado em `inputs.py:30`).
- Shim aplicado em `inputs.py:162` (`_project_company_context`) e
  `inputs.py:229-236, 276` (`_build_track_b_suggestion`) — branches
  `isinstance(ctx, dict)` adicionadas em CORR-042 inline.

**Decisão:** refactorizar `_build_company_context` para retornar
`CompanyContext` instance (não dict). Depois **deletar** as 3 branches
`isinstance(ctx, dict)` em `inputs.py`. Isto elimina o shim e tipa
o fluxo.

### Fix 3 — `--run-reduce` precondition guard

**Localização:** `cmd_run_reduce` em `src/aegis_phase1/v2/runner.py:644-703`.
Não tem guard para Doc 07b — quando falta, `orch.reduce()` em `:675`
produz SCHEMA_ERROR downstream em vez de abortar.

**Decisão:** adicionar guard em `runner.py:670` (depois de `orch.load`)
que verifica `state.get("output_paths", {}).get("07b")`. Se missing ou
vazio, abortar com mensagem útil:

```
ERROR: --run-reduce requires Doc 07b to be present. Run --run-map first
(or --run-all). State output_paths: {...}
```

Saída com exit code 1.

### Fix 4 — Workflow traced (Langfuse)

**Localização:** flag `--run-all-traced` em `runner.py:124`,
`cmd_run_all_traced` em `runner.py:709-743` já existe e está wired
(callbacks em `:732` passam `orch._langfuse_handler`).

**Decisão:** não mexer no código — só **exercitar o flag** em T5 deste
contract (substituir o passo `--run-all` final por `--run-all-traced`)
e **documentar no contract** que o traced é o caminho canónico para
observabilidade. Adicionar secção "Como observar no Langfuse" no fim
do contract com: URL `http://localhost:3000`, `trace_id` cached por
run (CORR-021), 16 generations esperadas.

### Fix 5 — Testes P1C-LLM-01 canonical path

**Decisão:** novo teste `tests/unit/v2/test_p1c_llm_01_canonical.py`
que:
- (a) chama `_map_domains_via_p1c_llm_01` (ou o método público que o
  expõe) num setup com state carregado de case1-tinytask real;
- (b) valida que **não** crasha com `'str' object has no attribute 'get'`;
- (c) valida que o `layer0_subdomain_refs` passado ao invoker é
  `list[dict]` (capture do prompt rendered);
- (d) valida que pelo menos 1 entry `scope_overlap_predicates.yaml`
  filtrada aparece no prompt rendered.

---

## Tarefas

### T1 — Fix P1C-LLM-01 canonical path (Fix 1)

- Modificar `_map_domains_via_p1c_llm_01` em
  `src/aegis_phase1/v2/orchestrator.py:560-595` para construir
  `layer0_subdomain_refs` a partir do `PreprocCatalogLoader` cached
  (`self.preproc_catalog.load_subdomains()`).
- Aplicar o mesmo fix nos 2 outros callers com o mesmo padrão:
  `orchestrator.py:956` e `:1598`. Considerar extrair helper privado
  `_build_layer0_subdomain_refs(subdomain_ids: list[str]) -> list[dict]`
  para evitar triplicação.
- Confirmar o schema esperado lendo
  `Methodology-main/00_METHODOLOGY/PROMPTS/P1C-LLM-01-OVERLAP-CLASSIFICATION.md`
  §"Inputs" (campo `layer0_subdomain_files`).

### T2 — CompanyContext typing (Fix 2)

- Refactorizar `_build_company_context` em
  `src/aegis_phase1/v2/orchestrator.py:273` para retornar
  `CompanyContext` instance (em vez de `dict[str, Any]`).
- Deletar as 3 branches `isinstance(ctx, dict)` em
  `src/aegis_phase1/v2/domain/inputs.py` (linhas ~162, 229-236, 276).
- Atualizar qualquer outro caller que esperava dict (procurar com
  `grep -rn "company_context" src/aegis_phase1/v2/`).

### T3 — `--run-reduce` precondition guard (Fix 3)

- Adicionar guard em `src/aegis_phase1/v2/runner.py:670` (dentro de
  `cmd_run_reduce`, depois de `orch.load`) que verifica Doc 07b.
- Em caso de missing, logar erro claro + exit 1.

### T4 — Testes P1C-LLM-01 canonical (Fix 5)

- Criar `tests/unit/v2/test_p1c_llm_01_canonical.py` com 4 casos
  (a-d descritos em Fix 5 acima).
- Os testes podem usar `MOCK_LLM=true` para o invoker — não precisam
  de Ollama real; o que se valida é a shape do `layer0_subdomain_refs`
  e que não há crash.
- Para capturar o prompt rendered: usar `MagicMock` no invoker e
  inspecionar `invoker.invoke.call_args.kwargs["inputs"]`.

### T5 — Re-run end-to-end traced (Fix 4 + regression check)

- Snapshot baseline dos outputs atuais (pós-CORR-042):
  ```bash
  mkdir -p output/phase1/baseline_pre_corr043/
  cp output/phase1/*.md output/phase1/*.xlsx output/phase1/baseline_pre_corr043/ 2>/dev/null
  ```
- Run com `--run-all-traced` (este é o fix 4 — exercitar o traced):
  ```bash
  source ../shared-venv/bin/activate
  python -m aegis_phase1.v2.runner \
      --case cases/case1-tinytask \
      --run-all-traced \
      2>&1 | tee logs/phase1/corr043_run_traced.log
  ```
- **Esperado:** 16 LLM calls, ~15-20 min, **0 PYTHON_ERROR**, **0
  SCHEMA_ERROR**, **0 fallback para legacy LLM-A loop** (o fix 1 deve
  fazer o path canónico funcionar).
- Verificar Langfuse UI: ir a `http://localhost:3000`, filtrar por
  tags `["case1-tinytask", "corr-043"]`, confirmar 1 root trace com
  16 generations aninhadas. Guardar trace_id em
  `logs/phase1/corr043_langfuse_trace_ids.txt`.

### T6 — Parity re-check

- Re-executar a verificação de paridade do CORR-042-T7 contra os novos
  outputs. Mesmos thresholds. Reportar em
  `logs/phase1/corr043_parity_report.md`.
- **Se paridade regredir** (algum doc que era ✅ ficou ⚠️/❌):
  investigar — o fix 1 pode ter mudado o conteúdo das lanes P1C-LLM-01
  (agora canónico em vez de legacy). Reportar honestamente; a
  divergência é dado real (canónico é mais correto que legacy).

### T7 — Verdict update em CONTRACT-040 e CONTRACT-042

- Em `execution/CONTRACT-040.md`, atualizar a secção "Verdict
  pós-execução" de ⚠️ PARTIAL para ✅ PASS (o fix 1 resolve o bug
  canónico que o PARTIAL documentava).
- Em `execution/CONTRACT-042.md`, atualizar a secção "Issues
  encontrados (para CORR-043)" marcando os 4 issues como RESOLVED
  em CORR-043 (commit hash).

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — P1C-LLM-01 canonical path não crasha
pytest tests/unit/v2/test_p1c_llm_01_canonical.py -q 2>&1 | tail -1 | grep -qE "passed" && echo "G1 OK" || { echo "FAIL G1"; exit 1; }

# G2 — inputs.py shim eliminado (CompanyContext tipado)
COUNT=$(grep -c "isinstance(ctx, dict)" src/aegis_phase1/v2/domain/inputs.py)
[ "$COUNT" = "0" ] && echo "G2 OK" || { echo "FAIL G2: shim still present ($COUNT occurrences)"; exit 1; }

# G3 — _build_company_context retorna CompanyContext
python3 -c "
import inspect
from aegis_phase1.v2.orchestrator import Phase1Orchestrator
src = inspect.getsource(Phase1Orchestrator._build_company_context)
assert 'CompanyContext(' in src, '_build_company_context must construct CompanyContext'
print('G3 OK')
" || { echo "FAIL G3"; exit 1; }

# G4 — run-reduce guard existe (verificação manual)
grep -A2 "07b" src/aegis_phase1/v2/runner.py | grep -qE "exit\(1\)|sys.exit|return 1" && echo "G4 OK" || echo "G4 WARN: verify runner.py:670 manually"

# G5 — suite v2 verde
pytest tests/unit/v2/ -q 2>&1 | tail -3 | grep -qE "passed" && echo "G5 OK" || { echo "FAIL G5"; exit 1; }

# G6 — run-traced produz 9 outputs com mtime > hoje
TODAY=$(date +%Y-%m-%d)
for doc in 04_Company_Context_Assessment 05_Regulatory_Applicability 06_Clause_Mapping_Matrix 07_Structured_Compliance_Matrix 07b_Proportionality_Profile 04a_Architecture_DataInventory 04b_Security_Posture 04c_ThirdParty_Landscape 04d_Org_Roles_RACI; do
    stat -c '%y' "output/phase1/${doc}.md" 2>/dev/null | grep -q "$TODAY" || { echo "FAIL G6: $doc.md not regenerated today"; exit 1; }
done
echo "G6 OK"

# G7 — sem PYTHON_ERROR no log traced
grep -q "PYTHON_ERROR" logs/phase1/corr043_run_traced.log && { echo "FAIL G7: PYTHON_ERROR present"; exit 1; } || echo "G7 OK"

# G8 — sem fallback legacy LLM-A no log traced (fix 1 validado)
grep -qE "falling back to legacy loop|P1C-LLM-01 MAP path failed" logs/phase1/corr043_run_traced.log && { echo "FAIL G8: still falling back to legacy"; exit 1; } || echo "G8 OK"

# G9 — Langfuse trace com generations (verificação manual da UI)
test -s logs/phase1/corr043_langfuse_trace_ids.txt && echo "G9 OK (manual verify Langfuse UI at http://localhost:3000)" || echo "G9 WARN: trace_ids file empty — check Langfuse UI manually"

# G10 — paridade sem regressão vs CORR-042
test -f logs/phase1/corr043_parity_report.md && ! grep -q "❌" logs/phase1/corr043_parity_report.md && echo "G10 OK" || { echo "FAIL G10: parity regression — see corr043_parity_report.md"; exit 1; }

# G11 — CI gates
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G11 OK" || { echo "FAIL G11"; exit 1; }

echo "=== ALL GATES PASSED ==="
```

**Definição de done:** G1–G11 todos PASS + commits no branch.

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `src/aegis_phase1/v2/orchestrator.py` | **MODIFY** — `_map_domains_via_p1c_llm_01` + 2 callers (`:956`, `:1598`) + `_build_company_context` retorna `CompanyContext` |
| `src/aegis_phase1/v2/domain/inputs.py` | **MODIFY** — deletar 3 branches `isinstance(ctx, dict)` |
| `src/aegis_phase1/v2/runner.py` | **MODIFY** — precondition guard em `cmd_run_reduce:670` |
| `tests/unit/v2/test_p1c_llm_01_canonical.py` | **NEW** — 4 casos (a-d) |
| `output/phase1/baseline_pre_corr043/` | **NEW** — snapshot pós-CORR-042 |
| `output/phase1/*.md` + `*.xlsx` | **REGENERATED** — por `--run-all-traced` |
| `logs/phase1/corr043_run_traced.log` | **NEW** |
| `logs/phase1/corr043_langfuse_trace_ids.txt` | **NEW** — trace_id + URL |
| `logs/phase1/corr043_parity_report.md` | **NEW** |
| `execution/CONTRACT-040.md` | **MODIFY** — verdict ⚠️ → ✅ |
| `execution/CONTRACT-042.md` | **MODIFY** — issues marcados RESOLVED |
| `execution/CONTRACT-043.md` | **NEW** (este) |

**Não modificar:** `preproc_out/`, `Methodology-main/`, `.hooks/`.

---

## Estrutura de commits

```
feature/aegis-p1-corr-043
├─ commit 1: T1 fix P1C-LLM-01 layer0_subdomain_refs shape (orchestrator.py 3 sítios)
├─ commit 2: T2 CompanyContext typing (orchestrator.py + inputs.py shim removal)
├─ commit 3: T3 run-reduce precondition guard (runner.py)
├─ commit 4: T4 test_p1c_llm_01_canonical.py
├─ commit 5: T5 snapshot + run-all-traced + outputs regenerados + langfuse trace_ids
├─ commit 6: T6 parity re-check (corr043_parity_report.md)
└─ commit 7: T7 verdict updates em CONTRACT-040 + CONTRACT-042
```

**Convenção AGENTS.md §10:** 1 branch por contract, commits sequenciais,
sem amending.

---

## Como observar no Langfuse (pós-run)

1. Abrir `http://localhost:3000` no browser.
2. Login com as creds de `src/.env` (`LANGFUSE_PUBLIC_KEY` /
   `LANGFUSE_SECRET_KEY`). Langfuse local costuma ter dev auth aberta.
3. Ir a **Traces** → filtrar por tags `case1-tinytask` e `corr-043`.
4. Esperado: **1 root trace** com nome tipo `phase1_run_all_traced`.
5. Abrir o trace → árvore de 16 generations:
   - 4 P1B-LLM-01/02 (GDPR + CRA × {interpretation, rationale})
   - 10 P1C-LLM-01 (1 por domain D-01..D-10)
   - 1 P1C-LLM-03 (strategic synthesis, runs 1st in reduce)
   - 1 P1C-LLM-02 (compound event, runs 2nd, consumes 03)
6. Cada generation tem tabs: **Prompt** (rendered com catálogos),
   **Output** (raw + parsed JSON), **Metrics** (latency, tokens).
7. **Validação visual do fix 1:** abrir o prompt de P1C-LLM-01 (domain
   D-01) e confirmar que `layer0_subdomain_refs` aparece como list de
   dicts (cada um com `sub_domain_id`, `objective`, `pairs`), **não**
   como list de str IDs.
8. Guardar o `trace_id` (visível na URL bar, formato
   `/trace/<uuid>`) em `logs/phase1/corr043_langfuse_trace_ids.txt`.

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Fix 1 muda output das lanes P1C-LLM-01 (canónico vs legacy) → paridade regrediu | G10 valida; se regredir, T6 reporta honestamente. Não reverter o fix — a divergência é dado real (canónico é mais correto que legacy). Considerar que o reference em `Methodology-main` é v1-style, então divergência de detail é esperada. |
| Fix 2 quebra outros callers de `_build_company_context` que esperavam dict | Grep antes: `grep -rn "_build_company_context\|state\[.company_context.\]" src/aegis_phase1/v2/`. Adaptar todos. |
| `--run-all-traced` mais lento que `--run-all` (overhead LangGraph) | Tempo esperado ~15-20 min vs 9 min do CORR-042. Aceitável para uma run de validação. |
| Langfuse server em localhost pode estar down | Pré-flight: `curl -s http://localhost:3000/api/public/health`. Se down, abortar T5 e reportar. |
| Fix 1 requer schema confirmation do spec P1C-LLM-01 | Ler `Methodology-main/.../PROMPTS/P1C-LLM-01-OVERLAP-CLASSIFICATION.md` §Inputs antes de codificar. Se spec ambíguo, perguntar ao orchestrator. |
| `test_p1c_llm_01_canonical.py` precisa de state real carregado | Usar `case1-tinytask` + `MOCK_LLM=true` para invoker; o que se testa é a shape do inputs dict, não a chamada LLM real. |
| `gemma4:e2b` pode produzir JSON malformado diferente quando o prompt muda (mais contexto) | `RobustParser` tem 5 estratégias; se aumentar format-errors, reportar mas não bloquear. |

---

## Pós-CORR-043

**Se G1–G11 passarem:** estratégia CORR-036 → CORR-043 CLOSED de
verdade (todos os 6 contracts originais PASS, canonical path vivo,
Langfuse observabilidade confirmada). Próximo passo =
generalização SecureBorder/OmniBank (CORR-044+).

**Se G7 ou G8 falharem** (PYTHON_ERROR ou legacy fallback persiste):
o fix 1 está incompleto. Investigar o `.get()` exato que ainda crasha
— pode ser outra key além de `layer0_subdomain_refs` (e.g.
`layer0_annotation` em `annotations/D-XX.yaml`). Reportar em
`logs/phase1/corr043_errors.md` e marcar G7/G8 como FAIL honesto.

**Se G10 falhar** (paridade regrediu): analisar o diff em
`corr043_parity_report.md`. Provável cenário: Doc 07 mudou porque
as lanes P1C-LLM-01 agora produzem output canónico (com mais detail)
em vez de legacy LLM-A (mais simples). Isto é melhoria, não regressão
— mas o verdict ⚠️ PARTIAL deve ser reportado se algum doc ficou ❌.

---

## Update CORR-044 (2026-07-22)

**Update CORR-044 (2026-07-22):** o fix canónico de CORR-043-T1 só
funciona no caminho `orch.map_domains()` (`--run-all` / `--map-only`).
O caminho LangGraph (`--run-all-traced`) tem bug pre-existing
(CORR-018b, commit `60ecf73`) que faz o MAP não escrever em
`state["domain_results"]`. CORR-044 aplica wiring minimal em
`graph.py:_make_map_node` para desbloquear; o refactor canónico
per-domain (substituir `map_single_domain` legacy por
`map_single_domain_canonical` com 1 call P1C-LLM-01 por span MAP)
fica para **CORR-045**.

Detalhe do fix: `graph.py` agora escreve
`orch.state["domain_results"][domain_id] = result` em ambos os
caminhos (sucesso e `MapPartialFailure`). O orchestrator instance
é partilhado entre nós via `configurable["orchestrator"]`, então a
mutação é visível ao downstream `_reduce_det` → `concatenate`.

Resultado pós-CORR-044: `--run-all-traced` deixa de produzir
"concatenate: 0 domains -> 0 subdomains" e os 9 outputs regeneram
com conteúdo real.

---

## Change log

- 2026-07-22: Update CORR-044 — nota retroactiva: o fix T1 deste
  contract (canonical P1C-LLM-01 path) só funciona via
  `orch.map_domains()`. O caminho LangGraph (--run-all-traced)
  ficou coberto pelo wiring minimal de CORR-044.

- 2026-07-21: v1.0 — contract inicial criado pelo orchestrator após
  auditoria pós-CORR-042 (4 issues documentados + novo requisito
  Langfuse traced workflow).
