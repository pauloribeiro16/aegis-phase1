"""Tests for ``aegis_phase1.v2.loader.common_loader``.

Regression coverage for the section-state leak bug where rows in
later analysis sections (e.g., negative applicability checklists)
containing both a regulation keyword and ``YES`` triggered false
appends to ``applicable_regs``.
"""

from aegis_phase1.v2.loader.common_loader import CommonLoader

CASE = "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/02_CASES/Case_01_TinyTask_SaaS"


def test_applicable_regs_only_gdpr_cra():
    """Verify the parser correctly extracts only GDPR + CRA as applicable."""
    cl = CommonLoader()
    result = cl.load(CASE)
    ctx = result["company_context"]
    assert ctx is not None
    assert "GDPR" in ctx.applicable_regs
    assert "CRA" in ctx.applicable_regs
    assert "NIS2" not in ctx.applicable_regs, f"got {ctx.applicable_regs}"
    assert "AI Act" not in ctx.applicable_regs, f"got {ctx.applicable_regs}"


def test_applicable_regs_count_is_exactly_two():
    """Only GDPR and CRA are applicable for TinyTask SaaS."""
    cl = CommonLoader()
    result = cl.load(CASE)
    ctx = result["company_context"]
    assert ctx is not None
    assert len(ctx.applicable_regs) == 2, f"got {ctx.applicable_regs}"


def test_other_company_context_fields_intact():
    """The refactor must preserve all other parsed fields."""
    cl = CommonLoader()
    result = cl.load(CASE)
    ctx = result["company_context"]
    assert ctx is not None
    assert ctx.company_name == "TinyTask Lda."
    assert ctx.sector == "Technology / Software"
    assert ctx.jurisdiction == "Portugal (EU)"
    assert ctx.employees == 8
    assert ctx.scale == "Micro-enterprise"
    assert "Cloud" in " ".join(ctx.tech_stack)
