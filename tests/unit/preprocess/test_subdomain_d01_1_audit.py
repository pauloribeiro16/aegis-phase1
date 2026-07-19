"""D-01.1 audit fixes — validation tests (CORR-024 v11).

Tests the 3 manual fixes applied to D-01.1 (Data at Rest Encryption):

1. participating_regulations must be populated (was empty)
2. csf_hint must be expanded to 8 CSF 2.0 IDs (was 2)
3. nist_csf_mapping per-SR must be populated (was empty for all 4 SRs)

Plus: aggregated cross-reference row must mirror csf_hint.
Plus: every CSF ID in csf_hint must be valid (exist in CSF 2.0 official).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SD_SHARD = REPO_ROOT / "preproc_out" / "entities" / "subdomains" / "D-01.1.json"
AGGREGATED = REPO_ROOT / "preproc_out" / "global" / "NIST_CSF_2.0_subcategories.json"

# v11 expected values (validated by AEGIS-KG auditor 2026-07-19)
EXPECTED_PARTICIPATING = ["GDPR", "NIS2", "CRA", "DORA"]
EXPECTED_CSF_HINT = [
    "PR.DS-01",  # data-at-rest
    "PR.DS-10",  # data-in-use
    "PR.DS-11",  # backups
    "PR.AA-01",  # identity & credential mgmt (relevant to encryption key access)
    "PR.AA-05",  # access permissions policy (relevant to "who reads encrypted data")
    "ID.AM-08",  # systems/data inventory (relevant to "what to encrypt")
    "GV.RM-04",  # risk tolerance (cited in source)
    "DE.CM-09",  # monitoring of computing/data (runtime)
]
EXPECTED_SR_CSF = {
    # SR id → expected CSF mapping (min. 1 CSF ID each)
    "D-01.1.1.1": ["PR.DS-01"],  # Personal data at rest (GDPR)
    "D-01.1.1.2": ["PR.DS-01"],  # NIS scope data at rest (NIS2)
    "D-01.1.1.3": ["PR.DS-01"],  # Product data at rest (CRA)
    "D-01.1.1.4": ["PR.DS-01"],  # Financial-entity ICT data at rest (DORA)
}


def test_d011_participating_regulations() -> None:
    """participating_regulations must list the 4 active regulations."""
    if not SD_SHARD.is_file():
        pytest.skip("D-01.1 shard missing")
    d = json.loads(SD_SHARD.read_text())
    assert d["participating_regulations"] == EXPECTED_PARTICIPATING, (
        f"got {d['participating_regulations']}, " f"expected {EXPECTED_PARTICIPATING}"
    )


def test_d011_csf_hint_expanded() -> None:
    """csf_hint must contain exactly the 8 CSF 2.0 IDs."""
    if not SD_SHARD.is_file():
        pytest.skip("D-01.1 shard missing")
    d = json.loads(SD_SHARD.read_text())
    csf_hint = sorted(d["csf_hint"])
    expected = sorted(EXPECTED_CSF_HINT)
    assert csf_hint == expected, f"got {csf_hint}, expected {expected}"


def test_d011_csf_hint_all_valid() -> None:
    """Every CSF ID in csf_hint must exist in CSF 2.0 official."""
    if not (SD_SHARD.is_file() and AGGREGATED.is_file()):
        pytest.skip("shards missing")
    sd = json.loads(SD_SHARD.read_text())
    agg = json.loads(AGGREGATED.read_text())
    active_ids = {s["id"] for s in agg["subcategories"]}
    for csf_id in sd["csf_hint"]:
        assert csf_id in active_ids, f"{csf_id} in csf_hint but NOT in CSF 2.0 official active list"


def test_d011_nist_csf_mapping_per_sr() -> None:
    """All 4 Security Requirements must have non-empty nist_csf_mapping."""
    if not SD_SHARD.is_file():
        pytest.skip("D-01.1 shard missing")
    d = json.loads(SD_SHARD.read_text())
    srs = d.get("security_requirements", [])
    assert len(srs) == 4, f"expected 4 SRs, got {len(srs)}"
    for sr in srs:
        sr_id = sr["id"]
        mapping = sr.get("nist_csf_mapping") or sr.get("csf") or []
        assert mapping, f"{sr_id} has empty nist_csf_mapping"
        # Each CSF in the mapping must be valid
        for csf_id in mapping:
            assert re.match(
                r"^[A-Z]{2}\.[A-Z]{2,3}-\d{2}$", csf_id
            ), f"{sr_id} has invalid CSF ID: {csf_id}"


def test_d011_aggregated_row_matches() -> None:
    """The aggregated cross-reference row for D-01.1 must mirror csf_hint."""
    if not (SD_SHARD.is_file() and AGGREGATED.is_file()):
        pytest.skip("shards missing")
    sd = json.loads(SD_SHARD.read_text())
    agg = json.loads(AGGREGATED.read_text())
    row = next(
        (
            r
            for r in agg["cross_reference_aegis_subdomains"]["rows"]
            if r["aegis_subdomain"] == "D-01.1"
        ),
        None,
    )
    assert row is not None, "D-01.1 row missing from aggregated cross_reference_aegis_subdomains"
    assert sorted(row["csf_ids"]) == sorted(
        sd["csf_hint"]
    ), f"aggregated csf_ids={row['csf_ids']} != csf_hint={sd['csf_hint']}"
