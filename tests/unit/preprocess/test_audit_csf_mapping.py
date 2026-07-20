"""Unit tests for the audit_csf_mapping.py tool (CORR-027, Phase 3).

Covers C7, C8, C9 from the contract:
  - C7: preproc_out/audit/csf_mapping_report.json has 38 rows
  - C8: D-10.1 row matches a known groundtruth (hint count, verdict)
  - C9: orphan detection works (synth a fake subdomain with a bad ID)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PREPROC_OUT = REPO_ROOT / "preproc_out"
AUDIT_REPORT = PREPROC_OUT / "audit" / "csf_mapping_report.json"
TOOL = REPO_ROOT / "scripts" / "preprocess" / "audit_csf_mapping.py"


@pytest.fixture(scope="module")
def report() -> dict:
    if not AUDIT_REPORT.is_file():
        pytest.skip(
            f"{AUDIT_REPORT} not present — run "
            "`python -m scripts.preprocess.audit_csf_mapping` first"
        )
    return json.loads(AUDIT_REPORT.read_text())


# ─── C7: report structure ─────────────────────────────────────────────


def test_report_has_38_subdomain_rows(report: dict) -> None:
    """C7: the report has exactly 38 rows (one per AEGIS subdomain)."""
    assert report["subdomain_count"] == 38
    assert len(report["rows"]) == 38


def test_report_top_level_keys(report: dict) -> None:
    """Schema sanity: top-level keys are present."""
    required = {
        "schema_version",
        "built_at",
        "frozen_list_source",
        "frozen_list_id_count",
        "subdomain_count",
        "summary",
        "rows",
    }
    assert required <= set(report.keys())


def test_report_frozen_list_count_is_106(report: dict) -> None:
    """The frozen list behind the audit has 106 IDs (matches xlsx)."""
    assert report["frozen_list_id_count"] == 106


def test_report_summary_keys(report: dict) -> None:
    """Summary has the canonical keys."""
    required = {
        "subdomains_with_empty_csf_hint",
        "subdomains_with_empty_sr_csf_mapping",
        "orphan_csf_in_hint_total",
        "subdomains_with_orphan",
        "verdict_counts",
    }
    assert required <= set(report["summary"].keys())


def test_report_rows_have_canonical_fields(report: dict) -> None:
    """Every row has the contract §4.2 canonical fields."""
    required = {
        "subdomain_id",
        "title",
        "participating_regulations",
        "csf_hint_count",
        "csf_hint_ids",
        "sr_csf_mapping_total",
        "sr_csf_mapping_empty",
        "orphan_csf_in_hint",
        "expected_families",
        "expected_families_missing",
        "audit_verdict",
    }
    for row in report["rows"]:
        assert required <= set(row.keys()), (
            f"{row.get('subdomain_id')} missing fields: {required - set(row.keys())}"
        )


# ─── C8: D-10.1 groundtruth ───────────────────────────────────────────


def test_d10_1_groundtruth(report: dict) -> None:
    """C8: D-10.1 has a known shape (Logging & Monitoring).

    The D-10.1 shard has 2 csf_hint IDs (PR.PS-04, DE.CM-09 from
    the .md cross-reference) and 5 SRs. The csf_hint count is 2
    (< 4 = SPARSE threshold), so the verdict should be SPARSE.
    """
    d101 = next(r for r in report["rows"] if r["subdomain_id"] == "D-10.1")
    assert d101["title"]  # non-empty
    assert d101["csf_hint_count"] == 2
    assert d101["csf_hint_ids"] == ["PR.PS-04", "DE.CM-09"]
    assert d101["sr_csf_mapping_total"] == 5
    assert d101["sr_csf_mapping_empty"] == 0  # all 5 SRs have a CSF mapping
    assert d101["audit_verdict"] == "SPARSE"  # hint < 4 triggers SPARSE
    assert "PR.PS" in d101["expected_families"]
    assert "DE.CM" in d101["expected_families"]


# ─── C9: orphan detection ─────────────────────────────────────────────


def test_orphan_detection_synth(tmp_path: Path) -> None:
    """C9: synth a fake preproc_out with a subdomain whose csf_hint
    contains a FAKE-99 ID — the tool must flag it as BROKEN.
    """
    # Build a minimal fake preproc_out structure
    fake = tmp_path / "preproc_out"
    (fake / "entities" / "subdomains").mkdir(parents=True)
    (fake / "global").mkdir(parents=True)
    # Frozen list: the real one (106 IDs from xlsx)
    real_frozen = json.loads(
        (PREPROC_OUT / "global" / "NIST_CSF_2.0_subcategories.json").read_text()
    )
    (fake / "global" / "NIST_CSF_2.0_subcategories.json").write_text(
        json.dumps(real_frozen)
    )
    # Fake subdomain with a FAKE-99 in csf_hint
    fake_sd = {
        "schema_version": "1.0",
        "id": "D-99.9",
        "domain_id": "D-99",
        "title": "Synth SubDomain",
        "participating_regulations": ["GDPR"],
        "csf_hint": ["PR.DS-01", "FAKE-99"],  # FAKE-99 is not in the 106
        "security_requirements": [
            {"id": "SR-D-99.9.GDPR", "nist_csf_mapping": ["PR.DS-01"]}
        ],
    }
    (fake / "entities" / "subdomains" / "D-99.9.json").write_text(json.dumps(fake_sd))

    # Run the tool with --preproc-out pointing to the fake tree
    out_path = tmp_path / "audit.json"
    # Invoke the module
    cmd = [
        sys.executable,
        "-m",
        "scripts.preprocess.audit_csf_mapping",
        "--preproc-out",
        str(fake),
        "--output",
        str(out_path),
        "--quiet",
    ]
    result = subprocess.run(
        cmd, cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    assert result.returncode == 0, f"tool failed: {result.stderr}"
    report = json.loads(out_path.read_text())
    d999 = next(r for r in report["rows"] if r["subdomain_id"] == "D-99.9")
    assert d999["audit_verdict"] == "BROKEN", (
        f"synth subdomain with FAKE-99 should be BROKEN, got {d999['audit_verdict']}"
    )
    assert "FAKE-99" in d999["orphan_csf_in_hint"]


def test_orphan_count_matches_summary(report: dict) -> None:
    """orphan_csf_in_hint_total = sum of orphan list lengths across rows."""
    total = sum(len(r["orphan_csf_in_hint"]) for r in report["rows"])
    assert total == report["summary"]["orphan_csf_in_hint_total"]


def test_no_orphan_in_ok_rows(report: dict) -> None:
    """OK-verdict rows have empty orphan list (by definition)."""
    for r in report["rows"]:
        if r["audit_verdict"] == "OK":
            assert r["orphan_csf_in_hint"] == []


# ─── CORR-028 cleanup validation: known legacy IDs are NO LONGER orphans ─


def test_known_legacy_ids_no_longer_orphans(report: dict) -> None:
    """PR.DS-12 and RS.CO-04 were in the source .md cross-reference for
    D-05.* and D-04.3 respectively. They were NEVER in the official CSF 2.0
    106. CORR-028 removes them from all subdomains' csf_hint and from the
    cross-reference table in the .md.

    The audit must now report zero orphans.
    """
    orphan_ids: set[str] = set()
    for r in report["rows"]:
        orphan_ids.update(r["orphan_csf_in_hint"])
    assert orphan_ids == set(), (
        f"CORR-028 cleanup: expected zero orphans, saw: {orphan_ids}"
    )
    # And specifically, these known-legacy IDs must not appear
    legacy = {"PR.DS-12", "RS.CO-04"}
    assert not (orphan_ids & legacy), (
        f"CORR-028 cleanup: legacy IDs {legacy & orphan_ids} still flagged"
    )
