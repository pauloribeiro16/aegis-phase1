"""regs — Filter the list of regulation short_names applicable to a domain.

A regulation is considered applicable when it appears in the
``source_regulations`` of at least one sub-domain belonging to the
requested domain AND it is also listed in the company context's
``applicable_regs`` (the case-level applicability assessment).

The two checks are intentionally intersected — this prevents
listing regulations whose clauses map to the domain but that the
company is exempt from (e.g. NIS 2 below the 50-employee threshold).

Fallback behaviour
-----------------
When the ontology has no ``source_regulations`` for the requested
domain (e.g. the ontology is missing the relevant sub-domain entries,
as happens for some D-10 sub-domains in the TinyTask case) but the
company context declares a non-empty ``applicable_regs``, the
intersection would collapse to ``[]`` and the domain would render no
per-regulation objectives. In that case we degrade gracefully and
return the company context's ``applicable_regs`` — at Phase 1A the
company-level applicability assessment is the authoritative source
for "which regulations apply to this organisation".

References:
    - contracts/SPRINT002_003_map_reduce_output.md
"""

from __future__ import annotations

import logging

from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)


def filter_regs(state: V2State, domain_id: str) -> list[str]:
    """Return regulation short-names applicable to a domain.

    Args:
        state: Pipeline V2State (uses ``ontology.subdomains`` and
            ``company_context.applicable_regs``).
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        Sorted, deduplicated list of regulation short names (e.g.
        ``["CRA", "GDPR"]``). Empty when both the ontology and the
        company context lack relevant data.

    Behaviour:
        * Normal path — intersect ontology ``source_regulations`` for
          the domain with ``company_context.applicable_regs``.
        * Fallback — when the ontology has no ``source_regulations``
          entries for ``domain_id`` (unknown domain or unpopulated
          ontology) but the company context has a non-empty
          ``applicable_regs``, return the company context's
          ``applicable_regs`` instead of an empty list. This avoids
          silent loss of per-regulation rendering at Phase 1A when
          the ontology is incomplete.
    """
    ontology = state.get("ontology") or {}
    domain_regs = _domain_source_regs(ontology, domain_id)

    ctx = state.get("company_context")
    applicable_regs: list[str] = []
    if ctx is not None:
        applicable_regs = list(getattr(ctx, "applicable_regs", []) or [])

    if not domain_regs and applicable_regs:
        # Fallback: ontology lacks source_regulations — use company applicability.
        logger.info(
            "filter_regs(%s): ontology empty for domain, falling back to "
            "company_context.applicable_regs=%s",
            domain_id,
            applicable_regs,
        )
        filtered = list(applicable_regs)
    elif applicable_regs:
        applicable_set = {str(r).strip() for r in applicable_regs if r}
        filtered = [r for r in domain_regs if r in applicable_set]
    else:
        filtered = list(domain_regs)

    out = sorted(set(filtered))
    logger.debug("filter_regs(%s): %s", domain_id, out)
    return out


def _domain_source_regs(ontology: dict, domain_id: str) -> list[str]:
    """Collect source_regulations from ontology subdomains in ``domain_id``."""
    prefix = domain_id + "."

    covered_container = ontology.get("subdomains")
    if isinstance(covered_container, dict):
        covered = covered_container.get("covered")
    elif isinstance(covered_container, list):
        covered = covered_container
    else:
        covered = None

    if not isinstance(covered, list):
        return []

    regs: list[str] = []
    for entry in covered:
        if not isinstance(entry, dict):
            continue
        sid = str(entry.get("id") or "").strip()
        if not sid.startswith(prefix):
            continue
        domain_id_attr = str(entry.get("domain_id") or "").strip()
        if domain_id_attr and domain_id_attr != domain_id:
            continue
        for r in entry.get("source_regulations") or []:
            if r:
                regs.append(str(r))

    return regs


__all__ = ["filter_regs"]
