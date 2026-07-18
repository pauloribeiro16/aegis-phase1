"""Tests for filter_subdomains."""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.subdomains import (
    _extract_regulation,
    filter_subdomains,
)
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


def test_falls_back_to_id_extraction_when_ontology_missing(mock_state: V2State) -> None:
    """Without ontology, regulations are extracted from per_reg_sos ids.

    The new behavior is a graceful fallback: instead of returning an
    empty ``hso_per_reg``, each per_reg_sos contributes an entry whose
    regulation is parsed from the entry's id (and then text).
    """
    mock_state["ontology"] = {}
    result = filter_subdomains(mock_state, "D-04")

    assert len(result) == 4
    sub_d401 = next(s for s in result if s["id"] == "D-04.1")
    assert [e["regulation"] for e in sub_d401["hso_per_reg"]] == ["CRA"]
    sub_d402 = next(s for s in result if s["id"] == "D-04.2")
    assert [e["regulation"] for e in sub_d402["hso_per_reg"]] == ["GDPR", "CRA"]


def test_does_not_match_subdomain_with_similar_prefix(mock_state: V2State) -> None:
    """D-04 must NOT match D-04a-style siblings without the dot separator."""
    mock_state["subdomains"]["D-040"] = mock_state["subdomains"]["D-04.1"]

    result = filter_subdomains(mock_state, "D-04")
    ids = [s["id"] for s in result]
    assert "D-040" not in ids
    assert all(i.startswith("D-04.") for i in ids)


def test_applicable_regs_filter_keeps_only_matching(mock_state: V2State) -> None:
    """When applicable_regs restricts, non-applicable entries are dropped."""
    assert mock_state["company_context"] is not None
    mock_state["company_context"].applicable_regs = ["GDPR"]
    result = filter_subdomains(mock_state, "D-04")

    sub_d402 = next(s for s in result if s["id"] == "D-04.2")
    regs = [e["regulation"] for e in sub_d402["hso_per_reg"]]
    assert regs == ["GDPR"]

    sub_d401 = next(s for s in result if s["id"] == "D-04.1")
    assert sub_d401["hso_per_reg"] == []

    sub_d404 = next(s for s in result if s["id"] == "D-04.4")
    assert [e["regulation"] for e in sub_d404["hso_per_reg"]] == ["GDPR"]


def test_applicable_regs_filter_handles_canonical_synonyms(mock_state: V2State) -> None:
    """applicable_regs comparison is tolerant of canonical-form variations.

    The fixture's per_reg_sos use ``"AI Act"`` (with a space) in the id,
    while ``applicable_regs`` carries the canonical ``"AI_Act"``. The
    comparison must still match.
    """
    sub = mock_state["subdomains"]["D-04.2"]
    sub.section2_hso["per_reg_sos"] = [
        {"id": "D-04.2.1 — Sub-SO for AI Act", "text": "AI-Act text."},
    ]
    assert mock_state["company_context"] is not None
    mock_state["company_context"].applicable_regs = ["AI_Act"]
    mock_state["ontology"] = {}

    result = filter_subdomains(mock_state, "D-04")
    sub_d402 = next(s for s in result if s["id"] == "D-04.2")
    assert [e["regulation"] for e in sub_d402["hso_per_reg"]] == ["AI_Act"]


def test_no_filter_when_company_context_missing(mock_state: V2State) -> None:
    """When company_context is None, no applicability filter is applied."""
    mock_state["company_context"] = None
    result = filter_subdomains(mock_state, "D-04")

    sub_d402 = next(s for s in result if s["id"] == "D-04.2")
    assert [e["regulation"] for e in sub_d402["hso_per_reg"]] == ["GDPR", "CRA"]


def test_empty_applicable_regs_yields_empty_hso_per_reg(mock_state: V2State) -> None:
    """An empty applicable_regs list is a valid value meaning 'none apply'."""
    assert mock_state["company_context"] is not None
    mock_state["company_context"].applicable_regs = []
    result = filter_subdomains(mock_state, "D-04")

    for summary in result:
        assert summary["hso_per_reg"] == []


def test_extract_regulation_returns_canonical_codes() -> None:
    assert _extract_regulation("Sub-SO for GDPR") == "GDPR"
    assert _extract_regulation("Sub-SO for CRA") == "CRA"
    assert _extract_regulation("Sub-SO for DORA") == "DORA"
    assert _extract_regulation("Sub-SO for NIS2") == "NIS2"
    assert _extract_regulation("Sub-SO for NIS 2") == "NIS2"
    assert _extract_regulation("Sub-SO for NIS_2") == "NIS2"
    assert _extract_regulation("Sub-SO for AI Act") == "AI_Act"
    assert _extract_regulation("Sub-SO for AI_Act") == "AI_Act"
    assert _extract_regulation("Sub-SO for AIAct") == "AI_Act"
    assert _extract_regulation("no regulation here") is None
    assert _extract_regulation("") is None


def test_extract_regulation_is_case_insensitive() -> None:
    assert _extract_regulation("gdpr") == "GDPR"
    assert _extract_regulation("nis 2") == "NIS2"
    assert _extract_regulation("ai act") == "AI_Act"


def test_extract_regulation_word_boundaries() -> None:
    """Word boundaries prevent spurious partial matches."""
    assert _extract_regulation("MINIS2") is None
    assert _extract_regulation("AINIS2") is None
    assert _extract_regulation("XGDPR") is None


def test_entry_with_no_recognizable_regulation_is_skipped(mock_state: V2State) -> None:
    """per_reg_sos whose id and text have no regulation are skipped."""
    mock_state["ontology"] = {}
    sub = mock_state["subdomains"]["D-04.2"]
    sub.section2_hso["per_reg_sos"] = [
        {"id": "D-04.2.1 — Sub-SO for GDPR", "text": "GDPR text."},
        {"id": "D-04.2.2", "text": "Generic text with no regulation code."},
    ]
    assert mock_state["company_context"] is not None
    mock_state["company_context"].applicable_regs = ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"]

    result = filter_subdomains(mock_state, "D-04")
    sub_d402 = next(s for s in result if s["id"] == "D-04.2")
    assert [e["regulation"] for e in sub_d402["hso_per_reg"]] == ["GDPR"]


def test_objective_falls_back_to_hl_when_text_empty(mock_state: V2State) -> None:
    """Empty per_reg_sos text falls back to the high-level objective."""
    mock_state["ontology"] = {}
    sub = mock_state["subdomains"]["D-04.1"]
    sub.section2_hso["per_reg_sos"] = [
        {"id": "D-04.1.1 — Sub-SO for CRA", "text": "   "},
    ]
    result = filter_subdomains(mock_state, "D-04")
    sub_d401 = next(s for s in result if s["id"] == "D-04.1")
    assert len(sub_d401["hso_per_reg"]) == 1
    assert sub_d401["hso_per_reg"][0]["objective"] == sub.section2_hso["hl_objective"]
