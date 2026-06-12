"""Tests for Phase 1 graph topology (SC-2026-50 O1)."""

from aegis_phase1.graph import build_phase1_graph


def test_phase1_graph_top_level_nodes():
    g = build_phase1_graph()
    nodes = set(g.get_graph().nodes.keys())
    expected = {"parse_inputs", "subphase_a", "subphase_b", "subphase_c"}
    assert expected.issubset(nodes), f"Missing top-level nodes: {expected - nodes}"


def test_subphase_b_runs_sequentially():
    g = build_phase1_graph()
    graph = g.get_graph()
    top_nodes = set(graph.nodes.keys())
    # No parallel Send nodes at top level — subphase_b is sequential
    send_nodes = {
        n
        for n in top_nodes
        if hasattr(graph.nodes[n], "metadata") and "Send" in str(graph.nodes[n])
    }
    assert not send_nodes, f"Unexpected parallel Send nodes at top level: {send_nodes}"


def test_subphase_c_node_exists():
    g = build_phase1_graph()
    nodes = set(g.get_graph().nodes.keys())
    assert "subphase_c" in nodes, "subphase_c node not found in graph"
