"""CORR-118 — agent loop entry points.

The actual loop lives in :mod:`aegis_phase1.v2.agents.graph` (LangGraph
Evaluator-Optimizer, per ~/.zcode/skills/langgraph/references/patterns.md
§4). This module keeps the public surface stable:

  build_doc05_facts(state) — compact facts the drafter/reviewer consume
  run_doc05_agent_loop(state, llm=..., max_cycles=N) — returns a dict
    with ``sections``, ``sidecar_lines``, ``gate_history``, ``review_history``
    so the renderer can write Doc 05 + the sidecar without knowing the
    graph internals.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from aegis_phase1.v2.agents.hydration import hydrate_rationale_by_reg

logger = logging.getLogger(__name__)


@dataclass
class Doc05AgentResult:
    """Stable view of the agent loop outcome for the renderer."""

    sections: dict[str, str]
    sidecar_lines: list[str]
    attempts: int
    gate_results: list[dict[str, Any]] = field(default_factory=list)
    review_results: list[dict[str, Any]] = field(default_factory=list)

    @property
    def converged(self) -> bool:
        if not self.review_results:
            return False
        last = self.review_results[-1]
        verdict = getattr(last, "loop_verdict", None)
        if verdict is None and isinstance(last, dict):
            verdict = last.get("loop_verdict")
        return verdict == "PASS"


def build_doc05_facts(state: dict[str, Any]) -> dict[str, Any]:
    """Compact facts payload the Drafter and Reviewer consume."""
    hydrate_rationale_by_reg(state)
    return {
        "applicable_regs": list(state.get("v2_applicable_regs") or state.get("regulations") or []),
        "company_profile": _company_profile(state),
        "subdomain_catalogue": _subdomain_catalogue(state),
        "clause_map": _clause_map(state),
        "synthesis": _synthesis(state),
    }


def run_doc05_agent_loop(
    state: dict[str, Any],
    *,
    llm: Any,
    max_cycles: int = 3,
) -> Doc05AgentResult:
    """Run the LangGraph agent loop; returns a renderer-friendly result."""
    from aegis_phase1.v2.agents.graph import run_doc05_agent_loop as _graph_run

    final_state = _graph_run(state, llm=llm, max_cycles=max_cycles)
    return _to_result(final_state, max_cycles=max_cycles)


def _to_result(final_state: dict[str, Any], *, max_cycles: int) -> Doc05AgentResult:
    """Wrap LangGraph state into the renderer-friendly Doc05AgentResult.

    review_history entries are dicts (``{loop_verdict, objectives, raw}``)
    coming straight from the graph; for the renderer we also expose a
    small :class:`ReviewVerdict`-compatible namespace so the existing
    doc_05 wiring can read ``review_results[-1].loop_verdict``.
    """
    from types import SimpleNamespace

    review_results: list[Any] = []
    for entry in final_state.get("review_history") or []:
        if isinstance(entry, dict):
            review_results.append(
                SimpleNamespace(
                    loop_verdict=entry.get("loop_verdict") or "",
                    objectives=entry.get("objectives") or {},
                    raw=entry.get("raw") or "",
                )
            )
        else:
            review_results.append(entry)
    return Doc05AgentResult(
        sections=dict(final_state.get("sections") or {}),
        sidecar_lines=list(final_state.get("sidecar_lines") or []),
        attempts=int(final_state.get("cycle_count") or 0),
        gate_results=list(final_state.get("gate_history") or []),
        review_results=review_results,
    )


# ── Facts builders (kept from the F1 module) ────────────────────────────


def _company_profile(state: dict[str, Any]) -> str:
    inventory = state.get("architecture_inventory") or {}
    role_matrix = state.get("role_matrix") or {}
    company_facts = state.get("company_facts") or state.get("company_profile") or {}
    payload = {
        "company_facts": company_facts,
        "architecture_inventory": inventory,
        "role_matrix": role_matrix,
    }
    return json.dumps(payload, indent=1, ensure_ascii=False, default=str)


def _subdomain_catalogue(state: dict[str, Any]) -> str:
    """Compact sub-domain catalogue. Tolerates both dicts (test fixtures)
    and Pydantic ``Subdomain`` objects (real orchestrator state)."""
    rows: list[dict[str, Any]] = []
    for sub in state.get("v2_subdomains") or []:
        sd_id = _get_field(sub, "id", default="")
        regs = _get_field(sub, "participating_regulations", default=[]) or []
        if not sd_id:
            continue
        rows.append({"id": str(sd_id), "regs": list(regs)})
    return json.dumps(rows, ensure_ascii=False)


def _get_field(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from either a dict or a Pydantic model without raising."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _clause_map(state: dict[str, Any]) -> str:
    mapping = state.get("ontology", {}).get("clause_mappings") or []
    rows: list[dict[str, Any]] = []
    for entry in mapping:
        if isinstance(entry, dict):
            rows.append(
                {
                    "article": entry.get("article") or entry.get("id"),
                    "regulation": entry.get("regulation"),
                    "sub_domains": entry.get("sub_domains") or entry.get("subdomains"),
                }
            )
    return json.dumps(rows, ensure_ascii=False, default=str)


def _synthesis(state: dict[str, Any]) -> dict[str, Any]:
    return hydrate_rationale_by_reg(state)
