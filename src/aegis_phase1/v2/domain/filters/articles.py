"""articles — Filter clause-mappings (ontology articles) for a domain.

Reads ``state["ontology"]["clause_mappings"]`` and returns truncated
``ArticleSnippet`` dicts for clauses whose ``maps_to_subdomain``
starts with the domain prefix. Each snippet includes the regulation
short name (parsed from ``regulation_id``, e.g. ``"REG-GDPR"`` →
``"GDPR"``), the article label, the description, and a truncated
text body.

Truncation: each article text is capped at 2000 characters (~500
tokens) so the prompt builder does not blow context windows.

References:
    - contracts/SPRINT002_003_map_reduce_output.md
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)

# 2000 chars ≈ 500 tokens (OpenAI/Anthropic rule of thumb for English).
_MAX_ARTICLE_CHARS = 2000


def filter_articles(state: V2State, domain_id: str) -> list[dict[str, str]]:
    """Return article snippets for clauses mapped to ``domain_id``.

    Args:
        state: Pipeline V2State (uses ``ontology.clause_mappings``).
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        Sorted list of ``ArticleSnippet`` dicts (deduplicated by
        ``(regulation, article)``). Empty when the ontology has no
        clause_mappings.
    """
    ontology = state.get("ontology") or {}
    mappings = ontology.get("clause_mappings") or []
    if not isinstance(mappings, list):
        return []

    prefix = domain_id + "."
    seen: set[tuple[str, str]] = set()
    snippets: list[dict[str, str]] = []

    for clause in mappings:
        if not isinstance(clause, dict):
            continue
        target = str(clause.get("maps_to_subdomain") or "").strip()
        if not target.startswith(prefix):
            continue

        regulation_id = str(clause.get("regulation_id") or "").strip()
        short_name = _short_name(regulation_id)
        article = str(clause.get("article") or "").strip()
        key = (short_name, article)
        if key in seen or not article:
            continue
        seen.add(key)

        title = str(clause.get("description") or "").strip()
        text_source = clause.get("text") or clause.get("article_text") or title
        truncated = _truncate(str(text_source))

        snippets.append({
            "regulation": short_name,
            "article": article,
            "title": title,
            "text": truncated,
        })

    snippets.sort(key=lambda s: (s["regulation"], s["article"]))
    logger.debug("filter_articles(%s): %d snippets", domain_id, len(snippets))
    return snippets


def _short_name(regulation_id: str) -> str:
    """Convert ``"REG-GDPR"`` → ``"GDPR"``; fall back to input."""
    if not regulation_id:
        return ""
    if regulation_id.startswith("REG-"):
        return regulation_id[4:]
    return regulation_id


def _truncate(text: str) -> str:
    """Trim to ``_MAX_ARTICLE_CHARS`` characters, appending a marker."""
    if len(text) <= _MAX_ARTICLE_CHARS:
        return text
    return text[: _MAX_ARTICLE_CHARS].rstrip() + " […]"


__all__ = ["filter_articles"]