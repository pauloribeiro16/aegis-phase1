"""reduce — REDUCE stage of the v2 map-reduce pipeline.

Concatenates MAP-stage domain results into a flat sub-domain view,
merges overlapping requirements across regulations, resolves
cross-regulation conflicts using the ambiguity catalogue, and finally
applies proportionality (TrackB) to assign a tier + 5 operational
attributes per sub-domain.

Modules:
    concatenator       - flatten DomainResult.subdomains into one dict
    merger             - merge requirements covered by multiple regs
    conflict_resolver  - apply AMBIGUITY_ANALYSIS resolutions
    proportionality    - TrackB.assign_tier() per sub-domain
"""

from aegis_phase1.v2.reduce.concatenator import concatenate
from aegis_phase1.v2.reduce.conflict_resolver import resolve_conflicts
from aegis_phase1.v2.reduce.merger import merge_requirements
from aegis_phase1.v2.reduce.proportionality import apply_proportionality

__all__ = [
    "concatenate",
    "merge_requirements",
    "resolve_conflicts",
    "apply_proportionality",
]