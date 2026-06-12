"""Tests for _validate_a node (SC-2026-50 O12)."""

from aegis_phase1.nodes._validate_a import _validate_a


def test_validate_a_with_valid_state():
    state = {
        "stakeholders": [
            {
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
        ],
        "business_goals": [
            {
                "goalId": "G001",
                "description": "Comply with GDPR",
                "goal": "GDPR compliance",
                "priority": "HIGH",
                "relatedRegulations": "GDPR",
                "successMetrics": "Zero fines",
                "strategicAlignment": "Compliance with GDPR",
            }
        ],
        "complexity_tier": "MEDIUM",
        "compliance_context": {
            "jurisdictionId": "EU",
            "scope": "EU operations",
            "timeline": "6 months",
            "budget": "100k",
            "maturityLevel": "intermediate",
        },
        "applicable_regulations": ["GDPR"],
    }
    result = _validate_a(state)
    assert "errors" in result
    assert result["errors"] == [], f"Expected no errors, got: {result['errors']}"


def test_validate_a_with_missing_stakeholders():
    state = {
        "stakeholders": [],
        "business_goals": [
            {
                "goalId": "G001",
                "description": "Comply",
                "goal": "Compliance",
                "priority": "HIGH",
                "relatedRegulations": "GDPR",
                "successMetrics": "Zero fines",
                "strategicAlignment": "Compliance",
            }
        ],
        "complexity_tier": "MEDIUM",
        "compliance_context": {
            "jurisdictionId": "EU",
            "scope": "EU",
            "timeline": "6 months",
            "budget": "100k",
            "maturityLevel": "intermediate",
        },
        "applicable_regulations": ["GDPR"],
    }
    result = _validate_a(state)
    assert any("No stakeholders" in e for e in result["errors"])


def test_validate_a_with_invalid_complexity_tier():
    state = {
        "stakeholders": [
            {
                "stakeholderId": "S001",
                "name": "CTO",
                "role": "Technical Lead",
                "stakeholderType": "internal",
                "department": "Engineering",
                "accessLevel": "HIGH",
                "organization": "Acme Corp",
                "contact": "cto@acme.com",
                "responsibilities": "Oversee",
                "influenceLevel": "HIGH",
                "interestLevel": "HIGH",
                "engagementStrategy": "Regular",
            }
        ],
        "business_goals": [
            {
                "goalId": "G001",
                "description": "Comply",
                "goal": "Compliance",
                "priority": "HIGH",
                "relatedRegulations": "GDPR",
                "successMetrics": "Zero fines",
                "strategicAlignment": "Compliance",
            }
        ],
        "complexity_tier": "INVALID",
        "compliance_context": {
            "jurisdictionId": "EU",
            "scope": "EU",
            "timeline": "6 months",
            "budget": "100k",
            "maturityLevel": "intermediate",
        },
        "applicable_regulations": ["GDPR"],
    }
    result = _validate_a(state)
    assert any("Invalid complexity_tier" in e for e in result["errors"])


def test_validate_a_with_missing_compliance_context():
    state = {
        "stakeholders": [
            {
                "stakeholderId": "S001",
                "name": "CTO",
                "role": "Technical Lead",
                "stakeholderType": "internal",
                "department": "Engineering",
                "accessLevel": "HIGH",
                "organization": "Acme Corp",
                "contact": "cto@acme.com",
                "responsibilities": "Oversee",
                "influenceLevel": "HIGH",
                "interestLevel": "HIGH",
                "engagementStrategy": "Regular",
            }
        ],
        "business_goals": [
            {
                "goalId": "G001",
                "description": "Comply",
                "goal": "Compliance",
                "priority": "HIGH",
                "relatedRegulations": "GDPR",
                "successMetrics": "Zero fines",
                "strategicAlignment": "Compliance",
            }
        ],
        "complexity_tier": "MEDIUM",
        "compliance_context": {},
        "applicable_regulations": ["GDPR"],
    }
    result = _validate_a(state)
    assert any("No compliance_context" in e for e in result["errors"])


def test_validate_a_returns_dict_with_errors_key():
    state = {
        "stakeholders": [],
        "business_goals": [],
        "complexity_tier": "",
        "compliance_context": {},
        "applicable_regulations": [],
    }
    result = _validate_a(state)
    assert isinstance(result, dict)
    assert "errors" in result
    assert isinstance(result["errors"], list)
