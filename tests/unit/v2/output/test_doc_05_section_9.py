"""Unit tests for Doc 05 §9 Per-Article Breakdown (deterministic).

The §9 table is sourced from ``state['raw_clause_mappings']`` which the
orchestrator populates from ``cases/<case>/context/phase1_ontology.yaml:clause_mappings``.

These tests cover three paths:

* Happy path — full table with rows + stats summary + sign-off
* Empty path — missing/empty state key → graceful notice
* Filtering path — only applicable regulations shown when `regs` carries
  applicable flags (Case 1: GDPR + CRA applicable, NIS2/DORA/AI_Act not)

Std-lib only: pytest + the renderer import. No fixtures on disk required
because all data is synthetic dicts constructed in the test body.
"""

from __future__ import annotations

from typing import Any

from aegis_phase1.v2.output.doc_05 import _section_9_per_article_breakdown

_GOLD_54 = [
    # 3 GDPR samples to exercise sorting + stats
    {
        "clause_id": "GDPR-C01",
        "regulation_id": "REG-GDPR",
        "article": "Art. 1",
        "description": "Lawfulness of processing",
        "maps_to_subdomain": "D-05.1",
        "obligated_party": "controller",
    },
    {
        "clause_id": "GDPR-C02",
        "regulation_id": "REG-GDPR",
        "article": "Art. 2",
        "description": "Material scope",
        "maps_to_subdomain": "D-05.1",
        "obligated_party": "controller",
    },
    {
        "clause_id": "GDPR-C03",
        "regulation_id": "REG-GDPR",
        "article": "Art. 11",
        "description": "Consent",
        "maps_to_subdomain": "D-05.1",
        "obligated_party": "controller",
    },
    # 1 CRA sample (numbers > GDPR-C03 to test sort-by-article)
    {
        "clause_id": "CRA-C24",
        "regulation_id": "REG-CRA",
        "article": "Art. 24",
        "description": "Encrypted data storage",
        "maps_to_subdomain": "D-01.1",
        "obligated_party": "manufacturer",
    },
]


_CASE1_APPLICABLE_REGS = [
    {"id": "GDPR", "abbreviation": "GDPR", "applicable": True},
    {"id": "CRA", "abbreviation": "CRA", "applicable": True},
    {"id": "NIS2", "abbreviation": "NIS2", "applicable": False},
    {"id": "DORA", "abbreviation": "DORA", "applicable": False},
    {"id": "AI_Act", "abbreviation": "AI_Act", "applicable": False},
]


def _state_with_clause_mappings(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"raw_clause_mappings": list(rows)}


def test_section_9_happy_path_renders_table_and_signoff() -> None:
    """All 4 rows + sorted article order + stats summary present."""
    state = _state_with_clause_mappings(_GOLD_54)
    parts = _section_9_per_article_breakdown(state, list(_CASE1_APPLICABLE_REGS))
    md = "\n".join(parts)

    # Header
    assert "## 9. PER-ARTICLE DETAILED BREAKDOWN" in md
    # All 4 rows present (regulation filter keeps GDPR + CRA only)
    for article in ("Art. 1", "Art. 2", "Art. 11", "Art. 24"):
        assert article in md, f"missing article {article}"
    # Stats summary present
    assert "Total articles" in md
    assert "GDPR articles" in md
    assert "CRA articles" in md
    # Footer
    assert "Sign-off" in md and "§9" in md
    # Note about columns the renderer intentionally does NOT synthesise
    assert "07c Appendix A" in md
    # Table format columns
    assert "Sub-Domains" in md
    assert "Obligated Party" in md


def test_section_9_sorts_by_article_within_regulation() -> None:
    """Articles within the same regulation appear in numeric order.

    Uses regex word-boundary search so ``Art. 1`` does not match
    inside ``Art. 11``.
    """
    import re

    state = _state_with_clause_mappings(_GOLD_54)
    parts = _section_9_per_article_breakdown(state, list(_CASE1_APPLICABLE_REGS))
    md = "\n".join(parts)

    # Use word boundaries so Art. 1 doesn't match inside Art. 11.
    matches = {
        a: re.search(rf"\b{re.escape(a)}\b", md)
        for a in (
            "Art. 1",
            "Art. 2",
            "Art. 11",
            "Art. 24",
        )
    }
    for article, m in matches.items():
        assert m is not None, f"missing article {article} in §9 output"

    pos_gdpr_art1 = matches["Art. 1"].start()
    pos_gdpr_art2 = matches["Art. 2"].start()
    pos_gdpr_art11 = matches["Art. 11"].start()
    pos_cra_art24 = matches["Art. 24"].start()

    assert (
        pos_gdpr_art1 < pos_gdpr_art2 < pos_gdpr_art11
    ), "GDPR articles should appear in numeric order (1, 2, 11)"
    assert pos_cra_art24 > pos_gdpr_art11, "CRA block should come after GDPR block"


def test_section_9_filters_to_applicable_regulations() -> None:
    """NIS2/DORA/AI_Act are NOT_APPLICABLE — rows for them would never
    land in the case data (the YAML does not store them as applicable),
    but if they did appear they must be filtered out.
    """
    rows = [*list(_GOLD_54), {"clause_id": "NIS2-C01", "regulation_id": "REG-NIS2", "article": "Art. 1", "description": "Should be filtered out", "maps_to_subdomain": "D-09.2", "obligated_party": "essential entity"}]
    state = _state_with_clause_mappings(rows)
    parts = _section_9_per_article_breakdown(state, list(_CASE1_APPLICABLE_REGS))
    md = "\n".join(parts)
    assert (
        "Should be filtered out" not in md
    ), "non-applicable regulation row should be filtered out"
    # Stats must reflect only applicable regs
    assert "NIS2 articles" not in md


def test_section_9_empty_state_emits_graceful_notice() -> None:
    """Missing raw_clause_mappings → no broken empty table."""
    state: dict[str, Any] = {}
    parts = _section_9_per_article_breakdown(state, list(_CASE1_APPLICABLE_REGS))
    md = "\n".join(parts)
    assert "## 9. PER-ARTICLE DETAILED BREAKDOWN" in md
    assert "No per-article data for this case" in md
    # The broken empty table would still surface the markdown table
    # header — the notice replaces it.
    assert "| Article |" not in md


def test_section_9_empty_list_state_emits_graceful_notice() -> None:
    """raw_clause_mappings present but empty list → graceful notice."""
    state = {"raw_clause_mappings": []}
    parts = _section_9_per_article_breakdown(state, list(_CASE1_APPLICABLE_REGS))
    md = "\n".join(parts)
    assert "No per-article data for this case" in md
    assert "| Article |" not in md


def test_section_9_falls_back_to_all_rows_when_regs_is_empty() -> None:
    """No applicable_regs list provided → don't filter, show all rows."""
    state = _state_with_clause_mappings(_GOLD_54)
    parts = _section_9_per_article_breakdown(state, [])
    md = "\n".join(parts)
    # All 4 rows still present
    for article in ("Art. 1", "Art. 2", "Art. 11", "Art. 24"):
        assert article in md


def test_section_9_handles_non_dict_rows_safely() -> None:
    """Bad rows (str/None) are skipped — never crash the renderer."""
    rows = [*list(_GOLD_54), None, "garbage", 42]  # type: ignore[list-item]
    state = _state_with_clause_mappings(rows)  # type: ignore[arg-type]
    parts = _section_9_per_article_breakdown(state, list(_CASE1_APPLICABLE_REGS))
    md = "\n".join(parts)
    # Still renders the 4 good rows
    assert "Art. 1" in md
    # No exception path truncated the doc
    assert "Sign-off" in md
