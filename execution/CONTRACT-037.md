# CORR-037 — SP-A: PreprocCatalogLoader + CaseProfileLoader + depreciação v1

## Resumo

Segundo contract da estratégia faseada **CORR-036 → CORR-041**
(reorientação do pipeline v2 para ler `preproc_out/` JSON diretamente,
sem regex, e alimentar os 5 LLMs canónicos com catálogos wired).

Este contract **altera código**. Troca a fonte de dados do v2 loader de
"MD com regex" para "JSON direto do `preproc_out/`", introduz dois novos
loaders com Pydantic models, refactoriza o `v2/orchestrator.py` para os
usar, e **remove o v1 legacy** (~5000 LOC em `graph.py`, `subphases/`,
`nodes/`, `shared/document_producer.py`).

> **Atenção:** este contract é um **sprint-contract de refactor pesado**.
> Não é executável de uma só vez em poucas horas. O contract define o
> specification completo e os FAIL gates. A implementação será feita em
> **múltiplas sessões** (sub-fases T1 → T5), com commits sequenciais no
> branch, mas sem sub-branches (AGENTS.md §10).

**Branch:** `feature/aegis-p1-corr-037`
**Data:** 2026-07-21
**Trigger:** SP-A da estratégia (ver `.zcode/plans/plan-sess_59e5ec8f-...md` §"ARQUITETURA ALVO" e §"SP-A").

**Dependência upstream:** CORR-036 já merged a main (commit `2a63271`).
O data fix (8/2M/MICRO) está em `phase1_ontology.yaml` para que o
`CaseProfileLoader` leia valores consistentes desde o início.

---

## Contexto (resumo da estratégia)

A v2 está implementada (1285 LOC orchestrator + 25 testes + 9 renderers).
O problema diagnosticado é de **contexto**, não de código:

1. **Catálogos não chegam ao LLM.** `prompts_v2/catalog.py: CatalogLoader`
   existe mas `invoker.py:53` declara-o opcional e o orchestrator nunca o
   passa. Os 5 LLMs são invocados sem `tipo2_interpretations`,
   `tipo3_derogations`, `scope_overlap_predicates`, `event_templates`.
2. **Contexto lido por regex de MDs.** `v2/loader/subdomain_loader.py:24`
   tem `HEADER_RE = re.compile(...)`. 81 ocorrências de regex em
   `v2/loader`+`v2/domain`. Perde-se estrutura (`participating_regulations`,
   `hso_hl.objective`, `hso_per_reg[].inherits_from`, `pairs[].downstream_implication`,
   `security_requirements[].nist_csf_mapping`, `csf_hint[]`) que **já existe
   como JSON** em `preproc_out/`.
3. **Discrepância caso1** (resolvida em CORR-036): `phase1_ontology.yaml`
   estava desalinhado com `classification.yaml`. Já corrigido.

**O que `preproc_out` JSON fornece (que a v2 ignora hoje):**
- **Sub-domain (38)** `3-entities/subdomains/D-XX/D-XX.Y.json`
- **SR (282)** `3-entities/srs/D-XX/SR-{REG}-NNN.json`
- **SO (338)** `3-entities/sos/D-XX/SO-{REG}-NNN.json`
- **CSF (106+79)** `3-entities/csfs/{FN}/{FN_CT_NN}.json`
- **Cláusulas (578)** `3-entities/clauses/_root/{REG}/{REG}_CLnn.json`
- **Pairs (196)** `3-entities/pairs/D-XX/D-XX.Y_{a}-{b}.json`
- **Audit (gate)** `4-reference_and_meta/audit/{csf_mapping_report,so_sr_coherence_report}.json`
- **Index (resolver)** `4-reference_and_meta/index/{entities,by_regulation,by_subdomain,cross_references}.json`

---

## Decisão de produto (arquitetura alvo)

A v2 passa a ler exclusivamente de `preproc_out/` JSON (zero regex de MDs
na stage LOAD). Introduz-se uma camada de **Pydantic models** entre o
filesystem e o orchestrator, garantindo:

1. **Type safety** — o orchestrator recebe objetos tipados, não dicts.
2. **Null tolerance** — `preproc_out` tem campos opcionais (e.g.
   `csf_hint[]`, `hso_hl.activation`); os Pydantic models são
   permissivos (`Optional[T] = None` ou `list[T] = Field(default_factory=list)`).
3. **Cache in-memory** — loaders carregam JSONs uma vez (lazy ou eager),
   expõem handles para o orchestrator sem custo repetido.
4. **Source-of-truth único** — `preproc_out/` é ground truth; MDs ficam
   como provenance, não como input.

Os 2 loaders são **independentes** mas partilham o mesmo padrão:

| Loader | Input | Output | Uso |
|--------|-------|--------|-----|
| `PreprocCatalogLoader` | `preproc_out/3-entities/**` + `4-reference_and_meta/audit/*` + `4-reference_and_meta/index/*` | Pydantic models (`Subdomain`, `SR`, `SO`, `CSFSubcat`, `Clause`, `Pair`, `AuditReport`, `Index`) | SP-C, SP-D, SP-E (LLM context) |
| `CaseProfileLoader` | `cases/<case>/input/{company,architecture,regulatory}/*.yaml` | `CompanyContext` Pydantic | SP-B (applicability), todos (company facts) |

O orchestrator é refactorizado para receber **injected loaders** (não
singletons). Isto facilita testing (mocks via construtor) e prepara o
terreno para SP-B (`ApplicabilityContext`).

---

## Tarefas

### T1 — NEW `src/aegis_phase1/v2/loader/preproc_catalog.py` (~300 LOC)

**Responsabilidade:** carregar `preproc_out/3-entities/**` e `preproc_out/4-reference_and_meta/{audit,index}/**` para Pydantic models, com cache in-memory.

**API pública:**

```python
from pathlib import Path
from aegis_phase1.v2.loader.preproc_catalog import (
    PreprocCatalogLoader,
    Subdomain, SR, SO, CSFSubcat, Clause, Pair,
    AuditReport, EntitiesIndex,
)

loader = PreprocCatalogLoader(preproc_root=Path("preproc_out"))

# Bulk load (cached)
subdomains: list[Subdomain] = loader.load_subdomains()       # 38
srs: list[SR] = loader.load_srs()                            # 282
sos: list[SO] = loader.load_sos()                            # 338
csfs: list[CSFSubcat] = loader.load_csfs()                   # 185
clauses: list[Clause] = loader.load_clauses()                # 578
pairs: list[Pair] = loader.load_pairs()                      # 196
audit: AuditReport = loader.load_audit()                     # csf_mapping_report + so_sr_coherence_report
index: EntitiesIndex = loader.load_index()                   # by_regulation, by_subdomain, cross_references

# Scoped queries (sem recarregar)
srs_for_subdomain: list[SR] = loader.load_srs(sub_domain="D-01.1")
srs_for_regulation: list[SR] = loader.load_srs(regulation="GDPR")
clauses_for_reg: list[Clause] = loader.load_clauses(regulation="CRA")
pairs_for_subdomain: list[Pair] = loader.load_pairs(sub_domain="D-01.1")

# Cache invalidation (para testes / rebuild)
loader.clear_cache()
```

**Pydantic models (mínimo viável, espelhar JSON schema de `preproc_out`):**

```python
class Subdomain(BaseModel):
    id: str                                          # "D-01.1"
    name: str
    domain: str                                      # "D-01"
    participating_regulations: list[str] = []        # ["GDPR", "NIS2", "CRA", "DORA"]
    hso_hl: Optional[HSOHighLevel] = None            # {id, objective, activation}
    hso_per_reg: list[HSOPerReg] = []                # per-reg sub-SOs
    pairs_in_subdomain: list[str] = []               # pair ids
    security_requirements_count: Optional[int] = None
    csf_hint: list[str] = []                         # CSF subcat ids

class HSOHighLevel(BaseModel):
    id: str                                          # "SO-D-01.1.HL"
    objective: str
    activation: Optional[str] = None

class HSOPerReg(BaseModel):
    id: str                                          # "SO-D-01.1.GDPR" or "SO-GDPR-001"
    regulation: str
    inherits_from: Optional[str] = None              # parent SO id
    source_SR: Optional[str] = None                  # root SR id
    activation: Optional[str] = None
    objective: str
    anchors: list[str] = []
    csf: list[str] = []                              # CSF subcat ids

class SR(BaseModel):
    id: str                                          # "SR-GDPR-001"
    regulation: str
    source_clauses: list[SourceClauseRef] = []       # [{clause_id, article, excerpt?}]
    linked_objectives: list[str] = []                # SO ids
    sub_domain: list[str] = []                       # D-XX.Y ids
    nist_csf_mapping: list[str] = []                 # CSF subcat ids
    applies_to_role: list[str] = []
    obligation_type: list[str] = []
    regulatory_rationale: str = ""
    ambiguity_notes: Optional[str] = None

class SO(BaseModel):
    id: str                                          # "SO-GDPR-001"
    regulation: str
    objective: str
    activation: Optional[str] = None
    inherits_from: Optional[str] = None
    source_SR: Optional[str] = None
    anchors: list[str] = []
    csf: list[str] = []

class CSFSubcat(BaseModel):
    id: str                                          # "GV.OC-01"
    function: str                                    # "GV"
    category: str
    subcategory: str
    text: str

class Clause(BaseModel):
    id: str                                          # "GDPR-CL01" or "DORA-CL17-1"
    regulation: str
    article: Optional[str] = None
    title: str
    text: str
    # ...

class Pair(BaseModel):
    id: str                                          # "D-01.1_GDPR-CRA"
    sub_domain: str
    regulation_a: str
    regulation_b: str
    classification: Optional[str] = None
    verified_relationship: str                      # FROZEN — never modify
    downstream_implication: str

class AuditReport(BaseModel):
    csf_mapping: dict                               # raw csf_mapping_report.json
    so_sr_coherence: dict                           # raw so_sr_coherence_report.json
    both_pass: bool                                  # csf broken==0 AND so_without_sr==0

class EntitiesIndex(BaseModel):
    by_regulation: dict[str, list[str]]              # {"GDPR": ["SR-GDPR-001", ...]}
    by_subdomain: dict[str, list[str]]               # {"D-01.1": ["SR-GDPR-001", ...]}
    cross_references: list[dict] = []
```

**Cache in-memory:** `@functools.lru_cache(maxsize=None)` em cada `load_*` method, keyed pelos argumentos. `clear_cache()` exposto para testes.

**Localização do JSON em preproc_out:**
- `preproc_out/3-entities/subdomains/D-{XX}/D-{XX.Y}.json` (1 ficheiro por subdomínio, 38 total)
- `preproc_out/3-entities/srs/D-{XX}/SR-{REG}-{NNN}.json` (282 total)
- `preproc_out/3-entities/sos/D-{XX}/SO-{REG}-{NNN}.json` (338 total)
- `preproc_out/3-entities/csfs/{FN}/{FN}.{CT}-{NN}.json` (185 total)
- `preproc_out/3-entities/clauses/_root/{REG}/{REG}-CL{NN}[-{M}].json` (578 total; DORA usa `-{M}` suffix)
- `preproc_out/3-entities/pairs/D-{XX}/D-{XX.Y}_{REG_A}-{REG_B}.json` (196 total; REG_A < REG_B alfabeticamente)
- `preproc_out/4-reference_and_meta/audit/{csf_mapping_report,so_sr_coherence_report}.json`
- `preproc_out/4-reference_and_meta/index/{entities,by_regulation,by_subdomain,cross_references}.json`

**Notas executor:**
- IDs em preproc usam `D-XX.Y` (não `SD-XX.Y`).
- Filename usa UNDERSCORE (`D-01.1_GDPR-CRA.json`) mas JSON `id` field usa HYPHEN (`D-01.1`).
- AI_Act canonical (não `AIACT`, `AI Act`, `AIA`).
- DORA multi-clause: `DORA-CL{NN}-{M}` (e.g. `DORA-CL17-1`). Não colapsar.
- **Não alterar preproc_out** (read-only).
- Pydantic tolerante a nulls (campos opcionais, defaults sensatos).

### T2 — NEW `src/aegis_phase1/v2/loader/case_profile.py` (~150 LOC)

**Responsabilidade:** carregar `cases/<case>/input/{company,architecture,regulatory}/*.yaml` para `CompanyContext` Pydantic.

**API pública:**

```python
from pathlib import Path
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader, CompanyContext

loader = CaseProfileLoader(case_path=Path("cases/case1-tinytask"))
ctx: CompanyContext = loader.load()

# Acesso direto a factos
ctx.company.name                    # "TinyTask Lda."
ctx.company.employees               # 8
ctx.company.revenue_eur             # 2000000
ctx.company.scale                   # "MICRO"
ctx.applicability_predicates        # {processes_personal_data: bool, ...}
ctx.applicable_regs                 # ["GDPR", "CRA"]  (computed from predicates)
ctx.declared_applicable_regs        # ["GDPR", "CRA"]  (from applicability.yaml)
ctx.declaration_gaps                # []  (diff between declared and computed)
```

**Pydantic model:**

```python
class CompanyFacts(BaseModel):
    name: str
    legal_structure: str
    sector: str
    jurisdiction: str
    employees: int
    revenue_eur: int
    scale: Literal["MICRO", "SMALL", "MEDIUM", "LARGE"]
    security_fte: float
    criticality_level: str
    tech_stack: list[str] = []

class ApplicabilityPredicates(BaseModel):
    """Filter 1 booleans (PHASE1_STRATEGY §Inputs MINIMAL)."""
    processes_personal_data: bool
    places_digital_products_eu: bool
    dora_financial_entity: bool
    nis2_sector: str                                  # "" = not NIS2
    aiact_high_risk_system: bool
    eu_data_subjects_count: int = 0

class ArchitectureFacts(BaseModel):
    # Loaded from input/architecture/*.yaml (currently minimal/empty in case1)
    # Future-proofed for SP-B/C extension
    pass

class RegulatoryFacts(BaseModel):
    applicable: list[str] = []
    obligated_party_per_reg: dict[str, str] = {}      # {"GDPR": "controller", ...}

class CompanyContext(BaseModel):
    company: CompanyFacts
    applicability_predicates: ApplicabilityPredicates
    applicable_regs: list[str]                       # computed from predicates
    declared_applicable_regs: list[str]              # from input/regulatory/applicability.yaml
    declaration_gaps: list[str]                      # diff declared vs computed
    architecture: ArchitectureFacts = ArchitectureFacts()
    regulatory: RegulatoryFacts = RegulatoryFacts()
    # ... plus raw 5-role-per-reg fields for the full Standard tier
```

**Compute `applicable_regs` from predicates:**

```python
def _compute_applicable_regs(p: ApplicabilityPredicates) -> list[str]:
    out = []
    if p.processes_personal_data:                     out.append("GDPR")
    if p.places_digital_products_eu:                  out.append("CRA")
    if p.nis2_sector and p.nis2_sector != "":         out.append("NIS2")
    if p.dora_financial_entity:                       out.append("DORA")
    if p.aiact_high_risk_system:                      out.append("AI_Act")
    return out
```

`declaration_gaps` = `set(declared_applicable_regs) ^ set(applicable_regs)`.
Padrão `DECLARATION_GAP` (PHASE1_STRATEGY §6): declarado ≠ computado →
flagear (não silenciar).

**Localização do YAML em case1 (já alinhado pelo CORR-036):**
- `cases/case1-tinytask/input/company/classification.yaml` ← canonical
- `cases/case1-tinytask/context/phase1_ontology.yaml` ← metadata (agora consistente)
- `cases/case1-tinytask/input/regulatory/applicability.yaml` ← a verificar se existe (recon na T1)
- `cases/case1-tinytask/input/architecture/*.yaml` ← a verificar (pode estar vazio em case1)

### T3 — REFACTOR `src/aegis_phase1/v2/orchestrator.py` (1285 LOC → ~1100 LOC)

**Objectivo:** trocar todas as chamadas a `SubDomainLoader`, `PreprocessingLoader`, `AmbiguityLoader`, `ArticleLoader` para `PreprocCatalogLoader` + `CaseProfileLoader`. Manter 4-stage e state shape (LangGraph).

**Métodos a refactorizar (grep `_load_` em orchestrator.py):**
- `_load_case` → usa `CaseProfileLoader` em vez de `YamlInputLoader` (parcial)
- `_load_subdomains` → usa `PreprocCatalogLoader.load_subdomains()` em vez de `SubDomainLoader` (regex)
- `_load_clauses` → usa `PreprocCatalogLoader.load_clauses()` em vez de `PreprocessingLoader._load_clauses` (regex)
- `_load_articles` → usa `PreprocCatalogLoader.load_clauses()` (filtra por article) em vez de `ArticleLoader` (regex)
- `_load_ambiguity` → usa `PreprocCatalogLoader.load_audit()` (gates) em vez de `AmbiguityLoader` (regex)
- `_load_sos` → usa `PreprocCatalogLoader.load_sos()` (NEW; v1 não tinha)
- `_load_srs` → usa `PreprocCatalogLoader.load_srs()` (NEW; v1 não tinha)

**Construtor:** passar `preproc_catalog: PreprocCatalogLoader` e `case_profile: CaseProfileLoader` ao construtor (injected, não singletons). Default factories no `__init__` para uso standalone.

```python
class Phase1Orchestrator:
    def __init__(
        self,
        case_path: Path,
        preproc_root: Path = Path("preproc_out"),
        preproc_catalog: Optional[PreprocCatalogLoader] = None,
        case_profile_loader: Optional[CaseProfileLoader] = None,
        llm_invoker: Optional[Phase1LLMInvoker] = None,
    ):
        self.case_path = case_path
        self.preproc_catalog = preproc_catalog or PreprocCatalogLoader(preproc_root)
        self.case_profile_loader = case_profile_loader or CaseProfileLoader(case_path)
        # ... rest unchanged
```

**State shape (`Phase1State`):** manter 4-stage e chaves existentes. Adicionar chaves se novas entidades forem necessárias (e.g. `p1b_outputs_by_reg: dict[str, list]` — mas isto é T4 de SP-C, não agora).

**Não tocar:** `v2/output/`, `v2/reduce/`, `v2/domain/` (estes vão ser refactorizados em SP-B/C/D, não agora). O objectivo de T3 é **só a stage LOAD**.

### T4 — REMOVE v1 legacy (~5000 LOC)

**Remover:**

| Path | LOC aprox | Razão |
|------|-----------|-------|
| `src/aegis_phase1/graph.py` | ~250 | LangGraph v1 (substituído por orchestrator v2) |
| `src/aegis_phase1/subphases/` (dir) | ~800 | Subphases v1 (a/b/c/d legacy) |
| `src/aegis_phase1/nodes/` (dir) | ~3000 | 23 node functions v1 |
| `src/aegis_phase1/shared/document_producer.py` | ~150 | Markdown producer v1 |
| `src/aegis_phase1/run_with_iteration.py` | ~50 | Entry point v1 (substituído por v2.runner) |
| `src/aegis_phase1/section_refill.py` | ~100 | LLM section refill v1 (substituído por v2 reducers) |
| `src/aegis_phase1/doc_evaluator.py` | ~200 | Doc evaluator v1 (substituído por GATE-1C em v2) |
| `_v2` dead hooks em `b01/b02/c01/c02/c03` | ~50 | Funções de hook que nunca são chamadas (já em subphases/, removidas com o dir) |

**Verificar que nada referencia os removidos:**

```bash
grep -rn "from aegis_phase1.nodes\|from aegis_phase1.subphases\|from aegis_phase1.graph import\|from aegis_phase1.shared.document_producer\|from aegis_phase1.run_with_iteration\|from aegis_phase1.section_refill\|from aegis_phase1.doc_evaluator" src/ tests/
# Expected: vazio

grep -rn "SubDomainLoader\|_parse_yaml_frontmatter\|HEADER_RE" src/aegis_phase1/v2/
# Expected: vazio (v2 deve usar PreprocCatalogLoader)
```

**Atualizar `AGENTS.md` §1:** remover a tabela/descrição do v1; manter só v2 + prompts_v2.

**Cuidado com `__init__.py` exports:** verificar que `from aegis_phase1 import graph, subphases, nodes, shared` não é feito em lado nenhum antes de remover.

### T5 — NEW tests

**`tests/unit/v2/loader/test_preproc_catalog.py` (~200 LOC):**

```python
import pytest
from pathlib import Path
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

@pytest.fixture
def loader(tmp_path) -> PreprocCatalogLoader:
    # Use real preproc_out (it's committed and read-only)
    return PreprocCatalogLoader(preproc_root=Path("preproc_out"))

def test_load_subdomains_count(loader):
    """38 subdomains expected (CORR-030 invariant)."""
    assert len(loader.load_subdomains()) == 38

def test_load_subdomains_d01_1(loader):
    """D-01.1: Data at Rest Encryption."""
    sd = next(s for s in loader.load_subdomains() if s.id == "D-01.1")
    assert sd.participating_regulations == ["GDPR", "NIS2", "CRA", "DORA"]
    assert sd.hso_hl.id == "SO-D-01.1.HL"
    assert sd.hso_per_reg[0].regulation == "GDPR"
    assert sd.hso_per_reg[0].inherits_from == "SO-GDPR-001"

def test_load_srs_count(loader):
    """282 SRs expected (CORR-030 invariant: coverage full=282)."""
    assert len(loader.load_srs()) == 282

def test_load_sos_count(loader):
    """338 SOs expected."""
    assert len(loader.load_sos()) == 338

def test_load_csfs_count(loader):
    """185 CSF subcategories (106 active + 79 deferred/archived)."""
    assert len(loader.load_csfs()) == 185

def test_load_clauses_count(loader):
    """578 clauses expected."""
    assert len(loader.load_clauses()) == 578

def test_load_pairs_count(loader):
    """196 pairs expected."""
    assert len(loader.load_pairs()) == 196

def test_load_audit_both_pass(loader):
    """Audit must report both gates pass (CSF BROKEN==0 AND SO-without-SR==0)."""
    audit = loader.load_audit()
    assert audit.both_pass is True

def test_load_index_by_regulation(loader):
    """Index by_regulation must have all 5 regulations."""
    idx = loader.load_index()
    for reg in ("GDPR", "CRA", "NIS2", "DORA", "AI_Act"):
        assert reg in idx.by_regulation
        assert len(idx.by_regulation[reg]) > 0

def test_cache(loader):
    """load_subdomains() called twice returns same object (lru_cache)."""
    a = loader.load_subdomains()
    b = loader.load_subdomains()
    assert a is b

def test_clear_cache(loader):
    """clear_cache() forces reload."""
    a = loader.load_subdomains()
    loader.clear_cache()
    b = loader.load_subdomains()
    assert a == b
    assert a is not b

def test_srs_scoped_by_subdomain(loader):
    """load_srs(sub_domain='D-01.1') returns only SRs in that subdomain."""
    srs = loader.load_srs(sub_domain="D-01.1")
    for sr in srs:
        assert "D-01.1" in sr.sub_domain
```

**`tests/unit/v2/loader/test_case_profile.py` (~150 LOC):**

```python
import pytest
from pathlib import Path
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader

@pytest.fixture
def ctx():
    loader = CaseProfileLoader(case_path=Path("cases/case1-tinytask"))
    return loader.load()

def test_company_canonical(ctx):
    """TinyTask is MICRO by design (post-CORR-036 alignment)."""
    assert ctx.company.name == "TinyTask Lda."
    assert ctx.company.employees == 8
    assert ctx.company.revenue_eur == 2000000
    assert ctx.company.scale == "MICRO"

def test_applicability_predicates(ctx):
    assert ctx.applicability_predicates.processes_personal_data is True
    assert ctx.applicability_predicates.places_digital_products_eu is True
    assert ctx.applicability_predicates.dora_financial_entity is False
    assert ctx.applicability_predicates.nis2_sector == ""
    assert ctx.applicability_predicates.aiact_high_risk_system is False

def test_applicable_regs_computed(ctx):
    """GDPR + CRA, not NIS2/DORA/AI_Act (TinyTask MICRO, 8 employees)."""
    assert set(ctx.applicable_regs) == {"GDPR", "CRA"}

def test_no_declaration_gaps(ctx):
    """Declared and computed must match for case1 (CORR-036 alignment)."""
    assert ctx.declaration_gaps == []
    assert set(ctx.declared_applicable_regs) == set(ctx.applicable_regs)

def test_obligated_party_per_reg(ctx):
    """TinyTask: GDPR=controller, CRA=manufacturer."""
    assert ctx.regulatory.obligated_party_per_reg.get("GDPR") == "controller"
    assert ctx.regulatory.obligated_party_per_reg.get("CRA") == "manufacturer"
```

---

## Ficheiros

| Ficheiro | Acção | LOC esperados |
|----------|-------|---------------|
| `src/aegis_phase1/v2/loader/preproc_catalog.py` | **NEW** | ~300 |
| `src/aegis_phase1/v2/loader/case_profile.py` | **NEW** | ~150 |
| `src/aegis_phase1/v2/orchestrator.py` | **MODIFY** (refactor `_load_*`) | 1285 → ~1100 |
| `src/aegis_phase1/graph.py` | **DELETE** | -250 |
| `src/aegis_phase1/subphases/` | **DELETE** (dir) | -800 |
| `src/aegis_phase1/nodes/` | **DELETE** (dir) | -3000 |
| `src/aegis_phase1/shared/document_producer.py` | **DELETE** | -150 |
| `src/aegis_phase1/run_with_iteration.py` | **DELETE** | -50 |
| `src/aegis_phase1/section_refill.py` | **DELETE** | -100 |
| `src/aegis_phase1/doc_evaluator.py` | **DELETE** | -200 |
| `tests/unit/v2/loader/__init__.py` | **NEW** | 0 |
| `tests/unit/v2/loader/test_preproc_catalog.py` | **NEW** | ~200 |
| `tests/unit/v2/loader/test_case_profile.py` | **NEW** | ~150 |
| `AGENTS.md` | **MODIFY** (§1 — remover v1) | ±5 |
| `execution/CONTRACT-037.md` | **NEW** (este) | (n/a) |

**Não modificar:** qualquer ficheiro em `preproc_out/`, `Methodology-main/`,
`cases/case1-tinytask/{context,input,output}/data/`, `.hooks/`.

---

## Quality gates (FAIL default — todos têm de passar)

```bash
source ../shared-venv/bin/activate

# G0 — Pre-flight (sanidade do branch limpo)
git branch --show-current                              # feature/aegis-p1-corr-037
git status                                             # working tree clean
python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('OK')"
python -c "from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader; print('OK')"
python -c "from aegis_phase1.v2.loader.case_profile import CaseProfileLoader; print('OK')"

# G1 — preproc_out/ audits permanecem pristine
python -m scripts.preprocess.audit_csf_mapping | grep -q "0 BROKEN"
python -m scripts.preprocess.audit_so_sr_coherence | grep -qE "SO without SR: 0|sr_without_so.*count.*0"

# G2 — CI gates
bash .hooks/ci-csf-frozen-list.sh                     # exit 0
bash .hooks/ci-frameworks.sh                          # exit 0

# G3 — PreprocCatalogLoader contagens (ACTUAL counts in committed preproc_out/ as of 2026-07-21;
# the strategy doc said 38/282/338/578/196/185 but the actual numbers are 38/282/328/498/196/106.
# SOs: 328 files on disk (10 fewer than doc; 189 are "real" per audit, rest are cross-refs).
# CSFs: 106 ACTIVE on disk (79 withdrawn/archived are not committed; doc said 185).
# Clauses: 498 files on disk (80 fewer than doc).
python -c "from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader; from pathlib import Path; cl = PreprocCatalogLoader(Path('preproc_out')); print(len(cl.load_subdomains()))" | grep -q "^38$"
python -c "from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader; from pathlib import Path; cl = PreprocCatalogLoader(Path('preproc_out')); print(len(cl.load_srs()))" | grep -q "^282$"
python -c "from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader; from pathlib import Path; cl = PreprocCatalogLoader(Path('preproc_out')); print(len(cl.load_sos()))" | grep -q "^328$"
python -c "from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader; from pathlib import Path; cl = PreprocCatalogLoader(Path('preproc_out')); print(len(cl.load_clauses()))" | grep -q "^498$"
python -c "from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader; from pathlib import Path; cl = PreprocCatalogLoader(Path('preproc_out')); print(len(cl.load_pairs()))" | grep -q "^196$"
python -c "from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader; from pathlib import Path; cl = PreprocCatalogLoader(Path('preproc_out')); print(len(cl.load_csfs()))" | grep -q "^106$"

# G4 — Specific D-01.1 assertions (per strategy doc)
python -c "
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from pathlib import Path
cl = PreprocCatalogLoader(Path('preproc_out'))
sd = next(s for s in cl.load_subdomains() if s.id == 'D-01.1')
assert sd.participating_regulations == ['GDPR', 'NIS2', 'CRA', 'DORA'], f'got {sd.participating_regulations}'
assert sd.hso_hl.id == 'SO-D-01.1.HL', f'got {sd.hso_hl.id}'
assert sd.hso_per_reg[0].inherits_from == 'SO-GDPR-001', f'got {sd.hso_per_reg[0].inherits_from}'
print('G4 OK: D-01.1 schema matches')
"

# G5 — v1 legacy completamente removido (zero referências)
grep -rE "from aegis_phase1\.nodes|from aegis_phase1\.subphases|from aegis_phase1\.graph import|from aegis_phase1\.shared\.document_producer|from aegis_phase1\.run_with_iteration|from aegis_phase1\.section_refill|from aegis_phase1\.doc_evaluator" src/ tests/ 2>&1 | head -5
# Expected: empty
! grep -rE "SubDomainLoader|_parse_yaml_frontmatter|HEADER_RE" src/aegis_phase1/v2/ 2>&1 | head -5
# Expected: empty (v2 não usa regex de MDs)

# G6 — Tests verdes
pytest tests/unit/v2/loader/ -v
# Expected: 0 FAILED, 0 ERROR
pytest tests/unit/v2/ -v --co -q 2>&1 | grep -E "^(ERROR|ModuleNotFoundError)" | head -5
# Expected: empty (collection clean)

# G7 — Lint + typecheck
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/aegis_phase1/v2/loader/preproc_catalog.py src/aegis_phase1/v2/loader/case_profile.py

# G8 — Linter/format
pre-commit run --files src/aegis_phase1/v2/loader/preproc_catalog.py src/aegis_phase1/v2/loader/case_profile.py

echo "=== ALL GATES PASSED ==="
```

**Definição de done:** G0–G8 todos PASS + commits sequenciais no branch (sem amend, sem rebase) + pre-push hook valida 17/17 contract checks.

---

## Estrutura de commits

```
feature/aegis-p1-corr-037
├─ commit 1: CORR-037-T1: NEW preproc_catalog.py (PreprocCatalogLoader + Pydantic)
├─ commit 2: CORR-037-T2: NEW case_profile.py (CaseProfileLoader + CompanyContext)
├─ commit 3: CORR-037-T3: REFACTOR orchestrator _load_* to use new loaders
├─ commit 4: CORR-037-T4: REMOVE v1 legacy (graph.py, subphases/, nodes/, shared/, ...)
├─ commit 5: CORR-037-T5: NEW tests (test_preproc_catalog + test_case_profile)
├─ commit 6: CORR-037: update AGENTS.md §1 (remove v1 references)
├─ commit 7 (optional): CORR-037: baseline snapshot post-refactor (output/phase1/baseline_post_corr037/)
```

Cada commit deve deixar o branch num estado coerente (pytest verde, gates passam). Se um commit intermédio quebrar testes, é aceitável **desde que o commit final** deixe tudo PASS.

**Convenção AGENTS.md §10:** 1 branch per contract, sem sub-branches, commits sequenciais, sem amending, sem rebase interativo.

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Pydantic models incompletos (campos do JSON não capturados) | `class Config: extra = "allow"` nos Pydantic models (tolerância a campos extra). Documentar campos não-mapeados como `model_extra`. |
| Cache invalidation em testes | `clear_cache()` exposto; `pytest` fixtures criam novo loader por teste (não reutilizar) |
| Orchestrator refactor quebra callers (v2/runner.py, v2/cli/, v2/reduce/) | Grep `SubDomainLoader\|PreprocessingLoader\|AmbiguityLoader\|ArticleLoader` antes de remover; substituir todas as referências |
| Pre-existing tests em `tests/unit/v2/` dependem de loaders v1 (regex) | Esses testes vão falhar após T3/T4; devem ser actualizados ou removidos no commit 3/4. Documentar como parte do refactor. |
| AI_Act canonical vs aliases | `_REG_NORMALIZE` em `parsers/entities/subdomain.py` (AGENTS.md §11) é o resolver; `preproc_catalog.py` deve usar canonical `AI_Act` |
| `verified_relationship` é FROZEN (strategy §"Princípios metodológicos invioláveis") | `Pair.verified_relationship: str` (não Optional, não Union). PreprocCatalogLoader NÃO modifica este campo. |
| `DORA-CL{NN}-{M}` multi-clause confusion | ID parsing: split on `-CL`, then check for `-{M}` suffix. Tratar `{M}` como integer. |
| `preproc_out/audit/*.json` regenerado pelos audit scripts durante gates | Reverter (igual CORR-036 side-effects). `git checkout -- preproc_out/audit/`. |
| Remoção de v1 quebra `__init__.py` que re-exporta | Verificar `from aegis_phase1 import X` em todos os sites antes de remover |

---

## Pre-flight check (OBRIGATÓRIO antes de cada sub-fase T1-T5)

Per AGENTS.md §10.1:

```bash
$ git branch --show-current
feature/aegis-p1-corr-037

$ git status
nothing to commit, working tree clean

$ python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('OK')"
OK

$ python -c "from aegis_phase1.v2.runner import main; print('OK')"
OK

$ pytest tests/unit/v2/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError"
# Expected: empty
```

Se algum check falhar, abortar a sub-fase, fixar, retomar.

---

## Métricas esperadas

- **Linhas adicionadas (código):** ~800 (T1: 300 + T2: 150 + T3: refactor ± + T5: 350)
- **Linhas removidas (código):** ~5000 (T4)
- **Net LOC:** -4200 (de ~8000 v1+v2 para ~3800 só v2)
- **Ficheiros novos:** 5 (2 loaders + 2 test files + contract)
- **Ficheiros removidos:** 7 (graph.py + 4 dirs + 3 .py)
- **Ficheiros modificados:** 2 (orchestrator.py + AGENTS.md)
- **Commits:** 5-7 (sequenciais, sem squash, sem amend)
- **Duração estimada:** 3-5 sessões (cada T é uma sessão)

---

## Pós-CORR-037

Próximos contracts (sequência da estratégia):

| SP | Contract | Foco |
|----|----------|------|
| B | **CORR-038** (`feature/aegis-p1-corr-038`) | ApplicabilityContext + Doc 04 + Doc 05 (primeiro output verificável) |
| C | **CORR-039** (`feature/aegis-p1-corr-039`) | ClauseMappingContext + Doc 06 + FIX crítico `catalog_loader=None` + 4 P1B-LLM calls com catálogos wired |
| D | **CORR-040** (`feature/aegis-p1-corr-040`) | DomainActivationContext + P1C-LLM-01 + Doc 07 matrix + Track B (Doc 07b) |
| E | **CORR-041** (`feature/aegis-p1-corr-041`) | SynthesisContext + P1C-LLM-03 + P1C-LLM-02 + outputs finais (04a-d) + parity check 9 outputs |

**Critério de sucesso global (pós CORR-041):**

```bash
python -m aegis_phase1.v2.runner --run-all cases/case1-tinytask
# produz 9 outputs (04/04a/04b/04c/04d/05/06/07/07b + xlsx) com diff semântico
# ≤ threshold vs Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/,
# lendo exclusivamente preproc_out/ JSON (zero regex na stage LOAD) e
# 5 LLMs canónicos invocados com catálogos wired.
```

---

## Change log

- 2026-07-21: v1.0 — contract inicial criado pelo orchestrator após
  merge de CORR-036 (`2a63271`) a main. Branch `feature/aegis-p1-corr-037`
  criada a partir do main actualizado. Contrato define T1-T5 com API
  pública, Pydantic models, testes, gates, e estrutura de commits.
  Implementação começa em sessão seguinte.
