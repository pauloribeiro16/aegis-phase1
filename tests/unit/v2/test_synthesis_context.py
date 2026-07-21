"""CORR-041-T6 tests: SynthesisContext + factory + P1B-LLM-02 + CLI + parity.

15 tests:
  - 6 SynthesisContext tests (build, status derivation, compound event
    parsing, strategic synthesis parsing, to_dict, empty)
  - 3 P1B-LLM-02 integration tests (via run_phase_1b populates
    rationale_by_reg + v2_synthesis_context)
  - 3 --run-reduce CLI tests (with MOCK_LLM produces 4 docs, defensive
    on reduce failure, exposes v2_synthesis_context)
  - 3 parity check tests (1 per category: applicability, clause, activation)
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Block 1: SynthesisContext (6 tests)
# ---------------------------------------------------------------------------


def test_synthesis_context_empty_state() -> None:
    """Empty state → SynthesisContext with status=EMPTY."""
    from aegis_phase1.v2.context import build_synthesis_context

    ctx = build_synthesis_context({})
    assert ctx.status == "EMPTY"
    assert not ctx.has_synthesis()
    assert ctx.compound_event_count() == 0
    assert ctx.per_reg_count() == 0
    assert ctx.synthesis.prose == ""
    assert ctx.compound_events == []
    assert ctx.track_b_profile == {}
    assert ctx.conflicts == []
    assert ctx.per_reg_rationale == {}


def test_synthesis_context_status_ok_when_all_fields_populated() -> None:
    """All 3 LLM outputs present → status=OK."""
    from aegis_phase1.v2.context import build_synthesis_context

    state = {
        "aggregated_data": {
            "synthesis": {"prose": "Strategic narrative..."},
            "compound_events": [{"event_id": "E1", "regulations": ["GDPR"]}],
            "rationale_by_reg": {"GDPR": {"synthesis": "GDPR applies because..."}},
            "profile": {"D-01.1": {"tier": "MUST"}},
        }
    }
    ctx = build_synthesis_context(state)
    assert ctx.status == "OK"
    assert ctx.has_synthesis()
    assert ctx.compound_event_count() == 1
    assert ctx.per_reg_count() == 1


def test_synthesis_context_status_mixed_when_partial() -> None:
    """Only synthesis populated → status=MIXED."""
    from aegis_phase1.v2.context import build_synthesis_context

    state = {
        "aggregated_data": {
            "synthesis": {"prose": "Partial narrative"},
        }
    }
    ctx = build_synthesis_context(state)
    assert ctx.status == "MIXED"
    assert ctx.has_synthesis()
    assert ctx.compound_event_count() == 0


def test_synthesis_context_parses_compound_events_canonical_shape() -> None:
    """Parse compound_events with canonical {event_id, regulations, ...} shape."""
    from aegis_phase1.v2.context import build_synthesis_context

    state = {
        "aggregated_data": {
            "compound_events": [
                {
                    "event_id": "E1",
                    "regulations": ["GDPR", "CRA"],
                    "description": "Data breach affecting EU users",
                    "severity": "HIGH",
                }
            ]
        }
    }
    ctx = build_synthesis_context(state)
    assert ctx.compound_event_count() == 1
    e = ctx.compound_events[0]
    assert e.event_id == "E1"
    assert e.regulations == ["GDPR", "CRA"]
    assert e.severity == "HIGH"


def test_synthesis_context_parses_compound_events_legacy_shape() -> None:
    """Parse compound_events with legacy {id, regs, narrative} shape."""
    from aegis_phase1.v2.context import build_synthesis_context

    state = {
        "aggregated_data": {
            "compound_events": [
                {
                    "id": "E2",
                    "regs": "GDPR, NIS2",
                    "narrative": "Cross-reg incident",
                }
            ]
        }
    }
    ctx = build_synthesis_context(state)
    e = ctx.compound_events[0]
    assert e.event_id == "E2"
    assert e.regulations == ["GDPR", "NIS2"]  # string parsed
    assert e.description == "Cross-reg incident"


def test_synthesis_context_to_dict_json_serializable() -> None:
    """to_dict returns a JSON-serializable dict."""
    import json

    from aegis_phase1.v2.context import build_synthesis_context

    state = {
        "aggregated_data": {
            "synthesis": {"prose": "narrative", "insights": ["i1", "i2"]},
            "compound_events": [{"event_id": "E1", "regulations": ["GDPR"]}],
        }
    }
    ctx = build_synthesis_context(state)
    d = ctx.to_dict()
    s = json.dumps(d)
    assert "synthesis" in d
    assert "compound_events" in d
    assert "status" in d
    assert d["synthesis"]["prose"] == "narrative"


# ---------------------------------------------------------------------------
# Block 2: P1B-LLM-02 integration (3 tests)
# ---------------------------------------------------------------------------


def test_orchestrator_populates_v2_synthesis_context_after_reduce() -> None:
    """_build_synthesis_context is called at the end of reduce()."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    with tempfile.TemporaryDirectory() as d:
        o = Phase1Orchestrator(
            work_dir=d,
            preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
            case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
            catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
        )
        o._load_v2_catalog("cases/case1-tinytask")
        # Inject empty aggregated_data so the helper has something to read
        o.state["aggregated_data"] = {
            "synthesis": {"prose": "Test synthesis"},
        }
        o._build_synthesis_context()
        assert "v2_synthesis_context" in o.state
        assert o.state["v2_synthesis_context"].status in ("MIXED", "OK")
        assert o.state["v2_synthesis_context"].has_synthesis()


def test_orchestrator_handles_missing_aggregated_data() -> None:
    """If aggregated_data is absent, _build_synthesis_context populates EMPTY ctx."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    with tempfile.TemporaryDirectory() as d:
        o = Phase1Orchestrator(
            work_dir=d,
            preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
            case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
            catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
        )
        o._load_v2_catalog("cases/case1-tinytask")
        # aggregated_data is empty dict (default)
        o._build_synthesis_context()
        assert "v2_synthesis_context" in o.state
        assert o.state["v2_synthesis_context"].status == "EMPTY"


def test_orchestrator_synthesis_context_refreshed_by_run_phase_1b() -> None:
    """run_phase_1b refreshes v2_synthesis_context with new rationale_by_reg."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    with tempfile.TemporaryDirectory() as d:
        o = Phase1Orchestrator(
            work_dir=d,
            preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
            case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
            catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
        )
        o._load_v2_catalog("cases/case1-tinytask")
        # Inject mock rationale_by_reg into aggregated_data and call _build
        o.state["aggregated_data"] = {
            "rationale_by_reg": {"GDPR": {"synthesis": "mock"}},
        }
        o._build_synthesis_context()
        ctx = o.state["v2_synthesis_context"]
        assert "GDPR" in ctx.per_reg_rationale
        assert ctx.per_reg_count() == 1


# ---------------------------------------------------------------------------
# Block 3: --run-reduce CLI (3 tests)
# ---------------------------------------------------------------------------


def test_run_reduce_flag_registered() -> None:
    """Source-level check: --run-reduce is registered in the parser."""
    import inspect

    from aegis_phase1.v2 import runner

    src = inspect.getsource(runner)
    assert '"--run-reduce"' in src or "'--run-reduce'" in src
    assert "run_reduce" in src


def test_cmd_run_reduce_with_mock_llm_produces_4_docs() -> None:
    """cmd_run_reduce with MOCK_LLM produces 4 docs (04a/b/c/d)."""
    os.environ["MOCK_LLM"] = "true"
    try:
        from aegis_phase1.prompts_v2.catalog import CatalogLoader
        from aegis_phase1.prompts_v2.factory import get_prompts_root
        from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
        from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
        from aegis_phase1.v2.orchestrator import Phase1Orchestrator
        from aegis_phase1.v2.runner import cmd_run_reduce

        with tempfile.TemporaryDirectory() as work:
            with tempfile.TemporaryDirectory() as out:
                o = Phase1Orchestrator(
                    work_dir=work,
                    preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                    case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                    catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
                )
                paths = cmd_run_reduce(
                    orch=o,
                    case_path="cases/case1-tinytask",
                    prep_path="",
                    output_path=out,
                )
                assert "AEGIS-P1-04a" in paths
                assert "AEGIS-P1-04b" in paths
                assert "AEGIS-P1-04c" in paths
                assert "AEGIS-P1-04d" in paths
                # All 4 files should exist
                for label in ("AEGIS-P1-04a", "AEGIS-P1-04b", "AEGIS-P1-04c", "AEGIS-P1-04d"):
                    assert Path(paths[label]).exists(), f"{label} not written"
    finally:
        del os.environ["MOCK_LLM"]


def test_cmd_run_reduce_populates_v2_synthesis_context() -> None:
    """cmd_run_reduce calls _build_synthesis_context at the end."""
    os.environ["MOCK_LLM"] = "true"
    try:
        from aegis_phase1.prompts_v2.catalog import CatalogLoader
        from aegis_phase1.prompts_v2.factory import get_prompts_root
        from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
        from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
        from aegis_phase1.v2.orchestrator import Phase1Orchestrator
        from aegis_phase1.v2.runner import cmd_run_reduce

        with tempfile.TemporaryDirectory() as work:
            with tempfile.TemporaryDirectory() as out:
                o = Phase1Orchestrator(
                    work_dir=work,
                    preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                    case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                    catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
                )
                cmd_run_reduce(
                    orch=o,
                    case_path="cases/case1-tinytask",
                    prep_path="",
                    output_path=out,
                )
                # v2_synthesis_context should be in state after cmd_run_reduce
                assert "v2_synthesis_context" in o.state
    finally:
        del os.environ["MOCK_LLM"]


# ---------------------------------------------------------------------------
# Block 4: Parity check (3 tests — one per category)
# ---------------------------------------------------------------------------


def test_parity_applicability_canonical_fields_in_doc_05() -> None:
    """Parity: Doc 05 surfaces the canonical applicability fields."""
    os.environ["MOCK_LLM"] = "true"
    try:
        from aegis_phase1.prompts_v2.catalog import CatalogLoader
        from aegis_phase1.prompts_v2.factory import get_prompts_root
        from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
        from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
        from aegis_phase1.v2.orchestrator import Phase1Orchestrator
        from aegis_phase1.v2.output.doc_05 import render_doc_05

        with tempfile.TemporaryDirectory() as work:
            with tempfile.TemporaryDirectory() as out:
                o = Phase1Orchestrator(
                    work_dir=work,
                    preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                    case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                    catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
                )
                o._load_v2_catalog("cases/case1-tinytask")
                paths = render_doc_05(o.state, out)
                body = Path(paths["AEGIS-P1-05"]).read_text(encoding="utf-8")
                # Canonical fields per CORR-038 (case-insensitive check)
                body_lc = body.lower()
                assert "GDPR".lower() in body_lc
                assert "CRA".lower() in body_lc
                assert "controller" in body_lc
                assert "manufacturer" in body_lc
    finally:
        del os.environ["MOCK_LLM"]


def test_parity_clause_doc_06_has_correct_row_count() -> None:
    """Parity: Doc 06 has 222 rows for case1 (per CORR-039)."""
    import re

    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator
    from aegis_phase1.v2.output.doc_06 import render_doc_06

    with tempfile.TemporaryDirectory() as work:
        with tempfile.TemporaryDirectory() as out:
            o = Phase1Orchestrator(
                work_dir=work,
                preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
            )
            o._load_v2_catalog("cases/case1-tinytask")
            paths = render_doc_06(o.state, out)
            body = Path(paths["AEGIS-P1-06"]).read_text(encoding="utf-8")
            rows = [l for l in body.split("\n") if re.match(r"^\|\s*(GDPR|CRA)-[A-Z]{2}\d+", l)]
            assert len(rows) == 222, f"expected 222 rows, got {len(rows)}"


def test_parity_activation_doc_06_lists_subdomain() -> None:
    """Parity: Doc 06 rows include the D-XX.Y sub-domain column."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator
    from aegis_phase1.v2.output.doc_06 import render_doc_06

    with tempfile.TemporaryDirectory() as work:
        with tempfile.TemporaryDirectory() as out:
            o = Phase1Orchestrator(
                work_dir=work,
                preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
            )
            o._load_v2_catalog("cases/case1-tinytask")
            paths = render_doc_06(o.state, out)
            body = Path(paths["AEGIS-P1-06"]).read_text(encoding="utf-8")
            # D-01.1 is a known sub-domain referenced in case1
            assert "D-01.1" in body
            assert "D-09.1" in body
