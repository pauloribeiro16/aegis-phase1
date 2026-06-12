"""Unit tests for doc_evaluator (rule-based detection + mocked LLM)."""

from unittest.mock import MagicMock, patch

from aegis_phase1.doc_evaluator import (
    Issue,
    _detect_contradictions,
    _detect_id_inconsistencies,
    _rule_based_scan,
    evaluate_filled_doc,
    group_issues_by_section,
)


def test_rule_based_detects_empty_field():
    text = "## My Section\n\n- **Sector:**\n- **Size:** SME"
    issues = _rule_based_scan(text, "")
    empty_fields = [i for i in issues if i.issue_type == "empty_field"]
    assert len(empty_fields) == 1
    assert "Sector" in empty_fields[0].description


def test_rule_based_detects_placeholder():
    text = "## My Section\n\nValue is [N] here and [X] there."
    issues = _rule_based_scan(text, "")
    placeholders = [i for i in issues if i.issue_type == "placeholder"]
    assert len(placeholders) == 2


def test_rule_based_detects_missing_section():
    text = "## Empty Section\n\n"
    issues = _rule_based_scan(text, "")
    missing = [i for i in issues if i.issue_type == "missing_section"]
    assert len(missing) == 1


def test_rule_based_clean_doc_no_issues():
    text = "## Section A\n\n- **Field:** Value\n- **Other:** Data"
    issues = _rule_based_scan(text, "")
    assert issues == []


def test_detect_contradictions_with_conflicting_coverage():
    text = "Coverage: 85% in section A. Coverage: 70% in section B."
    issues = _detect_contradictions(text)
    contradictions = [i for i in issues if i.issue_type == "contradiction"]
    assert len(contradictions) >= 1


def test_detect_no_contradictions_with_consistent_coverage():
    text = "Coverage: 85% here. Coverage: 85% there."
    issues = _detect_contradictions(text)
    assert issues == []


def test_detect_id_inconsistencies_mixed():
    text = "## Section\n\nRef SD-GDPR and also D-01.2."
    issues = _detect_id_inconsistencies(text)
    inconsistent = [i for i in issues if i.issue_type == "inconsistent"]
    assert len(inconsistent) == 1


def test_detect_no_id_inconsistencies_single_format():
    text = "## Section\n\nRef SD-GDPR and SD-NIS2."
    issues = _detect_id_inconsistencies(text)
    assert issues == []


def test_group_issues_by_section():
    issues = [
        Issue(
            section="A",
            issue_type="empty_field",
            severity="high",
            location="",
            description="",
            suggested_fix="",
        ),
        Issue(
            section="B",
            issue_type="placeholder",
            severity="medium",
            location="",
            description="",
            suggested_fix="",
        ),
        Issue(
            section="A",
            issue_type="placeholder",
            severity="low",
            location="",
            description="",
            suggested_fix="",
        ),
    ]
    grouped = group_issues_by_section(issues)
    assert "A" in grouped
    assert "B" in grouped
    assert len(grouped["A"]) == 2
    assert len(grouped["B"]) == 1


def test_evaluate_filled_doc_rule_based_only(tmp_path):
    filled = tmp_path / "doc_filled.md"
    filled.write_text(
        "## Section A\n\n- **Field:**\n\n## Section B\n\nValue is [N]", encoding="utf-8"
    )
    template = tmp_path / "doc.md"
    template.write_text(
        "## Section A\n\n- **Field:** [placeholder]\n\n## Section B\n\nValue", encoding="utf-8"
    )

    issues = evaluate_filled_doc(filled, template, state=None, use_llm=False)
    assert len(issues) >= 2
    types = {i.issue_type for i in issues}
    assert "empty_field" in types
    assert "placeholder" in types


@patch("aegis_phase1.llm.base.create_llm_client")
def test_evaluate_filled_doc_calls_llm_when_enabled(mock_create_client, tmp_path):
    filled = tmp_path / "doc_filled.md"
    filled.write_text("## Section\n\nSome content", encoding="utf-8")
    template = tmp_path / "doc.md"
    template.write_text("## Section\n\nExpected", encoding="utf-8")

    mock_client = MagicMock()
    mock_client.generate.return_value = {"raw": "[]"}
    mock_create_client.return_value = mock_client

    issues = evaluate_filled_doc(filled, template, state={"key": "val"}, use_llm=True)
    mock_client.generate.assert_called_once()
    assert isinstance(issues, list)


@patch("aegis_phase1.llm.base.create_llm_client")
def test_evaluate_filled_doc_skips_llm_when_disabled(mock_create_client, tmp_path):
    filled = tmp_path / "doc_filled.md"
    filled.write_text("## Section\n\nSome content", encoding="utf-8")
    template = tmp_path / "doc.md"
    template.write_text("## Section\n\nExpected", encoding="utf-8")

    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    issues = evaluate_filled_doc(filled, template, state={"key": "val"}, use_llm=False)
    mock_client.generate.assert_not_called()
    assert isinstance(issues, list)
