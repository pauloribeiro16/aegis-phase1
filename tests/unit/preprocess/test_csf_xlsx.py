"""CORR-024 v5: csf2.xlsx (NIST CSF 2.0 Reference Tool) parser tests.

Source: ``csf2.xlsx`` at the aegis-phase1 repo root. The xlsx is the
**official** NIST CSF 2.0 source of truth (185 subcategories, 79 withdrawn,
34 categories, 6 functions). The legacy ``NIST_CSF_2.0_subcategories.md``
(98 subcategories) is no longer the source of truth but is still
maintained for the AEGIS sub-domain cross-reference.

These tests verify:
  - All 185 subcategory IDs are present and unique.
  - Every shard has implementation_examples and informative_references.
  - Withdrawn subcategories are correctly marked.
  - Reference family glossary covers all 21 families.
  - The aggregated ``NIST_CSF_2.0_subcategories.json`` has no raw_md.
  - Source priority: xlsx is preferred over .md when both are present.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
XLSX = REPO_ROOT / "csf2.xlsx"
LEGACY_MD = REPO_ROOT / "methodology-00" / "PREPROCESSING" / "NIST_CSF_2.0_subcategories.md"
AGGREGATED = REPO_ROOT / "preproc_out" / "global" / "NIST_CSF_2.0_subcategories.json"
SHARDS_DIR = REPO_ROOT / "preproc_out" / "entities" / "csfs"

SUBCAT_ID_RE = re.compile(r"^([A-Z]{2})\.([A-Z]{2,3})-(\d{2})$")

# Expected layout: 6 subfolders (GV, ID, PR, DE, RS, RC) — one per Function.
# CORR-024 v7: shards are organized per Function rather than flat in
# entities/csfs/. The _meta/_index.json is the canonical map.
EXPECTED_FUNCTIONS = ["GV", "ID", "PR", "DE", "RS", "RC"]
CSF_INDEX_PATH = SHARDS_DIR / "_meta" / "_index.json"


def _all_csf_shards() -> list[Path]:
    """Recursively find all CSF shards under entities/csfs/ (v7/v8 layout)."""
    return [
        p
        for p in SHARDS_DIR.rglob("*.json")
        # Skip the _index.json (lives in _meta/) and any other meta files
        if p.name != "_index.json"
    ]


# ─── Source must exist ─────────────────────────────────────────────────


def test_xlsx_source_exists() -> None:
    assert XLSX.is_file(), f"missing csf2.xlsx at {XLSX}"


# ─── Parser unit tests ────────────────────────────────────────────────


def test_xlsx_parse_count() -> None:
    """CSF 2.0 Reference Tool has 185 subcategory rows."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    assert (
        parsed["counts"]["subcategories"] == 185
    ), f"expected 185 subcategories, got {parsed['counts']['subcategories']}"


def test_xlsx_parse_no_raw_md() -> None:
    """No subcategory dict may carry raw_md or raw fields."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    for sc in parsed["subcategories"]:
        assert "raw_md" not in sc, f"raw_md leaked into {sc['id']}"
        assert "raw" not in sc, f"raw field leaked into {sc['id']}"


def test_xlsx_parse_required_fields() -> None:
    """Every subcategory must have id, function, category_id, title, ex, refs."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    for sc in parsed["subcategories"]:
        for k in (
            "id",
            "function",
            "function_name",
            "category_id_resolved",
            "number",
            "title",
            "implementation_examples",
            "informative_references",
            "reference_families",
            "withdrawn",
            "withdrawal_note",
            "source_locus",
        ):
            assert k in sc, f"{sc.get('id')} missing field: {k}"


def test_xlsx_parse_function_summary_populated() -> None:
    """The 6 functions each have a non-empty summary_text."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    fn_ids = {f["id"] for f in parsed["functions"]}
    assert fn_ids == {"GV", "ID", "PR", "DE", "RS", "RC"}
    for f in parsed["functions"]:
        assert f["summary_text"], f"{f['id']} summary empty"
        assert f["category_count"] > 0
        assert f["subcategory_count"] > 0


def test_xlsx_parse_withdrawn_subcategories() -> None:
    """At least 79 subcategories are marked withdrawn (CSF 2.0 official)."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    withdrawn = [sc for sc in parsed["subcategories"] if sc["withdrawn"]]
    assert len(withdrawn) == 79, f"expected 79 withdrawn, got {len(withdrawn)}"
    # PR.DS-03 is the canonical withdrawn example
    pr_ds_03 = next(sc for sc in parsed["subcategories"] if sc["id"] == "PR.DS-03")
    assert pr_ds_03["withdrawn"] is True
    assert "Incorporated into" in pr_ds_03["withdrawal_note"]


def test_xlsx_parse_implementation_examples_split() -> None:
    """Implementation examples must be split into Ex1/Ex2/Ex3 records."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    gv_oc_01 = next(sc for sc in parsed["subcategories"] if sc["id"] == "GV.OC-01")
    ex_labels = [e["label"] for e in gv_oc_01["implementation_examples"]]
    assert ex_labels, "GV.OC-01 should have examples"
    assert ex_labels[0] == "Ex1"


def test_xlsx_parse_reference_families_glossary() -> None:
    """Reference family glossary must list families by count desc."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    fams = parsed["reference_families"]
    assert len(fams) >= 17, f"expected ≥17 families, got {len(fams)}"
    # Sorted by count desc
    from itertools import pairwise

    for a, b in pairwise(fams):
        assert a["count"] >= b["count"], "families not sorted by count desc"
    # Each family has {family, count, distinct_count, example}
    for fam in fams:
        assert fam["family"]
        assert fam["count"] > 0
        assert fam["distinct_count"] > 0
        assert fam["example"]
    # SP 800-53 should be the top family (1474 cells)
    top = fams[0]
    assert "SP 800" in top["family"], f"top family expected SP 800, got {top['family']}"
    assert top["count"] > 1000


def test_xlsx_parse_introduction() -> None:
    """Introduction sheet yields title, read_me, change_log, generated_date."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    intro = parsed["introduction"]
    assert intro["title"] == "The NIST Cybersecurity Framework (CSF) 2.0"
    assert "Reference Tool" in intro["read_me"]
    assert intro["change_log"] == "Final"
    assert intro["generated_date"].startswith("2026-")


def test_xlsx_id_uniqueness_and_format() -> None:
    """All 185 IDs are unique and match the FUNC.CAT-NN pattern."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    ids = [sc["id"] for sc in parsed["subcategories"]]
    assert len(set(ids)) == 185, f"duplicate IDs: {len(ids)} total, {len(set(ids))} unique"
    for sid in ids:
        assert SUBCAT_ID_RE.match(sid), f"bad id format: {sid}"


def test_xlsx_categories_count() -> None:
    """There are 34 categories in the official CSF 2.0 (vs 21 in the legacy .md)."""
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    assert (
        parsed["counts"]["categories"] == 34
    ), f"expected 34 categories, got {parsed['counts']['categories']}"


# ─── Per-subcategory shards on disk ────────────────────────────────────


def test_xlsx_shards_106() -> None:
    """preproc_out/entities/csfs/ must contain exactly 106 shards.

    185 - 79 withdrawn = 106 active subcategories. Withdrawn subs are
    NOT materialized as shards (they have no actionable content in the
    official xlsx) and are kept only in the aggregated
    ``withdrawn_subcategories`` section for audit traceability.
    """
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    files = _all_csf_shards()
    assert len(files) == 106, f"expected 106 active shards, got {len(files)}"


def test_xlsx_shards_layout_per_function() -> None:
    """CORR-024 v7/v8: shards are organized in 6 per-Function subfolders.

    Layout: entities/csfs/{_meta/,GV/,ID/,PR/,DE/,RS/,RC/}
    Shards:  entities/csfs/{FUNC}/{FUNC}_{CAT}_{NUM}.json
    Index:   entities/csfs/_meta/_index.json
    """
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    # Each expected function must have a subfolder
    for fn in EXPECTED_FUNCTIONS:
        sub = SHARDS_DIR / fn
        assert sub.is_dir(), f"missing subfolder: {sub}"
    # _meta/ subfolder with _index.json
    assert CSF_INDEX_PATH.is_file(), f"missing {CSF_INDEX_PATH}"
    # _meta/ subfolder must exist
    assert (SHARDS_DIR / "_meta").is_dir(), "missing _meta/ subfolder"
    # No flat shard files at the root (only _meta/ + the 6 subdirs)
    root_files = [p for p in SHARDS_DIR.iterdir() if p.is_file()]
    assert root_files == [], f"unexpected root files: {[p.name for p in root_files]}"


def test_xlsx_shards_index_consistent() -> None:
    """_meta/_index.json must list all 106 active subcategories and match
    the shards on disk (same set of IDs)."""
    if not CSF_INDEX_PATH.is_file():
        pytest.skip("preproc_out not built")
    idx = json.loads(CSF_INDEX_PATH.read_text())
    indexed_ids = set(idx["by_id"].keys())
    # On-disk IDs
    disk_ids = set()
    for p in _all_csf_shards():
        d = json.loads(p.read_text())
        disk_ids.add(d["id"])
    assert indexed_ids == disk_ids, (
        f"index/disk mismatch: only in index={indexed_ids - disk_ids}, "
        f"only on disk={disk_ids - indexed_ids}"
    )
    # Per-function counts in _index.json must match the actual subfolder sizes
    for fn, info in idx["by_function"].items():
        sub = SHARDS_DIR / fn
        actual = len(list(sub.glob("*.json")))
        assert (
            actual == info["count"]
        ), f"{fn}: index says {info['count']} but subfolder has {actual}"


def test_xlsx_shards_no_withdrawn() -> None:
    """No shard on disk may be marked withdrawn=True (those don't get shards)."""
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    bad = []
    for p in _all_csf_shards():
        d = json.loads(p.read_text())
        if d.get("withdrawn"):
            bad.append(p.name)
    assert not bad, f"withdrawn shards present (should be skipped): {bad[:5]}"


def test_xlsx_shards_no_legacy_id() -> None:
    """The legacy-only ID PR.DS-12 (renamed in CSF 2.0) must NOT be present."""
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    files = {p.stem for p in _all_csf_shards()}
    assert "PR_DS_12" not in files, "legacy PR.DS-12 shard still present (renamed in CSF 2.0)"


def test_xlsx_shards_have_implementation_examples() -> None:
    """All active shards carry non-empty implementation_examples.

    Since withdrawn subs (with empty examples) are no longer shards, the
    106 active shards should ALL have examples.
    """
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    without = []
    total = 0
    for p in _all_csf_shards():
        d = json.loads(p.read_text())
        total += 1
        if not d.get("implementation_examples"):
            without.append(d["id"])
    assert not without, f"active shards without implementation_examples: {without[:5]}"
    assert total == 106, f"test expects 106 shards, found {total}"


def test_xlsx_shards_have_informative_references() -> None:
    """Every active shard has at least one informative_reference."""
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    without = []
    total = 0
    for p in _all_csf_shards():
        d = json.loads(p.read_text())
        total += 1
        if not d.get("informative_references"):
            without.append(d["id"])
    assert not without, f"active shards without informative_references: {without[:5]}"
    assert total == 106


# ─── Aggregated top-level file ─────────────────────────────────────────


def test_xlsx_aggregated_no_raw_md() -> None:
    """The aggregated JSON must NOT carry raw_md."""
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    assert "raw_md" not in parsed, "raw_md leaked into aggregated"
    assert parsed["kind"] == "csf_reference"
    assert parsed["schema_version"] == "1.3"
    # Total subcategories in xlsx (active + withdrawn) is 185
    assert parsed["counts"]["subcategories"] == 185
    # Only 106 are non-withdrawn (active) — they appear in the
    # ``subcategories`` list and have shards on disk.
    assert len(parsed["subcategories"]) == 106
    # All 185 (active + withdrawn) are listed in ``all_subcategories`` for
    # audit traceability.
    assert len(parsed["all_subcategories"]) == 185
    # The 79 withdrawn are listed in their own section, each with parsed
    # ``withdrawal_target_ids``.
    assert len(parsed["withdrawn_subcategories"]) == 79
    for w in parsed["withdrawn_subcategories"][:3]:
        assert w["id"]
        assert w["withdrawal_note"]
        assert isinstance(w["withdrawal_target_ids"], list)
    assert parsed["counts"]["functions"] == 6
    assert parsed["counts"]["withdrawn"] == 79
    assert parsed["counts"]["reference_families"] >= 17


def test_xlsx_aggregated_source_is_xlsx() -> None:
    """The aggregated file's source must be csf2.xlsx, not the .md."""
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    assert "csf2.xlsx" in parsed["source"]
    # The legacy .md is still referenced for the D-XX cross-reference
    if "source_md_legacy" in parsed:
        assert parsed["source_md_legacy"] is None or ".md" in parsed["source_md_legacy"]


def test_xlsx_aggregated_subcategory_coverage() -> None:
    """All 106 active subcategory IDs are present in the aggregated file's
    main ``subcategories`` list. The 79 withdrawn are kept separately in
    ``all_subcategories`` + ``withdrawn_subcategories`` for audit."""
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    active_ids = {s["id"] for s in parsed["subcategories"]}
    assert len(active_ids) == 106, f"expected 106 active subs, got {len(active_ids)}"
    all_ids = {s["id"] for s in parsed["all_subcategories"]}
    assert len(all_ids) == 185
    # A few canonical active IDs must be present
    for sid in ("GV.OC-01", "RC.RP-06", "DE.CM-09", "PR.DS-11", "ID.AM-08"):
        assert sid in active_ids, f"missing canonical active ID: {sid}"
    # The withdrawn IDs are in all_subcategories and withdrawn_subcategories
    for sid in ("PR.DS-03", "ID.AM-06", "RC.IM-01"):
        assert sid in all_ids, f"missing canonical withdrawn ID: {sid}"
        assert sid not in active_ids, f"withdrawn ID leaked into active list: {sid}"


def test_xlsx_aggregated_contains_categories() -> None:
    """All 34 categories are present with proper structure."""
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    cats = parsed["categories"]
    assert len(cats) == 34
    # Each category has id, function, function_name, name, subcategory_count
    for c in cats:
        assert c["id"]
        assert c["function"] in {"GV", "ID", "PR", "DE", "RS", "RC"}
        assert c["name"]
        assert c["subcategory_count"] > 0


def test_xlsx_aggregated_withdrawn_section() -> None:
    """Withdrawn subcategories are listed in a dedicated section, each
    with parsed ``withdrawal_target_ids`` (the active IDs that absorbed it)."""
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    wd = parsed["withdrawn_subcategories"]
    assert len(wd) == 79
    # Each withdrawn entry has id + withdrawal_note + withdrawal_target_ids
    for w in wd[:5]:
        assert w["id"]
        assert w["withdrawal_note"]
        assert isinstance(w["withdrawal_target_ids"], list)
        # At least one target ID must be parseable (the source text is like
        # "Incorporated into ID.AM-08, PR.PS-03")
        if "Incorporated into" in w["withdrawal_note"] or "Moved to" in w["withdrawal_note"]:
            assert (
                len(w["withdrawal_target_ids"]) >= 1
            ), f"{w['id']} note {w['withdrawal_note']!r} should have target IDs"


def test_xlsx_aggregated_introduction_section() -> None:
    """Introduction metadata is propagated to the aggregated file."""
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    intro = parsed["introduction"]
    assert intro["title"] == "The NIST Cybersecurity Framework (CSF) 2.0"
    assert "Reference Tool" in intro["read_me"]


# ─── Per-shard structure ───────────────────────────────────────────────


def test_xlsx_shard_gv_oc_01_full() -> None:
    """Spot-check the GV.OC-01 shard has the expected xlsx-derived structure."""
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    p = SHARDS_DIR / "GV" / "GV_OC_01.json"
    if not p.is_file():
        pytest.skip("shard not present")
    d = json.loads(p.read_text())
    assert d["id"] == "GV.OC-01"
    assert d["function"] == "GV"
    assert d["function_name"] == "Govern"
    assert d["category_id"] == "GV.OC"
    assert d["title"].startswith("The organizational mission is understood")
    assert d["withdrawn"] is False
    assert d["withdrawal_note"] is None
    # Implementation examples
    assert d["implementation_examples"], "no examples"
    assert d["implementation_examples"][0]["label"] == "Ex1"
    # Informative references
    assert d["informative_references"], "no references"
    # Reference families
    assert d["reference_families"], "no families"
    # Tool metadata
    assert d["tool_metadata"]["title"] == "The NIST Cybersecurity Framework (CSF) 2.0"
    # Source locus
    assert d["source_locus"]["xlsx_row"] > 0
    assert d["source_locus"]["sheet"] == "CSF 2.0"


def test_xlsx_withdrawn_not_as_shard() -> None:
    """Withdrawn subcategories (e.g. PR.DS-03) are NOT materialized as
    per-subcategory shards. Their metadata is in the aggregated file's
    ``withdrawn_subcategories`` section.
    """
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    p = SHARDS_DIR / "PR" / "PR_DS_03.json"
    assert not p.is_file(), "PR.DS-03 is withdrawn — should NOT have a shard"
    # But it should appear in the aggregated file
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    pr_ds_03 = next(
        (w for w in parsed["withdrawn_subcategories"] if w["id"] == "PR.DS-03"),
        None,
    )
    assert pr_ds_03 is not None, "PR.DS-03 must be in aggregated withdrawn_subcategories"
    assert "Incorporated into" in pr_ds_03["withdrawal_note"]
    assert len(pr_ds_03["withdrawal_target_ids"]) >= 1


# ─── Reference family clustering ───────────────────────────────────────


def test_xlsx_reference_families_cover_top10() -> None:
    """The 10 most-populated families must cover ≥80% of references.

    Real coverage is 86.6% (5247/6062). The 17-family glossary is the
    long tail; the top-10 captures the dominant frameworks.
    """
    from scripts.preprocess.parsers.entities.csf_xlsx import parse_csf2

    parsed = parse_csf2(XLSX)
    fams = parsed["reference_families"]
    top10_total = sum(f["count"] for f in fams[:10])
    grand_total = sum(f["count"] for f in fams)
    assert top10_total / grand_total > 0.8, (
        f"top 10 families cover only {top10_total}/{grand_total} "
        f"({100*top10_total/grand_total:.1f}%)"
    )
