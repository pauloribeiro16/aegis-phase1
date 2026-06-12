"""models — Pydantic models aligned to class diagram."""

import logging
from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ─── Module logger (MANDATORY) ───────────────────────────────────────
logger = logging.getLogger(__name__)


# ─── Enumerations ────────────────────────────────────────────────────


class NormativeStrength(str, Enum):
    MANDATORY_UNCONDITIONAL = "MANDATORY_UNCONDITIONAL"
    MANDATORY_CONDITIONAL = "MANDATORY_CONDITIONAL"
    GUIDANCE = "GUIDANCE"


class ObligatedPartyType(str, Enum):
    CONTROLLER = "CONTROLLER"
    PROCESSOR = "PROCESSOR"
    MANUFACTURER = "MANUFACTURER"
    IMPORTER = "IMPORTER"
    DISTRIBUTOR = "DISTRIBUTOR"
    ESSENTIAL_OR_IMPORTANT_ENTITY = "ESSENTIAL_OR_IMPORTANT_ENTITY"
    FINANCIAL_ENTITY = "FINANCIAL_ENTITY"
    PROVIDER = "PROVIDER"
    DEPLOYER = "DEPLOYER"


class ObligationType(str, Enum):
    CONTINUOUS = "CONTINUOUS"
    PERIODIC = "PERIODIC"
    TRIGGERED = "TRIGGERED"
    ONE_TIME = "ONE_TIME"


class CoverageLevel(str, Enum):
    SUBSTANTIVE = "SUBSTANTIVE"
    PARTIAL = "PARTIAL"
    NOT_ADDRESSED = "NOT_ADDRESSED"


class GranularityLevel(str, Enum):
    ARTICLE = "ARTICLE"
    PARAGRAPH = "PARAGRAPH"
    SUB_PARAGRAPH = "SUB_PARAGRAPH"
    ATOMIC = "ATOMIC"


class RelationType(str, Enum):
    OVERLAP = "OVERLAP"
    CUMULATIVE_REINFORCEMENT = "CUMULATIVE_REINFORCEMENT"
    CONFLICT = "CONFLICT"
    GAP = "GAP"


class ComplexityTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class InteractionType(str, Enum):
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    REQUIREMENT_CONFLICT = "REQUIREMENT_CONFLICT"
    TRIGGER_MISMATCH = "TRIGGER_MISMATCH"
    NEGATIVE_ANALYSIS = "NEGATIVE_ANALYSIS"


class OverlapType(str, Enum):
    SYNERGISTIC = "SYNERGISTIC"
    STRUCTURAL_TENSION = "STRUCTURAL_TENSION"
    CONTEXTUAL_TENSION = "CONTEXTUAL_TENSION"
    CUMULATIVE_REINFORCEMENT = "CUMULATIVE_REINFORCEMENT"


# ─── Forward-declared models (needed by CompanyContext) ──────────────


class ConditionalExtension(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    block_id: str = Field(alias="blockId")
    block_name: str = Field(alias="blockName")
    trigger_condition: str = Field("", alias="triggerCondition")
    question_ids: list[str] = Field(default_factory=list, alias="questionIds")
    is_active: bool = Field(True, alias="isActive")
    regulation_id: str = Field("", alias="regulationId")

    @model_validator(mode="before")
    @classmethod
    def _coerce_csv_lists(cls, data: dict) -> dict:
        val = data.get("questionIds") or data.get("question_ids")
        if isinstance(val, str):
            data["questionIds"] = [v.strip() for v in val.split(",") if v.strip()] if val else []
        return data


class RegulatoryInteraction(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    interaction_id: str = Field(alias="interactionId")
    interaction_type: str = Field(alias="interactionType")
    involved_regulations: list[str] = Field(default_factory=list, alias="involvedRegulations")
    conflict_description: str = Field("", alias="conflictDescription")
    resolution_principle: str = Field("", alias="resolutionPrinciple")


# ─── Pydantic Models ────────────────────────────────────────────────


class Stakeholder(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    stakeholder_id: str = Field(alias="stakeholderId")
    name: str
    role: str
    stakeholder_type: str = Field("internal", alias="stakeholderType")
    department: str | None = None
    access_level: str | None = Field(None, alias="accessLevel")
    organization: str | None = None
    relationship_type: str | None = Field(None, alias="relationshipType")


class BusinessGoal(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    goal_id: str = Field(alias="goalId")
    description: str
    priority: str
    strategic_alignment: str = Field("", alias="strategicAlignment")


class CompanyContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    sector: str = ""
    size: str = ""
    processes_personal_data: bool = False
    places_digital_products_eu: bool = False
    dora_financial_entity: bool = False
    nis2_sector: str = ""
    aiact_high_risk_system: bool = False
    technological_control_plane: str = Field("", alias="technologicalControlPlane")
    complexity_tier: ComplexityTier = Field(ComplexityTier.MEDIUM, alias="complexityTier")
    active_extensions: list[ConditionalExtension] = Field(
        default_factory=list, alias="activeExtensions"
    )
    regulatory_interactions: list[RegulatoryInteraction] = Field(
        default_factory=list, alias="regulatoryInteractions"
    )


class ComplianceContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    jurisdiction_id: str = Field(alias="jurisdictionId")
    applicable_regulations: list[str] = Field(default_factory=list)
    assessment_date: date | None = Field(None, alias="assessmentDate")


class StructuredComplianceMatrix(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    matrix_id: str = Field(alias="matrixId")
    analysis_date: date | None = Field(None, alias="analysisDate")
    version: str = ""


class Regulation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    regulation_id: str = Field(alias="regulationId")
    name: str
    short_name: str = Field("", alias="shortName")
    jurisdiction: str = "EU"
    effective_date: date | None = Field(None, alias="effectiveDate")


class ResponsibilityEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    entry_id: str = Field(alias="entryId")
    responsibility_type: str = Field(alias="responsibilityType")
    rationale: str = ""
    regulation_id: str = Field("", alias="regulationId")


class NativeCompliance(ResponsibilityEntry):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    implementation_owner: str = Field("", alias="implementationOwner")
    resource_estimate: str = Field("", alias="resourceEstimate")


class InheritedCompliance(ResponsibilityEntry):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    provider_name: str = Field("", alias="providerName")
    inheritance_mechanism: str = Field("", alias="inheritanceMechanism")


class StrategicImplication(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    implication_id: str = Field(alias="implicationId")
    description: str = ""
    business_impact: str = Field("", alias="businessImpact")
    compliance_risk: str = Field("", alias="complianceRisk")


class RegulatoryObligation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    obligation_id: str = Field(alias="obligationId")
    description: str = ""
    category: str = ""
    target_sub_domain: str = Field("", alias="targetSubDomain")
    obligation_type: ObligationType | None = Field(None, alias="obligationType")
    obligated_party: list[ObligatedPartyType] = Field(default_factory=list, alias="obligatedParty")
    normative_intensity: float = Field(0.0, alias="normativeIntensity")


class SecurityControlDomain(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    domain_id: str = Field(alias="domainId")
    sub_domain_id: str = Field("", alias="subDomainId")
    name: str = ""
    description: str = ""
    reference_source: str = Field("", alias="referenceSource")


class RegulatoryClause(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    clause_id: str = Field(alias="clauseId")
    article_reference: str = Field("", alias="articleReference")
    description: str = ""
    normative_strength: NormativeStrength | None = Field(None, alias="normativeStrength")
    obligated_party: list[str] = Field(default_factory=list, alias="obligatedParty")
    obligation_type: ObligationType | None = Field(None, alias="obligationType")
    normative_weight: float = Field(0.0, alias="normativeWeight")
    is_atomic: bool = Field(True, alias="isAtomic")
    parent_clause_id: str = Field("", alias="parentClauseId")
    sibling_clause_ids: list[str] = Field(default_factory=list, alias="siblingClauseIds")
    sanction_reference: str = Field("", alias="sanctionReference")

    @model_validator(mode="before")
    @classmethod
    def _coerce_csv_lists(cls, data: dict) -> dict:
        for key in ("obligatedParty", "obligated_party", "siblingClauseIds", "sibling_clause_ids"):
            val = data.get(key)
            if isinstance(val, str):
                data[key] = [v.strip() for v in val.split(",") if v.strip()] if val else []
        return data


class DomainCoverageEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    entry_id: str = Field(alias="entryId")
    regulation_id: str = Field("", alias="regulationId")
    sub_domain_id: str = Field("", alias="subDomainId")
    coverage_level: str = Field(alias="coverageLevel")
    clause_count: int = Field(0, alias="clauseCount")
    granularity_level: str = Field(alias="granularityLevel")
    obligated_party_dist: dict = Field(default_factory=dict, alias="obligatedPartyDist")
    obligation_type_dist: dict = Field(default_factory=dict, alias="obligationTypeDist")

    @model_validator(mode="before")
    @classmethod
    def _coerce_csv_fields(cls, data: dict) -> dict:
        for key in (
            "obligatedPartyDist",
            "obligated_party_dist",
            "obligationTypeDist",
            "obligation_type_dist",
        ):
            val = data.get(key)
            if isinstance(val, str) and ":" in val:
                data[key] = dict(item.split(":") for item in val.split(",") if ":" in item)
        return data


class ComplementarityAnalysis(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    analysis_id: str = Field(alias="analysisId")
    shared_scope: float = Field(0.0, alias="sharedScope")
    complementarity_index: float = Field(0.0, alias="jaccardIndex")
    overlap_type: str = Field(alias="overlapType")
    analysis_date: str = Field("", alias="analysisDate")
    structural_connectedness: float = Field(0.0, alias="structuralConnectedness")
    regulation_1_id: str = Field("", alias="regulation1Id")
    regulation_2_id: str = Field("", alias="regulation2Id")
    description: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_csv_floats(cls, data: dict) -> dict:
        ni_map = {"HIGH": 0.9, "MEDIUM": 0.5, "LOW": 0.2}
        for key in (
            "sharedScope",
            "shared_scope",
            "structuralConnectedness",
            "structural_connectedness",
            "jaccardIndex",
            "complementarity_index",
        ):
            val = data.get(key)
            if isinstance(val, str):
                if val.upper() in ni_map:
                    data[key] = ni_map[val.upper()]
                else:
                    try:
                        data[key] = float(val)
                    except (ValueError, TypeError):
                        data[key] = 0.0
        return data


class DomainElaborationEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    entry_id: str = Field(alias="entryId")
    analysis_id: str = Field("", alias="analysisId")
    sub_domain_id: str = Field("", alias="subDomainId")
    elaboration_factor: float = Field(0.0, alias="elaborationFactor")
    dominant_regulation: str = Field("", alias="dominantRegulation")
    relation_type: str = Field(alias="relationType")
    normative_intensity: float = Field(0.0, alias="normativeIntensity")
    weighted_score: float = Field(0.0, alias="weightedScore")
    notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_csv_floats(cls, data: dict) -> dict:
        ni = data.get("normativeIntensity") or data.get("normative_intensity")
        if isinstance(ni, str):
            mapping = {"HIGH": 0.9, "MEDIUM": 0.5, "LOW": 0.2}
            data["normativeIntensity"] = mapping.get(ni.upper(), 0.0)
        return data


class ImplementationMapping(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    implementation_id: str = Field(alias="mappingId")
    sub_domain_id: str = Field("", alias="subDomainId")
    primary_framework: str = Field("", alias="primaryFramework")
    framework_reference: str = Field("", alias="frameworkReference")
    rationale: str = ""
    confidence_level: str = Field("MEDIUM", alias="confidenceLevel")


# ─── Legacy models (backward compat — used by existing nodes) ─────────


class StakeholderAnalysis(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    stakeholders: list[Stakeholder] = Field(default_factory=list)
    influence_matrix: dict[str, str] = Field(default_factory=dict)
    summary: str = ""


class BusinessGoalsCatalog(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    goals: list[BusinessGoal] = Field(default_factory=list)
    summary: str = ""


class RegulationAssessment(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    regulation_id: str = Field(alias="regulationId")
    applicable: bool = False
    confidence: str = ""
    obligated_party: str = Field("", alias="obligatedParty")
    rationale: str = ""
    nuances: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class ApplicabilityMatrix(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    assessments: list[RegulationAssessment] = Field(default_factory=list)
    native_compliance: list[dict] = Field(default_factory=list)
    inherited_compliance: list[dict] = Field(default_factory=list)


class ComplianceBoundary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    native_domains: list[str] = Field(default_factory=list, alias="nativeDomains")
    inherited_domains: list[str] = Field(default_factory=list, alias="inheritedDomains")


class ClauseMapping(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    clause_id: str = Field(alias="clauseId")
    regulation_id: str = Field(alias="regulationId")
    article: str = ""
    description: str = ""
    maps_to_subdomain: str = Field("", alias="mapsToSubdomain")
    normative_weight: int = Field(0, alias="normativeWeight")
    obligated_party: str = Field("", alias="obligatedParty")
    obligation_type: str = Field("", alias="obligationType")
    company_relevance: str = Field("", alias="companyRelevance")
    justification: str = ""


class SubDomainCoverage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    subdomain_id: str = Field(alias="subdomainId")
    subdomain_name: str = Field("", alias="subdomainName")
    regulation_coverages: dict[str, bool] = Field(default_factory=dict, alias="regulationCoverages")
    clause_count: int = Field(0, alias="clauseCount")
    coverage_level: CoverageLevel = Field(alias="coverageLevel")
    ni_avg: float = Field(0.0, alias="niAvg")


class CoverageSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    total_subdomains: int = Field(0, alias="totalSubdomains")
    covered: int = 0
    not_addressed: int = Field(0, alias="notAddressed")
    coverage_pct: float = Field(0.0, alias="coveragePct")
    mean_ni: float = Field(0.0, alias="meanNi")
    sole_authority_gaps: list[str] = Field(default_factory=list, alias="soleAuthorityGaps")


class ComplementarityEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    subdomain_id: str = Field(alias="subdomainId")
    complementarity_type: str = Field("", alias="complementarityType")
    involved_regulations: list[str] = Field(default_factory=list, alias="involvedRegulations")
    implementation_approach: str = Field("", alias="implementationApproach")
    decision_rationale: str = Field("", alias="decisionRationale")


class CompoundEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    event_id: str = Field(alias="eventId")
    description: str = ""
    involved_regulations: list[str] = Field(default_factory=list, alias="involvedRegulations")
    subdomain_id: str = Field("", alias="subdomainId")
    tension_type: str = Field("", alias="tensionType")
    resolution: str = ""


class RegulatoryGap(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    gap_id: str = Field(alias="gapId")
    regulation: str = ""
    clause: str = ""
    subdomain: str = ""
    description: str = ""
    risk_level: str = Field("", alias="riskLevel")


class ContextAssessment(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    stakeholders: list[Stakeholder] = Field(default_factory=list)
    business_goals: list[BusinessGoal] = Field(default_factory=list)
    company_context: CompanyContext = Field(default_factory=CompanyContext)
    regulatory_flags: dict[str, bool] = Field(default_factory=dict)
    architectural_implications: list[dict] = Field(default_factory=list)
    compliance_capability: list[dict] = Field(default_factory=list)
    assessment_markdown: str = ""


class Phase1OutputModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    subphase_a_output: dict = Field(default_factory=dict, alias="subphaseAOutput")
    subphase_b_output: dict = Field(default_factory=dict, alias="subphaseBOutput")
    subphase_c_output: dict = Field(default_factory=dict, alias="subphaseCOutput")


# ─── __all__ (alphabetical) ──────────────────────────────────────────

__all__ = [
    "ApplicabilityMatrix",
    "BusinessGoal",
    "BusinessGoalsCatalog",
    "ClauseMapping",
    "CompanyContext",
    "ComplementarityAnalysis",
    "ComplementarityEntry",
    "ComplexityTier",
    "ComplianceBoundary",
    "ComplianceContext",
    "CompoundEvent",
    "ConditionalExtension",
    "ContextAssessment",
    "CoverageLevel",
    "CoverageSummary",
    "DomainCoverageEntry",
    "DomainElaborationEntry",
    "GranularityLevel",
    "ImplementationMapping",
    "InheritedCompliance",
    "InteractionType",
    "NativeCompliance",
    "NormativeStrength",
    "ObligatedPartyType",
    "ObligationType",
    "OverlapType",
    "Phase1OutputModel",
    "Regulation",
    "RegulationAssessment",
    "RegulatoryClause",
    "RegulatoryGap",
    "RegulatoryInteraction",
    "RegulatoryObligation",
    "RelationType",
    "ResponsibilityEntry",
    "SecurityControlDomain",
    "Stakeholder",
    "StakeholderAnalysis",
    "StrategicImplication",
    "StructuredComplianceMatrix",
    "SubDomainCoverage",
]
