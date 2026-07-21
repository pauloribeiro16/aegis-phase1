"""CORR-039-T2: ClauseMappingContext — canonical source of clause→subdomain mappings.

Builds the clause-to-sub-domain mapping table that powers Doc 06. Reads
from ``PreprocCatalogLoader.load_clauses()`` filtered by the company's
``applicable_regs`` and resolves each clause to a sub-domain via the
``SR.source_clauses[] → SR.sub_domain[]`` chain.

Replaces the broken v1 read of ``state["ontology"]["clause_mappings"]``
(which the v1-compat shim never populated — Doc 06 rendered with 0 rows
pre-CORR-039).

Public API:
    ClauseMappingEntry     — one row of the mapping table (Pydantic)
    ClauseMappingContext   — full table with per-reg counts (Pydantic)
    build_clause_mapping_context(state) — factory: reads state, returns ctx

Consumers (CORR-039-T3):
    - v2/output/doc_06.py — reads entries, per_reg_count, total_clauses
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ClauseMappingEntry(BaseModel):
    """One row of the clause→sub-domain mapping table (Doc 06 row).

    Fields are minimal — Doc 06 needs 7 columns:
      clause_id, regulation, article, description, sub_domain,
      normative_strength, obligated_party
    Extra fields (source_sr_ids, nist_csf_mapping, text) are surfaced
    for future T4d enrichment but not used by Doc 06 today.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    clause_id: str
    regulation: str
    article: str = ""
    title: str = ""
    text: str = ""
    subdomain_id: str = ""
    maps_to_subdomain: str = ""  # human-readable (e.g., "D-01.1 Data at Rest Encryption")
    normative_strength: int = 2  # 1=low, 2=medium, 3=high; default until clause-level data lands
    obligated_party: str = "obligated_party"  # default; overridden by per-reg role when known
    source_sr_ids: list[str] = Field(default_factory=list)
    nist_csf_mapping: list[str] = Field(default_factory=list)


class ClauseMappingContext(BaseModel):
    """Canonical mapping table for Doc 06.

    Built from preproc catalog (clauses + SRs) filtered by applicable_regs.
    Sorted by (regulation, clause_id) for deterministic rendering.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    entries: list[ClauseMappingEntry] = Field(default_factory=list)
    per_reg_count: dict[str, int] = Field(default_factory=dict)
    total_clauses: int = 0
    unmapped_count: int = 0  # clauses with no SR link (orphans)

    def by_regulation(self, reg: str) -> list[ClauseMappingEntry]:
        """Return entries filtered by regulation (e.g. 'GDPR')."""
        return [e for e in self.entries if e.regulation == reg]

    def by_subdomain(self, subdomain_id: str) -> list[ClauseMappingEntry]:
        """Return entries filtered by sub-domain (e.g. 'D-01.1')."""
        return [e for e in self.entries if e.subdomain_id == subdomain_id]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict for downstream consumers (Doc 06, JSONL logs)."""
        return {
            "entries": [e.model_dump() for e in self.entries],
            "per_reg_count": dict(self.per_reg_count),
            "total_clauses": self.total_clauses,
            "unmapped_count": self.unmapped_count,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _build_clause_to_subdomain_map(
    srs: list[Any],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build clause_id → [sub_domain_ids] and clause_id → [sr_id] maps.

    Reads from a list of SR Pydantic models (each with ``source_clauses``
    and ``sub_domain`` attributes).

    Returns:
        (clause_to_subdomains, clause_to_sr_ids)
    """
    clause_to_subdomains: dict[str, list[str]] = {}
    clause_to_sr_ids: dict[str, list[str]] = {}
    for sr in srs:
        sr_id = getattr(sr, "id", None)
        sub_domains = list(getattr(sr, "sub_domain", []) or [])
        for src in getattr(sr, "source_clauses", []) or []:
            clause_id = getattr(src, "clause_id", None) or (
                src.get("clause_id") if isinstance(src, dict) else None
            )
            if not clause_id:
                continue
            if sub_domains:
                clause_to_subdomains.setdefault(clause_id, []).extend(sub_domains)
            if sr_id:
                clause_to_sr_ids.setdefault(clause_id, []).append(sr_id)
    return clause_to_subdomains, clause_to_sr_ids


def _resolve_article_ref(
    clause: Any,
    srs: list[Any],
    clause_id: str,
) -> str:
    """Return the article reference for a clause.

    Priority:
      1. SR.source_clauses[].article_ref (binding ref for this clause)
      2. clause.section_ref (fallback)
    """
    for sr in srs:
        for src in getattr(sr, "source_clauses", []) or []:
            cid = getattr(src, "clause_id", None) or (
                src.get("clause_id") if isinstance(src, dict) else None
            )
            if cid == clause_id:
                ref = getattr(src, "article_ref", None) or (
                    src.get("article_ref") if isinstance(src, dict) else None
                )
                if ref:
                    return str(ref)
    return str(getattr(clause, "section_ref", "") or "")


def _collect_nist_csf_mappings(
    srs: list[Any],
    clause_id: str,
) -> list[str]:
    """Aggregate NIST CSF subcategory IDs across all SRs that link to this clause."""
    out: list[str] = []
    for sr in srs:
        for src in getattr(sr, "source_clauses", []) or []:
            cid = getattr(src, "clause_id", None) or (
                src.get("clause_id") if isinstance(src, dict) else None
            )
            if cid != clause_id:
                continue
            for csf in getattr(sr, "nist_csf_mapping", []) or []:
                csf_id = getattr(csf, "id", None) or (
                    csf.get("id") if isinstance(csf, dict) else None
                )
                if csf_id and csf_id not in out:
                    out.append(str(csf_id))
    return out


def build_clause_mapping_context(
    state: dict[str, Any],
    *,
    applicable_regs: list[str] | None = None,
    srs: list[Any] | None = None,
    clauses: list[Any] | None = None,
) -> ClauseMappingContext:
    """Build the canonical clause→sub-domain mapping table.

    Args:
        state: V2 pipeline state. Read for:
            - ``v2_applicable_regs`` (or ``applicable_regs`` fallback)
            - ``v2_srs`` (list of SR Pydantic models)
            - ``v2_preproc_catalog_ref`` (PreprocCatalogLoader instance)
        applicable_regs: Override the applicable regs list (for tests).
        srs: Override the SR list (for tests).
        clauses: Override the clauses list (for tests).

    Returns:
        ClauseMappingContext with sorted entries + per-reg counts.
        Returns an empty context when:
          - applicable_regs is empty
          - v2_preproc_catalog_ref is missing AND no override (cannot load)
          - v2_srs is empty AND no override (no clause-to-subdomain resolution)
    """
    # Resolve applicable_regs
    if applicable_regs is None:
        applicable_regs = list(state.get("v2_applicable_regs") or [])
        if not applicable_regs:
            # Fallback: v1 shape (state.CompanyContext.applicable_regs)
            cc = state.get("company_context")
            if cc is not None and hasattr(cc, "applicable_regs"):
                applicable_regs = list(cc.applicable_regs or [])
            elif isinstance(cc, dict):
                applicable_regs = list(cc.get("applicable_regs", []) or [])

    if not applicable_regs:
        logger.info(
            "build_clause_mapping_context: no applicable_regs — returning empty context"
        )
        return ClauseMappingContext(entries=[], per_reg_count={}, total_clauses=0, unmapped_count=0)

    # Resolve SRs
    if srs is None:
        srs = list(state.get("v2_srs") or [])

    # Resolve clauses
    if clauses is None:
        catalog = state.get("v2_preproc_catalog_ref")
        if catalog is None:
            logger.info(
                "build_clause_mapping_context: no v2_preproc_catalog_ref — returning empty context"
            )
            return ClauseMappingContext(
                entries=[], per_reg_count={}, total_clauses=0, unmapped_count=0
            )
        clauses = []
        for reg in applicable_regs:
            clauses.extend(catalog.load_clauses(regulation=reg))

    if not clauses:
        logger.info(
            "build_clause_mapping_context: no clauses for applicable_regs=%s — empty context",
            applicable_regs,
        )
        return ClauseMappingContext(entries=[], per_reg_count={}, total_clauses=0, unmapped_count=0)

    # Build the clause → subdomain index from SRs
    clause_to_subdomains, clause_to_sr_ids = _build_clause_to_subdomain_map(srs)

    # Build entries
    entries: list[ClauseMappingEntry] = []
    unmapped_count = 0
    for clause in clauses:
        clause_id = getattr(clause, "id", None) or (
            clause.get("id") if isinstance(clause, dict) else None
        )
        if not clause_id:
            continue
        sub_domains = clause_to_subdomains.get(clause_id, [])
        if not sub_domains:
            unmapped_count += 1
            continue
        # Use the lexicographically first sub-domain for the row (deterministic).
        sd_id = sorted(set(sub_domains))[0]
        article = _resolve_article_ref(clause, srs, clause_id)
        nist = _collect_nist_csf_mappings(srs, clause_id)
        obligated = str(getattr(clause, "obligated_party", "") or "obligated_party")
        entries.append(
            ClauseMappingEntry(
                clause_id=clause_id,
                regulation=str(getattr(clause, "regulation", "") or ""),
                article=article,
                title=str(getattr(clause, "title", "") or ""),
                text=str(getattr(clause, "text", "") or "")[:200],
                subdomain_id=sd_id,
                maps_to_subdomain=sd_id,
                normative_strength=2,
                obligated_party=obligated,
                source_sr_ids=list(clause_to_sr_ids.get(clause_id, [])),
                nist_csf_mapping=nist,
            )
        )

    # Sort by (regulation, clause_id) for deterministic rendering
    entries.sort(key=lambda e: (e.regulation, e.clause_id))

    # Per-reg counts
    per_reg_count: dict[str, int] = {}
    for e in entries:
        per_reg_count[e.regulation] = per_reg_count.get(e.regulation, 0) + 1

    return ClauseMappingContext(
        entries=entries,
        per_reg_count=per_reg_count,
        total_clauses=len(entries),
        unmapped_count=unmapped_count,
    )


__all__ = [
    "ClauseMappingContext",
    "ClauseMappingEntry",
    "build_clause_mapping_context",
]
