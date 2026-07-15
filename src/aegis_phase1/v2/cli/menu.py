"""menu — Sequential wizard for the v2 map-reduce pipeline.

Replaces the legacy hub-and-spoke menu (CORR-006) with a linear 6-step
wizard: one question at a time, with Enter-to-accept-default for each
prompt. After the wizard collects the configuration, it invokes
``orchestrator.run_all()`` and prints a summary.

Sequence:
    1/6 Case directory
    2/6 Regulatory Baseline directory
    3/6 Mode (Mock / Real)
    4/6 Model (only if Mode=Real)
    5/6 Skip flags (advanced)
    6/6 Run pipeline? [Y/n]

If the user responds ``N`` to step 6, the wizard exits without running.
If stdin is not a TTY (e.g., piped input), the wizard exits with a
message suggesting ``--run-all`` instead.

References:
    - contracts/SPRINT001_v2-core.md (C-005)
    - AEGIS-P1-CORR-006 (wizard contract)
"""

from __future__ import annotations

import json
import logging
import sys
import termios
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MENU_HISTORY_PATH = Path("logs/phase1/v2/menu_history.jsonl")

_DEFAULT_PROJECTS = Path(__file__).resolve().parents[5]
DEFAULT_CASE_PATH = str(
    _DEFAULT_PROJECTS / "Methodology-main" / "02_CASES" / "Case_01_TinyTask_SaaS"
)
DEFAULT_REGULATORY_BASELINE_PATH = str(
    _DEFAULT_PROJECTS / "Methodology-main" / "00_METHODOLOGY" / "PREPROCESSING"
)
DEFAULT_OUTPUT_DIR = "output/phase1"
DEFAULT_MODEL = "gemma4:e4b"


def _log_action(action: str, **data) -> None:
    """Append a JSONL entry to the menu history file."""
    MENU_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(UTC).isoformat(), "action": action}
    entry.update(data)
    with open(MENU_HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _render_header() -> None:
    """Print the boxed header banner."""
    print()
    print("╔══════════════════════════════════════════╗")
    print("║       AEGIS Phase 1 Pipeline v2         ║")
    print("╚══════════════════════════════════════════╝")
    print()


def _prompt_with_default(label: str, default: str) -> str:
    """Prompt the user for a string value; Enter accepts the default.

    Args:
        label: Display label (e.g., "Case directory").
        default: Default value shown in brackets.

    Returns:
        User input, or ``default`` if empty.
    """
    raw = input(f"  {label} [{default}]: ").strip()
    return raw if raw else default


def _prompt_choice(label: str, choices: list[tuple[str, str]], default_index: int = 0) -> tuple[str, str]:
    """Prompt the user to pick one of several choices by number.

    Args:
        label: Display label (e.g., "Mode").
        choices: List of ``(key, description)`` tuples.
        default_index: Index of the default choice if user presses Enter.

    Returns:
        The chosen ``(key, description)`` tuple.
    """
    print(f"  {label}")
    for idx, (key, desc) in enumerate(choices, start=1):
        marker = ">" if (idx - 1) == default_index else " "
        print(f"  {marker} {idx}) {key} — {desc}")
    raw = input(f"  [{choices[default_index][0]}]: ").strip()
    if not raw:
        return choices[default_index]
    # Accept numeric input
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(choices):
            return choices[idx]
    # Accept key string
    for choice in choices:
        if choice[0] == raw:
            return choice
    # Fallback to default
    return choices[default_index]


def _prompt_yes_no(label: str, default_yes: bool = True) -> bool:
    """Prompt the user for a yes/no answer; Enter accepts the default."""
    suffix = "[Y/n]" if default_yes else "[y/N]"
    raw = input(f"  {label} {suffix}: ").strip().lower()
    if not raw:
        return default_yes
    return raw in ("y", "yes")


def _prompt_skip_flags() -> tuple[bool, bool]:
    """Ask the user whether to override the default skip flags."""
    print("  Skip flags (advanced):")
    print("    skip-phase-1b:  skip P1B-LLM-02 RATIONALE calls")
    print("    skip-reduce-llms: skip P1C-LLM-03/02 REDUCE calls")
    print("  Defaults: skip-phase-1b=n, skip-reduce-llms=n")
    if not _prompt_yes_no("Override?", default_yes=False):
        return (False, False)
    skip_1b = _prompt_yes_no("skip-phase-1b?", default_yes=False)
    skip_reduce = _prompt_yes_no("skip-reduce-llms?", default_yes=False)
    return (skip_1b, skip_reduce)


def _run_pipeline(orch: object, mode: str, model: str, output_dir: str) -> dict:
    """Execute the pipeline using the wizard's collected configuration."""
    from aegis_phase1.v2.domain.processor import MapPartialFailure

    case_path = orch.case_path
    regulatory_baseline_path = orch.regulatory_baseline_path

    print()
    print("─" * 50)
    print("Running pipeline with:")
    print(f"  case_path         : {case_path}")
    print(f"  regulatory_baseline: {regulatory_baseline_path}")
    print(f"  mode              : {mode}")
    if mode == "real":
        print(f"  model             : {model}")
    print(f"  output_dir        : {output_dir}")
    print("─" * 50)
    print()

    try:
        paths = orch.run_all()
    except MapPartialFailure as exc:
        logger.error("MAP partial failure: %s", exc)
        print(f"  ⚠ MAP partial failure: {exc}")
        paths = {}

    print()
    print("─" * 50)
    print("✓ Pipeline complete")
    if paths:
        for label, p in paths.items():
            if isinstance(p, str):
                print(f"  {label}: {p}")
            else:
                print(f"  {label}: {p}")
        print(f"  total: {len(paths)} artefacts")
    else:
        print("  (no artefacts produced — see logs)")
    print("─" * 50)
    return paths


def run_wizard(
    orch: object,
    case_path: str | None = None,
    regulatory_baseline_path: str | None = None,
    output_dir: str | None = None,
) -> dict:
    """Sequential wizard: collect config, then run the pipeline.

    Replaces the legacy hub-and-spoke ``run_menu``.  One question at a
    time, Enter accepts default.

    Args:
        orch: ``Phase1Orchestrator`` instance.
        case_path: Optional default case directory.
        regulatory_baseline_path: Optional default Regulatory Baseline path.
        output_dir: Optional default output directory.

    Returns:
        Paths dict from ``orchestrator.run_all()`` (empty if user declined
        to run or stdin not a TTY).
    """
    if not sys.stdin.isatty():
        print(
            "Interactive wizard requires a TTY. Use --run-all for "
            "non-interactive mode, or supply CLI flags directly."
        )
        _log_action("wizard_skipped_non_tty")
        return {}

    _render_header()
    print("Answer each prompt (Enter to accept default), or Ctrl+C to abort.")
    print()

    _log_action("wizard_start")

    # Step 1: Case directory
    default_case = case_path or DEFAULT_CASE_PATH
    case_path = _prompt_with_default("[1/6] Case directory", default_case)
    print()

    # Step 2: Regulatory Baseline directory
    default_baseline = regulatory_baseline_path or DEFAULT_REGULATORY_BASELINE_PATH
    regulatory_baseline_path = _prompt_with_default(
        "[2/6] Regulatory Baseline directory", default_baseline
    )
    print()

    # Step 3: Mode
    mode_choice = _prompt_choice(
        "[3/6] Mode",
        [
            ("mock", "MockInvoker (no LLM, fast, deterministic)"),
            ("real", "Real Ollama (requires `ollama serve` running)"),
        ],
        default_index=0,
    )
    mode = mode_choice[0]
    print()

    # Step 4: Model (only if real)
    model = DEFAULT_MODEL
    if mode == "real":
        model = _prompt_with_default(
            "[4/6] Model",
            f"{DEFAULT_MODEL} (32K context, 2048 max tokens)",
        )
        # Strip parenthetical hint if user accepted default
        if model.startswith(f"{DEFAULT_MODEL} ("):
            model = DEFAULT_MODEL
        print()

    # Step 5: Skip flags
    skip_step_number = 5 if mode == "real" else 4
    skip_1b, skip_reduce = _prompt_skip_flags()
    print()

    # Step 6: Run?
    run_step_number = 6 if mode == "real" else 5
    if not _prompt_yes_no(f"[{run_step_number}/6] Run pipeline?", default_yes=True):
        print()
        print("Aborted. Configured (not run):")
        print(f"  case_path          : {case_path}")
        print(f"  regulatory_baseline : {regulatory_baseline_path}")
        print(f"  mode               : {mode}")
        if mode == "real":
            print(f"  model              : {model}")
        print(f"  skip-phase-1b      : {skip_1b}")
        print(f"  skip-reduce-llms   : {skip_reduce}")
        print(f"  output_dir         : {output_dir or DEFAULT_OUTPUT_DIR}")
        _log_action("wizard_aborted")
        return {}

    # Apply configuration to orchestrator
    orch_output_dir = output_dir or DEFAULT_OUTPUT_DIR
    try:
        orch.load(case_path, regulatory_baseline_path=regulatory_baseline_path)
    except Exception as exc:
        logger.exception("LOAD failed")
        print(f"  ⚠ LOAD failed: {exc}")
        _log_action("wizard_load_failed", error=str(exc))
        return {}

    if mode == "real":
        # Set model and ensure LLM is enabled
        if hasattr(orch, "llm_invoker") and orch.llm_invoker is not None:
            if hasattr(orch.llm_invoker, "model"):
                orch.llm_invoker.model = model
    else:
        # Mock mode: ensure MOCK_LLM env var is set
        import os
        os.environ["MOCK_LLM"] = "true"
        if hasattr(orch, "llm_invoker") and orch.llm_invoker is None:
            from aegis_phase1.v2.llm import build_llm_invoker
            orch.llm_invoker = build_llm_invoker(model=model)

    if skip_1b:
        orch.set_skip_phase_1b(True)
    if skip_reduce:
        orch.set_skip_reduce_llms(True)

    _log_action(
        "wizard_run",
        case_path=case_path,
        regulatory_baseline_path=regulatory_baseline_path,
        mode=mode,
        model=model,
        skip_phase_1b=skip_1b,
        skip_reduce_llms=skip_reduce,
        output_dir=orch_output_dir,
    )

    return _run_pipeline(orch, mode, model, orch_output_dir)


# ─────────────────────────────────────────────────────────────────────
# Backwards-compatibility alias (deprecated since CORR-006)
# ─────────────────────────────────────────────────────────────────────


def run_menu(
    orch: object,
    case_path: str | None = None,
    regulatory_baseline_path: str | None = None,
    output_dir: str | None = None,
) -> None:
    """DEPRECATED alias for ``run_wizard``.

    Kept for one release so external callers don't break. Logs a
    DeprecationWarning and delegates to ``run_wizard``.
    """
    import warnings

    warnings.warn(
        "run_menu() is deprecated; use run_wizard() instead. (CORR-006)",
        DeprecationWarning,
        stacklevel=2,
    )
    run_wizard(orch, case_path, regulatory_baseline_path, output_dir)