"""ambiguities — Filter preprocessing ambiguity entries for a domain.

Reads ``state["preprocessing"]["ambiguities"]`` and returns entries
whose ``id``, ``domain_id`` (frontmatter) or ``applicable_regs``
(frontmatter) match the requested domain or its applicable
regulations.

Each returned entry is a flat ``Ambiguity`` dict with the three
fields the prompt builder needs: ``id``, ``description``, and
``resolution``. The ``resolution`` is taken from
``frontmatter.resolution`` when present, otherwise from a
``## Resolution`` heading inside the body, otherwise empty.

References:
    - contracts/SPRINT002_003_map_reduce_output.md
"""

from __future__ import annotations

import logging
import re
from typing import Any

from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)

_RESOLUTION_HEADING_RE = re.compile(
    r"(?im)^#{1,4}\s+resolution[^\n]*\n+(.*?)(?=^#{1,4}\s|\Z)",
    re.DOTALL | re.MULTILINE,
)


def filter_ambiguities(state: V2State, domain_id: str) -> list[dict[str, str]]:
    """Return ambiguity entries applicable to ``domain_id``.

    Args:
        state: Pipeline V2State (uses
            ``preprocessing.ambiguities`` and
            ``company_context.applicable_regs``).
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        Sorted list of ``Ambiguity`` dicts, deduplicated by ``id``.
        Empty when the preprocessing payload has no ambiguity data.
    """
    preprocessing = state.get("preprocessing") or {}
    raw = preprocessing.get("ambiguities") or []
    if not isinstance(raw, list):
        return []

    applicable_regs = _applicable_reg_set(state)

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if not _matches(entry, domain_id, applicable_regs):
            continue

        aid = str(entry.get("id") or entry.get("document_id") or "").strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)

        out.append({
            "id": aid,
            "description": str(entry.get("description") or "").strip(),
            "resolution": _extract_resolution(entry),
        })

    out.sort(key=lambda e: e["id"])
    logger.debug("filter_ambiguities(%s): %d entries", domain_id, len(out))
    return out


def _matches(
    entry: dict[str, Any],
    domain_id: str,
    applicable_regs: set[str],
) -> bool:
    """Decide whether an ambiguity entry applies to ``domain_id``."""
    frontmatter = entry.get("frontmatter") or {}

    entry_domain = (
        str(frontmatter.get("domain_id") or frontmatter.get("sub_domain") or "")
        .strip()
        .upper()
    )
    if entry_domain.startswith(domain_id.upper() + "."):
        return True
    if entry_domain == domain_id.upper():
        return True

    entry_regs = _as_reg_list(
        frontmatter.get("applicable_regs")
        or frontmatter.get("regulations")
        or frontmatter.get("regulation")
    )
    if entry_regs and applicable_regs and entry_regs & applicable_regs:
        return True

    return False


def _as_reg_list(value: Any) -> set[str]:
    """Normalise a YAML field that may be a string, list, or None."""
    if value is None:
        return set()
    if isinstance(value, str):
        return {v.strip() for v in value.split(",") if v.strip()}
    if isinstance(value, list):
        return {str(v).strip() for v in value if v}
    return set()


def _applicable_reg_set(state: V2State) -> set[str]:
    """Read applicable_regs from company_context, returning a set."""
    ctx = state.get("company_context")
    if ctx is None:
        return set()
    regs = getattr(ctx, "applicable_regs", None) or []
    return {str(r).strip() for r in regs if r}


def _extract_resolution(entry: dict[str, Any]) -> str:
    """Find the resolution string for an ambiguity entry.

    Order of preference:
        1. ``frontmatter.resolution`` (string)
        2. First ``## Resolution`` heading body in the file body
        3. Empty string
    """
    frontmatter = entry.get("frontmatter") or {}
    explicit = frontmatter.get("resolution")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if isinstance(explicit, list) and explicit:
        return "\n".join(str(x) for x in explicit).strip()

    body = entry.get("body") or entry.get("text") or ""
    if not body and entry.get("filepath"):
        try:
            from pathlib import Path

            body = Path(entry["filepath"]).read_text(encoding="utf-8")
        except Exception:
            body = ""
    if not body:
        return ""

    match = _RESOLUTION_HEADING_RE.search(body)
    if match:
        return match.group(1).strip()
    return ""


__all__ = ["filter_ambiguities"]