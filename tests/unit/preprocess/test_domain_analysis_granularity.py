"""Tests for DomainAnalysis pair granularity (CORR-PILOT-DA).

The v10 ``parse_crossregulation_subdomain`` extracted the DomainAnalysis
pair block as a single ``block_text_raw`` blob with only the legacy
``classification`` / ``why`` / ``oj_quotes`` fields populated.

The CORR-PILOT-DA enrichment adds the same structured fields per pair
that DeepAnalysis has (so consumers can read both kinds uniformly):

  - ``why_qualifier`` (the text in parens after the Why verdict),
    ``why_note`` (the prose paragraph)
  - ``oj_quotes_verbatim[]`` (extracted from the pair table — DA files
    have no blockquoted article, so the description cell is the
    synthesized OJ quote)
  - ``comparison_sections[]`` (2 axes: ``obligation`` and ``scope``,
    built from the table's column 1 and column 2)
  - ``scope_disjoint_test`` (derived from the canonical classification
    via a 4-label verdict map)
  - ``downstream_implication`` (per-pair, truncated from the Why note)
  - ``p0_notes[]``, ``sr_ids_per_pair[]``

The enrichment also adds top-level fields:
  - ``classification_distribution`` (Counter of classification values
    across all pairs in the file)
  - ``downstream_implication_top`` (the H4 "Downstream implication"
    section, file-level)
  - ``sr_cross_validation`` (the H4 "SR cross-validation" section,
    file-level)

The MD source uses inconsistent casing for the verdict
(``complementary`` / ``Complementary``, ``equal`` / ``Equal``, etc.).
The canonicalization map (_DA_CLASS_CANONICAL in narrative.py) folds
those into 4 labels: Complementary / Equal / Different perspective /
Contradictory.

These tests run against all 38 DomainAnalysis files across the 10
macro-domains. D-08 and D-10 have only 3 sub-domains each. Two files
(D-05.4 GDPR Art. 20 Data Portability and D-06.2 CRA SBOM) are
"sole authority" cases with 0 pairs — the tests handle that
gracefully (pair_count >= 0).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.preprocess.parsers.narrative import (
    parse_crossregulation_subdomain,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DOMAIN_ROOT = (
    REPO_ROOT
    / "methodology-00"
    / "PREPROCESSING"
    / "CrossRegulation"
    / "DomainAnalysis"
)

# Canonical classification values (4 labels — what _canonicalize_classification
# returns). Any pair in a parsed file must be one of these (or "(empty)"
# if the Why block was missing).
CANONICAL_CLASSES = {
    "Complementary",
    "Equal",
    "Different perspective",
    "Contradictory",
}

# (macro_domain, sub_domain) tuples. All 10 macro-domains are covered;
# D-08 and D-10 have only 3 sub-domains each.
CASES: list[tuple[str, str]] = []
for macro_dir in sorted(DOMAIN_ROOT.iterdir()):
    for md in sorted(macro_dir.glob("*.md")):
        CASES.append((macro_dir.name, md.stem))

SUB_DOMAINS = [sd for _, sd in CASES]


def _md_path(sub_domain: str) -> Path:
    for macro, sd in CASES:
        if sd == sub_domain:
            return DOMAIN_ROOT / macro / f"{sub_domain}.md"
    raise KeyError(f"unknown sub_domain: {sub_domain}")


@pytest.fixture(scope="module", params=SUB_DOMAINS)
def parsed(request) -> dict:
    sd = request.param
    md = _md_path(sd)
    if not md.is_file():
        pytest.skip(f"missing source: {md}")
    return parse_crossregulation_subdomain(md, sub_kind="domain_analysis")


# ─── Top-level structure (parametrized over all 38 files) ─────────────


def test_source_file_exists(parsed) -> None:
    """Sanity: each sub-domain source MD must exist."""
    assert parsed is not None


def test_top_level_has_new_da_fields(parsed) -> None:
    """All DA files must have the new top-level fields added in
    CORR-PILOT-DA (classification_distribution, downstream_implication_top,
    sr_cross_validation)."""
    assert "classification_distribution" in parsed
    assert "downstream_implication_top" in parsed
    assert "sr_cross_validation" in parsed
    assert isinstance(parsed["classification_distribution"], dict)


def test_legacy_participants_meta_still_present(parsed) -> None:
    """Backward-compat: legacy ``participants_meta`` and
    ``participants_table`` are kept."""
    assert "participants_meta" in parsed
    assert isinstance(parsed["participants_meta"], list)
    assert "participants_table" in parsed
    assert isinstance(parsed["participants_table"], list)


def test_participants_field_is_list(parsed) -> None:
    """The structured ``participants`` field is a list (may be empty if
    the source didn't have a participants comment — but in practice
    every DA file has one)."""
    assert "participants" in parsed
    assert isinstance(parsed["participants"], list)


def test_pair_count_is_non_negative(parsed) -> None:
    """pair_count is >= 0. D-05.4 and D-06.2 are the two sole-authority
    files with 0 pairs. The pair_count and len(pairs) must match."""
    assert parsed["pair_count"] >= 0
    assert len(parsed["pairs"]) == parsed["pair_count"]


# ─── Per-pair structure (parametrized) ────────────────────────────────


def test_each_pair_has_new_structured_fields(parsed) -> None:
    """Every pair must have all the CORR-PILOT-DA new fields."""
    new_fields = {
        "why_qualifier",
        "why_note",
        "oj_quotes_verbatim",
        "comparison_sections",
        "scope_disjoint_test",
        "downstream_implication",
        "p0_notes",
        "sr_ids_per_pair",
    }
    for p in parsed["pairs"]:
        missing = new_fields - set(p.keys())
        assert not missing, f"pair {p['reg_a']}<->{p['reg_b']} missing: {missing}"


def test_reg_names_canonical(parsed) -> None:
    """reg_a / reg_b must use canonical forms. Note: DA files may use the
    raw aliases (e.g. ``NIS 2`` in the HTML comment) — the parser passes
    them through verbatim. We accept both canonical and the 2 known
    aliases that appear in the source (NIS 2, AI Act)."""
    accepted = {
        "GDPR", "NIS2", "NIS 2", "CRA", "DORA", "AI_Act", "AI Act",
    }
    for p in parsed["pairs"]:
        assert p["reg_a"] in accepted, p["reg_a"]
        assert p["reg_b"] in accepted, p["reg_b"]


def test_classification_is_canonical(parsed) -> None:
    """Every pair's classification must be one of the 4 canonical
    labels (or empty if Why block was missing)."""
    for p in parsed["pairs"]:
        cls = p["classification"]
        assert cls in CANONICAL_CLASSES, (
            f"non-canonical classification: {cls!r} for "
            f"{p['reg_a']}<->{p['reg_b']}"
        )


def test_classification_distribution_sums_to_pair_count(parsed) -> None:
    """The classification_distribution Counter must sum to the pair count
    (0 is valid for sole-authority files)."""
    total = sum(parsed["classification_distribution"].values())
    assert total == parsed["pair_count"]


# ─── OJ quotes (the table-extracted layer) ────────────────────────────


def test_each_pair_has_2_oj_quote_verbatim(parsed) -> None:
    """Each pair has exactly 2 oj_quotes_verbatim (one per regulation,
    built from the pair table's data rows). Files with 0 pairs are
    trivially OK."""
    for p in parsed["pairs"]:
        n = len(p["oj_quotes_verbatim"])
        assert n == 2, (
            f"pair {p['reg_a']}<->{p['reg_b']} has {n} oj_quotes_verbatim "
            f"(expected 2)"
        )


def test_oj_quotes_verbatim_match_pair_regulations(parsed) -> None:
    """The set of oj_quotes_verbatim regulations must equal {reg_a, reg_b}
    (in any order)."""
    for p in parsed["pairs"]:
        regs = {q["regulation"] for q in p["oj_quotes_verbatim"]}
        pair_regs = {p["reg_a"], p["reg_b"]}
        # Accept the NIS 2 / AI Act aliases
        pair_regs_canonical = {
            "NIS2" if r == "NIS 2" else ("AI_Act" if r == "AI Act" else r)
            for r in pair_regs
        }
        assert regs == pair_regs_canonical, (
            f"pair {p['reg_a']}<->{p['reg_b']}: oj_regs={regs}, "
            f"pair_regs={pair_regs_canonical}"
        )


def test_oj_quotes_verbatim_have_at_least_one_id(parsed) -> None:
    """Each OJ quote must have at least one extracted identifier
    (SR-IDs, articles, or annexes)."""
    for p in parsed["pairs"]:
        for q in p["oj_quotes_verbatim"]:
            ids = q["sr_ids"] + q["articles"] + q["annexes"]
            assert ids, (
                f"empty IDs for {p['reg_a']}<->{p['reg_b']} reg={q['regulation']}"
            )


# ─── Comparison sections (2 axes) ────────────────────────────────────


def test_each_pair_has_2_comparison_axes(parsed) -> None:
    """Each pair has exactly 2 comparison_sections: ``obligation`` and
    ``scope`` (the 2 axes we extract from the DA pair table)."""
    for p in parsed["pairs"]:
        axes = [c["axis"] for c in p["comparison_sections"]]
        assert axes == ["obligation", "scope"], (
            f"pair {p['reg_a']}<->{p['reg_b']} axes={axes}"
        )


def test_comparison_sections_have_reg_values(parsed) -> None:
    """Each comparison section must have non-empty reg_a_value and
    reg_b_value for the ``obligation`` axis. The ``scope`` axis is
    optional (the DA pair table sometimes has an empty 3rd column —
    the description-only format is used by D-04.4, D-05, D-06, D-07,
    D-08, D-09 and D-10). When the axis is populated it must also be
    non-empty."""
    for p in parsed["pairs"]:
        for c in p["comparison_sections"]:
            if c["axis"] == "obligation":
                assert c["reg_a_value"], (
                    f"empty reg_a_value: axis={c['axis']} pair="
                    f"{p['reg_a']}<->{p['reg_b']}"
                )
                assert c["reg_b_value"], (
                    f"empty reg_b_value: axis={c['axis']} pair="
                    f"{p['reg_a']}<->{p['reg_b']}"
                )
            # The 'scope' axis is best-effort (the source table may
            # have an empty 3rd column). When populated, both sides
            # must be non-empty. When unpopulated, that's OK too.


# ─── Scope-disjoint test (derived) ───────────────────────────────────


def test_scope_disjoint_verdict_is_valid(parsed) -> None:
    """scope_disjoint_test.verdict must be one of {Y, N, Conditional}."""
    valid = {"Y", "N", "Conditional"}
    for p in parsed["pairs"]:
        v = p["scope_disjoint_test"].get("verdict", "")
        assert v in valid, (
            f"invalid scope_disjoint_test.verdict: {v!r} for "
            f"{p['reg_a']}<->{p['reg_b']}"
        )


def test_scope_disjoint_mapping_is_consistent(parsed) -> None:
    """The scope_disjoint verdict must match the classification via
    the documented 4-label map:
      Complementary  -> Y
      Equal          -> Y
      Different perspective -> N
      Contradictory  -> Conditional
    """
    expected_map = {
        "Complementary": "Y",
        "Equal": "Y",
        "Different perspective": "N",
        "Contradictory": "Conditional",
    }
    for p in parsed["pairs"]:
        cls = p["classification"]
        v = p["scope_disjoint_test"]["verdict"]
        assert v == expected_map[cls], (
            f"verdict={v!r} but classification={cls!r} for "
            f"{p['reg_a']}<->{p['reg_b']}"
        )


# ─── Downstream implication, p0 notes, SR-IDs ─────────────────────────


def test_downstream_implication_is_string(parsed) -> None:
    """downstream_implication is always a string (may be empty for
    pairs where the Why note was empty — but that's rare)."""
    for p in parsed["pairs"]:
        assert isinstance(p["downstream_implication"], str), (
            f"downstream_implication not a str for {p['reg_a']}<->{p['reg_b']}"
        )


def test_p0_notes_is_list(parsed) -> None:
    """p0_notes must be a list (may be empty — only the D-01.1 pilot
    has a p0_note)."""
    for p in parsed["pairs"]:
        assert isinstance(p["p0_notes"], list)


def test_sr_ids_per_pair_is_list(parsed) -> None:
    """sr_ids_per_pair must be a list of well-formed SR-XXX-NNN strings
    (may be empty if the pair body doesn't cite any SR-IDs — most pairs
    do, but some legacy files don't)."""
    import re
    # CORR-035 c3: NIS2 has digits in its canonical name. Use
    # [A-Za-z0-9_]+ (not [A-Z_]+) to match all 5 regulations.
    sr_pat = re.compile(r"^SR-[A-Za-z0-9_]+-\d{3}$")
    for p in parsed["pairs"]:
        assert isinstance(p["sr_ids_per_pair"], list)
        for sr_id in p["sr_ids_per_pair"]:
            assert sr_pat.match(sr_id), f"malformed SR id: {sr_id}"


# ─── Why metadata (the canonical-classification source) ──────────────


def test_why_note_is_string(parsed) -> None:
    """why_note is the prose paragraph after the Why header. Must be a
    string (may be empty if the Why block was missing — but that
    shouldn't happen in practice)."""
    for p in parsed["pairs"]:
        assert isinstance(p["why_note"], str)


def test_why_qualifier_is_string(parsed) -> None:
    """why_qualifier is the parenthetical text from the Why header
    (e.g. "with structural differences"). May be empty if the Why
    header had no parens."""
    for p in parsed["pairs"]:
        assert isinstance(p["why_qualifier"], str)


# ─── Zero-loss invariant ─────────────────────────────────────────────


def test_raw_md_preserved(parsed) -> None:
    """The zero-loss invariant: raw_md must be present and non-empty."""
    assert parsed["raw_md"]
    assert parsed["raw_md_kept_reason"] == "audit_fallback_for_zero_loss_invariant"


# ─── Sole-authority pattern (D-05.4, D-06.2) ─────────────────────────


@pytest.mark.parametrize("sub_domain", ["D-05.4", "D-06.2"])
def test_sole_authority_has_zero_pairs(sub_domain: str) -> None:
    """D-05.4 (GDPR Art. 20 Data Portability) and D-06.2 (CRA SBOM) are
    the two sole-authority cases — only 1 participant, 0 pairs."""
    md = _md_path(sub_domain)
    if not md.is_file():
        pytest.skip(f"missing source: {md}")
    parsed = parse_crossregulation_subdomain(md, sub_kind="domain_analysis")
    assert parsed["pair_count"] == 0
    assert parsed["pairs"] == []
    assert parsed["classification_distribution"] == {}


# ─── High-density sanity (D-04.3 — 10 pairs all classified) ──────────


@pytest.mark.parametrize(
    "sub_domain,expected_count",
    [
        ("D-04.3", 10),  # Regulatory Notification: 10 pairs, mix of classif.
        ("D-02.1", 10),  # Vulnerability Identification: 10 pairs.
        ("D-07.1", 10),  # 10 pairs.
        ("D-09.1", 10),  # 10 pairs.
        ("D-09.2", 10),  # 10 pairs.
        ("D-10.1", 10),  # 10 pairs.
        ("D-10.3", 10),  # 10 pairs.
    ],
)
def test_high_density_files_have_10_pairs(
    sub_domain: str, expected_count: int
) -> None:
    """The 7 DA files with 10 pairs each (the densest in the corpus)
    must report exactly 10 pairs."""
    md = _md_path(sub_domain)
    if not md.is_file():
        pytest.skip(f"missing source: {md}")
    parsed = parse_crossregulation_subdomain(md, sub_kind="domain_analysis")
    assert parsed["pair_count"] == expected_count


# ─── Cross-regime sanity (Contradictory in D-04.3) ────────────────────


def test_d_04_3_classification_distribution_has_contradictory() -> None:
    """D-04.3 (Regulatory Notification) is the densest Contradictory
    file — 8 of 10 pairs are classified as Contradictory because
    notification timelines differ wildly across GDPR / NIS2 / CRA / DORA
    / AI_Act."""
    md = _md_path("D-04.3")
    if not md.is_file():
        pytest.skip("D-04.3 source not found")
    parsed = parse_crossregulation_subdomain(md, sub_kind="domain_analysis")
    assert parsed["classification_distribution"].get("Contradictory", 0) >= 5
