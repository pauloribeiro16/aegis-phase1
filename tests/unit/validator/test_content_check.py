"""Tests for ContentValidator (CORR-061 S2)."""
import pytest
from aegis_phase1.validator import ContentValidator, ValidationResult, MIN_CONTENT_CHARS


class TestContentValidatorHappyPath:
    def test_markdown_output_passes(self):
        v = ContentValidator()
        md = "## Status\n- applicable: YES\n- confidence: HIGH\n\n## Rationale\nThis is a test markdown output with more than fifty characters in total."
        result = v.validate(md, spec_id="P1B-LLM-01", case_id="case1")
        assert result.status == "OK"
        assert result.parsed_output == {"raw_response": md}
        assert result.errors == []
        assert result.warnings == []

    def test_long_prose_passes(self):
        v = ContentValidator()
        prose = "This is a long prose response from the model. " * 5
        result = v.validate(prose)
        assert result.status == "OK"
        assert result.parsed_output is not None
        assert result.errors == []


class TestContentValidatorInsufficientEvidence:
    def test_empty_string(self):
        v = ContentValidator()
        result = v.validate("")
        assert result.status == "INSUFFICIENT_EVIDENCE"
        assert result.parsed_output is None
        assert len(result.errors) == 1
        assert "empty" in result.errors[0].lower()

    def test_whitespace_only(self):
        v = ContentValidator()
        result = v.validate("   \n\t  \n  ")
        assert result.status == "INSUFFICIENT_EVIDENCE"
        assert result.parsed_output is None

    def test_below_min_chars(self):
        v = ContentValidator()
        result = v.validate("short")
        assert result.status == "INSUFFICIENT_EVIDENCE"
        assert result.parsed_output is None
        assert "too short" in result.errors[0].lower()

    def test_at_min_chars_boundary(self):
        v = ContentValidator(min_chars=10)
        result = v.validate("a" * 10)
        assert result.status == "OK"

    def test_below_min_chars_boundary(self):
        v = ContentValidator(min_chars=10)
        result = v.validate("a" * 9)
        assert result.status == "INSUFFICIENT_EVIDENCE"


class TestContentValidatorCustomMin:
    def test_custom_min_chars(self):
        v = ContentValidator(min_chars=5)
        assert v.validate("hello").status == "OK"
        assert v.validate("hi").status == "INSUFFICIENT_EVIDENCE"


class TestContentValidatorExports:
    def test_min_content_chars_constant(self):
        assert MIN_CONTENT_CHARS == 50

    def test_validation_result_dataclass(self):
        r = ValidationResult(status="OK", parsed_output={}, errors=[], warnings=[])
        assert r.status == "OK"
        assert r.parsed_output == {}
        assert r.errors == []
        assert r.warnings == []
