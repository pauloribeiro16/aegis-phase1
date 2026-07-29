# CORR-069 — Fix 7 pre-existing test failures (de uma vez por todas)

## Resumo

Contract **focado** (3-4 sprints, ~2h trabalho), resolve os 7 testes
pré-existentes que falham desde antes do CORR-068. **Nenhum está
relacionado com os 5 bugs do CORR-068** — todos são bugs
independentes em tests ou fixtures.

**7 testes que falham (todos pré-existentes, validados pós-CORR-067 e pós-CORR-068):**

| # | Teste | Causa raíz | Tipo |
|---|---|---|---|
| 1-4 | `test_validator_schema_loading_corr049` (×4 testes) | Fixture do test não passa `output_schemas_path` ao `Phase1Validator`; logo `_schemas = {}` e `_resolve_schema` retorna `{}` | Test mal escrito |
| 5 | `test_extract_usage_empty_returns_zeros` | `_extract_usage` faz char-based estimate quando `total_tokens == 0` mesmo se content for vazio; test espera `{0,0,0}` | Test mal escrito (a função está OK, é um fallback defensivo) |
| 6 | `test_unified_invoker_init_defaults` | `UnifiedInvoker.__init__` agora passa `num_ctx=32768, num_gpu=99` (defaults CORR-056); test foi escrito antes sem esses kwargs | Test mal escrito (a função está OK, é melhor comportamento) |
| 7 | `test_load_case_config_typed` (flaky) | `test_get_invoker_minimax_corr067.py` polui `os.environ` no module-level (`os.environ["OLLAMA_MODEL"] = "should-be-ignored-model"`) sem restaurar; testes no mesmo worker veem o valor polluted | Test com side-effect global |

**Decisão do utilizador (2026-07-28):** "Faz um novo contrato para resolver isso tudo de uma vez por todas, mas no final não vais correr isso tudo, vais só fazer pequenos testes e testar as seções que estão a dar problemas."

**Branch:** `feature/aegis-p1-corr-069-pre-existing-test-failures`
**Base:** `feature/aegis-p1-corr-068-5-bugfixes` (commit `cdcdee8`)
**Data:** 2026-07-28

---

## Contexto

Após o CORR-068, restaram 7 falhas em `pytest tests/unit/` (de 2689
tests totais). As 7 falhas são estáveis (mesmo número, mesmo conjunto
de tests, em 3+ runs consecutivos). Investigação caso-a-caso revelou:

- **4 falhas** (`test_validator_schema_loading_corr049` × 4): test não
  inicializa o fixture correctamente (falta `output_schemas_path`).
- **1 falha** (`test_extract_usage_empty_returns_zeros`): test
  desactualizado após o fix CORR-021 (que adicionou char-based
  estimate como fallback para LLM constrained generation).
- **1 falha** (`test_unified_invoker_init_defaults`): test
  desactualizado após o fix CORR-056 (que adicionou `num_ctx=32768,
  num_gpu=99` para forçar GPU layers).
- **1 falha** (`test_load_case_config_typed`): flakey quando o
  `test_get_invoker_minimax_corr067` corre antes no mesmo worker
  xdist, porque esse test polui `os.environ` no module-level.

Os 4 primeiros + 1 último são bugs nos tests. Os 2 do meio são
tests desactualizados face a melhoramentos legítimos no código
(CORR-021, CORR-056).

---

## S1 — Fix tests de schema loading (4 tests)

### Hipótese de fix

**File:** `tests/unit/prompts_v2/test_validator_schema_loading_corr049.py`
**Lines:** 23-29 (fixture `validator`)

O fixture só passa `regulatory_baseline_root`, não `output_schemas_path`.
Logo `self._schemas = {}` e `_resolve_schema(spec_id)` retorna `{}`.

Fix: passar o `output_schemas_path` que existe em
`Methodology-main/00_METHODOLOGY/PROMPTS/output_schemas.yaml`.

```python
@pytest.fixture(scope="module")
def validator() -> Phase1Validator:
    return Phase1Validator(
        regulatory_baseline_root=Path(
            "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PREPROCESSING"
        ),
        output_schemas_path=Path(
            "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS/output_schemas.yaml"
        ),
    )
```

### Critérios S1

| # | Critério | Como verificar |
|---|---------|----------------|
| 1 | `test_p1b_llm_01_schema_resolves` passa | `pytest tests/unit/prompts_v2/test_validator_schema_loading_corr049.py -v` |
| 2 | `test_p1c_llm_01_schema_resolves` passa | mesmo |
| 3 | `test_p1c_llm_03_schema_resolves` passa | mesmo |
| 4 | `test_all_5_schemas_loaded` passa | mesmo |
| 5 | Todos os 5 schemas têm `required` + `properties` | mesmo |

---

## S2 — Fix test_extract_usage_empty_returns_zeros

### Hipótese de fix

**File:** `tests/unit/llm/test_unified_invoker_corr013.py`
**Line:** ~268

O test passa um `_FakeAIMessage(content="")` (string vazia) e espera
`usage == {0, 0, 0}`. Mas a função `_extract_usage` faz:

```python
if usage["total_tokens"] == 0:
    content = getattr(response, "content", None)
    if isinstance(content, str) and content:  # ← string vazia é falsy
        usage["completion_tokens"] = _estimate_tokens_by_chars(content)
```

Quando `content=""`, a condição `if ... and content` é False (string
vazia é falsy), então `_estimate_tokens_by_chars` **não é chamado**.
Logo o test deveria passar. Vou ver o que o `_FakeAIMessage` realmente
define.

Vou investigar o test exact e ver se o bug é na função ou no test.

(Ver `S2 detailed analysis` em `execution/CORR-069-VALIDATION-LOG.md`.)

### Critérios S2

| # | Critério | Como verificar |
|---|---------|----------------|
| 1 | `test_extract_usage_empty_returns_zeros` passa | `pytest tests/unit/llm/test_unified_invoker_corr013.py::test_extract_usage_empty_returns_zeros -v` |
| 2 | Comportamento de `_extract_usage` com content vazio documentado | manual inspection |

---

## S3 — Fix test_unified_invoker_init_defaults + test_get_invoker_minimax_corr067 env pollution

### Hipótese de fix

**File 1:** `tests/unit/llm/test_unified_invoker_corr013.py`
**Line:** ~81

O `UnifiedInvoker.__init__` agora passa `num_ctx=32768, num_gpu=99` ao
`ChatOllama` (defaults CORR-056 para forçar GPU layers). O test foi
escrito antes deste fix.

Fix: actualizar o test para esperar os novos kwargs.

```python
MockChatOllama.assert_called_once_with(
    model="gemma4:e4b",
    base_url="http://localhost:11434",
    timeout=120,
    num_ctx=32768,  # CORR-056: default
    num_gpu=99,     # CORR-056: force all layers on GPU
)
```

**File 2:** `tests/unit/prompts_v2/test_get_invoker_minimax_corr067.py`
**Lines:** 25-29 (module-level setenv)

O test polui `os.environ` no module-level sem restaurar. Move os
setenv para um fixture ou usa `monkeypatch`.

```python
# OLD (lines 25-29, module-level):
os.environ["OLLAMA_BASE_URL"] = "http://should-be-ignored:9999"
os.environ["OLLAMA_MODEL"] = "should-be-ignored-model"

# NEW: use a fixture with autouse
@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://should-be-ignored:9999")
    monkeypatch.setenv("OLLAMA_MODEL", "should-be-ignored-model")
    yield
```

### Critérios S3

| # | Critério | Como verificar |
|---|---------|----------------|
| 1 | `test_unified_invoker_init_defaults` passa | `pytest tests/unit/llm/test_unified_invoker_corr013.py::test_unified_invoker_init_defaults -v` |
| 2 | `test_get_invoker_minimax_corr067` tests ainda passam (regression check) | `pytest tests/unit/prompts_v2/test_get_invoker_minimax_corr067.py -v` |
| 3 | `test_load_case_config_typed` passa em 3+ runs consecutivos (não flaky) | `for i in 1 2 3; do pytest tests/unit/ -q; done` |

---

## S4 — Validar (só testes pequenos, sem re-run E2E)

### Actividade

Conforme pedido pelo user: **NÃO** correr o e2e real (S4 do CORR-068).
Validar SÓ com testes pequenos nas secções dos bugs:

1. `pytest tests/unit/prompts_v2/test_validator_schema_loading_corr049.py -v` (4 tests)
2. `pytest tests/unit/llm/test_unified_invoker_corr013.py -v` (inclui o extract_usage)
3. `pytest tests/unit/config/test_case_loader.py -v` (inclui o flaky)
4. `pytest tests/unit/prompts_v2/test_get_invoker_minimax_corr067.py -v` (regression)
5. `pytest tests/unit/ -q` (full suite, confirmar 7 → 0 fail)

### Critérios S4

| # | Critério | Como verificar |
|---|---------|----------------|
| 1 | 4 tests de schema loading passam | crit. S1 |
| 2 | `test_extract_usage_empty_returns_zeros` passa | crit. S2 |
| 3 | `test_unified_invoker_init_defaults` passa | crit. S3 |
| 4 | `test_load_case_config_typed` não-flaky (passa 3/3 runs) | crit. S3 |
| 5 | `test_get_invoker_minimax_corr067` (3 tests) ainda passam | crit. S3 |
| 6 | Full unit test suite: 2689 pass, 0 fail | `pytest tests/unit/ -q` |

---

## Ficheiros a alterar

| Ficheiro | S1 | S2 | S3 | LOC |
|----------|----|----|----|-----|
| `tests/unit/prompts_v2/test_validator_schema_loading_corr049.py` | x | — | — | +3 |
| `tests/unit/llm/test_unified_invoker_corr013.py` | — | x | x | +5 |
| `tests/unit/prompts_v2/test_get_invoker_minimax_corr067.py` | — | — | x | +5 |

**Estimativa total:** 3 ficheiros, ~13 linhas.

---

## Comandos de validação (só tests pequenos, sem re-run E2E)

```bash
# S1
PYTHONPATH=src python -m pytest tests/unit/prompts_v2/test_validator_schema_loading_corr049.py -v

# S2
PYTHONPATH=src python -m pytest tests/unit/llm/test_unified_invoker_corr013.py::test_extract_usage_empty_returns_zeros -v

# S3
PYTHONPATH=src python -m pytest tests/unit/llm/test_unified_invoker_corr013.py::test_unified_invoker_init_defaults -v
PYTHONPATH=src python -m pytest tests/unit/prompts_v2/test_get_invoker_minimax_corr067.py -v
PYTHONPATH=src python -m pytest tests/unit/config/test_case_loader.py -v

# S4: full suite (final, confirmar 0 fail)
for i in 1 2 3; do
    PYTHONPATH=src python -m pytest tests/unit/ -q --timeout=60
done
```

---

## Não-objetivos (out of scope)

- Adicionar novos tests (só fix os 7 existentes)
- Refactor dos tests para pytest fixtures modernos (não há tempo / não é o objectivo)
- Re-run end-to-end (cancelado pelo user — idem CORR-068 S4)
- Adicionar novo contract para outros pre-existing failures que possam aparecer depois

---

## Estado final esperado

| Test | Pre-CORR-069 | Post-CORR-069 |
|---|---|---|
| test_p1b_llm_01_schema_resolves | FAIL | PASS |
| test_p1c_llm_01_schema_resolves | FAIL | PASS |
| test_p1c_llm_03_schema_resolves | FAIL | PASS |
| test_all_5_schemas_loaded | FAIL | PASS |
| test_extract_usage_empty_returns_zeros | FAIL | PASS |
| test_unified_invoker_init_defaults | FAIL | PASS |
| test_load_case_config_typed | FLAKY (passa 5/5 sozinho, falha no suite) | PASS (3/3 no suite) |
| **Full suite** | **2682 pass, 7 fail** | **2689 pass, 0 fail** |
