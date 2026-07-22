"""CORR-049-T7.2: OTel híbrido — root span via start_as_current_observation.

Pre-CORR-049: graph.py had a CallbackHandler attached to run_config
that captured generations, but no OTel spans. The Langfuse tree was
flat (all generations at the same level, no parentObservationId chain).

Post-CORR-049: graph.py wraps graph.invoke() in
``lf.start_as_current_observation(name="AEGIS Phase 1", as_type="chain", ...)``
so the tree is hierarchical:
    AEGIS Phase 1  (root, OTel chain)
      └ MAP/P1B/REDUCE/OUTPUT Sub-Phase  (sub-graph CHAIN spans)
          └ GENERATION (ChatOllama, captured by CallbackHandler)
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "src")


@patch("aegis_phase1.v2.graph._lf_get_client")
def test_run_phase1_graph_creates_root_span(mock_lf_get_client) -> None:
    """CORR-049-T7.2: run_phase1_graph must wrap invoke in
    start_as_current_observation so the Langfuse tree is hierarchical.
    """
    from aegis_phase1.v2.graph import run_phase1_graph

    # Mock the Langfuse client
    mock_lf_client = MagicMock()
    mock_lf_get_client.return_value = mock_lf_client
    mock_root_span = MagicMock()
    # Make the context manager work
    mock_lf_client.start_as_current_observation.return_value.__enter__.return_value = mock_root_span

    # Mock the orchestrator
    mock_orch = MagicMock()

    # Mock compile_phase1_graph so we don't build the real StateGraph
    with patch("aegis_phase1.v2.graph.compile_phase1_graph") as mock_compile:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"stage_outputs": {}, "case_path": "x"}
        mock_compile.return_value = mock_graph

        # Mock get_langfuse_callback
        with patch("aegis_phase1.v2.graph.get_langfuse_callback", return_value=(None, None)):
            run_phase1_graph(
                orchestrator=mock_orch,
                case_path="/x",
                regulatory_baseline_path="/b",
                output_dir="/o",
                callbacks=None,
                tags=["phase:phase1"],
                extra_metadata={"model": "gemma4:e2b", "case": "case1-tinytask", "run_id": "abc"},
            )

    # Assert: start_as_current_observation was called once with
    # the expected name and as_type.
    mock_lf_client.start_as_current_observation.assert_called_once()
    call_kwargs = mock_lf_client.start_as_current_observation.call_args.kwargs
    assert call_kwargs["name"] == "AEGIS Phase 1"
    assert call_kwargs["as_type"] == "chain"
    # Metadata propagated (only string/int/float/bool values).
    assert call_kwargs["metadata"]["case"] == "case1-tinytask"
    assert call_kwargs["metadata"]["model"] == "gemma4:e2b"


@patch("aegis_phase1.v2.graph._lf_get_client")
def test_run_phase1_graph_falls_back_when_otel_unavailable(mock_lf_get_client) -> None:
    """If langfuse client is None (OTel unavailable), run_phase1_graph
    must still complete via plain graph.invoke()."""
    from aegis_phase1.v2.graph import run_phase1_graph

    mock_lf_get_client.return_value = None  # OTel unavailable

    mock_orch = MagicMock()
    with patch("aegis_phase1.v2.graph.compile_phase1_graph") as mock_compile:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"stage_outputs": {}, "case_path": "x"}
        mock_compile.return_value = mock_graph

        with patch("aegis_phase1.v2.graph.get_langfuse_callback", return_value=(None, None)):
            result = run_phase1_graph(
                orchestrator=mock_orch,
                case_path="/x",
                regulatory_baseline_path="/b",
                output_dir="/o",
                callbacks=None,
                tags=["phase:phase1"],
                extra_metadata={"model": "gemma4:e2b"},
            )

    # Plain invoke still called
    mock_graph.invoke.assert_called_once()
    assert result["case_path"] == "x"
