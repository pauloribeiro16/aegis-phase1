"""Tests for filter_articles."""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.articles import _MAX_ARTICLE_CHARS, filter_articles
from aegis_phase1.v2.state import V2State

from .conftest import make_empty_state


def test_returns_clauses_for_domain(mock_state: V2State) -> None:
    result = filter_articles(mock_state, "D-04")

    regs = {s["regulation"] for s in result}
    assert regs == {"GDPR", "CRA"}
    arts = {s["article"] for s in result}
    assert "Art. 33" in arts


def test_short_name_strips_REG_prefix(mock_state: V2State) -> None:
    result = filter_articles(mock_state, "D-04")

    for snippet in result:
        assert not snippet["regulation"].startswith("REG-")


def test_truncates_long_text(mock_state: V2State) -> None:
    result = filter_articles(mock_state, "D-04")

    art33 = next(s for s in result if s["article"] == "Art. 33")
    assert len(art33["text"]) <= _MAX_ARTICLE_CHARS + 10
    assert art33["text"].endswith("[…]")


def test_short_text_not_truncated(mock_state: V2State) -> None:
    result = filter_articles(mock_state, "D-04")

    art34 = next(s for s in result if s["article"] == "Art. 34")
    assert not art34["text"].endswith("…")
    assert "Short text" in art34["text"]


def test_returns_empty_for_unknown_domain(mock_state: V2State) -> None:
    assert filter_articles(mock_state, "D-99") == []


def test_returns_empty_when_clause_mappings_missing(mock_state: V2State) -> None:
    mock_state["ontology"]["clause_mappings"] = []
    assert filter_articles(mock_state, "D-04") == []


def test_dedupes_repeated_clause(mock_state: V2State) -> None:
    """Same article appearing twice in clause_mappings → returned once."""
    dup = dict(mock_state["ontology"]["clause_mappings"][0])
    mock_state["ontology"]["clause_mappings"].append(dup)

    result = filter_articles(mock_state, "D-04")
    arts = [s["article"] for s in result]
    assert arts.count("Art. 33") == 1


def test_handles_empty_state() -> None:
    state = make_empty_state()
    assert filter_articles(state, "D-04") == []


def test_results_sorted_by_regulation_then_article(mock_state: V2State) -> None:
    result = filter_articles(mock_state, "D-04")
    keys = [(s["regulation"], s["article"]) for s in result]
    assert keys == sorted(keys)


def test_skips_entries_without_article(mock_state: V2State) -> None:
    mock_state["ontology"]["clause_mappings"].append(
        {
            "clause_id": "GDPR-EMPTY",
            "regulation_id": "REG-GDPR",
            "description": "no article",
            "maps_to_subdomain": "D-04.3",
        }
    )

    result = filter_articles(mock_state, "D-04")
    for snippet in result:
        assert snippet["article"]