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
    """Load all subdomain entities from the by-D-XX layout.

    CORR-031 v11: shards live under ``entities/subdomains/D-XX/*.json``.
    We recurse one level deep (the D-XX subfolders) so the fixture
    picks up every D-XX.Y regardless of its parent. The ``_root/`` and
    ``_archive/`` subbuckets (if present) are skipped — those are
    pre-v11 leftovers or intentional archives.
    """
    out: dict[str, dict] = {}
    for p in SUBDOMAINS_DIR.rglob("D-*.json"):
        if any(part in p.parts for part in ("_root", "_archive", "_no_subdomain")):
            continue
        with p.open() as f:
            d = json.load(f)
        out[d["id"]] = d
    return out


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
    # CORR-029c: the audit now classifies coverage gaps as
    # coverage_partial and coverage_unresolved (was coverage_mismatches).
    assert "coverage_partial" in audit_report
    assert "coverage_unresolved" in audit_report


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

    CORR-030 (2026-07-20): the 2 (reg, sub) pairs that remained orphans
    after CORR-029's parser fix (AI_Act D-07.3, NIS2 D-01.2) are now
    resolved by CORR-030 phantom sub-SO propagation. So both the raw
    and the justified list are now empty.
    """
    sr_no_so = audit_report["sr_without_so"]
    # The raw orphans list should be empty
    assert sr_no_so["count"] == 0, (
        f"unexpected un-justified SR-without-SO pairs: "
        f"{[(i['regulation'], i['subdomain']) for i in sr_no_so['items']]}"
    )
    # CORR-030: the previously justified orphans are now resolved by
    # phantoms, so the justified list is also empty.
    assert sr_no_so.get("justified_count", 0) == 0, (
        f"expected 0 justified orphans after CORR-030, got {sr_no_so.get('justified_count', 0)}"
    )


def test_known_so_without_sr_justified(audit_report: dict) -> None:
    """The 8 SOs without SRs are documented with per-regulation justifications
    in the source MDs (CORR-029).

    The 8 (reg, sub) pairs were:
      D-03.2 GDPR, D-03.2 CRA, D-07.2 DORA, D-07.3 NIS2, D-07.3 CRA,
      D-09.3 CRA, D-09.4 DORA, D-09.4 AI_Act
    """
    so_no_sr = audit_report["so_without_sr"]
    # Raw un-justified orphans should be 0
    assert so_no_sr["count"] == 0, (
        f"unexpected un-justified SO-without-SR pairs: "
        f"{[(i['regulation'], i['subdomain']) for i in so_no_sr['items']]}"
    )
    # The justified list should have exactly 8 (the 8 known)
    assert so_no_sr.get("justified_count", 0) == 8, (
        f"expected 8 justified SO-without-SR pairs, got {so_no_sr.get('justified_count', 0)}"
    )


# ─── CORR-029c: coverage gaps detailed report ────────────────────────


def test_coverage_gaps_documented(audit_report: dict) -> None:
    """CORR-029c: the coverage gaps (partial + unresolved) are documented in
    the report and deferred to CORR-030 (per user decision).

    We do not assert zero gaps here (the user explicitly chose to defer).
    We do assert that the report has the structure to enumerate them
    so CORR-030 can pick up the work.
    """
    assert "coverage_partial" in audit_report
    assert "coverage_unresolved" in audit_report

    partial = audit_report["coverage_partial"]
    assert "count" in partial
    assert "items" in partial
    assert "by_pattern" in partial
    if partial["items"]:
        first = partial["items"][0]
        assert "sr_id" in first
        assert "sub_domain" in first
        assert "linked_objectives" in first
        assert "so_covered_subdomains" in first
        assert "extras" in first
        assert "pattern" in first
        assert first["pattern"] in ("multi_subdomain", "so_narrower")

    unresolved = audit_report["coverage_unresolved"]
    assert "distinct_unresolved" in unresolved
    if unresolved["distinct_unresolved"]:
        first = unresolved["distinct_unresolved"][0]
        assert "regulation" in first
        assert "so_id" in first
        assert "referenced_by_srs" in first
        assert "reference_count" in first


def test_known_gaps_deferred_to_corr_030(audit_report: dict) -> None:
    """The coverage gaps are explicitly deferred to CORR-030 with the
    user decision captured for the audit trail.
    """
    gaps = audit_report["known_gaps"]
    assert gaps["deferred_to"] == "CORR-030"
    # The user decision is captured
    assert "user_decision" in gaps
    assert "2026-07-20" in gaps["user_decision"]
    # And the user explicitly chose "defer_audit"
    assert "defer" in gaps["user_decision"].lower() or "audit" in gaps["user_decision"].lower()


def test_coverage_classification_invariants(audit_report: dict) -> None:
    """Invariants on the coverage classification:
    - every SR falls into exactly one of full / partial / unresolved
    - the count of each is consistent with the items length
    - the partial items have a 'pattern' field
    - the unresolved items have unresolved_los (not sub_domain mismatch)
    """
    t = audit_report["totals"]
    partial = audit_report["coverage_partial"]
    unresolved = audit_report["coverage_unresolved"]
    total_srs = t["srs_total"]
    # Sum of categories must equal total SRs
    assert (
        t["coverage_full"] + len(partial["items"]) + len(unresolved["items"])
        == total_srs
    )
    # Count fields must match items length
    assert partial["count"] == len(partial["items"])
    assert unresolved["count"] == len(unresolved["items"])
    # The pattern counts should sum to the items count
    if partial["by_pattern"]:
        assert sum(partial["by_pattern"].values()) == len(partial["items"])
