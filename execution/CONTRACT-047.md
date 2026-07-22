# CORR-047 — Enrich CompanyContext com 4 novos YAMLs

## Resumo

Contract de **enriquecimento** — o pipeline carrega ~25 campos do
CompanyContext, mas a methodology AEGIS-KG (`INTAKE_FORM.md` v2.1)
exige ~150 campos em 8 camadas. Este contract adiciona **4
CATEGORIAS NOVAS** de dados que não existem em lado nenhum hoje:

1. **`implementation_readiness.yaml`** — IR-01..IR-12 (12 áreas ×
   YES/NO/PARTIAL). Deliverable obrigatório methodology §6. Sem
   isto, Doc 04b não tem conteúdo real (capability assessment).
2. **`interactions.yaml`** — Layer 3 scans (temporal_conflicts,
   requirement_conflicts, trigger_mismatches, negative_analyses).
   Obrigatório quando ≥2 regs aplicáveis (case1 tem GDPR+CRA).
3. **`regulatory_classification.yaml`** — enums `nis2_entity_class`,
   `dora_article_2_entity`, `cra_product_class`,
   `ai_system_classification`, `critical_or_important_ict`.
4. **`role_matrix.yaml`** — 5 regs × {role, native_compliance,
   inherited_obligations, notes}.

**Branch:** `feature/aegis-p1-corr-047`
**Data:** 2026-07-22
**Trigger:** gap analysis pós-CORR-046 — loader agora tem 25 fields
mas Doc 04b/05/07 continuam a renderizar com placeholders.

---

## Pré-flight (validado pelo orchestrator)

```
$ git branch --show-current
feature/aegis-p1-corr-047       # ← branch criada pelo executor

$ ls cases/case1-tinytask/input/company/
business_goals.yaml
classification.yaml
stakeholders.yaml               # ← 3 YAMLs, faltam 2 (impl_readiness, regulatory_classification, role_matrix)

$ ls cases/case1-tinytask/input/regulatory/
applicability.yaml             # ← 1 YAML, falta 1 (interactions)

$ grep -nE "implementation_readiness|regulatory_interactions|RegulatoryClassification|RoleMatrix" \
       src/aegis_phase1/v2/loader/case_profile.py src/aegis_phase1/v2/state.py
(vazio — nenhum dos 4 fields existe no loader ou nos models)
```

---

## Decisões de produto

1. **Schemas Pydantic PRIMEIRO** (T1 antes de T2). Os YAMLs seguem
   o shape dos Pydantic models; o loader valida via
   `model_validate()`; testes verificam shape.

2. **Loader tolerante** (igual ao CORR-046): YAML falta → WARNING +
   `None`. Não crash. Não bloqueia runs de outros cases.

3. **Dados YAML realistas** mas marcados com `# verify with company`
   em valores estimados (ex: ciso=NO, dpo=NO, IR=PARTIAL — não
   inventamos; o company confirma). Enums oficiais dos regulamentos
   (CRA CLASS_I, NIS2 NOT_APPLICABLE, etc.) **não** precisam de
   `# verify` porque vêm das próprias regulamentações.

4. **Não fazer threading** destes campos nos prompts (escopo do
   CORR-048). O contract 047 fecha só a **camada de dados**;
   threading no Doc 04b/05/07 e nos LLM inputs é separado.

5. **1 branch per contract** (AGENTS.md §10) — 5 commits
   sequenciais.

---

## Tarefas

### T1 — Schemas Pydantic (8 models)

**Ficheiro:** `src/aegis_phase1/v2/state.py` (adicionar no fim do
ficheiro, antes de `__all__` se existir).

**Modelos a criar** (com `_TolerantModel`-style: `extra="allow"`,
`str_strip_whitespace=True`):

```python
# === Implementation Readiness (Doc 04b capability assessment) ===

class ReadinessState(str, Enum):
    """YES / NO / PARTIAL — the 3 states for an IR area."""
    YES = "YES"
    NO = "NO"
    PARTIAL = "PARTIAL"


class ImplementationReadiness(_TolerantModel):
    """12 readiness areas (IR-01..IR-12), per methodology §6.

    Areas (post-CORR-036 TinyTask baseline):
      IR-01: CISO appointed
      IR-02: DPO appointed
      IR-03: Information security policy (ISP) defined
      IR-04: Risk assessment methodology
      IR-05: Incident response plan
      IR-06: Business continuity / DR
      IR-07: Backup policy
      IR-08: Access control / RBAC
      IR-09: Vulnerability management
      IR-10: Third-party risk management
      IR-11: Security awareness training
      IR-12: Audit logging / SIEM
    """
    ciso: ReadinessState = ReadinessState.NO
    dpo: ReadinessState = ReadinessState.NO
    information_security_policy: ReadinessState = ReadinessState.NO
    risk_assessment: ReadinessState = ReadinessState.NO
    incident_response: ReadinessState = ReadinessState.NO
    business_continuity: ReadinessState = ReadinessState.NO
    backup: ReadinessState = ReadinessState.NO
    access_control: ReadinessState = ReadinessState.NO
    vulnerability_management: ReadinessState = ReadinessState.NO
    third_party_risk: ReadinessState = ReadinessState.NO
    security_awareness: ReadinessState = ReadinessState.NO
    audit_logging: ReadinessState = ReadinessState.NO


# === Regulatory Classification (5 enums) ===

class NIS2EntityClass(str, Enum):
    """NIS2 Art. 5 — entity classification."""
    ESSENTIAL = "ESSENTIAL"
    IMPORTANT = "IMPORTANT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DORAClassification(str, Enum):
    """DORA Art. 2 — entity classification."""
    FINANCIAL_ENTITY = "FINANCIAL_ENTITY"
    ICT_THIRD_PARTY = "ICT_THIRD_PARTY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CRAProductClass(str, Enum):
    """CRA Annex III — product criticality class."""
    CLASS_I = "CLASS_I"      # default: critical products
    CLASS_II = "CLASS_II"    # non-critical but regulated
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AISystemClass(str, Enum):
    """AI Act Art. 6 + Annex III — risk classification."""
    PROHIBITED = "PROHIBITED"
    HIGH_RISK = "HIGH_RISK"
    LIMITED_RISK = "LIMITED_RISK"
    MINIMAL_RISK = "MINIMAL_RISK"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CriticalOrImportantICT(str, Enum):
    """DORA Art. 6 — whether the ICT supports critical/important functions."""
    YES = "YES"
    NO = "NO"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RegulatoryClassification(_TolerantModel):
    """Per-regulation classification (5 enums)."""
    nis2_entity_class: NIS2EntityClass = NIS2EntityClass.NOT_APPLICABLE
    dora_article_2_entity: DORAClassification = DORAClassification.NOT_APPLICABLE
    cra_product_class: CRAProductClass = CRAProductClass.NOT_APPLICABLE
    ai_system_classification: AISystemClass = AISystemClass.NOT_APPLICABLE
    critical_or_important_ict: CriticalOrImportantICT = CriticalOrImportantICT.NOT_APPLICABLE


# === Role Matrix (5 regs × role) ===

class RoleMatrixEntry(_TolerantModel):
    """One regulation's role in the case."""
    role: str = ""                       # e.g. "controller", "manufacturer"
    native_compliance: bool = False       # does the company natively comply?
    inherited_obligations: list[str] = Field(default_factory=list)
    notes: str = ""


class RoleMatrix(_TolerantModel):
    """5 regulations × role entries."""
    gdpr: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)
    cra: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)
    nis2: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)
    dora: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)
    ai_act: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)


# === Regulatory Interactions (Layer 3 scans) ===

class RegulatoryConflictType(str, Enum):
    TEMPORAL = "TEMPORAL"           # breach notification timeline differs
    REQUIREMENT = "REQUIREMENT"     # obligation conflicts across regs
    TRIGGER = "TRIGGER"             # trigger event definitions differ
    NEGATIVE = "NEGATIVE"           # absent obligation that should be present


class RegulatoryInteraction(_TolerantModel):
    """One cross-regulation interaction (e.g. GDPR-CRA temporal conflict)."""
    id: str
    type: RegulatoryConflictType
    regulations: list[str] = Field(default_factory=list)  # e.g. ["GDPR", "CRA"]
    sub_domains: list[str] = Field(default_factory=list)  # e.g. ["D-04.3"]
    description: str = ""
    resolution: str = ""


class NegativeAnalysisItem(_TolerantModel):
    """One negative analysis finding (what SHOULD apply but DOESN'T)."""
    id: str
    description: str
    expected_regulations: list[str] = Field(default_factory=list)
    severity: str = "LOW"            # LOW / MEDIUM / HIGH


class RegulatoryInteractions(_TolerantModel):
    """Container for Layer 3 scans."""
    temporal_conflicts: list[RegulatoryInteraction] = Field(default_factory=list)
    requirement_conflicts: list[RegulatoryInteraction] = Field(default_factory=list)
    trigger_mismatches: list[RegulatoryInteraction] = Field(default_factory=list)
    negative_analyses: list[NegativeAnalysisItem] = Field(default_factory=list)
```

**Notas:**
- Usar `Enum` do `enum` module, `str` mixin para serialização JSON
  directa.
- `_TolerantModel` é a base em `case_profile.py:46-49` — mas está
  em `case_profile.py`, não em `state.py`. Em vez de importar
  (risco de cycle), definir uma cópia local em `state.py` com o
  mesmo comportamento (`extra="allow"`, `str_strip_whitespace=True`).
- `Field(default_factory=RoleMatrixEntry)` para default factory;
  não pode ser `RoleMatrixEntry()` directo senão é shared mutable.
- `RoleMatrixEntry.role` default `""` em vez de `None` para
  serialização limpa (vai renderizar como campo vazio, não `null`).

### T2 — 4 YAMLs em cases/case1-tinytask/input/

**Ficheiro A:** `cases/case1-tinytask/input/company/implementation_readiness.yaml`

```yaml
# AEGIS Phase 1 — Implementation Readiness (TinyTask Lda.)
# 12 readiness areas (IR-01..IR-12), per methodology §6.
# This file feeds Doc 04b (Security Posture) capability matrix.
# Values are PLACEHOLDERS — verify with company before applying.
ciso: NO                        # IR-01: verify with company
dpo: NO                         # IR-02: verify with company
information_security_policy: PARTIAL  # IR-03: ad-hoc policies exist
risk_assessment: NO             # IR-04: no formal risk methodology
incident_response: PARTIAL      # IR-05: runbook exists for GDPR 72h
business_continuity: NO         # IR-06: verify with company
backup: YES                     # IR-07: automated daily backups in place
access_control: PARTIAL         # IR-08: RBAC exists, no formal review
vulnerability_management: PARTIAL  # IR-09: dependabot + manual scans
third_party_risk: NO            # IR-10: no formal sub-processor register
security_awareness: NO          # IR-11: no formal training program
audit_logging: PARTIAL          # IR-12: app logs yes, SIEM no
```

**Ficheiro B:** `cases/case1-tinytask/input/regulatory/interactions.yaml`

```yaml
# AEGIS Phase 1 — Regulatory Interactions (Layer 3 scans)
# Required when ≥2 regulations apply (TinyTask: GDPR + CRA).
# Captures temporal/requirement conflicts, trigger mismatches,
# and negative analyses (what SHOULD apply but doesn't).
temporal_conflicts:
  - id: TI-01
    type: TEMPORAL
    regulations: [GDPR, CRA]
    sub_domains: [D-04.3]
    description: >
      GDPR Art. 33 requires 72h breach notification to the DPA;
      CRA Art. 14 requires 24h for actively exploited vulnerabilities.
      Single incident may need parallel reporting under both regimes.
    resolution: >
      Adopt the maximum-SLA workflow (24h internal escalation) so
      both regimes are satisfied from the same detection pipeline.
requirement_conflicts: []       # none identified at intake
trigger_mismatches: []          # none identified at intake
negative_analyses:
  - id: NA-01
    description: >
      CRA conformity assessment (Annex VIII) is required for CLASS_I
      products but no formal assessment programme is in place.
    expected_regulations: [CRA]
    severity: MEDIUM
  - id: NA-02
    description: >
      No Data Protection Impact Assessment (DPIA) on file despite
      systematic large-scale monitoring of EU data subjects.
    expected_regulations: [GDPR]
    severity: HIGH
  - id: NA-03
    description: >
      No formal sub-processor register despite 3 cloud providers
      (AWS, Stripe, Auth0) processing personal data.
    expected_regulations: [GDPR]
    severity: MEDIUM
  - id: NA-04
    description: >
      Vulnerability management does not cover CRA Annex I §2
      handled products (no SBOM, no coordinated disclosure).
    expected_regulations: [CRA]
    severity: MEDIUM
  - id: NA-05
    description: >
      No incident response playbook for CRA actively-exploited
      vuln path (24h SLA differs from GDPR 72h).
    expected_regulations: [CRA]
    severity: MEDIUM
```

**Ficheiro C:** `cases/case1-tinytask/input/company/regulatory_classification.yaml`

```yaml
# AEGIS Phase 1 — Regulatory Classification (per regulation)
# 5 enums: NIS2 entity class, DORA Art. 2 entity, CRA product
# class, AI Act risk class, DORA critical/important ICT.
# Values come from the regulations themselves, not company input.
nis2_entity_class: NOT_APPLICABLE         # TinyTask is a SaaS provider, not Annex I/II
dora_article_2_entity: NOT_APPLICABLE     # not a financial entity
cra_product_class: CLASS_I                # default for digital products w/ personal data
ai_system_classification: NOT_APPLICABLE  # no high-risk AI system in scope
critical_or_important_ict: NOT_APPLICABLE  # DORA not applicable
```

**Ficheiro D:** `cases/case1-tinytask/input/company/role_matrix.yaml`

```yaml
# AEGIS Phase 1 — Role Matrix (5 regulations × role)
# Captures the company's role per regulation + native compliance
# status + inherited obligations + notes.
gdpr:
  role: controller
  native_compliance: false
  inherited_obligations:
    - Article 30 records of processing
    - Article 32 security of processing
    - Article 33 breach notification
    - Article 35 DPIA (when high-risk)
  notes: "Verify with company — controllers may have processor addendums with cloud providers"
cra:
  role: manufacturer
  native_compliance: false
  inherited_obligations:
    - Annex I essential cybersecurity requirements
    - Annex VII conformity assessment
    - Annex VIII CE marking + technical documentation
    - Article 14 vulnerability handling (24h SLA)
  notes: "Placing digital products on EU market as manufacturer"
nis2:
  role: not_applicable
  native_compliance: false
  inherited_obligations: []
  notes: "TinyTask is not an Annex I/II entity; SaaS provider to NIS2 entities is not directly in scope"
dora:
  role: not_applicable
  native_compliance: false
  inherited_obligations: []
  notes: "Not a financial entity; DORA obligations do not apply directly. May be ICT third-party service provider to DORA entities (verify with company)"
ai_act:
  role: not_applicable
  native_compliance: false
  inherited_obligations: []
  notes: "No high-risk AI system in current product (verify with company — no biometric categorisation, no critical infrastructure, no education scoring, no employment, no essential services)"
```

### T3 — Estender CompanyProfile + 4 load* methods

**Ficheiro:** `src/aegis_phase1/v2/loader/case_profile.py`

**Adicionar no fim do módulo (após `_read_yaml_list_multi`):**

```python
# === CORR-047: import Pydantic models from state.py ===
# Import here (not at top) to avoid circular imports.

# === CompanyProfile extension ===
# Add 4 fields to CompanyProfile:
#   implementation_readiness: ImplementationReadiness | None
#   regulatory_classification: RegulatoryClassification | None
#   role_matrix: RoleMatrix | None
#   regulatory_interactions: RegulatoryInteractions | None

# In load(), call new methods and pass results to CompanyProfile:
#   implementation_readiness=self._load_implementation_readiness(),
#   regulatory_classification=self._load_regulatory_classification(),
#   role_matrix=self._load_role_matrix(),
#   regulatory_interactions=self._load_regulatory_interactions(),

# New methods (all tolerant: WARNING + None if YAML missing):

def _load_implementation_readiness(self) -> ImplementationReadiness | None:
    path = self.input_dir / "company" / "implementation_readiness.yaml"
    if not path.exists():
        logger.warning(
            "_load_implementation_readiness: missing %s; setting None "
            "(Doc 04b will render capability matrix as empty)",
            path,
        )
        return None
    try:
        return ImplementationReadiness.model_validate(self._read_yaml(path))
    except Exception as e:
        logger.warning(
            "_load_implementation_readiness: failed to parse %s: %s; setting None",
            path, e,
        )
        return None


def _load_regulatory_classification(self) -> RegulatoryClassification | None:
    path = self.input_dir / "company" / "regulatory_classification.yaml"
    if not path.exists():
        logger.warning("_load_regulatory_classification: missing %s; setting None", path)
        return None
    try:
        return RegulatoryClassification.model_validate(self._read_yaml(path))
    except Exception as e:
        logger.warning(
            "_load_regulatory_classification: failed to parse %s: %s; setting None",
            path, e,
        )
        return None


def _load_role_matrix(self) -> RoleMatrix | None:
    path = self.input_dir / "company" / "role_matrix.yaml"
    if not path.exists():
        logger.warning("_load_role_matrix: missing %s; setting None", path)
        return None
    try:
        return RoleMatrix.model_validate(self._read_yaml(path))
    except Exception as e:
        logger.warning(
            "_load_role_matrix: failed to parse %s: %s; setting None", path, e,
        )
        return None


def _load_regulatory_interactions(self) -> RegulatoryInteractions | None:
    path = self.input_dir / "regulatory" / "interactions.yaml"
    if not path.exists():
        logger.warning("_load_regulatory_interactions: missing %s; setting None", path)
        return None
    try:
        return RegulatoryInteractions.model_validate(self._read_yaml(path))
    except Exception as e:
        logger.warning(
            "_load_regulatory_interactions: failed to parse %s: %s; setting None",
            path, e,
        )
        return None
```

**Notas:**
- `ImplementationReadiness` etc. são importados de `state.py`. Para
  evitar circular import, fazer import lazy dentro de cada método
  (ou no topo do `case_profile.py` com `if TYPE_CHECKING`).
- WARNING (não ERROR) porque a ausência de YAML é tolerável.
- Default `None` (não `ImplementationReadiness()` vazio) para
  distinguir "presente mas vazio" de "ausente".

### T4 — Testes

**Ficheiro:** `tests/unit/v2/loader/test_case_profile_corr047.py` (NEW)

5 casos:

(a) `test_implementation_readiness_loaded` — usa o case1 real,
asserts `p.implementation_readiness is not None` e que tem
12 areas (ciso, dpo, isp, ..., audit_logging) com valores enum
válidos (`YES`/`NO`/`PARTIAL`).

(b) `test_regulatory_classification_loaded` — asserts
`p.regulatory_classification is not None` e que
`cra_product_class == "CLASS_I"` e `nis2_entity_class ==
"NOT_APPLICABLE"`.

(c) `test_role_matrix_loaded` — asserts `p.role_matrix is not None`
e que `gdpr.role == "controller"`, `nis2.role == "not_applicable"`.

(d) `test_regulatory_interactions_loaded` — asserts
`p.regulatory_interactions is not None` e que tem 1
`temporal_conflicts` (TI-01) e 5 `negative_analyses`
(NA-01..NA-05).

(e) `test_loader_tolerates_missing_yaml` — constrói um case
temporário SEM os 4 YAMLs novos (só com os 3 originais) e verifica
que `load()` retorna com sucesso, com `implementation_readiness`,
`regulatory_classification`, `role_matrix`, `regulatory_interactions`
todos `None`, e que 4 WARNING são logados.

### T5 — Smoke test

```bash
source ../shared-venv/bin/activate
PYTHONPATH=src python -c "
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
p = CaseProfileLoader('cases/case1-tinytask').load()
print('implementation_readiness:', p.implementation_readiness)
print('regulatory_classification:', p.regulatory_classification)
print('role_matrix:', p.role_matrix)
print('regulatory_interactions:', p.regulatory_interactions)
"
```

**Esperado:** os 4 campos populated (não None) com dados realistas.

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — 4 YAMLs existem
test -f cases/case1-tinytask/input/company/implementation_readiness.yaml && \
test -f cases/case1-tinytask/input/company/regulatory_classification.yaml && \
test -f cases/case1-tinytask/input/company/role_matrix.yaml && \
test -f cases/case1-tinytask/input/regulatory/interactions.yaml && \
echo "G1 OK" || { echo "FAIL G1"; exit 1; }

# G2 — 4 fields no CompanyProfile
PYTHONPATH=src python -c "
from aegis_phase1.v2.loader.case_profile import CompanyProfile
fields = {f for f in CompanyProfile.model_fields}
required = {'implementation_readiness', 'regulatory_classification', 'role_matrix', 'regulatory_interactions'}
assert required.issubset(fields), f'G2 FAIL: missing {required - fields}'
print('G2 OK', sorted(required))
" || { echo "FAIL G2"; exit 1; }

# G3 — Loader populates 4 fields para case1
PYTHONPATH=src python -c "
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
p = CaseProfileLoader('cases/case1-tinytask').load()
assert p.implementation_readiness is not None, 'G3 FAIL: impl_readiness is None'
assert p.regulatory_classification is not None, 'G3 FAIL: reg_class is None'
assert p.role_matrix is not None, 'G3 FAIL: role_matrix is None'
assert p.regulatory_interactions is not None, 'G3 FAIL: reg_interactions is None'
print('G3 OK')
" || { echo "FAIL G3"; exit 1; }

# G4 — testes loader passam
pytest tests/unit/v2/loader/test_case_profile_corr047.py -q 2>&1 | tail -1 | grep -qE "passed" && echo "G4 OK" || { echo "FAIL G4"; exit 1; }

# G5 — pytest tests/unit/v2/ verde (sem slow)
pytest tests/unit/v2/ -m "not slow" -q 2>&1 | tail -1 | grep -qE "passed" && echo "G5 OK" || { echo "FAIL G5"; exit 1; }

# G6 — CI gates
bash .hooks/ci-csf-frozen-list.sh 2>&1 | tail -1 | grep -q "OK" && \
bash .hooks/ci-frameworks.sh 2>&1 | tail -1 | grep -q "OK" && \
echo "G6 OK" || { echo "FAIL G6"; exit 1; }

echo "=== ALL GATES PASSED ==="
```

**Definição de done:** G1–G6 todos PASS.

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `src/aegis_phase1/v2/state.py` | **MODIFY** — adicionar 8 Pydantic models no fim |
| `cases/case1-tinytask/input/company/implementation_readiness.yaml` | **NEW** — 12 IR areas |
| `cases/case1-tinytask/input/company/regulatory_classification.yaml` | **NEW** — 5 enums |
| `cases/case1-tinytask/input/company/role_matrix.yaml` | **NEW** — 5 regs × role |
| `cases/case1-tinytask/input/regulatory/interactions.yaml` | **NEW** — Layer 3 scans |
| `src/aegis_phase1/v2/loader/case_profile.py` | **MODIFY** — 4 fields em CompanyProfile + 4 load* methods |
| `tests/unit/v2/loader/test_case_profile_corr047.py` | **NEW** — 5 testes |
| `execution/CONTRACT-047.md` | **NEW** (este) |

**Não modificar:** `invoker.py`, `orchestrator.py`, `graph.py`,
`preproc_out/`, `Methodology-main/`, `.hooks/`, prompts threading
(é CORR-048).

---

## Estrutura de commits

```
feature/aegis-p1-corr-047
├─ commit 1: T1 Pydantic models em state.py (8 models)
├─ commit 2: T2 4 YAMLs em cases/case1-tinytask/input/
├─ commit 3: T3 case_profile.py — 4 fields + 4 load* methods
├─ commit 4: T4 test_case_profile_corr047.py (5 cases)
└─ commit 5: T5 smoke test + report
```

5 commits sequenciais. 1 branch per contract (AGENTS.md §10).

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| `_TolerantModel` está em `case_profile.py`, não `state.py` | Definir cópia local em `state.py` (mesmo `extra="allow"`, `str_strip_whitespace=True`); sem cycle |
| `Enum` `str` mixin para serialização JSON | Usar `str, Enum` (não `Enum` puro); validação automática via Pydantic v2 |
| YAML values com strings em vez de Enum (ex: `"NO"` vs `NO`) | YAML serializa strings como strings; `model_validate` faz o cast via `Enum(value)` |
| `RoleMatrixEntry` default `RoleMatrixEntry()` é shared mutable | Usar `default_factory=RoleMatrixEntry` em Field |
| `load()` ainda não chama os novos métodos | Editar `load()` para incluir as 4 chamadas; testar com python -c |
| Threading nos prompts é separado | Não fazer threading neste contract (CORR-048) |

---

## Change log

- 2026-07-22: v1.0 — contract criado pelo orchestrator (recriado
  a partir do briefing da missão; o ficheiro `CONTRACT-047.md`
  original não foi encontrado no repositório — possível perda
  durante transições de branch).
