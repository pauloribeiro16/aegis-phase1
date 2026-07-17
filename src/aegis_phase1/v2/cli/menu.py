"""menu — Sequential interactive wizard using beaupy.

Replaces the legacy hub-and-spoke menu (CORR-006) and the input()-based
wizard (CORR-006 first iteration) with a clean beaupy.select()-driven
flow (CORR-007).

Flow (4 steps):
    1/4 Select case        (beaupy.select — auto-scanned from Methodology-main)
    2/4 Mode                (beaupy.select — Mock / Real)
    3/4 Model               (beaupy.select — only if Mode=Real)
    4/4 Confirm             (beaupy.select — Run / Cancel)

Regulatory Baseline path is auto-detected from the case's parent
(Methodology-main/00_METHODOLOGY/PREPROCESSING) so the user is not
asked about it.

If stdin is not a TTY (piped input, CI), the wizard prints a message
suggesting --run-all for non-interactive mode and returns {}.

References:
    - contracts/SPRINT001_v2-core.md (C-005)
    - AEGIS-P1-CORR-007 (beaupy wizard)
"""

from __future__ import annotations

import aegis_phase1.env  # noqa: F401 — load .env via env.py module-import side-effect
import json
import logging
import sys
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
DEFAULT_MODEL = "gemma4:e2b"
MODEL_CHOICES = ["gemma4:e2b", "gemma4:e4b", "Custom..."]


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
    print("║         Sequential Wizard              ║")
    print("╚══════════════════════════════════════════╝")
    print()


def _discover_cases() -> list[dict]:
    """Return the static catalogue of known cases.

    Mirrors the CASES table in ``scripts/run_phase1.py`` (v1 wizard).
    Update both tables together when a new case is published.

    Returns:
        List of dicts: {name, label, path, regulations, source}.
        Only entries whose ``path`` exists on disk are returned.
    """
    methodology_root = _DEFAULT_PROJECTS / "Methodology-main" / "02_CASES"

    static_cases: list[dict] = [
        {
            "name": "Case_01_TinyTask_SaaS",
            "label": "Case 01 - TinyTask SaaS (GDPR, CRA)",
            "path": str(methodology_root / "Case_01_TinyTask_SaaS"),
            "regulations": ["GDPR", "CRA"],
            "source": "Methodology-main",
        },
        {
            "name": "Case_02_SecureBorder_Solutions",
            "label": "Case 02 - SecureBorder (GDPR, CRA, NIS2, AI Act)",
            "path": str(methodology_root / "Case_02_SecureBorder_Solutions"),
            "regulations": ["GDPR", "CRA", "NIS2", "AI_Act"],
            "source": "Methodology-main",
        },
        {
            "name": "Case_03_OmniBank_Financial",
            "label": "Case 03 - OmniBank (GDPR, CRA, NIS2, DORA, AI Act)",
            "path": str(methodology_root / "Case_03_OmniBank_Financial"),
            "regulations": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"],
            "source": "Methodology-main",
        },
    ]

    # Filter to only those whose path actually exists on disk
    return [c for c in static_cases if Path(c["path"]).exists()]


def _render_step_header(step: int, total: int, title: str) -> None:
    """Print the step header."""
    print()
    print(f"[{step}/{total}] {title}")


def _step_select_case() -> tuple[str, str]:
    """Step 1: Select case. Returns (case_path, label)."""
    import beaupy

    cases = _discover_cases()
    if not cases:
        # Fallback: default Case_01 if scan failed
        print("  (No cases discovered; using default Case_01_TinyTask_SaaS)")
        return DEFAULT_CASE_PATH, "Case_01_TinyTask_SaaS (default)"

    options = [c["label"] for c in cases] + ["Custom path..."]
    selected = beaupy.select(options=options, cursor_index=0)
    if selected is None or selected == "Custom path...":
        custom = beaupy.prompt("Path to case directory:")
        if custom and Path(custom).exists():
            return custom, f"{Path(custom).name} (custom)"
        print(f"  (Path not found: {custom}; using default)")
        return DEFAULT_CASE_PATH, "Case_01_TinyTask_SaaS (default fallback)"

    for c in cases:
        if c["label"] == selected:
            return c["path"], c["label"]
    return DEFAULT_CASE_PATH, "Case_01_TinyTask_SaaS (default fallback)"


def _step_select_mode() -> str:
    """Step 2: Select mode. Returns 'mock' or 'real'."""
    import beaupy

    options = [
        "Mock (no Ollama, fast, deterministic)",
        "Real (Ollama + gemma4:e2b)",
    ]
    selected = beaupy.select(options=options, cursor_index=0)
    return "real" if selected and "Real" in selected else "mock"


def _step_select_model() -> str:
    """Step 3: Select model. Returns model name. Only called in Real mode."""
    import beaupy

    selected = beaupy.select(MODEL_CHOICES, cursor_index=0)
    if selected is None or selected == DEFAULT_MODEL:
        return DEFAULT_MODEL
    if selected == "Custom...":
        custom = beaupy.prompt(f"Custom model name [{DEFAULT_MODEL}]:")
        return custom if custom else DEFAULT_MODEL
    return selected


def _step_confirm() -> bool:
    """Step 4: Confirm run. Returns True if user picked 'Run pipeline'."""
    import beaupy

    options = ["Run pipeline", "Cancel"]
    selected = beaupy.select(options=options, cursor_index=0)
    return selected is not None and selected == "Run pipeline"


def _autodetect_regulatory_baseline(case_path: str) -> str:
    """Find Methodology-main/00_METHODOLOGY/PREPROCESSING relative to case_path.

    Walks up from case_path looking for a sibling Methodology-main/ directory.
    Falls back to DEFAULT_REGULATORY_BASELINE_PATH if not found.
    """
    path = Path(case_path).resolve()
    for ancestor in [path, *path.parents]:
        candidate = ancestor.parent / "Methodology-main" / "00_METHODOLOGY" / "PREPROCESSING"
        if candidate.exists():
            return str(candidate)
    return DEFAULT_REGULATORY_BASELINE_PATH


def _run_pipeline(
    orch: object,
    case_path: str,
    regulatory_baseline_path: str,
    mode: str,
    model: str,
    output_dir: str,
) -> dict:
    """Execute the pipeline using the wizard's collected configuration."""
    from aegis_phase1.v2.domain.processor import MapPartialFailure

    print()
    print("─" * 50)
    print("Running pipeline with:")
    print(f"  case_path          : {case_path}")
    print(f"  regulatory_baseline: {regulatory_baseline_path}")
    print(f"  mode               : {mode}")
    if mode == "real":
        print(f"  model              : {model}")
    print(f"  output_dir         : {output_dir}")
    print("─" * 50)
    print()

    try:
        paths = orch.run_all(
            case_path=case_path,
            regulatory_baseline_path=regulatory_baseline_path,
            output_dir=output_dir,
        )
    except MapPartialFailure as exc:
        logger.error("MAP partial failure: %s", exc)
        print(f"  ⚠ MAP partial failure: {exc}")
        paths = {}

    print()
    print("─" * 50)
    print("✓ Pipeline complete")
    if paths:
        for label, p in paths.items():
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
    """4-step sequential wizard using beaupy.select for all prompts.

    Replaces the input()-based wizard (CORR-006 first iteration) with
    arrow-key navigation via beaupy. One question at a time, Enter to
    accept pre-selected default at every step.

    Returns:
        Paths dict from ``orchestrator.run_all()`` (empty if user
        cancelled, no TTY, or run failed).
    """
    if not sys.stdin.isatty():
        print(
            "Interactive wizard requires a TTY. Use --run-all for "
            "non-interactive mode, or supply CLI flags directly."
        )
        _log_action("wizard_skipped_non_tty")
        return {}

    _render_header()
    print("Use ↑/↓ arrows + Enter. Ctrl+C to abort.")
    _log_action("wizard_start")

    # Step 1: Case
    _render_step_header(1, 4, "Select case")
    chosen_case_path, case_label = _step_select_case()
    _log_action("wizard_case", case_path=chosen_case_path, label=case_label)

    # Step 2: Mode
    _render_step_header(2, 4, "Select mode")
    mode = _step_select_mode()
    _log_action("wizard_mode", mode=mode)

    # Step 3: Model (only if Real)
    model = DEFAULT_MODEL
    if mode == "real":
        _render_step_header(3, 4, "Select model")
        model = _step_select_model()
        _log_action("wizard_model", model=model)

    # Step 4: Confirm
    confirm_step = 4 if mode == "real" else 3
    total = 4 if mode == "real" else 3
    _render_step_header(confirm_step, total, "Confirm")
    if not _step_confirm():
        print()
        print("Aborted by user. No pipeline run.")
        _log_action("wizard_aborted")
        return {}

    # Apply configuration
    final_baseline = (
        regulatory_baseline_path
        or _autodetect_regulatory_baseline(chosen_case_path)
    )
    final_output = output_dir or DEFAULT_OUTPUT_DIR

    try:
        orch.load(chosen_case_path, regulatory_baseline_path=final_baseline)
    except Exception as exc:
        logger.exception("LOAD failed")
        print(f"  ⚠ LOAD failed: {exc}")
        _log_action("wizard_load_failed", error=str(exc))
        return {}

    if mode == "mock":
        import os
        os.environ["MOCK_LLM"] = "true"
        if hasattr(orch, "llm_invoker") and orch.llm_invoker is None:
            from aegis_phase1.v2.llm import build_llm_invoker
            orch.llm_invoker = build_llm_invoker(model=model)
    else:
        if hasattr(orch, "llm_invoker") and orch.llm_invoker is not None:
            if hasattr(orch.llm_invoker, "model"):
                orch.llm_invoker.model = model

    _log_action(
        "wizard_run",
        case_path=chosen_case_path,
        regulatory_baseline_path=final_baseline,
        mode=mode,
        model=model,
        output_dir=final_output,
    )

    return _run_pipeline(orch, chosen_case_path, final_baseline, mode, model, final_output)


# ─────────────────────────────────────────────────────────────────────
# Backwards-compatibility alias (deprecated since CORR-007)
# ─────────────────────────────────────────────────────────────────────


def run_menu(
    orch: object,
    case_path: str | None = None,
    regulatory_baseline_path: str | None = None,
    output_dir: str | None = None,
) -> None:
    """DEPRECATED alias for ``run_wizard``.

    Kept for backwards compatibility. Logs a DeprecationWarning and
    delegates to ``run_wizard``.
    """
    import warnings

    warnings.warn(
        "run_menu() is deprecated; use run_wizard() instead. (CORR-006/007)",
        DeprecationWarning,
        stacklevel=2,
    )
    run_wizard(orch, case_path, regulatory_baseline_path, output_dir)