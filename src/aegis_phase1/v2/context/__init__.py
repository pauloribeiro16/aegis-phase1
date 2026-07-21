"""v2/context — canonical context objects for the AEGIS-KG Phase 1 v2 pipeline.

Public API:
    applicability_context    (CORR-038) — applicable_regs + tier + gaps
    clause_mapping_context   (CORR-039) — clause → sub-domain mapping
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

__all__ = [
    "ApplicabilityContext",
    "ClauseMappingContext",
    "ClauseMappingEntry",
    "DeclarationGap",
    "Tier",
    "build_applicability_context",
    "build_clause_mapping_context",
]
