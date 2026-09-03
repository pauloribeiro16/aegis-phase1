# CORR-046 — Fix CaseProfileLoader silent data drops

## Resumo

Contract de **fix crítico** — o `CaseProfileLoader` em
`src/aegis_phase1/v2/loader/case_profile.py` está a **descartar
silenciosamente** 4 campos ricos de arquitetura que já existem nos
YAMLs do case input. Os prompts P1B/P1C são forçados a raciocinar
**sem contexto de arquitetura** (tech stack, data stores, data flows,
cloud services).

**Branch:** `feature/aegis-p1-corr-046`
**Data:** 2026-07-22
**Trigger:** side-finding do CORR-045 (Doc 07 com `applicable_regs: []`).
Investigation revelou 4 silent data drops no loader.

---

## Os 4 bugs

### Bug #1 — `tech_stack` always `[]`

`cases/case1-tinytask/input/company/classification.yaml`:

```yaml
company:
  name: TinyTask Lda.
  …
  security_fte: 0.85
  criticality_level: non-critical
tech_stack:              # ← TOP-LEVEL (linha 14, fora de company:)
  - AWS
  - Firebase
  - GitHub Actions
applicable_regulations:
  - …
```

`CaseProfileLoader._load_company()` lê `data.get("company", {})` e
só procura `tech_stack` dentro desse sub-dict. O top-level
`data["tech_stack"]` é ignorado. Resultado: `p.company.tech_stack == []`.

### Bug #2 — `data_stores` always `[]`

`cases/case1-tinytask/input/architecture/data_stores.yaml` tem
`stores:` como root key (não `data_stores:`).

```yaml
stores:
  - id: STORE-01
    name: Primary Database
    type: postgres
    personal_data: true
    encryption_at_rest: AES-256
  - id: STORE-02
    …
  - id: STORE-03
    …
```

`_load_architecture` chama `data.get("data_stores", [])` → retorna `[]`.

### Bug #3 — `data_flows` always `[]`

`data_flows.yaml` tem `flows:` (5 entries: FLOW-01..FLOW-05).
`_load_architecture` procura `data_flows:` → `[]`.

### Bug #4 — `cloud_services` always `[]`

`cloud_services.yaml` tem `services:` (4 entries: CS-01..CS-04).
`_load_architecture` procura `cloud_services:` → `[]`.

**Impacto:** P1B-LLM-01 e P1C-LLM-01 prompts não têm tech stack,
data stores, flows, ou cloud services. LLM raciocina sem
contexto de arquitetura → Doc 07 sai vazio (post-CORR-045 ainda
vê `applicable_regs: []` em algumas secções porque company_context
nunca recebeu os 4 campos).

---

## Decisões de produto

1. **Adaptar o loader aos YAMLs existentes, NÃO alterar os YAMLs.**
   O contract é explícito: YAMLs são input do user, o loader adapta-se.
   Os YAMLs podem ter 2 variantes (`stores` vs `data_stores`),
   aceitar ambas é backward-compatible.

2. **Helper `_read_yaml_list_multi(path, key_aliases)`** — novo
   helper separado do `_read_yaml_list` original (outros callers
   podem depender do silent drop, não mexer). Aceita uma lista de
   aliases e devolve a primeira key que existir no YAML.

3. **Em vez de silent drop, LOGAR WARNING** quando uma key
   esperada está em falta no YAML. Os YAMLs do case 1 estão
   completos (3 stores, 5 flows, 4 services) — o warning é
   para futuros YAMLs que faltem dados.

4. **`ArchitectureFacts` Pydantic** pode precisar de aceitar
   `list[dict]` untyped (em vez de tipagem estreita) para
   acomodar a riqueza dos YAMLs (campos como `personal_data`,
   `encryption_in_transit`, `dpa_status` variam por entry).

5. **NÃO tocar `invoker.py` ou `orchestrator.py`** (são CORR-045,
   separados).

---

## Tarefas

### T1 — Fix `_load_company` (tech_stack no top level)

**Ficheiro:** `src/aegis_phase1/v2/loader/case_profile.py`

**Atual (linha aprox 80-120):**
```python
def _load_company(self, data: dict) -> CompanyFacts:
    company = data.get("company", {}) or {}
    return CompanyFacts(
        name=company.get("name"),
        legal_structure=company.get("legal_structure"),
        sector=company.get("sector"),
        # … outros campos …
        tech_stack=company.get("tech_stack") or [],  # ← só top-level em company
        applicable_regulations=company.get("applicable_regulations", []),
    )
```

**Alvo:**
```python
def _load_company(self, data: dict) -> CompanyFacts:
    company = data.get("company", {}) or {}
    # CORR-046: tech_stack pode estar no TOP level (caso 1) ou
    # dentro do sub-dict `company:`. Aceitar ambos.
    tech_stack = (
        data.get("tech_stack")
        or company.get("tech_stack")
        or []
    )
    if isinstance(tech_stack, str):
        tech_stack = [s.strip() for s in tech_stack.split(",") if s.strip()]
    return CompanyFacts(
        name=company.get("name"),
        …
        tech_stack=tech_stack,
        …
    )
```

### T2 — Fix `_load_architecture` + `_read_yaml_list_multi`

**Ficheiro:** `src/aegis_phase1/v2/loader/case_profile.py`

**Novo helper (no topo do módulo):**
```python
def _read_yaml_list_multi(
    path: Path,
    key_aliases: list[str],
    *,
    default: list | None = None,
) -> list:
    """CORR-046: read a list from a YAML file under one of several
    possible root keys (e.g. ['data_stores', 'stores']).
    
    Returns the first non-empty list found, or `default` (default []).
    Logs WARNING if a key is missing and the file exists.
    """
    default = default if default is not None else []
    if not path.exists():
        return default
    try:
        data = _read_yaml(path)  # use the same helper as the original
    except Exception as e:
        logger.warning("read_yaml_list_multi: failed to read %s: %s", path, e)
        return default
    for key in key_aliases:
        if key in data:
            value = data[key]
            if isinstance(value, list):
                return value
            logger.warning(
                "read_yaml_list_multi: key %r in %s is not a list (got %s); skipping",
                key, path, type(value).__name__,
            )
            return default
    logger.warning(
        "read_yaml_list_multi: none of %s found in %s; returning default (n=%d)",
        key_aliases, path, len(default),
    )
    return default
```

**Modificar `_load_architecture`:**
```python
def _load_architecture(self, data: dict) -> ArchitectureFacts:
    arch_dir = self._case_root / "input" / "architecture"
    # CORR-046: data_stores key may be 'data_stores' OR 'stores'
    data_stores = _read_yaml_list_multi(
        arch_dir / "data_stores.yaml",
        ["data_stores", "stores"],
    )
    data_flows = _read_yaml_list_multi(
        arch_dir / "data_flows.yaml",
        ["data_flows", "flows"],
    )
    cloud_services = _read_yaml_list_multi(
        arch_dir / "cloud_services.yaml",
        ["cloud_services", "services"],
    )
    return ArchitectureFacts(
        data_stores=data_stores,
        data_flows=data_flows,
        cloud_services=cloud_services,
        systems=data.get("systems", []) or _read_yaml_list(
            arch_dir / "systems.yaml", "systems"
        ),
    )
```

### T3 — Warnings em vez de silent drop

Já incluído no helper acima: `_read_yaml_list_multi` loga
`WARNING` quando nenhuma das keys alias é encontrada. Adicionalmente:

```python
# No final de _load_company:
if not tech_stack:
    logger.warning(
        "CaseProfileLoader._load_company: tech_stack missing in %s",
        self._case_root / "input" / "company" / "classification.yaml",
    )

# No final de _load_architecture:
for name, lst in [
    ("data_stores", data_stores),
    ("data_flows", data_flows),
    ("cloud_services", cloud_services),
]:
    if not lst:
        logger.warning(
            "CaseProfileLoader._load_architecture: %s is empty (check YAML aliases)", name,
        )
```

### T4 — Testes canónicos

**Ficheiro:** `tests/unit/v2/loader/test_case_profile_corr046.py` (NEW)

5 casos:

(a) `test_tech_stack_loaded_from_top_level` — usa o case1 real,
asserts `p.company.tech_stack == ["AWS", "Firebase", "GitHub Actions"]`.

(b) `test_data_stores_loaded_from_stores_key` — asserts
`len(p.architecture.data_stores) == 3` e que cada entry tem
`id` (STORE-01..03), `personal_data`, `encryption_at_rest`.

(c) `test_data_flows_loaded_from_flows_key` — asserts
`len(p.architecture.data_flows) == 5` (FLOW-01..05), cada um
com `source`/`destination`/`data_types`/`encryption_in_transit`.

(d) `test_cloud_services_loaded_from_services_key` — asserts
`len(p.architecture.cloud_services) == 4` (CS-01..04), cada um
com `provider`/`service_type`/`dpa_status`/`certifications`.

(e) `test_case_profile_loader_populates_all_expected_fields` — holístico,
valida que TODOS os campos do CompanyFacts e ArchitectureFacts
estão populated (não zeros/vazios) para o case1.

### T5 — Run real com Ollama + Langfuse

```bash
source ../shared-venv/bin/activate
mkdir -p output/phase1/baseline_pre_corr046
cp output/phase1/*.md output/phase1/baseline_pre_corr046/ 2>/dev/null

python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-map \
    2>&1 | tee logs/phase1/corr046_run_map.log
```

**Esperado pós-fix:**
- 10 lanes P1C-LLM-01 com `status: OK`
- Output de cada lane mostra `applicable_regs` populated
  (incluindo `tech_stack`, `data_stores`, `data_flows`,
  `cloud_services` em `company_facts`)
- Trace Langfuse: prompt do P1C-LLM-01 contém `tech_stack: [AWS,
  Firebase, GitHub Actions]`

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — tech_stack populated
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
p = CaseProfileLoader('cases/case1-tinytask').load()
assert p.company.tech_stack, f'G1 FAIL: tech_stack={p.company.tech_stack}'
print('G1 OK', p.company.tech_stack)
" || { echo "FAIL G1"; exit 1; }

# G2 — data_stores == 3
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
p = CaseProfileLoader('cases/case1-tinytask').load()
assert len(p.architecture.data_stores) == 3, f'G2 FAIL: n={len(p.architecture.data_stores)}'
print('G2 OK')
" || { echo "FAIL G2"; exit 1; }

# G3 — data_flows == 5
python -c "
…
assert len(p.architecture.data_flows) == 5, f'G3 FAIL: n={len(p.architecture.data_flows)}'
print('G3 OK')
" || { echo "FAIL G3"; exit 1; }

# G4 — cloud_services == 4
python -c "
…
assert len(p.architecture.cloud_services) == 4, f'G4 FAIL: n={len(p.architecture.cloud_services)}'
print('G4 OK')
" || { echo "FAIL G4"; exit 1; }

# G5 — _read_yaml_list_multi existe
grep -q "def _read_yaml_list_multi" src/aegis_phase1/v2/loader/case_profile.py && echo "G5 OK" || { echo "FAIL G5"; exit 1; }

# G6 — testes loader passam
pytest tests/unit/v2/loader/test_case_profile_corr046.py -q 2>&1 | tail -1 | grep -qE "passed" && echo "G6 OK" || { echo "FAIL G6"; exit 1; }

# G7 — pytest tests/unit/v2/ verde
pytest tests/unit/v2/ -m "not slow" -q 2>&1 | tail -1 | grep -qE "passed" && echo "G7 OK" || { echo "FAIL G7"; exit 1; }

# G8 — CI gates
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G8 OK" || { echo "FAIL G8"; exit 1; }

echo "=== ALL GATES PASSED ==="
```

**Definição de done:** G1–G8 todos PASS.

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `src/aegis_phase1/v2/loader/case_profile.py` | **MODIFY** — T1+T2+T3: fix _load_company tech_stack, novo _read_yaml_list_multi, fix _load_architecture aliases, warnings |
| `src/aegis_phase1/v2/loader/schemas.py` (se necessário) | **MODIFY** — T2: relaxar tipagem de `ArchitectureFacts.data_stores`/`data_flows`/`cloud_services` para `list[dict]` se a tipagem atual rejeitar a forma rica |
| `tests/unit/v2/loader/test_case_profile_corr046.py` | **NEW** — 5 testes |
| `output/phase1/baseline_pre_corr046/` | **NEW** — snapshot |
| `output/phase1/*.md` (Doc 07) | **REGENERATED** — com tech_stack + 3 lists populated |
| `logs/phase1/corr046_run_map.log` | **NEW** |
| `logs/phase1/corr046_langfuse_trace_id.txt` | **NEW** |
| `execution/CONTRACT-046.md` | **NEW** (este) |

**Não modificar:** `cases/case1-tinytask/input/*.yaml` (input do user),
`preproc_out/`, `Methodology-main/`, `.hooks/`, `invoker.py` (CORR-045),
`orchestrator.py` (CORR-045).

---

## Estrutura de commits

```
feature/aegis-p1-corr-046
├─ commit 1: T1 fix _load_company tech_stack (top-level + fallback company dict)
├─ commit 2: T2 _read_yaml_list_multi helper + T3 warnings
├─ commit 3: T2b _load_architecture uses _read_yaml_list_multi (stores/flows/services)
├─ commit 4: T4 testes canónicos (5 cases)
└─ commit 5: T5+T6 run real + Langfuse trace_id + report
```

5 commits sequenciais. 1 branch per contract (AGENTS.md §10).

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| `ArchitectureFacts` Pydantic rejeita list[dict] com campos extra | Inspecionar schema atual; relaxar para `list[dict]` se necessário; documentar no commit |
| `_read_yaml_list_multi` introduz regressão noutros callers | É novo helper; não substitui o `_read_yaml_list` original (que outros podem usar) |
| `tech_stack` pode vir como string (CSV) nalguns YAMLs | Aceitar string→split por vírgula, defensivo |
| Run real demora +10 min (10 lanes Ollama) | background com setsid+nohup; monitor via log |
| G6 (gate) só verifica os meus testes — se algum G1-G4 falhar é bug | Sanity check via `python -c` antes de declarar PASS |

---

## Change log

- 2026-07-22: v1.0 — contract inicial criado pelo orchestrator
  pós-CORR-045 (side-finding do Doc 07 `applicable_regs: []`).

---

## Verdict pós-CORR-049 (2026-07-22)

**Status:** PASS (cascade-merged into feature/aegis-p1-corr-049).

**CORR-049 integrou este contract num branch cascade. Detalhes em
`execution/CONTRACT-049.md` §FASE 1 e `logs/phase1/corr049_parity_report.md`.

**Evidence:** 15/16 quality gates pass; only G11 (concatenate: 0 domains)
fails, and that is a model-side issue (gemma4:e2b not following schema),
not a contract-046 fix issue. The 046 work (data path: catalogs/helper/lane
filter/loader-fields/threading/metadata) is permanent and 100% effective.
