"""Tests for SubPhase C nodes (c01-c05)."""


class TestC01Complementarity:
    def test_returns_dict_with_complementarity_data(self):
        from aegis_phase1.nodes.c01_complementarity import c01_complementarity

        result = c01_complementarity(
            {
                "applicable_regulations": ["GDPR", "CRA"],
                "domain_coverage_entries": [],
            }
        )
        assert isinstance(result, dict)
        assert "complementarity_analyses" in result or "complementarity_analysis" in result


class TestC02DomainElaboration:
    def test_returns_dict_with_elaboration_entries(self):
        from aegis_phase1.nodes.c02_domain_elaboration import c02_domain_elaboration

        result = c02_domain_elaboration(
            {
                "complementarity_analyses": [],
                "domain_coverage_entries": [],
            }
        )
        assert isinstance(result, dict)
        assert "domain_elaboration_entries" in result or "elaboration_entries" in result


class TestC03StrategicImplications:
    def test_returns_dict_with_implications(self):
        from aegis_phase1.nodes.c03_strategic_implications import c03_strategic_implications

        result = c03_strategic_implications(
            {
                "business_goals": [],
                "company_context": {},
                "complementarity_analyses": [],
                "domain_coverage_entries": [],
            }
        )
        assert isinstance(result, dict)
        assert "strategic_implications" in result


class TestC04ObligationShells:
    def test_returns_dict_with_obligation_shells(self):
        from aegis_phase1.nodes.c04_obligation_shells import c04_obligation_shells

        result = c04_obligation_shells(
            {
                "regulations": [],
                "clause_mappings": [],
            }
        )
        assert isinstance(result, dict)
        assert "obligation_shells" in result or "regulatory_obligations" in result


class TestC05Matrix:
    def test_returns_dict_with_matrix_data(self):
        from aegis_phase1.nodes.c05_matrix import c05_matrix

        result = c05_matrix(
            {
                "domain_coverage_entries": [],
                "complementarity_analysis": {},
                "strategic_implications": [],
                "regulatory_gaps": [],
                "company_context": {},
                "stakeholders": [],
                "business_goals": [],
            }
        )
        assert isinstance(result, dict)
        assert "coverage_matrix" in result or "structured_compliance_matrix" in result
