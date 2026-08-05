"""CORR-102: dry-run all Phase 1 prompt scenarios without calling LLM.

For each (case, spec_id, lane), builds the prompt the same way
:func:`Phase1LLMInvoker._attempt` does, measures the token count via
:class:`TokenCounter`, and dumps the structure of inputs. Saves a JSON
report for offline inspection.

The script NEVER calls Ollama / ChatMinimax. It only renders the
prompt and measures its size, so it is safe to run without any LLM
service available.

Usage:
    PYTHONPATH=src ../shared-venv-root/bin/python scripts/dev/dry_run_prompts.py

Output:
    tests/fixtures/dry_run/prompts_dump.json

Schema (top level):
    {
      "schema_version": "1.0",
      "generated_by": "scripts/dev/dry_run_prompts.py",
      "models_tested": ["gemma4:e4b", "MiniMax-M3"],
      "base_prompt_tokens": 100000,
      "max_prompt_tokens": 124000,
      "model_token_caps": {...},
      "summary": {"total": int, "within_budget": int, "over_budget": int, "errors": int},
      "scenarios": [Scenario, ...]
    }

Scenario shape (one per case x spec_id x lane x model):
    {
      "case": str,                  # e.g. "case1-tinytask"
      "spec_id": str,               # canonical Phase 1 LLM ID
      "lane_id": str,               # reg name (P1B) or D-XX (P1C) or "global" (reduce)
      "model": str,                 # model tag
      "prompt_bytes": int,          # bytes of system+user
      "prompt_tokens": int,         # estimated tokens (system+user)
      "sys_tokens": int,            # estimated tokens of system
      "user_tokens": int,           # estimated tokens of user
      "effective_cap": int,         # effective token cap for the model
      "within_budget": bool,        # True iff prompt_tokens <= effective_cap
      ...
    }

References:
    - src/aegis_phase1/llm/token_counter.py — TokenCounter impl
    - src/aegis_phase1/prompts_v2/invoker.py — MAX_PROMPT_TOKENS
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aegis_phase1.llm.token_counter import TokenCounter
from aegis_phase1.prompts_v2.invoker import (
    BASE_PROMPT_TOKENS,
    MAX_PROMPT_TOKENS,
    MODEL_TOKEN_CAPS,
    _effective_token_cap,
)
from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.phase1_executor import (
    DOMAINS,
    SPEC_COMPOUND,
    SPEC_INTERPRETATION,
    SPEC_OVERLAP,
    SPEC_RATIONALE,
    SPEC_STRATEGIC,
)
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.manifest_loader import ManifestLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator

CASES = [
    "cases/case1-tinytask",
    "cases/case2-secureborder",
    "cases/case3-omnibank",
]
MODELS_TO_TEST = ["gemma4:e4b", "MiniMax-M3"]
OUTPUT_PATH = Path("tests/fixtures/dry_run/prompts_dump.json")


def _filter_refs_per_lane(refs: list[dict], reg: str) -> list[dict]:
    """CORR-103: per-lane filter on hso_per_reg + pairs.

    Mirrors the in-place filter applied by
    :func:`Phase1Executor.run_phase_1b`. Returns the same refs dicts
    mutated in-place. Safe because the caller passes a fresh list.
    """
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


def build_inputs_for_p1b(profile: CaseProfileLoader, subdomains_by_reg: dict, reg: str) -> dict:
    """Build inputs for P1B-LLM-01/02 (per-reg lane).

    CORR-103: applies the per-lane filter on hso_per_reg + pairs
    (mirrors what ``run_phase_1b`` does) so the rendered prompt
    reflects what the LLM will actually see.
    """
    lane_refs = subdomains_by_reg.get(reg, [])
    lane_refs = _filter_refs_per_lane(list(lane_refs), reg)
    return {
        "case_id": Path(profile.case_path).name,
        "lane_id": reg,
        "applicable_regs": [reg],
        "layer0_subdomain_refs": lane_refs,
    }


def build_inputs_for_p1c(profile, state, dxx: str, lane_refs: list) -> dict:
    """Build inputs for P1C-LLM-01 (per-domain lane).

    Mirrors the contract documented in CORR-070
    (tests/fixtures/pipeline_inputs_golden/_schema.json). We populate
    the minimum fields the spec requires so the prompt renders.
    """
    case_id = Path(profile.case_path).name
    applicable_regs = list(getattr(state.get("company_context"), "applicable_regs", []) or [])
    return {
        "case_id": case_id,
        "domain_id": dxx,
        "lane_id": dxx,
        "applicable_regs": applicable_regs,
        "layer0_subdomain_refs": lane_refs,
        "company_context": {
            "company_name": getattr(state.get("company_context"), "company_name", ""),
            "scale": getattr(state.get("company_context"), "scale", "LOW"),
            "applicable_regs": applicable_regs,
        },
        "subdomains": [
            {
                "id": ref.get("sub_domain_id", ""),
                "title": ref.get("title", ""),
                "participating_regulations": ref.get("participating_regulations", []),
                "objective": ref.get("objective", ""),
            }
            for ref in lane_refs
        ],
        "manifest_summary": {
            "domain_id": dxx,
            "ai_act_present_count": 0,
            "ai_act_partial_count": 0,
            "ai_act_absent_count": 0,
            "nist_controls_by_reg": {reg: [] for reg in applicable_regs},
        },
    }


def build_inputs_for_reduce(profile, state, subdomains_by_reg) -> dict:
    """Build inputs for P1C-LLM-02/03 (global reduce)."""
    case_id = Path(profile.case_path).name
    return {
        "case_id": case_id,
        "lane_id": "global",
        "applicable_regs": [],
        "aggregated_activations": [
            {"sub_domain_id": f"{dxx}.1", "reg_pair": [], "company_scope_verdict": "APPLICABLE",
             "regulatory_baseline_relationship": "SAME"}
            for dxx in DOMAINS
        ],
        "doc07b_profile": {},
        "sync_conflicts": [],
    }


def render_prompt_for_spec(prompt_loader, spec_id: str, inputs: dict) -> dict:
    """Render a prompt (same way Phase1LLMInvoker does) without sending to LLM.

    Returns:
        On success: ``{"system": str, "user": str}``.
        On error: ``{"system": "", "user": "", "error": str}``.
    """
    try:
        prompt = prompt_loader.render(spec_id, inputs)
        return {"system": prompt.get("system", ""), "user": prompt.get("user", "")}
    except Exception as e:
        return {"system": "", "user": "", "error": f"{type(e).__name__}: {e}"}


def main() -> int:
    preproc = PreprocCatalogLoader(Path("preproc_out"))
    manifest = ManifestLoader(
        Path("Methodology-main/00_METHODOLOGY/PREPROCESSING_by_domain/domains")
    )
    prompt_loader = PromptLoader()

    all_scenarios: list[dict] = []
    summary = {"total": 0, "within_budget": 0, "over_budget": 0, "errors": 0}

    for case_path in CASES:
        case_name = Path(case_path).name
        profile = CaseProfileLoader(case_path).load()

        orch = Phase1Orchestrator(
            work_dir=f"/tmp/dry-run-{case_name}",
            preproc_catalog=preproc,
            case_profile_loader=CaseProfileLoader(case_path),
            manifest_loader=manifest,
        )
        orch.load(case_path, regulatory_baseline_path="preproc_out")

        # Group subdomains by participating regs for P1B lanes
        subdomains = preproc.load_subdomains()
        subs_by_reg: dict[str, list] = {}
        for sd in subdomains:
            for reg in (sd.participating_regulations or []):
                if reg in profile.applicable_regs:
                    subs_by_reg.setdefault(reg, []).append(sd)

        # P1B-LLM-01/02: per-reg lanes
        for reg in profile.applicable_regs:
            for spec_id in [SPEC_INTERPRETATION, SPEC_RATIONALE]:
                for model in MODELS_TO_TEST:
                    sd_list = subs_by_reg.get(reg, [])
                    lane_refs = orch._build_layer0_subdomain_refs(
                        [sd.id for sd in sd_list]
                    )
                    inputs = build_inputs_for_p1b(profile, {reg: lane_refs}, reg)
                    prompt = render_prompt_for_spec(prompt_loader, spec_id, inputs)
                    sys_t, user_t, total_t = TokenCounter.count_pair(
                        prompt.get("system", ""), prompt.get("user", "")
                    )
                    cap = _effective_token_cap(model)
                    within = total_t <= cap

                    scenario = {
                        "case": case_name,
                        "spec_id": spec_id,
                        "lane_id": reg,
                        "model": model,
                        "prompt_bytes": len(prompt.get("system", "")) + len(prompt.get("user", "")),
                        "prompt_tokens": total_t,
                        "sys_tokens": sys_t,
                        "user_tokens": user_t,
                        "effective_cap": cap,
                        "within_budget": within,
                        "n_refs": len(lane_refs),
                        "first_ref_keys": (
                            sorted(lane_refs[0].keys()) if lane_refs else []
                        ),
                    }
                    if "error" in prompt:
                        scenario["render_error"] = prompt["error"]
                        summary["errors"] += 1
                    elif not within:
                        summary["over_budget"] += 1
                    else:
                        summary["within_budget"] += 1
                    summary["total"] += 1
                    all_scenarios.append(scenario)

        # P1C-LLM-01: per-domain lanes
        for dxx in DOMAINS:
            lane_refs = orch._build_layer0_subdomain_refs(
                [
                    sd.id
                    for sd in subdomains
                    if (sd.id or "").startswith(f"{dxx}.")
                ]
            )
            inputs = build_inputs_for_p1c(profile, orch.state, dxx, lane_refs)
            spec_id = SPEC_OVERLAP
            for model in MODELS_TO_TEST:
                prompt = render_prompt_for_spec(prompt_loader, spec_id, inputs)
                sys_t, user_t, total_t = TokenCounter.count_pair(
                    prompt.get("system", ""), prompt.get("user", "")
                )
                cap = _effective_token_cap(model)
                within = total_t <= cap

                scenario = {
                    "case": case_name,
                    "spec_id": spec_id,
                    "lane_id": dxx,
                    "model": model,
                    "prompt_bytes": len(prompt.get("system", "")) + len(prompt.get("user", "")),
                    "prompt_tokens": total_t,
                    "sys_tokens": sys_t,
                    "user_tokens": user_t,
                    "effective_cap": cap,
                    "within_budget": within,
                    "n_subdomains": len(lane_refs),
                    "applicable_regs": list(
                        getattr(orch.state.get("company_context"), "applicable_regs", []) or []
                    ),
                    "has_manifest_summary": "manifest_summary" in inputs,
                }
                if "error" in prompt:
                    scenario["render_error"] = prompt["error"]
                    summary["errors"] += 1
                elif not within:
                    summary["over_budget"] += 1
                else:
                    summary["within_budget"] += 1
                summary["total"] += 1
                all_scenarios.append(scenario)

        # P1C-LLM-02/03: global reduce (no lane)
        for spec_id in [SPEC_STRATEGIC, SPEC_COMPOUND]:
            for model in MODELS_TO_TEST:
                inputs = build_inputs_for_reduce(profile, orch.state, subs_by_reg)
                prompt = render_prompt_for_spec(prompt_loader, spec_id, inputs)
                sys_t, user_t, total_t = TokenCounter.count_pair(
                    prompt.get("system", ""), prompt.get("user", "")
                )
                cap = _effective_token_cap(model)
                within = total_t <= cap

                scenario = {
                    "case": case_name,
                    "spec_id": spec_id,
                    "lane_id": "global",
                    "model": model,
                    "prompt_bytes": len(prompt.get("system", "")) + len(prompt.get("user", "")),
                    "prompt_tokens": total_t,
                    "sys_tokens": sys_t,
                    "user_tokens": user_t,
                    "effective_cap": cap,
                    "within_budget": within,
                }
                if "error" in prompt:
                    scenario["render_error"] = prompt["error"]
                    summary["errors"] += 1
                elif not within:
                    summary["over_budget"] += 1
                else:
                    summary["within_budget"] += 1
                summary["total"] += 1
                all_scenarios.append(scenario)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_by": "scripts/dev/dry_run_prompts.py",
                "models_tested": MODELS_TO_TEST,
                "base_prompt_tokens": BASE_PROMPT_TOKENS,
                "max_prompt_tokens": MAX_PROMPT_TOKENS,
                "model_token_caps": MODEL_TOKEN_CAPS,
                "summary": summary,
                "scenarios": all_scenarios,
            },
            indent=2,
            default=str,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Print summary table
    print(f"\n=== DRY RUN SUMMARY ({summary['total']} scenarios) ===")
    print(f"  Within budget: {summary['within_budget']}")
    print(f"  Over budget:   {summary['over_budget']}")
    print(f"  Render errors: {summary['errors']}")
    print(f"\nWrote: {OUTPUT_PATH}")

    if summary["over_budget"] > 0:
        print("\nWARNING: Some scenarios exceed token budget!")
        for s in all_scenarios:
            if not s.get("within_budget", True) and "render_error" not in s:
                print(
                    f"  OVER: case={s['case']} spec={s['spec_id']} "
                    f"lane={s['lane_id']} model={s['model']} "
                    f"tokens={s['prompt_tokens']} cap={s['effective_cap']}"
                )

    if summary["errors"] > 0:
        print("\nERRORS encountered:")
        for s in all_scenarios:
            if "render_error" in s:
                print(
                    f"  ERR: case={s['case']} spec={s['spec_id']} "
                    f"lane={s['lane_id']}: {s['render_error']}"
                )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
