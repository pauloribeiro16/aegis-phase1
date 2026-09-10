"""CORR-118 — LangGraph Evaluator-Optimizer loop for Doc 05.

Implements ~/.zcode/skills/langgraph/references/patterns.md §4:

  START → draft → gate ──fail──→ draft (gate feedback)
                       │pass
                       ▼
                     review ──REVISE──→ draft (reviewer feedback)
                       │PASS
                       ▼
                      END

Each node is a thin Python wrapper around a side-effect:
  draft    — invokes the LCEL drafter chain, updates sections + sidecar_lines
  gate     — DeterministicGate.check; routes back to draft on failure
  review   — LCEL reviewer chain + verdict parser; routes to draft or END
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from aegis_phase1.v2.agents.chains import build_drafter_chain, build_reviewer_chain
from aegis_phase1.v2.agents.gate import DeterministicGate
from aegis_phase1.v2.agents.reviewer import _LOOP_RE, _VERDICT_RE
from aegis_phase1.v2.agents.state import Doc05AgentState

logger = logging.getLogger(__name__)


# ── Section splitter (pure function) ─────────────────────────────────────


_MARKERS = [
    "## 3. PER-REGULATION APPLICABILITY",
    "## 4. NATIVE VS INHERITED COMPLIANCE",
    "## 5. SUB-DOMAIN COVERAGE PRELIMINARY",
    "## 6. STRATEGIC IMPLICATIONS",
    "## 7. REGULATORY GAPS IDENTIFIED",
]


def split_sections(raw: str) -> dict[str, str]:
    """Split a raw drafter response into the 5 Doc-05 sections (s3..s7)."""
    positions: list[tuple[int, str]] = [(m, h) for h in _MARKERS for m in (raw.find(h),) if m >= 0]
    positions.sort()
    if not positions:
        return {"s3": raw}
    keys = ["s3", "s4", "s5", "s6", "s7"]
    sections: dict[str, str] = {}
    for i, (idx, _marker) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(raw)
        sections[keys[i]] = raw[idx:end].strip()
    return sections


def parse_reviewer_verdict(raw: str) -> tuple[str, dict[str, str]]:
    """Return (loop_verdict, objectives_dict) from reviewer raw text."""
    objectives = {m.group(1): m.group(2) for m in _VERDICT_RE.finditer(raw)}
    loop_match = _LOOP_RE.search(raw)
    if loop_match:
        loop = loop_match.group(1)
    elif objectives and all(v != "FAIL" for v in objectives.values()):
        loop = "PASS"
    elif objectives:
        loop = "REVISE"
    else:
        loop = "UNPARSEABLE"
    return loop, objectives


# ── Node factories ──────────────────────────────────────────────────────


def make_draft_node(drafter_chain: Any):
    def draft_node(state: Doc05AgentState) -> dict[str, Any]:
        cycle = int(state.get("cycle_count", 0)) + 1
        max_cycles = int(state.get("max_cycles") or 3)
        if cycle > max_cycles:
            logger.warning("doc05 cycle budget exhausted (%d)", max_cycles)
            raise _BudgetExhausted(
                f"doc05 agent loop exhausted max_cycles={max_cycles}"
            )
        facts = state.get("facts") or {}
        synth = facts.get("synthesis") or {}
        gaps = synth.get("gaps") if isinstance(synth, dict) else None
        logger.warning(
            "doc05 DEBUG cycle %d: facts.applicable_regs=%s synthesis.gaps=%s derived=%s",
            cycle,
            facts.get("applicable_regs"),
            len(gaps) if isinstance(gaps, list) else gaps,
            synth.get("_derived_from_coverage_matrix") if isinstance(synth, dict) else None,
        )
        response = drafter_chain.invoke(dict(state))
        sections = split_sections(response)
        sidecar = list(state.get("sidecar_lines") or [])
        sidecar.append(f"\n## cycle {cycle} — drafter prompt + response\n")
        sidecar.append("```\n" + response[:6000] + "\n```\n")
        logger.info("doc05 cycle %d drafted %d section(s)", cycle, len(sections))
        return {
            "cycle_count": cycle,
            "last_response": response,
            "sections": sections,
            "sidecar_lines": sidecar,
        }

    return draft_node


class _BudgetExhausted(Exception):
    """Internal sentinel raised by draft when ``cycle_count > max_cycles``.

    Caught in build_doc05_graph; the loop finalises with the best
    sections already produced (gate_history and review_history are
    preserved in the state at the moment of the raise).
    """


def make_route_after_draft(state: Doc05AgentState) -> Literal["gate", END.__class__, "__end__"]:  # type: ignore[name-defined]
    if state.get("_budget_exhausted"):
        return END
    return "gate"


def make_gate_node(gate: DeterministicGate):
    def gate_node(state: Doc05AgentState) -> dict[str, Any]:
        expect = bool((state.get("facts") or {}).get("synthesis"))
        result = gate.check(state.get("sections") or {}, expect_gaps=expect)
        history = list(state.get("gate_history") or [])
        history.append({"passed": result.passed, "failures": list(result.failures)})
        feedback = "" if result.passed else result.feedback()
        logger.info(
            "doc05 cycle %d gate %s (%d failure(s))",
            state.get("cycle_count", 0),
            "PASS" if result.passed else "FAIL",
            len(result.failures),
        )
        return {
            "gate_passed": result.passed,
            "gate_failures": list(result.failures),
            "gate_history": history,
            "feedback": feedback,
        }

    return gate_node


def make_review_node(reviewer_chain: Any):
    def review_node(state: Doc05AgentState) -> dict[str, Any]:
        raw = reviewer_chain.invoke(dict(state))
        loop, objectives = parse_reviewer_verdict(raw)
        history = list(state.get("review_history") or [])
        history.append({"loop_verdict": loop, "objectives": dict(objectives), "raw": raw})
        sidecar = list(state.get("sidecar_lines") or [])
        sidecar.append(f"\n## cycle {state.get('cycle_count', 0)} — reviewer prompt + response\n")
        sidecar.append("```\n" + raw[:6000] + "\n```\n")
        feedback = "" if loop == "PASS" else raw
        logger.info("doc05 cycle %d review %s", state.get("cycle_count", 0), loop)
        return {
            "review_loop_verdict": loop,
            "review_objectives": objectives,
            "review_history": history,
            "sidecar_lines": sidecar,
            "feedback": feedback,
            "converged": loop == "PASS",
        }

    return review_node


def make_route_after_gate(state: Doc05AgentState) -> Literal["review", "draft"]:
    return "review" if state.get("gate_passed") else "draft"


def make_route_after_review(state: Doc05AgentState) -> Literal[END.__class__, "__end__", "draft"]:  # type: ignore[name-defined]
    verdict = state.get("review_loop_verdict")
    if verdict in ("PASS", "BUDGET_EXHAUSTED", "UNPARSEABLE"):
        return END
    return "draft"


# ── Graph builder + runner ─────────────────────────────────────────────


def build_doc05_graph(llm: Any, *, max_cycles: int = 3):
    """Compile the agent StateGraph with InMemorySaver (per skill template)."""
    drafter_chain = build_drafter_chain(llm)
    reviewer_chain = build_reviewer_chain(llm)
    gate = DeterministicGate()

    workflow = StateGraph(Doc05AgentState)
    workflow.add_node("draft", make_draft_node(drafter_chain))
    workflow.add_node("gate", make_gate_node(gate))
    workflow.add_node("review", make_review_node(reviewer_chain))
    workflow.add_edge(START, "draft")
    workflow.add_edge("draft", "gate")
    workflow.add_conditional_edges("gate", make_route_after_gate, {"review": "review", "draft": "draft"})
    workflow.add_conditional_edges(
        "review",
        make_route_after_review,
        {"draft": "draft", END: END},
    )

    return workflow.compile(
        checkpointer=InMemorySaver(),
        # recursion_limit caps total node visits; the budget sentinel in
        # ``draft`` raises ``_BudgetExhausted`` once cycle_count > max_cycles
        # so the ceiling is generous and the test for unbounded loops is
        # covered by the exception, not by the limit.
    )


def run_doc05_agent_loop(
    state: dict[str, Any],
    *,
    llm: Any,
    max_cycles: int = 3,
) -> dict[str, Any]:
    """Run the LangGraph agent loop on a v2 pipeline state.

    Returns the final state dict. The renderer reads ``sections``,
    ``sidecar_lines``, ``gate_history`` and ``review_history`` from it.
    """
    from aegis_phase1.v2.agents.loop import build_doc05_facts

    facts = build_doc05_facts(state)
    graph = build_doc05_graph(llm, max_cycles=max_cycles)
    initial: Doc05AgentState = {
        "facts": facts,
        "cycle_count": 0,
        "max_cycles": max_cycles,
        "feedback": "",
        "sections": {},
        "gate_passed": False,
        "gate_failures": [],
        "review_loop_verdict": "",
        "review_objectives": {},
        "sidecar_lines": ["# Doc 05 agent loop — raw prompts and responses"],
        "gate_history": [],
        "review_history": [],
        "converged": False,
    }
    config = {
        "configurable": {"thread_id": "doc05-agent"},
        "recursion_limit": max(20, max_cycles * 4 + 4),
    }
    try:
        graph.invoke(initial, config=config)
    except _BudgetExhausted as exc:
        logger.warning("doc05 budget exhausted: %s", exc)
    # Re-read the latest checkpoint from the InMemorySaver: it has the
    # most recent sections/gate_history even when the graph terminates
    # via the exception rather than END.
    state_snapshot = graph.get_state(config)
    final = dict(state_snapshot.values) if state_snapshot else initial
    if final.get("review_loop_verdict") == "BUDGET_EXHAUSTED":
        final.setdefault("review_loop_verdict", "BUDGET_EXHAUSTED")
        final.setdefault("converged", False)
    return final
