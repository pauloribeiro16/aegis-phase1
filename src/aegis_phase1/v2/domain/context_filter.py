"""context_filter — Extract company-context fields relevant to a domain.

Each sub-domain expects different slices of the CompanyContext. This
module centralises the per-domain filter rules so the prompt builder
receives a compact dict rather than the full context.

References:
    - contracts/SPRINT002_003_map_reduce_output.md
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)


# ─── Per-domain slice definitions ─────────────────────────────────────
# Maps domain_id -> list of CompanyContext fields to include. Fields
# not in CompanyContext fall back to the sub-domain HSO's relevant
# keys when available. Keep these lists small and intentional.

_DOMAIN_SLICES: dict[str, list[str]] = {
    "D-01": ["company_name", "sector", "applicable_regs", "tech_stack"],
    "D-02": ["company_name", "sector", "tech_stack", "security_fte"],
    "D-03": ["company_name", "employees", "tech_stack", "applicable_regs"],
    "D-04": ["company_name", "employees", "security_fte", "applicable_regs"],
    "D-05": ["company_name", "sector", "applicable_regs", "tech_stack"],
    "D-06": ["company_name", "sector", "applicable_regs", "tech_stack"],
    "D-07": ["company_name", "tech_stack", "security_fte", "applicable_regs"],
    "D-08": ["company_name", "employees", "sector", "security_fte"],
    "D-09": ["company_name", "scale", "employees", "applicable_regs", "complexity_tier"],
    "D-10": ["company_name", "tech_stack", "employees", "security_fte"],
}


def filter_context(state: V2State, domain_id: str) -> dict[str, Any]:
    """Return a compact dict of company-context fields relevant to a domain.

    Args:
        state: Pipeline V2State (must have ``company_context``).
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        Dict containing the selected CompanyContext fields, plus a
        ``_derived`` block with domain-specific convenience values
        (e.g. ``response_capability`` for D-04, ``attack_surface`` for
        D-02). Always includes ``company_name`` and ``scale`` as a
        minimum even if the slice omits them.

    Notes:
        Returns an empty dict when ``company_context`` is None — callers
        must handle that case.
    """
    ctx = state.get("company_context")
    if ctx is None:
        logger.debug("filter_context(%s): no company_context in state", domain_id)
        return {}

    fields = list(_DOMAIN_SLICES.get(domain_id, ["company_name", "scale", "applicable_regs"]))
    if "company_name" not in fields:
        fields.insert(0, "company_name")
    if "scale" not in fields:
        fields.append("scale")

    filtered: dict[str, Any] = {}
    for f in fields:
        if hasattr(ctx, f):
            filtered[f] = getattr(ctx, f)

    filtered["_derived"] = _derive_domain_extras(ctx, domain_id)
    logger.debug("filter_context(%s): %d fields", domain_id, len(filtered))
    return filtered


def _derive_domain_extras(ctx: Any, domain_id: str) -> dict[str, Any]:
    """Compute small domain-specific derived values from the context.

    These are convenience keys used by the prompt builder — they do
    NOT replace real data; they help the LLM reason about scale.

    Args:
        ctx: The CompanyContext instance.
        domain_id: Domain identifier.

    Returns:
        Dict of derived values (may be empty).
    """
    extras: dict[str, Any] = {}
    scale = (ctx.scale or "").upper()
    fte = ctx.security_fte or 0.0

    if domain_id == "D-04":
        extras["response_capability"] = "24x7" if fte >= 2.0 else "business_hours" if fte >= 1.0 else "ad_hoc"
        extras["incident_history"] = "unknown"  # not in CompanyContext; explicit placeholder
    elif domain_id == "D-02":
        extras["attack_surface"] = "public_facing" if ctx.tech_stack else "internal"
    elif domain_id == "D-03":
        extras["identity_provider"] = ctx.tech_stack[0] if ctx.tech_stack else "unknown"
    elif domain_id == "D-09":
        extras["governance_maturity"] = "high" if scale in {"LARGE", "MAX"} else "low" if scale in {"MICRO", "SMALL"} else "medium"
    return extras


__all__ = ["filter_context"]
