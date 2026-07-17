"""Test the beaupy-driven sequential wizard in src/aegis_phase1/v2/cli/menu.py.

Contract: AEGIS-P1-CORR-007.
"""
import warnings
from unittest.mock import MagicMock, patch

import pytest


def _make_orch():
    """Build a minimal mock orchestrator."""
    orch = MagicMock()
    orch.case_path = "/tmp/case"
    orch.regulatory_baseline_path = "/tmp/baseline"
    orch.load = MagicMock(return_value={"current_stage": "LOADED"})
    orch.run_all = MagicMock(return_value={"04_body": "/out/04.md"})
    orch.llm_invoker = None
    return orch


def _run_wizard_with_beaupy(orch, *, case=None, mode=None, model=None, confirm=None):
    """Invoke ``run_wizard`` with patched beaupy responses.

    Each argument is a string (the beaupy option label to return).
    Multiple beaupy.select calls are answered from this list in order;
    only the ones the wizard actually invokes are consumed.
    """
    responses = [r for r in [case, mode, model, confirm] if r is not None]
    iter_responses = iter(responses)

    def select_side_effect(*args, **kwargs):
        return next(iter_responses)

    with patch("beaupy.select", side_effect=select_side_effect) as mock_select, \
         patch("beaupy.prompt", return_value="") as mock_prompt, \
         patch.object(__import__("sys").stdin, "isatty", return_value=True):
        from aegis_phase1.v2.cli.menu import run_wizard
        result = run_wizard(orch)
        for c in mock_select.call_args_list:
            assert "pre_selected" not in c.kwargs
            assert c.kwargs["cursor_index"] == 0
        return result, (mock_select, mock_prompt)


def test_wizard_runs_full_pipeline_with_defaults():
    """All default selections → pipeline runs."""
    orch = _make_orch()
    paths, (mock_select, mock_prompt) = _run_wizard_with_beaupy(
        orch,
        case="Case 01 - TinyTask SaaS (GDPR, CRA)",
        mode="Mock (no Ollama, fast, deterministic)",
        confirm="Run pipeline",
    )
    # 3 beaupy.select calls: case (Mock skips model), mode, confirm
    assert mock_select.call_count == 3
    mock_select.assert_called_with(options=["Run pipeline", "Cancel"], cursor_index=0)
    orch.load.assert_called_once()
    orch.run_all.assert_called_once()


def test_wizard_real_mode_prompts_model():
    """Real mode prompts model selection (4 select calls)."""
    orch = _make_orch()
    paths, (mock_select, _) = _run_wizard_with_beaupy(
        orch,
        case="Case 01 - TinyTask SaaS (GDPR, CRA)",
        mode="Real (Ollama + gemma4:e2b)",
        model="gemma4:e2b",
        confirm="Run pipeline",
    )
    # 4 beaupy.select calls: case, mode, model, confirm
    assert mock_select.call_count == 4
    mock_select.assert_called_with(options=["Run pipeline", "Cancel"], cursor_index=0)
    assert any(c.kwargs.get("cursor_index") == 0 for c in mock_select.call_args_list)
    orch.run_all.assert_called_once()


def test_wizard_user_cancels_returns_empty():
    """User picks 'Cancel' at confirm → no run."""
    orch = _make_orch()
    paths, _ = _run_wizard_with_beaupy(
        orch,
        case="Case 01 - TinyTask SaaS (GDPR, CRA)",
        mode="Mock (no Ollama, fast, deterministic)",
        confirm="Cancel",
    )
    orch.run_all.assert_not_called()
    orch.load.assert_not_called()  # load only happens if user confirms
    assert paths == {}


def test_wizard_returns_paths_on_success():
    """Successful run returns the paths dict from orchestrator.run_all."""
    orch = _make_orch()
    orch.run_all = MagicMock(return_value={"04_body": "/out/04.md", "xlsx": "/x.xlsx"})
    paths, (mock_select, _) = _run_wizard_with_beaupy(
        orch,
        case="Case 01 - TinyTask SaaS (GDPR, CRA)",
        mode="Mock (no Ollama, fast, deterministic)",
        confirm="Run pipeline",
    )
    mock_select.assert_called_with(options=["Run pipeline", "Cancel"], cursor_index=0)
    assert paths == {"04_body": "/out/04.md", "xlsx": "/x.xlsx"}


def test_wizard_handles_load_exception():
    """If orch.load() raises, wizard returns empty (no run)."""
    orch = _make_orch()
    orch.load = MagicMock(side_effect=RuntimeError("case not found"))
    paths, (mock_select, _) = _run_wizard_with_beaupy(
        orch,
        case="Case 01 - TinyTask SaaS (GDPR, CRA)",
        mode="Mock (no Ollama, fast, deterministic)",
        confirm="Run pipeline",
    )
    mock_select.assert_called_with(options=["Run pipeline", "Cancel"], cursor_index=0)
    orch.run_all.assert_not_called()
    assert paths == {}


def test_wizard_non_tty_returns_empty():
    """Non-TTY stdin → wizard prints message and returns empty."""
    orch = _make_orch()
    with patch.object(__import__("sys").stdin, "isatty", return_value=False):
        from aegis_phase1.v2.cli.menu import run_wizard
        paths = run_wizard(orch)
    orch.load.assert_not_called()
    orch.run_all.assert_not_called()
    assert paths == {}


def test_wizard_uses_mock_llm_env_in_mock_mode():
    """Mock mode sets MOCK_LLM=true env var."""
    orch = _make_orch()
    import os
    # Clean any pre-existing
    os.environ.pop("MOCK_LLM", None)

    _run_wizard_with_beaupy(
        orch,
        case="Case 01 - TinyTask SaaS (GDPR, CRA)",
        mode="Mock (no Ollama, fast, deterministic)",
        confirm="Run pipeline",
    )

    assert os.environ.get("MOCK_LLM") == "true"


def test_wizard_custom_path_via_beaupy_prompt():
    """Selecting 'Custom path...' prompts user via beaupy.prompt."""
    orch = _make_orch()
    iter_responses = iter(["Custom path...",
                           "Mock (no Ollama, fast, deterministic)",
                           "Run pipeline"])

    def select_side_effect(*args, **kwargs):
        return next(iter_responses)

    with patch("beaupy.select", side_effect=select_side_effect) as mock_select, \
         patch("beaupy.prompt", return_value="/tmp/custom_case") as mock_prompt, \
         patch.object(__import__("sys").stdin, "isatty", return_value=True), \
         patch("pathlib.Path.exists", return_value=True):
        from aegis_phase1.v2.cli.menu import run_wizard
        run_wizard(orch)

    mock_select.assert_called_with(options=["Run pipeline", "Cancel"], cursor_index=0)
    for c in mock_select.call_args_list:
        assert "pre_selected" not in c.kwargs
        assert c.kwargs["cursor_index"] == 0
    mock_prompt.assert_called()
    # Custom path should be used
    call_args = orch.load.call_args
    assert "/tmp/custom_case" in str(call_args)


def test_run_menu_alias_emits_deprecation_warning():
    """Backwards-compat: run_menu() emits DeprecationWarning + delegates."""
    orch = _make_orch()
    iter_responses = iter(["Case 01 - TinyTask SaaS (GDPR, CRA)",
                           "Mock (no Ollama, fast, deterministic)",
                           "Cancel"])

    def select_side_effect(*args, **kwargs):
        return next(iter_responses)

    with patch("beaupy.select", side_effect=select_side_effect) as mock_select, \
         patch.object(__import__("sys").stdin, "isatty", return_value=True):
        from aegis_phase1.v2.cli.menu import run_menu

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            run_menu(orch)

        deprecation_warnings = [
            w for w in caught if issubclass(w.category, DeprecationWarning)
        ]
        assert any("run_menu" in str(w.message) for w in deprecation_warnings)

    mock_select.assert_called_with(options=["Run pipeline", "Cancel"], cursor_index=0)
    for c in mock_select.call_args_list:
        assert "pre_selected" not in c.kwargs
        assert c.kwargs["cursor_index"] == 0


def test_discover_cases_returns_three_cases():
    """_discover_cases() returns the 3 Methodology-main cases."""
    from aegis_phase1.v2.cli.menu import _discover_cases
    cases = _discover_cases()
    assert len(cases) == 3
    names = [c["name"] for c in cases]
    assert "Case_01_TinyTask_SaaS" in names
    assert "Case_02_SecureBorder_Solutions" in names
    assert "Case_03_OmniBank_Financial" in names


def test_discover_cases_includes_correct_regulations():
    """Each case entry has the right regulation list."""
    from aegis_phase1.v2.cli.menu import _discover_cases
    cases = {c["name"]: c for c in _discover_cases()}
    assert cases["Case_01_TinyTask_SaaS"]["regulations"] == ["GDPR", "CRA"]
    assert cases["Case_02_SecureBorder_Solutions"]["regulations"] == [
        "GDPR", "CRA", "NIS2", "AI_Act"
    ]
    assert cases["Case_03_OmniBank_Financial"]["regulations"] == [
        "GDPR", "CRA", "NIS2", "DORA", "AI_Act"
    ]


def test_wizard_handles_map_partial_failure():
    """If orch.run_all raises MapPartialFailure, wizard catches it."""
    orch = _make_orch()
    from aegis_phase1.v2.domain.processor import MapPartialFailure

    orch.run_all = MagicMock(side_effect=MapPartialFailure("test failure"))

    paths, (mock_select, _) = _run_wizard_with_beaupy(
        orch,
        case="Case 01 - TinyTask SaaS (GDPR, CRA)",
        mode="Mock (no Ollama, fast, deterministic)",
        confirm="Run pipeline",
    )
    mock_select.assert_called_with(options=["Run pipeline", "Cancel"], cursor_index=0)
    assert paths == {}


def test_run_pipeline_passes_args_to_orchestrator_run_all():
    """_run_pipeline forwards case_path/regulatory_baseline_path/output_dir to run_all.

    Regression for CORR-008 Phase F: previously called orch.run_all() without
    forwarding the args _run_pipeline already received, raising TypeError when
    the wizard reached the Confirm step in a real TTY.
    """
    from aegis_phase1.v2.cli.menu import _run_pipeline
    from unittest.mock import MagicMock

    orch = MagicMock()
    orch.load = MagicMock(return_value={"current_stage": "LOADED"})
    orch.run_all = MagicMock(return_value={"04_body": "/out/04.md"})

    paths = _run_pipeline(
        orch,
        case_path="/tmp/fake_case",
        regulatory_baseline_path="/tmp/fake_baseline",
        mode="mock",
        model="gemma4:e4b",
        output_dir="/tmp/fake_out",
    )

    assert orch.run_all.call_count == 1
    kw = orch.run_all.call_args.kwargs
    assert kw.get("case_path") == "/tmp/fake_case"
    assert kw.get("regulatory_baseline_path") == "/tmp/fake_baseline"
    assert kw.get("output_dir") == "/tmp/fake_out"
    assert paths == {"04_body": "/out/04.md"}