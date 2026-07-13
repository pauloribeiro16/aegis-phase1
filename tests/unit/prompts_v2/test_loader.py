"""Tests for PromptLoader — loads PROMPTS/*.md and extracts YAML frontmatter."""

from __future__ import annotations

import pytest

from aegis_phase1.prompts_v2.loader import PromptLoader, PromptLoadError

PHASE1_LLMS = [
    "P1B-LLM-01-INTERPRETATION",
    "P1B-LLM-02-RATIONALE",
    "P1C-LLM-01-OVERLAP-CLASSIFICATION",
    "P1C-LLM-02-COMPOUND-EVENT",
    "P1C-LLM-03-STRATEGIC-SYNTHESIS",
]


def test_prompt_loader_init():
    """PromptLoader initializes with default path."""
    loader = PromptLoader()
    assert loader.root.exists()
    assert loader.base_system  # base_system_prompt.md has content


def test_prompt_loader_loads_all_5_phase1_llms():
    """All 5 Phase 1 LLM prompts exist and can be loaded."""
    loader = PromptLoader()
    for spec_id in PHASE1_LLMS:
        loaded = loader.load(spec_id)
        assert loaded["spec_id"] == spec_id
        assert loaded["frontmatter"]
        assert loaded["body"]
        assert loaded["system"]
        assert "prompt_spec_id" in loaded["frontmatter"]
        assert loaded["frontmatter"]["prompt_spec_id"] == spec_id


def test_prompt_loader_inheritance_aliases():
    """Each prompt has legacy_aliases in frontmatter."""
    loader = PromptLoader()
    for spec_id in PHASE1_LLMS:
        loaded = loader.load(spec_id)
        fm = loaded["frontmatter"]
        assert "legacy_aliases" in fm, f"{spec_id} missing legacy_aliases"
        assert "invocation_pattern" in fm


def test_prompt_loader_render_returns_system_and_user():
    """render() returns a dict with system and user keys."""
    loader = PromptLoader()
    rendered = loader.render(
        "P1B-LLM-01-INTERPRETATION",
        {"case_id": "Case_01", "lane_id": "GDPR", "applicable_regs": ["GDPR"]},
    )
    assert "system" in rendered
    assert "user" in rendered
    assert "P1B-LLM-01-INTERPRETATION" in rendered["user"] or "P1B-LLM-01" in rendered["user"]


def test_prompt_loader_cache():
    """Second load() returns same dict (cache hit)."""
    loader = PromptLoader()
    a = loader.load("P1B-LLM-01-INTERPRETATION")
    b = loader.load("P1B-LLM-01-INTERPRETATION")
    assert a is b
    loader.invalidate("P1B-LLM-01-INTERPRETATION")
    c = loader.load("P1B-LLM-01-INTERPRETATION")
    assert c is not b


def test_prompt_loader_invalid_spec_raises():
    """Loading a non-existent spec raises PromptLoadError."""
    loader = PromptLoader()
    with pytest.raises(PromptLoadError):
        loader.load("P1Z-LLM-99-NONEXISTENT")


def test_prompt_loader_list_specs():
    """list_specs() returns the 5 Phase 1 LLM IDs."""
    loader = PromptLoader()
    specs = loader.list_specs()
    assert set(PHASE1_LLMS).issubset(set(specs))
