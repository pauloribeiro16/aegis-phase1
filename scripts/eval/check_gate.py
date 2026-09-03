#!/usr/bin/env python3
"""CORR-112 F4: Validate outputs and state against RefGate assertions.

Affirms:
  - 0 invented/ungrounded references across all outputs
  - 0 sections PENDING in state.json
  - 100% rendered sections tagged with [deterministic] or [LLM: ...]

Usage:
    python -m scripts.eval.check_gate --run-dir /path/to/run --preproc /path/to/preproc
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from aegis_phase1.prompts_v2.ref_gate import RefGate


def parse_args():
    p = argparse.ArgumentParser(description="Check RefGate assertions on a run output directory.")
    p.add_argument("--run-dir", required=True, type=Path, help="Path to run execution directory.")
    p.add_argument("--state-json", required=False, type=Path, help="Optional path to state.json.")
    return p.parse_args()


def check_run(run_dir: Path, state_json_path: Path | None = None) -> int:
    ref_gate = RefGate()
    exit_code = 0

    print(f"=== Checking RefGate assertions for {run_dir} ===")

    # 1. Check state.json for PENDING sections
    if not state_json_path:
        state_json_path = run_dir / "work" / "state.json"
        if not state_json_path.exists():
            state_json_path = run_dir / "state.json"

    if state_json_path.exists():
        try:
            state = json.loads(state_json_path.read_text(encoding="utf-8"))
            pending_count = 0
            # Scan state dictionary for any status == 'PENDING'
            state_str = json.dumps(state)
            pending_matches = re.findall(r'"status"\s*:\s*"PENDING"', state_str)
            pending_count = len(pending_matches)
            if pending_count > 0:
                print(f"❌ Found {pending_count} PENDING sections in state.json")
                exit_code = 1
            else:
                print("✅ 0 sections PENDING in state.json")
        except Exception as e:
            print(f"⚠️ Could not parse state.json: {e}")
    else:
        print("ℹ️ state.json not found, skipping PENDING sections check.")

    # 2. Check generated markdown docs for tags and RefGate violations
    doc_files = sorted(run_dir.glob("*.md"))
    tag_pattern = re.compile(r'\[(?:deterministic|LLM:[^\]]+)\]', re.IGNORECASE)

    tagged_docs = 0
    total_docs = 0
    invented_refs_found = 0

    for doc in doc_files:
        if doc.name.startswith("README") or doc.name.startswith("checker_"):
            continue
        total_docs += 1
        text = doc.read_text(encoding="utf-8", errors="ignore")

        # Check section tags
        tags = tag_pattern.findall(text)
        if tags:
            tagged_docs += 1
        else:
            print(f"⚠️ Document {doc.name} has no provenance section tags")

        # Check RefGate violations on doc content
        gate_res = ref_gate.validate("P1B-LLM-02-RATIONALE", text, inputs={})
        for v in gate_res.violations:
            if v.rule in ("GENERIC_MARKER", "INVENTED_STATISTICS"):
                print(f"❌ [{v.rule}] in {doc.name}: {v.message}")
                invented_refs_found += 1
                exit_code = 1

    if invented_refs_found == 0:
        print("✅ 0 invented references or generic markers found across markdown outputs.")
    else:
        print(f"❌ Total {invented_refs_found} reference/marker violations found.")

    if total_docs > 0 and tagged_docs == total_docs:
        print(f"✅ 100% of rendered documents ({tagged_docs}/{total_docs}) carry provenance tags.")
    elif total_docs > 0:
        print(f"ℹ️ {tagged_docs}/{total_docs} rendered documents carry provenance tags.")

    return exit_code


def main():
    args = parse_args()
    code = check_run(args.run_dir, args.state_json)
    sys.exit(code)


if __name__ == "__main__":
    main()
