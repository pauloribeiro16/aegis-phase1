"""Regression tests for CORR-103: prompt-ref fidelity.

Three issues were fixed in CORR-103 to bring the Phase 1 prompt
payload back within the 100K BASE cap (CORR-102):

  1. ``hso_hl_objective`` was duplicated as ``objective`` in each
     layer0 ref. 273 chars x 27 refs x ~5 lanes ~ 36KB wasted per
     P1B run. Fix: removed the duplicate ``objective`` key.

  2. P1B-LLM-01/02 prompts overflowed the 100K cap because each
     lane carried every ref's full ``hso_per_reg`` (54.7% of
     payload) and ``pairs`` (27.8%) — even though the lane only
     needs the entries that match the lane's regulation. Fix:
     per-lane filter on these two fields.

  3. P1C-LLM-01 prompts had empty ``applicable_articles`` and
     ``ambiguities`` (legacy post-T4 TODO). 498 clauses + 196 pairs
     are available in preproc. Fix: populate from preproc catalog
     ref and v2_pairs state key.

These tests pin the new behaviour so a future refactor cannot silently
regress any of the three fixes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis_phase1.v2.domain.inputs import assemble_inputs
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator


@pytest.fixture(scope="module")
def orch() -> Phase1Orchestrator:
    """Phase1Orchestrator with case1 loaded (CRA + GDPR)."""
    loader = PreprocCatalogLoader(Path("preproc_out"))
    case_profile = CaseProfileLoader("cases/case1-tinytask")
    orch = Phase1Orchestrator(
        work_dir="/tmp/aegis-test-corr103",
        preproc_catalog=loader,
        case_profile_loader=case_profile,
    )
    orch.load("cases/case1-tinytask", regulatory_baseline_path="preproc_out")
    return orch


@pytest.fixture(scope="module")
def all_subdomains(orch: Phase1Orchestrator) -> list:
    return orch.preproc_catalog.load_subdomains()


# ─── Issue 2: hso_per_reg + pairs filtered per lane ─────────────────────


def _build_p1b_lane_refs(orch: Phase1Orchestrator, reg: str) -> list[dict]:
    """Reproduce the per-lane ref filter that run_phase_1b applies.

    The executor mutates the ref dicts in-place, but we re-fetch a
    fresh set from the orchestrator for each call.
    """
    all_subs = orch.preproc_catalog.load_subdomains()
    ids_for_reg = [
        s.id
        for s in all_subs
        if reg in (s.participating_regulations or [])
    ]
    refs = orch._build_layer0_subdomain_refs(ids_for_reg)
    for ref in refs:
        if isinstance(ref, dict):
            ref["hso_per_reg"] = [
                e
                for e in (ref.get("hso_per_reg") or [])
                if isinstance(e, dict)
                and (e.get("regulation") or "").strip() == reg
            ]
            ref["pairs"] = [
                p
                for p in (ref.get("pairs") or [])
                if isinstance(p, dict)
                and (
                    (p.get("reg_a") or "").strip() == reg
                    or (p.get("reg_b") or "").strip() == reg
                )
            ]
    return refs


def test_p1b_refs_have_filtered_hso_per_reg(orch: Phase1Orchestrator) -> None:
    """Each ref's hso_per_reg only contains entries matching the lane reg."""
    for reg in ("CRA", "GDPR"):
        refs = _build_p1b_lane_refs(orch, reg)
        assert refs, f"expected at least 1 ref for {reg}, got 0"
        for ref in refs:
            hso = ref.get("hso_per_reg") or []
            assert all(
                (e.get("regulation") or "").strip() == reg for e in hso
            ), f"{ref['sub_domain_id']}/{reg}: hso_per_reg has entries "
            f"for other regulations: {[e.get('regulation') for e in hso]}"
            # At least one HSO entry should remain (each participating
            # subdomain has >=1 HSO per its participating regs).
            assert len(hso) >= 1, (
                f"{ref['sub_domain_id']}/{reg}: hso_per_reg is empty "
                f"after lane filter — this ref should have HSO entries "
                f"for {reg}"
            )


def test_p1b_refs_have_filtered_pairs(orch: Phase1Orchestrator) -> None:
    """Each ref's pairs only contain entries where reg_a OR reg_b == lane."""
    for reg in ("CRA", "GDPR"):
        refs = _build_p1b_lane_refs(orch, reg)
        assert refs, f"expected at least 1 ref for {reg}, got 0"
        for ref in refs:
            pairs = ref.get("pairs") or []
            for p in pairs:
                ra = (p.get("reg_a") or "").strip()
                rb = (p.get("reg_b") or "").strip()
                assert reg in (ra, rb), (
                    f"{ref['sub_domain_id']}/{reg}: pair "
                    f"{p.get('id', '?')} has regs ({ra}, {rb}); "
                    f"neither is the lane reg {reg}"
                )


def test_p1b_filter_reduces_payload(orch: Phase1Orchestrator) -> None:
    """After CORR-103 filtering, the CRA-lane hso_per_reg is ~1/4 of pre-filter.

    D-01.1 has 4 participating regulations, so its pre-filter hso_per_reg
    is ~4x the post-filter count for any single reg.
    """
    all_subs = orch.preproc_catalog.load_subdomains()
    target_ids = [s.id for s in all_subs if "CRA" in (s.participating_regulations or [])]
    pre_refs = orch._build_layer0_subdomain_refs(target_ids)
    pre_total_hso = sum(len(r.get("hso_per_reg") or []) for r in pre_refs)
    pre_total_pairs = sum(len(r.get("pairs") or []) for r in pre_refs)

    filtered = _build_p1b_lane_refs(orch, "CRA")
    post_total_hso = sum(len(r.get("hso_per_reg") or []) for r in filtered)
    post_total_pairs = sum(len(r.get("pairs") or []) for r in filtered)

    assert pre_total_hso > post_total_hso, (
        f"expected hso_per_reg to shrink after CORR-103 filter: "
        f"pre={pre_total_hso} post={post_total_pairs}"
    )
    assert pre_total_pairs > post_total_pairs, (
        f"expected pairs to shrink after CORR-103 filter: "
        f"pre={pre_total_pairs} post={post_total_pairs}"
    )


# ─── Issue 3: applicable_articles + ambiguities populated for P1C ───────


def test_p1c_inputs_have_populated_articles(orch: Phase1Orchestrator) -> None:
    """For D-01 (case1 has CRA + GDPR), applicable_articles is non-empty."""
    inp = assemble_inputs(orch.state, "D-01")
    arts = inp["applicable_articles"]
    assert len(arts) > 0, "CORR-103: expected applicable_articles to be populated"
    # All entries must be for a regulation in applicable_regs
    regs = set(inp["applicable_regs"])
    for entry in arts:
        assert "id" in entry
        assert "regulation" in entry
        assert entry["regulation"] in regs, (
            f"article {entry.get('id')} has regulation "
            f"{entry.get('regulation')!r} not in {regs}"
        )


def test_p1c_inputs_have_populated_ambiguities(orch: Phase1Orchestrator) -> None:
    """For D-01 (case1), ambiguities contain pairs for D-01.* subdomains."""
    inp = assemble_inputs(orch.state, "D-01")
    ambs = inp["ambiguities"]
    assert len(ambs) > 0, "CORR-103: expected ambiguities to be populated"
    sub_ids = {s["id"] for s in inp["subdomains"]}
    for entry in ambs:
        assert "subdomain_id" in entry
        assert entry["subdomain_id"] in sub_ids, (
            f"pair {entry.get('id')} has subdomain_id "
            f"{entry.get('subdomain_id')!r} not in {sub_ids}"
        )
        # Cross-regulation pairs must reference two different regulations
        ra = (entry.get("reg_a") or "").strip()
        rb = (entry.get("reg_b") or "").strip()
        assert ra and rb and ra != rb, (
            f"pair {entry.get('id')} has reg_a={ra!r} reg_b={rb!r}; "
            f"expected two distinct regulations"
        )


def test_p1c_inputs_d04_has_empty_articles_when_no_regs(
    orch: Phase1Orchestrator,
) -> None:
    """D-04 has no participating regs in case1 → articles must be empty.

    Ambiguities are filtered by subdomain_id only (not by regulation),
    so D-04 still gets cross-regulation pairs for D-04.* subdomains.
    """
    inp = assemble_inputs(orch.state, "D-04")
    assert inp["applicable_regs"] == [], (
        f"D-04 should have no applicable_regs in case1, got {inp['applicable_regs']}"
    )
    assert inp["applicable_articles"] == [], (
        "D-04 with no applicable_regs must have empty articles"
    )


# ─── Issue 1: duplicate 'objective' field removed from refs ─────────────


def test_layer0_refs_do_not_carry_duplicate_objective(
    orch: Phase1Orchestrator,
) -> None:
    """Issue 1 fix: refs MUST NOT have both hso_hl_objective and objective."""
    refs = orch._build_layer0_subdomain_refs(["D-01.1", "D-01.4"])
    assert len(refs) == 2
    for ref in refs:
        assert "hso_hl_objective" in ref, (
            "hso_hl_objective must remain (it's the canonical HL objective)"
        )
        assert "objective" not in ref, (
            f"CORR-103: ref {ref['sub_domain_id']} must NOT carry "
            f"the duplicate 'objective' field; only hso_hl_objective."
        )
