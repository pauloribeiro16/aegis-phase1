"""Shared fixtures for the v2 filter unit tests.

The fixtures build a minimal ``V2State`` in-memory without touching
disk. They cover:
    - 4 sub-domains (D-04.1 .. D-04.4) plus a sibling (D-05.1)
    - 2 regulations (GDPR, CRA)
    - 3 clause mappings per sub-domain
    - 1 ambiguity entry + 1 cross-regulation entry per sub-domain
    - A tech_stack with AWS / Firebase / GitHub Actions

Tests that need to exercise edge cases (empty state, missing
ontology, etc.) override individual fields rather than redefining
the whole state.
"""

from __future__ import annotations

from typing import Any

import pytest

from aegis_phase1.models import ComplexityTier
from aegis_phase1.v2.state import CompanyContext, SubDomainDef, V2State


def _make_subdomain(sid: str, title: str, regs: list[str]) -> SubDomainDef:
    return SubDomainDef(
        document_id=f"AEGIS-PREPROC-SD-{sid}",
        title=title,
        status="DRAFT",
        section1_crda=[],
        section2_hso={
            "hl_objective": f"High-level objective for {sid}.",
            "per_reg_sos": [
                {
                    "id": f"{sid}.{i + 1} — Sub-SO for {reg}",
                    "text": f"Per-regulation text for {sid} under {reg}.",
                }
                for i, reg in enumerate(regs)
            ],
            "emergent_tensions": [],
        },
        section3_requirements=[
            {"id": f"REQ-{sid}-01", "description": f"Volere req for {sid}", "priority": "MUST"},
        ],
        frontmatter={"document_id": f"AEGIS-PREPROC-SD-{sid}"},
    )


@pytest.fixture
def mock_company_context() -> CompanyContext:
    return CompanyContext(
        company_name="MockCo Lda.",
        sector="Technology/Software",
        jurisdiction="Portugal (EU)",
        employees=12,
        revenue=1_500_000.0,
        scale="MICRO",
        applicable_regs=["GDPR", "CRA"],
        complexity_tier=ComplexityTier.MEDIUM,
        security_fte=0.5,
        tech_stack=["AWS", "Firebase", "GitHub Actions"],
    )


@pytest.fixture
def mock_subdomains() -> dict[str, SubDomainDef]:
    return {
        "D-04.1": _make_subdomain("D-04.1", "Incident Detection & Triage", ["CRA"]),
        "D-04.2": _make_subdomain("D-04.2", "Containment & Mitigation", ["GDPR", "CRA"]),
        "D-04.3": _make_subdomain("D-04.3", "Regulatory Notification", ["GDPR", "CRA"]),
        "D-04.4": _make_subdomain("D-04.4", "Data Restoration & Recovery", ["GDPR"]),
        "D-05.1": _make_subdomain("D-05.1", "Data Minimization", ["GDPR"]),
    }


@pytest.fixture
def mock_ontology() -> dict:
    return {
        "regulations": [
            {"id": "REG-GDPR", "abbreviation": "GDPR", "name": "General Data Protection Regulation"},
            {"id": "REG-CRA", "abbreviation": "CRA", "name": "Cyber Resilience Act"},
        ],
        "subdomains": {
            "covered": [
                {"id": "D-04.1", "domain_id": "D-04", "source_regulations": ["CRA"]},
                {"id": "D-04.2", "domain_id": "D-04", "source_regulations": ["GDPR", "CRA"]},
                {"id": "D-04.3", "domain_id": "D-04", "source_regulations": ["GDPR", "CRA"]},
                {"id": "D-04.4", "domain_id": "D-04", "source_regulations": ["GDPR"]},
                {"id": "D-05.1", "domain_id": "D-05", "source_regulations": ["GDPR"]},
            ],
        },
        "clause_mappings": [
            {
                "clause_id": "GDPR-C23",
                "regulation_id": "REG-GDPR",
                "article": "Art. 33",
                "description": "Breach notification to authority",
                "maps_to_subdomain": "D-04.3",
                "text": "A" * 5000,
            },
            {
                "clause_id": "GDPR-C24",
                "regulation_id": "REG-GDPR",
                "article": "Art. 34",
                "description": "Breach notification to subject",
                "maps_to_subdomain": "D-04.3",
                "text": "Short text",
            },
            {
                "clause_id": "CRA-C20",
                "regulation_id": "REG-CRA",
                "article": "Art. 20",
                "description": "Reporting incidents",
                "maps_to_subdomain": "D-04.3",
            },
            {
                "clause_id": "GDPR-C16",
                "regulation_id": "REG-GDPR",
                "article": "Art. 19",
                "description": "Notification obligation",
                "maps_to_subdomain": "D-04.4",
            },
            {
                "clause_id": "GDPR-C01",
                "regulation_id": "REG-GDPR",
                "article": "Art. 1",
                "description": "Lawfulness",
                "maps_to_subdomain": "D-05.1",
            },
        ],
    }


@pytest.fixture
def mock_preprocessing() -> dict:
    return {
        "ambiguities": [
            {
                "id": "TC-001",
                "filepath": "/dev/null",
                "description": "Timeline divergence between GDPR 72h and CRA 24h.",
                "title": "Breach notification timeline",
                "frontmatter": {
                    "document_id": "TC-001",
                    "title": "Breach notification timeline",
                    "domain_id": "D-04.3",
                    "resolution": "Use 24h as internal standard for all breach notifications.",
                },
            },
            {
                "id": "TC-002",
                "filepath": "/dev/null",
                "description": "Processor vs Manufacturer obligations overlap.",
                "title": "Processor-Manufacturer scope",
                "frontmatter": {
                    "document_id": "TC-002",
                    "domain_id": "D-06.1",
                },
            },
            {
                "id": "TC-003",
                "filepath": "/dev/null",
                "description": "NIS 2 scope ambiguous for sub-contractors.",
                "title": "NIS 2 sub-contractor scope",
                "frontmatter": {
                    "document_id": "TC-003",
                    "applicable_regs": ["NIS2"],
                },
            },
        ],
        "cross_regulation": [
            {
                "domain_id": "D-04.3",
                "pairs": [
                    {
                        "reg_pair": "GDPR-CRA",
                        "text": "Timeline divergence: GDPR 72h vs CRA 24h breach notification.",
                    },
                    {
                        "reg_pair": "GDPR-NIS2",
                        "text": "Scope overlap on incident definitions and reporting thresholds.",
                    },
                ],
                "analysis_text": "Two divergent timelines across regulations.",
            },
            {
                "domain_id": "D-05.1",
                "pairs": [
                    {
                        "reg_pair": "GDPR-CRA",
                        "text": "Minimisation principles overlap with secure-by-design.",
                    },
                ],
            },
            {
                "domain_id": "D-04",
                "pairs": [
                    {
                        "reg_pair": "GDPR-CRA",
                        "text": "Domain-level overview without per-subdomain detail.",
                    },
                ],
            },
        ],
    }


@pytest.fixture
def mock_state(
    mock_company_context: CompanyContext,
    mock_subdomains: dict[str, SubDomainDef],
    mock_ontology: dict,
    mock_preprocessing: dict,
) -> V2State:
    state: V2State = {
        "current_stage": "LOADED",
        "case_path": "/tmp/mock_case",
        "preprocessing_path": "/tmp/mock_preproc",
        "company_context": mock_company_context,
        "taxonomy_entries": [],
        "ontology": mock_ontology,
        "regulations": mock_ontology["regulations"],
        "subdomains": mock_subdomains,
        "preprocessing": mock_preprocessing,
        "domain_results": {},
        "aggregated_data": {},
        "output_paths": {},
        "errors": [],
    }
    return state


def make_empty_state() -> V2State:
    """Return a completely empty V2State (no context, ontology, etc.)."""
    return {
        "current_stage": "INIT",
        "case_path": "",
        "preprocessing_path": "",
        "company_context": None,
        "taxonomy_entries": [],
        "ontology": {},
        "regulations": [],
        "subdomains": {},
        "preprocessing": {},
        "domain_results": {},
        "aggregated_data": {},
        "output_paths": {},
        "errors": [],
    }


__all__ = [
    "make_empty_state",
    "mock_company_context",
    "mock_ontology",
    "mock_preprocessing",
    "mock_state",
    "mock_subdomains",
]