"""Regression tests for CORR-100: layer0_subdomain_refs richness.

GAP (pre-CORR-100): ``_build_layer0_subdomain_refs`` produced refs with
only 9 keys (no ``hso_per_reg`` / ``security_requirements``), so the
P1B-LLM-01 per-regulation prompt payload did not expose the per-reg
SO objective or the SR details to the LLM.

These tests pin the new behaviour so a future refactor cannot silently
drop the enrichment.

CORR-101 Gap 2: added 2 tests covering the manifest enrichment
(``manifest_ai_act``, ``manifest_nist_controls``).
"""

import json
from pathlib import Path

import pytest

from aegis_phase1.v2.loader.manifest_loader import ManifestLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator


@pytest.fixture(scope="module")
def orch() -> Phase1Orchestrator:
    loader = PreprocCatalogLoader(Path("preproc_out"))
    return Phase1Orchestrator(work_dir="/tmp/aegis-test-corr100", preproc_catalog=loader)


@pytest.fixture(scope="module")
def orch_with_manifest() -> Phase1Orchestrator:
    """Phase1Orchestrator with a ManifestLoader injected (CORR-101 Gap 2)."""
    loader = PreprocCatalogLoader(Path("preproc_out"))
    manifest_loader = ManifestLoader()
    return Phase1Orchestrator(
        work_dir="/tmp/aegis-test-corr101",
        preproc_catalog=loader,
        manifest_loader=manifest_loader,
    )


@pytest.fixture(scope="module")
def all_subdomains(orch: Phase1Orchestrator) -> list:
    return orch.preproc_catalog.load_subdomains()


def test_load_subdomains_count(all_subdomains: list) -> None:
    assert len(all_subdomains) == 38, f"expected 38 canonical subdomains, got {len(all_subdomains)}"


def test_ref_has_hso_per_reg(orch: Phase1Orchestrator) -> None:
    refs = orch._build_layer0_subdomain_refs(["D-01.1"])
    assert len(refs) == 1
    ref = refs[0]
    assert "hso_per_reg" in ref, "GAP closed: hso_per_reg must be in ref"
    hso = ref["hso_per_reg"]
    assert isinstance(hso, list)
    assert (
        len(hso) >= 3
    ), f"D-01.1 has 4 participating regs; expected >=3 hso_per_reg, got {len(hso)}"
    for entry in hso:
        assert isinstance(entry, dict)
        assert "id" in entry
        assert "regulation" in entry
        assert "objective" in entry


def test_ref_has_security_requirements(orch: Phase1Orchestrator) -> None:
    refs = orch._build_layer0_subdomain_refs(["D-01.1"])
    assert len(refs) == 1
    ref = refs[0]
    assert "security_requirements" in ref, "GAP closed: security_requirements must be in ref"
    sr = ref["security_requirements"]
    assert isinstance(sr, list)
    assert len(sr) >= 3, f"D-01.1 has 4 SRs; expected >=3 security_requirements, got {len(sr)}"
    for entry in sr:
        assert isinstance(entry, dict)
        assert "id" in entry
        assert "title" in entry
        assert "nist_csf_mapping" in entry, "each SR must carry its NIST CSF mapping"
        assert isinstance(entry["nist_csf_mapping"], list)


def test_ref_hso_per_reg_matches_subdomain(orch: Phase1Orchestrator, all_subdomains: list) -> None:
    refs = orch._build_layer0_subdomain_refs(["D-01.1"])
    ref = refs[0]
    sd = next(s for s in all_subdomains if s.id == "D-01.1")
    expected = [h.model_dump() for h in (sd.hso_per_reg or [])]
    actual = ref["hso_per_reg"]
    assert len(actual) == len(
        expected
    ), f"hso_per_reg length mismatch: {len(actual)} vs {len(expected)}"
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
    assert (
        payload_bytes <= cap
    ), f"38 enriched refs payload {payload_bytes} bytes exceeds {cap} bytes (sanity cap)"


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


# --- CORR-101 Gap 2: manifest enrichment tests ---------------------------


def test_ref_has_manifest_ai_act(
    orch_with_manifest: Phase1Orchestrator,
) -> None:
    """When manifest_loader is injected, each ref has ``manifest_ai_act``."""
    refs = orch_with_manifest._build_layer0_subdomain_refs(["D-01.1", "D-01.4"])
    assert len(refs) == 2
    for ref in refs:
        assert "manifest_ai_act" in ref, (
            f"CORR-101 Gap 2: ref {ref['sub_domain_id']} must carry "
            f"manifest_ai_act when manifest_loader is injected."
        )
        assert ref["manifest_ai_act"] in ("absent", "partial", "present"), (
            f"manifest_ai_act must be one of the 3 valid states; " f"got {ref['manifest_ai_act']!r}"
        )
    # Specifically: D-01.4 is "partial", D-01.1 is "absent"
    by_id = {r["sub_domain_id"]: r for r in refs}
    assert by_id["D-01.4"]["manifest_ai_act"] == "partial"
    assert by_id["D-01.1"]["manifest_ai_act"] == "absent"


def test_ref_manifest_nist_controls_consistent(
    orch_with_manifest: Phase1Orchestrator,
) -> None:
    """For D-01 + GDPR, ``manifest_nist_controls`` length > 0."""
    refs = orch_with_manifest._build_layer0_subdomain_refs(["D-01.1", "D-01.4"])
    for ref in refs:
        assert "manifest_nist_controls" in ref, (
            f"CORR-101 Gap 2: ref {ref['sub_domain_id']} must carry "
            f"manifest_nist_controls when manifest_loader is injected."
        )
        assert isinstance(ref["manifest_nist_controls"], list)
    # D-01 has GDPR in participating; the manifest should contribute
    # GDPR's NIST controls (PR.DS-01, PR.DS-02, PR.DS-10, PR.DS-12,
    # PR.IR-01, PR.IR-03) — at minimum 6 entries.
    by_id = {r["sub_domain_id"]: r for r in refs}
    for sid in ("D-01.1", "D-01.4"):
        nist = by_id[sid]["manifest_nist_controls"]
        assert len(nist) >= 6, (
            f"{sid}: expected ≥6 NIST controls from D-01 manifest "
            f"(GDPR + CRA + DORA + NIS2), got {len(nist)}: {nist}"
        )
        # Controls are sorted
        assert nist == sorted(nist), f"{sid}: manifest_nist_controls must be sorted: {nist}"
        # Controls are deduplicated
        assert len(nist) == len(
            set(nist)
        ), f"{sid}: manifest_nist_controls must be deduplicated: {nist}"


def test_ref_without_manifest_loader_omits_enrichment(
    orch: Phase1Orchestrator,
) -> None:
    """When manifest_loader is NOT injected, refs do not have manifest fields."""
    refs = orch._build_layer0_subdomain_refs(["D-01.1"])
    ref = refs[0]
    assert "manifest_ai_act" not in ref, (
        "Without manifest_loader, refs must NOT carry manifest_ai_act "
        "(back-compat: pre-CORR-101 callers should not see new fields)."
    )
    assert "manifest_nist_controls" not in ref
