"""CORR-079 regulation-chain visualization tests."""

import re
from pathlib import Path

from docs.visualization.build_regulation_chain import (
    build_html,
    load_articles,
    load_clauses,
    load_regulations,
    load_sos,
    load_srs,
)

SOURCE_PATH = Path("docs/visualization/build_regulation_chain.py")


def _source() -> str:
    return SOURCE_PATH.read_text(encoding="utf-8")


def _markdown_renderer_body() -> str:
    match = re.search(
        r"function mdToHtml\([^)]*\)\s*\{(.+?)\n    \}",
        _source(),
        re.DOTALL,
    )
    assert match, "mdToHtml not found"
    return match.group(1)


def test_articles_have_security_rules():
    """CORR-079 C1: articles preserve security_rules[]."""
    articles = load_articles()
    with_rules = sum(1 for article in articles if article.get("securityRules"))
    assert with_rules / len(articles) >= 0.95, f"only {with_rules}/{len(articles)}"


def test_articles_have_security_objectives_full():
    """CORR-079 C2: articles preserve full security objectives."""
    articles = load_articles()
    with_objectives = sum(
        1 for article in articles if article.get("securityObjectivesFull") is not None
    )
    assert with_objectives / len(articles) >= 0.95


def test_articles_have_raw_md():
    """CORR-079 C3: articles preserve source markdown."""
    articles = load_articles()
    with_markdown = sum(1 for article in articles if len(article.get("rawMd", "")) > 100)
    assert with_markdown / len(articles) >= 0.95


def test_clauses_have_obligated_party():
    """CORR-079 C4: clauses preserve obligated parties."""
    clauses = load_clauses()
    with_party = sum(1 for clause in clauses if clause.get("obligatedParty"))
    assert with_party / len(clauses) >= 0.80


def test_clauses_have_raw_md():
    """CORR-079 C5: clauses preserve source markdown."""
    clauses = load_clauses()
    with_markdown = sum(1 for clause in clauses if len(clause.get("rawMd", "")) > 50)
    assert with_markdown / len(clauses) >= 0.80


def test_regulations_have_5_top_md():
    """CORR-079 C6: regulations preserve all methodology markdown files."""
    regulations = load_regulations()
    fields = ["rawReadme", "raw01", "raw02", "rawValidation", "rawAudit"]
    for regulation in regulations:
        for field in fields:
            assert len(regulation.get(field, "")) > 50, f"{regulation['id']}.{field} empty"


def test_sos_have_raw_row():
    """CORR-079 C8: security objectives preserve their raw row."""
    objectives = load_sos()
    with_row = sum(1 for objective in objectives if len(objective.get("rawRow", "")) > 20)
    assert with_row / len(objectives) >= 0.95


def test_srs_preserve_raw_md():
    """CORR-079 C9: security rules preserve source markdown."""
    rules = load_srs()
    with_markdown = sum(1 for rule in rules if len(rule.get("raw_md", "")) > 50)
    assert with_markdown / len(rules) >= 0.95


def test_all_entities_have_cross_refs():
    """CORR-079 C10: all loaded entities expose cross-reference dictionaries."""
    entities = load_articles() + load_clauses() + load_sos() + load_srs()
    missing = [entity["id"] for entity in entities if not isinstance(entity.get("crossRefs"), dict)]
    assert not missing


def test_html_has_4_detail_tabs():
    """CORR-079 C11: generated HTML exposes four detail tabs."""
    html = build_html(articles=[], clauses=[], sos=[], srs=[])
    for tab in ["Rendered", "JSON", "Markdown", "Context"]:
        assert f">{tab}<" in html, f"tab {tab} missing"
    assert html.count("detail-tab-btn") >= 4


def test_html_has_4_tab_panes():
    """CORR-079 C12: generated HTML exposes four detail panes."""
    html = build_html(articles=[], clauses=[], sos=[], srs=[])
    assert html.count('class="tab-pane"') >= 4


def test_state_has_active_detail_tab():
    """CORR-079 C13: detail tabs default to the rendered view."""
    source = _source()
    assert "activeDetailTab" in source
    assert "activeDetailTab: 'rendered'" in source or ('activeDetailTab: "rendered"' in source)


def test_switch_detail_tab_toggles_hidden():
    """CORR-079 C14: detail tab switching controls pane visibility."""
    source = _source()
    assert "switchDetailTab" in source
    assert "hidden" in source


def test_md_to_html_handles_headings():
    """CORR-079 C15: markdown rendering supports H1 through H6."""
    body = _markdown_renderer_body()
    assert "<h1>" in body
    assert "<h6>" in body


def test_md_to_html_handles_bold_italic():
    """CORR-079 C16: markdown rendering supports emphasis."""
    body = _markdown_renderer_body()
    assert "<strong>" in body
    assert "<em>" in body


def test_md_to_html_handles_unordered_list():
    """CORR-079 C17: markdown rendering supports unordered lists."""
    body = _markdown_renderer_body()
    assert "<ul>" in body
    assert "<li>" in body


def test_md_to_html_handles_gfm_table():
    """CORR-079 C18: markdown rendering supports GFM tables."""
    body = _markdown_renderer_body()
    assert "<table" in body or "<thead" in body
    assert "<th>" in body
    assert "<td>" in body
