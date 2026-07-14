"""subdomains — Filter SubDomainDef entries that belong to a domain.

Returns compact ``SubdomainSummary`` dicts for each sub-domain
(D-XX.Y) under the requested domain (D-XX). Each summary includes:

    - id:             sub-domain identifier (D-XX.Y)
    - title:          human-readable title from the SubDomainDef
    - hso_hl:         high-level objective from section2_hso
    - hso_per_reg:    list of ``{regulation, objective}`` entries
    - volere_requirements: list of Volere requirement dicts

The ``hso_per_reg`` mapping joins the parent's ``source_regulations``
(from the ontology) with the sub-domain's ``per_reg_sos`` entries,
so each per-regulation objective can be attributed to a regulation.

References:
    - contracts/SPRINT002_003_map_reduce_output.md
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)


def filter_subdomains(state: V2State, domain_id: str) -> list[dict[str, Any]]:
    """Return all sub-domain summaries for ``domain_id``.

    Args:
        state: Pipeline V2State (must have ``subdomains`` and
            optionally ``ontology``).
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        Sorted list of ``SubdomainSummary`` dicts, ordered by sub-id.
        Returns ``[]`` when no matching sub-domain exists or when
        ``state["subdomains"]`` is missing.
    """
    subs: dict[str, Any] = state.get("subdomains") or {}
    if not subs:
        logger.debug("filter_subdomains(%s): no subdomains in state", domain_id)
        return []

    prefix = domain_id + "."
    source_regs_by_sub = _build_source_regs_index(state.get("ontology") or {})

    summaries: list[dict[str, Any]] = []
    for sid in sorted(subs):
        if not sid.startswith(prefix):
            continue
        sub = subs[sid]
        summaries.append(_summarize(sid, sub, source_regs_by_sub))

    logger.debug(
        "filter_subdomains(%s): %d subdomains (of %d total)",
        domain_id, len(summaries), len(subs),
    )
    return summaries


def _summarize(
    sid: str,
    sub: Any,
    source_regs_by_sub: dict[str, list[str]],
) -> dict[str, Any]:
    """Build a single ``SubdomainSummary`` from a ``SubDomainDef``."""
    if hasattr(sub, "model_dump"):
        data = sub.model_dump()
    elif isinstance(sub, dict):
        data = sub
    else:
        data = {}

    title = data.get("title", sid) if isinstance(data, dict) else sid
    hso = data.get("section2_hso") or {} if isinstance(data, dict) else {}
    hl_objective = hso.get("hl_objective") or ""
    per_reg_sos = hso.get("per_reg_sos") or []

    source_regs = source_regs_by_sub.get(sid, [])
    hso_per_reg = _pair_per_reg(per_reg_sos, source_regs, hl_objective)
    volere_requirements = data.get("section3_requirements") or []

    return {
        "id": sid,
        "title": title,
        "hso_hl": hl_objective,
        "hso_per_reg": hso_per_reg,
        "volere_requirements": list(volere_requirements) if isinstance(volere_requirements, list) else [],
    }


def _pair_per_reg(
    per_reg_sos: list[dict],
    source_regs: list[str],
    fallback_objective: str,
) -> list[dict[str, str]]:
    """Pair ``per_reg_sos`` entries with ``source_regs`` 1:1 by index.

    When ``source_regs`` has more entries than ``per_reg_sos`` (common
    because the on-disk file may only contain a single combined SO
    block), the remaining regulations fall back to ``hl_objective``.
    When ``per_reg_sos`` has more entries than ``source_regs``, extra
    entries are dropped to keep the contract 1:1.
    """
    if not source_regs:
        return []

    out: list[dict[str, str]] = []
    for i, reg in enumerate(source_regs):
        if i < len(per_reg_sos) and isinstance(per_reg_sos[i], dict):
            objective = str(per_reg_sos[i].get("text") or "").strip()
        else:
            objective = fallback_objective
        if not objective:
            objective = fallback_objective
        out.append({"regulation": reg, "objective": objective})
    return out


def _build_source_regs_index(ontology: dict) -> dict[str, list[str]]:
    """Index ``source_regulations`` by sub-domain id from the ontology.

    Looks for ``subdomains.covered`` (the TinyTask ontology shape) and
    also accepts a flat ``subdomains`` list as fallback.
    """
    index: dict[str, list[str]] = {}

    covered_container = ontology.get("subdomains")
    if isinstance(covered_container, dict):
        covered = covered_container.get("covered")
    elif isinstance(covered_container, list):
        covered = covered_container
    else:
        covered = None

    if isinstance(covered, list):
        for entry in covered:
            if not isinstance(entry, dict):
                continue
            sid = str(entry.get("id") or "").strip()
            regs = entry.get("source_regulations") or []
            if sid and isinstance(regs, list) and regs:
                index[sid] = [str(r) for r in regs if r]

    return index


__all__ = ["filter_subdomains"]