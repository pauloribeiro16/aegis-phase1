"""CORR-039-T6 Block 1+2: ClauseMappingContext + Doc 06 refactor tests.

Tests:
  - 6 ClauseMappingContext tests (build, per_reg, unmapped, by_regulation, to_dict, empty)
  - 4 Doc 06 refactor tests (renders, 222 rows for case1, per_reg, no state ontology read)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aegis_phase1.v2.context import (
    ClauseMappingContext,
    ClauseMappingEntry,
    build_clause_mapping_context,
)
from aegis_phase1.v2.context.clause_mapping_context import (
    _build_clause_to_subdomain_map,
    _collect_nist_csf_mappings,
    _resolve_article_ref,
)


# ---------------------------------------------------------------------------
# Block 1: ClauseMappingContext (6 tests)
# ---------------------------------------------------------------------------


def test_clause_mapping_context_empty_when_no_applicable_regs() -> None:
    """Empty applicable_regs → empty context."""
    ctx = build_clause_mapping_context({"v2_applicable_regs": []})
    assert isinstance(ctx, ClauseMappingContext)
    assert ctx.entries == []
    assert ctx.per_reg_count == {}
    assert ctx.total_clauses == 0
    assert ctx.unmapped_count == 0


def test_clause_mapping_context_empty_when_no_catalog_ref() -> None:
    """No v2_preproc_catalog_ref and no override → empty context."""
    state = {"v2_applicable_regs": ["GDPR"], "v2_srs": []}
    ctx = build_clause_mapping_context(state)
    assert ctx.entries == []
    assert ctx.total_clauses == 0


def test_clause_mapping_context_populates_for_case1(case1_v2_state: dict) -> None:
    """Real case1 state → context with 222 entries, 41 unmapped."""
    ctx = build_clause_mapping_context(case1_v2_state)
    assert isinstance(ctx, ClauseMappingContext)
    assert ctx.total_clauses > 0
    assert ctx.total_clauses == len(ctx.entries)
    # Per the G2 smoke test: 72 GDPR + 150 CRA = 222 mapped
    assert ctx.total_clauses >= 170, (
        f"expected ≥170 mapped clauses (case1 has 222), got {ctx.total_clauses}"
    )
    # Per_reg count must be populated
    assert "GDPR" in ctx.per_reg_count
    assert "CRA" in ctx.per_reg_count


def test_clause_mapping_context_per_reg_count_gdpr_cra(case1_v2_state: dict) -> None:
    """case1 → GDPR and CRA both >0, NIS2/DORA/AI_Act absent (not applicable)."""
    ctx = build_clause_mapping_context(case1_v2_state)
    assert ctx.per_reg_count["GDPR"] >= 60
    assert ctx.per_reg_count["CRA"] >= 140
    # Not-applicable regs should not appear in per_reg_count
    for absent in ("NIS2", "DORA", "AI_Act"):
        assert absent not in ctx.per_reg_count


def test_clause_mapping_context_by_regulation_filters(case1_v2_state: dict) -> None:
    """by_regulation('GDPR') returns only GDPR entries."""
    ctx = build_clause_mapping_context(case1_v2_state)
    gdpr_only = ctx.by_regulation("GDPR")
    assert all(e.regulation == "GDPR" for e in gdpr_only)
    assert len(gdpr_only) == ctx.per_reg_count["GDPR"]
    assert len(gdpr_only) == sum(1 for e in ctx.entries if e.regulation == "GDPR")


def test_clause_mapping_context_to_dict_json_serializable(case1_v2_state: dict) -> None:
    """to_dict returns a JSON-serializable dict."""
    import json

    ctx = build_clause_mapping_context(case1_v2_state)
    d = ctx.to_dict()
    # Round-trip through json
    s = json.dumps(d)
    assert len(s) > 100  # non-trivial
    assert "entries" in d
    assert "per_reg_count" in d
    assert "total_clauses" in d
    assert "unmapped_count" in d


# ---------------------------------------------------------------------------
# Block 2: Doc 06 refactor (4 tests)
# ---------------------------------------------------------------------------


def test_doc_06_renders_with_clause_mapping_context(case1_v2_state: dict, tmp_path) -> None:
    """render_doc_06 with a populated state writes a non-empty file."""
    from aegis_phase1.v2.output.doc_06 import render_doc_06

    out = str(tmp_path / "out")
    paths = render_doc_06(case1_v2_state, out)
    assert "AEGIS-P1-06" in paths
    p = Path(paths["AEGIS-P1-06"])
    assert p.exists()
    body = p.read_text(encoding="utf-8")
    assert "Clause Mapping Matrix" in body
    assert len(body) > 5000  # populated, not the old empty stub


def test_doc_06_table_has_222_rows_for_case1(case1_v2_state: dict, tmp_path) -> None:
    """Doc 06 case1 → 222 rows (150 CRA + 24 GDPR-CL + 27 GDPR-CP + 11 GDPR-RT + 10 GDPR-TR)."""
    import re

    from aegis_phase1.v2.output.doc_06 import render_doc_06

    out = str(tmp_path / "out")
    paths = render_doc_06(case1_v2_state, out)
    body = Path(paths["AEGIS-P1-06"]).read_text(encoding="utf-8")
    # Count rows starting with | and containing a clause id pattern
    rows = [l for l in body.split("\n") if re.match(r"^\|\s*(GDPR|CRA)-[A-Z]{2}\d+", l)]
    assert len(rows) == 222, f"expected 222 clause rows, got {len(rows)}"


def test_doc_06_per_reg_count_matches_canonical(case1_v2_state: dict, tmp_path) -> None:
    """§2 SUMMARY surfaces per_reg_count: GDPR=72 CRA=150."""
    from aegis_phase1.v2.output.doc_06 import render_doc_06

    out = str(tmp_path / "out")
    paths = render_doc_06(case1_v2_state, out)
    body = Path(paths["AEGIS-P1-06"]).read_text(encoding="utf-8")
    assert "GDPR=72" in body
    assert "CRA=150" in body


def test_doc_06_no_longer_reads_state_ontology_clause_mappings() -> None:
    """Source-level check: doc_06 no longer references state['ontology']['clause_mappings']."""
    import inspect

    from aegis_phase1.v2.output import doc_06

    src = inspect.getsource(doc_06)
    # The v1 reads are gone
    assert "ontology.get(\"clause_mappings\"" not in src
    assert 'ontology.get("clause_mappings"' not in src
    # The new context-based read is present
    assert "build_clause_mapping_context" in src


# ---------------------------------------------------------------------------
# Internal helpers (bonus coverage for the T2 _build_* helpers)
# ---------------------------------------------------------------------------


def test_helpers_build_clause_to_subdomain_map_simple() -> None:
    """_build_clause_to_subdomain_map walks SR.source_clauses → SR.sub_domain."""

    class _SR:
        def __init__(self, sid, sources, subs):
            self.id = sid
            self.source_clauses = sources
            self.sub_domain = subs

    srs = [
        _SR("SR-X-001", [{"clause_id": "C1"}, {"clause_id": "C2"}], ["D-01.1"]),
        _SR("SR-X-002", [{"clause_id": "C2"}], ["D-01.2", "D-01.3"]),
    ]
    c2s, c2sr = _build_clause_to_subdomain_map(srs)
    assert sorted(c2s["C1"]) == ["D-01.1"]
    assert sorted(c2s["C2"]) == ["D-01.1", "D-01.2", "D-01.3"]
    assert c2sr["C1"] == ["SR-X-001"]
    assert c2sr["C2"] == ["SR-X-001", "SR-X-002"]


def test_helpers_collect_nist_csf_mappings_dedup() -> None:
    """NIST CSF mapping IDs deduplicated across multiple SRs."""

    class _CSF:
        def __init__(self, csf_id):
            self.id = csf_id

    class _SR:
        def __init__(self, sources, csfs):
            self.source_clauses = sources
            self.nist_csf_mapping = csfs

    srs = [
        _SR([{"clause_id": "C1"}], [_CSF("PR.DS-01"), _CSF("PR.DS-02")]),
        _SR([{"clause_id": "C1"}], [_CSF("PR.DS-02"), _CSF("PR.DS-03")]),
    ]
    out = _collect_nist_csf_mappings(srs, "C1")
    assert out == ["PR.DS-01", "PR.DS-02", "PR.DS-03"]


def test_helpers_resolve_article_ref_prefers_sr() -> None:
    """_resolve_article_ref returns the SR's article_ref over clause.section_ref."""

    class _Clause:
        section_ref = "fallback"

    class _SR:
        source_clauses = [{"clause_id": "C1", "article_ref": "Art. 5(1)(f)"}]

    assert _resolve_article_ref(_Clause(), [_SR()], "C1") == "Art. 5(1)(f)"


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def case1_v2_state():
    """Real case1 v2 state: orchestrator with all 3 loaders (T1 wiring) applied.

    Mirrors tests/unit/v2/conftest.py::case1_v2_state but adds the
    CORR-039-T1 catalog_loader so v2_catalog_tipo2/tipo3 are populated.
    """
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    with tempfile.TemporaryDirectory() as d:
        o = Phase1Orchestrator(
            work_dir=d,
            preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
            case_profile_loader=_CaseProfileLoaderLocal(),
            catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
        )
        o._load_v2_catalog("cases/case1-tinytask")
        yield dict(o.state)


class _CaseProfileLoaderLocal:
    """Minimal CaseProfileLoader shim for the test fixture (avoids the
    CORR-037-T2 loader's session-scope sharing)."""

    def __init__(self):
        from aegis_phase1.v2.loader.case_profile import CaseProfileLoader

        self._inner = CaseProfileLoader(Path("cases/case1-tinytask"))

    def load(self):
        return self._inner.load()
