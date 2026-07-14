"""Unit tests for ``doc_04b._section_adapted_objective`` rendering.

Covers all four review statuses (PENDING / APPROVED / EDITED /
REJECTED) and verifies the section text reflects the LLM proposal,
the human rewrite, or the rejection marker accordingly.
"""

from __future__ import annotations

from typing import Any

from aegis_phase1.v2.output.doc_04b import _section_adapted_objective


def _domain_result(
    *,
    objective: str = "LLM proposed text here.",
    key_changes: list[str] | None = None,
    confidence: str = "HIGH",
) -> dict[str, Any]:
    return {
        "domain_id": "D-01",
        "adapted_objective": objective,
        "key_changes": key_changes if key_changes is not None else ["change 1", "change 2"],
        "confidence": confidence,
        "tier": "LIGHTWEIGHT",
        "llm_status": "OK",
    }


def test_section_pending_default() -> None:
    """No review_entry → renders with [PENDING REVIEW] prefix."""
    section = _section_adapted_objective("D-01", _domain_result())
    assert "D-01 — Adapted Objective" in section
    assert "[PENDING REVIEW]" in section
    assert "LLM proposed text here." in section
    assert "change 1" in section
    assert "change 2" in section
    assert "LIGHTWEIGHT" in section
    assert "HIGH" in section


def test_section_pending_explicit() -> None:
    """status=PENDING behaves like the default branch."""
    review = {"status": "PENDING", "edited_text": "", "notes": ""}
    section = _section_adapted_objective("D-01", _domain_result(), review)
    assert "[PENDING REVIEW]" in section
    assert "LLM proposed text here." in section


def test_section_approved() -> None:
    """APPROVED → renders LLM proposal as-is, no [PENDING REVIEW] marker."""
    review = {"status": "APPROVED", "edited_text": "", "notes": ""}
    section = _section_adapted_objective("D-01", _domain_result(), review)
    assert "[PENDING REVIEW]" not in section
    assert "[RE-GENERATION REQUIRED]" not in section
    assert "LLM proposed text here." in section
    assert "APPROVED" in section


def test_section_edited() -> None:
    """EDITED → replaces LLM proposal with edited_text, no PENDING marker."""
    review = {"status": "EDITED", "edited_text": "Human rewritten", "notes": "by CTO"}
    section = _section_adapted_objective("D-01", _domain_result(), review)
    assert "Human rewritten" in section
    assert "LLM proposed text here." not in section
    assert "[PENDING REVIEW]" not in section
    assert "EDITED" in section


def test_section_edited_empty_falls_back() -> None:
    """EDITED with empty edited_text degrades to PENDING (safety net)."""
    review = {"status": "EDITED", "edited_text": "  ", "notes": ""}
    section = _section_adapted_objective("D-01", _domain_result(), review)
    assert "[PENDING REVIEW]" in section
    assert "LLM proposed text here." in section


def test_section_rejected() -> None:
    """REJECTED → LLM proposal prefixed with [RE-GENERATION REQUIRED]."""
    review = {"status": "REJECTED", "edited_text": "", "notes": "regenerate"}
    section = _section_adapted_objective("D-01", _domain_result(), review)
    assert "[RE-GENERATION REQUIRED]" in section
    assert "Bad text" not in section
    assert "LLM proposed text here." in section
    assert "REJECTED" in section


def test_section_empty_objective_still_renders_marker() -> None:
    """Even when LLM produced nothing, the PENDING marker must appear."""
    review = {"status": "PENDING", "edited_text": "", "notes": ""}
    section = _section_adapted_objective(
        "D-01",
        _domain_result(objective="", key_changes=[]),
        review,
    )
    assert "[PENDING REVIEW]" in section
    assert "**Key changes**" not in section


def test_section_handles_missing_review_fields() -> None:
    """A review_entry without explicit keys still parses to a usable status."""
    section = _section_adapted_objective("D-02", _domain_result(), {})
    assert "[PENDING REVIEW]" in section
