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
return ``applicable_regs ∩ participating_regs_in_domain`` rather than
all of ``applicable_regs`` — at Phase 1A the company-level
applicability assessment is the authoritative source for "which
regulations apply to this organisation", but the cross-check ensures
we never claim a regulation is applicable when no sub-domain in the
domain actually has it as a participant.

If BOTH data sources (the ontology shim and ``state["subdomains"]``)
lack participating subdomains for the requested domain, the fallback
returns ``[]`` and logs at ERROR — we cannot defensibly include any
regulation without corroborating data.

Refs:
    - contracts/SPRINT002_003_map_reduce_output.md
    - CORR-101 Gap 1 (defense-in-depth cross-check; was: silent
      return of all applicable_regs).
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
    # CORR-067 S4: also pull from state["subdomains"] when the ontology
    # shim is empty (see _build_ontology_shim — it doesn't populate
    # subdomains.covered today). state["subdomains"] is a dict[id, Subdomain]
    # populated by the preproc_catalog loader. We synthesise the
    # covered list on the fly.
    if not domain_regs:
        domain_regs = _domain_source_regs_from_state_subdomains(state, domain_id)

    ctx = state.get("company_context")
    applicable_regs: list[str] = []
    if ctx is not None:
        # CORR-067 S4: ctx can be a dict (from Pydantic .model_dump())
        # OR an object (legacy Pydantic state). Handle both — getattr
        # on a dict misses dict keys, so the previous code always saw
        # an empty list when ctx was a dict, which collapsed the
        # intersection to []. Use isinstance guard.
        if isinstance(ctx, dict):
            applicable_regs = list(ctx.get("applicable_regs", []) or [])
        else:
            applicable_regs = list(getattr(ctx, "applicable_regs", []) or [])

    if not domain_regs and applicable_regs:
        # Fallback: ontology lacks source_regulations — cross-check against
        # the participating regulations actually present in any subdomain of
        # the requested domain. CORR-101 Gap 1: previously this returned all
        # applicable_regs blindly, which would incorrectly include regulations
        # that don't apply to this domain at all (silent correctness issue).
        participating = _participating_regs_in_domain(state, domain_id)
        if not participating:
            # No data source corroborates ANY regulation for this domain —
            # we cannot defensibly include any reg. Log at ERROR so this is
            # investigated (loader failure or schema drift).
            logger.error(
                "filter_regs(%s): fallback requested but BOTH ontology and "
                "state['subdomains'] lack participating regs for this domain; "
                "returning [] (was: return all applicable_regs=%s). "
                "Investigate loader state.",
                domain_id,
                applicable_regs,
            )
            filtered = []
        else:
            applicable_set = {_canonical_reg_name(r) for r in applicable_regs if r}
            participating_set = {_canonical_reg_name(r) for r in participating}
            excluded = sorted(applicable_set - participating_set)
            if excluded:
                logger.warning(
                    "filter_regs(%s): fallback excludes %s — no participating "
                    "subdomain in this domain carries these regs. applicable=%s "
                    "participating=%s",
                    domain_id,
                    excluded,
                    sorted(applicable_set),
                    sorted(participating_set),
                )
            else:
                logger.warning(
                    "filter_regs(%s): fallback intersects applicable with "
                    "participating_in_domain=%s",
                    domain_id,
                    sorted(participating_set),
                )
            filtered = sorted(applicable_set & participating_set)
    elif applicable_regs:
        # CORR-101 Gap 1: canonicalize both sides so dirty strings
        # like "AI_Act (partial)" / "CRA (sole authority)" match
        # against the company-level applicable_regs (which is clean).
        applicable_set = {_canonical_reg_name(r) for r in applicable_regs if r}
        canonical_domain = {_canonical_reg_name(r) for r in domain_regs}
        filtered = sorted(applicable_set & canonical_domain)
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


def _domain_source_regs_from_state_subdomains(state: V2State, domain_id: str) -> list[str]:
    """CORR-067 S4: fallback when the ontology shim lacks subdomains.

    state['subdomains'] is a dict[subdomain_id, Subdomain] populated
    by the preproc_catalog loader. We extract source_regulations
    from each subdomain in the requested domain and return the
    deduped list.

    Subdomain objects (Pydantic) have an ``applies_to`` or
    ``source_regulations`` attribute depending on the loader version;
    we try both.

    CORR-101 Gap 1: log explicitly at DEBUG when no subdomains are
    found for the domain prefix (was: silent empty list).
    """
    subdomains = state.get("subdomains") or {}
    if not isinstance(subdomains, dict):
        logger.debug(
            "_domain_source_regs_from_state_subdomains(%s): "
            "state['subdomains'] is not a dict (%s); skipping",
            domain_id,
            type(subdomains).__name__,
        )
        return []

    prefix = domain_id + "."
    in_domain = [sid for sid in subdomains if isinstance(sid, str) and sid.startswith(prefix)]
    if not in_domain:
        logger.debug(
            "_domain_source_regs_from_state_subdomains(%s): no subdomains "
            "with prefix %r in state['subdomains'] (total=%d)",
            domain_id,
            prefix,
            len(subdomains),
        )
        return []

    regs: list[str] = []
    for sid in in_domain:
        sub = subdomains[sid]
        # Pydantic Subdomain object
        if hasattr(sub, "participating_regulations"):
            sr = sub.participating_regulations or []
        elif hasattr(sub, "source_regulations"):
            sr = sub.source_regulations or []
        elif hasattr(sub, "applies_to"):
            sr = sub.applies_to or []
        elif isinstance(sub, dict):
            sr = (
                sub.get("participating_regulations")
                or sub.get("source_regulations")
                or sub.get("applies_to")
                or []
            )
        else:
            sr = []
        for r in sr:
            if r:
                regs.append(str(r))
    return regs


def _participating_regs_in_domain(
    state: V2State, domain_id: str
) -> set[str] | None:
    """Return the set of regulations that participate in any subdomain of D-XX.

    Used by the CORR-101 Gap 1 defense-in-depth cross-check in
    :func:`filter_regs` to ensure the fallback path never returns a
    regulation that has no participating subdomain in the requested
    domain.

    Behaviour:
        * Returns ``None`` when BOTH the ontology shim and
          ``state['subdomains']`` lack any data for ``domain_id``
          (callers should treat ``None`` as "no corroborating data
          at all" and return ``[]`` with an ERROR-level log).
        * Returns an empty set when data sources are populated but
          no subdomain in the domain carries any participating
          regulation (suspicious but distinguishable from "no data").
        * Returns the union of canonical regulation names otherwise.

    Canonicalisation
        Regulation strings sometimes carry human annotations (e.g.
        ``"AI_Act (partial)"`` or ``"CRA (sole authority)"``). We
        strip parenthesised annotations and trailing qualifiers so
        the cross-check matches the company-level applicability
        assessment (``["GDPR", "CRA", ...]``).

    Args:
        state: Pipeline ``V2State``.
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        Set of canonical regulation names participating in at least
        one subdomain of ``domain_id``, or ``None`` when no data
        source has any subdomain for the requested domain.
    """
    subdomains = state.get("subdomains") or {}
    if isinstance(subdomains, dict):
        prefix = domain_id + "."
        in_domain = [
            sid for sid in subdomains if isinstance(sid, str) and sid.startswith(prefix)
        ]
        if in_domain:
            regs: set[str] = set()
            for sid in in_domain:
                sub = subdomains[sid]
                if hasattr(sub, "participating_regulations"):
                    sr = sub.participating_regulations or []
                elif hasattr(sub, "source_regulations"):
                    sr = sub.source_regulations or []
                elif hasattr(sub, "applies_to"):
                    sr = sub.applies_to or []
                elif isinstance(sub, dict):
                    sr = (
                        sub.get("participating_regulations")
                        or sub.get("source_regulations")
                        or sub.get("applies_to")
                        or []
                    )
                else:
                    sr = []
                for r in sr:
                    if r:
                        regs.add(_canonical_reg_name(r))
            return regs
    # state["subdomains"] missing or empty for D-XX — try the ontology shim
    ontology = state.get("ontology") or {}
    covered_container = ontology.get("subdomains")
    if isinstance(covered_container, dict):
        covered = covered_container.get("covered")
    elif isinstance(covered_container, list):
        covered = covered_container
    else:
        covered = None
    if isinstance(covered, list) and covered:
        prefix = domain_id + "."
        regs = set()
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
                    regs.add(_canonical_reg_name(r))
        if regs:
            return regs

    # Neither source has any data for this domain.
    return None


def _canonical_reg_name(raw: str) -> str:
    """Strip human annotations from a regulation short-name.

    Examples
        >>> _canonical_reg_name("AI_Act (partial)")
        'AI_Act'
        >>> _canonical_reg_name("CRA (sole authority)")
        'CRA'
        >>> _canonical_reg_name("GDPR")
        'GDPR'

    Rules:
        * If a ``(`` is present, take everything before it.
        * Else if a space is present, take the first whitespace-separated token.
        * Else return the trimmed string.

    Args:
        raw: Raw regulation string from participating_regulations.

    Returns:
        Canonical short-name suitable for equality matching against
        ``company_context.applicable_regs``.
    """
    s = str(raw).strip()
    if not s:
        return ""
    if "(" in s:
        s = s.split("(", 1)[0].strip()
    elif " " in s:
        s = s.split(" ", 1)[0].strip()
    return s


__all__ = ["filter_regs"]
