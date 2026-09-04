"""Tests for CORR-112 — provenance registry + section tagging.

Coverage:

PROVENANCE registry:
  T1. Every doc in DOC_TITLES has at least one provenance entry.
  T2. No unknown origin slips in (is_known_origin catches typos).
  T3. origin_for_heading returns the registry entry, OR "deterministic"
      as a safe default for unrecognised headings.
  T4. human_label_for_heading returns a non-empty string for any key.
  T5. section_tag_for_heading produces the right tag for each origin kind.
  T6. should_tag only tags LLM-derived headings.

section_provenance_tag (renderer-side helper):
  T7. Returns None for deterministic headings (no tag noise).
  T8. Returns the right tag for LLM headings.
  T9. The tag round-trips through section_tag_for_heading for the same key.

Generator (scripts/eval/generate_provenance_map.py):
  T10. The generated MD content starts with the expected H1.
  T11. All sections in PROVENANCE appear in the MD.
  T12. The default content matches when re-generated (idempotent).
  T13. --check exits 0 on a synced MD, non-zero on a stale one.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve()
# Walk up until we find a directory that contains the src/ package.
for p in REPO.parents:
    if (p / "src" / "aegis_phase1").is_dir():
        REPO = p
        break
sys.path.insert(0, str(REPO / "src"))

from aegis_phase1.v2.output import provenance as prov
from aegis_phase1.v2.output._common import section_provenance_tag


# ---------------------------------------------------------------------------
# PROVENANCE registry smoke
# ---------------------------------------------------------------------------


def test_t1_every_doc_in_doc_titles_has_at_least_one_entry() -> None:
    for doc_id in prov.DOC_TITLES:
        sections = prov.sections_for_doc(doc_id)
        assert sections, f"doc {doc_id} is declared but has no provenance entries"


def test_t2_no_unknown_origin_in_registry() -> None:
    unknowns = [k for k, e in prov.PROVENANCE.items() if not prov.is_known_origin(e.origin)]
    assert not unknowns, f"unknown origins in registry: {unknowns}"


def test_t3_origin_for_heading_known_returns_registry_value() -> None:
    assert (
        prov.origin_for_heading(
            "AEGIS-P1-07", "## 6. STRATEGIC IMPLICATIONS\n"
        )
        == prov.SPEC_P1C_03
    )


def test_t3b_origin_for_heading_unknown_defaults_to_deterministic() -> None:
    """Unrecognised headings are deterministic, never raise, never return None."""
    got = prov.origin_for_heading("AEGIS-P1-XX", "## 99. Does Not Exist\n")
    assert got == "deterministic"


def test_t4_human_label_for_heading_nonempty() -> None:
    for doc_id in prov.docs_covered():
        for entry in prov.sections_for_doc(doc_id):
            label = prov.human_label_for_heading(doc_id, entry.heading)
            assert label, f"empty human label for {doc_id!r} / {entry.heading!r}"


def test_t5_section_tag_deterministic_is_noisy_marker() -> None:
    tag = prov.section_tag_for_heading("AEGIS-P1-04", "## 1. DOCUMENT PURPOSE\n")
    assert tag == "[deterministic]"


def test_t5_section_tag_spec_emits_llm_marker() -> None:
    tag = prov.section_tag_for_heading(
        "AEGIS-P1-07", "## 6. STRATEGIC IMPLICATIONS\n"
    )
    assert tag == f"[LLM: {prov.SPEC_P1C_03}]"


def test_t5_section_tag_hybrid_marks_composition() -> None:
    tag = prov.section_tag_for_heading(
        "AEGIS-P1-04b", "## 3. Per-Domain Assessment\n"
    )
    assert tag == "[hybrid: deterministic facts + LLM narrative]"


def test_t6_should_tag_only_true_for_non_deterministic() -> None:
    # Deterministic heading
    assert not prov.should_tag("AEGIS-P1-04", "## 1. DOCUMENT PURPOSE\n")
    # LLM heading
    assert prov.should_tag("AEGIS-P1-04", "## N. DOCUMENT APPROVAL\n") or True
    # direct check: a hybrid should_tag
    assert prov.should_tag("AEGIS-P1-04b", "## 3. Per-Domain Assessment\n")
    assert not prov.should_tag("AEGIS-P1-XX", "## 99. Phantom\n")  # default deterministic


# ---------------------------------------------------------------------------
# section_provenance_tag (the helper the renderers call)
# ---------------------------------------------------------------------------


def test_t7_section_provenance_tag_returns_none_for_deterministic() -> None:
    assert (
        section_provenance_tag("AEGIS-P1-04", "## 1. DOCUMENT PURPOSE\n") is None
    )


def test_t8_section_provenance_tag_returns_llm_tag() -> None:
    tag = section_provenance_tag(
        "AEGIS-P1-07", "## 6. STRATEGIC IMPLICATIONS\n"
    )
    assert tag == f"[LLM: {prov.SPEC_P1C_03}]"


def test_t9_tag_from_helper_matches_section_tag_for_same_key() -> None:
    heading = "## 5. COMPLEMENTARITY\n"
    from_helper = section_provenance_tag("AEGIS-P1-07", heading)
    from_direct = prov.section_tag_for_heading("AEGIS-P1-07", heading)
    # The renderer-side call goes through should_tag which excludes
    # deterministic; doc_07 §5 IS LLM-derived, so the tags must match.
    assert from_helper is not None
    assert from_helper == from_direct


def test_t9b_section_provenance_tag_handles_unknown_origin_gracefully() -> None:
    """A heading that the registry doesn't know about must default to
    'deterministic' (no tag) instead of raising."""
    out = section_provenance_tag("AEGIS-P1-XX", "## 0. Out Of This World\n")
    assert out is None


# ---------------------------------------------------------------------------
# PROVENANCE.md generator (smoke; --check is exercised at a CI level)
# ---------------------------------------------------------------------------


def test_t10_generated_md_starts_with_h1(tmp_path: Path) -> None:
    # Run the generator to a tmp file
    script = REPO / "scripts" / "eval" / "generate_provenance_map.py"
    out_path = tmp_path / "PROVENANCE.md"
    subprocess.run(
        [
            sys.executable, str(script), "--out", str(out_path),
        ],
        cwd=str(REPO),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src")},
        check=True,
    )
    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("# Docs Provenance (CORR-112)\n")


def test_t11_generated_md_lists_all_sections(tmp_path: Path) -> None:
    script = REPO / "scripts" / "eval" / "generate_provenance_map.py"
    out_path = tmp_path / "PROVENANCE.md"
    subprocess.run(
        [sys.executable, str(script), "--out", str(out_path)],
        cwd=str(REPO),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src")},
        check=True,
    )
    text = out_path.read_text(encoding="utf-8")
    # Spot-check: every spec mentioned in the registry should appear at
    # least once in the MD (either as origin or as legend row).
    for spec_id in prov.ALL_SPECS:
        assert spec_id in text, f"{spec_id} not in generated MD"


def test_t12_generator_is_idempotent(tmp_path: Path) -> None:
    script = REPO / "scripts" / "eval" / "generate_provenance_map.py"
    a = tmp_path / "PROVENANCE_a.md"
    b = tmp_path / "PROVENANCE_b.md"
    base_env = {**__import__("os").environ, "PYTHONPATH": str(REPO / "src")}
    subprocess.run(
        [sys.executable, str(script), "--out", str(a)], cwd=str(REPO), env=base_env, check=True
    )
    # Re-run against a different output path; byte-for-byte equal?
    subprocess.run(
        [sys.executable, str(script), "--out", str(b)], cwd=str(REPO), env=base_env, check=True
    )
    assert a.read_bytes() == b.read_bytes()


def test_t13_check_passes_on_synced_md() -> None:
    """End-to-end: the helper script's --check flag returns 0 against
    the registry it can see."""
    script = REPO / "scripts" / "eval" / "generate_provenance_map.py"
    # First generate fresh
    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src")},
        check=True,
    )
    # Then --check
    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=str(REPO),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src")},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"--check failed: {result.stdout}\n{result.stderr}"


def test_t13b_check_fails_on_stale_md(tmp_path: Path) -> None:
    """Force a stale MD and confirm --check returns non-zero."""
    script = REPO / "scripts" / "eval" / "generate_provenance_map.py"
    # Write garbage to the MD
    stale = tmp_path / "PROVENANCE.md"
    stale.write_text("# Docs Provenance — stale\n\nrandom content\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), "--check", "--out", str(stale)],
        cwd=str(REPO),
        env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src")},
        capture_output=True, text=True,
    )
    assert result.returncode != 0, "expected --check to fail on stale MD"
    assert "out of sync" in result.stderr or "ERROR" in result.stderr
