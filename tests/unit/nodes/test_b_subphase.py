"""Tests for SubPhase B nodes (b01-b06)."""

from pathlib import Path

CASE1 = str(Path(__file__).parent.parent.parent.parent / "cases" / "case1-tinytask")


class TestB01LoadRegulations:
    def test_returns_dict_with_regulations(self):
        from aegis_phase1.nodes.b01_load_regulations import b01_load_regulations

        result = b01_load_regulations(
            {
                "case_path": CASE1,
                "applicable_regulations": ["GDPR"],
            }
        )
        assert isinstance(result, dict)
        assert "regulations" in result
        assert isinstance(result["regulations"], list)

    def test_regulations_have_required_fields(self):
        from aegis_phase1.nodes.b01_load_regulations import b01_load_regulations

        result = b01_load_regulations(
            {
                "case_path": CASE1,
                "applicable_regulations": ["GDPR"],
            }
        )
        for reg in result["regulations"]:
            assert "regulationId" in reg or "id" in reg
            assert "name" in reg


class TestB02LoadClausesBatch:
    def test_returns_dict_with_regulatory_clauses(self):
        from aegis_phase1.nodes.b02_load_clauses_batch import b02_load_clauses_batch

        result = b02_load_clauses_batch(
            {
                "case_path": CASE1,
                "regulations": [{"regulationId": "REG-GDPR", "name": "GDPR"}],
            }
        )
        assert isinstance(result, dict)
        key = "regulatory_clauses" if "regulatory_clauses" in result else "clause_mappings"
        assert isinstance(result[key], list)


class TestB03MapClauseDomain:
    def test_returns_dict_with_updated_clause_mappings(self):
        from aegis_phase1.nodes.b03_map_clause_domain import b03_map_clause_domain

        result = b03_map_clause_domain(
            {
                "case_path": CASE1,
                "regulatory_clauses": [],
                "security_domains": [],
                "applicable_regulations": [],
            }
        )
        assert isinstance(result, dict)
        assert "regulatory_clauses" in result


class TestB04CoverageEntries:
    def test_returns_dict_with_coverage_entries(self):
        from aegis_phase1.nodes.b04_coverage_entries import b04_coverage_entries

        result = b04_coverage_entries(
            {
                "case_path": CASE1,
                "clause_mappings": [],
                "applicable_regulations": ["GDPR"],
            }
        )
        assert isinstance(result, dict)
        assert "domain_coverage_entries" in result or "coverage_entries" in result


class TestB05Responsibility:
    def test_returns_dict_with_responsibility_entries(self):
        from aegis_phase1.nodes.b05_responsibility import b05_responsibility

        result = b05_responsibility(
            {
                "applicable_regulations": ["REG-GDPR"],
                "regulations": [{"regulationId": "REG-GDPR", "name": "GDPR"}],
                "company_context": {"processes_personal_data": True},
            }
        )
        assert isinstance(result, dict)
        assert "responsibility_entries" in result
        assert isinstance(result["responsibility_entries"], list)

    def test_native_for_direct_obligations(self):
        from aegis_phase1.nodes.b05_responsibility import b05_responsibility

        result = b05_responsibility(
            {
                "applicable_regulations": ["REG-GDPR"],
                "regulations": [{"regulationId": "REG-GDPR", "name": "GDPR"}],
                "company_context": {"processes_personal_data": True},
            }
        )
        entries = result["responsibility_entries"]
        assert any(e.get("responsibilityType") == "NATIVE" for e in entries)


class TestB06ImplementationMapping:
    def test_returns_dict_with_implementation_mappings(self):
        from aegis_phase1.nodes.b06_implementation_mapping import b06_implementation_mapping

        result = b06_implementation_mapping(
            {
                "case_path": CASE1,
                "clause_mappings": [],
            }
        )
        assert isinstance(result, dict)
        assert "implementation_mappings" in result or "mappings" in result
