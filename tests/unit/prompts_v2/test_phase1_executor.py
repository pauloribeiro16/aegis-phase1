"""Tests for Phase1Executor (Map/Reduce orchestration).

All tests use mocks — they never call real Ollama. The pattern matches
``tests/unit/nodes/test_b01_b02_v2.py``: replace ``executor.invoker`` with
a ``MagicMock`` whose ``.invoke.side_effect`` yields canned LLM responses.

Coverage:
  - Imports + DOMAINS constant
  - run_phase_1b success / failure aggregation
  - run_phase_1c_map (10 lanes)
  - run_sync no conflicts / with conflicts
  - run_phase_1c_reduce ordering (LLM-03 before LLM-02)
  - end-to-end run() shape
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aegis_phase1.prompts_v2.phase1_executor import (
    DOMAINS,
    SPEC_COMPOUND,
    SPEC_INTERPRETATION,
    SPEC_OVERLAP,
    SPEC_RATIONALE,
    SPEC_STRATEGIC,
    Phase1Executor,
    invoker_to_executor,
)

# ─── Helpers ──────────────────────────────────────────────────────────


def _make_executor() -> tuple[
    Phase1Executor, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock
]:
    """Construct a Phase1Executor with all dependencies mocked."""
    pl = MagicMock(name="PromptLoader")
    cl = MagicMock(name="CatalogLoader")
    val = MagicMock(name="Validator")
    ll = MagicMock(name="LLMLogger")
    fl = MagicMock(name="FormatLogger")
    executor = Phase1Executor(pl, cl, val, ll, fl)
    return executor, pl, cl, val, ll, fl


def _ok_response(parsed: dict | None = None, latency: float = 100.0) -> dict:
    """Build a canonical OK response from the invoker."""
    return {
        "status": "OK",
        "parsed_output": parsed or {},
        "validation": {"valid": True},
        "total_latency_ms": latency,
        "retry_count": 1,
    }


def _fail_response(reason: str = "FAILED_AFTER_RETRIES") -> dict:
    """Build a failure response from the invoker."""
    return {
        "status": reason,
        "parsed_output": None,
        "validation": None,
        "total_latency_ms": 0.0,
        "retry_count": 2,
    }


# ─── Imports + constants ──────────────────────────────────────────────


def test_phase1_executor_imports() -> None:
    """Phase1Executor and DOMAINS importable; DOMAINS is the canonical 10-lane list."""
    assert callable(Phase1Executor)
    assert len(DOMAINS) == 10
    assert DOMAINS[0] == "D-01"
    assert DOMAINS[-1] == "D-10"
    assert "D-01" in DOMAINS
    assert "D-05" in DOMAINS
    assert "D-10" in DOMAINS


def test_phase1_executor_init_stores_dependencies() -> None:
    """Constructor stores loaders + loggers as attributes."""
    executor, pl, cl, val, ll, fl = _make_executor()
    assert executor.prompts is pl
    assert executor.catalogs is cl
    assert executor.validator is val
    assert executor.llm_logger is ll
    assert executor.format_logger is fl
    # invoker was built internally with the loaders
    assert executor.invoker is not None


def test_phase1_executor_accepts_external_invoker() -> None:
    """When an invoker is passed, the executor reuses it (does NOT rebuild)."""
    pl = MagicMock(name="PromptLoader")
    cl = MagicMock(name="CatalogLoader")
    val = MagicMock(name="Validator")
    ll = MagicMock(name="LLMLogger")
    fl = MagicMock(name="FormatLogger")
    invoker = MagicMock(name="Phase1LLMInvoker")
    executor = Phase1Executor(pl, cl, val, ll, fl, invoker=invoker)
    assert executor.invoker is invoker


def test_invoker_to_executor_round_trip() -> None:
    """invoker_to_executor() builds a Phase1Executor from a real wired invoker."""
    invoker = MagicMock(spec=["prompts", "catalogs", "validator", "llm_logger", "format_logger"])
    invoker.prompts = MagicMock(name="real_prompts")
    invoker.catalogs = MagicMock(name="real_catalogs")
    invoker.validator = MagicMock(name="real_validator")
    invoker.llm_logger = MagicMock(name="real_llm_logger")
    invoker.format_logger = MagicMock(name="real_format_logger")
    executor = invoker_to_executor(invoker)
    assert isinstance(executor, Phase1Executor)
    assert executor.invoker is invoker
    assert executor.prompts is invoker.prompts


def test_invoker_to_executor_raises_on_missing_dep() -> None:
    """invoker_to_executor raises ValueError when a required attr is None."""
    invoker = MagicMock(spec=["prompts", "catalogs", "validator", "llm_logger", "format_logger"])
    invoker.prompts = None
    invoker.catalogs = MagicMock()
    invoker.validator = MagicMock()
    invoker.llm_logger = MagicMock()
    invoker.format_logger = MagicMock()
    with pytest.raises(ValueError, match="prompt_loader"):
        invoker_to_executor(invoker)


# ─── Phase 1B ─────────────────────────────────────────────────────────


def test_run_phase_1b_success_two_regs() -> None:
    """run_phase_1b calls P1B-LLM-01 + P1B-LLM-02 per regulation, aggregates OK."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    # 2 regs * 2 LLMs = 4 responses
    executor.invoker.invoke.side_effect = [
        # P1B-LLM-01 for GDPR
        _ok_response(
            parsed={"interpretations": [{"entry_id": "A"}], "derogations": []},
            latency=100.0,
        ),
        # P1B-LLM-02 for GDPR
        _ok_response(parsed={"synthesis": {"rationale": "r1"}}, latency=200.0),
        # P1B-LLM-01 for CRA
        _ok_response(
            parsed={"interpretations": [{"entry_id": "B"}], "derogations": [{"d": 1}]},
            latency=150.0,
        ),
        # P1B-LLM-02 for CRA
        _ok_response(parsed={"synthesis": {"rationale": "r2"}}, latency=250.0),
    ]

    result = executor.run_phase_1b("Case_01", ["GDPR", "CRA"])

    assert result["status"] == "OK"
    assert set(result["per_reg"].keys()) == {"GDPR", "CRA"}
    assert SPEC_INTERPRETATION in result["per_reg"]["GDPR"]
    assert SPEC_RATIONALE in result["per_reg"]["GDPR"]
    assert len(result["aggregated_interpretations"]) == 2
    assert len(result["aggregated_derogations"]) == 1
    assert "GDPR" in result["aggregated_synthesis"]
    assert "CRA" in result["aggregated_synthesis"]
    assert executor.invoker.invoke.call_count == 4
    spec_ids_called = [c.args[0] for c in executor.invoker.invoke.call_args_list]
    # alternating 01, 02, 01, 02 per reg
    assert spec_ids_called[0] == SPEC_INTERPRETATION
    assert spec_ids_called[1] == SPEC_RATIONALE
    assert spec_ids_called[2] == SPEC_INTERPRETATION
    assert spec_ids_called[3] == SPEC_RATIONALE


def test_run_phase_1b_empty_applicable() -> None:
    """No regulations → no LLM calls, all aggregates empty, status OK."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    result = executor.run_phase_1b("Case_01", [])
    assert result["per_reg"] == {}
    assert result["aggregated_interpretations"] == []
    assert result["aggregated_derogations"] == []
    assert result["aggregated_synthesis"] == {}
    assert result["status"] == "OK"
    assert executor.invoker.invoke.call_count == 0


def test_run_phase_1b_failure_aggregation_mixed() -> None:
    """If one of the 4 calls fails, aggregate status is MIXED."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        _ok_response(parsed={}, latency=100.0),
        _fail_response("FAILED_AFTER_RETRIES"),
        _ok_response(parsed={}, latency=100.0),
        _ok_response(parsed={}, latency=100.0),
    ]
    result = executor.run_phase_1b("Case_01", ["GDPR", "CRA"])
    assert result["status"] == "MIXED"


def test_run_phase_1b_failure_aggregation_all_failed() -> None:
    """If every call fails, aggregate status is FAILED."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        _fail_response("FAILED_AFTER_RETRIES"),
        _fail_response("FAILED_AFTER_RETRIES"),
    ]
    result = executor.run_phase_1b("Case_01", ["GDPR"])
    assert result["status"] == "FAILED"


def test_run_phase_1b_passes_lane_id_per_reg() -> None:
    """run_phase_1b sets lane_id = applicable_regs[0] per call."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        _ok_response(),
        _ok_response(),
        _ok_response(),
        _ok_response(),
    ]
    executor.run_phase_1b("Case_01", ["GDPR", "CRA"])
    for call in executor.invoker.invoke.call_args_list:
        assert call.args[1]["lane_id"] in {"GDPR", "CRA"}
        assert call.args[1]["applicable_regs"] == [call.args[1]["lane_id"]]
        assert call.args[1]["case_id"] == "Case_01"


# ─── Phase 1C Map ─────────────────────────────────────────────────────


def test_run_phase_1c_map_emits_10_lanes() -> None:
    """run_phase_1c_map calls P1C-LLM-01 for each of the 10 domains."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    side_effects: list[dict] = []
    for i in range(10):
        side_effects.append(
            _ok_response(
                parsed={
                    "sub_domain_activations": [
                        {
                            "sub_domain_id": f"{DOMAINS[i]}.1",
                            "applicable": True,
                            "scope_overlap": "Y",
                        }
                    ]
                },
                latency=100.0 + i,
            )
        )
    executor.invoker.invoke.side_effect = side_effects

    result = executor.run_phase_1c_map("Case_01", ["GDPR", "CRA"])

    assert len(result) == 10
    assert result[0]["lane_id"] == "D-01"
    assert result[9]["lane_id"] == "D-10"
    assert executor.invoker.invoke.call_count == 10
    for call in executor.invoker.invoke.call_args_list:
        assert call.args[0] == SPEC_OVERLAP
    # Verify the first lane's activation was extracted
    assert result[0]["sub_domain_activations"][0]["sub_domain_id"] == "D-01.1"
    assert result[9]["latency_ms"] == 109.0  # 100 + 9


def test_run_phase_1c_map_handles_missing_activations() -> None:
    """Lanes without sub_domain_activations yield empty list, not crash."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    side_effects = [
        _ok_response(parsed={}),  # D-01: missing
        _ok_response(parsed={"sub_domain_activations": None}),  # D-02: null
        _ok_response(parsed={"sub_domain_activations": "not-a-list"}),  # D-03: bad type
    ] + [_ok_response(parsed={"sub_domain_activations": []}) for _ in range(7)]
    executor.invoker.invoke.side_effect = side_effects
    result = executor.run_phase_1c_map("Case_01", ["GDPR"])
    assert len(result) == 10
    for lane in result[:3]:
        assert lane["sub_domain_activations"] == []


def test_run_phase_1c_map_handles_failure_lane() -> None:
    """Failed lanes get status FAILED_AFTER_RETRIES; lane still in result."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    side_effects = [_fail_response("FAILED_AFTER_RETRIES")] + [
        _ok_response(parsed={"sub_domain_activations": []}) for _ in range(9)
    ]
    executor.invoker.invoke.side_effect = side_effects
    result = executor.run_phase_1c_map("Case_01", ["GDPR"])
    assert result[0]["status"] == "FAILED_AFTER_RETRIES"
    assert result[0]["sub_domain_activations"] == []
    assert result[1]["status"] == "OK"


# ─── Sync ─────────────────────────────────────────────────────────────


def test_run_sync_no_conflicts_all_agree() -> None:
    """When all lanes agree on a (sub_domain, reg_pair), no conflict is raised."""
    executor, _, _, _, _, _ = _make_executor()
    lane_outputs = [
        {
            "lane_id": "D-01",
            "sub_domain_activations": [
                {
                    "sub_domain_id": "D-01.1",
                    "verified_relationship_per_pair": [
                        {
                            "reg_pair": ["GDPR", "CRA"],
                            "company_scope_verdict": "OVERLAP_CONFIRMED",
                            "layer0_relationship": "COMPLEMENTARY",
                        }
                    ],
                }
            ],
        },
        {
            "lane_id": "D-02",
            "sub_domain_activations": [
                {
                    "sub_domain_id": "D-02.1",
                    "verified_relationship_per_pair": [
                        {
                            "reg_pair": ["GDPR", "CRA"],
                            "company_scope_verdict": "OVERLAP_CONFIRMED",
                            "layer0_relationship": "COMPLEMENTARY",
                        }
                    ],
                }
            ],
        },
    ]
    result = executor.run_sync(lane_outputs)
    assert result["status"] == "OK"
    assert result["conflicts"] == []
    assert len(result["matrix"]) == 2  # two (sub_domain, reg_pair) keys


def test_run_sync_detects_cross_lane_conflict() -> None:
    """Two lanes disagree on the same (sub_domain, reg_pair) → INDETERMINATE."""
    executor, _, _, _, _, _ = _make_executor()
    lane_outputs = [
        {
            "lane_id": "D-04",
            "sub_domain_activations": [
                {
                    "sub_domain_id": "D-04.3",
                    "verified_relationship_per_pair": [
                        {
                            "reg_pair": ["GDPR", "CRA"],
                            "company_scope_verdict": "OVERLAP_CONFIRMED",
                            "layer0_relationship": "COMPLEMENTARY",
                        }
                    ],
                }
            ],
        },
        {
            "lane_id": "D-09",
            "sub_domain_activations": [
                {
                    "sub_domain_id": "D-04.3",
                    "verified_relationship_per_pair": [
                        {
                            "reg_pair": ["GDPR", "CRA"],
                            "company_scope_verdict": "SCOPE_DISJOINT",
                            "layer0_relationship": "COMPLEMENTARY",
                        }
                    ],
                }
            ],
        },
    ]
    result = executor.run_sync(lane_outputs)
    assert result["status"] == "CONFLICTS_DETECTED"
    assert len(result["conflicts"]) == 1
    c = result["conflicts"][0]
    assert c["sub_domain"] == "D-04.3"
    assert sorted(c["reg_pair"]) == ["CRA", "GDPR"]
    assert "OVERLAP_CONFIRMED" in c["verdicts"]
    assert "SCOPE_DISJOINT" in c["verdicts"]
    assert c["severity"] == "INDETERMINATE"


def test_run_sync_different_sub_domains_no_conflict() -> None:
    """Different (sub_domain, reg_pair) keys never conflict, even with different verdicts."""
    executor, _, _, _, _, _ = _make_executor()
    lane_outputs = [
        {
            "lane_id": "D-01",
            "sub_domain_activations": [
                {
                    "sub_domain_id": "D-01.1",
                    "verified_relationship_per_pair": [
                        {
                            "reg_pair": ["GDPR", "CRA"],
                            "company_scope_verdict": "OVERLAP_CONFIRMED",
                        }
                    ],
                }
            ],
        },
        {
            "lane_id": "D-09",
            "sub_domain_activations": [
                {
                    "sub_domain_id": "D-09.1",
                    "verified_relationship_per_pair": [
                        {
                            "reg_pair": ["GDPR", "CRA"],
                            "company_scope_verdict": "SCOPE_DISJOINT",
                        }
                    ],
                }
            ],
        },
    ]
    result = executor.run_sync(lane_outputs)
    assert result["status"] == "OK"
    assert result["conflicts"] == []
    # Both sub_domains are entries in the matrix
    assert len(result["matrix"]) == 2


def test_run_sync_reg_pair_normalized_to_canonical_order() -> None:
    """(sub_domain, sorted(reg_pair)) is the key — input order does not matter."""
    executor, _, _, _, _, _ = _make_executor()
    lane_outputs = [
        {
            "lane_id": "D-01",
            "sub_domain_activations": [
                {
                    "sub_domain_id": "D-01.1",
                    "verified_relationship_per_pair": [
                        {
                            "reg_pair": ["CRA", "GDPR"],  # reverse order
                            "company_scope_verdict": "OVERLAP_CONFIRMED",
                        }
                    ],
                }
            ],
        },
        {
            "lane_id": "D-02",
            "sub_domain_activations": [
                {
                    "sub_domain_id": "D-01.1",
                    "verified_relationship_per_pair": [
                        {
                            "reg_pair": ["GDPR", "CRA"],  # normal order
                            "company_scope_verdict": "OVERLAP_CONFIRMED",
                        }
                    ],
                }
            ],
        },
    ]
    result = executor.run_sync(lane_outputs)
    assert result["status"] == "OK"  # both should agree under canonical ordering
    assert result["conflicts"] == []


def test_run_sync_handles_empty_inputs() -> None:
    """Empty lane list yields OK + empty matrix."""
    executor, _, _, _, _, _ = _make_executor()
    result = executor.run_sync([])
    assert result["status"] == "OK"
    assert result["conflicts"] == []
    assert result["matrix"] == {}


def test_run_sync_skips_malformed_pair_entries() -> None:
    """Pairs with non-list reg_pair or fewer than 2 regs are ignored (no crash)."""
    executor, _, _, _, _, _ = _make_executor()
    lane_outputs = [
        {
            "lane_id": "D-01",
            "sub_domain_activations": [
                {
                    "sub_domain_id": "D-01.1",
                    "verified_relationship_per_pair": [
                        {"reg_pair": "GDPR", "company_scope_verdict": "OVERLAP_CONFIRMED"},
                        {"reg_pair": ["GDPR"], "company_scope_verdict": "OVERLAP_CONFIRMED"},
                        {"reg_pair": None, "company_scope_verdict": "OVERLAP_CONFIRMED"},
                        {
                            "reg_pair": ["GDPR", "CRA"],
                            "company_scope_verdict": "OVERLAP_CONFIRMED",
                        },
                    ],
                }
            ],
        }
    ]
    result = executor.run_sync(lane_outputs)
    assert result["status"] == "OK"
    assert len(result["matrix"]) == 1


# ─── Phase 1C Reduce ──────────────────────────────────────────────────


def test_run_phase_1c_reduce_llm03_before_llm02() -> None:
    """Per contract: LLM-03 (STRATEGIC) runs before LLM-02 (COMPOUND)."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        # First call: LLM-03
        _ok_response(
            parsed={"implications": [{"id": "IMP-1"}]},
            latency=500.0,
        ),
        # Second call: LLM-02 (consumes LLM-03 output)
        _ok_response(
            parsed={"positive_events": [], "negative_events": []},
            latency=600.0,
        ),
    ]

    lane_outputs = [{"lane_id": "D-01", "sub_domain_activations": []}]
    sync_result = {"status": "OK", "conflicts": []}

    result = executor.run_phase_1c_reduce(
        "Case_01",
        lane_outputs,
        sync_result,
        track_b_profile={"tier": "LOW"},
    )

    spec_ids = [c.args[0] for c in executor.invoker.invoke.call_args_list]
    assert spec_ids == [SPEC_STRATEGIC, SPEC_COMPOUND]
    assert result["status"] == "OK"


def test_run_phase_1c_reduce_passes_track_b_to_llm03() -> None:
    """track_b_profile is forwarded into LLM-03 as doc07b_profile."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        _ok_response(parsed={"implications": []}, latency=100.0),
        _ok_response(parsed={"positive_events": [], "negative_events": []}, latency=100.0),
    ]
    executor.run_phase_1c_reduce(
        "Case_01",
        [{"lane_id": "D-01", "sub_domain_activations": []}],
        {"status": "OK", "conflicts": []},
        track_b_profile={"tier": "MEDIUM", "headcount_band": "11-50"},
    )
    first_call = executor.invoker.invoke.call_args_list[0]
    assert first_call.args[1]["doc07b_profile"] == {"tier": "MEDIUM", "headcount_band": "11-50"}


def test_run_phase_1c_reduce_default_track_b_empty() -> None:
    """When track_b_profile is None, doc07b_profile is empty dict."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        _ok_response(parsed={}, latency=100.0),
        _ok_response(parsed={}, latency=100.0),
    ]
    executor.run_phase_1c_reduce(
        "Case_01",
        [{"lane_id": "D-01", "sub_domain_activations": []}],
        {"status": "OK", "conflicts": []},
        track_b_profile=None,
    )
    first_call = executor.invoker.invoke.call_args_list[0]
    assert first_call.args[1]["doc07b_profile"] == {}


def test_run_phase_1c_reduce_passes_llm03_output_to_llm02() -> None:
    """LLM-02 receives LLM-03's parsed_output as c03_strategic_synthesis."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        _ok_response(
            parsed={"implications": [{"id": "IMP-42"}], "synthesis": "S"},
            latency=100.0,
        ),
        _ok_response(parsed={}, latency=100.0),
    ]
    executor.run_phase_1c_reduce(
        "Case_01",
        [{"lane_id": "D-01", "sub_domain_activations": []}],
        {"status": "OK", "conflicts": []},
    )
    second_call = executor.invoker.invoke.call_args_list[1]
    assert second_call.args[1]["c03_strategic_synthesis"] == {
        "implications": [{"id": "IMP-42"}],
        "synthesis": "S",
    }


def test_run_phase_1c_reduce_mix_status_when_one_fails() -> None:
    """If only LLM-03 fails, status is MIXED."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        _fail_response("FAILED_AFTER_RETRIES"),
        _ok_response(parsed={}, latency=100.0),
    ]
    result = executor.run_phase_1c_reduce(
        "Case_01",
        [{"lane_id": "D-01", "sub_domain_activations": []}],
        {"status": "OK", "conflicts": []},
    )
    assert result["status"] == "MIXED"


def test_run_phase_1c_reduce_surfaces_conflict_count() -> None:
    """conflicts_count in result reflects number of conflicts passed in."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        _ok_response(parsed={}, latency=100.0),
        _ok_response(parsed={}, latency=100.0),
    ]
    sync_result = {
        "status": "CONFLICTS_DETECTED",
        "conflicts": [{"sub_domain": "D-04.3"}, {"sub_domain": "D-09.1"}],
    }
    result = executor.run_phase_1c_reduce(
        "Case_01",
        [{"lane_id": "D-01", "sub_domain_activations": []}],
        sync_result,
    )
    assert result["conflicts_count"] == 2


def test_run_phase_1c_reduce_flattens_lane_activations() -> None:
    """Aggregated activations are the union of lane.sub_domain_activations."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    executor.invoker.invoke.side_effect = [
        _ok_response(parsed={}, latency=100.0),
        _ok_response(parsed={}, latency=100.0),
    ]
    lane_outputs = [
        {
            "lane_id": "D-01",
            "sub_domain_activations": [
                {"sub_domain_id": "D-01.1", "applicable": True},
                {"sub_domain_id": "D-01.2", "applicable": True},
            ],
        },
        {
            "lane_id": "D-02",
            "sub_domain_activations": [
                {"sub_domain_id": "D-02.1", "applicable": False},
            ],
        },
    ]
    result = executor.run_phase_1c_reduce(
        "Case_01",
        lane_outputs,
        {"status": "OK", "conflicts": []},
    )
    assert len(result["aggregated_activations"]) == 3
    sub_ids = {sd["sub_domain_id"] for sd in result["aggregated_activations"]}
    assert sub_ids == {"D-01.1", "D-01.2", "D-02.1"}


# ─── End-to-end run() ─────────────────────────────────────────────────


def test_run_end_to_end_shape() -> None:
    """run() produces all four phases with correct shape."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    # 2 regs * 2 LLMs (4) + 10 domains (10) + 2 reduce = 16 calls
    side_effects = [
        _ok_response(
            parsed={
                "interpretations": [{"entry_id": "INT-1"}],
                "derogations": [],
            },
            latency=100.0,
        ),  # GDPR LLM-01
        _ok_response(parsed={"synthesis": {"r": "x"}}, latency=100.0),  # GDPR LLM-02
        _ok_response(
            parsed={"interpretations": [{"entry_id": "INT-2"}], "derogations": []},
            latency=100.0,
        ),  # CRA LLM-01
        _ok_response(parsed={"synthesis": {"r": "y"}}, latency=100.0),  # CRA LLM-02
    ]
    # 10 lanes for the map stage
    for i in range(10):
        side_effects.append(
            _ok_response(
                parsed={
                    "sub_domain_activations": [
                        {"sub_domain_id": f"{DOMAINS[i]}.1", "applicable": True}
                    ]
                },
                latency=100.0 + i,
            )
        )
    # 2 reduce calls (LLM-03 then LLM-02)
    side_effects.append(_ok_response(parsed={"implications": []}, latency=100.0))
    side_effects.append(_ok_response(parsed={"positive_events": [], "negative_events": []}, latency=100.0))
    executor.invoker.invoke.side_effect = side_effects

    result = executor.run(
        "Case_01",
        ["GDPR", "CRA"],
        track_b_profile={"tier": "LOW"},
        classification={"role": "Controller", "tier": "LOW"},
    )

    assert result["case_id"] == "Case_01"
    assert "phase_1b" in result
    assert "phase_1c_map" in result
    assert "sync" in result
    assert "phase_1c_reduce" in result
    # Per-reg
    assert result["phase_1b"]["status"] == "OK"
    assert len(result["phase_1b"]["per_reg"]) == 2
    assert len(result["phase_1b"]["aggregated_interpretations"]) == 2
    # Map
    assert len(result["phase_1c_map"]) == 10
    assert result["sync"]["status"] == "OK"  # all lanes agree in this mock
    # Reduce
    assert result["phase_1c_reduce"]["status"] == "OK"
    assert executor.invoker.invoke.call_count == 16


def test_run_end_to_end_propagates_failure() -> None:
    """If the first LLM-01 call fails, phase_1b.status reflects it."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    side_effects = [
        _fail_response("FAILED_AFTER_RETRIES"),
        _ok_response(parsed={"synthesis": {}}, latency=100.0),
    ]
    for _ in range(10):
        side_effects.append(_ok_response(parsed={"sub_domain_activations": []}, latency=100.0))
    side_effects.append(_ok_response(parsed={}, latency=100.0))
    side_effects.append(_ok_response(parsed={}, latency=100.0))
    executor.invoker.invoke.side_effect = side_effects

    result = executor.run("Case_01", ["GDPR"])
    assert result["phase_1b"]["status"] == "MIXED"


def test_run_does_not_block_on_conflicts() -> None:
    """Even when sync detects conflicts, reduce still runs (per contract)."""
    executor, _, _, _, _, _ = _make_executor()
    executor.invoker = MagicMock()
    # Two regs; first sub_domain in first lane conflicts with second.
    side_effects = [
        _ok_response(parsed={"interpretations": [], "derogations": []}, latency=10.0),
        _ok_response(parsed={"synthesis": {}}, latency=10.0),
        _ok_response(parsed={"interpretations": [], "derogations": []}, latency=10.0),
        _ok_response(parsed={"synthesis": {}}, latency=10.0),
    ]
    # 10 map responses, two of which disagree on D-04.3
    for i in range(10):
        # D-04 (i=3) and D-09 (i=8) disagree on D-04.3
        if DOMAINS[i] == "D-04":
            verdict = "OVERLAP_CONFIRMED"
        elif DOMAINS[i] == "D-09":
            verdict = "SCOPE_DISJOINT"
        else:
            verdict = "OVERLAP_CONFIRMED"
        side_effects.append(
            _ok_response(
                parsed={
                    "sub_domain_activations": [
                        {
                            "sub_domain_id": "D-04.3",
                            "verified_relationship_per_pair": [
                                {
                                    "reg_pair": ["GDPR", "CRA"],
                                    "company_scope_verdict": verdict,
                                }
                            ],
                        }
                    ]
                },
                latency=10.0,
            )
        )
    side_effects.append(_ok_response(parsed={}, latency=10.0))  # LLM-03
    side_effects.append(_ok_response(parsed={}, latency=10.0))  # LLM-02
    executor.invoker.invoke.side_effect = side_effects

    result = executor.run("Case_01", ["GDPR", "CRA"])
    assert result["sync"]["status"] == "CONFLICTS_DETECTED"
    assert len(result["sync"]["conflicts"]) >= 1
    # Reduce still ran (LLM-03 + LLM-02 = 2 calls past map)
    assert result["phase_1c_reduce"]["status"] == "OK"
    assert result["phase_1c_reduce"]["conflicts_count"] >= 1
