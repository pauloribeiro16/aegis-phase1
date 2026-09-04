# CORR-049 — Rework: cascade merge + 3 fixes cirúrgicos + OTel híbrido

## Resumo

Contract de **recovery** da estratégia CORR-045 → 048. A auditoria
revelou que:

1. **Os 4 branches foram feitos em paralelo, não em cascata.** Só
   047→048 está em cadeia; 045 e 046 **não são ancestrais** de 048.
   Consequência: o 048 não tem o fix do prompt P1C-LLM-01 (045) nem
   os fixes do loader (046). Nenhum dos 4 está merged em main.
2. **CORR-048 tem 3 bugs graves mascarados por testes falsos-positivos.**
   - Threading é dead code (Paths 1/2/3 do `_extract_corr047_fields`
     nunca match o shape real do `state["company_context"]`).
   - `MAX_PROMPT_BYTES = 10240` trunca prompts de 86KB para 4KB →
     57% FORMAT_ERROR rate, output vazio.
   - Plano A OTel nunca tentado; árvore Langfuse continua flat.
3. **Bug do `output_schemas.yaml` é o root cause de "0 sub_domain_activations"
   em todas as runs reais.** O loader (`validator.py:76-111`) trata o
   ficheiro como YAML+frontmatter mas o ficheiro é **Markdown com ```yaml
   fenced blocks**. Descarta o body todo onde os schemas estão.
   `_resolve_schema(spec_id)` retorna sempre `{}`.

Este contract **fecha os 3 + faz cascade merge + fix schema**. Sem isto,
qualquer run de produção continua a produzir `concatenate: 0 domains`.

**Branch:** `feature/aegis-p1-corr-049`
**Data:** 2026-07-22
**Trigger:** auditoria pós-048 — "user não acreditava que estivesse tudo
bem; auditor confirmou que não está".

---

## Pré-flight (executor TEM de verificar antes de começar — se falhar, ABORTAR)

```bash
cd /home/epmq-cyber/Área de Trabalho/projects/aegis-phase1
source ../shared-venv/bin/activate

# 1. Confirmar que está num estado limpo
git status --short | head -5
# Esperado: vazio ou só artefactos

# 2. Confirmar que 045, 046, 047, 048 existem como branches
git branch | grep -E "corr-04[5-8]"
# Esperado: 4 linhas, uma por branch

# 3. Confirmar que NENHUM está merged em main
git log main --oneline | grep -iE "CORR-04[5-8]" | head -5
# Esperado: vazio (se houver commits, ABORTAR e reportar)

# 4. Confirmar os bugs que vamos fixar
grep -n "MAX_PROMPT_BYTES" src/aegis_phase1/prompts_v2/invoker.py | head -2
# Esperado: mostra "MAX_PROMPT_BYTES = 10240"

python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.prompts_v2.validator import Phase1Validator
v = Phase1Validator()
schema = v._resolve_schema('P1B-LLM-01-INTERPRETATION')
print('Schema for P1B-LLM-01:', 'EMPTY (BUG)' if not schema else f'{len(schema)} keys')
"
# Esperado: "EMPTY (BUG)"

# 5. Validar que ollama + langfuse estão acessíveis
curl -s http://localhost:11434/api/tags | jq -r '.models[].name' | grep e2b   # gemma4:e2b
curl -s http://localhost:3000/api/public/health                                # {"status":"OK"}

# 6. Validar pelo menos 5G livres em disco
df -h / | awk 'NR==2 {print "Free:", $4}'
# Se < 5G, ABORTAR e reportar — langfuse não vai conseguir ingerir traces
```

**Se qualquer pré-flight falhar: ABORTAR. Não tentar "contornar". Reportar
ao orchestrator com o output exacto.**

---

## Decisões de produto (NÃO negociáveis)

1. **Cascade merge é obrigatório.** A estratégia original era sequencial.
   Vamos criar branch nova `feature/aegis-p1-corr-049` a partir de main,
   e fazer cherry-pick OU merge dos 4 branches na ordem 045 → 046 → 047 →
   (048 reworkado inline). Sem disto o rework é impossível.
2. **3 fixes são cirúrgicos, com commits separados.** Cada fix tem o seu
   commit para ser revertível independentemente.
3. **OTel híbrido** (CallbackHandler + `start_as_current_observation`).
   Não tentar Plano A puro (não suportado em 4.8.0b1) nem aceitar Plano B
   como permanente sem tentar o híbrido primeiro.
4. **MAX_PROMPT_BYTES = 524288** (512KB). Razão: prompts P1C-LLM-01 têm
   ~211K tokens ≈ 850KB; o limite prático antes do gemma4:e2b degradar é
   ~512KB. Não usar 200KB (corta demasiado); não usar ilimitado (vai
   estourar contexto do modelo).
5. **Schema loader rewrite.** Extrair fenced blocks do Markdown, não
   tentar `safe_load_all`.

---

## Tarefas

### FASE 1 — CASCADE MERGE (commits 1-4)

### T1 — Branch nova + cherry-pick de 045

```bash
git checkout main
git pull
git checkout -b feature/aegis-p1-corr-049

# Merge de 045 (nao cherry-pick; merge preserva history e tests)
git merge --no-ff feature/aegis-p1-corr-045 -m "CORR-049-T1: merge CORR-045 (fix P1C-LLM-01 prompt: catalogs + helper + lane filter)"

# Resolver conflitos se houver. Regra: preference para o conteúdo do 045.
# Se houver conflito em ficheiro que 045 não toca, manter main.

# Verificar que 045 está aplicado
grep -n "_build_layer0_subdomain_refs" src/aegis_phase1/v2/orchestrator.py | head -3
# Esperado: mostra a definição do helper

# Testar
pytest tests/unit/v2/test_p1c_llm_01_canonical.py tests/unit/prompts_v2/test_invoker_catalogs_merged.py -q 2>&1 | tail -3
# Esperado: passed
```

**Commit 1.** Se os testes falharem após merge, NÃO commitar. Investigar
conflitos silenciosos (e.g., helper definido mas chamadas ainda em
`list(...keys())`).

### T2 — Merge de 046

```bash
git merge --no-ff feature/aegis-p1-corr-046 -m "CORR-049-T2: merge CORR-046 (fix loader: tech_stack top-level + multi-key)"

# Verificar
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
p = CaseProfileLoader('cases/case1-tinytask').load()
assert p.company.tech_stack == ['AWS', 'Firebase', 'GitHub Actions'], f'tech_stack={p.company.tech_stack}'
assert len(p.architecture.data_stores) == 3, f'data_stores={len(p.architecture.data_stores)}'
assert len(p.architecture.data_flows) == 5, f'data_flows={len(p.architecture.data_flows)}'
assert len(p.architecture.cloud_services) == 4, f'cloud_services={len(p.architecture.cloud_services)}'
print('T2 OK')
"

pytest tests/unit/v2/loader/test_case_profile_corr046.py -q 2>&1 | tail -3
# Esperado: passed
```

**Commit 2.**

### T3 — Merge de 047

```bash
git merge --no-ff feature/aegis-p1-corr-047 -m "CORR-049-T3: merge CORR-047 (enrich CompanyContext: 4 YAMLs + 8 Pydantic models)"

# Verificar
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
p = CaseProfileLoader('cases/case1-tinytask').load()
assert p.implementation_readiness is not None
assert p.regulatory_classification is not None
assert p.role_matrix is not None and len(p.role_matrix.entries) == 5
assert p.regulatory_interactions is not None
print('T3 OK')
"

pytest tests/unit/v2/loader/test_case_profile_corr047.py -q 2>&1 | tail -3
```

**Commit 3.**

### T4 — Merge de 048 (com rework inline)

```bash
git merge --no-ff feature/aegis-p1-corr-048 -m "CORR-049-T4: merge CORR-048 base (Langfuse metadata cleanup + threading attempt — rework follows in T5/T6/T7)"
```

**Conflitos esperados** em `inputs.py` (CORR-048 mexeu no `_project_company_context`
e `_extract_corr047_fields`; CORR-047 pode ter mexido nos mesmos sítios).
Resolução: manter a estrutura do 048 mas preparar para rework T5.

Após o merge, o estado ainda tem os 3 bugs do 048 — T5, T6, T7 corrigem.

**Commit 4** (pós-resolução de conflitos).

### FASE 2 — REWORK (commits 5-7)

### T5 — FIX Schema loader (CRÍTICO — root cause de "0 sub_domain_activations")

**Ficheiro:** `src/aegis_phase1/prompts_v2/validator.py`

**Bug exato (linhas 74-111):** `_load_yaml_with_frontmatter` trata
`output_schemas.yaml` como YAML+frontmatter. O ficheiro é Markdown com
```yaml fenced blocks. Só extrai as 9 keys de frontmatter; descarta o
body. `_resolve_schema(spec_id)` retorna sempre `{}`.

**Fix cirúrgico:** substituir o body de `_load_yaml_with_frontmatter`
quando aplicado a `output_schemas.yaml` por um parser que:

1. Lê o ficheiro como texto.
2. Encontra todos os ```yaml ... ``` fenced blocks via regex.
3. Para cada block, faz `yaml.safe_load(block_content)`.
4. Indexa por `properties.prompt_spec_id.const` (a key de lookup).

**Implementação exacta** (substituir o método, NÃO patchar):

```python
import re
import yaml
from pathlib import Path

_FENCED_YAML_RE = re.compile(
    r"```yaml\s*\n(.*?)\n```",
    re.DOTALL,
)

def _load_output_schemas(path: Path) -> dict[str, dict]:
    """Load JSON Schemas from output_schemas.yaml (Markdown with fenced blocks).

    CORR-049-T5: the file is NOT pure YAML — it's Markdown with ```yaml
    fenced code blocks, one per LLM spec. The previous loader treated it
    as YAML+frontmatter and discarded the body, so _resolve_schema()
    always returned {} (root cause of "0 sub_domain_activations" across
    all real LLM runs since CORR-045).

    Strategy:
      1. Find all ```yaml ... ``` fenced blocks.
      2. yaml.safe_load each block.
      3. Index by schema["properties"]["prompt_spec_id"]["const"].

    Args:
        path: path to output_schemas.yaml.

    Returns:
        dict mapping spec_id (e.g. "P1B-LLM-01-INTERPRETATION") to the
        parsed JSON Schema dict. Empty dict if file missing or no blocks.
    """
    if not path.exists():
        logger.warning("output_schemas.yaml not found at %s", path)
        return {}

    text = path.read_text(encoding="utf-8")
    schemas: dict[str, dict] = {}

    for match in _FENCED_YAML_RE.finditer(text):
        block_text = match.group(1)
        try:
            parsed = yaml.safe_load(block_text)
        except yaml.YAMLError as e:
            logger.debug("skipping fenced block (parse error): %s", e)
            continue
        if not isinstance(parsed, dict):
            continue
        # Lookup key: properties.prompt_spec_id.const (JSON Schema convention)
        spec_id = (
            parsed.get("properties", {})
            .get("prompt_spec_id", {})
            .get("const")
        )
        if spec_id:
            schemas[spec_id] = parsed
        else:
            logger.debug(
                "fenced block has no properties.prompt_spec_id.const; "
                "keys=%s",
                list(parsed.keys())[:5],
            )

    logger.info(
        "CORR-049-T5: loaded %d schemas from %s (specs=%s)",
        len(schemas), path.name, sorted(schemas.keys()),
    )
    return schemas
```

**Aplicar no sítio certo:** em `validator.py`, onde se chama
`_load_yaml_with_frontmatter` para `output_schemas.yaml` (linha 74),
substituir por `_load_output_schemas(path)`. O `self._schemas` passa a
ser o dict retornado (spec_id → schema).

**Manter backward-compat:** se por acaso `output_schemas.yaml` algum
dia se tornar YAML puro, o `_FENCED_YAML_RE` não vai apanhar blocks →
retorna `{}`. Por segurança, adicionar fallback: se 0 schemas
encontrados, tentar `_load_yaml_with_frontmatter` antigo.

**Teste novo** `tests/unit/prompts_v2/test_validator_schema_loading_corr049.py`:

```python
import pytest
from pathlib import Path
from aegis_phase1.prompts_v2.validator import Phase1Validator

@pytest.fixture
def validator():
    return Phase1Validator()

def test_p1b_llm_01_schema_resolves(validator):
    """CORR-049-T5: P1B-LLM-01-INTERPRETATION must resolve to a real schema."""
    schema = validator._resolve_schema("P1B-LLM-01-INTERPRETATION")
    assert schema, "schema is empty — fenced block parsing failed"
    assert schema.get("properties", {}).get("prompt_spec_id", {}).get("const") == "P1B-LLM-01-INTERPRETATION"
    assert "interpretations" in schema.get("properties", {}), "missing interpretations field"

def test_p1c_llm_01_schema_resolves(validator):
    """P1C-LLM-01-OVERLAP-CLASSIFICATION must resolve with sub_domain_activations."""
    schema = validator._resolve_schema("P1C-LLM-01-OVERLAP-CLASSIFICATION")
    assert schema, "schema is empty"
    assert "sub_domain_activations" in schema.get("properties", {}), \
        "missing sub_domain_activations — root cause of LLM emitting {pairs:[...]}"

def test_p1c_llm_03_schema_resolves(validator):
    schema = validator._resolve_schema("P1C-LLM-03-STRATEGIC-SYNTHESIS")
    assert schema, "schema is empty"
    assert "implications" in schema.get("properties", {})

def test_all_5_schemas_loaded(validator):
    """All 5 canonical LLM specs should have schemas after CORR-049-T5."""
    expected_specs = [
        "P1B-LLM-01-INTERPRETATION",
        "P1B-LLM-02-RATIONALE",
        "P1C-LLM-01-OVERLAP-CLASSIFICATION",
        "P1C-LLM-02-COMPOUND-EVENT",
        "P1C-LLM-03-STRATEGIC-SYNTHESIS",
    ]
    for spec in expected_specs:
        assert validator._resolve_schema(spec), f"missing schema for {spec}"
```

**Verificação pós-fix:**
```bash
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.prompts_v2.validator import Phase1Validator
v = Phase1Validator()
for spec in ['P1B-LLM-01-INTERPRETATION', 'P1B-LLM-02-RATIONALE',
             'P1C-LLM-01-OVERLAP-CLASSIFICATION', 'P1C-LLM-02-COMPOUND-EVENT',
             'P1C-LLM-03-STRATEGIC-SYNTHESIS']:
    s = v._resolve_schema(spec)
    print(f'{spec}: {len(s)} keys' if s else f'{spec}: EMPTY')
"
# Esperado: cada um tem >0 keys
```

**Commit 5.**

### T6 — FIX Context bridge (threading morto)

**Ficheiro:** `src/aegis_phase1/v2/orchestrator.py` (método
`_build_company_context`, linhas 273-305) + `src/aegis_phase1/v2/domain/inputs.py`
(função `_extract_corr047_fields`, linhas 201-250).

**Bug exato:** `_build_company_context` retorna
`CompanyContext.model_dump()` — dict flat de 9 keys. O
`_extract_corr047_fields` testa 3 paths que NUNCA dão match com este
shape. Os 4 fields do CORR-047 nunca chegam ao prompt.

**Fix cirúrgico:** fazer `_build_company_context` injetar
`v2_company_profile` (referência ao `CompanyProfile` Pydantic completo)
no dict retornado. Assim Path 2 do `_extract_corr047_fields` funciona.

**Implementação exacta:**

Em `orchestrator.py:273-305`, modificar o return de `_build_company_context`:

```python
def _build_company_context(self, facts) -> dict[str, Any]:
    """Build the company_context dict for state["company_context"].

    CORR-049-T6: previous version returned CompanyContext.model_dump()
    (9 flat keys). _extract_corr047_fields in inputs.py could not find
    the CORR-047 fields (implementation_readiness, regulatory_classification,
    role_matrix, regulatory_interactions) because the flat dict didn't
    carry them. We now embed the full v2 CompanyProfile under the
    'v2_company_profile' key so Path 2 of _extract_corr047_fields matches.
    """
    # ... existing logic building CompanyContext Pydantic ...

    base = cc.model_dump()

    # CORR-049-T6: attach the rich CompanyProfile (loaded by CaseProfileLoader
    # in CORR-047) so _extract_corr047_fields Path 2 can find the 4 new fields.
    profile = self.state.get("v2_company_profile")
    if profile is not None:
        base["v2_company_profile"] = profile  # Pydantic instance, not dict
        # Also expose the 4 fields directly as top-level keys (Path 3 fallback)
        for field in ("implementation_readiness", "regulatory_classification",
                      "role_matrix", "regulatory_interactions"):
            value = getattr(profile, field, None)
            if value is not None:
                base[field] = value.model_dump() if hasattr(value, "model_dump") else value

    return base
```

**Garantir que `self.state["v2_company_profile"]` está populado.** Procurar
onde `CaseProfileLoader.load()` é chamado no orchestrator (provavelmente
no init ou no `_load_case`). Adicionar, se não estiver já:

```python
# Em _load_case ou equivalente:
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
profile = CaseProfileLoader(case_path).load()
self.state["v2_company_profile"] = profile
```

**Confirmar que Path 2 do `_extract_corr047_fields` funciona** (em
`inputs.py:228-235`):
```python
# Path 2 atual:
profile = ctx.get("v2_company_profile") if isinstance(ctx, dict) else None
if profile is not None and hasattr(profile, field):
    return getattr(profile, field)
```
Isto deve funcionar com o fix acima. Validar com teste.

**Teste novo** `tests/unit/v2/test_corr049_context_bridge.py`:

```python
import sys; sys.path.insert(0, 'src')
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.domain.inputs import _project_company_context, _extract_corr047_fields

def test_corr047_fields_reach_prompt_after_bridge():
    """CORR-049-T6: end-to-end — after _build_company_context fix,
    the 4 CORR-047 fields must appear in the projected context dict.
    """
    profile = CaseProfileLoader('cases/case1-tinytask').load()

    # Simular o que _build_company_context agora produz
    ctx = {
        "company_name": profile.company.name,
        "sector": profile.company.sector,
        # ... rest of flat keys ...
        "v2_company_profile": profile,
        "implementation_readiness": profile.implementation_readiness.model_dump(),
        "regulatory_classification": profile.regulatory_classification.model_dump(),
        "role_matrix": [e.model_dump() for e in profile.role_matrix.entries],
        "regulatory_interactions": profile.regulatory_interactions.model_dump(),
    }

    projected = _project_company_context(ctx)
    assert "implementation_readiness" in projected, "IR missing"
    assert "regulatory_classification" in projected, "RegClass missing"
    assert "role_matrix" in projected, "RoleMatrix missing"
    assert "regulatory_interactions" in projected, "Interactions missing"

def test_extract_corr047_fields_path2_works():
    """Direct unit test of _extract_corr047_fields with v2_company_profile key."""
    profile = CaseProfileLoader('cases/case1-tinytask').load()
    ctx = {"v2_company_profile": profile}
    ir = _extract_corr047_fields(ctx, "implementation_readiness")
    assert ir is not None
    assert "governance_ciso" in ir  # IR-01 field
```

**Verificação pós-fix:**
```bash
python -c "
import sys; sys.path.insert(0, 'src')
# Simular o fluxo real
from aegis_phase1.v2.orchestrator import Phase1Orchestrator
# Setup mínimo para chamar _build_company_context
# (pode necessitar de mock; ver como os testes existentes fazem)
"
```

**Commit 6.**

### T7 — FIX MAX_PROMPT_BYTES + OTel híbrido (Langfuse tree)

**Ficheiro:** `src/aegis_phase1/prompts_v2/invoker.py` (truncagem) +
`src/aegis_phase1/v2/graph.py` (OTel híbrido).

#### T7.1 — Subir MAX_PROMPT_BYTES para 512KB

Em `invoker.py:261`:
```python
# Antes:
MAX_PROMPT_BYTES = 10240  # 10KB — CORR-048 bug: trunca prompts de 86KB para 4KB

# Depois:
MAX_PROMPT_BYTES = 524288  # 512KB — CORR-049-T7: prompts P1C-LLM-01 são ~211K tokens ≈ 850KB
                            # 512KB é o sweet spot antes do gemma4:e2b degradar
```

Adicionar log INFO (não WARNING) quando truncar, para ser visível mas não ruidoso:
```python
if needs_truncation:
    logger.info(
        "CORR-049-T7: prompt truncated %dB → %dB (spec=%s, cap=%dB)",
        sys_len + user_len, MAX_PROMPT_BYTES, spec_id, MAX_PROMPT_BYTES,
    )
    # ... existing truncation logic ...
```

E emitir flag Langfuse:
```python
# Adicionar ao metadata da generation span
if hasattr(self, "_langfuse_handler") and self._langfuse_handler:
    # Isto é best-effort; se não funcionar, não bloqueia
    try:
        self._langfuse_handler.metadata = {
            **(self._langfuse_handler.metadata or {}),
            "truncated": True,
            "original_size_bytes": sys_len + user_len,
            "truncated_to_bytes": MAX_PROMPT_BYTES,
        }
    except Exception:
        pass
```

#### T7.2 — OTel híbrido em graph.py

**Abordagem:** manter o `CallbackHandler` para ChatOllama generations
(captura input/output/tokens automaticamente), mas criar spans OTel
explícitos para dar a estrutura hierárquica via
`Langfuse.start_as_current_observation`.

Em `src/aegis_phase1/v2/graph.py`, no `run_phase1_graph` (em torno da
linha 666):

```python
from langfuse import Langfuse

def run_phase1_graph(
    orchestrator: Phase1Orchestrator,
    callbacks: list | None = None,
    tags: list[str] | None = None,
    extra_metadata: dict | None = None,
) -> dict:
    """Run the 18-node LangGraph with hybrid Langfuse tracing.

    CORR-049-T7.2: hybrid approach — keep the LangChain CallbackHandler
    for ChatOllama generations (auto-captures I/O/tokens), but wrap the
    whole graph.invoke() in a Langfuse OTel span so the tree is
    hierarchical. Per-node spans created via start_as_current_observation
    inside _make_*_node factories.
    """
    lf = Langfuse()  # uses env

    with lf.start_as_current_observation(
        name="AEGIS Phase 1",
        as_type="chain",
        metadata={
            "case": extra_metadata.get("case") if extra_metadata else None,
            "model": extra_metadata.get("model") if extra_metadata else None,
            "graph": "v2.langgraph.full",
            "run_id": extra_metadata.get("run_id") if extra_metadata else None,
        },
    ) as root_span:
        try:
            result = _invoke_graph_internal(orchestrator, callbacks, tags, extra_metadata)
            root_span.end(output="completed")
            return result
        except Exception as e:
            root_span.end(output=f"failed: {e}")
            raise
        finally:
            lf.flush()
```

Em cada node factory (`_make_map_node`, `_make_1b_node`, etc.), criar
child span:

```python
def _make_map_node(domain_id: str):
    span_name = f"MAP {domain_id}"
    lf = Langfuse()  # cached singleton

    def node(state, config):
        with lf.start_as_current_observation(
            name=span_name,
            as_type="chain",
            metadata={"domain_id": domain_id, "stage": "MAP"},
        ) as span:
            cfg = _add_named_callback(config, span_name, {"domain_id": domain_id})
            orch = _orchestrator_from(config)
            try:
                result = orch.map_single_domain(domain_id, config=cfg)
                orch.state.setdefault("domain_results", {})[domain_id] = result
                span.end(output=f"{result.get('llm_status', 'unknown')}")
                return {"stage_outputs": {f"map_{domain_id}": result}, "map_complete": {domain_id: True}}
            except Exception as e:
                span.end(output=f"failed: {e}")
                raise
    return node
```

**Aplicar o mesmo padrão** em `_make_1b_node` (span name `f"P1B-LLM-{nn} {KIND} ({reg_id})"`),
`_make_reduce_node` (`"REDUCE Deterministic"`, `"P1C-LLM-03 STRATEGIC SYNTHESIS"`,
`"P1C-LLM-02 COMPOUND EVENTS"`), e `_make_output_node` (`f"OUTPUT {doc_id}"`).

**Verificar comportamento:** abrir Langfuse UI após run, validar que:
- 1 root span "AEGIS Phase 1"
- Dentro dele: load_baseline, subphase_map, subphase_1b, subphase_reduce, subphase_output (em ordem)
- Dentro de subphase_map: 10 spans "MAP D-01".."MAP D-10"
- Dentro de cada MAP span: generation(s) ChatOllama (via CallbackHandler)

Se a árvore não aparecer hierárquica, o OTel context não está a propagar
— validar com `langfuse.start_as_current_observation` documentation para 4.8.0b1.

**Teste novo** `tests/unit/v2/test_corr049_otel_hybrid.py`:

```python
from unittest.mock import MagicMock, patch

def test_run_phase1_graph_creates_root_span():
    """CORR-049-T7.2: run_phase1_graph must wrap invoke in start_as_current_observation."""
    with patch("aegis_phase1.v2.graph.Langfuse") as mock_langfuse_class:
        mock_lf = MagicMock()
        mock_langfuse_class.return_value = mock_lf
        mock_root = MagicMock()
        mock_lf.start_as_current_observation.return_value.__enter__.return_value = mock_root

        # Call run_phase1_graph with mocked orchestrator + graph
        from aegis_phase1.v2.graph import run_phase1_graph
        # ... setup mocks ...

        # Assert
        mock_lf.start_as_current_observation.assert_called_once()
        call_kwargs = mock_lf.start_as_current_observation.call_args.kwargs
        assert call_kwargs["name"] == "AEGIS Phase 1"
        assert call_kwargs["as_type"] == "chain"
```

**Commit 7.**

### FASE 3 — VALIDAÇÃO (commits 8-9)

### T8 — Run end-to-end real + verificar Langfuse tree

```bash
source ../shared-venv/bin/activate

# Snapshot baseline (pós-merge + 3 fixes, antes da run final)
mkdir -p output/phase1/baseline_pre_corr049_run/
cp output/phase1/*.md output/phase1/*.xlsx output/phase1/baseline_pre_corr049_run/ 2>/dev/null

# Run completo com tracing
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --run-all-traced \
    2>&1 | tee logs/phase1/corr049_run_traced.log
```

**Esperado pós-fix:**
- 16 LLM calls (4 P1B + 10 P1C-01 + 1 P1C-03 + 1 P1C-02), TODOS com schema válido
- `concatenate: 10 domains -> N subdomains` (N > 0, tipicamente 30-38)
- 0 FORMAT_ERROR (prompts já não são truncados para 4KB)
- Outputs Doc 04/05/06/07/07b com conteúdo real (não "Total clauses mapped: 0")
- Langfuse: 1 root span "AEGIS Phase 1", árvore hierárquica visível

**Validar via Langfuse API:**
```bash
PK=$(grep "^LANGFUSE_PUBLIC_KEY=" .env | cut -d= -f2 | tr -d '"')
SK=$(grep "^LANGFUSE_SECRET_KEY=" .env | cut -d= -f2 | tr -d '"')

# Trazer o trace mais recente
TRACE_DATA=$(curl -s -u "$PK:$SK" "http://localhost:3000/api/public/traces?limit=1&orderBy=createdAt&order=desc")
TRACE_ID=$(echo "$TRACE_DATA" | jq -r '.data[0].id')
echo "Trace ID: $TRACE_ID" | tee logs/phase1/corr049_langfuse_trace_id.txt

# Listar observations (deve mostrar tree hierárquica)
curl -s -u "$PK:$SK" "http://localhost:3000/api/public/traces/$TRACE_ID/observations?limit=30" | \
    jq -r '.[] | "\(.type)\t\(.name // "-")\t\(.parentObservationId // "ROOT")"' | head -30
```

**Esperado:** observations com parent IDs formando árvore (não todos
órfãos). Tipicamente: 1 CHAIN root → 4-5 CHAIN subphase → 10 CHAIN
MAP D-XX → GENERATION dentro de cada MAP.

**Commit 8** (logs + trace_id).

### T9 — Parity report final + verdicts nos 4 contracts anteriores

Parity check contra `Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`
usando o mesmo `normalize()` do CORR-042-T7. Reportar em
`logs/phase1/corr049_parity_report.md`.

**Esperado:** com schema loader fixed, threading real, prompts não
truncados, outputs devem ter conteúdo significativamente mais rico que
antes. Validar que Doc 07 tem > 30 subdomain rows com cells não-vazias.

Em cada um dos `execution/CONTRACT-{045,046,047,048}.md`, adicionar no
fim uma secção:

```markdown
---

## Verdict pós-CORR-049 (2026-07-22)

**Status:** ✅ PASS / ⚠️ PARTIAL / ❌ FAIL

**CORR-049 integrou este contract num branch cascade e aplicou reworks
necessários. Detalhes em `execution/CONTRACT-049.md` §"Resultado da run".**

**Evidence:** <resumo do que foi validado após o cascade merge + rework>
```

**Commit 9.**

---

## Quality gates (FAIL default — TODOS têm de passar; sem atalhos)

```bash
source ../shared-venv/bin/activate

# G1 — Cascade merge completo (4 commits de merge)
COMMITS=$(git log main..HEAD --oneline | grep -c "CORR-049-T[1-4]: merge")
[ "$COMMITS" -ge 4 ] && echo "G1 OK" || { echo "FAIL G1: só $COMMITS/4 merges presentes"; exit 1; }

# G2 — 045 helper presente
grep -q "def _build_layer0_subdomain_refs" src/aegis_phase1/v2/orchestrator.py && echo "G2 OK" || { echo "FAIL G2"; exit 1; }

# G3 — 046 loader fix presente
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
p = CaseProfileLoader('cases/case1-tinytask').load()
assert p.company.tech_stack != [], 'tech_stack empty'
assert len(p.architecture.data_stores) > 0, 'data_stores empty'
print('G3 OK')
"

# G4 — 047 fields carregados
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
p = CaseProfileLoader('cases/case1-tinytask').load()
assert p.implementation_readiness is not None
assert p.regulatory_classification is not None
assert p.role_matrix is not None
assert p.regulatory_interactions is not None
print('G4 OK')
"

# G5 — Schema loader fix (T5): 5 schemas resolvem
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.prompts_v2.validator import Phase1Validator
v = Phase1Validator()
for spec in ['P1B-LLM-01-INTERPRETATION', 'P1B-LLM-02-RATIONALE',
             'P1C-LLM-01-OVERLAP-CLASSIFICATION', 'P1C-LLM-02-COMPOUND-EVENT',
             'P1C-LLM-03-STRATEGIC-SYNTHESIS']:
    s = v._resolve_schema(spec)
    assert s, f'schema for {spec} empty'
print('G5 OK: all 5 schemas resolve')
"

# G6 — Context bridge (T6): state["company_context"] carrega 4 fields
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.v2.orchestrator import Phase1Orchestrator
# Inspecionar source do _build_company_context
import inspect
src = inspect.getsource(Phase1Orchestrator._build_company_context)
assert 'v2_company_profile' in src, 'bridge missing v2_company_profile'
print('G6 OK')
"

# G7 — MAX_PROMPT_BYTES subiu
python -c "
import sys; sys.path.insert(0, 'src')
import re
src = open('src/aegis_phase1/prompts_v2/invoker.py').read()
m = re.search(r'MAX_PROMPT_BYTES\s*=\s*(\d+)', src)
val = int(m.group(1))
assert val >= 200000, f'MAX_PROMPT_BYTES={val} (esperado ≥ 200000)'
print(f'G7 OK: MAX_PROMPT_BYTES={val}')
"

# G8 — OTel híbrido (T7.2): graph.py usa start_as_current_observation
grep -q "start_as_current_observation" src/aegis_phase1/v2/graph.py && echo "G8 OK" || { echo "FAIL G8: OTel não implementado"; exit 1; }

# G9 — Testes novos passam
pytest tests/unit/prompts_v2/test_validator_schema_loading_corr049.py \
       tests/unit/v2/test_corr049_context_bridge.py \
       tests/unit/v2/test_corr049_otel_hybrid.py -q 2>&1 | tail -1 | grep -qE "passed" && echo "G9 OK" || { echo "FAIL G9"; exit 1; }

# G10 — Suite completa verde (sem falsos positivos)
pytest tests/unit/v2/ tests/unit/prompts_v2/ -q 2>&1 | tail -3 | grep -qE "passed" && echo "G10 OK" || { echo "FAIL G10"; exit 1; }

# G11 — Run real sem "concatenate: 0 domains"
test -f logs/phase1/corr049_run_traced.log && \
    ! grep -q "concatenate: 0 domains" logs/phase1/corr049_run_traced.log && echo "G11 OK" || { echo "FAIL G11: ainda 0 domains"; exit 1; }

# G12 — Run real sem FORMAT_ERROR em massa (permitir até 2)
FERRORS=$(grep -c "FORMAT_ERROR" logs/phase1/corr049_run_traced.log 2>/dev/null || echo 0)
[ "$FERRORS" -le 2 ] && echo "G12 OK ($FERRORS format errors)" || { echo "FAIL G12: $FERRORS format errors (esperado ≤2)"; exit 1; }

# G13 — 9 outputs regenerados hoje
TODAY=$(date +%Y-%m-%d)
for doc in 04_Company_Context_Assessment 05_Regulatory_Applicability 06_Clause_Mapping_Matrix 07_Structured_Compliance_Matrix 07b_Proportionality_Profile 04a_Architecture_DataInventory 04b_Security_Posture 04c_ThirdParty_Landscape 04d_Org_Roles_RACI; do
    stat -c '%y' "output/phase1/${doc}.md" 2>/dev/null | grep -q "$TODAY" || { echo "FAIL G13: $doc.md não regenerado hoje"; exit 1; }
done
echo "G13 OK"

# G14 — Doc 07 tem subdomain rows (não vazio)
ROWS=$(grep -cE "^\| D-[0-9]+\.[0-9]+" output/phase1/07_Structured_Compliance_Matrix.md 2>/dev/null || echo 0)
[ "$ROWS" -ge 30 ] && echo "G14 OK ($ROWS rows)" || { echo "FAIL G14: só $ROWS rows (esperado ≥30)"; exit 1; }

# G15 — Langfuse trace_id capturado
test -s logs/phase1/corr049_langfuse_trace_id.txt && echo "G15 OK (manual verify tree)" || { echo "FAIL G15"; exit 1; }

# G16 — CI gates
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G16 OK" || { echo "FAIL G16"; exit 1; }

echo "=== ALL 16 GATES PASSED ==="
```

**Definição de done:** G1–G16 TODOS PASS. Sem atalhos. Se algum falhar,
investigar — não desabilitar.

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `src/aegis_phase1/prompts_v2/validator.py` | **MODIFY (T5)** — substituir `_load_yaml_with_frontmatter` para `output_schemas.yaml` por `_load_output_schemas` (parser de fenced blocks) |
| `src/aegis_phase1/v2/orchestrator.py` | **MODIFY (T6)** — `_build_company_context` injeta `v2_company_profile` + 4 fields top-level |
| `src/aegis_phase1/prompts_v2/invoker.py` | **MODIFY (T7.1)** — `MAX_PROMPT_BYTES = 524288`; log INFO em truncagem; flag Langfuse `truncated: true` |
| `src/aegis_phase1/v2/graph.py` | **MODIFY (T7.2)** — `run_phase1_graph` wrap em `lf.start_as_current_observation`; cada node factory cria child span |
| `tests/unit/prompts_v2/test_validator_schema_loading_corr049.py` | **NEW (T5)** — 4 testes |
| `tests/unit/v2/test_corr049_context_bridge.py` | **NEW (T6)** — 2 testes |
| `tests/unit/v2/test_corr049_otel_hybrid.py` | **NEW (T7.2)** — 1+ testes |
| `output/phase1/baseline_pre_corr049_run/` | **NEW (T8)** — snapshot |
| `output/phase1/*.md` + `*.xlsx` | **REGENERATED (T8)** |
| `logs/phase1/corr049_run_traced.log` | **NEW (T8)** |
| `logs/phase1/corr049_langfuse_trace_id.txt` | **NEW (T8)** |
| `logs/phase1/corr049_parity_report.md` | **NEW (T9)** |
| `execution/CONTRACT-{045,046,047,048}.md` | **MODIFY (T9)** — secção "Verdict pós-CORR-049" |
| `execution/CONTRACT-049.md` | **NEW** (este) |

**Não modificar:** `preproc_out/`, `Methodology-main/`, `.hooks/`,
`cases/case1-tinytask/input/*.yaml`.

---

## Estrutura de commits (9 commits — NÃO consolidar)

```
feature/aegis-p1-corr-049
├─ commit 1: T1 merge CORR-045
├─ commit 2: T2 merge CORR-046
├─ commit 3: T3 merge CORR-047
├─ commit 4: T4 merge CORR-048 (base; conflitos resolvidos)
├─ commit 5: T5 FIX output_schemas.yaml loader + 4 testes
├─ commit 6: T6 FIX context bridge (v2_company_profile) + 2 testes
├─ commit 7: T7 FIX MAX_PROMPT_BYTES + OTel híbrido + 1 teste
├─ commit 8: T8 run-all-traced real + logs + trace_id
└─ commit 9: T9 parity report + verdicts em 045/046/047/048
```

**Cada commit tem de deixar a suite de testes verde.** Não fazer commit
intermédio que parta `pytest tests/unit/`.

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Merge de 045/046/047/048 tem conflitos significativos em `inputs.py`, `orchestrator.py` | Resolução preference para o conteúdo do branch que está a ser merged (mantém o novo); testar após cada merge |
| `_FENCED_YAML_RE` pode falhar se algum block tiver ``` yaml com espaço ou tabs | Regex aceita `\s*` entre ``` e yaml; testar com ficheiro real |
| `Langfuse.start_as_current_observation` API pode diferir em 4.8.0b1 do esperado | Validar com `python -c "from langfuse import Langfuse; import inspect; print(inspect.signature(Langfuse.start_as_current_observation))"` antes de codificar |
| OTel context pode não propagar através de LangGraph sub-graphs | Validar após T8 via Langfuse API (observar `parentObservationId`); se flat, documentar e usar Plano B permanente |
| `MAX_PROMPT_BYTES=524288` pode causar OOM ou timeout no gemma4:e2b | Se run T8 demorar > 30 min ou falhar com timeout, reduzir para 262144 (256KB) e re-testar |
| `_resolve_schema` pode ser usado por outros callers que esperavam `{}` | Grep antes: `grep -rn "_resolve_schema" src/aegis_phase1/`. Adaptar callers que dependiam do comportamento antigo (raro) |

---

## Pós-CORR-049

**Se G1–G16 todos PASS:** estratégia CORR-045 → 049 está fechada. Pipeline
produz outputs com:
- Schema loading funcional (LLM recebe constraint de schema)
- Threading real (4 fields CORR-047 chegam ao prompt)
- Prompts não truncados (512KB cap em vez de 10KB)
- Langfuse tree hierárquica (OTel híbrido)
- Cascade merge completo (045+046+047+048 num branch só)

**Próximo passo:** validar paridade com referência Methodology-main. Se
Doc 07 tem estrutura correta e cells não-vazias, estratégia CLOSED e
avançamos para generalização SecureBorder/OmniBank (CORR-050+).

**Se G11 falhar** (ainda 0 domains): o rework T5/T6/T7 não resolveu. Provável
causa: prompt ainda não tem dados suficientes OU schema ainda não é
passado ao ChatOllama. Investigar via Langfuse — abrir generation
P1C-LLM-01 e validar que tem catálogos + company_facts + schema.

**Se G12 falhar** (>2 FORMAT_ERROR): prompts ainda demasiado truncados
ou schemas conflitantes. Aumentar MAX_PROMPT_BYTES ou rever T5.

---

## Change log

- 2026-07-22: v1.0 — contract inicial criado pelo orchestrator para
  recuperar a estratégia CORR-045→048 após auditoria revelar branches
  paralelos + 3 bugs no 048 + 1 bug de schema (root cause). Faz cascade
  merge + 3 fixes cirúrgicos + OTel híbrido.
