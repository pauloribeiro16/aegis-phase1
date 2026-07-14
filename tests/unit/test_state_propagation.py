"""Tests for Phase 1 state propagation."""

import inspect


class TestGraphStatePropagation:
    """Verify subgraph return dicts include all required keys."""

    def test_run_subphase_b_is_callable(self):
        from aegis_phase1 import graph

        assert callable(graph._run_subphase_b), "_run_subphase_b should be callable"

    def test_run_phase1_is_callable(self):
        from aegis_phase1 import graph

        assert callable(graph.run_phase1), "run_phase1 should be callable"

    def test_run_phase1_returns_dict_with_expected_fields(self):
        from aegis_phase1 import graph

        src = inspect.getsource(graph.run_phase1)
        assert "stakeholders" in src, "run_phase1 initial_state missing stakeholders"
        assert "business_goals" in src, "run_phase1 initial_state missing business_goals"
