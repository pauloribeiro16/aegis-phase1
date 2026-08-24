"""CORR-074 propagation: P1B-LLM-02-RATIONALE markdown parser hardening.

The v1.1.0 spec (P1B-LLM-02-RATIONALE.md) asks the LLM to emit a
5-section markdown document (Status / Rationale / Implications /
Gaps / Notes). This test file pins the parser's contract — the same
way ``test_p1b01_markdown_parser_corr074.py`` does for the upstream
P1B-LLM-01 spec.

The tests cover the shapes the parser must accept:

  - Empirical M3-style output (prose Status, free-form Rationale,
    one ``### IMP-D-XX.Y-N`` per implication, one ``### GAP-D-XX.Y``
    per gap, optional Notes).
  - Empty sections (Rationale only, no Implications, no Gaps).
  - Optional Notes missing.
  - Verdict normalisers: effort estimate aliases
    (``hours to days`` / ``weeks (1-2)`` / ``1-3 months``),
    priority variant (``1`` → ``P1``), coverage variant
    (``NOT ADDRESSED`` → ``NOT_ADDRESSED``).
  - Heading qualifiers (``## Rationale (P1B-02)`` — parser must
    still recognise the section).

No live LLM is required — the tests feed pre-recorded markdown
through the parser and assert structural correctness.
"""

from __future__ import annotations

import pytest

from aegis_phase1.prompts_v2.markdown_parser import P1BLLM02Parser
from aegis_phase1.v2.state import (
    P1BLLM01Confidence,
    P1BLLM01Status,
    P1BLLM02CoverageLevel,
    P1BLLM02EffortEstimate,
    P1BLLM02Priority,
)

# Empirical M3-style output (representative shape — what M3 will
# naturally produce given the v1.1.0 Output Format spec).
M3_STYLE_FULL = """# Synthesis — CRA — TinyTask Lda.

## Status
**OK** — HIGH confidence. CRA applicability is unambiguous; predicate satisfaction is clear from company facts.

## Rationale
TinyTask Lda. is a **manufacturer** placing a digital product (the SaaS application) on the EU market (Doc 04 §5, architecture_ref=DOC04:ARCH-07). Under CRA Art. 13(1) and Annex III, the product falls in scope as a Class I device with digital elements. The P1B-LLM-01 output confirms activation of Tipo 2 entries TIPO2-CRA-ART14-DUAL-FLOW and TIPO2-CRA-ART15-VOLUNTARY. No derogations apply (Tipo 3 entries NOT_ACTIVATED).

## Implications

### IMP-D-02.3-1
- description: Establish a coordinated vulnerability disclosure process per CRA Art. 12, including a public contact point and timelines.
- effort_estimate: weeks_2_4
- dependencies: []
- layer0_refs: SubDomains/D-02.3.md
- company_fact_refs: DOC04:ARCH-07

### IMP-D-07.1-1
- description: Document secure-by-design principles in the engineering playbook; align with CRA Art. 13(2).
- effort_estimate: weeks_1
- dependencies: []
- layer0_refs: SubDomains/D-07.1.md
- company_fact_refs: DOC04:ARCH-02

## Gaps

### GAP-D-07.1
- gap_id: GAP-D-07.1
- sub_domain_id: D-07.1
- coverage_level: NOT_ADDRESSED
- risk_description: Engineering playbook does not yet document secure-by-design principles aligned to CRA.
- covered_by_other_reg: []
- recommendation: Document and accept (LOW tier).
- priority: P2
- layer0_refs: SubDomains/D-07.1.md

## Notes
- Two implications + one gap reflect the lane-filtered P1B-01 output (CORR-071).
"""


def test_empirical_m3_full_round_trip() -> None:
    """The empirical M3-style output (5 sections + 2 implications + 1 gap)
    parses to a valid P1BLLM02Output."""
    parser = P1BLLM02Parser()
    model, err = parser.parse(M3_STYLE_FULL)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status == P1BLLM01Status.OK
    assert model.confidence == P1BLLM01Confidence.HIGH
    assert "CRA Art. 13(1)" in model.rationale

    assert len(model.implications) == 2
    assert model.implications[0].id == "IMP-D-02.3-1"
    assert model.implications[0].effort_estimate == P1BLLM02EffortEstimate.WEEKS_2_4
    assert "coordinated vulnerability disclosure" in model.implications[0].description
    assert model.implications[1].id == "IMP-D-07.1-1"
    assert model.implications[1].effort_estimate == P1BLLM02EffortEstimate.WEEKS_1

    assert len(model.gaps) == 1
    assert model.gaps[0].gap_id == "GAP-D-07.1"
    assert model.gaps[0].sub_domain_id == "D-07.1"
    assert model.gaps[0].coverage_level == P1BLLM02CoverageLevel.NOT_ADDRESSED
    assert model.gaps[0].priority == P1BLLM02Priority.P2

    assert "lane-filtered P1B-01 output" in model.notes


def test_minimal_status_only() -> None:
    """Only the `## Status` section is strictly required.

    Rationale is missing → empty string. Implications / Gaps / Notes
    are missing → empty lists / empty string. The parser still succeeds.
    """
    raw = """## Status
**OK** — MEDIUM confidence. Minimal case.
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status == P1BLLM01Status.OK
    assert model.confidence == P1BLLM01Confidence.MEDIUM
    assert model.rationale == ""
    assert model.implications == []
    assert model.gaps == []
    assert model.notes == ""


def test_rationale_present_no_implications_no_gaps() -> None:
    """Rationale is captured verbatim; sections without subsections
    (Implications / Gaps) yield empty lists."""
    raw = """## Status
**OK** — HIGH confidence. OK.

## Rationale
TinyTask is a manufacturer under CRA. Predicate satisfied.

## Implications
(no implications)

## Gaps
(no gaps)
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert "TinyTask is a manufacturer under CRA" in model.rationale
    assert model.implications == []
    assert model.gaps == []


def test_notes_section_is_optional() -> None:
    """If `## Notes` is missing, the parser still succeeds with notes=''."""
    raw = """## Status
**OK** — HIGH confidence. Test.

## Rationale
Test rationale.

## Implications

### IMP-D-02.3-1
- description: x
- effort_estimate: hours
- dependencies: []
- layer0_refs: []
- company_fact_refs: []

"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.notes == ""
    assert len(model.implications) == 1


def test_effort_estimate_hours_to_days_normalised() -> None:
    """`hours to days` aliases → canonical `days`."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Implications

### IMP-D-02.3-1
- description: x
- effort_estimate: hours to days
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.implications[0].effort_estimate == P1BLLM02EffortEstimate.DAYS


def test_effort_estimate_weeks_1_2_normalised() -> None:
    """`weeks (1-2)` aliases → canonical `weeks_1`."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Implications

### IMP-D-02.3-1
- description: x
- effort_estimate: weeks (1-2)
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.implications[0].effort_estimate == P1BLLM02EffortEstimate.WEEKS_1


def test_effort_estimate_1_3_months_normalised() -> None:
    """`1-3 months` aliases → canonical `months_1_3`."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Implications

### IMP-D-02.3-1
- description: x
- effort_estimate: 1-3 months
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.implications[0].effort_estimate == P1BLLM02EffortEstimate.MONTHS_1_3


def test_priority_numeric_1_normalised_to_p1() -> None:
    """`priority: 1` (numeric) → canonical `P1`."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Gaps

### GAP-D-07.1
- gap_id: GAP-D-07.1
- sub_domain_id: D-07.1
- coverage_level: NOT_ADDRESSED
- risk_description: r
- priority: 1
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.gaps[0].priority == P1BLLM02Priority.P1


def test_coverage_level_not_addressed_with_space() -> None:
    """`NOT ADDRESSED` (with space) → canonical `NOT_ADDRESSED`."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Gaps

### GAP-D-07.1
- gap_id: GAP-D-07.1
- sub_domain_id: D-07.1
- coverage_level: NOT ADDRESSED
- risk_description: r
- priority: P2
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.gaps[0].coverage_level == P1BLLM02CoverageLevel.NOT_ADDRESSED


def test_coverage_level_partial() -> None:
    """Canonical `PARTIAL` accepted."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Gaps

### GAP-D-02.1
- gap_id: GAP-D-02.1
- sub_domain_id: D-02.1
- coverage_level: PARTIAL
- risk_description: r
- priority: P3
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.gaps[0].coverage_level == P1BLLM02CoverageLevel.PARTIAL
    assert model.gaps[0].priority == P1BLLM02Priority.P3


def test_heading_qualifier_rationale_p1b02() -> None:
    """Heading qualifiers like `## Rationale (P1B-02)` are tolerated.

    The tolerant SECTION_PATTERNS regex (``^##\\s+Rationale\\b.*$``)
    accepts any trailing text after the section name.
    """
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale (P1B-02)
Test rationale with qualifier.

## Implications (per regulation)

### IMP-D-02.3-1
- description: x
- effort_estimate: hours
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert "qualifier" in model.rationale
    assert len(model.implications) == 1


def test_gap_sub_domain_id_falls_back_to_heading() -> None:
    """If `sub_domain_id` is missing in the body, the parser falls back
    to the heading token (``### GAP-D-XX.Y`` → ``D-XX.Y``)."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Gaps

### GAP-D-07.1
- gap_id: GAP-D-07.1
- coverage_level: NOT_ADDRESSED
- risk_description: r
- priority: P1
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.gaps[0].sub_domain_id == "D-07.1"


def test_invalid_status_returns_none() -> None:
    """If `## Status` is missing entirely, the parser returns None
    (the model can't be built without a status)."""
    raw = """## Rationale
Missing status.
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is None
    assert "did not match" in err or "Pydantic" in err


def test_invalid_effort_returns_none() -> None:
    """An effort_estimate that's not in the canonical 8-value enum
    (and not in the alias table) fails the parse — Pydantic surfaces
    the mismatch instead of silently accepting."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Implications

### IMP-D-02.3-1
- description: x
- effort_estimate: galaxy_epochs
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is None
    assert err != ""


def test_envelope_invariants() -> None:
    """The envelope defaults are wired correctly; the parser does NOT
    let the LLM inject prompt_spec_id / schema_version / case_id /
    invocation_pattern — those are invoker-injected post-parse."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    # Even though the LLM didn't emit them, the model exposes the
    # defaults — the invoker will overwrite them post-parse.
    assert model.prompt_spec_id == "P1B-LLM-02-RATIONALE"
    assert model.schema_version == "1.0.0"
    assert model.case_id == ""
    assert model.invocation_pattern == "per_regulation"


def test_backticked_field_names_and_bracketed_lists() -> None:
    """Empirical MiniMax-M3 wraps field names in backticks
    (``- `id`: value``) and emits list values as JSON-like arrays
    (``["foo.md", "bar.md"]``). The parser must accept both."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Implications

### IMP-D-07.1-1
- `id`: IMP-D-07.1-1
- `description`: Establish secure development lifecycle.
- `effort_estimate`: days
- `dependencies`: []
- `layer0_refs`: ["SubDomains/D-07.1.md §2 HSO"]
- `company_fact_refs`: ["DOC04:ARCH-SYS-01"]
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.implications) == 1
    imp = model.implications[0]
    assert imp.id == "IMP-D-07.1-1"
    assert imp.effort_estimate == P1BLLM02EffortEstimate.DAYS
    assert imp.layer0_refs == ["SubDomains/D-07.1.md §2 HSO"]
    assert imp.company_fact_refs == ["DOC04:ARCH-SYS-01"]
    assert imp.dependencies == []


def test_backticked_field_names_with_dependencies() -> None:
    """Dependencies list (often with IMP-IDs) parses correctly when
    emitted as a JSON-style array."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Implications

### IMP-D-02.3-1
- `id`: IMP-D-02.3-1
- `description`: CVD policy.
- `effort_estimate`: hours
- `dependencies`: ["IMP-D-02.3-0", "IMP-D-07.1-1"]
- `layer0_refs`: ["SubDomains/D-02.3.md"]
- `company_fact_refs`: ["DOC04:ARCH-SYS-01"]
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    imp = model.implications[0]
    assert imp.dependencies == ["IMP-D-02.3-0", "IMP-D-07.1-1"]


def test_plain_field_names_comma_separated_lists_still_work() -> None:
    """The spec canonical form is plain field names with comma-separated
    lists — the test fixtures use this shape and must continue to work
    after the backticked/JSON-array variants were added."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Implications

### IMP-D-02.3-1
- id: IMP-D-02.3-1
- description: CVD policy.
- effort_estimate: hours
- dependencies: IMP-D-07.1-1, IMP-D-02.3-0
- layer0_refs: SubDomains/D-02.3.md, SubDomains/D-02.3.annex.md
- company_fact_refs: DOC04:ARCH-SYS-01
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    imp = model.implications[0]
    assert imp.dependencies == ["IMP-D-07.1-1", "IMP-D-02.3-0"]
    assert imp.layer0_refs == [
        "SubDomains/D-02.3.md",
        "SubDomains/D-02.3.annex.md",
    ]


def test_json_envelope_wrapper_rejected() -> None:
    """The spec forbids ```json``` / code-fence wrapping. The parser
    strips code fences then parses the markdown body — so JSON output
    shouldn't parse to a valid ``P1BLLM02Output`` model and the parser
    returns None."""
    raw = '''```json
{
  "status": "OK",
  "confidence": "HIGH",
  "rationale": "fake"
}
```'''
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    # After stripping code fences, the body has no `## ` section
    # headers — parser returns None with the markdown-mismatch error.
    assert model is None
    assert "did not match" in err or "Pydantic" in err


def test_bold_field_names_also_accepted() -> None:
    """Empirical M3 also wraps field names in ``**bold**`` markdown
    emphasis (``- **id**: value``). The parser must accept this too
    in addition to the plain / backtick forms."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Implications

### IMP-D-07.1-1
- **id**: IMP-D-07.1-1
- **description**: Establish secure development lifecycle.
- **effort_estimate**: days
- **dependencies**: []
- **layer0_refs**: ["SubDomains/D-07.1.md"]
- **company_fact_refs**: ["DOC04:ARCH-SYS-01"]
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    imp = model.implications[0]
    assert imp.id == "IMP-D-07.1-1"
    assert imp.effort_estimate == P1BLLM02EffortEstimate.DAYS
    assert imp.layer0_refs == ["SubDomains/D-07.1.md"]


def test_mixed_field_name_decorations_in_one_document() -> None:
    """Within a single M3 run, field-name decorations can vary across
    sections (e.g. plain in the first subsection, backticked in the
    second). The parser must accept a mixed document."""
    raw = """## Status
**OK** — HIGH confidence. x

## Rationale
r

## Implications

### IMP-D-02.3-1
- id: IMP-D-02.3-1
- description: CVD policy.
- effort_estimate: hours
- dependencies: []
- layer0_refs: SubDomains/D-02.3.md
- company_fact_refs: DOC04:ARCH-SYS-01

### IMP-D-07.1-1
- `id`: IMP-D-07.1-1
- `description`: SDLC.
- `effort_estimate`: days
- `dependencies`: []
- `layer0_refs`: ["SubDomains/D-07.1.md"]
- `company_fact_refs`: ["DOC04:ARCH-SYS-01"]

### IMP-D-04.2-1
- **id**: IMP-D-04.2-1
- **description**: Incident response.
- **effort_estimate**: weeks_1
- **dependencies**: []
- **layer0_refs**: ["SubDomains/D-04.2.md"]
- **company_fact_refs**: ["DOC04:ARCH-SYS-01"]
"""
    parser = P1BLLM02Parser()
    model, err = parser.parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.implications) == 3
    assert model.implications[0].id == "IMP-D-02.3-1"
    assert model.implications[0].effort_estimate == P1BLLM02EffortEstimate.HOURS
    assert model.implications[1].id == "IMP-D-07.1-1"
    assert model.implications[1].effort_estimate == P1BLLM02EffortEstimate.DAYS
    assert model.implications[2].id == "IMP-D-04.2-1"
    assert model.implications[2].effort_estimate == P1BLLM02EffortEstimate.WEEKS_1


@pytest.mark.parametrize(
    "effort_token,expected",
    [
        ("hours", "hours"),
        ("hour", "hours"),
        ("hours to days", "days"),
        ("1-2 days", "days"),
        ("1 week", "weeks_1"),
        ("weeks (1-2)", "weeks_1"),
        ("2-4 weeks", "weeks_2_4"),
        ("1-3 months", "months_1_3"),
        ("3-6 months", "months_3_6"),
        ("fte_quarter", "fte_quarter"),
        ("permanent fte", "fte_permanent"),
    ],
)
def test_normalise_effort_table(effort_token: str, expected: str) -> None:
    """The effort-estimate normaliser maps LLM aliases to the 8-value enum."""
    actual = P1BLLM02Parser._normalise_effort(effort_token)
    assert actual == expected


@pytest.mark.parametrize(
    "coverage_token,expected",
    [
        ("NOT_ADDRESSED", "NOT_ADDRESSED"),
        ("not_addressed", "NOT_ADDRESSED"),
        ("NOT ADDRESSED", "NOT_ADDRESSED"),
        ("not addressed", "NOT_ADDRESSED"),
        ("PARTIAL", "PARTIAL"),
        ("partial", "PARTIAL"),
        ("partially_addressed", "PARTIAL"),
    ],
)
def test_normalise_coverage_table(coverage_token: str, expected: str) -> None:
    """The coverage-level normaliser maps LLM variants to the strict enum."""
    actual = P1BLLM02Parser._normalise_coverage(coverage_token)
    assert actual == expected


@pytest.mark.parametrize(
    "priority_token,expected",
    [
        ("P1", "P1"),
        ("p1", "P1"),
        ("1", "P1"),
        ("P2", "P2"),
        ("2", "P2"),
        ("P3", "P3"),
        ("3", "P3"),
    ],
)
def test_normalise_priority_table(priority_token: str, expected: str) -> None:
    """The priority normaliser maps LLM variants to the strict enum."""
    actual = P1BLLM02Parser._normalise_priority(priority_token)
    assert actual == expected
