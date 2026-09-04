"""scripts/kg_eval/score_t2.py — Scorer for T2 Model Usability Evaluation.

Measures the 5 dimensions of graph navigation from docs/KG_EVAL_PROTOCOL.md §8:

1. Schema & Syntax Validity (0 syntax/unknown-token errors)
2. Query Strategy / Efficiency (count vs optimal + sub-grades WELL/BORDERLINE)
3. Grounding Discipline (final answer must cite ≥1 closed-set artefact)
4. Error Recovery (when a query errors, does the model adapt the next query?)
5. Knowing When to Stop (for impossible tasks, declare absence explicitly)

The dataclass mirrors the JSON shape produced by the T2 sbatch so adding
fields is a backward-compatible change (the sbatch writes .__dict__).

References:
    - docs/KG_EVAL_PROTOCOL.md §8
    - scripts/kg_eval/run_t2.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from scripts.kg_eval.run_t2 import QueryRecord, T2RunLog

_RE_CSF = re.compile(r"\b[A-Z]{2}\.[A-Z]{2}-\d{2}[a-z]?\b")

_RE_CLAUSE = re.compile(r"\b((?:GDPR|CRA|NIS2|DORA|AI_Act|NIS_2)-(?:CL|RT|TR|CP)\d{2,3})\b")

_RE_ARTICLE = re.compile(
    r"\b((?:GDPR|CRA|NIS2|DORA|AI_Act) Art\.\s*\d+(?:\([0-9a-z]+\))*)",
    re.IGNORECASE,
)


def extract_artefacts(text: str) -> dict[str, list[str]]:
    """Extract closed-set artefacts cited by the model."""
    if not text:
        return {"csf": [], "clauses": [], "articles": []}
    return {
        "csf": sorted(set(_RE_CSF.findall(text))),
        "clauses": sorted(set(_RE_CLAUSE.findall(text))),
        "articles": sorted(set(_RE_ARTICLE.findall(text))),
    }


_ABSENCE_TOKENS = (
    "not found in",
    "does not exist",
    "no record",
    "absent from",
    "no dedicated",
    "no mainframe",
    "no such",
    "not in graph",
    "not present in",
    "graph has no",
    "case does not contain",
    "is absent",
    "are absent",
    "none exist",
    "does not contain",
)


def has_absence_declaration(text: str) -> bool:
    """True iff the text acknowledges the absence of the requested concept."""
    if not text:
        return False
    lower = text.lower()
    if any(tok in lower for tok in _ABSENCE_TOKENS):
        return True
    return bool(
        re.search(r"\bno [a-z ]{2,40} in (the )?graph\b", lower)
        or re.search(r"\bgraph has no [a-z ]{2,40}\b", lower)
    )


def _error_recovery_metrics(queries: list[QueryRecord]) -> dict[str, Any]:
    """Compute Error Recovery dim 4 metrics.

    Two failure modes, counted independently:
    - stuck_retries: same failing query text appears more than once.
    - adapted_errors: errored query followed (later) by a successful query
      with different text.
    """
    errored_queries = [q for q in queries if not q.success and q.error]
    total_errors = len(errored_queries)

    text_counts: dict[str, int] = {}
    for q in errored_queries:
        text_counts[q.query] = text_counts.get(q.query, 0) + 1
    stuck = sum(c - 1 for c in text_counts.values() if c > 1)

    adapted = sum(
        1
        for q in errored_queries
        if any(nq.success and nq.query != q.query for nq in queries[queries.index(q) + 1 :])
    )

    rate = (adapted / total_errors) if total_errors else 0.0
    return {
        "total_errors": total_errors,
        "adapted_errors": adapted,
        "stuck_retries": stuck,
        "recovery_rate": rate,
    }


@dataclass
class T2ScoreCard:
    task_id: str
    model: str
    syntax_validity_pass: bool
    query_efficiency_pass: bool
    grounding_discipline_pass: bool
    error_recovery_pass: bool
    absence_declared_pass: bool
    overall_usability_pass: bool
    total_queries: int
    failed_queries: int
    query_efficiency_grade: str
    artefacts_cited: dict[str, list[str]] = field(default_factory=dict)
    recovery_total_errors: int = 0
    recovery_adapted: int = 0
    recovery_stuck: int = 0
    recovery_rate: float = 0.0
    notes: list[str] = field(default_factory=list)


def score_t2_run(run_log: T2RunLog, optimal_query_count: int = 2) -> T2ScoreCard:
    """Score a T2 run log against the 5 usability dimensions."""
    notes: list[str] = []
    queries = list(run_log.queries)
    query_count = len(queries)
    failed_queries = sum(1 for q in queries if not q.success)

    syntax_validity_pass = failed_queries == 0
    if not syntax_validity_pass:
        notes.append(f"{failed_queries} query/ies with syntax or schema error.")

    budget_well = optimal_query_count
    budget_borderline = min(2 * optimal_query_count, optimal_query_count + 3)
    if query_count == 0:
        # Zero queries is a NO-OP, not "optimal": cannot judge efficiency on
        # a run that did not actually attempt to navigate the graph.
        efficiency_grade = ""
        query_efficiency_pass = False
        notes.append("No queries attempted; cannot judge efficiency.")
    elif query_count <= budget_well:
        efficiency_grade = "well"
        query_efficiency_pass = True
    elif query_count <= budget_borderline:
        efficiency_grade = "borderline"
        query_efficiency_pass = True
    else:
        efficiency_grade = ""
        query_efficiency_pass = False
        notes.append(
            f"Exceeded query budget: {query_count} queries "
            f"(optimal: {optimal_query_count}, borderline cap: {budget_borderline})."
        )

    final_answer = run_log.final_answer or ""
    has_answer = bool(final_answer.strip()) and len(final_answer.strip()) > 10
    artefacts = extract_artefacts(final_answer)
    artefact_count = sum(len(v) for v in artefacts.values())
    if run_log.impossible:
        grounding_discipline_pass = has_answer
        if not has_answer:
            notes.append("Final answer empty on impossible task.")
    else:
        grounding_discipline_pass = has_answer and artefact_count >= 1
        if not has_answer:
            notes.append("Final answer empty or truncated.")
        elif artefact_count < 1:
            notes.append(
                "Final answer present but cites no closed-set artefacts "
                "(NIST CSF ID, clause ID, or article reference)."
            )

    recovery = _error_recovery_metrics(queries)
    if recovery["total_errors"] == 0:
        error_recovery_pass = True
    else:
        if recovery["stuck_retries"] >= 1:
            error_recovery_pass = False
            notes.append(f"Stuck on retry: {recovery['stuck_retries']} duplicate failing query.")
        elif recovery["recovery_rate"] < 0.5:
            error_recovery_pass = False
            notes.append(
                f"Low recovery rate: {recovery['recovery_rate']:.0%} "
                f"(adapted {recovery['adapted_errors']} of {recovery['total_errors']})."
            )
        else:
            error_recovery_pass = True

    absence_declared_pass = True
    if run_log.impossible:
        declared = has_absence_declaration(final_answer)
        absence_declared_pass = declared
        if not declared:
            notes.append("Failed to declare absence on impossible task.")

    overall_usability_pass = (
        syntax_validity_pass
        and query_efficiency_pass
        and grounding_discipline_pass
        and error_recovery_pass
        and absence_declared_pass
    )

    return T2ScoreCard(
        task_id=run_log.task_id,
        model=run_log.model,
        syntax_validity_pass=syntax_validity_pass,
        query_efficiency_pass=query_efficiency_pass,
        grounding_discipline_pass=grounding_discipline_pass,
        error_recovery_pass=error_recovery_pass,
        absence_declared_pass=absence_declared_pass,
        overall_usability_pass=overall_usability_pass,
        total_queries=query_count,
        failed_queries=failed_queries,
        query_efficiency_grade=efficiency_grade,
        artefacts_cited=artefacts,
        recovery_total_errors=recovery["total_errors"],
        recovery_adapted=recovery["adapted_errors"],
        recovery_stuck=recovery["stuck_retries"],
        recovery_rate=recovery["recovery_rate"],
        notes=notes,
    )


__all__ = [
    "T2ScoreCard",
    "extract_artefacts",
    "has_absence_declaration",
    "score_t2_run",
]
