# CORR-055 — Fix 3 testes langfuse_callback_corr011 (regressão CORR-050)

## Resumo

Contract **simples** para corrigir 3 testes que falham desde o CORR-050.
Os testes em `tests/unit/prompts_v2/test_langfuse_callback_corr011.py`
não falham por problemas de callback (o que eles testam) — falham porque
o setup do mock é incompatível com a nova arquitetura.

**Causa raiz confirmada:**
- O `_FakeAIMessage` (linha 36-42) retorna `content = '{"items": []}'`
  (JSON vazio).
- Os testes constroem o invoker com `validator=MagicMock(...)` (que
  retornaria `valid: True` por defeito) — mas **o CORR-050 introduziu o
  `MARKDOWN_PARSERS` registry** que é consultado ANTES do `self.validator`.
- Quando se invoca `P1B-LLM-01-INTERPRETATION`, o invoker vai ao registry
  **real** (não mock), encontra `P1BLLM01Parser`, faz parse de
  `'{"items": []}'` → falha → status `FAILED_AFTER_RETRIES`.

**O callback wiring funciona** — os 3 testes falham é no assertion
`result["status"] == "OK"` que nada tem a ver com o que eles testam.

**Branch:** `feature/aegis-p1-corr-055`
**Data:** 2026-07-22
**Trigger:** auditoria CORR-054 revelou 3 falhas pré-existentes (regressão
silenciosa do CORR-050) — CORR-055 fecha a dívida.

---

## Pré-flight (executor TEM de verificar antes de começar)

```bash
cd /home/epmq-cyber/Área de Trabalho/projects/aegis-phase1
source ../shared-venv/bin/activate

# 1. Confirmar as 3 falhas
pytest tests/unit/prompts_v2/test_langfuse_callback_corr011.py -v 2>&1 | tail -10
# Esperado: 3 FAILED (test_callback_attached_when_handler_present,
#                    test_no_callback_when_handler_is_none,
#                    test_callback_chain_includes_other_callbacks)
# Mensagem: AssertionError: assert 'FAILED_AFTER_RETRIES' == 'OK'

# 2. Confirmar a causa (look at _FakeAIMessage content)
sed -n '36,42p' tests/unit/prompts_v2/test_langfuse_callback_corr011.py
# Esperado: class _FakeAIMessage com content='{"items": []}'

# 3. Confirmar que P1BLLM01Parser existe (CORR-050 aplicado)
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.prompts_v2.markdown_parser import P1BLLM01Parser, MARKDOWN_PARSERS
assert 'P1B-LLM-01-INTERPRETATION' in MARKDOWN_PARSERS
print('P1BLLM01Parser registered')
"

# 4. Confirmar o parser falha com o conteúdo do mock
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.prompts_v2.markdown_parser import P1BLLM01Parser
model, err = P1BLLM01Parser().parse('{\"items\": []}')
print(f'Parse result: model={model}, err={err[:100]}')
"
# Esperado: model=None, err menciona "Missing '## Status' section"
```

Se qualquer pré-flight falhar: ABORTAR. Reportar output exacto.

---

## Decisões de produto (NÃO negociáveis)

1. **Fix no teste, não no código de produção.** O callback wiring está
   correto; o teste é que tem setup incompatível com a arquitetura
   pós-CORR-050.
2. **Mock deve retornar markdown válido** para P1B-LLM-01. Isto testa o
   path completo (callback + parser + validator) com dados realistas.
3. **Não mockar o `MARKDOWN_PARSERS` registry.** Se mockarmos, perdemos
   cobertura do path real. Melhor: mock retorna markdown válido e o
   parser real consegue processar.
4. **Não alterar o que os testes verificam.** Os 3 testes continuam a
   testar exatamente o mesmo (callback em config, no-callback quando
   handler=None, append vs overwrite). Só o setup é que muda.

---

## Tarefas

### T1 — Atualizar `_FakeAIMessage` para retornar markdown válido

**Ficheiro:** `tests/unit/prompts_v2/test_langfuse_callback_corr011.py`

**Estado atual (linhas 36-42):**
```python
class _FakeAIMessage:
    """Minimal stand-in for ``langchain_core.messages.AIMessage``."""

    def __init__(self, content: str = '{"items": []}') -> None:
        self.content = content
        self.response_metadata = {}
        self.usage_metadata = {}
```

**Alvo:**
```python
# CORR-055: content must be valid P1B-LLM-01 markdown (not '{"items": []}').
# Before CORR-050, the validator was a no-op and any JSON would pass.
# After CORR-050, P1B-LLM-01-INTERPRETATION has a registered MarkdownParser
# that requires '## Status' + '## Interpretations' + '## Derogations' sections.
_VALID_P1B_LLM_01_MARKDOWN = """## Status

- status: OK
- confidence: HIGH

## Interpretations

### INT-01

- entry_id: TIPO2-TEST
- applicable: YES
- activation_rationale: Test rationale for callback wiring verification.
- layer0_refs: SubDomains/D-04.3.md
- legal_refs: GDPR Art. 33(1)
- company_fact_refs: test=true

## Derogations

### DER-01

- entry_id: TIPO3-TEST
- activation_verdict: NOT_ACTIVATED
- activation_rationale: Test derogation for callback wiring.
- layer0_refs: SubDomains/D-04.3.md
- legal_refs: GDPR Art. 2(2)(c)
- company_fact_refs: test=true
"""


class _FakeAIMessage:
    """Minimal stand-in for ``langchain_core.messages.AIMessage``.

    CORR-055: default content is now valid P1B-LLM-01 markdown so the
    invoker's MarkdownParser succeeds (status=OK). The original
    '{"items": []}' worked before CORR-050 because the validator was
    mocked, but post-CORR-050 the parser registry is real and rejects
    JSON that doesn't match the markdown template.
    """

    def __init__(self, content: str = _VALID_P1B_LLM_01_MARKDOWN) -> None:
        self.content = content
        self.response_metadata = {}
        self.usage_metadata = {}
```

### T2 — Validar que os 3 testes agora passam

```bash
pytest tests/unit/prompts_v2/test_langfuse_callback_corr011.py -v 2>&1 | tail -10
# Esperado: 3 passed
```

Se algum ainda falhar:
- **`test_callback_attached_when_handler_present`**: o status agora é OK
  mas o callback assertion falha? Então o wiring está realmente partido —
  investigar `invoker._attempt` onde se constrói o `config={"callbacks": ...}`.
- **`test_no_callback_when_handler_is_none`**: similar
- **`test_callback_chain_includes_other_callbacks`**: similar

### T3 — Confirmar que outros testes não regressiram

```bash
pytest tests/unit/prompts_v2/ tests/unit/v2/ -q 2>&1 | tail -5
# Esperado: 0 failed (ou mesmo número de pass que antes)
```

### T4 — Documentar no ficheiro de teste o porquê do markdown

Adicionar comment no topo do ficheiro (depois dos imports) a explicar:

```python
# CORR-055 (2026-07-22): the _FakeAIMessage default content changed from
# '{"items": []}' to valid P1B-LLM-01 markdown. Pre-CORR-050, the validator
# was a no-op mock and any JSON would yield status=OK. Post-CORR-050, the
# invoker consults the real MARKDOWN_PARSERS registry; P1B-LLM-01-INTERPRETATION
# has a registered P1BLLM01Parser that requires '## Status' etc., so the
# mock must return markdown matching the template. See CONTRACT-055.md.
```

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — _FakeAIMessage default é markdown válido
python -c "
import sys; sys.path.insert(0, 'src')
sys.path.insert(0, 'tests/unit/prompts_v2')
# Importar o _FakeAIMessage diretamente
import importlib.util
spec = importlib.util.spec_from_file_location('t', 'tests/unit/prompts_v2/test_langfuse_callback_corr011.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
content = mod._FakeAIMessage().content
assert '## Status' in content, f'content não tem ## Status: {content[:100]}'
assert '## Interpretations' in content
assert '## Derogations' in content
print('G1 OK')
"

# G2 — Os 3 testes passam
pytest tests/unit/prompts_v2/test_langfuse_callback_corr011.py -v 2>&1 | tail -10 | grep -E "passed|failed"
# Esperado: 3 passed

# G3 — Suite completa não regrediu
pytest tests/unit/prompts_v2/ tests/unit/v2/ -q 2>&1 | tail -3 | grep -qE "passed" && echo "G3 OK" || { echo "FAIL G3"; exit 1; }

# G4 — Documentação CORR-055 no ficheiro de teste
grep -q "CORR-055" tests/unit/prompts_v2/test_langfuse_callback_corr011.py && echo "G4 OK" || { echo "FAIL G4: comment em falta"; exit 1; }

# G5 — CI gates
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G5 OK" || { echo "FAIL G5"; exit 1; }

echo "=== ALL 5 GATES PASSED ==="
```

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `tests/unit/prompts_v2/test_langfuse_callback_corr011.py` | **MODIFY** — `_FakeAIMessage` default content + comment |
| `execution/CONTRACT-055.md` | **NEW** (este) |

**Não modificar:** qualquer source file em `src/`. O bug é no teste, não
no código de produção. Se o fix no teste não resultar, investigar mais
fundo — mas NÃO mudar o invoker.py ou markdown_parser.py para acomodar
o teste.

---

## Estrutura de commits

```
feature/aegis-p1-corr-055
└─ commit único: fix _FakeAIMessage default content to valid P1B-LLM-01 markdown
   (regressão do CORR-050: validator era no-op mock, agora MarkdownParser é real)
```

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Testes ainda falham após mudar o content — significa que o wiring do callback está realmente partido | Investigar `invoker._attempt` — o `_patched_chat` patcha `ChatOllama` mas pode não patchear o sítio certo |
| Markdown do mock não bate com o template exato do parser | Copiar literalmente o exemplo do `test_corr054_prompts_logged.py` ou do `test_markdown_parser_corr050.py` |
| Outros testes que usam `_FakeAIMessage` quebram | Grep antes: `grep -rn "_FakeAIMessage\|items.*\[\]" tests/unit/prompts_v2/` — se outros ficheiros usam o mesmo helper, este fix pode afectá-los (provavelmente positivo: também vão precisar) |
| O `MARKDOWN_PARSERS` registry é lazy-load e pode falhar se prompts_v2.markdown_parser não importar | Teste já faz `from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker` que deve importar a cadeia |

---

## Pós-CORR-055

**Se G1–G5 passam:** 3 testes langfuse ficam verdes. Suite
`tests/unit/prompts_v2/` está 100% verde (assumindo que não há outras
falhas escondidas). Dívida técnica do CORR-050 fechada.

**Próximo passo:** validar estado geral do projeto — sem falhas
pre-existing, podemos avançar para nova funcionalidade ou fechar a
estratégia CORR-045 → 055.

---

## Change log

- 2026-07-22: v1.0 — contract criado pelo orchestrator para corrigir
  3 testes em test_langfuse_callback_corr011.py que falham desde o
  CORR-050 (MarkdownParser rework mudou contrato de validação; o mock
  _FakeAIMessage precisa retornar markdown válido em vez de JSON).
