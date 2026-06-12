"""_mock_data — Mock LLM responses for testing with MOCK_LLM=true.

Each function returns a list of dicts matching the Pydantic model schema
for the corresponding node.  The dicts use aliases (camelCase) so they
can be validated by the models directly.
"""

import os


def is_mock_mode() -> bool:
    """Return True if MOCK_LLM env var is enabled."""
    return os.getenv("MOCK_LLM", "").lower() in ("true", "1", "yes")


def mock_stakeholders() -> list[dict]:
    """a02_stakeholders mock data — 3 stakeholders."""
    return [
        {
            "stakeholderId": "STK-CEO-01",
            "name": "Mock CEO",
            "role": "CEO",
            "stakeholderType": "internal",
            "department": "Executive",
            "accessLevel": "HIGH",
        },
        {
            "stakeholderId": "STK-CTO-01",
            "name": "Mock CTO",
            "role": "CTO",
            "stakeholderType": "internal",
            "department": "Engineering",
            "accessLevel": "HIGH",
        },
        {
            "stakeholderId": "STK-DPO-01",
            "name": "Mock DPO",
            "role": "DPO",
            "stakeholderType": "internal",
            "department": "Legal",
            "accessLevel": "MEDIUM",
        },
    ]


def mock_business_goals() -> list[dict]:
    """a03_business_goals mock data — 2 goals."""
    return [
        {
            "goalId": "BG-01",
            "description": "Achieve GDPR compliance for all data processing activities",
            "priority": "HIGH",
            "strategicAlignment": "Regulatory risk mitigation",
        },
        {
            "goalId": "BG-02",
            "description": "Maintain product security posture across the portfolio",
            "priority": "MEDIUM",
            "strategicAlignment": "Market trust and customer confidence",
        },
    ]


def mock_regulatory_interactions() -> list[dict]:
    """a06_regulatory_interactions mock data — 2 interactions."""
    return [
        {
            "interactionId": "RI-001",
            "interactionType": "TEMPORAL_CONFLICT",
            "involvedRegulations": ["GDPR", "NIS2"],
            "conflictDescription": "GDPR enforcement predates NIS2, creating a gap in incident reporting timelines",
            "resolutionPrinciple": "Apply NIS2 24-hour reporting window for incidents involving personal data breaches",
        },
        {
            "interactionId": "RI-002",
            "interactionType": "REQUIREMENT_CONFLICT",
            "involvedRegulations": ["GDPR", "CRA"],
            "conflictDescription": "CRA requires default-on security updates while GDPR requires minimal data processing",
            "resolutionPrinciple": "Separate security update telemetry from personal data processing",
        },
    ]


def mock_clauses_for_regulation(regulation_id: str) -> list[dict]:
    """b02_load_clauses_batch mock data — enriched clauses for a regulation."""
    return [
        {
            "clauseId": f"{regulation_id}-CLAUSE-001",
            "articleReference": "Art. 5",
            "description": f"Core obligation clause for {regulation_id}",
            "normativeStrength": "MANDATORY_UNCONDITIONAL",
            "obligatedParty": ["CONTROLLER"],
            "obligationType": "CONTINUOUS",
            "normativeWeight": 0.9,
            "isAtomic": True,
            "parentClauseId": "",
            "siblingClauseIds": [],
            "sanctionReference": "",
        },
        {
            "clauseId": f"{regulation_id}-CLAUSE-002",
            "articleReference": "Art. 10",
            "description": f"Reporting obligation clause for {regulation_id}",
            "normativeStrength": "MANDATORY_CONDITIONAL",
            "obligatedParty": ["ESSENTIAL_OR_IMPORTANT_ENTITY"],
            "obligationType": "TRIGGERED",
            "normativeWeight": 0.7,
            "isAtomic": True,
            "parentClauseId": "",
            "siblingClauseIds": [],
            "sanctionReference": "",
        },
    ]


def mock_clause_domain_mappings(unmapped_clauses: list[dict]) -> list[dict]:
    """b03_map_clause_domain mock data — map unmapped clauses to D-UNMAPPED."""
    mappings = []
    for clause in unmapped_clauses:
        clause_id = clause.get("clauseId", clause.get("clause_id", ""))
        mappings.append({"clauseId": clause_id, "subDomainId": "D-UNMAPPED"})
    return mappings


def mock_complementarity_analyses() -> list[dict]:
    """c01_complementarity mock data — 2 analyses."""
    return [
        {
            "analysisId": "CA-001",
            "sharedScope": 0.65,
            "jaccardIndex": 0.45,
            "overlapType": "SYNERGISTIC",
            "analysisDate": "2026-01-01",
            "structuralConnectedness": 0.7,
            "regulation1Id": "GDPR",
            "regulation2Id": "NIS2",
            "description": "GDPR and NIS2 share overlapping data protection and incident reporting requirements",
        },
        {
            "analysisId": "CA-002",
            "sharedScope": 0.5,
            "jaccardIndex": 0.3,
            "overlapType": "STRUCTURAL_TENSION",
            "analysisDate": "2026-01-01",
            "structuralConnectedness": 0.55,
            "regulation1Id": "GDPR",
            "regulation2Id": "CRA",
            "description": "GDPR and CRA have tension between security-by-default and minimal data processing",
        },
    ]


def mock_domain_elaboration_entries() -> list[dict]:
    """c02_domain_elaboration mock data — 3 entries."""
    return [
        {
            "entryId": "DE-001",
            "analysisId": "CA-001",
            "subDomainId": "D-GOVERNANCE",
            "elaborationFactor": 1.2,
            "dominantRegulation": "GDPR",
            "relationType": "OVERLAP",
            "normativeIntensity": 0.9,
            "weightedScore": 1.08,
            "notes": "Strong governance overlap between GDPR and NIS2",
        },
        {
            "entryId": "DE-002",
            "analysisId": "CA-001",
            "subDomainId": "D-INCIDENT",
            "elaborationFactor": 1.5,
            "dominantRegulation": "NIS2",
            "relationType": "CUMULATIVE_REINFORCEMENT",
            "normativeIntensity": 0.8,
            "weightedScore": 1.2,
            "notes": "Incident reporting requirements reinforce across NIS2 and GDPR",
        },
        {
            "entryId": "DE-003",
            "analysisId": "CA-002",
            "subDomainId": "D-SECURITY",
            "elaborationFactor": 0.8,
            "dominantRegulation": "CRA",
            "relationType": "CONFLICT",
            "normativeIntensity": 0.7,
            "weightedScore": 0.56,
            "notes": "CRA security-by-default conflicts with GDPR data minimization",
        },
    ]


def mock_strategic_implications() -> list[dict]:
    """c03_strategic_implications mock data — 2 implications."""
    return [
        {
            "implicationId": "SI-01",
            "description": "Dual compliance with GDPR and NIS2 requires unified incident reporting process",
            "businessImpact": "Medium — process consolidation needed",
            "complianceRisk": "HIGH — gaps in reporting timelines if not addressed",
        },
        {
            "implicationId": "SI-02",
            "description": "CRA product security requirements need reconciliation with GDPR privacy-by-design",
            "businessImpact": "High — product architecture changes may be required",
            "complianceRisk": "MEDIUM — existing security measures partially cover both",
        },
    ]
