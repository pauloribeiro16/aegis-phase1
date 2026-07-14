"""Tests for OutputParser (v2/domain/parser.py).

Covers the happy path, every error path, and feedback generation for
retry. Regex edge cases (trailing whitespace, code fences, lowercase
confidence) are also exercised.
"""

from __future__ import annotations

import pytest

from aegis_phase1.v2.domain.parser import OutputParser, ParseResult


@pytest.fixture
def parser() -> OutputParser:
    return OutputParser()


# ─── Happy path ────────────────────────────────────────────────────────


def test_parses_well_formed_output(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: This is the adapted objective spanning\n"
        "three sentences for the domain. It references the company reality.\n"
        "It is bounded by proportionality.\n"
        "KEY_ADJUSTMENTS:\n"
        "- added explicit incident classification\n"
        "- tightened 24h notification target\n"
        "- excluded redundant sub-domain\n"
        "CONFIDENCE: HIGH"
    )

    result = parser.parse(raw)
    assert result.success is True
    assert "adapted objective" in result.adapted_objective.lower()
    assert len(result.key_adjustments) == 3
    assert result.confidence == "HIGH"
    assert result.error_feedback == ""


def test_parses_multiline_adapted_objective(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: First sentence.\n"
        "Second sentence.\n"
        "KEY_ADJUSTMENTS:\n"
        "- adj 1\n"
        "- adj 2\n"
        "CONFIDENCE: MEDIUM"
    )

    result = parser.parse(raw)
    assert result.success is True
    assert "First sentence." in result.adapted_objective
    assert "Second sentence." in result.adapted_objective
    assert result.confidence == "MEDIUM"


def test_parses_lowercase_confidence(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: Objective text.\n"
        "KEY_ADJUSTMENTS:\n"
        "- one\n"
        "CONFIDENCE: low"
    )

    result = parser.parse(raw)
    assert result.success is True
    assert result.confidence == "LOW"


def test_parses_with_code_fences(parser: OutputParser) -> None:
    raw = (
        "```\n"
        "ADAPTED_OBJECTIVE: Objective.\n"
        "KEY_ADJUSTMENTS:\n"
        "- one\n"
        "CONFIDENCE: HIGH\n"
        "```"
    )

    result = parser.parse(raw)
    assert result.success is True
    assert result.confidence == "HIGH"
    assert len(result.key_adjustments) == 1


def test_parses_strips_bullet_punctuation_and_quotes(parser: OutputParser) -> None:
    raw = (
        'ADAPTED_OBJECTIVE: obj.\n'
        'KEY_ADJUSTMENTS:\n'
        '-  "quoted adjustment"\n'
        "- 'another'\n"
        "CONFIDENCE: HIGH"
    )

    result = parser.parse(raw)
    assert result.success
    assert result.key_adjustments == ["quoted adjustment", "another"]


def test_parses_five_adjustments(parser: OutputParser) -> None:
    bullets = "\n".join(f"- adj {i}" for i in range(1, 6))
    raw = (
        "ADAPTED_OBJECTIVE: obj.\n"
        f"KEY_ADJUSTMENTS:\n{bullets}\n"
        "CONFIDENCE: HIGH"
    )

    result = parser.parse(raw)
    assert result.success
    assert len(result.key_adjustments) == 5


# ─── Error paths ───────────────────────────────────────────────────────


def test_missing_adapted_objective_feedback(parser: OutputParser) -> None:
    raw = "KEY_ADJUSTMENTS:\n- one\nCONFIDENCE: HIGH"
    result = parser.parse(raw)
    assert result.success is False
    assert "ADAPTED_OBJECTIVE" in result.error_feedback
    assert result.adapted_objective == ""


def test_missing_adjustments_feedback(parser: OutputParser) -> None:
    raw = "ADAPTED_OBJECTIVE: Some objective text.\nCONFIDENCE: HIGH"
    result = parser.parse(raw)
    assert result.success is False
    assert "KEY_ADJUSTMENTS" in result.error_feedback
    assert result.key_adjustments == []


def test_missing_confidence_defaults_to_low_with_feedback(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: Objective.\n"
        "KEY_ADJUSTMENTS:\n- one\n"
        "CONFIDENCE: BOGUS"
    )
    result = parser.parse(raw)
    assert result.success is False
    assert result.confidence == "LOW"
    assert "CONFIDENCE" in result.error_feedback


def test_missing_all_sections(parser: OutputParser) -> None:
    raw = "no format here"
    result = parser.parse(raw)
    assert result.success is False
    assert "ADAPTED_OBJECTIVE" in result.error_feedback
    assert "KEY_ADJUSTMENTS" in result.error_feedback
    assert "CONFIDENCE" in result.error_feedback


def test_empty_string_returns_failure(parser: OutputParser) -> None:
    result = parser.parse("")
    assert result.success is False
    assert result.error_feedback


def test_none_input_returns_clean_failure(parser: OutputParser) -> None:
    result = parser.parse(None)  # type: ignore[arg-type]
    assert result.success is False
    assert "Empty" in result.error_feedback


def test_adjustments_without_dash_prefix(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: obj.\n"
        "KEY_ADJUSTMENTS:\n"
        "first item\n"
        "second item\n"
        "CONFIDENCE: HIGH"
    )
    result = parser.parse(raw)
    assert result.success is False
    assert "KEY_ADJUSTMENTS" in result.error_feedback


def test_parse_result_is_immutable_namedtuple() -> None:
    """ParseResult is a NamedTuple — verifying the contract."""
    r = ParseResult(
        success=True,
        adapted_objective="x",
        key_adjustments=["a"],
        confidence="HIGH",
        error_feedback="",
    )
    assert r.success is True
    assert r.adapted_objective == "x"
    assert r.key_adjustments == ["a"]
    assert r.confidence == "HIGH"
    assert r.error_feedback == ""
    # NamedTuples are iterable for backwards compat
    assert tuple(r) == (True, "x", ["a"], "HIGH", "")


# ─── Retry-feedback round-trip ─────────────────────────────────────────


def test_parser_feedback_is_suitable_for_retry_prompt(parser: OutputParser) -> None:
    """The feedback string is non-empty and references actionable keywords
    so the orchestrator can pass it to render_prompt(feedback=...)."""
    raw = "garbage"
    result = parser.parse(raw)
    assert result.success is False
    assert result.error_feedback
    # Must contain at least one of the section names so the LLM can fix it.
    lowered = result.error_feedback.lower()
    assert any(
        keyword in lowered
        for keyword in ("adapted_objective", "key_adjustments", "confidence")
    )
