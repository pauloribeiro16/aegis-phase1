"""Unit tests for scripts/kg_eval/engine.py."""

from pathlib import Path

import pytest

from scripts.kg_eval.engine import (
    CypherSyntaxError,
    build_graph_for_case,
    execute_cypher,
)


def test_build_graph_and_execute_queries():
    repo_root = Path(__file__).resolve().parents[3]
    case_path = repo_root / "cases" / "case1-tinytask"
    preproc_root = repo_root / "preproc_out"

    graph = build_graph_for_case(case_path, preproc_root)
    assert len(graph.nodes) > 10, f"Expected >10 nodes, got {len(graph.nodes)}"
    assert len(graph.edges) > 5, f"Expected >5 edges, got {len(graph.edges)}"

    # Test basic query
    res = execute_cypher(graph, "MATCH (e:Enterprise) RETURN e")
    assert len(res) >= 1
    assert res[0]["case_id"] == "case1-tinytask"

    # Test system lookup
    res_sys = execute_cypher(graph, "MATCH (s:System {id: 'SYS-01'}) RETURN s")
    assert len(res_sys) == 1
    assert res_sys[0]["id"] == "SYS-01"


def test_syntax_error_detection():
    repo_root = Path(__file__).resolve().parents[3]
    case_path = repo_root / "cases" / "case1-tinytask"
    preproc_root = repo_root / "preproc_out"
    graph = build_graph_for_case(case_path, preproc_root)

    # Test invented label
    with pytest.raises(CypherSyntaxError, match="Unknown label"):
        execute_cypher(graph, "MATCH (c:InventedCompany) RETURN c")

    # Test invented relationship
    with pytest.raises(CypherSyntaxError, match="Unknown relationship"):
        execute_cypher(graph, "MATCH (s:System)-[:INVENTED_REL]->(o) RETURN o")

    # Test non-read statement
    with pytest.raises(CypherSyntaxError, match="Only read queries"):
        execute_cypher(graph, "CREATE (n:System {id: 'SYS-X'})")
