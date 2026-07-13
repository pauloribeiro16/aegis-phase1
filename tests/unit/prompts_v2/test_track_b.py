"""Tests for TrackB deterministic tier assignment.

Covers proportionality_model.md section 5 (decision table), section 5.2
(SHOULD/COULD drop-one-tier + MICRO low-FTE DEFERRED), and section 5.3
(floor rule: MUST never below MINIMAL).

Test plan:
  - Imports + decision-table shape
  - Section 5.1 MUST table entries (10 (S, I) combinations)
  - Section 5.2 SHOULD/COULD drop-one-tier
  - Section 5.2 DEFERRED special case (MICRO + low FTE)
  - Section 5.3 floor rule (MUST never below MINIMAL)
  - Input validation (invalid scale / inheritability / priority)
  - assign_all: returns profile with tier + 5 attributes per sd
  - summarize: tier distribution + active/deferred counts
  - Case 01 expected distribution: 31 LIGHTWEIGHT + 5 MINIMAL + 1 DEFERRED
"""

from __future__ import annotations

import pytest

from aegis_phase1.prompts_v2.track_b import (
    _INHERIT_RANK,
    _MUST_TABLE,
    _SCALE_RANK,
    _TIER_NAMES,
    TrackB,
)

# ─── Imports + table shape ────────────────────────────────────────────


def test_track_b_imports():
    from aegis_phase1.prompts_v2.track_b import TrackB as TbClass

    assert callable(TbClass)


def test_track_b_module_exports():
    """TrackB is exported from aegis_phase1.prompts_v2.__init__."""
    from aegis_phase1.prompts_v2 import TrackB as TbFromInit

    assert TbFromInit is TrackB


def test_must_table_shape():
    """The MUST table has exactly 10 (S, I) entries (5 scales x 2 inherit)."""
    assert len(_MUST_TABLE) == 10
    assert len(_SCALE_RANK) == 5
    assert len(_INHERIT_RANK) == 2
    # All ranks in MUST table are non-negative (>= MINIMAL = 0).
    assert all(0 <= v <= 3 for v in _MUST_TABLE.values())


def test_tier_names_covers_all_ranks():
    """_TIER_NAMES covers MINIMAL/LIGHTWEIGHT/STANDARD/RIGOROUS/DEFERRED ranks."""
    assert _TIER_NAMES[0] == "MINIMAL"
    assert _TIER_NAMES[1] == "LIGHTWEIGHT"
    assert _TIER_NAMES[2] == "STANDARD"
    assert _TIER_NAMES[3] == "RIGOROUS"
    assert _TIER_NAMES[-1] == "DEFERRED"


# ─── Section 5.1 MUST table entries ───────────────────────────────────


def test_assign_tier_micro_inheritable_must():
    """Section 5.1: MICRO + INHERITABLE + MUST = MINIMAL."""
    tb = TrackB()
    assert tb.assign_tier("MICRO", "INHERITABLE", "MUST") == "MINIMAL"


def test_assign_tier_micro_build_must():
    """Section 5.1: MICRO + BUILD_REQUIRED + MUST = LIGHTWEIGHT."""
    tb = TrackB()
    assert tb.assign_tier("MICRO", "BUILD_REQUIRED", "MUST") == "LIGHTWEIGHT"


def test_assign_tier_small_inheritable_must():
    """Section 5.1: SMALL + INHERITABLE + MUST = LIGHTWEIGHT."""
    tb = TrackB()
    assert tb.assign_tier("SMALL", "INHERITABLE", "MUST") == "LIGHTWEIGHT"


def test_assign_tier_small_build_must():
    """Section 5.1: SMALL + BUILD_REQUIRED + MUST = STANDARD."""
    tb = TrackB()
    assert tb.assign_tier("SMALL", "BUILD_REQUIRED", "MUST") == "STANDARD"


def test_assign_tier_medium_inheritable_must():
    """Section 5.1: MEDIUM + INHERITABLE + MUST = LIGHTWEIGHT."""
    tb = TrackB()
    assert tb.assign_tier("MEDIUM", "INHERITABLE", "MUST") == "LIGHTWEIGHT"


def test_assign_tier_medium_build_must():
    """Section 5.1: MEDIUM + BUILD_REQUIRED + MUST = STANDARD."""
    tb = TrackB()
    assert tb.assign_tier("MEDIUM", "BUILD_REQUIRED", "MUST") == "STANDARD"


def test_assign_tier_large_inheritable_must():
    """Section 5.1: LARGE + INHERITABLE + MUST = STANDARD."""
    tb = TrackB()
    assert tb.assign_tier("LARGE", "INHERITABLE", "MUST") == "STANDARD"


def test_assign_tier_large_build_must():
    """Section 5.1: LARGE + BUILD_REQUIRED + MUST = RIGOROUS."""
    tb = TrackB()
    assert tb.assign_tier("LARGE", "BUILD_REQUIRED", "MUST") == "RIGOROUS"


def test_assign_tier_max_inheritable_must():
    """Section 5.1: MAX + INHERITABLE + MUST = STANDARD."""
    tb = TrackB()
    assert tb.assign_tier("MAX", "INHERITABLE", "MUST") == "STANDARD"


def test_assign_tier_max_build_must():
    """Section 5.1: MAX + BUILD_REQUIRED + MUST = RIGOROUS."""
    tb = TrackB()
    assert tb.assign_tier("MAX", "BUILD_REQUIRED", "MUST") == "RIGOROUS"


# ─── Section 5.3 floor rule ───────────────────────────────────────────


def test_floor_rule_must_never_below_minimal():
    """Section 5.3: MUST priority never goes below MINIMAL."""
    tb = TrackB()
    rank_map = {"MINIMAL": 0, "LIGHTWEIGHT": 1, "STANDARD": 2, "RIGOROUS": 3}
    for s in ["MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"]:
        for i in ["INHERITABLE", "BUILD_REQUIRED"]:
            tier = tb.assign_tier(s, i, "MUST")
            assert rank_map[tier] >= 0, f"MUST tier {tier} below MINIMAL for ({s}, {i})"


def test_micro_inheritable_must_is_minimal_floor():
    """Section 5.3: the absolute floor is MICRO + INHERITABLE + MUST = MINIMAL."""
    tb = TrackB()
    assert tb.assign_tier("MICRO", "INHERITABLE", "MUST") == "MINIMAL"


# ─── Section 5.2 SHOULD/COULD rules ───────────────────────────────────


def test_should_drop_one_tier():
    """Section 5.2: SHOULD drops one tier vs MUST (non-MICRO-low-FTE)."""
    tb = TrackB()
    # LARGE + BUILD_REQUIRED + MUST = RIGOROUS (rank 3)
    # SHOULD should drop to STANDARD (rank 2)
    assert tb.assign_tier("LARGE", "BUILD_REQUIRED", "SHOULD", fte=10.0) == "STANDARD"


def test_could_drop_one_tier():
    """Section 5.2: COULD drops one tier vs MUST."""
    tb = TrackB()
    # SMALL + BUILD_REQUIRED + MUST = STANDARD (rank 2)
    # COULD -> LIGHTWEIGHT (rank 1)
    assert tb.assign_tier("SMALL", "BUILD_REQUIRED", "COULD", fte=5.0) == "LIGHTWEIGHT"


def test_should_deferred_micro_low_fte():
    """Section 5.2: MICRO + low FTE + SHOULD = DEFERRED."""
    tb = TrackB()
    # Case 01 has FTE = 0.85
    assert tb.assign_tier("MICRO", "BUILD_REQUIRED", "SHOULD", fte=0.85) == "DEFERRED"


def test_could_deferred_micro_low_fte():
    """Section 5.2: MICRO + low FTE + COULD = DEFERRED."""
    tb = TrackB()
    assert tb.assign_tier("MICRO", "INHERITABLE", "COULD", fte=0.5) == "DEFERRED"


def test_micro_high_fte_does_not_defer():
    """Section 5.2: MICRO + FTE > 1.0 -> SHOULD/COULD drops one tier (NOT DEFERRED)."""
    tb = TrackB()
    # MICRO + BUILD_REQUIRED + MUST = LIGHTWEIGHT
    # FTE > 1.0 should drop to MINIMAL, not defer.
    assert tb.assign_tier("MICRO", "BUILD_REQUIRED", "SHOULD", fte=1.5) == "MINIMAL"


def test_should_floor_at_minimal_when_dropping():
    """Section 5.2 + 5.3: SHOULD/COULD can drop down to MINIMAL but no further."""
    tb = TrackB()
    # MICRO + INHERITABLE + MUST = MINIMAL (rank 0)
    # Dropping once would go to rank -1, but floor rule keeps it at MINIMAL.
    assert tb.assign_tier("MICRO", "INHERITABLE", "SHOULD", fte=10.0) == "MINIMAL"


def test_deferred_only_for_should_or_could():
    """Section 5.3: DEFERRED is unreachable for MUST priority."""
    tb = TrackB()
    # For all S/I/FTE combinations, MUST should never produce DEFERRED.
    for s in ["MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"]:
        for i in ["INHERITABLE", "BUILD_REQUIRED"]:
            for fte in [None, 0.5, 1.0, 5.0]:
                tier = tb.assign_tier(s, i, "MUST", fte=fte)
                assert (
                    tier != "DEFERRED"
                ), f"MUST must not produce DEFERRED for ({s}, {i}, fte={fte})"


# ─── Input validation ────────────────────────────────────────────────


def test_invalid_scale_raises():
    tb = TrackB()
    with pytest.raises(ValueError):
        tb.assign_tier("INVALID", "INHERITABLE", "MUST")


def test_invalid_inheritability_raises():
    tb = TrackB()
    with pytest.raises(ValueError):
        tb.assign_tier("MICRO", "INVALID", "MUST")


def test_invalid_priority_raises():
    tb = TrackB()
    with pytest.raises(ValueError):
        tb.assign_tier("MICRO", "INHERITABLE", "INVALID")


def test_assign_all_invalid_scale_raises():
    tb = TrackB()
    with pytest.raises(ValueError):
        tb.assign_all("INVALID", 0.85, {})


# ─── assign_all + summarize ───────────────────────────────────────────


def test_assign_all_returns_profile():
    """assign_all returns per-subdomain dict with tier + 5 attributes."""
    tb = TrackB()
    per_sd = {
        "D-01.1": {"inheritability": "BUILD_REQUIRED", "priority": "MUST"},
        "D-03.1": {"inheritability": "INHERITABLE", "priority": "MUST"},
    }
    profile = tb.assign_all("MICRO", fte=0.85, per_subdomain_input=per_sd)
    assert "D-01.1" in profile
    assert "D-03.1" in profile
    # MICRO + INHERITABLE + MUST = MINIMAL
    assert profile["D-03.1"]["tier"] == "MINIMAL"
    # MICRO + BUILD_REQUIRED + MUST = LIGHTWEIGHT
    assert profile["D-01.1"]["tier"] == "LIGHTWEIGHT"
    # 5 attributes present
    required_attrs = [
        "satisfaction_pattern",
        "evidence_depth",
        "verification_method",
        "ownership",
        "example_controls",
    ]
    for sd_id in profile:
        for attr in required_attrs:
            assert attr in profile[sd_id], f"Missing {attr} in {sd_id}"


def test_assign_all_default_inheritability_and_priority():
    """Missing inputs default to BUILD_REQUIRED + MUST."""
    tb = TrackB()
    profile = tb.assign_all("MICRO", fte=0.85, per_subdomain_input={"D-X": {}})
    assert profile["D-X"]["tier"] == "LIGHTWEIGHT"  # MICRO+BUILD+MUST


def test_assign_all_deferred_has_dash_attributes():
    """DEFERRED tier carries "-" placeholders (non-empty strings)."""
    tb = TrackB()
    profile = tb.assign_all(
        "MICRO",
        fte=0.85,
        per_subdomain_input={
            "D-DEF": {"inheritability": "BUILD_REQUIRED", "priority": "SHOULD"},
        },
    )
    assert profile["D-DEF"]["tier"] == "DEFERRED"
    assert profile["D-DEF"]["satisfaction_pattern"] == "-"
    assert profile["D-DEF"]["evidence_depth"] == "-"
    assert profile["D-DEF"]["ownership"] == "-"


def test_summarize_distribution():
    """summarize returns tier counts."""
    tb = TrackB()
    profile = {
        "D-01.1": {"tier": "LIGHTWEIGHT"},
        "D-01.2": {"tier": "LIGHTWEIGHT"},
        "D-02.1": {"tier": "MINIMAL"},
    }
    summary = tb.summarize(profile)
    assert summary["total_sub_domains"] == 3
    assert summary["tier_distribution"] == {"LIGHTWEIGHT": 2, "MINIMAL": 1}
    assert summary["active_sub_domains"] == 3
    assert summary["deferred_count"] == 0


def test_summarize_with_deferred():
    """summarize correctly counts DEFERRED entries."""
    tb = TrackB()
    profile = {
        "D-A": {"tier": "DEFERRED"},
        "D-B": {"tier": "LIGHTWEIGHT"},
        "D-C": {"tier": "DEFERRED"},
    }
    summary = tb.summarize(profile)
    assert summary["total_sub_domains"] == 3
    assert summary["deferred_count"] == 2
    assert summary["active_sub_domains"] == 1
    assert summary["tier_distribution"]["DEFERRED"] == 2


# ─── Case 01 expected distribution ──────────────────────────────────


def test_case_01_distribution():
    """Case 01 expected: 31 LIGHTWEIGHT + 5 MINIMAL + 1 DEFERRED (37 active)."""
    tb = TrackB()
    # Case 01 (TinyTask SaaS): S=MICRO, FTE=0.85 (per Doc 07b Section 2)
    # 31 LIGHTWEIGHT = MICRO + BUILD_REQUIRED + MUST
    # 5 MINIMAL     = MICRO + INHERITABLE + MUST
    # 1 DEFERRED    = MICRO + BUILD_REQUIRED + SHOULD + fte<=1.0
    per_sd: dict[str, dict[str, str]] = {}
    for i in range(31):
        per_sd[f"D-A.{i}"] = {"inheritability": "BUILD_REQUIRED", "priority": "MUST"}
    for i in range(5):
        per_sd[f"D-B.{i}"] = {"inheritability": "INHERITABLE", "priority": "MUST"}
    per_sd["D-DEFERRED"] = {"inheritability": "BUILD_REQUIRED", "priority": "SHOULD"}

    profile = tb.assign_all("MICRO", fte=0.85, per_subdomain_input=per_sd)
    summary = tb.summarize(profile)

    assert summary["total_sub_domains"] == 37
    assert summary["tier_distribution"].get("LIGHTWEIGHT") == 31
    assert summary["tier_distribution"].get("MINIMAL") == 5
    assert summary["tier_distribution"].get("DEFERRED") == 1
    assert summary["active_sub_domains"] == 36
    assert summary["deferred_count"] == 1


# ─── Phase1Executor integration ──────────────────────────────────────


def test_phase1_executor_default_track_b():
    """Phase1Executor creates a default TrackB() if none is provided."""
    from unittest.mock import MagicMock

    from aegis_phase1.prompts_v2 import Phase1Executor

    pl = MagicMock()

    cl = MagicMock()

    val = MagicMock()
    ll = MagicMock()
    fl = MagicMock()
    ex = Phase1Executor(pl, cl, val, ll, fl)
    assert isinstance(ex.track_b, TrackB)


def test_phase1_executor_accepts_explicit_track_b():
    """Phase1Executor accepts an explicit TrackB instance."""
    from unittest.mock import MagicMock

    from aegis_phase1.prompts_v2 import Phase1Executor

    tb = TrackB()
    pl = MagicMock()
    cl = MagicMock()
    val = MagicMock()
    ll = MagicMock()
    fl = MagicMock()
    ex = Phase1Executor(pl, cl, val, ll, fl, track_b=tb)
    assert ex.track_b is tb


def test_phase1_executor_run_track_b_method():
    """run_track_b returns {profile, summary} for a small input."""
    from unittest.mock import MagicMock

    from aegis_phase1.prompts_v2 import Phase1Executor

    pl = MagicMock()

    cl = MagicMock()

    val = MagicMock()
    ll = MagicMock()
    fl = MagicMock()
    ex = Phase1Executor(pl, cl, val, ll, fl)
    result = ex.run_track_b(
        "MICRO",
        0.85,
        {
            "D-1": {"inheritability": "BUILD_REQUIRED", "priority": "MUST"},
            "D-2": {"inheritability": "INHERITABLE", "priority": "MUST"},
            "D-3": {"inheritability": "BUILD_REQUIRED", "priority": "SHOULD"},
        },
    )
    assert "profile" in result
    assert "summary" in result
    assert result["summary"]["tier_distribution"]["LIGHTWEIGHT"] == 1
    assert result["summary"]["tier_distribution"]["MINIMAL"] == 1
    assert result["summary"]["tier_distribution"]["DEFERRED"] == 1


def test_run_does_not_break_without_track_b_args():
    """run() works as before when track_b params are not provided."""
    from unittest.mock import MagicMock

    from aegis_phase1.prompts_v2 import Phase1Executor

    pl = MagicMock()

    cl = MagicMock()

    val = MagicMock()
    ll = MagicMock()
    fl = MagicMock()
    ex = Phase1Executor(pl, cl, val, ll, fl)
    ex.invoker = MagicMock()
    ex.invoker.invoke.side_effect = [
        # Phase 1B: interpretation
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
        # Phase 1B: rationale
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
        # Phase 1C Map (D-01..D-10) -> 10 invocations
        *[{"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1}] * 10,
        # Phase 1C Reduce: LLM-03
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
        # Phase 1C Reduce: LLM-02
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
    ]
    result = ex.run("Case_01", applicable_regs=["GDPR"])
    assert "case_id" in result
    assert "track_b" not in result  # not computed unless params supplied


def test_run_with_track_b_args_computes_profile():
    """run() computes track_b when scale/fte/per_subdomain are supplied."""
    from unittest.mock import MagicMock

    from aegis_phase1.prompts_v2 import Phase1Executor

    pl = MagicMock()

    cl = MagicMock()

    val = MagicMock()
    ll = MagicMock()
    fl = MagicMock()
    ex = Phase1Executor(pl, cl, val, ll, fl)
    ex.invoker = MagicMock()
    ex.invoker.invoke.side_effect = [
        # Phase 1B: interpretation
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
        # Phase 1B: rationale
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
        # Phase 1C Map (D-01..D-10) -> 10 invocations
        *[{"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1}] * 10,
        # Phase 1C Reduce: LLM-03
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
        # Phase 1C Reduce: LLM-02
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
    ]
    per_sd = {
        "D-A": {"inheritability": "BUILD_REQUIRED", "priority": "MUST"},
        "D-B": {"inheritability": "INHERITABLE", "priority": "MUST"},
    }
    result = ex.run(
        "Case_01",
        applicable_regs=["GDPR"],
        track_b_scale="MICRO",
        track_b_fte=0.85,
        track_b_per_subdomain=per_sd,
    )
    assert "track_b" in result
    assert result["track_b"]["summary"]["tier_distribution"]["LIGHTWEIGHT"] == 1
    assert result["track_b"]["summary"]["tier_distribution"]["MINIMAL"] == 1
    # The computed profile is forwarded to the reduce stage.
    # First two calls are Phase 1B; track_b_profile flows through phase_1c_reduce.
    # The doc07b_profile arg is present in the LLM-03 invocation (3rd group of calls).
    reduce_call = ex.invoker.invoke.call_args_list[12]
    assert "doc07b_profile" in reduce_call.args[1]
    assert reduce_call.args[1]["doc07b_profile"]["D-A"]["tier"] == "LIGHTWEIGHT"


def test_run_precomputed_track_b_profile_takes_precedence():
    """If track_b_profile is supplied directly, run() does not recompute it."""
    from unittest.mock import MagicMock

    from aegis_phase1.prompts_v2 import Phase1Executor

    pl = MagicMock()

    cl = MagicMock()

    val = MagicMock()
    ll = MagicMock()
    fl = MagicMock()
    ex = Phase1Executor(pl, cl, val, ll, fl)
    ex.invoker = MagicMock()
    ex.invoker.invoke.side_effect = [
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
        *[{"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1}] * 10,
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
        {"status": "OK", "parsed_output": {}, "total_latency_ms": 1, "retry_count": 1},
    ]
    # Pass BOTH a precomputed profile and (scale/fte/per_sd).
    # The precomputed profile should win (no track_b key in result).
    result = ex.run(
        "Case_01",
        applicable_regs=["GDPR"],
        track_b_profile={"D-X": {"tier": "MINIMAL"}},
        track_b_scale="MICRO",
        track_b_fte=0.85,
        track_b_per_subdomain={"D-Y": {"inheritability": "BUILD_REQUIRED", "priority": "MUST"}},
    )
    assert "track_b" not in result
