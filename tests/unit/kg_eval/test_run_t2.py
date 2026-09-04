"""Unit tests for scripts/kg_eval/run_t2.py."""

from pathlib import Path

from scripts.kg_eval.run_t2 import (
    extract_cypher_block,
    mock_t2_invoker,
    run_t2_agent,
)


def test_extract_cypher_block():
    text = "Here is my query:\n```cypher\nMATCH (s:System) RETURN s\n```\nDone."
    assert extract_cypher_block(text) == "MATCH (s:System) RETURN s"

    no_block = "I cannot find any matches."
    assert extract_cypher_block(no_block) is None


def test_run_t2_agent_with_mock():
    repo_root = Path(__file__).resolve().parents[3]
    case_path = repo_root / "cases" / "case1-tinytask"
    preproc_root = repo_root / "preproc_out"

    task = {
        "id": "T2.1-test",
        "case": "case1-tinytask",
        "question": "Investigate SYS-01",
        "impossible": False,
    }

    log = run_t2_agent(task, case_path, preproc_root, mock_t2_invoker, max_turns=3)
    assert log.task_id == "T2.1-test"
    assert log.turn_count >= 1
    assert len(log.queries) >= 1
    assert log.queries[0].success is True
    assert "PR.DS-01" in log.final_answer
