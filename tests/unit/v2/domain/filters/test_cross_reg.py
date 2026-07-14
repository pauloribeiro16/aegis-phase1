"""Tests for filter_cross_reg."""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.cross_reg import filter_cross_reg
from aegis_phase1.v2.state import V2State

from .conftest import make_empty_state


def test_returns_pairs_for_subdomain(mock_state: V2State) -> None:
    result = filter_cross_reg(mock_state, "D-04")

    pairs = [e["pair"] for e in result]
    assert "GDPR-CRA" in pairs
    assert "GDPR-NIS2" in pairs


def test_includes_domain_level_entry_for_match(mock_state: V2State) -> None:
    """D-04 entry (no .Y) must match D-04 prefix."""
    result = filter_cross_reg(mock_state, "D-04")
    pairs = [e["pair"] for e in result]
    assert "GDPR-CRA" in pairs


def test_excludes_other_subdomain(mock_state: V2State) -> None:
    result = filter_cross_reg(mock_state, "D-04")
    pairs = [e["pair"] for e in result]
    assert not any("Minimisation" in e["summary"] for e in result)


def test_type_inferred_from_text(mock_state: V2State) -> None:
    result = filter_cross_reg(mock_state, "D-04")

    tc_gdpr_cra = next(e for e in result if e["pair"] == "GDPR-CRA")
    assert tc_gdpr_cra["type"] in {
        "TIMELINE_DIVERGENCE",
        "SCOPE_DIVERGENCE",
        "REQUIREMENT_DIVERGENCE",
        "INTENSITY_DIVERGENCE",
        "OVERLAP",
    }


def test_timeline_text_inferred_as_timeline(mock_state: V2State) -> None:
    result = filter_cross_reg(mock_state, "D-04")

    timeline = next(e for e in result if e["type"] == "TIMELINE_DIVERGENCE")
    assert "Timeline" in timeline["summary"] or "timeline" in timeline["summary"]


def test_summary_present(mock_state: V2State) -> None:
    result = filter_cross_reg(mock_state, "D-04")
    for entry in result:
        assert isinstance(entry["summary"], str)
        assert entry["summary"]


def test_returns_empty_for_no_match(mock_state: V2State) -> None:
    assert filter_cross_reg(mock_state, "D-99") == []


def test_handles_empty_preprocessing() -> None:
    state = make_empty_state()
    assert filter_cross_reg(state, "D-04") == []


def test_dedupes_same_pair(mock_state: V2State) -> None:
    mock_state["preprocessing"]["cross_regulation"][0]["pairs"].append(
        {
            "reg_pair": "GDPR-CRA",
            "text": "Duplicate pair block.",
        }
    )

    result = filter_cross_reg(mock_state, "D-04")
    pairs = [e["pair"] for e in result]
    assert pairs.count("GDPR-CRA") == 1


def test_sorted_by_pair_then_type(mock_state: V2State) -> None:
    result = filter_cross_reg(mock_state, "D-04")
    keys = [(e["pair"], e["type"]) for e in result]
    assert keys == sorted(keys)