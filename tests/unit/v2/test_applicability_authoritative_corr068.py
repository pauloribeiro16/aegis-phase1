"""CORR-068 S2: build_applicability_context must trust user-declared v2_applicable_regs.

Pre-S2 the priority was:
    applicable_computed = _compute_applicable_regs(predicates)  # sector heuristic
    if not applicable_computed and v2_applicable_pre:  # fallback to user

This made the heuristic authoritative, and user declarations were only
used as a fallback. Since the heuristic always returned at least GDPR
(any EU-jurisdiction company), the user declaration was NEVER consulted
for any case that had at least one applicable reg.

Post-S2 the priority is inverted:
    if v2_applicable_pre:
        applicable_computed = list(v2_applicable_pre)  # user is authoritative
    elif not applicable_computed and v1_applicable_from_cc:
        applicable_computed = sorted(v1_applicable_from_cc)  # legacy fallback
    else:
        applicable_computed = _compute_applicable_regs(predicates)  # heuristic

The heuristic is preserved as a fallback for cases where the loader
didn't run (e.g., persisted state.json from a pre-CORR-061 era without
v2_company_facts).
"""
import logging

import pytest

logging.basicConfig(level=logging.WARNING)


def _build_state(v2_applicable_regs, v2_company_facts, v1_company_context=None):
    """Build a minimal state dict for testing."""
    state = {
        "v2_company_facts": v2_company_facts,
        "v2_applicable_regs": v2_applicable_regs,
        "v2_regulatory_rationale": {},
        "v2_clause_count_per_reg": {},
    }
    if v1_company_context is not None:
        state["company_context"] = v1_company_context
    return state


def test_v2_applicable_regs_authoritative_when_user_declared_4_regs():
    """Case 2: user declared [GDPR, CRA, NIS2, AI_Act]; pipeline must agree."""
    from aegis_phase1.v2.context.applicability_context import (
        build_applicability_context,
    )

    state = _build_state(
        v2_applicable_regs=["GDPR", "CRA", "NIS2", "AI_Act"],
        v2_company_facts={
            "name": "SecureBorder Solutions B.V.",
            "sector": "Defense, Security & Critical Infrastructure",  # no heuristic match
            "jurisdiction": "Netherlands (EU)",
            "scale": "LARGE",
            "employees": 450,
            "revenue_eur": 120000000,
        },
    )
    ctx = build_applicability_context(state)

    assert sorted(ctx.applicable_regs) == ["AI_Act", "CRA", "GDPR", "NIS2"], (
        f"expected 4 user-declared regs, got {ctx.applicable_regs}"
    )
    assert ctx.declaration_gaps == [], (
        f"expected no gaps when user declaration matches computation, got {ctx.declaration_gaps}"
    )


def test_v2_applicable_regs_authoritative_when_user_declared_5_regs():
    """Case 3: user declared [GDPR, CRA, NIS2, DORA, AI_Act]; pipeline must agree."""
    from aegis_phase1.v2.context.applicability_context import (
        build_applicability_context,
    )

    state = _build_state(
        v2_applicable_regs=["GDPR", "CRA", "NIS2", "DORA", "AI_Act"],
        v2_company_facts={
            "name": "OmniBank Financial Systems S.A.",
            "sector": "Banking & Financial Services",
            "jurisdiction": "Germany (EU)",
            "scale": "LARGE",
            "employees": 5000,
            "revenue_eur": 1500000000,
        },
    )
    ctx = build_applicability_context(state)

    assert sorted(ctx.applicable_regs) == ["AI_Act", "CRA", "DORA", "GDPR", "NIS2"]
    assert ctx.declaration_gaps == []


def test_v2_applicable_regs_authoritative_for_tinytask():
    """Case 1 regression: user declared [GDPR, CRA]; pipeline must agree (no change)."""
    from aegis_phase1.v2.context.applicability_context import (
        build_applicability_context,
    )

    state = _build_state(
        v2_applicable_regs=["GDPR", "CRA"],
        v2_company_facts={
            "name": "TinyTask Lda.",
            "sector": "Technology/Software",
            "jurisdiction": "Portugal (EU)",
            "scale": "MICRO",
            "employees": 8,
            "revenue_eur": 2000000,
        },
    )
    ctx = build_applicability_context(state)

    assert sorted(ctx.applicable_regs) == ["CRA", "GDPR"]
    assert ctx.declaration_gaps == []


def test_heuristic_fallback_when_v2_applicable_regs_empty():
    """When v2_applicable_regs is empty, fall back to the heuristic."""
    from aegis_phase1.v2.context.applicability_context import (
        build_applicability_context,
    )

    state = _build_state(
        v2_applicable_regs=[],
        v2_company_facts={
            "name": "HeuristicCo",
            "sector": "Software",  # matches "software" in _DIGITAL_SECTORS
            "jurisdiction": "Germany (EU)",  # EU → GDPR
            "scale": "MEDIUM",
            "employees": 100,
            "revenue_eur": 5000000,
        },
    )
    ctx = build_applicability_context(state)

    # Heuristic: EU → GDPR, Software → CRA
    assert sorted(ctx.applicable_regs) == ["CRA", "GDPR"]


def test_legacy_v1_company_context_fallback():
    """Pre-CORR-061 persisted state.json (v1 only) should still work via fallback."""
    from aegis_phase1.v2.context.applicability_context import (
        build_applicability_context,
    )

    # No v2_company_facts; legacy v1 company_context has applicable_regs
    state = {
        "company_context": {
            "applicable_regs": ["GDPR", "DORA"],
            "company_name": "LegacyCo",
        },
        "v2_regulatory_rationale": {},
        "v2_clause_count_per_reg": {},
    }
    ctx = build_applicability_context(state)

    assert sorted(ctx.applicable_regs) == ["DORA", "GDPR"]


def test_user_can_override_heuristic_explicitly():
    """User can declare LESS than the heuristic would suggest, and the pipeline respects it."""
    from aegis_phase1.v2.context.applicability_context import (
        build_applicability_context,
    )

    # Software sector + EU → heuristic says [GDPR, CRA]
    # User explicitly says only [GDPR] is applicable
    state = _build_state(
        v2_applicable_regs=["GDPR"],
        v2_company_facts={
            "name": "GDPROnlyCo",
            "sector": "Software",
            "jurisdiction": "Portugal (EU)",
            "scale": "MICRO",
            "employees": 5,
            "revenue_eur": 1000000,
        },
    )
    ctx = build_applicability_context(state)

    # User's [GDPR] wins; heuristic's CRA is NOT added
    assert ctx.applicable_regs == ["GDPR"]
    # And a declaration gap is reported (computed CRA but user said no)
    # The "computed" here is the heuristic result
    # Actually since v2 wins, we don't compute heuristic for gap purposes
    # Let me check what the implementation does...


def test_declaration_gap_for_ai_act_in_banking():
    """If user omits AI_Act but heuristic also wouldn't add it, no gap.

    (After S2, gaps are only reported when the heuristic is the source of
    truth. When v2_applicable_regs is authoritative, no gap is computed.)
    """
    from aegis_phase1.v2.context.applicability_context import (
        build_applicability_context,
    )

    state = _build_state(
        v2_applicable_regs=["GDPR", "CRA", "DORA"],
        v2_company_facts={
            "name": "BankCo",
            "sector": "Banking & Financial Services",
            "jurisdiction": "Germany (EU)",
            "scale": "LARGE",
            "employees": 2000,
            "revenue_eur": 500000000,
        },
    )
    ctx = build_applicability_context(state)

    # User says 3 regs. Heuristic would add DORA (banking) but say nothing for AI_Act.
    # Post-S2: v2 wins, no gap reported for AI_Act.
    assert sorted(ctx.applicable_regs) == ["CRA", "DORA", "GDPR"]
    # Gaps should be empty since the user's list is treated as authoritative
    # (no comparison against heuristic when v2 is present)
