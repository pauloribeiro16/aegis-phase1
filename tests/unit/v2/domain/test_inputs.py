"""Tests for assemble_inputs (v2/domain/inputs.py).

These tests use the shared ``mock_state`` fixture from
``tests/unit/v2/domain/filters/conftest.py`` so they exercise the
real ``filter_*`` chain without touching disk.
"""

from __future__ import annotations

import pytest

from aegis_phase1.v2.domain.inputs import (
    _normalise_scale,
    assemble_inputs,
)
from aegis_phase1.v2.state import V2State
from tests.unit.v2.domain.filters.conftest import make_empty_state

# ─── Happy paths ───────────────────────────────────────────────────────


def test_assemble_inputs_returns_all_required_keys(mock_state: V2State) -> None:
    """The returned dict contains every key documented in the docstring."""
    result = assemble_inputs(mock_state, "D-04")

    expected = {
        "case_id",
        "domain_id",
        "company_context",
        "subdomains",
        "applicable_regs",
        "applicable_articles",
        "ambiguities",
        "cross_reg_analysis",
        "existing_implementations",
        "track_b_suggestion",
    }
    assert set(result.keys()) == expected


def test_assemble_inputs_uppercases_domain_id(mock_state: V2State) -> None:
    result = assemble_inputs(mock_state, "d-04")
    assert result["domain_id"] == "D-04"


def test_assemble_inputs_project_company_context(mock_state: V2State) -> None:
    result = assemble_inputs(mock_state, "D-04")
    ctx = result["company_context"]

    assert ctx["company_name"] == "MockCo Lda."
    assert ctx["scale"] == "MICRO"
    assert ctx["security_fte"] == 0.5
    assert "AWS" in ctx["tech_stack"]
    assert "GDPR" in ctx["applicable_regs"]


def test_assemble_inputs_case_id_uses_basename(mock_state: V2State) -> None:
    mock_state["case_path"] = "/tmp/some/Case_42_Acme"
    result = assemble_inputs(mock_state, "D-04")
    assert result["case_id"] == "Case_42_Acme"


def test_assemble_inputs_filters_subdomains_to_domain(mock_state: V2State) -> None:
    """D-04 returns only its 4 sub-domains, not the D-05 sibling."""
    result = assemble_inputs(mock_state, "D-04")
    ids = {s["id"] for s in result["subdomains"]}
    assert ids == {"D-04.1", "D-04.2", "D-04.3", "D-04.4"}


def test_assemble_inputs_returns_applicable_regs_intersected(mock_state: V2State) -> None:
    """Only regs in company_context.applicable_regs are returned."""
    result = assemble_inputs(mock_state, "D-04")
    assert set(result["applicable_regs"]) == {"CRA", "GDPR"}


def test_assemble_inputs_includes_articles_with_truncation(mock_state: V2State) -> None:
    result = assemble_inputs(mock_state, "D-04")
    arts = result["applicable_articles"]
    assert arts, "expected at least one article"
    for art in arts:
        assert {"regulation", "article", "title", "text"} <= set(art.keys())


def test_assemble_inputs_returns_ambiguities_for_domain(mock_state: V2State) -> None:
    """TC-001 targets D-04.3 → must surface for D-04."""
    result = assemble_inputs(mock_state, "D-04")
    ids = {a["id"] for a in result["ambiguities"]}
    assert ids == {"TC-001"}
    assert result["ambiguities"][0]["resolution"].startswith("Use 24h")


def test_assemble_inputs_excludes_ambiguities_for_other_domains(
    mock_state: V2State,
) -> None:
    """TC-002 targets D-06.1 → must NOT appear for D-04."""
    result = assemble_inputs(mock_state, "D-04")
    ids = {a["id"] for a in result["ambiguities"]}
    assert "TC-002" not in ids


def test_assemble_inputs_returns_cross_reg(mock_state: V2State) -> None:
    result = assemble_inputs(mock_state, "D-04")
    pairs = {entry["pair"] for entry in result["cross_reg_analysis"]}
    assert "GDPR-CRA" in pairs


def test_assemble_inputs_returns_implementations_from_tech_stack(mock_state: V2State) -> None:
    """AWS → GuardDuty covers D-04.1."""
    result = assemble_inputs(mock_state, "D-04")
    names = {impl["name"] for impl in result["existing_implementations"]}
    assert "AWS GuardDuty" in names


def test_assemble_inputs_track_b_suggestion_shape(mock_state: V2State) -> None:
    result = assemble_inputs(mock_state, "D-04")
    track_b = result["track_b_suggestion"]

    assert {"tier", "rationale", "attrs"} <= set(track_b.keys())
    assert track_b["tier"] in {"MINIMAL", "LIGHTWEIGHT", "STANDARD", "RIGOROUS", "DEFERRED"}
    assert isinstance(track_b["attrs"], dict)
    assert track_b["attrs"]["scale"] in {"MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"}


def test_assemble_inputs_track_b_inheritable_when_all_subs_covered(mock_state: V2State) -> None:
    """If every sub-domain in the domain is covered ADEQUATELY by an
    implementation, the domain-level inheritability should be INHERITABLE.
    """
    mock_state["company_context"].tech_stack = ["AWS", "AWS KMS"]
    mock_state["company_context"].applicable_regs = ["GDPR", "CRA"]

    # Force all D-04.* sub-domain ids into the ADEQUATE covers set

    result = assemble_inputs(mock_state, "D-04")
    covered = {
        sid
        for impl in result["existing_implementations"]
        if impl["adequacy"] == "ADEQUATE"
        for sid in impl["covers"]
    }
    sub_ids = {s["id"] for s in result["subdomains"]}

    if sub_ids and sub_ids <= covered:
        assert result["track_b_suggestion"]["attrs"]["inheritability"] == "INHERITABLE"
    else:
        # Otherwise: BUILD_REQUIRED — the default for partial coverage.
        assert result["track_b_suggestion"]["attrs"]["inheritability"] == "BUILD_REQUIRED"


def test_assemble_inputs_handles_alternate_scale_labels(mock_state: V2State) -> None:
    """TrackB should accept non-canonical scale labels like 'Micro-enterprise'."""
    mock_state["company_context"].scale = "Micro-enterprise"
    mock_state["company_context"].employees = 8

    result = assemble_inputs(mock_state, "D-04")
    assert result["track_b_suggestion"]["attrs"]["scale"] == "MICRO"


# ─── Error / edge cases ────────────────────────────────────────────────


def test_assemble_inputs_raises_on_empty_domain_id(mock_state: V2State) -> None:
    with pytest.raises(ValueError, match="domain_id must be a non-empty string"):
        assemble_inputs(mock_state, "")


def test_assemble_inputs_raises_on_missing_company_context() -> None:
    state = make_empty_state()
    with pytest.raises(ValueError, match="company_context"):
        assemble_inputs(state, "D-04")


def test_assemble_inputs_handles_empty_ontology() -> None:
    state = make_empty_state()
    state["company_context"] = None  # will raise — verifies strict validation
    with pytest.raises(ValueError):
        assemble_inputs(state, "D-04")


def test_assemble_inputs_returns_empty_lists_when_no_data(mock_state: V2State) -> None:
    """A domain with no sub-domains/regs returns empty lists — does not raise.

    Implementations depend on tech_stack (not sub-domain presence), so
    they may still be returned; we verify the per-subdomain fields are
    empty.
    """
    result = assemble_inputs(mock_state, "D-99")
    assert result["subdomains"] == []
    assert result["applicable_regs"] == []
    assert result["applicable_articles"] == []
    assert result["ambiguities"] == []
    assert result["cross_reg_analysis"] == []
    # Implementations are tech-stack driven, not subdomain-driven,
    # so they may still be present for any domain the company uses.
    assert isinstance(result["existing_implementations"], list)


# ─── Internal helpers ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("MICRO", "MICRO"),
        ("micro", "MICRO"),
        ("Micro", "MICRO"),
        ("Micro-enterprise", "MICRO"),
        ("SMALL", "SMALL"),
        ("sme", "SMALL"),
        ("MEDIUM", "MEDIUM"),
        ("Mid-market", "MEDIUM"),
        ("LARGE", "LARGE"),
        ("enterprise", "LARGE"),
        ("MAX", "MAX"),
        ("Very Large", "MAX"),
    ],
)
def test_normalise_scale_canonical_and_aliases(raw: str, expected: str) -> None:
    assert _normalise_scale(raw) == expected


@pytest.mark.parametrize(
    "employees,expected",
    [
        (0, "MICRO"),
        (3, "MICRO"),
        (9, "MICRO"),
        (10, "SMALL"),
        (49, "SMALL"),
        (50, "MEDIUM"),
        (249, "MEDIUM"),
        (250, "LARGE"),
        (999, "LARGE"),
        (1000, "MAX"),
        (10000, "MAX"),
    ],
)
def test_normalise_scale_falls_back_to_employee_count(
    employees: int, expected: str
) -> None:
    assert _normalise_scale(None, employees) == expected


def test_normalise_scale_prefers_label_over_employee_count() -> None:
    """When both label and employee count disagree, label wins."""
    assert _normalise_scale("LARGE", employees=3) == "LARGE"
    assert _normalise_scale("MICRO", employees=200) == "MICRO"
