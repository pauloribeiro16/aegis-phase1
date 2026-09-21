"""CORR-116 S2.1 regression: GenericMarkdownParser JSON-envelope fallback.

Real failure (JOB 1903560, 2026-09-09): nemotron-3.5-lightning:30b answers
P1B-LLM-02-RATIONALE with a valid JSON envelope (no ``##`` headers). The
GenericMarkdownParser rejected it with "no section headers found in markdown",
which burned 3 blind retries x ~150 s per regulation and killed the 30-min
scout on walltime. P1B-01 already tolerates JSON via its own fallback; this
brings the same tolerance to the generic parser.
"""

from pathlib import Path

import pytest

from aegis_phase1._archive.corr061.markdown_parser import GenericMarkdownParser

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "p1b02"
    / "nemotron_json_attempt1.md"
)


@pytest.fixture
def nemotron_json_raw() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_real_nemotron_json_envelope_parses(nemotron_json_raw: str) -> None:
    """The actual JOB 1903560 response must parse with status OK."""
    output, error = GenericMarkdownParser().parse(nemotron_json_raw)

    assert error == "", f"expected clean parse, got error: {error}"
    assert output is not None
    assert output.status.value == "OK"
    # Content keys become verbatim sections (envelope keys excluded); the
    # real response nests its analysis under "synthesis".
    assert "synthesis" in output.sections, sorted(output.sections)
    assert "GAP-" in output.sections["synthesis"]
    # Envelope keys must not leak into sections
    assert "prompt_spec_id" not in output.sections
    assert "schema_version" not in output.sections


def test_markdown_output_still_parses_normally() -> None:
    """The fallback must not change behaviour for well-formed markdown."""
    raw = "## Status\n- status: OK\n- confidence: HIGH\n\n## Findings\n- nothing"
    output, error = GenericMarkdownParser().parse(raw)

    assert error == ""
    assert output is not None
    assert output.status.value == "OK"
    assert "Findings" in output.sections


def test_non_json_prose_still_fails_cleanly() -> None:
    """Prose without headers and without JSON must keep the original error."""
    output, error = GenericMarkdownParser().parse("just prose, no structure")

    assert output is None
    assert "no section headers" in error


def test_truncated_json_still_fails_cleanly() -> None:
    """A JSON-looking prefix that fails to parse must not crash the parser."""
    output, error = GenericMarkdownParser().parse('{"status": "OK", "trunc')

    assert output is None
    assert "no section headers" in error
