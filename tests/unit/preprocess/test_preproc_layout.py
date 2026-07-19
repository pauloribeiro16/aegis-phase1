"""CORR-024 v9: preproc_out layout invariants.

Verifies the v8/v9 disk invariants after `python -m scripts.preprocess build`:

- regulation/{REG}/_root/ shards have NO ``raw_md`` (the body content is
  duplicated in regulation/{REG}/aggregated/ for 01_SO/02_SR, or purely
  narrative for 00_README/03_validation/04_deduction where frontmatter
  is enough audit info).
- Other dirs that legitimately carry raw_md (crossregulation/analyses,
  global templates, ambiguity_analysis, _templates) still have it.
- No flat shard files at unexpected places.
- CSF per-Function layout (v7+) is preserved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PREPROC_OUT = REPO_ROOT / "preproc_out"

# v9: regulation/_root/ shards must NOT carry raw_md
REG_ROOT = PREPROC_OUT / "regulation"

# v9: dirs that DO carry raw_md by design (catch-all parser, no structured
# counterpart available)
RAW_MD_ALLOWED_DIRS = {
    "ambiguity_analysis",
    "crossregulation",  # includes _templates/
    "global",  # except NIST_CSF_2.0_subcategories.json (structured)
}


# ─── Top-level layout ──────────────────────────────────────────────────


def test_top_level_layout() -> None:
    """v8 top-level dirs are exactly the 8 expected (no extras)."""
    if not PREPROC_OUT.is_dir():
        pytest.skip("preproc_out not built")
    actual = {p.name for p in PREPROC_OUT.iterdir() if p.is_dir()}
    expected = {
        "ambiguity_analysis",
        "crossregulation",
        "diagrams",
        "entities",
        "global",
        "index",
        "meta",
        "regulation",
    }
    assert actual == expected, (
        f"top-level dirs mismatch: missing={expected - actual}, " f"unexpected={actual - expected}"
    )


def test_root_files() -> None:
    """preproc_out/ root may only have README.md (no manifest.json, etc.)."""
    if not PREPROC_OUT.is_dir():
        pytest.skip("preproc_out not built")
    root_files = [p.name for p in PREPROC_OUT.iterdir() if p.is_file()]
    assert root_files == ["README.md"], f"unexpected root files: {root_files}"


# ─── v9 invariant: regulation/_root/ has NO raw_md ─────────────────────


def test_regulation_root_no_raw_md() -> None:
    """CORR-024 v9: regulation/{REG}/_root/*.json must NOT carry raw_md.

    The body of those files is either duplicated in
    regulation/{REG}/aggregated/ (01_SO, 02_SR) or purely narrative
    (00_README, 03_validation, 04_deduction). Frontmatter alone is
    enough for audit.
    """
    if not REG_ROOT.is_dir():
        pytest.skip("preproc_out not built")
    # Path: regulation/{REG}/_root/*.json → 3 levels under REG_ROOT
    raw_root = list(REG_ROOT.glob("*/_root/*.json"))
    if not raw_root:
        pytest.skip("no regulation/_root/ shards")
    bad = []
    for p in raw_root:
        d = json.loads(p.read_text())
        if "raw_md" in d:
            bad.append(str(p.relative_to(PREPROC_OUT)))
    assert not bad, f"regulation/_root/ has raw_md (should be dropped): {bad[:5]}"


def test_regulation_root_keys() -> None:
    """regulation/_root/ shards must keep frontmatter + standard fields."""
    if not REG_ROOT.is_dir():
        pytest.skip("preproc_out not built")
    sample = next(REG_ROOT.glob("*/_root/*.json"), None)
    if sample is None:
        pytest.skip("no regulation/_root/ shards")
    d = json.loads(sample.read_text())
    expected_keys = {
        "schema_version",
        "source",
        "doc_id",
        "title",
        "status",
        "chain_version",
        "frontmatter",
    }
    assert set(d.keys()) == expected_keys, f"unexpected keys: {set(d.keys()) ^ expected_keys}"


# ─── v9 invariant: raw_md is allowed in the catch-all dirs ──────────────


@pytest.mark.parametrize("allowed_dir", sorted(RAW_MD_ALLOWED_DIRS))
def test_raw_md_allowed_dirs(allowed_dir: str) -> None:
    """The catch-all dirs SHOULD carry raw_md (no structured counterpart)."""
    if not (PREPROC_OUT / allowed_dir).is_dir():
        pytest.skip(f"{allowed_dir}/ not built")
    files = list((PREPROC_OUT / allowed_dir).rglob("*.json"))
    assert files, f"no files in {allowed_dir}/"
    with_raw = [p for p in files if "raw_md" in json.loads(p.read_text())]
    # Most files in these dirs should have raw_md (NIST_CSF_2.0
    # subcategories is the only structured global, and a few csfs may
    # not have raw_md, so we just require a healthy majority)
    ratio = len(with_raw) / len(files)
    assert ratio > 0.5, (
        f"{allowed_dir}/: only {len(with_raw)}/{len(files)} ({ratio:.0%}) "
        f"have raw_md — expected most to (catch-all parser)"
    )


def test_global_nist_csf_no_raw_md() -> None:
    """The CSF 2.0 aggregated JSON is fully structured (no raw_md)."""
    p = PREPROC_OUT / "global" / "NIST_CSF_2.0_subcategories.json"
    if not p.is_file():
        pytest.skip("aggregated CSF file missing")
    d = json.loads(p.read_text())
    assert "raw_md" not in d, "NIST_CSF_2.0_subcategories.json should be structured"


# ─── Sanity: aggregate raw_md count is well below v8's 109 ──────────────


def test_raw_md_count_below_v8_baseline() -> None:
    """v8 had 109 files with raw_md. v9 should have ~84 (the 25
    regulation/_root/ files are dropped)."""
    if not PREPROC_OUT.is_dir():
        pytest.skip("preproc_out not built")
    n_with = 0
    for p in PREPROC_OUT.rglob("*.json"):
        d = json.loads(p.read_text())
        if "raw_md" in d:
            n_with += 1
    assert n_with < 109, f"raw_md count {n_with} >= 109 (v8 baseline) — v9 dropped nothing?"
    # Should be exactly 84 (or close, depending on whether other tests
    # run add new files)
    assert n_with <= 90, (
        f"raw_md count {n_with} too high — expected ~84 after dropping "
        f"regulation/_root/ (25 files)"
    )
