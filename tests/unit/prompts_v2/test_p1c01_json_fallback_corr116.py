"""CORR-116 S2.2 regression: P1CLLM01Parser JSON-envelope fallback.

Real failure (JOB 1904151, 2026-09-09): nemotron-3.5-lightning:30b answers
P1C-LLM-01-OVERLAP-CLASSIFICATION per-domain lanes with a valid pure-JSON
envelope carrying the canonical ``sub_domain_activations`` key — 30/30
attempts rejected with "no `## Section` headers found in markdown", MAP
10/10 FAILED, exit 2. The content was correct; only the serialization
differed from the two markdown shapes.
"""

from pathlib import Path

import pytest

from aegis_phase1._archive.corr061.markdown_parser import P1CLLM01Parser

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "p1c01"
    / "nemotron_json_d01.md"
)


@pytest.fixture
def nemotron_json_raw() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_real_nemotron_json_envelope_parses(nemotron_json_raw: str) -> None:
    """The actual JOB 1904151 lane D-01 response must parse with activations."""
    output, error = P1CLLM01Parser().parse(nemotron_json_raw)

    assert error == "", f"expected clean parse, got error: {error}"
    assert output is not None
    assert output.status.value == "OK"
    assert len(output.sub_domain_activations) == 2

    rec = output.sub_domain_activations[0]
    assert rec["sub_domain_id"] == "D-01.1"
    assert rec["applicable"] == "YES"
    assert rec["company_scope_verdict"] == "YES"
    assert rec["reg_pair"] == ["GDPR", "CRA"]
    assert rec["layer0_refs"] == ["SubDomains/D-01.1.md §1 CRDA"]


def test_markdown_shape_a_still_parses() -> None:
    """The fallback must not change behaviour for canonical Shape A."""
    raw = (
        "## Status\n- status: OK\n- confidence: HIGH\n\n"
        "## Sub-domain Activations\n\n"
        "### D-01.1\n"
        "- sub_domain_id: D-01.1\n"
        "- reg_pair: [GDPR, CRA]\n"
        "- company_scope_verdict: APPLICABLE\n"
        "- layer0_refs: [SubDomains/D-01.1.md §1]\n"
    )
    output, error = P1CLLM01Parser().parse(raw)

    assert error == ""
    assert output is not None
    assert len(output.sub_domain_activations) == 1
    assert output.sub_domain_activations[0]["sub_domain_id"] == "D-01.1"


def test_json_without_activations_still_fails_cleanly() -> None:
    """A JSON envelope without sub_domain_activations keeps the old error."""
    output, error = P1CLLM01Parser().parse('{"status": "OK", "confidence": "HIGH"}')

    assert output is None
    assert "no `## Section` headers" in error


def test_prose_still_fails_cleanly() -> None:
    output, error = P1CLLM01Parser().parse("free text, no structure at all")

    assert output is None
    assert "no `## Section` headers" in error
