"""Tests for disk-backed OJ article filtering."""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.articles import filter_articles
from aegis_phase1.v2.state import V2State

from .conftest import make_empty_state


def test_returns_articles_for_domain(mock_state: V2State) -> None:
    result = filter_articles(mock_state, "D-04")

    regs = {article["regulation"] for article in result}
    assert regs == {"GDPR", "CRA"}
    assert any(article["article"] == "Art. 33" for article in result)


def test_short_name_does_not_include_reg_prefix(mock_state: V2State) -> None:
    result = filter_articles(mock_state, "D-04")

    assert all(not article["regulation"].startswith("REG-") for article in result)


def test_filter_articles_returns_verbatim_text(mock_state: V2State) -> None:
    result = filter_articles(mock_state, "D-10.2")

    gdpr_article = next(article for article in result if article["regulation"] == "GDPR")
    assert len(gdpr_article["text"]) > 200


def test_returns_empty_for_unknown_domain(mock_state: V2State) -> None:
    assert filter_articles(mock_state, "D-99") == []


def test_returns_empty_for_state_without_applicable_regs(mock_state: V2State) -> None:
    mock_state["ontology"] = {}
    mock_state["company_context"] = None

    assert filter_articles(mock_state, "D-10") == []


def test_handles_empty_state() -> None:
    assert filter_articles(make_empty_state(), "D-04") == []


def test_results_sorted_by_regulation_then_article(mock_state: V2State) -> None:
    result = filter_articles(mock_state, "D-04")
    keys = [(article["regulation"], article["article"]) for article in result]

    assert keys == sorted(keys)
