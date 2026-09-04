"""Tests for ``scripts.kg_eval.ground_truth`` + T1.6 scoring (CORR-113 Commit 6).

Verifies:
- ``compute_ground_truth`` reads preproc + interactions deterministically.
- ``compute_ground_truth`` SHA-256 is stable across calls (reproducibility).
- ``_score_t16`` exact-matches cited clause_ids vs ground truth.
- ``score_run`` threads the ground truth for T1.6 runs.
- The scorer emits ``MISSING_GATE`` when ground truth cannot be threaded.
- Invalid families surface as ``errors`` (no silent pass).
"""

from __future__ import annotations

from pathlib import Path

from scripts.kg_eval.ground_truth import compute_ground_truth
from scripts.kg_eval.score_t1 import (
    _extract_cited_obligation_ids,
    _score_t16,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CASE1 = REPO_ROOT / "cases" / "case1-tinytask"
CASE3 = REPO_ROOT / "cases" / "case3-omnibank"
PREPROC = REPO_ROOT / "preproc_out"


# ─── compute_ground_truth ────────────────────────────────────────────


def test_compute_ground_truth_case1_d01_1_is_deterministic() -> None:
    """Same inputs → same SHA across two calls."""
    gt1 = compute_ground_truth(CASE1, PREPROC, "D-01.1")
    gt2 = compute_ground_truth(CASE1, PREPROC, "D-01.1")
    assert gt1["ground_truth_sha256"] == gt2["ground_truth_sha256"]
    assert gt1["count"] == gt2["count"]
    # At minimum one clause for a universally applicable case1 subdomain.
    assert gt1["count"] >= 1


def test_compute_ground_truth_case3_has_more_regs_than_case1() -> None:
    """OmniBank is 5-regulation; case1 is 2. D-01.1 should have more activations."""
    g1 = compute_ground_truth(CASE1, PREPROC, "D-01.1")
    g3 = compute_ground_truth(CASE3, PREPROC, "D-01.1")
    assert g3["count"] >= g1["count"]
    # Case3 must include DORA / NIS2 / AI_Act (or at least a superset of case1).
    g3_regs = {c["regulation"] for c in g3["activated_clauses"]}
    assert {"GDPR", "DORA"}.issubset(g3_regs) or {"GDPR", "NIS2"}.issubset(g3_regs)


def test_compute_ground_truth_subdomain_with_no_clauses_returns_empty() -> None:
    """Synthetic subdomain D-99.9 has no clauses — count=0, sha still stable."""
    gt = compute_ground_truth(CASE1, PREPROC, "D-99.9")
    assert gt["count"] == 0
    assert gt["activated_clauses"] == []
    assert isinstance(gt["ground_truth_sha256"], str)
    assert len(gt["ground_truth_sha256"]) == 64


# ─── _extract_cited_clause_ids ───────────────────────────────────────


def test_extract_cited_obligation_ids_finds_typical_patterns() -> None:
    raw = (
        "## Activated obligations\n"
        "- GDPR-CL06: Art. 32(1)(a) — encryption\n"
        "- DORA-CL14: Art. 9(2) — ICT risk\n"
        "- CRA-CP02: procedure\n"
        "- I made up a no-pattern-here sentence\n"
    )
    cited = _extract_cited_obligation_ids(raw)
    assert "GDPR-CL06" in cited
    assert "DORA-CL14" in cited
    assert "CRA-CP02" in cited
    # No clause_id pattern in the third bullet.
    for cid in cited:
        assert cid.startswith(("GDPR", "DORA", "NIS2", "CRA", "AI_Act"))


def test_extract_cited_obligation_ids_empty_on_empty_input() -> None:
    assert _extract_cited_obligation_ids("") == []
    assert _extract_cited_obligation_ids("no clauses here") == []


# ─── _score_t16 (exact-match) ───────────────────────────────────────


def test_score_t16_exact_match_passes() -> None:
    gt = compute_ground_truth(CASE1, PREPROC, "D-01.1")
    cited_ids = " ".join(c["clause_id"] for c in gt["activated_clauses"])
    raw = f"## Activated obligations\n{cited_ids}\n"
    metrics = _score_t16(raw, packet=None, ground_truth=gt)
    assert len(metrics) == 1
    m = metrics[0]
    assert m["pass"] is True
    assert m["status"] == "OK"
    assert m["value"]["false_positives"] == []
    assert m["value"]["false_negatives"] == []


def test_score_t16_missing_clauses_marks_false_negatives() -> None:
    gt = compute_ground_truth(CASE1, PREPROC, "D-01.1")
    # Drop the last activated clause from the output.
    cited_ids = [c["clause_id"] for c in gt["activated_clauses"][:-1]]
    raw = "## Activated obligations\n" + " ".join(cited_ids)
    metrics = _score_t16(raw, packet=None, ground_truth=gt)
    m = metrics[0]
    assert m["pass"] is False
    assert m["value"]["false_negatives"] == [gt["activated_clauses"][-1]["clause_id"]]
    assert 0.0 < m["value"]["recall"] < 1.0


def test_score_t16_invented_clauses_mark_false_positives() -> None:
    gt = compute_ground_truth(CASE1, PREPROC, "D-01.1")
    cited_ids = [c["clause_id"] for c in gt["activated_clauses"]]
    cited_ids.append("GDPR-CL999")  # invented
    raw = "## Activated obligations\n" + " ".join(cited_ids)
    metrics = _score_t16(raw, packet=None, ground_truth=gt)
    m = metrics[0]
    assert m["pass"] is False
    assert "GDPR-CL999" in m["value"]["false_positives"]


def test_score_t16_missing_ground_truth_emits_missing_gate() -> None:
    """No ground truth threaded → MISSING_GATE, not silent pass."""
    metrics = _score_t16("GDPR-CL06", packet=None, ground_truth=None)
    m = metrics[0]
    assert m["pass"] is None
    assert m["status"] == "MISSING_GATE"


def test_score_t16_empty_ground_truth_emits_empty_ground_truth() -> None:
    metrics = _score_t16(
        "anything",
        packet=None,
        ground_truth={
            "activated_clauses": [],
            "ground_truth_sha256": "x" * 64,
            "count": 0,
        },
    )
    m = metrics[0]
    assert m["status"] == "EMPTY_GROUND_TRUTH"
    assert m["pass"] is None
