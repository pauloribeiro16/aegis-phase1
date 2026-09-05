"""Unit tests for scripts/kg_eval/score_t2.py — 5 dimensions (CORR-115 T2-EXP-2)."""

from __future__ import annotations

import pytest

from scripts.kg_eval.run_t2 import QueryRecord, T2RunLog
from scripts.kg_eval.score_t2 import (
    _error_recovery_metrics,
    extract_artefacts,
    has_absence_declaration,
    score_t2_run,
)


def _make_run(
    *,
    queries: list[QueryRecord] | None = None,
    final_answer: str = "GDPR Art. 32 mandates PR.DS-01 and DORA-CL14 controls.",
    impossible: bool = False,
    turn_count: int | None = None,
) -> T2RunLog:
    return T2RunLog(
        task_id="T2.1-case1",
        model="qwen3.8:27b",
        provider="ollama",
        case_id="case1-tinytask",
        started_at="2026-09-04T12:00:00Z",
        completed_at="2026-09-04T12:01:00Z",
        turn_count=turn_count if turn_count is not None else (len(queries) if queries else 1),
        queries=queries or [],
        final_answer=final_answer,
        impossible=impossible,
    )


def _ok_query(turn: int, query: str = "MATCH (n) RETURN n") -> QueryRecord:
    return QueryRecord(turn=turn, query=query, success=True, result_count=1)


def _err_query(turn: int, query: str, error: str = "syntax error") -> QueryRecord:
    return QueryRecord(turn=turn, query=query, success=False, result_count=0, error=error)


def test_dim1_pass_when_no_failed_queries() -> None:
    card = score_t2_run(_make_run(queries=[_ok_query(1), _ok_query(2)]), optimal_query_count=2)
    assert card.syntax_validity_pass is True
    assert card.failed_queries == 0


def test_dim1_fail_when_any_query_fails() -> None:
    card = score_t2_run(
        _make_run(
            queries=[
                _ok_query(1),
                _err_query(2, "MATCH (:InventedCompany) RETURN x", "unknown label"),
                _ok_query(3),
            ]
        ),
        optimal_query_count=2,
    )
    assert card.syntax_validity_pass is False
    assert card.failed_queries == 1


def test_dim2_well_at_optimal() -> None:
    card = score_t2_run(_make_run(queries=[_ok_query(1), _ok_query(2)]), optimal_query_count=2)
    assert card.query_efficiency_pass is True
    assert card.query_efficiency_grade == "well"


def test_dim2_borderline_just_under_2x() -> None:
    card = score_t2_run(
        _make_run(queries=[_ok_query(i) for i in range(1, 5)]),
        optimal_query_count=2,
    )
    assert card.query_efficiency_grade == "borderline"
    assert card.query_efficiency_pass is True


def test_dim2_fail_above_borderline_cap() -> None:
    card = score_t2_run(
        _make_run(queries=[_ok_query(i) for i in range(1, 6)]),
        optimal_query_count=2,
    )
    assert card.query_efficiency_pass is False


def test_dim2_tightens_against_old_floor_of_4() -> None:
    card = score_t2_run(
        _make_run(queries=[_ok_query(i) for i in range(1, 4)]),
        optimal_query_count=1,
    )
    assert card.query_efficiency_pass is False


def test_dim3_extracts_csf_clauses_articles() -> None:
    art = extract_artefacts("Per GDPR Art. 32, PR.DS-01 applies; DORA-CL14 is also relevant.")
    assert "PR.DS-01" in art["csf"]
    assert "DORA-CL14" in art["clauses"]
    assert any("GDPR" in a and "32" in a for a in art["articles"])


def test_dim3_pass_when_at_least_one_artefact() -> None:
    card = score_t2_run(
        _make_run(final_answer="Article GDPR Art. 32 mandates PR.DS-01."),
        optimal_query_count=1,
    )
    assert card.grounding_discipline_pass is True


def test_dim3_fail_when_answer_present_but_no_artefacts() -> None:
    card = score_t2_run(
        _make_run(final_answer="Yes, there are some relevant controls."),
        optimal_query_count=1,
    )
    assert card.grounding_discipline_pass is False


def test_dim3_fail_when_answer_empty() -> None:
    card = score_t2_run(_make_run(final_answer=""), optimal_query_count=1)
    assert card.grounding_discipline_pass is False


def test_dim3_relaxed_for_impossible_tasks() -> None:
    card = score_t2_run(
        _make_run(
            final_answer="No mainframe HSM is present in this graph.",
            impossible=True,
        ),
        optimal_query_count=1,
    )
    assert card.grounding_discipline_pass is True


def test_recovery_vacuous_pass_when_no_errors() -> None:
    card = score_t2_run(_make_run(queries=[_ok_query(1), _ok_query(2)]), optimal_query_count=2)
    assert card.error_recovery_pass is True
    assert card.recovery_total_errors == 0


def test_recovery_pass_when_model_adapts_after_error() -> None:
    card = score_t2_run(
        _make_run(
            queries=[
                _err_query(1, "MATCH (:InventedCompany)", "unknown label"),
                _ok_query(2, "MATCH (:Enterprise) RETURN e"),
            ]
        ),
        optimal_query_count=2,
    )
    assert card.error_recovery_pass is True
    assert card.recovery_total_errors == 1
    assert card.recovery_adapted == 1


def test_recovery_fail_when_stuck_on_same_query() -> None:
    card = score_t2_run(
        _make_run(
            queries=[
                _err_query(1, "MATCH (:InventedCompany)", "unknown label"),
                _err_query(2, "MATCH (:InventedCompany)", "unknown label"),
                _ok_query(3, "MATCH (:Enterprise) RETURN e"),
            ]
        ),
        optimal_query_count=2,
    )
    assert card.error_recovery_pass is False
    assert card.recovery_stuck == 1


def test_recovery_low_rate_when_mostly_stuck() -> None:
    card = score_t2_run(
        _make_run(
            queries=[
                _err_query(1, "MATCH (:InventedCompany) RETURN 1", "unknown label"),
                _ok_query(2, "MATCH (:Enterprise) RETURN e"),
                _err_query(3, "MATCH (:OtherBad) RETURN 2", "unknown label"),
                _err_query(4, "MATCH (:OtherBad2) RETURN 3", "unknown label"),
            ]
        ),
        optimal_query_count=2,
    )
    assert card.recovery_total_errors == 3
    assert card.recovery_rate < 0.5
    assert card.error_recovery_pass is False


def test_recovery_metrics_helper_direct() -> None:
    queries = [
        _err_query(1, "Q1", "err"),
        _ok_query(2, "Q2"),
        _err_query(3, "Q3", "err"),
        _err_query(4, "Q3", "err"),
        _ok_query(5, "Q5"),
    ]
    m = _error_recovery_metrics(queries)
    assert m["total_errors"] == 3
    assert m["stuck_retries"] == 1


def test_dim5_pass_with_token() -> None:
    assert has_absence_declaration("No dedicated mainframe cryptographic modules are found") is True
    assert has_absence_declaration("Such an AuthSystem does not exist in the graph") is True


def test_dim5_pass_with_regex_fallback() -> None:
    assert has_absence_declaration("There is no mainframe HSM in this graph") is True
    assert has_absence_declaration("graph has no AuthSystem of mainframe type") is True


def test_dim5_fail_with_no_acknowledgement() -> None:
    assert has_absence_declaration("") is False
    assert has_absence_declaration("The system uses HSM clusters on-premise") is False


def test_happy_full_run_with_one_recovered_error() -> None:
    card = score_t2_run(
        _make_run(
            queries=[
                _err_query(1, "MATCH (:InventedCompany) RETURN c", "unknown label"),
                _ok_query(2, "MATCH (:Enterprise) RETURN e"),
            ],
            final_answer="PR.DS-01 applies via GDPR Art. 32 and DORA-CL14.",
        ),
        optimal_query_count=2,
    )
    assert card.syntax_validity_pass is False
    assert card.query_efficiency_pass is True
    assert card.grounding_discipline_pass is True
    assert card.error_recovery_pass is True
    assert card.overall_usability_pass is False


def test_dim5_requires_useful_negative() -> None:
    log = _make_run(
        final_answer="No mainframe cryptographic module in this graph.",
        impossible=True,
    )
    card = score_t2_run(log, optimal_query_count=1)
    assert card.absence_declared_pass is False
    assert any("useful-negative" in n.lower() for n in card.notes)


def test_dim5_passes_when_useful_negative_present() -> None:
    log = _make_run(
        final_answer="No mainframe crypto; case1 is MICRO SaaS so DORA does not bind.",
        impossible=True,
    )
    card = score_t2_run(log, optimal_query_count=1)
    assert card.absence_declared_pass is True


def test_impossible_task_full_integration() -> None:
    log = _make_run(
        queries=[_ok_query(1, "MATCH (s:AuthSystem) RETURN s")],
        final_answer=(
            "No mainframe cryptographic module in this graph; the case does not contain one "
            "(case1-tinytask is a MICRO SaaS enterprise running on AWS and Firebase)."
        ),
        impossible=True,
    )
    card = score_t2_run(log, optimal_query_count=1)
    assert card.absence_declared_pass is True
    assert card.overall_usability_pass is True


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("No mainframe HSM here.", True),
        ("Such AuthSystem is absent.", True),
        ("Not present in this graph.", True),
        ("AuthSystem of mainframe type is not found in this case.", True),
        ("The system has many controls.", False),
        ("", False),
    ],
)
def test_absence_parametrized(answer: str, expected: bool) -> None:
    assert has_absence_declaration(answer) is expected


def test_dim2_zero_queries_is_fail() -> None:
    """A run that never queried the graph is a NO-OP, not 'well'/'optimal'.

    The scorer must mark query_efficiency_pass=False, leave the grade empty,
    and append an explanatory note so the matrix treats this distinctly from
    a 2-query optimal run.
    """
    card = score_t2_run(_make_run(queries=[]), optimal_query_count=2)
    assert card.total_queries == 0
    assert card.query_efficiency_pass is False
    assert card.query_efficiency_grade == ""
    assert any("No queries attempted" in n for n in card.notes)


# --- CORR-115 T2-EXP-2: broader artefact + useful-negative regexes ---


def test_extract_artefacts_includes_so_sr_subdomain() -> None:
    art = extract_artefacts("Per SO-D-09.1.GDPR and SR-AI_Act-014, D-09.1 needs STANDARD tier.")
    assert "SO-D-09.1.GDPR" in art["sos"]
    assert "SR-AI_Act-014" in art["srs"]
    assert "D-09.1" in art["subdomains"]
    assert "STANDARD" in art["tiers"]


def test_extract_artefacts_includes_systems_and_ds() -> None:
    art = extract_artefacts("System SYS-CBS hosts data for DS-case3-001 that is GDPR-CL01.")
    assert "SYS-CBS" in art["systems"]
    assert "DS-case3-001" in art["data_subjects"]
    assert "GDPR-CL01" in art["clauses"]


def test_useful_negative_relaxed_for_scale_words() -> None:
    log = _make_run(
        final_answer="No mainframe crypto here; the company is too small for DORA to apply.",
        impossible=True,
    )
    card = score_t2_run(log, optimal_query_count=1)
    assert card.absence_declared_pass is True


def test_useful_negative_relaxed_for_does_not_apply() -> None:
    log = _make_run(
        final_answer="There is no such AuthSystem. DORA does not apply because the company is below threshold.",
        impossible=True,
    )
    card = score_t2_run(log, optimal_query_count=1)
    assert card.absence_declared_pass is True
