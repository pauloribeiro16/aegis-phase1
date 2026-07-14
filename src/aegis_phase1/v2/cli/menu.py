"""menu — Interactive CLI menu for the v2 map-reduce pipeline.

Uses ``beaupy`` for interactive option selection (same pattern as
``scripts/run_phase1.py``).  All menu actions are dispatched to handler
functions in ``commands.py``.

References:
    - contracts/SPRINT001_v2-core.md (C-005)
    - scripts/run_phase1.py (beaupy usage pattern)
"""

from __future__ import annotations

import json
import logging
import sys
import termios
import time
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MENU_HISTORY_PATH = Path("logs/phase1/v2/menu_history.jsonl")

_DEFAULT_PROJECTS = Path(__file__).resolve().parents[5]
DEFAULT_CASE_PATH = _DEFAULT_PROJECTS / "Methodology-main" / "02_CASES" / "Case_01_TinyTask_SaaS"
DEFAULT_PREPROC_PATH = _DEFAULT_PROJECTS / "Methodology-main" / "00_METHODOLOGY" / "PREPROCESSING"
DEFAULT_OUTPUT_DIR = Path("cases/case1-tinytask/output/phase1/")


def _log_action(action: str, **data) -> None:
    """Append a JSONL entry to the menu history file."""
    MENU_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(UTC).isoformat(), "action": action}
    entry.update(data)
    with open(MENU_HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def build_menu() -> list[str]:
    """Build the ordered menu options list.

    Returns:
        List of display strings for ``beaupy.select()``.
    """
    return [
        "1. Load inputs",
        "2. Map domains (LLM) [10 calls]",
        "3. Reduce & resolve",
        "4. Generate outputs",
        "───",
        "5. Run all (1 → 2 → 3 → 4)",
        "6. Run with checkpoint",
        "───",
        "7. View logs",
        "8. View work/ directory",
        "9. Compare with reference",
        "───",
        "q. Quit",
    ]


def _render_header() -> None:
    """Print the boxed header banner."""
    print()
    print("╔══════════════════════════════════════════╗")
    print("║       AEGIS Phase 1 Pipeline v2         ║")
    print("╚══════════════════════════════════════════╝")
    print()


def _resolve_menu_choice(choice: str) -> str:
    """Map a display string to a short action identifier.

    Args:
        choice: The option string selected by the user.

    Returns:
        Short action key used for dispatch.
    """
    if not choice:
        return "quit"
    if "Quit" in choice or choice.lower().startswith("q"):
        return "quit"
    if choice.startswith("1."):
        return "load"
    if choice.startswith("2."):
        return "map"
    if choice.startswith("3."):
        return "reduce"
    if choice.startswith("4."):
        return "output"
    if choice.startswith("5."):
        return "run_all"
    if choice.startswith("6."):
        return "checkpoint"
    if choice.startswith("7."):
        return "logs"
    if choice.startswith("8."):
        return "work"
    if choice.startswith("9."):
        return "compare"
    return "quit"


def run_menu(
    orch: "Phase1Orchestrator | None" = None,
    case_path: str | None = None,
    preprocessing_path: str | None = None,
    output_dir: str | None = None,
) -> None:
    """Main menu loop.

    Displays the interactive menu, dispatches to the appropriate command
    handler, and repeats until the user chooses to quit.

    Args:
        orch: Optional pre-built orchestrator (built if None).
        case_path: Optional case directory path (uses default if None).
        preprocessing_path: Optional preprocessing directory (uses default if None).
        output_dir: Optional output directory (uses default if None).
    """
    import beaupy

    from aegis_phase1.v2.cli.commands import (
        cmd_compare_with_reference,
        cmd_load,
        cmd_map,
        cmd_output,
        cmd_reduce,
        cmd_run_all,
        cmd_run_with_checkpoint,
        cmd_view_logs,
        cmd_view_work,
    )
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    if orch is None:
        orch = Phase1Orchestrator()
    case_path = case_path or str(DEFAULT_CASE_PATH)
    preprocessing_path = preprocessing_path or str(DEFAULT_PREPROC_PATH)
    output_dir = output_dir or str(DEFAULT_OUTPUT_DIR)

    if not sys.stdin.isatty():
        print("Interactive menu requires a TTY. Use --run-all for non-interactive mode.")
        _log_action("menu_skipped_non_tty")
        return

    state = {
        "current_stage": "INIT",
        "case_path": case_path,
        "preprocessing_path": preprocessing_path,
        "output_paths": {},
    }

    _log_action("menu_start")

    while True:
        _render_header()
        options = build_menu()
        try:
            choice = beaupy.select(options=options, return_index=False)
        except (termios.error, OSError, ValueError) as e:
            print(f"Terminal error: {e}. Use --run-all for non-interactive mode.")
            _log_action("menu_terminal_error", error=str(e))
            return

        action = _resolve_menu_choice(choice)
        logger.debug("Menu choice: %s -> %s", choice, action)
        _log_action("menu_select", choice=action)

        if action == "quit":
            print("\nGoodbye.")
            _log_action("menu_exit")
            break

        try:
            if action == "load":
                state = cmd_load(orch, case_path, preprocessing_path)

            elif action == "map":
                state = cmd_map(orch, state)

            elif action == "reduce":
                state = cmd_reduce(orch, state)

            elif action == "output":
                state = cmd_output(orch, state, output_dir)

            elif action == "run_all":
                state = cmd_run_all(orch, case_path, preprocessing_path, output_dir)

            elif action == "checkpoint":
                state = cmd_run_with_checkpoint(
                    orch, case_path, preprocessing_path, output_dir
                )

            elif action == "logs":
                cmd_view_logs()

            elif action == "work":
                cmd_view_work()

            elif action == "compare":
                reference = input("  Reference path [default: ../../../Methodology-main/02_CASES/Case_01_TinyTask_SaaS/output/]: ").strip()
                if not reference:
                    reference = str(
                        _DEFAULT_PROJECTS / "Methodology-main" / "02_CASES" / "Case_01_TinyTask_SaaS" / "output" / ""
                    )
                cmd_compare_with_reference(state, reference)

        except Exception:
            logger.exception("Error executing action=%s", action)
            print(f"\n  ⚠ Error executing '{action}'. See logs for details.")

        print()
        try:
            input("  Press Enter to continue...")
        except (EOFError, KeyboardInterrupt):
            print("\n  (interrupted)")
