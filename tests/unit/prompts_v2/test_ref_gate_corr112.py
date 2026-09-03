"""Tests for RefGate and invoker feedback retry (CORR-112)."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aegis_phase1.prompts_v2.ref_gate import RefGate, GateResult, GateViolation
from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker
from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.catalog import CatalogLoader


@pytest.fixture
def ref_gate() -> RefGate:
    return RefGate()


def test_p1b01_valid_output(ref_gate: RefGate):
    raw = """
## Interpretations
### INT-01: GDPR-RTS-DEADLINES
- entry_id: TIPO2-GDPR-RTS-DEADLINES
- applicable: YES
- activation_rationale: Applies to company.

## Derogations
### TIPO3-GDPR-HOUSEHOLD
- entry_id: TIPO3-GDPR-HOUSEHOLD
- activation_verdict: NOT_ACTIVATED
- activation_rationale: Company is a commercial entity.
"""
    res = ref_gate.validate("P1B-LLM-01-INTERPRETATION", raw, inputs={})
    assert res.valid is True
    assert len(res.violations) == 0


def test_p1b01_invalid_verdict(ref_gate: RefGate):
    raw = """
## Derogations
### TIPO3-GDPR-HOUSEHOLD
- entry_id: TIPO3-GDPR-HOUSEHOLD
- activation_verdict: MAYBE_APPLICABLE
"""
    res = ref_gate.validate("P1B-LLM-01-INTERPRETATION", raw, inputs={})
    assert res.valid is False
    assert any(v.rule == "INVALID_VERDICT" for v in res.violations)


def test_p1b01_duplicate_int_id(ref_gate: RefGate):
    raw = """
## Interpretations
### INT-1
- entry_id: TIPO2-GDPR-RTS-DEADLINES
### INT-1
- entry_id: TIPO2-CRA-ART14-DUAL-FLOW
"""
    res = ref_gate.validate("P1B-LLM-01-INTERPRETATION", raw, inputs={})
    assert res.valid is False
    assert any(v.rule == "DUPLICATE_INT_ID" for v in res.violations)


def test_p1b01_unknown_catalog_id(ref_gate: RefGate):
    raw = """
## Interpretations
- entry_id: TIPO2-GDPR-FAKE-NONEXISTENT
"""
    res = ref_gate.validate("P1B-LLM-01-INTERPRETATION", raw, inputs={})
    assert res.valid is False
    assert any(v.rule == "UNKNOWN_CATALOG_ID" for v in res.violations)


def test_p1b01_unauthorised_subdomain(ref_gate: RefGate):
    raw = """
## Interpretations
- sub_domain_id: D-09.9
"""
    inputs = {"authoritative_ids": {"subdomain_ids": ["D-01.1", "D-04.3"]}}
    res = ref_gate.validate("P1B-LLM-01-INTERPRETATION", raw, inputs=inputs)
    assert res.valid is False
    assert any(v.rule == "UNAUTHORISED_SUBDOMAIN" for v in res.violations)


def test_p1b02_valid_output(ref_gate: RefGate):
    raw = """
## Rationale
TinyTask is a MICRO company processing data on SYS-01 on AWS eu-west-1.
Per GDPR Art. 32(1), technical measures are required.

## Findings
### Implications
- implication: IMP-1
  effort_estimate: hours to days (LOW tier, MICRO company)
  company_fact_refs: DOC04:ARCH-01 SYS-01
"""
    res = ref_gate.validate("P1B-LLM-02-RATIONALE", raw, inputs={})
    assert res.valid is True


def test_p1b02_invented_statistics(ref_gate: RefGate):
    raw = """
## Rationale
TinyTask reduced by 45% effort across operations with 3.5 million euros in annual savings.
SYS-01 architecture facts referenced.
"""
    res = ref_gate.validate("P1B-LLM-02-RATIONALE", raw, inputs={})
    assert res.valid is False
    assert any(v.rule == "INVENTED_STATISTICS" for v in res.violations)


def test_p1b02_missing_doc04_grounding(ref_gate: RefGate):
    raw = """
## Rationale
GDPR applies universally to all European entities processing data.
"""
    res = ref_gate.validate("P1B-LLM-02-RATIONALE", raw, inputs={})
    assert res.valid is False
    assert any(v.rule == "MISSING_DOC04_GROUNDING" for v in res.violations)


def test_p1b02_invalid_effort_estimate(ref_gate: RefGate):
    raw = """
## Rationale
SYS-01 DOC04 facts present.
## Findings
- effort_estimate: instant magic
"""
    res = ref_gate.validate("P1B-LLM-02-RATIONALE", raw, inputs={})
    assert res.valid is False
    assert any(v.rule == "INVALID_EFFORT_ESTIMATE" for v in res.violations)


def test_p1c01_valid_output(ref_gate: RefGate):
    raw = """
## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-01.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED — TinyTask is controller and manufacturer.
"""
    inputs = {
        "authoritative_ids": {
            "subdomain_ids": ["D-01.1", "D-01.2"],
            "regulation_ids": ["GDPR", "CRA"],
        }
    }
    res = ref_gate.validate("P1C-LLM-01-OVERLAP-CLASSIFICATION", raw, inputs=inputs)
    assert res.valid is True


def test_p1c01_unauthorised_subdomain(ref_gate: RefGate):
    raw = """
## Status
- applicable: YES
- D-07.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED
"""
    inputs = {
        "authoritative_ids": {
            "subdomain_ids": ["D-01.1", "D-01.2"],
            "regulation_ids": ["GDPR", "CRA"],
        }
    }
    res = ref_gate.validate("P1C-LLM-01-OVERLAP-CLASSIFICATION", raw, inputs=inputs)
    assert res.valid is False
    assert any(v.rule == "UNAUTHORISED_SUBDOMAIN" for v in res.violations)


def test_p1c01_unauthorised_regulation_pair(ref_gate: RefGate):
    raw = """
## Status
- applicable: YES
- D-01.1 : GDPR ↔ NIS2: OVERLAP_CONFIRMED
"""
    inputs = {
        "authoritative_ids": {
            "subdomain_ids": ["D-01.1"],
            "regulation_ids": ["GDPR", "CRA"],
        }
    }
    res = ref_gate.validate("P1C-LLM-01-OVERLAP-CLASSIFICATION", raw, inputs=inputs)
    assert res.valid is False
    assert any(v.rule == "UNAUTHORISED_REGULATION_PAIR" for v in res.violations)


def test_generic_marker_rejected_across_all(ref_gate: RefGate):
    raw = """
## Status
- D-01.1 references DOC04:SEC-NN and D-XX.Y generic markers.
"""
    res = ref_gate.validate("P1C-LLM-01-OVERLAP-CLASSIFICATION", raw, inputs={})
    assert res.valid is False
    assert any(v.rule == "GENERIC_MARKER" for v in res.violations)


def test_invoker_feedback_retry_flow():
    """Demonstrate: raw with violations -> retry with feedback -> clean response -> OK."""
    prompt_loader = MagicMock(spec=PromptLoader)
    prompt_loader.render.return_value = {"system": "sys", "user": "user"}
    prompt_loader.load.return_value = {}

    catalog_loader = MagicMock(spec=CatalogLoader)
    catalog_loader.load.return_value = []

    invoker = Phase1LLMInvoker(
        prompt_loader=prompt_loader,
        catalog_loader=catalog_loader,
    )

    bad_raw = """## Rationale
Generic claim with 45% effort reduction without SYS-01 grounding."""
    good_raw = """## Rationale
SYS-01 on AWS eu-west-1 complies with GDPR Art. 32(1).
## Findings
- effort_estimate: hours to days"""

    mock_resp1 = MagicMock(content=bad_raw)
    mock_resp2 = MagicMock(content=good_raw)

    with patch.dict(os.environ, {"AEGIS_GATE_MODE": "hard"}):
        with patch.object(invoker, "_attempt") as mock_att:
            mock_att.side_effect = [
                {
                    "ok": False,
                    "raw_response": bad_raw,
                    "gate_result": GateResult(valid=False, violations=[GateViolation("INVENTED_STATISTICS", "45% reduction")], feedback="Fix statistics"),
                    "parsed_output": None,
                    "validation": {"valid": False},
                },
                {
                    "ok": True,
                    "raw_response": good_raw,
                    "gate_result": GateResult(valid=True, violations=[]),
                    "parsed_output": {"rationale": good_raw},
                    "validation": {"valid": True},
                },
            ]
            res = invoker.invoke(
                "P1B-LLM-02-RATIONALE",
                inputs={"case_id": "case1"},
                max_retries=3,
            )
            assert res["status"] == "OK"
            assert res["retry_count"] == 2
            assert len(res["all_attempts"]) == 2
            assert res["all_attempts"][0]["ok"] is False
            assert res["all_attempts"][1]["ok"] is True
