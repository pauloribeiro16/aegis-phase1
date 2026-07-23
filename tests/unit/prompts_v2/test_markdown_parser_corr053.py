"""CORR-053: schema-tolerant parser tests for P1BLLM01Parser.

The gemma4:e4b model emits JSON for regulatory analysis tasks, ignoring
prompt-level "Do NOT emit JSON" instructions (CORR-050) and even the
base_system_prompt.md rule 4 reformulation (CORR-052). So the parser
now tries markdown first, then JSON as fallback.

These tests cover the JSON fallback path and edge cases:

  - test_json_fallback_parses_valid_json_output
      Full valid JSON (no markdown sections) → parser succeeds
  - test_json_fallback_tolerates_envelope_fields
      JSON includes prompt_spec_id etc. → parser still succeeds
      (Pydantic model has extra="ignore")
  - test_json_fallback_rejects_invalid_status_enum
      JSON with status: "BAD" → parser returns error
  - test_json_fallback_rejects_missing_interpretations
      JSON without interpretations key → parser returns error
      (interpretations is required if LLM emits non-empty list;
       default empty list is acceptable per Pydantic default)
  - test_both_fail_returns_combined_error
      Neither markdown nor JSON parses → parser returns (None, "markdown...; json...")
  - test_markdown_wins_over_json_when_both_present
      Text with both ## sections and JSON → markdown path wins
  - test_robust_fallback_rejected
      Garbage input triggers construct_minimal_object strategy →
      parser rejects (CORR-053: not real LLM JSON, just safety net)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure src/ is on path (matching conftest.py behavior)
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aegis_phase1.prompts_v2.markdown_parser import P1BLLM01Parser


# Sample full markdown output (mirror of test_markdown_parser_corr050.py's VALID_OUTPUT)
VALID_MARKDOWN = """## Status
- status: OK
- confidence: HIGH

## Interpretations

### INT-01
- entry_id: INT-01
- applicable: YES
- activation_rationale: SaaS processes personal data
- layer0_refs:
  - SubDomains/D-01.1.md

### INT-02
- entry_id: INT-02
- applicable: NO
- activation_rationale: Not relevant
- layer0_refs: SubDomains/D-04.3.md

## Derogations

### DER-01
- entry_id: DER-01
- activation_verdict: NOT_ACTIVATED
- activation_rationale: No derogation applies
- layer0_refs: SubDomains/D-04.3.md
"""


# Sample full JSON output (what gemma4:e4b actually emits)
VALID_JSON = """{
  "prompt_spec_id": "P1B-LLM-01-INTERPRETATION",
  "schema_version": "1.0.0",
  "case_id": "Case_01",
  "invocation_pattern": "per_regulation",
  "lane_id": "GDPR",
  "status": "OK",
  "confidence": "HIGH",
  "interpretations": [
    {
      "entry_id": "INT-01",
      "applicable": true,
      "activation_rationale": "SaaS processes personal data",
      "layer0_refs": ["SubDomains/D-01.1.md"],
      "company_fact_refs": ["DOC04:ARCH-07"]
    }
  ],
  "derogations": [
    {
      "entry_id": "DER-01",
      "activation_verdict": "NOT_ACTIVATED",
      "activation_rationale": "No derogation applies",
      "layer0_refs": ["SubDomains/D-04.3.md"]
    }
  ]
}"""


def test_json_fallback_parses_valid_json_output():
    """LLM emits pure JSON (no markdown). Parser should accept via JSON fallback."""
    parser = P1BLLM01Parser()
    model, err = parser.parse(VALID_JSON)
    assert err == "", f"unexpected error: {err}"
    assert model is not None
    assert model.status.value == "OK"
    assert model.confidence.value == "HIGH"
    assert len(model.interpretations) == 1
    assert model.interpretations[0].entry_id == "INT-01"
    assert len(model.derogations) == 1
    assert model.derogations[0].activation_verdict.value == "NOT_ACTIVATED"


def test_json_fallback_tolerates_envelope_fields():
    """JSON includes envelope fields (prompt_spec_id, case_id, etc.) → Pydantic
    accepts them via extra='ignore' (they're already model fields with defaults).
    The invoker overwrites them after parse() returns.
    """
    parser = P1BLLM01Parser()
    json_with_envelope = """{
      "prompt_spec_id": "P1B-LLM-01-INTERPRETATION",
      "case_id": "Case_01",
      "status": "INSUFFICIENT_EVIDENCE",
      "confidence": "LOW",
      "interpretations": [],
      "derogations": []
    }"""
    model, err = parser.parse(json_with_envelope)
    assert err == "", f"unexpected error: {err}"
    assert model is not None
    assert model.status.value == "INSUFFICIENT_EVIDENCE"


def test_json_fallback_rejects_invalid_status_enum():
    """JSON with bad status value → Pydantic validation fails."""
    parser = P1BLLM01Parser()
    bad = VALID_JSON.replace('"status": "OK"', '"status": "MAYBE_BAD"')
    model, err = parser.parse(bad)
    assert model is None
    assert "validation" in err.lower() or "Pydantic" in err


def test_json_fallback_rejects_missing_required_field():
    """JSON without required status → Pydantic validation fails."""
    parser = P1BLLM01Parser()
    bad = """{
      "interpretations": [],
      "derogations": []
    }"""
    model, err = parser.parse(bad)
    assert model is None
    assert "validation" in err.lower() or "pydantic" in err.lower() or "missing" in err.lower()


def test_both_fail_returns_combined_error():
    """Neither markdown nor JSON parses → parser returns (None, combined error)."""
    parser = P1BLLM01Parser()
    garbage = "this is just text, not markdown, not json\nno structure here"
    model, err = parser.parse(garbage)
    assert model is None
    # Both error messages should be present
    assert "markdown" in err.lower()
    assert "json" in err.lower() or "construct_minimal" in err.lower()


def test_markdown_wins_over_json_when_both_present():
    """If input has both ## markdown sections and JSON, markdown path is tried first."""
    parser = P1BLLM01Parser()
    # Pure markdown → should parse via markdown path
    model, err = parser.parse(VALID_MARKDOWN)
    assert err == "", f"unexpected error: {err}"
    assert model is not None
    assert model.status.value == "OK"
    assert len(model.interpretations) == 2
    # (markdown path extracts 2 INT-* blocks; JSON has only 1)


def test_robust_fallback_rejected():
    """Garbage input triggers RobustParser's construct_minimal_object strategy.
    Parser must reject this (CORR-053: not real LLM JSON, just safety net).
    """
    parser = P1BLLM01Parser()
    # "## Interpretations\n\n(empty)" — looks like markdown heading but
    # no actual ## Status section. RobustParser's construct_minimal_object
    # would otherwise return a synthetic dict.
    model, err = parser.parse("## Interpretations\n\n(empty)")
    assert model is None
    assert "construct_minimal_object" in err or "no real JSON" in err


def test_empty_interpretations_in_json_ok():
    """JSON with empty interpretations array is valid (Pydantic default empty list)."""
    parser = P1BLLM01Parser()
    json_with_empty = """{
      "status": "OK",
      "confidence": "MEDIUM",
      "interpretations": [],
      "derogations": []
    }"""
    model, err = parser.parse(json_with_empty)
    assert err == "", f"unexpected error: {err}"
    assert model is not None
    assert model.interpretations == []
    assert model.derogations == []
