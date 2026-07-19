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


# ─── v10 invariants: zero-loss + structured extraction ────────────────


@pytest.mark.parametrize(
    "shard_path",
    [
        "ambiguity_analysis/00_Index.json",
        "ambiguity_analysis/01_Framework.json",
        "global/TEMPLATE_subagent_brief.json",
        "global/README.json",
        "crossregulation/DomainAnalysis/index.json",
        "crossregulation/DeepAnalysis/index.json",
        "crossregulation/_templates/TEMPLATE_crossreg_brief.json",
    ],
)
def test_v10_shard_has_structured_fields(shard_path: str) -> None:
    """Each Fase 1 file must have BOTH the raw_md (verbatim) AND
    structured fields extracted by the typed parser."""
    p = PREPROC_OUT / shard_path
    if not p.is_file():
        pytest.skip(f"{shard_path} not built")
    d = json.loads(p.read_text())
    # raw_md must be present (zero-loss invariant)
    assert "raw_md" in d, f"{shard_path} lost raw_md"
    assert d["raw_md"], f"{shard_path} raw_md is empty"
    # At least 1 structured field beyond the catch-all schema
    structured_keys = {
        "regulations", "scope", "lens", "layer", "sections",
        "constraints", "mission", "supporting_files", "source_lens",
        "relationship_taxonomy", "preserved_tags", "workflow_steps",
    }
    found = structured_keys & set(d.keys())
    assert found, (
        f"{shard_path} has no structured fields beyond the catch-all schema"
    )


def test_v10_zero_loss_invariant() -> None:
    """Zero-loss invariant: every Fase 1 file's raw_md is preserved
    verbatim in the structured fields (or as the raw_md itself).

    This test reads the SOURCE .md from methodology-00 and compares
    the body to the raw_md field in the JSON. They MUST match.
    """
    pairs = [
        (
            PREPROC_OUT / "ambiguity_analysis/00_Index.json",
            "methodology-00/PREPROCESSING/AMBIGUITY_ANALYSIS/00_Index.md",
        ),
        (
            PREPROC_OUT / "ambiguity_analysis/01_Framework.json",
            "methodology-00/PREPROCESSING/AMBIGUITY_ANALYSIS/01_Framework.md",
        ),
        (
            PREPROC_OUT / "global/TEMPLATE_subagent_brief.json",
            "methodology-00/PREPROCESSING/TEMPLATE_subagent_brief.md",
        ),
        (
            PREPROC_OUT / "global/README.json",
            "methodology-00/PREPROCESSING/README.md",
        ),
        (
            PREPROC_OUT / "crossregulation/DomainAnalysis/index.json",
            "methodology-00/PREPROCESSING/CrossRegulation/DomainAnalysis/index.md",
        ),
        (
            PREPROC_OUT / "crossregulation/DeepAnalysis/index.json",
            "methodology-00/PREPROCESSING/CrossRegulation/DeepAnalysis/index.md",
        ),
        (
            PREPROC_OUT / "crossregulation/_templates/TEMPLATE_crossreg_brief.json",
            "methodology-00/PREPROCESSING/CrossRegulation/TEMPLATE_crossreg_brief.md",
        ),
    ]
    for json_p, src_p in pairs:
        if not (json_p.is_file() and Path(src_p).is_file()):
            continue
        d = json.loads(json_p.read_text())
        text = Path(src_p).read_text(encoding="utf-8")
        from scripts.preprocess.parsers.frontmatter import parse_frontmatter
        _, src_body = parse_frontmatter(text)
        json_raw = d.get("raw_md", "")
        assert src_body.strip() == json_raw.strip(), (
            f"{json_p.name}: raw_md in JSON does not match source body. "
            f"DIFF: source len={len(src_body)}, json len={len(json_raw)}"
        )


def test_v10_hso_keeps_raw_md_with_reason() -> None:
    """The HSO file is the only global/ file that keeps raw_md with
    an explicit reason (it's pure design rationale)."""
    p = PREPROC_OUT / "global/00_Hierarchical_SecurityObjectives.json"
    if not p.is_file():
        pytest.skip("HSO file missing")
    d = json.loads(p.read_text())
    assert "raw_md" in d, "HSO should keep raw_md (no structured form)"
    assert d.get("raw_md_kept_reason") == "narrative_design_rationale_no_structured_form", (
        f"HSO must declare why raw_md is kept: {d.get('raw_md_kept_reason')}"
    )
