"""Tests for OBJ-05 proportionality adequacy cell (CORR-OBJ-05).

OBJECTIVES_CONTRACT §2.1 — OBJ-05 [G+J] mechanism. The deterministic half ([G])
lives in REDUCE / Doc 04b dynamic maturity (CORR-109); the judge half ([J])
lives in ``scripts/eval/rubric.py:obj05_proportionality_adequacy``.

What we verify here:

1. The cell returns a :class:`ScorecardCell` with the 5-layer verbose
   criteria shape (what/how/measured/why/score) per OBJECTIVES_CONTRACT §5.2
   ("bare PASS/FAIL is unacceptable").
2. The proportionality score reflects narrative depth: a MICRO/LOW case
   with 200-word paragraphs scores lower than a MAX/HIGH case with the same
   narrative.
3. Invalid ``scale`` or ``complexity_tier`` values produce a 1-score cell
   with a clear ``why`` explaining the failure.
4. The ``evaluate_obj05`` end-to-end entry point correctly reads Enterprise
   context from ``state.json`` and the rendered Doc 04.
5. The ``read_enterprise_context`` helper finds Enterprise context in the
   state.json ``v2_company_context`` shape.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.eval.rubric import (
    PROPORTIONALITY_BOUNDS,
    SCORECARD_LAYERS,
    ScorecardCell,
    _count_words,
    _proportionality_score,
    _split_subdomain_sections,
    evaluate_obj05,
    obj05_proportionality_adequacy,
    read_enterprise_context,
)

# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────


def _make_doc_04(subdomain_paragraphs: dict[str, int]) -> str:
    """Build a synthetic Doc 04 with one paragraph per subdomain id.

    ``subdomain_paragraphs`` maps ``D-XX.Y`` -> number of words to emit. The
    generated text uses the canonical ``### D-XX.Y`` header so the
    ``_split_subdomain_sections`` helper will pick it up.
    """
    lines = [
        "---",
        "document_id: AEGIS-P1-04",
        "title: Company Context Assessment",
        "---",
        "",
        "# Company Context Assessment",
        "",
    ]
    for sub_id, n_words in subdomain_paragraphs.items():
        lines.append(f"### {sub_id} Subdomain")
        lines.append(" ".join(["word"] * n_words))
        lines.append("")
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
# 1. 5-layer verbose criteria shape
# ────────────────────────────────────────────────────────────────────


def test_scorecard_has_five_layers():
    """OBJECTIVES_CONTRACT §5.2: 5-layer verbose criteria, not bare PASS/FAIL."""
    cell = obj05_proportionality_adequacy(
        doc_04_text=_make_doc_04({"D-01.1": 50}),
        scale="MICRO",
        complexity_tier="LOW",
    )
    assert isinstance(cell, ScorecardCell)
    for layer in SCORECARD_LAYERS:
        assert hasattr(cell, layer), f"missing layer {layer!r}"
        assert getattr(cell, layer) != "", f"layer {layer!r} must be non-empty"
    # All five layers populated as strings (score is the int 1-5)
    assert isinstance(cell.what, str) and cell.what
    assert isinstance(cell.how, str) and cell.how
    assert isinstance(cell.measured, str) and cell.measured
    assert isinstance(cell.why, str) and cell.why
    assert isinstance(cell.score, int) and 1 <= cell.score <= 5


def test_scorecard_dict_round_trip():
    """to_dict() must include all 5 layers + evidence."""
    cell = obj05_proportionality_adequacy(
        doc_04_text=_make_doc_04({"D-04.1": 80}),
        scale="SMALL",
        complexity_tier="MEDIUM",
    )
    d = cell.to_dict()
    for k in ("objective_id", "cell", "what", "how", "measured", "why", "score", "evidence"):
        assert k in d
    assert d["objective_id"] == "OBJ-05"
    assert d["cell"] == "proportionality_adequacy"
    assert d["score"] == cell.score
    assert isinstance(d["evidence"], dict)


# ────────────────────────────────────────────────────────────────────
# 2. Proportionality scoring reflects narrative depth
# ────────────────────────────────────────────────────────────────────


def test_micro_low_with_long_paragraphs_scores_low():
    """A MICRO/LOW case with 200-word paragraphs is OVER-scaled → score 1-2."""
    cell = obj05_proportionality_adequacy(
        doc_04_text=_make_doc_04({"D-01.1": 200, "D-01.2": 200, "D-01.3": 200}),
        scale="MICRO",
        complexity_tier="LOW",
    )
    # MICRO/LOW expects 20-80 words. Three 200-word sections are over by 2.5x.
    assert cell.score <= 2, f"expected over-scaled score <= 2, got {cell.score}"


def test_max_high_with_long_narrative_scores_high():
    """A MAX/HIGH case with deep narratives (>200 words) is proportional → score 5."""
    cell = obj05_proportionality_adequacy(
        doc_04_text=_make_doc_04({"D-04.1": 300, "D-04.2": 400, "D-04.3": 500}),
        scale="MAX",
        complexity_tier="HIGH",
    )
    # MAX/HIGH expects 220-800. All in range.
    assert cell.score == 5, f"expected score 5 for MAX/HIGH deep narrative, got {cell.score}"


def test_medium_medium_at_lower_bound_scores_well():
    """A MEDIUM/MEDIUM case at the lower end of the range is acceptable."""
    cell = obj05_proportionality_adequacy(
        doc_04_text=_make_doc_04({"D-02.1": 100, "D-02.2": 100, "D-02.3": 100}),
        scale="MEDIUM",
        complexity_tier="MEDIUM",
    )
    # MEDIUM/MEDIUM expects 90-300 words. 100 is in range.
    assert cell.score >= 4, f"expected score >= 4 for in-range MEDIUM/MEDIUM, got {cell.score}"


def test_high_tier_with_stub_scores_low():
    """A MAX/HIGH case with 30-word stubs is UNDER-scaled → score 1-2."""
    cell = obj05_proportionality_adequacy(
        doc_04_text=_make_doc_04({"D-09.1": 30, "D-09.2": 30, "D-09.3": 30}),
        scale="MAX",
        complexity_tier="HIGH",
    )
    # MAX/HIGH expects 220-800. Three 30-word stubs are grossly under.
    assert cell.score <= 2, f"expected under-scaled score <= 2, got {cell.score}"


def test_empty_doc_returns_lowest_score():
    """No subdomains observed → score 1 with explanatory evidence."""
    cell = obj05_proportionality_adequacy(
        doc_04_text="# Empty Doc\n\nNo subdomains here.\n",
        scale="MICRO",
        complexity_tier="LOW",
    )
    assert cell.score == 1
    # The "no subdomains" branch records the reason in evidence.
    assert "no subdomains" in cell.evidence.get("reason", "").lower()


# ────────────────────────────────────────────────────────────────────
# 3. Invalid tier inputs
# ────────────────────────────────────────────────────────────────────


def test_invalid_scale_returns_score_one():
    cell = obj05_proportionality_adequacy(
        doc_04_text=_make_doc_04({"D-01.1": 50}),
        scale="WRONG",
        complexity_tier="LOW",
    )
    assert cell.score == 1
    assert "INVALID scale" in cell.measured
    assert "Scale must be one of" in cell.why


def test_invalid_complexity_tier_returns_score_one():
    cell = obj05_proportionality_adequacy(
        doc_04_text=_make_doc_04({"D-01.1": 50}),
        scale="MICRO",
        complexity_tier="MEGA",
    )
    assert cell.score == 1
    assert "INVALID complexity_tier" in cell.measured
    assert "complexity_tier must be one of" in cell.why


# ────────────────────────────────────────────────────────────────────
# 4. End-to-end evaluate_obj05
# ────────────────────────────────────────────────────────────────────


def test_evaluate_obj05_reads_state_and_doc04(tmp_path: Path):
    """End-to-end: state.json + Doc 04 in run_dir → ScorecardCell."""
    # Write a state.json with Enterprise context
    state = {
        "case_id": "case1-tinytask",
        "v2_company_context": {
            "scale": "MICRO",
            "complexity_tier": "LOW",
            "company_name": "TinyTask",
        },
    }
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "state.json").write_text(json.dumps(state), encoding="utf-8")

    # Write a Doc 04 with proportional narrative
    doc04 = _make_doc_04({"D-01.1": 40, "D-01.2": 50, "D-01.3": 60})
    (tmp_path / "04_Company_Context_Assessment.md").write_text(doc04, encoding="utf-8")

    cell = evaluate_obj05(tmp_path)
    assert cell.objective_id == "OBJ-05"
    assert cell.evidence["case_id"] == "case1-tinytask"
    assert cell.evidence["scale"] == "MICRO"
    assert cell.evidence["complexity_tier"] == "LOW"
    # MICRO/LOW expects 20-80 words. All 3 sections in range.
    assert cell.score == 5


def test_evaluate_obj05_missing_doc04_returns_one(tmp_path: Path):
    """No Doc 04 → score 1 with 'not found' reason (not a crash)."""
    state = {"case_id": "x", "v2_company_context": {"scale": "SMALL", "complexity_tier": "MEDIUM"}}
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    cell = evaluate_obj05(tmp_path)
    assert cell.score == 1
    assert "not found" in cell.measured.lower()


# ────────────────────────────────────────────────────────────────────
# 5. read_enterprise_context
# ────────────────────────────────────────────────────────────────────


def test_read_enterprise_context_from_v2_company_context(tmp_path: Path):
    (tmp_path / "work").mkdir()
    state = {
        "case_id": "case3-omnibank",
        "v2_company_context": {"scale": "MAX", "complexity_tier": "HIGH"},
    }
    (tmp_path / "work" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    ctx = read_enterprise_context(tmp_path)
    assert ctx == {
        "scale": "MAX",
        "complexity_tier": "HIGH",
        "case_id": "case3-omnibank",
    }


def test_read_enterprise_context_falls_back_to_top_level_enterprise(tmp_path: Path):
    (tmp_path / "work").mkdir()
    state = {
        "case_id": "case2",
        "Enterprise": {"scale": "MEDIUM", "complexity_tier": "MEDIUM"},
    }
    (tmp_path / "work" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    ctx = read_enterprise_context(tmp_path)
    assert ctx["scale"] == "MEDIUM"
    assert ctx["complexity_tier"] == "MEDIUM"


def test_read_enterprise_context_uses_state_json_path(tmp_path: Path):
    state = {
        "case_id": "x",
        "v2_company_context": {"scale": "LARGE", "complexity_tier": "HIGH"},
    }
    state_path = tmp_path / "alt_state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    ctx = read_enterprise_context(tmp_path, state_json_path=state_path)
    assert ctx["scale"] == "LARGE"
    assert ctx["complexity_tier"] == "HIGH"


def test_read_enterprise_context_missing_returns_unknown(tmp_path: Path):
    """No state.json at all → scale/complexity_tier = UNKNOWN, case_id = unknown."""
    ctx = read_enterprise_context(tmp_path)
    assert ctx["scale"] == "UNKNOWN"
    assert ctx["complexity_tier"] == "UNKNOWN"
    assert ctx["case_id"] == "unknown"


# ────────────────────────────────────────────────────────────────────
# 6. Internal helpers
# ────────────────────────────────────────────────────────────────────


def test_count_words_simple():
    assert _count_words("hello world") == 2
    assert _count_words("") == 0
    assert _count_words("  multiple   spaces   here  ") == 3


def test_split_subdomain_sections_recognises_h2_to_h4():
    """Helper must accept ### and #### headers; ignore non-D-XX.Y headers."""
    text = (
        "# Top heading\n"
        "## 1. Stakeholders\n"
        "This is stakeholders section.\n"
        "### D-01.1 Subdomain One\n"
        "Body of D-01.1.\n"
        "### D-01.2 Subdomain Two\n"
        "Body of D-01.2.\n"
        "#### D-04.1 Nested subdomain\n"
        "Body of D-04.1.\n"
    )
    sections = _split_subdomain_sections(text)
    ids = [sid for sid, _ in sections]
    assert ids == ["D-01.1", "D-01.2", "D-04.1"]


def test_proportionality_bounds_table_complete():
    """Sanity: every (VALID_SCALE, VALID_COMPLEXITY_TIER) combo is mapped."""
    from scripts.eval.rubric import VALID_COMPLEXITY_TIERS, VALID_SCALES
    for scale in VALID_SCALES:
        for tier in VALID_COMPLEXITY_TIERS:
            assert (scale, tier) in PROPORTIONALITY_BOUNDS, (
                f"missing bound for ({scale}, {tier})"
            )


def test_proportionality_bounds_higher_tiers_have_higher_min():
    """For a given complexity_tier, higher scale ⇒ higher min words."""
    for tier in ("LOW", "MEDIUM", "HIGH"):
        mins = [PROPORTIONALITY_BOUNDS[(s, tier)][0] for s in ("MICRO", "SMALL", "MEDIUM", "LARGE", "MAX")]
        assert mins == sorted(mins), f"min words not monotonic for tier={tier}: {mins}"


def test_proportionality_score_no_word_counts_returns_one():
    """Empty word-counts list → score 1."""
    score, evidence = _proportionality_score("MICRO", "LOW", [])
    assert score == 1
    assert "no subdomains" in evidence["reason"]
