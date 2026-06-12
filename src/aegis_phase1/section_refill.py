"""Section-level refill: surgically replace a single section in a filled document.

Given a filled document, a section name with issues, and the state context,
regenerate ONLY that section using the LLM and substitute it in-place.
"""

from __future__ import annotations

import re
from pathlib import Path

from aegis_phase1.logging_config import get_logger

logger = get_logger(__name__)


SECTION_HEADER_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)


def _split_into_sections(text: str) -> list[tuple[int, str, str]]:
    """Split text into (level, header, body) tuples with byte offsets.

    Returns list of (header_level, header_text, body_text).
    Last entry may have empty header (text before first header).
    """
    lines = text.split("\n")
    sections: list[tuple[int, str, str, int, int]] = []
    current_level = 0
    current_header = ""
    current_body: list[str] = []
    header_start = 0

    pos = 0
    for line in lines:
        line_start = pos
        line_end = pos + len(line)
        m = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if m:
            if current_header or current_body:
                body_text = "\n".join(current_body).rstrip("\n")
                sections.append(
                    (current_level, current_header, body_text, header_start, line_start)
                )
            current_level = len(m.group(1))
            current_header = m.group(2)
            current_body = []
            header_start = line_start
        else:
            if not current_header and not current_body and not sections:
                pass
            current_body.append(line)
        pos = line_end + 1

    if current_header or current_body:
        body_text = "\n".join(current_body).rstrip("\n")
        sections.append((current_level, current_header, body_text, header_start, len(text)))

    return [(s[0], s[1], s[2], s[3], s[4]) for s in sections]


def find_section_range(text: str, section_name: str) -> tuple[int, int, int] | None:
    """Find the byte range of a section in the document.

    Returns (header_level, body_start_offset, body_end_offset) or None.
    """
    sections = _split_into_sections(text)
    norm = _normalize(section_name)

    for level, header, _body, _h_start, h_end in sections:
        if _normalize(header) == norm:
            body_start = h_end
            next_h_start = len(text)
            for _l2, _h2, _b2, _hs2, _he2 in sections:
                if _hs2 > h_end:
                    next_h_start = min(next_h_start, _hs2)
                    break
            return (level, body_start, next_h_start)

    return None


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _build_refill_prompt(
    section_name: str,
    template_section: str,
    state: dict,
    current_body: str,
    issue_description: str,
) -> str:
    """Build a focused prompt for the LLM to refill a single section."""
    state_summary_lines: list[str] = []
    for k, v in state.items():
        if isinstance(v, str | int | float | bool):
            state_summary_lines.append(f"  - {k}: {v}")
        elif isinstance(v, list):
            state_summary_lines.append(f"  - {k}: (list of {len(v)} items)")
        elif isinstance(v, dict):
            state_summary_lines.append(f"  - {k}: (dict with {len(v)} keys)")
    state_summary = "\n".join(state_summary_lines) if state_summary_lines else "  (no state)"

    return f"""You are refilling ONE specific section of a regulatory document.

SECTION NAME: {section_name}

TEMPLATE STRUCTURE (what the section should look like):
{template_section[:2000]}

CURRENT (PROBLEMATIC) CONTENT:
{current_body[:2000]}

ISSUE TO FIX:
{issue_description}

AVAILABLE STATE (data you can draw from):
{state_summary[:3000]}

RULES:
- Output ONLY the section body (content under the header). Do NOT include the header line.
- Do NOT output preamble like "Here is the section:" — just the content.
- Be concise but complete. If the template expected a list, output a list.
- Replace any [N], [X], [Y], [...] placeholders with concrete values.
- If the section is "Company Overview" and the state has sector="SME", use that.
- If the section had data in a previous correct run, you can use the same data here.
- Match the style of the original document (Markdown bullets, tables, etc).

REFILLED SECTION BODY:"""


def refill_section(
    filled_path: Path,
    section_name: str,
    template_path: Path,
    state: dict,
    issue_description: str,
    output_path: Path | None = None,
) -> Path:
    """Refill a single section of a filled document.

    Args:
        filled_path: Path to current filled document
        section_name: Name of the section to refill
        template_path: Path to template (for structure reference)
        state: Phase state dict for context
        issue_description: What was wrong with the section
        output_path: Where to write output (defaults to {filled}_v2.md)

    Returns:
        Path to the output document with the section refilled.
    """
    from aegis_phase1.llm.base import create_llm_client
    from aegis_phase1.shared.template_parser import parse_sections

    filled = filled_path.read_text(encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")

    section_range = find_section_range(filled, section_name)
    if section_range is None:
        logger.warning(
            "[refill] section '%s' not found in %s, skipping",
            section_name,
            filled_path.name,
        )
        return filled_path

    _level, body_start, body_end = section_range
    current_body = filled[body_start:body_end].strip()

    template_sections = parse_sections(template)
    template_section_body = ""
    norm = _normalize(section_name)
    for s in template_sections:
        if _normalize(s.header) == norm:
            template_section_body = s.body
            break

    if not template_section_body:
        template_section_body = f"(No template section for '{section_name}')"

    logger.info(
        "[refill] refilling section '%s' in %s (%d → ? chars)",
        section_name,
        filled_path.name,
        len(current_body),
    )

    try:
        client = create_llm_client()
    except Exception:
        logger.error("[refill] could not create LLM client", exc_info=True)
        return filled_path

    prompt = _build_refill_prompt(
        section_name=section_name,
        template_section=template_section_body,
        state=state,
        current_body=current_body,
        issue_description=issue_description,
    )

    try:
        result = client.generate(
            prompt=prompt,
            system="You are a precise documentation assistant fixing a single section.",
            task_name=f"refill_section_{_normalize(section_name)[:30]}",
            temperature=0.1,
            num_predict=1500,
        )
    except Exception:
        logger.error("[refill] LLM call failed for section '%s'", section_name, exc_info=True)
        return filled_path

    if result.get("error"):
        logger.warning("[refill] LLM returned error: %s", result["error"])
        return filled_path

    new_body = result.get("raw", "").strip()

    if not new_body:
        logger.warning("[refill] LLM returned empty body for section '%s'", section_name)
        return filled_path

    new_filled = (
        filled[:body_start].rstrip("\n")
        + "\n\n"
        + new_body
        + "\n\n"
        + filled[body_end:].lstrip("\n")
    )

    if output_path is None:
        stem = filled_path.stem
        if stem.endswith("_filled"):
            stem = stem[:-7] + "_v2_filled"
        elif "_v" in stem:
            stem = re.sub(r"_v\d+_filled", "_v2_filled", stem)
        else:
            stem = stem + "_v2"
        output_path = filled_path.parent / f"{stem}.md"

    output_path.write_text(new_filled, encoding="utf-8")
    logger.info(
        "[refill] wrote %s (%d chars, section was %d → %d)",
        output_path.name,
        len(new_filled),
        len(current_body),
        len(new_body),
    )

    return output_path
