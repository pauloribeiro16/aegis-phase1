"""inputs — Assemble all MAP-stage per-domain inputs in one structured dict.

This is the single entry point used by ``render_prompt`` to feed an LLM
the full context it needs to produce a per-domain adaptation of Regulatory Baseline
HSOs. The function is intentionally pure and stateless: it consumes a
``V2State`` and a ``domain_id`` and returns a dict whose keys mirror the
schema declared in ``prompts/MAP-DOMAIN-ADAPT.md``.

Public API:
    assemble_inputs(state, domain_id) -> dict[str, Any]

References:
    - contracts/SPRINT002_003_map_reduce_output.md
    - prompts/MAP-DOMAIN-ADAPT.md (input schema)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from aegis_phase1.prompts_v2.track_b import TrackB
from aegis_phase1.v2.domain.filters import (
    filter_cross_reg,
    filter_implementations,
    filter_regs,
    filter_subdomains,
)
from aegis_phase1.v2.state import CompanyContext, V2State

logger = logging.getLogger(__name__)

# Default priority used by TrackB when sub-domain section2_hso doesn't
# expose one. The proportionality_model.md expects MUST/SHOULD/COULD;
# Regulatory Baseline sub-domains in this project do not yet carry priority fields,
# so MUST is the safe default for adaptation (deferral is a later step).
_DEFAULT_PRIORITY = "MUST"

# Map of human-readable scale strings (used in TinyTask and similar
# case data) to the canonical TrackB scale enum. TrackB only accepts
# MICRO | SMALL | MEDIUM | LARGE | MAX; everything else is normalised
# before being passed to ``TrackB.assign_tier``. The fallback is
# computed deterministically from employee count when the textual
# label is unknown.
_SCALE_NORMALISATION: dict[str, str] = {
    "micro": "MICRO",
    "micro-enterprise": "MICRO",
    "small": "SMALL",
    "sme": "SMALL",
    "medium": "MEDIUM",
    "mid-market": "MEDIUM",
    "large": "LARGE",
    "enterprise": "LARGE",
    "max": "MAX",
    "very large": "MAX",
}


def assemble_inputs(state: V2State, domain_id: str) -> dict[str, Any]:
    """Assemble all filtered inputs for one domain's LLM call.

    Orchestrates the 6 filter functions from
    :mod:`aegis_phase1.v2.domain.filters` plus a compact
    ``company_context`` projection and a TrackB suggestion into a
    single dict that matches the schema declared in
    ``prompts/MAP-DOMAIN-ADAPT.md``.

    Args:
        state: Pipeline ``V2State``. Must have ``company_context``
            populated (otherwise ``ValueError`` is raised).
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        Dict with keys:
            - ``case_id`` (str): ``state["case_path"]`` basename.
            - ``domain_id`` (str): the input ``domain_id``.
            - ``company_context`` (dict): compact projection of the
              ``CompanyContext`` (name/scale/employees/fte/tech/applicable_regs).
            - ``subdomains`` (list[dict]): from ``filter_subdomains``.
            - ``applicable_regs`` (list[str]): from ``filter_regs``.
            - ``applicable_articles`` (list[dict]): empty post-T4
              (replaced by preproc catalog clause data in future contracts).
            - ``ambiguities`` (list[dict]): empty post-T4 (replaced by
              preproc_catalog.load_pairs() for cross-regulation analysis).
            - ``cross_reg_analysis`` (list[dict]): from ``filter_cross_reg``.
            - ``existing_implementations`` (list[dict]): from
              ``filter_implementations``.
            - ``track_b_suggestion`` (dict): ``{tier, rationale, attrs}``
              computed by ``TrackB.assign_tier``.

    Raises:
        ValueError: if ``domain_id`` is empty or ``state["company_context"]``
            is missing.
    """
    if not domain_id or not domain_id.strip():
        raise ValueError("domain_id must be a non-empty string")

    ctx = state.get("company_context")
    if ctx is None:
        raise ValueError(
            "state['company_context'] is None — call orchestrator.load() before assemble_inputs()"
        )

    domain_id = domain_id.strip().upper()

    subdomains = filter_subdomains(state, domain_id)
    applicable_regs = filter_regs(state, domain_id)
    # CORR-103: populate applicable_articles + ambiguities from preproc.
    # Pre-CORR-103 these were hard-coded empty lists (post-T4 TODO);
    # P1C-LLM-01 needs clause-level info to do ambiguity analysis. We
    # now read from preproc_catalog (load_clauses + the preloaded
    # v2_pairs) and fall back to [] when the catalog is unavailable.
    applicable_articles: list[dict] = []
    ambiguities: list[dict] = []
    subdomain_ids_for_domain = [s.get("id") for s in subdomains if isinstance(s, dict) and s.get("id")]
    try:
        preproc = state.get("v2_preproc_catalog_ref")
        if preproc is not None and subdomain_ids_for_domain:
            # Articles: load clauses, filter by regulation ∩ applicable_regs.
            all_clauses = preproc.load_clauses()
            if isinstance(all_clauses, list) and applicable_regs:
                seen_clause_ids: set[str] = set()
                for clause in all_clauses:
                    cid = (
                        getattr(clause, "id", None)
                        if not isinstance(clause, dict)
                        else clause.get("id")
                    )
                    if not cid or cid in seen_clause_ids:
                        continue
                    creg = (
                        getattr(clause, "regulation", None)
                        if not isinstance(clause, dict)
                        else clause.get("regulation")
                    )
                    if creg in applicable_regs:
                        if hasattr(clause, "model_dump"):
                            applicable_articles.append(clause.model_dump())
                        elif isinstance(clause, dict):
                            applicable_articles.append(dict(clause))
                        seen_clause_ids.add(cid)
            # Ambiguities: pairs from state (already preloaded by orchestrator).
            all_pairs = list(state.get("v2_pairs", []) or [])
            if all_pairs:
                subdomain_set = set(subdomain_ids_for_domain)
                for pair in all_pairs:
                    if hasattr(pair, "model_dump"):
                        p = pair.model_dump()
                    elif isinstance(pair, dict):
                        p = dict(pair)
                    else:
                        continue
                    if p.get("subdomain_id") in subdomain_set:
                        ambiguities.append(p)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "CORR-103: failed to populate applicable_articles/ambiguities "
            "(falling back to empty): %s",
            exc,
        )
        applicable_articles = []
        ambiguities = []
    cross_reg_analysis = filter_cross_reg(state, domain_id)
    existing_implementations = filter_implementations(state, domain_id)

    track_b_suggestion = _build_track_b_suggestion(ctx, subdomains, existing_implementations)

    inputs: dict[str, Any] = {
        "case_id": _case_id(state),
        "domain_id": domain_id,
        "company_context": _project_company_context(ctx),
        "subdomains": subdomains,
        "applicable_regs": applicable_regs,
        "applicable_articles": applicable_articles,
        "ambiguities": ambiguities,
        "cross_reg_analysis": cross_reg_analysis,
        "existing_implementations": existing_implementations,
        "track_b_suggestion": track_b_suggestion,
    }

    # CORR-112 F2: closed ID anchors for the lane. The LLM must cite
    # ONLY IDs from these lists; anything else is a violation caught by
    # the ref gate (prompts_v2/ref_gate.py). Built from the same
    # filtered data the prompt already carries — zero new loaders.
    # CORR-OBJ-01: include case asset IDs (SYS-*, STORE-*, FLOW-*) so
    # the per-section citation gate can catch invented architecture
    # references. Loaded fresh per-domain (no orchestrator state
    # mutation) — see _load_case_assets().
    article_id_set = sorted({
        a.get("id") for a in applicable_articles
        if isinstance(a, dict) and a.get("id")
    })
    case_assets_all = _load_case_assets(state)
    case_assets_filtered = _filter_assets_for_domain(
        case_assets_all, domain_id, subdomains
    )
    inputs["authoritative_ids"] = {
        "subdomain_ids": list(subdomain_ids_for_domain),
        "regulation_ids": list(applicable_regs),
        "article_ids": article_id_set,
        "asset_ids": {
            "systems": list(case_assets_filtered.get("systems") or []),
            "data_stores": list(case_assets_filtered.get("data_stores") or []),
            "data_flows": list(case_assets_filtered.get("data_flows") or []),
        },
        "note": (
            "CLOSED LIST: cite only these IDs (subdomain/regulation/"
            "article AND SYS-*/STORE-*/FLOW-* asset IDs). Any identifier "
            "not present here is a violation."
        ),
    }

    # CORR-101 Gap 2: when a ManifestLoader was injected into the
    # orchestrator, add a top-level ``manifest_summary`` block to the
    # inputs dict. The summary aggregates the per-subdomain ai_act
    # states + the per-regulation NIST control sets for this domain.
    # Gracefully skipped when the loader was not injected (back-compat).
    manifest_loader = state.get("manifest_loader_ref")
    if manifest_loader is not None:
        inputs["manifest_summary"] = _build_manifest_summary(
            manifest_loader=manifest_loader,
            domain_id=domain_id,
            applicable_regs=applicable_regs,
        )

    logger.debug(
        "assemble_inputs(%s): subs=%d regs=%d cr=%d impls=%d articles=%d ambiguities=%d",
        domain_id,
        len(subdomains),
        len(applicable_regs),
        len(cross_reg_analysis),
        len(existing_implementations),
        len(applicable_articles),
        len(ambiguities),
    )
    return inputs


# ─── Internal helpers ─────────────────────────────────────────────────


def _case_id(state: V2State) -> str:
    """Return the basename of ``state['case_path']`` (or empty string)."""
    case_path = state.get("case_path") or ""
    if not case_path:
        return ""
    return Path(case_path).name


# ─── Case asset loading (CORR-OBJ-01) ─────────────────────────────────


# Top-level key aliases for the case architecture YAMLs. Case 1 uses the
# short forms ("systems", "stores", "flows"); case 2+ use the explicit
# forms ("systems", "data_stores", "data_flows"). Mirror the convention
# in CaseProfileLoader._read_yaml_list_multi.
_ASSET_KEY_ALIASES: dict[str, list[str]] = {
    "systems": ["systems"],
    "data_stores": ["data_stores", "stores"],
    "data_flows": ["data_flows", "flows"],
}


def _read_yaml_list_safe(path: Path, key_aliases: list[str]) -> list[dict[str, Any]]:
    """Read a list[dict] from a YAML file under one of several root keys.

    Tolerant of missing files (returns []) and parse errors (logs WARNING
    and returns []). Used by :func:`_load_case_assets` to read the three
    case architecture inventories without ever raising.
    """
    if not path.exists():
        logger.debug("_read_yaml_list_safe: missing %s; returning []", path)
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception as exc:
        logger.warning(
            "_read_yaml_list_safe: failed to parse %s: %s; returning []",
            path, exc,
        )
        return []
    if not isinstance(raw, dict):
        logger.warning(
            "_read_yaml_list_safe: top-level YAML at %s is not a dict (got %s); returning []",
            path, type(raw).__name__,
        )
        return []
    for alias in key_aliases:
        if alias in raw and isinstance(raw[alias], list):
            return [item for item in raw[alias] if isinstance(item, dict)]
    logger.debug(
        "_read_yaml_list_safe: none of aliases %s found in %s; returning []",
        key_aliases, path,
    )
    return []


def _load_case_assets(state: V2State) -> dict[str, list[dict[str, Any]]]:
    """Load all case architecture assets (SYS-*/STORE-*/FLOW-*) from disk.

    CORR-OBJ-01: previously the MAP context only carried ``subdomain_ids``,
    ``regulation_ids`` and ``article_ids`` to the LLM. SYS-*/STORE-*/FLOW-*
    were never anchored, so the LLM could invent (or drop) them freely.
    This loader reads the three architecture YAMLs once per call and
    returns a dict shaped like::

        {
            "systems":     [ {id, name, type, ...}, ... ],
            "data_stores": [ {id, name, type, ...}, ... ],
            "data_flows":  [ {id, name, source, ...}, ... ],
        }

    Files that don't exist or fail to parse return an empty list for
    that category (no exception propagates). The loader is pure: it
    reads from ``state['case_path']/input/architecture/`` and does not
    mutate state.

    Args:
        state: Pipeline ``V2State`` carrying ``case_path``.

    Returns:
        Dict with keys ``systems``, ``data_stores``, ``data_flows``;
        each value is a list of dicts (possibly empty).
    """
    case_path = state.get("case_path") or ""
    if not case_path:
        return {"systems": [], "data_stores": [], "data_flows": []}
    arch_dir = Path(case_path) / "input" / "architecture"
    if not arch_dir.is_dir():
        logger.debug(
            "_load_case_assets: %s is not a directory; returning empty",
            arch_dir,
        )
        return {"systems": [], "data_stores": [], "data_flows": []}
    return {
        "systems": _read_yaml_list_safe(
            arch_dir / "systems.yaml", _ASSET_KEY_ALIASES["systems"],
        ),
        "data_stores": _read_yaml_list_safe(
            arch_dir / "data_stores.yaml", _ASSET_KEY_ALIASES["data_stores"],
        ),
        "data_flows": _read_yaml_list_safe(
            arch_dir / "data_flows.yaml", _ASSET_KEY_ALIASES["data_flows"],
        ),
    }


def _filter_assets_for_domain(
    assets: dict[str, list[dict[str, Any]]],
    domain_id: str,
    subdomains: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Heuristically filter the case asset list to those likely relevant to a domain.

    Heuristic v1 (CORR-OBJ-01): case-insensitive substring match between
    each asset's text fields (name + type + notes-like fields) and the
    keywords harvested from the domain's subdomain IDs (the numeric
    part — e.g. for D-01.1 the keyword is "01" and "1") plus the
    subdomain names if present.

    See ``data/asset_filter_rules.yaml`` (future) for a versioned,
    rules-based replacement. Until that file exists, this is a
    conservative, deterministic v1: any asset with no field that
    substring-matches a domain keyword is dropped. If no keywords can
    be derived (empty subdomains / no numeric content), the function
    falls back to returning ALL asset IDs — which is safer than
    returning nothing.

    Args:
        assets: Dict as returned by :func:`_load_case_assets`.
        domain_id: Domain identifier (e.g. ``"D-01"``).
        subdomains: List of subdomain dicts for this domain (each may
            carry an ``id`` and ``name`` field).

    Returns:
        Dict with the same shape as ``assets`` but each value is a
        sorted list of asset IDs (strings) only.
    """
    keywords = _domain_keywords(domain_id, subdomains)
    out: dict[str, list[str]] = {"systems": [], "data_stores": [], "data_flows": []}
    if not keywords:
        # No keywords → can't filter safely; return all IDs.
        for category, items in assets.items():
            out[category] = sorted(
                str(item.get("id")) for item in items
                if isinstance(item, dict) and item.get("id")
            )
        return out
    for category, items in assets.items():
        for item in items:
            if not isinstance(item, dict):
                continue
            aid = item.get("id")
            if not aid:
                continue
            haystack = " ".join(
                str(v) for v in item.values() if v is not None
            ).lower()
            if any(kw in haystack for kw in keywords):
                out[category].append(str(aid))
    for k in out:
        out[k] = sorted(out[k])
    return out


def _domain_keywords(domain_id: str, subdomains: list[dict[str, Any]]) -> list[str]:
    """Derive substring keywords for the asset filter.

    For ``D-XX.Y`` → return both ``"XX"`` and ``"Y"`` plus any
    subdomain ``name`` fields (lower-cased). The heuristic is
    intentionally generous: a few extra matches are preferable to
    dropping a real reference, because the per-section gate will
    only flag *missing* IDs, not extra ones.
    """
    keywords: list[str] = []
    # Pull numeric tokens out of the domain ID.
    digits = "".join(ch for ch in domain_id if ch.isdigit())
    if digits:
        # Both "01" and "1" so a YAML field containing either matches.
        keywords.append(digits)
        if len(digits) > 1 and digits.startswith("0"):
            keywords.append(digits.lstrip("0") or "0")
    for sub in subdomains:
        if not isinstance(sub, dict):
            continue
        name = sub.get("name") or sub.get("title") or ""
        if isinstance(name, str) and name.strip():
            keywords.append(name.strip().lower())
    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for kw in keywords:
        kwl = kw.lower() if not kw.isdigit() else kw
        if kwl and kwl not in seen:
            seen.add(kwl)
            deduped.append(kwl)
    return deduped


def _build_manifest_summary(
    *,
    manifest_loader: Any,
    domain_id: str,
    applicable_regs: list[str],
) -> dict[str, Any]:
    """Build the ``manifest_summary`` block for the per-domain inputs.

    Reads the per-domain ``D-XX.manifest.json`` via the injected
    ``manifest_loader`` (CORR-101 Gap 2). Aggregates:

      * ``ai_act_present_count`` / ``_partial_count`` / ``_absent_count``
        — tallies of subdomains in this domain by ai_act state.
      * ``nist_controls_by_reg`` — dict ``{reg: [list of NIST ids]}``
        for every reg in ``applicable_regs``. When the reg has no
        NIST controls in the domain, the value is ``[]``.

    Args:
        manifest_loader: A ``ManifestLoader`` instance.
        domain_id: Domain identifier (e.g. ``"D-01"``).
        applicable_regs: The company-level regulations applicable to
            this domain (from :func:`filter_regs`).

    Returns:
        Dict suitable for inclusion in the per-domain inputs under
        the key ``"manifest_summary"``. The shape is documented in
        CORR-101 §Gap 2 §3.
    """
    manifest = manifest_loader.manifest_for_domain(domain_id)
    summary: dict[str, Any] = {
        "domain_id": domain_id,
        "ai_act_present_count": 0,
        "ai_act_partial_count": 0,
        "ai_act_absent_count": 0,
        "nist_controls_by_reg": {},
    }
    for s in manifest.subdomain_summaries:
        state = (s.ai_act or "").strip().lower()
        if state == "present":
            summary["ai_act_present_count"] += 1
        elif state == "partial":
            summary["ai_act_partial_count"] += 1
        else:
            summary["ai_act_absent_count"] += 1
    for reg in applicable_regs:
        summary["nist_controls_by_reg"][reg] = manifest_loader.nist_controls_for_reg_in_domain(
            domain_id, reg
        )
    return summary


def _project_company_context(ctx: Any) -> dict[str, Any]:
    """Project the company context to the 7+ fields the prompt needs.

    CORR-042 inline fix: ctx may be a Pydantic CompanyContext or a
    dict (v1-compat shim). Handle both.

    CORR-048: extend with the 4 new fields from CORR-047
    (implementation_readiness, regulatory_classification,
    role_matrix, regulatory_interactions) when present in the
    CompanyProfile. Backward-compat: if the 4 fields are not
    available (legacy v1 state, or older case inputs that lack the
    new YAMLs), return the original 8-field shape without error.
    """
    if isinstance(ctx, dict):
        # v1-compat shim path (8 fields)
        base = {
            "company_name": ctx.get("company_name") or ctx.get("name") or "",
            "scale": ctx.get("scale") or ctx.get("complexity_tier") or "LOW",
            "sector": ctx.get("sector") or "",
            "employees": ctx.get("employees") or 0,
            "revenue": ctx.get("revenue") or 0,
            "security_fte": ctx.get("security_fte") or 0.0,
            "tech_stack": list(ctx.get("tech_stack") or []),
            "applicable_regs": list(ctx.get("applicable_regs") or []),
        }
    else:
        # Pydantic CompanyContext path
        base = {
            "company_name": ctx.company_name,
            "scale": ctx.scale,
            "sector": ctx.sector,
            "employees": ctx.employees,
            "revenue": ctx.revenue,
            "security_fte": ctx.security_fte,
            "tech_stack": list(ctx.tech_stack or []),
            "applicable_regs": list(ctx.applicable_regs or []),
        }

    # CORR-048: thread the 4 new fields from CORR-047 if available
    extra = _extract_corr047_fields(ctx)
    if extra:
        base.update(extra)
    return base


def _extract_corr047_fields(ctx: Any) -> dict[str, Any]:
    """CORR-048: extract the 4 CORR-047 fields from any supported shape.

    Tries 3 paths to maximise compatibility with existing callers:

      1. Direct attribute on ctx (Pydantic CompanyContext or
         CompanyProfile wrapper).
      2. v2_company_profile sub-key on dict-shaped state shims.
      3. Direct key on dict-shaped state shims.

    Each non-None value is serialised via model_dump() if it's a
    Pydantic model, or via __dict__ if it's a plain object. Returns
    a dict of serialised fields, or {} if none available.

    Caller must handle backward-compat: if the 4 fields are not
    populated (e.g. case input lacks the YAMLs), the prompt
    consumer will see them as missing — which is the correct
    signal to skip capability/role/interaction sections.
    """
    out: dict[str, Any] = {}
    for field in (
        "implementation_readiness",
        "regulatory_classification",
        "role_matrix",
        "regulatory_interactions",
    ):
        value: Any = None
        # Path 1: direct attribute (Pydantic)
        if hasattr(ctx, field):
            value = getattr(ctx, field)
        # Path 2: v2_company_profile sub-dict on state shim
        if value is None and isinstance(ctx, dict):
            profile = ctx.get("v2_company_profile")
            if profile is not None and hasattr(profile, field):
                value = getattr(profile, field)
        # Path 3: direct dict key
        if value is None and isinstance(ctx, dict):
            value = ctx.get(field)
        if value is None:
            continue
        # Serialise Pydantic model
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        elif hasattr(value, "__dict__") and not isinstance(value, str | int | float | bool | list | dict):
            value = {k: v for k, v in value.__dict__.items() if not k.startswith("_")}
        out[field] = value
    return out


def _build_track_b_suggestion(
    ctx: CompanyContext,
    subdomains: list[dict[str, Any]],
    implementations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute the TrackB tier suggestion for the domain's sub-domains.

    Logic:
        1. Determine inheritability per sub-domain. A sub-domain is
           ``INHERITABLE`` when at least one existing implementation
           covers its id with adequacy ``ADEQUATE``. Otherwise
           ``BUILD_REQUIRED``.
        2. The domain-level inheritability is ``INHERITABLE`` only if
           ALL sub-domains are INHERITABLE; otherwise ``BUILD_REQUIRED``.
        3. Assign a tier per sub-domain via ``TrackB.assign_tier``
           (priority defaults to MUST) and pick the maximum (most
           rigorous) tier as the domain-level suggestion.
        4. Return ``{tier, rationale, attrs}``.

    Args:
        ctx: Company context (uses ``scale`` and ``security_fte``).
        subdomains: List of sub-domain summaries from ``filter_subdomains``.
        implementations: List of existing implementations from
            ``filter_implementations``.

    Returns:
        Dict with ``tier`` (str), ``rationale`` (str) and ``attrs``
        (dict of TrackB tier attributes).
    """
    covered_adeq = _covered_adequacy_index(implementations)

    if not subdomains:
        inheritability = "BUILD_REQUIRED"
        per_sub: list[tuple[str, str]] = []
    else:
        per_sub = []
        for sub in subdomains:
            sid = sub.get("id", "")
            inheritability = "INHERITABLE" if sid in covered_adeq else "BUILD_REQUIRED"
            per_sub.append((sid, inheritability))
        inheritability = (
            "INHERITABLE" if all(i == "INHERITABLE" for _, i in per_sub) else "BUILD_REQUIRED"
        )

    # CORR-042 inline fix: ctx may be dict (v1-compat shim) or Pydantic.
    # Handle both so the legacy MAP path (assemble_inputs) doesn't crash.
    if isinstance(ctx, dict):
        scale_raw = ctx.get("scale") or ctx.get("complexity_tier") or "LOW"
        employees_raw = ctx.get("employees") or 0
        fte_raw = ctx.get("security_fte") or 0.0
    else:
        scale_raw = ctx.scale
        employees_raw = ctx.employees
        fte_raw = ctx.security_fte
    scale_norm = _normalise_scale(scale_raw, employees_raw)
    fte = fte_raw if fte_raw > 0 else 0.0

    track_b = TrackB()
    tiers: list[str] = []
    attrs_by_sub: dict[str, dict[str, Any]] = {}
    for sid, inh in per_sub:
        try:
            tier = track_b.assign_tier(scale_norm, inh, _DEFAULT_PRIORITY, fte=fte)
        except ValueError as exc:
            logger.warning("TrackB.assign_tier failed for %s: %s", sid, exc)
            tier = "STANDARD"
        tiers.append(tier)
        attrs_by_sub[sid] = {
            "inheritability": inh,
            "tier": tier,
            "priority": _DEFAULT_PRIORITY,
        }

    tier_order = {"MINIMAL": 0, "LIGHTWEIGHT": 1, "STANDARD": 2, "RIGOROUS": 3, "DEFERRED": -1}
    if tiers:
        domain_tier = max(tiers, key=lambda t: tier_order.get(t, 0))
    else:
        try:
            domain_tier = track_b.assign_tier(
                scale_norm, inheritability, _DEFAULT_PRIORITY, fte=fte
            )
        except ValueError:
            domain_tier = "STANDARD"

    rationale = _track_b_rationale(inheritability, len(subdomains), covered_adeq, scale_norm)

    return {
        "tier": domain_tier,
        "rationale": rationale,
        "attrs": {
            "inheritability": inheritability,
            "scale": scale_norm,
            # CORR-042 inline fix: ctx may be dict (v1-compat shim)
            "scale_original": ctx.get("scale") if isinstance(ctx, dict) else ctx.scale,
            "priority": _DEFAULT_PRIORITY,
            "by_subdomain": attrs_by_sub,
        },
    }


def _covered_adequacy_index(implementations: list[dict[str, Any]]) -> set[str]:
    """Return the set of sub-domain ids covered ADEQUATELY by an implementation."""
    covered: set[str] = set()
    for impl in implementations:
        if str(impl.get("adequacy", "")).upper() != "ADEQUATE":
            continue
        for sid in impl.get("covers") or []:
            covered.add(str(sid))
    return covered


def _normalise_scale(scale: str | None, employees: int | None = None) -> str:
    """Map a free-text scale label to the canonical TrackB scale enum.

    Order of preference:
        1. Uppercase literal (``MICRO``, ``SMALL`` …) → returned as-is.
        2. Lowercase lookup in :data:`_SCALE_NORMALISATION`.
        3. Fallback by employee count when the label is unknown.

    Returns:
        One of ``MICRO | SMALL | MEDIUM | LARGE | MAX``. Always valid
        for ``TrackB.assign_tier``.
    """
    if scale:
        candidate = scale.strip()
        if candidate.upper() in {"MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"}:
            return candidate.upper()
        norm = _SCALE_NORMALISATION.get(candidate.lower())
        if norm:
            return norm

    n = employees or 0
    if n <= 9:
        return "MICRO"
    if n <= 49:
        return "SMALL"
    if n <= 249:
        return "MEDIUM"
    if n <= 999:
        return "LARGE"
    return "MAX"


def _track_b_rationale(
    inheritability: str,
    subdomain_count: int,
    covered_adeq: set[str],
    scale: str,
) -> str:
    """Build a short human-readable rationale for the TrackB suggestion."""
    if subdomain_count == 0:
        return (
            f"No active sub-domains in this domain; defaulting to "
            f"{inheritability} at scale {scale}."
        )
    if inheritability == "INHERITABLE":
        return (
            f"All {subdomain_count} sub-domain(s) inherit ADEQUATE controls "
            f"({len(covered_adeq)} covered); scale={scale} lowers the tier."
        )
    return (
        f"{subdomain_count} sub-domain(s) at scale {scale}; "
        f"{len(covered_adeq)} adequately covered, the rest require building."
    )


__all__ = [
    "assemble_inputs",
    "_load_case_assets",
    "_filter_assets_for_domain",
]
