"""prompt_builder — Assemble the MAP-stage LLM prompt for a domain.

The prompt has five clearly delimited sections so a local model can
focus on adaptation without re-deriving context:

    1. COMPANY CONTEXT     — filtered CompanyContext slice
    2. APPLICABLE ARTICLES — filtered regulations
    3. SUB-DOMAIN HSOs     — raw HSOs (Adaptation targets)
    4. CROSS-REG ANALYSIS  — preprocessing entries for the domain
    5. TASK                — explicit instruction to adapt HSOs to scale

References:
    - contracts/SPRINT002_003_map_reduce_output.md
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.v2.domain.article_filter import filter_articles
from aegis_phase1.v2.domain.context_filter import filter_context
from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)


def build_domain_prompt(state: V2State, domain_id: str) -> str:
    """Build the full MAP-stage prompt string for a domain.

    Args:
        state: Pipeline V2State.
        domain_id: Domain identifier (e.g. ``"D-04"``).

    Returns:
        A single string containing all five prompt sections separated
        by ``##`` headers. Empty sections render as ``"(none)"`` so
        the LLM never gets a confusing blank.
    """
    ctx = filter_context(state, domain_id)
    articles = filter_articles(state, domain_id)
    subdomains = _subdomains_for(state, domain_id)
    cross_reg = _cross_reg_for(state, domain_id)

    parts: list[str] = []
    parts.append(_section_company(ctx))
    parts.append(_section_articles(articles))
    parts.append(_section_hsos(subdomains))
    parts.append(_section_cross_reg(cross_reg))
    parts.append(_section_task(domain_id, ctx))
    prompt = "\n\n".join(parts)

    logger.debug(
        "build_domain_prompt(%s): ctx=%d keys, articles=%d, subs=%d, cross_reg=%d, len=%d",
        domain_id, len(ctx), len(articles), len(subdomains), len(cross_reg), len(prompt),
    )
    return prompt


# ─── Section builders ─────────────────────────────────────────────────


def _section_company(ctx: dict[str, Any]) -> str:
    """Format the COMPANY CONTEXT section."""
    if not ctx:
        return "## 1. COMPANY CONTEXT\n(none available)"
    lines = ["## 1. COMPANY CONTEXT", ""]
    derived = ctx.pop("_derived", None) if isinstance(ctx.get("_derived"), dict) else ctx.get("_derived")
    for k, v in ctx.items():
        if k == "_derived":
            continue
        lines.append(f"- {k}: {_fmt(v)}")
    if derived:
        lines.append("")
        lines.append("Derived:")
        for k, v in derived.items():
            lines.append(f"- {k}: {_fmt(v)}")
    return "\n".join(lines)


def _section_articles(articles: list[dict]) -> str:
    """Format the APPLICABLE ARTICLES section."""
    if not articles:
        return "## 2. APPLICABLE ARTICLES\n(none)"
    lines = ["## 2. APPLICABLE ARTICLES", ""]
    for reg in articles:
        name = reg.get("short_name") or reg.get("name") or "?"
        src = reg.get("_match_source", "?")
        lines.append(f"- {name} (matched by: {src})")
    return "\n".join(lines)


def _section_hsos(subdomains: list[tuple[str, dict]]) -> str:
    """Format the SUB-DOMAIN HSOs section."""
    if not subdomains:
        return "## 3. SUB-DOMAIN HSOs\n(none)"
    lines = ["## 3. SUB-DOMAIN HSOs", ""]
    for sid, sub in subdomains:
        title = sub.title if hasattr(sub, "title") else sub.get("title", sid)
        hso = sub.section2_hso if hasattr(sub, "section2_hso") else sub.get("section2_hso", {})
        lines.append(f"### {sid} — {title}")
        hl = hso.get("hl_objective") or hso.get("hlObjective") or "(no HL objective)"
        lines.append(f"HL objective: {hl}")
        per_reg = hso.get("per_reg_sos") or hso.get("perRegSos") or []
        if isinstance(per_reg, list) and per_reg:
            for so in per_reg:
                reg = so.get("regulation") or so.get("regulation_id") or "?"
                txt = so.get("security_objective") or so.get("objective") or ""
                lines.append(f"  - [{reg}] {txt}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _section_cross_reg(entries: list[dict]) -> str:
    """Format the CROSS-REG ANALYSIS section."""
    if not entries:
        return "## 4. CROSS-REG ANALYSIS\n(none)"
    lines = ["## 4. CROSS-REG ANALYSIS", ""]
    for e in entries:
        reg_pair = e.get("reg_pair") or e.get("regPair") or ""
        rel = e.get("relationship") or e.get("overlap_type") or ""
        analysis = (e.get("analysis_text") or e.get("analysisText") or "").strip()
        first_line = analysis.splitlines()[0] if analysis else ""
        lines.append(f"- {reg_pair} [{rel}] — {first_line}")
    return "\n".join(lines)


def _section_task(domain_id: str, ctx: dict[str, Any]) -> str:
    """Format the TASK section with explicit adaptation guidance."""
    scale = (ctx.get("scale") or "UNKNOWN") if isinstance(ctx, dict) else "UNKNOWN"
    fte = ctx.get("security_fte") if isinstance(ctx, dict) else None
    return (
        "## 5. TASK\n"
        f"Domain: {domain_id}\n"
        f"Company scale: {scale}\n"
        f"Security FTE: {fte if fte is not None else 'unknown'}\n\n"
        "Adapt the sub-domain HSOs above to this company's scale and capability. "
        "Produce:\n"
        "  - adapted_objective: a short paragraph (3-6 sentences) describing the\n"
        "    tailored objectives, citing the applicable regulations.\n"
        "  - coverage: one of SUBSTANTIVE / PARTIAL / NOT_ADDRESSED, based\n"
        "    on how many applicable regulations and cross-reg entries exist.\n"
        "  - key_changes: bullet list of concrete deltas vs. the raw HSOs\n"
        "    (empty if no changes needed).\n\n"
        "Return JSON with exactly those three keys. Do NOT add commentary\n"
        "outside the JSON object."
    )


# ─── Helpers ──────────────────────────────────────────────────────────


def _subdomains_for(state: V2State, domain_id: str) -> list[tuple[str, Any]]:
    """Return [(sub_id, SubDomainDef), ...] belonging to the domain."""
    subs: dict[str, Any] = state.get("subdomains", {}) or {}
    prefix = domain_id + "."
    return sorted(
        [(sid, s) for sid, s in subs.items() if sid.startswith(prefix)],
        key=lambda kv: kv[0],
    )


def _cross_reg_for(state: V2State, domain_id: str) -> list[dict]:
    """Return cross-regulation entries that mention this domain."""
    entries: list[dict] = list(state.get("preprocessing", {}).get("cross_regulation", []) or [])
    out: list[dict] = []
    for e in entries:
        did = str(e.get("domain_id") or e.get("domainId") or "").upper()
        if did == domain_id.upper():
            out.append(e)
    return out


def _fmt(v: Any) -> str:
    """Render a value compactly for inclusion in the prompt."""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) if v else "(empty)"
    return str(v)


__all__ = ["build_domain_prompt"]
