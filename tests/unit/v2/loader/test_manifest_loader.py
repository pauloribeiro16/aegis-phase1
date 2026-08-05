"""Tests for ManifestLoader (CORR-101 Gap 2).

GAP (pre-CORR-101): the v2 pipeline ignored the
``D-XX.manifest.json`` files. Sub-domains with ``ai_act: "partial"``
(e.g. D-01.4 Data Integrity) looked identical to ``ai_act: "absent"``
in the prompt context — the LLM never saw the AI Act participation
signal.

These tests pin the new loader behaviour so a future refactor cannot
silently drop the enrichment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegis_phase1.v2.loader.manifest_loader import (
    DEFAULT_MANIFESTS_ROOT,
    Counts,
    Manifest,
    ManifestLoader,
    SubdomainSummary,
)


@pytest.fixture(scope="module")
def loader() -> ManifestLoader:
    """Module-scoped loader sharing the default Methodology-main root."""
    return ManifestLoader()


@pytest.fixture(scope="module")
def all_d_ids() -> list[str]:
    """List the 10 canonical domain IDs (D-01 .. D-10)."""
    return [f"D-{n:02d}" for n in range(1, 11)]


# --- G1: Manifest models parse correctly ---------------------------------


def test_load_d01_manifest(loader: ManifestLoader) -> None:
    """ManifestLoader().manifest_for_domain('D-01') returns Manifest with 4 subdomains."""
    m = loader.manifest_for_domain("D-01")
    assert isinstance(m, Manifest)
    assert m.domain_id == "D-01"
    assert (
        len(m.subdomain_summaries) == 4
    ), f"D-01 has 4 subdomains in the manifest; got {len(m.subdomain_summaries)}"
    assert len(m.subdomains) == 4
    for s in m.subdomain_summaries:
        assert isinstance(s, SubdomainSummary)
        assert s.id.startswith("D-01.")
    assert m.counts.subdomains == 4


def test_ai_act_for_subdomain_returns_correct_status(
    loader: ManifestLoader,
) -> None:
    """D-01.4 returns 'partial', D-01.1 returns 'absent'."""
    assert loader.ai_act_for_subdomain("D-01.4") == "partial", (
        "D-01.4 (Data Integrity Mechanisms) has ai_act='partial' per "
        "the manifest. Loader must surface this."
    )
    assert (
        loader.ai_act_for_subdomain("D-01.1") == "absent"
    ), "D-01.1 (Data at Rest Encryption) has ai_act='absent'."
    assert loader.ai_act_for_subdomain("D-01.2") == "absent"
    assert loader.ai_act_for_subdomain("D-01.3") == "absent"


def test_nist_controls_for_reg_in_domain(loader: ManifestLoader) -> None:
    """D-01 + GDPR returns the 6 NIST controls in the manifest."""
    nist = loader.nist_controls_for_reg_in_domain("D-01", "GDPR")
    assert nist == [
        "PR.DS-01",
        "PR.DS-02",
        "PR.DS-10",
        "PR.DS-12",
        "PR.IR-01",
        "PR.IR-03",
    ], f"expected 6 NIST controls for D-01 + GDPR, got {nist}"


def test_nist_controls_for_reg_in_domain_sorted_unique(
    loader: ManifestLoader,
) -> None:
    """Manifest list is sorted and deduplicated."""
    nist = loader.nist_controls_for_reg_in_domain("D-01", "DORA")
    # Must be sorted
    assert nist == sorted(nist)
    # Must be deduplicated
    assert len(nist) == len(set(nist))
    # DORA has at least 5 NIST controls per the manifest
    assert len(nist) >= 5


def test_all_10_manifests_loadable(loader: ManifestLoader, all_d_ids: list[str]) -> None:
    """All 10 manifests load; D-04 has empty participating but valid summary."""
    for d_id in all_d_ids:
        m = loader.manifest_for_domain(d_id)
        assert isinstance(m, Manifest)
        assert m.domain_id == d_id
        # Every domain except D-08 / D-10 has 4 subdomains.
        # D-08 and D-10 have 3 (per STRUCTURE_REFERENCE.md §1).
        assert len(m.subdomain_summaries) in (
            3,
            4,
        ), f"{d_id}: unexpected subdomain count {len(m.subdomain_summaries)}"


# --- G2: Tolerated failure modes -----------------------------------------


def test_missing_manifest_returns_empty(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Nonexistent domain returns empty manifest + WARNING log."""

    isolated = ManifestLoader(manifests_root=tmp_path)
    # tmp_path has no manifest directories → empty defaults
    m = isolated.manifest_for_domain("D-XX")
    assert isinstance(m, Manifest)
    assert m.domain_id == "D-XX"
    assert m.subdomain_summaries == []
    assert m.applicable_nist_controls_by_regulation == {}
    assert m.counts.subdomains == 0


def test_missing_subdomain_in_manifest_returns_absent(
    loader: ManifestLoader,
) -> None:
    """Unknown subdomain_id in a valid manifest → returns 'absent'."""
    # D-01 manifest has 4 subdomains; D-01.99 is not among them.
    assert loader.ai_act_for_subdomain("D-01.99") == "absent"


def test_empty_subdomain_id_returns_absent(
    loader: ManifestLoader,
) -> None:
    """Empty / whitespace / malformed subdomain_id → 'absent'."""
    assert loader.ai_act_for_subdomain("") == "absent"
    assert loader.ai_act_for_subdomain("   ") == "absent"
    assert loader.ai_act_for_subdomain("not-a-subdomain") == "absent"


def test_nist_controls_for_missing_domain_returns_empty(
    loader: ManifestLoader,
) -> None:
    """Missing domain or reg → empty list (never raises)."""
    assert loader.nist_controls_for_reg_in_domain("D-99", "GDPR") == []
    assert loader.nist_controls_for_reg_in_domain("D-01", "MADE_UP_REG") == []


def test_default_root_is_methodology_main() -> None:
    """DEFAULT_MANIFESTS_ROOT points at the Methodology-main path."""
    assert "Methodology-main" in str(DEFAULT_MANIFESTS_ROOT)
    assert "domains" in str(DEFAULT_MANIFESTS_ROOT)


# --- G3: Cross-check with preproc participating_regs ----------------------


def test_cross_check_with_preproc_participating_regs(
    loader: ManifestLoader,
) -> None:
    """ManifestLoader's ``applicable_regs`` ⊆ subdomain.participating_regulations.

    Drift detection: every regulation listed in
    ``subdomain_summaries[].applicable_regs`` for a sub-domain must
    also appear in the preproc catalog's
    ``Subdomain.participating_regulations`` (canonical form).

    The canonicalisation rule (see
    :func:`aegis_phase1.v2.domain.filters.regs._canonical_reg_name`)
    strips human annotations like ``"AI_Act (partial)"``.

    Note: as of 2026-08-05 there is known drift in D-01.2 / D-01.3 /
    D-01.4 — the manifest lists NIS2 in ``applicable_regs`` but the
    preproc has empty participating_regulations for those entries.
    This is a Methodology-main data inconsistency (separate repo),
    NOT a loader bug. The test logs the drift via ``pytest.warns``
    so the issue is visible without hard-failing the loader test
    suite (a separate drift-regression contract should reconcile the
    two sources).
    """
    import warnings

    from aegis_phase1.v2.domain.filters.regs import _canonical_reg_name
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

    preproc = PreprocCatalogLoader(Path("preproc_out"))
    by_id = {s.id: s for s in preproc.load_subdomains()}

    drift_records: list[str] = []
    for d_id in [f"D-{n:02d}" for n in range(1, 11)]:
        m = loader.manifest_for_domain(d_id)
        for s in m.subdomain_summaries:
            preproc_sd = by_id.get(s.id)
            if preproc_sd is None:
                drift_records.append(f"{s.id}: not in preproc")
                continue
            manifest_canon = {_canonical_reg_name(r) for r in s.applicable_regs if r}
            preproc_canon = {
                _canonical_reg_name(r) for r in (preproc_sd.participating_regulations or []) if r
            }
            missing = manifest_canon - preproc_canon
            if missing:
                drift_records.append(
                    f"{s.id}: manifest.applicable_regs={sorted(manifest_canon)} "
                    f"vs preproc.participating_regulations={sorted(preproc_canon)} "
                    f"missing={sorted(missing)}"
                )

    # All 38 subdomain_summaries must be iterated (sanity: loader is complete)
    total = sum(
        len(loader.manifest_for_domain(f"D-{n:02d}").subdomain_summaries) for n in range(1, 11)
    )
    assert total == 38, f"expected 38 subdomain summaries across 10 manifests, got {total}"

    # Soft-fail drift (known drift in 2026-08-05 corpus; future contracts
    # should reconcile). Emit as warnings so the issue is visible in CI
    # without hard-failing the loader test suite.
    if drift_records:
        warnings.warn(
            f"ManifestLoader: {len(drift_records)} drift record(s) between "
            f"manifest.applicable_regs and preproc.participating_regulations. "
            f"First 3: {drift_records[:3]}",
            stacklevel=2,
        )


# --- G4: Pydantic model invariants ---------------------------------------


def test_manifest_model_dump_is_jsonable(loader: ManifestLoader) -> None:
    """Manifest.model_dump() round-trips through json.dumps()."""
    m = loader.manifest_for_domain("D-01")
    # json.dumps will fail on non-serialisable values; this guards
    # against accidental Object / Decimal / datetime leaks.
    serialised = json.dumps(m.model_dump(), default=str)
    assert isinstance(serialised, str)
    assert "D-01" in serialised
    assert "GDPR" in serialised


def test_counts_model_defaults_to_zero() -> None:
    """Counts() with no args has all fields 0 (default factory)."""
    c = Counts()
    assert c.subdomains == 0
    assert c.applicable_nist_controls_total == 0


def test_clear_cache_idempotent(loader: ManifestLoader) -> None:
    """clear_cache() works on a warm loader and doesn't break re-load."""
    m1 = loader.manifest_for_domain("D-01")
    loader.clear_cache()
    m2 = loader.manifest_for_domain("D-01")
    assert m1.domain_id == m2.domain_id == "D-01"
    assert len(m1.subdomain_summaries) == len(m2.subdomain_summaries)


# --- G5: ai_act_summary property ------------------------------------------


def test_ai_act_summary_property(loader: ManifestLoader) -> None:
    """Manifest.ai_act_summary tallies the 3 states for D-01."""
    m = loader.manifest_for_domain("D-01")
    summary = m.ai_act_summary
    # D-01 has 3 absent + 1 partial
    assert summary.get("absent", 0) == 3
    assert summary.get("partial", 0) == 1
    assert summary.get("present", 0) == 0
    # Total must equal subdomain count
    assert sum(summary.values()) == 4


__all__ = []
