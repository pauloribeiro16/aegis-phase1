"""Tests for SubPhase A nodes (a02–a07)."""
from pathlib import Path


CASE1 = str(Path(__file__).parent.parent.parent.parent / "cases" / "case1-tinytask")


class TestA02Stakeholders:
    def test_returns_dict_with_stakeholders(self):
        from aegis_phase1.nodes.a02_stakeholders import a02_stakeholders

        state = {"case_path": CASE1, "applicable_regulations": ["GDPR"]}
        result = a02_stakeholders(state)
        assert isinstance(result, dict)
        assert "stakeholders" in result
        assert len(result["stakeholders"]) > 0

    def test_stakeholders_have_required_fields(self):
        from aegis_phase1.nodes.a02_stakeholders import a02_stakeholders

        result = a02_stakeholders({"case_path": CASE1, "applicable_regulations": ["GDPR"]})
        for s in result["stakeholders"]:
            assert "stakeholderId" in s
            assert "name" in s


class TestA03BusinessGoals:
    def test_returns_dict_with_business_goals(self):
        from aegis_phase1.nodes.a03_business_goals import a03_business_goals

        result = a03_business_goals({"case_path": CASE1, "applicable_regulations": ["GDPR"]})
        assert isinstance(result, dict)
        assert "business_goals" in result
        assert len(result["business_goals"]) > 0

    def test_goals_have_goal_id_and_description(self):
        from aegis_phase1.nodes.a03_business_goals import a03_business_goals

        result = a03_business_goals({"case_path": CASE1, "applicable_regulations": ["GDPR"]})
        for g in result["business_goals"]:
            assert "goalId" in g
            assert "description" in g


class TestA04ComplexityTier:
    def test_returns_dict_with_complexity_tier(self):
        from aegis_phase1.nodes.a04_complexity_tier import a04_complexity_tier

        result = a04_complexity_tier({
            "company_context": {},
            "applicable_regulations": ["GDPR"],
        })
        assert isinstance(result, dict)
        assert "complexity_tier" in result
        assert result["complexity_tier"] in ("LOW", "MEDIUM", "HIGH")

    def test_medium_for_two_regulations(self):
        from aegis_phase1.nodes.a04_complexity_tier import a04_complexity_tier

        result = a04_complexity_tier({
            "company_context": {},
            "applicable_regulations": ["GDPR", "CRA"],
        })
        assert result["complexity_tier"] == "MEDIUM"

    def test_low_for_single_regulation(self):
        from aegis_phase1.nodes.a04_complexity_tier import a04_complexity_tier

        result = a04_complexity_tier({
            "company_context": {},
            "applicable_regulations": ["GDPR"],
        })
        assert result["complexity_tier"] == "LOW"


class TestA05ConditionalExtensions:
    def test_returns_dict_with_conditional_extensions(self):
        from aegis_phase1.nodes.a05_conditional_extensions import a05_conditional_extensions

        result = a05_conditional_extensions({
            "conditional_extensions_data": [],
            "company_context": {},
            "applicable_regulations": ["GDPR"],
        })
        assert isinstance(result, dict)
        assert "conditional_extensions" in result
        assert isinstance(result["conditional_extensions"], list)


class TestA06RegulatoryInteractions:
    def test_returns_dict_with_interactions(self):
        from aegis_phase1.nodes.a06_regulatory_interactions import a06_regulatory_interactions

        result = a06_regulatory_interactions({
            "company_context": {},
            "applicable_regulations": ["GDPR", "CRA"],
        })
        assert isinstance(result, dict)
        assert "regulatory_interactions" in result
        assert isinstance(result["regulatory_interactions"], list)


class TestA07ComplianceContext:
    def test_returns_dict_with_compliance_context(self):
        from aegis_phase1.nodes.a07_compliance_context import a07_compliance_context

        result = a07_compliance_context({
            "company_context": None,
            "stakeholders": [],
            "business_goals": [],
            "applicable_regulations": ["GDPR"],
        })
        assert isinstance(result, dict)
        assert "compliance_context" in result

    def test_jurisdiction_defaults_to_eu(self):
        from aegis_phase1.nodes.a07_compliance_context import a07_compliance_context

        result = a07_compliance_context({
            "company_context": None,
            "stakeholders": [],
            "business_goals": [],
            "applicable_regulations": ["GDPR"],
        })
        assert result["compliance_context"].get("jurisdictionId") == "EU"
