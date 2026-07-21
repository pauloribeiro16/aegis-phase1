"""Tests for CaseProfileLoader (CORR-037-T2).

Reference: execution/CONTRACT-037.md §T2 / §Risks.
Case under test: cases/case1-tinytask (canonical, post-CORR-036 alignment).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis_phase1.v2.loader.case_profile import (
    ApplicabilityPredicates,
    CaseProfileLoader,
    CompanyProfile,
    CompanyFacts,
    RegulatoryFacts,
)


@pytest.fixture(scope="module")
def ctx() -> CompanyProfile:
    """Module-scoped fixture: shared CompanyProfile for case1-tinytask."""
    return CaseProfileLoader(case_path=Path("cases/case1-tinytask")).load()


# --- G3 (extended): canonical company facts (post-CORR-036) ----------------


def test_company_name_canonical(ctx: CompanyProfile) -> None:
    """Post-CORR-036 invariant: name is 'TinyTask Lda.' (not 'TinyTask SaaS')."""
    assert ctx.company.name == "TinyTask Lda."
    assert ctx.company.legal_structure == "Private Limited Company (Lda.)"


def test_company_size_micro(ctx: CompanyProfile) -> None:
    """Post-CORR-036: 8 employees / 2M EUR / MICRO scale."""
    assert ctx.company.employees == 8
    assert ctx.company.revenue_eur == 2000000
    assert ctx.company.scale == "MICRO"


def test_company_jurisdiction(ctx: CompanyProfile) -> None:
    assert "Portugal" in ctx.company.jurisdiction
    assert "EU" in ctx.company.jurisdiction


def test_company_security_fte(ctx: CompanyProfile) -> None:
    """0.85 FTE per classification.yaml."""
    assert ctx.company.security_fte == 0.85


# --- Applicability predicates (derived from applicable_regs) --------------


def test_applicability_predicates_gdpr_cra(ctx: CompanyProfile) -> None:
    """GDPR + CRA applicable → corresponding predicates True."""
    assert ctx.applicability_predicates.processes_personal_data is True
    assert ctx.applicability_predicates.places_digital_products_eu is True


def test_applicability_predicates_nis2_dora_aiact(ctx: CompanyProfile) -> None:
    """NIS2 / DORA / AI_Act NOT applicable → predicates False / empty."""
    assert ctx.applicability_predicates.nis2_sector == ""
    assert ctx.applicability_predicates.dora_financial_entity is False
    assert ctx.applicability_predicates.aiact_high_risk_system is False


# --- Computed applicable_regs vs declared ----------------------------------


def test_applicable_regs_computed(ctx: CompanyProfile) -> None:
    """Computed from classification.yaml#applicable_regulations (sorted)."""
    assert set(ctx.applicable_regs) == {"GDPR", "CRA"}
    # sorted
    assert ctx.applicable_regs == sorted(ctx.applicable_regs)


def test_declared_applicable_regs(ctx: CompanyProfile) -> None:
    """Declared from regulatory/applicability.yaml (sorted)."""
    assert set(ctx.declared_applicable_regs) == {"GDPR", "CRA"}


def test_no_declaration_gaps(ctx: CompanyProfile) -> None:
    """TinyTask: declared matches computed (post-CORR-036 alignment)."""
    assert ctx.declaration_gaps == []


# --- Regulatory facts (clause counts per reg for SP-C parity) --------------


def test_obligated_party_per_reg(ctx: CompanyProfile) -> None:
    assert ctx.regulatory.obligated_party_per_reg.get("GDPR") == "controller"
    assert ctx.regulatory.obligated_party_per_reg.get("CRA") == "manufacturer"


def test_clause_count_per_reg(ctx: CompanyProfile) -> None:
    """Per applicability.yaml: GDPR=28, CRA=26 — used by SP-C parity checks."""
    assert ctx.regulatory.clause_count_per_reg.get("GDPR") == 28
    assert ctx.regulatory.clause_count_per_reg.get("CRA") == 26


def test_regulatory_non_applicable(ctx: CompanyProfile) -> None:
    """NIS2, DORA, AI_Act are non-applicable."""
    assert set(ctx.regulatory.non_applicable) == {"NIS2", "DORA", "AI_Act"}


# --- Business goals & stakeholders (Full tier) -----------------------------


def test_business_goals_count(ctx: CompanyProfile) -> None:
    """BG-01..BG-05 per business_goals.yaml."""
    assert len(ctx.business_goals) == 5
    ids = {g.id for g in ctx.business_goals}
    assert ids == {"BG-01", "BG-02", "BG-03", "BG-04", "BG-05"}


def test_business_goals_have_priority(ctx: CompanyProfile) -> None:
    bg1 = next(g for g in ctx.business_goals if g.id == "BG-01")
    assert bg1.priority == "HIGH"


def test_stakeholders_count(ctx: CompanyProfile) -> None:
    """SH-01..SH-07 per stakeholders.yaml."""
    assert len(ctx.stakeholders) == 7
    ids = {s.id for s in ctx.stakeholders}
    assert ids == {f"SH-0{i}" for i in range(1, 8)}


def test_stakeholder_responsibilities(ctx: CompanyProfile) -> None:
    dpo = next(s for s in ctx.stakeholders if s.role.startswith("Data Protection Officer"))
    assert "gdpr_compliance" in dpo.responsibilities


# --- Architecture (5 files) ------------------------------------------------


def test_architecture_systems(ctx: CompanyProfile) -> None:
    """SYS-01..SYS-05 per systems.yaml."""
    assert len(ctx.architecture.systems) == 5


def test_architecture_auth_systems(ctx: CompanyProfile) -> None:
    """AS-01..AS-03 per auth_systems.yaml."""
    assert len(ctx.architecture.auth_systems) == 3


def test_architecture_other_sections_present(ctx: CompanyProfile) -> None:
    """Other 3 architecture YAMLs loaded as raw lists."""
    # We don't assert counts (case1 may have variable counts), just that
    # the lists exist (not None) and are lists.
    assert isinstance(ctx.architecture.cloud_services, list)
    assert isinstance(ctx.architecture.data_flows, list)
    assert isinstance(ctx.architecture.data_stores, list)


# --- Round-trip / cache ----------------------------------------------------


def test_load_is_idempotent(ctx: CompanyProfile) -> None:
    """A second loader instance should produce an equal (but distinct) context."""
    other = CaseProfileLoader(case_path=Path("cases/case1-tinytask")).load()
    assert other == ctx
    assert other is not ctx  # distinct objects


def test_invalid_case_path_raises(tmp_path: Path) -> None:
    """Non-existent case_path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        CaseProfileLoader(case_path=tmp_path / "nonexistent_case")


def test_case_without_input_dir_raises(tmp_path: Path) -> None:
    """case_path exists but lacks input/ subdir raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        CaseProfileLoader(case_path=tmp_path)


# --- Type sanity -----------------------------------------------------------


def test_models_are_pydantic(ctx: CompanyProfile) -> None:
    """All sub-models are Pydantic v2 instances (sanity check)."""
    assert isinstance(ctx, CompanyProfile)
    assert isinstance(ctx.company, CompanyFacts)
    assert isinstance(ctx.applicability_predicates, ApplicabilityPredicates)
    assert isinstance(ctx.regulatory, RegulatoryFacts)
