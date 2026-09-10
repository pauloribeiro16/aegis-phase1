"""Loop + facts builder — CORR-118 agent loop for Doc 05.

Wire-up:

  build_doc05_facts(state)
    → compact facts dict the drafter consumes (no raw LLM payloads)

  run_doc05_agent_loop(state, *, invoker, max_cycles=3)
    → returns {sections, sidecar, attempts, gate_results, review_results}
    → writes a sidecar string with raw LLM responses per cycle for the
      ``05_llm_raw.md`` file the renderer will write next to the doc.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from aegis_phase1.v2.agents.drafter import DrafterAgent
from aegis_phase1.v2.agents.gate import DeterministicGate, GateResult
from aegis_phase1.v2.agents.hydration import hydrate_rationale_by_reg
from aegis_phase1.v2.agents.reviewer import ReviewerAgent, ReviewVerdict

logger = logging.getLogger(__name__)


@dataclass
class Doc05AgentResult:
    sections: dict[str, str]
    sidecar_lines: list[str]
    attempts: int
    gate_results: list[GateResult] = field(default_factory=list)
    review_results: list[ReviewVerdict] = field(default_factory=list)

    @property
    def converged(self) -> bool:
        return bool(self.review_results) and self.review_results[-1].loop_verdict == "PASS"


def build_doc05_facts(state: dict[str, Any]) -> dict[str, Any]:
    """Compact facts payload the DrafterAgent sees (closed anchors only)."""
    hydrate_rationale_by_reg(state)

    profile = _company_profile(state)
    subdomains = _subdomain_catalogue(state)
    clause_map = _clause_map(state)
    synthesis = _synthesis(state)

    return {
        "applicable_regs": list(state.get("v2_applicable_regs") or state.get("regulations") or []),
        "company_profile": profile,
        "subdomain_catalogue": subdomains,
        "clause_map": clause_map,
        "synthesis": synthesis,
    }


def run_doc05_agent_loop(
    state: dict[str, Any],
    *,
    invoker: Any,
    max_cycles: int = 3,
) -> Doc05AgentResult:
    """Drafter → Gate → Reviewer loop, ≤ max_cycles.

    The same LLM serves Drafter and Reviewer with different prompts; the
    loop accumulates every raw prompt/response in ``sidecar_lines`` for the
    ``05_llm_raw.md`` sidecar file.
    """
    facts = build_doc05_facts(state)
    drafter = DrafterAgent(invoker)
    reviewer = ReviewerAgent(invoker)
    gate = DeterministicGate()
    invoker = _wrap_for_agent(invoker)

    feedback = ""
    sections: dict[str, str] = {}
    sidecar_lines: list[str] = ["# Doc 05 agent loop — raw prompts and responses"]
    gate_results: list[GateResult] = []
    review_results: list[ReviewVerdict] = []

    for cycle in range(1, max_cycles + 1):
        system, user = drafter.build_prompt(facts)
        if feedback:
            user = (
                f"{user}\n\n# REVISION REQUEST (cycle {cycle} feedback)\n\n{feedback}"
            )
        full_prompt = system + "\n\n" + user
        sidecar_lines.append(f"\n## cycle {cycle} — drafter prompt\n\n```\n{full_prompt[:4000]}\n```")

        draft_raw = _invoke_raw(invoker, system, user)
        sidecar_lines.append(f"\n## cycle {cycle} — drafter response\n\n```\n{draft_raw[:4000]}\n```")
        sections = drafter._extract_sections(draft_raw)

        gate_res = gate.check(sections, expect_gaps=bool(facts.get("synthesis")))
        gate_results.append(gate_res)
        if not gate_res.passed:
            feedback = gate_res.feedback()
            logger.info("doc05 cycle %d failed gate: %s", cycle, gate_res.failures[:2])
            continue

        # Gate passed — call the reviewer
        rev_system, rev_user = _reviewer_messages(reviewer, facts, sections)
        rev_prompt = rev_system + "\n\n" + rev_user
        sidecar_lines.append(f"\n## cycle {cycle} — reviewer prompt\n\n```\n{rev_prompt[:4000]}\n```")
        rev_raw = _invoke_raw(invoker, rev_system, rev_user)
        sidecar_lines.append(f"\n## cycle {cycle} — reviewer response\n\n```\n{rev_raw[:4000]}\n```")
        verdict = reviewer._parse(rev_raw)
        review_results.append(verdict)
        if verdict.loop_verdict == "PASS":
            logger.info("doc05 PASS after %d cycle(s)", cycle)
            break

        feedback = verdict.feedback or verdict.raw
        logger.info("doc05 cycle %d review REVISE: %s", cycle, verdict.objectives)

    return Doc05AgentResult(
        sections=sections,
        sidecar_lines=sidecar_lines,
        attempts=len(gate_results),
        gate_results=gate_results,
        review_results=review_results,
    )


# ── helpers ────────────────────────────────────────────────────────────


def _invoke_raw(invoker: Any, system: str, user: str) -> str:
    """Invoke and return raw text. Accepts UnifiedInvoker, a callable, or an
    agent-style ``invoke(system, user) -> dict`` that we wrap on the fly."""
    full_prompt = system + "\n\n" + user

    # Fast path: any callable that takes (system, user) — used by the loop
    # to wrap a MockInvoker without forcing tests to know the MockInvoker's
    # exact signature.
    if callable(invoker) and not hasattr(invoker, "_invoke_raw"):
        result = invoker(system, user)
    elif hasattr(invoker, "invoke"):
        try:
            # Prefer the agent-style (system, user) signature; fall back to
            # the MockInvoker's (prompt, feedback=None) if needed.
            result = invoker.invoke(system, user)
        except TypeError:
            try:
                result = invoker.invoke(full_prompt, "")
            except TypeError:
                result = invoker.invoke(full_prompt)
    else:
        raise TypeError(f"invoker does not support invoke: {type(invoker).__name__}")

    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        raw = result.get("raw")
        if isinstance(raw, str) and raw:
            return raw
        return result.get("content") or ""
    return str(result)


class _StringScriptInvoker:
    """Wrap a list of strings as an agent-style invoker for tests.

    MockInvoker from v2/llm.py expects each script entry to be a dict-like
    iterable; tests want to pass plain strings (one draft per call). This
    adapter exposes ``invoke(system, user) -> {"raw": next_script}``.
    """

    def __init__(self, scripts: list[str]) -> None:
        self._scripts = list(scripts)
        self.call_count = 0

    def invoke(self, system: str, user: str) -> dict[str, str]:
        if self.call_count < len(self._scripts):
            text = self._scripts[self.call_count]
            self.call_count += 1
        else:
            text = ""
        return {"raw": text, "status": "OK"}

    def __call__(self, system: str, user: str) -> dict[str, str]:
        return self.invoke(system, user)


def _wrap_for_agent(invoker: Any) -> Any:
    """Wrap a v2 MockInvoker (script of dicts) so the agent loop sees a
    callable ``(system, user) -> dict`` with plain strings."""
    if callable(invoker) and not hasattr(invoker, "_script_entries"):
        return invoker
    script = getattr(invoker, "script", None)
    if script is None:
        return invoker
    texts = [entry if isinstance(entry, str) else (entry.get("raw") or "") for entry in script]
    return _StringScriptInvoker(texts)


def _reviewer_messages(reviewer: ReviewerAgent, facts: dict[str, Any], sections: dict[str, str]) -> tuple[str, str]:
    system = reviewer.__class__.__dict__["_SYSTEM"] if False else (  # placeholder
        "You are the REVIEWER agent for AEGIS Doc 05 (per OBJECTIVES_CONTRACT)."
    )
    user = (
        f"# FACTS\n\napplicable_regs: {facts.get('applicable_regs')}\n"
        f"synthesis gap ids: {_gap_ids(facts.get('synthesis') or {})}\n\n"
        "# DRAFT\n\n" + "\n\n".join(sections.values()) + "\n\nProduce the verdict blocks."
    )
    return system, user


def _gap_ids(synthesis: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for reg_synth in synthesis.values():
        if not isinstance(reg_synth, dict):
            continue
        for gap in reg_synth.get("gaps") or []:
            if isinstance(gap, dict) and gap.get("gap_id"):
                ids.append(str(gap["gap_id"]))
    return sorted(set(ids))


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
    """Pull a compact row per sub-domain from v2_subdomains."""
    rows: list[dict[str, Any]] = []
    for sub in state.get("v2_subdomains") or []:
        sd_id = getattr(sub, "id", None) or sub.get("id")
        regs = getattr(sub, "participating_regulations", None) or sub.get("participating_regulations") or []
        rows.append({"id": sd_id, "regs": list(regs)})
    return json.dumps(rows, ensure_ascii=False)


def _clause_map(state: dict[str, Any]) -> str:
    """Compact clause→sub-domain map from the preproc ontology."""
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
    """{regulation: synthesis_dict} after hydration."""
    return hydrate_rationale_by_reg(state)
