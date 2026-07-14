"""Test Doc 07 §5.2 (compound events) and §6.2 (strategic implications) rendering.

Contract: AEGIS-P1-CORR-002 Phase B+C+D.
"""
from pathlib import Path

import pytest


def _make_state(synth: dict | None = None, ce: dict | None = None) -> dict:
    return {
        "company_context": None,
        "aggregated_data": {
            "concatenated": {},
            "merged": {},
            "conflicts": [],
            "profile": {},
            "synthesis": synth,
            "compound_events": ce,
        },
        "ontology": {
            "subdomains": {"covered": [], "not_covered": []},
            "clause_mappings": [],
            "coverage_summary": {},
            "tensions": [],
            "applicability_assessments": [],
        },
        "regulations": [],
    }


def _make_ontology_with_rows() -> dict:
    return {
        "subdomains": {"covered": [], "not_covered": []},
        "clause_mappings": [],
        "coverage_summary": {"total_subdomains": 0},
        "tensions": [],
        "applicability_assessments": [],
    }


def test_compound_events_section_renders_table():
    """Given synthetic compound_events, §5.2 renders a table with rows."""
    from aegis_phase1.v2.output.doc_07 import _render_compound_events_section

    ce = {
        "status": "OK",
        "confidence": "HIGH",
        "positive_events": [
            {
                "event_id": "EVT-01",
                "description": "Personal data breach via actively exploited product vulnerability",
                "sub_domains": ["D-01.1", "D-04.3"],
                "regulations_triggered": ["GDPR", "CRA"],
                "tension_type": "TEMPORAL_CONFLICT",
                "severity": "CRITICAL",
                "layer0_refs": ["SubDomains/D-04_Incident-Response/D-04.3.md"],
            }
        ],
        "negative_events": [],
    }
    parts = _render_compound_events_section(_make_state(ce=ce))
    text = "\n".join(parts)
    assert "5.2 Compound Events" in text
    assert "EVT-01" in text
    assert "GDPR" in text
    assert "CRA" in text
    assert "PENDING REVIEW" not in text
    assert "Confirmed compound events" in text


def test_compound_events_section_pending_when_missing():
    """Given no compound_events, §5.2 shows PENDING REVIEW marker."""
    from aegis_phase1.v2.output.doc_07 import _render_compound_events_section

    parts = _render_compound_events_section(_make_state())
    text = "\n".join(parts)
    assert "PENDING REVIEW" in text
    assert "doc_07.section_5_2.compound_events" in text


def test_compound_events_section_includes_negative_calibration():
    """Negative calibration rows render when present."""
    from aegis_phase1.v2.output.doc_07 import _render_compound_events_section

    ce = {
        "status": "OK",
        "positive_events": [],
        "negative_events": [
            {
                "scenario": "S-1",
                "regulations_checked": ["GDPR", "CRA"],
                "why_not_compound": "Different timers, mutually exclusive triggers",
            }
        ],
    }
    parts = _render_compound_events_section(_make_state(ce=ce))
    text = "\n".join(parts)
    assert "Apparent but NOT compound" in text
    assert "S-1" in text
    assert "Different timers" in text


def test_strategic_synthesis_section_renders_table():
    """Given synthetic synthesis, §6.2 renders a table."""
    from aegis_phase1.v2.output.doc_07 import _render_strategic_synthesis_section

    synth = {
        "status": "OK",
        "confidence": "HIGH",
        "implications": [
            {
                "id": "IMP-01",
                "description": "Shared KMS across D-01.1 and D-01.3 enables unified key-rotation program",
                "affected_sub_domains": ["D-01.1", "D-01.3"],
                "regulations": ["GDPR", "CRA"],
                "architectural_impact": "Single AWS KMS config satisfies both.",
                "risk_level": "LOW",
                "doc07b_refs": ["D-01.1", "D-01.3"],
            }
        ],
    }
    parts = _render_strategic_synthesis_section(_make_state(synth=synth))
    text = "\n".join(parts)
    assert "6.2 Strategic Implications" in text
    assert "IMP-01" in text
    assert "PENDING REVIEW" not in text
    assert "doc07b_refs" in text


def test_strategic_synthesis_section_pending_when_missing():
    """Given no synthesis, §6.2 shows PENDING REVIEW marker."""
    from aegis_phase1.v2.output.doc_07 import _render_strategic_synthesis_section

    parts = _render_strategic_synthesis_section(_make_state())
    text = "\n".join(parts)
    assert "PENDING REVIEW" in text
    assert "doc_07.section_6_2.strategic_implications" in text


def test_section_5_renders_5_2_block_in_full():
    """End-to-end: §5 includes the LLM compound events block."""
    from aegis_phase1.v2.output.doc_07 import _section_5_complementarity

    state = _make_state(
        ce={
            "status": "OK",
            "positive_events": [
                {
                    "event_id": "EVT-99",
                    "description": "x",
                    "sub_domains": ["D-01"],
                    "regulations_triggered": ["GDPR"],
                }
            ],
        }
    )
    parts = _section_5_complementarity([], state)
    text = "\n".join(parts)
    assert "5.2 Compound Events (LLM-02)" in text
    assert "EVT-99" in text


def test_section_6_renders_6_2_block_in_full():
    """End-to-end: §6 includes §6.1 narrative + §6.2 strategic synthesis."""
    from aegis_phase1.v2.output.doc_07 import _section_6_strategic_implications

    state = _make_state(
        synth={
            "status": "OK",
            "implications": [{"id": "IMP-99", "description": "y"}],
        }
    )
    parts = _section_6_strategic_implications(state, [], None)
    text = "\n".join(parts)
    assert "6.1 Narrative" in text
    assert "6.2 Strategic Implications (LLM-03)" in text
    assert "IMP-99" in text


def test_gate_includes_reduce_criteria():
    """Gate checklist shows 8 rows including the 2 new REDUCE-LLM criteria."""
    from aegis_phase1.v2.output.doc_07 import _gate_rows

    state = _make_state(
        synth={"status": "OK", "implications": []},
        ce={"status": "OK", "positive_events": []},
    )
    rows = _gate_rows(state, _make_ontology_with_rows())
    assert len(rows) == 8, f"Expected 8 gate rows, got {len(rows)}"

    row7 = rows[6]
    row8 = rows[7]
    assert row7[0] == "7"
    assert "Compound events computed" in row7[1]
    assert row7[2] == "PASS"
    assert "5.2" in row7[3]

    assert row8[0] == "8"
    assert "Strategic synthesis computed" in row8[1]
    assert row8[2] == "PASS"
    assert "6.2" in row8[3]


def test_gate_fail_when_reduce_data_missing():
    """Gate rows 7/8 FAIL when compound_events / synthesis absent."""
    from aegis_phase1.v2.output.doc_07 import _gate_rows

    state = _make_state()  # no synth, no ce
    rows = _gate_rows(state, _make_ontology_with_rows())
    assert rows[6][2] == "FAIL"
    assert rows[7][2] == "FAIL"


def test_render_doc_07_does_not_crash_with_reduce_data():
    """Full render_doc_07 with REDUCE-LLM data produces expected sections."""
    from aegis_phase1.v2.output.doc_07 import render_doc_07

    state = _make_state(
        synth={"status": "OK", "implications": [{"id": "IMP-R", "description": "rendered"}]},
        ce={
            "status": "OK",
            "positive_events": [
                {"event_id": "EVT-R", "description": "rendered", "sub_domains": ["D-01"], "regulations_triggered": ["GDPR"]}
            ],
        },
    )
    out = render_doc_07(state, output_dir="/tmp")
    path = out["AEGIS-P1-07"]
    text = Path(path).read_text(encoding="utf-8")
    assert "5.2 Compound Events (LLM-02)" in text
    assert "6.2 Strategic Implications (LLM-03)" in text
    assert "EVT-R" in text
    assert "IMP-R" in text
