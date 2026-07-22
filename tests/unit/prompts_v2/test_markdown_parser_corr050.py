"""CORR-050: tests for markdown+regex parsing of P1B-LLM-01."""

import pytest

from aegis_phase1.prompts_v2.markdown_parser import P1BLLM01Parser
from aegis_phase1.v2.state import (
    P1BLLM01Applicable,
    P1BLLM01Confidence,
    P1BLLM01DerogationVerdict,
    P1BLLM01Output,
    P1BLLM01Status,
)

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
    assert (
        model.derogations[0].activation_verdict
        == P1BLLM01DerogationVerdict.NOT_ACTIVATED
    )


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
    assert model.interpretations[0].legal_refs[0] == "GDPR Art. 33(1)"
    assert model.interpretations[0].legal_refs[1] == "GDPR Art. 34(1)"


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
    assert m.case_id == ""  # invoker will fill this
