"""state — Pydantic models and TypedDicts for the v2 map-reduce pipeline.

Defines the data models used throughout the v2 pipeline: CompanyContext,
SubDomainDef, DomainResult, and V2State.

References:
    - contracts/SPRINT001_v2-core.md (C-001)
    - src/aegis_phase1/models.py (existing enums)
"""

from __future__ import annotations

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
# CORR-074: P1B-LLM-02-RATIONALE output models (markdown+regex parsing)
#
# Mirrors the P1B-LLM-01 contract — the spec is a 5-section markdown
# document (Status / Rationale / Implications / Gaps / Notes). The
# parser at src/aegis_phase1/prompts_v2/markdown_parser.py
# (re-exports the implementation archived at
#  src/aegis_phase1/_archive/corr061/markdown_parser.py)
# extracts the structured fields via regex + Pydantic.
#
# Envelope fields (prompt_spec_id, schema_version, case_id,
# invocation_pattern) are injected by the invoker post-parse — the
# LLM never emits them.
# =============================================================================


class P1BLLM02EffortEstimate(str, Enum):
    """CORR-074: canonical effort estimate enum (8 values, tier-aware)."""

    HOURS = "hours"
    DAYS = "days"
    WEEKS_1 = "weeks_1"
    WEEKS_2_4 = "weeks_2_4"
    MONTHS_1_3 = "months_1_3"
    MONTHS_3_6 = "months_3_6"
    FTE_QUARTER = "fte_quarter"
    FTE_PERMANENT = "fte_permanent"


class P1BLLM02CoverageLevel(str, Enum):
    """CORR-074: gap coverage_level enum (canonical tokens)."""

    NOT_ADDRESSED = "NOT_ADDRESSED"
    PARTIAL = "PARTIAL"


class P1BLLM02Priority(str, Enum):
    """CORR-074: gap priority enum (canonical tokens)."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class P1BLLM02Implication(BaseModel):
    """One activated sub-domain's implication (parsed from `### IMP-D-XX.Y-N` block)."""

    id: str
    description: str
    effort_estimate: P1BLLM02EffortEstimate
    dependencies: list[str] = Field(default_factory=list)
    layer0_refs: list[str] = Field(default_factory=list)
    company_fact_refs: list[str] = Field(default_factory=list)


class P1BLLM02Gap(BaseModel):
    """One gap entry (parsed from `### GAP-D-XX.Y` block)."""

    gap_id: str
    sub_domain_id: str
    coverage_level: P1BLLM02CoverageLevel
    risk_description: str
    covered_by_other_reg: list[str] = Field(default_factory=list)
    recommendation: str = ""
    priority: P1BLLM02Priority
    layer0_refs: list[str] = Field(default_factory=list)


class P1BLLM02Output(BaseModel):
    """Parsed + validated output of P1B-LLM-02-RATIONALE.

    Envelope fields (prompt_spec_id, schema_version, case_id,
    invocation_pattern) are injected by the invoker post-parse.
    """

    # Envelope (invoker-injected; LLM never emits)
    prompt_spec_id: str = "P1B-LLM-02-RATIONALE"
    schema_version: str = "1.0.0"
    case_id: str = ""
    invocation_pattern: str = "per_regulation"

    # Content (LLM-emitted, parser-extracted from markdown)
    status: P1BLLM01Status
    confidence: P1BLLM01Confidence
    rationale: str = ""
    implications: list[P1BLLM02Implication] = Field(default_factory=list)
    gaps: list[P1BLLM02Gap] = Field(default_factory=list)
    notes: str = ""

    model_config = {"extra": "ignore"}


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
    # CORR-065: also accept the legacy/templated values emitted by
    # the example block in the prompt file (`- applicable: YES/NO`).
    # The JSON Schema in output_schemas.yaml says OK/INSUFFICIENT_EVIDENCE/
    # INDETERMINATE, but the example output uses YES/NO/INDETERMINATE —
    # real models (gemma4:e4b, MiniMax-M3) follow the example.
    YES = "YES"
    NO = "NO"


class P1BLLM01Confidence(str, Enum):
    """CORR-050: confidence values for P1B-LLM-01-INTERPRETATION output."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class P1BLLM01Applicable(str, Enum):
    """CORR-050: applicable values for P1BLLM01Interpretation.

    Canonical taxonomy (CORR-074 user decision 2026-08-05):
    ``YES / NO / INDETERMINATE``. The LLM may emit legacy tokens
    ``APPLIES`` or ``DOES_NOT_APPLY`` — the parser's
    ``_normalise_verdict`` maps those to ``YES`` / ``NO``. This keeps
    the enum minimal (no synonym members) and the canonical value
    stable for downstream renderers and tests.
    """

    YES = "YES"
    NO = "NO"
    INDETERMINATE = "INDETERMINATE"


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
    notes: str = ""

    model_config = {"extra": "ignore"}


class GenericMarkdownOutput(BaseModel):
    """CORR-066: parser-agnostic markdown container for the 4 LLMs
    that don't yet have a spec-specific parser
    (P1B-LLM-02-RATIONALE, P1C-LLM-01-OVERLAP-CLASSIFICATION,
    P1C-LLM-02-COMPOUND-EVENT, P1C-LLM-03-STRATEGIC-SYNTHESIS).

    These LLMs emit markdown with a `## Status` block (containing
    `applicable` and `confidence`) plus 1-3 spec-specific body
    sections (Findings / Rationale / Synthesis / Events / etc).
    Rather than write a hand-rolled parser per spec, we capture the
    `## Status` fields structurally and store every other
    `## Section` body verbatim in ``sections[section_name]``.

    Downstream doc renderers and the v2 orchestrator can use either
    the structured fields or the raw ``sections`` blob. The
    raw markdown is also captured separately in
    ``state['per_spec_markdown'][spec_id]`` (CORR-061 S3b) for
    renderers that prefer to consume the original text.
    """

    # Envelope (invoker-injected; LLM never emits)
    prompt_spec_id: str = ""
    schema_version: str = "1.0.0"
    case_id: str = ""
    invocation_pattern: str = "per_regulation"

    # Content (LLM-emitted, parser-extracted from `## Status`)
    status: P1BLLM01Status = P1BLLM01Status.OK
    confidence: P1BLLM01Confidence = P1BLLM01Confidence.MEDIUM

    # Raw sections from the LLM markdown (key = section name, value = body)
    sections: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


# =============================================================================
# CORR-074 propagation: P1C-LLM-02-COMPOUND-EVENT output models
# (markdown+regex parsing — mirrors the CORR-050 / CORR-074 P1B-LLM-01 pattern).
#
# Replaces the JSON Schema in output_schemas.yaml as the source of truth
# for this spec. Envelope fields (prompt_spec_id, schema_version, case_id,
# invocation_pattern) are injected by the invoker post-parse — the LLM
# never emits them. Pydantic replaces JSON Schema as the only validator.
# =============================================================================


class P1CLLM02TensionType(str, Enum):
    """CORR-074 propagation: tension_type values for P1CLLM02PositiveEvent.

    Canonical taxonomy (mirrors Regulatory Baseline event_templates.yaml):
      - TEMPORAL_CONFLICT: notification timelines differ across regs
      - REQUIREMENT_CONFLICT: obligation content conflicts across regs
      - FREQUENCY_MISMATCH: periodic-vs-event-driven reporting mismatch
      - TRIGGER_MISMATCH: trigger event definitions differ across regs
      - INTENSITY_GAP: rigour level of obligations differs across regs
    """

    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    REQUIREMENT_CONFLICT = "REQUIREMENT_CONFLICT"
    FREQUENCY_MISMATCH = "FREQUENCY_MISMATCH"
    TRIGGER_MISMATCH = "TRIGGER_MISMATCH"
    INTENSITY_GAP = "INTENSITY_GAP"


class P1CLLM02Severity(str, Enum):
    """CORR-074 propagation: severity values for P1CLLM02PositiveEvent."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class P1CLLM02PositiveEvent(BaseModel):
    """One confirmed compound event (parsed from `### EVT-NN` block).

    CORR-074 propagation: cross-domain compound event (≥2 sub_domains from
    ≥2 different domains; ≥2 regulations_triggered). Resolution design
    deliberately excluded — Phase 2B territory.
    """

    event_id: str
    description: str
    sub_domains: list[str] = Field(default_factory=list, min_length=2)
    regulations_triggered: list[str] = Field(default_factory=list, min_length=2)
    tension_type: P1CLLM02TensionType
    severity: P1CLLM02Severity
    layer0_refs: list[str] = Field(default_factory=list)


class P1CLLM02NegativeEvent(BaseModel):
    """One apparent-but-not-actually-compound event (parsed from `### NEG-NN`).

    CORR-074 propagation: calibration entry. The LLM surfaced something
    that looked like a compound event but failed one of the 3 criteria
    (single factual event / 2+ reg triggers / incompatible obligations).
    """

    scenario: str
    regulations_checked: list[str] = Field(default_factory=list)
    why_not_compound: str


class P1CLLM02Output(BaseModel):
    """Parsed + validated output of P1C-LLM-02-COMPOUND-EVENT.

    CORR-074 propagation: envelope fields (prompt_spec_id, schema_version,
    case_id, invocation_pattern) are injected by the invoker post-parse —
    the LLM never emits them. Pydantic replaces JSON Schema as the
    single source of truth for validation (mirrors CORR-050 P1B-LLM-01
    pattern).

    `status` / `confidence` are reused from P1BLLM01Status / P1BLLM01Confidence
    (canonical top-level enum: OK / INSUFFICIENT_EVIDENCE / INDETERMINATE,
    HIGH / MEDIUM / LOW) — no new enums needed.
    """

    # Envelope (invoker-injected; LLM never emits)
    prompt_spec_id: str = "P1C-LLM-02-COMPOUND-EVENT"
    schema_version: str = "1.0.0"
    case_id: str = ""
    invocation_pattern: str = "global_reduce"

    # Content (LLM-emitted, parser-extracted from markdown)
    status: P1BLLM01Status
    confidence: P1BLLM01Confidence
    positive_events: list[P1CLLM02PositiveEvent] = Field(default_factory=list)
    negative_events: list[P1CLLM02NegativeEvent] = Field(default_factory=list)
    notes: str = ""

    model_config = {"extra": "ignore"}


# =============================================================================
# CORR-074 propagation: P1C-LLM-01-OVERLAP-CLASSIFICATION output models
# (markdown+regex parsing — mirrors the CORR-050 / CORR-074 P1B-LLM-01 pattern).
#
# Replaces the JSON Schema in output_schemas.yaml as the source of truth
# for this spec. Envelope fields (prompt_spec_id, schema_version, case_id,
# invocation_pattern) are injected by the invoker post-parse — the LLM
# never emits them. Pydantic replaces JSON Schema as the only validator.
# =============================================================================


class P1CLLM01CompanyScopeVerdict(str, Enum):
    """CORR-074 propagation: company_scope_verdict values for P1CLLM01Pair.

    Canonical taxonomy for the company-side overlap verdict
    (derived from the activation predicate evaluation):
      - OVERLAP_CONFIRMED: predicate is met against company facts
      - OVERLAP_NOT_TRIGGERED: predicate is not met
      - SCOPE_DISJOINT: parties fall outside the predicate scope
      - INDETERMINATE: predicate requires missing facts
    """

    OVERLAP_CONFIRMED = "OVERLAP_CONFIRMED"
    OVERLAP_NOT_TRIGGERED = "OVERLAP_NOT_TRIGGERED"
    SCOPE_DISJOINT = "SCOPE_DISJOINT"
    INDETERMINATE = "INDETERMINATE"


class P1CLLM01ScopeOverlap(str, Enum):
    """CORR-074 propagation: scope_overlap values for P1CLLM01SubDomainActivation.

    Canonical taxonomy for the sub-domain-level scope overlap summary:
      - Y: at least one reg pair is OVERLAP_CONFIRMED
      - CONDITIONAL: only CONDITIONAL pairs with INDETERMINATE verdicts
      - N: no reg pair overlaps the company's scope
    """

    Y = "Y"
    CONDITIONAL = "CONDITIONAL"
    N = "N"


class P1CLLM01Layer0Relationship(str, Enum):
    """CORR-074 propagation: layer0_relationship values for P1CLLM01Pair.

    FROZEN taxonomy propagated verbatim from the Regulatory Baseline
    (the LLM must NOT re-classify these):
      - SAME: pairwise relationship is identity-equivalent
      - COMPLEMENTARY: pairwise relationship is additive
      - CONTRADICTORY: pairwise relationship conflicts
      - SCOPE_DISJOINT: pairwise relationship operates on different scopes
      - CONDITIONAL: pairwise relationship requires predicate evaluation
    """

    SAME = "SAME"
    COMPLEMENTARY = "COMPLEMENTARY"
    CONTRADICTORY = "CONTRADICTORY"
    SCOPE_DISJOINT = "SCOPE_DISJOINT"
    CONDITIONAL = "CONDITIONAL"


class P1CLLM01Pair(BaseModel):
    """One verified pair within a sub-domain activation.

    CORR-074 propagation: parsed from a `#### REG-A ↔ REG-B` nested
    block under `### D-XX.Y`. The `layer0_relationship` is READ-ONLY
    from the Regulatory Baseline; the parser must not normalise it.
    """

    reg_a: str
    reg_b: str
    layer0_relationship: P1CLLM01Layer0Relationship
    company_scope_verdict: P1CLLM01CompanyScopeVerdict
    rationale: str = ""
    layer0_refs: list[str] = Field(default_factory=list)


class P1CLLM01SubDomainActivation(BaseModel):
    """One sub-domain's activation record (parsed from `### D-XX.Y`).

    CORR-074 propagation: aggregates the body fields plus the nested
    `#### Verified relationships` blocks (one per reg pair).
    """

    sub_domain_id: str
    applicable: bool
    scope_overlap: P1CLLM01ScopeOverlap
    applicable_regulations: list[str] = Field(default_factory=list)
    layer0_refs: list[str] = Field(default_factory=list)
    verified_relationship_per_pair: list[P1CLLM01Pair] = Field(default_factory=list)


class P1CLLM01DomainSummary(BaseModel):
    """Domain-level summary (parsed from `## Domain Summary`)."""

    total_sub_domains: int = 0
    active_sub_domains: int = 0
    pairwise_relationships: int = 0


class P1CLLM01Output(BaseModel):
    """Parsed + validated output of P1C-LLM-01-OVERLAP-CLASSIFICATION.

    CORR-074 propagation: envelope fields (prompt_spec_id, schema_version,
    case_id, invocation_pattern) are injected by the invoker post-parse —
    the LLM never emits them. Pydantic replaces JSON Schema as the
    single source of truth for validation (mirrors CORR-050 P1B-LLM-01
    pattern).

    `status` / `confidence` are reused from P1BLLM01Status /
    P1BLLM01Confidence (canonical top-level enum: OK /
    INSUFFICIENT_EVIDENCE / INDETERMINATE, HIGH / MEDIUM / LOW) — no
    new enums needed.
    """

    # Envelope (invoker-injected; LLM never emits)
    prompt_spec_id: str = "P1C-LLM-01-OVERLAP-CLASSIFICATION"
    schema_version: str = "1.0.0"
    case_id: str = ""
    invocation_pattern: str = "per_domain_lane"

    # Content (LLM-emitted, parser-extracted from markdown)
    status: P1BLLM01Status
    confidence: P1BLLM01Confidence
    domain_summary: P1CLLM01DomainSummary = Field(default_factory=P1CLLM01DomainSummary)
    sub_domain_activations: list[P1CLLM01SubDomainActivation] = Field(
        default_factory=list
    )
    notes: str = ""

    model_config = {"extra": "ignore"}


# =============================================================================
# CORR-074 propagation: P1C-LLM-03-STRATEGIC-SYNTHESIS output models
# (markdown+regex parsing — mirrors the CORR-050 / CORR-074 P1B-LLM-01
# pattern and the P1C-LLM-02 propagation shape).
#
# Replaces the JSON Schema in output_schemas.yaml as the source of truth
# for this spec. Envelope fields (prompt_spec_id, schema_version, case_id,
# invocation_pattern) are injected by the invoker post-parse — the LLM
# never emits them. Pydantic replaces JSON Schema as the only validator.
#
# Cross-lane (affected_sub_domains ≥ 2) and cross-regulation
# (regulations ≥ 2) enforcement is done at the Pydantic level via
# min_length=2 — any implication spanning a single sub-domain or
# a single regulation surfaces a clear ValidationError.
# =============================================================================


class P1CLLM03RiskLevel(str, Enum):
    """CORR-074 propagation: risk_level values for P1CLLM03Implication.

    Canonical taxonomy for the strategic implication risk-level:
      - LOW: minimal cross-lane risk
      - MEDIUM: moderate cross-lane risk
      - HIGH: significant cross-lane risk requiring escalation
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class P1CLLM03Implication(BaseModel):
    """One strategic implication (parsed from a `### IMP-NN` block).

    CORR-074 propagation: the LLM emits each implication as a markdown
    subsection under `## Implications` with body fields. The parser
    extracts the id from the heading and the structured fields from
    the body. `confidence` is reused from P1BLLM01Confidence so the
    per-implication confidence uses the canonical HIGH/MEDIUM/LOW
    enum.

    Cross-lane (`affected_sub_domains ≥ 2`) and cross-regulation
    (`regulations ≥ 2`) enforcement is at the Pydantic level.
    """

    id: str
    description: str
    affected_sub_domains: list[str] = Field(default_factory=list, min_length=2)
    regulations: list[str] = Field(default_factory=list, min_length=2)
    architectural_impact: str = ""
    business_goal_alignment: str = ""
    risk_level: P1CLLM03RiskLevel
    assumptions: list[str] = Field(default_factory=list)
    layer0_refs: list[str] = Field(default_factory=list)
    doc07b_refs: list[str] = Field(default_factory=list)
    confidence: P1BLLM01Confidence


class P1CLLM03Output(BaseModel):
    """Parsed + validated output of P1C-LLM-03-STRATEGIC-SYNTHESIS.

    CORR-074 propagation: envelope fields (prompt_spec_id, schema_version,
    case_id, invocation_pattern) are injected by the invoker post-parse —
    the LLM never emits them. Pydantic replaces JSON Schema as the
    single source of truth for validation (mirrors the P1B-LLM-01,
    P1B-LLM-02 and P1C-LLM-02 propagation patterns).

    `status` / `confidence` are reused from P1BLLM01Status /
    P1BLLM01Confidence (canonical top-level enum: OK /
    INSUFFICIENT_EVIDENCE / INDETERMINATE, HIGH / MEDIUM / LOW) — no
    new enums needed. The default empty implications list mirrors
    the spec's "1-2 acknowledging mostly settled" edge case.
    """

    # Envelope (invoker-injected; LLM never emits)
    prompt_spec_id: str = "P1C-LLM-03-STRATEGIC-SYNTHESIS"
    schema_version: str = "1.0.0"
    case_id: str = ""
    invocation_pattern: str = "global_reduce"

    # Content (LLM-emitted, parser-extracted from markdown)
    status: P1BLLM01Status
    confidence: P1BLLM01Confidence
    implications: list[P1CLLM03Implication] = Field(default_factory=list)
    notes: str = ""

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
    "P1BLLM02CoverageLevel",
    "P1BLLM02EffortEstimate",
    "P1BLLM02Gap",
    "P1BLLM02Implication",
    "P1BLLM02Output",
    "P1BLLM02Priority",
    "P1CLLM01CompanyScopeVerdict",
    "P1CLLM01DomainSummary",
    "P1CLLM01Layer0Relationship",
    "P1CLLM01Output",
    "P1CLLM01Pair",
    "P1CLLM01ScopeOverlap",
    "P1CLLM01SubDomainActivation",
    "P1CLLM02NegativeEvent",
    "P1CLLM02Output",
    "P1CLLM02PositiveEvent",
    "P1CLLM02Severity",
    "P1CLLM02TensionType",
    "P1CLLM03Implication",
    "P1CLLM03Output",
    "P1CLLM03RiskLevel",
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
