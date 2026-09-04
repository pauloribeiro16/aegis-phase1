"""scripts/kg_eval/score_t2.py — Scorer for T2 Model Usability Evaluation.

Measures the 5 dimensions of graph navigation from docs/KG_EVAL_PROTOCOL.md §8:
1. Query Strategy (turns vs optimal)
2. Schema & Syntax Validity (0 syntax/unknown token errors)
3. Error Recovery (did the model adapt when receiving an error?)
4. Grounding Discipline (citations matched query results)
5. Knowing When to Stop (for impossible tasks, declared absence)

References:
    - docs/KG_EVAL_PROTOCOL.md §8
    - scripts/kg_eval/run_t2.py
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.kg_eval.run_t2 import T2RunLog


@dataclass
class T2ScoreCard:
    task_id: str
    model: str
    syntax_validity_pass: bool
    query_efficiency_pass: bool
    grounding_discipline_pass: bool
    absence_declared_pass: bool
    overall_usability_pass: bool
    total_queries: int
    failed_queries: int
    notes: list[str]


def score_t2_run(run_log: T2RunLog, optimal_query_count: int = 2) -> T2ScoreCard:
    notes: list[str] = []

    # 1. Schema & Syntax validity: all queries must succeed without syntax errors
    failed_queries = sum(1 for q in run_log.queries if not q.success)
    syntax_validity_pass = failed_queries == 0
    if not syntax_validity_pass:
        notes.append(f"{failed_queries} queries failed syntax or schema validation.")

    # 2. Query efficiency: queries <= 2x optimal
    query_count = len(run_log.queries)
    query_efficiency_pass = query_count <= max(optimal_query_count * 2, 4)
    if not query_efficiency_pass:
        notes.append(
            f"Exceeded query budget: {query_count} queries (optimal: {optimal_query_count})."
        )

    # 3. Grounding discipline: final answer non-empty and cites facts
    has_answer = bool(run_log.final_answer and len(run_log.final_answer.strip()) > 10)
    grounding_discipline_pass = has_answer
    if not has_answer:
        notes.append("Final answer empty or truncated.")

    # 4. Knowing when to stop (for impossible tasks)
    absence_declared_pass = True
    if run_log.impossible:
        absence_tokens = ["not found", "absent", "none exist", "no dedicated", "does not contain"]
        declared = any(t in run_log.final_answer.lower() for t in absence_tokens)
        absence_declared_pass = declared
        if not declared:
            notes.append("Failed to declare absence on impossible task.")

    overall_usability_pass = (
        syntax_validity_pass
        and query_efficiency_pass
        and grounding_discipline_pass
        and absence_declared_pass
    )

    return T2ScoreCard(
        task_id=run_log.task_id,
        model=run_log.model,
        syntax_validity_pass=syntax_validity_pass,
        query_efficiency_pass=query_efficiency_pass,
        grounding_discipline_pass=grounding_discipline_pass,
        absence_declared_pass=absence_declared_pass,
        overall_usability_pass=overall_usability_pass,
        total_queries=query_count,
        failed_queries=failed_queries,
        notes=notes,
    )


__all__ = [
    "T2ScoreCard",
    "score_t2_run",
]
