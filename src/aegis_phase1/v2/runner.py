#!/usr/bin/env python3
"""Runner for AEGIS Phase 1 v2 pipeline.

Usage:
    python -m aegis_phase1.v2.runner                          # interactive menu
    python -m aegis_phase1.v2.runner --case PATH --run-all    # non-interactive

Sprint MAP-3 flags:
    --mock-llm                  Set MOCK_LLM=true (use MockInvoker).
    --model NAME                Ollama model (default: gemma4:e4b).
    --retry-failed D-04,D-07    After --run-all, re-process failed domains.
    --map-only                  Run only the MAP stage (skip REDUCE/OUTPUT).

Sprint Phase 3 decouple flag:
    --deterministic-only        Generate only the deterministic docs (04 body,
                                05, 06, 07, 07b, xlsx) without running MAP
                                or REDUCE. Useful for baseline validation
                                and post-MAP-failure recovery.
"""

import argparse
import logging
import sys
from pathlib import Path

import aegis_phase1.env  # noqa: F401 — load .env via env.py module-import side-effect

logger = logging.getLogger(__name__)

from aegis_phase1.llm.unified import OllamaUnreachableError  # noqa: E402 — placed after logger

_DEFAULT_PROJECTS = Path(__file__).resolve().parents[4]
DEFAULT_CASE = str(_DEFAULT_PROJECTS / "Methodology-main" / "02_CASES" / "Case_01_TinyTask_SaaS")
DEFAULT_PREPROC = str(_DEFAULT_PROJECTS / "Methodology-main" / "00_METHODOLOGY" / "PREPROCESSING")
DEFAULT_OUTPUT = "output/phase1"


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the v2 pipeline."""
    log_dir = Path("logs") / "phase1" / "v2"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_dir / "pipeline.log"), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> None:
    from aegis_phase1.v2.domain.processor import MapPartialFailure
    from aegis_phase1.v2.llm import build_llm_invoker
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    parser = argparse.ArgumentParser(description="AEGIS Phase 1 v2 Pipeline")
    parser.add_argument(
        "--case",
        default=DEFAULT_CASE,
        help="Case directory path",
    )
    parser.add_argument(
        "--regulatory-baseline-path",
        dest="regulatory_baseline_path",
        default=None,
        help=(
            "Path to the Regulatory Baseline directory (canonical; "
            "default: ../../../Methodology-main/00_METHODOLOGY/PREPROCESSING). "
            "Replaces the former --preprocessing flag."
        ),
    )
    parser.add_argument(
        "--preprocessing-path",
        dest="preprocessing_path",
        default=None,
        help=(
            "DEPRECATED alias for --regulatory-baseline-path. "
            "If supplied, a DeprecationWarning is emitted. "
            "Remove usage in new code."
        ),
    )
    parser.add_argument(
        "-p",
        "--preprocessing",
        dest="legacy_preprocessing",
        default=None,
        help=(
            "DEPRECATED legacy short form for --preprocessing-path. "
            "Use --regulatory-baseline-path instead."
        ),
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output directory path",
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run all stages non-interactively",
    )
    parser.add_argument(
        "--map-only",
        action="store_true",
        help="Run only the MAP stage (skip REDUCE/OUTPUT)",
    )
    parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help=(
            "Generate only the deterministic docs (04 body, 05, 06, "
            "07, 07b, xlsx). Skips MAP and REDUCE entirely. Useful "
            "for verifying baseline artefacts after LOAD when the "
            "MAP/REDUCE stages are broken or too slow."
        ),
    )
    parser.add_argument(
        "--skip-reduce-llms",
        action="store_true",
        help=(
            "Skip the 2 REDUCE-stage LLM calls (P1C-LLM-03 + P1C-LLM-02). "
            "Use for fast iteration or when running with --mock-llm."
        ),
    )
    parser.add_argument(
        "--skip-phase-1b",
        action="store_true",
        help=(
            "Skip the per-regulation P1B-LLM-02 RATIONALE call (Phase 1B). "
            "DOC 05 §6.1b will render a PENDING-REVIEW marker instead of "
            "per-regulation rationale prose. Use for fast iteration or "
            "when running with --mock-llm. (CORR-004 / CORR-005)"
        ),
    )
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Use MockInvoker (equivalent to MOCK_LLM=true)",
    )
    parser.add_argument(
        "--model",
        default="gemma4:e4b",
        help="Ollama model name (default: gemma4:e4b)",
    )
    parser.add_argument(
        "--retry-failed",
        default="",
        help="Comma-separated domain IDs to retry after --run-all (e.g. D-04,D-07)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    setup_logging("DEBUG" if args.verbose else "INFO")
    logger.info("AEGIS Phase 1 v2 Pipeline starting")

    if args.mock_llm:
        import os as _os
        _os.environ["MOCK_LLM"] = "true"

    # Resolve effective Regulatory Baseline path with deprecation handling.
    # Priority: --regulatory-baseline-path > --preprocessing-path > -p/--preprocessing > DEFAULT_PREPROC
    if args.regulatory_baseline_path is not None:
        rb_path = args.regulatory_baseline_path
    elif args.preprocessing_path is not None or args.legacy_preprocessing is not None:
        deprecated_value = (
            args.preprocessing_path
            if args.preprocessing_path is not None
            else args.legacy_preprocessing
        )
        import warnings

        warnings.warn(
            "CLI flag for the Regulatory Baseline path is deprecated "
            "(--preprocessing-path / --preprocessing). Use "
            "--regulatory-baseline-path instead. (Phase 0 rebranding)",
            DeprecationWarning,
            stacklevel=2,
        )
        rb_path = deprecated_value
    else:
        rb_path = DEFAULT_PREPROC

    case_path = str(Path(args.case).resolve())
    prep_path = str(Path(rb_path).resolve())
    output_path = str(Path(args.output).resolve())

    logger.info("Case path: %s", case_path)
    logger.info("Regulatory Baseline path: %s", prep_path)
    logger.info("Output path: %s", output_path)

    llm_invoker = build_llm_invoker(model=args.model)
    orch = Phase1Orchestrator(llm_invoker=llm_invoker)
    if args.skip_reduce_llms:
        orch.set_skip_reduce_llms(True)
    if getattr(args, "skip_phase_1b", False):
        orch.set_skip_phase_1b(True)

    if args.run_all:
        logger.info("Non-interactive mode — running all stages")
        try:
            orch.run_all(case_path, prep_path, output_path)
        except MapPartialFailure as exc:
            logger.error("Pipeline aborted — MAP partial failure: %s", exc)
            sys.exit(2)
        if args.retry_failed:
            domains = [d.strip() for d in args.retry_failed.split(",") if d.strip()]
            if domains:
                logger.info("Retrying failed domains: %s", domains)
                try:
                    orch.retry_failed(domains)
                except MapPartialFailure as exc:
                    logger.error("Retry still failing: %s", exc)
                    sys.exit(3)
        logger.info("Pipeline complete")
    elif args.map_only:
        logger.info("Non-interactive mode — MAP only")
        orch.load(case_path, prep_path)
        try:
            orch.map_domains()
        except MapPartialFailure as exc:
            logger.error("MAP partial failure: %s", exc)
            sys.exit(2)
        if args.retry_failed:
            domains = [d.strip() for d in args.retry_failed.split(",") if d.strip()]
            if domains:
                logger.info("Retrying failed domains: %s", domains)
                try:
                    orch.retry_failed(domains)
                except MapPartialFailure as exc:
                    logger.error("Retry still failing: %s", exc)
                    sys.exit(3)
    elif args.deterministic_only:
        logger.info(
            "Non-interactive mode — deterministic docs only (skip MAP/REDUCE)"
        )
        orch.load(case_path, prep_path)
        orch.generate_deterministic_docs(output_path)
        paths = orch.state.get("output_paths", {})
        logger.info("=== DETERMINISTIC DOCS COMPLETE ===")
        for label, p in paths.items():
            print(f"  {label}: {p}")
        print(f"  total: {len(paths)} artefacts")
    else:
        logger.info("Interactive mode — running wizard (CORR-006)")
        from aegis_phase1.v2.cli.menu import run_wizard

        try:
            run_wizard(orch, case_path, prep_path, output_path)
        except OllamaUnreachableError as exc:
            print(f"⚠ Ollama not reachable at {exc.base_url}.")
            print("  Start it with: ollama serve")
            print("  Or run with --mock-llm for offline mode.")
            sys.exit(2)


if __name__ == "__main__":
    main()
