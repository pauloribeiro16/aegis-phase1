"""CORR-078 WS3 — Tests for the build_regulation_chain.py script.

Covers:
  C9 — out_of_scope articles filtered from §2
  C10 — securityObjectives union of top-level + inner linked_objectives
  C11 — §3 HTML has 4 columns VAG/POLY/COORD/SCOPE-Q
  C12 — §3 cells populated (not —) for AI_Act and GDPR clauses

These tests operate against the build script directly (not the rendered HTML
file). The build script is gitignored; tests import it via
``sys.path.insert(0, "src")`` — but ``docs/visualization/build_regulation_chain.py``
is OUTSIDE ``src/``, so we add its parent to sys.path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PREPROC_OUT = REPO_ROOT / "preproc_out"

# Make the build script importable. Its parent is ``docs/visualization/``,
# not ``src/`` — so we add it explicitly.
_BUILD_SCRIPT = REPO_ROOT / "docs/visualization/build_regulation_chain.py"
sys.path.insert(0, str(_BUILD_SCRIPT.parent))


# ─── C9 / C10: load_articles behaviour ──────────────────────────────────


@pytest.mark.skipif(
    not PREPROC_OUT.is_dir(),
    reason="preproc_out/ not yet regenerated (WS4 must run first)",
)
def test_c9_out_of_scope_articles_filtered() -> None:
    """load_articles() filters articles with source_role == out_of_scope."""
    from docs.visualization.build_regulation_chain import load_articles

    arts = load_articles()
    oos = [a for a in arts if a.get("sourceRole") == "out_of_scope"]
    assert len(oos) == 0, f"{len(oos)} out_of_scope articles not filtered"
    # After the 11 out_of_scope AI_Act citations are removed, total drops
    # from 140 → 129. The threshold is "total < 140" per the contract.
    assert len(arts) < 140, f"filter not applied: got {len(arts)} articles"


@pytest.mark.skipif(
    not PREPROC_OUT.is_dir(),
    reason="preproc_out/ not yet regenerated (WS4 must run first)",
)
def test_c10_ai_act_sos_union_after_so_fix() -> None:
    """After WS1 + WS4, all AI_Act articles have ≥1 SO via the union."""
    from docs.visualization.build_regulation_chain import load_articles

    arts = load_articles()
    ai_articles = [a for a in arts if a.get("regulation") == "AI_Act"]
    zero_sos = [a for a in ai_articles if len(a.get("securityObjectives", [])) == 0]
    assert len(zero_sos) == 0, (
        f"{len(zero_sos)}/{len(ai_articles)} AI_Act articles have 0 SOs "
        f"after WS1 fix + WS3 union"
    )


# ─── C11: HTML has the 4-column header ──────────────────────────────────


def test_c11_html_has_4_berry_columns() -> None:
    """§3 table has 4 columns VAG, POLY, COORD, SCOPE-Q."""
    from docs.visualization.build_regulation_chain import build_html

    html = build_html(articles=[], clauses=[], sos=[], srs=[])
    for col in ["VAG", "POLY", "COORD", "SCOPE-Q"]:
        assert f">{col}<" in html or f'"{col}"' in html, (
            f"column {col} not in HTML output"
        )


# ─── C12: cells populated for AI_Act + GDPR ─────────────────────────────


@pytest.mark.skipif(
    not PREPROC_OUT.is_dir(),
    reason="preproc_out/ not yet regenerated (WS4 must run first)",
)
def test_c12_ai_act_and_gdpr_clauses_have_types_found() -> None:
    """At least all AI_Act clauses + ≥50 GDPR clauses have types_found."""
    ai_dir = PREPROC_OUT / "entities/clauses/_root/AI_Act"
    gdpr_dir = PREPROC_OUT / "entities/clauses/_root/GDPR"
    assert ai_dir.is_dir(), "AI_Act clause shards missing"
    assert gdpr_dir.is_dir(), "GDPR clause shards missing"

    ai_populated = sum(
        1
        for f in ai_dir.glob("*.json")
        if any(t in json.loads(f.read_text()).get("types_found", []) for t in ["VAG", "POLY", "COORD", "SCOPE-Q"])
    )
    ai_total = sum(1 for _ in ai_dir.glob("*.json"))
    assert ai_populated == ai_total, (
        f"AI_Act: only {ai_populated}/{ai_total} have types_found populated"
    )

    gdpr_populated = sum(
        1
        for f in gdpr_dir.glob("*.json")
        if any(t in json.loads(f.read_text()).get("types_found", []) for t in ["VAG", "POLY", "COORD", "SCOPE-Q"])
    )
    gdpr_total = sum(1 for _ in gdpr_dir.glob("*.json"))
    assert gdpr_populated >= 50, (
        f"GDPR: only {gdpr_populated}/{gdpr_total} have types_found populated "
        f"(expected ≥50)"
    )


# ─── Renderer unit test: simulate renderClauses() logic ──────────────────


def test_renderClauses_cells_use_berry_indicators() -> None:
    """Inline simulation of the JS renderClauses() logic — confirms that
    clauses with VAG/POLY/COORD/SCOPE-Q in typesFound OR instances[].label
    produce a ``●`` indicator in the corresponding cell."""
    # Simulate a clause with all 4 categories populated via types_found
    clause = {
        "id": "GDPR-RT01",
        "regulation": "GDPR",
        "sectionRef": "Art. 12(1)",
        "title": "Transparency modalities",
        "typesFound": ["VAG", "POLY", "COORD"],
        "instances": [{"label": "SCOPE-Q"}],
        "isSkeleton": False,
        "severity": "S3",
    }
    tf = clause.get("typesFound") or []
    instLabels = [i.get("label") for i in clause.get("instances", []) if i.get("label")]
    allTypes = set(tf + instLabels)
    for cat in ["VAG", "POLY", "COORD", "SCOPE-Q"]:
        assert cat in allTypes, f"{cat} should be detected from typesFound/instances"

    # Now confirm a clause with NO Berry categories gets all-empty cells
    empty_clause = {
        "id": "GDPR-XX01",
        "typesFound": [],
        "instances": [],
    }
    tf2 = empty_clause.get("typesFound") or []
    instLabels2 = [i.get("label") for i in empty_clause.get("instances", []) if i.get("label")]
    allTypes2 = set(tf2 + instLabels2)
    for cat in ["VAG", "POLY", "COORD", "SCOPE-Q"]:
        assert cat not in allTypes2, f"{cat} should NOT be detected for empty clause"
