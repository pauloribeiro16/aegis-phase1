"""Shared test fixtures for phase1."""
import os
from pathlib import Path
from typing import Any

import pytest

# ─── Module-level constants ──────────────────────────────────────────
CASE1_DIR = Path(__file__).parent.parent / "cases" / "case1-tinytask"
SAMPLE_STAKEHOLDER = {
    "stakeholderId": "S001",
    "name": "CTO",
    "role": "Technical Lead",
    "stakeholderType": "internal",
    "department": "Engineering",
    "accessLevel": "HIGH",
    "organization": "Acme Corp",
}
SAMPLE_BUSINESS_GOAL = {
    "goalId": "G001",
    "description": "GDPR compliance",
    "goal": "Compliance",
    "priority": "HIGH",
    "relatedRegulations": "GDPR",
    "successMetrics": "Zero fines",
    "strategicAlignment": "Compliance",
}


# ─── Pytest configuration ────────────────────────────────────────────


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: requires Ollama or running services")
    config.addinivalue_line("markers", "slow: long-running test (>5s)")


def pytest_addoption(parser):
    """Add --skip-slow flag."""
    parser.addoption(
        "--skip-slow",
        action="store_true",
        default=False,
        help="Skip tests marked as slow",
    )


def pytest_collection_modifyitems(config, items):
    """Skip slow tests when --skip-slow is passed."""
    if config.getoption("--skip-slow"):
        skip_slow = pytest.mark.skip(reason="Skipped with --skip-slow")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def case1_path() -> Path:
    """Path to case1-tinytask directory."""
    return CASE1_DIR


@pytest.fixture
def mock_llm_env(monkeypatch):
    """Set MOCK_LLM=true so no real API calls are made."""
    monkeypatch.setenv("MOCK_LLM", "true")


@pytest.fixture
def minimal_state() -> dict[str, Any]:
    """Minimal valid Phase1State for subphase-a-level tests."""
    return {
        "stakeholders": [dict(SAMPLE_STAKEHOLDER)],
        "business_goals": [dict(SAMPLE_BUSINESS_GOAL)],
        "complexity_tier": "MEDIUM",
        "compliance_context": {
            "jurisdictionId": "EU",
            "scope": "EU operations",
            "timeline": "6 months",
            "budget": "100k",
            "maturityLevel": "intermediate",
        },
        "applicable_regulations": ["GDPR", "CRA"],
        "errors": [],
        "doc_paths": {},
        "current_phase": "subphase_a",
    }


@pytest.fixture
def regulation_state(minimal_state) -> dict[str, Any]:
    """State extended with regulation data for subphase-b tests."""
    return {
        **minimal_state,
        "current_phase": "subphase_b",
        "regulations": [
            {"regulationId": "REG-GDPR", "name": "GDPR", "jurisdiction": "EU"},
            {"regulationId": "REG-CRA", "name": "CRA", "jurisdiction": "EU"},
        ],
        "clause_mappings": [],
        "applicability_matrix": {
            "assessments": [
                {"regulationId": "REG-GDPR", "applicable": True, "confidence": "HIGH"},
            ]
        },
    }


@pytest.fixture
def analysis_state(regulation_state) -> dict[str, Any]:
    """State extended for subphase-c tests."""
    return {
        **regulation_state,
        "current_phase": "subphase_c",
        "complementarity_analysis": {
            "overlaps": [],
            "tensions": [],
        },
        "strategic_implications": [],
        "regulatory_gaps": [],
        "coverage_matrix": {},
        "coverage_summary": {"total_subdomains": 0},
    }


@pytest.fixture
def no_errors() -> list:
    """Empty error list for valid-state assertions."""
    return []


@pytest.fixture
def skip_if_no_ollama():
    """Skip test if OLLAMA_BASE_URL is not reachable."""
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        import urllib.request

        urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=2)
    except Exception:
        pytest.skip(f"Ollama not reachable at {ollama_url}")
