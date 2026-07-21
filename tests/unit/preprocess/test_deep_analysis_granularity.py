"""Tests for DeepAnalysis pair granularity (CORR-PILOT — D-01 macro domain).

The v8/v9 ``parse_crossregulation_subdomain`` extracted the pair block as
a single ``block_text_raw`` blob and only parsed a few legacy fields.
The CORR-PILOT enrichment adds structured fields per pair:

  - ``header_text``, ``classified_relationship_crda``,
    ``verified_relationship_oj``
  - ``oj_quotes_verbatim[]`` (with header, verbatim text, sr_ids, articles,
    annexes)
  - ``comparison_sections[]`` (5 axes: scope, trigger, threshold_timeline,
    recipient, content_template) with reg_a/b values and axis-specific
    markers
  - ``scope_disjoint_test``, ``downstream_implication``, ``p0_notes``,
    ``sr_ids_per_pair``

It also fixes the v10 bug where ``participants_table`` was always empty
for DeepAnalysis files (no H4 "Participants" table). The new fields
``participants``, ``participants_absent``, ``participants_note`` are
populated from the ``<!-- participants: ... -->`` comment + the
prose ``**Participants (from CRDA):**`` paragraph.

These tests run against all 4 sub-domains in D-01 (Data Protection &
Encryption): D-01.1 (pilot), D-01.2, D-01.3, D-01.4. They use
pytest parametrize so the SAME test runs against all 4 files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.preprocess.parsers.narrative import (
    parse_crossregulation_subdomain,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEEP_ROOT = (
    REPO_ROOT
    / "methodology-00"
    / "PREPROCESSING"
    / "CrossRegulation"
    / "DeepAnalysis"
)

# (macro_domain, sub_domain) tuples. All 10 macro-domains from D-01 to
# D-10 are covered (D-08 and D-10 have only 3 sub-domains each).
CASES: list[tuple[str, str]] = []
for macro_dir in sorted(DEEP_ROOT.iterdir()):
    for md in sorted(macro_dir.glob("*.md")):
        CASES.append((macro_dir.name, md.stem))

SUB_DOMAINS = [sd for _, sd in CASES]


def _md_path(sub_domain: str) -> Path:
    for macro, sd in CASES:
        if sd == sub_domain:
            return DEEP_ROOT / macro / f"{sub_domain}.md"
    raise KeyError(f"unknown sub_domain: {sub_domain}")


@pytest.fixture(scope="module", params=SUB_DOMAINS)
def parsed(request) -> dict:
    sd = request.param
    md = _md_path(sd)
    if not md.is_file():
        pytest.skip(f"missing source: {md}")
    return parse_crossregulation_subdomain(md, sub_kind="deep_analysis")


# ─── Top-level structure (parametrized over all 4 files) ──────────────


def test_source_file_exists(parsed) -> None:
    """Sanity: each sub-domain source MD must exist."""
    # The fixture itself skips if missing, but the explicit assert gives
    # a clearer error if a sub_domain is added to SUB_DOMAINS without
    # an MD being present.
    assert parsed is not None


def test_top_level_has_new_participants_fields(parsed) -> None:
    """All DeepAnalysis files must have the new participants fields.

    Some files (D-05.4, D-06.2) have only 1 participant — that's the
    "sole authority" pattern (e.g. GDPR Art. 20 alone for Data
    Portability). Other files (D-07.3, D-07.4) have only 2.
    """
    assert "participants" in parsed
    assert "participants_absent" in parsed
    assert "participants_note" in parsed
    assert isinstance(parsed["participants"], list)
    assert len(parsed["participants"]) >= 1
    # Canonical names only (no aliases like "NIS 2" or "AI Act")
    canonical = {"GDPR", "NIS2", "CRA", "DORA", "AI_Act"}
    for p in parsed["participants"]:
        assert p in canonical, f"non-canonical: {p}"
    for a in parsed["participants_absent"]:
        assert a in canonical, f"non-canonical absent: {a}"


def test_legacy_participants_meta_still_present(parsed) -> None:
    """Backward-compat: legacy ``participants_meta`` is kept."""
    assert "participants_meta" in parsed
    assert isinstance(parsed["participants_meta"], list)


def test_pair_count_is_non_negative(parsed) -> None:
    """pair_count is >= 0. Some files have 0 pairs (sole authority
    pattern — D-05.4, D-06.2). The pair_count and len(pairs) must match."""
    assert parsed["pair_count"] >= 0
    assert len(parsed["pairs"]) == parsed["pair_count"]


# ─── Per-pair structure (parametrized) ────────────────────────────────


def test_each_pair_has_new_structured_fields(parsed) -> None:
    """Every pair must have all the CORR-PILOT new fields."""
    new_fields = {
        "header_text",
        "classified_relationship_crda",
        "verified_relationship_oj",
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
    """reg_a / reg_b must use canonical forms."""
    canonical = {"GDPR", "NIS2", "CRA", "DORA", "AI_Act"}
    for p in parsed["pairs"]:
        assert p["reg_a"] in canonical, p["reg_a"]
        assert p["reg_b"] in canonical, p["reg_b"]


def test_each_pair_has_at_least_one_oj_quote(parsed) -> None:
    """Each pair has at least 1 OJ verbatim quote. Most pairs have 2
    (one per regulation), but some MDs use "[as quoted above]" cross-
    references and only quote one side fresh (e.g. D-10.2 DORA<->AI_Act)."""
    for p in parsed["pairs"]:
        n = len(p["oj_quotes_verbatim"])
        assert n >= 1, (
            f"pair {p['reg_a']}<->{p['reg_b']} has {n} oj_quotes_verbatim"
        )


def test_oj_quotes_have_regulation_sr_articles(parsed) -> None:
    """Each OJ quote must have a normalized regulation + at least one
    extracted identifier (SR-IDs, articles, or annexes)."""
    for p in parsed["pairs"]:
        for q in p["oj_quotes_verbatim"]:
            assert q["regulation"] in {"GDPR", "NIS2", "CRA", "DORA", "AI_Act"}
            assert (
                q["sr_ids"] or q["articles"] or q["annexes"]
            ), f"empty quote for {p['reg_a']}<->{p['reg_b']}: {q}"


def test_oj_quotes_regulations_match_pair(parsed) -> None:
    """The set of oj_quotes_verbatim regulations must be a subset of
    {reg_a, reg_b}. (Some MDs cross-reference a previous pair's quote,
    so we may have 1 quote from one side and 0 from the other.)"""
    for p in parsed["pairs"]:
        regs = {q["regulation"] for q in p["oj_quotes_verbatim"]}
        assert regs.issubset({p["reg_a"], p["reg_b"]}), (
            f"pair {p['reg_a']}<->{p['reg_b']} oj_regs={regs}"
        )


# ─── Comparison sections (the 5 axes) ───────────────────────────────


def test_each_pair_has_at_least_3_comparison_sections(parsed) -> None:
    """Each pair has at least 3 of the 5 canonical axes. Some pairs may
    omit content_template (e.g. D-01.4 NIS2 pairs) but the scope/trigger
    /threshold_timeline triple is always present."""
    for p in parsed["pairs"]:
        axes = {c["axis"] for c in p["comparison_sections"]}
        assert {"scope", "trigger", "threshold_timeline"}.issubset(axes), (
            f"pair {p['reg_a']}<->{p['reg_b']} missing required axes: {axes}"
        )


def test_comparison_sections_have_reg_values(parsed) -> None:
    """Each comparison section must have reg_a_value + reg_b_value."""
    for p in parsed["pairs"]:
        for c in p["comparison_sections"]:
            assert c["reg_a_value"], f"empty reg_a_value: {c}"
            assert c["reg_b_value"], f"empty reg_b_value: {c}"


def test_scope_axis_has_scope_overlap(parsed) -> None:
    """The 'scope' axis must carry a scope_overlap marker."""
    for p in parsed["pairs"]:
        scope = next(
            (c for c in p["comparison_sections"] if c["axis"] == "scope"),
            None,
        )
        assert scope is not None
        assert scope.get("scope_overlap"), (
            f"missing scope_overlap in pair {p['reg_a']}<->{p['reg_b']}"
        )


def test_trigger_axis_has_alignment(parsed) -> None:
    """The 'trigger' axis must carry a trigger_alignment marker."""
    for p in parsed["pairs"]:
        trigger = next(
            (c for c in p["comparison_sections"] if c["axis"] == "trigger"),
            None,
        )
        assert trigger is not None
        assert trigger.get("trigger_alignment"), (
            f"missing trigger_alignment in pair {p['reg_a']}<->{p['reg_b']}"
        )


def test_threshold_axis_has_tension(parsed) -> None:
    """The 'threshold_timeline' axis must carry a tension marker."""
    for p in parsed["pairs"]:
        thr = next(
            (c for c in p["comparison_sections"] if c["axis"] == "threshold_timeline"),
            None,
        )
        assert thr is not None
        assert thr.get("tension"), (
            f"missing tension in pair {p['reg_a']}<->{p['reg_b']}"
        )


# ─── Scope-disjoint test + downstream implication ───────────────────


def test_scope_disjoint_has_verdict(parsed) -> None:
    """scope_disjoint_test.verdict must be one of {Y, N, Conditional}."""
    valid = {"Y", "N", "Conditional"}
    for p in parsed["pairs"]:
        v = p["scope_disjoint_test"].get("verdict", "")
        assert any(v.startswith(x) for x in valid), (
            f"invalid scope_disjoint_test.verdict: {v!r} for {p['reg_a']}<->{p['reg_b']}"
        )


def test_downstream_implication_non_empty(parsed) -> None:
    """Every pair must have a non-empty downstream_implication."""
    for p in parsed["pairs"]:
        assert p["downstream_implication"], (
            f"empty downstream_implication for {p['reg_a']}<->{p['reg_b']}"
        )


def test_p0_notes_is_list(parsed) -> None:
    """p0_notes must be a list (may be empty)."""
    for p in parsed["pairs"]:
        assert isinstance(p["p0_notes"], list), (
            f"p0_notes not a list for {p['reg_a']}<->{p['reg_b']}"
        )


# ─── SR cross-references per pair ────────────────────────────────────


def test_sr_ids_per_pair_is_list(parsed) -> None:
    """sr_ids_per_pair must be a list (may be empty for MDs that don't
    cite SR-IDs inline — e.g. D-04 / D-07 which reference regulations by
    name without the SR-XXX-NNN tag in the pair body)."""
    for p in parsed["pairs"]:
        assert isinstance(p["sr_ids_per_pair"], list), (
            f"sr_ids_per_pair not a list for {p['reg_a']}<->{p['reg_b']}"
        )
        # CORR-035 c3: NIS2 has digits in its canonical name. Use
        # [A-Za-z0-9_]+ (not [A-Z_]+) to match all 5 regulations.
        sr_pat = __import__("re").compile(r"^SR-[A-Za-z0-9_]+-\d{3}$")
        for sr_id in p["sr_ids_per_pair"]:
            assert sr_pat.match(sr_id), f"malformed SR id: {sr_id}"


def test_sr_ids_per_pair_consistent_with_oq_quotes(parsed) -> None:
    """Where SR-IDs are present, they must match the union of SR-IDs
    extracted from oj_quotes_verbatim (same source data, two extractors)."""
    for p in parsed["pairs"]:
        from_oj = set()
        for q in p["oj_quotes_verbatim"]:
            from_oj.update(q["sr_ids"])
        from_pair = set(p["sr_ids_per_pair"])
        # The pair-level SRs should be a SUPERSET of the per-quote SRs
        # (the pair body may cite SRs outside the OJ quote headers).
        assert from_oj.issubset(from_pair), (
            f"pair {p['reg_a']}<->{p['reg_b']}: oj_sr={from_oj}, pair_sr={from_pair}"
        )


# ─── Zero-loss invariant ─────────────────────────────────────────────


def test_raw_md_preserved(parsed) -> None:
    """The zero-loss invariant: raw_md must be present and non-empty."""
    assert parsed["raw_md"]
    assert parsed["raw_md_kept_reason"] == "audit_fallback_for_zero_loss_invariant"


# ─── D-01.1 specific regression (kept from pilot phase) ──────────────


def test_d_01_1_p0_note_in_gdpr_cra() -> None:
    """D-01.1's GDPR<->CRA pair has a P0 note (the SaaS-using-CRA-product
    Orchestrator pattern)."""
    md = _md_path("D-01.1")
    if not md.is_file():
        pytest.skip("D-01.1 source not found")
    parsed = parse_crossregulation_subdomain(md, sub_kind="deep_analysis")
    pair = next(
        p for p in parsed["pairs"] if (p["reg_a"], p["reg_b"]) == ("GDPR", "CRA")
    )
    assert len(pair["p0_notes"]) >= 1
    assert "Orchestrator" in pair["p0_notes"][0]


def test_d_01_1_crda_classification_gdpr_nis2() -> None:
    """D-01.1's GDPR<->NIS2 pair: CRDA says COMPLEMENTARY but the OJ
    verification corrects it to SAME — the two fields must be distinct."""
    md = _md_path("D-01.1")
    if not md.is_file():
        pytest.skip("D-01.1 source not found")
    parsed = parse_crossregulation_subdomain(md, sub_kind="deep_analysis")
    pair = next(
        p for p in parsed["pairs"] if (p["reg_a"], p["reg_b"]) == ("GDPR", "NIS2")
    )
    assert pair["classified_relationship_crda"] == "COMPLEMENTARY"
    assert "SAME" in pair["verified_relationship_oj"]
    assert pair["classified_relationship_crda"] != pair["verified_relationship_oj"]


# ─── Per-file participant sanity (the v10 bug fix) ──────────────────


def test_d_01_1_participants_excludes_ai_act() -> None:
    """D-01.1: AI_Act is absent (sole authority is CRA Annex I)."""
    md = _md_path("D-01.1")
    if not md.is_file():
        pytest.skip("D-01.1 source not found")
    parsed = parse_crossregulation_subdomain(md, sub_kind="deep_analysis")
    assert "AI_Act" not in parsed["participants"]
    assert "AI_Act" in parsed["participants_absent"]


def test_d_01_4_participants_includes_ai_act_partial() -> None:
    """D-01.4: AI_Act is partial present (via Art. 15(3) backup/fail-safe)."""
    md = _md_path("D-01.4")
    if not md.is_file():
        pytest.skip("D-01.4 source not found")
    parsed = parse_crossregulation_subdomain(md, sub_kind="deep_analysis")
    assert "AI_Act" in parsed["participants"]
    # The note should mention "partial" or Art. 15(3)
    assert (
        "partial" in parsed["participants_note"].lower()
        or "Art. 15(3)" in parsed["participants_note"]
    )
