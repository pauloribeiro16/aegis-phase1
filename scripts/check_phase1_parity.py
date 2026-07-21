#!/usr/bin/env python3
"""CORR-041-T5: Phase 1 parity check — diff v2 outputs against Methodology-main reference.

Runs the full Phase 1 v2 pipeline with MOCK_LLM=true and compares
the 9 generated outputs against the reference docs in
``Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/``.

Outputs a per-document PASS/INFO/WARN summary plus an overall verdict.
Best-effort: not blocking, only informational.

Usage:
    python scripts/check_phase1_parity.py [--case case1-tinytask] [--output /tmp/out]

Exit code: 0 (always — parity check is best-effort, not a quality gate).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE = REPO_ROOT / "cases" / "case1-tinytask"
REFERENCE_ROOT = (
    REPO_ROOT.parent
    / "Methodology-main"
    / "02_CASES"
    / "Case_01_TinyTask_SaaS"
    / "01_PHASE1_CONTEXT"
)
RUNNER = ["python", "-m", "aegis_phase1.v2.runner"]


def _run_stage(stage: str, case: str, out: str) -> dict[str, str]:
    """Run a single CLI stage; return the AEGIS-P1-XX → path mapping."""
    cmd = RUNNER + [
        "--case", case,
        f"--{stage}",
        "--output", out,
    ]
    env = dict(os.environ)
    env.setdefault("MOCK_LLM", "true")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        print(f"WARN: {stage} exited with {result.returncode}", file=sys.stderr)
    paths: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("AEGIS-P1-"):
            label, _, p = line.partition(":")
            paths[label.strip()] = p.strip()
    return paths


def _check_doc(label: str, generated: Path | None, reference: Path | None) -> dict[str, Any]:
    """Compare generated vs reference; return metrics + verdict."""
    result: dict[str, Any] = {
        "label": label,
        "generated": str(generated) if generated else "(missing)",
        "reference": str(reference) if reference else "(no reference)",
        "verdict": "SKIP",
        "metrics": {},
    }
    if not generated or not generated.exists():
        result["verdict"] = "MISSING"
        return result
    if not reference or not reference.exists():
        result["verdict"] = "NO_REFERENCE"
        return result
    gen_text = generated.read_text(encoding="utf-8")
    ref_text = reference.read_text(encoding="utf-8")
    gen_size = len(gen_text)
    ref_size = len(ref_text)
    # Simple keyword presence check on the generated doc
    keywords_to_check = [
        "GDPR", "CRA", "TinyTask", "D-01", "D-04",
    ]
    present = [k for k in keywords_to_check if k in gen_text]
    missing = [k for k in keywords_to_check if k not in gen_text]
    result["metrics"] = {
        "generated_size": gen_size,
        "reference_size": ref_size,
        "size_ratio": round(gen_size / ref_size, 2) if ref_size else 0,
        "keywords_present": present,
        "keywords_missing": missing,
    }
    # Verdict: PASS if generated has the canonical keywords and is within
    # 0.5x-2x of reference size. Otherwise WARN.
    if not missing and 0.5 <= result["metrics"]["size_ratio"] <= 2.0:
        result["verdict"] = "PASS"
    elif missing:
        result["verdict"] = "WARN"
    else:
        result["verdict"] = "INFO"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1 parity check")
    parser.add_argument("--case", default=str(DEFAULT_CASE))
    parser.add_argument("--output", default=None, help="Output dir (default: tempdir)")
    parser.add_argument(
        "--reference-root",
        default=str(REFERENCE_ROOT),
        help="Path to Methodology-main Case_01_Phase1_Context/",
    )
    args = parser.parse_args()

    if args.output:
        out_dir = Path(args.output)
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="phase1_parity_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_root = Path(args.reference_root)

    print(f"Case: {args.case}")
    print(f"Output: {out_dir}")
    print(f"Reference: {ref_root}")
    print()

    # Run each stage
    all_paths: dict[str, str] = {}
    for stage in ("run-applicability", "run-clauses", "run-map", "run-reduce", "run-phase-1b"):
        print(f"=== Running {stage} ===")
        paths = _run_stage(stage, args.case, str(out_dir))
        for label, p in paths.items():
            all_paths[label] = p
            print(f"  {label}: {p}")

    # Map AEGIS labels to reference filenames
    label_to_ref = {
        "AEGIS-P1-04": "04_Company_Context_Assessment.md",
        "AEGIS-P1-04a": "04a_Architecture_DataInventory.md",
        "AEGIS-P1-04b": "04b_Security_Posture.md",
        "AEGIS-P1-04c": "04c_ThirdParty_Landscape.md",
        "AEGIS-P1-04d": "04d_Org_Roles_RACI.md",
        "AEGIS-P1-05": "05_Regulatory_Applicability.md",
        "AEGIS-P1-06": "06_Clause_Mapping_Matrix.md",
        "AEGIS-P1-07": "07_Structured_Compliance_Matrix.md",
        "AEGIS-P1-07b": "07b_Proportionality_Profile.md",
    }

    # Per-doc parity check
    print()
    print("=== Parity check ===")
    results = []
    for label, ref_name in label_to_ref.items():
        gen = Path(all_paths[label]) if label in all_paths else None
        ref = ref_root / ref_name
        r = _check_doc(label, gen, ref)
        results.append(r)
        marker = {"PASS": "✓", "INFO": "ℹ", "WARN": "⚠", "MISSING": "✗", "NO_REFERENCE": "—"}.get(
            r["verdict"], "?"
        )
        print(f"  {marker} {label}: {r['verdict']}")
        if r["verdict"] in ("WARN", "MISSING"):
            print(f"      generated: {r['generated']}")
            print(f"      reference: {r['reference']}")
            if r["metrics"].get("keywords_missing"):
                print(f"      missing keywords: {r['metrics']['keywords_missing']}")

    # Summary
    print()
    total = len(results)
    passed = sum(1 for r in results if r["verdict"] == "PASS")
    warned = sum(1 for r in results if r["verdict"] == "WARN")
    missing = sum(1 for r in results if r["verdict"] == "MISSING")
    print(f"=== Summary: {passed}/{total} PASS, {warned} WARN, {missing} MISSING ===")
    print()
    print("(Best-effort parity check; not a quality gate. Exit 0.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
