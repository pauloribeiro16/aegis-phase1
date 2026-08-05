"""manifest_loader — Typed loader for the Methodology domain manifests.

CORR-101 Gap 2: previously the v2 pipeline read nothing from the
per-domain ``D-XX.manifest.json`` files under
``Methodology-main/00_METHODOLOGY/PREPROCESSING_by_domain/domains/``.
This meant that ``D-01.4`` with ``ai_act: "partial"`` looked
identical to ``D-01.1`` with ``ai_act: "absent"`` in the prompt
context — the LLM never saw the AI Act participation signal.

This loader mirrors the schema documented in
``Methodology-main/00_METHODOLOGY/PREPROCESSING_by_domain/domains/STRUCTURE_REFERENCE.md``
§3 and exposes:

  * ``Manifest``                — full Pydantic model (one domain)
  * ``SubdomainSummary``        — one entry in ``subdomain_summaries``
  * ``Counts``                  — aggregate counts per domain
  * ``ManifestLoader``          — typed, cache-backed reader

Usage::

    from aegis_phase1.v2.loader.manifest_loader import ManifestLoader

    loader = ManifestLoader()  # uses default Methodology-main root
    m = loader.manifest_for_domain("D-01")
    ai_act_d014 = loader.ai_act_for_subdomain("D-01.4")  # "partial"
    nist = loader.nist_controls_for_reg_in_domain("D-01", "GDPR")  # [...]

Missing manifests / missing fields are tolerated with WARNING logs
(returned as safe defaults — empty Manifest / "absent" / empty list).
This keeps the loader usable in production cases that have a partial
manifest corpus while making missing data visible at WARNING level.

Refs:
    - Methodology-main/.../domains/STRUCTURE_REFERENCE.md §3 (schema)
    - CORR-101 Gap 2 (manifest ai_act / nist enrichment)
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# CORR-102: fail-loud exceptions for missing manifest files and
# manifest/preproc drift. Previously these were WARNING logs that
# silently degraded the prompt context.
class ManifestNotFoundError(RuntimeError):
    """Raised when no ``D-XX.manifest.json`` exists for a requested domain.

    Attributes:
        d_id: The requested domain identifier (e.g. ``"D-01"``).
    """

    def __init__(self, d_id: str) -> None:
        self.d_id = d_id
        super().__init__(
            f"CORR-102: no manifest file found for domain {d_id}. "
            "Refusing to silently fall back to empty defaults — regenerate "
            "Methodology-main manifests or fix the domain_id."
        )


class ManifestDriftError(RuntimeError):
    """Raised when a manifest's applicable_regs drifts from preproc.

    Each manifest entry's ``applicable_regs`` must be a subset of the
    preproc catalog's ``Subdomain.participating_regulations`` for the
    same sub-domain. Drift indicates Methodology-main / preproc
    catalogue are out of sync.

    Attributes:
        d_id: The domain identifier.
        drift_records: List of human-readable drift strings, one per
            affected sub-domain.
    """

    def __init__(self, d_id: str, drift_records: list[str]) -> None:
        self.d_id = d_id
        self.drift_records = list(drift_records)
        super().__init__(
            f"CORR-102: manifest/preproc drift for {d_id} "
            f"({len(drift_records)} record(s)): "
            f"{drift_records[:3]}{'...' if len(drift_records) > 3 else ''}. "
            "Reconcile Methodology-main and preproc_out."
        )


# Default root (relative to the repo root). Tests can inject a
# different path via ``ManifestLoader(manifests_root=...)``.
DEFAULT_MANIFESTS_ROOT = Path("Methodology-main/00_METHODOLOGY/PREPROCESSING_by_domain/domains")

# The 3 ai_act states allowed by the schema (see STRUCTURE_REFERENCE.md
# §3: "absent" | "partial" | "present"). Anything else is coerced to
# "absent" with a WARNING log.
VALID_AI_ACT = frozenset({"absent", "partial", "present"})
_DEFAULT_AI_ACT = "absent"


# ---------------------------------------------------------------------------
# Pydantic models — mirror the schema in STRUCTURE_REFERENCE.md §3.
# extra="allow" tolerates fields we don't yet consume (e.g. the verbose
# sub_objectives_by_regulation / sub_requirements_by_regulation maps).
# ---------------------------------------------------------------------------


class _TolerantModel(BaseModel):
    """Base for manifest models — tolerates extra fields and nulls."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


class Counts(_TolerantModel):
    """Aggregate counts per domain (``manifest.counts``)."""

    subdomains: int = 0
    total_cards: int = 0
    applicable_articles_total: int = 0
    applicable_clauses_total: int = 0
    sub_objectives_total: int = 0
    sub_requirements_total: int = 0
    applicable_nist_controls_total: int = 0


class SubdomainSummary(_TolerantModel):
    """One entry in ``manifest.subdomain_summaries[]``.

    Per STRUCTURE_REFERENCE.md §3:
        id: "D-01.1"
        name: "Data at Rest Encryption"
        participants: ["GDPR", "NIS2", "CRA", "DORA"]
        ai_act: "absent" | "partial" | "present"
        applicable_regs: ["CRA", "DORA", "GDPR", "NIS2"]
        total_cards: 46
        applicable_articles: 33
        applicable_clauses: 44
        sub_objectives: 4
        sub_requirements: 4
        applicable_nist_controls: 10
    """

    id: str
    name: str = ""
    participants: list[str] = Field(default_factory=list)
    ai_act: str = _DEFAULT_AI_ACT
    applicable_regs: list[str] = Field(default_factory=list)
    total_cards: int = 0
    applicable_articles: int = 0
    applicable_clauses: int = 0
    sub_objectives: int = 0
    sub_requirements: int = 0
    applicable_nist_controls: int = 0


class Manifest(_TolerantModel):
    """One ``D-XX.manifest.json`` file (one domain).

    Per STRUCTURE_REFERENCE.md §3 schema. The verbose
    ``applicable_articles_by_regulation``,
    ``applicable_clauses_by_regulation``,
    ``sub_objectives_by_regulation``, and
    ``sub_requirements_by_regulation`` maps are tolerated via
    ``extra="allow"`` and exposed as raw dicts when present.
    """

    schema_version: str | None = None
    manifest_type: str | None = None
    domain_id: str
    domain_name: str = ""
    subdomains: list[str] = Field(default_factory=list)
    subdomain_summaries: list[SubdomainSummary] = Field(default_factory=list)
    applicable_articles_by_regulation: dict[str, list[str]] = Field(default_factory=dict)
    applicable_clauses_by_regulation: dict[str, list[str]] = Field(default_factory=dict)
    sub_objectives_by_regulation: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    sub_requirements_by_regulation: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    applicable_nist_controls_by_regulation: dict[str, list[str]] = Field(default_factory=dict)
    counts: Counts = Field(default_factory=Counts)
    generated_at: str | None = None

    @property
    def ai_act_summary(self) -> dict[str, int]:
        """Tally of subdomains by ai_act state (``{"absent": 3, "partial": 1}``)."""
        tally: dict[str, int] = {}
        for s in self.subdomain_summaries:
            state = s.ai_act or _DEFAULT_AI_ACT
            tally[state] = tally.get(state, 0) + 1
        return tally


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class ManifestLoader:
    """Typed, cache-backed loader for per-domain manifest files.

    Reads from ``manifests_root / D-XX_<Name> / D-XX.manifest.json``.
    The 10 manifests are loaded once and cached for the lifetime of
    the loader (use ``clear_cache()`` to force a reload — primarily
    for tests).

    Thread-safety: ``functools.lru_cache`` is thread-safe in CPython.
    The loader is stateless after construction. Safe to share across
    threads.

    Tolerated failure modes (always logged at WARNING, never raised):
        * Missing manifests root directory (returns empty for all).
        * Missing manifest file for a specific domain (returns
          empty ``Manifest(domain_id=...)``).
        * Malformed JSON or schema mismatch (returns empty
          ``Manifest`` + WARNING).
    """

    def __init__(
        self,
        manifests_root: Path | str | None = None,
    ) -> None:
        self.manifests_root = Path(
            manifests_root if manifests_root is not None else DEFAULT_MANIFESTS_ROOT
        ).resolve()
        if not self.manifests_root.exists():
            logger.warning(
                "ManifestLoader: manifests_root %s does not exist; "
                "all manifest reads will return empty defaults",
                self.manifests_root,
            )
        else:
            logger.debug("ManifestLoader(root=%s)", self.manifests_root)

    # -- cache management (for tests) -------------------------------------

    def clear_cache(self) -> None:
        """Clear all lru_caches (for test isolation / rebuild)."""
        self._manifest_for_domain_cached.cache_clear()  # type: ignore[attr-defined]

    # -- public API -------------------------------------------------------

    @lru_cache(maxsize=16)  # noqa: B019 — module-level cache acceptable
    def _manifest_for_domain_cached(self, d_id: str) -> Manifest:
        """Internal cached read. Public API is :meth:`manifest_for_domain`.

        CORR-102: fail-loud. Raises :class:`ManifestNotFoundError`
        when no manifest file exists for ``d_id``. Previously this
        returned an empty ``Manifest`` with a WARNING log, hiding the
        missing data from downstream consumers.
        """
        if not self.manifests_root.exists():
            logger.error(
                "CORR-102: ManifestLoader: manifests_root %s missing — raising",
                self.manifests_root,
            )
            raise ManifestNotFoundError(d_id or "")
        # Find D-XX_<Name> directory that starts with d_id
        for path in sorted(self.manifests_root.iterdir()):
            if not path.is_dir():
                continue
            if not path.name.startswith(d_id + "_"):
                continue
            manifest_path = path / f"{d_id}.manifest.json"
            if not manifest_path.exists():
                logger.error(
                    "CORR-102: directory %s exists but %s is missing — raising",
                    path,
                    manifest_path.name,
                )
                raise ManifestNotFoundError(d_id)
            try:
                raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.error(
                    "CORR-102: failed to read %s: %s — raising",
                    manifest_path,
                    exc,
                )
                raise ManifestNotFoundError(d_id) from exc
            try:
                m = Manifest.model_validate(raw)
            except Exception as exc:
                logger.error(
                    "CORR-102: failed to validate %s: %s — raising",
                    manifest_path,
                    exc,
                )
                raise ManifestNotFoundError(d_id) from exc
            return m
        logger.error(
            "CORR-102: no directory for %s under %s — raising",
            d_id,
            self.manifests_root,
        )
        raise ManifestNotFoundError(d_id)

    def manifest_for_domain(self, d_id: str) -> Manifest:
        """Return the ``Manifest`` for a domain (e.g. ``"D-01"``).

        Args:
            d_id: Domain identifier (e.g. ``"D-01"``, ``"D-10"``).

        Returns:
            Typed ``Manifest``.

        Raises:
            ManifestNotFoundError: CORR-102 fail-loud. Raised when
                the manifest file is missing or malformed (was: empty
                ``Manifest`` + WARNING).
        """
        d_id = (d_id or "").strip()
        return self._manifest_for_domain_cached(d_id)

    def ai_act_for_subdomain(self, sd_id: str) -> str:
        """Return the ``ai_act`` state for a sub-domain (``"D-01.4"``).

        Args:
            sd_id: Sub-domain identifier (e.g. ``"D-01.4"``).

        Returns:
            One of ``"absent" | "partial" | "present"``. Defaults to
            ``"absent"`` (the safest value — never claim AI Act
            participation that isn't on disk).
        """
        sd_id = (sd_id or "").strip()
        if not sd_id or "." not in sd_id:
            return _DEFAULT_AI_ACT
        d_id = sd_id.split(".", 1)[0]
        manifest = self.manifest_for_domain(d_id)
        for s in manifest.subdomain_summaries:
            if s.id == sd_id:
                state = (s.ai_act or "").strip().lower()
                if state in VALID_AI_ACT:
                    return state
                if state:
                    logger.warning(
                        "ManifestLoader: %s has unknown ai_act=%r; " "coercing to %r",
                        sd_id,
                        s.ai_act,
                        _DEFAULT_AI_ACT,
                    )
                return _DEFAULT_AI_ACT
        return _DEFAULT_AI_ACT

    def nist_controls_for_reg_in_domain(self, d_id: str, reg: str) -> list[str]:
        """Return NIST CSF controls applicable to a regulation in a domain.

        Reads ``manifest.applicable_nist_controls_by_regulation[reg]``.
        Returns an empty list when the regulation has no entries or
        the manifest is missing.

        Args:
            d_id: Domain identifier (e.g. ``"D-01"``).
            reg: Regulation short-name (e.g. ``"GDPR"``,
                ``"AI_Act"``).

        Returns:
            Sorted, deduplicated list of NIST CSF control IDs.
        """
        d_id = (d_id or "").strip()
        reg = (reg or "").strip()
        if not d_id or not reg:
            return []
        manifest = self.manifest_for_domain(d_id)
        controls = manifest.applicable_nist_controls_by_regulation.get(reg, [])
        return sorted({str(c) for c in controls if c})

    def cross_check_with_preproc_participating_regs(
        self,
        d_id: str,
        preproc_by_id: dict[str, Any],
    ) -> list[str]:
        """Cross-check a manifest against the preproc catalogue (CORR-102).

        For each ``subdomain_summary`` in the manifest, verify that the
        manifest's ``applicable_regs`` is a subset of the preproc
        catalog's ``Subdomain.participating_regulations`` for the same
        sub-domain. Drift is collected as a list of human-readable
        strings.

        CORR-102: fail-loud. If any drift is detected, this method
        raises :class:`ManifestDriftError` listing the drift records
        (was: WARNING + silent soft-fail).

        Args:
            d_id: Domain identifier (e.g. ``"D-01"``).
            preproc_by_id: Mapping ``subdomain_id -> Subdomain`` (the
                typed ``Subdomain`` from :class:`PreprocCatalogLoader`).

        Returns:
            Empty list when no drift was detected (and does NOT raise).

        Raises:
            ManifestDriftError: When at least one manifest entry drifts.
        """
        from aegis_phase1.v2.domain.filters.regs import _canonical_reg_name

        manifest = self.manifest_for_domain(d_id)
        drift_records: list[str] = []
        for s in manifest.subdomain_summaries:
            preproc_sd = preproc_by_id.get(s.id)
            if preproc_sd is None:
                drift_records.append(f"{s.id}: not in preproc")
                continue
            manifest_canon = {_canonical_reg_name(r) for r in s.applicable_regs if r}
            preproc_canon = {
                _canonical_reg_name(r)
                for r in (getattr(preproc_sd, "participating_regulations", []) or [])
                if r
            }
            missing = manifest_canon - preproc_canon
            if missing:
                drift_records.append(
                    f"{s.id}: manifest.applicable_regs={sorted(manifest_canon)} "
                    f"vs preproc.participating_regulations={sorted(preproc_canon)} "
                    f"missing={sorted(missing)}"
                )
        if drift_records:
            raise ManifestDriftError(d_id, drift_records)
        return []


def _empty_manifest(d_id: str) -> Manifest:
    """Return an empty Manifest for ``d_id`` (used on missing/malformed)."""
    return Manifest(domain_id=d_id or "", domain_name="")


__all__ = [
    "DEFAULT_MANIFESTS_ROOT",
    "Counts",
    "Manifest",
    "ManifestDriftError",
    "ManifestLoader",
    "ManifestNotFoundError",
    "SubdomainSummary",
]
