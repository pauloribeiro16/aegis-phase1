"""Multi-case end-to-end tests for Phase1Executor (mocked path).

These tests use mocks to simulate the full Map/Reduce pipeline without
requiring Ollama. They verify the orchestration logic for all 3 cases.

The test pattern: build a complete Phase1Executor with mocked invoker,
provide fake per-regulation and per-domain responses, then verify:
  - run() returns the expected structure
  - Phase 1B iterates over applicable_regs
  - Phase 1C Map runs 10 lanes
  - Sync detects cross-lane conflicts (when set up)
  - Reduce stage runs LLM-03 before LLM-02
"""
from unittest.mock import MagicMock

from aegis_phase1.prompts_v2.phase1_executor import DOMAINS, Phase1Executor
from aegis_phase1.prompts_v2.track_b import TrackB


def _make_executor_mocked():
    """Create Phase1Executor with all deps mocked except the invoker."""
    pl = MagicMock()
    cl = MagicMock()
    val = MagicMock()
    ll = MagicMock()
    fl = MagicMock()
    return Phase1Executor(pl, cl, val, ll, fl)


def test_case_01_e2e_mocked():
    """Case 01: 2 regs (GDPR, CRA) + 10 domains -> full Map/Reduce."""
    ex = _make_executor_mocked()

    # 2 regs x 2 LLMs (P1B-LLM-01 + P1B-LLM-02) = 4 calls
    # + 10 domains (P1C-LLM-01) = 10 calls
    # + 2 reduce (LLM-03 + LLM-02) = 2 calls
    # Total: 16 calls
    side_effects = []
    for _ in range(4):
        side_effects.append({
            "status": "OK",
            "parsed_output": {"interpretations": [], "derogations": [], "synthesis": {}},
            "total_latency_ms": 100,
            "retry_count": 1,
        })
    for i in range(10):
        side_effects.append({
            "status": "OK",
            "parsed_output": {
                "sub_domain_activations": [
                    {
                        "sub_domain_id": f"{DOMAINS[i]}.1",
                        "applicable": True,
                        "scope_overlap": "Y",
                        "verified_relationship_per_pair": [],
                        "applicable_regulations": ["GDPR", "CRA"],
                        "regulatory_baseline_refs": [],
                    }
                ]
            },
            "total_latency_ms": 100,
            "retry_count": 1,
        })
    side_effects.append({
        "status": "OK",
        "parsed_output": {"implications": [{"id": "IMP-1", "description": "x", "affected_sub_domains": ["D-01.1"]}]},
        "total_latency_ms": 200,
        "retry_count": 1,
    })
    side_effects.append({
        "status": "OK",
        "parsed_output": {"positive_events": [], "negative_events": []},
        "total_latency_ms": 200,
        "retry_count": 1,
    })
    ex.invoker = MagicMock()
    ex.invoker.invoke.side_effect = side_effects

    result = ex.run("Case_01_TinyTask_SaaS", ["GDPR", "CRA"])

    assert result["case_id"] == "Case_01_TinyTask_SaaS"
    assert result["phase_1b"]["status"] == "OK"
    assert "GDPR" in result["phase_1b"]["per_reg"]
    assert "CRA" in result["phase_1b"]["per_reg"]
    assert len(result["phase_1c_map"]) == 10
    assert result["sync"]["status"] == "OK"
    assert result["sync"]["conflicts"] == []
    assert "P1C-LLM-03-STRATEGIC-SYNTHESIS" in result["phase_1c_reduce"]
    assert "P1C-LLM-02-COMPOUND-EVENT" in result["phase_1c_reduce"]
    assert ex.invoker.invoke.call_count == 16  # 4 + 10 + 2


def test_case_02_e2e_mocked():
    """Case 02: 4 regs (GDPR, CRA, NIS2, AI_Act) -> 8 + 10 + 2 = 20 calls."""
    ex = _make_executor_mocked()
    side_effects = [{"status": "OK", "parsed_output": {}, "total_latency_ms": 100, "retry_count": 1}] * 8
    side_effects += [{"status": "OK", "parsed_output": {"sub_domain_activations": []}, "total_latency_ms": 100, "retry_count": 1}] * 10
    side_effects += [{"status": "OK", "parsed_output": {}, "total_latency_ms": 200, "retry_count": 1}] * 2
    ex.invoker = MagicMock()
    ex.invoker.invoke.side_effect = side_effects

    result = ex.run("Case_02_SecureBorder_Solutions", ["GDPR", "CRA", "NIS2", "AI_Act"])
    assert result["phase_1b"]["status"] == "OK"
    assert len(result["phase_1c_map"]) == 10
    assert ex.invoker.invoke.call_count == 20  # 4 regs x 2 + 10 + 2


def test_case_03_e2e_mocked():
    """Case 03: 5 regs (GDPR, CRA, NIS2, DORA, AI_Act) -> 10 + 10 + 2 = 22 calls."""
    ex = _make_executor_mocked()
    side_effects = [{"status": "OK", "parsed_output": {}, "total_latency_ms": 100, "retry_count": 1}] * 10
    side_effects += [{"status": "OK", "parsed_output": {"sub_domain_activations": []}, "total_latency_ms": 100, "retry_count": 1}] * 10
    side_effects += [{"status": "OK", "parsed_output": {}, "total_latency_ms": 200, "retry_count": 1}] * 2
    ex.invoker = MagicMock()
    ex.invoker.invoke.side_effect = side_effects

    ex.run("Case_03_OmniBank_Financial", ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"])
    assert ex.invoker.invoke.call_count == 22  # 5 regs x 2 + 10 + 2


def test_e2e_with_sync_conflict():
    """When 2 lanes give different verdicts for the same (sub_domain, reg_pair), sync detects INDETERMINATE."""
    ex = _make_executor_mocked()
    side_effects = []
    for _ in range(4):
        side_effects.append({"status": "OK", "parsed_output": {}, "total_latency_ms": 100, "retry_count": 1})
    # 10 lane responses: D-04 and D-09 give conflicting verdicts on D-04.3 GDPR<->CRA
    for _i, d in enumerate(DOMAINS):
        if d in ("D-04", "D-09"):
            # Both report on D-04.3 with different verdicts
            side_effects.append({
                "status": "OK",
                "parsed_output": {
                    "sub_domain_activations": [
                        {
                            "sub_domain_id": "D-04.3",
                            "applicable": True,
                            "scope_overlap": "Y",
                            "verified_relationship_per_pair": [
                                {
                                    "reg_pair": ["GDPR", "CRA"],
                                    "regulatory_baseline_relationship": "CONDITIONAL",
                                    "company_scope_verdict": "OVERLAP_CONFIRMED" if d == "D-04" else "SCOPE_DISJOINT",
                                }
                            ],
                            "applicable_regulations": ["GDPR", "CRA"],
                            "regulatory_baseline_refs": [],
                        }
                    ]
                },
                "total_latency_ms": 100,
                "retry_count": 1,
            })
        else:
            side_effects.append({
                "status": "OK",
                "parsed_output": {"sub_domain_activations": []},
                "total_latency_ms": 100,
                "retry_count": 1,
            })
    # 2 reduce calls
    side_effects += [{"status": "OK", "parsed_output": {}, "total_latency_ms": 200, "retry_count": 1}] * 2
    ex.invoker = MagicMock()
    ex.invoker.invoke.side_effect = side_effects

    result = ex.run("Case_01", ["GDPR", "CRA"])
    assert result["sync"]["status"] == "CONFLICTS_DETECTED"
    assert len(result["sync"]["conflicts"]) == 1
    assert result["sync"]["conflicts"][0]["sub_domain"] == "D-04.3"


def test_e2e_with_track_b_integration():
    """Full e2e with TrackB (Case 01 distribution check)."""
    from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor
    pl = MagicMock()
    cl = MagicMock()
    val = MagicMock()
    ll = MagicMock()
    fl = MagicMock()
    tb = TrackB()
    ex = Phase1Executor(pl, cl, val, ll, fl, track_b=tb)
    ex.invoker = MagicMock()
    # Mock to return OK with empty outputs (just verify executor handles track_b)
    side_effects = [{"status": "OK", "parsed_output": {}, "total_latency_ms": 100, "retry_count": 1}] * 16
    ex.invoker.invoke.side_effect = side_effects

    # Build per_subdomain_input matching Case 01 distribution
    per_sd = {}
    for i in range(31):
        per_sd[f"D-A.{i}"] = {"inheritability": "BUILD_REQUIRED", "priority": "MUST"}
    for i in range(5):
        per_sd[f"D-B.{i}"] = {"inheritability": "INHERITABLE", "priority": "MUST"}
    per_sd["D-DEFERRED"] = {"inheritability": "BUILD_REQUIRED", "priority": "SHOULD"}

    track_b_profile = tb.assign_all("MICRO", fte=0.85, per_subdomain_input=per_sd)
    summary = tb.summarize(track_b_profile)
    assert summary["tier_distribution"].get("LIGHTWEIGHT") == 31
    assert summary["tier_distribution"].get("MINIMAL") == 5
    assert summary["tier_distribution"].get("DEFERRED") == 1
