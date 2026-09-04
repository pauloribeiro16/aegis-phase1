"""Tests for CORR-111 — Doc preamble + aegis: frontmatter stripping.

The user's complaint ("vou a achar que foi o modelo normal que fez isso e não foi o caso")
needs both:
  - the Doc 01-09 first line to NAME the model + quant + job;
  - the per_spec_markdown cache to NOT leak the HTML frontmatter into
    user-facing appendices.

These two helpers (``doc_preamble`` + ``strip_aegis_frontmatter``)
are the only surface that touches Doc output, so we cover them with
fast unit tests that don't depend on the full pipeline state.
"""

from __future__ import annotations

from aegis_phase1.v2.output._common import (
    doc_preamble,
    strip_aegis_frontmatter,
)


def test_preamble_returns_empty_when_no_capabilities() -> None:
    """No state → no preamble. Deterministic-only runs don't claim a model."""
    assert doc_preamble({}) == ""
    assert doc_preamble(None) == ""
    assert doc_preamble({"v2_model_capabilities": None}) == ""


def test_preamble_with_unknown_quant_appends_caveat() -> None:
    cap = {
        "model": "gemma4:31b",
        "provider": "ollama",
        "quantization": "unknown",
        "quantization_provenance": "unknown",
        "job_id": "1869082",
    }
    out = doc_preamble({"v2_model_capabilities": cap})
    assert out.startswith("Model: gemma4:31b @ unknown (job 1869082)")
    assert "[quant unknown — verify manifest]" in out


def test_preamble_with_provider_default_appends_caveat() -> None:
    cap = {
        "model": "gemma4:31b",
        "provider": "ollama",
        "quantization": "provider_default",
        "quantization_provenance": "provider_default",
        "job_id": "1869082",
    }
    out = doc_preamble({"v2_model_capabilities": cap})
    assert "Model: gemma4:31b @ provider_default (job 1869082)" in out
    assert "[quant = provider default — declare explicitly if reproducible]" in out


def test_preamble_with_known_quant_is_clean() -> None:
    cap = {
        "model": "qwen3.5:27b",
        "provider": "ollama",
        "quantization": "q4_K_M",
        "quantization_provenance": "ollama-pull",
        "job_id": "1869082",
    }
    out = doc_preamble({"v2_model_capabilities": cap})
    assert out == "Model: qwen3.5:27b @ q4_K_M (job 1869082)\n\n"


def test_preamble_ends_with_blank_line_for_h1() -> None:
    """Renderers append '# AEGIS-…' immediately after. The preamble
    provides the blank line so the H1 stays on its own paragraph."""
    cap = {
        "model": "x", "provider": "ollama",
        "quantization": "q4_K_M", "quantization_provenance": "ollama-pull",
        "job_id": "1",
    }
    assert doc_preamble({"v2_model_capabilities": cap}).endswith("\n\n")


def test_strip_aegis_frontmatter_removes_leading_comment_only() -> None:
    md = "<!-- aegis:model=\"x\" provider=\"ollama\" quant=\"q4_K_M\" -->\n## Status\nbody"
    out = strip_aegis_frontmatter(md)
    assert out.startswith("## Status")
    assert "aegis:" not in out


def test_strip_aegis_frontmatter_handles_multiple_leading_comments() -> None:
    md = (
        "<!-- aegis:x -->\n"
        "<!-- another comment -->\n"
        "## Status\nbody"
    )
    out = strip_aegis_frontmatter(md)
    # Only strips aegis: prefixed; leaves unrelated comments alone.
    assert out.startswith("<!-- another comment -->\n## Status")


def test_strip_aegis_frontmatter_no_op_on_normal_text() -> None:
    md = "## Status\nbody"
    assert strip_aegis_frontmatter(md) == md


def test_strip_aegis_frontmatter_empty_safe() -> None:
    assert strip_aegis_frontmatter("") == ""
    assert strip_aegis_frontmatter(None) is None  # type: ignore[arg-type]


def test_round_trip_with_real_frontmatter() -> None:
    """End-to-end: an aegis: frontmatter on top of a substantive doc still
    renders cleanly when fed through ``strip_aegis_frontmatter``."""
    front = (
        "<!-- aegis:model=\"qwen3.5:27b\" provider=\"ollama\" "
        "quant=\"q4_K_M\" job=\"1869082\" spec=\"P1B-LLM-01-INTERPRETATION\" "
        "ts=\"2026-09-02T20:14:00Z\" -->\n"
    )
    body = "## Status\n- applicable: true\n- confidence: HIGH\n\n## Findings\nreal content"
    md = front + body
    stripped = strip_aegis_frontmatter(md)
    assert stripped == body
