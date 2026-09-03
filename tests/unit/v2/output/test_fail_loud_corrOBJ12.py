"""Tests for CORR-OBJ-12: fail-loud degradation marker across 9 doc renderers.

The contract:

  * When an LLM call produces empty / None content, the rendered doc
    must contain an EXPLICIT, REVIEWER-VISIBLE degradation marker -
    not silently skip the section.
  * When an LLM call succeeds, the marker must NOT appear for that
    spec (otherwise the marker is noise).

Today's implementation
======================

All 9 doc renderers delegate to
:func:`aegis_phase1.v2.output._common.render_per_spec_markdown_appendix`,
which dumps every entry of ``state["per_spec_markdown"]`` as a
markdown sub-section keyed by ``spec_id``. When a spec entry is
missing or empty, the helper emits a single
``_(no LLM response for this spec)_`` placeholder line. This is
reviewer-visible (NOT silent skipping), but it is NOT a structured
``[LLM: <spec_id>] [DEGRADED: <reason>]`` marker.

These tests cover the existing placeholder behaviour. The findings
section below tracks the gap to the ideal marker.

Findings (TODO - out of scope for OBJ-12)
=========================================

The 9 renderers fall into 3 buckets with respect to the strict
``[DEGRADED: <reason>]`` marker:

  1. **All-deterministic docs** (doc_04, doc_04a, doc_04d, doc_06):
     no LLM sections in the H2 layer; the appendix is the only
     place LLM output surfaces. Today the placeholder is the
     degradation marker; a structured marker would be a renderer
     change. **Marked TODO.**

  2. **Hybrid docs with LLM sections** (doc_04b, doc_04c, doc_05,
     doc_07, doc_07b): LLM output is interpolated into H2 sections
     (e.g. Doc 04b section 3 per-domain assessment). When the LLM
     call fails, the renderer's own fallback text replaces the LLM
     output (see ``_section_adapted_objective_placeholder`` in
     doc_04b and ``render_strategic_implications`` in doc_05). This
     is reviewer-visible but ALSO not a structured marker.
     **Marked TODO.**

  3. **The shared appendix helper** (covered by tests below): the
     ONLY place a single degradation marker is emitted per spec.

OBJ-12's deliverable is the test surface that pins the existing
behaviour so future refactors can introduce the structured marker
without regressing the no-silent-skipping invariant.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve()
for p in REPO.parents:
    if (p / "src" / "aegis_phase1").is_dir():
        REPO = p
        break
sys.path.insert(0, str(REPO / "src"))

from aegis_phase1.v2.output._common import (
    get_per_spec_markdown,
    render_per_spec_markdown_appendix,
)


# The 9 doc renderers in emit order. 8 of 9 call
# render_per_spec_markdown_appendix at the end of their render
# function. doc_04 is the exception: it is the all-deterministic
# body-only doc (render_doc_04_body) and never surfaces LLM output,
# so the appendix is meaningless. The 4 all-deterministic docs
# (doc_04, doc_04a, doc_04d, doc_06) are tagless per OBJ-08; only
# doc_04 also lacks the appendix because it has no LLM surface to
# append.
NINE_RENDERERS = (
    "doc_04",
    "doc_04a",
    "doc_04b",
    "doc_04c",
    "doc_04d",
    "doc_05",
    "doc_06",
    "doc_07",
    "doc_07b",
)

# Renderers that emit the LLM appendix (8 of 9; doc_04 is body-only).
RENDERERS_WITH_APPENDIX = (
    "doc_04a",
    "doc_04b",
    "doc_04c",
    "doc_04d",
    "doc_05",
    "doc_06",
    "doc_07",
    "doc_07b",
)


def _state_with(per_spec: dict[str, str]) -> dict:
    """Build a minimal state dict for ``render_per_spec_markdown_appendix``."""
    return {"per_spec_markdown": per_spec}


def test_empty_state_emits_placeholder_for_every_spec() -> None:
    """When ALL specs are empty, the appendix emits the (no LLM
    response) placeholder for each spec and the global 'no LLM
    responses were captured' notice at the bottom. This is the
    strict-mode behaviour - a reviewer can see the run was
    deterministic-only / mock and re-run with MOCK_LLM=false.
    """
    state = _state_with({})
    parts = render_per_spec_markdown_appendix(state)
    text = "".join(parts)
    # Every spec gets a (no LLM response) marker UNDER its H3 heading.
    # The helper's preamble docstring ALSO mentions "(no LLM response)"
    # in prose, so we slice per-section to avoid false positives.
    for spec_id in (
        "P1B-LLM-01-INTERPRETATION",
        "P1B-LLM-02-RATIONALE",
        "P1C-LLM-01-OVERLAP-CLASSIFICATION",
        "P1C-LLM-02-COMPOUND-EVENT",
        "P1C-LLM-03-STRATEGIC-SYNTHESIS",
    ):
        assert f"### {spec_id}" in text, f"missing spec heading for {spec_id}"
        after = text.split(f"### {spec_id}", 1)[1]
        next_h3 = after.find("\n### ")
        section = after if next_h3 < 0 else after[:next_h3]
        assert "(no LLM response for this spec)" in section, (
            f"expected degradation placeholder for {spec_id}"
        )
    # The global 'no LLM responses were captured' notice is the
    # fail-loud signal that the whole run was deterministic-only.
    assert "No LLM responses were captured for this run" in text


def test_partial_state_only_marks_missing_specs() -> None:
    """When ONE spec has a response and the others don't, the
    placeholder is emitted for the missing ones and the response
    body for the populated one. No cross-contamination.
    """
    state = _state_with({
        "P1B-LLM-02-RATIONALE": "## Real response\n\nSYS-01 grounded.\n",
    })
    parts = render_per_spec_markdown_appendix(state)
    text = "".join(parts)

    # Populated spec: body present, no placeholder
    assert "## Real response" in text
    assert "SYS-01 grounded." in text
    # The populated spec heading is still emitted
    assert "### P1B-LLM-02-RATIONALE" in text

    # The populated spec must NOT have a (no LLM response) line under
    # its heading.
    p1b02_section = text.split("### P1B-LLM-02-RATIONALE", 1)[1]
    # Take the part up to the next H3 heading
    p1b02_section = p1b02_section.split("### ", 1)[0]
    assert "(no LLM response" not in p1b02_section

    # Global 'no LLM responses' notice is NOT emitted (some ran)
    assert "No LLM responses were captured" not in text


def test_get_per_spec_markdown_returns_empty_for_missing_spec() -> None:
    """Defensive: get_per_spec_markdown must not raise and must
    return an empty string when the spec entry is missing or None.
    """
    assert get_per_spec_markdown({}, "P1B-LLM-01-INTERPRETATION") == ""
    assert get_per_spec_markdown(
        {"per_spec_markdown": {}}, "P1B-LLM-01-INTERPRETATION"
    ) == ""
    assert get_per_spec_markdown(
        {"per_spec_markdown": {"P1B-LLM-01-INTERPRETATION": None}},
        "P1B-LLM-01-INTERPRETATION",
    ) == ""


def test_successful_run_emits_no_placeholder() -> None:
    """Inverse: when ALL specs are populated, the appendix has NO
    (no LLM response) markers and NO 'no LLM responses were
    captured' global notice.
    """
    state = _state_with({
        "P1B-LLM-01-INTERPRETATION": "## INT-01\nOK\n",
        "P1B-LLM-02-RATIONALE": "## Rationale\nOK\n",
        "P1C-LLM-01-OVERLAP-CLASSIFICATION": "## Pair\nOK\n",
        "P1C-LLM-02-COMPOUND-EVENT": "## Event\nOK\n",
        "P1C-LLM-03-STRATEGIC-SYNTHESIS": "## Strategy\nOK\n",
    })
    parts = render_per_spec_markdown_appendix(state)
    text = "".join(parts)

    # The helper's preamble docstring mentions "(no LLM response)" as
    # a description of the placeholder, so the substring matches the
    # preamble. We assert on the BODY of each spec section instead.
    for spec_id, body in (
        ("P1B-LLM-01-INTERPRETATION", "## INT-01\nOK"),
        ("P1B-LLM-02-RATIONALE", "## Rationale\nOK"),
        ("P1C-LLM-01-OVERLAP-CLASSIFICATION", "## Pair\nOK"),
        ("P1C-LLM-02-COMPOUND-EVENT", "## Event\nOK"),
        ("P1C-LLM-03-STRATEGIC-SYNTHESIS", "## Strategy\nOK"),
    ):
        # Slice the text between this spec's H3 and the next H3.
        after = text.split(f"### {spec_id}", 1)[1]
        next_h3 = after.find("\n### ")
        section = after if next_h3 < 0 else after[:next_h3]
        assert body in section, f"missing populated body for {spec_id}"
        assert "(no LLM response" not in section, (
            f"unexpected placeholder under populated {spec_id}"
        )

    # Global 'no LLM responses' notice is NOT emitted (some ran)
    assert "No LLM responses were captured" not in text

    # H3 spec headings are still present (for the audit trail).
    for spec_id in (
        "P1B-LLM-01-INTERPRETATION",
        "P1B-LLM-02-RATIONALE",
        "P1C-LLM-01-OVERLAP-CLASSIFICATION",
        "P1C-LLM-02-COMPOUND-EVENT",
        "P1C-LLM-03-STRATEGIC-SYNTHESIS",
    ):
        assert f"### {spec_id}" in text


def test_every_renderer_invokes_appendix_helper() -> None:
    """8 of 9 doc renderers delegate to render_per_spec_markdown_appendix.
    The exception is doc_04 (body-only, all-deterministic, no LLM
    surface to append). Source-grep audit; mirrors the OBJ-08 test
    pattern (no execution of heavy renderer bodies).
    """
    out_dir = REPO / "src" / "aegis_phase1" / "v2" / "output"
    missing: list[str] = []
    for stem in RENDERERS_WITH_APPENDIX:
        src = (out_dir / f"{stem}.py").read_text(encoding="utf-8")
        if "render_per_spec_markdown_appendix" not in src:
            missing.append(stem)
    assert missing == [], (
        f"These renderers do not call render_per_spec_markdown_appendix: "
        f"{missing}. Add the call so the degradation marker reaches the "
        "rendered doc."
    )


def test_doc_04_has_no_appendix_by_design() -> None:
    """doc_04 is body-only and does not call the appendix helper. This
    is intentional: the doc is the all-deterministic company context
    assessment. If a future contributor adds LLM sections to doc_04
    (updating the PROVENANCE registry), this test will fail and they
    will need to add the appendix call.
    """
    out_dir = REPO / "src" / "aegis_phase1" / "v2" / "output"
    src = (out_dir / "doc_04.py").read_text(encoding="utf-8")
    assert "render_per_spec_markdown_appendix" not in src, (
        "doc_04 was always body-only. If you added the appendix call, "
        "also update RENDERERS_WITH_APPENDIX above and the OBJ-08 / OBJ-12 "
        "documentation."
    )


def test_appendix_helper_is_exhaustive_for_5_specs() -> None:
    """Pins the set of specs the appendix iterates over. If a new
    spec is added, this test fails and the developer must decide
    whether to add it to the appendix surface.
    """
    from aegis_phase1.v2.output._common import PER_SPEC_MD_SPECS

    assert set(PER_SPEC_MD_SPECS) == {
        "P1B-LLM-01-INTERPRETATION",
        "P1B-LLM-02-RATIONALE",
        "P1C-LLM-01-OVERLAP-CLASSIFICATION",
        "P1C-LLM-02-COMPOUND-EVENT",
        "P1C-LLM-03-STRATEGIC-SYNTHESIS",
    }
