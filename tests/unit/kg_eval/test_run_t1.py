"""Tests for `scripts.kg_eval.run_t1` (CORR-113 Commit 3).

Exercises the T1 runner in three modes:
  - WITH-KG: packet is generated and embedded in the prompt.
  - NO-KG: bare case context only.
  - EMPTY-CONTEXT: a case with no architecture YAMLs (covered by the
    "skip asset" code path).

Uses the real case1-tinytask data + the MockInvoker (MOCK_LLM env) so the
tests are deterministic and fast.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.kg_eval.generate_context_packets import generate_packet
from scripts.kg_eval.run_t1 import (
    _build_no_kg_case_context,
    _build_prompt,
    _git_commit_sha,
    invoke_llm,
    load_tasks,
    run_task,
    select_task,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CASE1 = REPO_ROOT / "cases" / "case1-tinytask"
PREPROC = REPO_ROOT / "preproc_out"
TASKS_YAML = REPO_ROOT / "scripts" / "kg_eval" / "tasks.yaml"


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def tasks() -> list[dict]:
    return load_tasks(TASKS_YAML)


@pytest.fixture(autouse=True)
def mock_llm_env(monkeypatch):
    """Force MOCK_LLM=true so the harness uses MockInvoker."""
    monkeypatch.setenv("MOCK_LLM", "true")


@pytest.fixture(scope="module")
def t11_task(tasks: list[dict]) -> dict:
    return select_task(tasks, "T1.1-case1-D-01.1")


@pytest.fixture(scope="module")
def t14_task(tasks: list[dict]) -> dict:
    return select_task(tasks, "T1.4-case1-D-07.1")


# ─── Tasks catalogue ─────────────────────────────────────────────────


def test_load_tasks_returns_15(tasks: list[dict]) -> None:
    """15 tasks = 3 cases x 5 families (1 representative task per family per case)."""
    assert len(tasks) == 15


def test_load_tasks_5_per_family(tasks: list[dict]) -> None:
    """3 cases x 5 families = 15; each family must appear exactly 3 times."""
    from collections import Counter
    counts = Counter(t["family"] for t in tasks)
    for family in ("T1.1", "T1.2", "T1.3", "T1.4", "T1.5"):
        assert counts[family] == 3, f"family {family} appears {counts[family]} times"


def test_select_task_unknown_raises(tasks: list[dict]) -> None:
    """Unknown IDs raise ValueError (fail-loud)."""
    with pytest.raises(ValueError, match="not found"):
        select_task(tasks, "T1.99-not-a-task")


def test_select_task_required_keys(t11_task: dict) -> None:
    """Every task carries the 6 minimum fields the runner + scorer require."""
    for key in ("id", "family", "case", "subdomain_id", "question", "expected_structure"):
        assert key in t11_task, f"missing key {key!r}"


# ─── Prompt construction ─────────────────────────────────────────────


def test_no_kg_prompt_has_no_packet_block(t11_task: dict) -> None:
    """NO-KG prompt has the bare case context, NOT the packet JSON block."""
    case_context = _build_no_kg_case_context(CASE1)
    prompt = _build_prompt(t11_task, case_context, packet=None, with_kg=False)
    assert "CONTEXT PACKET" not in prompt["user"]
    assert "TASK (T1.1)" in prompt["user"]
    assert t11_task["question"].strip() in prompt["user"]


def test_with_kg_prompt_includes_packet(t11_task: dict) -> None:
    """WITH-KG prompt embeds the packet JSON block."""
    case_context = _build_no_kg_case_context(CASE1)
    packet = generate_packet(CASE1, t11_task["subdomain_id"], PREPROC)
    prompt = _build_prompt(t11_task, case_context, packet=packet, with_kg=True)
    assert "CONTEXT PACKET" in prompt["user"]
    # The packet's case_id should appear in the user block
    assert "case1-tinytask" in prompt["user"]


def test_no_kg_case_context_has_required_fields() -> None:
    """The no-KG case context carries name, sector, scale, regs (3-sentence format)."""
    ctx = _build_no_kg_case_context(CASE1)
    assert "company=" in ctx
    assert "sector=" in ctx
    assert "scale=" in ctx
    assert "applicable_regulations=" in ctx


def test_git_commit_sha_returns_string() -> None:
    """`_git_commit_sha` is non-empty and string-typed (used in env.json)."""
    sha = _git_commit_sha()
    assert isinstance(sha, str)
    assert sha  # non-empty


# ─── LLM invocation ─────────────────────────────────────────────────


def test_invoke_llm_returns_mock_response() -> None:
    """invoke_llm delegates to the MockInvoker and returns its dict shape."""
    from aegis_phase1.v2.llm import MockInvoker

    inv = MockInvoker(script=[{"raw": "T1 test response", "status": "OK"}])
    response = invoke_llm(inv, "system", "user")
    assert response["raw"] == "T1 test response"
    assert response["status"] == "OK"


def test_invoke_llm_exhausted_script_returns_default() -> None:
    """When the script is exhausted, the MockInvoker returns a default OK response."""
    from aegis_phase1.v2.llm import MockInvoker

    inv = MockInvoker(script=[{"raw": "first", "status": "OK"}])
    first = invoke_llm(inv, "s", "u")
    second = invoke_llm(inv, "s", "u")  # falls back to default OK
    assert first["raw"] == "first"
    assert second["status"] == "OK"  # default response
    assert second["raw"]  # non-empty default


# ─── Run orchestration (the 3 required scenarios) ───────────────────


def test_run_task_with_kg_writes_artefacts(
    t11_task: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WITH-KG arm: packet.json + packet.sha256 + raw_response.md + env.json present."""
    # Redirect output to tmp so we don't pollute repo output/
    monkeypatch.setattr(
        "scripts.kg_eval.run_t1._PROJECT_ROOT", tmp_path
    )
    env = run_task(
        t11_task, CASE1, PREPROC, with_kg=True,
        script=[{"raw": "## Affected systems\n- SYS-01\n", "status": "OK"}],
        allow_mock=True,
    )
    out_dir = tmp_path / env["output_dir"]
    assert (out_dir / "packet.json").exists()
    assert (out_dir / "packet.sha256").exists()
    assert (out_dir / "raw_response.md").exists()
    assert (out_dir / "env.json").exists()
    # Env record carries the WITH-KG provenance
    assert env["arm"] == "with_kg"
    assert env["packet_sha256"]
    assert env["commit_sha"]
    assert env["status"] == "OK"


def test_run_task_no_kg_skips_packet(
    t11_task: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NO-KG arm: no packet.json / no packet.sha256 (only env + raw_response + prompt)."""
    monkeypatch.setattr(
        "scripts.kg_eval.run_t1._PROJECT_ROOT", tmp_path
    )
    env = run_task(
        t11_task, CASE1, PREPROC, with_kg=False,
        script=[{"raw": "## Affected systems\n- SYS-01\n", "status": "OK"}],
        allow_mock=True,
    )
    out_dir = tmp_path / env["output_dir"]
    assert not (out_dir / "packet.json").exists(), "NO-KG must not write packet"
    assert not (out_dir / "packet.sha256").exists(), "NO-KG must not write packet sha"
    assert (out_dir / "raw_response.md").exists()
    assert (out_dir / "env.json").exists()
    assert env["arm"] == "no_kg"
    assert env["packet_sha256"] is None


def test_run_task_empty_case_context(
    t14_task: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty-context case (no architecture YAMLs) — packet still generates (empty lists)."""
    # Create an empty-case skeleton under tmp
    empty_case = tmp_path / "case-empty"
    (empty_case / "input" / "architecture").mkdir(parents=True)
    (empty_case / "input" / "company").mkdir(parents=True)
    (empty_case / "input" / "regulatory").mkdir(parents=True)
    # Empty applicability.yaml
    (empty_case / "input" / "regulatory" / "applicability.yaml").write_text(
        "applicable_regulations: []\n", encoding="utf-8"
    )
    # Minimal classification.yaml
    (empty_case / "input" / "company" / "classification.yaml").write_text(
        "company:\n  name: ''\n  sector: ''\n  scale: MICRO\n  employees: 0\n",
        encoding="utf-8",
    )
    # No architecture files at all → packet returns empty asset lists
    monkeypatch.setattr(
        "scripts.kg_eval.run_t1._PROJECT_ROOT", tmp_path
    )
    env = run_task(
        t14_task, empty_case, PREPROC, with_kg=True,
        script=[{"raw": "## Proportionality for D-07.1 at tier STANDARD\n", "status": "OK"}],
        allow_mock=True,
    )
    out_dir = tmp_path / env["output_dir"]
    packet = json.loads((out_dir / "packet.json").read_text())
    # Empty lists for every asset category
    for kind in packet["asset_ids"]:
        assert packet["asset_ids"][kind] == []
    # Empty applicability list
    assert packet["regulation_ids"] == []


# ─── Failure handling (OBJ-12 fail-loud) ─────────────────────────────


def test_run_task_captures_failed_status(
    t11_task: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM failure surfaces in env.json as status=FAILED_AFTER_RETRIES."""
    monkeypatch.setattr(
        "scripts.kg_eval.run_t1._PROJECT_ROOT", tmp_path
    )
    env = run_task(
        t11_task, CASE1, PREPROC, with_kg=True,
        script=[{"raw": "", "status": "FAILED_AFTER_RETRIES"}],
        allow_mock=True,
    )
    assert env["status"] == "FAILED_AFTER_RETRIES"
    # OBJ-12: raw_response.md is written even on failure (no silent drop)
    out_dir = tmp_path / env["output_dir"]
    assert (out_dir / "raw_response.md").exists()


# ─── Anti-mock guard (closes the silent-mock gap) ────────────────────


def test_invoker_no_model_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """No model specified → must raise (cannot silently fall back to mock)."""
    from scripts.kg_eval.run_t1 import _invoker_from_env

    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.delenv("KG_EVAL_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="No model specified"):
        _invoker_from_env()


def test_invoker_mock_without_allow_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """MOCK_LLM=true with default allow_mock=False → must raise (no silent mock)."""
    from scripts.kg_eval.run_t1 import _invoker_from_env

    monkeypatch.setenv("MOCK_LLM", "true")
    with pytest.raises(RuntimeError, match="MOCK_LLM=true but allow_mock=False"):
        _invoker_from_env()


def test_invoker_mock_with_allow_returns_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """MOCK_LLM=true + allow_mock=True → MockInvoker (tests deliberately use it)."""
    from scripts.kg_eval.run_t1 import _invoker_from_env

    monkeypatch.setenv("MOCK_LLM", "true")
    inv = _invoker_from_env(allow_mock=True)
    assert type(inv).__name__ == "MockInvoker"


def test_invoke_llm_aborts_on_mock() -> None:
    """invoke_llm(..., abort_on_mock=True) with a MockInvoker raises before the call."""
    from aegis_phase1.v2.llm import MockInvoker

    from scripts.kg_eval.run_t1 import _is_mock, invoke_llm

    inv = MockInvoker()
    assert _is_mock(inv)
    with pytest.raises(RuntimeError, match="MockInvoker but abort_on_mock=True"):
        invoke_llm(inv, "system", "user", abort_on_mock=True)


def test_invoke_llm_allows_mock_when_explicit() -> None:
    """invoke_llm(..., abort_on_mock=False) with a MockInvoker does NOT raise."""
    from aegis_phase1.v2.llm import MockInvoker

    from scripts.kg_eval.run_t1 import invoke_llm

    inv = MockInvoker()
    inv.script = [{"raw": "ok", "status": "OK"}]
    out = invoke_llm(inv, "system", "user", abort_on_mock=False)
    assert out["raw"] == "ok"
