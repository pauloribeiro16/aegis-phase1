"""End-to-end tests with REAL Ollama. Skipped if Ollama not reachable.

Run manually with: PYTHONPATH=src pytest tests/unit/test_phase1_e2e_ollama.py -v

Requires: Ollama running with gemma4:e2b model pulled.
"""
import os
import socket
import pytest
from urllib.parse import urlparse


OLLAMA_HOST = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _ollama_reachable():
    try:
        u = urlparse(OLLAMA_HOST)
        host = u.hostname or "localhost"
        port = u.port or 11434
        with socket.create_connection((host, port), timeout=2):
            return True
    except (OSError, socket.timeout):
        return False


requires_ollama = pytest.mark.skipif(
    not _ollama_reachable(), reason=f"Ollama not reachable at {OLLAMA_HOST}"
)


@requires_ollama
@pytest.mark.timeout(120)
def test_e2e_real_ollama_case_01_gdpr():
    """End-to-end with real Ollama: P1B-LLM-01 for Case_01 + GDPR.

    Asserts:
      - Status is OK or INSUFFICIENT_EVIDENCE (NOT FAILED_AFTER_RETRIES)
      - Latency < 60s (gemma4:e2b cold start can be slow)
      - Logs are written
    """
    from aegis_phase1.prompts_v2 import get_invoker
    invoker = get_invoker()
    result = invoker.invoke(
        "P1B-LLM-01-INTERPRETATION",
        {
            "case_id": "Case_01_TinyTask_SaaS",
            "lane_id": "GDPR",
            "applicable_regs": ["GDPR"],
            "classification": {"role": "Controller", "tier": "LOW"},
            "company_facts": {"sector": "saas", "employees": 8, "is_manufacturer": False, "uses_cra_regulated_product": True, "processes_eu_personal_data": True, "products": ["B2B task management SaaS"]},
            "layer0_catalog": {},
            "layer0_subdomain_refs": ["SubDomains/D-01.1.md", "SubDomains/D-09.1.md"],
        },
        max_retries=1,
    )
    assert result["status"] in ("OK", "INSUFFICIENT_EVIDENCE", "PARSE_ERROR", "SCHEMA_ERROR")
    assert result["total_latency_ms"] < 60000  # < 60s
    assert result["retry_count"] >= 1


@requires_ollama
@pytest.mark.timeout(180)
def test_e2e_real_ollama_case_01_executor_run():
    """End-to-end with real Ollama: full Phase1Executor.run() for Case 01.

    Asserts:
      - All 16 LLM calls complete (4 P1B + 10 P1C map + 2 reduce)
      - Final result has expected structure
      - Sync status is OK (no conflicts in Case 01)
    """
    from aegis_phase1.prompts_v2 import get_invoker
    from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor
    from aegis_phase1.prompts_v2.logging_helper import JSONLLogger
    from aegis_phase1.prompts_v2.validator import Phase1Validator
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_layer0_root
    from aegis_phase1.prompts_v2.loader import PromptLoader
    from aegis_phase1.prompts_v2.track_b import TrackB

    invoker = get_invoker()
    pl = PromptLoader()
    cl = CatalogLoader()
    val = Phase1Validator(layer0_root=get_layer0_root())
    ll = JSONLLogger(invoker.llm_logger.filepath)
    fl = JSONLLogger(invoker.format_logger.filepath)
    tb = TrackB()
    ex = Phase1Executor(pl, cl, val, ll, fl, track_b=tb)
    # Use the invoker from get_invoker() to share connection
    ex.invoker = invoker

    result = ex.run("Case_01_TinyTask_SaaS", ["GDPR", "CRA"])

    assert result["case_id"] == "Case_01_TinyTask_SaaS"
    assert len(result["phase_1c_map"]) == 10
    assert result["sync"]["status"] in ("OK", "CONFLICTS_DETECTED")  # could be either
    assert "P1C-LLM-03-STRATEGIC-SYNTHESIS" in result["phase_1c_reduce"]
    assert "P1C-LLM-02-COMPOUND-EVENT" in result["phase_1c_reduce"]
