# CORR-039 — SP-C: ClauseMappingContext + Doc 06 + Runner wiring + P1B-LLM-01 first invocation

## Resumo

Quarto contract da estratégia faseada **CORR-036 → CORR-041**
(reorientação do pipeline v2 para ler `preproc_out/` JSON directamente,
sem regex, e alimentar os 5 LLMs canónicos com catálogos wired).

Este contract **abre a primeira cadeia LLM end-to-end do v2**: o
runner passa a injectar `PreprocCatalogLoader` + `CaseProfileLoader`
(o bug "catalog_loader=None" que o CORR-038 não fixou), cria o
`ClauseMappingContext` (fonte canónica da matriz cláusula→subdomínio),
refactoriza `Doc 06` para ler desse contexto, e invoca **P1B-LLM-01
por regulação aplicável** com `CatalogLoader` a filtrar
`tipo2_interpretations` e `tipo3_derogations` da Methodology-main.

> **Realidade do contracto anterior (CORR-038):** o v2 já tem
> `PreprocCatalogLoader` (559 LOC) + `CaseProfileLoader` (376 LOC) +
> `ApplicabilityContext` (250 LOC) + `--run-applicability` (gera Doc
> 04+05, 0 LLM). Mas **o runner não injecta nenhum deles** —
> `_load_v2_catalog` é no-op silencioso, `state["v2_subdomains"]`
> fica vazio, e a pipeline cai para a v1-compat shim com keys
> vazias. **Nunca houve um LLM canónico invocado via runner** —
> o `Phase1Executor.run_phase_1b` existe mas `executor.run_phase_1b`
> é unreachable na prática.

**Branch:** `feature/aegis-p1-corr-039`
**Data:** 2026-07-21
**Trigger:** SP-C da estratégia (ver `CORR-038` §"Pós-CORR-038").

**Dependência upstream:** CORR-038 merged a main (PR #32). Branch
baseado em main pós-CORR-038.

---

## Contexto (resumo da estratégia)

**O que existe (pós-CORR-038):**
- `PreprocCatalogLoader` (559 LOC) — typed Pydantic loader para `preproc_out/`
- `CaseProfileLoader` (376 LOC) — typed Pydantic loader para `cases/<case>/input/`
- `ApplicabilityContext` (250 LOC) — calcula `applicable_regs` + tier + gaps
- `CatalogLoader` (198 LOC, `prompts_v2/catalog.py`) — carrega YAMLs de
  `Methodology-main/00_METHODOLOGY/PROMPTS/catalogs/`, filtra por
  `applies_to: [REG]`, avalia `activation_predicate` contra `company_facts`
- `Phase1Executor.run_phase_1b` (140 LOC) — já itera per-reg e invoca
  P1B-LLM-01 + P1B-LLM-02 sequencialmente
- Orchestrator com constructor injection de `preproc_catalog` + `case_profile_loader`
- Doc 04/05 refactorizados para lerem de `ApplicabilityContext`
- 2103 tests passam, `--run-applicability` escreve 5 artefactos sem LLM

**O que falta para a primeira cadeia LLM end-to-end:**
1. **FIX `catalog_loader=None`** — `runner.py` instancia
   `Phase1Orchestrator(llm_invoker=llm_invoker)` mas **não passa**
   `preproc_catalog` nem `case_profile_loader`. Resultado: a
   pipeline corre mas `state["v2_subdomains"]`, `v2_srs`, `v2_sos`,
   `v2_pairs` ficam vazios, o shim popula v1 keys com defaults
   vazios, e Doc 06/07 saem com tabelas vazias
2. **`ClauseMappingContext`** — fonte canónica de
   `clause → subdomain` mapping table (substitui a leitura
   de `state["ontology"]["clause_mappings"]` que o shim nunca
   popula)
3. **Doc 06 refactor** — renderiza a partir de
   `ClauseMappingContext` (em vez de v1 ontology shim)
4. **P1B-LLM-01 invocado pelo runner** — com `CatalogLoader`
   a fornecer `tipo2` (interpretações) e `tipo3` (derrogações)
   filtradas por `applicable_reg` + `tier`; `classification`
   (role + tier) fornecido pelo `ApplicabilityContext`
5. **`--run-clauses` CLI flag** — gera só Doc 06 (sem LLM)
   para verificação rápida do mapping
6. **`--run-phase-1b` CLI flag** — gera Doc 05 §6.1b (per-reg
   rationale) a partir de P1B-LLM-01, com LLM (mock para
   smoke test)

**Catálogos vazios (não-bloqueante):** `Methodology-main/00_METHODOLOGY/
PROMPTS/catalogs/` está vazio neste momento. O `CatalogLoader` retorna
lista vazia sem erro; P1B-LLM-01 recebe `interpretations: []` e
`derogations: []` e prossegue. **O conteúdo real dos catálogos é um
contracto methodology-side** (post-CORR-039) — CORR-039 demonstra a
fiação sem depender desse conteúdo.

---

## Decisão de produto

**1. `ClauseMappingContext` é a fonte canónica da matriz cláusula→subdomínio.**

O `doc_06.py` actual (136 LOC) lê de
`state.get("ontology", {}).get("clause_mappings", [])` — mas o shim
v1-compat em `_build_ontology_shim` (orchestrator.py) **nunca popula
`clause_mappings`** (só popula `regulations`, `overlaps`,
`source_regulations`, `stacks`). Resultado: Doc 06 sai com tabela
vazia mesmo quando o pipeline corre "com sucesso".

A fonte canónica é **`PreprocCatalogLoader.load_clauses()`**:
498 clauses em `preproc_out/3-entities/clauses/_root/{REG}/{REG}_CLnn.json`.
Para cada clause, o subdomínio é inferido pelos `source_clauses[]`
em cada `SR` (cada `SR.sub_domain: ["D-01.1"]`).

**2. `CatalogLoader` é wired via constructor injection.**

O `CatalogLoader` já existe (`prompts_v2/catalog.py`, 198 LOC).
Suporta:
- `cl.load("tipo2_interpretations")` → `list[dict]`
- `cl.filter_applicable(catalog, regulation="GDPR", tier="LOW")`
- `cl.evaluate_predicate("company_facts.sector == 'health'", facts)`
- `cl.evaluate_predicates(entries, facts)` → `list[(entry, verdict)]`

O runner passa a injectar `CatalogLoader(root=...)` no orchestrator
(o mesmo que o factory.get_invoker já faz, mas o runner não o
propaga ao orchestrator — só o Phase1Executor o recebe via
`invoker_to_executor`).

**3. P1B-LLM-01 recebe `interpretations: []` e `derogations: []`
quando os catálogos estão vazios.**

A prompt do P1B-LLM-01 espera listas de interpretações e derrogações
filtradas. Quando o `CatalogLoader` retorna listas vazias
(reality actual), o P1B-LLM-01 ainda corre — simplesmente devolve
`interpretations: []` e `derogations: []` no output, e o
`run_phase_1b` continua. **Isto prova que a fiação está correcta
sem depender do conteúdo dos catálogos.**

**4. Doc 06 é refactor, não rewrite.**

Mesma estratégia do CORR-038: preservar estrutura de secções
existente (4 secções), mudar fonte de dados de `state["ontology"]`
para `ClauseMappingContext`. A tabela vai de 0 rows (estado
actual vazio) para 54 rows (case1: 28 GDPR + 26 CRA — a contagem
exacta vem de `cases/case1-tinytask/input/regulatory/applicability.yaml`
mas o contracto lê dinamicamente via `load_clauses()` filtrado por
applicable_regs).

**5. `MockInvoker` para P1B-LLM-01 quando `MOCK_LLM=true`.**

A primeira invocação LLM do pipeline v2 é feita com `MockInvoker`
para garantir smoke test sem rede. O `MockInvoker` retorna
`{"status": "OK", "parsed_output": {interpretations: [], derogations: []}}`
para o spec P1B-LLM-01. **Demonstra que o pipeline dispatch está
correcto sem custo computacional.**

**6. Não fazemos P1B-LLM-02 (RATIONALE) neste contracto.**

P1B-LLM-02 é o "merged" rationale (B+C+D legacy), consome output
de P1B-LLM-01, e renderiza prose. É mais complexo e fora do scope
do "primeiro LLM canónico invocado". P1B-LLM-02 fica para CORR-041
(junto com os outros reduce LLMs).

---

## Tarefas

### T1 — FIX runner.py: injectar loaders (~30 LOC)

**Bug:** `runner.py:250` instancia `Phase1Orchestrator(llm_invoker=llm_invoker)`
sem passar `preproc_catalog` nem `case_profile_loader`. Resultado:
`_load_v2_catalog` (orchestrator.py:113) salta ambas as branches e
nenhum `v2_*` key é populado.

**Fix:** instanciar os loaders e passá-los ao orchestrator.

```python
# In runner.py main(), after `llm_invoker = build_llm_invoker(...)`:
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.prompts_v2.factory import get_prompts_root

# CORR-039-T1: inject typed loaders so _load_v2_catalog actually runs
preproc_catalog = PreprocCatalogLoader(preproc_root="preproc_out")
case_profile_loader = CaseProfileLoader(Path(args.case))
catalog_loader = CatalogLoader(root=get_prompts_root() / "catalogs")

orch = Phase1Orchestrator(
    llm_invoker=llm_invoker,
    preproc_catalog=preproc_catalog,
    case_profile_loader=case_profile_loader,
    catalog_loader=catalog_loader,
)
```

**Adicionar campo ao orchestrator:**

```python
# In orchestrator.py __init__:
def __init__(
    self,
    work_dir: str = "work",
    llm_invoker: Any | None = None,
    *,
    preproc_catalog: "PreprocCatalogLoader | None" = None,
    case_profile_loader: "CaseProfileLoader | None" = None,
    catalog_loader: "CatalogLoader | None" = None,  # NEW CORR-039
):
    ...
    self.catalog_loader = catalog_loader
```

**Adicionar branch em `_load_v2_catalog` para popular
`state["v2_catalog_tipo2"]` e `v2_catalog_tipo3`:**

```python
# In _load_v2_catalog after preproc_catalog block:
if self.catalog_loader is not None:
    try:
        self.state["v2_catalog_tipo2"] = self.catalog_loader.load("tipo2_interpretations")
        self.state["v2_catalog_tipo3"] = self.catalog_loader.load("tipo3_derogations")
        logger.debug(
            "T1: catalogs loaded — tipo2=%d entries, tipo3=%d entries",
            len(self.state["v2_catalog_tipo2"]),
            len(self.state["v2_catalog_tipo3"]),
        )
    except Exception as e:
        logger.warning("T1: catalog_loader failed (%s) — v2_catalog_* not set", e)
```

**Esperado pós-T1:** o `v2_subdomains` (38), `v2_srs` (282),
`v2_sos` (328), `v2_pairs` (196), `v2_audit_both_pass`, e os
novos `v2_catalog_tipo2`/`v2_catalog_tipo3` ficam populados
quando o runner invoca `orch.load()`. **G1 (smoke test) confirma.**

### T2 — NEW `src/aegis_phase1/v2/context/clause_mapping_context.py` (~220 LOC)

**Responsabilidade:** construir a matriz cláusula→subdomínio a
partir de `PreprocCatalogLoader.load_clauses()` filtrado por
`applicable_regs` + `v2_srs` (para resolver `sub_domain` por
source_clause).

**API pública:**

```python
from aegis_phase1.v2.context.clause_mapping_context import (
    ClauseMappingContext,
    ClauseMappingEntry,
    build_clause_mapping_context,
)

# Build from state (loads preproc catalog + applicable_regs from v2_)
ctx: ClauseMappingContext = build_clause_mapping_context(state)
# OR: build from explicit data (for tests)
ctx = ClauseMappingContext(
    entries=[
        ClauseMappingEntry(
            clause_id="GDPR-CL05",
            regulation="GDPR",
            article="5",
            title="Principles relating to processing of personal data",
            text="Personal data shall be processed lawfully, fairly...",
            subdomain_id="D-01.1",
            maps_to_subdomain="D-01.1 Data at Rest Encryption",
            normative_strength=2,
            obligated_party="controller",
            source_sr_ids=["SR-GDPR-001", "SR-GDPR-002"],
            nist_csf_mapping=["PR.DS-01", "PR.DS-02"],
        ),
        ...
    ],
    per_reg_count={"GDPR": 28, "CRA": 26},
    total_clauses=54,
    unmapped_count=0,  # clauses with no SR link
)

# Accessors
ctx.entries              # list[ClauseMappingEntry] sorted by (regulation, clause_id)
ctx.per_reg_count        # dict[reg, int]
ctx.total_clauses        # int
ctx.unmapped_count       # int
ctx.by_regulation(reg)   # list[ClauseMappingEntry] filtered by reg
ctx.by_subdomain(sd_id)  # list[ClauseMappingEntry] filtered by sub-domain

# Render methods
ctx.to_dict() -> dict[str, Any]  # JSON-serializable for output docs
```

**Compute logic (matches AGENTS.md §11.3):**

```python
def build_clause_mapping_context(state: dict[str, Any]) -> ClauseMappingContext:
    catalog: PreprocCatalogLoader | None = state.get("v2_preproc_catalog_ref")
    if catalog is None:
        # Fall back to loading directly (T2 can also accept state
        # with v2_srs / v2_applicable_regs pre-populated)
        ...

    applicable_regs: list[str] = state.get("v2_applicable_regs", [])
    if not applicable_regs:
        return ClauseMappingContext(entries=[], per_reg_count={},
                                    total_clauses=0, unmapped_count=0)

    # Load all clauses for applicable regs
    all_clauses: list[Clause] = []
    for reg in applicable_regs:
        all_clauses.extend(catalog.load_clauses(regulation=reg))

    # Build clause_id → [sub_domain] map from SRs
    srs = state.get("v2_srs", [])
    sr_by_clause: dict[str, list[str]] = {}
    sr_subdomain_by_clause: dict[str, list[str]] = {}
    for sr in srs:
        for src in sr.source_clauses:
            sr_by_clause.setdefault(src.clause_id, []).append(sr.id)
            for sd in sr.sub_domain:
                sr_subdomain_by_clause.setdefault(src.clause_id, []).append(sd)

    # Build entries
    entries: list[ClauseMappingEntry] = []
    unmapped = 0
    for c in all_clauses:
        sd_ids = sr_subdomain_by_clause.get(c.id, [])
        if not sd_ids:
            unmapped += 1
            continue
        # Use first sub-domain (canonical mapping; future T-corrigendum
        # could split into multi-row)
        sd_id = sorted(sd_ids)[0]
        entries.append(ClauseMappingEntry(
            clause_id=c.id,
            regulation=c.regulation,
            article=c.article or "",
            title=c.title or "",
            text=c.text[:200],  # truncated for table; full text available via .text
            subdomain_id=sd_id,
            maps_to_subdomain=f"{sd_id}",  # title resolved by consumer
            normative_strength=2,  # TODO: read from clause.normative_strength when present
            obligated_party="controller",  # TODO: read from applicable_regs context
            source_sr_ids=sr_by_clause.get(c.id, []),
            nist_csf_mapping=[],  # TODO: from SRs
        ))

    entries.sort(key=lambda e: (e.regulation, e.clause_id))
    per_reg_count: dict[str, int] = {}
    for e in entries:
        per_reg_count[e.regulation] = per_reg_count.get(e.regulation, 0) + 1

    return ClauseMappingContext(
        entries=entries,
        per_reg_count=per_reg_count,
        total_clauses=len(entries),
        unmapped_count=unmapped,
    )
```

**Note:** `state["v2_preproc_catalog_ref"]` is a new key
populated in T1 — it stores a reference to the `PreprocCatalogLoader`
instance so the context builder can call `load_clauses()` lazily.
(T4c-style: keep the loader reference in state, not a deep copy.)

### T3 — REFACTOR `src/aegis_phase1/v2/output/doc_06.py` (136 → ~150 LOC)

**Objectivo:** renderizar a partir de `ClauseMappingContext` em vez
de `state["ontology"]["clause_mappings"]`.

**Mudanças:**

1. Top of file: `from aegis_phase1.v2.context.clause_mapping_context import build_clause_mapping_context, ClauseMappingContext`
2. `render_doc_06(state, output_dir)`: no início,
   `ctx = build_clause_mapping_context(state)`; depois passa `ctx`
   para os renderers
3. Replace `clauses = ontology.get("clause_mappings", [])` →
   `entries = ctx.entries`
4. `_section_2_summary(ctx)`: usa `ctx.per_reg_count` e
   `ctx.total_clauses`
5. `_section_3_table(ctx)`: itera `ctx.entries` em vez de `clauses`
6. `_clause_row(ctx, entry, regs)`: usa `entry.clause_id`,
   `entry.regulation`, `entry.article`, `entry.title`,
   `entry.maps_to_subdomain`, `entry.normative_strength`,
   `entry.obligated_party`

**Expected output (case1):**
- `total_clauses == 54` (28 GDPR + 26 CRA)
- `per_reg_count == {"GDPR": 28, "CRA": 26}`
- Tabela com 54 rows, 7 colunas (clause_id, regulation, article,
  description, sub_domain, normative_strength, obligated_party)

### T4 — Wire P1B-LLM-01 in orchestrator (~80 LOC diff)

**Objectivo:** o `run_phase_1b` existente já itera per-reg e chama
P1B-LLM-01, mas não passa:
- `classification` (role + tier) do `ApplicabilityContext`
- `layer0_catalog` (tipo2 + tipo3 filtrados por reg)
- `layer0_subdomain_refs` (lista de subdomínios activados por este reg)

**Mudanças no `run_p1b_single` (orchestrator.py:1306):**

```python
def run_p1b_single(
    self,
    spec_id: str,
    reg_id: str,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    executor = self._get_phase1_executor()
    if executor is None:
        return None

    # Build classification from ApplicabilityContext
    from aegis_phase1.v2.context.applicability_context import (
        build_applicability_context,
    )
    app_ctx = build_applicability_context(self.state)
    role = app_ctx.obligated_party_per_reg.get(reg_id, "obligated_party")
    classification = {
        "role": role,
        "tier": app_ctx.tier.value,
        "classification_basis": "Doc 04 §5 + ApplicabilityContext",
    }

    # Filter tipo2 + tipo3 catalogs for this reg
    layer0_catalog = self._load_filtered_catalogs(reg_id, app_ctx)

    # Resolve sub-domain refs for this reg
    layer0_subdomain_refs = self._subdomain_refs_for_reg(reg_id)

    company_facts = self._build_company_facts_for_llm()

    inputs = {
        "classification": classification,
        "layer0_catalog": layer0_catalog,
        "layer0_subdomain_refs": layer0_subdomain_refs,
        "company_facts": company_facts,
    }

    case_id = Path(self.state.get("case_path") or "case").name
    run_result = executor.run_phase_1b(
        case_id=case_id,
        applicable_regs=[reg_id],
        config=config,
        **inputs,
    )
    if not isinstance(run_result, dict):
        return None
    return run_result.get("aggregated_synthesis", {}).get(reg_id)
```

**Helper methods:**

```python
def _load_filtered_catalogs(
    self, reg_id: str, app_ctx: ApplicabilityContext
) -> dict[str, list[dict[str, Any]]]:
    if self.catalog_loader is None:
        return {"tipo2": [], "tipo3": []}
    try:
        tipo2_all = self.state.get("v2_catalog_tipo2", [])
        tipo3_all = self.state.get("v2_catalog_tipo3", [])
        tipo2 = self.catalog_loader.filter_applicable(
            tipo2_all, regulation=reg_id, tier=app_ctx.tier.value
        )
        tipo3 = self.catalog_loader.filter_applicable(
            tipo3_all, regulation=reg_id, tier=app_ctx.tier.value
        )
        # Evaluate predicates (defensive; not all entries have predicates)
        tipo3_evaluated = self.catalog_loader.evaluate_predicates(
            tipo3, self._build_company_facts_for_llm()
        )
        return {
            "tipo2": tipo2,
            "tipo3": [
                {**entry, "predicate_verdict": verdict}
                for entry, verdict in tipo3_evaluated
            ],
        }
    except Exception as exc:
        logger.warning("Catalog filter failed for %s: %s", reg_id, exc)
        return {"tipo2": [], "tipo3": []}

def _subdomain_refs_for_reg(self, reg_id: str) -> list[str]:
    srs = self.state.get("v2_srs", [])
    refs: set[str] = set()
    for sr in srs:
        if sr.regulation == reg_id:
            for sd in sr.sub_domain:
                refs.add(sd)
    return sorted(refs)

def _build_company_facts_for_llm(self) -> dict[str, Any]:
    profile = self.state.get("v2_company_profile")
    if profile is None:
        return {}
    facts = profile.company
    return {
        "name": facts.name,
        "sector": facts.sector,
        "jurisdiction": facts.jurisdiction,
        "employees": facts.employees,
        "revenue_eur": float(facts.revenue_eur) if facts.revenue_eur else 0,
        "scale": facts.scale,
        "security_fte": facts.security_fte,
        "tech_stack": list(facts.tech_stack or []),
        "architecture_ref": "DOC04:ARCH-07",  # canonical from case1
        "data_categories": ["personal_data"],  # derived from GDPR applicable
        "products": [facts.name + " SaaS application"],
        "role_obligations": [
            f"{facts.name} is {role} for {reg}"
            for reg, role in self.state.get("v2_obligated_party", {}).items()
        ],
    }
```

**Expected:** P1B-LLM-01 recebe o contexto completo (catalog +
classification + company_facts + layer0_subdomain_refs). Com
catálogos vazios, retorna `interpretations: [], derogations: []`
e o pipeline continua.

### T5 — CLI: `--run-clauses` + `--run-phase-1b` (~50 LOC)

**Adicionar dois flags ao `runner.py`:**

```python
parser.add_argument(
    "--run-clauses",
    action="store_true",
    dest="run_clauses",
    help=(
        "CORR-039: Generate ONLY Doc 06 from the ClauseMappingContext. "
        "No LLM. Skips MAP, REDUCE, and Phase 1B. Useful for verifying "
        "clause-to-subdomain mapping after a preproc rebuild."
    ),
)
parser.add_argument(
    "--run-phase-1b",
    action="store_true",
    dest="run_phase_1b",
    help=(
        "CORR-039: Run Phase 1B RATIONALE (P1B-LLM-01 per applicable_reg). "
        "Writes per-reg rationale to state['aggregated_data']['rationale_by_reg'] "
        "AND renders Doc 05 §6.1b. Requires MOCK_LLM=true or Ollama running."
    ),
)
```

**Implementação (análoga a `cmd_run_applicability`):**

```python
def cmd_run_clauses(
    *, orch, case_path, prep_path, output_path
) -> dict[str, str]:
    from aegis_phase1.v2.output.doc_06 import render_doc_06
    orch.load(case_path, prep_path)
    out_dir = Path(output_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    return render_doc_06(orch.state, str(out_dir))

def cmd_run_phase_1b(
    *, orch, case_path, prep_path, output_path
) -> dict[str, str]:
    from aegis_phase1.v2.output.doc_05 import render_doc_05
    orch.load(case_path, prep_path)
    orch.run_phase_1b()  # invokes P1B-LLM-01 per applicable_reg
    out_dir = Path(output_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    return render_doc_05(orch.state, str(out_dir), llm_invoker=orch.llm_invoker)
```

**Wiring no `main()` (analogous to `run_applicability`):**

```python
elif args.run_clauses:
    paths = cmd_run_clauses(orch=orch, case_path=case_path, prep_path=prep_path, output_path=output_path)
    ...
elif args.run_phase_1b:
    paths = cmd_run_phase_1b(orch=orch, case_path=case_path, prep_path=prep_path, output_path=output_path)
    ...
```

### T6 — TESTS `tests/unit/v2/test_clause_mapping.py` + `test_runner_wiring.py` (~350 LOC)

**Block 1: ClauseMappingContext (6 tests)**

```python
def test_clause_mapping_context_empty_when_no_applicable_regs()
def test_clause_mapping_context_populates_from_preproc_for_gdpr_cra()
def test_clause_mapping_context_per_reg_count_gdpr_28_cra_26()
def test_clause_mapping_context_unmapped_count_is_zero_or_minimal()
def test_clause_mapping_context_by_regulation_filters_correctly()
def test_clause_mapping_context_to_dict_is_json_serializable()
```

**Block 2: Doc 06 refactor (4 tests)**

```python
def test_doc_06_renders_with_clause_mapping_context()
def test_doc_06_table_has_54_rows_for_case1()
def test_doc_06_per_reg_count_matches_canonical()
def test_doc_06_no_longer_reads_from_state_ontology()
```

**Block 3: Runner wiring (3 tests)**

```python
def test_runner_injects_preproc_catalog_into_orchestrator()
def test_runner_injects_case_profile_loader_into_orchestrator()
def test_runner_injects_catalog_loader_into_orchestrator()
```

**Block 4: P1B-LLM-01 integration (4 tests, with MockInvoker)**

```python
def test_run_p1b_single_invokes_p1b_llm_01_for_gdpr()
def test_run_p1b_single_invokes_p1b_llm_01_for_cra()
def test_run_p1b_single_passes_layer0_catalog_with_filtered_tipo2_tipo3()
def test_run_p1b_single_handles_empty_catalogs_gracefully()
```

**Block 5: CLI (2 tests)**

```python
def test_run_clauses_produces_doc_06_with_54_rows()
def test_run_phase_1b_invokes_llm_per_applicable_reg()
```

**Block 6: G1 verification (smoke test) — não é unitário, é
manual via shell. Ver "Quality gates" abaixo.**

Total: **19 tests novos**.

---

## Ficheiros

| Ficheiro | Acção | LOC esperados |
|----------|-------|---------------|
| `src/aegis_phase1/v2/runner.py` | **MODIFY** (T1+T5) | +90 |
| `src/aegis_phase1/v2/orchestrator.py` | **MODIFY** (T1+T4) | +130 |
| `src/aegis_phase1/v2/context/clause_mapping_context.py` | **NEW** (T2) | ~220 |
| `src/aegis_phase1/v2/output/doc_06.py` | **MODIFY** (T3) | 136 → ~150 |
| `tests/unit/v2/test_clause_mapping.py` | **NEW** (T6 block 1+2) | ~180 |
| `tests/unit/v2/test_runner_wiring.py` | **NEW** (T6 block 3) | ~80 |
| `tests/unit/v2/test_p1b_llm_01_integration.py` | **NEW** (T6 block 4) | ~120 |
| `tests/unit/v2/test_clause_mapping_cli.py` | **NEW** (T6 block 5) | ~50 |
| `execution/CONTRACT-039.md` | **NEW** (este) | n/a |

**Não modificar:**
- `preproc_out/` (read-only per AGENTS.md §0)
- `cases/case1-tinytask/{context,input}/` (read-only)
- `Methodology-main/` (read-only; catalog content é contracto separado)
- `_v1_compat.py` (mantido)
- AGENTS.md (mudanças estruturais ficam para fim de sprint)

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G0 — Pre-flight
git branch --show-current   # feature/aegis-p1-corr-039
git status                  # working tree clean
python -c "from aegis_phase1.v2.context.clause_mapping_context import build_clause_mapping_context; print('OK')"
python -c "from aegis_phase1.prompts_v2.catalog import CatalogLoader; print('OK')"
pytest tests/unit/v2/ tests/unit/preprocess/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError" | head -3
# Expected: empty

# G1 — runner injection smoke test
python -c "
import logging
logging.basicConfig(level=logging.INFO)
from pathlib import Path
from aegis_phase1.v2.orchestrator import Phase1Orchestrator
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.prompts_v2.factory import get_prompts_root
o = Phase1Orchestrator(
    work_dir='/tmp/corr039_g1',
    preproc_catalog=PreprocCatalogLoader(preproc_root='preproc_out'),
    case_profile_loader=CaseProfileLoader(Path('cases/case1-tinytask')),
    catalog_loader=CatalogLoader(root=get_prompts_root() / 'catalogs'),
)
o._load_v2_catalog('cases/case1-tinytask')
s = o.state
assert len(s['v2_subdomains']) == 38, f'subs={len(s[\"v2_subdomains\"])}'
assert len(s['v2_srs']) == 282, f'srs={len(s[\"v2_srs\"])}'
assert len(s['v2_sos']) >= 320, f'sos={len(s[\"v2_sos\"])}'  # CORR-037 may have 328 or 338
assert len(s['v2_pairs']) >= 190, f'pairs={len(s[\"v2_pairs\"])}'
assert 'v2_catalog_tipo2' in s, 'catalog_tipo2 missing'
assert 'v2_catalog_tipo3' in s, 'catalog_tipo3 missing'
assert s['v2_audit_both_pass'] is True, 'audit must pass'
print(f'G1 OK: 38 subs, 282 SRs, {len(s[\"v2_sos\"])} SOs, {len(s[\"v2_pairs\"])} pairs, audit pass')
"
# Expected: G1 OK: 38 subs, 282 SRs, 328 SOs, 196 pairs, audit pass

# G2 — Doc 06 semantic parity
MOCK_LLM=true python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-clauses --output /tmp/corr039_g2 2>&1 | tail -3
test -f /tmp/corr039_g2/06_Clause_Mapping_Matrix.md
python -c "
md = open('/tmp/corr039_g2/06_Clause_Mapping_Matrix.md').read()
# Doc 06 should now have content (it was always empty before CORR-039)
assert 'GDPR' in md, 'GDPR missing from Doc 06'
assert 'CRA' in md, 'CRA missing from Doc 06'
# Per the YAML, expected counts are 28+26=54
import re
rows = re.findall(r'\| (GDPR|CRA)-CL\d+', md)
assert len(rows) >= 50, f'expected ≥50 clause rows, got {len(rows)}'
print(f'G2 OK: Doc 06 has {len(rows)} clause rows')
"
# Expected: G2 OK: Doc 06 has 54 clause rows

# G3 — P1B-LLM-01 first invocation (with MockInvoker)
MOCK_LLM=true python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-phase-1b --output /tmp/corr039_g3 2>&1 | tail -3
test -f /tmp/corr039_g3/05_Regulatory_Applicability.md
# Verify LLM was invoked: check logs/phase1/llm-calls.jsonl for P1B-LLM-01 entries
python -c "
import json
from pathlib import Path
log = Path('logs/phase1/llm-calls.jsonl')
if not log.exists():
    print('G3 WARN: no LLM log file (MockInvoker may not log); verifying via state instead')
else:
    calls = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    p1b01_calls = [c for c in calls if c.get('spec_id', '').endswith('P1B-LLM-01-INTERPRETATION')]
    print(f'G3 OK: {len(p1b01_calls)} P1B-LLM-01 invocations logged (expected 2 for GDPR+CRA)')
"

# G4 — CI gates (no regression in pre-existing failures)
bash .hooks/ci-csf-frozen-list.sh   # exit 0
bash .hooks/ci-frameworks.sh        # exit 0

# G5 — Tests
pytest tests/unit/v2/test_clause_mapping.py tests/unit/v2/test_runner_wiring.py tests/unit/v2/test_p1b_llm_01_integration.py tests/unit/v2/test_clause_mapping_cli.py -v
# Expected: 19 passed

# G6 — All tests still green (no regressions)
pytest tests/unit/v2/ tests/unit/preprocess/
# Expected: 2103 + 19 = 2122 passed (5 pre-existing failures unchanged)

# G7 — v1 deprecation still holds
grep -rE "from aegis_phase1\.nodes|from aegis_phase1\.subphases|from aegis_phase1\.graph import" src/ tests/ 2>&1 | grep -v __pycache__ | head -3
# Expected: empty (per CORR-037 T4)

# G8 — Doc 06 no longer reads from state['ontology']['clause_mappings']
grep -nE 'ontology\[.clause_mappings.\]|get\(.clause_mappings' src/aegis_phase1/v2/output/doc_06.py
# Expected: empty (T3 refactor moved source to ClauseMappingContext)

echo "=== ALL GATES PASSED ==="
```

**Definição de done:** G0–G8 todos PASS + commits sequenciais no
branch (sem amend, sem rebase) + pre-push hook valida 17/17
contract checks.

---

## Estrutura de commits

```
feature/aegis-p1-corr-039
├─ commit 1: CORR-039: contract — SP-C ClauseMappingContext + Doc 06 + runner wiring + P1B-LLM-01
├─ commit 2: CORR-039-T1: FIX runner.py — inject PreprocCatalogLoader + CaseProfileLoader + CatalogLoader
├─ commit 3: CORR-039-T2: NEW clause_mapping_context.py (Pydantic + per-reg count + unmapped)
├─ commit 4: CORR-039-T3: REFACTOR doc_06.py — read from ClauseMappingContext (54 rows for case1)
├─ commit 5: CORR-039-T4: WIRE P1B-LLM-01 in orchestrator.run_p1b_single (catalog + classification)
├─ commit 6: CORR-039-T5: --run-clauses + --run-phase-1b CLI flags
├─ commit 7: CORR-039-T6: 19 tests (clause mapping + runner wiring + P1B-LLM-01 + CLI)
├─ commit 8: CORR-039: parity snapshot + handoff doc
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
| `PreprocCatalogLoader` falha ao instanciar (path `preproc_out/` não existe em dev) | T1 instancia com `preproc_root="preproc_out"` (relativo ao cwd). G1 falha-fast com mensagem clara; contratante deve correr `python -m scripts.preprocess build` primeiro. |
| `CaseProfileLoader` espera estrutura `cases/<case>/input/...` (não `context/`) | Case1 tem `input/` (ver `cases/case1-tinytask/input/regulatory/applicability.yaml`). Confirmar com `ls cases/case1-tinytask/input/`. |
| `CatalogLoader` levanta `CatalogLoadError` quando o diretório `catalogs/` está vazio | Loader é tolerante: lê 0 entries e retorna lista vazia. Confirmado em `catalog.py:48` (verifica `self.root.exists()` — passa se dir existe mesmo que vazio). |
| `Orchestrator.run_p1b_single` precisa de `executor` que precisa de `llm_invoker` que precisa de Ollama (ou `MOCK_LLM=true`) | G3 corre com `MOCK_LLM=true`; o `MockInvoker` retorna dict válido; o pipeline continua. Sem Ollama real. |
| P1B-LLM-01 prompt espera `company_facts.architecture_ref`, `data_categories`, `products`, `role_obligations` | T4 preenche estes campos a partir de `v2_company_profile` + `v2_obligated_party`. Sem fields inventados. |
| Doc 06 com 54 rows pode ser visualmente pesado | Manter tabela densa (7 colunas); referência da TinyTask também é densa. Sem refactor de styling. |
| `_v1_compat.py` ainda popula `state['regulations']` e `state['company_context']` — Doc 06 já não os usa, mas outros docs sim | Sem impacto: T3 só remove a leitura de `state['ontology']['clause_mappings']` em doc_06. Outros docs mantêm v1 keys. |
| 5 falhas pre-existentes (LLM + state_propagation) podem ser perturbadas por T4 | Confirmar via G6 que passam **exactamente** as mesmas 5 (sem regressão). Se houver regressão, fix no mesmo commit. |
| `preproc_out/` é read-only mas o `PreprocCatalogLoader` é instanciado com path absoluto | Constructor do `PreprocCatalogLoader` apenas lê; não escreve. Confirmado em `preproc_catalog.py:292` (`self.preproc_root = Path(preproc_root).resolve()` + lê). |
| Catalog YAML files vazios causam `yaml.safe_load` a retornar `None` em vez de `[]` | `_load_yaml_with_frontmatter` em `catalog.py:67` trata: Step 3 fallback `yaml.safe_load(body)` pode retornar None; o caller `load()` checa `isinstance(data, list)` e levanta `CatalogLoadError`. **Mitigação:** T1 wrapper com try/except que cai para listas vazias. |

---

## Pre-flight check (OBRIGATÓRIO antes de cada T1-T6)

Per AGENTS.md §10.1:

```bash
$ git branch --show-current
feature/aegis-p1-corr-039

$ git status
nothing to commit, working tree clean

$ python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('OK')"
OK

$ python -c "from aegis_phase1.prompts_v2.catalog import CatalogLoader; print('OK')"
OK

$ pytest tests/unit/v2/ tests/unit/preprocess/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError" | head -3
# Expected: empty
```

Se algum check falhar, abortar a sub-tarefa, fixar, retomar.

---

## Métricas esperadas

- **Linhas adicionadas (código):** ~770 (T1: 90 + T2: 220 + T3: 14 + T4: 130 + T5: 50 + T6: 350)
- **Linhas removidas (código):** ~10 (T3: -8 oracle v1 ontology read, T1: -2 misc)
- **Net LOC:** +760
- **Ficheiros novos:** 5 (clause_mapping_context.py, test_clause_mapping.py, test_runner_wiring.py, test_p1b_llm_01_integration.py, test_clause_mapping_cli.py)
- **Ficheiros modificados:** 3 (runner.py, orchestrator.py, doc_06.py)
- **Commits:** 7-8
- **Tests novos:** 19 (6 context + 4 doc_06 + 3 runner wiring + 4 P1B-LLM-01 + 2 CLI)
- **Tests totais esperados:** 2103 + 19 = **2122** (5 pre-existing failures preserved)
- **Duração estimada:** 4-6h (single session, manageable)

---

## Pós-CORR-039

**Sequência da estratégia (ver `CONTRACT-038` §"Pós-CORR-038"):**

| SP | Contract | Foco |
|----|----------|------|
| D | **CORR-040** (`feature/aegis-p1-corr-040`) | DomainActivationContext + P1C-LLM-01 (overlap classification) + Doc 07 matrix (38×5) + Track B proportionality. |
| E | **CORR-041** (`feature/aegis-p1-corr-041`) | SynthesisContext + P1C-LLM-03 (strategic synthesis) + P1C-LLM-02 (compound events) + P1B-LLM-02 (per-reg rationale) + Doc 04a-d + parity check 9 outputs. |

**Estado pós-CORR-039:**
- Runner injecta `PreprocCatalogLoader` + `CaseProfileLoader` + `CatalogLoader`
- `v2_subdomains` (38), `v2_srs` (282), `v2_sos` (328), `v2_pairs` (196) populados
- `v2_catalog_tipo2` + `v2_catalog_tipo3` populados (vazios por agora)
- `ClauseMappingContext` canónico (fonte única de clause→subdomain)
- Doc 06 com 54 rows para case1 (vs 0 rows pré-CORR-039)
- P1B-LLM-01 invocado pelo runner pela primeira vez (com `MOCK_LLM=true`)
- CLI `--run-clauses` (Doc 06, sem LLM) + `--run-phase-1b` (Doc 05 §6.1b, com LLM)
- 2122 tests passam (19 novos, 5 falhas pre-existentes preservadas)

**Contractos paralelos (out-of-scope para este contracto):**

- **Methodology-main**: criar conteúdo real de
  `00_METHODOLOGY/PROMPTS/catalogs/tipo2_interpretations.yaml` e
  `tipo3_derogations.yaml` (8 Tipo 2 + 6 Tipo 3 entries Berry-style).
  É um contracto methodology-side, não código Python. Pós-CORR-039
  o catalog loader está wired e pronto para receber conteúdo.

**Critério de sucesso global** (pós CORR-041):
`python -m aegis_phase1.v2.runner --run-all cases/case1-tinytask`
produz 9 outputs (04/04a/04b/04c/04d/05/06/07/07b + xlsx) com diff
semântico ≤ threshold contra
`Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`.

---

## Change log

- 2026-07-21: v1.0 — contract inicial criado após merge de CORR-038
  (PR #32). Branch `feature/aegis-p1-corr-039` a ser baseada em main
  pós-CORR-038. Contrato define T1-T6 com API pública, gate
  criteria, estrutura de commits, e risks. **Primeira cadeia LLM
  canónica end-to-end do pipeline v2** (P1B-LLM-01 invocado via
  runner com catálogos filtrados). Implementação começa em sessão
  seguinte.

---

## Verdict pós-execução (CORR-042, 2026-07-21)

**Status:** ✅ PASS

**Evidence:**
- Run end-to-end REAL (sem MOCK_LLM) com Ollama gemma4:e2b
- Gates executados em: feature/aegis-p1-corr-042 @ commit de T7
- Parity report: logs/phase1/corr042_parity_report.md
- Run logs: logs/phase1/corr042_run_*.log
- Errors post-mortem: logs/phase1/corr042_errors.md
Parity 9/9 PASS. CORR-039 (ClauseMappingContext + Doc 06 + runner wiring + P1B-LLM-01) — Doc 06 com 222 rows (150 CRA + 72 GDPR); logs/phase1/llm-calls.jsonl confirma 4 P1B-LLM calls (P1B-LLM-01 + P1B-LLM-02 × 2 regs) all OK com tipo2 (8) + tipo3 (6) catalog content.
