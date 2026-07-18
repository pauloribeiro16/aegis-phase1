"""Filter complete OJ article bodies for a domain."""

from __future__ import annotations

import logging
from pathlib import Path

from aegis_phase1.v2.domain.filters.regs import filter_regs
from aegis_phase1.v2.loader.article_loader import load_articles_for_domain
from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)

_OJ_BASE_PATH = Path(
    "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/" "00_METHODOLOGY/PREPROCESSING"
)


def filter_articles(state: V2State, domain_id: str) -> list[dict[str, str]]:
    """Return complete OJ article text applicable to a domain.

    Regulation applicability is taken from the domain filter first and from
    ``company_context.applicable_regs`` when the domain filter has no result.
    Article source bodies are returned without prompt-size truncation.
    """
    regs = filter_regs(state, domain_id)
    if not regs:
        ctx = state.get("company_context")
        if ctx is not None:
            regs = list(getattr(ctx, "applicable_regs", []) or [])
    if not regs:
        return []

    applicable_subdomains = _applicable_subdomains(state, domain_id)
    articles = load_articles_for_domain(
        domain_id, regs, _OJ_BASE_PATH, applicable_subdomains=applicable_subdomains
    )
    result = [
        {
            "regulation": article["regulation"],
            "article": article["article"],
            "title": article["title"],
            "text": article["text"],
            "source_file": article.get("source_file", ""),
        }
        for article in articles
    ]
    logger.debug(
        "filter_articles(%s): %d articles (subs=%s)",
        domain_id,
        len(result),
        applicable_subdomains,
    )
    return result


def _applicable_subdomains(state: V2State, domain_id: str) -> list[str]:
    """Return the sub-domain IDs under ``domain_id`` for sub-domain filtering."""
    subdomains = state.get("subdomains") or {}
    if not subdomains:
        return []
    prefix = f"{domain_id.strip().upper()}."
    return sorted(sid for sid in subdomains if sid.upper().startswith(prefix))


__all__ = ["filter_articles"]
