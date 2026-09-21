"""CORR-116 S1 — unit tests for the parser replay harness.

Drives :mod:`scripts.eval.parser_replay` on a tmpdir tree of synthetic
raw responses, in AAA style. Each scenario proves the classification
branch the S1 contract cares about:

  - OK P1B-01              → parse_ok
  - missing-Status P1B-01  → parse_fail / no_status_section
  - OK Generic (P1C-02)    → parse_ok
  - empty body             → empty_body / empty_body class

These four scenarios cover the three branches of ``replay_one`` plus
the ``empty_body`` fast-path, which is the same fast-path that lets
the corpus-wide C1/C2/C3 runs recognise the Ollama-down raws
(``raw_response_preview: ""``) without crashing the harness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.eval import parser_replay

# ── Synthetic raw fixtures (AAA: arrange once, reuse via tmp_path) ──────


def _write_raw(
    base: Path, spec: str, name: str, fm: dict[str, str], body: str
) -> Path:
    """Write a single ``*.md`` file with the canonical frontmatter + body shape."""
    spec_dir = base / spec
    spec_dir.mkdir(parents=True, exist_ok=True)
    path = spec_dir / name
    fm_lines = "\n".join(f"{k}: {v}" for k, v in fm.items())
    path.write_text(
        f"---\n{fm_lines}\n---\n\n## Raw response\n\n{body}\n",
        encoding="utf-8",
    )
    return path


OK_P1B01_BODY = """\
## Status
- applicable: YES
- confidence: HIGH

## Interpretations

### INT-1
- entry_id: TIPO2-GDPR-RTS-DEADLINES
- applicable: YES
- activation_rationale: company processes EU personal data
- layer0_refs: [SubDomains/D-01.1.md]
- legal_refs: [GDPR Art. 33]
- company_fact_refs: [DOC04:ARCH-07]

## Derogations

### DER-1
- entry_id: TIPO3-GDPR-HOUSEHOLD
- activation_verdict: NOT_ACTIVATED
- activation_rationale: SaaS, not household
- layer0_refs: [SubDomains/D-01.1.md]
- legal_refs: [GDPR Art. 2(2)(c)]
- company_fact_refs: [DOC04:ARCH-07]

## Rationale
Company is a SaaS data controller for admin data and a processor for
customer data; the household-activity derogation does not apply.
"""

MISSING_STATUS_P1B01_BODY = """\
## Interpretations

### INT-1
- entry_id: TIPO2-GDPR-RTS-DEADLINES
- applicable: YES
- activation_rationale: short

## Derogations

### DER-1
- entry_id: TIPO3-GDPR-HOUSEHOLD
- activation_verdict: NOT_ACTIVATED
- activation_rationale: short
"""

OK_GENERIC_BODY = """\
## Status
- applicable: YES
- confidence: HIGH

## Findings
- The compound event D-01.1 ↔ D-02.2 is triggered when both are
  applicable and the company processes EU personal data.
"""

EMPTY_BODY = ""


@pytest.fixture
def synthetic_raws(tmp_path: Path) -> dict[str, Path]:
    """Arrange: 4 synthetic raws in their canonical spec dirs."""
    return {
        "ok_p1b01": _write_raw(
            tmp_path,
            "P1B-LLM-01-INTERPRETATION",
            "2026-09-09T00-00-00__attempt1.md",
            {"spec_id": "P1B-LLM-01-INTERPRETATION", "attempt": "1",
             "model": "minimax-mock", "status": "OK"},
            OK_P1B01_BODY,
        ),
        "missing_status_p1b01": _write_raw(
            tmp_path,
            "P1B-LLM-01-INTERPRETATION",
            "2026-09-09T00-01-00__attempt1.md",
            {"spec_id": "P1B-LLM-01-INTERPRETATION", "attempt": "1",
             "model": "minimax-mock", "status": "SCHEMA_ERROR"},
            MISSING_STATUS_P1B01_BODY,
        ),
        "ok_generic": _write_raw(
            tmp_path,
            "P1C-LLM-02-COMPOUND-EVENT",
            "2026-09-09T00-02-00__attempt1.md",
            {"spec_id": "P1C-LLM-02-COMPOUND-EVENT", "attempt": "1",
             "model": "minimax-mock", "status": "OK"},
            OK_GENERIC_BODY,
        ),
        "empty_body": _write_raw(
            tmp_path,
            "P1B-LLM-02-RATIONALE",
            "2026-09-09T00-03-00__attempt1.md",
            {"spec_id": "P1B-LLM-02-RATIONALE", "attempt": "1",
             "model": "minimax-mock", "status": "PYTHON_ERROR"},
            EMPTY_BODY,
        ),
    }


# ── Tests ──────────────────────────────────────────────────────────────


def test_classify_error_branches() -> None:
    """Pure function: error → class."""
    # Act + Assert
    assert parser_replay.classify_error("") == "empty_body"
    assert parser_replay.classify_error(
        "markdown parsing failed: no status section found"
    ) in {"no_status_section", "no_headers"}
    assert parser_replay.classify_error(
        "no `## Section` headers found in markdown"
    ) == "no_headers"
    assert parser_replay.classify_error(
        "INT-1 entry missing activation_rationale"
    ) == "missing_int"
    assert parser_replay.classify_error("completely unknown failure") == "other"


def test_parse_frontmatter_basic() -> None:
    text = "---\nspec_id: P1B-LLM-01-INTERPRETATION\nattempt: 2\n---\nbody"
    assert parser_replay.parse_frontmatter(text) == {
        "spec_id": "P1B-LLM-01-INTERPRETATION",
        "attempt": "2",
    }


def test_extract_raw_body_strips_header() -> None:
    text = "frontmatter\n\n## Raw response\n\nactual body"
    assert parser_replay.extract_raw_body(text) == "actual body"


def test_replay_ok_p1b01(synthetic_raws: dict[str, Path]) -> None:
    """Act: parse a well-formed P1B-01 raw → assert parse_ok."""
    from aegis_phase1._archive.corr061.markdown_parser import P1BLLM01Parser

    text = synthetic_raws["ok_p1b01"].read_text(encoding="utf-8")
    body = parser_replay.extract_raw_body(text)

    outcome, error_class, _ = parser_replay.replay_one(
        "P1B-LLM-01-INTERPRETATION", P1BLLM01Parser, body, gate=None,
    )

    assert outcome == "parse_ok"
    assert error_class == ""


def test_replay_missing_status_p1b01(synthetic_raws: dict[str, Path]) -> None:
    """Act: parse a P1B-01 raw missing ## Status → assert classified.

    The P1B-01 parser emits a generic fallback error string when
    markdown extraction fails (CORR-053), so the body-aware
    classifier in ``analyse_corpus`` is what actually tags this case
    as ``no_status_section``. The test exercises both code paths:

      - ``replay_one`` alone returns ``"other"`` (because the parser
        error string contains no signature tokens)
      - ``analyse_corpus`` body-aware escalation returns
        ``"no_status_section"``
    """
    from aegis_phase1._archive.corr061.markdown_parser import P1BLLM01Parser

    text = synthetic_raws["missing_status_p1b01"].read_text(encoding="utf-8")
    body = parser_replay.extract_raw_body(text)

    # Direct call: parse_fail with generic class.
    outcome, error_class, err = parser_replay.replay_one(
        "P1B-LLM-01-INTERPRETATION", P1BLLM01Parser, body, gate=None,
    )
    assert outcome == "parse_fail"
    assert err  # non-empty error string

    # Body-aware escalation: tags as no_status_section because the body
    # is missing the Status section (this is what the full matrix uses).
    escalated = parser_replay.classify_error_with_body(
        "P1B-LLM-01-INTERPRETATION", err, body,
    )
    assert escalated == "no_status_section"


def test_replay_ok_generic(synthetic_raws: dict[str, Path]) -> None:
    """Act: parse a GenericMarkdownParser-acceptable raw → parse_ok."""
    from aegis_phase1._archive.corr061.markdown_parser import GenericMarkdownParser

    text = synthetic_raws["ok_generic"].read_text(encoding="utf-8")
    body = parser_replay.extract_raw_body(text)

    outcome, _, _ = parser_replay.replay_one(
        "P1C-LLM-02-COMPOUND-EVENT", GenericMarkdownParser, body, gate=None,
    )

    assert outcome == "parse_ok"


def test_replay_empty_body(synthetic_raws: dict[str, Path]) -> None:
    """Act: replay an empty body → empty_body / empty_body class."""
    from aegis_phase1._archive.corr061.markdown_parser import P1BLLM01Parser

    text = synthetic_raws["empty_body"].read_text(encoding="utf-8")
    body = parser_replay.extract_raw_body(text)

    outcome, error_class, _ = parser_replay.replay_one(
        "P1B-LLM-02-RATIONALE", P1BLLM01Parser, body, gate=None,
    )

    assert outcome == "empty_body"
    assert error_class == "empty_body"


def test_analyse_corpus_full_flow(
    synthetic_raws: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: drive ``analyse_corpus`` on the synthetic tree.

    This is the assertion that ties the four AAA cases together — the
    per_file list must contain exactly the 4 scenarios with the right
    classifications, and totals_by_spec must aggregate them.
    """
    monkeypatch.setattr(parser_replay, "DEFAULT_RAW_DIR", tmp_path, raising=False)

    payload: dict[str, Any] = parser_replay.analyse_corpus(
        raw_dir=tmp_path,
        specs=(
            "P1B-LLM-01-INTERPRETATION",
            "P1B-LLM-02-RATIONALE",
            "P1C-LLM-02-COMPOUND-EVENT",
        ),
        models=None,
        limit=50,
        gate=None,
    )

    by_path = {rec["path"].rsplit("/", 1)[-1]: rec for rec in payload["per_file"]}
    assert by_path["2026-09-09T00-00-00__attempt1.md"]["outcome"] == "parse_ok"
    assert by_path["2026-09-09T00-01-00__attempt1.md"]["outcome"] == "parse_fail"
    assert by_path["2026-09-09T00-02-00__attempt1.md"]["outcome"] == "parse_ok"
    assert by_path["2026-09-09T00-03-00__attempt1.md"]["outcome"] == "empty_body"

    # totals_by_spec shape: flat cell per spec with model_count,
    # parse_ok, parse_fail, gate_fail, error_classes (matches C3).
    for _spec, cell in payload["totals_by_spec"].items():
        assert {"model_count", "parse_ok", "parse_fail", "gate_fail",
                "error_classes", "by_model"} <= set(cell.keys())

    # JSON-roundtrip stability (C3 also asserts this on the real corpus).
    assert json.loads(json.dumps(payload)) == payload
