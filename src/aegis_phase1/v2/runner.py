#!/usr/bin/env python3
"""Runner for AEGIS Phase 1 v2 pipeline.

Usage:
    python -m aegis_phase1.v2.runner                          # interactive menu
    python -m aegis_phase1.v2.runner --case PATH --run-all    # non-interactive

Sprint MAP-3 flags:
    --mock-llm                  Set MOCK_LLM=true (use MockInvoker).
    --model NAME                Ollama model (default: gemma4:e2b).
    --retry-failed D-04,D-07    After --run-all, re-process failed domains.
    --map-only                  Run only the MAP stage (skip REDUCE/OUTPUT).

Sprint Phase 3 decouple flag:
    --deterministic-only        Generate only the deterministic docs (04 body,
                                05, 06, 07, 07b, xlsx) without running MAP
                                or REDUCE. Useful for baseline validation
                                and post-MAP-failure recovery.

CORR-038 flag:
    --run-applicability         Generate ONLY Doc 04 + Doc 05 from the
                                ApplicabilityContext (v2 source of truth).
                                Skips MAP / REDUCE / Phase 1B entirely.
                                No LLM is invoked. Useful for verifying
                                applicability after a data fix without
                                waiting for the full pipeline.
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

    logging.getLogger("aegis_phase1.v2.output").setLevel(logging.WARNING)
    logging.getLogger("aegis_phase1.v2.output.doc_04a").setLevel(logging.WARNING)
    logging.getLogger("aegis_phase1.v2.output.doc_04b").setLevel(logging.WARNING)
    logging.getLogger("aegis_phase1.v2.output.doc_04c").setLevel(logging.WARNING)
    logging.getLogger("aegis_phase1.v2.output.doc_04d").setLevel(logging.WARNING)
    logging.getLogger("aegis_phase1.v2.output.doc_05").setLevel(logging.WARNING)
    logging.getLogger("aegis_phase1.v2.output.doc_07").setLevel(logging.WARNING)
    logging.getLogger("aegis_phase1.v2.output.doc_07b").setLevel(logging.WARNING)
    logging.getLogger("aegis_phase1.v2.output.xlsx_generator").setLevel(logging.WARNING)
    logging.getLogger("aegis_phase1.v2.output._common").setLevel(logging.WARNING)


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
        "--run-all-traced",
        action="store_true",
        help=(
            "AEGIS-P1-CORR-018a: run all stages through the full 18-node "
            "LangGraph (one root trace, per-domain/per-spec spans, nested "
            "LLM generations). Opt-in alternative to --run-all. Falls "
            "back to direct orchestrator calls when Langfuse is disabled."
        ),
    )
    parser.add_argument(
        "--run-all-graph",
        action="store_true",
        dest="run_all_graph",
        help=(
            "Alias of --run-all-traced (CORR-018a). Renamed for clarity; "
            "the legacy --run-all-traced flag still works."
        ),
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
        "--run-applicability",
        action="store_true",
        dest="run_applicability",
        help=(
            "CORR-038: Generate ONLY Doc 04 + Doc 05 from the "
            "ApplicabilityContext (v2 source of truth). Skips MAP, "
            "REDUCE, and Phase 1B. No LLM is invoked. Useful for "
            "verifying applicability after a data fix without "
            "waiting for the full pipeline."
        ),
    )
    parser.add_argument(
        "--run-clauses",
        action="store_true",
        dest="run_clauses",
        help=(
            "CORR-039: Generate ONLY Doc 06 (clause mapping matrix) "
            "from the ClauseMappingContext. No LLM. Skips MAP, "
            "REDUCE, and Phase 1B. Useful for verifying clause-to-"
            "sub-domain mapping after a preproc rebuild."
        ),
    )
    parser.add_argument(
        "--run-phase-1b",
        action="store_true",
        dest="run_phase_1b",
        help=(
            "CORR-039: Run Phase 1B (P1B-LLM-01 + P1B-LLM-02 per "
            "applicable_reg) and render Doc 05 with per-reg rationale. "
            "Requires MOCK_LLM=true or Ollama running with gemma4:e2b."
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
        default="gemma4:e2b",
        help="Ollama model name (default: gemma4:e2b)",
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
    # CORR-039-T1: inject typed loaders so _load_v2_catalog actually
    # populates v2_subdomains / v2_srs / v2_sos / v2_pairs / v2_catalog_*.
    # Pre-CORR-039 the runner passed only llm_invoker — every v2_* key
    # stayed empty and the v1-compat shim produced a hollow state.
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

    preproc_catalog = PreprocCatalogLoader(preproc_root="preproc_out")
    case_profile_loader = CaseProfileLoader(Path(args.case))
    catalog_loader = CatalogLoader(root=get_prompts_root() / "catalogs")
    orch = Phase1Orchestrator(
        llm_invoker=llm_invoker,
        preproc_catalog=preproc_catalog,
        case_profile_loader=case_profile_loader,
        catalog_loader=catalog_loader,
    )
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
    elif args.run_all_traced or getattr(args, "run_all_graph", False):
        logger.info(
            "Non-interactive mode — running all stages via 18-node LangGraph (CORR-018a)"
        )
        try:
            rc = cmd_run_all_traced(
                orch=orch,
                case_path=case_path,
                prep_path=prep_path,
                output_path=output_path,
            )
        except MapPartialFailure as exc:
            logger.error("Pipeline aborted — MAP partial failure: %s", exc)
            sys.exit(2)
        if rc != 0:
            sys.exit(rc)
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
    elif args.run_applicability:
        logger.info(
            "Non-interactive mode — applicability only (CORR-038; no LLM)"
        )
        paths = cmd_run_applicability(
            orch=orch, case_path=case_path, prep_path=prep_path, output_path=output_path
        )
        logger.info("=== APPLICABILITY DOCS COMPLETE ===")
        for label, p in paths.items():
            print(f"  {label}: {p}")
        print(f"  total: {len(paths)} artefacts")
    elif args.run_clauses:
        logger.info(
            "Non-interactive mode — clauses only (CORR-039; no LLM)"
        )
        paths = cmd_run_clauses(
            orch=orch, case_path=case_path, prep_path=prep_path, output_path=output_path
        )
        logger.info("=== CLAUSES DOC COMPLETE ===")
        for label, p in paths.items():
            print(f"  {label}: {p}")
        print(f"  total: {len(paths)} artefacts")
    elif args.run_phase_1b:
        logger.info(
            "Non-interactive mode — Phase 1B only (CORR-039; with LLM)"
        )
        paths = cmd_run_phase_1b(
            orch=orch, case_path=case_path, prep_path=prep_path, output_path=output_path
        )
        logger.info("=== PHASE 1B COMPLETE ===")
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


def cmd_run_applicability(
    *,
    orch: "Phase1Orchestrator",
    case_path: str,
    prep_path: str,
    output_path: str,
) -> dict[str, str]:
    """CORR-038-T4: render only Doc 04 + Doc 05 from the ApplicabilityContext.

    Skips MAP / REDUCE / Phase 1B entirely. No LLM is invoked. Builds
    the v2 state via ``orch.load()`` (which runs the v2 loaders + v1-compat
    shim), then renders Doc 04 (composite) and Doc 05.

    Returns:
        Mapping ``AEGIS-P1-04`` / ``AEGIS-P1-04b`` / ``AEGIS-P1-04c`` /
        ``AEGIS-P1-04d`` / ``AEGIS-P1-05`` -> absolute file path.
    """
    from aegis_phase1.v2.output.doc_04 import render_doc_04
    from aegis_phase1.v2.output.doc_05 import render_doc_05

    # Load v2 state (no LLM calls; no MAP / REDUCE).
    orch.load(case_path, prep_path)

    # Build output dir.
    out_dir = Path(output_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}
    # Doc 04 (composite: 04 + 04b + 04c + 04d).
    paths.update(render_doc_04(orch.state, str(out_dir), llm_invoker=None))
    # Doc 05 (per-regulation applicability).
    paths.update(render_doc_05(orch.state, str(out_dir), llm_invoker=None))

    # Surface in orch state for downstream consumers.
    orch.state["output_paths"] = dict(orch.state.get("output_paths", {}), **paths)

    logger.info("cmd_run_applicability: wrote %d artefacts to %s", len(paths), out_dir)
    return paths


def cmd_run_clauses(
    *,
    orch: "Phase1Orchestrator",
    case_path: str,
    prep_path: str,
    output_path: str,
) -> dict[str, str]:
    """CORR-039-T5: render only Doc 06 from the ClauseMappingContext.

    Skips MAP / REDUCE / Phase 1B entirely. No LLM is invoked. Builds
    the v2 state via ``orch.load()`` (which runs the v2 loaders + the
    T1 catalog_loader), then renders Doc 06 from the populated
    ClauseMappingContext.

    Returns:
        Mapping ``AEGIS-P1-06`` -> absolute file path.
    """
    from aegis_phase1.v2.output.doc_06 import render_doc_06

    orch.load(case_path, prep_path)
    out_dir = Path(output_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = render_doc_06(orch.state, str(out_dir))
    orch.state["output_paths"] = dict(orch.state.get("output_paths", {}), **paths)

    logger.info("cmd_run_clauses: wrote %d artefacts to %s", len(paths), out_dir)
    return paths


def cmd_run_phase_1b(
    *,
    orch: "Phase1Orchestrator",
    case_path: str,
    prep_path: str,
    output_path: str,
) -> dict[str, str]:
    """CORR-039-T5: run Phase 1B (P1B-LLM-01 + P1B-LLM-02 per applicable_reg).

    Loads the v2 state, then calls ``orch.run_phase_1b()`` which iterates
    per-regulation and invokes the 5-canonical-LLM ``Phase1Executor``
    (CORR-039-T4: with catalog filtering wired). Finally re-renders
    Doc 05 so §6.1b surfaces the per-reg rationale that Phase 1B
    populates into ``state['aggregated_data']['rationale_by_reg']``.

    Requires either ``MOCK_LLM=true`` / ``--mock-llm`` (returns a
    stub response) or a running Ollama with ``gemma4:e2b``.

    Returns:
        Mapping ``AEGIS-P1-05`` -> absolute file path (re-rendered
        Doc 05 with per-reg rationale populated).
    """
    from aegis_phase1.v2.output.doc_05 import render_doc_05

    orch.load(case_path, prep_path)
    out_dir = Path(output_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1B invokes P1B-LLM-01 + P1B-LLM-02 per applicable_reg
    # (CORR-039-T4 wires the catalog + classification inputs).
    orch.run_phase_1b()

    # Re-render Doc 05 so §6.1b surfaces the rationale_by_reg data.
    paths = render_doc_05(orch.state, str(out_dir), llm_invoker=orch.llm_invoker)
    orch.state["output_paths"] = dict(orch.state.get("output_paths", {}), **paths)

    # Surface per-reg count for the CLI summary line.
    rationale = (orch.state.get("aggregated_data") or {}).get("rationale_by_reg") or {}
    logger.info(
        "cmd_run_phase_1b: wrote %d artefacts to %s; rationale_by_reg has %d entries",
        len(paths),
        out_dir,
        len(rationale) if isinstance(rationale, dict) else 0,
    )
    return paths


def cmd_run_all_traced(
    *,
    orch: "Phase1Orchestrator",
    case_path: str,
    prep_path: str,
    output_path: str,
) -> int:
    """AEGIS-P1-CORR-018a entry: run the pipeline through the 18-node LangGraph.

    Builds the full StateGraph (load_baseline + 10 map nodes + 4 phase 1B
    nodes + 3 reduce nodes), wires callbacks / tags / metadata, and invokes
    it. The orchestrator's ``_langfuse_handler`` is forwarded (if present)
    so every LLM call inside each span nests under its named span. When
    Langfuse is disabled (``LANGFUSE_ENABLED=false``) the handler is
    ``None`` and the graph still runs — just without spans.

    Returns:
        Process-style exit code: ``0`` on success, ``2`` on
        ``OllamaUnreachableError`` (re-raised so the CLI can also map it).
    """
    from aegis_phase1.v2.graph import run_phase1_graph

    case_name = Path(case_path).name
    callbacks = [orch._langfuse_handler] if orch._langfuse_handler else None

    try:
        run_phase1_graph(
            orch,
            case_path,
            prep_path,
            output_dir=output_path,
            callbacks=callbacks,
            tags=[f"phase:phase1", f"case:{case_name}"],
            extra_metadata={"stage": "phase1", "graph": "v2.langgraph.full"},
        )
    except OllamaUnreachableError as exc:
        print(f"⚠ Ollama not reachable at {exc.base_url}.")
        print("  Start it with: ollama serve")
        print("  Or run with --mock-llm for offline mode.")
        return 2
    return 0


if __name__ == "__main__":
    main()
