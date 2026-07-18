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

    spec = load_prompt_spec()
    applicable_regs = inputs.get("applicable_regs")
    reduced_inputs = {
        "case_id": inputs.get("case_id"),
        "domain_id": inputs.get("domain_id"),
        "company_context": inputs.get("company_context"),
        "applicable_regs": applicable_regs,
    }
    inputs_block = _format_inputs_block(reduced_inputs)

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
        _render_subdomains(inputs.get("subdomains") or [], applicable_regs=applicable_regs),
        "",
        _S_CROSS,
        _render_cross_reg(
            inputs.get("cross_reg_analysis") or [],
            applicable_regs=applicable_regs,
        ),
        "",
        _S_AMBIG,
        _render_ambiguities(inputs.get("ambiguities") or []),
        "",
        _S_TRACKB,
        _render_track_b(inputs.get("track_b_suggestion") or {}),
        "",
        _S_TASK,
        _TASK_BODY_V13.format(domain_id=domain_id),
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
    parts.append(_OUTPUT_FORMAT_BODY_V13)
    parts.append("```")

    return _append_spec_metadata("\n".join(parts), spec, inputs)


_TASK_BODY_V13 = """\
For domain **{domain_id}** (MAP stage — per sub-domain adaptation, v1.3):

1. Read company context (§1) for the perimeter ONLY — so you know which
   regulations apply to scope. Do NOT carry any company-specific detail
   into the adapted prose: the output is regulation-centric and generic
   across companies.

2. §4 contains SUB-DOMAIN HSOs. Each sub-domain block provides:
   - a high-level (HL) **Objective.** paragraph (frozen — verbatim copy);
   - a **Considerations.** bullet block (verbatim copy);
   - one entry per applicable regulation (per-reg **Objective.**
     paragraph, frozen as the legal anchor; per-reg **Considerations.**
     bullet block, verbatim).

3. For EACH sub-domain block in §4, produce a 3-block output (see §9
   OUTPUT FORMAT):
   a. **Generic Objective** block (always emitted): 5-field structure.
      - **Original**: verbatim HL **Objective.** paragraph.
      - **Adapted**: HL adapted to the applicable regulatory perimeter
        and to the company's scale/capability, without naming the
        company.
      - **Rationale**: why — covers regulatory perimeter and
        scale/capability.
      - **Adjustments needed**: high-level strategic actions.
      - **Considerations.**: verbatim **Considerations.** bullets from
        source.
   b. **GDPR Objective** block (only if GDPR is in the applicable
      regulations): the 5-field structure populated from the GDPR sub-SO.
   c. **CRA Objective** block (only if CRA is in the applicable
      regulations): the 5-field structure populated from the CRA sub-SO.
   d. Add additional regulation blocks following the same pattern for
      each applicable regulation.

HARD PROHIBITIONS:
- Connectives at sentence start are forbidden: do NOT use "Furthermore",
  "Moreover", "Additionally", "Also", "In addition", "Besides",
  "On top of that", "As well as".
- Do NOT introduce generic consulting headings as adapted objectives
  (e.g. "Risk Identification", "Governance and Oversight",
  "Control Implementation", "Incident Response and Management",
  "Monitoring and Analysis").
- Output is regulation-centric, generic across companies. Do NOT
  mention company name, scale (MICRO/SMALL/MEDIUM/LARGE/MAX),
  employees count, security FTE, sector, tech stack, or jurisdiction.
- Do NOT reclassify, rename, or re-derive the upstream HSOs. Adapt
  in place.
- Do NOT reference regulations not listed in §4.
- Do NOT emit KEY_ADJUSTMENTS or CONFIDENCE blocks — they are part of
  the legacy contract and have been replaced by the 5-field structure.
- Do NOT emit any commentary, headings, or prose outside the structured
  3-blocos x 5-campos pattern."""


_OUTPUT_FORMAT_BODY_V13 = """\
For each sub-domain D-XX.Y in §4, emit EXACTLY ONE block:

### D-XX.Y — <sub-domain title>

**Generic Objective.**
- Original: <verbatim HL **Objective.** paragraph from source>
- Adapted: <HL adapted to applicable regulatory perimeter + scale/capability>
- Rationale: <why — covers regulatory perimeter and scale/capability>
- Adjustments needed: <high-level strategic actions>
**Considerations.**
- <verbatim bullet 1 from **Considerations.** in source>
- <verbatim bullet 2 from source>
...

**GDPR Objective.**
- Original: <verbatim GDPR sub-SO **Objective.** paragraph>
- Adapted: <adapted GDPR sub-SO>
- Rationale: <why>
- Adjustments needed: <high-level strategic actions>
**Considerations.**
- <verbatim bullets from GDPR sub-SO's **Considerations.**>
...

**CRA Objective.**
- Original: <verbatim CRA sub-SO **Objective.** paragraph>
- Adapted: <adapted CRA sub-SO>
- Rationale: <why>
- Adjustments needed: <high-level strategic actions>
**Considerations.**
- <verbatim bullets from CRA sub-SO's **Considerations.**>
...

Add additional regulation blocks following the same pattern for each
applicable regulation.

Do NOT emit anything outside the structured 3-blocos x 5-campos pattern."""


def load_prompt_spec() -> str:
    """Load the canonical MAP-DOMAIN-ADAPT.md prompt spec.

    Returns:
        The raw markdown text of the spec (frontmatter + body).

    Raises:
        FileNotFoundError: when the spec file is missing.
    """
    if not _PROMPT_SPEC_PATH.exists():
        raise FileNotFoundError(f"Prompt spec not found at {_PROMPT_SPEC_PATH}")
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
        lines.append(f"| {impl.get('name', '?')} | {covers} | {impl.get('adequacy', '?')} |")
    return "\n".join(lines)


def _render_articles(articles: list[dict]) -> str:
    if not articles:
        return "_No applicable articles for this domain._"
    lines = ["## 3. APPLICABLE ARTICLES", ""]
    seen_files: set[str] = set()
    for art in articles:
        reg = art.get("regulation", "?")
        article = art.get("article", "?")
        title = art.get("title", "")
        text = art.get("text", "")
        source = art.get("source_file", "")
        # Multiple CRA Art. 13 references all resolve to the same per-article
        # split file. Dedupe by source_file so we render the file body once.
        dedupe_key = f"{reg}|{source}" if source else f"{reg}|{article}"
        if dedupe_key in seen_files:
            continue
        seen_files.add(dedupe_key)
        lines.append(f"### {reg} {article} — {title}")
        if len(text) > 3000:
            text = text[:3000] + "\n_(truncated at 3000 chars)_"
        lines.append(text or "_(no text)_")
        lines.append("")
    return "\n".join(lines).rstrip()


def _extract_objective_paragraph(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r"\A\s*---\s*\n.*?\n---\s*", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(
        r"(\A(?:^#{1,6}\s+[^\n]+\n)+)",
        "",
        cleaned,
        flags=re.MULTILINE,
    )
    cleaned = re.sub(
        r"\A\s*```(?:yaml|yml)?\s*\n.*?\n```\s*",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if "**Objective.**" not in cleaned:
        # Strip leading whitespace, headings, blockquotes, and table rows
        # in a loop so the cleaned text starts at the first narrative
        # paragraph. The upstream D-10 sub-domain HL is a CRDA-deep
        # provenance blockquote followed by a Participants table followed
        # by a `### Participants` heading — all of which must be removed.
        for _ in range(4):
            previous = cleaned
            cleaned = re.sub(r"\A\s+", "", cleaned)
            cleaned = re.sub(
                r"(\A(?:^#{1,6}\s+[^\n]+\n)+)",
                "",
                cleaned,
                flags=re.MULTILINE,
            )
            cleaned = re.sub(r"(\A(?:^>\s*[^\n]*\n?)+)", "", cleaned, flags=re.MULTILINE)
            cleaned = re.sub(r"(\A(?:^\|[^\n]*\n)+)", "", cleaned, flags=re.MULTILINE)
            if cleaned == previous:
                break
        cleaned = re.sub(r"\A\s+", "", cleaned)
    objective_match = re.search(
        r"\*\*Objective\.\*\*\s*(?P<obj>.+?)(?=\n\s*\*\*[A-Z][A-Za-z _]*\.|\Z)",
        cleaned,
        flags=re.DOTALL,
    )
    if objective_match is None:
        cleaned = cleaned.strip()
        if not cleaned:
            return ""
        # Fallback: the source HL carries a CRDA-deep provenance block
        # rather than an explicit `**Objective.**` marker. Surface the
        # first SUBSTANTIVE sentence (skipping meta-summaries like
        # "Of N pairs, N verified as SAME" that begin with
        # bookkeeping tokens).
        first_para = cleaned.split("\n\n", 1)[0].strip()
        candidate_sentences = re.split(
            r"(?<=[.!?])\s+(?=[A-Z])", first_para, maxsplit=10
        )
        meta_prefixes = ("Of ", "All ", "The high-level ", "These are ", "NIS ")
        chosen = ""
        for sentence in candidate_sentences:
            stripped_sentence = sentence.strip()
            if len(stripped_sentence) < 30:
                continue
            if any(stripped_sentence.startswith(prefix) for prefix in meta_prefixes):
                continue
            chosen = stripped_sentence
            break
        if not chosen:
            chosen = first_para
        if len(chosen) > 1500:
            chosen = chosen[:1500] + "\n_(truncated)_"
        return f"**Objective.** {chosen}"
    objective = objective_match.group("obj").strip()
    objective = re.split(r"\n\s*\*\*CSF anchors\b", objective, maxsplit=1)[0].rstrip()
    return f"**Objective.** {objective}"


def _extract_objective_and_first_consideration(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\A\s*---\s*\n.*?\n---\s*", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\A\s*#{1,6}\s+[^\n]+\n", "", cleaned)
    cleaned = re.sub(
        r"\A\s*```(?:yaml|yml)?\s*\n.*?\n```\s*",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    objective_match = re.search(
        r"\*\*Objective\.\*\*\s*(?P<obj>.+?)(?=\n\s*\*\*Considerations\.|\Z)",
        cleaned,
        flags=re.DOTALL,
    )
    if objective_match is None:
        logger.debug("No Objective paragraph found in sub-SO text")
        return cleaned

    objective = objective_match.group("obj").strip()
    objective = re.split(r"\n\s*\*\*CSF anchors\b", objective, maxsplit=1)[0].rstrip()
    result = f"**Objective.** {objective}"
    consideration_match = re.search(
        r"\*\*Considerations\.\*\*\s*\n-\s*(?P<first>[^\n]+)",
        cleaned,
    )
    if consideration_match:
        result += f"\n**Considerations.**\n- {consideration_match.group('first').strip()}"
    return result


def _norm_reg_for_compare(code: str) -> str:
    return code.upper().replace(" ", "").replace("_", "")


_REG_LABEL_MAP: dict[str, str] = {
    "GDPR": "GDPR Objective",
    "CRA": "CRA Objective",
    "NIS2": "NIS 2 Objective",
    "NIS": "NIS 2 Objective",
    "DORA": "DORA Objective",
    "AIACT": "AI Act Objective",
    "AI_ACT": "AI Act Objective",
}


def _extract_considerations(text: str) -> str:
    """Extract the ``**Considerations.**`` bullet block from a sub-SO text.

    Returns the bullet block (without the ``**Considerations.**`` header).
    Empty string when no Considerations block found.
    """
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r"\A\s*---\s*\n.*?\n---\s*", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"(\A(?:^#{1,6}\s+[^\n]+\n)+)", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\A\s*```(?:yaml|yml)?\s*\n.*?\n```\s*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    m = re.search(
        r"\*\*Considerations\.\*\*\s*\n(?P<bullets>(?:-\s+[^\n]+\n?)+)",
        cleaned,
    )
    if not m:
        return ""
    return m.group("bullets").strip()


def _render_subdomains(
    subs: list[dict[str, Any]],
    applicable_regs: list[str] | None = None,
) -> str:
    if not subs:
        return "_No sub-domains for this domain._"
    applicable_set = (
        {_norm_reg_for_compare(reg) for reg in applicable_regs if reg}
        if applicable_regs is not None
        else None
    )
    out: list[str] = []
    for sub in subs:
        sid = sub.get("id", "?")
        title = sub.get("title", "")
        hl_text = str(sub.get("hso_hl") or "")
        hl_objective = _extract_objective_paragraph(hl_text)
        if not hl_objective:
            continue
        if len(hl_objective) > 1500:
            hl_objective = hl_objective[:1500] + "\n_(truncated)_"
        hl_considerations = _extract_considerations(hl_text)
        if len(hl_considerations) > 1500:
            hl_considerations = hl_considerations[:1500] + "\n_(truncated)_"
        out.append(f"### {sid} — {title}")
        out.append("")
        out.append("**Generic Objective.**")
        out.append("")
        out.append(hl_objective)
        out.append("")
        if hl_considerations:
            out.append("**Considerations.**")
            out.append("")
            out.append(hl_considerations)
            out.append("")
        for pr in sub.get("hso_per_reg") or []:
            reg = str(pr.get("regulation") or "?")
            if applicable_set is not None and _norm_reg_for_compare(reg) not in applicable_set:
                continue
            objective_text = str(pr.get("objective") or "")
            objective = _extract_objective_paragraph(objective_text)
            if not objective:
                continue
            if len(objective) > 1500:
                objective = objective[:1500] + "\n_(truncated)_"
            considerations = _extract_considerations(objective_text)
            if len(considerations) > 1500:
                considerations = considerations[:1500] + "\n_(truncated)_"
            reg_norm = _norm_reg_for_compare(reg)
            reg_label = _REG_LABEL_MAP.get(reg_norm, f"{reg} Objective")
            label = f"**{reg_label}.**"
            out.append(label)
            out.append("")
            out.append(objective)
            out.append("")
            if considerations:
                out.append("**Considerations.**")
                out.append("")
                out.append(considerations)
                out.append("")
    return "\n".join(out).rstrip()


def _render_cross_reg(
    entries: list[dict],
    applicable_regs: list[str] | None = None,
) -> str:
    if applicable_regs is not None:
        applicable_set = {_norm_reg_for_compare(r) for r in applicable_regs if r}
        out: list[dict] = []
        for e in entries:
            pair = str(e.get("reg_pair") or e.get("pair") or "")
            regs_in_pair = re.split(r"[↔\-/,]", pair)
            regs_normalized = {_norm_reg_for_compare(r) for r in regs_in_pair if r.strip()}
            if regs_normalized and regs_normalized.issubset(applicable_set):
                out.append(e)
        entries = out
    if not entries:
        return "_No cross-regulation analysis for this domain (only applicable pairs shown)._"
    lines = ["| Pair | Type | Summary |", "|---|---|---|"]
    for e in entries:
        pair = e.get("reg_pair") or e.get("pair") or "?"
        ptype = e.get("relationship") or e.get("overlap_type") or ""
        summary = (e.get("summary") or e.get("analysis_text") or "").replace("|", "\\|")
        lines.append(f"| {pair} | {ptype} | {summary} |")
    return "\n".join(lines)


def _render_ambiguities(ambigs: list[dict]) -> str:
    if not ambigs:
        return "_No applicable ambiguities for this domain._"
    out: list[str] = []
    for a in ambigs:
        out.append(f"- **{a.get('id', '?')}** — {a.get('description', '')}")
        if a.get("resolution"):
            out.append(f"  - Resolution: {a['resolution']}")
    rendered = "\n".join(out)
    if len(rendered) > 10000:
        rendered = rendered[:10000] + "\n_(truncated at 10000 chars)_"
    return rendered


def _render_track_b(suggestion: dict) -> str:
    if not suggestion:
        return "_No Track B suggestion._"
    tier = suggestion.get("tier", "?")
    rationale = suggestion.get("rationale", "")
    attrs = suggestion.get("attrs") or {}
    lines = [
        f"- **Tier**: {tier}",
        f"- **Rationale**: {rationale}",
    ]
    if attrs.get("inheritability"):
        lines.append(f"- **Inheritability**: {attrs['inheritability']}")
    if attrs.get("scale"):
        lines.append(f"- **Scale**: {attrs['scale']}")
    by_sub = attrs.get("by_subdomain") or {}
    if by_sub:
        lines.append("- **Per sub-domain:**")
        for sid, sub_attr in by_sub.items():
            lines.append(
                f"  - `{sid}`: tier={sub_attr.get('tier', '?')}, "
                f"priority={sub_attr.get('priority', '?')}, "
                f"inheritability={sub_attr.get('inheritability', '?')}"
            )
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
