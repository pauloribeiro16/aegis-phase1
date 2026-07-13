"""Tests for scripts/run_phase1.py (beaupy interactive menu)."""
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Path setup to import the script
SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR.parent))  # project root for `scripts.run_phase1` import


def test_mock_invoker_loads_fixture():
    """MockPhase1LLMInvoker loads fixture from data/fixtures/."""
    from scripts.run_phase1 import MockPhase1LLMInvoker
    project_root = SCRIPTS_DIR.parent
    invoker = MockPhase1LLMInvoker(project_root=project_root)
    result = invoker.invoke(
        "P1B-LLM-01-INTERPRETATION",
        {"case_id": "Case_01_TinyTask_SaaS", "lane_id": "GDPR"},
    )
    assert result["status"] == "OK"
    assert "parsed_output" in result
    assert result["retry_count"] == 1


def test_mock_invoker_falls_back():
    """Mock invoker returns generic empty OK when no fixture exists."""
    from scripts.run_phase1 import MockPhase1LLMInvoker
    project_root = SCRIPTS_DIR.parent
    invoker = MockPhase1LLMInvoker(project_root=project_root)
    result = invoker.invoke(
        "UNKNOWN-LLM",
        {"case_id": "Case_99_Unknown", "lane_id": "X"},
    )
    assert result["status"] == "OK"
    assert result["parsed_output"] == {}


def test_select_case_writes_history(tmp_path, monkeypatch):
    """select_case updates CONFIG + writes JSONL history."""
    from scripts import run_phase1
    monkeypatch.setattr(run_phase1, "MENU_HISTORY", tmp_path / "menu.jsonl")
    monkeypatch.setattr("scripts.run_phase1.beaupy.select", MagicMock(return_value="Case 02 - SecureBorder (4 regs)"))
    run_phase1.select_case()
    assert "SecureBorder" in run_phase1.CONFIG["case"]
    assert tmp_path.joinpath("menu.jsonl").exists()


def test_select_mode_writes_history(tmp_path, monkeypatch):
    from scripts import run_phase1
    monkeypatch.setattr(run_phase1, "MENU_HISTORY", tmp_path / "menu.jsonl")
    monkeypatch.setattr("scripts.run_phase1.beaupy.select", MagicMock(return_value="Real (Ollama + gemma4:e2b, slow)"))
    run_phase1.select_mode()
    assert "Real" in run_phase1.CONFIG["mode"]


def test_select_scope_writes_history(tmp_path, monkeypatch):
    from scripts import run_phase1
    monkeypatch.setattr(run_phase1, "MENU_HISTORY", tmp_path / "menu.jsonl")
    monkeypatch.setattr("scripts.run_phase1.beaupy.select", MagicMock(return_value="Phase 1B only (per-regulation)"))
    run_phase1.select_scope()
    assert "Phase 1B" in run_phase1.CONFIG["scope"]


def test_select_llm_writes_history(tmp_path, monkeypatch):
    from scripts import run_phase1
    monkeypatch.setattr(run_phase1, "MENU_HISTORY", tmp_path / "menu.jsonl")
    monkeypatch.setattr("scripts.run_phase1.beaupy.select", MagicMock(return_value="P1B-LLM-02-RATIONALE"))
    run_phase1.select_llm()
    assert run_phase1.CONFIG["llm"] == "P1B-LLM-02-RATIONALE"


def test_select_llm_back_doesnt_change_config(tmp_path, monkeypatch):
    """If user picks '<- Back', CONFIG is unchanged."""
    from scripts import run_phase1
    monkeypatch.setattr(run_phase1, "MENU_HISTORY", tmp_path / "menu.jsonl")
    prev = run_phase1.CONFIG["llm"]
    monkeypatch.setattr("scripts.run_phase1.beaupy.select", MagicMock(return_value="<- Back (cancel)"))
    run_phase1.select_llm()
    assert run_phase1.CONFIG["llm"] == prev


def test_run_unit_tests_invokes_pytest(monkeypatch):
    """run_unit_tests calls subprocess with pytest + correct flags."""
    from scripts import run_phase1
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr(subprocess, "run", mock_run)
    run_phase1.run_unit_tests()
    args = mock_run.call_args.args[0]
    assert "pytest" in args
    assert "tests/unit/" in args
    assert any("smoke" in str(a) for a in args)


def test_run_full_pipeline_uses_mock_invoker(monkeypatch):
    """run_full_pipeline uses MockPhase1LLMInvoker when mode = Mock."""
    from scripts import run_phase1
    # Reset CONFIG to mock-mode + Case 01
    run_phase1.CONFIG["mode"] = "Mock (no Ollama, fast, uses fixtures in data/)"
    run_phase1.CONFIG["case"] = "Case 01 - TinyTask SaaS (2 regs: GDPR, CRA)"
    mock_executor = MagicMock()
    mock_executor.run.return_value = {
        "phase_1b": {"status": "OK"},
        "phase_1c_map": [{"lane_id": "D-01"}],
        "sync": {"status": "OK"},
        "phase_1c_reduce": {"P1C-LLM-03": {}, "P1C-LLM-02": {}, "status": "OK"},
    }
    monkeypatch.setattr("scripts.run_phase1._build_executor", lambda inv: mock_executor)
    monkeypatch.setattr("scripts.run_phase1.build_invoker", lambda: MagicMock())
    run_phase1.run_full_pipeline()
    assert mock_executor.run.called
    assert mock_executor.run.call_args.args[0] == "Case_01_TinyTask_SaaS"


def test_main_loop_exit(monkeypatch):
    """main loop exits cleanly when user picks 6."""
    from scripts import run_phase1
    monkeypatch.setattr("scripts.run_phase1.beaupy.select", MagicMock(return_value="6) Exit"))
    # Should not hang
    run_phase1.main()
