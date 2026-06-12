"""Tests for subphase orchestrators (build_subphase_* return LangGraph subgraphs)."""


class TestSubPhaseA:
    def test_build_subphase_a_returns_graph(self):
        from aegis_phase1.subphases.subphase_a import build_subphase_a

        sg = build_subphase_a()
        assert hasattr(sg, "compile") or hasattr(sg, "get_graph")

    def test_subphase_a_has_expected_nodes(self):
        from aegis_phase1.subphases.subphase_a import build_subphase_a

        sg = build_subphase_a()
        g = sg.get_graph()
        node_names = set(g.nodes.keys())
        assert "a02_stakeholders" in node_names or "stakeholders" in g.nodes
        assert "compliance_context" in g.nodes or any("compliance" in n for n in node_names)


class TestSubPhaseB:
    def test_build_subphase_b_returns_graph(self):
        from aegis_phase1.subphases.subphase_b import build_subphase_b

        sg = build_subphase_b()
        assert hasattr(sg, "compile") or hasattr(sg, "get_graph")

    def test_subphase_b_has_regulation_nodes(self):
        from aegis_phase1.subphases.subphase_b import build_subphase_b

        sg = build_subphase_b()
        g = sg.get_graph()
        node_names = set(g.nodes.keys())
        assert any("regulation" in n.lower() or "clause" in n.lower() for n in node_names)


class TestSubPhaseC:
    def test_build_subphase_c_returns_graph(self):
        from aegis_phase1.subphases.subphase_c import build_subphase_c

        sg = build_subphase_c()
        assert hasattr(sg, "compile") or hasattr(sg, "get_graph")

    def test_subphase_c_has_analysis_nodes(self):
        from aegis_phase1.subphases.subphase_c import build_subphase_c

        sg = build_subphase_c()
        g = sg.get_graph()
        node_names = set(g.nodes.keys())
        assert any("complementarity" in n or "matrix" in n for n in node_names)
