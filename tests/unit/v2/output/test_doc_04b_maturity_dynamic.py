"""CORR-107 tests for dynamic maturity from DOC04 readiness.

Before this contract, Doc 04b's maturity-by-domain table was static per
tier - every domain painted the tier-floor value (MICRO=1) regardless
of what DOC04 said. These tests pin the new bridge behaviour:
- All NO -> empty overrides (no behavioural change vs legacy)
- Mixed (case1-tinytask as-is) -> variance > 0; D-04 lifts above the floor
- Empty state / non-mapping -> no crash, empty override
- Explicit overrides win over derived (humans override heuristics)
"""

from __future__ import annotations

from typing import Any

import pytest

from aegis_phase1.v2.output.doc_04b import (
    _dynamic_maturity_from_readiness,
    _merged_maturity_overrides,
)


def _full_readiness(value: str = "NO") -> dict[str, str]:
    d: dict[str, str] = {
        "ciso": value, "dpo": value, "information_security_policy": value,
        "risk_assessment": value, "incident_response": value,
        "business_continuity": value, "backup": value,
        "access_control": value, "vulnerability_management": value,
        "third_party_risk": value, "security_awareness": value,
        "audit_logging": value,
    }
    return d


def _case1_readiness() -> dict[str, str]:
    d: dict[str, str] = {
        "ciso": "NO", "dpo": "NO",
        "information_security_policy": "PARTIAL",
        "risk_assessment": "NO",
        "incident_response": "PARTIAL",
        "business_continuity": "NO",
        "backup": "YES",
        "access_control": "PARTIAL",
        "vulnerability_management": "PARTIAL",
        "third_party_risk": "NO",
        "security_awareness": "NO",
        "audit_logging": "PARTIAL",
    }
    return d


def test_all_no_returns_empty_overrides():
    """Legacy behaviour preserved: NO answers don't trigger overrides."""
    state: dict[str, Any] = {"implementation_readiness": _full_readiness("NO")}
    assert _merged_maturity_overrides(state) == {}


def test_case1_tinytask_lifts_d04_above_floor():
    """case1-tinytask has backup=YES + incident_response=PARTIAL +
    information_security_policy=PARTIAL + access_control=PARTIAL +
    vulnerability_management=PARTIAL + audit_logging=PARTIAL.
    Expected lifts: D-04=2, D-03=1, D-09=1, D-02=1, D-10=1.
    """
    state: dict[str, Any] = {"implementation_readiness": _case1_readiness()}
    result = _merged_maturity_overrides(state)
    # Variance must now be > 0 (was 0 before this contract).
    assert len(result) > 0
    # D-04 gets the most lift (incident_response=PARTIAL + backup=YES).
    assert result["D-04"] == 2
    # D-03, D-02, D-09, D-10 each get +1 from PARTIAL deltas.
    assert result["D-03"] == 1
    assert result["D-02"] == 1
    assert result["D-09"] == 1
    assert result["D-10"] == 1


def test_all_yes_mature_profile():
    """Fully mature profile should accumulate multiple deltas per domain."""
    state: dict[str, Any] = {"implementation_readiness": _full_readiness("YES")}
    result = _merged_maturity_overrides(state)
    assert result["D-09"] >= 1
    assert result["D-04"] >= 2
    # Variance strictly > 0 (sanity).
    assert len(set(result.values())) >= 2


def test_empty_state_does_not_crash():
    """Defensive: state missing the key, or empty readiness, must not crash."""
    assert _merged_maturity_overrides({}) == {}
    assert _merged_maturity_overrides({"unrelated_key": "value"}) == {}
    assert _merged_maturity_overrides({"implementation_readiness": None}) == {}
    assert _merged_maturity_overrides(
        {"implementation_readiness": "not_a_dict"}
    ) == {}


def test_explicit_override_wins_over_derived():
    """Human-explicit overrides (state["security_posture_overrides"])
    win over heuristic-derived values."""
    state: dict[str, Any] = {
        "implementation_readiness": _case1_readiness(),
        # Human says D-04 should be 4 (override of override).
        "security_posture_overrides": {"D-04": 4},
    }
    result = _merged_maturity_overrides(state)
    assert result["D-04"] == 4


def test_dynamic_function_returns_floats():
    """The raw dynamic function returns floats, not int-rounded. The
    merge function is what rounds."""
    state: dict[str, Any] = {"implementation_readiness": _case1_readiness()}
    raw = _dynamic_maturity_from_readiness(state)
    # D-04 should have incident_response=PARTIAL (+0.5) + backup=YES (+1.0)
    # = 1.5 floats (rounded to 2 by the merge).
    assert raw["D-04"] == pytest.approx(1.5)


def test_regression_legacy_behaviour_preserved_for_zero_readiness():
    """No readiness data -> empty overrides -> render uses tier floor
    exclusively. This is the backwards-compatibility case."""
    state: dict[str, Any] = {"company_context": {"legal_structure": "Private Limited Company"}}
    assert _merged_maturity_overrides(state) == {}
