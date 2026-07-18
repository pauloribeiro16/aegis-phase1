"""Tests for the OJ article loader."""

from pathlib import Path

from aegis_phase1.v2.loader.article_loader import load_article, load_articles_for_domain

PREPROCESSING = Path(
    "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/" "00_METHODOLOGY/PREPROCESSING"
)


def test_load_article_gdpr_art_30() -> None:
    article = load_article("GDPR", "Art. 30", PREPROCESSING)

    assert article is not None
    assert article["regulation"] == "GDPR"
    assert "30" in article["article"]
    assert article["text"]
    assert article["source_file"].endswith("Art_30.md")


def test_load_article_missing_returns_none() -> None:
    assert load_article("GDPR", "Art. 999", PREPROCESSING) is None


def test_load_articles_for_domain_d10() -> None:
    articles = load_articles_for_domain("D-10", ["GDPR", "CRA"], PREPROCESSING)

    assert sum(article["regulation"] == "GDPR" for article in articles) >= 1
    assert sum(article["regulation"] == "CRA" for article in articles) >= 1
