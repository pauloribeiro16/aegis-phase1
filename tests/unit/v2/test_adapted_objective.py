"""Unit tests for the adapted_objective wiring layer.

Covers:
    - review.loader path / save+load roundtrip
    - DomainResult TypedDict field contract
    - concatenator() propagation to ``adapted_objectives``
    - doc_04b._section_adapted_objective PENDING/APPROVED/EDITED/REJECTED
"""

from __future__ import annotations

import typing
from pathlib import Path

from aegis_phase1.v2.review.loader import (
    get_review_path,
    load_review,
    save_review,
    seed_review,
)
from aegis_phase1.v2.state import DomainResult

# ─── review.loader ─────────────────────────────────────────────────────


def test_get_review_path() -> None:
    """The review YAML lives at ``<case>/review/adapted_objectives.yaml``."""
    p = get_review_path("cases/case1-tinytask")
    assert p.name == "adapted_objectives.yaml"
    assert p.parent.name == "review"
    assert str(p).endswith("cases/case1-tinytask/review/adapted_objectives.yaml")


def test_load_review_empty(tmp_path: Path) -> None:
    """Missing file → empty dict (no exception, no crash)."""
    review = load_review(str(tmp_path))
    assert review == {}


def test_save_and_load_review(tmp_path: Path) -> None:
    """save_review → load_review is a lossless roundtrip."""
    review = {
        "D-01": {
            "status": "EDITED",
            "llm_proposal": "original text",
            "edited_text": "edited text",
            "notes": "human note",
        }
    }
    save_review(str(tmp_path), review)
    loaded = load_review(str(tmp_path))
    assert loaded == review


def test_seed_review_creates_pending_entries(tmp_path: Path) -> None:
    """seed_review adds PENDING entries for domains, preserves human edits."""
    results = {
        "D-01": {"adapted_objective": "obj A", "confidence": "HIGH"},
        "D-02": {"adapted_objective": "obj B", "confidence": "MEDIUM"},
    }
    seeded = seed_review(str(tmp_path), results)
    assert set(seeded.keys()) == {"D-01", "D-02"}
    for did in seeded:
        assert seeded[did]["status"] == "PENDING"
        assert seeded[did]["llm_proposal"] in {"obj A", "obj B"}
        assert seeded[did]["edited_text"] == ""
        assert seeded[did]["notes"] == ""

    p = get_review_path(str(tmp_path))
    assert p.exists()


def test_seed_review_preserves_existing_entries(tmp_path: Path) -> None:
    """Re-seeding must NOT clobber an EDITED entry."""
    save_review(
        str(tmp_path),
        {
            "D-01": {
                "status": "EDITED",
                "llm_proposal": "orig",
                "edited_text": "rewritten",
                "notes": "approved by CTO",
            },
            "D-02": {"status": "APPROVED", "llm_proposal": "x", "edited_text": "", "notes": ""},
        },
    )
    seed_review(
        str(tmp_path),
        {"D-01": {"adapted_objective": "fresh"}, "D-02": {"adapted_objective": "fresh"}},
    )
    reloaded = load_review(str(tmp_path))
    assert reloaded["D-01"]["edited_text"] == "rewritten"
    assert reloaded["D-01"]["status"] == "EDITED"
    assert reloaded["D-02"]["status"] == "APPROVED"


def test_review_path_under_case() -> None:
    """Path resolves under the case directory, not anywhere global."""
    p = get_review_path("/some/other/case")
    assert p.parts[-3] == "case"
    assert p.parts[-2] == "review"
    assert p.parts[-1] == "adapted_objectives.yaml"


# ─── DomainResult TypedDict contract ──────────────────────────────────


def test_domain_result_has_adapted_objective() -> None:
    """DomainResult TypedDict exposes ``adapted_objective`` (not ``adapted_text``)."""
    hints = typing.get_type_hints(DomainResult)
    assert "adapted_objective" in hints
    assert "key_changes" in hints
    assert "confidence" in hints
    assert "domain_id" in hints
    assert "domain_name" in hints
    assert "subdomains" in hints
    assert "coverage" in hints
    assert "cross_regulation" in hints
    assert "llm_status" in hints


# ─── concatenator propagation ──────────────────────────────────────────


def test_concatenate_propagates_adapted_objectives() -> None:
    """concatenate() returns an ``adapted_objectives`` per-domain view."""
    from aegis_phase1.v2.reduce.concatenator import concatenate

    state = {
        "domain_results": {
            "D-01": {
                "domain_id": "D-01",
                "domain_name": "Data Protection",
                "subdomains": [],
                "coverage": "SUBSTANTIVE",
                "cross_regulation": [],
                "llm_status": "OK",
                "adapted_objective": "Tailored objective for D-01.",
                "key_changes": ["delta 1", "delta 2"],
                "confidence": "HIGH",
            },
            "D-02": {
                "domain_id": "D-02",
                "domain_name": "Vulnerability Mgmt",
                "subdomains": [],
                "coverage": "PARTIAL",
                "cross_regulation": [],
                "llm_status": "FAILED",
                "adapted_objective": "",
                "key_changes": [],
                "confidence": "LOW",
            },
        },
    }
    out = concatenate(state)
    assert "adapted_objectives" in out
    assert "subdomains" in out
    assert set(out["adapted_objectives"].keys()) == {"D-01", "D-02"}
    d01 = out["adapted_objectives"]["D-01"]
    assert d01["adapted_objective"] == "Tailored objective for D-01."
    assert d01["key_changes"] == ["delta 1", "delta 2"]
    assert d01["confidence"] == "HIGH"
    assert d01["llm_status"] == "OK"
    assert d01["domain_name"] == "Data Protection"
    d02 = out["adapted_objectives"]["D-02"]
    assert d02["adapted_objective"] == ""
    assert d02["key_changes"] == []
    assert d02["confidence"] == "LOW"
    assert d02["llm_status"] == "FAILED"
