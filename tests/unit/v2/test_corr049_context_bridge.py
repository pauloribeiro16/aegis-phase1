"""CORR-049-T6: context bridge — fix dead-code threading.

Pre-CORR-049 the orchestrator's _build_company_context returned a flat
9-key dict. _extract_corr047_fields in inputs.py tried 3 paths to find
the 4 CORR-047 fields but none matched the flat shape, so the fields
were silently dropped before reaching the prompt.

Post-CORR-049 _build_company_context embeds the full v2 CompanyProfile
under the ``v2_company_profile`` key (Path 2) and exposes the 4 fields
as top-level keys (Path 3). Both paths now resolve.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make src/ importable
sys.path.insert(0, "src")

from aegis_phase1.v2.domain.inputs import (
    _extract_corr047_fields,
    _project_company_context,
)
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader


@pytest.fixture(scope="module")
def profile():
    """Real CompanyProfile for case1-tinytask (uses CORR-047 4 new fields)."""
    return CaseProfileLoader(case_path=Path("cases/case1-tinytask")).load()


def test_corr047_fields_reach_prompt_after_bridge(profile) -> None:
    """CORR-049-T6: end-to-end — after _build_company_context fix, the
    4 CORR-047 fields must appear in the projected context dict.
    """
    # Simulate what _build_company_context now produces: flat CompanyContext
    # dict + v2_company_profile + 4 top-level CORR-047 fields.
    base = {
        "company_name": profile.company.name,
        "sector": profile.company.sector,
        "jurisdiction": profile.company.jurisdiction,
        "employees": profile.company.employees,
        "revenue": float(profile.company.revenue_eur),
        "scale": profile.company.scale,
        "applicable_regs": [],
        "complexity_tier": "LOW",
        "security_fte": profile.company.security_fte or 0.0,
        "tech_stack": list(profile.company.tech_stack or []),
    }
    base["v2_company_profile"] = profile
    base["implementation_readiness"] = (
        profile.implementation_readiness.model_dump()
        if profile.implementation_readiness
        else None
    )
    base["regulatory_classification"] = (
        profile.regulatory_classification.model_dump()
        if profile.regulatory_classification
        else None
    )
    base["role_matrix"] = (
        profile.role_matrix.model_dump()
        if profile.role_matrix
        else None
    )
    base["regulatory_interactions"] = (
        profile.regulatory_interactions.model_dump()
        if profile.regulatory_interactions
        else None
    )

    projected = _project_company_context(base)
    assert "implementation_readiness" in projected, (
        f"IR missing from projected context; got keys: {sorted(projected.keys())}"
    )
    assert "regulatory_classification" in projected, "RegClass missing"
    assert "role_matrix" in projected, "RoleMatrix missing"
    assert "regulatory_interactions" in projected, "Interactions missing"
    # Verify values are real (not None)
    assert projected["implementation_readiness"] is not None
    assert projected["regulatory_classification"] is not None
    assert projected["role_matrix"] is not None
    assert projected["regulatory_interactions"] is not None


def test_extract_corr047_fields_path2_works(profile) -> None:
    """Direct unit test of _extract_corr047_fields Path 2 (v2_company_profile)."""
    # The 048 helper signature is (ctx) returning a dict of all 4 fields.
    # We test by giving it a dict with v2_company_profile and verifying
    # the helper returns the 4 fields.
    ctx = {"v2_company_profile": profile}
    out = _extract_corr047_fields(ctx)
    # Each field should be present in the output
    assert "implementation_readiness" in out, (
        f"Path 2 failed; got keys: {sorted(out.keys())}"
    )
    assert "regulatory_classification" in out
    assert "role_matrix" in out
    assert "regulatory_interactions" in out
    # Values are real (not None)
    assert out["implementation_readiness"] is not None
    # Value is a dict (serialised)
    assert isinstance(out["implementation_readiness"], dict)
    # Spot-check IR-01 value
    assert "ciso" in out["implementation_readiness"]
