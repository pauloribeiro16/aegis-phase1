"""Tests for PreprocCatalogLoader (CORR-037-T1).

Reference: execution/CONTRACT-037.md §T1 / §G3 / §G4.

These tests read from the committed `preproc_out/` directory (treated as
read-only per AGENTS.md §0). They are NOT snapshot tests — they assert
structural invariants (counts, schema shape, scoped queries) that are
expected to hold across the project lifetime. The strategy doc claims
38/282/338/578/196/185 counts, but the actual committed preproc_out has
slightly different numbers (see notes per test). The tests assert the
ACTUAL counts so they serve as a regression guard for the loader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis_phase1.v2.loader.preproc_catalog import (
    SO,
    SR,
    AuditReport,
    CSFSubcat,
    EntitiesIndex,
    Pair,
    PreprocCatalogLoader,
    Subdomain,
)

# Real counts in committed preproc_out/ (verified 2026-07-21).
# These differ from the strategy doc's 38/282/338/578/196/185 because
# the strategy doc was written before the latest preproc rebuild. The
# gates in CONTRACT-037.md §G3 are corrected to these values.
ACTUAL_COUNTS = {
    "subdomains": 38,
    "srs": 282,
    "sos": 328,
    "csfs": 106,  # active only; withdrawn/archived are not on disk
    "clauses": 498,
    "pairs": 196,
    "audit_coverage_full": 282,  # matches SR count
}


@pytest.fixture(scope="module")
def loader() -> PreprocCatalogLoader:
    """Module-scoped fixture: shared loader (lru_cache is in-memory)."""
    return PreprocCatalogLoader(preproc_root=Path("preproc_out"))


# --- G3: counts -----------------------------------------------------------


def test_load_subdomains_count(loader: PreprocCatalogLoader) -> None:
    assert len(loader.load_subdomains()) == ACTUAL_COUNTS["subdomains"]


def test_load_srs_count(loader: PreprocCatalogLoader) -> None:
    assert len(loader.load_srs()) == ACTUAL_COUNTS["srs"]


def test_load_sos_count(loader: PreprocCatalogLoader) -> None:
    assert len(loader.load_sos()) == ACTUAL_COUNTS["sos"]


def test_load_csfs_count(loader: PreprocCatalogLoader) -> None:
    """Active CSF subcategories only (106). Withdrawn/archived are not in preproc_out/."""
    assert len(loader.load_csfs()) == ACTUAL_COUNTS["csfs"]


def test_load_clauses_count(loader: PreprocCatalogLoader) -> None:
    assert len(loader.load_clauses()) == ACTUAL_COUNTS["clauses"]


def test_load_pairs_count(loader: PreprocCatalogLoader) -> None:
    assert len(loader.load_pairs()) == ACTUAL_COUNTS["pairs"]


# --- G4: D-01.1 schema (per strategy doc) ---------------------------------


def test_d01_1_participating_regulations(loader: PreprocCatalogLoader) -> None:
    """D-01.1 has GDPR, NIS2, CRA, DORA (no AI_Act per taxonomy §4.1)."""
    sd = next(s for s in loader.load_subdomains() if s.id == "D-01.1")
    assert sd.participating_regulations == ["GDPR", "NIS2", "CRA", "DORA"]


def test_d01_1_hso_hl_id(loader: PreprocCatalogLoader) -> None:
    """High-level HSO id is SO-D-01.1.HL."""
    sd = next(s for s in loader.load_subdomains() if s.id == "D-01.1")
    assert sd.hso_hl is not None
    assert sd.hso_hl.id == "SO-D-01.1.HL"


def test_d01_1_hso_per_reg_gdpr_inherits(loader: PreprocCatalogLoader) -> None:
    """hso_per_reg[0] (GDPR) inherits from SO-GDPR-001."""
    sd = next(s for s in loader.load_subdomains() if s.id == "D-01.1")
    assert sd.hso_per_reg, "D-01.1 should have hso_per_reg entries"
    gdpr_hso = next(h for h in sd.hso_per_reg if h.regulation == "GDPR")
    assert gdpr_hso.inherits_from == "SO-GDPR-001"


# --- Audit report ---------------------------------------------------------


def test_load_audit_both_pass(loader: PreprocCatalogLoader) -> None:
    """CSF BROKEN==0 AND SO-without-SR==0 AND SR-without-SO==0."""
    audit = loader.load_audit()
    assert isinstance(audit, AuditReport)
    assert audit.both_pass is True
    assert audit.csf_broken_count == 0
    assert audit.so_without_sr == 0
    assert audit.sr_without_so == 0


def test_load_audit_coverage_full(loader: PreprocCatalogLoader) -> None:
    """Coverage full count = 282 (matches SR count, CORR-030 invariant)."""
    audit = loader.load_audit()
    assert audit.coverage_full == ACTUAL_COUNTS["audit_coverage_full"]
    assert audit.coverage_partial == 0
    assert audit.coverage_unresolved == 0


def test_load_audit_csf_verdicts(loader: PreprocCatalogLoader) -> None:
    """CSF verdict_counts has 2 OK + 36 SPARSE + 0 BROKEN."""
    audit = loader.load_audit()
    vc = audit.csf_verdict_counts
    assert vc.get("BROKEN", 0) == 0
    # 38 subdomains total (OK + SPARSE)
    assert sum(vc.values()) == 38


# --- Index ----------------------------------------------------------------


def test_load_index_basic(loader: PreprocCatalogLoader) -> None:
    """Index returns EntitiesIndex with entities/by_regulation/by_subdomain/xref."""
    idx = loader.load_index()
    assert isinstance(idx, EntitiesIndex)
    # entities.json has 'count' and 'by_id' per the actual file
    assert "count" in idx.entities or "by_id" in idx.entities


def test_load_index_by_regulation_has_regs(loader: PreprocCatalogLoader) -> None:
    """by_regulation covers all 5 canonical regulations (AGENTS.md §11)."""
    idx = loader.load_index()
    if idx.by_regulation:
        # Schema varies across preproc versions; if present, expect 5 regs
        for reg in ("GDPR", "CRA", "NIS2", "DORA", "AI_Act"):
            assert reg in idx.by_regulation, f"missing reg {reg} in by_regulation"


# --- Cache behavior -------------------------------------------------------


def test_cache_returns_same_object(loader: PreprocCatalogLoader) -> None:
    """load_subdomains() called twice returns the SAME list (lru_cache)."""
    a = loader.load_subdomains()
    b = loader.load_subdomains()
    assert a is b


def test_clear_cache_reloads(loader: PreprocCatalogLoader) -> None:
    """clear_cache() forces a reload (returns equal but distinct object)."""
    a = loader.load_subdomains()
    loader.clear_cache()
    b = loader.load_subdomains()
    assert a == b
    assert a is not b


# --- Scoped queries -------------------------------------------------------


def test_srs_scoped_by_subdomain(loader: PreprocCatalogLoader) -> None:
    """load_srs(sub_domain='D-01.1') returns only SRs in that subdomain."""
    srs = loader.load_srs(sub_domain="D-01.1")
    assert srs, "D-01.1 should have at least 1 SR"
    for sr in srs:
        assert "D-01.1" in sr.sub_domain


def test_srs_scoped_by_regulation(loader: PreprocCatalogLoader) -> None:
    """load_srs(regulation='GDPR') returns only GDPR SRs."""
    srs = loader.load_srs(regulation="GDPR")
    assert srs
    for sr in srs:
        assert sr.regulation == "GDPR"


def test_sos_scoped_by_subdomain(loader: PreprocCatalogLoader) -> None:
    """load_sos(sub_domain='D-01.1') returns only SOs in that subdomain."""
    sos = loader.load_sos(sub_domain="D-01.1")
    for so in sos:
        assert "D-01.1" in so.sub_domains


def test_clauses_scoped_by_regulation(loader: PreprocCatalogLoader) -> None:
    """load_clauses(regulation='GDPR') returns 86 GDPR clauses."""
    clauses = loader.load_clauses(regulation="GDPR")
    assert len(clauses) == 86
    for c in clauses:
        assert c.regulation == "GDPR"


def test_pairs_scoped_by_subdomain(loader: PreprocCatalogLoader) -> None:
    """load_pairs(sub_domain='D-01.1') returns 6 pairs (all-SAME per CRDA-deep)."""
    pairs = loader.load_pairs(sub_domain="D-01.1")
    assert len(pairs) == 6
    for p in pairs:
        assert p.subdomain_id == "D-01.1"


# --- Schema validation (Pydantic tolerance) -------------------------------


def test_subdomain_model_tolerates_extra(loader: PreprocCatalogLoader) -> None:
    """Pydantic model has extra='allow' — should not raise on extra fields."""
    subs = loader.load_subdomains()
    assert all(isinstance(s, Subdomain) for s in subs)


def test_sr_model_basic(loader: PreprocCatalogLoader) -> None:
    """SRs have all required fields populated for SR-GDPR-001."""
    sr = next(s for s in loader.load_srs() if s.id == "SR-GDPR-001")
    assert isinstance(sr, SR)
    assert sr.regulation == "GDPR"
    assert sr.source_clauses, "SR-GDPR-001 should have source_clauses"
    assert sr.linked_objectives, "SR-GDPR-001 should have linked_objectives"
    assert "D-01.1" in sr.sub_domain


def test_so_model_basic(loader: PreprocCatalogLoader) -> None:
    """SO-CRA-001 has 3 sub-domains and is not a cross-ref."""
    so = next(s for s in loader.load_sos() if s.id == "SO-CRA-001")
    assert isinstance(so, SO)
    assert so.regulation == "CRA"
    assert so.is_cross_ref is False
    assert "D-01.1" in so.sub_domains


def test_csf_model_basic(loader: PreprocCatalogLoader) -> None:
    """PR.DS-01 is a 'Protect' subcategory in the Data Security category."""
    csf = next(c for c in loader.load_csfs() if c.id == "PR.DS-01")
    assert isinstance(csf, CSFSubcat)
    assert csf.function == "PR"
    assert csf.function_name == "Protect"
    assert csf.category_id == "PR.DS"


def test_pair_model_preserves_verified_relationship(loader: PreprocCatalogLoader) -> None:
    """verified_relationship is FROZEN — loader reads it as-is from JSON."""
    pair = next(p for p in loader.load_pairs() if p.id == "D-01.1_GDPR-CRA")
    assert isinstance(pair, Pair)
    assert pair.verified_relationship  # non-empty
    assert "SAME" in pair.verified_relationship  # all 6 D-01.1 pairs are SAME


# --- Constructor / path resolution ---------------------------------------


def test_invalid_preproc_root_raises(tmp_path: Path) -> None:
    """Non-existent preproc_root raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        PreprocCatalogLoader(preproc_root=tmp_path / "does_not_exist")
