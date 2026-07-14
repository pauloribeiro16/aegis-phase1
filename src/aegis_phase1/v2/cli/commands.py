"""commands — Handler functions for v2 CLI menu actions.

Each function encapsulates a single menu action.  Functions that interact
with the pipeline accept an ``orchestrator`` instance (``Phase1Orchestrator``)
and an optional ``state`` dict, and return the updated state.

References:
    - contracts/SPRINT001_v2-core.md (C-005)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Stage-level commands ──────────────────────────────────────────────


def cmd_load(
    orchestrator: object,
    case_path: str,
    preprocessing_path: str,
) -> dict:
    """Run the LOAD stage.

    Loads company context, taxonomy, ontology, and sub-domain definitions
    into the pipeline state.

    Args:
        orchestrator: ``Phase1Orchestrator`` instance.
        case_path: Path to the case directory.
        preprocessing_path: Path to the PREPROCESSING directory.

    Returns:
        Updated pipeline state dict.
    """
    logger.info("CMD load case_path=%s preprocessing_path=%s", case_path, preprocessing_path)
    start = time.perf_counter()
    state = orchestrator.load(case_path, preprocessing_path)
    elapsed = time.perf_counter() - start
    subdomain_count = len(state.get("subdomains", {}))
    reg_count = len(state.get("regulations", []))
    logger.info(
        "LOAD complete subdomains=%d regulations=%d elapsed=%.2fs",
        subdomain_count,
        reg_count,
        elapsed,
    )
    print(f"  LOAD stage finished in {elapsed:.1f}s — {subdomain_count} sub-domains, {reg_count} regulations")
    return state


def cmd_map(orchestrator: object, state: dict) -> dict:
    """Run the MAP stage.

    Processes each macro-domain through an LLM to adapt HSOs.

    Args:
        orchestrator: ``Phase1Orchestrator`` instance.
        state: Current pipeline state.

    Returns:
        Updated pipeline state dict. On partial failure the state is
        still returned (with the FAILED entries), the message is
        printed, and a ``MapPartialFailure`` is re-raised so the menu
        loop can decide whether to continue.
    """
    logger.info("CMD map")
    start = time.perf_counter()
    from aegis_phase1.v2.domain.processor import MapPartialFailure

    try:
        result = orchestrator.map_domains()
    except MapPartialFailure as exc:
        elapsed = time.perf_counter() - start
        state["current_stage"] = "MAP_FAILED"
        failed = _extract_failed_domains(getattr(orchestrator, "state", {}))
        print(f"  MAP stage finished in {elapsed:.1f}s — PARTIAL FAILURE")
        print(f"  Failed domains: {', '.join(failed) if failed else '(unknown)'}")
        print(f"  Reason: {exc}")
        print("  → state persisted. Use --retry-failed to re-process.")
        raise

    elapsed = time.perf_counter() - start
    domain_count = len(result.get("domain_results", {}))
    logger.info("MAP complete domains=%d elapsed=%.2fs", domain_count, elapsed)
    state["domain_results"] = result.get("domain_results", {})
    state["current_stage"] = "MAPPED"
    print(f"  MAP stage finished in {elapsed:.1f}s — {domain_count} domains processed")
    return state


def cmd_reduce(orchestrator: object, state: dict) -> dict:
    """Run the REDUCE stage.

    Concatenates, merges, resolves conflicts, and applies proportionality.

    Args:
        orchestrator: ``Phase1Orchestrator`` instance.
        state: Current pipeline state.

    Returns:
        Updated pipeline state dict.
    """
    logger.info("CMD reduce")
    start = time.perf_counter()
    result = orchestrator.reduce()
    elapsed = time.perf_counter() - start
    logger.info("REDUCE complete elapsed=%.2fs", elapsed)
    state["aggregated_data"] = result.get("aggregated_data", {})
    state["current_stage"] = "REDUCED"
    print(f"  REDUCE stage finished in {elapsed:.1f}s")
    return state


def cmd_output(orchestrator: object, state: dict, output_dir: str) -> dict:
    """Run the OUTPUT stage.

    Generates all output documents from templates.

    Args:
        orchestrator: ``Phase1Orchestrator`` instance.
        state: Current pipeline state.
        output_dir: Directory to write outputs into.

    Returns:
        Updated pipeline state dict.
    """
    logger.info("CMD output output_dir=%s", output_dir)
    start = time.perf_counter()
    orchestrator.generate_outputs(output_dir)
    elapsed = time.perf_counter() - start
    state.setdefault("output_paths", {})
    detailed = getattr(orchestrator.state, "get", lambda *_: None)("output_paths") if hasattr(orchestrator, "state") else None
    if isinstance(detailed, dict):
        for k, v in detailed.items():
            state["output_paths"][k] = v
    elif isinstance(getattr(orchestrator, "state", None), dict):
        orch_paths = orchestrator.state.get("output_paths", {})
        if isinstance(orch_paths, dict):
            for k, v in orch_paths.items():
                state["output_paths"][k] = v
    state["output_paths"]["output_dir"] = output_dir
    orch_errors = getattr(orchestrator.state, "get", lambda *_: None)("errors") if hasattr(orchestrator, "state") else None
    if isinstance(orch_errors, list):
        for err in orch_errors:
            if err not in state.setdefault("errors", []):
                state["errors"].append(err)
    elif isinstance(getattr(orchestrator, "state", None), dict):
        for err in orchestrator.state.get("errors", []):
            if err not in state.setdefault("errors", []):
                state["errors"].append(err)
    state["current_stage"] = "OUTPUT_DONE"
    logger.info("OUTPUT complete elapsed=%.2fs", elapsed)
    print(f"  OUTPUT stage finished in {elapsed:.1f}s — outputs written to {output_dir}")
    return state


# ── Composite commands ────────────────────────────────────────────────


def cmd_run_all(
    orchestrator: object,
    case_path: str,
    preprocessing_path: str,
    output_dir: str,
) -> dict:
    """Run the full pipeline: LOAD → MAP → REDUCE → OUTPUT.

    Args:
        orchestrator: ``Phase1Orchestrator`` instance.
        case_path: Path to the case directory.
        preprocessing_path: Path to the PREPROCESSING directory.
        output_dir: Directory to write outputs into.

    Returns:
        Final pipeline state dict.

    Raises:
        MapPartialFailure: When MAP fails for ≥1 domain. The exception
            propagates to the menu loop; the user is told how to retry.
    """
    logger.info("CMD run_all case_path=%s output_dir=%s", case_path, output_dir)
    start = time.perf_counter()
    from aegis_phase1.v2.domain.processor import MapPartialFailure

    try:
        state = orchestrator.run_all(case_path, preprocessing_path, output_dir)
    except MapPartialFailure as exc:
        elapsed = time.perf_counter() - start
        failed = _extract_failed_domains(getattr(orchestrator, "state", {}))
        print(f"  Pipeline aborted after {elapsed:.1f}s — MAP partial failure")
        print(f"  Failed domains: {', '.join(failed) if failed else '(unknown)'}")
        print(f"  Reason: {exc}")
        print("  → state persisted. Use --retry-failed D-XX[,D-YY] to re-process.")
        raise

    elapsed = time.perf_counter() - start
    logger.info("RUN_ALL complete elapsed=%.2fs", elapsed)
    stages = ["LOAD", "MAP", "REDUCE", "OUTPUT"]
    for s in stages:
        print(f"  ✓ {s}")
    print(f"  Full pipeline finished in {elapsed:.1f}s")
    return state


def cmd_run_with_checkpoint(
    orchestrator: object,
    case_path: str,
    preprocessing_path: str,
    output_dir: str,
) -> dict:
    """Run the pipeline with pauses between stages.

    Shows the contents of the ``work/`` directory after each stage and
    prompts the user to press Enter before continuing.

    Args:
        orchestrator: ``Phase1Orchestrator`` instance.
        case_path: Path to the case directory.
        preprocessing_path: Path to the PREPROCESSING directory.
        output_dir: Directory to write outputs into.

    Returns:
        Final pipeline state dict.
    """
    logger.info("CMD run_with_checkpoint")
    print("\n  Running pipeline with checkpoint mode...\n")

    state = cmd_load(orchestrator, case_path, preprocessing_path)
    _checkpoint_prompt()

    state = cmd_map(orchestrator, state)
    _checkpoint_prompt()

    state = cmd_reduce(orchestrator, state)
    _checkpoint_prompt()

    state = cmd_output(orchestrator, state, output_dir)
    print("  Pipeline complete.")
    return state


def _checkpoint_prompt() -> None:
    """Show work/ contents and wait for the user to continue."""
    work_dir = Path("work")
    if work_dir.is_dir():
        print("\n  work/ directory contents:")
        for p in sorted(work_dir.iterdir()):
            size = p.stat().st_size if p.is_file() else 0
            tag = "(dir)" if p.is_dir() else f"{size:>8,} B"
            print(f"    {p.name:40s} {tag}")
    else:
        print("\n  work/ directory does not exist yet.")
    input("\n  Press Enter to continue to the next stage...")


# ── Utility commands ──────────────────────────────────────────────────


def cmd_view_logs() -> None:
    """Show the contents of the log directory (``logs/phase1/v2/``)."""
    log_dir = Path("logs/phase1/v2")
    if not log_dir.is_dir():
        print("  Log directory not found: logs/phase1/v2/")
        return
    print(f"\n  Logs in {log_dir}/:")
    jsonl_files = sorted(log_dir.glob("*.jsonl"))
    txt_files = sorted(log_dir.glob("*.log"))
    for f in jsonl_files + txt_files:
        size = f.stat().st_size
        mtime = f.stat().st_mtime
        print(f"    {f.name:45s} {size:>8,} B  (modified {time.ctime(mtime)})")
    if not jsonl_files and not txt_files:
        print("    (empty — no log files yet)")


def cmd_view_work() -> None:
    """Show the contents of the ``work/`` directory."""
    work_dir = Path("work")
    if not work_dir.is_dir():
        print("  work/ directory not found.")
        return
    print(f"\n  Contents of work/:")
    for p in sorted(work_dir.iterdir()):
        if p.is_dir():
            print(f"    {p.name}/")
        else:
            size = p.stat().st_size
            print(f"    {p.name:45s} {size:>8,} B")
    if not list(work_dir.iterdir()):
        print("    (empty)")


def cmd_compare_with_reference(state: dict, reference_path: str) -> None:
    """Compare pipeline output with reference documents.

    Args:
        state: Current pipeline state (must contain ``output_paths``).
        reference_path: Path to reference documents directory.
    """
    ref_dir = Path(reference_path)
    if not ref_dir.is_dir():
        print(f"  Reference directory not found: {reference_path}")
        return

    output_dir = Path(state.get("output_paths", {}).get("output_dir", ""))
    if not output_dir.is_dir():
        print("  No output directory in state — run the OUTPUT stage first.")
        return

    print(f"\n  Comparing {output_dir} with reference {ref_dir}/ ...\n")
    ref_files = sorted(ref_dir.glob("*.md"))
    out_files = sorted(output_dir.glob("*.md"))

    ref_names = {p.name for p in ref_files}
    out_names = {p.name for p in out_files}

    missing = ref_names - out_names
    extra = out_names - ref_names

    if not missing and not extra:
        print("  All expected files present.")
    else:
        if missing:
            print(f"  Missing from output ({len(missing)}):")
            for m in sorted(missing):
                print(f"    - {m}")
        if extra:
            print(f"  Extra files in output ({len(extra)}):")
            for e in sorted(extra):
                print(f"    + {e}")

    # Compare content of matching files
    common = ref_names & out_names
    differing = 0
    for name in sorted(common):
        ref = ref_dir / name
        out = output_dir / name
        ref_text = ref.read_text(encoding="utf-8")
        out_text = out.read_text(encoding="utf-8")
        if ref_text != out_text:
            differing += 1

    print(f"\n  Matching files: {len(common)}")
    print(f"  Content differs: {differing}")
    print(f"  Missing/extra: {len(missing) + len(extra)}")
    logger.info(
        "compare_with_reference matching=%d differing=%d missing=%d extra=%d",
        len(common),
        differing,
        len(missing),
        len(extra),
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _extract_failed_domains(orch_state: dict | object) -> list[str]:
    """Return the list of domain IDs whose ``llm_status`` is ``FAILED``.

    Accepts either a dict ``state`` or an object exposing ``.state``.
    Returns an empty list when nothing failed.
    """
    state_obj: dict | None = None
    if isinstance(orch_state, dict) and "domain_results" in orch_state:
        state_obj = orch_state
    elif hasattr(orch_state, "get"):
        try:
            state_obj = orch_state.get("domain_results")  # type: ignore[union-attr]
            if not isinstance(state_obj, dict):
                state_obj = None
        except Exception:  # noqa: BLE001
            state_obj = None
    if not isinstance(state_obj, dict):
        return []
    return sorted(
        did for did, res in state_obj.items()
        if isinstance(res, dict) and res.get("llm_status") == "FAILED"
    )
