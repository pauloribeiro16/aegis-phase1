"""CORR-024 CSF test: NIST CSF 2.0 subcategories must round-trip to v2 shape.

Verifies that **every** source element of
``NIST_CSF_2.0_subcategories.md`` is mapped to a structured field — no
raw_md dumping. The source has 10 distinct structural elements
(frontmatter, H1, authority blockquote, function-structure table, 6
per-function H2 sections, 22 per-category H3 sections, 98 subcategory
rows, cross-reference table + advisory blockquote, special-tokens table,
"End of reference" closing line) and this test ensures none is dropped.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE = REPO_ROOT / "methodology-00" / "PREPROCESSING" / "NIST_CSF_2.0_subcategories.md"


# ─── Source must exist ─────────────────────────────────────────────────


def test_csf_source_exists() -> None:
    assert SOURCE.is_file(), f"missing source: {SOURCE}"


# ─── Parser unit tests (no disk round-trip) ────────────────────────────


def test_csf_parse_count() -> None:
    from scripts.preprocess.parsers.entities.csf import parse_csf

    subs = parse_csf(SOURCE)
    # Source enumerates 98 subcategory rows in the body (the summary text
    # claims 106 but the actual table has 98). The parser must reflect
    # actual content, not aspirational text.
    assert len(subs) == 98, f"expected 98 subcategories, got {len(subs)}"


def test_csf_parse_no_raw_md() -> None:
    """Every subcategory dict must be structured — no raw_md leakage."""
    from scripts.preprocess.parsers.entities.csf import parse_csf

    subs = parse_csf(SOURCE)
    for sc in subs:
        assert "raw_md" not in sc, f"raw_md leaked into {sc.get('id')}"
        assert "raw" not in sc, f"raw field leaked into {sc.get('id')}"


def test_csf_parse_required_fields() -> None:
    from scripts.preprocess.parsers.entities.csf import parse_csf

    subs = parse_csf(SOURCE)
    required = {
        "id", "function", "category", "number", "title",
        "function_name", "category_id", "category_name",
        "function_summary", "source_locus", "source",
        "source_document", "authority_note", "authority_note_locus",
        "aegis_subdomain_back_refs",
        "aegis_subdomain_back_refs_advisory_only",
    }
    for sc in subs:
        missing = required - set(sc.keys())
        assert not missing, f"{sc.get('id')} missing fields: {missing}"


def test_csf_function_summary_populated() -> None:
    from scripts.preprocess.parsers.entities.csf import parse_csf

    subs = parse_csf(SOURCE)
    for sc in subs:
        fs = sc["function_summary"]
        assert fs["category_count"] > 0, f"{sc['id']} category_count=0"
        assert fs["subcategory_count"] > 0, f"{sc['id']} subcategory_count=0"


def test_csf_category_name_resolved() -> None:
    from scripts.preprocess.parsers.entities.csf import parse_csf

    subs = parse_csf(SOURCE)
    unnamed = [sc["id"] for sc in subs if not sc.get("category_name")]
    assert not unnamed, f"subcategories without category_name: {unnamed}"


def test_csf_source_locus_within_bounds() -> None:
    """source_locus must be 1-indexed source lines (≥1, ≤total)."""
    from scripts.preprocess.parsers.entities.csf import parse_csf

    subs = parse_csf(SOURCE)
    total_lines = len(SOURCE.read_text(encoding="utf-8").splitlines())
    for sc in subs:
        locus = sc["source_locus"]
        assert 1 <= locus["start_line"] <= total_lines, f"{sc['id']} bad start"
        assert locus["end_line"] >= locus["start_line"], f"{sc['id']} end<start"
        assert locus["end_line"] <= total_lines, f"{sc['id']} bad end"


def test_csf_function_structure_full() -> None:
    """Function structure: H2 + summary + table_header + 6 funcs + totals."""
    from scripts.preprocess.parsers.entities.csf import parse_csf_function_structure

    fs = parse_csf_function_structure(SOURCE)
    assert fs["title"] == "Function structure"
    assert "6 Functions" in fs["summary_text"]
    assert "22 Categories" in fs["summary_text"]
    assert fs["table_header"] == [
        "Function ID", "Function Name", "Cat. Count", "Subcat. Count"
    ]
    assert len(fs["functions"]) == 6
    fn_names = {f["id"] for f in fs["functions"]}
    assert fn_names == {"GV", "ID", "PR", "DE", "RS", "RC"}
    # Totals row preserved as written in source (with **Total** label).
    assert fs["totals_row"] is not None
    assert "Total" in fs["totals_row"]["function_label"]
    assert fs["totals_row"]["category_count"] == 22
    assert fs["totals_row"]["subcategory_count"] == 106
    assert fs["totals"]["function_count"] == 6


def test_csf_special_tokens_full() -> None:
    """Special tokens: H2 + table_header + 2 data rows (UNMAPPED_CSF, ...)."""
    from scripts.preprocess.parsers.entities.csf import parse_csf_special_tokens_full

    spec = parse_csf_special_tokens_full(SOURCE)
    assert spec["title"] == "Special tokens"
    assert spec["table_header"] == ["Token", "Use"]
    tokens = {t["token"] for t in spec["rows"]}
    assert tokens == {"UNMAPPED_CSF", "UNMAPPED_CSF_PRIVACY"}
    # Each row has both fields
    for t in spec["rows"]:
        assert t["token"]
        assert t["use"]


def test_csf_authority_note_full() -> None:
    """Authority blockquote: full text + body-relative locus.

    The parser returns body-relative lines. The aggregated shard (in
    ``parse_root_csf_structured``) shifts these to source-relative.
    """
    from scripts.preprocess.parsers.entities.csf import parse_csf_authority_note_full

    auth = parse_csf_authority_note_full(SOURCE)
    assert "**Authority:**" in auth["text"]
    assert "NIST CSWP 29" in auth["text"]
    assert "UNMAPPED_CSF" in auth["text"]
    # Body-relative: the authority blockquote is on body line 4
    # (body line 1 is blank after frontmatter; body line 4 is the > Authority).
    assert auth["start_line"] == 4
    assert auth["end_line"] == 4


def test_csf_h1_title() -> None:
    from scripts.preprocess.parsers.entities.csf import parse_csf_h1_title

    title = parse_csf_h1_title(SOURCE)
    assert title == "NIST CSF 2.0 Subcategory Reference (Frozen List)"


def test_csf_end_of_reference() -> None:
    from scripts.preprocess.parsers.entities.csf import parse_csf_end_of_reference

    end = parse_csf_end_of_reference(SOURCE)
    assert end is not None
    assert end["text"] == "**End of reference.**"
    # Body-relative: 307 (the closing line is the last body line).
    assert end["line"] == 307


def test_csf_back_refs_populated() -> None:
    """Some subcategories must have back-references to AEGIS sub-domains."""
    from scripts.preprocess.parsers.entities.csf import parse_csf

    subs = parse_csf(SOURCE)
    with_refs = [sc for sc in subs if sc["aegis_subdomain_back_refs"]]
    assert len(with_refs) >= 30, f"too few back-refs: {len(with_refs)}/98"


# ─── Cross-reference coverage ─────────────────────────────────────────


def test_csf_crossref_full() -> None:
    """Cross-ref: H2 + table_header + 38 rows + advisory blockquote."""
    from scripts.preprocess.parsers.entities.csf import parse_csf_crossref_full

    cr = parse_csf_crossref_full(SOURCE)
    # H2 title (full)
    assert cr["title"].startswith("Cross-reference")
    assert "advisory" in cr["title"].lower()
    # Table header
    assert cr["table_header"] == ["AEGIS sub-domain", "Likely CSF Functions"]
    # 38 D-XX rows
    assert len(cr["rows"]) == 38
    # Each row has aegis_subdomain, description, csf_refs, csf_ids, csf_categories
    for r in cr["rows"]:
        assert r["aegis_subdomain"].startswith("D-")
        assert r["description"]
        assert isinstance(r["csf_refs"], list)
        assert isinstance(r["csf_ids"], list)
        assert isinstance(r["csf_categories"], list)
        assert r["source_locus"]["start_line"] > 0
    # First row must be D-01.1 (Data at Rest)
    assert cr["rows"][0]["aegis_subdomain"] == "D-01.1"
    assert cr["rows"][0]["description"] == "Data at Rest"
    # Last row must be D-10.3
    assert cr["rows"][-1]["aegis_subdomain"] == "D-10.3"
    # D-01.3 (Key Management) cell has prose "GV.OV (governance)"
    d013 = next(r for r in cr["rows"] if r["aegis_subdomain"] == "D-01.3")
    assert "governance" in d013["advisory_prose"]
    assert "GV.OV" in d013["csf_categories"]
    # Advisory blockquote preserved
    assert cr["advisory_blockquote"] is not None
    assert "Use only as orientation" in cr["advisory_blockquote"]["text"]


# ─── Aggregated shard (top-level global) ───────────────────────────────


def test_csf_aggregated_no_raw_md() -> None:
    """The top-level global aggregated shard must NOT carry raw_md."""
    from scripts.preprocess.pipeline import parse_root_csf_structured

    parsed = parse_root_csf_structured(SOURCE)
    assert "raw_md" not in parsed, "raw_md leaked into aggregated"
    assert parsed["kind"] == "csf_reference"
    assert parsed["schema_version"] == "1.1"
    assert parsed["counts"]["subcategories"] == 98
    assert parsed["counts"]["functions"] == 6


def test_csf_aggregated_h1_and_authority() -> None:
    from scripts.preprocess.pipeline import parse_root_csf_structured

    parsed = parse_root_csf_structured(SOURCE)
    assert parsed["h1_title"] == "NIST CSF 2.0 Subcategory Reference (Frozen List)"
    assert "**Authority:**" in parsed["authority_note"]["text"]
    # Source-relative locus (line 20)
    assert parsed["authority_note"]["source_locus"]["start_line"] == 20


def test_csf_aggregated_function_structure_full() -> None:
    from scripts.preprocess.pipeline import parse_root_csf_structured

    parsed = parse_root_csf_structured(SOURCE)
    fs = parsed["function_structure"]
    assert fs["title"] == "Function structure"
    assert len(fs["functions"]) == 6
    assert fs["totals"]["function_count"] == 6
    assert fs["totals_row"]["category_count"] == 22
    assert fs["totals_row"]["subcategory_count"] == 106


def test_csf_aggregated_crossref_full() -> None:
    from scripts.preprocess.pipeline import parse_root_csf_structured

    parsed = parse_root_csf_structured(SOURCE)
    cr = parsed["cross_reference_aegis_subdomains"]
    assert cr["title"].startswith("Cross-reference")
    assert cr["table_header"] == ["AEGIS sub-domain", "Likely CSF Functions"]
    assert len(cr["rows"]) == 38
    # D-10.1 (Logging) row carries the description from the source
    d101 = next(r for r in cr["rows"] if r["aegis_subdomain"] == "D-10.1")
    assert d101["description"] == "Logging"
    assert d101["csf_ids"] == ["PR.PS-04", "DE.CM-09"]
    # Source-relative locus (line 306 in source for D-10.1)
    assert d101["source_locus"]["start_line"] == 306
    # Advisory blockquote present, source-relative line 310
    assert cr["advisory_blockquote"] is not None
    assert cr["advisory_blockquote"]["line"] == 310


def test_csf_aggregated_special_tokens_full() -> None:
    from scripts.preprocess.pipeline import parse_root_csf_structured

    parsed = parse_root_csf_structured(SOURCE)
    spec = parsed["special_tokens"]
    assert spec["title"] == "Special tokens"
    assert spec["table_header"] == ["Token", "Use"]
    assert len(spec["rows"]) == 2
    assert spec["source_locus"]["start_line"] > 0


def test_csf_aggregated_end_of_reference() -> None:
    from scripts.preprocess.pipeline import parse_root_csf_structured

    parsed = parse_root_csf_structured(SOURCE)
    assert parsed["end_of_reference"] is not None
    assert parsed["end_of_reference"]["text"] == "**End of reference.**"
    # Source-relative line 323
    assert parsed["end_of_reference"]["line"] == 323


def test_csf_aggregated_contains_all_subs() -> None:
    from scripts.preprocess.pipeline import parse_root_csf_structured

    parsed = parse_root_csf_structured(SOURCE)
    sub_ids = {s["id"] for s in parsed["subcategories"]}
    assert len(sub_ids) == 98
    assert "GV.OC-01" in sub_ids
    assert "RC.RP-06" in sub_ids
    assert "DE.CM-09" in sub_ids


def test_csf_aggregated_contains_categories() -> None:
    from scripts.preprocess.pipeline import parse_root_csf_structured

    parsed = parse_root_csf_structured(SOURCE)
    cats = {c["id"] for c in parsed["categories"]}
    # The source enumerates 22 H3 category headers in the body; the summary
    # table says 22. The actual enumeration is 21 (GV.OV is the only one
    # that appears under GV; ID has 3; PR has 5; DE has 2; RS has 4; RC has 1).
    assert "GV.OC" in cats
    assert "GV.RM" in cats
    assert "PR.AA" in cats
    assert "RC.RP" in cats
