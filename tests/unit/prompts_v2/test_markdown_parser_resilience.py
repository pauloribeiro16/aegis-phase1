"""Tests for markdown parser resilience with real-world open-weight model quirks."""

import pytest

from aegis_phase1.prompts_v2.markdown_parser import GenericMarkdownParser, P1BLLM01Parser
from aegis_phase1.v2.state import (
    P1BLLM01Applicable,
    P1BLLM01Confidence,
    P1BLLM01DerogationVerdict,
    P1BLLM01Status,
)


def test_markdown_parser_with_preamble_and_fences():
    raw_output = """Here is the complete regulatory assessment for the requested regulation:

```markdown
## 1. Status:
- **status**: **APPLICABLE**
- **confidence**: **HIGH**

## 2. Interpretations
### INT-01
- **entry_id**: TIPO2-GDPR-RTS-DEADLINES
- **applicable**: **YES**
- **activation_rationale**: Company processes personal data of EU users.
- **layer0_refs**: SubDomains/D-04.3.md
- **legal_refs**: GDPR Art. 33(1), GDPR Art. 34(1)
- **company_fact_refs**: processes_personal_data=true

## 3. Derogations
### DER-01
- **entry_id**: TIPO3-GDPR-HOUSEHOLD
- **activation_verdict**: NOT_ACTIVATED
- **activation_rationale**: Company is SaaS, not household.
- **layer0_refs**: SubDomains/D-04.3.md
- **legal_refs**: GDPR Art. 2(2)(c)
- **company_fact_refs**: business_activity=saas_provider
```

I hope this analysis is helpful! Let me know if you need further clarifications.
"""
    parser = P1BLLM01Parser()
    model, err = parser.parse(raw_output)
    assert model is not None, f"Parse failed: {err}"
    assert model.status == P1BLLM01Status.YES
    assert model.confidence == P1BLLM01Confidence.HIGH
    assert len(model.interpretations) == 1
    assert model.interpretations[0].entry_id == "TIPO2-GDPR-RTS-DEADLINES"
    assert model.interpretations[0].applicable == P1BLLM01Applicable.YES
    assert len(model.derogations) == 1
    assert (
        model.derogations[0].activation_verdict
        == P1BLLM01DerogationVerdict.NOT_ACTIVATED
    )


def test_markdown_parser_bullet_variations():
    raw_output = """# Status
* **applicable:** YES
* **confidence:** MEDIUM

# Interpretations
- **ENTRY_GDPR_CORE** (APPLICABLE): Processing cloud telemetry with PII.
- **ENTRY_GDPR_DPO** (NOT_APPLICABLE): Core activities do not require large-scale systematic monitoring.

# Derogations
- **DER_MICRO_EXEMPTION** (NOT_ACTIVATED): Enterprise scale exceeds micro-threshold.
"""
    parser = P1BLLM01Parser()
    model, err = parser.parse(raw_output)
    assert model is not None, f"Parse failed: {err}"
    assert model.status == P1BLLM01Status.YES
    assert model.confidence == P1BLLM01Confidence.MEDIUM
    assert len(model.interpretations) == 2
    assert model.interpretations[0].entry_id == "ENTRY_GDPR_CORE"
    assert model.interpretations[0].applicable == P1BLLM01Applicable.YES
    assert model.interpretations[1].applicable == P1BLLM01Applicable.NO
    assert len(model.derogations) == 1
    assert (
        model.derogations[0].activation_verdict
        == P1BLLM01DerogationVerdict.NOT_ACTIVATED
    )


def test_generic_markdown_parser_with_bold_headers():
    raw_output = """```markdown
## 1. Status Assessment
- **status:** OK
- **confidence:** HIGH

## 2. Executive Rationale
This regulation applies due to financial operations in the EU.

## 3. High Risk Findings
Critical systems require MFA and encryption at rest.
```"""
    parser = GenericMarkdownParser()
    model, err = parser.parse(raw_output)
    assert model is not None, f"Parse failed: {err}"
    assert model.status == P1BLLM01Status.OK
    assert model.confidence == P1BLLM01Confidence.HIGH
    assert "Executive Rationale" in model.sections
    assert "High Risk Findings" in model.sections
