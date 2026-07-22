"""state — Pydantic models and TypedDicts for the v2 map-reduce pipeline.

Defines the data models used throughout the v2 pipeline: CompanyContext,
SubDomainDef, DomainResult, and V2State.

References:
    - contracts/SPRINT001_v2-core.md (C-001)
    - src/aegis_phase1/models.py (existing enums)
"""

import logging
from enum import Enum
from typing import NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from aegis_phase1.models import ComplexityTier

logger = logging.getLogger(__name__)


class CompanyContext(BaseModel):
    """Pipeline context describing the company under assessment.

    Attributes:
        company_name: Name of the company.
        sector: Industry sector (e.g. "tech", "finance").
        jurisdiction: Regulatory jurisdiction. Defaults to "EU".
        employees: Number of employees.
        revenue: Annual revenue in EUR.
        scale: Company size tier — MICRO/SMALL/MEDIUM/LARGE/MAX.
        applicable_regs: List of applicable regulation short names.
        complexity_tier: Assessment complexity — LOW/MEDIUM/HIGH.
        security_fte: Security-dedicated full-time equivalent.
        tech_stack: Key technologies used (e.g. ["AWS", "Kubernetes"]).
    """

    company_name: str
    sector: str
    jurisdiction: str = "EU"
    employees: int
    revenue: float
    scale: str
    applicable_regs: list[str]
    complexity_tier: ComplexityTier
    security_fte: float
    tech_stack: list[str]


class SubDomainDef(BaseModel):
    """Full parsed content of a single sub-domain preprocessing file (D-XX.Y).

    Attributes:
        document_id: Full AEGIS document identifier.
        title: Human-readable sub-domain title.
        status: Document status (DRAFT, REVIEW, FINAL). Defaults to "DRAFT".
        section1_crda: Cross-regulation dual analyses list.
        section2_hso: Hierarchical security objectives (hl_objective + per_reg_sos).
        section3_requirements: Volere-format requirements list.
        frontmatter: Raw YAML frontmatter as a dict.
    """

    document_id: str
    title: str
    status: str = Field(default="DRAFT")
    section1_crda: list[dict] = Field(default_factory=list)
    section2_hso: dict = Field(default_factory=dict)
    section3_requirements: list[dict] = Field(default_factory=list)
    frontmatter: dict = Field(default_factory=dict)


class DomainResult(TypedDict, total=False):
    """Result of the MAP stage for a single domain (D-XX).

    Attributes:
        domain_id: Domain identifier (e.g. "D-01").
        domain_name: Human-readable domain name.
        subdomains: List of processed sub-domain dicts.
        coverage: Coverage level from CoverageLevel enum.
        cross_regulation: List of cross-regulation overlap analyses.
        llm_status: LLM processing status — OK/FAILED/SKIPPED.
        adapted_objective: Concat of HLs (verbatim) for downstream rendering.
        adapted_subdomains: Per-sub-domain adaptation (v1.2 spec).
        key_changes: Bullet list of concrete deltas vs. raw HSOs (may be
            empty when no changes were needed or on parse failure).
        confidence: LLM self-rated confidence — HIGH / MEDIUM / LOW.
            ``LOW`` on parse failure.
    """

    domain_id: str
    domain_name: str
    subdomains: list[dict]
    coverage: str
    cross_regulation: list[dict]
    applicable_regs: list[str]
    llm_status: str
    adapted_objective: str  # concat of HLs (for downstream verbatim rendering)
    adapted_subdomains: list[dict]  # NEW: per-sub-domain adaptation (v1.2)
    adapted_subdomains_v3: list[dict]  # NEW: per-sub-domain 3-blocks x 5-fields (v1.3)
    key_changes: list[str]
    confidence: str
    error_reason: NotRequired[str]  # populated only when llm_status == "FAILED"


class V2State(TypedDict):
    """Complete pipeline state for the v2 map-reduce workflow.

    Attributes:
        current_stage: Pipeline stage — INIT/LOADED/MAPPED/REDUCED/OUTPUT_DONE.
        case_path: Absolute path to the case directory.
        preprocessing_path: Absolute path to the PREPROCESSING directory.
        company_context: Parsed CompanyContext, or None before loading.
        architecture_inventory: Structured systems, stores, flows, and related inventory.
        stakeholders: Stakeholder register parsed from 01_Company_Context.md
            (§10) as a list of dicts with id/name/role/organisation/contact/
            responsibilities keys.
        business_goals: Business goals catalog parsed from
            01_Company_Context.md (§11) as a list of dicts with id/description/
            priority/related_regs/success_metric keys.
        taxonomy_entries: List of taxonomy reference entries.
        ontology: Loaded phase1 ontology dict.
        regulations: List of regulation descriptors.
        subdomains: Dict of SubDomainDef keyed by sub-domain ID (D-XX.Y).
        preprocessing: Cross-regulation and ambiguity analysis data.
        domain_results: Dict of DomainResult keyed by domain ID (D-XX).
        aggregated_data: Cross-domain aggregated analysis data.
        output_paths: Dict of output file paths by type.
        errors: Accumulated error messages.
    """

    current_stage: str
    case_path: str
    preprocessing_path: str
    company_context: CompanyContext | None
    architecture_inventory: dict
    stakeholders: list[dict]
    business_goals: list[dict]
    taxonomy_entries: list[dict]
    ontology: dict
    regulations: list[dict]
    subdomains: dict[str, SubDomainDef]
    preprocessing: dict
    domain_results: dict[str, DomainResult]
    aggregated_data: dict
    output_paths: dict[str, str]
    errors: list[str]


# =============================================================================
# CORR-047: 4 new categories of company context data
#
# 1. ImplementationReadiness (12 IR areas — feeds Doc 04b capability matrix)
# 2. RegulatoryClassification (5 enums — feeds Doc 05/07 per-regulation state)
# 3. RoleMatrix (5 regs × role — feeds Doc 05 + Layer 3 analyses)
# 4. RegulatoryInteractions (Layer 3 scans — temporal/requirement conflicts +
#    negative analyses)
#
# Local _TolerantModel mirrors case_profile._TolerantModel to avoid a cycle
# (state.py ↔ case_profile.py). Keep both in sync if the contract changes.
# =============================================================================


class _TolerantModel(BaseModel):
    """Local mirror of case_profile._TolerantModel. Tolerates extra fields."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


# ── 1. Implementation Readiness (Doc 04b) ──────────────────────────────────


class ReadinessState(str, Enum):
    """YES / NO / PARTIAL — the 3 states for an IR area."""

    YES = "YES"
    NO = "NO"
    PARTIAL = "PARTIAL"


class ImplementationReadiness(_TolerantModel):
    """12 readiness areas (IR-01..IR-12), per methodology §6.

    Areas (post-CORR-036 TinyTask baseline):
      IR-01: CISO appointed
      IR-02: DPO appointed
      IR-03: Information security policy (ISP) defined
      IR-04: Risk assessment methodology
      IR-05: Incident response plan
      IR-06: Business continuity / DR
      IR-07: Backup policy
      IR-08: Access control / RBAC
      IR-09: Vulnerability management
      IR-10: Third-party risk management
      IR-11: Security awareness training
      IR-12: Audit logging / SIEM
    """

    ciso: ReadinessState = ReadinessState.NO
    dpo: ReadinessState = ReadinessState.NO
    information_security_policy: ReadinessState = ReadinessState.NO
    risk_assessment: ReadinessState = ReadinessState.NO
    incident_response: ReadinessState = ReadinessState.NO
    business_continuity: ReadinessState = ReadinessState.NO
    backup: ReadinessState = ReadinessState.NO
    access_control: ReadinessState = ReadinessState.NO
    vulnerability_management: ReadinessState = ReadinessState.NO
    third_party_risk: ReadinessState = ReadinessState.NO
    security_awareness: ReadinessState = ReadinessState.NO
    audit_logging: ReadinessState = ReadinessState.NO


# ── 2. Regulatory Classification (5 enums) ─────────────────────────────────


class NIS2EntityClass(str, Enum):
    """NIS2 Art. 5 — entity classification."""

    ESSENTIAL = "ESSENTIAL"
    IMPORTANT = "IMPORTANT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DORAClassification(str, Enum):
    """DORA Art. 2 — entity classification."""

    FINANCIAL_ENTITY = "FINANCIAL_ENTITY"
    ICT_THIRD_PARTY = "ICT_THIRD_PARTY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CRAProductClass(str, Enum):
    """CRA Annex III — product criticality class."""

    CLASS_I = "CLASS_I"
    CLASS_II = "CLASS_II"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AISystemClass(str, Enum):
    """AI Act Art. 6 + Annex III — risk classification."""

    PROHIBITED = "PROHIBITED"
    HIGH_RISK = "HIGH_RISK"
    LIMITED_RISK = "LIMITED_RISK"
    MINIMAL_RISK = "MINIMAL_RISK"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CriticalOrImportantICT(str, Enum):
    """DORA Art. 6 — whether ICT supports critical/important functions."""

    YES = "YES"
    NO = "NO"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RegulatoryClassification(_TolerantModel):
    """Per-regulation classification (5 enums)."""

    nis2_entity_class: NIS2EntityClass = NIS2EntityClass.NOT_APPLICABLE
    dora_article_2_entity: DORAClassification = DORAClassification.NOT_APPLICABLE
    cra_product_class: CRAProductClass = CRAProductClass.NOT_APPLICABLE
    ai_system_classification: AISystemClass = AISystemClass.NOT_APPLICABLE
    critical_or_important_ict: CriticalOrImportantICT = (
        CriticalOrImportantICT.NOT_APPLICABLE
    )


# ── 3. Role Matrix (5 regs × role) ─────────────────────────────────────────


class RoleMatrixEntry(_TolerantModel):
    """One regulation's role in the case."""

    role: str = ""
    native_compliance: bool = False
    inherited_obligations: list[str] = Field(default_factory=list)
    notes: str = ""


class RoleMatrix(_TolerantModel):
    """5 regulations × role entries (one per applicable regulation)."""

    gdpr: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)
    cra: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)
    nis2: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)
    dora: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)
    ai_act: RoleMatrixEntry = Field(default_factory=RoleMatrixEntry)


# ── 4. Regulatory Interactions (Layer 3 scans) ─────────────────────────────


class RegulatoryConflictType(str, Enum):
    """Type of cross-regulation interaction."""

    TEMPORAL = "TEMPORAL"           # breach notification timeline differs
    REQUIREMENT = "REQUIREMENT"     # obligation conflicts across regs
    TRIGGER = "TRIGGER"             # trigger event definitions differ
    NEGATIVE = "NEGATIVE"           # absent obligation that should be present


class RegulatoryInteraction(_TolerantModel):
    """One cross-regulation interaction (e.g. GDPR-CRA temporal conflict)."""

    id: str
    type: RegulatoryConflictType
    regulations: list[str] = Field(default_factory=list)
    sub_domains: list[str] = Field(default_factory=list)
    description: str = ""
    resolution: str = ""


class NegativeAnalysisItem(_TolerantModel):
    """One negative-analysis finding (what SHOULD apply but DOESN'T)."""

    id: str
    description: str
    expected_regulations: list[str] = Field(default_factory=list)
    severity: str = "LOW"  # LOW / MEDIUM / HIGH


class RegulatoryInteractions(_TolerantModel):
    """Container for Layer 3 scans (4 categories)."""

    temporal_conflicts: list[RegulatoryInteraction] = Field(default_factory=list)
    requirement_conflicts: list[RegulatoryInteraction] = Field(default_factory=list)
    trigger_mismatches: list[RegulatoryInteraction] = Field(default_factory=list)
    negative_analyses: list[NegativeAnalysisItem] = Field(default_factory=list)


# =============================================================================
# CORR-050: P1B-LLM-01-INTERPRETATION output models (markdown+regex parsing)
#
# Replaces the JSON Schema in output_schemas.yaml as the source of truth
# for this spec. Envelope fields (prompt_spec_id, schema_version, case_id,
# invocation_pattern) are injected by the invoker post-parse — the LLM
# never emits them. Pydantic replaces JSON Schema as the only validator.
# =============================================================================


class P1BLLM01Status(str, Enum):
    """CORR-050: status values for P1B-LLM-01-INTERPRETATION output."""

    OK = "OK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INDETERMINATE = "INDETERMINATE"


class P1BLLM01Confidence(str, Enum):
    """CORR-050: confidence values for P1B-LLM-01-INTERPRETATION output."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class P1BLLM01Applicable(str, Enum):
    """CORR-050: applicable values for P1BLLM01Interpretation."""

    YES = "YES"
    NO = "NO"


class P1BLLM01DerogationVerdict(str, Enum):
    """CORR-050: activation_verdict values for P1BLLM01Derogation."""

    ACTIVATED = "ACTIVATED"
    NOT_ACTIVATED = "NOT_ACTIVATED"
    INDETERMINATE = "INDETERMINATE"


class P1BLLM01Interpretation(BaseModel):
    """One Tipo 2 interpretation entry (parsed from ### INT-NN block)."""

    entry_id: str
    applicable: P1BLLM01Applicable
    activation_rationale: str
    layer0_refs: list[str] = Field(default_factory=list)
    legal_refs: list[str] = Field(default_factory=list)
    company_fact_refs: list[str] = Field(default_factory=list)


class P1BLLM01Derogation(BaseModel):
    """One Tipo 3 derogation entry (parsed from ### DER-NN block)."""

    entry_id: str
    activation_verdict: P1BLLM01DerogationVerdict
    activation_rationale: str
    layer0_refs: list[str] = Field(default_factory=list)
    legal_refs: list[str] = Field(default_factory=list)
    company_fact_refs: list[str] = Field(default_factory=list)


class P1BLLM01Output(BaseModel):
    """Parsed + validated output of P1B-LLM-01-INTERPRETATION.

    CORR-050: envelope fields (prompt_spec_id, schema_version, case_id,
    invocation_pattern) are injected by the invoker post-parse — the
    LLM never emits them. Pydantic replaces JSON Schema as the
    single source of truth for validation.
    """

    # Envelope (invoker-injected; LLM never emits)
    prompt_spec_id: str = "P1B-LLM-01-INTERPRETATION"
    schema_version: str = "1.0.0"
    case_id: str = ""
    invocation_pattern: str = "per_regulation"

    # Content (LLM-emitted, parser-extracted from markdown)
    status: P1BLLM01Status
    confidence: P1BLLM01Confidence
    interpretations: list[P1BLLM01Interpretation] = Field(default_factory=list)
    derogations: list[P1BLLM01Derogation] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


__all__ = [
    "AISystemClass",
    "CRAProductClass",
    "CompanyContext",
    "CriticalOrImportantICT",
    "DORAClassification",
    "DomainResult",
    "ImplementationReadiness",
    "NIS2EntityClass",
    "NegativeAnalysisItem",
    "P1BLLM01Applicable",
    "P1BLLM01Confidence",
    "P1BLLM01Derogation",
    "P1BLLM01DerogationVerdict",
    "P1BLLM01Interpretation",
    "P1BLLM01Output",
    "P1BLLM01Status",
    "ReadinessState",
    "RegulatoryClassification",
    "RegulatoryConflictType",
    "RegulatoryInteraction",
    "RegulatoryInteractions",
    "RoleMatrix",
    "RoleMatrixEntry",
    "SubDomainDef",
    "V2State",
]
