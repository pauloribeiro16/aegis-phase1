"""Test utilities and state builders."""

from typing import Any

SAMPLE_STAKEHOLDER = {
    "stakeholderId": "S001",
    "name": "CTO",
    "role": "Technical Lead",
    "stakeholderType": "internal",
    "department": "Engineering",
    "accessLevel": "HIGH",
    "organization": "Acme Corp",
    "contact": "cto@acme.com",
    "responsibilities": "Oversee architecture",
    "influenceLevel": "HIGH",
    "interestLevel": "HIGH",
    "engagementStrategy": "Regular updates",
}

SAMPLE_BUSINESS_GOAL = {
    "goalId": "G001",
    "description": "GDPR compliance",
    "goal": "Compliance",
    "priority": "HIGH",
    "relatedRegulations": "GDPR",
    "successMetrics": "Zero fines",
    "strategicAlignment": "Compliance with GDPR",
}

SAMPLE_COMPLIANCE_CONTEXT = {
    "jurisdictionId": "EU",
    "scope": "EU operations",
    "timeline": "6 months",
    "budget": "100k",
    "maturityLevel": "intermediate",
}


def build_minimal_state(**overrides: Any) -> dict[str, Any]:
    """Build a minimal valid state with optional overrides."""
    state = {
        "stakeholders": [dict(SAMPLE_STAKEHOLDER)],
        "business_goals": [dict(SAMPLE_BUSINESS_GOAL)],
        "complexity_tier": "MEDIUM",
        "compliance_context": dict(SAMPLE_COMPLIANCE_CONTEXT),
        "applicable_regulations": ["GDPR", "CRA"],
        "errors": [],
        "doc_paths": {},
        "current_phase": "subphase_a",
    }
    state.update(overrides)
    return state
