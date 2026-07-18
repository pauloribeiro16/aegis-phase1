"""Tests for ``aegis_phase1.v2.domain.anchor_validator``.

Covers the 6 regression scenarios called out in CONTRACT-022 §E.2 plus the
Annex II / Annex I hallucination guard (C10).
"""

from __future__ import annotations

from aegis_phase1.v2.domain.anchor_validator import (
    extract_anchors,
    extract_anchors_with_context,
    normalize_anchor,
    validate_output_citations,
)


def test_extract_anchors_gdpr() -> None:
    anchors = extract_anchors("Art. 30(3) + Art. 5(2) + Art. 31 GDPR")

    assert anchors == {"art:30(3)", "art:5(2)", "art:31"}


def test_extract_anchers_cra_annexes() -> None:
    anchors = extract_anchors("Annex VII §5-§8 + Annex I Part II (3)")

    assert "annex:vii" in anchors
    assert "annex:i" in anchors
    assert "section:5" in anchors
    assert "section:8" in anchors


def test_extract_anchors_empty() -> None:
    assert extract_anchors("") == set()


def test_validate_output_with_annex_ii_hallucination() -> None:
    output = "Annex II Part II (6) CRA"
    source = {"annex:i"}

    ok, unknown = validate_output_citations(output, source)

    assert ok is False
    assert "annex:ii" in unknown


def test_validate_output_with_only_known_anchors() -> None:
    output = "Art. 30(3) GDPR + Annex VII CRA"
    source = {"art:30(3)", "art:5(2)", "annex:vii"}

    ok, unknown = validate_output_citations(output, source)

    assert ok is True
    assert unknown == []


def test_extract_anchors_with_context() -> None:
    result = extract_anchors_with_context("Art. 30(3) GDPR and Annex VII §5 CRA")

    assert "GDPR" in result
    assert "art:30(3)" in result["GDPR"]
    assert "CRA" in result
    assert "annex:vii" in result["CRA"]


def test_normalize_anchor_lowercases_and_strips() -> None:
    assert normalize_anchor("Art. 30(3)") == "art:30(3)"
    assert normalize_anchor("art. 30") == "art:30"
    assert normalize_anchor("Annex VII") == "annex:vii"
    assert normalize_anchor("annex i part ii (3)") == "annex:i part ii (3)"
    assert normalize_anchor("§5") == "section:5"
