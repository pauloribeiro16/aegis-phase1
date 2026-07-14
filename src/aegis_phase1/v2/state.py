"""state — Pydantic models and TypedDicts for the v2 map-reduce pipeline.

Defines the data models used throughout the v2 pipeline: CompanyContext,
SubDomainDef, DomainResult, and V2State.

References:
    - contracts/SPRINT001_v2-core.md (C-001)
    - src/aegis_phase1/models.py (existing enums)
"""

import logging
from typing import TypedDict

from pydantic import BaseModel, Field

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


class DomainResult(TypedDict):
    """Result of the MAP stage for a single domain (D-XX).

    Attributes:
        domain_id: Domain identifier (e.g. "D-01").
        domain_name: Human-readable domain name.
        subdomains: List of processed sub-domain dicts.
        coverage: Coverage level from CoverageLevel enum.
        cross_regulation: List of cross-regulation overlap analyses.
        llm_status: LLM processing status — OK/FAILED/SKIPPED.
        adapted_objective: LLM-adapted narrative paragraph (3-6 sentences)
            tailoring HSOs to company reality. Empty string when
            ``llm_status`` is ``FAILED``.
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
    llm_status: str
    adapted_objective: str
    key_changes: list[str]
    confidence: str


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


__all__ = [
    "CompanyContext",
    "DomainResult",
    "SubDomainDef",
    "V2State",
]
