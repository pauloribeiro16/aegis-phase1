"""Test Phase 1B RATIONALE wire-up (CORR-004 Phase A / CORR-005 Phase A).

Verifies:

- ``Phase1Orchestrator.run_phase_1b`` returns sentinel ``None`` (which
  triggers the PENDING REVIEW marker in Doc 05 §6.1b) when no LLM
  invoker is configured.
- ``--skip-phase-1b`` flag short-circuits the executor and yields the
  same sentinel.
- Doc 05 §6.1b renders the PENDING REVIEW marker when rationale data
  is absent.
- Doc 05 §6.1b renders per-regulation rationale prose when the data is
  present.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def _work_dir() -> str:
    return str(tempfile.mkdtemp(prefix="phase_1b_rationale_"))


def test_run_phase_1b_skipped_when_no_invoker():
    """Without llm_invoker, rationale_by_reg is None (PENDING REVIEW triggers)."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator(
        work_dir=_work_dir(),
        llm_invoker=None,
    )
    orch.state["aggregated_data"] = {}
    orch.run_phase_1b()
    assert orch.state["aggregated_data"]["rationale_by_reg"] is None


def test_run_phase_1b_skipped_with_skip_phase_1b_flag(monkeypatch):
    """With --skip-phase-1b, rationale_by_reg stays empty (sentinel None)."""
    from aegis_phase1.v2.llm import MockInvoker
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    monkeypatch.delenv("MOCK_LLM", raising=False)

    orch = Phase1Orchestrator(
        work_dir=_work_dir(),
        llm_invoker=MockInvoker(),
    )
    orch.set_skip_phase_1b(True)
    orch.state["aggregated_data"] = {}
    orch.run_phase_1b()
    assert orch.state["aggregated_data"]["rationale_by_reg"] is None


def test_run_phase_1b_skipped_with_mock_llm_env(monkeypatch):
    """With MOCK_LLM=true env var, executor is None → rationale_by_reg is None."""
    from aegis_phase1.v2.llm import MockInvoker
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    monkeypatch.setenv("MOCK_LLM", "true")

    orch = Phase1Orchestrator(
        work_dir=_work_dir(),
        llm_invoker=MockInvoker(),
    )
    orch.state["aggregated_data"] = {}
    orch.run_phase_1b()
    assert orch.state["aggregated_data"]["rationale_by_reg"] is None


def test_run_phase_1b_skipped_with_skip_reduce_llms_flag(monkeypatch):
    """--skip-reduce-llms also short-circuits Phase 1B by convention."""
    from aegis_phase1.v2.llm import MockInvoker
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    monkeypatch.delenv("MOCK_LLM", raising=False)

    orch = Phase1Orchestrator(
        work_dir=_work_dir(),
        llm_invoker=MockInvoker(),
    )
    orch.set_skip_reduce_llms(True)
    orch.state["aggregated_data"] = {}
    orch.run_phase_1b()
    assert orch.state["aggregated_data"]["rationale_by_reg"] is None


def test_run_phase_1b_no_applicable_regs(monkeypatch):
    """Empty applicable_regs list → rationale_by_reg becomes empty dict.

    We monkeypatch ``_get_phase1_executor`` so the executor short-circuit
    doesn't fire, allowing the empty-regs branch in ``run_phase_1b`` to
    run instead.
    """
    from aegis_phase1.v2.llm import MockInvoker
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    monkeypatch.delenv("MOCK_LLM", raising=False)

    orch = Phase1Orchestrator(
        work_dir=_work_dir(),
        llm_invoker=MockInvoker(),
    )
    orch._get_phase1_executor = lambda: object()  # type: ignore[assignment]
    orch.state["aggregated_data"] = {}
    orch.state["company_context"] = {"applicable_regs": []}
    orch.run_phase_1b()
    # rationale_by_reg becomes an empty dict (not None) when regs are empty
    # so the renderer can detect "skipped-no-regs" separately from "skipped-no-invoker"
    assert orch.state["aggregated_data"]["rationale_by_reg"] == {}


def test_rationale_section_renders_table():
    """Given rationale_by_reg data, §6.1b renders per-regulation prose."""
    from aegis_phase1.v2.output.doc_05 import _render_rationale_by_reg_section

    state = {
        "aggregated_data": {
            "rationale_by_reg": {
                "GDPR": {
                    "status": "OK",
                    "confidence": "HIGH",
                    "synthesis": {
                        "rationale": (
                            "GDPR applies because the company processes "
                            "EU personal data."
                        ),
                        "implications": [
                            {
                                "id": "IMP-D-01.1-1",
                                "description": "Implement AES-256",
                                "effort_estimate": "hours",
                            }
                        ],
                        "gaps": [
                            {
                                "gap_id": "GAP-D-09.1-1",
                                "sub_domain_id": "D-09.1",
                                "risk_description": "RoPA missing",
                                "priority": "P1",
                            }
                        ],
                    },
                },
            }
        }
    }
    section = _render_rationale_by_reg_section(state)
    assert "6.1b Per-Regulation Rationale" in section
    assert "GDPR" in section
    assert "PENDING REVIEW" not in section
    assert "Implement AES-256" in section
    assert "GAP-D-09.1-1" in section
    assert "P1B-LLM-02 RATIONALE" in section


def test_rationale_section_pending_when_missing():
    """Without rationale_by_reg, §6.1b shows PENDING REVIEW marker."""
    from aegis_phase1.v2.output.doc_05 import _render_rationale_by_reg_section

    state = {"aggregated_data": {}}
    section = _render_rationale_by_reg_section(state)
    assert "PENDING REVIEW" in section
    assert "doc_05.section_6_1_b.per_regulation_rationale" in section


def test_rationale_section_pending_when_none():
    """When rationale_by_reg is explicitly None, still PENDING REVIEW."""
    from aegis_phase1.v2.output.doc_05 import _render_rationale_by_reg_section

    state = {"aggregated_data": {"rationale_by_reg": None}}
    section = _render_rationale_by_reg_section(state)
    assert "PENDING REVIEW" in section


def test_rationale_section_handles_flat_synthesis_dict():
    """When synthesis fields live at the top level (not nested), still render."""
    from aegis_phase1.v2.output.doc_05 import _render_rationale_by_reg_section

    state = {
        "aggregated_data": {
            "rationale_by_reg": {
                "CRA": {
                    "rationale": "CRA applies as the company ships digital products.",
                    "implications": [],
                    "gaps": [],
                }
            }
        }
    }
    section = _render_rationale_by_reg_section(state)
    assert "CRA" in section
    assert "CRA applies" in section
    assert "PENDING REVIEW" not in section


def test_run_all_wires_run_phase_1b(monkeypatch):
    """Verify run_all() invokes run_phase_1b() between MAP and REDUCE."""
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    calls: list[str] = []

    def fake_load(self, *args, **kwargs):
        calls.append("load")
        self.state["current_stage"] = "LOADED"
        return self.state

    def fake_map(self):
        calls.append("map")
        self.state["current_stage"] = "MAPPED"
        self.state["domain_results"] = {
            "D-01": {"subdomains": [{"activation_id": "a1"}]}
        }
        return self.state

    def fake_phase_1b(self):
        calls.append("phase_1b")
        if "aggregated_data" not in self.state:
            self.state["aggregated_data"] = {}
        self.state["aggregated_data"]["rationale_by_reg"] = None
        return self.state

    def fake_reduce(self):
        calls.append("reduce")
        self.state["current_stage"] = "REDUCED"
        return self.state

    def fake_outputs(self, *args, **kwargs):
        calls.append("outputs")
        self.state["current_stage"] = "OUTPUT_DONE"
        return self.state

    monkeypatch.setattr(Phase1Orchestrator, "load", fake_load)
    monkeypatch.setattr(Phase1Orchestrator, "map_domains", fake_map)
    monkeypatch.setattr(Phase1Orchestrator, "run_phase_1b", fake_phase_1b)
    monkeypatch.setattr(Phase1Orchestrator, "reduce", fake_reduce)
    monkeypatch.setattr(
        Phase1Orchestrator, "generate_outputs", fake_outputs
    )

    orch = Phase1Orchestrator(work_dir=_work_dir(), llm_invoker=None)
    orch.run_all(case_path="/tmp/case")

    assert calls == ["load", "map", "phase_1b", "reduce", "outputs"], (
        f"Unexpected call order: {calls}"
    )


def test_doc_05_includes_rationale_section_when_present(tmp_path):
    """End-to-end: render_doc_05 embeds §6.1b prose when rationale provided."""
    from aegis_phase1.v2.output.doc_05 import render_doc_05

    state = {
        "company_context": None,
        "ontology": {},
        "regulations": [],
        "architecture_inventory": {},
        "aggregated_data": {
            "rationale_by_reg": {
                "GDPR": {
                    "synthesis": {
                        "rationale": "GDPR applies; sample rationale."
                    }
                }
            }
        },
    }
    out = render_doc_05(state, str(tmp_path), llm_invoker=None)
    assert "AEGIS-P1-05" in out
    md_path = Path(out["AEGIS-P1-05"])
    content = md_path.read_text(encoding="utf-8")
    assert "6.1b Per-Regulation Rationale" in content
    assert "GDPR applies; sample rationale" in content
    # §6.1b-specific PENDING REVIEW marker must NOT be in the output
    assert (
        "doc_05.section_6_1_b.per_regulation_rationale" not in content
    ), (
        "§6.1b should NOT emit its PENDING REVIEW marker when "
        "rationale data is provided"
    )


def test_doc_05_emits_pending_marker_without_data(tmp_path):
    """End-to-end: without rationale data, §6.1b shows PENDING REVIEW."""
    from aegis_phase1.v2.output.doc_05 import render_doc_05

    state = {
        "company_context": None,
        "ontology": {},
        "regulations": [],
        "architecture_inventory": {},
        "aggregated_data": {},
    }
    out = render_doc_05(state, str(tmp_path), llm_invoker=None)
    content = Path(out["AEGIS-P1-05"]).read_text(encoding="utf-8")
    assert "PENDING REVIEW" in content
    assert "doc_05.section_6_1_b.per_regulation_rationale" in content
