"""CORR-043-T4 (Fix 4): tests for the canonical P1C-LLM-01 path shape.

The P1C-LLM-01 (overlap classification) prompt spec expects a
metadata-rich ``layer0_subdomain_refs`` argument: a ``list[dict]`` with
per-subdomain id, title, participating_regulations, hso_hl_objective,
pairs, anchors, csf.

Pre-CORR-043-T1, the orchestrator passed ``list[str]`` of IDs which
crashed the P1C-LLM-01 canonical path with:
    ``'str' object has no attribute 'get'``

These tests pin the canonical shape so the regression does not
reappear.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator


# Required keys per the P1C-LLM-01 spec (§Inputs of
# 00_METHODOLOGY/PROMPTS/P1C-LLM-01-OVERLAP-CLASSIFICATION.md).
_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "sub_domain_id",
        "title",
        "participating_regulations",
        "hso_hl_objective",
        "objective",  # alias per spec
        "pairs",
        "anchors",
        "csf",
    }
)


@pytest.fixture
def tmp_work_dir() -> Path:
    with tempfile.TemporaryDirectory(prefix="aegis-test-p1c-canonical-") as d:
        yield Path(d)


def _build_orch(tmp_work_dir: Path) -> Phase1Orchestrator:
    """Build a Phase1Orchestrator with the v2 catalog loaded."""
    orch = Phase1Orchestrator(
        work_dir=str(tmp_work_dir),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
        preproc_catalog=PreprocCatalogLoader(Path("preproc_out")),
    )
    orch._load_v2_catalog("cases/case1-tinytask")
    return orch


def test_p1c_canonical_helper_returns_list_of_dicts(
    tmp_work_dir: Path,
) -> None:
    """CORR-043-T1 regression guard: layer0_subdomain_refs is list[dict]
    (not list[str]). The P1C-LLM-01 canonical path calls
    ``entry.get("title")`` and would crash on a list[str].
    """
    orch = _build_orch(tmp_work_dir)
    refs = orch._build_layer0_subdomain_refs()

    assert isinstance(refs, list)
    assert len(refs) > 0
    # Every entry must be a dict (not a str)
    for entry in refs:
        assert isinstance(entry, dict), (
            f"layer0_subdomain_refs entry must be dict, got {type(entry).__name__}"
        )
    # Regression: the first entry has a "title" key that .get() can read
    assert refs[0].get("title") is not None or refs[0].get("title") == ""


def test_p1c_canonical_helper_has_required_keys(
    tmp_work_dir: Path,
) -> None:
    """Every dict must carry the spec-required keys.
    Pins the contract between orchestrator and the P1C-LLM-01 prompt.
    """
    orch = _build_orch(tmp_work_dir)
    refs = orch._build_layer0_subdomain_refs()

    assert len(refs) == 38, f"expected 38 subdomains, got {len(refs)}"
    for entry in refs:
        missing = _REQUIRED_KEYS - entry.keys()
        assert not missing, (
            f"subdomain {entry.get('sub_domain_id')!r} missing keys: {sorted(missing)}"
        )
    # Spot-check value types
    sample = refs[0]
    assert isinstance(sample["sub_domain_id"], str)
    assert isinstance(sample["title"], str)
    assert isinstance(sample["participating_regulations"], list)
    assert isinstance(sample["pairs"], list)
    assert isinstance(sample["anchors"], list)
    assert isinstance(sample["csf"], list)
    # hso_hl_objective and objective are aliases (same value or both None)
    assert sample["hso_hl_objective"] == sample["objective"]


def test_p1c_canonical_helper_is_sorted_by_subdomain_id(
    tmp_work_dir: Path,
) -> None:
    """Refs are sorted by sub_domain_id for deterministic prompt input.

    LLM calls must be reproducible: the same set of subdomains in the
    same order, every time.
    """
    orch = _build_orch(tmp_work_dir)
    refs = orch._build_layer0_subdomain_refs()
    ids = [r["sub_domain_id"] for r in refs]
    assert ids == sorted(ids), f"refs not sorted: {ids[:5]}..."


def test_p1c_canonical_helper_filter_by_subdomain_ids(
    tmp_work_dir: Path,
) -> None:
    """Filter by subdomain_ids keeps only the requested entries (in the
    same order as the canonical sort, not the input list).
    """
    orch = _build_orch(tmp_work_dir)
    wanted = ["D-04.3", "D-01.1", "D-09.2"]
    refs = orch._build_layer0_subdomain_refs(subdomain_ids=wanted)

    assert len(refs) == 3
    got_ids = [r["sub_domain_id"] for r in refs]
    # Sorted (not the input order)
    assert got_ids == sorted(wanted)
    for r in refs:
        assert r["sub_domain_id"] in wanted
        # Filtered entries still have the canonical shape
        assert _REQUIRED_KEYS <= r.keys()


def test_p1c_canonical_helper_handles_legacy_list_str(
    tmp_work_dir: Path,
) -> None:
    """Regression: pre-CORR-043-T1 the orchestrator passed list[str] of
    IDs. Calling ``refs[0].get("title")`` on a list[str] would raise
    ``AttributeError: 'str' object has no attribute 'get'``.

    This test reproduces that exact crash as a guard.
    """
    orch = _build_orch(tmp_work_dir)
    refs = orch._build_layer0_subdomain_refs()

    # Simulate what P1C-LLM-01 does: iterate and .get() per entry
    for entry in refs:
        # This line would crash on list[str]
        _ = entry.get("title", "")
        _ = entry.get("participating_regulations", [])
        _ = entry.get("pairs", [])
    # If we got here without AttributeError, the canonical shape is
    # intact and the regression is fixed.
