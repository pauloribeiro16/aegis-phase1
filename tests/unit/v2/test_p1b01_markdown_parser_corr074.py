"""CORR-074: P1B-LLM-01 markdown parser hardening.

Empirical M3 dry-runs showed that when the P1B-LLM-01 spec asks for
markdown, M3 emits clean markdown with ``## Status / ## Interpretations /
## Derogations / ## Notes`` headings. The parser must tolerate:

  - The empirical Test 1 shape: ``## Status`` with ``**OK** — HIGH
    confidence. <justification>`` and ``### ENTRY_ID — **YES**`` /
    ``### ENTRY_ID — **NOT_ACTIVATED**`` subsections with ``**`` bold
    markers around verdict tokens.
  - Variability across runs: headings can gain a ``(Tipo 2)`` /
    ``(Tipo 3)`` qualifier; verdicts can be ``APPLIES (YES)`` or
    ``NOT ACTIVATED`` (with space) instead of the strict enum tokens.
  - Optional ``## Notes`` section.

These tests are the regression contract for the parser hardening
introduced in CORR-074. They live alongside the existing parser tests
and do NOT require a live LLM — they feed pre-recorded M3 outputs
through the parser and assert structural correctness.
"""

from __future__ import annotations

import pytest

from aegis_phase1.prompts_v2.markdown_parser import P1BLLM01Parser

# Empirical M3 Test 1 output (verbatim, copied from the dry-run).
M3_TEST_1 = """# Interpretation Note — TinyTask Lda.

## Status
**OK** — HIGH confidence. Company facts clearly establish CRA applicability as a manufacturer placing a Class I digital product on the EU market.

## Interpretations

### TIPO2-CRA-ART14-DUAL-FLOW — **YES**
TinyTask Lda. is identified as a **manufacturer** (predicate satisfied)...

### TIPO2-CRA-ART15-VOLUNTARY — **YES**
Predicate satisfied (products present)...

## Derogations

### TIPO3-CRA-NON-PLACED — **NOT_ACTIVATED**
Predicate fails...

### TIPO3-CRA-OPEN-SOURCE — **NOT_ACTIVATED**
Predicate fails on multiple grounds...

## Notes
- The two in-scope subdomains...
"""


def test_empirical_m3_test1_basic() -> None:
    """Empirical M3 Test 1 output parses to a valid P1BLLM01Output.

    Asserts the structural shape: status=OK, confidence=HIGH,
    2 interpretations + 2 derogations, notes captured.

    CORR-074 (post-fix 2026-08-05): canonical verdict taxonomy is
    ``YES / NO / INDETERMINATE``. The parser normalises ``APPLIES`` /
    ``APPLIES (YES)`` (and the bold-wrapped variants) to ``YES``.
    """
    parser = P1BLLM01Parser()
    model, err = parser.parse(M3_TEST_1)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "OK"
    assert model.confidence.value == "HIGH"
    assert len(model.interpretations) == 2
    assert len(model.derogations) == 2
    assert model.interpretations[0].entry_id == "TIPO2-CRA-ART14-DUAL-FLOW"
    assert model.interpretations[1].entry_id == "TIPO2-CRA-ART15-VOLUNTARY"
    # Bold-wrapped YES → normalised to canonical YES.
    assert model.interpretations[0].applicable.value == "YES"
    assert model.interpretations[1].applicable.value == "YES"
    assert model.derogations[0].entry_id == "TIPO3-CRA-NON-PLACED"
    assert model.derogations[0].activation_verdict.value == "NOT_ACTIVATED"
    assert model.derogations[1].entry_id == "TIPO3-CRA-OPEN-SOURCE"
    assert model.derogations[1].activation_verdict.value == "NOT_ACTIVATED"
    # Notes captured as free-form prose (CORR-074).
    assert "two in-scope subdomains" in model.notes


def test_empirical_m3_test2_with_qualifiers() -> None:
    """M3 sometimes emits ``## Interpretations (Tipo 2)`` qualifier.

    The tolerant SECTION_PATTERNS regex (``^##\\s+Interpretations\\b.*$``)
    must accept the qualifier without breaking the parse.
    """
    raw = """# Interpretation Note — TinyTask Lda.

## Status
**OK** — HIGH confidence. Company facts clearly establish CRA applicability.

## Interpretations (Tipo 2)

### TIPO2-CRA-ART14-DUAL-FLOW — **YES**
Predicate satisfied...

### TIPO2-CRA-ART15-VOLUNTARY — **YES**
Predicate satisfied...

## Derogations (Tipo 3)

### TIPO3-CRA-NON-PLACED — **NOT_ACTIVATED**
Predicate fails...

### TIPO3-CRA-OPEN-SOURCE — **NOT_ACTIVATED**
Predicate fails on multiple grounds...

## Notes
- Operational concerns.
"""
    parser = P1BLLM01Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "OK"
    assert model.confidence.value == "HIGH"
    assert len(model.interpretations) == 2
    assert len(model.derogations) == 2
    assert model.interpretations[0].applicable.value == "YES"
    assert model.derogations[0].activation_verdict.value == "NOT_ACTIVATED"


def test_verdict_variant_applies_yes_normalises_to_yes() -> None:
    """M3 emits ``APPLIES (YES)`` or ``DOES_NOT_APPLY`` in headings.

    CORR-074 (post-fix 2026-08-05): the parser normalises both legacy
    tokens to the canonical ``YES / NO / INDETERMINATE`` taxonomy.
    ``APPLIES (YES)`` → ``YES``; ``DOES_NOT_APPLY`` → ``NO``.
    """
    raw = """## Status
**OK** — HIGH confidence. Test.

## Interpretations

### TIPO2-CRA-ART14-DUAL-FLOW — **APPLIES (YES)**
Predicate satisfied...

### TIPO2-CRA-ART15-VOLUNTARY — **DOES_NOT_APPLY**
Predicate fails...

## Derogations

### TIPO3-CRA-NON-PLACED — NOT_ACTIVATED
Predicate fails...

"""
    parser = P1BLLM01Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.interpretations) == 2
    assert model.interpretations[0].entry_id == "TIPO2-CRA-ART14-DUAL-FLOW"
    # APPLIES (YES) → YES
    assert model.interpretations[0].applicable.value == "YES"
    # DOES_NOT_APPLY → NO
    assert model.interpretations[1].applicable.value == "NO"


def test_notes_section_is_optional() -> None:
    """If ``## Notes`` is missing, the parser still succeeds and notes=""."""
    raw = """## Status
**OK** — HIGH confidence. OK.

## Interpretations

### TIPO2-CRA-ART14-DUAL-FLOW — **YES**
Predicate satisfied...

## Derogations

### TIPO3-CRA-NON-PLACED — NOT_ACTIVATED
Predicate fails...

"""
    parser = P1BLLM01Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.notes == ""
    assert len(model.interpretations) == 1
    assert len(model.derogations) == 1


def test_legacy_int_der_subsection_shape_still_works() -> None:
    """The CORR-050 ``### INT-NN`` / ``### DER-NN`` shape still parses.

    Backward compat: renderers and tests still emit the legacy shape.
    """
    raw = """## Status
OK — HIGH confidence. Test.

## Interpretations

### INT-01
- entry_id: TIPO2-CRA-ART14-DUAL-FLOW
- applicable: YES
- activation_rationale: Predicate satisfied.
- layer0_refs: SubDomains/D-01.1.md

### INT-02
- entry_id: TIPO2-CRA-ART15-VOLUNTARY
- applicable: NO
- activation_rationale: Predicate fails.

## Derogations

### DER-01
- entry_id: TIPO3-CRA-NON-PLACED
- activation_verdict: NOT_ACTIVATED
- activation_rationale: Predicate fails.

## Notes
- Legacy shape still works.
"""
    parser = P1BLLM01Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "OK"
    assert len(model.interpretations) == 2
    assert len(model.derogations) == 1
    assert model.interpretations[0].entry_id == "TIPO2-CRA-ART14-DUAL-FLOW"
    assert model.interpretations[0].applicable.value == "YES"
    assert model.interpretations[1].applicable.value == "NO"
    assert "Legacy shape still works." in model.notes


def test_not_activated_with_space_normalised() -> None:
    """The empirical ``NOT ACTIVATED`` (space) variant → ``NOT_ACTIVATED``."""
    raw = """## Status
**OK** — HIGH confidence. OK.

## Interpretations

### TIPO2-CRA-ART14-DUAL-FLOW — **YES**
Predicate satisfied...

## Derogations

### TIPO3-CRA-NON-PLACED — NOT ACTIVATED
Predicate fails...

"""
    parser = P1BLLM01Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.derogations) == 1
    assert model.derogations[0].activation_verdict.value == "NOT_ACTIVATED"


@pytest.mark.parametrize(
    "verdict_token,expected",
    [
        ("YES", "YES"),
        ("APPLIES", "YES"),
        ("APPLIES (YES)", "YES"),
        ("NO", "NO"),
        ("DOES_NOT_APPLY", "NO"),
        ("INDETERMINATE", "INDETERMINATE"),
    ],
)
def test_normalise_verdict_interp_table(verdict_token: str, expected: str) -> None:
    """The verdict normaliser maps LLM variants to the canonical enum token.

    CORR-074 (post-fix 2026-08-05): canonical interpretation taxonomy is
    ``YES / NO / INDETERMINATE``. Legacy ``APPLIES`` / ``DOES_NOT_APPLY``
    (and the ``APPLIES (YES)`` / ``DOES_NOT_APPLY (NO)`` annotated
    variants) collapse onto ``YES`` / ``NO``.
    """
    actual = P1BLLM01Parser._normalise_verdict(verdict_token, "interp")
    assert actual == expected


@pytest.mark.parametrize(
    "verdict_token,expected",
    [
        ("ACTIVATED", "ACTIVATED"),
        ("NOT_ACTIVATED", "NOT_ACTIVATED"),
        ("NOT ACTIVATED", "NOT_ACTIVATED"),
        ("INDETERMINATE", "INDETERMINATE"),
    ],
)
def test_normalise_verdict_derog_table(verdict_token: str, expected: str) -> None:
    """The derog normaliser maps LLM variants to strict enum tokens."""
    actual = P1BLLM01Parser._normalise_verdict(verdict_token, "derog")
    assert actual == expected
