"""Unit tests for the CSF 1.1 → CSF 2.0 mapping (CORR-027, Phase 1).

Covers C1, C2, C3 from the contract:
  - C1: 108 mappings total
  - C2: every mapping has the canonical 5 keys
  - C3: category_level_only == ['DE.DP-2']; unmapped_v1_1_ids is empty
        (RC.CO-2 is WITHDRAWN_DESTINATION_INCONSISTENT, not UNMAPPED)
Plus regression tests for the id-strip and category-header logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.preprocess.parsers.entities.csf_mapping import (
    _CSF_1_1_TITLES,
    build_v11_to_v20_mapping,
    _v11_id_from_v20_id_strip,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
XLSX = REPO_ROOT / "csf2.xlsx"


@pytest.fixture(scope="module")
def mapping() -> dict:
    """Build the full v1.1→v2.0 mapping once per module."""
    if not XLSX.is_file():
        pytest.skip(f"csf2.xlsx not present at {XLSX}")
    return build_v11_to_v20_mapping(XLSX)


# ─── C1: count ─────────────────────────────────────────────────────────


def test_count_108(mapping: dict) -> None:
    """C1: the mapping has exactly 108 v1.1 entries (NIST CSWP 41, 2018)."""
    assert mapping["csf_1_1_total"] == 108
    assert len(mapping["mappings"]) == 108


def test_no_duplicate_v11_ids(mapping: dict) -> None:
    """No v1.1 ID appears twice in mappings."""
    ids = [m["v11_id"] for m in mapping["mappings"]]
    assert len(ids) == len(set(ids)), f"duplicates: {[i for i in ids if ids.count(i) > 1]}"


# ─── C2: schema (every entry has the 5 canonical keys) ───────────────


def test_every_mapping_has_canonical_fields(mapping: dict) -> None:
    """C2: every mapping has v11_id, v11_title, v20_destinations, mapping_type, provenance."""
    required = {"v11_id", "v11_title", "v20_destinations", "mapping_type", "provenance"}
    for m in mapping["mappings"]:
        missing = required - set(m.keys())
        assert not missing, f"{m['v11_id']} missing: {missing}"


def test_every_v11_id_has_title(mapping: dict) -> None:
    """Every v11_title is non-empty and present in the static catalogue."""
    for m in mapping["mappings"]:
        assert m["v11_title"], f"{m['v11_id']} has empty title"
        assert m["v11_title"] == _CSF_1_1_TITLES.get(m["v11_id"]), (
            f"{m['v11_id']} title mismatch: {m['v11_title']!r} vs catalogue"
        )


# ─── C3: known-fuzzy cases ────────────────────────────────────────────


def test_de_dp_2_is_category_level(mapping: dict) -> None:
    """C3: DE.DP-2 has only a category-level mapping (DE.AE)."""
    entry = next(m for m in mapping["mappings"] if m["v11_id"] == "DE.DP-2")
    assert entry["mapping_type"] == "CATEGORY_LEVEL"
    assert entry["v20_destinations"] == ["DE.AE"]
    assert mapping["category_level_only"] == ["DE.DP-2"]


def test_rc_co_2_is_withdrawn_inconsistent(mapping: dict) -> None:
    """RC.CO-2 has the only WITHDRAWN_DESTINATION_INCONSISTENT flag.

    The withdrawn row tag says "Incorporated into RC.CO-04" but the
    active RC.CO-04 cites only RC.CO-1 and RS.CO-2, not RC.CO-2.
    """
    entry = next(m for m in mapping["mappings"] if m["v11_id"] == "RC.CO-2")
    assert entry["mapping_type"] == "WITHDRAWN_DESTINATION_INCONSISTENT"
    assert entry["v20_destinations"] == ["RC.CO-04"]
    assert mapping["inconsistent_v1_1_ids"] == ["RC.CO-2"]
    assert "rationale" in entry, "WITHDRAWN_DESTINATION_INCONSISTENT must carry a rationale"


def test_unmapped_list_is_empty(mapping: dict) -> None:
    """No v1.1 ID is truly UNMAPPED (all 108 have at least one destination)."""
    assert mapping["unmapped_v1_1_ids"] == []
    for m in mapping["mappings"]:
        assert m["mapping_type"] != "UNMAPPED", (
            f"{m['v11_id']} is UNMAPPED but contract C3 requires all 108 to have a destination"
        )


# ─── Regression: id-strip works for 2-digit v1.1 IDs ─────────────────


def test_id_strip_two_digit_v11() -> None:
    """id-strip is for direct renames (PR.AC-01 → PR.AC-1), not for
    category renames (PR.PS-06 has no v1.1 form because the entire
    PR.IP category was renamed to PR.PS in v2.0)."""
    # Direct rename: PR.AC-01 → PR.AC-1 (works, both in catalogues)
    assert _v11_id_from_v20_id_strip("PR.AC-01") == "PR.AC-1"
    # Category rename: PR.PS-06 → no v1.1 form (PR.PS didn't exist in v1.1)
    assert _v11_id_from_v20_id_strip("PR.PS-06") is None
    # Category rename: PR.AA-01 → no v1.1 form (PR.AA didn't exist in v1.1)
    assert _v11_id_from_v20_id_strip("PR.AA-01") is None
    # Direct rename: ID.AM-01 → ID.AM-1
    assert _v11_id_from_v20_id_strip("ID.AM-01") == "ID.AM-1"
    # New v2.0 ID with no v1.1 equivalent: DE.AE-07 (v1.1 had DE.AE-1..5)
    assert _v11_id_from_v20_id_strip("DE.AE-07") is None


def test_id_strip_returns_none_for_unknown_v11() -> None:
    """A v2.0 ID that doesn't correspond to any v1.1 ID returns None."""
    # DE.AE-07 is a v2.0 ID with no v1.1 equivalent (DE.AE-7 doesn't exist)
    assert _v11_id_from_v20_id_strip("DE.AE-07") is None


def test_id_strip_returns_none_for_category_only() -> None:
    """A FUNC.CAT id without a number suffix returns None."""
    assert _v11_id_from_v20_id_strip("DE.AE") is None


# ─── Regression: type distribution sanity ─────────────────────────────


def test_type_distribution_matches_known_counts(mapping: dict) -> None:
    """Sanity check on the mapping type histogram.

    Known: 29 IDENTITY_RENAME (the AM-1..6, BE-1..5, etc. renames),
    1 CATEGORY_LEVEL (DE.DP-2), 1 WITHDRAWN_DESTINATION_INCONSISTENT
    (RC.CO-2). The rest is split between SINGLE and MULTI.
    """
    from collections import Counter

    types = Counter(m["mapping_type"] for m in mapping["mappings"])
    assert types["IDENTITY_RENAME"] == 29
    assert types["CATEGORY_LEVEL"] == 1
    assert types["WITHDRAWN_DESTINATION_INCONSISTENT"] == 1
    assert types["UNMAPPED"] == 0
    # All 108 accounted for
    assert sum(types.values()) == 108


# ─── Regression: known easy mappings (spot-check 10) ──────────────────


@pytest.mark.parametrize(
    "v11_id, expected_dests",
    [
        ("PR.DS-1", ["PR.DS-01"]),  # data-at-rest
        ("PR.AC-1", ["PR.AA-01", "PR.AA-05"]),  # identity mgmt split
        ("DE.CM-8", ["ID.RA-01"]),  # vuln scans → risk assess
        ("RC.RP-1", ["RC.RP-01", "RC.RP-02"]),  # recovery plan
        ("RS.MI-1", ["RS.MI-01"]),  # contained
        ("RS.MI-2", ["RS.MI-02"]),  # mitigated
        ("ID.AM-1", ["ID.AM-01"]),  # identity rename
        ("ID.SC-1", ["GV.RM-05", "GV.SC-01", "GV.SC-06", "GV.SC-09", "GV.SC-10"]),  # SC RMT spread across multiple GV.* subcats
        ("PR.DS-4", ["PR.IR-04"]),  # capacity → IR (move)
        ("DE.DP-3", ["ID.IM-02"]),  # detection process testing
    ],
)
def test_spot_check_mappings(mapping: dict, v11_id: str, expected_dests: list[str]) -> None:
    """Spot-check 10 known mappings to catch regressions in the parser."""
    entry = next(m for m in mapping["mappings"] if m["v11_id"] == v11_id)
    assert entry["v20_destinations"] == expected_dests, (
        f"{v11_id} expected {expected_dests} got {entry['v20_destinations']}"
    )


# ─── Regression: provenance is non-empty for every entry ──────────────


def test_every_mapping_has_provenance(mapping: dict) -> None:
    """Every mapping entry carries at least one provenance record."""
    for m in mapping["mappings"]:
        assert m["provenance"], f"{m['v11_id']} has empty provenance"
        for p in m["provenance"]:
            assert "row" in p and "kind" in p, f"{m['v11_id']} provenance missing fields: {p}"


# ─── Phase 1 emits the JSON into preproc_out ──────────────────────────


def test_pipeline_emits_mapping_json() -> None:
    """Sanity: the preproc build writes global/csf_1_1_to_2_0_mapping.json."""
    mapping_path = REPO_ROOT / "preproc_out" / "global" / "csf_1_1_to_2_0_mapping.json"
    if not mapping_path.is_file():
        pytest.skip(
            "preproc_out/global/csf_1_1_to_2_0_mapping.json not yet built — "
            "run `python -m scripts.preprocess build` to populate"
        )
    import json

    data = json.loads(mapping_path.read_text())
    assert data["csf_1_1_total"] == 108
    assert len(data["mappings"]) == 108
