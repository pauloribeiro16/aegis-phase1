"""v2/context — canonical context objects for the AEGIS-KG Phase 1 v2 pipeline.

Public API:
    applicability_context    (CORR-038) — applicable_regs + tier + gaps
    clause_mapping_context   (CORR-039) — clause → sub-domain mapping
    domain_activation_context (CORR-040) — per-domain lane activation
    synthesis_context        (CORR-041) — REDUCE-stage output
"""
from __future__ import annotations

from aegis_phase1.v2.context.applicability_context import (
    ApplicabilityContext,
    DeclarationGap,
    Tier,
    build_applicability_context,
)
from aegis_phase1.v2.context.clause_mapping_context import (
    ClauseMappingContext,
    ClauseMappingEntry,
    build_clause_mapping_context,
)
from aegis_phase1.v2.context.domain_activation_context import (
    CoverageLevel,
    DomainActivationContext,
    DomainLaneActivation,
    SubDomainActivation,
    build_domain_activation_context,
)
from aegis_phase1.v2.context.synthesis_context import (
    CompoundEvent,
    StrategicSynthesis,
    SynthesisContext,
    build_synthesis_context,
)

__all__ = [
    "ApplicabilityContext",
    "ClauseMappingContext",
    "ClauseMappingEntry",
    "CompoundEvent",
    "CoverageLevel",
    "DomainActivationContext",
    "DomainLaneActivation",
    "DeclarationGap",
    "StrategicSynthesis",
    "SubDomainActivation",
    "SynthesisContext",
    "Tier",
    "build_applicability_context",
    "build_clause_mapping_context",
    "build_domain_activation_context",
    "build_synthesis_context",
]
