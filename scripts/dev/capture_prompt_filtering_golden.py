"""Capture the expected per-case prompt-filtering golden JSON.

Developer tool (NOT a test). Run after the layer0 enrichment is in
place to regenerate ``tests/fixtures/contracts/cases_prompt_filtering_golden.json``.

Usage (from repo root):

    PYTHONPATH=src ../shared-venv-root/bin/python scripts/dev/capture_prompt_filtering_golden.py
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from aegis_phase1.v2.context.applicability_context import build_applicability_context
from aegis_phase1.v2.domain.inputs import assemble_inputs
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator

CASES = [
    "cases/case1-tinytask",
    "cases/case2-secureborder",
    "cases/case3-omnibank",
]
SAMPLE_DOMAINS = ["D-01", "D-04", "D-07", "D-10"]


def main() -> None:
    loader = PreprocCatalogLoader(Path("preproc_out"))
    all_subdomains = loader.load_subdomains()
    golden: dict = {
        "_schema_version": "1.0",
        "_generated": datetime.now(UTC).isoformat(),
        "_generator": "scripts/dev/capture_prompt_filtering_golden.py",
    }

    for case in CASES:
        case_name = Path(case).name
        profile = CaseProfileLoader(case).load()
        orch = Phase1Orchestrator(
            work_dir=f"/tmp/aegis-dump/work_{case_name}",
            preproc_catalog=loader,
            case_profile_loader=CaseProfileLoader(case),
        )
        orch.load(case, regulatory_baseline_path="preproc_out")
        app_ctx = build_applicability_context(orch.state)

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

        golden[case_name] = {
            "company_name": profile.company.name,
            "scale": profile.company.scale,
            "applicable_regs_computed": list(profile.applicable_regs),
            "applicable_regs_declared": list(profile.declared_applicable_regs),
            "declaration_gaps": list(profile.declaration_gaps),
            "tier": app_ctx.tier,
            "expected_p1b_lanes": list(profile.applicable_regs),
            "expected_p1b_refs_per_reg": per_reg_refs,
            "expected_p1c_filter_sample": p1c_sample,
        }

    out_path = Path("tests/fixtures/contracts/cases_prompt_filtering_golden.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(golden, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
