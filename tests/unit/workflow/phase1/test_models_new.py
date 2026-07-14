"""Verify Pydantic models instantiate correctly."""

from aegis_phase1.models import (
    ComplementarityAnalysis,
    ComplementarityEntry,
    DomainElaborationEntry,
    NormativeStrength,
    ObligationType,
    RegulatoryClause,
    StrategicImplication,
)


class TestRegulatoryClause:
    def test_instantiation_with_required_fields(self):
        rc = RegulatoryClause(
            clauseId="GDPR-C01",
            articleReference="Art. 5(1)(c)",
            description="Data minimisation",
            normativeStrength="MANDATORY_UNCONDITIONAL",
            obligatedParty=["CONTROLLER"],
            obligationType="CONTINUOUS",
            normativeWeight=3,
        )
        assert rc.clause_id == "GDPR-C01"
        assert rc.normative_strength == NormativeStrength.MANDATORY_UNCONDITIONAL
        assert rc.obligated_party == ["CONTROLLER"]
        assert rc.obligation_type == ObligationType.CONTINUOUS
        assert rc.normative_weight == 3
        assert rc.is_atomic is True
        assert rc.parent_clause_id == ""
        assert rc.sibling_clause_ids == []
        assert rc.sanction_reference == ""

    def test_instantiation_with_optional_fields(self):
        rc = RegulatoryClause(
            clauseId="GDPR-C01",
            articleReference="Art. 5",
            description="Test",
            normativeStrength="MANDATORY_CONDITIONAL",
            obligatedParty=["CONTROLLER", "PROCESSOR"],
            obligationType="TRIGGERED",
            normativeWeight=2,
            isAtomic=False,
            parentClauseId="GDPR-C00",
            siblingClauseIds=["GDPR-C02", "GDPR-C03"],
            sanctionReference="Art. 83(5)",
        )
        assert rc.is_atomic is False
        assert rc.parent_clause_id == "GDPR-C00"
        assert rc.sibling_clause_ids == ["GDPR-C02", "GDPR-C03"]
        assert rc.sanction_reference == "Art. 83(5)"


class TestComplementarityAnalysis:
    def test_instantiation(self):
        ca = ComplementarityAnalysis(
            analysisId="CA-01",
            sharedScope=0.65,
            overlapType="Overlap",
            analysisDate="2026-06-03",
            structuralConnectedness=0.5,
        )
        assert ca.analysis_id == "CA-01"
        assert ca.shared_scope == 0.65
        assert ca.overlap_type == "Overlap"
        assert ca.structural_connectedness == 0.5


class TestDomainElaborationEntry:
    def test_instantiation(self):
        de = DomainElaborationEntry(
            entryId="DE-01",
            subDomainId="SD-01",
            elaborationFactor=1.2,
            dominantRegulation="REG-GDPR",
            relationType="Overlap",
            normativeIntensity=2.5,
            weightedScore=0.85,
            notes="Test note",
        )
        assert de.entry_id == "DE-01"
        assert de.sub_domain_id == "SD-01"
        assert de.elaboration_factor == 1.2
        assert de.dominant_regulation == "REG-GDPR"
        assert de.relation_type == "Overlap"
        assert de.normative_intensity == 2.5
        assert de.weighted_score == 0.85
        assert de.notes == "Test note"


class TestRefinements:
    def test_strategic_implication_has_business_impact_and_compliance_risk(self):
        si = StrategicImplication(
            implicationId="SI-01",
            description="Test",
        )
        assert si.business_impact == ""
        assert si.compliance_risk == ""

    def test_complementarity_entry_has_decision_rationale(self):
        ce = ComplementarityEntry(
            subdomainId="SD-01",
            complementarityType="SYNERGISTIC",
            involvedRegulations=["REG-GDPR"],
            implementationApproach="Unified",
        )
        assert ce.decision_rationale == ""
