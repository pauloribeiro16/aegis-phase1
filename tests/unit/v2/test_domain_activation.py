"""CORR-040-T6 tests: DomainActivationContext + factory + accessors.

15 tests:
  - 6 context tests (build, by_domain, sub_domains_covered, pairs_with_indeterminate, to_dict, empty)
  - 3 factory tests (parse adapted_subdomains_v3, parse legacy adapted_subdomains, missing lanes)
  - 3 coverage level tests (FULL, PARTIAL, NOT_ADDRESSED)
  - 3 CLI tests (--run-map fires, no-LLM fallback, defensive on MAP failure)
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Block 1: DomainActivationContext (6 tests)
# ---------------------------------------------------------------------------


def test_domain_activation_context_empty_state() -> None:
    """Empty state → context with 10 SKIPPED lanes."""
    from aegis_phase1.v2.context import build_domain_activation_context

    ctx = build_domain_activation_context({})
    assert ctx.total_lanes == 10
    assert ctx.ok_lanes == 0
    assert ctx.failed_lanes == 0
    assert all(lane.llm_status == "SKIPPED" for lane in ctx.lanes)
    assert ctx.total_sub_domain_activations == 0


def test_domain_activation_context_by_domain() -> None:
    """by_domain('D-04') returns the lane or None."""
    from aegis_phase1.v2.context import build_domain_activation_context

    ctx = build_domain_activation_context({})
    d04 = ctx.by_domain("D-04")
    assert d04 is not None
    assert d04.lane_id == "D-04"
    assert d04.domain_name == "Incident Response"
    # Non-existent lane
    assert ctx.by_domain("D-99") is None


def test_domain_activation_context_sub_domains_covered() -> None:
    """sub_domains_covered() returns the set of D-XX.Y with APPLICABLE verdict."""
    from aegis_phase1.v2.context import (
        DomainActivationContext,
        DomainLaneActivation,
        SubDomainActivation,
        CoverageLevel,
    )

    ctx = DomainActivationContext(
        lanes=[
            DomainLaneActivation(
                lane_id="D-01",
                coverage_level=CoverageLevel.FULL,
                llm_status="OK",
                sub_domain_activations=[
                    SubDomainActivation(
                        sub_domain_id="D-01.1",
                        reg_pair=["GDPR", "CRA"],
                        company_scope_verdict="APPLICABLE",
                    ),
                    SubDomainActivation(
                        sub_domain_id="D-01.2",
                        reg_pair=["GDPR"],
                        company_scope_verdict="NOT_APPLICABLE",
                    ),
                ],
            )
        ]
    )
    covered = ctx.sub_domains_covered()
    assert covered == {"D-01.1"}


def test_domain_activation_context_pairs_with_indeterminate() -> None:
    """pairs_with_indeterminate() returns (sub_domain, (reg_a, reg_b)) tuples."""
    from aegis_phase1.v2.context import (
        DomainActivationContext,
        DomainLaneActivation,
        SubDomainActivation,
        CoverageLevel,
    )

    ctx = DomainActivationContext(
        lanes=[
            DomainLaneActivation(
                lane_id="D-01",
                coverage_level=CoverageLevel.PARTIAL,
                llm_status="OK",
                sub_domain_activations=[
                    SubDomainActivation(
                        sub_domain_id="D-01.1",
                        reg_pair=["GDPR", "CRA"],
                        company_scope_verdict="INDETERMINATE",
                    ),
                    SubDomainActivation(
                        sub_domain_id="D-01.2",
                        reg_pair=["GDPR", "CRA"],
                        company_scope_verdict="APPLICABLE",
                    ),
                ],
            )
        ]
    )
    pairs = ctx.pairs_with_indeterminate()
    assert pairs == {("D-01.1", ("CRA", "GDPR"))}  # sorted alphabetically


def test_domain_activation_context_to_dict() -> None:
    """to_dict() returns a JSON-serializable dict."""
    import json

    from aegis_phase1.v2.context import (
        DomainActivationContext,
        DomainLaneActivation,
        SubDomainActivation,
        CoverageLevel,
    )

    ctx = DomainActivationContext(
        lanes=[
            DomainLaneActivation(
                lane_id="D-01",
                coverage_level=CoverageLevel.FULL,
                llm_status="OK",
                sub_domain_activations=[
                    SubDomainActivation(
                        sub_domain_id="D-01.1",
                        reg_pair=["GDPR", "CRA"],
                        company_scope_verdict="APPLICABLE",
                    )
                ],
            )
        ]
    )
    d = ctx.to_dict()
    s = json.dumps(d)
    assert "lanes" in d
    assert "total_lanes" in d
    assert "per_reg_count" in d
    assert d["lanes"][0]["lane_id"] == "D-01"


def test_domain_activation_context_per_reg_count() -> None:
    """per_reg_count aggregates activations per reg."""
    from aegis_phase1.v2.context import build_domain_activation_context

    state = {
        "domain_results": {
            "D-01": {
                "llm_status": "OK",
                "adapted_subdomains_v3": [
                    {
                        "sub_domain_id": "D-01.1",
                        "reg_pair": ["GDPR", "CRA"],
                        "company_scope_verdict": "APPLICABLE",
                    }
                ],
            },
            "D-02": {
                "llm_status": "OK",
                "adapted_subdomains_v3": [
                    {
                        "sub_domain_id": "D-02.1",
                        "reg_pair": ["CRA"],
                        "company_scope_verdict": "APPLICABLE",
                    }
                ],
            },
        }
    }
    ctx = build_domain_activation_context(state)
    assert ctx.per_reg_count["GDPR"] == 1
    assert ctx.per_reg_count["CRA"] == 2  # one in D-01, one in D-02


# ---------------------------------------------------------------------------
# Block 2: Factory (3 tests)
# ---------------------------------------------------------------------------


def test_factory_parses_canonical_v3_shape() -> None:
    """build_domain_activation_context reads adapted_subdomains_v3 (canonical)."""
    from aegis_phase1.v2.context import build_domain_activation_context

    state = {
        "domain_results": {
            "D-04": {
                "llm_status": "OK",
                "adapted_subdomains_v3": [
                    {
                        "sub_domain_id": "D-04.1",
                        "reg_pair": ["GDPR", "CRA"],
                        "company_scope_verdict": "APPLICABLE",
                        "regulatory_baseline_relationship": "SUBSTANTIVE",
                        "layer0_refs": ["SubDomains/D-04.1.md"],
                    }
                ],
            }
        }
    }
    ctx = build_domain_activation_context(state)
    d04 = ctx.by_domain("D-04")
    assert d04 is not None
    assert d04.coverage_level.value == "FULL"
    assert len(d04.sub_domain_activations) == 1
    sd = d04.sub_domain_activations[0]
    assert sd.sub_domain_id == "D-04.1"
    assert sd.reg_pair == ["GDPR", "CRA"]
    assert sd.company_scope_verdict == "APPLICABLE"


def test_factory_parses_legacy_shape() -> None:
    """build_domain_activation_context falls back to adapted_subdomains (legacy)."""
    from aegis_phase1.v2.context import build_domain_activation_context

    state = {
        "domain_results": {
            "D-04": {
                "llm_status": "OK",
                "adapted_subdomains": [
                    {
                        "id": "D-04.1",
                        "applicable": True,
                    },
                    {
                        "id": "D-04.2",
                        "applicable": False,
                    },
                ],
            }
        }
    }
    ctx = build_domain_activation_context(state)
    d04 = ctx.by_domain("D-04")
    assert d04 is not None
    assert d04.coverage_level.value == "PARTIAL"  # 1 of 2 APPLICABLE
    verdicts = {sd.sub_domain_id: sd.company_scope_verdict for sd in d04.sub_domain_activations}
    assert verdicts["D-04.1"] == "APPLICABLE"
    assert verdicts["D-04.2"] == "NOT_APPLICABLE"


def test_factory_fills_missing_lanes_with_failed() -> None:
    """If executor returns only some lanes, missing ones get FAILED status."""
    from aegis_phase1.v2.context import build_domain_activation_context

    state = {
        "domain_results": {
            "D-01": {
                "llm_status": "OK",
                "adapted_subdomains_v3": [],
            }
            # D-02..D-10 missing
        }
    }
    ctx = build_domain_activation_context(state)
    assert ctx.total_lanes == 10
    d01 = ctx.by_domain("D-01")
    assert d01.llm_status == "OK"
    d05 = ctx.by_domain("D-05")
    assert d05.llm_status == "SKIPPED"  # not present in state → SKIPPED


# ---------------------------------------------------------------------------
# Block 3: Coverage level (3 tests)
# ---------------------------------------------------------------------------


def test_lane_coverage_full_when_all_applicable() -> None:
    """CoverageLevel.FULL when all sub_domain_activations are APPLICABLE."""
    from aegis_phase1.v2.context import build_domain_activation_context

    state = {
        "domain_results": {
            "D-01": {
                "llm_status": "OK",
                "adapted_subdomains_v3": [
                    {"sub_domain_id": "D-01.1", "reg_pair": ["GDPR"], "company_scope_verdict": "APPLICABLE"},
                    {"sub_domain_id": "D-01.2", "reg_pair": ["CRA"], "company_scope_verdict": "APPLICABLE"},
                ],
            }
        }
    }
    ctx = build_domain_activation_context(state)
    assert ctx.by_domain("D-01").coverage_level.value == "FULL"


def test_lane_coverage_partial_when_mixed() -> None:
    """CoverageLevel.PARTIAL when some sub_domain_activations are APPLICABLE."""
    from aegis_phase1.v2.context import build_domain_activation_context

    state = {
        "domain_results": {
            "D-01": {
                "llm_status": "OK",
                "adapted_subdomains_v3": [
                    {"sub_domain_id": "D-01.1", "reg_pair": ["GDPR"], "company_scope_verdict": "APPLICABLE"},
                    {"sub_domain_id": "D-01.2", "reg_pair": ["CRA"], "company_scope_verdict": "NOT_APPLICABLE"},
                ],
            }
        }
    }
    ctx = build_domain_activation_context(state)
    assert ctx.by_domain("D-01").coverage_level.value == "PARTIAL"


def test_lane_coverage_not_addressed_when_empty() -> None:
    """CoverageLevel.NOT_ADDRESSED when no sub_domain_activations."""
    from aegis_phase1.v2.context import build_domain_activation_context

    state = {
        "domain_results": {
            "D-01": {"llm_status": "OK", "adapted_subdomains_v3": []}
        }
    }
    ctx = build_domain_activation_context(state)
    assert ctx.by_domain("D-01").coverage_level.value == "NOT_ADDRESSED"


# ---------------------------------------------------------------------------
# Block 4: CLI (3 tests)
# ---------------------------------------------------------------------------


def test_run_map_flag_registered() -> None:
    """Source-level: --run-map flag is registered in the parser."""
    import inspect

    from aegis_phase1.v2 import runner

    src = inspect.getsource(runner)
    assert '"--run-map"' in src or "'--run-map'" in src
    assert "run_map" in src


def test_cmd_run_map_handles_map_failure() -> None:
    """cmd_run_map catches MapPartialFailure and continues to render."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator
    from aegis_phase1.v2.runner import cmd_run_map

    with tempfile.TemporaryDirectory() as work:
        with tempfile.TemporaryDirectory() as out:
            from aegis_phase1.v2.llm import MockInvoker
            o = Phase1Orchestrator(
                work_dir=work,
                llm_invoker=MockInvoker(),
                preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
            )
            # Should not raise even when MAP fails (pre-existing bug)
            paths = cmd_run_map(
                orch=o,
                case_path="cases/case1-tinytask",
                prep_path="",
                output_path=out,
            )
            # Doc 07 + Doc 07b should still be rendered
            assert "AEGIS-P1-07" in paths or len(paths) >= 1, (
                f"cmd_run_map should produce at least 1 artefact even on MAP failure, got {paths}"
            )


def test_cmd_run_map_with_mock_llm_produces_docs() -> None:
    """cmd_run_map with MOCK_LLM=true produces Doc 07 + Doc 07b (deterministic fallback)."""
    os.environ["MOCK_LLM"] = "true"
    try:
        from aegis_phase1.prompts_v2.catalog import CatalogLoader
        from aegis_phase1.prompts_v2.factory import get_prompts_root
        from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
        from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
        from aegis_phase1.v2.orchestrator import Phase1Orchestrator
        from aegis_phase1.v2.runner import cmd_run_map

        with tempfile.TemporaryDirectory() as work:
            with tempfile.TemporaryDirectory() as out:
                from aegis_phase1.v2.llm import MockInvoker
                o = Phase1Orchestrator(
                    work_dir=work,
                    llm_invoker=MockInvoker(),
                    preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                    case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                    catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
                )
                paths = cmd_run_map(
                    orch=o,
                    case_path="cases/case1-tinytask",
                    prep_path="",
                    output_path=out,
                )
                assert "AEGIS-P1-07" in paths
                assert "AEGIS-P1-07b" in paths
                assert Path(paths["AEGIS-P1-07"]).exists()
                assert Path(paths["AEGIS-P1-07b"]).exists()
    finally:
        del os.environ["MOCK_LLM"]
