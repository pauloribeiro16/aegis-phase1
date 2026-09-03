# CORR-050 — Markdown+regex parsing infra + P1B-LLM-01 exemplo

## Resumo

Contract de **mudança de paradigma**. Em vez de forçar JSON Schema rígido no
`gemma4:e2b` (que o modelo ignora sistematicamente — auditoria Langfuse mostrou
17/17 generations free-form sem envelope), mudamos para:

- **LLM emite markdown natural** (com secções `##` + bullets `- field:`)
- **Regex tolerante extrai** estrutura (padrão já provado pelo `OutputParserV3`
  usado em MAP-DOMAIN-ADAPT)
- **Envelope determinístico injetado pelo invoker** (`prompt_spec_id`,
  `schema_version`, `case_id`, `invocation_pattern`) — nunca responsabilidade
  do LLM
- **Validação via Pydantic** sobre o struct parsed (substitui JSON Schema;
  fonte única de verdade)
- **`format=` removido do Ollama** — deixamos o modelo emitir natural

**Este contract faz:**
1. **Infraestrutura** — base class `MarkdownParser` + envelope injection +
   Pydantic validators em `state.py` + wiring no invoker
2. **1 exemplo completo: P1B-LLM-01-INTERPRETATION** — template markdown
   (escrito pelo orchestrator), parser `P1BLLM01Parser`, teste end-to-end
3. **Validação** — run real confirma que P1B-LLM-01 produz struct válido

Os outros 4 LLMs (P1B-LLM-02, P1C-LLM-01, P1C-LLM-02, P1C-LLM-03) ficam
para **CORR-051** replicando este padrão. Não os converter aqui.

**Branch:** `feature/aegis-p1-corr-050`
**Data:** 2026-07-22
**Trigger:** "não deves forçar o modelo a responder de forma muito rígida;
deve ser algo simples e depois fazer um regex".

---

## Pré-flight (executor TEM de verificar antes de começar)

```bash
cd /home/epmq-cyber/Área de Trabalho/projects/aegis-phase1
source ../shared-venv/bin/activate

# 1. Estar em branch pós-CORR-049 (com T5/T6/T7 aplicados)
git branch --show-current
# Esperado: feature/aegis-p1-corr-049 ou derivada

# 2. Confirmar que 5 schemas carregam (T5 do CORR-049 funcionou)
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.prompts_v2.validator import Phase1Validator
v = Phase1Validator()
n = sum(1 for s in ['P1B-LLM-01-INTERPRETATION','P1B-LLM-02-RATIONALE',
                    'P1C-LLM-01-OVERLAP-CLASSIFICATION','P1C-LLM-02-COMPOUND-EVENT',
                    'P1C-LLM-03-STRATEGIC-SYNTHESIS'] if v._resolve_schema(s))
print(f'{n}/5 schemas loaded')
"
# Esperado: 5/5

# 3. Confirmar que RobustParser existe (vamos estender, não substituir)
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.prompts_v2.robust_parser import RobustParser
print('RobustParser strategies:', RobustParser.STRATEGIES)
"
# Esperado: lista com 8 strategies

# 4. Confirmar que OutputParserV3 existe (modelo a replicar)
ls src/aegis_phase1/v2/domain/parser.py
grep -n "class OutputParserV3\|class OutputParserV2\|class OutputParser" src/aegis_phase1/v2/domain/parser.py
# Esperado: 3 classes definidas

# 5. Ollama + Langfuse up
curl -s http://localhost:11434/api/tags | jq -r '.models[].name' | grep e2b   # gemma4:e2b
curl -s http://localhost:3000/api/public/health                                # {"status":"OK"}
```

Se qualquer pré-flight falhar: ABORTAR. Reportar output exacto.

---

## Decisões de produto (NÃO negociáveis)

1. **Markdown natural no prompt.** Templates desenhados pelo orchestrator
   (este contract). Exemplo concreto de output incluído no prompt — LLM
   aprende por imitação.
2. **Regex tolerante.** Aceitar variações de whitespace, capitalização,
   ordem de fields. Inspirado em `OutputParserV3` (já provado em produção).
3. **Envelope nunca é LLM.** `prompt_spec_id`, `schema_version`, `case_id`,
   `invocation_pattern` são deterministic — invoker injeta post-parse.
4. **Status/confidence são LLM.** Extraídos via regex do markdown
   (`- status: OK` / `- confidence: HIGH`). São os únicos campos de
   envelope que fazem sentido vir do modelo.
5. **Pydantic é a única validação.** `output_schemas.yaml` JSON Schema
   fica obsoleto (mantém em disco como documentação histórica, mas o
   código não usa para validar). Pydantic models em `state.py` são a
   fonte única de verdade.
6. **`format=` removido do Ollama invoke.** Não passamos `format=schema`
   — deixamos o modelo emitir markdown natural.
7. **5 LLMs em 2 contracts.** Este (050) faz infra + P1B-LLM-01.
   CORR-051 faz os outros 4. Não os fundir.

---

## Tarefas

### T1 — Template markdown P1B-LLM-01 (escrito pelo orchestrator)

**Ficheiro:** `/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md`

**Substituir a secção `## Output Schema` (linhas ~93-104) por:**

````markdown
## Output Format

Emit your answer as **markdown** following this structure EXACTLY.
Section headers (`##`, `###`) must match. Field bullets (`- field:`)
must use the exact field names. Use the example below as your template.

### Required structure

```markdown
## Status

- status: OK | INSUFFICIENT_EVIDENCE | INDETERMINATE
- confidence: HIGH | MEDIUM | LOW

## Interpretations

### INT-01

- entry_id: TIPO2-GDPR-RTS-DEADLINES
- applicable: YES | NO
- activation_rationale: 1-2 sentences explaining why this Tipo 2
  interpretation applies (or not) to THIS company.
- layer0_refs: SubDomains/D-04.3.md §1 CRDA
- legal_refs: GDPR Art. 33(1), GDPR Art. 34(1)
- company_fact_refs: which company facts drove the decision (e.g.
  "sector=health", "employees=8")

### INT-02

- entry_id: TIPO2-CRA-ART14-DUAL-FLOW
- applicable: YES | NO
- activation_rationale: ...
- layer0_refs: ...
- legal_refs: ...
- company_fact_refs: ...

(add one ### block per applicable Tipo 2 entry)

## Derogations

### DER-01

- entry_id: TIPO3-GDPR-HOUSEHOLD
- activation_verdict: ACTIVATED | NOT_ACTIVATED | INDETERMINATE
- activation_rationale: ...
- layer0_refs: ...
- legal_refs: ...
- company_fact_refs: ...

(add one ### block per Tipo 3 entry whose applies_to includes the
regulation being analyzed)
```

### Rules

1. **Section order matters**: Status first, then Interpretations, then
   Derogations. The parser splits on these headers.
2. **Field names are exact**: `entry_id`, `applicable`, `activation_rationale`,
   `layer0_refs`, `legal_refs`, `company_fact_refs` — match these
   character-for-character. The parser uses regex on these names.
3. **List fields**: `layer0_refs`, `legal_refs`, `company_fact_refs` accept
   comma-separated values on one line OR repeated `- field:` bullets:
   ```
   - legal_refs: GDPR Art. 33(1), GDPR Art. 34(1)
   ```
   OR
   ```
   - legal_refs:
     - GDPR Art. 33(1)
     - GDPR Art. 34(1)
   ```
4. **Status values**: only the 3 enum values. If you cannot decide, use
   `INSUFFICIENT_EVIDENCE` and explain in `activation_rationale`.
5. **Do NOT emit JSON.** Do NOT wrap in ```json fences. Plain markdown only.
6. **Do NOT include prompt_spec_id, schema_version, case_id,
   invocation_pattern.** The system adds these automatically.

### Example (GDPR lane, fictional company)

```
## Status

- status: OK
- confidence: HIGH

## Interpretations

### INT-01

- entry_id: TIPO2-GDPR-RTS-DEADLINES
- applicable: YES
- activation_rationale: Company processes personal data of EU data
  subjects (5000); Art. 33(1) 72h deadline applies as continuous
  obligation.
- layer0_refs: SubDomains/D-04.3.md §1 CRDA
- legal_refs: GDPR Art. 33(1), GDPR Art. 34(1)
- company_fact_refs: processes_personal_data=true, eu_data_subjects=5000

## Derogations

### DER-01

- entry_id: TIPO3-GDPR-HOUSEHOLD
- activation_verdict: NOT_ACTIVATED
- activation_rationale: Company is a SaaS provider, not a household
  activity; derogation does not apply.
- layer0_refs: SubDomains/D-04.3.md §1 CRDA
- legal_refs: GDPR Art. 2(2)(c)
- company_fact_refs: business_activity=saas_provider
```

### Quality criteria

- Every `entry_id` matches a row in `tipo2_interpretations.yaml` (for
  Interpretations) or `tipo3_derogations.yaml` (for Derogations).
- Every `applicable: YES` has a non-empty `activation_rationale` citing
  specific company facts.
- No invented article numbers — only `legal_refs` from the catalog.
- INSUFFICIENT_EVIDENCE only when predicates require missing facts.
````

**Adicionar também à secção "## Task" do prompt** uma instrução curta:

> Emit your answer as **markdown** (NOT JSON) following the structure in
> "## Output Format" below. The system will parse your markdown with regex.

### T2 — Pydantic models para P1B-LLM-01 output

**Ficheiro:** `src/aegis_phase1/v2/state.py` (extender)

Adicionar (junto aos models existentes do CORR-047):

```python
class P1BLLM01Status(str, Enum):
    OK = "OK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INDETERMINATE = "INDETERMINATE"

class P1BLLM01Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class P1BLLM01Applicable(str, Enum):
    YES = "YES"
    NO = "NO"

class P1BLLM01DerogationVerdict(str, Enum):
    ACTIVATED = "ACTIVATED"
    NOT_ACTIVATED = "NOT_ACTIVATED"
    INDETERMINATE = "INDETERMINATE"

class P1BLLM01Interpretation(BaseModel):
    """One Tipo 2 interpretation entry."""
    entry_id: str
    applicable: P1BLLM01Applicable
    activation_rationale: str
    layer0_refs: list[str] = []
    legal_refs: list[str] = []
    company_fact_refs: list[str] = []

class P1BLLM01Derogation(BaseModel):
    """One Tipo 3 derogation entry."""
    entry_id: str
    activation_verdict: P1BLLM01DerogationVerdict
    activation_rationale: str
    layer0_refs: list[str] = []
    legal_refs: list[str] = []
    company_fact_refs: list[str] = []

class P1BLLM01Output(BaseModel):
    """Parsed + validated output of P1B-LLM-01-INTERPRETATION.

    Envelope fields (prompt_spec_id, schema_version, case_id,
    invocation_pattern) are injected by the invoker post-parse — the
    LLM never emits them.
    """
    # Envelope (invoker-injected)
    prompt_spec_id: str = "P1B-LLM-01-INTERPRETATION"
    schema_version: str = "1.0.0"
    case_id: str = ""
    invocation_pattern: str = "per_regulation"

    # Content (LLM-emitted, parser-extracted)
    status: P1BLLM01Status
    confidence: P1BLLM01Confidence
    interpretations: list[P1BLLM01Interpretation] = []
    derogations: list[P1BLLM01Derogation] = []

    model_config = {"extra": "ignore"}
```

### T3 — Base class `MarkdownParser`

**Ficheiro:** `src/aegis_phase1/prompts_v2/markdown_parser.py` (NEW)

```python
"""Base class for markdown-output parsers.

CORR-050: replaces JSON Schema enforcement with markdown+regex parsing.
LLM emits markdown following a section/bullet template; parser extracts
structured fields via regex. Pattern proven by OutputParserV3 (used for
MAP-DOMAIN-ADAPT).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class MarkdownParser:
    """Base class. Subclasses define SECTION_PATTERNS and FIELD_PATTERNS.

    Subclasses must implement `parse(raw: str) -> tuple[BaseModel | None, str]`
    returning (parsed_model, error_feedback). If parsing fails, error_feedback
    is a human-readable message the invoker can feed back to the LLM for retry.
    """

    # Override in subclasses: {section_name: compiled_regex_with_named_group}
    SECTION_PATTERNS: dict[str, re.Pattern] = {}

    # Common helpers
    _CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n|\n```\s*$", re.MULTILINE)

    @classmethod
    def _strip_code_fences(cls, text: str) -> str:
        """Tolerate models that wrap markdown in ``` fences."""
        return cls._CODE_FENCE_RE.sub("", text).strip()

    @classmethod
    def _extract_section(cls, text: str, section: str) -> str | None:
        """Extract the body of a `## Section` header until the next `## ` header."""
        pat = cls.SECTION_PATTERNS.get(section)
        if pat is None:
            return None
        m = pat.search(text)
        if m is None:
            return None
        start = m.end()
        # Find next ## header (not ### which is sub-section)
        next_h2 = re.search(r"^##\s+\S", text[start:], re.MULTILINE)
        end = start + next_h2.start() if next_h2 else len(text)
        return text[start:end].strip()

    @classmethod
    def _split_subsections(cls, section_body: str, header_pattern: re.Pattern) -> list[tuple[str, str]]:
        """Split a section body into (sub_header_match, sub_body) pairs.

        Used to split `## Interpretations` into individual `### INT-NN` blocks.
        """
        results: list[tuple[str, str]] = []
        matches = list(header_pattern.finditer(section_body))
        for i, m in enumerate(matches):
            sub_id = m.group(1) if m.groups() else m.group(0)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(section_body)
            results.append((sub_id, section_body[start:end].strip()))
        return results

    @classmethod
    def _extract_field(cls, text: str, field_name: str) -> str | None:
        """Extract `- field_name: value` from text. Returns stripped value or None."""
        pat = re.compile(
            rf"^- \s*{re.escape(field_name)}\s*:\s*(.+?)(?=\n- |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pat.search(text)
        return m.group(1).strip() if m else None

    @classmethod
    def _extract_list_field(cls, text: str, field_name: str) -> list[str]:
        """Extract `- field_name: a, b, c` OR `- field_name:\n  - a\n  - b`.

        Returns list of stripped values.
        """
        # Check multi-bullet form first
        pat_multi = re.compile(
            rf"^- \s*{re.escape(field_name)}\s*:\s*\n((?:\s+-\s+.+\n?)+)",
            re.MULTILINE,
        )
        m_multi = pat_multi.search(text)
        if m_multi:
            return [
                b.strip().lstrip("-").strip()
                for b in m_multi.group(1).split("\n")
                if b.strip().lstrip("-").strip()
            ]
        # Single line, comma-separated
        single = cls._extract_field(text, field_name)
        if single is None:
            return []
        return [v.strip() for v in single.split(",") if v.strip()]

    def parse(self, raw: str) -> tuple[BaseModel | None, str]:
        """Override in subclass. Returns (model_instance, error_feedback)."""
        raise NotImplementedError
```

### T4 — `P1BLLM01Parser` concreto

**Ficheiro:** `src/aegis_phase1/prompts_v2/markdown_parser.py` (extender, mesmo ficheiro)

```python
class P1BLLM01Parser(MarkdownParser):
    """Parser for P1B-LLM-01-INTERPRETATION markdown output."""

    SECTION_PATTERNS = {
        "status": re.compile(r"^##\s+Status\s*$", re.MULTILINE),
        "interpretations": re.compile(r"^##\s+Interpretations\s*$", re.MULTILINE),
        "derogations": re.compile(r"^##\s+Derogations\s*$", re.MULTILINE),
    }
    _SUBSEC_INT = re.compile(r"^###\s+(INT-\d+)\s*$", re.MULTILINE)
    _SUBSEC_DER = re.compile(r"^###\s+(DER-\d+)\s*$", re.MULTILINE)

    def parse(self, raw: str) -> tuple[P1BLLM01Output | None, str]:
        text = self._strip_code_fences(raw)

        # Status section (required)
        status_body = self._extract_section(text, "status")
        if status_body is None:
            return None, "Missing '## Status' section. Add it with `- status: OK|INSUFFICIENT_EVIDENCE|INDETERMINATE` and `- confidence: HIGH|MEDIUM|LOW`."
        status_str = (self._extract_field(status_body, "status") or "").upper()
        conf_str = (self._extract_field(status_body, "confidence") or "").upper()
        if status_str not in {e.value for e in P1BLLM01Status}:
            return None, f"Invalid status '{status_str}'. Must be one of: OK, INSUFFICIENT_EVIDENCE, INDETERMINATE."

        # Interpretations section
        interpretations: list[P1BLLM01Interpretation] = []
        interp_body = self._extract_section(text, "interpretations") or ""
        for sub_id, sub_body in self._split_subsections(interp_body, self._SUBSEC_INT):
            entry_id = self._extract_field(sub_body, "entry_id") or ""
            applicable_str = (self._extract_field(sub_body, "applicable") or "").upper()
            if applicable_str not in {e.value for e in P1BLLM01Applicable}:
                return None, f"{sub_id}: invalid 'applicable' value '{applicable_str}'. Must be YES or NO."
            rationale = self._extract_field(sub_body, "activation_rationale") or ""
            interpretations.append(P1BLLM01Interpretation(
                entry_id=entry_id,
                applicable=P1BLLM01Applicable(applicable_str),
                activation_rationale=rationale,
                layer0_refs=self._extract_list_field(sub_body, "layer0_refs"),
                legal_refs=self._extract_list_field(sub_body, "legal_refs"),
                company_fact_refs=self._extract_list_field(sub_body, "company_fact_refs"),
            ))

        # Derogations section
        derogations: list[P1BLLM01Derogation] = []
        der_body = self._extract_section(text, "derogations") or ""
        for sub_id, sub_body in self._split_subsections(der_body, self._SUBSEC_DER):
            entry_id = self._extract_field(sub_body, "entry_id") or ""
            verdict_str = (self._extract_field(sub_body, "activation_verdict") or "").upper()
            if verdict_str not in {e.value for e in P1BLLM01DerogationVerdict}:
                return None, f"{sub_id}: invalid 'activation_verdict' value '{verdict_str}'. Must be ACTIVATED, NOT_ACTIVATED, or INDETERMINATE."
            rationale = self._extract_field(sub_body, "activation_rationale") or ""
            derogations.append(P1BLLM01Derogation(
                entry_id=entry_id,
                activation_verdict=P1BLLM01DerogationVerdict(verdict_str),
                activation_rationale=rationale,
                layer0_refs=self._extract_list_field(sub_body, "layer0_refs"),
                legal_refs=self._extract_list_field(sub_body, "legal_refs"),
                company_fact_refs=self._extract_list_field(sub_body, "company_fact_refs"),
            ))

        # Build envelope-less model; envelope injected by invoker
        try:
            confidence = P1BLLM01Confidence(conf_str) if conf_str in {e.value for e in P1BLLM01Confidence} else P1BLLM01Confidence.MEDIUM
            model = P1BLLM01Output(
                status=P1BLLM01Status(status_str),
                confidence=confidence,
                interpretations=interpretations,
                derogations=derogations,
            )
            return model, ""
        except ValidationError as e:
            return None, f"Pydantic validation failed: {e}"


# Registry of parsers per spec_id (extensible for CORR-051)
MARKDOWN_PARSERS: dict[str, type[MarkdownParser]] = {
    "P1B-LLM-01-INTERPRETATION": P1BLLM01Parser,
}
```

### T5 — Invoker: usar markdown parser + injetar envelope

**Ficheiro:** `src/aegis_phase1/prompts_v2/invoker.py`

**Localização:** o sítio onde hoje se faz `output = parse_result.json` seguido
de `self.validator.validate(...)`. Procurar por `parse_result.json` em invoker.py.

**Lógica nova (substituir o bloco de validação):**

```python
# CORR-050: markdown+regex parsing for LLMs with a registered MarkdownParser.
# JSON Schema validator (Phase1Validator) is bypassed for these specs.
from aegis_phase1.prompts_v2.markdown_parser import MARKDOWN_PARSERS

output = parse_result.json  # ainda usamos RobustParser para extrair o texto/markdown
if not isinstance(output, dict):
    # markdown output não é dict — usar o raw text
    raw_text = parse_result.raw if hasattr(parse_result, "raw") else str(output)
    output = {"_raw_text": raw_text}

parser_cls = MARKDOWN_PARSERS.get(spec_id)
if parser_cls is not None:
    raw_text = output.get("_raw_text", "") if isinstance(output, dict) else str(output)
    parser = parser_cls()
    parsed_model, error_feedback = parser.parse(raw_text)
    if parsed_model is None:
        validation_result = {"valid": False, "errors": [error_feedback], "warnings": []}
    else:
        # CORR-050: inject deterministic envelope fields (never LLM-emitted)
        parsed_model.case_id = inputs.get("case_id", "")
        parsed_model.prompt_spec_id = spec_id
        parsed_model.schema_version = "1.0.0"
        parsed_model.invocation_pattern = invocation_pattern  # already computed at line 173
        output = parsed_model.model_dump()
        validation_result = {"valid": True, "warnings": []}
elif self.validator:
    # Legacy path: LLMs without a MarkdownParser still use JSON Schema
    validation_result = self.validator.validate(spec_id, output, inputs)
else:
    validation_result = {"valid": True, "warnings": []}
```

**Atenção:**
- `parse_result.raw` — confirmar que RobustParser expõe o texto raw (não só `.json`).
  Se não, adicionar `.raw` attribute ou usar `parse_result.text`.
- `invocation_pattern` já é computado algures no invoker (linha 173 segundo
  diagnóstico anterior). Reutilizar a variável.
- Manter o path legacy (`self.validator`) para specs sem parser registado —
  os outros 4 LLMs continuam a usar JSON Schema até CORR-051.

**Também:** remover o `format=schema` do Ollama invoke para specs que têm
MarkdownParser. Procurar `format=` em invoker.py (à volta da linha 322):
```python
# Antes:
schema = ... or {}
if schema:
    invoke_kwargs["format"] = schema

# Depois:
if spec_id not in MARKDOWN_PARSERS:
    schema = ... or {}
    if schema:
        invoke_kwargs["format"] = schema
# Para specs com MarkdownParser: não passar format=, deixar markdown livre
```

### T6 — Testes P1B-LLM-01 parser

**Ficheiro:** `tests/unit/prompts_v2/test_markdown_parser_corr050.py` (NEW)

```python
"""CORR-050: tests for markdown+regex parsing of P1B-LLM-01."""

import pytest
from aegis_phase1.prompts_v2.markdown_parser import P1BLLM01Parser
from aegis_phase1.v2.state import P1BLLM01Output, P1BLLM01Status, P1BLLM01Confidence, P1BLLM01Applicable

VALID_OUTPUT = """## Status

- status: OK
- confidence: HIGH

## Interpretations

### INT-01

- entry_id: TIPO2-GDPR-RTS-DEADLINES
- applicable: YES
- activation_rationale: Company processes personal data.
- layer0_refs: SubDomains/D-04.3.md
- legal_refs: GDPR Art. 33(1), GDPR Art. 34(1)
- company_fact_refs: processes_personal_data=true

## Derogations

### DER-01

- entry_id: TIPO3-GDPR-HOUSEHOLD
- activation_verdict: NOT_ACTIVATED
- activation_rationale: Company is SaaS, not household.
- layer0_refs: SubDomains/D-04.3.md
- legal_refs: GDPR Art. 2(2)(c)
- company_fact_refs: business_activity=saas_provider
"""

def test_valid_full_output_parses():
    parser = P1BLLM01Parser()
    model, err = parser.parse(VALID_OUTPUT)
    assert model is not None, f"Parse failed: {err}"
    assert model.status == P1BLLM01Status.OK
    assert model.confidence == P1BLLM01Confidence.HIGH
    assert len(model.interpretations) == 1
    assert model.interpretations[0].entry_id == "TIPO2-GDPR-RTS-DEADLINES"
    assert model.interpretations[0].applicable == P1BLLM01Applicable.YES
    assert len(model.interpretations[0].legal_refs) == 2
    assert len(model.derogations) == 1
    assert model.derogations[0].entry_id == "TIPO3-GDPR-HOUSEHOLD"

def test_missing_status_section_returns_error():
    parser = P1BLLM01Parser()
    model, err = parser.parse("## Interpretations\n\n(empty)")
    assert model is None
    assert "Status" in err

def test_invalid_status_enum_returns_error():
    parser = P1BLLM01Parser()
    bad = VALID_OUTPUT.replace("- status: OK", "- status: MAYBE")
    model, err = parser.parse(bad)
    assert model is None
    assert "MAYBE" in err or "status" in err.lower()

def test_code_fence_tolerated():
    parser = P1BLLM01Parser()
    fenced = f"```markdown\n{VALID_OUTPUT}\n```"
    model, err = parser.parse(fenced)
    assert model is not None, f"Should tolerate fence: {err}"

def test_multi_bullet_list_field():
    parser = P1BLLM01Parser()
    multi = VALID_OUTPUT.replace(
        "- legal_refs: GDPR Art. 33(1), GDPR Art. 34(1)",
        "- legal_refs:\n  - GDPR Art. 33(1)\n  - GDPR Art. 34(1)",
    )
    model, _ = parser.parse(multi)
    assert model is not None
    assert len(model.interpretations[0].legal_refs) == 2

def test_empty_interpretations_section_ok():
    """No Tipo 2 entries applicable — Interpretations can be empty."""
    parser = P1BLLM01Parser()
    output = """## Status

- status: OK
- confidence: MEDIUM

## Interpretations

(none applicable)

## Derogations

(none applicable)
"""
    model, err = parser.parse(output)
    assert model is not None, f"Empty lists should be OK: {err}"
    assert len(model.interpretations) == 0
    assert len(model.derogations) == 0

def test_envelope_fields_default_in_model():
    """Pydantic model has envelope defaults; invoker overrides post-parse."""
    m = P1BLLM01Output(
        status=P1BLLM01Status.OK,
        confidence=P1BLLM01Confidence.HIGH,
    )
    assert m.prompt_spec_id == "P1B-LLM-01-INTERPRETATION"
    assert m.schema_version == "1.0.0"
    assert m.invocation_pattern == "per_regulation"
```

### T7 — Run real + verificar Langfuse

```bash
source ../shared-venv/bin/activate

# Snapshot
mkdir -p output/phase1/baseline_pre_corr050/
cp output/phase1/*.md output/phase1/*.xlsx output/phase1/baseline_pre_corr050/ 2>/dev/null

# Run só da fase 1B (P1B-LLM-01/02 × 2 regs = 4 calls), mas só P1B-LLM-01
# vai usar markdown parser; P1B-LLM-02 ainda usa JSON Schema (CORR-051).
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --run-phase-1b \
    2>&1 | tee logs/phase1/corr050_run_phase1b.log
```

**Esperado pós-fix:**
- 2 P1B-LLM-01 calls (GDPR + CRA) — sem SCHEMA_ERROR; markdown parsed com sucesso
- 2 P1B-LLM-02 calls — ainda podem ter SCHEMA_ERROR (CORR-051 converte)
- Langfuse: abrir generation P1B-LLM-01, validar que output é markdown
  (não JSON) e que tem secções `## Status`, `## Interpretations`, `## Derogations`

Guardar trace_id em `logs/phase1/corr050_langfuse_trace_id.txt`.

### T8 — Documentar padrão para CORR-051

**Ficheiro:** `docs/CORR-051_pattern.md` (NEW, opcional)

Documentar o padrão markdown+regex para os outros 4 LLMs:
- Template markdown structure (varia por LLM)
- Parser class espelhando P1BLLM01Parser
- Pydantic model em state.py
- Registo no MARKDOWN_PARSERS dict

Isto facilita o trabalho de CORR-051.

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — Template P1B-LLM-01 tem secção Output Format (não Output Schema)
grep -q "^## Output Format" "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md" && echo "G1 OK" || { echo "FAIL G1: template não aplicado"; exit 1; }

# G2 — Template menciona regra "Do NOT emit JSON"
grep -q "Do NOT emit JSON\|Do NOT include prompt_spec_id" "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md" && echo "G2 OK" || { echo "FAIL G2: regra anti-JSON em falta"; exit 1; }

# G3 — Pydantic models P1BLLM01 definidos
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.v2.state import P1BLLM01Output, P1BLLM01Interpretation, P1BLLM01Derogation, P1BLLM01Status
print('G3 OK')
" || { echo "FAIL G3"; exit 1; }

# G4 — MarkdownParser base + P1BLLM01Parser existem
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.prompts_v2.markdown_parser import MarkdownParser, P1BLLM01Parser, MARKDOWN_PARSERS
assert 'P1B-LLM-01-INTERPRETATION' in MARKDOWN_PARSERS
print('G4 OK')
" || { echo "FAIL G4"; exit 1; }

# G5 — Parser parseia exemplo válido
python -c "
import sys; sys.path.insert(0, 'src')
from aegis_phase1.prompts_v2.markdown_parser import P1BLLM01Parser
example = '''## Status

- status: OK
- confidence: HIGH

## Interpretations

### INT-01

- entry_id: TIPO2-GDPR-RTS-DEADLINES
- applicable: YES
- activation_rationale: test rationale
- layer0_refs: SubDomains/D-04.3.md
- legal_refs: GDPR Art. 33(1)
- company_fact_refs: fact

## Derogations

### DER-01

- entry_id: TIPO3-GDPR-HOUSEHOLD
- activation_verdict: NOT_ACTIVATED
- activation_rationale: test
- layer0_refs: foo
- legal_refs: bar
- company_fact_refs: baz
'''
model, err = P1BLLM01Parser().parse(example)
assert model is not None, f'parse failed: {err}'
assert model.status.value == 'OK'
assert len(model.interpretations) == 1
assert len(model.derogations) == 1
print('G5 OK')
" || { echo "FAIL G5"; exit 1; }

# G6 — Invoker usa markdown parser para P1B-LLM-01
grep -q "MARKDOWN_PARSERS\|markdown_parser" src/aegis_phase1/prompts_v2/invoker.py && echo "G6 OK" || { echo "FAIL G6: invoker não integrado"; exit 1; }

# G7 — Testes parser passam
pytest tests/unit/prompts_v2/test_markdown_parser_corr050.py -q 2>&1 | tail -1 | grep -qE "passed" && echo "G7 OK" || { echo "FAIL G7"; exit 1; }

# G8 — Suite completa verde (sem regressões nos outros LLMs)
pytest tests/unit/v2/ tests/unit/prompts_v2/ -q 2>&1 | tail -3 | grep -qE "passed" && echo "G8 OK" || { echo "FAIL G8"; exit 1; }

# G9 — Run real: P1B-LLM-01 sem SCHEMA_ERROR
test -f logs/phase1/corr050_run_phase1b.log && \
    ! grep -E "P1B-LLM-01-INTERPRETATION.*SCHEMA_ERROR" logs/phase1/corr050_run_phase1b.log && echo "G9 OK" || { echo "FAIL G9: P1B-LLM-01 ainda SCHEMA_ERROR"; exit 1; }

# G10 — Langfuse trace_id capturado
test -s logs/phase1/corr050_langfuse_trace_id.txt && echo "G10 OK (manual verify markdown output in Langfuse)" || echo "G10 WARN"

# G11 — CI gates
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G11 OK" || { echo "FAIL G11"; exit 1; }

echo "=== ALL 11 GATES PASSED ==="
```

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `Methodology-main/00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md` | **MODIFY (T1)** — substituir `## Output Schema` por `## Output Format` markdown (template acima) |
| `src/aegis_phase1/v2/state.py` | **MODIFY (T2)** — adicionar P1BLLM01* models + enums |
| `src/aegis_phase1/prompts_v2/markdown_parser.py` | **NEW (T3+T4)** — `MarkdownParser` base + `P1BLLM01Parser` + `MARKDOWN_PARSERS` registry |
| `src/aegis_phase1/prompts_v2/invoker.py` | **MODIFY (T5)** — integrar markdown parser path + envelope injection + remover `format=` para specs com parser |
| `tests/unit/prompts_v2/test_markdown_parser_corr050.py` | **NEW (T6)** — 7 testes |
| `output/phase1/baseline_pre_corr050/` | **NEW (T7)** — snapshot |
| `output/phase1/*.md` (parcial) | **REGENERATED (T7)** — só se --run-phase-1b afetar outputs |
| `logs/phase1/corr050_run_phase1b.log` | **NEW (T7)** |
| `logs/phase1/corr050_langfuse_trace_id.txt` | **NEW (T7)** |
| `docs/CORR-051_pattern.md` | **NEW (T8, opcional)** — documentação para CORR-051 |
| `execution/CONTRACT-050.md` | **NEW** (este) |

**Não modificar:** `preproc_out/`, `.hooks/`, `cases/case1-tinytask/input/*.yaml`,
os outros 4 prompt MDs (P1B-LLM-02, P1C-LLM-01/02/03 — são CORR-051).

**`output_schemas.yaml`:** manter em disco como documentação histórica (não
apagar). O código deixa de o usar para validar P1B-LLM-01 (Pydantic substitui).

---

## Estrutura de commits

```
feature/aegis-p1-corr-050
├─ commit 1: T1 P1B-LLM-01 template markdown
├─ commit 2: T2 Pydantic models P1BLLM01*
├─ commit 3: T3+T4 MarkdownParser base + P1BLLM01Parser + registry
├─ commit 4: T5 invoker integration + envelope injection + remove format=
├─ commit 5: T6 testes parser (7 casos)
├─ commit 6: T7 run-phase-1b + Langfuse verification
└─ commit 7: T8 docs CORR-051 pattern (opcional)
```

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| `gemma4:e2b` ainda emite JSON apesar do template markdown | O parser tolera ``` fences (strip); se output for JSON puro, fallback para `RobustParser.parse()` + log WARNING |
| Regex parser parte com whitespace/variações não previstas | `_extract_field` usa `\s*` generoso; testes T6 cobrem variações (fence, multi-bullet) |
| `parse_result.raw` não existe no RobustParser | Verificar antes: `python -c "from aegis_phase1.prompts_v2.robust_parser import RobustParser; ..."`. Se faltar, adicionar `.raw` ou usar o último strategy output |
| Output de P1B-LLM-02 (ainda JSON Schema) pode regredir | Path legacy mantém `self.validator` para specs sem parser; testes G8 garantem que suite não regrediu |
| Template markdown não incluiu campo crítico que downstream precisa | Audit: garantir que todos os fields que downstream lê (`interpretations[].entry_id`, etc.) estão no template |
| `Pydantic ValidationError` em produção com dados do mundo real | Modelos usam `extra="ignore"` para tolerar fields extras; defaults razoáveis onde possível |

---

## Pós-CORR-050

**Se G1–G11 passarem:** P1B-LLM-01 deixa de produzir SCHEMA_ERROR. Markdown
natural + regex parsing + envelope injection funcionam end-to-end. **CORR-051**
replica o padrão para os outros 4 LLMs (P1B-LLM-02, P1C-LLM-01, P1C-LLM-02,
P1C-LLM-03).

**Se G9 falhar** (P1B-LLM-01 ainda SCHEMA_ERROR): investigar via Langfuse o
output real do modelo. Provavelmente está a emitir JSON apesar do template
— pode ser preciso tornar o template ainda mais explícito OU usar fallback
`RobustParser` para extrair JSON e converter para struct.

---

## Change log

- 2026-07-22: v1.0 — contract inicial criado pelo orchestrator após
  diagnóstico de que JSON Schema rígido força o `gemma4:e2b` a emitir
  free-form. Mudança para markdown natural + regex + Pydantic. Infra +
  1 exemplo (P1B-LLM-01); outros 4 LLMs ficam para CORR-051.
