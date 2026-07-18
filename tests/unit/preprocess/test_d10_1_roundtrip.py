"""CORR-024 groundtruth test: D-10.1 must round-trip to a known shape.

Asserts the parser extracts the expected counts and key anchors from
``methodology-00/PREPROCESSING/SubDomains/D-10_Monitoring-Audit/D-10.1.md``.

This is the C4 acceptance criterion from the contract.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE = REPO_ROOT / "methodology-00" / "PREPROCESSING" / "SubDomains" / "D-10_Monitoring-Audit" / "D-10.1.md"


def test_d10_1_source_exists() -> None:
    assert SOURCE.is_file(), f"missing source: {SOURCE}"


def test_d10_1_parses_cleanly() -> None:
    from scripts.preprocess.parsers.subdomain import parse_subdomain

    parsed = parse_subdomain(SOURCE)

    # Top-level shape
    assert parsed["schema_version"] == "1.0"
    assert parsed["subdomain_id"] == "D-10.1"
    assert parsed["domain_id"] == "D-10"
    assert "Continuous Security Monitoring" in parsed["title"]

    # Sections exist (with raw_md preserved)
    for sec in ("cross_reg_analysis", "hso", "security_requirements"):
        assert sec in parsed["sections"], f"missing section: {sec}"
        assert parsed["sections"][sec]["raw_md"], f"empty raw_md for {sec}"

    # 10 pairs (5×5 minus self, minus 0 disjoint) per the §1.1 scope-overlap matrix
    pairs = parsed["sections"]["cross_reg_analysis"]["pairs"]
    assert len(pairs) == 10, f"expected 10 pairs, got {len(pairs)}: {[p['pair'] for p in pairs]}"
    pair_labels = {p["pair"] for p in pairs}
    expected_pairs = {
        "GDPR ↔ NIS2", "GDPR ↔ CRA", "GDPR ↔ DORA", "GDPR ↔ AI_Act",
        "NIS2 ↔ CRA", "NIS2 ↔ DORA", "NIS2 ↔ AI_Act",
        "CRA ↔ DORA", "CRA ↔ AI_Act", "DORA ↔ AI_Act",
    }
    assert pair_labels == expected_pairs, f"missing pairs: {expected_pairs - pair_labels}"

    # At least 1 pair flagged Layer 2 (the CRA opt-out tension propagates to 3 pairs)
    layer2_pairs = [p["pair"] for p in pairs if p["layer2_flag"]]
    assert len(layer2_pairs) >= 1, "no Layer-2 flagged pair found"

    # HL HSO must exist
    hl = parsed["sections"]["hso"]["hl"]
    assert hl, "HL HSO is empty"
    assert "monitoring" in hl["objective"].lower() or "monitor" in hl["objective"].lower(), (
        f"HL objective should mention monitoring; got: {hl['objective'][:120]}"
    )
    assert len(hl["anchors"]) > 0, "HL has no anchors"

    # Per-reg sub-SOs: 5 participating regulations → 5 sub-SOs
    sub_sos = parsed["sections"]["hso"]["sub_sos"]
    assert len(sub_sos) == 5, f"expected 5 sub-SOs, got {len(sub_sos)}"
    regs = {s["regulation"] for s in sub_sos}
    assert regs == {"GDPR", "NIS2", "CRA", "DORA", "AI_Act"}, f"got regs: {regs}"

    # Each sub-SO has a non-empty objective and at least 1 anchor
    for s in sub_sos:
        assert s["objective"], f"sub-SO {s['sub_so_id']} has empty objective"
        assert s["anchors"], f"sub-SO {s['sub_so_id']} has no anchors"

    # Security Requirements: D-10.1 has 5 SRs (one per participating reg)
    srs = parsed["sections"]["security_requirements"]["srs"]
    assert len(srs) == 5, f"expected 5 SRs, got {len(srs)}: {[s['sr_id'] for s in srs]}"

    # Critical: GDPR Art. 32(2) must be among the HL anchors
    hl_anchors = " ".join(hl["anchors"])
    assert "Art. 32" in hl_anchors, f"HL anchors missing GDPR Art. 32: {hl_anchors}"

    # Critical: CRA Annex I Part I (2)(l) must be in the CRA sub-SO anchors
    cra_sub = next(s for s in sub_sos if s["regulation"] == "CRA")
    cra_anchors = " ".join(cra_sub["anchors"])
    assert "Annex I" in cra_anchors, f"CRA sub-SO anchors missing Annex I: {cra_anchors}"


def test_d10_1_no_warnings() -> None:
    from scripts.preprocess.parsers.subdomain import parse_subdomain

    parsed = parse_subdomain(SOURCE)
    assert parsed["warnings"] == [], f"parser warnings: {parsed['warnings']}"
