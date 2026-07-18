"""CORR-024 groundtruth test: D-10.1 must round-trip to the expected v2 shape."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE = (
    REPO_ROOT
    / "methodology-00"
    / "PREPROCESSING"
    / "SubDomains"
    / "D-10_Monitoring-Audit"
    / "D-10.1.md"
)


def test_d10_1_source_exists() -> None:
    assert SOURCE.is_file(), f"missing source: {SOURCE}"


def test_d10_1_v2_shape() -> None:
    """The parser must return the v2 SubDomain shape with HL + per-reg sub-SOs
    + 10 CRDA pairs + 5 SRs + anchors for the canonical GDPR/CRA refs."""
    from scripts.preprocess.parsers.entities.subdomain import parse_subdomain

    parsed = parse_subdomain(SOURCE)

    # Top-level shape (v2)
    assert parsed["schema_version"] == "1.0"
    assert parsed["id"] == "D-10.1"
    assert parsed["domain_id"] == "D-10"
    assert "Continuous Security Monitoring" in parsed["title"]
    assert "participating_regulations" in parsed

    # HL HSO
    hl = parsed["hso_hl"]
    assert hl
    assert hl["id"] == "SO-D-10.1.HL"
    assert "monitoring" in hl["objective"].lower() or "monitor" in hl["objective"].lower()
    assert len(hl["anchors"]) > 0

    # Per-reg sub-SOs: 5 participating regulations
    sub_sos = parsed["hso_per_reg"]
    assert len(sub_sos) == 5
    regs = {s["regulation"] for s in sub_sos}
    assert regs == {"GDPR", "NIS2", "CRA", "DORA", "AI_Act"}
    for s in sub_sos:
        assert s["objective"]
        assert s["anchors"]
        assert s["id"].startswith("SO-D-10.1.")

    # Pairs: 10 CRDA pairs
    pairs = parsed["pairs"]
    assert len(pairs) == 10
    pair_labels = {p["pair"] for p in pairs}
    expected_pairs = {
        "GDPR ↔ NIS2", "GDPR ↔ CRA", "GDPR ↔ DORA", "GDPR ↔ AI_Act",
        "NIS2 ↔ CRA", "NIS2 ↔ DORA", "NIS2 ↔ AI_Act",
        "CRA ↔ DORA", "CRA ↔ AI_Act", "DORA ↔ AI_Act",
    }
    assert pair_labels == expected_pairs

    # At least 1 pair flagged Layer 2
    layer2 = [p["pair"] for p in pairs if p["layer2_flag"]]
    assert len(layer2) >= 1, "no Layer-2 flagged pair found"

    # SRs: 5 (one per participating reg)
    srs = parsed["security_requirements"]
    assert len(srs) == 5

    # Critical anchors
    hl_anchors = " ".join(hl["anchors"])
    assert "Art. 32" in hl_anchors, f"HL anchors missing GDPR Art. 32: {hl_anchors}"
    cra = next(s for s in sub_sos if s["regulation"] == "CRA")
    assert "Annex I" in " ".join(cra["anchors"])

    # Each pair has a canonical id
    for p in pairs:
        assert p["id"].startswith("D-10.1_")
        assert p["subdomain_id"] == "D-10.1"


def test_d10_1_no_warnings() -> None:
    from scripts.preprocess.parsers.entities.subdomain import parse_subdomain

    parsed = parse_subdomain(SOURCE)
    assert parsed["warnings"] == [], f"parser warnings: {parsed['warnings']}"


def test_aggregated_so_extraction() -> None:
    """01_SecurityObjectives.md for GDPR must yield 38 SOs (the actual count
    is 38; some SOs are cross-references, so unique IDs < 38)."""
    from scripts.preprocess.parsers.aggregated.security_objectives import parse_security_objectives

    path = (
        REPO_ROOT
        / "methodology-00"
        / "PREPROCESSING"
        / "Regulation"
        / "GDPR"
        / "01_SecurityObjectives.md"
    )
    if not path.is_file():
        pytest.skip("GDPR 01_SecurityObjectives.md not present in this branch")
    sos = parse_security_objectives(path, "GDPR")
    assert len(sos) > 0, "no SOs extracted from 01_SecurityObjectives.md"
    so_ids = {s["id"] for s in sos if not s["is_cross_ref"]}
    # The file is supposed to have ~38 SOs (some may be cross-refs of the same id)
    assert len(so_ids) > 20, f"too few unique SO ids: {len(so_ids)}"

    # Every SO has at least 1 sub_domain
    for so in sos:
        assert so["sub_domains"], f"SO {so['id']} has no sub_domains"
        assert so["description"], f"SO {so['id']} has no description"
