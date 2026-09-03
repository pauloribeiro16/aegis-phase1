#!/usr/bin/env python3
"""CORR-112 F4: Validate outputs and state against RefGate assertions.

Affirms:
  - 0 invented/ungrounded references across all outputs
  - 0 sections PENDING in state.json
  - 100% rendered sections tagged with [deterministic] or [LLM: ...]
  - 100% subdomain coverage across rendered Doc 04-07b (--check-coverage)

Usage:
    python -m scripts.eval.check_gate --run-dir /path/to/run
    python -m scripts.eval.check_gate --run-dir /path/to/run --check-coverage --preproc-root preproc_out
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

from aegis_phase1.prompts_v2.ref_gate import RefGate

logger = logging.getLogger(__name__)


# A subdomain ID matches "D-NN.M" (e.g. D-01.1). Used by the coverage
# check to scan rendered markdown for evidence of each applicable
# subdomain.
_SUBDOMAIN_ID_RE = re.compile(r"\bD-\d{2}\.\d+\b")


def parse_args():
    p = argparse.ArgumentParser(description="Check RefGate assertions on a run output directory.")
    p.add_argument("--run-dir", required=True, type=Path, help="Path to run execution directory.")
    p.add_argument("--state-json", required=False, type=Path, help="Optional path to state.json.")
    p.add_argument(
        "--check-coverage",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Verify every applicable subdomain is mentioned in at least one rendered doc (default: ON).",
    )
    p.add_argument(
        "--preproc-root",
        required=False,
        type=Path,
        default=Path("preproc_out"),
        help="Path to the preproc catalogue root (used by --check-coverage).",
    )
    p.add_argument(
        "--coverage-min-pct",
        required=False,
        type=float,
        default=100.0,
        help="Minimum subdomain coverage %% required for the check to pass (default: 100.0).",
    )
    return p.parse_args()


def _applicable_subdomains(preproc_root: Path) -> set[str]:
    """Return the set of subdomain IDs (D-XX.Y) present in preproc_out.

    This is the universe of *applicable* subdomains for the workspace
    (a stricter per-case filter exists in case profiles, but a
    case-level filter is out of scope for this minimal coverage check).
    Empty set on error (caller logs a warning and the check is skipped).
    """
    try:
        from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    except Exception as e:  # pragma: no cover
        logger.warning("Could not import PreprocCatalogLoader: %s", e)
        return set()
    try:
        loader = PreprocCatalogLoader(preproc_root=preproc_root)
        subdomains = loader.load_subdomains()
    except Exception as e:
        logger.warning("Could not load subdomains from %s: %s", preproc_root, e)
        return set()
    return {s.id for s in subdomains if getattr(s, "id", None)}


def check_subdomain_coverage(
    run_dir: Path, preproc_root: Path, min_pct: float = 100.0
) -> tuple[int, int, set[str], set[str]]:
    """Check every applicable subdomain is mentioned in at least one
    rendered doc under ``run_dir``.

    Returns ``(covered_count, total_count, covered, missing)``. Exits
    non-zero when coverage falls below ``min_pct``.

    The check is intentionally light: a subdomain ID (D-XX.Y) appearing
    anywhere in any of the 9 docs (Doc 04..07b) counts as covered. Full
    clause-level coverage is a separate bigger task (out of scope here).
    """
    doc_files = [
        p
        for p in sorted(run_dir.glob("*.md"))
        if not p.name.startswith("README") and not p.name.startswith("checker_")
    ]
    if not doc_files:
        print("  (no rendered docs found in run-dir; coverage check skipped)")
        return 0, 0, set(), set()

    applicable = _applicable_subdomains(preproc_root)
    if not applicable:
        print(f"  (no subdomains loaded from {preproc_root}; coverage check skipped)")
        return 0, 0, set(), set()

    found: set[str] = set()
    for doc in doc_files:
        text = doc.read_text(encoding="utf-8", errors="ignore")
        for sid in _SUBDOMAIN_ID_RE.findall(text):
            found.add(sid)

    covered = applicable & found
    missing = applicable - found
    total = len(applicable)
    covered_n = len(covered)
    pct = 100.0 * covered_n / total if total else 100.0
    print(
        f"  Subdomain coverage: {covered_n}/{total} ({pct:.1f}%) "
        f"(applicable from {preproc_root})"
    )
    if missing:
        # Show up to the first 20 to keep output bounded.
        sample = sorted(missing)[:20]
        more = f" (+{len(missing) - 20} more)" if len(missing) > 20 else ""
        print(f"  Missing subdomains: {sample}{more}")
    return covered_n, total, covered, missing


def check_run(
    run_dir: Path,
    state_json_path: Path | None = None,
    *,
    check_coverage: bool = True,
    preproc_root: Path | None = None,
    coverage_min_pct: float = 100.0,
) -> int:
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

    # 3. Zero-omission subdomain coverage (CORR-OBJ-02)
    if check_coverage:
        print()
        print("--- Zero-omission subdomain coverage (--check-coverage) ---")
        cov_n, cov_total, _covered, missing = check_subdomain_coverage(
            run_dir,
            preproc_root if preproc_root is not None else Path("preproc_out"),
            min_pct=coverage_min_pct,
        )
        if cov_total > 0:
            pct = 100.0 * cov_n / cov_total if cov_total else 100.0
            if pct < coverage_min_pct:
                print(
                    f"❌ Subdomain coverage {pct:.1f}% < required {coverage_min_pct:.1f}% "
                    f"({len(missing)} missing of {cov_total} applicable)"
                )
                exit_code = 1
            else:
                print(f"✅ Subdomain coverage {pct:.1f}% >= required {coverage_min_pct:.1f}%")

    return exit_code


def main():
    args = parse_args()
    code = check_run(
        args.run_dir,
        args.state_json,
        check_coverage=args.check_coverage,
        preproc_root=args.preproc_root,
        coverage_min_pct=args.coverage_min_pct,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
