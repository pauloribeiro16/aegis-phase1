"""Unit tests for run_with_iteration with mocked LLM and doc producer."""

from pathlib import Path
from unittest.mock import patch

import pytest

from aegis_phase1.doc_evaluator import Issue
from aegis_phase1.run_with_iteration import (
    PHASE1_DOCS,
    _next_version_path,
    run_with_iteration,
)


def test_next_version_path_v1_to_v2():
    p = Path("/tmp/doc_v1_filled.md")
    result = _next_version_path(p, 2)
    assert "v2" in result.name
    assert result.suffix == ".md"


def test_next_version_path_fills_to_v2():
    p = Path("/tmp/doc_filled.md")
    result = _next_version_path(p, 2)
    assert "v2" in result.name


def test_phase1_docs_has_4_entries():
    assert len(PHASE1_DOCS) == 4


@patch("aegis_phase1.run_with_iteration._save_state")
@patch("aegis_phase1.run_with_iteration._initial_fill")
@patch("aegis_phase1.run_with_iteration.evaluate_filled_doc")
@patch("aegis_phase1.run_with_iteration.refill_section")
def test_max_runs_1_stops_after_first_iteration(
    mock_refill, mock_eval, mock_fill, mock_save, tmp_path
):
    (tmp_path / ".phase1_state.json").write_text("{}")
    mock_fill.return_value = {
        "04_Company_Context_Assessment": tmp_path / "04_filled.md",
    }
    (tmp_path / "04_filled.md").write_text("content")
    mock_eval.return_value = []

    result = run_with_iteration(
        case_path=str(tmp_path),
        state={"key": "val"},
        max_runs=1,
        docs_to_produce=["04_Company_Context_Assessment"],
        use_llm_evaluator=False,
    )

    doc_result = result["04_Company_Context_Assessment"]
    assert doc_result.runs == 1
    mock_eval.assert_not_called()


@patch("aegis_phase1.run_with_iteration._save_state")
@patch("aegis_phase1.run_with_iteration._initial_fill")
@patch("aegis_phase1.run_with_iteration.evaluate_filled_doc")
@patch("aegis_phase1.run_with_iteration.refill_section")
def test_single_iteration_produces_output(mock_refill, mock_eval, mock_fill, mock_save, tmp_path):
    (tmp_path / ".phase1_state.json").write_text("{}")
    filled_path = tmp_path / "04_filled.md"
    filled_path.write_text("content")
    mock_fill.return_value = {"04_Company_Context_Assessment": filled_path}
    mock_eval.return_value = []

    result = run_with_iteration(
        case_path=str(tmp_path),
        state={"key": "val"},
        max_runs=1,
        docs_to_produce=["04_Company_Context_Assessment"],
        use_llm_evaluator=False,
    )

    assert "04_Company_Context_Assessment" in result
    assert result["04_Company_Context_Assessment"].final_path == filled_path


@patch("aegis_phase1.run_with_iteration._save_state")
@patch("aegis_phase1.run_with_iteration._initial_fill")
@patch("aegis_phase1.run_with_iteration._evaluate_and_decide")
@patch("aegis_phase1.run_with_iteration._patch_issues")
@patch("aegis_phase1.run_with_iteration.evaluate_filled_doc")
def test_iteration_continues_when_evaluator_finds_issues(
    mock_final_eval, mock_patch, mock_decide, mock_fill, mock_save, tmp_path
):
    (tmp_path / ".phase1_state.json").write_text("{}")
    filled_path = tmp_path / "04_filled.md"
    filled_path.write_text("content")
    mock_fill.return_value = {"04_Company_Context_Assessment": filled_path}

    high_issue = Issue(
        section="Section A",
        issue_type="empty_field",
        severity="high",
        location="",
        description="Field is empty",
        suggested_fix="Fill it",
    )
    mock_decide.return_value = ([high_issue], True)
    mock_patch.return_value = filled_path
    mock_final_eval.return_value = []

    result = run_with_iteration(
        case_path=str(tmp_path),
        state={"key": "val"},
        max_runs=3,
        docs_to_produce=["04_Company_Context_Assessment"],
        use_llm_evaluator=False,
    )

    doc_result = result["04_Company_Context_Assessment"]
    assert doc_result.runs >= 2
    assert mock_patch.call_count >= 1


@patch("aegis_phase1.run_with_iteration._save_state")
@patch("aegis_phase1.run_with_iteration._initial_fill")
@patch("aegis_phase1.run_with_iteration.evaluate_filled_doc")
def test_run_with_iteration_file_not_found(mock_eval, mock_fill, tmp_path):
    with pytest.raises(FileNotFoundError):
        run_with_iteration(
            case_path=str(tmp_path / "nonexistent"),
            state={"key": "val"},
        )
