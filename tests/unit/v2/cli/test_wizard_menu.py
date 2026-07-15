"""Test the sequential wizard in src/aegis_phase1/v2/cli/menu.py.

Contract: AEGIS-P1-CORR-006 Phase B.
"""
import io
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest


def _make_orch():
    """Build a minimal mock orchestrator that won't actually run anything."""
    orch = MagicMock()
    orch.case_path = "/tmp/case"
    orch.regulatory_baseline_path = "/tmp/baseline"
    orch.load = MagicMock(return_value={"current_stage": "LOADED"})
    orch.run_all = MagicMock(return_value={"04_body": "/tmp/out/04_body.md"})
    orch.set_skip_phase_1b = MagicMock()
    orch.set_skip_reduce_llms = MagicMock()
    orch.llm_invoker = None  # default mock mode path
    return orch


def _run_wizard_with_input(orch, user_inputs: str):
    """Helper: feed ``user_inputs`` to stdin and invoke ``run_wizard``."""
    sys.stdin = io.StringIO(user_inputs)
    try:
        sys.stdin.isatty = lambda: True  # simulate TTY
        from aegis_phase1.v2.cli.menu import run_wizard

        return run_wizard(orch)
    finally:
        sys.stdin = sys.__stdin__


def test_wizard_accepts_all_defaults_and_runs():
    """All 6 prompts with Enter (default values) → pipeline runs."""
    orch = _make_orch()
    # 6 prompts: 1, 2, 3, 4 (only shown if Real — but Mock skips),
    # 5, 6. Mock mode means 5 prompts total.
    # For Mock: prompts 1, 2, 3, 5, 6 (5 prompts).
    # For Real: prompts 1, 2, 3, 4, 5, 6 (6 prompts).
    # Let's test Mock: 5 inputs.
    user_input = "\n\n\n\nY\n"  # 1=default, 2=default, 3=default(mock), 5=N, 6=Y

    paths = _run_wizard_with_input(orch, user_input)
    # Pipeline should have run
    orch.load.assert_called_once()
    orch.run_all.assert_called_once()


def test_wizard_aborts_on_n_at_run_prompt():
    """User says N at step 6 → no run, returns empty."""
    orch = _make_orch()
    user_input = "\n\n\n\nN\n"  # 1, 2, 3, 5, 6=N

    paths = _run_wizard_with_input(orch, user_input)
    # Pipeline should NOT have run
    orch.run_all.assert_not_called()
    orch.load.assert_not_called()  # load only happens if [Y]
    assert paths == {}


def test_wizard_real_mode_prompts_model():
    """When user picks Real (2), wizard prompts for model."""
    orch = _make_orch()
    # 6 prompts: 1=case, 2=baseline, 3=mode(2=Real), 4=model, 5=skip, 6=run
    user_input = "\n\n2\ncustom-model:7b\nN\nN\n"

    _run_wizard_with_input(orch, user_input)
    orch.run_all.assert_not_called()  # aborted at 6


def test_wizard_skips_model_prompt_in_mock():
    """In Mock mode (default), wizard does NOT prompt for model."""
    orch = _make_orch()
    # 5 inputs for Mock: case, baseline, mode, skip, run
    user_input = "\n\n\nN\nN\n"

    paths = _run_wizard_with_input(orch, user_input)
    orch.run_all.assert_not_called()
    assert paths == {}


def test_wizard_skips_phase_1b_flag():
    """User overrides skip flags: skip-phase-1b=Y."""
    orch = _make_orch()
    # Mock mode: 1=case, 2=baseline, 3=mode, 4=skip_override=Y, 5=skip_1b=Y, 6=skip_reduce=N, 7=run=Y
    user_input = "\n\n\nY\nY\nN\nY\n"

    paths = _run_wizard_with_input(orch, user_input)
    orch.run_all.assert_called_once()
    orch.set_skip_phase_1b.assert_called_once_with(True)
    orch.set_skip_reduce_llms.assert_not_called()


def test_wizard_skips_reduce_llms_flag():
    """User overrides skip flags: skip-reduce-llms=Y."""
    orch = _make_orch()
    # Mock: 1=case, 2=baseline, 3=mode, 4=skip_override=Y, 5=skip_1b=N, 6=skip_reduce=Y, 7=run=Y
    user_input = "\n\n\nY\nN\nY\nY\n"

    paths = _run_wizard_with_input(orch, user_input)
    orch.run_all.assert_called_once()
    orch.set_skip_reduce_llms.assert_called_once_with(True)


def test_wizard_mode_choice_accepts_numeric():
    """User enters '2' to pick Real mode."""
    orch = _make_orch()
    # Real: 1=case, 2=baseline, 3=mode(2), 4=model, 5=skip, 6=run=N
    user_input = "\n\n2\n\nN\nN\n"

    paths = _run_wizard_with_input(orch, user_input)
    orch.run_all.assert_not_called()
    assert paths == {}


def test_wizard_mode_choice_accepts_keyword():
    """User enters 'real' (key string) to pick Real mode."""
    orch = _make_orch()
    user_input = "\n\nreal\n\nN\nN\n"

    paths = _run_wizard_with_input(orch, user_input)
    orch.run_all.assert_not_called()
    assert paths == {}


def test_wizard_returns_paths_on_success():
    """On successful run, wizard returns the paths dict from run_all."""
    orch = _make_orch()
    orch.run_all = MagicMock(return_value={"04_body": "/out/04.md", "xlsx": "/out/x.xlsx"})
    user_input = "\n\n\n\nY\n"

    paths = _run_wizard_with_input(orch, user_input)
    assert paths == {"04_body": "/out/04.md", "xlsx": "/out/x.xlsx"}


def test_wizard_handles_load_exception():
    """If orch.load() raises, wizard returns empty (no run)."""
    orch = _make_orch()
    orch.load = MagicMock(side_effect=RuntimeError("case not found"))
    user_input = "\n\n\n\nY\n"

    paths = _run_wizard_with_input(orch, user_input)
    orch.run_all.assert_not_called()
    assert paths == {}


def test_run_menu_alias_emits_deprecation_warning():
    """Backwards-compat: run_menu() emits DeprecationWarning + delegates."""
    orch = _make_orch()
    import warnings

    sys.stdin = io.StringIO("\n\n\n\nN\n")  # abort
    try:
        sys.stdin.isatty = lambda: True
        from aegis_phase1.v2.cli.menu import run_menu

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            run_menu(orch)

        deprecation_warnings = [
            w for w in caught if issubclass(w.category, DeprecationWarning)
        ]
        assert any("run_menu" in str(w.message) for w in deprecation_warnings)
        assert any("CORR-006" in str(w.message) for w in deprecation_warnings)
    finally:
        sys.stdin = sys.__stdin__