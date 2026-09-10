"""CORR-118 — LCEL chains for the Doc 05 agent loop.

Drafter and Reviewer are expressed as LangChain Expression Language
chains (per ~/.zcode/skills/langchain/templates/chains.py):

  drafter_chain = DRAFTER_PROMPT | ChatOllama(...) | StrOutputParser()
  reviewer_chain = REVIEWER_PROMPT | ChatOllama(...) | StrOutputParser()

The chains take ``state`` (Doc05AgentState dict) as input and return the
raw model text; section splitting + verdict parsing live in the graph
nodes so the chains stay pure and testable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda

from aegis_phase1.v2.agents.drafter import _USER_TMPL as _DRAFTER_USER_TMPL
from aegis_phase1.v2.agents.reviewer import _SYSTEM as _REVIEWER_SYSTEM

logger = logging.getLogger(__name__)


def _make_llm_callable(llm: Any) -> Runnable:
    """Adapt a non-Runnable invoker (UnifiedInvoker, MockInvoker, callable)
    to a LangChain Runnable so it can sit between ChatPromptTemplate and
    StrOutputParser in an LCEL chain.

    If the supplied object is already a LangChain Runnable (e.g.
    GenericFakeChatModel in tests, ChatOllama in production), return it
    unchanged so LCEL's type system stays happy.

    The wrapped invoker is expected to expose either:
      * ``invoke(prompt: str) -> dict`` (UnifiedInvoker / MockInvoker
        adapted via _invoke_raw in graph.py) returning ``{"raw": str}``
      * ``invoke(system, user) -> str`` (the agent's own (sys, user) shape)

    Accepts the prompt output (string user-input) and returns raw text.
    """
    # If the invoker is already a LangChain Runnable, pass it through
    # untouched — LCEL will invoke it natively and we don't need our
    # adapter (the Runnable already accepts the chat-prompt output).
    if hasattr(llm, "invoke") and hasattr(llm, "stream") and hasattr(llm, "batch"):
        return llm  # type: ignore[return-value]

    def _call(input_: Any) -> str:
        # The previous RunnableLambda emits a dict { "_user_input": str }.
        # ChatPromptTemplate then renders it to a ChatPromptValue
        # (a wrapper over a list of BaseMessage objects — one
        # SystemMessage + one HumanMessage in our case). We need to
        # extract the (system, user) pair from any of these shapes
        # and pass the formatted text to the invoker.
        if isinstance(input_, dict) and "_user_input" in input_:
            user = str(input_["_user_input"])
            system = ""
        elif hasattr(input_, "to_messages"):
            # LangChain ChatPromptValue has a to_messages() helper.
            messages = list(input_.to_messages())
            contents = [getattr(m, "content", "") for m in messages]
            if len(contents) == 2:
                system, user = contents
            else:
                system, user = "", "\n\n".join(contents)
        elif isinstance(input_, list | tuple) and len(input_) == 2 and all(
            isinstance(x, str) for x in input_
        ):
            system, user = input_
        elif isinstance(input_, list) and all(
            getattr(m, "content", None) is not None for m in input_
        ):
            contents = [getattr(m, "content", "") for m in input_]
            if len(contents) == 2:
                system, user = contents
            else:
                system, user = "", "\n\n".join(contents)
        elif isinstance(input_, str):
            system, user = "", input_
        else:
            system, user = "", str(input_)

        if hasattr(llm, "invoke"):
            try:
                result = llm.invoke(system, user)
            except TypeError:
                full = system + "\n\n" + user
                result = llm.invoke(full)
        elif callable(llm):
            result = llm(system, user)
        else:  # pragma: no cover — defensive
            raise TypeError(
                f"invoker does not support invoke: {type(llm).__name__}"
            )
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return result.get("raw") or result.get("content") or ""
        return str(result)

    return RunnableLambda(_call)


_DRAFTER_SYSTEM = """You are a markdown writer. The user message below already contains all the facts you need: applicable regulations, company profile, sub-domain catalogue, clause map, and per-regulation synthesis with rationales / implications / gaps. Your only job is to render those facts as five markdown sections.

CRITICAL: Do NOT ask the user for more data, do NOT request "items 1-8", do NOT say "Please paste the source facts". The facts are already in the user message — use them.

OUTPUT CONTRACT (no negotiation):
- Exactly these 5 headers, in this order, with no other markdown before or between them:
  ## 3. PER-REGULATION APPLICABILITY
  ## 4. NATIVE VS INHERITED COMPLIANCE
  ## 5. SUB-DOMAIN COVERAGE PRELIMINARY
  ## 6. STRATEGIC IMPLICATIONS
  ## 7. REGULATORY GAPS IDENTIFIED
- §3: for each applicable regulation, a short paragraph (trigger + company value + result) plus a small table.
- §4: pipe table | Regulation | Status (NATIVE / INHERITED) | Basis |.
- §5: per-sub-domain list with status + a summary table | Status | Count |.
- §6: pipe table | Imp ID | Source | Description | Effort | Priority | followed by a 1-paragraph narrative.
- §7: pipe table | Gap ID | Sub-domain | Type | Risk | Priority | Recommendation |. If the provided synthesis.gaps array is non-empty, you MUST emit at least one row per gap; never write "no gaps detected" when the facts contain gaps.
- Markdown prose + pipe tables only. NO ```json fences, NO "I need more data" replies, NO questions to the user.
- Cite only the anchors given in the user message (Art./Annex tokens, D-XX.Y ids, DOC04 fact refs).
- Do not invent IDs, articles, statistics, or facts — but DO use the ones provided."""


def build_drafter_chain(llm: Any) -> Runnable:
    """Return an LCEL chain that takes Doc05AgentState-like dict and emits
    the drafter's raw markdown response."""
    prompt = ChatPromptTemplate.from_messages(
        [("system", _DRAFTER_SYSTEM), ("human", "{_user_input}")]
    )

    def _format_input(state: dict[str, Any]) -> dict[str, Any]:
        facts = state.get("facts") or {}
        user_input = _DRAFTER_USER_TMPL.format(
            applicable_regs=json.dumps(facts.get("applicable_regs", [])),
            company_profile=facts.get("company_profile", "(not provided)"),
            subdomain_catalogue=facts.get("subdomain_catalogue", "(not provided)"),
            clause_map=facts.get("clause_map", "(not provided)"),
            synthesis=json.dumps(facts.get("synthesis", {}), indent=1, ensure_ascii=False),
        )
        feedback = state.get("feedback") or ""
        if feedback:
            user_input = (
                f"{user_input}\n\n# REVISION REQUEST (cycle {state.get('cycle_count', 0) + 1} feedback)\n\n"
                f"{feedback}"
            )
        return {"_user_input": user_input}

    return RunnableLambda(_format_input) | prompt | _make_llm_callable(llm) | StrOutputParser()


def build_reviewer_chain(llm: Any) -> Runnable:
    """Return an LCEL chain that takes Doc05AgentState-like dict and emits
    the reviewer's raw verdict text."""
    prompt = ChatPromptTemplate.from_messages(
        [("system", _REVIEWER_SYSTEM), ("human", "{_user_input}")]
    )

    def _format_input(state: dict[str, Any]) -> dict[str, Any]:
        facts = state.get("facts") or {}
        sections = state.get("sections") or {}
        draft_md = "\n\n".join(sections.values())
        gap_ids = _gap_ids(facts.get("synthesis") or {})
        user_input = (
            "# FACTS\n\n"
            f"applicable_regs: {facts.get('applicable_regs')}\n"
            f"synthesis gap ids: {gap_ids}\n\n"
            "# DRAFT\n\n"
            f"{draft_md}\n\n"
            "Produce the verdict blocks now."
        )
        return {"_user_input": user_input}

    return RunnableLambda(_format_input) | prompt | _make_llm_callable(llm) | StrOutputParser()


def _gap_ids(synthesis: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for reg_synth in synthesis.values():
        if not isinstance(reg_synth, dict):
            continue
        for gap in reg_synth.get("gaps") or []:
            if isinstance(gap, dict) and gap.get("gap_id"):
                ids.append(str(gap["gap_id"]))
    return sorted(set(ids))
