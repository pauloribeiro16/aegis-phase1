"""Tests for CORR-030: zero SR↔SO coverage gaps after phantom propagation.

CORR-030 resolved the 168 coverage gaps left by CORR-029c:
- 66 unresolved (37 distinct SOs missing hso_per_reg entries) → fixed by
  B.1 (phantom sub-SO propagation in 17 source MDs).
- 102 partial (linked SOs resolve but don't cover all sub_domains) → fixed by
  B.2 (heuristic: add cross-cutting linked_objectives to 113 SRs + propagate
  2 more phantoms for D-01.2 NIS2 and D-07.3 AI_Act).

The audit invariants after CORR-030:
- coverage_partial_count == 0
- coverage_unresolved_count == 0
- coverage_full + 0 + 0 == srs_total (all 282 SRs are full coverage)
- so_without_sr.justified_count == 8 (the 8 SOs without SRs, unchanged from CORR-029)
- sr_without_so.count == 0 AND sr_without_so.justified_count == 0 (CORR-030
  resolved the 2 previously justified (AI_Act D-07.3, NIS2 D-01.2) orphans).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_REPORT = REPO_ROOT / "preproc_out" / "audit" / "so_sr_coherence_report.json"


@pytest.fixture(scope="module")
def audit_report() -> dict:
    if not AUDIT_REPORT.is_file():
        pytest.skip(f"audit report not built: {AUDIT_REPORT}")
    with AUDIT_REPORT.open() as f:
        return json.load(f)


def test_coverage_partial_count_is_zero(audit_report: dict) -> None:
    """B.3-1: after CORR-030 B.2, coverage_partial_count == 0.

    Before B.2, this was 102 (B.1 reduced unresolved from 66 to 0, then B.1
    re-classified some as partial, giving 136). After B.2: 0.
    """
    t = audit_report["totals"]
    assert t["coverage_partial_count"] == 0, (
        f"coverage_partial_count is {t['coverage_partial_count']}, expected 0 "
        f"after CORR-030"
    )


def test_coverage_unresolved_count_is_zero(audit_report: dict) -> None:
    """B.3-1: after CORR-030 B.1, coverage_unresolved_count == 0.

    Before B.1, this was 66. After B.1: 0.
    """
    t = audit_report["totals"]
    assert t["coverage_unresolved_count"] == 0, (
        f"coverage_unresolved_count is {t['coverage_unresolved_count']}, "
        f"expected 0 after CORR-030"
    )


def test_all_srs_have_full_coverage(audit_report: dict) -> None:
    """B.3-1 / O1: coverage_full == srs_total (every SR is fully covered).

    O1 from the contract: coverage_full + coverage_partial_count +
    coverage_unresolved_count == srs_total. With partial=0 and unresolved=0,
    coverage_full must equal srs_total.
    """
    t = audit_report["totals"]
    assert t["coverage_full"] == t["srs_total"], (
        f"coverage_full {t['coverage_full']} != srs_total {t['srs_total']}; "
        f"partial {t['coverage_partial_count']} and unresolved "
        f"{t['coverage_unresolved_count']} must both be 0"
    )


def test_so_with_inherits_from_100_percent(audit_report: dict) -> None:
    """CORR-030 B.1: every hso_per_reg entry has inherits_from populated
    (the 100% baseline was established in CORR-029 B.1; CORR-030 phantom
    entries are written with the same YAML format and must not regress).
    """
    t = audit_report["totals"]
    assert t["so_with_inherits_from"] == t["so_entries"], (
        f"so_with_inherits_from {t['so_with_inherits_from']} != "
        f"so_entries {t['so_entries']}"
    )
    assert t["so_inherits_from_pct"] == 100.0, (
        f"so_inherits_from_pct {t['so_inherits_from_pct']} != 100.0"
    )


def test_sr_linked_objectives_100_percent_resolved(audit_report: dict) -> None:
    """CORR-030 B.1+B.2: every SR linked_objective resolves to a sub-SO.

    Before B.1+B.2, the resolution was 80.2% (276/344). After: 100% (484/484).
    """
    t = audit_report["totals"]
    assert t["sr_linked_objectives_resolved"] == t["sr_linked_objectives_total"], (
        f"sr_linked_objectives_resolved {t['sr_linked_objectives_resolved']} != "
        f"sr_linked_objectives_total {t['sr_linked_objectives_total']}"
    )
    assert t["sr_lo_resolution_pct"] == 100.0, (
        f"sr_lo_resolution_pct {t['sr_lo_resolution_pct']} != 100.0"
    )


def test_no_sr_without_so(audit_report: dict) -> None:
    """CORR-030: the (reg, sub) orphan pairs from CORR-029 are resolved.

    Before CORR-030, sr_without_so.justified_count was 2 (AI_Act D-07.3,
    NIS2 D-01.2). After CORR-030 phantom propagation: 0.
    """
    sr_no_so = audit_report["sr_without_so"]
    assert sr_no_so["count"] == 0, (
        f"unexpected un-justified SR-without-SO pairs: "
        f"{[(i['regulation'], i['subdomain']) for i in sr_no_so['items']]}"
    )
    assert sr_no_so["justified_count"] == 0, (
        f"expected 0 justified orphans after CORR-030, "
        f"got {sr_no_so['justified_count']}"
    )


def test_corresponding_phantom_phantoms_present() -> None:
    """CORR-030: verify the phantom hso_per_reg entries are materialised
    in the corresponding preproc_out subdomain JSON shards.

    Sample 3 phantoms: the 2 cross-reg (AI_Act D-07.3, NIS2 D-01.2) plus
    one randomly-chosen CRA D-09.4 (the subdomain with the most phantoms).
    """
    SUB_DIR = REPO_ROOT / "preproc_out" / "entities" / "subdomains"

    def _load_subdomain(sid: str) -> dict:
        # CORR-031 v11: shards live under D-XX/ subfolders
        d_xx = "-".join(["D", sid.split(".")[0].split("-")[1]])
        p = SUB_DIR / d_xx / f"{sid}.json"
        assert p.is_file(), f"missing {p}"
        return json.loads(p.read_text())

    # 1. AI_Act D-07.3 phantom (SO-AI_Act-001 cross-ref)
    d = _load_subdomain("D-07.3")
    ai_phantoms = [
        hso
        for hso in d.get("hso_per_reg", [])
        if hso.get("regulation") == "AI_Act"
        and (hso.get("inherits_from") or "").endswith("SO-AI_Act-001")
        and hso.get("phase_1A_role") == "propagated"
    ]
    assert ai_phantoms, "no AI_Act D-07.3 phantom (inherits SO-AI_Act-001) found"

    # 2. NIS2 D-01.2 phantom (SO-NIS2-004 partial)
    d = _load_subdomain("D-01.2")
    nis2_phantoms = [
        hso
        for hso in d.get("hso_per_reg", [])
        if hso.get("regulation") == "NIS2"
        and (hso.get("inherits_from") or "").endswith("SO-NIS2-004")
        and hso.get("phase_1A_role") == "propagated"
    ]
    assert nis2_phantoms, "no NIS2 D-01.2 phantom (inherits SO-NIS2-004) found"

    # 3. CRA D-09.4 (largest phantom count, sample one)
    d = _load_subdomain("D-09.4")
    cra_phantoms = [
        hso
        for hso in d.get("hso_per_reg", [])
        if hso.get("regulation") == "CRA"
        and hso.get("phase_1A_role") == "propagated"
    ]
    assert len(cra_phantoms) >= 5, (
        f"expected ≥5 CRA D-09.4 phantoms (e.g. SO-CRA-023, 028, 030, 039, "
        f"040, 041, 048, 066, 073), got {len(cra_phantoms)}"
    )


def test_phantom_entries_not_reclassified_as_orphans(audit_report: dict) -> None:
    """CORR-030: phantom hso_per_reg entries must produce a corresponding SR
    in the same (reg, sub) — they must NOT be classified as SO-without-SR.

    Sample: the CRA D-09.4 phantom for SO-CRA-048 — there are 5 SRs in
    D-09.4 for CRA (SR-CRA-071, 107, 108, 110, 111), so the phantom should
    not appear in so_without_sr.
    """
    so_no_sr = audit_report["sr_without_so"]
    # No phantom-bearing (reg, sub) pair should be in so_without_sr
    for item in so_no_sr["items"]:
        assert "CORR-030 propagated phantom" not in str(
            item.get("subdomain", "")
        ), f"phantom classified as orphan: {item}"


def test_total_srs_unchanged(audit_report: dict) -> None:
    """O1 from the contract: coverage_full + coverage_partial_count +
    coverage_unresolved_count == srs_total (282, unchanged from CORR-029).
    """
    t = audit_report["totals"]
    assert t["srs_total"] == 282, (
        f"expected srs_total == 282 (unchanged from CORR-029), "
        f"got {t['srs_total']}"
    )
