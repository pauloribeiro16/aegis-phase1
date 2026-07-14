"""prompt — Render the MAP-DOMAIN-ADAPT prompt from assembled inputs.

Reads the canonical prompt spec from
``prompts/MAP-DOMAIN-ADAPT.md`` (or an inline fallback if the file is
not available at runtime) and substitutes the structured ``inputs``
dict produced by :func:`assemble_inputs`. The rendered markdown string
is what gets sent to the LLM.

Sections (in order):
    1. COMPANY CONTEXT
    2. EXISTING IMPLEMENTATIONS
    3. APPLICABLE ARTICLES (with text snippets)
    4. SUB-DOMAIN HSOs (verbatim from the Regulatory Baseline)
    5. CROSS-REG ANALYSIS
    6. KNOWN AMBIGUITIES
    7. TRACK B SUGGESTION (informational)
    8. TASK
    9. OUTPUT FORMAT

Public API:
    render_prompt(inputs, feedback="") -> str
    load_prompt_spec() -> str
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROMPT_SPEC_PATH = Path(__file__).parent / "prompts" / "MAP-DOMAIN-ADAPT.md"

# Section header constants used by render_prompt(). Kept as constants so
# tests and downstream code can refer to them without duplicating strings.
_S_COMPANY = "## 1. COMPANY CONTEXT"
_S_IMPLS = "## 2. EXISTING IMPLEMENTATIONS"
_S_ARTS = "## 3. APPLICABLE ARTICLES"
_S_SUBS = "## 4. SUB-DOMAIN HSOs"
_S_CROSS = "## 5. CROSS-REG ANALYSIS"
_S_AMBIG = "## 6. KNOWN AMBIGUITIES"
_S_TRACKB = "## 7. TRACK B SUGGESTION"
_S_TASK = "## 8. TASK"
_S_OUTPUT = "## 9. OUTPUT FORMAT"


def render_prompt(inputs: dict[str, Any], feedback: str = "") -> str:
    """Render the MAP-DOMAIN-ADAPT prompt with inputs filled in.

    Args:
        inputs: Dict produced by :func:`assemble_inputs`. Must contain
            at least ``domain_id`` and ``company_context.company_name``.
        feedback: Optional retry feedback from a previous failed parse.
            When non-empty, appended to the TASK section so the LLM
            can correct its output format on the next attempt.

    Returns:
        Rendered prompt string (markdown) ready for the LLM.
    """
    if not isinstance(inputs, dict):
        raise TypeError("inputs must be a dict produced by assemble_inputs()")
    domain_id = str(inputs.get("domain_id") or "UNKNOWN")
    ctx = inputs.get("company_context") or {}
    company_name = str(ctx.get("company_name") or "the company")

    spec = load_prompt_spec()
    inputs_block = _format_inputs_block(inputs)

    parts: list[str] = [
        _S_COMPANY,
        _render_company_context(ctx),
        "",
        _S_IMPLS,
        _render_implementations(inputs.get("existing_implementations") or []),
        "",
        _S_ARTS,
        _render_articles(inputs.get("applicable_articles") or []),
        "",
        _S_SUBS,
        _render_subdomains(inputs.get("subdomains") or []),
        "",
        _S_CROSS,
        _render_cross_reg(inputs.get("cross_reg_analysis") or []),
        "",
        _S_AMBIG,
        _render_ambiguities(inputs.get("ambiguities") or []),
        "",
        _S_TRACKB,
        _render_track_b(inputs.get("track_b_suggestion") or {}),
        "",
        _S_TASK,
        f"For domain **{domain_id}** at company **{company_name}**:",
        "",
        "1. Read company context + existing implementations.",
        "2. Adapt HSOs to company scale (MICRO/SMALL/MEDIUM/LARGE/MAX).",
        "3. Produce ONE adapted_objective (3-6 sentences) for the whole domain.",
        "4. List 3-5 key_adjustments (concrete changes vs raw HSOs).",
        "5. Rate confidence: HIGH/MEDIUM/LOW.",
        "",
        "INPUTS (verbatim, do not reclassify):",
        "```yaml",
        inputs_block,
        "```",
    ]

    if feedback:
        parts.append("")
        parts.append(f"PREVIOUS ERROR: {feedback}")
        parts.append("Please correct the output format.")

    parts.append("")
    parts.append(_S_OUTPUT)
    parts.append("```")
    parts.append("ADAPTED_OBJECTIVE: <3-6 sentences>")
    parts.append("KEY_ADJUSTMENTS:")
    parts.append("- <adjustment 1>")
    parts.append("- <adjustment 2>")
    parts.append("- <adjustment 3>")
    parts.append("CONFIDENCE: HIGH | MEDIUM | LOW")
    parts.append("```")

    return _append_spec_metadata("\n".join(parts), spec, inputs)


def load_prompt_spec() -> str:
    """Load the canonical MAP-DOMAIN-ADAPT.md prompt spec.

    Returns:
        The raw markdown text of the spec (frontmatter + body).

    Raises:
        FileNotFoundError: when the spec file is missing.
    """
    if not _PROMPT_SPEC_PATH.exists():
        raise FileNotFoundError(
            f"Prompt spec not found at {_PROMPT_SPEC_PATH}"
        )
    return _PROMPT_SPEC_PATH.read_text(encoding="utf-8")


# ─── Section renderers ─────────────────────────────────────────────────


def _format_inputs_block(inputs: dict[str, Any]) -> str:
    """Render the ``inputs`` dict as a compact YAML-ish block.

    Using ``json.dumps(indent=2)`` keeps the block valid YAML for any
    reasonable LLM parser while staying readable.
    """
    serializable = _make_serializable(inputs)
    return json.dumps(serializable, indent=2, ensure_ascii=False, default=str)


def _make_serializable(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    return obj


def _render_company_context(ctx: dict[str, Any]) -> str:
    if not ctx:
        return "_No company context available._"
    lines = [
        f"- **Company**: {ctx.get('company_name', '?')}",
        f"- **Sector**: {ctx.get('sector', '?')}",
        f"- **Scale**: {ctx.get('scale', '?')}",
        f"- **Employees**: {ctx.get('employees', '?')}",
        f"- **Security FTE**: {ctx.get('security_fte', '?')}",
        f"- **Applicable regulations**: {_join_or_dash(ctx.get('applicable_regs'))}",
        f"- **Tech stack**: {_join_or_dash(ctx.get('tech_stack'))}",
    ]
    return "\n".join(lines)


def _render_implementations(impls: list[dict[str, Any]]) -> str:
    if not impls:
        return "_No existing implementations on the company tech stack._"
    lines = ["| Implementation | Covers | Adequacy |", "|---|---|---|"]
    for impl in impls:
        covers = ", ".join(impl.get("covers") or []) or "-"
        lines.append(
            f"| {impl.get('name', '?')} | {covers} | {impl.get('adequacy', '?')} |"
        )
    return "\n".join(lines)


def _render_articles(arts: list[dict[str, Any]]) -> str:
    if not arts:
        return "_No applicable articles for this domain._"
    out: list[str] = []
    for art in arts:
        reg = art.get("regulation", "?")
        article = art.get("article", "?")
        title = art.get("title", "")
        text = art.get("text", "")
        out.append(f"### {reg} {article} — {title}")
        snippet = text[:600] + ("…" if len(text) > 600 else "")
        out.append(snippet or "_(no text)_")
        out.append("")
    return "\n".join(out).rstrip()


def _render_subdomains(subs: list[dict[str, Any]]) -> str:
    if not subs:
        return "_No sub-domains for this domain._"
    out: list[str] = []
    for sub in subs:
        sid = sub.get("id", "?")
        title = sub.get("title", "")
        hl = sub.get("hso_hl", "")
        out.append(f"### {sid} — {title}")
        if hl:
            out.append(f"**High-level objective (Regulatory Baseline, FROZEN)**: {hl}")
        for pr in sub.get("hso_per_reg") or []:
            reg = pr.get("regulation", "?")
            obj = pr.get("objective", "")
            out.append(f"- **{reg}**: {obj}")
        out.append("")
    return "\n".join(out).rstrip()


def _render_cross_reg(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "_No cross-regulation analysis for this domain._"
    lines = ["| Pair | Type | Summary |", "|---|---|---|"]
    for e in entries:
        pair = e.get("pair", "?")
        ptype = e.get("type", "?")
        summary = (e.get("summary") or "").replace("|", "\\|")
        lines.append(f"| {pair} | {ptype} | {summary} |")
    return "\n".join(lines)


def _render_ambiguities(ambigs: list[dict[str, Any]]) -> str:
    if not ambigs:
        return "_No known ambiguities for this domain._"
    out: list[str] = []
    for a in ambigs:
        out.append(f"- **{a.get('id', '?')}** — {a.get('description', '')}")
        if a.get("resolution"):
            out.append(f"  - Resolution: {a['resolution']}")
    return "\n".join(out)


def _render_track_b(suggestion: dict[str, Any]) -> str:
    if not suggestion:
        return "_No TrackB suggestion computed._"
    tier = suggestion.get("tier", "?")
    rationale = suggestion.get("rationale", "")
    attrs = suggestion.get("attrs") or {}
    lines = [
        f"- **Suggested tier**: {tier}",
        f"- **Rationale**: {rationale}",
    ]
    if attrs.get("inheritability"):
        lines.append(f"- **Inheritability**: {attrs['inheritability']}")
    if attrs.get("scale"):
        lines.append(f"- **Scale**: {attrs['scale']}")
    return "\n".join(lines)


# ─── Spec metadata pass-through ───────────────────────────────────────


def _append_spec_metadata(rendered: str, spec: str, inputs: dict[str, Any]) -> str:
    """Prepend a short header with the prompt-spec identifier.

    Kept minimal so the LLM receives clean instructions. The full spec
    lives next to the code for human auditors.
    """
    spec_id = _extract_frontmatter_value(spec, "prompt_spec_id") or "MAP-DOMAIN-ADAPT"
    header = (
        f"# {spec_id} — AEGIS Phase 1 MAP (rendered)\n"
        f"_Prompt-spec: {spec_id}. Read OUTPUT FORMAT strictly._\n"
    )
    return header + "\n" + rendered


def _extract_frontmatter_value(spec: str, key: str) -> str | None:
    """Return the value of a YAML frontmatter key, or ``None``."""
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", spec, re.MULTILINE)
    return match.group(1).strip() if match else None


def _join_or_dash(values: Any) -> str:
    """Render a list-like value as a comma-separated string, or '-'."""
    if not values:
        return "-"
    if isinstance(values, list | tuple):
        return ", ".join(str(v) for v in values if v) or "-"
    return str(values)


__all__ = ["load_prompt_spec", "render_prompt"]
