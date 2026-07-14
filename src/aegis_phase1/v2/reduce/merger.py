"""merger — merge overlapping requirements from multiple regulations.

When a sub-domain is covered by more than one applicable regulation,
each regulation produces a parallel requirement (same intent, different
legal anchor). The merger keeps the highest-priority requirement per
logical group, joins the fit criteria with ``" AND "``, and unions the
source regulations.

Priority is the Volere ``priority`` field (``MUST`` > ``SHOULD`` >
``COULD``); when priorities tie, the first occurrence wins to keep
output deterministic.

References:
    - contracts/SPRINT002_003_map_reduce_output.md (Sprint 003 — REDUCE step 2)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_PRIORITY_RANK: dict[str, int] = {"MUST": 3, "SHOULD": 2, "COULD": 1}


def merge_requirements(subdomain_results: dict[str, Any]) -> dict[str, Any]:
    """Merge overlapping requirements per sub-domain.

    Iterates each sub-domain in ``subdomain_results["subdomains"]`` and,
    for every requirement group, keeps the entry with the highest
    priority. Fit criteria of merged peers are joined with ``" AND "``
    and their source regulations are unioned into a sorted list.

    Args:
        subdomain_results: Output of :func:`concatenate` — a dict whose
            ``subdomains`` key maps sub-domain IDs to raw MAP-stage
            sub-domain dicts. Each sub-domain dict may carry either a
            ``requirements`` list or an ``all_requirements`` list; if
            neither is present, an empty list is produced.

    Returns:
        A dictionary with one key:

        * ``merged_requirements`` — list of dicts, one per sub-domain.
          Each entry has the shape
          ``{"subdomain": str, "requirements": list[dict], "source_regs": list[str]}``.
    """
    raw: dict[str, dict[str, Any]] = (
        (subdomain_results or {}).get("subdomains", {}) or {}
    )

    merged: list[dict[str, Any]] = []

    for sub_id in sorted(raw.keys()):
        entry = raw[sub_id] or {}
        requirements: list[dict[str, Any]] = list(
            entry.get("requirements")
            or entry.get("all_requirements")
            or []
        )
        source_regs: list[str] = sorted(set(entry.get("source_regs", []) or []))

        kept = _merge_one_subdomain(requirements)
        merged.append(
            {
                "subdomain": sub_id,
                "requirements": kept,
                "source_regs": source_regs,
            }
        )

    logger.info(
        "merge_requirements: %d subdomains merged, %d total requirements kept",
        len(merged),
        sum(len(m["requirements"]) for m in merged),
    )
    return {"merged_requirements": merged}


def _merge_one_subdomain(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge requirements sharing the same logical key.

    Grouping key is the requirement's ``title`` when present, otherwise
    its ``req_id``. Within each group, the requirement with the highest
    Volere priority (``MUST`` > ``SHOULD`` > ``COULD``) is retained.
    Other peer requirements contribute their fit criterion (joined
    with ``" AND "``) and any new source regulation to the kept entry.
    """
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for req in requirements:
        key = str(req.get("title") or req.get("req_id") or "").strip()
        if not key:
            continue
        priority = str(req.get("priority", "MUST")).upper()
        rank = _PRIORITY_RANK.get(priority, 0)

        if key not in groups:
            groups[key] = dict(req)
            groups[key]["_rank"] = rank
            groups[key]["_peer_sources"] = set(_safe_regs(req))
            order.append(key)
            continue

        existing = groups[key]
        existing_rank = existing.get("_rank", 0)
        if rank > existing_rank:
            prev_fit = existing.get("fit_criterion")
            new_fit = req.get("fit_criterion")
            prev_sources = existing.get("_peer_sources", set())
            existing.clear()
            existing.update(req)
            existing["_rank"] = rank
            if prev_fit and new_fit and prev_fit != new_fit:
                existing["fit_criterion"] = f"{new_fit} AND {prev_fit}"
            existing["_peer_sources"] = prev_sources | set(_safe_regs(req))
        else:
            existing["_peer_sources"].update(_safe_regs(req))
            other_fit = req.get("fit_criterion")
            existing_fit = existing.get("fit_criterion")
            if other_fit and existing_fit and other_fit not in existing_fit:
                existing["fit_criterion"] = f"{existing_fit} AND {other_fit}"

    result: list[dict[str, Any]] = []
    for key in order:
        entry = dict(groups[key])
        entry.pop("_rank", None)
        sources = sorted(entry.pop("_peer_sources", set()))
        if sources:
            entry["source_regs"] = sorted(set(_safe_regs(entry) + sources))
        result.append(entry)
    return result


def _safe_regs(req: dict[str, Any]) -> list[str]:
    """Return a list of regulation tags from a requirement's ``regs`` field."""
    raw = req.get("regs") or req.get("source_regs") or []
    if isinstance(raw, str):
        return [r.strip() for r in raw.split(",") if r.strip()]
    return [str(r).strip() for r in raw if str(r).strip()]


__all__ = ["merge_requirements"]