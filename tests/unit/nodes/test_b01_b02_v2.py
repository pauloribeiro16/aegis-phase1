"""Tests for b01 and b02 v2 functions (P1B-LLM-01 + P1B-LLM-02)."""

from unittest.mock import MagicMock, patch

from aegis_phase1.nodes.b01_load_regulations import b01_load_regulations_v2
from aegis_phase1.nodes.b02_load_clauses_batch import b02_load_clauses_batch_v2


def test_b01_v2_imports() -> None:
    """b01_load_regulations_v2 exists and is callable."""
    assert callable(b01_load_regulations_v2)


def test_b01_v2_calls_invoker() -> None:
    """b01 calls get_invoker().invoke with P1B-LLM-01-INTERPRETATION."""
    with patch("aegis_phase1.nodes.b01_load_regulations.get_invoker") as mock_get:
        mock_invoker = MagicMock()
        mock_invoker.invoke.return_value = {
            "status": "OK",
            "parsed_output": {
                "interpretations": [
                    {
                        "entry_id": "TIPO2-TEST",
                        "applicable": True,
                        "regulatory_baseline_refs": ["test"],
                        "company_fact_refs": [],
                    }
                ],
                "derogations": [],
            },
            "total_latency_ms": 100,
            "retry_count": 1,
        }
        mock_get.return_value = mock_invoker

        state = {
            "case_id": "Case_01",
            "applicable_regulations": ["GDPR", "CRA"],
        }
        result = b01_load_regulations_v2(state)
        assert result["b01_v2_status"] == "OK"
        assert "GDPR" in result["b01_v2_per_reg"]
        assert "CRA" in result["b01_v2_per_reg"]
        assert len(result["b01_v2_aggregated_interpretations"]) == 2
        assert mock_invoker.invoke.call_count == 2
        for call in mock_invoker.invoke.call_args_list:
            assert call.args[0] == "P1B-LLM-01-INTERPRETATION"


def test_b01_v2_empty_applicable() -> None:
    """b01 returns empty results if no applicable regulations."""
    with patch("aegis_phase1.nodes.b01_load_regulations.get_invoker") as mock_get:
        mock_get.return_value.invoke.return_value = {"status": "OK", "parsed_output": {}}
        state = {"case_id": "Case_01", "applicable_regulations": []}
        result = b01_load_regulations_v2(state)
        assert result["b01_v2_per_reg"] == {}
        assert result["b01_v2_aggregated_interpretations"] == []
        assert result["b01_v2_aggregated_derogations"] == []
        # 0 invoker calls because no regs to process.
        assert mock_get.return_value.invoke.call_count == 0


def test_b01_v2_handles_failure() -> None:
    """b01 handles LLM failure gracefully."""
    with patch("aegis_phase1.nodes.b01_load_regulations.get_invoker") as mock_get:
        mock_invoker = MagicMock()
        mock_invoker.invoke.return_value = {
            "status": "FAILED_AFTER_RETRIES",
            "parsed_output": None,
            "total_latency_ms": 0,
        }
        mock_get.return_value = mock_invoker
        state = {"case_id": "Case_01", "applicable_regulations": ["GDPR"]}
        result = b01_load_regulations_v2(state)
        assert result["b01_v2_status"] == "FAILED_AFTER_RETRIES"
        assert result["b01_v2_aggregated_interpretations"] == []


def test_b02_v2_imports() -> None:
    """b02_load_clauses_batch_v2 exists and is callable."""
    assert callable(b02_load_clauses_batch_v2)


def test_b02_v2_calls_invoker() -> None:
    """b02 calls get_invoker().invoke with P1B-LLM-02-RATIONALE."""
    with patch("aegis_phase1.nodes.b02_load_clauses_batch.get_invoker") as mock_get:
        mock_invoker = MagicMock()
        mock_invoker.invoke.return_value = {
            "status": "OK",
            "parsed_output": {
                "synthesis": {
                    "rationale": "test rationale",
                    "implications": [],
                    "gaps": [],
                }
            },
            "total_latency_ms": 200,
            "retry_count": 1,
        }
        mock_get.return_value = mock_invoker
        state = {
            "case_id": "Case_01",
            "applicable_regulations": ["GDPR"],
        }
        result = b02_load_clauses_batch_v2(state)
        assert result["b02_v2_status"] == "OK"
        assert "GDPR" in result["b02_v2_per_reg_synthesis"]
        args = mock_invoker.invoke.call_args
        assert args.args[0] == "P1B-LLM-02-RATIONALE"


def test_b02_v2_empty() -> None:
    """b02 returns empty aggregate if no applicable regulations."""
    with patch("aegis_phase1.nodes.b02_load_clauses_batch.get_invoker") as mock_get:
        mock_get.return_value.invoke.return_value = {
            "status": "OK",
            "parsed_output": {},
            "total_latency_ms": 0,
        }
        state = {"case_id": "Case_01", "applicable_regulations": []}
        result = b02_load_clauses_batch_v2(state)
        assert result["b02_v2_aggregated_synthesis"] == {}
        assert result["b02_v2_per_reg_synthesis"] == {}
        assert mock_get.return_value.invoke.call_count == 0


def test_b02_v2_failure() -> None:
    """b02 surfaces LLM failure as aggregate status."""
    with patch("aegis_phase1.nodes.b02_load_clauses_batch.get_invoker") as mock_get:
        mock_get.return_value.invoke.return_value = {
            "status": "FAILED",
            "parsed_output": None,
            "total_latency_ms": 0,
        }
        state = {"case_id": "Case_01", "applicable_regulations": ["GDPR"]}
        result = b02_load_clauses_batch_v2(state)
        assert result["b02_v2_status"] == "FAILED"
