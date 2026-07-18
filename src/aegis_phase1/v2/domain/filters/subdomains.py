"""subdomains — Filter SubDomainDef entries that belong to a domain.

Returns compact ``SubdomainSummary`` dicts for each sub-domain
(D-XX.Y) under the requested domain (D-XX). Each summary includes:

    - id:             sub-domain identifier (D-XX.Y)
    - title:          human-readable title from the SubDomainDef
    - hso_hl:         high-level objective from section2_hso
    - hso_per_reg:    list of ``{regulation, objective}`` entries
    - volere_requirements: list of Volere requirement dicts

The ``hso_per_reg`` mapping joins the parent's ``source_regulations``
(from the ontology, when available) with the sub-domain's
``per_reg_sos`` entries. For each per-regulation objective, the
regulation is determined in this order:

    1. the ontology's ``source_regulations[sid][i]`` by position
       (legacy 1:1 pairing);
    2. otherwise, extracted from the entry's ``id`` (e.g.
       ``"D-10.2.1 — Sub-SO for GDPR"``) via
       :func:`_extract_regulation`;
    3. otherwise, extracted from the entry's ``text`` via
       :func:`_extract_regulation`.

Entries for which no regulation can be determined are skipped.

When ``applicable_regs`` is provided (from
``state["company_context"].applicable_regs``), only entries whose
regulation is in that set are kept, so the LLM prompt only sees the
company-applicable regulations. This avoids confusing the model with
non-applicable per-regulation detail.

References:
    - contracts/SPRINT002_003_map_reduce_output.md
"""

from __future__ import annotations

import logging
import re
from typing import Any

from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)

_REG_PATTERN = re.compile(
    r"\b(GDPR|CRA|NIS[\s_]*2|DORA|AI[\s_]*Act)\b",
    re.IGNORECASE,
)


def _extract_regulation(text: str) -> str | None:
    """Return the canonical regulation code found in ``text``, or ``None``.

    Accepts synonyms and normalises to the canonical form:

        - ``"GDPR"`` / ``"gdpr"`` → ``"GDPR"``
        - ``"CRA"`` / ``"cra"`` → ``"CRA"``
        - ``"NIS 2"`` / ``"NIS2"`` / ``"NIS_2"`` / ``"nis 2"`` → ``"NIS2"``
        - ``"DORA"`` / ``"dora"`` → ``"DORA"``
        - ``"AI Act"`` / ``"AI_Act"`` / ``"AIAct"`` / ``"ai act"`` → ``"AI_Act"``

    Word boundaries in the regex prevent partial matches (e.g.
    ``"MINIS2"`` does not match).

    Args:
        text: Header or body text to scan (e.g. a per_reg_sos id).

    Returns:
        Canonical regulation code, or ``None`` if no known regulation
        is found in ``text``.
    """
    if not text:
        return None
    match = _REG_PATTERN.search(text)
    if match is None:
        return None
    raw = match.group(0)
    norm = raw.upper().replace(" ", "").replace("_", "")
    if norm.startswith("NIS"):
        return "NIS2"
    if norm.startswith("AI"):
        return "AI_Act"
    return norm


def _norm_reg_for_compare(code: str) -> str:
    """Normalise a regulation code for case/format-insensitive comparison.

    Strips spaces/underscores and upper-cases so ``"AI_Act"``,
    ``"AI Act"`` and ``"AIACT"`` all compare equal.
    """
    return code.upper().replace(" ", "").replace("_", "")


def filter_subdomains(state: V2State, domain_id: str) -> list[dict[str, Any]]:
    """Return all sub-domain summaries for ``domain_id``.

    Args:
        state: Pipeline ``V2State`` (must have ``subdomains`` and
            optionally ``ontology`` and ``company_context``).
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

    company_context = state.get("company_context")
    if company_context is not None and getattr(company_context, "applicable_regs", None) is not None:
        applicable_regs = company_context.applicable_regs
    else:
        applicable_regs = None

    summaries: list[dict[str, Any]] = []
    for sid in sorted(subs):
        if not sid.startswith(prefix):
            continue
        sub = subs[sid]
        summaries.append(
            _summarize(sid, sub, source_regs_by_sub, applicable_regs=applicable_regs)
        )

    logger.debug(
        "filter_subdomains(%s): %d subdomains (of %d total)",
        domain_id, len(summaries), len(subs),
    )
    return summaries


def _summarize(
    sid: str,
    sub: Any,
    source_regs_by_sub: dict[str, list[str]],
    *,
    applicable_regs: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Build a single ``SubdomainSummary`` from a ``SubDomainDef``.

    Args:
        sid: Sub-domain identifier (e.g. ``"D-04.1"``).
        sub: ``SubDomainDef`` instance (or dict) for the sub-domain.
        source_regs_by_sub: Ontology-derived regulation index keyed by
            sub-domain id. Used as a position-based hint for legacy
            1:1 pairing.
        applicable_regs: Optional list/tuple of regulation codes
            applicable to the company. When provided (non-None), only
            per-regulation entries whose regulation is in this set
            are kept. When ``None``, no applicability filter is
            applied and all parseable entries are kept.
    """
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

    hso_per_reg = _build_hso_per_reg(
        per_reg_sos,
        source_regs_by_sub.get(sid, []),
        hl_objective,
        applicable_regs=applicable_regs,
    )
    volere_requirements = data.get("section3_requirements") or []

    return {
        "id": sid,
        "title": title,
        "hso_hl": hl_objective,
        "hso_per_reg": hso_per_reg,
        "volere_requirements": list(volere_requirements) if isinstance(volere_requirements, list) else [],
    }


def _build_hso_per_reg(
    per_reg_sos: list[dict],
    source_regs: list[str],
    fallback_objective: str,
    *,
    applicable_regs: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, str]]:
    """Build the ``hso_per_reg`` list from ``per_reg_sos``.

    For each ``per_reg_sos`` entry, the regulation is determined in
    this order:

        1. ``source_regs[i]`` by position (legacy 1:1 pairing from
           the ontology's ``source_regulations``);
        2. else extracted from the entry's ``id`` via
           :func:`_extract_regulation`;
        3. else extracted from the entry's ``text`` via
           :func:`_extract_regulation`.

    Entries for which no regulation can be determined are skipped.

    When ``applicable_regs`` is provided (a non-None ``list`` or
    ``tuple``), only entries whose regulation (case/format-insensitive
    match) is in that set are kept. When ``applicable_regs`` is
    ``None``, no applicability filter is applied and all parseable
    entries are kept.

    The ``objective`` for each kept entry is the per_reg_sos text
    (stripped), falling back to ``fallback_objective`` (the high-level
    objective) when empty.
    """
    applicable_set: set[str] | None = None
    if isinstance(applicable_regs, list | tuple):
        applicable_set = {_norm_reg_for_compare(r) for r in applicable_regs if r}

    out: list[dict[str, str]] = []
    for i, entry in enumerate(per_reg_sos):
        if not isinstance(entry, dict):
            continue

        regulation: str | None = None
        if i < len(source_regs) and source_regs[i]:
            regulation = str(source_regs[i]).strip() or None
        if regulation is None:
            regulation = _extract_regulation(str(entry.get("id") or ""))
        if regulation is None:
            regulation = _extract_regulation(str(entry.get("text") or ""))
        if regulation is None:
            logger.debug("Skipping per_reg_so at index %d: no regulation found", i)
            continue

        if applicable_set is not None and _norm_reg_for_compare(regulation) not in applicable_set:
            continue

        objective = str(entry.get("text") or "").strip()
        if not objective:
            objective = fallback_objective

        out.append({"regulation": regulation, "objective": objective})
    return out


def _pair_per_reg(
    per_reg_sos: list[dict],
    source_regs: list[str],
    fallback_objective: str,
) -> list[dict[str, str]]:
    """Legacy 1:1 pairing helper (kept for backward compatibility).

    When ``source_regs`` has more entries than ``per_reg_sos`` (common
    because the on-disk file may only contain a single combined SO
    block), the remaining regulations fall back to ``hl_objective``.
    When ``per_reg_sos`` has more entries than ``source_regs``, extra
    entries are dropped to keep the contract 1:1.

    Not used by :func:`_summarize` anymore (see
    :func:`_build_hso_per_reg`); retained so any external import
    keeps working.
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
