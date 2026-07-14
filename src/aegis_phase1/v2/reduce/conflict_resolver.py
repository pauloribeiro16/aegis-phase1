"""conflict_resolver — apply AMBIGUITY_ANALYSIS resolutions.

Each ambiguity in ``state.preprocessing["ambiguities"]`` represents a
known tension between two (or more) regulations on a sub-domain. The
resolver matches ambiguities against the merged requirements and
records the resolution outcome.

Typical example: TC-001 — CRA 24h notification vs GDPR 72h notification.
The resolution is to use the **stricter** deadline (CRA 24h), which
discharges both obligations. The resolver tags the affected
sub-domains as ``conflict resolved`` and stores the rationale in
``resolved_tensions``.

References:
    - contracts/SPRINT002_003_map_reduce_output.md (Sprint 003 — REDUCE step 3)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def resolve_conflicts(
    merged: dict[str, Any],
    ambiguities: list[dict[str, Any]] | dict[str, Any],
) -> dict[str, Any]:
    """Apply each ambiguity resolution to the relevant sub-domains.

    The function is intentionally conservative: it never rewrites
    requirement content. It only annotates the merged requirements
    dict with two sidecars (``resolved_tensions`` and
    ``conflicts_remaining``) so downstream stages can render Doc 07
    coverage + complementarity + gaps + gate.

    Args:
        merged: Output of :func:`merge_requirements`. Either the raw
            ``{"merged_requirements": [...]}`` dict or a flat list of
            merged-requirement dicts is accepted for convenience.
        ambiguities: List of ambiguity dicts as produced by
            :class:`PreprocessingLoader`. May also be a dict shaped
            ``{"ambiguities": [...]}``; both forms are tolerated.

    Returns:
        A dict with two keys:

        * ``resolved_tensions`` — list of resolution records, one per
          ambiguity that matched at least one sub-domain.
        * ``conflicts_remaining`` — list of ambiguity IDs that did not
          match any sub-domain in ``merged`` (left for the human to
          adjudicate per principle P7).
    """
    ambig_list = _normalise_ambiguities(ambiguities)
    merged_reqs = _normalise_merged(merged)

    subdomains_by_id: dict[str, dict[str, Any]] = {
        entry.get("subdomain", ""): entry for entry in merged_reqs
    }

    resolved: list[dict[str, Any]] = []
    remaining: list[str] = []

    for amb in ambig_list:
        amb_id = str(amb.get("id") or amb.get("document_id") or "").strip()
        target_subdomains = _extract_target_subdomains(amb, merged_reqs)

        if not target_subdomains:
            if amb_id:
                remaining.append(amb_id)
            continue

        resolution_text = (
            amb.get("resolution")
            or amb.get("decision")
            or amb.get("description")
            or ""
        )
        regulations = _safe_list(amb.get("regulations_involved") or amb.get("regs"))

        resolved.append(
            {
                "ambiguity_id": amb_id,
                "subdomains": target_subdomains,
                "regulations": regulations,
                "resolution": resolution_text,
                "status": "resolved",
            }
        )
        for sub_id in target_subdomains:
            entry = subdomains_by_id.get(sub_id)
            if entry is not None:
                entry.setdefault("resolutions", []).append(
                    {
                        "ambiguity_id": amb_id,
                        "resolution": resolution_text,
                    }
                )

    logger.info(
        "resolve_conflicts: %d ambiguities processed (%d resolved, %d remaining)",
        len(ambig_list),
        len(resolved),
        len(remaining),
    )
    return {
        "resolved_tensions": resolved,
        "conflicts_remaining": remaining,
    }


def _normalise_ambiguities(
    ambiguities: list[dict[str, Any]] | dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if ambiguities is None:
        return []
    if isinstance(ambiguities, dict):
        return list(ambiguities.get("ambiguities", []) or [])
    return list(ambiguities)


def _normalise_merged(
    merged: dict[str, Any] | list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if merged is None:
        return []
    if isinstance(merged, list):
        return merged
    return list(merged.get("merged_requirements", []) or [])


def _extract_target_subdomains(
    amb: dict[str, Any], merged_reqs: list[dict[str, Any]]
) -> list[str]:
    """Find which merged sub-domains the ambiguity applies to.

    Heuristics, in order:
        1. Explicit ``subdomains`` / ``target_subdomains`` field on the
           ambiguity.
        2. Explicit ``subdomain`` field (singular).
        3. Match by the regulations involved: any merged sub-domain
           whose ``source_regs`` overlaps the ambiguity's regulations.
    """
    explicit = amb.get("subdomains") or amb.get("target_subdomains")
    if explicit:
        return [str(s).strip() for s in explicit if str(s).strip()]

    single = amb.get("subdomain")
    if single:
        return [str(single).strip()]

    regs = {r.upper() for r in _safe_list(amb.get("regulations_involved") or amb.get("regs"))}
    if not regs:
        return []

    matches: list[str] = []
    for entry in merged_reqs:
        entry_regs = {r.upper() for r in _safe_list(entry.get("source_regs", []))}
        if entry_regs & regs:
            matches.append(entry.get("subdomain", ""))
    return [m for m in matches if m]


def _safe_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


__all__ = ["resolve_conflicts"]