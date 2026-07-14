"""Unit tests for section_refill with mocked LLM."""

from unittest.mock import MagicMock, patch

from aegis_phase1.section_refill import (
    _normalize,
    _split_into_sections,
    find_section_range,
    refill_section,
)


def test_split_into_sections_basic():
    text = "# Title\n\nBody\n\n## Section A\n\nContent here"
    sections = _split_into_sections(text)
    assert len(sections) >= 2
    headers = [s[1] for s in sections if s[1]]
    assert "Title" in headers
    assert "Section A" in headers


def test_split_into_sections_empty():
    sections = _split_into_sections("")
    assert len(sections) == 1
    assert sections[0][1] == ""


def test_find_section_range_found():
    text = "preamble\n\n## My Section\n\nSection body text\n\n## Other\n\nOther body"
    result = find_section_range(text, "My Section")
    assert result is not None
    level, _body_start, _body_end = result
    assert level == 2


def test_find_section_range_not_found():
    text = "## Only Section\n\nBody"
    result = find_section_range(text, "Nonexistent")
    assert result is None


def test_normalize_handles_whitespace():
    assert _normalize("  My   Section  ") == "my section"


def test_normalize_lowercases():
    assert _normalize("SECTION A") == "section a"


@patch("aegis_phase1.llm.base.create_llm_client")
def test_refill_section_returns_path(mock_create_client, tmp_path):
    filled = tmp_path / "doc_filled.md"
    filled.write_text("## Section A\n\nOld content\n\n## Section B\n\nKeep this", encoding="utf-8")
    template = tmp_path / "doc.md"
    template.write_text(
        "## Section A\n\n[placeholder]\n\n## Section B\n\n[placeholder]", encoding="utf-8"
    )

    mock_client = MagicMock()
    mock_client.generate.return_value = {"raw": "New content for A"}
    mock_create_client.return_value = mock_client

    result = refill_section(
        filled_path=filled,
        section_name="Section A",
        template_path=template,
        state={"key": "value"},
        issue_description="Fix section A",
        output_path=tmp_path / "output.md",
    )

    assert result.exists()
    assert result == tmp_path / "output.md"
    mock_client.generate.assert_called_once()


@patch("aegis_phase1.llm.base.create_llm_client")
def test_refill_section_writes_output_file(mock_create_client, tmp_path):
    filled = tmp_path / "doc_filled.md"
    filled.write_text("## Alpha\n\nAlpha body\n\n## Beta\n\nBeta body", encoding="utf-8")
    template = tmp_path / "doc.md"
    template.write_text("## Alpha\n\n[placeholder]\n\n## Beta\n\n[placeholder]", encoding="utf-8")

    mock_client = MagicMock()
    mock_client.generate.return_value = {"raw": "Fixed alpha"}
    mock_create_client.return_value = mock_client

    result = refill_section(
        filled_path=filled,
        section_name="Alpha",
        template_path=template,
        state={},
        issue_description="Fix alpha",
        output_path=tmp_path / "out.md",
    )

    assert result.exists()
    output = result.read_text(encoding="utf-8")
    assert "Fixed alpha" in output


@patch("aegis_phase1.llm.base.create_llm_client")
def test_refill_section_nonexistent_section_returns_original(mock_create_client, tmp_path):
    filled = tmp_path / "doc_filled.md"
    filled.write_text("## Only Section\n\nBody", encoding="utf-8")
    template = tmp_path / "doc.md"
    template.write_text("## Only Section\n\n[placeholder]", encoding="utf-8")

    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    result = refill_section(
        filled_path=filled,
        section_name="Nonexistent",
        template_path=template,
        state={},
        issue_description="Fix nonexistent",
    )

    assert result == filled
    mock_client.generate.assert_not_called()


@patch("aegis_phase1.llm.base.create_llm_client")
def test_refill_section_llm_error_returns_original(mock_create_client, tmp_path):
    filled = tmp_path / "doc_filled.md"
    filled.write_text("## Section\n\nBody", encoding="utf-8")
    template = tmp_path / "doc.md"
    template.write_text("## Section\n\n[placeholder]", encoding="utf-8")

    mock_client = MagicMock()
    mock_client.generate.return_value = {"error": "connection refused"}
    mock_create_client.return_value = mock_client

    result = refill_section(
        filled_path=filled,
        section_name="Section",
        template_path=template,
        state={},
        issue_description="Fix",
    )

    assert result == filled


@patch("aegis_phase1.llm.base.create_llm_client")
def test_refill_section_empty_llm_response_returns_original(mock_create_client, tmp_path):
    filled = tmp_path / "doc_filled.md"
    filled.write_text("## Section\n\nBody", encoding="utf-8")
    template = tmp_path / "doc.md"
    template.write_text("## Section\n\n[placeholder]", encoding="utf-8")

    mock_client = MagicMock()
    mock_client.generate.return_value = {"raw": ""}
    mock_create_client.return_value = mock_client

    result = refill_section(
        filled_path=filled,
        section_name="Section",
        template_path=template,
        state={},
        issue_description="Fix",
    )

    assert result == filled
