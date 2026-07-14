"""proportionality — TrackB tier assignment + 5 operational attributes.

For each active sub-domain, the proportionality stage combines:

* **scale** — from the company context (MICRO / SMALL / MEDIUM / LARGE / MAX).
* **inheritability** — INHERITABLE if any requirement in the sub-domain
  marks a satisfied ``inherited`` control in its ``satisfaction`` block;
  otherwise BUILD_REQUIRED.
* **priority** — the strongest Volere priority present in the
  sub-domain's merged requirements (MUST > SHOULD > COULD).
* **fte** — the company context's ``security_fte`` (consulted for the
  MICRO + low-FTE DEFERRED path in TrackB section 5.2).

The five operational attributes (``satisfaction_pattern``,
``evidence_depth``, ``verification_method``, ``ownership``,
``example_controls``) come from
:meth:`TrackB._tier_attributes` and are appended verbatim.

References:
    - contracts/SPRINT002_003_map_reduce_output.md (Sprint 003 — REDUCE step 4)
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.prompts_v2.track_b import TrackB
from aegis_phase1.v2.state import CompanyContext

logger = logging.getLogger(__name__)

_TRACK_B = TrackB()

_PRIORITY_RANK: dict[str, int] = {"MUST": 3, "SHOULD": 2, "COULD": 1}


def apply_proportionality(
    subdomain_data: dict[str, Any],
    company_context: CompanyContext | None,
) -> dict[str, Any]:
    """Assign a tier + 5 attributes to every sub-domain in ``subdomain_data``.

    Args:
        subdomain_data: Output of :func:`concatenate`. Expected shape:
            ``{"subdomains": {D-XX.Y: {...}, ...}}``. A merged dict
            (``{"merged_requirements": [...]}``) is also accepted and
            converted internally.
        company_context: Parsed ``CompanyContext`` (may be ``None`` for
            dry runs — falls back to MICRO + fte=0).

    Returns:
        A dict with one key:

        * ``profile`` — mapping sub-domain ID -> dict containing
          ``tier``, ``satisfaction_pattern``, ``evidence_depth``,
          ``verification_method``, ``ownership``,
          ``example_controls``. Each entry also carries the inputs
          used to compute the tier (``scale``, ``inheritability``,
          ``priority``, ``source_regs``) for downstream rendering.
    """
    subdomains = _normalise_subdomains(subdomain_data)

    scale = _scale_from_context(company_context)
    fte = float(getattr(company_context, "security_fte", 0.0) or 0.0) if company_context else 0.0

    profile: dict[str, dict[str, Any]] = {}
    for sub_id in sorted(subdomains.keys()):
        entry = subdomains[sub_id] or {}
        requirements = _extract_requirements(entry)
        inheritability = _detect_inheritability(requirements, entry)
        priority = _highest_priority(requirements)
        source_regs = sorted(
            set(_safe_list(entry.get("source_regs", [])))
            | _collect_regs_from_requirements(requirements)
        )

        tier = _TRACK_B.assign_tier(
            scale=scale,
            inheritability=inheritability,
            priority=priority,
            fte=fte,
        )
        attrs = TrackB._tier_attributes(tier, inheritability)

        profile[sub_id] = {
            "tier": tier,
            "scale": scale,
            "inheritability": inheritability,
            "priority": priority,
            "source_regs": source_regs,
            "security_fte": fte,
            **attrs,
        }

    logger.info(
        "apply_proportionality: %d subdomains profiled (scale=%s, fte=%.2f)",
        len(profile),
        scale,
        fte,
    )
    return {"profile": profile}


def _normalise_subdomains(
    subdomain_data: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not subdomain_data:
        return {}
    if "subdomains" in subdomain_data and isinstance(subdomain_data["subdomains"], dict):
        return subdomain_data["subdomains"]
    if "merged_requirements" in subdomain_data:
        return {
            entry.get("subdomain", ""): entry
            for entry in subdomain_data.get("merged_requirements", [])
            if entry.get("subdomain")
        }
    return subdomain_data


def _scale_from_context(ctx: CompanyContext | None) -> str:
    if ctx is None:
        return "MICRO"
    scale = (getattr(ctx, "scale", "") or "").upper()
    if scale in {"MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"}:
        return scale
    employees = getattr(ctx, "employees", 0) or 0
    if employees <= 10:
        return "MICRO"
    if employees <= 50:
        return "SMALL"
    if employees <= 250:
        return "MEDIUM"
    if employees <= 1000:
        return "LARGE"
    return "MAX"


def _extract_requirements(entry: dict[str, Any]) -> list[dict[str, Any]]:
    return list(
        entry.get("requirements")
        or entry.get("all_requirements")
        or entry.get("merged_requirements")
        or []
    )


def _detect_inheritability(
    requirements: list[dict[str, Any]], entry: dict[str, Any]
) -> str:
    """Return ``INHERITABLE`` if any satisfied control is marked inherited.

    Checks each requirement's ``satisfaction.controls`` list for the
    ``inherited`` marker (case-insensitive substring). Falls back to
    the sub-domain's own ``inheritability`` hint, and finally to
    ``BUILD_REQUIRED``.
    """
    for req in requirements:
        satisfaction = req.get("satisfaction") or {}
        controls = satisfaction.get("controls") or []
        for control in controls:
            if isinstance(control, dict):
                token = (
                    str(control.get("pattern", ""))
                    + " "
                    + str(control.get("status", ""))
                ).lower()
            else:
                token = str(control).lower()
            if "inherit" in token:
                return "INHERITABLE"

    hint = str(entry.get("inheritability", "")).upper()
    if hint in {"INHERITABLE", "BUILD_REQUIRED"}:
        return hint

    return "BUILD_REQUIRED"


def _highest_priority(requirements: list[dict[str, Any]]) -> str:
    if not requirements:
        return "MUST"
    best = "COULD"  # weakest default for selection
    best_rank = _PRIORITY_RANK.get(best, 0)
    for req in requirements:
        p = str(req.get("priority", "")).upper()
        rank = _PRIORITY_RANK.get(p, 0)
        if rank > best_rank:
            best = p
            best_rank = rank
    return best if best_rank > 0 else "MUST"


def _collect_regs_from_requirements(requirements: list[dict[str, Any]]) -> set[str]:
    regs: set[str] = set()
    for req in requirements:
        raw = req.get("applicable_if") or {}
        if isinstance(raw, dict):
            raw = raw.get("regs", [])
        for r in _safe_list(raw):
            regs.add(r.upper())
    return regs


def _safe_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


__all__ = ["apply_proportionality"]