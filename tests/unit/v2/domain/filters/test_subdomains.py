"""Tests for filter_subdomains."""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.subdomains import filter_subdomains
from aegis_phase1.v2.state import V2State

from .conftest import make_empty_state


def test_returns_only_subdomains_matching_prefix(mock_state: V2State) -> None:
    result = filter_subdomains(mock_state, "D-04")

    ids = [s["id"] for s in result]
    assert ids == ["D-04.1", "D-04.2", "D-04.3", "D-04.4"]
    assert "D-05.1" not in ids


def test_summary_shape(mock_state: V2State) -> None:
    result = filter_subdomains(mock_state, "D-04")

    for summary in result:
        assert set(summary.keys()) == {
            "id",
            "title",
            "hso_hl",
            "hso_per_reg",
            "volere_requirements",
        }
        assert isinstance(summary["hso_per_reg"], list)
        assert isinstance(summary["volere_requirements"], list)


def test_hso_per_reg_attributed_to_correct_regulation(mock_state: V2State) -> None:
    result = filter_subdomains(mock_state, "D-04")

    sub_d402 = next(s for s in result if s["id"] == "D-04.2")
    regs = [entry["regulation"] for entry in sub_d402["hso_per_reg"]]
    assert regs == ["GDPR", "CRA"]
    assert all(entry["objective"] for entry in sub_d402["hso_per_reg"])


def test_hso_per_reg_singleton_for_single_reg_subdomain(mock_state: V2State) -> None:
    result = filter_subdomains(mock_state, "D-04")

    sub_d401 = next(s for s in result if s["id"] == "D-04.1")
    assert len(sub_d401["hso_per_reg"]) == 1
    assert sub_d401["hso_per_reg"][0]["regulation"] == "CRA"


def test_volere_requirements_present(mock_state: V2State) -> None:
    result = filter_subdomains(mock_state, "D-04")

    for summary in result:
        assert summary["volere_requirements"], f"Missing Volere reqs for {summary['id']}"
        req = summary["volere_requirements"][0]
        assert req["id"].startswith("REQ-")
        assert req["priority"] == "MUST"


def test_returns_empty_list_when_no_match(mock_state: V2State) -> None:
    result = filter_subdomains(mock_state, "D-99")
    assert result == []


def test_returns_empty_list_when_subdomains_missing() -> None:
    state = make_empty_state()
    assert filter_subdomains(state, "D-04") == []


def test_handles_missing_ontology_gracefully(mock_state: V2State) -> None:
    mock_state["ontology"] = {}
    result = filter_subdomains(mock_state, "D-04")

    assert len(result) == 4
    for summary in result:
        assert summary["hso_per_reg"] == []


def test_does_not_match_subdomain_with_similar_prefix(mock_state: V2State) -> None:
    """D-04 must NOT match D-04a-style siblings without the dot separator."""
    mock_state["subdomains"]["D-040"] = mock_state["subdomains"]["D-04.1"]

    result = filter_subdomains(mock_state, "D-04")
    ids = [s["id"] for s in result]
    assert "D-040" not in ids
    assert all(i.startswith("D-04.") for i in ids)