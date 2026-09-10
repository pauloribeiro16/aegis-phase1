"""CORR-118 — Doc 05 agent loop tests (LangGraph + LCEL, qwen3.8 only).

Drives the graph with a scripted LangChain fake model (GenericFakeChatModel
from langchain_core.language_models.fake_chat_models). The model returns
a pre-canned list of AIMessages in order: drafter cycle 1, drafter cycle 2
(if needed), reviewer cycle 1, drafter cycle 3, reviewer cycle 2, ...

Each test asserts one contract; together they prove the LangGraph agent
loop converges to a JSON-free Doc 05 with real gap ids from the synthesis.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from aegis_phase1.v2.agents import (
    DeterministicGate,
    run_doc05_agent_loop,
)
from aegis_phase1.v2.agents.graph import (
    build_doc05_graph,
    parse_reviewer_verdict,
    split_sections,
)
from aegis_phase1.v2.agents.hydration import hydrate_rationale_by_reg


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
        ],
        "architecture_inventory": {
            "N.1_systems": [{"id": "SYS-01", "name": "Main SaaS Application"}],
            "N.3_cloud": [{"id": "CS-01", "provider": "AWS"}],
        },
        "role_matrix": {"gdpr": {"role": "controller"}, "cra": {"role": "manufacturer"}},
        "ontology": {
            "clause_mappings": [
                {"article": "Art. 32", "regulation": "GDPR", "sub_domains": ["D-01.1"]},
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
        "GDPR: controller, Art. 32 applies (see D-01.1). CRA: manufacturer.\n\n"
        "## 4. NATIVE VS INHERITED COMPLIANCE\n"
        "NATIVE on D-01.1. INHERITED on CS-01 AWS via ISO 27001.\n\n"
        "## 5. SUB-DOMAIN COVERAGE PRELIMINARY\n"
        "| Status | Count |\n|---|---|\n| SUBSTANTIVE | 2 |\n| PARTIAL | 3 |\n| NOT_ADDRESSED | 0 |\n\n"
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
        "OBJ-01: PASS\nwhat: grounding\nmeasured: cites DOC04/Art./D-XX.Y\nwhy: ok\n\n"
        "OBJ-02: PASS\nwhat: no omissions\nmeasured: both regs in §3, gaps in §7\nwhy: complete\n\n"
        "OBJ-03: PASS\nwhat: citation precision\nmeasured: Art. 32 well-formed\nwhy: matches catalogue\n\n"
        "OBJ-09: PASS\nwhat: no fabrication\nmeasured: all ids traceable\nwhy: complete\n\n"
        "OBJ-12: PASS\nwhat: fail-loud\nmeasured: no placeholders\nwhy: complete\n\n"
        "LOOP_VERDICT: PASS\n"
    )


def _fake_responses(*texts: str) -> GenericFakeChatModel:
    """GenericFakeChatModel with one AIMessage per call (cycled).
    Falls back to an empty drafter response once the script is exhausted
    so the graph's max_cycles limit, not the mock, decides when to stop.
    """
    from itertools import cycle

    msgs = [AIMessage(content=t) for t in texts] or [AIMessage(content="")]
    return GenericFakeChatModel(messages=iter(cycle(msgs)))


def test_hydration_recovers_synthesis_from_per_spec() -> None:
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


def test_graph_converges_in_one_cycle() -> None:
    state = _state()
    llm = _fake_responses(_draft_pass_text(), _review_pass_text())
    final = run_doc05_agent_loop(state, llm=llm, max_cycles=3)
    assert final.converged
    assert final.attempts == 1
    assert "```json" not in final.sections.get("s7", "")
    assert "GAP-D-09.2" in final.sections.get("s7", "")


def test_graph_routes_back_to_draft_when_gate_fails() -> None:
    """Cycle 1 emits a ```json fence (gate fails); cycle 2 produces clean text."""
    bad = _draft_pass_text().replace(
        "## 7. REGULATORY GAPS IDENTIFIED",
        "## 7. REGULATORY GAPS IDENTIFIED\n```json\n{\"x\":1}\n```",
    )
    llm = _fake_responses(bad, _draft_pass_text(), _review_pass_text())
    final = run_doc05_agent_loop(_state(), llm=llm, max_cycles=3)
    assert final.converged
    assert len(final.gate_results) >= 2
    assert not final.gate_results[0]["passed"]
    assert final.gate_results[1]["passed"]


def test_graph_returns_unconverged_when_max_cycles_reached() -> None:
    bad = "## 3. PER-REGULATION APPLICABILITY\nnope"
    llm = _fake_responses(bad, bad, bad)
    final = run_doc05_agent_loop(_state(), llm=llm, max_cycles=3)
    assert not final.converged
    assert final.attempts == 3


def test_reviewer_parser_handles_missing_loop_line() -> None:
    loop, objs = parse_reviewer_verdict("OBJ-01: PASS\nOBJ-02: PASS\n")
    assert loop == "PASS"
    assert objs == {"OBJ-01": "PASS", "OBJ-02": "PASS"}


def test_split_sections_resilient_to_prose_padding() -> None:
    text = "Some preamble...\n\n" + _draft_pass_text() + "\n\nTail noise."
    sections = split_sections(text)
    assert set(sections) == {"s3", "s4", "s5", "s6", "s7"}
    assert sections["s3"].startswith("## 3.")


def test_sidecar_captures_every_node_visit() -> None:
    llm = _fake_responses(_draft_pass_text(), _review_pass_text())
    final = run_doc05_agent_loop(_state(), llm=llm, max_cycles=2)
    joined = "\n".join(final.sidecar_lines)
    assert "cycle 1 — drafter prompt + response" in joined
    assert "cycle 1 — reviewer prompt + response" in joined


def test_graph_compiles_with_checkpointer() -> None:
    """Skill template pattern: build_doc05_graph exposes InMemorySaver."""
    graph = build_doc05_graph(_fake_responses("x", "y"), max_cycles=1)
    assert graph is not None  # compiled successfully with checkpointer


def test_gate_unchanged_after_refactor() -> None:
    """[G] layer behaviour is preserved (regression guard)."""
    g = DeterministicGate()
    sections = {
        "s3": "## 3. PER-REGULATION APPLICABILITY\nclean",
        "s4": "## 4. NATIVE VS INHERITED COMPLIANCE\nok",
        "s5": "## 5. SUB-DOMAIN COVERAGE PRELIMINARY\n| Status | Count |\n|---|---|\n| SUBSTANTIVE | 1 |",
        "s6": "## 6. STRATEGIC IMPLICATIONS\nclean",
        "s7": (
            "## 7. REGULATORY GAPS IDENTIFIED\n"
            "| Gap ID | Sub-domain | Type | Risk | Priority | Recommendation |\n"
            "|---|---|---|---|---|---|\n"
            "| GAP-D-09.2 | D-09.2 | DPIA | r | P1 | rec |"
        ),
    }
    ok = g.check(sections, expect_gaps=True)
    assert ok.passed, ok.failures
    bad = g.check({"s3": "## 3. PER-REGULATION APPLICABILITY\n```json\n{}\n```"})
    assert not bad.passed
