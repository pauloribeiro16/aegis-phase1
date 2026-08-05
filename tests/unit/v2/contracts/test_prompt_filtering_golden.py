"""Regression tests for CORR-100: per-case prompt filtering golden.

Each case declares a different ``applicable_regs`` set (2/4/5 regs).
This test pins those exact sets + the per-reg ref ids so a regression
in the loader or in ``_build_layer0_subdomain_refs`` is caught early.
"""

import json
from pathlib import Path

import pytest

from aegis_phase1.v2.context.applicability_context import build_applicability_context
from aegis_phase1.v2.domain.inputs import assemble_inputs
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator

SAMPLE_DOMAINS = ["D-01", "D-04", "D-07", "D-10"]
GOLDEN_PATH = Path(
    "tests/fixtures/contracts/cases_prompt_filtering_golden.json"
)
CASES = [
    "cases/case1-tinytask",
    "cases/case2-secureborder",
    "cases/case3-omnibank",
]


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def loader() -> PreprocCatalogLoader:
    return PreprocCatalogLoader(Path("preproc_out"))


def _runtime_snapshot(
    loader: PreprocCatalogLoader, case_path: str
) -> dict:
    """Mirror the dump logic from scripts/dev/capture_prompt_filtering_golden.py."""
    case_name = Path(case_path).name
    profile = CaseProfileLoader(case_path).load()
    orch = Phase1Orchestrator(
        work_dir=f"/tmp/aegis-test-corr100-contracts/{case_name}",
        preproc_catalog=loader,
        case_profile_loader=CaseProfileLoader(case_path),
    )
    orch.load(case_path, regulatory_baseline_path="preproc_out")
    app_ctx = build_applicability_context(orch.state)

    all_subdomains = loader.load_subdomains()
    per_reg_refs: dict[str, list[str]] = {}
    for reg in profile.applicable_regs:
        ids_for_reg = [
            s.id
            for s in all_subdomains
            if reg in (s.participating_regulations or [])
        ]
        lane_refs = orch._build_layer0_subdomain_refs(ids_for_reg)
        per_reg_refs[reg] = sorted(r["sub_domain_id"] for r in lane_refs)

    p1c_sample: dict[str, dict] = {}
    for dxx in SAMPLE_DOMAINS:
        inputs = assemble_inputs(orch.state, dxx)
        p1c_sample[dxx] = {
            "applicable_regs": inputs["applicable_regs"],
            "subdomain_ids": sorted(s["id"] for s in inputs["subdomains"]),
        }

    return {
        "company_name": profile.company.name,
        "scale": profile.company.scale,
        "applicable_regs_computed": list(profile.applicable_regs),
        "declaration_gaps": list(profile.declaration_gaps),
        "tier": app_ctx.tier,
        "expected_p1b_lanes": list(profile.applicable_regs),
        "expected_p1b_refs_per_reg": per_reg_refs,
        "expected_p1c_filter_sample": p1c_sample,
    }


def _check_case(case_path: str, golden: dict, loader: PreprocCatalogLoader) -> None:
    case_name = Path(case_path).name
    expected = golden[case_name]
    runtime = _runtime_snapshot(loader, case_path)

    assert runtime["applicable_regs_computed"] == expected[
        "applicable_regs_computed"
    ], (
        f"{case_name}: applicable_regs_computed changed: "
        f"{runtime['applicable_regs_computed']} vs {expected['applicable_regs_computed']}"
    )
    assert runtime["declaration_gaps"] == expected["declaration_gaps"], (
        f"{case_name}: declaration_gaps changed: "
        f"{runtime['declaration_gaps']} vs {expected['declaration_gaps']}"
    )
    assert runtime["tier"] == expected["tier"], (
        f"{case_name}: tier changed: {runtime['tier']} vs {expected['tier']}"
    )
    assert runtime["expected_p1b_lanes"] == expected["expected_p1b_lanes"]
    assert runtime["expected_p1b_refs_per_reg"] == expected[
        "expected_p1b_refs_per_reg"
    ], (
        f"{case_name}: P1B ref ids changed (per-reg). "
        f"Likely cause: change in participating_regulations or ref filtering."
    )

    for dxx in SAMPLE_DOMAINS:
        if dxx not in expected["expected_p1c_filter_sample"]:
            continue
        assert (
            runtime["expected_p1c_filter_sample"][dxx]["applicable_regs"]
            == expected["expected_p1c_filter_sample"][dxx]["applicable_regs"]
        ), f"{case_name}/{dxx}: applicable_regs filter drifted"
        assert (
            runtime["expected_p1c_filter_sample"][dxx]["subdomain_ids"]
            == expected["expected_p1c_filter_sample"][dxx]["subdomain_ids"]
        ), f"{case_name}/{dxx}: subdomain_ids filter drifted"


def test_case1_golden_matches_runtime(
    golden: dict, loader: PreprocCatalogLoader
) -> None:
    _check_case("cases/case1-tinytask", golden, loader)


def test_case2_golden_matches_runtime(
    golden: dict, loader: PreprocCatalogLoader
) -> None:
    _check_case("cases/case2-secureborder", golden, loader)


def test_case3_golden_matches_runtime(
    golden: dict, loader: PreprocCatalogLoader
) -> None:
    _check_case("cases/case3-omnibank", golden, loader)


def test_all_cases_have_applicable_regs(golden: dict) -> None:
    counts = {
        case_name: len(data["applicable_regs_computed"])
        for case_name, data in golden.items()
        if not case_name.startswith("_")
    }
    assert counts == {
        "case1-tinytask": 2,
        "case2-secureborder": 4,
        "case3-omnibank": 5,
    }, (
        f"case applicable_regs counts changed: {counts}. "
        f"Expected 2/4/5 for tinytask/secureborder/omnibank. "
        f"Update the golden (capture script) if this is intentional."
    )
