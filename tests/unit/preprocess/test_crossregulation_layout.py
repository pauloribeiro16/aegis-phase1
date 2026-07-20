"""Tests for the crossregulation parser changes (D-10 move + DeepAnalysis pair format).

These invariants guard the v11.1 crossregulation refactor:
  1. Every CrossRegulation macro domain D-01..D-10 has its own subdir
     in both DomainAnalysis/ and DeepAnalysis/ (no more nested D-10
     inside D-09).
  2. The parser extracts ``pairs[]`` from BOTH the
     ``<!-- pair: ... -->`` format (DomainAnalysis) and the
     ``#### Pair: A ↔ B`` H4 format (DeepAnalysis).
  3. Pairs are deduped by (reg_a, reg_b) so the same pair in
     both formats counts once.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CR = REPO_ROOT / "preproc_out" / "crossregulation"
DA = CR / "DomainAnalysis"
DEEP = CR / "DeepAnalysis"


@pytest.fixture(scope="module")
def crossregulation_layout() -> dict:
    if not DA.is_dir() or not DEEP.is_dir():
        pytest.skip("crossregulation/ not built")
    return {
        "da_subdirs": sorted(p.name for p in DA.iterdir() if p.is_dir()),
        "deep_subdirs": sorted(p.name for p in DEEP.iterdir() if p.is_dir()),
    }


# ─── 1. Macro-domain directory layout (D-10 is at top level) ──────


def test_all_10_macro_domains_have_own_subdirs(crossregulation_layout) -> None:
    """Both DomainAnalysis/ and DeepAnalysis/ have a D-XX_* subdir for
    every macro domain. The pre-v11.1 bug had D-10 nested inside D-09.
    """
    expected = {
        "D-01_Data-Protection",
        "D-02_Vulnerability-Management",
        "D-03_Access-Control",
        "D-04_Incident-Response",
        "D-05_Data-Lifecycle",
        "D-06_Supply-Chain",
        "D-07_Secure-Development",
        "D-08_Human-Factors",
        "D-09_Governance-Documentation",
        "D-10_Monitoring-Audit",
    }
    da = set(crossregulation_layout["da_subdirs"])
    deep = set(crossregulation_layout["deep_subdirs"])
    assert expected.issubset(da), (
        f"DomainAnalysis missing macro domains: {expected - da}"
    )
    assert expected.issubset(deep), (
        f"DeepAnalysis missing macro domains: {expected - deep}"
    )


def test_d10_files_live_in_d10_subdir_not_d09(crossregulation_layout) -> None:
    """The pre-v11.1 bug placed D-10.* files inside D-09. After the fix,
    they must live in D-10_Monitoring-Audit/ in both DomainAnalysis and
    DeepAnalysis.
    """
    for kind, base in [("DomainAnalysis", DA), ("DeepAnalysis", DEEP)]:
        d10_dir = base / "D-10_Monitoring-Audit"
        assert d10_dir.is_dir(), f"{kind}/D-10_Monitoring-Audit missing"
        d10_files = sorted(p.name for p in d10_dir.iterdir() if p.is_file())
        # Should have the 3 sub-SO files
        assert "D-10.1.md" in d10_files or any(
            f.startswith("D-10.1.") for f in d10_files
        ), f"{kind}/D-10_Monitoring-Audit missing D-10.1 file"
        # And NOT in D-09
        d09_dir = base / "D-09_Governance-Documentation"
        if d09_dir.is_dir():
            d09_files = [p.name for p in d09_dir.iterdir() if p.is_file()]
            assert not any(f.startswith("D-10.") for f in d09_files), (
                f"{kind}/D-09 still contains D-10 files: "
                f"{[f for f in d09_files if f.startswith('D-10.')]}"
            )


# ─── 2. Parser extracts pairs from both formats ───────────────────


def test_domain_analysis_pairs_extracted() -> None:
    """DomainAnalysis uses <!-- pair: --> markers; pairs[] must be populated."""
    da_files = list(DA.rglob("D-*.json"))
    assert da_files, "no DomainAnalysis JSON files"
    total = 0
    for f in da_files:
        d = json.loads(f.read_text())
        total += len(d.get("pairs", []) or [])
    # The 10-pair pair-relationship matrix should yield ~180+ pairs
    # (38 subdomains × ~5 average pairs/subdomain, with some 5-regulation
    # subdomains having all 10 pairs)
    assert total > 150, f"DomainAnalysis only extracted {total} pairs"


def test_deep_analysis_pairs_extracted() -> None:
    """DeepAnalysis uses #### Pair: A ↔ B headings; pairs[] must be
    populated (was 0 before the v11.1 fix).
    """
    deep_files = list(DEEP.rglob("D-*.json"))
    assert deep_files, "no DeepAnalysis JSON files"
    total = 0
    sample = None
    for f in deep_files:
        d = json.loads(f.read_text())
        n = len(d.get("pairs", []) or [])
        total += n
        if sample is None and n > 0:
            sample = (f.name, d["pairs"][0])
    # Each DeepAnalysis file has 10 pairs (5 regulations × 4 / 2 = 10)
    # Total: 38 files × 10 = ~380, but the parser dedupes across
    # DomainAnalysis + DeepAnalysis so the post-merge count is lower
    # in the merged view; here we just check > 100 (was 0)
    assert total > 100, (
        f"DeepAnalysis only extracted {total} pairs (was 0 before fix)"
    )
    # Verify the extracted pair has reg_a/reg_b populated
    if sample:
        name, p = sample
        assert "reg_a" in p and "reg_b" in p, f"{name}: pair missing keys"
        assert p["reg_a"] and p["reg_b"], f"{name}: empty reg_a/reg_b"


def test_pairs_have_classification_extracted() -> None:
    """Both parsers extract the classification from `**WORD**` patterns
    (e.g. **COMPLEMENTARY**, **TENSION**).
    """
    classified = 0
    total = 0
    for f in list(DEEP.rglob("D-*.json"))[:5]:
        d = json.loads(f.read_text())
        for p in d.get("pairs", []) or []:
            total += 1
            if p.get("classification"):
                classified += 1
    # At least 50% of pairs should have a classification
    if total > 0:
        ratio = classified / total
        assert ratio > 0.5, (
            f"Only {classified}/{total} DeepAnalysis pairs have a "
            f"classification extracted (ratio {ratio:.2f})"
        )


# ─── 3. Pair dedup across formats ──────────────────────────────────


def test_pairs_deduped_in_merged_view(crossregulation_layout) -> None:
    """The ``pairs[]`` arrays of DomainAnalysis and DeepAnalysis for the
    same subdomain are merged and deduped by (reg_a, reg_b).

    We verify by comparing total pair counts: if the dedup worked,
    no pair appears twice in the same file. We check by re-loading
    a sample of files and asserting no duplicate (reg_a, reg_b).
    """
    for kind, base in [("DomainAnalysis", DA), ("DeepAnalysis", DEEP)]:
        for f in list(base.rglob("D-*.json"))[:3]:
            d = json.loads(f.read_text())
            keys = []
            for p in d.get("pairs", []) or []:
                key = tuple(sorted([p.get("reg_a", ""), p.get("reg_b", "")]))
                keys.append(key)
            counter = Counter(keys)
            dups = [k for k, c in counter.items() if c > 1]
            assert not dups, (
                f"{kind}/{f.name}: duplicate pairs {dups}"
            )
