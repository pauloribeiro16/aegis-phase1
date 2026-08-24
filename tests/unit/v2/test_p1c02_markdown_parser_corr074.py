"""CORR-074 propagation: P1C-LLM-02-COMPOUND-EVENT markdown parser hardening.

Mirrors the CORR-074 P1B-LLM-01 pattern
(``tests/unit/v2/test_p1b01_markdown_parser_corr074.py``). The
P1C-LLM-02 spec was bumped to ``prompt_spec_version: 1.1.0`` on
2026-08-05, switching the output contract from JSON Schema
(``output_schemas.yaml#P1C-LLM-02``) to markdown+regex. Empirical M3
dry-runs show that P1C-LLM-02 emits clean markdown with
``## Status / ## Positive Events / ## Negative Events / ## Notes``
headings — the parser must tolerate:

  - The empirical shape: ``### EVT-NN`` / ``### NEG-NN`` subsections
    with body fields (``event_id``, ``description``, ``sub_domains``,
    ``regulations_triggered``, ``tension_type``, ``severity``,
    ``layer0_refs``) using the spec-mandated bracketed list syntax
    (``- sub_domains: [D-XX.Y, ...]``).
  - Variability across runs: headings can gain a ``(Phase 1C)`` /
    ``(Calibration)`` qualifier; tension type can be
    ``temporal conflict`` (space) or ``TEMPORAL_CONFLICT`` (underscore);
    severity can be ``Severity`` (capital) or ``severity``.
  - Empty ``## Positive Events`` / ``## Negative Events`` (header only
    — no confirmed events is a valid output per the spec).
  - Optional ``## Notes`` section.

These tests are the regression contract for the parser hardening
introduced as part of the CORR-074 propagation to P1C-LLM-02. They
live alongside the existing parser tests and do NOT require a live
LLM — they feed pre-recorded M3 outputs through the parser and assert
structural correctness.
"""

from __future__ import annotations

import pytest

from aegis_phase1.prompts_v2.markdown_parser import P1CLLM02Parser

# Empirical M3-style output (representative — matches the spec's
# "Output Format (mandatory)" section verbatim, with 1 positive +
# 1 negative event).
M3_EMPIRICAL = """# Compound Event Analysis — TinyTask Lda.

## Status
**OK** — HIGH confidence. Two confirmed compound events surfaced from the event_templates catalog; one apparent-but-not scenario flagged for calibration.

## Positive Events

### EVT-01
- event_id: EVT-01
- description: Personal data breach via actively exploited product vulnerability. Cross-domain: incident response + product security.
- sub_domains: [D-01.1, D-04.3, D-02.3]
- regulations_triggered: [GDPR, CRA, NIS2]
- tension_type: TEMPORAL_CONFLICT
- severity: CRITICAL
- layer0_refs: [SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA pair GDPR↔CRA, SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA pair GDPR↔NIS2]

### EVT-02
- event_id: EVT-02
- description: Major ICT incident in financial entity with downstream payment disruption.
- sub_domains: [D-04.3, D-09.2, D-04.4]
- regulations_triggered: [DORA, NIS2]
- tension_type: FREQUENCY_MISMATCH
- severity: HIGH
- layer0_refs: [SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA pair DORA↔NIS2]

## Negative Events

### NEG-01
- scenario: Routine security patch release under CRA Art. 14 (voluntary security update).
- regulations_checked: [CRA, GDPR]
- why_not_compound: Single regulation trigger (CRA only) — fails criterion #2 of the compound event definition. No GDPR obligation is activated by a vendor-driven security patch.

## Notes
- Both positive events sourced from event_templates.yaml (EVT-TPL-DATA-BREACH-WITH-VULN, EVT-TPL-FINANCIAL-ICT-MAJOR-INCIDENT).
- No resolution_approach included (Phase 2B territory).
"""


def test_empirical_m3_basic() -> None:
    """Empirical M3-shaped output parses to a valid P1CLLM02Output.

    Asserts the structural shape: status=OK, confidence=HIGH,
    2 positive events + 1 negative event, notes captured.

    Bracketed list fields (``sub_domains: [D-01.1, D-04.3]``) are
    stripped of their outer brackets and split on commas.
    """
    parser = P1CLLM02Parser()
    model, err = parser.parse(M3_EMPIRICAL)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "OK"
    assert model.confidence.value == "HIGH"
    assert len(model.positive_events) == 2
    assert len(model.negative_events) == 1
    # EVT-01 — bracketed list fields split cleanly (no leading `[`).
    e1 = model.positive_events[0]
    assert e1.event_id == "EVT-01"
    assert e1.sub_domains == ["D-01.1", "D-04.3", "D-02.3"]
    assert e1.regulations_triggered == ["GDPR", "CRA", "NIS2"]
    assert e1.tension_type.value == "TEMPORAL_CONFLICT"
    assert e1.severity.value == "CRITICAL"
    # EVT-02 — different tension type + severity.
    e2 = model.positive_events[1]
    assert e2.event_id == "EVT-02"
    assert e2.tension_type.value == "FREQUENCY_MISMATCH"
    assert e2.severity.value == "HIGH"
    # NEG-01 — calibration entry.
    n1 = model.negative_events[0]
    assert n1.regulations_checked == ["CRA", "GDPR"]
    assert "Single regulation trigger" in n1.why_not_compound
    # Notes captured as free-form prose.
    assert "event_templates.yaml" in model.notes


def test_heading_qualifier_phase1c() -> None:
    """M3 sometimes emits ``## Positive Events (Phase 1C)`` qualifier.

    The tolerant SECTION_PATTERNS regex
    (``^##\\s+Positive\\s+Events\\b.*$``) must accept the qualifier
    without breaking the parse — mirrors the P1B-01 `(Tipo 2)` test.
    """
    raw = """# Compound Event Analysis

## Status
**OK** — HIGH confidence. One confirmed event.

## Positive Events (Phase 1C)

### EVT-01
- event_id: EVT-01
- description: Cross-domain test
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, CRA]
- tension_type: TEMPORAL_CONFLICT
- severity: HIGH
- layer0_refs: [SubDomains/D-01.1.md]

## Negative Events (Calibration)

### NEG-01
- scenario: Test
- regulations_checked: [GDPR, NIS2]
- why_not_compound: Test.

## Notes
- Qualifier tolerated.
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "OK"
    assert len(model.positive_events) == 1
    assert len(model.negative_events) == 1
    assert model.positive_events[0].event_id == "EVT-01"


def test_tension_type_variant_space_normalised() -> None:
    """``tension_type: temporal conflict`` (space) → ``TEMPORAL_CONFLICT``.

    The CORR-074 propagation normaliser maps spaced / dashed /
    underscored variants of all 5 tension types onto the canonical
    enum tokens.
    """
    raw = """## Status
**OK** — MEDIUM confidence. Test.

## Positive Events

### EVT-01
- event_id: EVT-01
- description: Test
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, NIS2]
- tension_type: temporal conflict
- severity: HIGH
- layer0_refs: [SubDomains/D-01.1.md]
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.positive_events) == 1
    assert model.positive_events[0].tension_type.value == "TEMPORAL_CONFLICT"


def test_severity_variant_capitalised_normalised() -> None:
    """``Severity: HIGH`` (capital S, value is canonical) → ``HIGH``.

    Empirical M3 sometimes titlecases the field name (``Severity``).
    The case-insensitive field extractor accepts both ``severity``
    and ``Severity``; the value is already canonical.
    """
    raw = """## Status
**OK** — MEDIUM confidence. Test.

## Positive Events

### EVT-01
- event_id: EVT-01
- description: Test
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, NIS2]
- tension_type: TEMPORAL_CONFLICT
- Severity: HIGH
- layer0_refs: [SubDomains/D-01.1.md]
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.positive_events) == 1
    assert model.positive_events[0].severity.value == "HIGH"


def test_empty_positive_events_section_succeeds() -> None:
    """``## Positive Events`` header only — parser returns empty list.

    Per the spec: "If no compound events apply to this company,
    return empty positive_events[]." Empty section is a valid
    output — parser must succeed, not fail.
    """
    raw = """## Status
**OK** — HIGH confidence. No compound events apply to this company.

## Positive Events

(empty — no compound events apply)

## Negative Events

### NEG-01
- scenario: Considered data breach
- regulations_checked: [GDPR, NIS2]
- why_not_compound: NIS2 not applicable (company is too small).

## Notes
- Empty positive_events is valid per spec.
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "OK"
    assert model.positive_events == []
    assert len(model.negative_events) == 1
    assert model.negative_events[0].scenario.startswith("Considered")


def test_optional_notes_section() -> None:
    """If ``## Notes`` is missing, the parser still succeeds.

    `notes=""` is the canonical empty default per the spec.
    """
    raw = """## Status
**OK** — MEDIUM confidence. One confirmed event.

## Positive Events

### EVT-01
- event_id: EVT-01
- description: Test
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, CRA]
- tension_type: TEMPORAL_CONFLICT
- severity: CRITICAL
- layer0_refs: []

## Negative Events

(empty)
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.notes == ""
    assert len(model.positive_events) == 1
    assert model.positive_events[0].severity.value == "CRITICAL"


def test_event_with_single_sub_domain_rejected() -> None:
    """Event with only 1 sub-domain fails ``min_length=2`` → parser returns None.

    The spec mandates ``sub_domains: [D-XX.Y, ...] minItems 2``
    (cross-domain requirement). Pydantic validation surfaces the
    mismatch; the parser propagates ``None`` with an error message.
    """
    raw = """## Status
**OK** — HIGH confidence. Test.

## Positive Events

### EVT-01
- event_id: EVT-01
- description: Within-lane event (invalid — single sub-domain)
- sub_domains: [D-01.1]
- regulations_triggered: [GDPR, CRA]
- tension_type: TEMPORAL_CONFLICT
- severity: LOW
- layer0_refs: [SubDomains/D-01.1.md]

## Negative Events

(empty)
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is None, f"parser should reject single sub-domain, got {model!r}"
    assert err  # non-empty error feedback for the invoker's retry path


@pytest.mark.parametrize(
    "tension_input,expected",
    [
        ("TEMPORAL_CONFLICT", "TEMPORAL_CONFLICT"),
        ("temporal_conflict", "TEMPORAL_CONFLICT"),
        ("temporal conflict", "TEMPORAL_CONFLICT"),
        ("temporal-conflict", "TEMPORAL_CONFLICT"),
        ("REQUIREMENT_CONFLICT", "REQUIREMENT_CONFLICT"),
        ("requirement conflict", "REQUIREMENT_CONFLICT"),
        ("FREQUENCY_MISMATCH", "FREQUENCY_MISMATCH"),
        ("frequency mismatch", "FREQUENCY_MISMATCH"),
        ("TRIGGER_MISMATCH", "TRIGGER_MISMATCH"),
        ("trigger-mismatch", "TRIGGER_MISMATCH"),
        ("INTENSITY_GAP", "INTENSITY_GAP"),
        ("intensity_gap", "INTENSITY_GAP"),
    ],
)
def test_normalise_tension_table(tension_input: str, expected: str) -> None:
    """The tension-type normaliser maps LLM variants to the strict enum."""
    actual = P1CLLM02Parser._normalise_tension(tension_input)
    assert actual == expected


@pytest.mark.parametrize(
    "severity_input,expected",
    [
        ("LOW", "LOW"),
        ("low", "LOW"),
        ("MEDIUM", "MEDIUM"),
        ("medium", "MEDIUM"),
        ("med", "MEDIUM"),
        ("HIGH", "HIGH"),
        ("high", "HIGH"),
        ("CRITICAL", "CRITICAL"),
        ("critical", "CRITICAL"),
        ("crit", "CRITICAL"),
    ],
)
def test_normalise_severity_table(severity_input: str, expected: str) -> None:
    """The severity normaliser maps LLM variants to the strict enum."""
    actual = P1CLLM02Parser._normalise_severity(severity_input)
    assert actual == expected


def test_insufficient_evidence_status() -> None:
    """Status prose ``INSUFFICIENT_EVIDENCE — LOW confidence.`` parses."""
    raw = """## Status
**INSUFFICIENT_EVIDENCE** — LOW confidence. Missing company facts on EU personal data processing.

## Positive Events

(empty)

## Negative Events

(empty)

## Notes
- Cannot determine without company_facts.processes_eu_personal_data.
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "INSUFFICIENT_EVIDENCE"
    assert model.confidence.value == "LOW"
    assert model.positive_events == []
    assert model.negative_events == []
    assert "company_facts" in model.notes


def test_all_five_tension_types_parse() -> None:
    """All 5 canonical tension types parse without error.

    Defensive — ensures the parser's enum membership check accepts
    every value in the strict taxonomy (no typos in the normaliser).
    """
    raw = """## Status
**OK** — HIGH confidence. All 5 tension types tested.

## Positive Events

### EVT-01
- event_id: EVT-01
- description: temporal
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, NIS2]
- tension_type: TEMPORAL_CONFLICT
- severity: HIGH
- layer0_refs: []

### EVT-02
- event_id: EVT-02
- description: requirement
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, NIS2]
- tension_type: REQUIREMENT_CONFLICT
- severity: MEDIUM
- layer0_refs: []

### EVT-03
- event_id: EVT-03
- description: frequency
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, NIS2]
- tension_type: FREQUENCY_MISMATCH
- severity: LOW
- layer0_refs: []

### EVT-04
- event_id: EVT-04
- description: trigger
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, NIS2]
- tension_type: TRIGGER_MISMATCH
- severity: CRITICAL
- layer0_refs: []

### EVT-05
- event_id: EVT-05
- description: intensity
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, NIS2]
- tension_type: INTENSITY_GAP
- severity: MEDIUM
- layer0_refs: []

## Negative Events

(empty)
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.positive_events) == 5
    expected_types = {
        "TEMPORAL_CONFLICT",
        "REQUIREMENT_CONFLICT",
        "FREQUENCY_MISMATCH",
        "TRIGGER_MISMATCH",
        "INTENSITY_GAP",
    }
    actual_types = {e.tension_type.value for e in model.positive_events}
    assert actual_types == expected_types


def test_registry_p1c02_uses_new_parser() -> None:
    """The MARKDOWN_PARSERS registry wires P1C-LLM-02 to P1CLLM02Parser.

    Sanity check that the CORR-074 propagation registry update landed.
    """
    from aegis_phase1.prompts_v2.markdown_parser import MARKDOWN_PARSERS

    assert (
        MARKDOWN_PARSERS["P1C-LLM-02-COMPOUND-EVENT"] is P1CLLM02Parser
    )


def test_severity_variant_critical_lowercase_normalised() -> None:
    """``Severity: critical`` (lowercase value) → ``CRITICAL``.

    Empirical M3 sometimes emits ``Severity: critical`` (lowercase).
    The severity normaliser maps lowercase tokens to the strict enum
    (CRITICAL is a valid token per the spec taxonomy).
    """
    raw = """## Status
**OK** — MEDIUM confidence. Test.

## Positive Events

### EVT-01
- event_id: EVT-01
- description: Test
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, NIS2]
- tension_type: TEMPORAL_CONFLICT
- Severity: critical
- layer0_refs: [SubDomains/D-01.1.md]
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.positive_events) == 1
    assert model.positive_events[0].severity.value == "CRITICAL"


def test_event_with_single_regulation_triggered_rejected() -> None:
    """Event with only 1 ``regulations_triggered`` fails ``min_length=2``.

    The spec mandates ``regulations_triggered: [REG, ...] minItems 2``
    (cross-regulation requirement). Pydantic validation surfaces the
    mismatch; the parser returns ``None``.
    """
    raw = """## Status
**OK** — HIGH confidence. Test.

## Positive Events

### EVT-01
- event_id: EVT-01
- description: Single-regulation event (invalid — cross-reg requirement)
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR]
- tension_type: TEMPORAL_CONFLICT
- severity: HIGH
- layer0_refs: [SubDomains/D-01.1.md]

## Negative Events

(empty)
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is None, f"parser should reject single regulation_triggered, got {model!r}"
    assert err  # non-empty error feedback


def test_negative_event_with_empty_regulations_checked_accepted() -> None:
    """Negative event with empty ``regulations_checked`` is accepted.

    Per the spec: ``regulations_checked`` is a "checked" list (no
    cross-reg requirement) — it can be empty. The Pydantic model has
    no ``min_length`` constraint for it.
    """
    raw = """## Status
**OK** — HIGH confidence. Test.

## Positive Events

### EVT-01
- event_id: EVT-01
- description: Test
- sub_domains: [D-01.1, D-04.3]
- regulations_triggered: [GDPR, NIS2]
- tension_type: TEMPORAL_CONFLICT
- severity: HIGH
- layer0_refs: [SubDomains/D-01.1.md]

## Negative Events

### NEG-01
- scenario: Apparent cross-reg event (single factual event)
- regulations_checked: []
- why_not_compound: Single factual event criterion #1 satisfied,
  but no second regulation trigger exists — within-lane, not compound.
"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.negative_events) == 1
    assert model.negative_events[0].regulations_checked == []


def test_json_envelope_rejected() -> None:
    """LLM output wrapped in ```json``` fence is rejected by the parser.

    The spec explicitly forbids wrapping output in a code fence
    (``Do NOT: Wrap output in ```json``` or any code fence``). The
    parser strips fences defensively, but if the stripped content is
    still JSON rather than markdown, the parse fails (no ``## Status``
    heading → ``_extract_section`` returns None).
    """
    raw = """```json
{
  "prompt_spec_id": "P1C-LLM-02-COMPOUND-EVENT",
  "schema_version": "1.0.0",
  "case_id": "case1-tinytask",
  "invocation_pattern": "global_reduce",
  "status": "OK",
  "confidence": "HIGH",
  "positive_events": [],
  "negative_events": [],
  "notes": "Wrapped in JSON fence."
}
```"""
    parser = P1CLLM02Parser()
    model, err = parser.parse(raw)

    assert model is None, (
        f"parser should reject JSON envelope (spec forbids it), got {model!r}"
    )
    assert err
