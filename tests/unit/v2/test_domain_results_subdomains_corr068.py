"""CORR-068 S1: domain_results[D-XX]['subdomains'] must be populated from adapted_v3.

Pre-S1 the field was hardcoded to [] in _map_domains_via_p1c_llm_01, which
cascaded into Track B seeing 0 subdomains and the reduce-stage LLMs receiving
empty aggregated_activations.

This test mocks the Phase1Executor lane output and verifies that:
1. The legacy "subdomains" field is populated (not empty)
2. The entries have the expected shape (subdomain_id, reg_pair, etc.)
3. The concatenator can read the entries and produce a non-empty dict
4. The reduce_synthesis lane_outputs aggregator sees non-empty sub_domain_activations
"""
import logging
from unittest.mock import MagicMock

import pytest

logging.basicConfig(level=logging.WARNING)


def _build_lane_output(lane_id, sub_domain_activations):
    """Build a fake P1C-LLM-01 lane output for testing."""
    return {
        "lane_id": lane_id,
        "status": "OK",
        "sub_domain_activations": sub_domain_activations,
        "latency_ms": 1000,
    }


def _build_sd_activation(sub_id, reg_pair=("GDPR", "CRA"), verdict="IN_SCOPE"):
    """Build a fake sub_domain_activation entry."""
    return {
        "sub_domain_id": sub_id,
        "reg_pair": list(reg_pair),
        "company_scope_verdict": verdict,
        "regulatory_baseline_relationship": "EXTENDS",
        "layer0_refs": [f"SubDomains/D-XX.Y.md"],
    }


def test_map_domains_via_p1c_populates_legacy_subdomains_field():
    """The legacy 'subdomains' field must be populated from adapted_v3.

    Pre-S1 this field was hardcoded to [] which broke:
    - concatenator.concatenate (saw 0 subdomains)
    - apply_proportionality (profiled 0 rows)
    - reduce_synthesis lane_outputs (0 sub_domain_activations → INDETERMINATE LLM)
    """
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator()
    executor = MagicMock()
    executor.run_phase_1c_map.return_value = [
        _build_lane_output("D-01", [
            _build_sd_activation("D-01.1"),
            _build_sd_activation("D-01.2"),
        ]),
        _build_lane_output("D-02", [
            _build_sd_activation("D-02.1", reg_pair=("NIS2",)),
        ]),
    ]

    # Pre-populate the state minimally so _map_domains_via_p1c_llm_01 can run
    orch.state["company_context"] = {
        "applicable_regs": ["GDPR", "CRA"],
        "company_name": "TestCo",
    }
    orch.state["aggregated_data"] = {
        "rationale_by_reg": {"GDPR": {"rationale": "applies"}}
    }

    results = orch._map_domains_via_p1c_llm_01(executor)

    assert executor.run_phase_1c_map.call_args.kwargs["p1b_outputs_by_reg"] == {
        "GDPR": {"rationale": "applies"}
    }
    assert "D-01" in results
    assert "D-02" in results

    # THE FIX: subdomains is now populated, not empty
    d01 = results["D-01"]
    assert d01["subdomains"], f"D-01 subdomains should be populated, got {d01['subdomains']!r}"
    assert len(d01["subdomains"]) == 2

    d02 = results["D-02"]
    assert d02["subdomains"], f"D-02 subdomains should be populated, got {d02['subdomains']!r}"
    assert len(d02["subdomains"]) == 1

    # Verify the legacy shape (subdomain_id field, list of dicts)
    assert d01["subdomains"][0]["subdomain_id"] == "D-01.1"
    assert d01["subdomains"][0]["id"] == "D-01.1"  # both keys for compat
    assert d01["subdomains"][0]["reg_pair"] == ["GDPR", "CRA"]
    assert d01["subdomains"][0]["company_scope_verdict"] == "IN_SCOPE"

    # adapted_subdomains_v3 should ALSO be present (v3 path still works)
    assert d01["adapted_subdomains_v3"]
    assert len(d01["adapted_subdomains_v3"]) == 2


def test_concatenator_sees_populated_subdomains():
    """End-to-end: concatenator should read domain_results[D-XX].subdomains
    and produce a non-empty subdomains dict.
    """
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator
    from aegis_phase1.v2.reduce.concatenator import concatenate

    orch = Phase1Orchestrator()
    executor = MagicMock()
    executor.run_phase_1c_map.return_value = [
        _build_lane_output(f"D-{i:02d}", [
            _build_sd_activation(f"D-{i:02d}.1"),
            _build_sd_activation(f"D-{i:02d}.2"),
        ])
        for i in range(1, 11)
    ]
    orch.state["company_context"] = {
        "applicable_regs": ["GDPR"],
        "company_name": "TestCo",
    }
    results = orch._map_domains_via_p1c_llm_01(executor)
    orch.state["domain_results"] = results

    out = concatenate(orch.state)
    assert len(out["subdomains"]) > 0, (
        f"concatenate should produce non-empty subdomains dict, got {len(out['subdomains'])} entries"
    )
    # 10 domains × 2 sub-domains = 20
    assert len(out["subdomains"]) == 20
    assert "D-01.1" in out["subdomains"]
    assert "D-10.2" in out["subdomains"]


def test_reduce_synthesis_lane_outputs_have_sub_domain_activations():
    """End-to-end: reduce_synthesis should produce lane_outputs with
    non-empty sub_domain_activations (so the reduce-stage LLMs receive
    the data they need, not INDETERMINATE).
    """
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator()
    executor = MagicMock()
    executor.run_phase_1c_map.return_value = [
        _build_lane_output(f"D-{i:02d}", [
            _build_sd_activation(f"D-{i:02d}.1"),
        ])
        for i in range(1, 11)
    ]
    orch.state["company_context"] = {
        "applicable_regs": ["GDPR"],
        "company_name": "TestCo",
    }
    results = orch._map_domains_via_p1c_llm_01(executor)
    orch.state["domain_results"] = results

    # Simulate the lane_outputs construction from reduce_synthesis
    lane_outputs = [
        {
            "lane_id": lane_id,
            "sub_domain_activations": (
                lane_result.get("subdomains") or [] if isinstance(lane_result, dict) else []
            ),
        }
        for lane_id, lane_result in orch.state.get("domain_results", {}).items()
    ]

    # Each lane should have at least 1 sub_domain_activation
    assert len(lane_outputs) == 10
    for lo in lane_outputs:
        assert lo["sub_domain_activations"], (
            f"lane {lo['lane_id']} should have non-empty sub_domain_activations, "
            f"got {lo['sub_domain_activations']!r}"
        )
        assert len(lo["sub_domain_activations"]) >= 1

    # Aggregated should be 10 entries (1 per D-XX domain)
    aggregated = []
    for lo in lane_outputs:
        aggregated.extend(lo["sub_domain_activations"])
    assert len(aggregated) == 10


def test_failed_domain_result_still_has_empty_subdomains():
    """The _failed_domain_result helper must continue to return subdomains=[].

    This is intentional (failed domain has no sub-domain activations).
    """
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator()
    failed = orch._failed_domain_result("D-05", RuntimeError("test"))

    assert failed["domain_id"] == "D-05"
    assert failed["subdomains"] == []  # intentional for failed domains
    assert failed["llm_status"] == "FAILED"
