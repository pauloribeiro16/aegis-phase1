"""filters — Per-domain context filters for the MAP stage.

Each filter is a PURE function: takes the ``V2State`` and a
``domain_id`` and returns a list/dict slice of the data that the
MAP-stage prompt builder needs for that domain.

Public API:
    filter_subdomains(state, domain_id) -> list[dict]
    filter_regs(state, domain_id) -> list[str]
    filter_cross_reg(state, domain_id) -> list[dict]
    filter_implementations(state, domain_id) -> list[dict]

Removed in CORR-037-T4 (v1 deprecation):
    filter_articles  — was using v1 ambiguity_loader; use domain/article_filter.filter_articles
    filter_ambiguities — was using v1 ambiguity_loader; replaced by preproc_catalog v2_pairs
"""

from aegis_phase1.v2.domain.filters.subdomains import filter_subdomains
from aegis_phase1.v2.domain.filters.regs import filter_regs
from aegis_phase1.v2.domain.filters.cross_reg import filter_cross_reg
from aegis_phase1.v2.domain.filters.implementations import filter_implementations

__all__ = [
    "filter_subdomains",
    "filter_regs",
    "filter_cross_reg",
    "filter_implementations",
]