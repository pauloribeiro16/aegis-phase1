"""Regression tests for CORR-100: layer0_subdomain_refs richness.

GAP (pre-CORR-100): ``_build_layer0_subdomain_refs`` produced refs with
only 9 keys (no ``hso_per_reg`` / ``security_requirements``), so the
P1B-LLM-01 per-regulation prompt payload did not expose the per-reg
SO objective or the SR details to the LLM.

These tests pin the new behaviour so a future refactor cannot silently
drop the enrichment.
"""

import json
from pathlib import Path

import pytest

from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator


@pytest.fixture(scope="module")
def orch() -> Phase1Orchestrator:
    loader = PreprocCatalogLoader(Path("preproc_out"))
    return Phase1Orchestrator(
        work_dir="/tmp/aegis-test-corr100", preproc_catalog=loader
    )


@pytest.fixture(scope="module")
def all_subdomains(orch: Phase1Orchestrator) -> list:
    return orch.preproc_catalog.load_subdomains()


def test_load_subdomains_count(all_subdomains: list) -> None:
    assert len(all_subdomains) == 38, (
        f"expected 38 canonical subdomains, got {len(all_subdomains)}"
    )


def test_ref_has_hso_per_reg(orch: Phase1Orchestrator) -> None:
    refs = orch._build_layer0_subdomain_refs(["D-01.1"])
    assert len(refs) == 1
    ref = refs[0]
    assert "hso_per_reg" in ref, "GAP closed: hso_per_reg must be in ref"
    hso = ref["hso_per_reg"]
    assert isinstance(hso, list)
    assert len(hso) >= 3, (
        f"D-01.1 has 4 participating regs; expected >=3 hso_per_reg, got {len(hso)}"
    )
    for entry in hso:
        assert isinstance(entry, dict)
        assert "id" in entry
        assert "regulation" in entry
        assert "objective" in entry


def test_ref_has_security_requirements(orch: Phase1Orchestrator) -> None:
    refs = orch._build_layer0_subdomain_refs(["D-01.1"])
    assert len(refs) == 1
    ref = refs[0]
    assert "security_requirements" in ref, (
        "GAP closed: security_requirements must be in ref"
    )
    sr = ref["security_requirements"]
    assert isinstance(sr, list)
    assert len(sr) >= 3, (
        f"D-01.1 has 4 SRs; expected >=3 security_requirements, got {len(sr)}"
    )
    for entry in sr:
        assert isinstance(entry, dict)
        assert "id" in entry
        assert "title" in entry
        assert "nist_csf_mapping" in entry, (
            "each SR must carry its NIST CSF mapping"
        )
        assert isinstance(entry["nist_csf_mapping"], list)


def test_ref_hso_per_reg_matches_subdomain(
    orch: Phase1Orchestrator, all_subdomains: list
) -> None:
    refs = orch._build_layer0_subdomain_refs(["D-01.1"])
    ref = refs[0]
    sd = next(s for s in all_subdomains if s.id == "D-01.1")
    expected = [h.model_dump() for h in (sd.hso_per_reg or [])]
    actual = ref["hso_per_reg"]
    assert len(actual) == len(expected), (
        f"hso_per_reg length mismatch: {len(actual)} vs {len(expected)}"
    )
    assert [e["id"] for e in actual] == [e["id"] for e in expected]
    assert [e["regulation"] for e in actual] == [e["regulation"] for e in expected]


def test_enriched_ref_payload_size_within_budget(
    orch: Phase1Orchestrator, all_subdomains: list
) -> None:
    all_ids = [s.id for s in all_subdomains]
    refs = orch._build_layer0_subdomain_refs(all_ids)
    assert len(refs) == 38
    payload_bytes = len(json.dumps(refs, default=str, ensure_ascii=False))
    cap = 600 * 1024
    assert payload_bytes <= cap, (
        f"38 enriched refs payload {payload_bytes} bytes exceeds {cap} bytes (sanity cap)"
    )


def test_existing_keys_still_present(orch: Phase1Orchestrator) -> None:
    refs = orch._build_layer0_subdomain_refs(["D-01.1"])
    ref = refs[0]
    expected_original_keys = {
        "sub_domain_id",
        "title",
        "domain_id",
        "participating_regulations",
        "hso_hl_objective",
        "objective",
        "pairs",
        "anchors",
        "csf",
    }
    for key in expected_original_keys:
        assert key in ref, f"original key {key!r} must remain in ref (no regression)"
