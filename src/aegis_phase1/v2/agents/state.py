"""CORR-118 state schema for the Doc 05 agent loop.

Implements the Evaluator-Optimizer pattern from
~/.zcode/skills/langgraph/references/patterns.md §4.
"""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph import add_messages
from typing_extensions import TypedDict


class Doc05AgentState(TypedDict, total=False):
    """Mutable state threaded through draft → gate → review nodes."""

    # Inputs (set once by build_doc05_facts)
    facts: dict[str, Any]
    """Closed-anchor facts for the drafter (company profile, regs,
    sub-domain catalogue, clause map, hydrated P1B-02 synthesis)."""

    # Cycle bookkeeping
    cycle_count: int
    """How many draft+gate+review rounds have elapsed (≤ max_cycles)."""
    max_cycles: int
    """Upper bound on draft invocations (default 3)."""

    # Last draft
    feedback: str
    """Feedback string injected into the next draft prompt (gate or
    reviewer output). Empty on the first cycle."""
    last_prompt: str
    """The system+user prompt sent to the drafter in this cycle (for
    sidecar)."""
    last_response: str
    """The raw markdown the drafter produced in this cycle."""

    # Sections
    sections: dict[str, str]
    """section_key -> markdown body for the latest draft (s3/s4/s5/s6/s7)."""

    # Deterministic gate
    gate_passed: bool
    """Whether the latest draft passed the DeterministicGate."""
    gate_failures: list[str]
    """List of failure strings when gate_passed is False."""

    # Reviewer
    review_loop_verdict: str
    """'PASS' | 'REVISE' | 'UNPARSEABLE'."""
    review_objectives: dict[str, str]
    """{OBJ-XX: 'PASS'|'WARN'|'FAIL'} from the reviewer's verdict block."""

    # History (append-only)
    sidecar_lines: list[str]
    """Markdown lines that the renderer writes to 05_llm_raw.md next to
    the document. Each cycle contributes one prompt + one response
    block; reviewer adds its own block when the gate passed."""
    gate_history: list[dict[str, Any]]
    """[{passed, failures}] per cycle."""
    review_history: list[dict[str, Any]]
    """[{loop_verdict, objectives, raw}] per cycle where the gate passed."""

    # Result
    converged: bool
    """True iff review PASS (gate must have passed first)."""

    # LangChain messages (for tools/observability hook)
    messages: Annotated[list, add_messages]
    """Conversation-style trail of the loop."""
