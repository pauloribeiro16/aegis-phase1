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
    # CORR-037-T4: filter_articles/filter_ambiguities removed (v1 ambiguity/
    # article loaders deprecated). For now, leave the keys in the inputs
    # dict as empty lists so consumers don't KeyError. New consumers (SP-B/C)
    # should use preproc_catalog.load_pairs() for cross-regulation analysis
    # and read the regulatory OJ text directly from preproc_out/3-entities/clauses/.
    applicable_articles: list[dict] = []
    ambiguities: list[dict] = []
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

    logger.debug(
        "assemble_inputs(%s): subs=%d regs=%d cr=%d impls=%d (articles/ambiguities empty post-T4)",
        domain_id,
        len(subdomains),
        len(applicable_regs),
        len(cross_reg_analysis),
        len(existing_implementations),
    )
    return inputs


# ─── Internal helpers ─────────────────────────────────────────────────


def _case_id(state: V2State) -> str:
    """Return the basename of ``state['case_path']`` (or empty string)."""
    case_path = state.get("case_path") or ""
    if not case_path:
        return ""
    return Path(case_path).name


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
        elif hasattr(value, "__dict__") and not isinstance(value, (str, int, float, bool, list, dict)):
            value = {
                k: v for k, v in value.__dict__.items()
                if not k.startswith("_")
            }
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
        inheritability = "INHERITABLE" if all(i == "INHERITABLE" for _, i in per_sub) else "BUILD_REQUIRED"

    # CORR-042 inline fix: ctx may be dict (v1-compat shim) or Pydantic.
    # Handle both so the legacy MAP path (assemble_inputs) doesn't crash.
    if isinstance(ctx, dict):
        scale_raw = ctx.get('scale') or ctx.get('complexity_tier') or 'LOW'
        employees_raw = ctx.get('employees') or 0
        fte_raw = ctx.get('security_fte') or 0.0
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


__all__ = ["assemble_inputs"]
