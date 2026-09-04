"""scripts/kg_eval/run_t2.py — T2 Navigation Agent Runner for Model Usability Evaluation.

Executes a multi-turn conversation loop where the LLM is given a schema card and can
issue Cypher queries via ```cypher ... ``` code blocks.
Captures queries, execution results, error recovery, and final answers.

References:
    - docs/KG_EVAL_PROTOCOL.md §8
    - scripts/kg_eval/engine.py
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.kg_eval.engine import (
    CypherSyntaxError,
    build_graph_for_case,
    execute_cypher,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AEGIS-KG Phase 1 regulatory reasoning agent with access to a Neo4j Knowledge Graph.
To inspect the graph, output a Cypher query inside a ```cypher ... ``` code block.
You will receive the query results (or error message) in the next turn.
When you have gathered sufficient evidence, provide your final answer.

Ontology Summary:
- Nodes: (:Enterprise {case_id, name, scale}), (:System {id, name, criticality}), (:DataStore {id, storage_type, contains_pii}), (:SubDomain {id, name, macro_id}), (:Regulation {id}), (:RegulatoryClause {id, regulation_id, article_reference}), (:CSFSubcategory {id, outcome_text}), (:RegulatoryInteraction {id, interaction_type, severity, resolution_principle, sub_domains}).
- Relationships:
  (:Enterprise)-[:OPERATES_SYSTEM]->(:System|:DataStore)
  (:System)-[:IN_SCOPE_OF]->(:SubDomain)
  (:RegulatoryClause)-[:MAPPED_TO_SUBDOMAIN]->(:SubDomain)
  (:RegulatoryClause)-[:ANCHORED_TO_CSF]->(:CSFSubcategory)
  (:RegulatoryInteraction)-[:SCOPED_TO_SUBDOMAIN]->(:SubDomain)
  (:Enterprise)-[:HAS_REGULATORY_INTERACTION]->(:RegulatoryInteraction)

Rule: Only MATCH queries are allowed. If information is absent from the graph, explicitly declare absence.
"""


@dataclass
class QueryRecord:
    turn: int
    query: str
    success: bool
    result_count: int
    error: str | None = None


@dataclass
class T2RunLog:
    task_id: str
    model: str
    provider: str
    case_id: str
    started_at: str
    completed_at: str
    turn_count: int
    queries: list[QueryRecord]
    final_answer: str
    impossible: bool


def extract_cypher_block(text: str) -> str | None:
    """Extract Cypher query from ```cypher ... ``` block."""
    match = re.search(r"```(?:cypher)?\s*(MATCH[\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def run_t2_agent(
    task: dict[str, Any],
    case_path: Path,
    preproc_root: Path,
    invoker_fn: Any,
    max_turns: int = 6,
) -> T2RunLog:
    """Run interactive navigation loop with the model against the case graph."""
    graph = build_graph_for_case(case_path, preproc_root)
    task_id = task["id"]
    case_id = task.get("case", case_path.name)
    question = task["question"]
    impossible = task.get("impossible", False)

    history: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Task: {question}"},
    ]

    queries_log: list[QueryRecord] = []
    started_at = datetime.now(UTC).isoformat()
    final_answer = ""

    for turn in range(1, max_turns + 1):
        # Format prompt for the model
        prompt_text = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
        response_text = invoker_fn(prompt_text)

        cypher_query = extract_cypher_block(response_text)
        if not cypher_query:
            # Model decided to give final answer without more queries
            final_answer = response_text
            break

        # Execute query against in-memory graph
        try:
            results = execute_cypher(graph, cypher_query)
            record = QueryRecord(
                turn=turn,
                query=cypher_query,
                success=True,
                result_count=len(results),
            )
            feedback = f"Query Result ({len(results)} rows):\n" + json.dumps(results[:10], indent=2)
            if len(results) > 10:
                feedback += f"\n... ({len(results) - 10} more rows truncated)"
        except CypherSyntaxError as exc:
            record = QueryRecord(
                turn=turn,
                query=cypher_query,
                success=False,
                result_count=0,
                error=str(exc),
            )
            feedback = f"Cypher Execution Error: {exc}"
        except Exception as exc:
            record = QueryRecord(
                turn=turn,
                query=cypher_query,
                success=False,
                result_count=0,
                error=str(exc),
            )
            feedback = f"Unexpected Error: {exc}"

        queries_log.append(record)
        history.append({"role": "assistant", "content": response_text})
        history.append({"role": "user", "content": f"TOOL RESULT:\n{feedback}"})

    completed_at = datetime.now(UTC).isoformat()

    return T2RunLog(
        task_id=task_id,
        model=getattr(invoker_fn, "model_name", "unknown"),
        provider=getattr(invoker_fn, "provider_name", "ollama"),
        case_id=case_id,
        started_at=started_at,
        completed_at=completed_at,
        turn_count=len(queries_log),
        queries=queries_log,
        final_answer=final_answer,
        impossible=impossible,
    )


def mock_t2_invoker(prompt: str) -> str:
    """Mock invoker simulating an agent querying and answering."""
    if "TOOL RESULT" not in prompt:
        return "Let me check the graph.\n```cypher\nMATCH (s:System {id: 'SYS-01'})-[:IN_SCOPE_OF]->(sd:SubDomain)<-[:MAPPED_TO_SUBDOMAIN]-(c:RegulatoryClause) RETURN s, sd, c\n```"
    return "Based on the graph query, system SYS-01 is bound by GDPR clauses anchored to NIST CSF 2.0 PR.DS-01."


__all__ = [
    "QueryRecord",
    "T2RunLog",
    "extract_cypher_block",
    "mock_t2_invoker",
    "run_t2_agent",
]
