"""Tests for CORR-OBJ-08: 100% provenance coverage across 9 doc renderers.

For every doc renderer in ``src/aegis_phase1/v2/output/`` we expect
either:

  (a) at least one call to ``section_provenance_tag`` (or the
      underlying ``section_tag_for_heading``), meaning the renderer
      tags LLM-derived headings via the registry; OR
  (b) the doc is **all-deterministic** — every H2 section in
      :data:`aegis_phase1.v2.output.provenance.PROVENANCE` is
      classified as ``deterministic``, so the renderer is
      intentionally tagless and the registry records the audit trail.

This test uses **AST parsing** (not import-and-render) so it stays
fast and side-effect free. The audit is content-based: we don't
execute the renderer (which would require heavy state); we read the
source and count call sites.

What this test does NOT do (out of scope for OBJ-08):

  * Run the full pipeline and verify the tag appears in the rendered
    markdown on disk. check_gate.py already does that for every doc
    in --run-dir.
  * Refactor renderers to add new calls. The 4 all-deterministic
    renderers (doc_04, doc_04a, doc_04d, doc_06) are correctly
    tagless per the registry and the test documents that.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve()
for p in REPO.parents:
    if (p / "src" / "aegis_phase1").is_dir():
        REPO = p
        break

RENDERERS_DIR = REPO / "src" / "aegis_phase1" / "v2" / "output"

# The 9 docs produced by the pipeline, in emit order.
# Each entry is (filename_stem, doc_id).
DOC_RENDERERS: list[tuple[str, str]] = [
    ("doc_04",  "AEGIS-P1-04"),
    ("doc_04a", "AEGIS-P1-04a"),
    ("doc_04b", "AEGIS-P1-04b"),
    ("doc_04c", "AEGIS-P1-04c"),
    ("doc_04d", "AEGIS-P1-04d"),
    ("doc_05",  "AEGIS-P1-05"),
    ("doc_06",  "AEGIS-P1-06"),
    ("doc_07",  "AEGIS-P1-07"),
    ("doc_07b", "AEGIS-P1-07b"),
]


def _count_provenance_calls(source: str) -> int:
    """Count call sites to ``section_provenance_tag`` or
    ``section_tag_for_heading`` in ``source`` (AST-based, no execution).
    """
    tree = ast.parse(source)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {
                "section_provenance_tag",
                "section_tag_for_heading",
            }:
                count += 1
            elif isinstance(func, ast.Attribute) and func.attr in {
                "section_provenance_tag",
                "section_tag_for_heading",
            }:
                count += 1
    return count


def _sections_for_doc(doc_id: str) -> list[tuple[str, str]]:
    """Return [(heading, origin), ...] for ``doc_id`` from the registry."""
    sys_path_insert = [str(REPO / "src")]
    import sys
    for s in sys_path_insert:
        if s not in sys.path:
            sys.path.insert(0, s)
    from aegis_phase1.v2.output import provenance as prov

    return [
        (entry.heading, entry.origin)
        for entry in prov.sections_for_doc(doc_id)
    ]


def _all_deterministic(doc_id: str) -> bool:
    return all(origin == "deterministic" for _, origin in _sections_for_doc(doc_id))


@pytest.mark.parametrize("stem,doc_id", DOC_RENDERERS)
def test_renderer_provenance_coverage(stem: str, doc_id: str) -> None:
    """Every renderer either has at least one provenance tag call, or
    the doc is registered as all-deterministic in the registry.
    """
    src_path = RENDERERS_DIR / f"{stem}.py"
    assert src_path.exists(), f"renderer missing: {src_path}"
    source = src_path.read_text(encoding="utf-8")
    calls = _count_provenance_calls(source)
    is_all_det = _all_deterministic(doc_id)
    if is_all_det:
        # Doc 04, 04a, 04d, 06 are intentionally tagless. Document it.
        assert calls == 0, (
            f"{stem}.py ({doc_id}) is registered as all-deterministic "
            f"but the source has {calls} provenance call(s). Either remove "
            "the call (renderer is over-tagging) or reclassify the section "
            "in provenance.py."
        )
    else:
        assert calls >= 1, (
            f"{stem}.py ({doc_id}) has at least one non-deterministic "
            f"section in the registry but the source has NO "
            f"section_provenance_tag / section_tag_for_heading call. "
            "Add the call to emit the [LLM: ...] tag under LLM headings."
        )


def test_documented_all_deterministic_renderers() -> None:
    """Pinned list of renderers that are intentionally tagless.

    If a future contributor adds an LLM section to one of these docs
    in provenance.py, the parametrised test above will fail and this
    list will need updating.
    """
    all_det = [
        (stem, doc_id)
        for stem, doc_id in DOC_RENDERERS
        if _all_deterministic(doc_id)
    ]
    # Stable assertion: pin the 4 deterministic-only renderers we
    # know about today. If this changes intentionally, update both
    # this list AND provenance.py / the renderer.
    assert all_det == [
        ("doc_04",  "AEGIS-P1-04"),
        ("doc_04a", "AEGIS-P1-04a"),
        ("doc_04d", "AEGIS-P1-04d"),
        ("doc_06",  "AEGIS-P1-06"),
    ]


def test_renderers_with_llm_sections_have_tag_calls() -> None:
    """The 5 renderers that emit LLM sections each have at least one
    provenance tag call.
    """
    for stem, doc_id in DOC_RENDERERS:
        if _all_deterministic(doc_id):
            continue
        src_path = RENDERERS_DIR / f"{stem}.py"
        source = src_path.read_text(encoding="utf-8")
        calls = _count_provenance_calls(source)
        assert calls >= 1, (
            f"{stem}.py ({doc_id}) has LLM sections but no tag call. "
            "See test_renderer_provenance_coverage for the same check."
        )
