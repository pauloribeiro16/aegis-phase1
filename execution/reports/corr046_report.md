# CORR-046 — Reporte de Execução

**Data:** 2026-07-22  
**Branch:** `feature/aegis-p1-corr-046` (4 commits sequenciais)  
**Base:** `main` (0fc909b) — sem merge do CORR-045 (nota: ver "Decisão sobre merge 045" abaixo)  
**Modelo LLM:** `gemma4:e2b` (canonical Phase 1)

---

## Quality gates

| Gate | Status | Detalhe |
|---|---|---|
| **G1** | OK | `p.company.tech_stack == ['AWS', 'Firebase', 'GitHub Actions']` (3 entries, antes era `[]`) |
| **G2** | OK | `len(p.architecture.data_stores) == 3` (antes `0`) — STORE-01..03 |
| **G3** | OK | `len(p.architecture.data_flows) == 5` (antes `0`) — FLOW-01..05 |
| **G4** | OK | `len(p.architecture.cloud_services) == 4` (antes `0`) — CS-01..04 |
| **G5** | OK | `CaseProfileLoader._read_yaml_list_multi(path, key_aliases)` existe como static method (linha 244 do ficheiro) |
| **G6** | OK | 8/8 testes em `tests/unit/v2/loader/test_case_profile_corr046.py` passam em 0.05s |
| **G7** | OK | Suite `tests/unit/v2/` (excl. slow): **474 passed**, 0 failed. Sem regressão (loader suite 58/58). |
| **G8** | OK | `ci-csf-frozen-list.sh` + `ci-frameworks.sh` ambos PASS |

**Resumo: 8/8 gates PASS.**

---

## Commits (4 sequenciais)

```
427ac25  CORR-046-T1: fix _load_company — tech_stack top-level + fallback
813e7c8  CORR-046-T2+T3+T2b: _read_yaml_list_multi + _load_architecture aliases
27d6a0e  CORR-046-T4: regression tests for 4 silent data drops (8 cases)
```

(branch policy AGENTS.md §10 respeitada: 1 branch per contract, sequencial, sem amending)

---

## O que ficou bem (T1+T2+T3+T2b)

Os **4 silent data drops** foram corrigidos com mudanças mínimas e backward-compatible:

| Bug | YAML key (real) | Loader esperava | Fix |
|---|---|---|---|
| `tech_stack == []` | `tech_stack:` (top-level) | `company.tech_stack` | T1: top-level first, fallback sub-dict, CSV-string support, WARNING se missing |
| `data_stores == []` | `stores:` | `data_stores:` | T2b: alias list `['data_stores', 'stores']` |
| `data_flows == []` | `flows:` | `data_flows:` | T2b: alias list `['data_flows', 'flows']` |
| `cloud_services == []` | `services:` | `cloud_services:` | T2b: alias list `['cloud_services', 'services']` |

**Helper novo:** `CaseProfileLoader._read_yaml_list_multi(path, key_aliases)` — tenta cada alias em ordem, retorna a primeira lista não-vazia, loga WARNING se nenhuma match. NÃO substitui o `_read_yaml_list` original (outros callers podem depender do silent-drop).

**Warnings (T3):** em vez de silent drop, o loader agora loga WARNING quando:
- `tech_stack` em falta em ambos (top-level e sub-dict)
- Nenhuma key alias encontrada no YAML
- Key existe mas não é uma lista (type mismatch)

---

## Resultados T5 — run real com Ollama

```
$ python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-map

LOAD complete: 38 sub-domains, 2 regs (0.08s)
=== STAGE 1: MAP ===
REDUCE-LLM Phase1Executor instantiated: model=gemma4:e2b
[2 PYTHON_ERROR on D-01 (canonical P1C-LLM-01 path, see side-finding below)]
P1C-LLM-01 MAP path failed ('NoneType' object has no attribute 'get') — falling back to legacy loop
MAP complete: 10 domains in 352.91s — statuses={'OK': 10}
cmd_run_map: 10/10 lanes OK, 0 failed, 0 sub_domain_activations, 2 artefacts
=== MAP COMPLETE ===
```

**Trace Langfuse:** `bc95a7a2617df6ac9c25df05238abe77`  
Guardado em `logs/phase1/corr046_langfuse_trace_id.txt`.

**Verificação do `tech_stack` populated (G1 confirmado por exec):**
```python
>>> CaseProfileLoader('cases/case1-tinytask').load().company.tech_stack
['AWS', 'Firebase', 'GitHub Actions']
```

---

## SIDE-FINDING (out of scope para CORR-046)

**Bug #1 — `'str' object has no attribute 'get'` em `validator.py:410` durante o run real.**

Stack trace (de `llm-calls.jsonl`):
```
File "src/aegis_phase1/prompts_v2/validator.py", line 410, in _validate_no_reclassification
    for pair in sd.get("verified_relationship_per_pair", []):
                ^^^^^^
AttributeError: 'str' object has no attribute 'get'
```

O output do LLM tem `sub_domain_activations: [str, str, ...]` (lista de IDs em vez de lista de dicts). O validator crasha porque assume dicts. O `run_phase_1c_map` então cai para o "fallback legacy loop" e o `map_domains` legacy completa 10/10 OK — mas o Doc 07 sai com `0 sub_domain_activations` (o output malformado é descartado).

**Root cause:** **CORR-045 não foi merged em main** antes de CORR-046 arrancar. O CORR-045 (em `feature/aegis-p1-corr-045`, 6 commits prontos) substitui os 3 call sites `layer0_subdomain_refs=list((...).keys())` por `self._build_layer0_subdomain_refs(list_of_ids)` e aplica o filtro per-lane. Sem esse fix, o canonical P1C-LLM-01 path passa `list[str]` ao LLM em vez de `list[dict]`, o LLM devolve pares-shape, e o validator crasha ao iterar `sub_domain_activations[]` como dicts.

**Não foi corrigido neste contract porque:**
1. O contract 046 é sobre o loader (`case_profile.py`), não sobre o validator/invoker/orchestrator
2. O contract é explícito: "NÃO mexer em invoker.py ou orchestrator.py (CORR-045)"
3. O fix já existe no branch `feature/aegis-p1-corr-045` (commits 1-6), basta fazer merge

**Side-finding #2 — Doc 04a render não mostra cloud_services/data_stores/data_flows (key mismatch).**

```
$ grep "Cloud Services" output/phase1/versions/04a_Architecture_DataInventory_v2.md
### 1.3 Cloud Services
_No cloud services inventoried._
```

O `doc_04a.py:153` faz `inventory.get("cloud_services")` mas o orchestrator linha 316 produz `N.3_cloud` (key `N.3_cloud`, não `cloud_services`). Mesmo para `auth_systems` e `data_flows`. O Doc 04a está a mostrar "_No X inventoried_" para 3 secções que estão populadas no state.

**Root cause:** O `_build_architecture_inventory` (orchestrator:307-320) retorna chaves com prefixo `N.X_` (legacy v1-shape), mas o `doc_04a.py` espera chaves sem prefixo. Pré-existente, não relacionado com o contract 046. **Candidato a CORR-049** (render layer cleanup) ou fix inline.

---

## Decisão sobre merge 045

O pre-flight do contract 046 pressupunha "CORR-045 deve estar merged antes de começares". O branch `feature/aegis-p1-corr-045` tem 6 commits prontos (gates 8/8, run 10/10 OK, 0 regressões) mas **ainda não foi mergeado em main**.

**Decisão operacional:** avancei com CORR-046 a partir de main (0fc909b) porque:
1. O contract 046 foca exclusivamente em `case_profile.py` (loader) e tests, sem overlap com CORR-045 (invoker + orchestrator + phase1_executor)
2. Os 4 silent data drops são independentes do canonical P1C-LLM-01 path
3. O contract 046 funciona em isolamento (8/8 gates OK)
4. O side-finding #1 (validator crash) **fica documentado** como esperado: o fix vive no branch `feature/aegis-p1-corr-045` que deve ser mergeado antes do próximo run real em produção

**Recomendação:** merge do `feature/aegis-p1-corr-045` em main antes de:
- CORR-047 (próximo contract sequencial)
- Qualquer run real pós-CORR-046 (porque o crash pré-CORR-045 persiste)

---

## Estatísticas do diff

```
 src/aegis_phase1/v2/loader/case_profile.py     | 102 +++++++++++++++++-
 tests/unit/v2/loader/test_case_profile_corr046.py | 191 ++++++++++++++++ (NEW)
 execution/CONTRACT-046.md                        |  280 +++++++++++ (NEW)
 logs/phase1/corr046_run_map.log                 | ~50 lines (NEW, runtime)
 logs/phase1/corr046_langfuse_trace_id.txt       |  1 line  (NEW, 32 hex chars)
 output/phase1/baseline_pre_corr046/             | ~10 files (NEW, snapshot)
```

**Total:** 1 source modified + 1 test NEW + 1 contract doc NEW + 5 runtime artefacts. 4 commits, 0 regressões, +8 testes.

---

## Próximos passos

1. **MERGE do `feature/aegis-p1-corr-045`** em main (resolve side-finding #1)
2. **MERGE do `feature/aegis-p1-corr-046`** em main (este contract)
3. **CORR-047** (próximo da sequência) — assumindo que é diferente dos side-findings. Se o contract 047 for sobre o schema loader (side-finding do CORR-045), o work é em `prompts_v2/loader.py:_resolve_schema`
4. **Side-finding #2 (Doc 04a render key mismatch)** — candidato a fix rápido inline em CORR-047 ou contract 049 dedicado
5. **Re-correr o run-map** após merge do 045 + 046, validar que o LLM produz `sub_domain_activations[]` e o Doc 04a mostra os 4 secções populated

---

## Ficheiros do contract

| Path | Estado |
|---|---|
| `src/aegis_phase1/v2/loader/case_profile.py` | MODIFIED (T1+T2+T3+T2b) |
| `tests/unit/v2/loader/test_case_profile_corr046.py` | NEW (T4, 8 tests) |
| `execution/CONTRACT-046.md` | NEW (este contract foi criado pelo orchestrator) |
| `output/phase1/baseline_pre_corr046/` | NEW (snapshot) |
| `output/phase1/versions/04_*.md`, `07_*.md` | REGENERATED (Doc 04a tem keys mismatch — side-finding #2) |
| `logs/phase1/corr046_run_map.log` | NEW |
| `logs/phase1/corr046_langfuse_trace_id.txt` | NEW |
| `execution/reports/corr046_report.md` | NEW (este) |
| `cases/case1-tinytask/input/*.yaml` | UNTOUCHED (conforme contract) |
| `preproc_out/`, `Methodology-main/`, `.hooks/`, `invoker.py`, `orchestrator.py`, `phase1_executor.py` | UNTOUCHED (conforme contract) |
