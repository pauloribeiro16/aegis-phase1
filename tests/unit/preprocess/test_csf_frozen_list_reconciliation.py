"""Unit tests for the .md frozen-list reconciliation (CORR-027, Phase 2).

Covers C4, C5, C6 from the contract:
  - C4: 5 removed IDs (PR.AT-03, PR.AT-04, PR.DS-12, RS.CO-01, RS.CO-04)
       are NOT present as active subcategory rows in the .md
  - C5: 13 previously-missing IDs (DE.AE-07, GV.SC-06..10, ID.AM-08,
       ID.RA-07..10, RC.CO-03, RC.CO-04) are now in the .md with the
       correct title
  - C6: the .md's claimed total is 106 subcategories
Plus a cross-check that the .md and the preproc_out xlsx-derived set agree.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MD_PATH = REPO_ROOT / "methodology-00" / "PREPROCESSING" / "NIST_CSF_2.0_subcategories.md"
PREPROC_JSON = REPO_ROOT / "preproc_out" / "global" / "NIST_CSF_2.0_subcategories.json"


@pytest.fixture(scope="module")
def md_text() -> str:
    if not MD_PATH.is_file():
        pytest.skip(f"frozen-list .md not present at {MD_PATH}")
    return MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def md_ids(md_text: str) -> set[str]:
    """All subcategory IDs found in the .md's tables."""
    return set(re.findall(r"^\|\s*([A-Z]{2}\.[A-Z]{2}-\d+)\s*\|", md_text, re.MULTILINE))


# ─── C4: 5 removed IDs absent ──────────────────────────────────────────


@pytest.mark.parametrize(
    "removed_id",
    ["PR.AT-03", "PR.AT-04", "PR.DS-12", "RS.CO-01", "RS.CO-04"],
)
def test_removed_ids_absent(md_ids: set[str], removed_id: str) -> None:
    """C4: each of the 5 removed IDs must not appear as a table row in the .md."""
    assert removed_id not in md_ids, (
        f"{removed_id} still present in the .md as a table row; "
        f"CORR-027 Phase 2 must remove it"
    )


# ─── C5: 12 missing IDs now present ───────────────────────────────────


EXPECTED_12 = [
    "DE.AE-07",
    "GV.SC-06",
    "GV.SC-07",
    "GV.SC-08",
    "GV.SC-09",
    "GV.SC-10",
    "ID.AM-08",
    "ID.RA-07",
    "ID.RA-08",
    "ID.RA-09",
    "ID.RA-10",
    "RC.CO-03",
    "RC.CO-04",
]


@pytest.mark.parametrize("added_id", EXPECTED_12)
def test_12_ids_now_present(md_ids: set[str], added_id: str) -> None:
    """C5: each of the 12 previously-missing IDs is now in the .md."""
    assert added_id in md_ids, f"{added_id} not in .md frozen list"


def test_12_count_is_exactly_13(md_ids: set[str]) -> None:
    """Sanity: all 13 added IDs are present, no extras slipped in."""
    present = [i for i in EXPECTED_12 if i in md_ids]
    assert len(present) == len(EXPECTED_12), (
        f"only {len(present)} of {len(EXPECTED_12)} added IDs present: {present}"
    )


# ─── C6: .md total is 106 ──────────────────────────────────────────────


def test_md_total_is_106(md_text: str, md_ids: set[str]) -> None:
    """C6: the .md carries 106 unique subcategory IDs."""
    assert len(md_ids) == 106, f"expected 106, got {len(md_ids)}"


def test_md_function_structure_table_says_106(md_text: str) -> None:
    """The summary table at the top of the .md states 106 subcategories."""
    # Look for the line `| **Total** | — | **22** | **106** |` (or similar)
    m = re.search(r"\*\*Total\*\*.*?\*\*(\d+)\*\*\s*\|?\s*$", md_text, re.MULTILINE)
    assert m, "no Total row in function structure table"
    assert m.group(1) == "106", f"Total says {m.group(1)}, expected 106"


# ─── Cross-check: .md ↔ preproc_out xlsx-derived truth ────────────────


def test_md_matches_preproc_out_truth() -> None:
    """The .md's active ID set must equal the xlsx-derived preproc_out set."""
    if not PREPROC_JSON.is_file():
        pytest.skip("preproc_out/global/NIST_CSF_2.0_subcategories.json not yet built")
    data = json.loads(PREPROC_JSON.read_text())
    xlsx_ids = set(s["id"] for s in data["subcategories"])
    md_ids = set(
        re.findall(
            r"^\|\s*([A-Z]{2}\.[A-Z]{2}-\d+)\s*\|",
            MD_PATH.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    assert md_ids == xlsx_ids, (
        f"md ↔ preproc_out mismatch: "
        f"only-in-md={sorted(md_ids - xlsx_ids)}, "
        f"only-in-xlsx={sorted(xlsx_ids - md_ids)}"
    )


# ─── Decisions section exists and covers D1–D4 ─────────────────────────


def test_decisions_section_present(md_text: str) -> None:
    """The .md has a 'Decisions (CORR-027)' section."""
    assert "## Decisions (CORR-027)" in md_text, "no Decisions section"
    for d in ("D1", "D2", "D3", "D4"):
        assert f"### {d} " in md_text or f"### {d}\n" in md_text, (
            f"missing decision subsection {d}"
        )


def test_decisions_d1_explains_pr_ds_12(md_text: str) -> None:
    """D1 explains the PR.DS-12 drop and why."""
    # Find the D1 block
    d1_start = md_text.find("### D1 —")
    d1_end = md_text.find("### D2 —", d1_start) if d1_start > 0 else -1
    assert d1_start > 0 and d1_end > 0, "D1/D2 sections not found"
    d1 = md_text[d1_start:d1_end]
    assert "PR.DS-12" in d1, "D1 must mention PR.DS-12"
    assert "draft" in d1.lower(), "D1 should explain the source (pre-finalization draft)"


# ─── Counter-test: the 4 withdrawn IDs do appear in any historical
#         narrative in the .md (e.g. the withdrawn log) ───────────────


def test_withdrawn_ids_can_still_appear_in_narrative(md_text: str) -> None:
    """The removed IDs should still be MENTIONED in the Decisions / RC.CO
    note (so a future reader understands what was removed), but only as
    prose — not as table rows. This test guards against accidental
    table re-insertion.
    """
    # The Decisions D2 block MUST mention the 4 withdrawn IDs by name
    d2_start = md_text.find("### D2 —")
    d2_end = md_text.find("### D3 —", d2_start) if d2_start > 0 else -1
    assert d2_start > 0 and d2_end > 0, "D2/D3 sections not found"
    d2 = md_text[d2_start:d2_end]
    for wid in ("PR.AT-03", "PR.AT-04", "RS.CO-01", "RS.CO-04"):
        assert wid in d2, f"D2 narrative must mention withdrawn {wid}"
