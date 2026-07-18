"""Tests for regulation-scoped ambiguity filtering."""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.ambiguities import filter_ambiguities
from aegis_phase1.v2.state import V2State

from .conftest import make_empty_state


def test_filter_ambiguities_returns_non_empty_for_gdpr(mock_state: V2State) -> None:
    mock_state["company_context"].applicable_regs = ["GDPR"]

    result = filter_ambiguities(mock_state, "D-10")

    assert result
    assert all(entry["regulation"] == "GDPR" for entry in result)
    assert {"id", "regulation", "description", "resolution", "source_file"} <= set(result[0])


def test_filter_ambiguities_returns_only_applicable_regs(mock_state: V2State) -> None:
    result = filter_ambiguities(mock_state, "D-04")

    assert result
    assert {entry["regulation"] for entry in result} <= {"GDPR", "CRA"}


def test_returns_empty_when_no_regs_are_available() -> None:
    state = make_empty_state()

    assert filter_ambiguities(state, "D-04") == []


def test_returns_empty_for_unknown_domain_without_context() -> None:
    state = make_empty_state()

    assert filter_ambiguities(state, "D-99") == []
