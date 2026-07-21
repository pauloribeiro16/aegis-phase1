"""CORR-038-T1 tests: ApplicabilityContext + build_… factory + compute helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aegis_phase1.v2.context.applicability_context import (
    ApplicabilityContext,
    DeclarationGap,
    Tier,
    _compute_applicable_regs,
    _compute_declaration_gaps,
    _estimate_tier,
    build_applicability_context,
)


# ---------------------------------------------------------------------------
# _compute_applicable_regs
# ---------------------------------------------------------------------------


def test_compute_applicable_regs_gdpr_cra_only() -> None:
    """processes_personal_data + places_digital_products_eu → GDPR + CRA only."""
    out = _compute_applicable_regs(
        {
            "processes_personal_data": True,
            "places_digital_products_eu": True,
        }
    )
    assert out == ["CRA", "GDPR"]


def test_compute_applicable_regs_all_five_when_all_predicates_true() -> None:
    """All 5 predicates True → all 5 regulations, sorted."""
    out = _compute_applicable_regs(
        {
            "processes_personal_data": True,
            "places_digital_products_eu": True,
            "nis2_sector": "energy",
            "dora_financial_entity": True,
            "aiact_high_risk_system": True,
        }
    )
    assert out == ["AI_Act", "CRA", "DORA", "GDPR", "NIS2"]


def test_compute_applicable_regs_empty_when_all_predicates_false() -> None:
    """No predicates True → no applicable regs."""
    out = _compute_applicable_regs({})
    assert out == []


# ---------------------------------------------------------------------------
# _compute_declaration_gaps
# ---------------------------------------------------------------------------


def test_declaration_gap_detected_when_mismatch() -> None:
    """Mismatch between computed and declared → DeclarationGap present."""
    gaps = _compute_declaration_gaps(["GDPR"], ["GDPR", "CRA"])
    assert len(gaps) == 1
    g = gaps[0]
    assert isinstance(g, DeclarationGap)
    assert g.regulation == "CRA"
    assert g.direction == "declared_not_computed"
    assert g.computed is False
    assert g.declared is True


def test_declaration_gap_empty_when_match() -> None:
    """Match between computed and declared → no gaps."""
    gaps = _compute_declaration_gaps(["GDPR", "CRA"], ["CRA", "GDPR"])
    assert gaps == []


# ---------------------------------------------------------------------------
# _estimate_tier
# ---------------------------------------------------------------------------


def test_tier_low_for_micro_with_few_regs() -> None:
    """MICRO scale with 1-2 regs → LOW."""
    assert _estimate_tier({"scale": "MICRO"}, 1) == Tier.LOW
    assert _estimate_tier({"scale": "MICRO"}, 2) == Tier.LOW


def test_tier_high_for_large_with_many_regs() -> None:
    """LARGE scale OR 3+ regs → HIGH."""
    assert _estimate_tier({"scale": "LARGE"}, 3) == Tier.HIGH
    assert _estimate_tier({"scale": "MEDIUM"}, 5) == Tier.HIGH
    assert _estimate_tier({"scale": "MICRO"}, 3) == Tier.HIGH  # 3+ regs override


# ---------------------------------------------------------------------------
# build_applicability_context
# ---------------------------------------------------------------------------


def test_applicability_context_from_case1_state_matches_canonical(
    case1_v2_state: dict,
) -> None:
    """Build from real case1 v2 state: applicable = {GDPR, CRA}, tier = LOW."""
    ctx = build_applicability_context(case1_v2_state)
    assert isinstance(ctx, ApplicabilityContext)
    assert ctx.applicable_regs == ["CRA", "GDPR"]
    assert ctx.declared_applicable_regs == ["CRA", "GDPR"]
    assert ctx.declaration_gaps == []
    assert ctx.tier == "LOW"
    assert ctx.company_facts["employees"] == 8
    assert ctx.company_facts["revenue_eur"] == 2_000_000


def test_applicability_context_to_dict_is_json_serializable(
    case1_v2_state: dict,
) -> None:
    """to_dict() returns a JSON-serializable dict."""
    import json

    ctx = build_applicability_context(case1_v2_state)
    d = ctx.to_dict()
    # json.dumps must not raise
    json.dumps(d)
    # Spot-check keys
    assert "applicable_regs" in d
    assert "tier" in d
    assert d["tier"] == "LOW"
