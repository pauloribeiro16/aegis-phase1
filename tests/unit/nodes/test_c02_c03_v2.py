"""Tests for c02 and c03 v2 functions (P1C-LLM-02 + P1C-LLM-03)."""

from unittest.mock import MagicMock, patch

from aegis_phase1.nodes.c02_domain_elaboration import c02_domain_elaboration_v2
from aegis_phase1.nodes.c03_strategic_implications import c03_strategic_implications_v2


def test_c02_v2_imports() -> None:
    """c02_domain_elaboration_v2 exists and is callable."""
    assert callable(c02_domain_elaboration_v2)


def test_c02_v2_calls_invoker() -> None:
    """c02 calls get_invoker().invoke with P1C-LLM-02-COMPOUND-EVENT."""
    with patch("aegis_phase1.nodes.c02_domain_elaboration.get_invoker") as mock_get:
        mock_invoker = MagicMock()
        mock_invoker.invoke.return_value = {
            "status": "OK",
            "parsed_output": {
                "positive_events": [{"event_id": "EV-POS-01", "description": "ok"}],
                "negative_events": [{"event_id": "EV-NEG-01", "description": "bad"}],
            },
            "total_latency_ms": 50,
            "retry_count": 1,
        }
        mock_get.return_value = mock_invoker
        state = {"case_id": "Case_01", "applicable_regulations": ["GDPR"]}
        result = c02_domain_elaboration_v2(state)
        assert result["c02_v2_status"] == "OK"
        assert len(result["c02_v2_positive_events"]) == 1
        assert len(result["c02_v2_negative_events"]) == 1
        args = mock_invoker.invoke.call_args
        assert args.args[0] == "P1C-LLM-02-COMPOUND-EVENT"
        # Inputs that the prompt expects are passed.
        assert args.args[1]["applicable_regs"] == ["GDPR"]


def test_c02_v2_empty_activations() -> None:
    """c02 tolerates a state without upstream lane outputs."""
    with patch("aegis_phase1.nodes.c02_domain_elaboration.get_invoker") as mock_get:
        mock_invoker = MagicMock()
        mock_invoker.invoke.return_value = {
            "status": "OK",
            "parsed_output": {"positive_events": [], "negative_events": []},
            "total_latency_ms": 10,
        }
        mock_get.return_value = mock_invoker
        state = {"case_id": "Case_01", "applicable_regulations": ["GDPR"]}
        # No aggregated_activations / c03_strategic_synthesis keys.
        result = c02_domain_elaboration_v2(state)
        assert result["c02_v2_status"] == "OK"
        assert result["c02_v2_positive_events"] == []
        assert result["c02_v2_negative_events"] == []
        inputs = mock_invoker.invoke.call_args.args[1]
        assert inputs["aggregated_activations"] == []
        assert inputs["c03_strategic_synthesis"] == {}


def test_c02_v2_failure() -> None:
    """c02 surfaces LLM failure as the v2 status field."""
    with patch("aegis_phase1.nodes.c02_domain_elaboration.get_invoker") as mock_get:
        mock_invoker = MagicMock()
        mock_invoker.invoke.return_value = {
            "status": "FAILED_AFTER_RETRIES",
            "parsed_output": None,
            "total_latency_ms": 0,
        }
        mock_get.return_value = mock_invoker
        state = {"case_id": "Case_01", "applicable_regulations": ["GDPR"]}
        result = c02_domain_elaboration_v2(state)
        assert result["c02_v2_status"] == "FAILED_AFTER_RETRIES"
        assert result["c02_v2_positive_events"] == []


def test_c03_v2_imports() -> None:
    """c03_strategic_implications_v2 exists and is callable."""
    assert callable(c03_strategic_implications_v2)


def test_c03_v2_calls_invoker() -> None:
    """c03 calls get_invoker().invoke with P1C-LLM-03-STRATEGIC-SYNTHESIS."""
    with patch("aegis_phase1.nodes.c03_strategic_implications.get_invoker") as mock_get:
        mock_invoker = MagicMock()
        mock_invoker.invoke.return_value = {
            "status": "OK",
            "parsed_output": {"implications": [{"id": "IMP-01", "description": "x"}]},
            "total_latency_ms": 75,
            "retry_count": 1,
        }
        mock_get.return_value = mock_invoker
        state = {
            "case_id": "Case_01",
            "applicable_regulations": ["GDPR"],
            "doc07b_profile": {"D-01.1": {"tier": "LIGHTWEIGHT"}},
            "business_goals": [{"id": "BG-01"}],
        }
        result = c03_strategic_implications_v2(state)
        assert result["c03_v2_status"] == "OK"
        assert len(result["c03_v2_implications"]) == 1
        args = mock_invoker.invoke.call_args
        assert args.args[0] == "P1C-LLM-03-STRATEGIC-SYNTHESIS"
        # Inputs the prompt expects are passed.
        inputs = args.args[1]
        assert inputs["applicable_regs"] == ["GDPR"]
        assert inputs["doc07b_profile"] == {"D-01.1": {"tier": "LIGHTWEIGHT"}}
        assert inputs["business_goals"] == [{"id": "BG-01"}]


def test_c03_v2_empty() -> None:
    """c03 tolerates a state without doc07b_profile/business_goals."""
    with patch("aegis_phase1.nodes.c03_strategic_implications.get_invoker") as mock_get:
        mock_invoker = MagicMock()
        mock_invoker.invoke.return_value = {
            "status": "OK",
            "parsed_output": {"implications": []},
            "total_latency_ms": 5,
        }
        mock_get.return_value = mock_invoker
        state = {"case_id": "Case_01", "applicable_regulations": ["GDPR"]}
        result = c03_strategic_implications_v2(state)
        assert result["c03_v2_status"] == "OK"
        assert result["c03_v2_implications"] == []
        inputs = mock_invoker.invoke.call_args.args[1]
        assert inputs["doc07b_profile"] == {}
        assert inputs["business_goals"] == []


def test_c03_v2_failure() -> None:
    """c03 surfaces LLM failure as the v2 status field."""
    with patch("aegis_phase1.nodes.c03_strategic_implications.get_invoker") as mock_get:
        mock_invoker = MagicMock()
        mock_invoker.invoke.return_value = {
            "status": "FAILED_AFTER_RETRIES",
            "parsed_output": None,
            "total_latency_ms": 0,
        }
        mock_get.return_value = mock_invoker
        state = {"case_id": "Case_01", "applicable_regulations": ["GDPR"]}
        result = c03_strategic_implications_v2(state)
        assert result["c03_v2_status"] == "FAILED_AFTER_RETRIES"


def test_c02_runs_after_c03() -> None:
    """Phase 1C Reduce order: c03 is invoked BEFORE c02 (c03 = runs 1st)."""
    invocation_order: list[str] = []

    def make_invoker(spec_id_for_caller: str):
        invoker = MagicMock()

        def _invoke(spec_id, *_args, **_kwargs):
            invocation_order.append(spec_id)
            return {
                "status": "OK",
                "parsed_output": (
                    {"positive_events": [], "negative_events": []}
                    if spec_id == "P1C-LLM-02-COMPOUND-EVENT"
                    else {"implications": []}
                ),
                "total_latency_ms": 1,
                "retry_count": 1,
            }

        invoker.invoke.side_effect = _invoke
        return invoker

    with (
        patch(
            "aegis_phase1.nodes.c03_strategic_implications.get_invoker",
            return_value=make_invoker("c03"),
        ),
        patch(
            "aegis_phase1.nodes.c02_domain_elaboration.get_invoker",
            return_value=make_invoker("c02"),
        ),
    ):
        state = {"case_id": "Case_01", "applicable_regulations": ["GDPR"]}
        c03_strategic_implications_v2(state)
        c02_domain_elaboration_v2(state)

    assert invocation_order == [
        "P1C-LLM-03-STRATEGIC-SYNTHESIS",
        "P1C-LLM-02-COMPOUND-EVENT",
    ]
