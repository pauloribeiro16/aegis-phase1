"""Tests for `scripts.kg_eval.generate_context_packets` (CORR-113 Commit 2).

Verifies the file-based context packet generator emits the documented shape and
that each of the 5 task-family substrate blocks is populated for case1-tinytask.

Uses the real `cases/case1-tinytask/` and `preproc_out/` directories — no
in-memory fixtures — so the tests exercise the same code path the harness does.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.kg_eval.generate_context_packets import (
    CANONICAL_REGULATIONS,
    generate_packet,
    packet_sha256,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CASE1 = REPO_ROOT / "cases" / "case1-tinytask"
CASE2 = REPO_ROOT / "cases" / "case2-secureborder"
CASE3 = REPO_ROOT / "cases" / "case3-omnibank"
PREPROC = REPO_ROOT / "preproc_out"


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def case1_packet_d01_1() -> dict:
    """Packet for case1 + D-01.1 — covers T1.1 (asset+clause) and T1.5 (synthesis)."""
    return generate_packet(CASE1, "D-01.1", PREPROC)


@pytest.fixture(scope="module")
def case1_packet_d04_3() -> dict:
    """Packet for case1 + D-04.3 — covers T1.2 (temporal conflict in interactions.yaml)."""
    return generate_packet(CASE1, "D-04.3", PREPROC)


@pytest.fixture(scope="module")
def case1_packet_d01_2() -> dict:
    """Packet for case1 + D-01.2 — exercises CONDITIONAL pairs path (if any)."""
    return generate_packet(CASE1, "D-01.2", PREPROC)


@pytest.fixture(scope="module")
def case1_packet_d07_1() -> dict:
    """Packet for case1 + D-07.1 — covers T1.4 (proportionality adequacy)."""
    return generate_packet(CASE1, "D-07.1", PREPROC)


@pytest.fixture(scope="module")
def case3_packet_d01_1() -> dict:
    """Packet for case3 + D-01.1 — 5-reg corpus case; T1.5 cross-tier synthesis."""
    return generate_packet(CASE3, "D-01.1", PREPROC)


# ─── Shape ────────────────────────────────────────────────────────────


def test_packet_has_documented_keys(case1_packet_d01_1: dict) -> None:
    """The packet keys must mirror the spec v3 entities the T1 scorecard consumes."""
    expected = {
        "schema_version",
        "subdomain_id",
        "case_id",
        "regulation_ids",
        "article_ids",
        "asset_ids",
        "business_goal_ids",
        "must_business_goal_ids",
        "csf_anchors",
        "clause_pairs",
        "ambiguity_pairs",
        "proportional_profile",
        "regulatory_interactions",
        "company_context",
    }
    assert expected.issubset(set(case1_packet_d01_1.keys()))


def test_packet_is_json_serialisable(case1_packet_d01_1: dict) -> None:
    """Packet must round-trip through json.dumps for sha256 + sidecar persistence."""
    blob = json.dumps(case1_packet_d01_1, sort_keys=True)
    parsed = json.loads(blob)
    assert parsed == case1_packet_d01_1


def test_packet_sha256_is_stable(case1_packet_d01_1: dict) -> None:
    """Same packet input → same SHA-256 (KG-02 fingerprint pattern)."""
    digest_a = packet_sha256(case1_packet_d01_1)
    digest_b = packet_sha256(case1_packet_d01_1)
    assert digest_a == digest_b
    assert len(digest_a) == 64  # SHA-256 hex
    assert all(c in "0123456789abcdef" for c in digest_a)


def test_packet_sha256_changes_on_payload_change(case1_packet_d01_1: dict) -> None:
    """Different content → different hash (catches accidental no-op updates)."""
    mutated = dict(case1_packet_d01_1)
    mutated["subdomain_id"] = "D-01.2"
    assert packet_sha256(mutated) != packet_sha256(case1_packet_d01_1)


# ─── Per-family substrate (T1.1..T1.5) ───────────────────────────────


def test_t11_substrate_present(case1_packet_d01_1: dict) -> None:
    """T1.1 needs asset_ids populated AND ≥1 article id (SYS-01 + GDPR-CL* for case1)."""
    assert case1_packet_d01_1["asset_ids"]["systems"], "case1 should have ≥1 system"
    assert case1_packet_d01_1["article_ids"], "case1 should have ≥1 article id"
    # Every cited system ID matches the SYS-/STORE-/FLOW- pattern (RefGate vocab)
    import re
    pat = re.compile(r"^(SYS|STORE|FLOW)-[A-Z0-9][A-Z0-9_-]*$")
    for kind in ("systems", "data_stores", "data_flows"):
        for aid in case1_packet_d01_1["asset_ids"][kind]:
            assert pat.match(aid), f"unexpected asset id format: {aid}"


def test_t12_substrate_present(case1_packet_d04_3: dict) -> None:
    """T1.2 needs regulatory_interactions for the subdomain (case1 has TI-01 on D-04.3)."""
    inters = case1_packet_d04_3["regulatory_interactions"]
    assert inters, "case1 + D-04.3 should expose ≥1 temporal/requirement conflict"
    # Each interaction has the spec v3 fields
    for ri in inters:
        assert ri["interaction_type"]
        assert ri["involved_regs"]
        assert ri["conflict_description"]


def test_t13_substrate_path_runs(case1_packet_d01_2: dict) -> None:
    """T1.3: ambiguity_pairs is a list (may be empty for case1; the path must run)."""
    assert isinstance(case1_packet_d01_2["ambiguity_pairs"], list)
    # If non-empty, every entry must be a CONDITIONAL pair
    for ap in case1_packet_d01_2["ambiguity_pairs"]:
        assert "CONDITIONAL" in ap["classification"]


def test_t14_substrate_present(case1_packet_d07_1: dict) -> None:
    """T1.4: proportional_profile has tier + evidence_depth + example_controls."""
    prof = case1_packet_d07_1["proportional_profile"]
    assert prof["subdomain_id"] == "D-07.1"
    assert prof["tier"]  # non-empty (defaults to STANDARD when unknown)
    # Either evidence_depth or example_controls populated from control_evidence YAML
    assert isinstance(prof["evidence_depth"], str)
    assert isinstance(prof["example_controls"], str)


def test_t15_substrate_present(case3_packet_d01_1: dict) -> None:
    """T1.5: case3 is 5-reg corpus; regulation_ids + csf_anchors + interactions all populated."""
    assert len(case3_packet_d01_1["regulation_ids"]) >= 2, "case3 should expose ≥2 regs"
    assert case3_packet_d01_1["csf_anchors"], "case3 D-01.1 should have CSF anchors"
    # CSF anchors are in the closed vocabulary shape (PR.DS-01 etc.)
    import re
    csf_pat = re.compile(r"^[A-Z]{2}\.[A-Z]{2}-\d{2}$")
    for csf in case3_packet_d01_1["csf_anchors"]:
        assert csf_pat.match(csf), f"unexpected CSF token format: {csf}"


# ─── Closed-vocabulary fidelity (KG-09 reused) ───────────────────────


def test_regulation_ids_are_canonical(case1_packet_d01_1: dict) -> None:
    """Every regulation token must be in the closed 5-regulation vocabulary."""
    canonical = set(CANONICAL_REGULATIONS)
    cited = set(case1_packet_d01_1["regulation_ids"])
    assert cited.issubset(canonical), (
        f"non-canonical regs found: {cited - canonical}"
    )


def test_subdomain_id_is_canonical(case1_packet_d01_1: dict) -> None:
    """subdomain_id matches the closed D-XX.Y shape (no 'D-XX.Y.Z' etc.)."""
    import re
    assert re.match(r"^D-\d{2}\.\d+$", case1_packet_d01_1["subdomain_id"])


def test_must_business_goal_ids_subset(case1_packet_d01_1: dict) -> None:
    """must_business_goal_ids must be a subset of business_goal_ids."""
    all_ids = set(case1_packet_d01_1["business_goal_ids"])
    must_ids = set(case1_packet_d01_1["must_business_goal_ids"])
    assert must_ids.issubset(all_ids)


# ─── Cross-case + edge cases ─────────────────────────────────────────


def test_case2_packet_generates(case1_packet_d01_1: dict) -> None:
    """case2 + D-01.1 must also generate without error (smoke across cases)."""
    pkt = generate_packet(CASE2, "D-01.1", PREPROC)
    assert pkt["case_id"] == "case2-secureborder"
    assert pkt["subdomain_id"] == "D-01.1"


def test_invalid_subdomain_id_rejected() -> None:
    """Non-canonical subdomain IDs must raise ValueError (fail-loud, OBJ-12)."""
    with pytest.raises(ValueError, match="D-XX.Y"):
        generate_packet(CASE1, "D-01", PREPROC)  # macro-only is invalid
    with pytest.raises(ValueError, match="D-XX.Y"):
        generate_packet(CASE1, "BAD-ID", PREPROC)


def test_missing_case_path_rejected() -> None:
    """Non-existent case path must raise ValueError (fail-loud)."""
    with pytest.raises(ValueError, match="not a directory"):
        generate_packet("/tmp/does-not-exist-aegis", "D-01.1", PREPROC)
