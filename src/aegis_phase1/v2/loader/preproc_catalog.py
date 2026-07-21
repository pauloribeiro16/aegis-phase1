"""CORR-037-T1: PreprocCatalogLoader — typed JSON loader for preproc_out/.

Replaces regex-based MD parsing in v1 loaders (subdomain_loader, article_loader,
ambiguity_loader, preprocessing_loader) with a single typed JSON loader that
returns Pydantic models. The loader reads exclusively from `preproc_out/`
(treated as read-only per AGENTS.md §0 / §"Não mexer em preproc_out/") and
caches in-memory via `functools.lru_cache` for the duration of a run.

Public API (used by orchestrator and tests):
    loader = PreprocCatalogLoader(preproc_root=Path("preproc_out"))
    loader.load_subdomains()     # -> list[Subdomain]  (38)
    loader.load_srs(...)         # -> list[SR]         (282)
    loader.load_sos(...)         # -> list[SO]         (338)
    loader.load_csfs()           # -> list[CSFSubcat]  (185)
    loader.load_clauses(...)     # -> list[Clause]     (578)
    loader.load_pairs(...)       # -> list[Pair]       (196)
    loader.load_audit()          # -> AuditReport      (2 reports aggregated)
    loader.load_index()          # -> EntitiesIndex
    loader.clear_cache()         # for tests / rebuild

Conventions (AGENTS.md §11):
- IDs are `D-XX.Y` (not `SD-XX.Y`).
- Filename uses UNDERSCORE (`D-01.1_GDPR-CRA.json`); JSON `id` field uses HYPHEN.
- AI_Act canonical (not AIACT / AI Act / AIA).
- DORA multi-clause: `DORA-CL{NN}-{M}`.
- `verified_relationship` is FROZEN — loader does not modify it.
- Pydantic models are tolerant to nulls and extra fields (`extra="allow"`).
"""

from __future__ import annotations

import json
import logging
from functools import cache as functools_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models — mirror the actual JSON in preproc_out/3-entities/.
# Kept minimal: only the fields needed by the orchestrator + tests.
# `extra="allow"` tolerates fields not yet captured (model_extra exposed).
# ---------------------------------------------------------------------------


class _TolerantModel(BaseModel):
    """Base for all preproc models — tolerates extra fields and nulls."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


class SourceClauseRef(_TolerantModel):
    """Reference from SR/SO to a source clause (e.g. GDPR-CL06)."""

    clause_id: str
    article_ref: str | None = None


class CSFMapping(_TolerantModel):
    """NIST CSF subcategory mapping on an SR."""

    id: str
    title: str | None = None


class HSOHighLevel(_TolerantModel):
    """High-level hierarchical security objective for a subdomain."""

    id: str  # e.g. "SO-D-01.1.HL"
    subdomain_id: str | None = None
    is_high_level: bool | None = None
    applies_to: list[str] = Field(default_factory=list)
    derivation_source: str | None = None
    verified_relationship_basis: str | None = None
    emergent_tensions: int | None = None
    objective: str = ""
    considerations: list[str] = Field(default_factory=list)
    anchors: list[str] = Field(default_factory=list)
    csf: list[str] = Field(default_factory=list)
    inherits_from: str | None = None
    source_SR: str | None = None
    activation: str | None = None


class HSOPerReg(_TolerantModel):
    """Per-regulation HSO sub-SO (e.g. SO-D-01.1.GDPR)."""

    id: str
    yaml_id: str | None = None
    regulation: str
    subdomain_id: str | None = None
    applies_to: str | list[str] | None = None  # raw: string "[GDPR]" or list ["GDPR"]
    inherits_from: str | None = None
    source_SR: str | None = None
    activation: str | None = None
    phase_1A_role: str | None = None
    verified_relationship: str | None = None
    objective: str = ""
    considerations: list[str] = Field(default_factory=list)
    anchors: list[str] = Field(default_factory=list)
    csf: list[str] = Field(default_factory=list)


class SubdomainSecurityRequirement(_TolerantModel):
    """One Volere-style SR inside a subdomain (e.g. D-01.1.1.1)."""

    id: str
    sr_short: str | None = None
    title: str = ""
    yaml_body: dict[str, Any] = Field(default_factory=dict)
    anchors: list[str] = Field(default_factory=list)
    csf: list[str] = Field(default_factory=list)
    nist_csf_mapping: list[str] = Field(default_factory=list)


class SubdomainPair(_TolerantModel):
    """Pair embedded in a subdomain JSON (duplicate of files in preproc_out/.../pairs/)."""

    id: str
    subdomain_id: str | None = None
    pair: str | None = None
    reg_a: str
    reg_b: str
    classification: str | None = None
    verified_relationship: str = ""  # FROZEN — never modify
    layer2_flag: bool | None = None
    scope_overlap: str | None = None
    scope_disjoint_test: str | None = None
    downstream_implication: str = ""
    verbatim_articles: dict[str, Any] = Field(default_factory=dict)
    source_subdomain: str | None = None


class Subdomain(_TolerantModel):
    """One sub-domain (e.g. D-01.1 Data at Rest Encryption).

    38 total. CORR-030 invariant: must be exactly 38.
    """

    id: str  # "D-01.1"
    domain_id: str | None = None  # "D-01"
    title: str = ""
    status: str | None = None
    chain_version: str | None = None
    participating_regulations: list[str] = Field(default_factory=list)
    hso_hl: HSOHighLevel | None = None
    hso_per_reg: list[HSOPerReg] = Field(default_factory=list)
    pairs: list[SubdomainPair] = Field(default_factory=list)
    security_requirements: list[SubdomainSecurityRequirement] = Field(default_factory=list)
    csf_hint: list[str] = Field(default_factory=list)
    sections: dict[str, Any] = Field(default_factory=dict)
    warnings: list[Any] = Field(default_factory=list)
    orphan_sr_justifications: dict[str, Any] = Field(default_factory=dict)
    orphan_so_justifications: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None  # provenance path
    doc_id: str | None = None
    schema_version: str | None = None


class SR(_TolerantModel):
    """Security Requirement (e.g. SR-GDPR-001). 282 total. CORR-030 invariant."""

    id: str
    regulation: str
    title: str | None = None
    heading_under: str | None = None
    source_clauses: list[SourceClauseRef] = Field(default_factory=list)
    linked_objectives: list[str] = Field(default_factory=list)
    sub_domain: list[str] = Field(default_factory=list)
    nist_csf_mapping: list[CSFMapping] = Field(default_factory=list)
    applies_to_role: list[str] = Field(default_factory=list)
    obligation_type: list[str] = Field(default_factory=list)
    regulatory_rationale: str = ""
    security_rationale: str | None = None
    ambiguity_notes: str | None = None


class SO(_TolerantModel):
    """Security Objective (e.g. SO-GDPR-001). 338 total."""

    id: str
    regulation: str
    description: str = ""
    source_clauses: list[SourceClauseRef] = Field(default_factory=list)
    sub_domains: list[str] = Field(default_factory=list)
    is_cross_ref: bool = False


class CSFSubcat(_TolerantModel):
    """NIST CSF 2.0 subcategory (e.g. PR.DS-01). 185 total (106 active + 79 withdrawn/archived)."""

    id: str  # "PR.DS-01"
    function: str | None = None  # "PR"
    function_name: str | None = None  # "Protect"
    category_id: str | None = None  # "PR.DS"
    category_name: str | None = None  # "Data Security"
    category_full_text: str | None = None
    number: str | None = None  # "01"
    title: str = ""
    withdrawn: bool = False
    withdrawal_note: str | None = None
    implementation_examples: list[dict[str, Any]] = Field(default_factory=list)
    informative_references: list[dict[str, Any]] = Field(default_factory=list)
    reference_families: list[str] = Field(default_factory=list)
    source_locus: dict[str, Any] = Field(default_factory=dict)
    schema_version: str | None = None
    kind: str | None = None


class Clause(_TolerantModel):
    """Regulatory clause (e.g. GDPR-CL01). 578 total. DORA may have `-{M}` suffix."""

    id: str  # "GDPR-CL01" or "DORA-CL17-1"
    regulation: str
    article: str | None = None
    title: str = ""
    text: str = ""
    # ... other fields tolerated via extra="allow"


class Pair(_TolerantModel):
    """Cross-regulation pair (e.g. D-01.1_GDPR-CRA). 196 total. FROZEN classification."""

    id: str
    subdomain_id: str | None = None
    pair: str | None = None
    reg_a: str
    reg_b: str
    classification: str | None = None
    verified_relationship: str = ""  # FROZEN — never modify by loader
    layer2_flag: bool | None = None
    scope_overlap: str | None = None
    scope_disjoint_test: str | None = None
    downstream_implication: str = ""
    verbatim_articles: dict[str, Any] = Field(default_factory=dict)
    source_subdomain: str | None = None


class AuditReport(_TolerantModel):
    """Aggregated gate reports from preproc_out/4-reference_and_meta/audit/.

    `both_pass` is True iff:
      - csf_mapping_report shows `BROKEN == 0` in `summary.verdict_counts`
      - so_sr_coherence_report shows `so_without_sr == 0` and `sr_without_so == 0`
    """

    csf_mapping: dict[str, Any] = Field(default_factory=dict)
    so_sr_coherence: dict[str, Any] = Field(default_factory=dict)
    both_pass: bool = False

    csf_broken_count: int = 0
    csf_verdict_counts: dict[str, int] = Field(default_factory=dict)
    so_without_sr: int = 0
    sr_without_so: int = 0
    coverage_full: int = 0
    coverage_partial: int = 0
    coverage_unresolved: int = 0


class EntitiesIndex(_TolerantModel):
    """Pre-computed lookup tables from preproc_out/4-reference_and_meta/index/.

    Note: by_subdomain/by_regulation schemas vary across preproc versions —
    some have `list[str]` values, others have nested dicts (e.g. {"self": [...],
    "so_per_reg": [...], "sr": [...]}). We type them as `dict[str, Any]` to
    tolerate both. Consumers should use EntitiesIndex.entities["by_id"] for
    detailed lookups instead.
    """

    entities: dict[str, Any] = Field(default_factory=dict)  # raw entities.json
    by_regulation: dict[str, Any] = Field(default_factory=dict)
    by_subdomain: dict[str, Any] = Field(default_factory=dict)
    cross_references: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class PreprocCatalogLoader:
    """Typed loader for preproc_out/. Caches in-memory; immutable to callers.

    Thread-safety: lru_cache is thread-safe in CPython. The loader itself
    is stateless after construction. Safe to share across threads.
    """

    def __init__(self, preproc_root: Path | str = "preproc_out") -> None:
        self.preproc_root = Path(preproc_root).resolve()
        if not self.preproc_root.exists():
            raise FileNotFoundError(
                f"preproc_root does not exist: {self.preproc_root}. "
                "Run `python -m scripts.preprocess build` first."
            )
        # Layout — resolved at construction so tests can override
        self.entities_root = self.preproc_root / "3-entities"
        self.reference_root = self.preproc_root / "4-reference_and_meta"
        self._subdomains_dir = self.entities_root / "subdomains"
        self._srs_dir = self.entities_root / "srs"
        self._sos_dir = self.entities_root / "sos"
        self._csfs_dir = self.entities_root / "csfs"
        self._clauses_dir = self.entities_root / "clauses" / "_root"
        self._pairs_dir = self.entities_root / "pairs"
        self._audit_dir = self.reference_root / "audit"
        self._index_dir = self.reference_root / "index"
        logger.debug("PreprocCatalogLoader(root=%s)", self.preproc_root)

    # -- internal helpers -------------------------------------------------

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object in {path}, got {type(data).__name__}")
        return data

    @staticmethod
    def _list_json_files(directory: Path, skip_subdirs: tuple[str, ...] = ()) -> list[Path]:
        if not directory.exists():
            return []
        out: list[Path] = []
        for path in sorted(directory.rglob("*.json")):
            if any(part in skip_subdirs for part in path.parts):
                continue
            out.append(path)
        return out

    # -- bulk loaders -----------------------------------------------------

    @functools_cache  # noqa: B019
    def load_subdomains(self) -> list[Subdomain]:
        """Load all 38 subdomains from 3-entities/subdomains/D-{XX}/D-{XX.Y}.json."""
        files = self._list_json_files(self._subdomains_dir)
        out: list[Subdomain] = []
        for path in files:
            try:
                out.append(Subdomain.model_validate(self._read_json(path)))
            except Exception as e:
                logger.warning("Skipping malformed subdomain %s: %s", path, e)
        return out

    @functools_cache  # noqa: B019
    def load_srs(
        self,
        *,
        sub_domain: str | None = None,
        regulation: str | None = None,
    ) -> list[SR]:
        """Load SRs. Optional filters:
        - sub_domain: keep only SRs whose `sub_domain` contains this id (e.g. "D-01.1")
        - regulation: keep only SRs whose `regulation` matches (e.g. "GDPR")
        """
        files = self._list_json_files(self._srs_dir)
        out: list[SR] = []
        for path in files:
            try:
                raw = self._read_json(path)
                sr = SR.model_validate(raw)
            except Exception as e:
                logger.warning("Skipping malformed SR %s: %s", path, e)
                continue
            if sub_domain is not None and sub_domain not in sr.sub_domain:
                continue
            if regulation is not None and sr.regulation != regulation:
                continue
            out.append(sr)
        return out

    @functools_cache  # noqa: B019
    def load_sos(
        self,
        *,
        sub_domain: str | None = None,
        regulation: str | None = None,
    ) -> list[SO]:
        """Load SOs. Optional filters on `sub_domains` (note plural) or `regulation`."""
        files = self._list_json_files(self._sos_dir)
        out: list[SO] = []
        for path in files:
            try:
                raw = self._read_json(path)
                so = SO.model_validate(raw)
            except Exception as e:
                logger.warning("Skipping malformed SO %s: %s", path, e)
                continue
            if sub_domain is not None and sub_domain not in so.sub_domains:
                continue
            if regulation is not None and so.regulation != regulation:
                continue
            out.append(so)
        return out

    @functools_cache  # noqa: B019
    def load_csfs(self) -> list[CSFSubcat]:
        """Load all 106 ACTIVE CSF subcategories. Withdrawn/archived are not on disk."""
        files = self._list_json_files(self._csfs_dir, skip_subdirs=("_meta",))
        out: list[CSFSubcat] = []
        for path in files:
            try:
                out.append(CSFSubcat.model_validate(self._read_json(path)))
            except Exception as e:
                logger.warning("Skipping malformed CSF %s: %s", path, e)
        return out

    @functools_cache  # noqa: B019
    def load_clauses(self, *, regulation: str | None = None) -> list[Clause]:
        """Load all 498 clauses from 3-entities/clauses/_root/{REG}/{REG}_CLnn.json.

        DORA may have `-{M}` suffix in filenames; the loader tolerates both forms.
        """
        files = self._list_json_files(self._clauses_dir)
        out: list[Clause] = []
        for path in files:
            try:
                raw = self._read_json(path)
                clause = Clause.model_validate(raw)
            except Exception as e:
                logger.warning("Skipping malformed clause %s: %s", path, e)
                continue
            if regulation is not None and clause.regulation != regulation:
                continue
            out.append(clause)
        return out

    @functools_cache  # noqa: B019
    def load_pairs(
        self,
        *,
        sub_domain: str | None = None,
    ) -> list[Pair]:
        """Load all 196 pairs from 3-entities/pairs/D-{XX}/D-{XX.Y}_{A}-{B}.json."""
        files = self._list_json_files(self._pairs_dir)
        out: list[Pair] = []
        for path in files:
            try:
                raw = self._read_json(path)
                pair = Pair.model_validate(raw)
            except Exception as e:
                logger.warning("Skipping malformed pair %s: %s", path, e)
                continue
            if sub_domain is not None and pair.subdomain_id != sub_domain:
                continue
            out.append(pair)
        return out

    @functools_cache  # noqa: B019
    def load_audit(self) -> AuditReport:
        """Aggregate audit gate reports. both_pass iff both gates pass.

        Sources:
          - 4-reference_and_meta/audit/csf_mapping_report.json
          - 4-reference_and_meta/audit/so_sr_coherence_report.json
        """
        csf_path = self._audit_dir / "csf_mapping_report.json"
        so_sr_path = self._audit_dir / "so_sr_coherence_report.json"
        csf_raw = self._read_json(csf_path) if csf_path.exists() else {}
        so_sr_raw = self._read_json(so_sr_path) if so_sr_path.exists() else {}

        # csf_mapping schema: {summary: {verdict_counts: {OK, SPARSE, BROKEN, ...}}, ...}
        csf_verdicts = csf_raw.get("summary", {}).get("verdict_counts", {}) if csf_raw else {}
        csf_broken = int(csf_verdicts.get("BROKEN", 0) or 0)

        # so_sr_coherence schema (CORR-035 v1.1):
        #   {
        #     totals: {subdomains, srs_total, so_entries, coverage_full, ...},
        #     so_without_sr: {count, items, justified_count, justified_items},
        #     sr_without_so: {count, items, justified_count, justified_items},
        #     coverage_partial: {count, by_pattern, items},
        #     coverage_unresolved: {count, items, distinct_unresolved, distinct_count},
        #   }
        so_sr_totals = so_sr_raw.get("totals", {}) if so_sr_raw else {}

        def _count(field: str, default: int = 0) -> int:
            """Read `count` from a {count: N, ...} dict, with int fallback."""
            value = so_sr_raw.get(field, default)
            if isinstance(value, dict):
                return int(value.get("count", default) or 0)
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        so_without_sr = _count("so_without_sr")
        sr_without_so = _count("sr_without_so")
        coverage_partial_count = _count("coverage_partial")
        coverage_unresolved_count = _count("coverage_unresolved")

        return AuditReport(
            csf_mapping=csf_raw,
            so_sr_coherence=so_sr_raw,
            csf_broken_count=csf_broken,
            csf_verdict_counts=csf_verdicts,
            so_without_sr=so_without_sr,
            sr_without_so=sr_without_so,
            coverage_full=int(so_sr_totals.get("coverage_full", 0) or 0),
            coverage_partial=coverage_partial_count,
            coverage_unresolved=coverage_unresolved_count,
            both_pass=(csf_broken == 0 and so_without_sr == 0 and sr_without_so == 0),
        )

    @functools_cache  # noqa: B019
    def load_index(self) -> EntitiesIndex:
        """Load pre-computed lookup tables from 4-reference_and_meta/index/."""
        entities_path = self._index_dir / "entities.json"
        by_reg_path = self._index_dir / "by_regulation.json"
        by_sub_path = self._index_dir / "by_subdomain.json"
        xref_path = self._index_dir / "cross_references.json"

        entities_raw = self._read_json(entities_path) if entities_path.exists() else {}
        by_reg_raw = self._read_json(by_reg_path) if by_reg_path.exists() else {}
        by_sub_raw = self._read_json(by_sub_path) if by_sub_path.exists() else {}
        xref_raw: list[dict[str, Any]] = []
        if xref_path.exists():
            data = self._read_json(xref_path)
            xref_raw = data if isinstance(data, list) else list(data.get("items", []))

        return EntitiesIndex(
            entities=entities_raw,
            by_regulation=by_reg_raw.get("by_regulation", by_reg_raw) or {},
            by_subdomain=by_sub_raw.get("by_subdomain", by_sub_raw) or {},
            cross_references=xref_raw,
        )

    # -- cache management (for tests) -------------------------------------

    def clear_cache(self) -> None:
        """Clear all lru_caches (for test isolation / rebuild)."""
        self.load_subdomains.cache_clear()  # type: ignore[attr-defined]
        self.load_srs.cache_clear()  # type: ignore[attr-defined]
        self.load_sos.cache_clear()  # type: ignore[attr-defined]
        self.load_csfs.cache_clear()  # type: ignore[attr-defined]
        self.load_clauses.cache_clear()  # type: ignore[attr-defined]
        self.load_pairs.cache_clear()  # type: ignore[attr-defined]
        self.load_audit.cache_clear()  # type: ignore[attr-defined]
        self.load_index.cache_clear()  # type: ignore[attr-defined]


__all__ = [
    "SO",
    "SR",
    "AuditReport",
    "CSFMapping",
    "CSFSubcat",
    "Clause",
    "EntitiesIndex",
    "HSOHighLevel",
    "HSOPerReg",
    "Pair",
    "PreprocCatalogLoader",
    "SourceClauseRef",
    "Subdomain",
    "SubdomainPair",
    "SubdomainSecurityRequirement",
]
