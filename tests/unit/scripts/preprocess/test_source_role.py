"""CORR-078 WS2 — Tests for the ``source_role`` schema field.

Covers:
  C7 — each ``regulation/<REG>/articles/Art_*.json`` has ``source_role`` ∈
       {primary_source, supporting_citation, out_of_scope}
  C8 — in-scope count for AI_Act == 13 primary_source (matches 00_README.md)

Methodology-main must be present; tests are skipped if not.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "src"))

METHODOLOGY = REPO_ROOT.parent / "Methodology-main" / "00_METHODOLOGY"
PREPROC_OUT = REPO_ROOT / "preproc_out"

requires_methodology = pytest.mark.skipif(
    not METHODOLOGY.is_dir(),
    reason="Methodology-main not mounted; CORR-078 WS2 tests need real MD sources",
)


# ─── source_role unit tests ──────────────────────────────────────────────


@requires_methodology
def test_compute_source_role_primary_source() -> None:
    """An in-scope article with own source_clauses is primary_source."""
    from scripts.preprocess.source_role import compute_source_role

    article = {
        "article_ref": "Art. 9",
        "security_rules": [
            {"source_clauses": [{"article_ref": "Art. 9(1)"}]}
        ],
    }
    in_scope = [9, 10, 12, 13, 14, 15, 17, 19, 26, 55, 72, 73, 74]
    assert compute_source_role(article, in_scope, "AI_Act") == "primary_source"


@requires_methodology
def test_compute_source_role_out_of_scope() -> None:
    """An article NOT in-scope and with NO own source_clauses is out_of_scope."""
    from scripts.preprocess.source_role import compute_source_role

    article = {
        "article_ref": "Art. 3",
        "security_rules": [
            {"source_clauses": [{"article_ref": "Art. 73(1)"}]}
        ],
    }
    in_scope = [9, 10, 12, 13, 14, 15, 17, 19, 26, 55, 72, 73, 74]
    assert compute_source_role(article, in_scope, "AI_Act") == "out_of_scope"


@requires_methodology
def test_compute_source_role_supporting_citation() -> None:
    """An in-scope article whose SRs reference OTHER articles is
    supporting_citation."""
    from scripts.preprocess.source_role import compute_source_role

    article = {
        "article_ref": "Art. 55",
        "security_rules": [
            {"source_clauses": [{"article_ref": "Art. 73(1)"}]}
        ],
    }
    in_scope = [9, 10, 12, 13, 14, 15, 17, 19, 26, 55, 72, 73, 74]
    assert compute_source_role(article, in_scope, "AI_Act") == "supporting_citation"


@requires_methodology
def test_extract_in_scope_articles_ai_act_count_13() -> None:
    """AI_Act 00_README.md enumerates 13 in-scope articles."""
    from scripts.preprocess.source_role import extract_in_scope_articles

    readme = (
        METHODOLOGY / "PREPROCESSING/Regulation/AI_Act/00_README.md"
    )
    in_scope = extract_in_scope_articles(readme)
    assert len(in_scope) == 13
    # Spot-check the canonical numbers (per CORR-077 §1 spec):
    for n in (9, 10, 12, 13, 14, 15, 17, 19, 26, 55, 72, 73, 74):
        assert n in in_scope, f"AI_Act in-scope must contain Art. {n}"


@requires_methodology
def test_extract_in_scope_handles_gdpr_range_and_exclusion() -> None:
    """GDPR range 'Art. 5-49' minus 'excluding Art. 40-43 and Art. 50'."""
    from scripts.preprocess.source_role import extract_in_scope_articles

    readme = METHODOLOGY / "PREPROCESSING/Regulation/GDPR/00_README.md"
    in_scope = extract_in_scope_articles(readme)
    # Art. 4 included, range 5-49 minus 40-43 = 41, but spec reads 42 (the
    # post-processing README comment says 41 — actual count after parser
    # excludes 40-43 from the range only, 50 isn't in the range so it's a no-op).
    assert 4 in in_scope
    assert 5 in in_scope
    assert 39 in in_scope
    assert 44 in in_scope
    assert 49 in in_scope
    for n in (40, 41, 42, 43):
        assert n not in in_scope


# ─── Pre-processor integration: C7 / C8 (full preproc_out walk) ──────────


def test_c7_all_articles_have_valid_source_role_after_regen() -> None:
    """C7: every article JSON has source_role in the canonical Literal set."""
    if not PREPROC_OUT.is_dir():
        pytest.skip("preproc_out/ not yet regenerated (WS4)")
    import json

    VALID = {"primary_source", "supporting_citation", "out_of_scope"}
    total = 0
    for art_dir in (PREPROC_OUT / "regulation").glob("*/articles"):
        for f in sorted(art_dir.glob("Art_*.json")):
            d = json.loads(f.read_text())
            total += 1
            sr = d.get("source_role")
            assert sr in VALID, f"{f}: source_role={sr!r} not in {VALID}"
    assert total > 0, "no article shards found — was WS2 run?"


def test_c8_ai_act_has_13_primary_source() -> None:
    """C8: AI_Act has 13 primary_source articles (matches 00_README.md)."""
    if not PREPROC_OUT.is_dir():
        pytest.skip("preproc_out/ not yet regenerated (WS4)")
    import json

    art_dir = PREPROC_OUT / "regulation/AI_Act/articles"
    if not art_dir.is_dir():
        pytest.skip("AI_Act/articles shard missing — was WS2 run?")
    primary = sum(
        1
        for f in art_dir.glob("Art_*.json")
        if json.loads(f.read_text()).get("source_role") == "primary_source"
    )
    assert primary == 13, f"AI_Act expected 13 primary_source, got {primary}"
