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
    if (
        company_context is not None
        and getattr(company_context, "applicable_regs", None) is not None
    ):
        applicable_regs = company_context.applicable_regs
    else:
        applicable_regs = None

    summaries: list[dict[str, Any]] = []
    for sid in sorted(subs):
        if not sid.startswith(prefix):
            continue
        sub = subs[sid]
        summaries.append(_summarize(sid, sub, source_regs_by_sub, applicable_regs=applicable_regs))

    logger.debug(
        "filter_subdomains(%s): %d subdomains (of %d total)",
        domain_id,
        len(summaries),
        len(subs),
    )
    return summaries


def _summarize(
    sid: str,
    sub: Any,
    source_regs_by_sub: dict[str, list[str]],
    *,
    applicable_regs: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Build a single ``SubdomainSummary`` from a sub-domain.

    Args:
        sid: Sub-domain identifier (e.g. ``"D-04.1"``).
        sub: A v1 ``SubDomainDef`` (state.py) OR a v2 Pydantic ``Subdomain``
            (preproc_catalog.py). Both shapes are accepted; the helper
            :func:`_normalize_subdomain_to_v1` adapts the v2 shape to the
            v1 dict shape so the rest of the consumer code is unchanged.
        source_regs_by_sub: Ontology-derived regulation index keyed by
            sub-domain id. Used as a position-based hint for legacy
            1:1 pairing.
        applicable_regs: Optional list/tuple of regulation codes
            applicable to the company. When provided (non-None), only
            per-regulation entries whose regulation is in this set
            are kept. When ``None``, no applicability filter is
            applied and all parseable entries are kept.
    """
    data = _normalize_subdomain_to_v1(sub)
    if not isinstance(data, dict):
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
        "volere_requirements": list(volere_requirements)
        if isinstance(volere_requirements, list)
        else [],
    }


def _normalize_subdomain_to_v1(sub: Any) -> dict[str, Any]:
    """Normalize a sub-domain object to the v1 dict shape.

    Accepts:
      - v1: ``SubDomainDef`` (state.py) — has ``model_dump()`` returning
        the v1 shape (title, section2_hso, section3_requirements, ...)
      - v1: plain dict in v1 shape (passes through)
      - v2: ``Subdomain`` Pydantic (preproc_catalog.py) — has different
        field names (hso_hl / hso_per_reg / security_requirements /
        participating_regulations / pairs) that this helper maps to
        the v1 shape (section2_hso.hl_objective + per_reg_sos;
        section3_requirements).

    Returns:
        A dict with v1 keys (title, section2_hso, section3_requirements,
        section1_crda, frontmatter) so the rest of the consumer code is
        shape-agnostic.

    CORR-037-T3c: enables the orchestrator to substitute v2 Pydantic
    Subdomain (from preproc_catalog) for v1 SubDomainDef (from
    SubDomainLoader) without breaking downstream consumers.
    """
    # Pass-through: already a dict (assume v1 shape; if it's v2 shape,
    # the model_dump-equivalent values won't have section2_hso and the
    # rest of the helper would return empty — that path is rare).
    if isinstance(sub, dict):
        # Quick detection: v1 has "section2_hso" key; v2 has "hso_hl".
        if "section2_hso" in sub or "section3_requirements" in sub:
            return sub
        # If it looks like a v2 model_dump (has hso_hl / hso_per_reg),
        # fall through to the Pydantic-style normalization below.
        if "hso_hl" in sub or "hso_per_reg" in sub:
            return _v2_dict_to_v1_dict(sub)
        # Unknown shape; return as-is (best effort).
        return sub

    if hasattr(sub, "model_dump"):
        try:
            dumped = sub.model_dump()
        except Exception:
            return {}
        return _normalize_subdomain_to_v1(dumped)

    return {}


def _v2_dict_to_v1_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Convert a v2 Pydantic Subdomain model_dump() to the v1 dict shape.

    Mapping:
      data["title"]                    -> data["title"]                  (same)
      data["hso_hl"]["objective"]      -> data["section2_hso"]["hl_objective"]
      data["hso_per_reg"][...]         -> data["section2_hso"]["per_reg_sos"][...]
                                          (each item: {id, text, regulation})
      data["security_requirements"]    -> data["section3_requirements"][...]
      data["pairs"]                    -> data["section1_crda"][...]
    """
    out: dict[str, Any] = {}
    out["title"] = data.get("title", "")

    # hso_hl (Pydantic object after model_dump) -> section2_hso.hl_objective
    hso_hl = data.get("hso_hl")
    if isinstance(hso_hl, dict):
        hl_objective = hso_hl.get("objective") or ""
    elif hso_hl is not None and hasattr(hso_hl, "objective"):
        hl_objective = getattr(hso_hl, "objective", "") or ""
    else:
        hl_objective = ""

    # hso_per_reg (list of Pydantic HSOPerReg after model_dump) -> per_reg_sos
    hso_per_reg = data.get("hso_per_reg") or []
    per_reg_sos: list[dict[str, str]] = []
    for entry in hso_per_reg:
        if entry is None:
            continue
        if isinstance(entry, dict):
            entry_id = str(entry.get("id") or "")
            entry_text = str(entry.get("objective") or "")
            entry_reg = str(entry.get("regulation") or "")
        else:
            entry_id = str(getattr(entry, "id", "") or "")
            entry_text = str(getattr(entry, "objective", "") or "")
            entry_reg = str(getattr(entry, "regulation", "") or "")
        per_reg_sos.append(
            {
                "id": entry_id,
                "text": entry_text,
                "regulation": entry_reg,
            }
        )

    out["section2_hso"] = {
        "hl_objective": hl_objective,
        "per_reg_sos": per_reg_sos,
    }

    # security_requirements -> section3_requirements
    sec_reqs = data.get("security_requirements") or []
    section3: list[dict[str, Any]] = []
    for sr in sec_reqs:
        if sr is None:
            continue
        if isinstance(sr, dict):
            section3.append(
                {
                    "id": sr.get("id", ""),
                    "sr_short": sr.get("sr_short", ""),
                    "title": sr.get("title", ""),
                    "csf": list(sr.get("csf") or []),
                    "anchors": list(sr.get("anchors") or []),
                    "nist_csf_mapping": list(sr.get("nist_csf_mapping") or []),
                }
            )
        else:
            section3.append(
                {
                    "id": getattr(sr, "id", ""),
                    "sr_short": getattr(sr, "sr_short", ""),
                    "title": getattr(sr, "title", ""),
                    "csf": list(getattr(sr, "csf", []) or []),
                    "anchors": list(getattr(sr, "anchors", []) or []),
                    "nist_csf_mapping": list(getattr(sr, "nist_csf_mapping", []) or []),
                }
            )
    out["section3_requirements"] = section3

    # pairs -> section1_crda
    pairs = data.get("pairs") or []
    section1: list[dict[str, Any]] = []
    for p in pairs:
        if p is None:
            continue
        if isinstance(p, dict):
            section1.append(dict(p))
        else:
            section1.append(
                {
                    "id": getattr(p, "id", ""),
                    "subdomain_id": getattr(p, "subdomain_id", ""),
                    "reg_a": getattr(p, "reg_a", ""),
                    "reg_b": getattr(p, "reg_b", ""),
                    "classification": getattr(p, "classification", ""),
                    "verified_relationship": getattr(p, "verified_relationship", ""),
                    "downstream_implication": getattr(p, "downstream_implication", ""),
                }
            )
    out["section1_crda"] = section1

    return out


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
