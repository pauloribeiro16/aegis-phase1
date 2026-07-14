"""v2 — Public API for the v2 map-reduce pipeline.

Re-exports the main models and entry points.

References:
    - contracts/SPRINT001_v2-core.md
"""

from aegis_phase1.v2.state import CompanyContext, DomainResult, SubDomainDef, V2State

__all__ = [
    "CompanyContext",
    "DomainResult",
    "SubDomainDef",
    "V2State",
]
