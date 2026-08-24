"""CORR-074 propagation: P1C-LLM-03-STRATEGIC-SYNTHESIS markdown parser hardening.

Empirical M3 dry-runs (TinyTask Lda. baseline) showed that when the
P1C-LLM-03 spec asks for markdown, M3 emits clean markdown with
``## Status / ## Implications / ## Notes`` headings. The parser must
tolerate:

  - The empirical shape: ``## Status`` with
    ``**OK** — HIGH confidence. <justification>`` and ``### IMP-NN``
    subsections with body fields (``- affected_sub_domains:``,
    ``- regulations:``, ``- risk_level:``, ``- confidence:``).
  - Heading qualifiers like ``## Implications (Phase 1C)``.
  - Risk-level variants: ``Risk Level: Medium`` / ``Risk Level: High`` →
    ``MEDIUM`` / ``HIGH`` (the canonical enum token).
  - Confidence variants: ``Confidence: high`` / ``Confidence: low`` →
    ``HIGH`` / ``LOW``.
  - Empty implications list — the "1-2 acknowledging mostly settled"
    case from the spec.
  - Optional ``## Notes`` section (missing → ``notes=""``).
  - Cross-lane / cross-regulation enforcement: Pydantic
    ``min_length=2`` on ``affected_sub_domains`` and ``regulations``
    surfaces a clear error when M3 violates the constraint.

These tests are the regression contract for the CORR-074 propagation
of P1C-LLM-03 (mirrors ``tests/unit/v2/test_p1b01_markdown_parser_corr074.py``).
They live alongside the existing parser tests and do NOT require a
live LLM — they feed pre-recorded M3 outputs through the parser and
assert structural correctness.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aegis_phase1.prompts_v2.markdown_parser import P1CLLM03Parser
from aegis_phase1.v2.state import (
    P1CLLM03Implication,
    P1CLLM03Output,
    P1CLLM03RiskLevel,
)

# Empirical M3-style output (TinyTask baseline, mocked for testing).
# Mirrors the shape of the M3 raw response captured under
# ``output/case1-tinytask/.../raw/P1C-LLM-03-STRATEGIC-SYNTHESIS/*.md``,
# adapted to the new v1.1.0 spec (### IMP-NN subsections with body fields).
M3_STYLE_2_IMPLICATIONS = """## Status
OK — HIGH confidence. Two cross-lane implications detected.

## Implications

### IMP-01
- description: Cross-lane architecture sharing: D-01.1 + D-01.3 share AWS KMS primitive.
- affected_sub_domains: D-01.1, D-01.3
- regulations: GDPR, CRA
- architectural_impact: Single AWS KMS deployment with HSM-anchored key custody serves both sub-domains.
- business_goal_alignment: Supports BG-01 (EU customer trust) by minimising compliance complexity.
- risk_level: MEDIUM
- assumptions: AWS KMS configuration is consistent across both sub-domains; HSM is regionally available.
- layer0_refs: SubDomains/D-01.1.md, SubDomains/D-01.3.md
- doc07b_refs: SD-D-01.1, SD-D-01.3
- confidence: HIGH

### IMP-02
- description: Cross-regulation consolidation: D-04.x + D-09.4 share incident-workflow primitive.
- affected_sub_domains: D-04.3, D-09.4
- regulations: GDPR, CRA
- architectural_impact: Single incident-detection + escalation pipeline branches to SA and CSIRT.
- business_goal_alignment: Strengthens operational resilience (BG-02) without duplicating infrastructure.
- risk_level: HIGH
- assumptions: Member State CSIRT network accepts electronic notification in the prescribed form.
- layer0_refs: SubDomains/D-04.3.md, SubDomains/D-09.4.md
- doc07b_refs: SD-D-04.3, SD-D-09.4
- confidence: MEDIUM

## Notes
- Both implications grounded in Doc 07b rows. No tier changes; no controls proposed.
"""


M3_STYLE_3_IMPLICATIONS = """## Status
OK — MEDIUM confidence. Three implications across the cross-regulation landscape.

## Implications

### IMP-01
- description: Shared KMS primitive (D-01.1 + D-01.3) discharges GDPR Art. 32 + CRA Annex I (2)(e).
- affected_sub_domains: D-01.1, D-01.3
- regulations: GDPR, CRA
- architectural_impact: Single AWS KMS deployment serves both sub-domains.
- business_goal_alignment: BG-01 (EU customer trust).
- risk_level: MEDIUM
- assumptions: AWS KMS HSM availability.
- layer0_refs: SubDomains/D-01.1.md, SubDomains/D-01.3.md
- doc07b_refs: SD-D-01.1, SD-D-01.3
- confidence: HIGH

### IMP-02
- description: Shared incident-workflow (D-04.3 + D-09.4) discharges GDPR Art. 33 + CRA Art. 14.
- affected_sub_domains: D-04.3, D-09.4
- regulations: GDPR, CRA
- architectural_impact: Unified 24h/72h dual-SLA pipeline.
- business_goal_alignment: BG-02 (resilience).
- risk_level: HIGH
- assumptions: CSIRT network accepts electronic notification.
- layer0_refs: SubDomains/D-04.3.md, SubDomains/D-09.4.md
- doc07b_refs: SD-D-04.3, SD-D-09.4
- confidence: HIGH

### IMP-03
- description: Vulnerability-management consolidation (D-02.1 + D-02.3 + D-02.4) shared pipeline.
- affected_sub_domains: D-02.1, D-02.3, D-02.4
- regulations: CRA, NIS2
- architectural_impact: Single SBOM + CVD + TLPT pipeline.
- business_goal_alignment: BG-01 (EU customer trust).
- risk_level: MEDIUM
- assumptions: CRA SBOM upstream; NIS2 entity-status verified.
- layer0_refs: SubDomains/D-02.1.md, SubDomains/D-02.3.md, SubDomains/D-02.4.md
- doc07b_refs: SD-D-02.1, SD-D-02.3, SD-D-02.4
- confidence: MEDIUM

## Notes
- All implications grounded in Doc 07b; no controls proposed.
"""


M3_STYLE_HEADING_QUALIFIER = """## Status
OK — HIGH confidence. Test.

## Implications (Phase 1C)

### IMP-01
- description: Cross-lane pattern test.
- affected_sub_domains: D-01.1, D-01.3
- regulations: GDPR, CRA
- architectural_impact: x
- business_goal_alignment: y
- risk_level: LOW
- assumptions: z
- layer0_refs: a.md, b.md
- doc07b_refs: c
- confidence: HIGH
"""


M3_STYLE_RISK_VARIANT = """## Status
OK — HIGH confidence. Test risk-level case variants.

## Implications

### IMP-01
- description: Risk-level case variant test.
- affected_sub_domains: D-01.1, D-01.3
- regulations: GDPR, CRA
- architectural_impact: x
- business_goal_alignment: y
- Risk Level: Medium
- assumptions: z
- layer0_refs: a.md, b.md
- doc07b_refs: c
- confidence: HIGH
"""


M3_STYLE_CONFIDENCE_VARIANT = """## Status
OK — HIGH confidence. Test confidence case variants.

## Implications

### IMP-01
- description: Confidence case variant test.
- affected_sub_domains: D-01.1, D-01.3
- regulations: GDPR, CRA
- architectural_impact: x
- business_goal_alignment: y
- risk_level: HIGH
- assumptions: z
- layer0_refs: a.md, b.md
- doc07b_refs: c
- Confidence: high
"""


M3_STYLE_EMPTY_IMPLICATIONS = """## Status
OK — MEDIUM confidence. Cross-lane picture mostly settled.

## Implications

## Notes
- No material implications at this time.
"""


M3_STYLE_NO_NOTES = """## Status
OK — HIGH confidence. Test without Notes section.

## Implications

### IMP-01
- description: Cross-lane test without Notes.
- affected_sub_domains: D-01.1, D-01.3
- regulations: GDPR, CRA
- architectural_impact: x
- business_goal_alignment: y
- risk_level: LOW
- assumptions: z
- layer0_refs: a.md, b.md
- doc07b_refs: c
- confidence: HIGH
"""


M3_STYLE_INSUFFICIENT_EVIDENCE = """## Status
INSUFFICIENT_EVIDENCE — LOW confidence. Doc 07b profile empty; cannot derive implications.

## Implications
"""


def test_empirical_m3_style_2_implications() -> None:
    """Empirical M3-style output with 2 implications parses correctly.

    CORR-074 propagation (2026-08-05): the v1.1.0 spec uses
    ``### IMP-NN`` subsections with body fields. The parser extracts
    the id from the heading and the structured fields from the body.
    """
    parser = P1CLLM03Parser()
    model, err = parser.parse(M3_STYLE_2_IMPLICATIONS)

    assert model is not None, f"parser returned None: {err!r}"
    assert isinstance(model, P1CLLM03Output)
    assert model.status.value == "OK"
    assert model.confidence.value == "HIGH"
    assert len(model.implications) == 2

    # First implication: cross-lane KMS sharing.
    imp1 = model.implications[0]
    assert imp1.id == "IMP-01"
    assert imp1.risk_level == P1CLLM03RiskLevel.MEDIUM
    assert imp1.confidence.value == "HIGH"
    assert imp1.affected_sub_domains == ["D-01.1", "D-01.3"]
    assert imp1.regulations == ["GDPR", "CRA"]
    assert "AWS KMS" in imp1.description
    assert imp1.layer0_refs == ["SubDomains/D-01.1.md", "SubDomains/D-01.3.md"]
    assert imp1.doc07b_refs == ["SD-D-01.1", "SD-D-01.3"]
    assert len(imp1.assumptions) >= 1

    # Second implication: cross-regulation incident-workflow.
    imp2 = model.implications[1]
    assert imp2.id == "IMP-02"
    assert imp2.risk_level == P1CLLM03RiskLevel.HIGH
    assert imp2.confidence.value == "MEDIUM"
    assert imp2.affected_sub_domains == ["D-04.3", "D-09.4"]

    # Notes captured.
    assert "Doc 07b" in model.notes


def test_empirical_m3_style_3_implications() -> None:
    """3-implication output: parser handles larger batches correctly.

    The Pydantic model allows up to 8 implications per spec. The
    parser splits by ``### IMP-NN`` and produces one model per
    subsection.
    """
    parser = P1CLLM03Parser()
    model, err = parser.parse(M3_STYLE_3_IMPLICATIONS)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "OK"
    assert len(model.implications) == 3
    assert model.implications[0].id == "IMP-01"
    assert model.implications[1].id == "IMP-02"
    assert model.implications[2].id == "IMP-03"
    # IMP-03 spans 3 sub-domains (cross-lane).
    assert model.implications[2].affected_sub_domains == ["D-02.1", "D-02.3", "D-02.4"]
    assert model.implications[2].regulations == ["CRA", "NIS2"]


def test_heading_qualifier_phase_1c() -> None:
    """M3 sometimes emits ``## Implications (Phase 1C)`` qualifier.

    The tolerant ``SECTION_PATTERNS`` regex
    (``^##\\s+Implications\\b.*$``) must accept the qualifier without
    breaking the parse — same pattern as P1B-01's ``(Tipo 2)``.
    """
    parser = P1CLLM03Parser()
    model, err = parser.parse(M3_STYLE_HEADING_QUALIFIER)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.implications) == 1
    assert model.implications[0].id == "IMP-01"


def test_risk_level_variant_medium_normalises() -> None:
    """M3 emits ``Risk Level: Medium`` — the parser normalises to ``MEDIUM``.

    CORR-074 propagation: canonical ``risk_level`` taxonomy is
    ``LOW / MEDIUM / HIGH``. The parser's ``_normalise_risk`` accepts
    both ``- risk_level: medium`` and ``- Risk Level: Medium`` (the
    colon-prefixed form with capitalisation).
    """
    parser = P1CLLM03Parser()
    model, err = parser.parse(M3_STYLE_RISK_VARIANT)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.implications) == 1
    assert model.implications[0].risk_level == P1CLLM03RiskLevel.MEDIUM


def test_confidence_variant_high_normalises() -> None:
    """M3 emits ``Confidence: high`` — the parser normalises to ``HIGH``."""
    parser = P1CLLM03Parser()
    model, err = parser.parse(M3_STYLE_CONFIDENCE_VARIANT)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.implications) == 1
    assert model.implications[0].confidence.value == "HIGH"


def test_empty_implications_list_parses() -> None:
    """The "1-2 acknowledging mostly settled" case: empty list is valid.

    The spec allows 1-2 implications; if M3 produces none (rare,
    degenerate case), the parser still succeeds with
    ``implications=[]``. The Pydantic default is ``default_factory=list``.
    """
    parser = P1CLLM03Parser()
    model, err = parser.parse(M3_STYLE_EMPTY_IMPLICATIONS)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "OK"
    assert len(model.implications) == 0
    # Notes captured even when implications are empty.
    assert "No material implications" in model.notes


def test_notes_section_optional() -> None:
    """Missing ``## Notes`` → ``notes=""`` (no error)."""
    parser = P1CLLM03Parser()
    model, err = parser.parse(M3_STYLE_NO_NOTES)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.notes == ""
    assert len(model.implications) == 1


def test_insufficient_evidence_status() -> None:
    """Top-level ``INSUFFICIENT_EVIDENCE`` status propagates."""
    parser = P1CLLM03Parser()
    model, err = parser.parse(M3_STYLE_INSUFFICIENT_EVIDENCE)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status.value == "INSUFFICIENT_EVIDENCE"
    assert model.confidence.value == "LOW"
    assert len(model.implications) == 0


def test_validation_rejects_single_affected_sub_domain() -> None:
    """Implication with only 1 ``affected_sub_domains`` is rejected.

    CORR-074 propagation: cross-lane requirement is enforced at the
    Pydantic level via ``min_length=2``. If M3 emits 1 sub-domain, the
    parser surfaces a ``ValidationError`` (caught by ``parse()``) and
    returns ``(None, "markdown parse exception: ...")``.
    """
    raw = """## Status
OK — HIGH confidence. Test.

## Implications

### IMP-01
- description: Test
- affected_sub_domains: D-01.1
- regulations: GDPR, CRA
- risk_level: MEDIUM
- confidence: HIGH
- layer0_refs: a.md, b.md
- doc07b_refs: c
"""
    parser = P1CLLM03Parser()
    model, err = parser.parse(raw)

    assert model is None, f"parser should return None: {model!r}"
    assert "affected_sub_domains" in err or "List should have" in err


def test_validation_rejects_single_regulation() -> None:
    """Implication with only 1 ``regulations`` is rejected (cross-reg requirement)."""
    raw = """## Status
OK — HIGH confidence. Test.

## Implications

### IMP-01
- description: Test
- affected_sub_domains: D-01.1, D-01.3
- regulations: GDPR
- risk_level: MEDIUM
- confidence: HIGH
- layer0_refs: a.md, b.md
- doc07b_refs: c
"""
    parser = P1CLLM03Parser()
    model, err = parser.parse(raw)

    assert model is None, f"parser should return None: {model!r}"
    assert "regulations" in err or "List should have" in err


def test_validation_at_pydantic_level_directly() -> None:
    """Belt-and-braces: the Pydantic model itself rejects <2 entries.

    Verifies the cross-lane / cross-regulation guard is enforced at
    the Pydantic layer, not just the parser — so any future caller that
    bypasses the parser (e.g. round-trip from a dict) gets the same
    protection.
    """
    with pytest.raises(ValidationError):
        P1CLLM03Implication(
            id="IMP-01",
            description="Test",
            affected_sub_domains=["D-01.1"],  # too few
            regulations=["GDPR"],  # too few
            risk_level=P1CLLM03RiskLevel.MEDIUM,
            layer0_refs=["a.md"],
            doc07b_refs=["c"],
            confidence="HIGH",
        )


def test_pydantic_min_length_constants() -> None:
    """Cross-lane + cross-regulation enforcement at the Pydantic level.

    This guards the contract — if someone weakens the ``min_length=2``
    constraint, both the parser and downstream consumers would lose
    the protection.
    """

    # Inspect the Field definitions directly. Pydantic v2 stores
    # metadata under ``json_schema_extra`` and the constraint under
    # the field's ``metadata`` attribute.
    sd_field = P1CLLM03Implication.model_fields["affected_sub_domains"]
    reg_field = P1CLLM03Implication.model_fields["regulations"]
    # Both fields must have ``min_length=2`` in their constraints.
    assert sd_field.default_factory is list or sd_field.default is None
    assert reg_field.default_factory is list or reg_field.default is None
    # The Field() constraint is encoded via metadata; we check the
    # schema-level minItems to verify the contract.
    schema = P1CLLM03Implication.model_json_schema()
    assert schema["properties"]["affected_sub_domains"].get("minItems") == 2
    assert schema["properties"]["regulations"].get("minItems") == 2


def test_normalise_risk_table() -> None:
    """Risk-level normaliser maps case variants to canonical enum token."""
    assert P1CLLM03Parser._normalise_risk("low") == "LOW"
    assert P1CLLM03Parser._normalise_risk("LOW") == "LOW"
    assert P1CLLM03Parser._normalise_risk("medium") == "MEDIUM"
    assert P1CLLM03Parser._normalise_risk("Medium") == "MEDIUM"
    assert P1CLLM03Parser._normalise_risk("high") == "HIGH"
    assert P1CLLM03Parser._normalise_risk("HIGH") == "HIGH"


def test_normalise_confidence_table() -> None:
    """Confidence normaliser maps case variants to canonical enum token."""
    assert P1CLLM03Parser._normalise_confidence("low") == "LOW"
    assert P1CLLM03Parser._normalise_confidence("LOW") == "LOW"
    assert P1CLLM03Parser._normalise_confidence("medium") == "MEDIUM"
    assert P1CLLM03Parser._normalise_confidence("high") == "HIGH"
    assert P1CLLM03Parser._normalise_confidence("HIGH") == "HIGH"
