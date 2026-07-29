"""_functional_prompts — Shared functional-context block for LLM narrative prompts.

Used by the 9 narrative-prompt functions in doc_04a/04b/04c/04d/05/07/07b.
Injects a roster of functional roles (from data/role_models/{tier}.yaml) and
applicable capabilities (from data/capabilities/{D-XX}.yaml), with explicit
disclaimer against naming individuals.

The data loaders are imported lazily inside :func:`build_functional_context` to
avoid a circular import: the 9 caller modules already import from
``aegis_phase1.data.loader`` (for ``classify_tier`` and friends), and a
top-level import here would close the loop on package initialisation.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_regs(applicable_regs: Any) -> tuple[str, ...]:
    """Convert an iterable of regulation abbreviations to a hashable tuple."""
    if applicable_regs is None:
        return ()
    if isinstance(applicable_regs, str):
        return (applicable_regs,)
    try:
        return tuple(str(r) for r in applicable_regs if r)
    except TypeError:
        return ()


@lru_cache(maxsize=32)
def _build_functional_context_cached(tier: str, applicable_regs: tuple[str, ...]) -> str:
    """Cached core of :func:`build_functional_context`.

    Splits caching from input normalisation so callers can pass either a
    ``list[str]`` or ``tuple[str, ...]`` for ``applicable_regs``.
    """
    try:
        from aegis_phase1.data import (
            ROLE_VOCABULARY,
            load_capabilities,
            load_role_model,
        )
    except Exception as exc:
        logger.debug("Functional context: data loader unavailable: %s", exc)
        return ""

    parts: list[str] = []

    role_roster: list[str] = []
    try:
        roles = load_role_model(tier)
    except Exception as exc:
        logger.debug("Functional context: load_role_model(%s) failed: %s", tier, exc)
        roles = []

    if isinstance(roles, list):
        for r in roles:
            if not isinstance(r, dict):
                continue
            role = str(r.get("role", "")).strip()
            if not role:
                continue
            reports_to = str(r.get("reports_to", "—")).strip() or "—"
            fte = str(r.get("fte", "—")).strip() or "—"
            role_roster.append(f"- {role} (reports to {reports_to}, FTE {fte})")

    if role_roster:
        parts.append("Functional roles available (DO NOT name individuals):")
        parts.extend(role_roster)

    if applicable_regs:
        applicable_set = set(applicable_regs)
        cap_lines: list[str] = []
        for dxx in ("D-01", "D-02", "D-03", "D-04", "D-05", "D-06", "D-07", "D-08", "D-09", "D-10"):
            try:
                info = load_capabilities(dxx)
            except Exception as exc:
                logger.debug("Functional context: load_capabilities(%s) failed: %s", dxx, exc)
                continue
            if not isinstance(info, dict):
                continue
            caps = info.get("capabilities", [])
            if not isinstance(caps, list):
                continue
            for cap in caps:
                if not isinstance(cap, dict):
                    continue
                obligations = cap.get("obligations")
                if not isinstance(obligations, dict) or not obligations:
                    continue
                if not any(reg in applicable_set for reg in obligations):
                    continue
                cap_id = str(cap.get("id", "")).strip()
                if not cap_id:
                    continue
                a_fn = str(cap.get("a_function", "—")).strip() or "—"
                r_fn = str(cap.get("r_function", "—")).strip() or "—"
                title = str(cap.get("title", "")).strip()
                cap_lines.append(f"- {cap_id}: A={a_fn}, R={r_fn} ({title})")

        if cap_lines:
            parts.append("")
            parts.append("Capabilities required by applicable regulations:")
            parts.extend(cap_lines)

    if not parts:
        return ""

    parts.append("")
    parts.append(
        "Use FUNCTION NAMES only. Do NOT name individuals. Describe roles "
        "and responsibilities by their function, never by a person's title or "
        "name. The five canonical functions are: "
        f"{', '.join(sorted(ROLE_VOCABULARY))}."
    )
    return "\n".join(parts)


def build_functional_context(tier: str, applicable_regs: Any) -> str:
    """Build a functional context block to prepend to LLM prompts.

    Returns the empty string on any loader failure (defensive — the 9 prompts
    must keep working even when data/role_models/ or data/capabilities/ are
    partially missing). The result is cached on ``(tier, applicable_regs)``
    so repeated calls from ``_domain_notes_prompt`` (10x per doc_04b render)
    are O(1).

    Args:
        tier: One of ``MICRO``, ``SMALL``, ``MEDIUM``, ``LARGE``, ``MAX``.
        applicable_regs: Iterable of regulation abbreviations, e.g.
            ``["GDPR", "CRA"]`` or ``("GDPR",)``. A bare string is also
            accepted for convenience.

    Returns:
        Multi-line string with a role roster, an optional capability list, and
        an explicit disclaimer. Empty when no data could be loaded.
    """
    return _build_functional_context_cached(tier, _normalize_regs(applicable_regs))


def extract_tier_and_regs(state: Any) -> tuple[str, tuple[str, ...]]:
    """Extract ``tier`` and ``applicable_regs`` from a Phase1 state dict.

    Defensive against missing/oddly-shaped ``company_context`` — never raises.
    """
    if not isinstance(state, dict):
        return "MICRO", ()
    ctx = state.get("company_context")
    if not isinstance(ctx, dict):
        return "MICRO", ()
    tier = str(ctx.get("scale", "MICRO") or "MICRO").upper()
    if tier not in {"MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"}:
        tier = "MICRO"
    regs = ctx.get("applicable_regs") or []
    if not isinstance(regs, list | tuple):
        regs = []
    return tier, tuple(str(r) for r in regs if r)


__all__ = [
    "build_functional_context",
    "extract_tier_and_regs",
]
