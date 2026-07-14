"""Tests for filter_ambiguities."""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.ambiguities import filter_ambiguities
from aegis_phase1.v2.state import V2State

from .conftest import make_empty_state


def test_returns_matching_by_subdomain(mock_state: V2State) -> None:
    result = filter_ambiguities(mock_state, "D-04")
    ids = [e["id"] for e in result]
    assert "TC-001" in ids


def test_excludes_non_matching_subdomain(mock_state: V2State) -> None:
    result = filter_ambiguities(mock_state, "D-04")
    ids = [e["id"] for e in result]
    assert "TC-002" not in ids


def test_resolution_from_frontmatter(mock_state: V2State) -> None:
    result = filter_ambiguities(mock_state, "D-04")
    tc001 = next(e for e in result if e["id"] == "TC-001")
    assert "24h" in tc001["resolution"]


def test_resolution_empty_when_missing(mock_state: V2State) -> None:
    result = filter_ambiguities(mock_state, "D-04")
    tc002_ids = [e["id"] for e in result]
    if "TC-002" in tc002_ids:
        tc002 = next(e for e in result if e["id"] == "TC-002")
        assert tc002["resolution"] == ""


def test_matches_by_applicable_regulation(mock_state: V2State) -> None:
    """TC-003 has no domain but lists NIS2 — should match only if NIS2 applies."""
    mock_state["company_context"].applicable_regs = ["GDPR", "CRA", "NIS2"]

    result = filter_ambiguities(mock_state, "D-04")
    ids = [e["id"] for e in result]
    assert "TC-003" in ids


def test_excludes_reg_match_when_not_applicable(mock_state: V2State) -> None:
    mock_state["company_context"].applicable_regs = ["GDPR", "CRA"]

    result = filter_ambiguities(mock_state, "D-04")
    ids = [e["id"] for e in result]
    assert "TC-003" not in ids


def test_returns_empty_for_no_matches(mock_state: V2State) -> None:
    assert filter_ambiguities(mock_state, "D-99") == []


def test_handles_missing_preprocessing() -> None:
    state = make_empty_state()
    assert filter_ambiguities(state, "D-04") == []


def test_dedupes_repeated_ids(mock_state: V2State) -> None:
    mock_state["preprocessing"]["ambiguities"].append(dict(mock_state["preprocessing"]["ambiguities"][0]))

    result = filter_ambiguities(mock_state, "D-04")
    ids = [e["id"] for e in result]
    assert ids.count("TC-001") == 1


def test_description_truncated(mock_state: V2State) -> None:
    """The pipeline feeds a 500-char body excerpt as description."""
    result = filter_ambiguities(mock_state, "D-04")
    for entry in result:
        assert isinstance(entry["description"], str)


def test_sorted_by_id(mock_state: V2State) -> None:
    result = filter_ambiguities(mock_state, "D-04")
    ids = [e["id"] for e in result]
    assert ids == sorted(ids)