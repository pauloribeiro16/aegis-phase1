"""CORR-118 — agent loop tests for Doc 05 (qwen3.8 only, offline).

Drives the loop with a MockInvoker and the real DeterministicGate +
ReviewerAgent. Each test asserts one contract; together they prove that
the drafter-reviewer-revise cycle converges on a JSON-free Doc 05 with
real gap ids from the synthesis.
"""

from __future__ import annotations

from typing import Any

from aegis_phase1.v2.agents import (
    DrafterAgent,
    run_doc05_agent_loop,
)
from aegis_phase1.v2.agents.hydration import hydrate_rationale_by_reg
from aegis_phase1.v2.llm import MockInvoker

CASE = "case1-tinytask"


def _state() -> dict[str, Any]:
    """Minimal case1-tinytask state with real synthesis gaps."""
    return {
        "v2_applicable_regs": ["GDPR", "CRA"],
        "v2_subdomains": [
            {"id": "D-01.1", "participating_regulations": ["GDPR", "CRA"]},
            {"id": "D-02.1", "participating_regulations": ["GDPR", "CRA"]},
            {"id": "D-09.2", "participating_regulations": ["GDPR"]},
            {"id": "D-08.1", "participating_regulations": ["GDPR"]},
            {"id": "D-06.1", "participating_regulations": ["GDPR"]},
            {"id": "D-09.1", "participating_regulations": ["GDPR"]},
            {"id": "D-09.4", "participating_regulations": ["GDPR"]},
        ],
        "architecture_inventory": {
            "N.1_systems": [{"id": "SYS-01", "name": "Main SaaS Application"}],
            "N.3_cloud": [{"id": "CS-01", "provider": "AWS"}],
            "N.4_data_flows": [{"id": "FLOW-01", "data_types": ["email"]}],
            "N.5_data_stores": [{"id": "STORE-01", "personal_data": True}],
        },
        "role_matrix": {
            "gdpr": {"role": "controller"},
            "cra": {"role": "manufacturer"},
        },
        "ontology": {
            "clause_mappings": [
                {"article": "Art. 32", "regulation": "GDPR", "sub_domains": ["D-01.1"]},
                {"article": "Annex I Part II (5)", "regulation": "CRA", "sub_domains": ["D-02.3"]},
            ]
        },
        "aggregated_data": {
            "rationale_by_reg": {
                "GDPR": {
                    "synthesis": {
                        "rationale": "GDPR applies as controller.",
                        "gaps": [
                            {"gap_id": "GAP-D-09.2", "priority": "P1",
                             "risk_description": "No DPIA on file.",
                             "recommendation": "Commission a lightweight DPIA within 30 days."},
                            {"gap_id": "GAP-D-08.1", "priority": "P2",
                             "risk_description": "No security awareness training.",
                             "recommendation": "Schedule annual GDPR session."},
                        ],
                    }
                },
                "CRA": {
                    "synthesis": {
                        "rationale": "CRA applies as manufacturer.",
                        "gaps": [
                            {"gap_id": "GAP-D-05.2", "priority": "P2",
                             "risk_description": "Retention schedule not explicit.",
                             "recommendation": "Add retention schedule to Annex VII."},
                        ],
                    }
                },
            }
        },
    }


def _draft_pass_text() -> str:
    return (
        "## 3. PER-REGULATION APPLICABILITY\n"
        "GDPR: controller, Art. 32 applies (see D-01.1). CRA: manufacturer, "
        "Annex I Part II (5) applies (see D-02.3).\n\n"
        "## 4. NATIVE VS INHERITED COMPLIANCE\n"
        "NATIVE on D-01.1 (Encryption). INHERITED on CS-01 AWS via ISO 27001.\n\n"
        "## 5. SUB-DOMAIN COVERAGE PRELIMINARY\n"
        "| Status | Count |\n|---|---|\n| SUBSTANTIVE | 2 |\n| PARTIAL | 5 |\n| NOT_ADDRESSED | 0 |\n\n"
        "## 6. STRATEGIC IMPLICATIONS\n"
        "| Imp ID | Source | Description | Effort | Priority |\n|---|---|---|---|---|\n"
        "| IMP-D-09.2-1 | GDPR | DPIA within 30 days | days | P1 |\n\n"
        "## 7. REGULATORY GAPS IDENTIFIED\n"
        "| Gap ID | Sub-domain | Type | Risk | Priority | Recommendation |\n"
        "|---|---|---|---|---|---|\n"
        "| GAP-D-09.2 | D-09.2 | DPIA | No DPIA on file | P1 | Commission DPIA |\n"
        "| GAP-D-08.1 | D-08.1 | Training | No training | P2 | Annual session |\n"
        "| GAP-D-05.2 | D-05.2 | Retention | Schedule missing | P2 | Add to Annex VII |\n"
    )


def _review_pass_text() -> str:
    return (
        "OBJ-01: PASS\nwhat: company grounding\nmeasured: every claim cites DOC04/Art./D-XX.Y\nwhy: complete\n\n"
        "OBJ-02: PASS\nwhat: no omissions\nmeasured: both regs in §3, 7 subdomains in §5, 3 gaps in §7\nwhy: complete\n\n"
        "OBJ-03: PASS\nwhat: citation precision\nmeasured: Art. 32, Annex I Part II (5) well-formed\nwhy: matches catalogue\n\n"
        "OBJ-09: PASS\nwhat: no fabrication\nmeasured: all ids traceable\nwhy: complete\n\n"
        "OBJ-12: PASS\nwhat: fail-loud\nmeasured: no placeholders\nwhy: complete\n\n"
        "LOOP_VERDICT: PASS\n"
    )


def test_hydration_recovers_synthesis_from_per_spec() -> None:
    """If rationale_by_reg is empty but per_spec_markdown has JSON fences,
    hydration recovers the synthesis (the JSON-fallback of CORR-116 S2.1)."""
    state = _state()
    state["aggregated_data"]["rationale_by_reg"] = {"GDPR": {}, "CRA": {}}
    state["per_spec_markdown"] = {
        "P1B-LLM-02-RATIONALE": (
            '```json\n{"prompt_spec_id":"P1B-LLM-02-RATIONALE","lane_id":"GDPR",'
            '"synthesis":{"rationale":"recovered","gaps":[{"gap_id":"GAP-X","priority":"P1",'
            '"risk_description":"r","recommendation":"c"}]}}\n```'
        )
    }
    out = hydrate_rationale_by_reg(state)
    assert "GDPR" in out and out["GDPR"]["rationale"] == "recovered"
    assert state["aggregated_data"]["rationale_by_reg"]["GDPR"]["synthesis"]["gaps"][0]["gap_id"] == "GAP-X"


def test_loop_converges_in_one_cycle_when_draft_and_review_pass() -> None:
    script = [_draft_pass_text(), _review_pass_text()]
    invoker = MockInvoker(script=script)
    state = _state()
    res = run_doc05_agent_loop(state, invoker=invoker, max_cycles=3)
    assert res.converged
    assert res.attempts == 1
    assert "```json" not in res.sections["s7"]


def test_gate_rejects_json_fence_and_loop_recovers() -> None:
    """Cycle 1 emits a json fence (gate fails), cycle 2 produces clean text."""
    bad = _draft_pass_text().replace(
        "## 7. REGULATORY GAPS IDENTIFIED",
        "## 7. REGULATORY GAPS IDENTIFIED\n```json\n{\"x\":1}\n```",
    )
    script = [bad, _draft_pass_text(), _review_pass_text()]
    invoker = MockInvoker(script=script)
    state = _state()
    res = run_doc05_agent_loop(state, invoker=invoker, max_cycles=3)
    assert res.converged
    assert len(res.gate_results) >= 2
    assert not res.gate_results[0].passed
    assert res.gate_results[1].passed


def test_loop_stops_when_max_cycles_reached() -> None:
    """If neither gate nor review ever passes, loop ends at max_cycles."""
    bad = "## 3. PER-REGULATION APPLICABILITY\nnope"
    script = [bad, bad, bad]
    invoker = MockInvoker(script=script)
    state = _state()
    res = run_doc05_agent_loop(state, invoker=invoker, max_cycles=3)
    assert not res.converged
    assert res.attempts == 3


def test_review_parse_handles_missing_loop_line() -> None:
    """Reviewer might omit the LOOP_VERDICT line — the parser falls back."""
    from aegis_phase1.v2.agents.reviewer import ReviewerAgent
    invoker = MockInvoker()
    rev = ReviewerAgent(invoker)
    verdict = rev._parse("OBJ-01: PASS\nOBJ-02: PASS\n")
    assert verdict.loop_verdict == "PASS"


def test_drafter_section_split_is_resilient_to_prose_padding() -> None:
    invoker = MockInvoker()
    drafter = DrafterAgent(invoker)
    text = "Some preamble...\n\n" + _draft_pass_text() + "\n\nTail noise."
    sections = drafter._extract_sections(text)
    assert set(sections) == {"s3", "s4", "s5", "s6", "s7"}
    assert sections["s3"].startswith("## 3.")


def test_sidecar_captures_all_cycles() -> None:
    script = [_draft_pass_text(), _review_pass_text()]
    invoker = MockInvoker(script=script)
    state = _state()
    res = run_doc05_agent_loop(state, invoker=invoker, max_cycles=2)
    joined = "\n".join(res.sidecar_lines)
    assert "cycle 1 — drafter prompt" in joined
    assert "cycle 1 — drafter response" in joined
    assert "cycle 1 — reviewer prompt" in joined
    assert "cycle 1 — reviewer response" in joined
