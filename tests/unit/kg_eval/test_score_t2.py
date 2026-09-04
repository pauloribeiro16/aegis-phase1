"""Unit tests for scripts/kg_eval/score_t2.py."""

from scripts.kg_eval.run_t2 import QueryRecord, T2RunLog
from scripts.kg_eval.score_t2 import score_t2_run


def test_score_t2_run_passing():
    log = T2RunLog(
        task_id="T2.1-case1",
        model="qwen3.8:27b",
        provider="ollama",
        case_id="case1-tinytask",
        started_at="2026-09-04T12:00:00Z",
        completed_at="2026-09-04T12:01:00Z",
        turn_count=2,
        queries=[
            QueryRecord(turn=1, query="MATCH (s:System) RETURN s", success=True, result_count=1),
            QueryRecord(
                turn=2, query="MATCH (sd:SubDomain) RETURN sd", success=True, result_count=1
            ),
        ],
        final_answer="System SYS-01 maps to PR.DS-01.",
        impossible=False,
    )

    card = score_t2_run(log, optimal_query_count=2)
    assert card.overall_usability_pass is True
    assert card.syntax_validity_pass is True
    assert card.query_efficiency_pass is True
    assert card.grounding_discipline_pass is True


def test_score_t2_run_impossible_task():
    log_fail = T2RunLog(
        task_id="T2.3-impossible",
        model="qwen3.8:27b",
        provider="ollama",
        case_id="case1-tinytask",
        started_at="2026-09-04T12:00:00Z",
        completed_at="2026-09-04T12:01:00Z",
        turn_count=1,
        queries=[
            QueryRecord(turn=1, query="MATCH (s:System) RETURN s", success=True, result_count=0),
        ],
        final_answer="The system operates an HSM cluster on premise.",
        impossible=True,
    )
    card_fail = score_t2_run(log_fail, optimal_query_count=1)
    assert card_fail.absence_declared_pass is False
    assert card_fail.overall_usability_pass is False

    log_pass = T2RunLog(
        task_id="T2.3-impossible",
        model="qwen3.8:27b",
        provider="ollama",
        case_id="case1-tinytask",
        started_at="2026-09-04T12:00:00Z",
        completed_at="2026-09-04T12:01:00Z",
        turn_count=1,
        queries=[
            QueryRecord(turn=1, query="MATCH (s:System) RETURN s", success=True, result_count=0),
        ],
        final_answer="No dedicated mainframe cryptographic modules are found; they are absent from the graph.",
        impossible=True,
    )
    card_pass = score_t2_run(log_pass, optimal_query_count=1)
    assert card_pass.absence_declared_pass is True
    assert card_pass.overall_usability_pass is True
