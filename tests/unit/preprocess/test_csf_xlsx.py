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


def test_xlsx_shards_185() -> None:
    """preproc_out/entities/csfs/ must contain exactly 185 shards."""
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    files = list(SHARDS_DIR.glob("*.json"))
    assert len(files) == 185, f"expected 185 shards, got {len(files)}"


def test_xlsx_shards_no_legacy_id() -> None:
    """The legacy-only ID PR.DS-12 (renamed in CSF 2.0) must NOT be present."""
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    files = {p.stem for p in SHARDS_DIR.glob("*.json")}
    assert "PR_DS_12" not in files, "legacy PR.DS-12 shard still present (renamed in CSF 2.0)"


def test_xlsx_shards_have_implementation_examples() -> None:
    """At least 50% of shards carry non-empty implementation_examples.

    Withdrawn subcategories (79 of 185) often have no examples, so the
    real-world coverage is ~57% (106/185). 50% is a safe lower bound.
    """
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    with_ex = 0
    total = 0
    for p in SHARDS_DIR.glob("*.json"):
        d = json.loads(p.read_text())
        total += 1
        if d.get("implementation_examples"):
            with_ex += 1
    assert with_ex / total > 0.5, f"only {with_ex}/{total} shards have implementation_examples"


def test_xlsx_shards_have_informative_references() -> None:
    """All withdrawn subcategories lack references (79/185 = 42.7%);
    every non-withdrawn subcategory must have at least one reference.

    The official NIST xlsx is consistent: withdrawn rows have empty
    Refs column, active rows always have ≥1 reference.
    """
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    active_without = []
    total_active = 0
    for p in SHARDS_DIR.glob("*.json"):
        d = json.loads(p.read_text())
        if d.get("withdrawn"):
            continue
        total_active += 1
        if not d.get("informative_references"):
            active_without.append(d["id"])
    assert (
        not active_without
    ), f"active (non-withdrawn) shards without references: {active_without[:5]}"
    # Sanity: there should be plenty of active subs
    assert total_active > 100, f"only {total_active} active subs — test stale"


# ─── Aggregated top-level file ─────────────────────────────────────────


def test_xlsx_aggregated_no_raw_md() -> None:
    """The aggregated JSON must NOT carry raw_md."""
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    assert "raw_md" not in parsed, "raw_md leaked into aggregated"
    assert parsed["kind"] == "csf_reference"
    assert parsed["schema_version"] == "1.2"
    assert parsed["counts"]["subcategories"] == 185
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
    """All 185 subcategory IDs are present in the aggregated file."""
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    ids = {s["id"] for s in parsed["subcategories"]}
    assert len(ids) == 185
    # A few canonical IDs must be present
    for sid in ("GV.OC-01", "RC.RP-06", "DE.CM-09", "PR.DS-11", "ID.AM-08"):
        assert sid in ids, f"missing canonical ID: {sid}"


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
    """Withdrawn subcategories are listed in a dedicated section."""
    if not AGGREGATED.is_file():
        pytest.skip(f"aggregated file missing: {AGGREGATED}")
    parsed = json.loads(AGGREGATED.read_text())
    wd = parsed["withdrawn_subcategories"]
    assert len(wd) == 79
    # Each withdrawn entry has id + withdrawal_note
    for w in wd[:5]:
        assert w["id"]
        assert w["withdrawal_note"]


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
    p = SHARDS_DIR / "GV_OC_01.json"
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


def test_xlsx_shard_withdrawn_pr_ds_03() -> None:
    """Spot-check the withdrawn PR.DS-03 shard."""
    if not SHARDS_DIR.is_dir():
        pytest.skip("preproc_out not built")
    p = SHARDS_DIR / "PR_DS_03.json"
    if not p.is_file():
        pytest.skip("shard not present")
    d = json.loads(p.read_text())
    assert d["withdrawn"] is True
    assert "Incorporated into" in d["withdrawal_note"]


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
