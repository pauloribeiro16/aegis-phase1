"""filters — Per-domain context filters for the MAP stage.

Each filter is a PURE function: takes the ``V2State`` and a
``domain_id`` and returns a list/dict slice of the data that the
MAP-stage prompt builder needs for that domain.

Public API:
    filter_subdomains(state, domain_id) -> list[dict]
    filter_regs(state, domain_id) -> list[str]
    filter_articles(state, domain_id) -> list[dict]
    filter_ambiguities(state, domain_id) -> list[dict]
    filter_cross_reg(state, domain_id) -> list[dict]
    filter_implementations(state, domain_id) -> list[dict]
"""

from aegis_phase1.v2.domain.filters.subdomains import filter_subdomains
from aegis_phase1.v2.domain.filters.regs import filter_regs
from aegis_phase1.v2.domain.filters.articles import filter_articles
from aegis_phase1.v2.domain.filters.ambiguities import filter_ambiguities
from aegis_phase1.v2.domain.filters.cross_reg import filter_cross_reg
from aegis_phase1.v2.domain.filters.implementations import filter_implementations

__all__ = [
    "filter_subdomains",
    "filter_regs",
    "filter_articles",
    "filter_ambiguities",
    "filter_cross_reg",
    "filter_implementations",
]