"""cross_reg — Filter cross-regulation analysis entries for a domain.

Reads ``state["preprocessing"]["cross_regulation"]`` and returns a
flat ``CrossRegEntry`` per pair (e.g. GDPR-CRA) found in entries
whose ``domain_id`` matches the requested domain prefix.

Each cross-regulation file may contain multiple ``<!-- pair: ... -->``
blocks (one per regulation pair). We emit one ``CrossRegEntry`` per
block so the prompt builder can cite specific divergences.

References:
    - contracts/SPRINT002_003_map_reduce_output.md
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)


def filter_cross_reg(state: V2State, domain_id: str) -> list[dict[str, str]]:
    """Return cross-regulation pair entries for ``domain_id``.

    Args:
        state: Pipeline V2State (uses
            ``preprocessing.cross_regulation``).
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        Sorted list of ``CrossRegEntry`` dicts (deduplicated by
        ``(pair, type)``). Empty when no cross-regulation data
        exists for the domain.
    """
    preprocessing = state.get("preprocessing") or {}
    raw = preprocessing.get("cross_regulation") or []
    if not isinstance(raw, list):
        return []

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if not _matches_domain(entry, domain_id):
            continue

        for pair_entry in _iter_pairs(entry):
            pair = pair_entry["pair"]
            if not pair or pair in seen:
                continue
            seen.add(pair)
            out.append({
                "pair": pair,
                "type": pair_entry["type"],
                "summary": pair_entry["summary"],
            })

    out.sort(key=lambda e: (e["pair"], e["type"]))
    logger.debug("filter_cross_reg(%s): %d entries", domain_id, len(out))
    return out


def _matches_domain(entry: dict[str, Any], domain_id: str) -> bool:
    """True when the entry's domain_id matches ``domain_id`` (prefix)."""
    raw_id = str(entry.get("domain_id") or entry.get("domainId") or "").strip().upper()
    if not raw_id:
        return False
    if raw_id == domain_id.upper():
        return True
    if raw_id.startswith(domain_id.upper() + "."):
        return True
    return False


def _iter_pairs(entry: dict[str, Any]) -> list[dict[str, str]]:
    """Yield one record per pair-block found in a cross-reg entry."""
    pairs_raw = entry.get("pairs") or []
    results: list[dict[str, str]] = []

    if isinstance(pairs_raw, list) and pairs_raw:
        for p in pairs_raw:
            if not isinstance(p, dict):
                continue
            pair = str(p.get("reg_pair") or p.get("pair") or "").strip()
            text = str(p.get("text") or p.get("analysis_text") or "").strip()
            ptype = _infer_type(text)
            results.append({
                "pair": pair,
                "type": ptype,
                "summary": _summarize(text),
            })
        return results

    analysis_text = str(entry.get("analysis_text") or "").strip()
    if analysis_text:
        results.append({
            "pair": str(entry.get("reg_pair") or entry.get("pair") or "").strip(),
            "type": _infer_type(analysis_text),
            "summary": _summarize(analysis_text),
        })
    return results


def _infer_type(text: str) -> str:
    """Pick a coarse type label from keywords in the pair text."""
    lower = text.lower()
    if "timing" in lower or "timeline" in lower or "notification" in lower:
        return "TIMELINE_DIVERGENCE"
    if "scope" in lower:
        return "SCOPE_DIVERGENCE"
    if "requirement" in lower or "documentation" in lower:
        return "REQUIREMENT_DIVERGENCE"
    if "intensity" in lower or "competence" in lower:
        return "INTENSITY_DIVERGENCE"
    return "OVERLAP"


def _summarize(text: str, max_chars: int = 300) -> str:
    """Extract the first sentence of the pair text as a short summary."""
    if not text:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        snippet = stripped
        if len(snippet) > max_chars:
            snippet = snippet[:max_chars].rstrip() + "…"
        return snippet
    return text[:max_chars]


__all__ = ["filter_cross_reg"]