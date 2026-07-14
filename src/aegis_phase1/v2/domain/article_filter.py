"""article_filter — Select regulations applicable to a given domain.

Two filter modes:
    1. Keyword match against the regulation description (short_name /
       name / ontology keywords).
    2. Cross-regulation analysis entries that explicitly cite the
       domain.

The two modes are unioned (deduplicated by regulation short name).

References:
    - contracts/SPRINT002_003_map_reduce_output.md
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)


# ─── Domain → keyword map ─────────────────────────────────────────────
# Conservative keywords matched (case-insensitive) against regulation
# name / short_name / description. Keep lists short — better to miss
# a marginal hit than to over-fire.

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "D-01": ["gdpr", "data protection", "privacy", "personal data"],
    "D-02": ["cra", "vulnerability", "product", "psirt"],
    "D-03": ["access control", "nis 2", "nis2", "gdpr", "authentication"],
    "D-04": ["incident", "nis 2", "nis2", "dora", "breach", "psirt"],
    "D-05": ["gdpr", "data lifecycle", "retention", "ai act"],
    "D-06": ["supply chain", "cra", "third party", "dora", "vendor"],
    "D-07": ["secure development", "cra", "vulnerability", "sdlc"],
    "D-08": ["ai act", "gdpr", "nis 2", "nis2", "human", "awareness"],
    "D-09": ["governance", "nis 2", "nis2", "dora", "ai act", "gdpr"],
    "D-10": ["monitoring", "audit", "dora", "nis 2", "nis2", "logging"],
}


def filter_articles(state: V2State, domain_id: str) -> list[dict]:
    """Return regulations applicable to a domain.

    Args:
        state: Pipeline V2State (uses ``regulations`` and
            ``preprocessing.cross_regulation``).
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        List of regulation dicts. Each dict is a shallow copy of the
        source regulation entry with an added ``_match_source`` key
        (``"keyword"`` or ``"cross_reg"``) indicating why it was
        selected. Always deduplicated by ``short_name`` (falls back to
        ``name``).
    """
    regulations: list[dict] = list(state.get("regulations", []) or [])
    keywords = [k.lower() for k in _DOMAIN_KEYWORDS.get(domain_id, [])]
    cross_reg: list[dict] = list(state.get("preprocessing", {}).get("cross_regulation", []) or [])

    selected: dict[str, dict] = {}

    for reg in regulations:
        haystack = " ".join(
            str(reg.get(k, "")) for k in ("short_name", "name", "description", "keywords")
        ).lower()
        if any(kw in haystack for kw in keywords):
            key = _reg_key(reg)
            if key not in selected:
                entry = dict(reg)
                entry["_match_source"] = "keyword"
                selected[key] = entry

    for entry in cross_reg:
        if domain_id.upper() not in {str(entry.get("domain_id", "")).upper(), str(entry.get("domainId", "")).upper()}:
            continue
        involved = entry.get("involved_regulations") or entry.get("involvedRegulations") or []
        if isinstance(involved, str):
            involved = [s.strip() for s in involved.split(",") if s.strip()]
        for reg_name in involved:
            if reg_name not in selected:
                selected[reg_name] = {
                    "short_name": reg_name,
                    "name": reg_name,
                    "_match_source": "cross_reg",
                }

    result = list(selected.values())
    logger.debug("filter_articles(%s): %d applicable regs", domain_id, len(result))
    return result


def _reg_key(reg: dict) -> str:
    """Stable key for dedupe — prefer ``short_name`` over ``name``."""
    return str(reg.get("short_name") or reg.get("name") or reg.get("regulation_id") or "").strip()


__all__ = ["filter_articles"]
