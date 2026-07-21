# CORR-038 — SP-B: ApplicabilityContext + Doc 04 + Doc 05 (first verifiable output)

## Resumo

Terceiro contract da estratégia faseada **CORR-036 → CORR-041**
(reorientação do pipeline v2 para ler `preproc_out/` JSON diretamente,
sem regex, e alimentar os 5 LLMs canónicos com catálogos wired).

Este contract **produz o primeiro output verificável contra referência**.
Cria o `ApplicabilityContext` (fonte canónica de `applicable_regs` por
empresa) e refactoriza `Doc 04` (Company Context Assessment) +
`Doc 05` (Regulatory Applicability) para lerem do `ApplicabilityContext`
em vez de acederem directamente a state keys ad-hoc.

> **Realidade do contracto anterior (CORR-037):** a pipeline v2 agora
> carrega dados de `preproc_out/` JSON via `PreprocCatalogLoader` +
> `CaseProfileLoader` (T1/T2), e o `_v1_compat.py` shim popula v1 state
> keys (T4b/T4c). Mas **nenhum output real** (Doc 04..07) é gerado — o
> pipeline aborta no MAP stage. Este contracto arranca o **primeiro output
> end-to-end**: applicability → Doc 04 → Doc 05.

**Branch:** `feature/aegis-p1-corr-038`
**Data:** 2026-07-21
**Trigger:** SP-B da estratégia (ver `.zcode/plans/plan-sess_59e5ec8f-...md` §"SP-B").

**Dependência upstream:** CORR-037 merged a main. Branch baseado em main pós-CORR-037 (commit `3de5aa6`).

---

## Contexto (resumo da estratégia)

**O que existe (pós-CORR-037):**
- `PreprocCatalogLoader` (559 LOC) — typed Pydantic loader para `preproc_out/`
- `CaseProfileLoader` (376 LOC) — typed Pydantic loader para `cases/<case>/input/`
- Orchestrator com constructor injection de ambos
- `_v1_compat.py` shim — output consumers podem ler v1 shape de v2 sources
- 2084 tests passam, G5 fully PASS, 17/17 contract checks no pre-push

**O que falta para o primeiro output end-to-end:**
1. **ApplicabilityContext** — calcula `applicable_regs` por empresa (Filter 1)
   com cross-check vs `input/regulatory/applicability.yaml` → `declaration_gaps`
2. **Tier assignment** — LOW/MEDIUM/HIGH per PHASE1_STRATEGY §8 (depende de
   revenue + employees + applicable_regs)
3. **Doc 04 refactor** — renderiza a partir de `ApplicabilityContext`
   (em vez de v1 state keys ad-hoc)
4. **Doc 05 refactor** — tabela applicability com applicable, obligated_party,
   rationale, declaration_gap_flag
5. **`--run-applicability` CLI flag** — gera só Doc 04 + Doc 05 sem LLM calls

**Catálogos não são necessários aqui** (Filter 1 é determinístico — não usa
LLM). Wiring dos catálogos é CORR-039 (SP-C).

---

## Decisão de produto

**1. `ApplicabilityContext` é a fonte canónica de `applicable_regs`.**

Os 8 output consumers leem `applicable_regs` de:
- `state.get("regulations")` (v1, hoje shim-populated a partir de `v2_applicable_regs`)
- `company_context.applicable_regs` (v1 Pydantic `state.CompanyContext`)

Com T4c, isto é v1 shim-populated. Mas o **shim é frágil** (decisão hardcoded
de "GDPR + CRA applicable quando predicates dizem"). A metodologia prescreve
que o applicability é **computado** a partir de 5 booleans (PHASE1_STRATEGY
§Inputs MINIMAL):

```
processes_personal_data      → GDPR applicable
places_digital_products_eu   → CRA applicable
nis2_sector                  → NIS2 applicable (string vazia = not applicable)
dora_financial_entity        → DORA applicable
aiact_high_risk_system       → AI_Act applicable
```

T4c codificou isto como hardcoded rules em `_derive_predicates` do
`CaseProfileLoader`. **CORR-038 promove para `ApplicabilityContext`** —
uma classe dedicada com método explícito `_compute_applicable_regs(predicates)`
e o cross-check com `state['regulatory.applicability.yaml']`.

**2. DECLARATION_GAP é flageado, NÃO silenciado.**

PHASE1_STRATEGY §6: "When declared ≠ computed — flag (do NOT silently
override)". O `ApplicabilityContext` calcula `declaration_gaps` = diff
simétrico entre `declared_applicable_regs` (do YAML) e `applicable_regs`
(computado). Se diferente, **NÃO sobrescrever** — renderiza com flag
visual nos Docs 04/05.

**3. Tier (LOW/MEDIUM/HIGH) é derivado determinísticamente.**

PHASE1_STRATEGY §8 prescreve Tier por receita + número de employees +
número de applicable_regs. Estimativa heuristic para esta contract:
- MICRO (≤9 employees, ≤€2M) → LOW
- SMALL (≤49 employees, ≤€10M) → MEDIUM
- MEDIUM/LARGE → HIGH
Refinamento do tier é T4d (out of scope).

**4. Doc 04 e Doc 05 são **refactors**, não rewrites.**

A estratégia (`.zcode/plans/...`) diz "REFACTOR `v2/output/doc_04.py`
para renderizar de `CompanyContext`". Refactor = preservar a estrutura
de secções existente, mudar a fonte de dados. Diff semântico contra
referência deve ficar **dentro do threshold** (≤ N cells diferentes
em Doc 04; Doc 05 com `applicable_regs == [GDPR, CRA]` e roles
`[CONTROLLER, MANUFACTURER]` exact match).

---

## Tarefas

### T1 — NEW `src/aegis_phase1/v2/context/applicability_context.py` (~200 LOC)

**Responsabilidade:** calcular `applicable_regs` por empresa a partir de
`CompanyContext.applicability_predicates`, fazer cross-check com
`state['regulatory.applicable_regulations']` (do YAML declarado), e
produzir `DeclarationGap` por gap detectado.

**API pública:**

```python
from aegis_phase1.v2.context.applicability_context import (
    ApplicabilityContext,
    DeclarationGap,
    Tier,
    build_applicability_context,
)

# Build from a state (loads company_context + regulatory.applicability.yaml)
ctx: ApplicabilityContext = build_applicability_context(state)
# OR: build from explicit predicates (for tests)
ctx: ApplicabilityContext = ApplicabilityContext(
    applicable_regs=["GDPR", "CRA"],
    declared_applicable_regs=["GDPR", "CRA"],
    declaration_gaps=[],
    obligated_party_per_reg={
        "GDPR": "controller",
        "CRA": "manufacturer",
    },
    rationale_per_reg={
        "GDPR": "processes_personal_data = true",
        "CRA": "places_digital_products_eu = true",
    },
    clause_count_per_reg={"GDPR": 28, "CRA": 26},
    tier=Tier.LOW,
)

# Accessors
ctx.applicable_regs          # list[str] (sorted)
ctx.declared_applicable_regs  # list[str] (sorted, from YAML)
ctx.declaration_gaps          # list[DeclarationGap] (symmetric diff)
ctx.obligated_party_per_reg   # dict[str, str]
ctx.rationale_per_reg         # dict[str, str]
ctx.tier                      # Tier enum

# Render methods
ctx.to_dict() -> dict[str, Any]  # JSON-serializable for output docs
```

**Compute logic (matches PHASE1_STRATEGY §Inputs MINIMAL):**

```python
def _compute_applicable_regs(p: ApplicabilityPredicates) -> list[str]:
    out: list[str] = []
    if p.processes_personal_data:           out.append("GDPR")
    if p.places_digital_products_eu:        out.append("CRA")
    if p.nis2_sector and p.nis2_sector != "":  out.append("NIS2")
    if p.dora_financial_entity:             out.append("DORA")
    if p.aiact_high_risk_system:            out.append("AI_Act")
    return out
```

**Declaration gap detection:**

```python
@dataclass(frozen=True)
class DeclarationGap:
    regulation: str           # "GDPR" / "CRA" / etc.
    direction: str            # "computed_not_declared" | "declared_not_computed"
    computed: bool            # True if filter says applicable
    declared: bool            # True if YAML says applicable

def _compute_declaration_gaps(
    applicable: list[str], declared: list[str]
) -> list[DeclarationGap]:
    out: list[DeclarationGap] = []
    app_set, dec_set = set(applicable), set(declared)
    for reg in sorted(app_set | dec_set):
        out.append(DeclarationGap(
            regulation=reg,
            direction=("computed_not_declared" if reg in app_set and reg not in dec_set
                        else "declared_not_computed"),
            computed=reg in app_set,
            declared=reg in dec_set,
        ))
    return out
```

**Tier heuristic (PHASE1_STRATEGY §8 simplified):**

```python
class Tier(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

def _estimate_tier(facts: CompanyFacts, applicable_count: int) -> Tier:
    """LOW for MICRO+≤1 reg, MEDIUM for SMALL or 2-3 regs, HIGH otherwise."""
    if facts.scale == "MICRO" and applicable_count <= 1:
        return Tier.LOW
    if facts.scale in ("MICRO", "SMALL") and applicable_count <= 3:
        return Tier.MEDIUM
    return Tier.HIGH
```

### T2 — REFACTOR `src/aegis_phase1/v2/output/doc_04.py` (1068 → ~1000 LOC)

**Objectivo:** preservar estrutura de secções existente, mudar fonte de
dados de `state.get("company_context")` / `state.get("stakeholders")` para
`ApplicabilityContext`.

**Mudanças:**

1. Top of file: `from aegis_phase1.v2.context.applicability_context import build_applicability_context, ApplicabilityContext`
2. `render_doc_04(state, ...)`: no início, `ctx = build_applicability_context(state)`, depois passa `ctx` para todas as `_section_*` helpers em vez de `state`
3. Cada `_section_N_*` recebe `ctx` em vez de `state`:
   - `_section_1_purpose(ctx)` — usa `ctx.tier`, `ctx.applicable_regs`
   - `_section_2_summary(ctx)` — usa `ctx.company_facts` (name, scale, employees, revenue)
   - `_section_3_stakeholders(ctx.stakeholders)` — passa lista de stakeholders
   - `_section_4_business_goals(ctx.business_goals)` — passa lista de goals
   - `_section_5_intake_summary(ctx)` — usa `ctx.applicability_predicates` (5 booleans)
   - `_section_6_regulatory_flags(ctx)` — usa `ctx.applicable_regs` + `ctx.declaration_gaps`
   - `_section_7_architectural_implications(ctx)` — usa `ctx.architecture_inventory`
4. Adicionar secção 8 (nova) — **"Tier & Compliance Posture"** que sumariza
   `ctx.tier` + count de applicable_regs + gaps. Inspirada na reference.

**Não fazer:** mudança de wording/sections. O contract é "diff semântico ≤
threshold contra `Methodology-main/.../04_*.md`", não "re-escrita completa".

### T3 — REFACTOR `src/aegis_phase1/v2/output/doc_05.py` (974 → ~900 LOC)

**Objectivo:** tabela applicability com applicable, obligated_party,
rationale, declaration_gap_flag.

**Mudanças:**

1. `render_doc_05(state, ...)`: extrai `ctx = build_applicability_context(state)` no início
2. `_section_3_per_regulation(ctx)`: renderiza uma linha por regulação:
   - **GDPR** (em `ctx.applicable_regs`): APPLICABLE, role=CONTROLLER, rationale=ctx.rationale_per_reg['GDPR'], gap_flag=(NÃO)
   - **CRA**: APPLICABLE, role=MANUFACTURER, rationale=ctx.rationale_per_reg['CRA'], gap_flag=(NÃO)
   - **NIS2** (em `ctx.declared_applicable_regs` mas NÃO em `ctx.applicable_regs`): NOT APPLICABLE, gap_flag=SIM (declared_not_computed), rationale="Below employee threshold (8 < 50)"
   - **DORA**: NOT APPLICABLE, gap_flag=SIM, rationale="Not a financial entity"
   - **AI_Act**: NOT APPLICABLE, gap_flag=SIM, rationale="No high-risk AI system"
3. `_regulation_evidence_and_reasoning(ctx, reg)`: usa `ctx.obligated_party_per_reg[reg]` e `ctx.rationale_per_reg[reg]`
4. **DECLARATION_GAP visible**: linhas com gap_flag têm marker `⚠ DECLARATION GAP` no output (per PHASE1_STRATEGY §6)

**Expected output (per strategy doc):**
- `applicable_regs == [GDPR, CRA]`
- `roles == [CONTROLLER, MANUFACTURER]` (exact match)
- 3 declaration gaps (NIS2, DORA, AI_Act estão em declared como "non-applicable" mas estão em different scope — flagear para review)

### T4 — CLI: `--run-applicability` em `v2/runner.py`

**Objectivo:** gerar **só** Doc 04 + Doc 05 sem chamar LLMs (Filter 1 é determinístico).

**Adicionar flag:**

```python
parser.add_argument(
    "--run-applicability",
    action="store_true",
    help="Run only the applicability stage (SP-B): generate Doc 04 + Doc 05 "
         "from CaseProfile + ApplicabilityContext. No LLM calls. "
         "Equivalent to --deterministic-only filtered to docs 04 and 05.",
)
```

**Implementação:**

```python
# In main() after parse_args:
if args.run_applicability:
    # 1. Load (uses v2 loaders + T4b shim)
    state = orchestrator.load(case_path=args.case, regulatory_baseline_path="preproc_out")
    # 2. Build ApplicabilityContext
    from aegis_phase1.v2.context.applicability_context import build_applicability_context
    ctx = build_applicability_context(state)
    # 3. Render Doc 04 + Doc 05
    output_dir = Path(args.output or "output/phase1")
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_04_path = output_dir / f"04_Company_Context_Assessment.md"
    doc_05_path = output_dir / f"05_Regulatory_Applicability.md"
    doc_04_path.write_text(render_doc_04(ctx, output_dir=str(output_dir)))
    doc_05_path.write_text(render_doc_05(ctx, output_dir=str(output_dir)))
    logger.info("Applicability docs written: %s, %s", doc_04_path, doc_05_path)
    return orchestrator.state
```

**Nota:** o `runner.py` actual passa `state` (dict) a `render_doc_04`/`render_doc_05`. Após T2/T3, estas funções passam a receber `ctx` (ApplicabilityContext). O `runner.py` precisa de construir o `ctx` e passá-lo. **Breaking change** no signature público de `render_doc_04`/`render_doc_05`.

### T5 — TESTS `tests/unit/v2/test_applicability_parity.py` (~250 LOC)

```python
# Test ApplicabilityContext (8 tests)
def test_compute_applicable_regs_gdpr_cra_only()
def test_compute_applicable_regs_all_five_when_all_predicates_true()
def test_declaration_gap_detected_when_mismatch()
def test_declaration_gap_empty_when_match()
def test_tier_low_for_micro_with_few_regs()
def test_tier_high_for_large_with_many_regs()
def test_applicability_context_from_case1_state_matches_canonical()
def test_applicability_context_to_dict_is_json_serializable()

# Test Doc 04 refactor (4 tests)
def test_doc_04_renders_with_applicability_context()
def test_doc_04_contains_tier_section()
def test_doc_04_company_facts_match_canonical()
def test_doc_04_architecture_inventory_present()

# Test Doc 05 refactor (4 tests)
def test_doc_05_applicable_regs_exact_match_gdpr_cra()
def test_doc_05_obligated_party_controller_for_gdpr()
def test_doc_05_obligated_party_manufacturer_for_cra()
def test_doc_05_declaration_gaps_flagged_for_nis2_dora_aiact()

# Test CLI (2 tests)
def test_run_applicability_produces_doc_04_and_05()
def test_run_applicability_no_llm_calls()
```

Total: **18 tests novos**.

---

## Ficheiros

| Ficheiro | Acção | LOC esperados |
|----------|-------|---------------|
| `src/aegis_phase1/v2/context/applicability_context.py` | **NEW** | ~200 |
| `src/aegis_phase1/v2/output/doc_04.py` | **MODIFY** (refactor) | 1068 → ~1000 |
| `src/aegis_phase1/v2/output/doc_05.py` | **MODIFY** (refactor) | 974 → ~900 |
| `src/aegis_phase1/v2/runner.py` | **MODIFY** (add CLI flag) | +30 |
| `src/aegis_phase1/v2/context/__init__.py` | **NEW** | 5 |
| `tests/unit/v2/test_applicability_parity.py` | **NEW** | ~250 |
| `execution/CONTRACT-038.md` | **NEW** (este) | n/a |

**Não modificar:**
- `preproc_out/` (read-only per AGENTS.md §0)
- `cases/case1-tinytask/{context,input}/` (read-only)
- `Methodology-main/` (read-only, sister repo)
- `_v1_compat.py` (mantido como T4c; v2-only será em T4d)
- AGENTS.md (mudanças estruturais ficam para fim de sprint)

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G0 — Pre-flight
git branch --show-current   # feature/aegis-p1-corr-038
git status                  # working tree clean
python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('OK')"
python -c "from aegis_phase1.v2.context.applicability_context import build_applicability_context; print('OK')"
pytest tests/unit/v2/ tests/unit/preprocess/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError" | head -3
# Expected: empty

# G1 — preproc_out/ audits permanecem pristine
python -m scripts.preprocess.audit_csf_mapping | grep -q "0 BROKEN"
python -m scripts.preprocess.audit_so_sr_coherence | grep -qE "SO without SR: 0|sr_without_so.*count.*0"

# G2 — CI gates
bash .hooks/ci-csf-frozen-list.sh   # exit 0
bash .hooks/ci-frameworks.sh        # exit 0

# G3 — ApplicabilityContext sanity
python -c "
from aegis_phase1.v2.context.applicability_context import build_applicability_context
from aegis_phase1.v2.orchestrator import Phase1Orchestrator
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from pathlib import Path
import tempfile, json
with tempfile.TemporaryDirectory() as d:
    o = Phase1Orchestrator(work_dir=d, case_profile_loader=CaseProfileLoader(Path('cases/case1-tinytask')))
    o._load_v2_catalog('cases/case1-tinytask')
    ctx = build_applicability_context(o.state)
    assert ctx.applicable_regs == ['CRA', 'GDPR'], f'got {ctx.applicable_regs}'
    assert ctx.tier.value == 'LOW', f'got {ctx.tier}'
    assert ctx.obligated_party_per_reg == {'GDPR': 'controller', 'CRA': 'manufacturer'}, f'got {ctx.obligated_party_per_reg}'
print('G3 OK: case1 applicability matches canonical')
"

# G4 — Doc 04 semantic parity (subset of canonical fields)
python -c "
from aegis_phase1.v2.context.applicability_context import build_applicability_context
from aegis_phase1.v2.orchestrator import Phase1Orchestrator
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.output.doc_04 import render_doc_04
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as d:
    o = Phase1Orchestrator(work_dir=d, case_profile_loader=CaseProfileLoader(Path('cases/case1-tinytask')))
    o._load_v2_catalog('cases/case1-tinytask')
    ctx = build_applicability_context(o.state)
    body = render_doc_04(ctx, output_dir=d)
    # Semantic assertions
    assert 'TinyTask Lda.' in body, 'company name missing'
    assert '8' in body, 'employees count missing'
    assert 'Technology' in body or 'Software' in body, 'sector missing'
    assert 'Portugal' in body, 'jurisdiction missing'
    assert 'LOW' in body or 'MEDIUM' in body or 'HIGH' in body, 'tier section missing'
    assert 'GDPR' in body and 'CRA' in body, 'applicable regs missing'
print('G4 OK: Doc 04 contains canonical facts')
"

# G5 — Doc 05 semantic parity
python -c "
from aegis_phase1.v2.context.applicability_context import build_applicability_context
from aegis_phase1.v2.orchestrator import Phase1Orchestrator
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.output.doc_05 import render_doc_05
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as d:
    o = Phase1Orchestrator(work_dir=d, case_profile_loader=CaseProfileLoader(Path('cases/case1-tinytask')))
    o._load_v2_catalog('cases/case1-tinytask')
    ctx = build_applicability_context(o.state)
    body = render_doc_05(ctx, output_dir=d)
    assert 'GDPR' in body and 'CRA' in body, 'GDPR + CRA not in body'
    assert 'CONTROLLER' in body, 'GDPR role CONTROLLER missing'
    assert 'MANUFACTURER' in body, 'CRA role MANUFACTURER missing'
    assert 'NIS2' in body, 'NIS2 row missing'
    assert 'DORA' in body, 'DORA row missing'
    assert 'AI Act' in body or 'AI_Act' in body, 'AI Act row missing'
    # Declaration gaps
    assert 'DECLARATION GAP' in body or 'gap' in body.lower(), 'no gap marker'
print('G5 OK: Doc 05 contains 5 regs + roles + gaps')
"

# G6 — CLI flag functional
MOCK_LLM=true python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-applicability --output /tmp/corr038_test 2>&1 | tail -3
test -f /tmp/corr038_test/04_Company_Context_Assessment.md
test -f /tmp/corr038_test/05_Regulatory_Applicability.md
# Expected: 0 LLM calls (verify by checking logs/phase1/v2/llm-calls.jsonl size == 0)
echo "G6 OK: --run-applicability produced both docs without LLM"

# G7 — Tests
pytest tests/unit/v2/test_applicability_parity.py -v
# Expected: 18 passed

# G8 — All tests still green (no regressions)
pytest tests/unit/v2/ tests/unit/preprocess/
# Expected: 2084 + 18 = 2102 passed

# G9 — G5 contract gate (v1 deprecation still holds)
bash .hooks/ci-csf-frozen-list.sh   # exit 0
bash .hooks/ci-frameworks.sh        # exit 0
grep -rE "from aegis_phase1\.nodes|from aegis_phase1\.subphases|from aegis_phase1\.graph import" src/ tests/ 2>&1 | grep -v __pycache__ | head -3
# Expected: empty

echo "=== ALL GATES PASSED ==="
```

**Definição de done:** G0–G9 todos PASS + commits sequenciais no branch (sem amend, sem rebase) + pre-push hook valida 17/17 contract checks.

---

## Estrutura de commits

```
feature/aegis-p1-corr-038
├─ commit 1: CORR-038-T1: NEW applicability_context.py (ApplicabilityContext + Pydantic + compute)
├─ commit 2: CORR-038-T2: REFACTOR doc_04.py to read from ApplicabilityContext
├─ commit 3: CORR-038-T3: REFACTOR doc_05.py (applicability table + gap flags)
├─ commit 4: CORR-038-T4: add --run-applicability CLI flag in runner.py
├─ commit 5: CORR-038-T5: NEW test_applicability_parity.py (18 tests)
├─ commit 6: CORR-038: parity snapshot + handoff doc
```

Cada commit deve deixar o branch num estado coerente. Se um commit
intermédio quebrar tests, é aceitável desde que o commit final deixe
tudo PASS.

**Convenção AGENTS.md §10:** 1 branch per contract, sem sub-branches,
commits sequenciais, sem amending, sem rebase interativo.

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Doc 04/05 refactor introduz regressão visual vs reference | Gates G4/G5 com semantic assertions (key fields must appear). Diff completo contra `Methodology-main/.../04_*.md` é verificação manual do owner. |
| Breaking change em `render_doc_04`/`render_doc_05` (agora recebem `ctx` em vez de `state`) | Update todos os call sites (apenas `runner.py` no v2). Tests de consumidores (test_doc_04b.py etc.) passam mock data, não precisam de update. |
| `build_applicability_context` precisa de company_context Pydantic v1 (state.CompanyContext) com `applicable_regs` field | Em T4c, state.CompanyContext é shim-populated a partir de v2_company_facts. Garantir que a shim popula `applicable_regs` (já faz, ver T4b tests). |
| Declaration gaps para TinyTask (NIS2/DORA/AI_Act estão em declared como "non_applicable" mas o YAML diz "non_applicable_regulations" como list) | O input YAML em `cases/case1-tinytask/input/regulatory/applicability.yaml` tem `applicable_regulations: [GDPR, CRA]` e `non_applicable_regulations: [NIS2, DORA, AI_Act]`. T1 usa `applicable_regulations` (declared) e T1's compute usa predicates. Match. |
| Tier heuristic é approximation | Documentar como "v1 heuristic" no docstring. Refinamento (Tier by revenue brackets + complexity) é T4d. |
| Doc 05 refactor muda estrutura de secções | Preservar secções 1-6 da versão actual; apenas mudar fonte de dados. Diff semântico limitado a keywords + table content. |
| LLM-related regressions (Doc 04/05 ainda não usam LLM mas mudanças podem quebrar imports) | Run pytest tests/unit/v2/ completo a cada commit. Pre-push hook valida 17/17. |

---

## Pre-flight check (OBRIGATÓRIO antes de cada T1-T5)

Per AGENTS.md §10.1:

```bash
$ git branch --show-current
feature/aegis-p1-corr-038

$ git status
nothing to commit, working tree clean

$ python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('OK')"
OK

$ python -c "from aegis_phase1.v2.context.applicability_context import build_applicability_context; print('OK')"
OK   (após T1)

$ pytest tests/unit/v2/ tests/unit/preprocess/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError" | head -3
# Expected: empty
```

Se algum check falhar, abortar a sub-tarefa, fixar, retomar.

---

## Métricas esperadas

- **Linhas adicionadas (código):** ~600 (T1: 200 + T2: -68 + T3: -74 + T4: +30 + T5: 250)
- **Linhas removidas (código):** ~250 (T2 + T3 — refactor remove v1 state key access boilerplate)
- **Net LOC:** +350 (T1 + T5 dominam; T2/T3 são refactor sem grandes deltas)
- **Ficheiros novos:** 3 (applicability_context.py, context/__init__.py, test_applicability_parity.py)
- **Ficheiros modificados:** 3 (doc_04.py, doc_05.py, runner.py)
- **Commits:** 5-6
- **Tests novos:** 18 (8 context + 4 Doc 04 + 4 Doc 05 + 2 CLI)
- **Tests totais esperados:** 2084 + 18 = **2102**
- **Duração estimada:** 3-5h (single session, manageable)

---

## Pós-CORR-038

Próximos contracts (sequência da estratégia):

| SP | Contract | Foco |
|----|----------|------|
| C | **CORR-039** (`feature/aegis-p1-corr-039`) | ClauseMappingContext + Doc 06 + FIX `catalog_loader=None` + 4 P1B-LLM-01/02 calls com catálogos wired. Primeiro contract que **invoca LLM**. |
| D | **CORR-040** (`feature/aegis-p1-corr-040`) | DomainActivationContext + P1C-LLM-01 (overlap classification) + Doc 07 matrix (38×5) + Track B proportionality. |
| E | **CORR-041** (`feature/aegis-p1-corr-041`) | SynthesisContext + P1C-LLM-03 (strategic synthesis) + P1C-LLM-02 (compound events) + Doc 04a-d + parity check 9 outputs. |

**Critério de sucesso global** (pós CORR-041):
`python -m aegis_phase1.v2.runner --run-all cases/case1-tinytask` produz
9 outputs (04/04a/04b/04c/04d/05/06/07/07b + xlsx) com diff semântico ≤
threshold contra `Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`.

**Estado pós-CORR-038:**
- Doc 04/05 funcionais (filter 1 determinístico)
- AplicabilityContext canónico (fonte única de applicable_regs)
- CLI `--run-applicability` para gerar só Doc 04+05 (sem LLM)
- Tier LOW/MEDIUM/HIGH derivado de CompanyFacts
- 2102 tests passam
- Próximo: CORR-039 (LLM-driven clause mapping + catalog wiring)

---

## Change log

- 2026-07-21: v1.0 — contract inicial criado pelo orchestrator após
  merge de CORR-037 (`3de5aa6`) a main. Branch
  `feature/aegis-p1-corr-038` baseada em main pós-CORR-037. Contrato
  define T1-T5 com API pública, gate criteria, estrutura de commits,
  e risks. Implementação começa em sessão seguinte.
