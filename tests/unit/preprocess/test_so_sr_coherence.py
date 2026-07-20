"""Tests for SO↔SR structural coherence (CORR-029).

Validates the invariants:
  1. `inherits_from` is populated in 100% of `hso_per_reg[]` entries
  2. SR `linked_objectives` resolve to a known SO via the inherits_from bridge
     at rate ≥ 30% (the remaining 70% are SOs without SRs, deferred to CORR-030)
  3. The 4 real orphan (reg, sub) pairs are documented (not silently fixed —
     they need a contract decision)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PREPROC_OUT = REPO_ROOT / "preproc_out"
SUBDOMAINS_DIR = PREPROC_OUT / "entities" / "subdomains"
REG_DIR = PREPROC_OUT / "regulation"
AUDIT_REPORT = PREPROC_OUT / "audit" / "so_sr_coherence_report.json"


@pytest.fixture(scope="module")
def audit_report() -> dict:
    if not AUDIT_REPORT.is_file():
        pytest.skip(f"audit report not built: {AUDIT_REPORT}")
    with AUDIT_REPORT.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def subdomains() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in SUBDOMAINS_DIR.glob("D-*.json"):
        with p.open() as f:
            out[p.stem.replace("D-", "D-")] = json.load(f)
    # Wait — that's wrong. Let me fix it.
    return {p.stem: json.loads(p.read_text()) for p in SUBDOMAINS_DIR.glob("D-*.json")}


def test_inherits_from_populated_in_100_percent(subdomains: dict[str, dict]) -> None:
    """CORR-029 B.1: every hso_per_reg entry must have inherits_from populated.

    Before the fix, this was 0% because the unquoted verified_relationship
    broke yaml.safe_load.
    """
    total = 0
    populated = 0
    for sid, sd in subdomains.items():
        for hso in sd.get("hso_per_reg", []):
            total += 1
            if hso.get("inherits_from"):
                populated += 1
    assert total > 0, "no hso_per_reg entries found"
    assert populated == total, (
        f"inherits_from populated: {populated}/{total} " f"(expected 100% after CORR-029 fix)"
    )


def test_audit_report_exists(audit_report: dict) -> None:
    """B.5: the audit tool produces a structured report."""
    assert "totals" in audit_report
    assert "so_without_sr" in audit_report
    assert "sr_without_so" in audit_report
    assert "coverage_mismatches" in audit_report


def test_audit_totals(audit_report: dict) -> None:
    """B.5: the audit report has the expected totals."""
    t = audit_report["totals"]
    assert t["subdomains"] == 38, f"expected 38 subdomains, got {t['subdomains']}"
    assert t["so_with_inherits_from"] == t["so_entries"], (
        f"so_with_inherits_from {t['so_with_inherits_from']} != " f"so_entries {t['so_entries']}"
    )
    # Resolution rate must be > 30% (was 0.2% before fix)
    assert t["sr_lo_resolution_pct"] >= 30, (
        f"SR linked_objectives resolution {t['sr_lo_resolution_pct']}% is "
        f"< 30% — bridge may still be broken"
    )


def test_no_silent_orphan_creation(audit_report: dict) -> None:
    """B.4: the orphan (reg, sub) pairs must be documented (justified) in the
    source MDs / JSON shards, not silently created.

    The 4 (reg, sub) pairs (AI_Act D-07.3, CRA D-08.1, CRA D-08.2, NIS2 D-01.2)
    are intentional partial-coverage or out-of-scope cross-refs (per the
    source MDs). They are documented in each subdomain's
    `orphan_sr_justifications` field. The audit must classify them as
    'justified', not as raw orphans.
    """
    sr_no_so = audit_report["sr_without_so"]
    # The raw orphans list should be empty (or very small — only new cases
    # that haven't been justified yet).
    assert sr_no_so["count"] == 0, (
        f"unexpected un-justified SR-without-SO pairs: "
        f"{[(i['regulation'], i['subdomain']) for i in sr_no_so['items']]}"
    )
    # And the justified list should have at least 4 entries (the 4 known)
    assert (
        sr_no_so.get("justified_count", 0) >= 4
    ), f"expected ≥4 justified orphans, got {sr_no_so.get('justified_count', 0)}"


def test_known_so_without_sr_deferred(audit_report: dict) -> None:
    """8 SOs without SRs are deferred to CORR-030 and must be documented."""
    so_no_sr = audit_report["so_without_sr"]
    known = audit_report["known_gaps"]
    # The 8 known items
    expected_count = 8
    assert so_no_sr["count"] == expected_count, (
        f"expected {expected_count} SO-without-SR items, got {so_no_sr['count']}. "
        f"Either the orphans grew (need new contract) or shrank (good — they got SRs)."
    )
    # The known_gaps section must reference CORR-030
    assert known.get("deferred_to") == "CORR-030"
