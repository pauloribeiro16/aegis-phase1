"""Regression guard for track_b scale per case (CORR-101 Bonus Gap 3).

GAP (verified non-issue 2026-08-05): the track_b_suggestion block
in ``assemble_inputs()`` reads the scale from classification.yaml
(via the company_context) and normalises it through
``_normalise_scale`` into the canonical TrackB scale enum
(MICRO / SMALL / MEDIUM / LARGE / MAX). The ``attrs.scale_original``
field preserves the raw value for debugging.

Verified at runtime for all 3 cases:
    - case1-tinytask    : MICRO   -> LIGHTWEIGHT/MINIMAL/STANDARD (tier=LOW)
    - case2-secureborder: LARGE   -> RIGOROUS                     (tier=HIGH)
    - case3-omnibank    : LARGE   -> RIGOROUS                     (tier=HIGH)

These tests pin that contract so a future refactor cannot silently
break the scale -> tier mapping (a class of bugs where the LLM
prompt receives the wrong proportionality tier).

Refs:
    - CORR-101 Bonus Gap 3 (regression guard)
    - src/aegis_phase1/v2/domain/inputs.py:_normalise_scale
    - src/aegis_phase1/prompts_v2/track_b.py:TrackB.assign_tier
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis_phase1.v2.domain.inputs import assemble_inputs
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator

CASES = [
    ("cases/case1-tinytask", "MICRO", "MICRO"),
    ("cases/case2-secureborder", "LARGE", "LARGE"),
    ("cases/case3-omnibank", "LARGE", "LARGE"),
]


@pytest.fixture(scope="module")
def loader() -> PreprocCatalogLoader:
    return PreprocCatalogLoader(Path("preproc_out"))


def _build_orchestrator(case_path: str, loader: PreprocCatalogLoader) -> Phase1Orchestrator:
    cpl = CaseProfileLoader(case_path)
    orch = Phase1Orchestrator(
        work_dir=f"/tmp/aegis-test-corr101-trackb/{Path(case_path).name}",
        preproc_catalog=loader,
        case_profile_loader=cpl,
    )
    orch.load(case_path, regulatory_baseline_path="preproc_out")
    return orch


def test_case1_tinytask_track_b_scale_is_micro(
    loader: PreprocCatalogLoader,
) -> None:
    """case1: scale=MICRO, track_b scale=MICRO (canonical)."""
    orch = _build_orchestrator("cases/case1-tinytask", loader)
    inputs = assemble_inputs(orch.state, "D-01")
    track_b = inputs["track_b_suggestion"]
    attrs = track_b["attrs"]
    # Scale (canonical TrackB enum)
    assert attrs["scale"] == "MICRO", f"case1-tinytask scale must be MICRO, got {attrs['scale']!r}"
    # Scale_original mirrors the raw value from classification.yaml
    # (preserved verbatim for debugging)
    assert attrs.get("scale_original") == "MICRO", (
        f"case1-tinytask scale_original must equal the raw value 'MICRO', "
        f"got {attrs.get('scale_original')!r}"
    )
    # Tier is one of the lightweight ones for MICRO scale
    assert track_b["tier"] in (
        "MINIMAL",
        "LIGHTWEIGHT",
        "STANDARD",
    ), f"MICRO scale must yield a lightweight tier, got {track_b['tier']!r}"


def test_case2_secureborder_track_b_scale_is_large(
    loader: PreprocCatalogLoader,
) -> None:
    """case2: scale=LARGE, tier=RIGOROUS."""
    orch = _build_orchestrator("cases/case2-secureborder", loader)
    inputs = assemble_inputs(orch.state, "D-01")
    track_b = inputs["track_b_suggestion"]
    attrs = track_b["attrs"]
    assert (
        attrs["scale"] == "LARGE"
    ), f"case2-secureborder scale must be LARGE, got {attrs['scale']!r}"
    assert attrs.get("scale_original") == "LARGE", (
        f"case2-secureborder scale_original must be 'LARGE', "
        f"got {attrs.get('scale_original')!r}"
    )
    # LARGE scale forces RIGOROUS tier (CORR-042 + CORR-067 verified)
    assert (
        track_b["tier"] == "RIGOROUS"
    ), f"LARGE scale must yield RIGOROUS tier, got {track_b['tier']!r}"


def test_case3_omnibank_track_b_scale_is_large(
    loader: PreprocCatalogLoader,
) -> None:
    """case3: scale=LARGE, tier=RIGOROUS."""
    orch = _build_orchestrator("cases/case3-omnibank", loader)
    inputs = assemble_inputs(orch.state, "D-01")
    track_b = inputs["track_b_suggestion"]
    attrs = track_b["attrs"]
    assert attrs["scale"] == "LARGE", f"case3-omnibank scale must be LARGE, got {attrs['scale']!r}"
    assert attrs.get("scale_original") == "LARGE", (
        f"case3-omnibank scale_original must be 'LARGE', " f"got {attrs.get('scale_original')!r}"
    )
    assert (
        track_b["tier"] == "RIGOROUS"
    ), f"LARGE scale must yield RIGOROUS tier, got {track_b['tier']!r}"


def test_scale_original_matches_classification_yaml_input(
    loader: PreprocCatalogLoader,
) -> None:
    """All 3 cases: ``scale_original`` matches the raw value, no transformation.

    Guards against a class of bugs where a refactor silently
    normalises / overwrites the raw scale (e.g. case1 originally
    declares ``scale: \"micro-enterprise\"`` — that should pass
    through verbatim to ``scale_original`` even though
    ``_normalise_scale`` maps it to ``\"MICRO\"``).
    """
    for case_path, expected_canonical, expected_original in CASES:
        profile = CaseProfileLoader(case_path).load()
        raw_scale = profile.company.scale
        # Expected canonical mapping (raw -> canonical TrackB enum)
        # Hard-coded per the verified runtime check on 2026-08-05.
        assert raw_scale.upper() == expected_original.upper(), (
            f"{Path(case_path).name}: classification.yaml scale={raw_scale!r} "
            f"doesn't match expected {expected_original!r}. "
            f"Update this test if the classification changed intentionally."
        )

        orch = _build_orchestrator(case_path, loader)
        inputs = assemble_inputs(orch.state, "D-01")
        scale_original = inputs["track_b_suggestion"]["attrs"].get("scale_original")
        assert scale_original == raw_scale, (
            f"{Path(case_path).name}: scale_original={scale_original!r} must "
            f"equal the raw classification.yaml value {raw_scale!r} "
            f"(no transformation)"
        )
        assert inputs["track_b_suggestion"]["attrs"]["scale"] == expected_canonical


__all__ = []
