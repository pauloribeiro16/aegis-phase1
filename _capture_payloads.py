"""Interceptor for the pipeline that captures all LLM payloads without making real API calls.

The pipeline normally goes:
    runner.run_all() → orchestrator → Phase1Executor → UnifiedInvoker.invoke(spec, inputs)

This script patches UnifiedInvoker to capture the (spec_id, inputs) pairs
that the executor would have sent, returning a fake response so the pipeline
can complete its downstream stages (concatenate, apply_proportionality,
doc_04, doc_05, etc.) without the network.

Output: writes captured payloads to /tmp/payload_capture/<case>/<spec>.json
"""
import json
import sys
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.WARNING)


class PayloadCapture:
    """Captures (spec_id, inputs) pairs from UnifiedInvoker.invoke()."""

    def __init__(self, case_name: str, out_dir: Path):
        self.case_name = case_name
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.captures: list[dict[str, Any]] = []

    def __call__(self, spec_id: str, inputs: dict, **kwargs):
        """Mimics UnifiedInvoker.invoke(spec_id, inputs, **kwargs)."""
        # Capture
        capture = {
            "spec_id": spec_id,
            "inputs_keys": sorted(inputs.keys()) if isinstance(inputs, dict) else None,
            "inputs_size": sum(len(str(v)) for v in (inputs or {}).values()) if isinstance(inputs, dict) else 0,
            "config_keys": sorted((kwargs or {}).keys()),
            "config_size": sum(len(str(v)) for v in (kwargs or {}).values()),
        }

        # Detail: inspect inputs structure
        if isinstance(inputs, dict):
            for k, v in inputs.items():
                if isinstance(v, str):
                    capture[f"input.{k}_len"] = len(v)
                    capture[f"input.{k}_head"] = v[:200].replace("\n", " ")
                elif isinstance(v, list):
                    capture[f"input.{k}_count"] = len(v)
                    if v and isinstance(v[0], dict):
                        capture[f"input.{k}_first_keys"] = sorted(v[0].keys())[:10]
                elif isinstance(v, dict):
                    capture[f"input.{k}_keys"] = sorted(v.keys())[:10]
                else:
                    capture[f"input.{k}_type"] = type(v).__name__

        self.captures.append(capture)

        # Save full payload to disk (per spec)
        spec_dir = self.out_dir / self.case_name
        spec_dir.mkdir(parents=True, exist_ok=True)
        seq = sum(1 for c in self.captures if c["spec_id"] == spec_id)
        out_file = spec_dir / f"{spec_id}__{seq:02d}.json"
        full = {
            "spec_id": spec_id,
            "inputs": inputs,
            "kwargs": {k: v for k, v in (kwargs or {}).items() if k != "state"},
        }
        with out_file.open("w") as f:
            json.dump(full, f, indent=2, default=str)

        # Return a fake OK response so the pipeline can continue
        return {
            "status": "OK",
            "parsed_output": {"placeholder": True, "spec_id": spec_id},
            "retry_count": 0,
            "invocation_pattern": "captured",
        }


def run_case_with_capture(case_name: str, out_dir: Path):
    """Run the pipeline for one case, capturing all LLM payloads."""
    from pathlib import Path as P
    from aegis_phase1.v2.llm import build_llm_invoker
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    # Build the executor
    case_path = P(f"cases/{case_name}")
    case_profile_loader = CaseProfileLoader(case_path)
    catalog_loader = CatalogLoader(root=get_prompts_root() / "catalogs")
    llm_invoker = build_llm_invoker(model="MiniMax-M3", provider="minimax")

    # Patch the invoker to capture
    capture = PayloadCapture(case_name, out_dir)
    llm_invoker.invoke = capture  # monkey-patch the method

    # Build the orchestrator with our captured invoker
    orch = Phase1Orchestrator(
        llm_invoker=llm_invoker,
        case_profile_loader=case_profile_loader,
        catalog_loader=catalog_loader,
    )

    # Run the full pipeline
    regulatory_baseline_root = str(P("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PREPROCESSING").resolve())
    output_dir = P(f"/tmp/payload_capture_{case_name}_out")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {case_name}...")
    try:
        orch.run_all(
            case_path=str(case_path),
            regulatory_baseline_path=regulatory_baseline_root,
            output_dir=str(output_dir),
        )
    except Exception as exc:
        print(f"  run_all raised (expected — capture continues): {type(exc).__name__}: {exc}")

    print(f"  Captured {len(capture.captures)} LLM calls")
    return capture


if __name__ == "__main__":
    out_dir = Path("/tmp/payload_capture")
    for case_name in ["case1-tinytask", "case2-secureborder", "case3-omnibank"]:
        cap = run_case_with_capture(case_name, out_dir)
        # Write summary
        summary_file = out_dir / case_name / "_summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        with summary_file.open("w") as f:
            json.dump(cap.captures, f, indent=2, default=str)
        print(f"  Summary: {summary_file}")
        print()
