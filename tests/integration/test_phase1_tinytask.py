"""Smoke E2E: Phase 1 runs on Case_01_TinyTask_SaaS without Neo4j and produces Doc 04-07."""

import os
from pathlib import Path

import pytest

METHODOLOGY_CASES = os.getenv(
    "METHODOLOGY_CASES_PATH",
    "/home/epmq-cyber/Desktop/Methodology-main/02_CASES",  # dev default
)
TINYTASK_CASE_DIR = Path(METHODOLOGY_CASES) / "Case_01_TinyTask_SaaS"
COMMON_DIR = TINYTASK_CASE_DIR / "00_COMMON"
PHASE1_OUTPUT_DIR = TINYTASK_CASE_DIR / "01_PHASE1_CONTEXT"


def _check_ollama_available() -> bool:
    """Best-effort check if Ollama is reachable."""
    import urllib.error
    import urllib.request

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        urllib.request.urlopen(f"{host}/api/tags", timeout=2)
        return True
    except (urllib.error.URLError, ConnectionError, OSError):
        return False


@pytest.mark.skipif(
    not COMMON_DIR.exists(),
    reason=f"Methodology case not found: {COMMON_DIR}",
)
@pytest.mark.skipif(
    not _check_ollama_available(),
    reason="Ollama not available — skipping E2E smoke",
)
class TestPhase1TinyTaskE2E:
    def test_run_phase1_produces_doc_04_to_07(self):
        """Run Phase 1 on Case_01_TinyTask_SaaS — verify all 4 docs are produced."""
        from aegis_phase1.graph import run_phase1

        result = run_phase1(
            case_path=str(TINYTASK_CASE_DIR),
            verbose=False,
            skip_interrupt=True,
        )

        assert isinstance(result, dict)
        assert "errors" in result or "error" in result

        for doc in [
            "04_Company_Context_Assessment",
            "05_Regulatory_Applicability",
            "06_Clause_Mapping_Matrix",
            "07_Structured_Compliance_Matrix",
        ]:
            found = False
            for ext in ["_filled.md", ".md"]:
                candidate = PHASE1_OUTPUT_DIR / f"{doc}{ext}"
                if candidate.exists():
                    found = True
                    break
            if not found:
                candidate2 = TINYTASK_CASE_DIR / f"{doc}_filled.md"
                if candidate2.exists():
                    found = True
            assert found, f"Doc {doc} not produced (neither in 01_PHASE1_CONTEXT nor case root)"

    def test_run_phase1_no_neo4j_in_path(self):
        """Static check: the Phase 1 code path does not import neo4j/kg/cypher execution."""
        import inspect

        from aegis_phase1 import graph, nodes

        graph_source = inspect.getsource(graph)
        nodes_source = ""
        for name in dir(nodes):
            obj = getattr(nodes, name)
            if inspect.isfunction(obj) and obj.__module__ == nodes.__name__:
                nodes_source += inspect.getsource(obj)

        combined = graph_source + nodes_source
        assert "core.kg" not in combined, "core.kg import found in Phase 1"
        assert "exec_cypher" not in combined, "exec_cypher call found in Phase 1"
        assert "neo4j" not in combined.lower(), "neo4j reference found in Phase 1"
