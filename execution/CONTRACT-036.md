# CORR-036 — SP-A.0 Pre-flight + correção dados caso1

## Resumo

Primeiro contract da estratégia faseada **CORR-036 → CORR-041**
(reorientação do pipeline v2 para ler `preproc_out/` JSON diretamente,
sem regex, e alimentar os 5 LLMs canónicos com catálogos wired).

Este contract **não altera código**. Estabiliza os inputs antes de
o CORR-037 iniciar a refactorização dos loaders.

**Objetivo:** garantir que (a) o `preproc_out/` está limpo nos gates
de auditoria, (b) o source-of-truth do caso1 é consistente
(`phase1_ontology.yaml` alinhado com `classification.yaml`), e
(c) existe um snapshot baseline dos outputs atuais para diff futuro.

**Branch:** `feature/aegis-p1-corr-036`
**Data:** 2026-07-21
**Trigger:** diagnóstico da estratégia faseada — causa raiz identificada:
`phase1_ontology.yaml` (employees: 50, revenue: 5M) diverge de
`classification.yaml` (employees: 8, revenue: 2M); isto é o padrão
`DECLARATION_GAP` que `PHASE1_STRATEGY.md §6` manda flagear, mas como
source-of-truth está em conflito, os outputs não podem ser consistentes.

---

## Contexto (resumo da estratégia — ver plan aprovado)

A estratégia completa (6 contracts) tem como objetivo final:

> `python -m aegis_phase1.v2.runner --run-all cases/case1-tinytask`
> produz os 9 outputs (04/04a/04b/04c/04d/05/06/07/07b + xlsx) com
> diff semântico ≤ threshold contra
> `Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`,
> lendo exclusivamente `preproc_out/` JSON e com os 5 LLMs canónicos
> invocados com catálogos wired.

| SP | Contract | Branch | Foco |
|----|----------|--------|------|
| A.0 | **CORR-036 (este)** | feature/aegis-p1-corr-036 | Pre-flight + correção caso1 |
| A   | CORR-037 | feature/aegis-p1-corr-037 | PreprocCatalogLoader + CaseProfileLoader + depreciação v1 |
| B   | CORR-038 | feature/aegis-p1-corr-038 | ApplicabilityContext + Doc 04 + Doc 05 |
| C   | CORR-039 | feature/aegis-p1-corr-039 | ClauseMappingContext + Doc 06 + wiring catálogos P1B |
| D   | CORR-040 | feature/aegis-p1-corr-040 | DomainActivationContext + P1C-LLM-01 + Doc 07 + Track B |
| E   | CORR-041 | feature/aegis-p1-corr-041 | SynthesisContext + P1C-LLM-03 + P1C-LLM-02 + outputs finais |

---

## Decisão de produto (a justificar este contract)

`cases/case1-tinytask/input/company/classification.yaml` é o
**canonical source** (per o seu próprio cabeçalho: "This file is the
canonical source for company facts. The 01_Company_Context.md is
auto-generated FROM this file.").

Valores canonical: `employees: 8`, `revenue_eur: 2000000`,
`scale: MICRO`, `name: TinyTask Lda.`, `sector: Technology/Software`,
`jurisdiction: Portugal (EU)`.

`cases/case1-tinytask/context/phase1_ontology.yaml` diverge:
`employees: 50`, `revenue_eur: 5000000`, `size: small`,
`name: "TinyTask SaaS"`, `sector: "technology"`. Está stale.

**Decisão:** alinhar `phase1_ontology.yaml` com `classification.yaml`.
TinyTask foi desenhado como caso MICRO (8 empregados, €2M revenue) —
este é o valor que aparece consistentemente em
`01_Company_Context.md`, nos CSVs (`05_company_context.csv`), e na
referência `Methodology-main/02_CASES/Case_01_TinyTask_SaaS/.../04_Company_Context_Assessment.md`.
Os valores 50/5M são erro de snapshot.

**Isto é relevante para a estratégia porque** CORR-038 (SP-B) vai
produzir Doc 04 com base no `CompanyContext`, que é carregado a partir
destes YAMLs. Se o source estiver em conflito, o resultado de
`applicability` pode mudar (e.g., NIS2 passa a aplicar se
employees ≥ 50). Pequeno, mas disruptivo.

---

## Tarefas

### T1 — Corrigir `phase1_ontology.yaml`

Ficheiro: `cases/case1-tinytask/context/phase1_ontology.yaml`

Alterar o bloco `company:` para refletir o canonical:

```yaml
company:
  name: "TinyTask Lda."              # era "TinyTask SaaS"
  sector: "Technology/Software"      # era "technology"
  size: "micro"                      # era "small"
  employees: 8                       # era 50
  revenue_eur: 2000000               # era 5000000
  jurisdiction: "Portugal, EU"       # inalterado
  processes_personal_data: true
  places_digital_products_eu: true
  dora_financial_entity: false
  nis2_sector: ""
  aiact_high_risk_system: false
  technological_control_plane: "web application"
  data_types: [email, name, password, phone, address]
  tech_stack: [python, django, postgresql, aws, react]
  eu_data_subjects: 5000
```

Adicionar comment no topo do bloco `company:`:

```yaml
# CORR-036 (2026-07-21): aligned with input/company/classification.yaml
# (canonical source). Previous values (employees: 50, revenue: 5M,
# size: small) were a stale snapshot inconsistent with classification.yaml
# and with 01_Company_Context.md / 05_company_context.csv / the Case_01
# reference output in Methodology-main. TinyTask is a MICRO case by design
# (8 employees, EUR 2M revenue, security_fte 0.85).
```

Manter o resto do ficheiro (`regulations:` block e `subdomains:` block
se existirem) inalterado.

### T2 — Validar gates de auditoria do `preproc_out/`

Correr (todos têm de passar):

```bash
source ../shared-venv/bin/activate

# CSF mapping: BROKEN == 0 (OK/SPARSE aceitáveis)
python -m scripts.preprocess.audit_csf_mapping
# Expected: "audit done: 38 subdomains, 2 OK, 36 SPARSE, 0 BROKEN, 0 orphan hint IDs"

# SO↔SR coherence: sr_without_so.count == 0
python -m scripts.preprocess.audit_so_sr_coherence
# Expected: "SO without SR: 0 / SR without SO: 0 / Coverage: full=282"

# CI gates
bash .hooks/ci-csf-frozen-list.sh   # exit 0
bash .hooks/ci-frameworks.sh        # exit 0
```

Se algum falhar, **NÃO avançar** — reportar ao orchestrator. Os gates
já passavam pré-contract (verificado pelo orchestrator antes de escrever
este contract), pelo que qualquer regressão é introduzida por este
contract e deve ser investigada.

### T3 — Snapshot baseline dos outputs atuais

Correr o pipeline v2 em modo mock e guardar snapshot para diff futuro:

```bash
source ../shared-venv/bin/activate

# Snapshot dos outputs atuais (mock-llm — não há Ollama necessário)
MOCK_LLM=true python -m aegis_phase1.v2.runner --run-all cases/case1-tinytask 2>&1 | tee logs/phase1/baseline_corr036_run.log

# Guardar cópia
mkdir -p output/phase1/baseline_pre_corr036/
cp output/phase1/{04,04a,04b,04c,04d,05,06,07,07b}_*.md output/phase1/baseline_pre_corr036/ 2>/dev/null
cp output/phase1/Case_01_Phase1.xlsx output/phase1/baseline_pre_corr036/ 2>/dev/null
```

Se o runner falhar (e.g., dependência em falta, erro de import), registar
o erro em `logs/phase1/baseline_corr036_run.log` e prosseguir — o
propósito do snapshot é servir de comparação, não validar o pipeline
atual (sabe-se que está degradado; CORR-037+ corrige).

**Nota sobre `output/phase1/baseline_pre_corr036/`:** adicionar a
`.gitignore`? **NÃO.** Este snapshot deve ser committed como artefacto
de auditoria para futuros diffs. Se o orchestrator preferir, pode mover
para `execution/baselines/corr036/` — ver T5.

### T4 — Criar/atualizar `CONTRACT-036.md` (este ficheiro)

Self-explanatory — já está feito neste commit.

### T5 — (Opcional, decisão do executor) Mover snapshot para `execution/baselines/`

Se fizer mais sentido organizacional, mover o snapshot de
`output/phase1/baseline_pre_corr036/` para
`execution/baselines/corr036_pre_refactor/` para evitar poluir
`output/phase1/` que é regenerado a cada run. **Decisão left to
executor** — registar a escolha no commit message.

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `cases/case1-tinytask/context/phase1_ontology.yaml` | **MODIFY** — bloco `company:` alinhado com `classification.yaml` |
| `execution/CONTRACT-036.md` | **NEW** (este ficheiro) |
| `output/phase1/baseline_pre_corr036/*.md` (ou `execution/baselines/corr036_pre_refactor/`) | **NEW** — snapshot baseline |
| `logs/phase1/baseline_corr036_run.log` | **NEW** — log da run que produziu o snapshot |

**Não modificar:** qualquer ficheiro em `src/`, `tests/`, `preproc_out/`,
`scripts/`, `.hooks/`, `Methodology-main/`.

---

## Quality gates (FAIL default — todos têm de passar)

```bash
source ../shared-venv/bin/activate

# G1 — preproc_out audit gates (pristine)
python -m scripts.preprocess.audit_csf_mapping 2>&1 | grep -q "0 BROKEN" || { echo "FAIL G1a: BROKEN > 0"; exit 1; }
python -m scripts.preprocess.audit_so_sr_coherence 2>&1 | grep -qE "SO without SR: 0|sr_without_so.*count.*0" || { echo "FAIL G1b: SO without SR > 0"; exit 1; }

# G2 — CI gates
bash .hooks/ci-csf-frozen-list.sh || { echo "FAIL G2a: ci-csf-frozen-list"; exit 1; }
bash .hooks/ci-frameworks.sh || { echo "FAIL G2b: ci-frameworks"; exit 1; }

# G3 — phase1_ontology.yaml consistente com classification.yaml (custom check)
python3 - <<'PY'
import yaml
ont = yaml.safe_load(open("cases/case1-tinytask/context/phase1_ontology.yaml"))["company"]
cls = yaml.safe_load(open("cases/case1-tinytask/input/company/classification.yaml"))["company"]
for k in ("employees", "revenue_eur", "name", "sector"):
    # classification.yaml uses "revenue_eur" (no underscore variant) and "TinyTask Lda."
    # phase1_ontology.yaml uses "revenue_eur"; align both
    cv = cls.get(k) or cls.get(k.replace("_", ""))
    ov = ont.get(k) or ont.get(k.replace("_", ""))
    assert cv == ov, f"FAIL G3: {k} mismatch — classification={cv!r} ontology={ov!r}"
print("G3 OK: phase1_ontology.yaml aligned with classification.yaml")
PY

# G4 — pytest collection still clean (nothing should break from a YAML-only change)
pytest tests/unit/v2/ tests/unit/preprocess/ --co -q 2>&1 | grep -E "^(ERROR|ModuleNotFoundError|ImportError)" && { echo "FAIL G4: collection errors"; exit 1; } || echo "G4 OK: collection clean"

# G5 — snapshot baseline existe
ls output/phase1/baseline_pre_corr036/04_*.md execution/baselines/corr036_pre_refactor/04_*.md 2>/dev/null | head -1 || { echo "FAIL G5: baseline snapshot missing"; exit 1; }
echo "G5 OK: baseline snapshot exists"

echo "=== ALL GATES PASSED ==="
```

**Definição de done:** G1–G5 todos PASS + commit único neste branch.

---

## Estrutura de commits

```
feature/aegis-p1-corr-036
└─ commit único:
    CORR-036: align phase1_ontology.yaml with classification.yaml + baseline snapshot
    - cases/case1-tinytask/context/phase1_ontology.yaml (company block)
    - execution/CONTRACT-036.md (este)
    - output/phase1/baseline_pre_corr036/ (snapshot)
    - logs/phase1/baseline_corr036_run.log
```

**Convenção AGENTS.md §10:** 1 branch por contract, sem sub-branches,
commits sequenciais, sem amending.

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Alterar `phase1_ontology.yaml` quebra outro consumer que esperava 50/5M | Grep primeiro: `grep -rn "employees.*50\|revenue.*5000000" cases/ src/ tests/`. Se houver test que assume 50, é bug do teste (estava a testar contra dados stale). |
| Snapshot inclui dados de uma run degradada (pode confundir futuros diffs) | Documentar em `baseline_pre_corr036/README.md` que o snapshot é do estado PRÉ-refactor (CORR-036), outputs sabidamente degradados, serve só como baseline de regressão para CORR-037+ |
| `MOCK_LLM=true` falha porque o pipeline v2 já não corre | Registar erro e prosseguir; snapshot pode faltar mas não bloqueia o contract (G5 pode ser skipado com justificação) |
| Reformat do `phase1_ontology.yaml` muda whitespace e cria diff ruído | Usar `Edit` (string replacement) em vez de reescrever o ficheiro inteiro; preservar estrutura existente |

---

## Pre-flight check (antes de despachar Executor — já validado pelo orchestrator)

```bash
$ git branch --show-current
feature/aegis-p1-corr-035    # ← executor precisa de mudar para corr-036

$ python -m scripts.preprocess.audit_so_sr_coherence | tail -5
SO entries with inherits_from: 189/189 (100.0%)
SR linked_objectives resolved: 484/484 (100.0%)
SO without SR: 0
SR without SO: 0
Coverage: full=282, partial=0, unresolved=0

$ python -m scripts.preprocess.audit_csf_mapping | tail -1
audit done: 38 subdomains, 2 OK, 36 SPARSE, 0 BROKEN, 0 orphan hint IDs
```

Gates pré-contract passam. Baseline de auditoria é zero.

---

## Métricas esperadas

- **Linhas alteradas (código):** 0
- **Linhas alteradas (YAML):** ~10 (bloco `company:` em `phase1_ontology.yaml`)
- **Ficheiros novos:** 3 (CONTRACT-036.md, snapshot dir, log)
- **Commits:** 1
- **Impacto no pipeline:** nenhum (YAML-only change; o pipeline só vai
  consumir os valores novos em CORR-037+)

---

## Pós-CORR-036

Próximo contract: **CORR-037** (SP-A) — criar
`src/aegis_phase1/v2/loader/preproc_catalog.py` (PreprocCatalogLoader),
`src/aegis_phase1/v2/loader/case_profile.py` (CaseProfileLoader),
refactorizar `v2/orchestrator.py` `_load_*` para usar os novos loaders,
e remover `src/aegis_phase1/{graph.py, subphases/, nodes/}` (v1 legacy).

O Executor de CORR-037 deve começar por:

```bash
git checkout main
git checkout -b feature/aegis-p1-corr-037
# verificar que phase1_ontology.yaml está consistente (CORR-036 merged)
diff <(python3 -c "import yaml; print(yaml.safe_load(open('cases/case1-tinytask/context/phase1_ontology.yaml'))['company'])") \
     <(python3 -c "import yaml; print(yaml.safe_load(open('cases/case1-tinytask/input/company/classification.yaml'))['company'])")
# Expected: diff vazio em employees/revenue/name/sector
```

---

## Change log

- 2026-07-21: v1.0 — contract inicial criado pelo orchestrator após
  diagnóstico da estratégia faseada (CORR-036 → CORR-041) e aprovação
  do plan.
