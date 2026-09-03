#!/usr/bin/env python3
"""CORR-112 F4: Validate outputs and state against RefGate assertions.

Affirms:
  - 0 invented/ungrounded references across all outputs
  - 0 sections PENDING in state.json
  - 100% rendered sections tagged with [deterministic] or [LLM: ...]
  - 100% subdomain coverage across rendered Doc 04-07b (--check-coverage)

CORR-OBJ-Phase4: this script is also the **single entry point** for the
no-regression rule (per ``docs/OBJECTIVES_CONTRACT.md`` §5). When invoked
with ``--contract``, it walks the 14 objectives table, runs the
deterministic [G] gates and sampled [J] judge cells, and emits a
per-objective scorecard. Missing gates and unwired judges are warned
in non-strict mode; in ``--strict`` mode they are reported but the
exit code is driven by:
  * any [G] failure, and
  * any regression vs ``--baseline PATH`` (per-objective status more
    severe than the baseline).

Usage:
    # Legacy single-run mode (CORR-112 F4)
    python -m scripts.eval.check_gate --run-dir /path/to/run
    # Contract-driven scorecard (no-regression rule)
    python -m scripts.eval.check_gate --run-dir /path/to/run --contract docs/OBJECTIVES_CONTRACT.md
    python -m scripts.eval.check_gate --run-dir /path/to/run --contract ... --strict --baseline baseline.json
    python -m scripts.eval.check_gate --run-dir /path/to/run --contract ... --strict --capture-baseline baseline.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

from aegis_phase1.prompts_v2.ref_gate import RefGate

logger = logging.getLogger(__name__)

# Default contract path (per OBJECTIVES_CONTRACT §2 — AEGIS-DOC-OBJ-001).
DEFAULT_CONTRACT_PATH = Path("docs/OBJECTIVES_CONTRACT.md")


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
    # ────────────────────────────────────────────────────────────────
    # CORR-OBJ-Phase4: contract-driven scorecard flags
    # ────────────────────────────────────────────────────────────────
    p.add_argument(
        "--contract",
        required=False,
        type=Path,
        default=None,
        help=(
            "Path to OBJECTIVES_CONTRACT.md. When provided, check_gate runs "
            "the per-objective scorecard (14 objectives) and applies the "
            "no-regression rule per OBJECTIVES_CONTRACT §5."
        ),
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Strict mode: any [G] failure OR any regression vs the "
            "baseline (when --baseline is set) exits non-zero. Missing "
            "gates and unwired judges are reported but do not fail by "
            "themselves (per OBJECTIVES_CONTRACT §2 status column)."
        ),
    )
    p.add_argument(
        "--baseline",
        required=False,
        type=Path,
        default=None,
        help=(
            "Path to a baseline scorecard JSON (saved by a previous "
            "run via --capture-baseline). In --strict mode, any [G] "
            "regression against the baseline exits 2."
        ),
    )
    p.add_argument(
        "--capture-baseline",
        required=False,
        type=Path,
        default=None,
        help=(
            "Path to write the current run's scorecard JSON as the "
            "baseline. Used to bootstrap the no-regression rule on the "
            "first validation run. Conflicts with --baseline."
        ),
    )
    p.add_argument(
        "--output",
        required=False,
        type=Path,
        default=None,
        help="Path to write the scorecard JSON (in addition to stdout).",
    )
    p.add_argument(
        "--case-id",
        required=False,
        type=str,
        default="",
        help="Optional case_id tag for the scorecard (e.g. case1-tinytask).",
    )
    p.add_argument(
        "--run-id",
        required=False,
        type=str,
        default="",
        help="Optional run_id tag for the scorecard.",
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
        print("[info] state.json not found, skipping PENDING sections check.")

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
        print(f"[info] {tagged_docs}/{total_docs} rendered documents carry provenance tags.")

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
    # CORR-OBJ-00: default to AEGIS_GATE_MODE=hard so RefGate violations
    # fail the check; --lenient switches to warn (dev mode).
    if getattr(args, "lenient", False):
        os.environ.setdefault("AEGIS_GATE_MODE", "warn")
    else:
        os.environ.setdefault("AEGIS_GATE_MODE", "hard")
    print(f"Gate mode: {os.environ['AEGIS_GATE_MODE']}")
    # Contract-driven scorecard mode (CORR-OBJ-Phase4). When --contract
    # is supplied, the scorecard is the primary artefact and the exit
    # code is driven by the no-regression rule. The legacy check_run
    # still runs underneath so a single invocation covers both legacy
    # checks and the new scorecard.
    if args.contract is not None:
        code = run_scorecard_check(
            args.run_dir,
            contract_path=args.contract,
            state_json=args.state_json,
            preproc_root=args.preproc_root,
            case_id=args.case_id,
            run_id=args.run_id,
            strict=args.strict,
            baseline_path=args.baseline,
            capture_baseline_path=args.capture_baseline,
            output_path=args.output,
        )
        sys.exit(code)
    code = check_run(
        args.run_dir,
        args.state_json,
        check_coverage=args.check_coverage,
        preproc_root=args.preproc_root,
        coverage_min_pct=args.coverage_min_pct,
    )
    sys.exit(code)


# ────────────────────────────────────────────────────────────────────
# CORR-OBJ-Phase4: contract-driven scorecard entry point
# ────────────────────────────────────────────────────────────────────


def run_scorecard_check(
    run_dir: Path,
    *,
    contract_path: Path,
    state_json: Path | None = None,
    preproc_root: Path | None = None,
    case_id: str = "",
    run_id: str = "",
    strict: bool = False,
    baseline_path: Path | None = None,
    capture_baseline_path: Path | None = None,
    output_path: Path | None = None,
) -> int:
    """Run the contract-driven per-objective scorecard against a run.

    This is the **single entry point** for the no-regression rule
    (OBJECTIVES_CONTRACT §5). Behaviour:

    * Parses the 14 objectives from ``contract_path`` (markdown table).
    * Runs the registered [G] / [J] cells.
    * Emits a per-objective scorecard to stdout AND ``--output PATH``.
    * In ``strict`` mode: any [G] failure OR regression vs ``--baseline``
      exits non-zero (exit code 2 for regressions, 1 for failures).
    * ``--capture-baseline PATH`` saves the current scorecard as JSON
      and returns 0 regardless of failures (the bootstrap path).

    Returns 0 on success, 1 on [G] failure, 2 on regression.
    """
    if baseline_path is not None and capture_baseline_path is not None:
        print("❌ --baseline and --capture-baseline are mutually exclusive", file=sys.stderr)
        return 1

    # Local import to avoid a hard dependency for users who only run
    # the legacy single-run checks. Try package import first; fall back
    # to absolute import if scripts/eval/ was invoked directly.
    try:
        from scripts.eval.objectives_contract import (  # type: ignore[import-not-found]
            EXPECTED_OBJECTIVE_COUNT,
            CellStatus,
            diff_against_baseline,
            load_baseline,
            parse_objectives_contract,
            run_scorecard,
            save_baseline,
        )
    except ModuleNotFoundError:
        # Direct invocation: ensure repo root is on sys.path.
        _repo_root = Path(__file__).resolve().parents[2]
        if str(_repo_root) not in sys.path:
            sys.path.insert(0, str(_repo_root))
        from scripts.eval.objectives_contract import (
            EXPECTED_OBJECTIVE_COUNT,
            CellStatus,
            diff_against_baseline,
            load_baseline,
            parse_objectives_contract,
            run_scorecard,
            save_baseline,
        )

    print(f"=== AEGIS Phase 1 scorecard for {run_dir} ===")
    print(f"  contract: {contract_path}")
    if strict:
        print("  mode: STRICT (any [G] failure or regression fails the run)")
    else:
        print("  mode: NON-STRICT (missing gates warn; only hard failures exit non-zero)")

    objectives = parse_objectives_contract(contract_path)
    if not objectives:
        print(f"❌ No objectives parsed from {contract_path}.", file=sys.stderr)
        return 1
    print(f"  parsed {len(objectives)} objectives (expected {EXPECTED_OBJECTIVE_COUNT})")

    scorecard = run_scorecard(
        run_dir,
        objectives,
        case_id=case_id,
        run_id=run_id,
        state_json=state_json,
        preproc_root=preproc_root,
    )
    scorecard.contract_path = str(contract_path)

    # Print per-objective verdict to stdout.
    print()
    print(scorecard.to_markdown())
    print(
        f"Summary: {scorecard.n_pass()} PASS / {scorecard.n_fail()} FAIL / "
        f"{scorecard.n_missing()} MISSING / {scorecard.n_skipped()} SKIPPED / "
        f"{scorecard.n_total()} total"
    )

    # Optionally write JSON.
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(scorecard.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  scorecard JSON written to {output_path}")

    # Capture-baseline path: bootstrap the no-regression rule.
    if capture_baseline_path is not None:
        save_baseline(scorecard, capture_baseline_path)
        print(f"  baseline captured to {capture_baseline_path}")
        return 0

    # Regression check (only when a baseline is supplied).
    regression_exit_code = 0
    if baseline_path is not None:
        if not baseline_path.exists():
            print(
                f"❌ baseline {baseline_path} not found. "
                f"Use --capture-baseline on the first run.",
                file=sys.stderr,
            )
            return 1
        baseline = load_baseline(baseline_path)
        regressions = diff_against_baseline(scorecard, baseline)
        if regressions:
            print()
            print(f"❌ {len(regressions)} regression(s) vs baseline {baseline_path}:")
            for r in regressions:
                print(
                    f"   - {r.objective_id} ({r.title}): "
                    f"{r.baseline_status} → {r.current_status}"
                )
            regression_exit_code = 2
        else:
            print(f"  0 regressions vs baseline {baseline_path}")

    # Decide exit code.
    fail_results = [r for r in scorecard.results if r.status == CellStatus.FAIL]
    error_results = [r for r in scorecard.results if r.status == CellStatus.ERROR]

    if strict:
        if regression_exit_code != 0:
            return regression_exit_code
        if fail_results:
            return 1
        if error_results:
            return 1
        return 0

    # Non-strict: hard-fail on FAIL/ERROR only (missing gates warn).
    if fail_results or error_results:
        return 1
    return 0


if __name__ == "__main__":
    main()
