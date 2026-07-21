# CORR-042 — SP-F Fecho + run end-to-end real + paridade verificada

## Resumo

Contract de **fecho** da estratégia faseada CORR-036 → CORR-041.
Os 6 contracts anteriores foram estruturalmente executados (branches,
commits, módulos criados, 466/466 testes v2 passam, smoking gun do
catálogo fixed), mas a auditoria pós-execução revelou **3 lacunas** que
invalidam parcialmente o sucesso declarado:

1. **Outputs nunca regenerados pós-refactor.** Todos os ficheiros em
   `output/phase1/*.md` são de 2026-07-14; os contracts são de
   2026-07-21. A paridade contra a referência está por verificar —
   os "9/9 gates PASS" dos commit messages referem-se a testes
   unitários com mocks, não a uma run real.
2. **`tests/unit/test_state_propagation.py` a falhar 3/3.** Faz
   `from aegis_phase1 import graph` (linhas 10/15/20); `graph.py` foi
   removido em CORR-037-T4. Teste vermelho que passou despercebido
   porque o número "466/466" reportado era só `tests/unit/v2/`.
3. **`invoker.py:53` ainda tolerante.** `catalog_loader: CatalogLoader | None = None`
   continua opcional sem guard. Funciona hoje porque runner/factory
   passam loader, mas é regressão-latente — qualquer novo entrypoint
   que esqueça volta ao smoking gun original.

Este contract **fecha as 3 lacunas** + **corre o pipeline end-to-end
real** (Ollama `gemma4:e2b`) + **verifica paridade** contra a referência
com diffs normalizados.

**Branch:** `feature/aegis-p1-corr-042`
**Data:** 2026-07-21
**Trigger:** auditoria pós-CORR-041 — "tests passed" sem run real é o
anti-pattern que AGENTS.md §10.2 avisa.

---

## Pré-flight (validado pelo orchestrator antes de escrever este contract)

```
$ git branch --show-current
feature/aegis-p1-corr-041       # ← executor cria corr-042 a partir de main

$ curl -s http://localhost:11434/api/tags | jq -r '.models[].name' | grep e2b
gemma4:e2b                       # ✓ disponível

$ grep OLLAMA_MODEL .env src/.env
.env:7:OLLAMA_MODEL=gemma4:e2b
src/.env:8:OLLAMA_MODEL=gemma4:e4b   # ← CONFLITO: corrigir em T4

$ git log -1 --format="%ai" feature/aegis-p1-corr-041
2026-07-21 21:58                # refactor = 21 jul

$ stat -c '%y' output/phase1/05_Regulatory_Applicability.md
2026-07-14 12:18                # output = 14 jul (7 dias stale)

$ source ../shared-venv/bin/activate && pytest tests/unit/test_state_propagation.py -q | tail -3
3 failed                        # ← vermelho real
```

---

## Tarefas

### T1 — Remover teste stale `test_state_propagation.py`

**Ficheiro:** `tests/unit/test_state_propagation.py`

As 3 funções fazem `from aegis_phase1 import graph` (linhas 10, 15, 20).
`graph.py` foi removido em CORR-037-T4 (v1 legacy elimination).

**Decisão:** **deletar o ficheiro inteiro.** Não há equivalente v2
útil — `tests/unit/v2/test_graph_corr018a.py` (343 LOC) já cobre a
topologia v2 do `StateGraph`. Se houver cobertura útil para preservar
(state propagation entre nós), migrar para um novo teste em
`tests/unit/v2/` — mas avaliar primeiro se vale a pena (o teste v1
validava a topologia `parse_inputs → A → B → C`, que não existe em v2).

Antes de deletar, confirmar com
`grep -rn "test_state_propagation\|state_propagation" tests/ src/ docs/` —
se ninguém referencia, é seguro apagar.

### T2 — Limpar `__pycache__` órfãos do v1

```bash
# Estes dirs só contêm __pycache__ (source foi removido em CORR-037-T4)
ls src/aegis_phase1/nodes/        # só __pycache__
ls src/aegis_phase1/subphases/    # só __pycache__
rm -rf src/aegis_phase1/nodes/ src/aegis_phase1/subphases/

# Verificar
git status --short                # deve mostrar "deleted: ..." para os dirs
```

### T3 — Endurecer `invoker.py:53` (anti-regressão)

**Ficheiro:** `src/aegis_phase1/prompts_v2/invoker.py`

**Estado atual (linha 53):**
```python
def __init__(
    self,
    ...,
    catalog_loader: CatalogLoader | None = None,   # ← tolerante
) -> None:
    ...
    self.catalogs = catalog_loader                   # ← sem guard
```

**Alvo:** manter o `None = None` (retro-compat com testes isolados do
invoker), **mas adicionar um guard explícito** no método que consome
catálogos. Localizar o método que chama `self.catalogs.load(...)` ou
`self.catalogs.filter_applicable(...)` (procurar `self.catalogs` em
invoker.py) e adicionar:

```python
def _load_catalogs_for(self, prompt_spec_id: str) -> dict:
    """Load catalogs required by a prompt spec. Raises if missing."""
    if self.catalogs is None:
        raise RuntimeError(
            f"catalog_loader is None but prompt {prompt_spec_id} requires "
            f"deterministic catalogs (tipo2/tipo3/scope_overlap/event_templates). "
            f"Wire a CatalogLoader at Phase1LLMInvoker construction time. "
            f"(CORR-042 anti-regression guard; original smoking gun was "
            f"v2/orchestrator.py never passing catalog_loader — see CORR-039-T1.)"
        )
    # ... existing load logic
```

Os 4 LLMs que requerem catálogos (consultar `prompts_v2/llm_inventory.py`
`LLM_SPECS` para confirmar): `P1B-LLM-01-INTERPRETATION` (tipo2/tipo3),
`P1B-LLM-02-RATIONALE` (herda de 01), `P1C-LLM-01-OVERLAP-CLASSIFICATION`
(scope_overlap_predicates), `P1C-LLM-02-COMPOUND-EVENT` (event_templates).
`P1C-LLM-03-STRATEGIC-SYNTHESIS` não requer catálogo (consome doc07b).

Determinar para cada spec_id se requer catálogo e adicionar o guard
apenas onde aplicável. Pode ser útil um set constante
`_CATALOG_REQUIRED_SPECS = {"P1B-LLM-01-INTERPRETATION", ...}` no topo
do módulo.

**Teste novo:** `tests/unit/prompts_v2/test_invoker_catalog_guard.py`
que valida:
- (a) construir invoker sem `catalog_loader` + invocar `P1B-LLM-01` →
  `RuntimeError` com a mensagem acima (use `pytest.raises(RuntimeError,
  match="catalog_loader is None")`).
- (b) construir com `CatalogLoader` real (ou `MagicMock(spec=CatalogLoader)`) +
  invocar → não levanta.
- (c) `P1C-LLM-03-STRATEGIC-SYNTHESIS` sem `catalog_loader` → NÃO levanta
  (não requer catálogo).

### T4 — Resolver conflito `.env` vs `src/.env`

**Ficheiros:** `.env` (root) e `src/.env`

```
$ grep OLLAMA_MODEL .env src/.env
.env:7:OLLAMA_MODEL=gemma4:e2b      # canonical
src/.env:8:OLLAMA_MODEL=gemma4:e4b  # ← divergente
```

**Decisão:** alinhar `src/.env` com `.env` → `OLLAMA_MODEL=gemma4:e2b`.
Segundo AGENTS.md §9, o `.env` "oficial" vive em `src/.env` (loaded por
`aegis_phase1/env.py`), mas o root `.env` também é usado por scripts.
Ambos devem dizer o mesmo.

Adicionar comment em `src/.env`:
```bash
# CORR-042 (2026-07-21): aligned with root .env. gemma4:e2b is the
# canonical Phase 1 model (per PROMPTS/*.md Model Configuration sections
# and the RobustParser 5-strategy fallback tuned for its format bugs).
```

### T5 — Snapshot pré-run (baseline dos outputs stale)

Antes de correr o pipeline, snapshot do estado atual (stale) para
comparação:

```bash
mkdir -p output/phase1/baseline_pre_corr042/
cp output/phase1/{04,04a,04b,04c,04d,05,06,07,07b}_*.md output/phase1/baseline_pre_corr042/ 2>/dev/null
cp output/phase1/Case_01_Phase1.xlsx output/phase1/baseline_pre_corr042/ 2>/dev/null
```

Isto preserva os outputs de 14 jul para auditoria futura ("o que mudou
entre a run antiga e a nova?").

### T6 — Run end-to-end REAL (sem mock)

Esta é a tarefa central do contract. Correr o pipeline completo contra
Ollama `gemma4:e2b`, **sem** `MOCK_LLM=true`. Sequência de 5 invocações
cada uma com o seu log:

```bash
source ../shared-venv/bin/activate

# 6.1 — Stage deterministicos primeiro (sem LLM, validação rápida)
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --deterministic-only \
    2>&1 | tee logs/phase1/corr042_run_deterministic.log

# 6.2 — Stage Phase 1B (4 P1B-LLM calls, 2 regs × 2 LLMs)
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --run-phase-1b \
    2>&1 | tee logs/phase1/corr042_run_phase1b.log

# 6.3 — Stage MAP (10 P1C-LLM-01 calls, 1 por domain)
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --run-map \
    2>&1 | tee logs/phase1/corr042_run_map.log

# 6.4 — Stage REDUCE (1 P1C-LLM-03 + 1 P1C-LLM-02, nesta ordem)
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --run-reduce \
    2>&1 | tee logs/phase1/corr042_run_reduce.log

# 6.5 — Verificação final: run-all completo (deve ser idempotente)
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --run-all \
    2>&1 | tee logs/phase1/corr042_run_all.log
```

**Se uma stage falhar**, **NÃO** avançar para a seguinte. Investigar,
corrigir, e re-correr essa stage. Reportar o erro em
`logs/phase1/corr042_errors.md` com:
- Stage que falhou
- Stack trace completo
- Hipótese de causa raiz
- Fix aplicado (ou justificação de deferral para CORR-043)

**Tempo esperado:** ~30-60 min total (16 LLM calls + rendering). Cada
call `gemma4:e2b` demora ~30-90s dependendo do prompt.

**Timeout:** se uma stage demorar > 30 min, abortar com
`timeout 1800 <command>` e reportar — pode indicar loop de retry ou
hang no Ollama.

**Nota sobre format errors:** o `gemma4:e2b` tem format bugs conhecidos
(o `RobustParser` foi desenhado para eles). Se uma chamada falhar após
retries, aparece em `logs/phase1/format-errors.jsonl` — verificar esse
log; se houver um padrão recorrente de malformation, reportar.

### T7 — Verificação de paridade contra referência

**Referência:** `/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`

Para cada output, fazer diff semântico (não textual — ignorar
timestamps, IDs gerados, whitespace):

```bash
REF="/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT"
NEW="output/phase1"

# Normalização: strip timestamps, IDs tipo A417FB3B/CM-TINYTASK-2026-001,
# UUIDs, blank lines, trailing whitespace
normalize() {
    sed -E \
        -e 's/[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}//g' \
        -e 's/[A-F0-9]{8}//g' \
        -e 's/[0-9]{4}-[0-9]{2}-[0-9]{2}/DATE/g' \
        -e 's/(created|updated|completionDate|assessmentDate):.*/\1: DATE/' \
        -e 's/[A-Z]+-[A-Z]+-[0-9]{4}-[0-9]{3}/ID/g' \
        "$1" | grep -vE '^\s*$' | sed -E 's/[[:space:]]+$//'
}

{
for doc in 04_Company_Context_Assessment 05_Regulatory_Applicability 06_Clause_Mapping_Matrix 07_Structured_Compliance_Matrix 07b_Proportionality_Profile 04a_Architecture_DataInventory 04b_Security_Posture 04c_ThirdParty_Landscape 04d_Org_Roles_RACI; do
    echo "=== $doc ==="
    diff <(normalize "$REF/${doc}.md") <(normalize "$NEW/${doc}.md") | head -60
    echo ""
done
} > logs/phase1/corr042_parity_diff.txt 2>&1
```

Compilar `logs/phase1/corr042_parity_report.md` com tabela de verdicts:

| Output | Métrica | Esperado | Real | Verdict |
|--------|---------|----------|------|---------|
| Doc 04 | company facts (employees, sector, jurisdiction, revenue) | idêntico | … | ✅/⚠️/❌ |
| Doc 05 | `applicable_regs == [GDPR, CRA]`, roles `[CONTROLLER, MANUFACTURER]` | idêntico | … | ✅/⚠️/❌ |
| Doc 06 | contagem de cláusulas GDPR/CRA aplicáveis | 28/26 ±2 | … | ✅/⚠️/❌ |
| Doc 06 | NI médio GDPR/CRA | 2.714/2.923 ±0.1 | … | ✅/⚠️/❌ |
| Doc 07 | nº de rows D-XX.Y | 38 | … | ✅/⚠️/❌ |
| Doc 07 | cells ✅/— divergentes da referência | ≤ 3 | … | ✅/⚠️/❌ |
| Doc 07 | NI por subdomain (máx desvio) | ±0.2 | … | ✅/⚠️/❌ |
| Doc 07b | Track B tiers atribuídos (% de subdomains ativos) | 100% | … | ✅/⚠️/❌ |
| Doc 04a-d | estrutura (secções presentes vs referência) | idêntica | … | ✅/⚠️/❌ |
| xlsx | nº de sheets | 7 | … | ✅/⚠️/❌ |

**Thresholds são defaults justos; se algum estiver off, reportar
honestamente com ❌.** Divergências são dados reais, não tuning.

### T8 — Escrever verdicts PASS/PARTIAL/FAIL nos contracts CORR-036..041

Para cada um dos 6 contracts anteriores (`execution/CONTRACT-036.md` …
`CONTRACT-041.md`), adicionar no fim do ficheiro uma secção:

```markdown
---

## Verdict pós-execução (CORR-042, 2026-07-21)

**Status:** ✅ PASS / ⚠️ PARTIAL / ❌ FAIL

**Evidence:**
- Gates executados em: <commit hash do CORR-042 que validou>
- Outputs verificados contra referência: <ver logs/phase1/corr042_parity_report.md>
- Notas: <qualquer caveat, e.g. "Doc 07 com 5 cells divergentes — ver CORR-043 se necessário">
```

O verdict reflete o estado **atual** (pós CORR-042 run), não o estado
declarado na altura do commit. Exemplo: se CORR-040 prometia "Doc 07
com ≤3 cells divergentes" mas o run real mostra 8 cells divergentes,
o verdict é ⚠️ PARTIAL com essa nota.

Os verdicts por contract (referência):
- CORR-036 (ontology fix): deveria ser ✅ PASS — verificável com G1 do
  contract original.
- CORR-037 (loaders): deveria ser ✅ PASS se `pytest tests/unit/` verde.
- CORR-038 (applicability + Doc 04/05): ✅ se Doc 04 e Doc 05 dentro de
  thresholds; ⚠️ caso contrário.
- CORR-039 (clause mapping + catalogs): ✅ se Doc 06 dentro de thresholds
  + catálogos wired (verificar `logs/phase1/llm-calls.jsonl` mostra
  `tipo2_*` no prompt rendered).
- CORR-040 (domain activation + Doc 07): ✅ se Doc 07 ≤3 cells
  divergentes; ⚠️ caso contrário.
- CORR-041 (synthesis + Doc 04a-d): ✅ se Doc 04a-d estrutura idêntica;
  ⚠️ caso contrário.

### T9 — Atualizar CONTRACT-042 com o resultado real (self)

No fim, preencher a secção §"Resultado da run" abaixo com os números
reais. Isto fecha o loop — o contract é self-documenting.

---

## Quality gates (FAIL default — todos têm de passar)

```bash
source ../shared-venv/bin/activate

# G1 — stale test resolvido (deletado ou migrado)
if [ -f tests/unit/test_state_propagation.py ]; then
    pytest tests/unit/test_state_propagation.py -q 2>&1 | tail -1 | grep -qE "passed" && echo "G1 OK: test passes" || { echo "FAIL G1: test still failing"; exit 1; }
else
    echo "G1 OK: stale test removed"
fi

# G2 — __pycache__ órfãos removidos
if [ -d src/aegis_phase1/nodes/ ] || [ -d src/aegis_phase1/subphases/ ]; then
    echo "FAIL G2: v1 dirs still present"; exit 1
else
    echo "G2 OK: v1 dirs gone"
fi

# G3 — invoker catalog guard funciona
pytest tests/unit/prompts_v2/test_invoker_catalog_guard.py -q 2>&1 | tail -1 | grep -qE "passed" && echo "G3 OK: guard tested" || { echo "FAIL G3: catalog guard missing/broken"; exit 1; }

# G4 — .env alinhado
diff <(grep OLLAMA_MODEL .env) <(grep OLLAMA_MODEL src/.env) > /dev/null && echo "G4 OK: .env aligned" || { echo "FAIL G4: .env diverges"; exit 1; }

# G5 — suite completa verde (inclui tests/unit/ raiz, não só v2/)
pytest tests/unit/ -q 2>&1 | tail -3 | grep -qE "passed" && echo "G5 OK: full unit suite green" || { echo "FAIL G5: unit suite has failures"; exit 1; }

# G6 — run-all real produziu 9 outputs com mtime > hoje 00:00
TODAY=$(date +%Y-%m-%d)
for doc in 04_Company_Context_Assessment 05_Regulatory_Applicability 06_Clause_Mapping_Matrix 07_Structured_Compliance_Matrix 07b_Proportionality_Profile 04a_Architecture_DataInventory 04b_Security_Posture 04c_ThirdParty_Landscape 04d_Org_Roles_RACI; do
    stat -c '%y' "output/phase1/${doc}.md" 2>/dev/null | grep -q "$TODAY" || { echo "FAIL G6: $doc.md not regenerated today"; exit 1; }
done
echo "G6 OK: all 9 outputs regenerated today"

# G7 — Paridade dentro dos thresholds (T7)
test -f logs/phase1/corr042_parity_report.md && \
    ! grep -q "❌" logs/phase1/corr042_parity_report.md && echo "G7 OK: parity within thresholds" || \
    { echo "FAIL G7: parity outside thresholds — see logs/phase1/corr042_parity_report.md"; exit 1; }

# G8 — CI gates preservados
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G8 OK: CI gates green" || { echo "FAIL G8: CI gate failed"; exit 1; }

# G9 — LLM call log mostra ~16 calls (4 P1B + 10 P1C-01 + 1 P1C-03 + 1 P1C-02)
CALLS=$(jq -s 'length' logs/phase1/llm-calls.jsonl 2>/dev/null || echo 0)
if [ "$CALLS" -ge 14 ]; then
    echo "G9 OK: $CALLS LLM calls logged (≥14 expected)"
else
    echo "FAIL G9: only $CALLS LLM calls logged (expected ~16)"
    exit 1
fi

echo "=== ALL 9 GATES PASSED ==="
```

**Definição de done:** G1–G9 todos PASS + commits no branch +
verdicts written back em CONTRACT-036..041 + secção §"Resultado" abaixo
preenchida.

**Caso G7 (paridade) falhe:** **NÃO** tentar tuningar. Reportar em
`logs/phase1/corr042_parity_report.md` com ❌ e detalhes. O contract
ainda é considered PARTIAL-success se G1-G6, G8, G9 passarem — a falha
de paridade é o input para CORR-043 ("fix divergências").

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `tests/unit/test_state_propagation.py` | **DELETE** |
| `src/aegis_phase1/nodes/` | **DELETE** (só `__pycache__`) |
| `src/aegis_phase1/subphases/` | **DELETE** (só `__pycache__`) |
| `src/aegis_phase1/prompts_v2/invoker.py` | **MODIFY** — adicionar `_load_catalogs_for` com guard + constante `_CATALOG_REQUIRED_SPECS` |
| `tests/unit/prompts_v2/test_invoker_catalog_guard.py` | **NEW** |
| `src/.env` | **MODIFY** — `OLLAMA_MODEL=gemma4:e4b` → `gemma4:e2b` + comment |
| `output/phase1/baseline_pre_corr042/` | **NEW** — snapshot dos outputs stale de 14 jul |
| `output/phase1/*.md` + `Case_01_Phase1.xlsx` | **REGENERATED** — pelo run T6 |
| `logs/phase1/corr042_run_{deterministic,phase1b,map,reduce,all}.log` (5 ficheiros) | **NEW** |
| `logs/phase1/corr042_parity_diff.txt` | **NEW** — diffs normalizados |
| `logs/phase1/corr042_parity_report.md` | **NEW** — tabela de verdicts por output |
| `logs/phase1/corr042_errors.md` | **NEW (se houver erros)** — incident log |
| `execution/CONTRACT-{036,037,038,039,040,041}.md` | **MODIFY** — adiciona secção "Verdict pós-execução" no fim |
| `execution/CONTRACT-042.md` | **NEW** (este) + modify no fim com §"Resultado da run" |

**Não modificar:** `preproc_out/`, `Methodology-main/`, `.hooks/` (exceto se CI gate revelar bug).

---

## Estrutura de commits

```
feature/aegis-p1-corr-042
├─ commit 1: T1+T2 cleanup (delete stale test + v1 __pycache__)
├─ commit 2: T3 invoker catalog guard + test_invoker_catalog_guard.py
├─ commit 3: T4 .env align
├─ commit 4: T5 baseline snapshot output/phase1/baseline_pre_corr042/
├─ commit 5: T6 run-all real (5 stages) + outputs regenerados + logs
├─ commit 6: T7 parity report (corr042_parity_diff.txt + corr042_parity_report.md)
└─ commit 7: T8+T9 verdicts em CONTRACT-036..041 + resultado em CONTRACT-042
```

**Convenção AGENTS.md §10:** 1 branch por contract, commits sequenciais,
sem amending.

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Run-all demora > 1h ou hang | Cada stage tem o seu log; usar `timeout 1800 <cmd>`; se uma stage não terminar em 30 min, abortar e reportar |
| Outputs divergem muito da referência (>threshold) | **Esperado** — reportar em `corr042_parity_report.md` com ❌ e marcar G7 como FAIL. **NÃO** tuningar para passar; a divergência é dado real que pode indicar bug no pipeline ou imprecisão na referência |
| `gemma4:e2b` produz JSON malformado (format bugs) | O `RobustParser` tem 5 estratégias de fallback; se falhar, vai para `logs/phase1/format-errors.jsonl` — verificar esse log |
| LLM inventa artigos/regulations | `base_system_prompt.md` + validator JSON Schema devem apanhar; se passarem, é bug do validator — reportar |
| Diff paridade tem muito ruído (timestamps, IDs) | A função `normalize()` em T7 já stripa IDs/timestamps; se ainda houver ruído, ajustar a regex em `corr042_parity_diff.txt` e re-gerar |
| Catalog guard quebra tests existentes do invoker | Os tests atuais passam `CatalogLoader` mock; o guard só dispara se `self.catalogs is None`. Verificar com `pytest tests/unit/prompts_v2/ -q` antes de avançar para T6 |
| `src/.env` tem outras chaves além de `OLLAMA_MODEL` | Só alterar a linha `OLLAMA_MODEL=`; preservar resto do ficheiro |
| Outputs Doc 04a-d (REDUCE) vazios ou curtos | Pode acontecer se P1C-LLM-03/02 falharem; reportar e marcar verdict ⚠️. Não é bloqueador para os docs deterministicos |

---

## Resultado da run (preencher no commit 7 — T9)

```
Pipeline: <DONE/PARTIAL/FAILED>
Tempo total: <min>
LLM calls: <n> (esperado ~16)

Paridade contra Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/:
  Doc 04:  <✅/⚠️/❌> <notas>
  Doc 05:  <✅/⚠️/❌> <notas>
  Doc 06:  <✅/⚠️/❌> <GDPR count: x vs 28; CRA count: y vs 26; NI: a.bcd vs 2.714/2.923>
  Doc 07:  <✅/⚠️/❌> <rows: n vs 38; cells divergentes: n>
  Doc 07b: <✅/⚠️/❌> <Track B tiers atribuídos: n/38>
  Doc 04a-d: <✅/⚠️/❌> <notas>
  xlsx:   <✅/⚠️/❌> <n sheets vs 7>

Gates G1-G9: <X/9 PASS>

Issues encontrados (para CORR-043 se necessário):
  - <lista de divergências ou bugs que este contract não fechou>
```

---

## Pós-CORR-042

**Se todos os gates G1-G9 passarem e paridade estiver dentro de
thresholds:** estratégia CORR-036 → CORR-042 está **CLOSED**. Pipeline
v2 produz 9 outputs verificados contra referência. Próximo passo =
generalização para SecureBorder/OmniBank (CORR-043+).

**Se G7 (paridade) falhar:** **NÃO** avançar para generalização. Os
diffs em `corr042_parity_report.md` são o input para o próximo contract:
CORR-043 passa a ser "fix divergências Doc 0X" em vez de "generalizar".

**Se G6 (outputs não regenerados) falhar:** o pipeline v2 tem um bug
bloqueador. Reportar stack trace em `corr042_errors.md` e abortar —
CORR-043 é "fix pipeline crash".

---

## Change log

- 2026-07-21: v1.0 — contract inicial criado pelo orchestrator após
  auditoria pós-CORR-041 revelar 3 lacunas (outputs stale, teste stale,
  invoker sem guard).
