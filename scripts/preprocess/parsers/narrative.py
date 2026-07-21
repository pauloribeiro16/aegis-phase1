"""Structured parsers for narrative .md files (CORR-024 v10).

The v8/v9 pipeline used a catch-all ``parse_root_md`` that produced
``{schema_version, source, doc_id, title, status, chain_version,
frontmatter, raw_md}``. v10 keeps ``parse_root_md`` for files that are
genuinely free-form (e.g. the HSO design rationale) and adds **typed
parsers** for the 7 files in Fase 1 + a generic ``narrative_index``
parser that splits a markdown body into:

  - ``title`` (first H1)
  - ``intro`` (blockquote + paragraphs before the first H2)
  - ``sections[]`` (one per H2, each with ``heading``, ``level``,
    ``paragraphs[]``, ``bullet_lists[]``, ``numbered_lists[]``,
    ``tables[]``)
  - ``frontmatter``, ``raw_md`` (full body — audit-only when structured
    fields are present)

**Zero-loss invariant:** the original ``raw_md`` body is always present
verbatim in the output (either as ``raw_md`` or in the structured
fields concatenated). The structured form is **additive**: it never
removes information from the source.

This module produces **only the structured dict** — the caller is
responsible for writing the JSON file. The intent is that pipeline
callers swap ``parse_root_md(src)`` for the specific parser
(``parse_ambiguity_index``, ``parse_ambiguity_framework``, etc.) so
consumers get typed fields instead of having to parse the raw_md
themselves every time.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Import frontmatter parser lazily so this module works as a script
    OR as a package member.
    """
    try:
        from .frontmatter import parse_frontmatter  # type: ignore[import-not-found]

        return parse_frontmatter(text)
    except (ImportError, ModuleNotFoundError):
        from scripts.preprocess.parsers.frontmatter import (  # type: ignore[import-not-found]
            parse_frontmatter,
        )

        return parse_frontmatter(text)


# ─── shared helpers ────────────────────────────────────────────────────

_H1_RE = re.compile(r"^#\s+(.+?)\s*$")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_H3_RE = re.compile(r"^###\s+(.+?)\s*$")
_H4_RE = re.compile(r"^####\s+(.+?)\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
_BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _parse_table_row(line: str) -> list[str] | None:
    """Parse a single markdown table row. Returns None if not a table row."""
    s = line.strip()
    if not s.startswith("|"):
        return None
    # Drop leading/trailing pipe
    inner = s.strip("|")
    cells = [c.strip() for c in inner.split("|")]
    return cells


def _is_table_separator(line: str) -> bool:
    return bool(_TABLE_SEP_RE.match(line.strip()))


def _split_into_blocks(body: str) -> list[tuple[str, str]]:
    """Split a markdown body into (kind, content) blocks.

    Kinds: 'h1', 'h2', 'h3', 'h4', 'blockquote', 'bullet_list',
    'numbered_list', 'table', 'paragraph'.
    """
    blocks: list[tuple[str, str]] = []
    lines = body.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if _H1_RE.match(stripped):
            blocks.append(("h1", _H1_RE.match(stripped).group(1)))
            i += 1
        elif _H2_RE.match(stripped):
            blocks.append(("h2", _H2_RE.match(stripped).group(1)))
            i += 1
        elif _H3_RE.match(stripped):
            blocks.append(("h3", _H3_RE.match(stripped).group(1)))
            i += 1
        elif _H4_RE.match(stripped):
            blocks.append(("h4", _H4_RE.match(stripped).group(1)))
            i += 1
        elif _BLOCKQUOTE_RE.match(stripped):
            # collect contiguous blockquote lines
            j = i
            collected: list[str] = []
            while j < n and _BLOCKQUOTE_RE.match(lines[j].strip()):
                collected.append(_BLOCKQUOTE_RE.match(lines[j].strip()).group(1))
                j += 1
            blocks.append(("blockquote", "\n".join(collected)))
            i = j
        elif _parse_table_row(stripped) is not None:
            # collect contiguous table rows
            j = i
            rows: list[list[str]] = []
            while j < n:
                row = _parse_table_row(lines[j].strip())
                if row is None:
                    break
                if not rows and _is_table_separator(lines[j]):
                    j += 1
                    continue
                if _is_table_separator(lines[j]):
                    j += 1
                    continue
                rows.append(row)
                j += 1
            if rows:
                header = rows[0]
                body_rows = rows[1:]
                # Render table as a single block string for verbatim storage
                rendered = "| " + " | ".join(header) + " |\n"
                rendered += "|" + "|".join(["---"] * len(header)) + "|\n"
                for r in body_rows:
                    rendered += "| " + " | ".join(r) + " |\n"
                blocks.append(("table", rendered.rstrip()))
            i = j
        elif re.match(r"^\s*[-*+]\s+", stripped):
            # collect contiguous bullet list
            j = i
            items: list[str] = []
            while j < n:
                m = re.match(r"^\s*[-*+]\s+(.*)$", lines[j])
                if not m:
                    break
                items.append(m.group(1).strip())
                j += 1
            blocks.append(("bullet_list", "\n".join(f"- {x}" for x in items)))
            i = j
        elif re.match(r"^\s*\d+\.\s+", stripped):
            # collect contiguous numbered list
            j = i
            items = []
            while j < n:
                m = re.match(r"^\s*\d+\.\s+(.*)$", lines[j])
                if not m:
                    break
                items.append(m.group(1).strip())
                j += 1
            blocks.append(
                (
                    "numbered_list",
                    "\n".join(f"{k+1}. {x}" for k, x in enumerate(items)),
                )
            )
            i = j
        else:
            # paragraph: collect contiguous non-special lines
            j = i
            para_lines: list[str] = []
            while j < n:
                s = lines[j].strip()
                if not s:
                    break
                if (
                    _H1_RE.match(s)
                    or _H2_RE.match(s)
                    or _H3_RE.match(s)
                    or _H4_RE.match(s)
                    or _BLOCKQUOTE_RE.match(s)
                    or _parse_table_row(s) is not None
                    or re.match(r"^\s*[-*+]\s+", s)
                    or re.match(r"^\s*\d+\.\s+", s)
                ):
                    break
                para_lines.append(s)
                j += 1
            if para_lines:
                blocks.append(("paragraph", " ".join(para_lines)))
            i = j
    return blocks


# ─── generic narrative parser ──────────────────────────────────────────


def parse_narrative(path: Path) -> dict[str, Any]:
    """Generic structured parse of a narrative .md file.

    Returns:
        schema_version: "1.0"
        source: str (path)
        doc_id, title, status, chain_version, frontmatter: from FM
        title_h1: first H1 in body (or fallback to FM title)
        intro: blockquote + paragraphs before first H2 (verbatim text)
        sections[]: each H2 section with {heading, level, blocks[]}
            where blocks is a list of {kind, content} preserving the
            verbatim content of the section
        raw_md: full body (audit)
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    blocks = _split_into_blocks(body)
    # First H1
    title_h1 = ""
    for kind, content in blocks:
        if kind == "h1":
            title_h1 = content
            break

    # Intro: everything before the first H2
    intro_blocks: list[tuple[str, str]] = []
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    for kind, content in blocks:
        if kind == "h2":
            if current_section is not None:
                sections.append(current_section)
            current_section = {"heading": content, "level": 2, "blocks": []}
        elif current_section is None:
            # Pre-H2 content → intro
            intro_blocks.append((kind, content))
        else:
            current_section["blocks"].append({"kind": kind, "content": content})
    if current_section is not None:
        sections.append(current_section)

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{path.stem}"),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "frontmatter": fm,
        "title_h1": title_h1,
        "intro": "\n\n".join(content for _, content in intro_blocks),
        "intro_blocks": [{"kind": k, "content": c} for k, c in intro_blocks],
        "sections": sections,
        "section_count": len(sections),
        "raw_md": body,  # zero-loss: full body always preserved
        "raw_md_kept_reason": "audit_fallback_for_zero_loss_invariant",
    }


# ─── Fase 1: ambiguity_analysis/00_Index.json ──────────────────────────


def parse_ambiguity_index(path: Path) -> dict[str, Any]:
    """Parse the Ambiguity Analysis master index.

    Structure (from the source .md):
      - H1 title
      - blockquote scope/lens/layer
      - H2 "Status" with a table of regulations (1 per row)
      - H2 "Supporting files" with a table of file → purpose
      - H2 "Methodology contract" or similar (free-form prose)

    Output adds:
      - scope: text of the first blockquote after H1
      - lens: extracted from blockquote (matches "Lens: ...")
      - layer: extracted from blockquote (matches "Layer: ...")
      - regulations[]: rows of the Status table, with status flag parsed
        ('v0.2 (complete)' → complete=True, 'v0.1' → complete=False, etc.)
      - supporting_files[]: rows of the Supporting files table
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    blocks = _split_into_blocks(body)

    # Scope/Lens/Layer from the first blockquote
    scope = ""
    lens = ""
    layer = ""
    for kind, content in blocks:
        if kind == "blockquote":
            # Strip bold/italic markers for matching
            cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
            m_layer = re.search(r"Layer[:\s]+(\d+)\s+of\s+(\d+)\s*[—\-:]?\s*([^\n]+)?", cleaned)
            if m_layer:
                layer = f"{m_layer.group(1)} of {m_layer.group(2)}"
                if m_layer.group(3):
                    layer += f" — {m_layer.group(3).strip()}"
            m_lens = re.search(r"Lens[:\s]+([^\n]+)", cleaned)
            if m_lens:
                lens = m_lens.group(1).strip().rstrip(".")
            m_scope = re.search(r"Scope[:\s]+([^\n]+)", cleaned)
            if m_scope:
                scope = m_scope.group(1).strip()
            if not scope and not lens and not layer:
                # First blockquote is the scope block
                scope = content
            break

    # Sections
    regulations: list[dict[str, Any]] = []
    supporting_files: list[dict[str, Any]] = []
    other_sections: list[dict[str, Any]] = []
    for kind, content in blocks:
        if kind != "h2":
            continue
        heading = content
        # The block immediately after the H2 is typically the table
        idx = blocks.index((kind, content))
        # Find the first table block after the H2
        for j in range(idx + 1, len(blocks)):
            bk, bv = blocks[j]
            if bk in ("h2", "h3"):
                break
            if bk == "table":
                rows = _extract_table_rows_from_block(bv)
                if not rows:
                    break
                if heading.lower() == "status" and len(rows[0]) >= 3:
                    # First table column is "#", second is "Regulation"
                    for r in rows[1:]:
                        if len(r) < 2:
                            continue
                        regulations.append(
                            {
                                "index": r[0],
                                "regulation": r[1] if len(r) > 1 else "",
                                "status_raw": r[2] if len(r) > 2 else "",
                                "file": r[3] if len(r) > 3 else "",
                                "atomic_clauses": r[4] if len(r) > 4 else "",
                                "date": r[5] if len(r) > 5 else "",
                                "complete": "v0.2" in (r[2] if len(r) > 2 else ""),
                            }
                        )
                elif heading.lower().startswith("supporting files") and len(rows[0]) >= 2:
                    for r in rows[1:]:
                        if len(r) < 2:
                            continue
                        supporting_files.append(
                            {
                                "file": r[0],
                                "purpose": r[1] if len(r) > 1 else "",
                            }
                        )
                break
        else:
            # No table in this section
            other_sections.append({"heading": heading})

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{path.stem}"),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "frontmatter": fm,
        "scope": scope,
        "lens": lens,
        "layer": layer,
        "regulations": regulations,
        "regulation_count": len(regulations),
        "supporting_files": supporting_files,
        "supporting_file_count": len(supporting_files),
        "other_sections": other_sections,
        "raw_md": body,  # zero-loss
        "raw_md_kept_reason": "audit_fallback_for_zero_loss_invariant",
    }


# ─── Fase 1: ambiguity_analysis/01_Framework.json ─────────────────────


def parse_ambiguity_framework(path: Path) -> dict[str, Any]:
    """Parse the Berry (2003) framework document.

    Structure:
      - H1 + blockquote (source + scope)
      - H2 sections numbered "1.", "2.", ... (1, 2, 3, 4, 5, 6, 7, etc.)
      - Each section is free-form prose (Berry methodology)
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    blocks = _split_into_blocks(body)

    # Extract source theoretical lens from first blockquote
    source_lens = ""
    scope = ""
    for kind, content in blocks:
        if kind == "blockquote":
            m_source = re.search(r"Source\s+theoretical\s+lens[:\s]+([^\n]+)", content)
            if m_source:
                source_lens = m_source.group(1).strip()
            m_scope = re.search(r"Scope\s+of\s+this\s+framework[:\s]+([^\n]+(?:\n>.*)*)", content)
            if m_scope:
                scope = m_scope.group(1).strip()
            if not source_lens and not scope:
                scope = content
            break

    # Collect H2 sections with their number prefix
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for kind, content in blocks:
        if kind == "h2":
            if current is not None:
                sections.append(current)
            m_num = re.match(r"^(\d+)\.\s+(.+)$", content)
            current = {
                "number": int(m_num.group(1)) if m_num else None,
                "heading": m_num.group(2) if m_num else content,
                "blocks": [],
            }
        elif current is not None:
            current["blocks"].append({"kind": kind, "content": content})
    if current is not None:
        sections.append(current)

    # Concatenate section text for verbatim loss check
    for s in sections:
        s["text_verbatim"] = "\n\n".join(b["content"] for b in s["blocks"])

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{path.stem}"),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "frontmatter": fm,
        "source_lens": source_lens,
        "scope": scope,
        "sections": sections,
        "section_count": len(sections),
        "raw_md": body,  # zero-loss
        "raw_md_kept_reason": "audit_fallback_for_zero_loss_invariant",
    }


# ─── Fase 1: TEMPLATE_subagent_brief.json ─────────────────────────────


def parse_subagent_brief_template(path: Path) -> dict[str, Any]:
    """Parse the per-regulation sub-agent brief template.

    Structure:
      - H1 title + blockquote (mission)
      - H2 "0. Strict constraints" with a numbered list (1, 2, 3, ...)
      - H2 "1. Inputs" with bullet list
      - H2 "2. Outputs" with bullet list
      - H2 "3. Workflow" (or similar) with numbered list

    Each numbered constraint is parsed into a structured dict with
    ``number`` and ``body`` (the text of the constraint, preserving
    inline markdown).
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    blocks = _split_into_blocks(body)

    # Mission from first blockquote
    mission = ""
    for kind, content in blocks:
        if kind == "blockquote":
            mission = content
            break

    # Sections: collect H2 headings + their block structure
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for kind, content in blocks:
        if kind == "h2":
            if current is not None:
                sections.append(current)
            m_num = re.match(r"^(\d+)\.\s+(.+)$", content)
            current = {
                "number": int(m_num.group(1)) if m_num else None,
                "heading": m_num.group(2) if m_num else content,
                "heading_full": content,
                "blocks": [],
            }
        elif current is not None:
            current["blocks"].append({"kind": kind, "content": content})
    if current is not None:
        sections.append(current)

    # Specifically pull out the strict constraints section
    constraints_section = next((s for s in sections if "constraint" in s["heading"].lower()), None)
    constraints: list[dict[str, Any]] = []
    if constraints_section:
        # Each numbered list block → split into constraints
        for blk in constraints_section["blocks"]:
            if blk["kind"] == "numbered_list":
                # Parse the numbered_list content
                lines = blk["content"].splitlines()
                for line in lines:
                    m = re.match(r"^\d+\.\s+(.*)$", line.strip())
                    if m:
                        constraints.append(
                            {
                                "text": m.group(1),
                                "verbatim": line,
                            }
                        )

    # Pull bullets from all sections (they may be inputs/outputs/etc.)
    bullet_lists: list[dict[str, Any]] = []
    for s in sections:
        for blk in s["blocks"]:
            if blk["kind"] == "bullet_list":
                items = []
                for line in blk["content"].splitlines():
                    m = re.match(r"^-\s+(.*)$", line.strip())
                    if m:
                        items.append(m.group(1))
                if items:
                    bullet_lists.append(
                        {
                            "section_number": s["number"],
                            "section_heading": s["heading"],
                            "items": items,
                        }
                    )

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{path.stem}"),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "frontmatter": fm,
        "mission": mission,
        "constraints": constraints,
        "constraint_count": len(constraints),
        "bullet_lists": bullet_lists,
        "sections": sections,
        "raw_md": body,  # zero-loss
        "raw_md_kept_reason": "audit_fallback_for_zero_loss_invariant",
    }


# ─── Fase 1: global/README.json ───────────────────────────────────────


def parse_preproc_readme(path: Path) -> dict[str, Any]:
    """Parse the preproc_out README.md (static regulatory catalog guide).

    Structure:
      - H1
      - H2 "Purpose"
      - H2 "What lives here" with code-fence directory tree
      - H2 "Cross-regulation analysis" with code-fence directory tree
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    blocks = _split_into_blocks(body)

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for kind, content in blocks:
        if kind == "h2":
            if current is not None:
                sections.append(current)
            current = {"heading": content, "blocks": []}
        elif current is not None:
            current["blocks"].append({"kind": kind, "content": content})
    if current is not None:
        sections.append(current)

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{path.stem}"),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "frontmatter": fm,
        "sections": sections,
        "section_count": len(sections),
        "raw_md": body,  # zero-loss
        "raw_md_kept_reason": "audit_fallback_for_zero_loss_invariant",
    }


# ─── Fase 1: crossregulation/DomainAnalysis/index.json ────────────────


def parse_crossregulation_index(path: Path) -> dict[str, Any]:
    """Parse a crossregulation index.md (DomainAnalysis or DeepAnalysis).

    Structure:
      - H1 + intro (blockquotes)
      - H2 "How to use" with numbered list
      - H2 "Relationship taxonomy (5 types)" with bullet list
      - H2 "Scope overlap analysis" with prose
      - H2 "Pairwise matrix" with code-fence table
      - (DeepAnalysis variant) H2 "Methodology" with numbered list
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    blocks = _split_into_blocks(body)

    # Extract taxonomy (bullet list under "taxonomy" H2)
    relationship_taxonomy: list[dict[str, str]] = []
    workflow_steps: list[str] = []
    preserved_tags: list[dict[str, str]] = []
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for kind, content in blocks:
        if kind == "h2":
            if current is not None:
                sections.append(current)
            current = {"heading": content, "blocks": []}
        elif current is not None:
            current["blocks"].append({"kind": kind, "content": content})

            # Extract specific structured fields
            h_lower = current["heading"].lower()
            if "taxonomy" in h_lower and kind == "bullet_list":
                for line in content.splitlines():
                    m = re.match(r"^-\s+\*\*(\w[\w\s\-]*?)\*\*[:\s]+(.*)$", line.strip())
                    if m:
                        relationship_taxonomy.append(
                            {
                                "code": m.group(1).strip(),
                                "name": m.group(1).strip(),
                                "description": m.group(2).strip(),
                            }
                        )
            if "use" in h_lower and kind == "numbered_list":
                for line in content.splitlines():
                    m = re.match(r"^\d+\.\s+(.*)$", line.strip())
                    if m:
                        workflow_steps.append(m.group(1))
    if current is not None:
        sections.append(current)

    # Preserved HTML comment tags
    for m in re.finditer(r"<!--\s*(\w+):\s*([^>]+?)\s*-->", body):
        tag_kind = m.group(1)
        tag_value = m.group(2).strip()
        if tag_kind in ("pair", "emergent", "participants"):
            preserved_tags.append({"kind": tag_kind, "value": tag_value})

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{path.stem}"),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "frontmatter": fm,
        "relationship_taxonomy": relationship_taxonomy,
        "taxonomy_count": len(relationship_taxonomy),
        "workflow_steps": workflow_steps,
        "preserved_tags": preserved_tags,
        "sections": sections,
        "section_count": len(sections),
        "raw_md": body,  # zero-loss
        "raw_md_kept_reason": "audit_fallback_for_zero_loss_invariant",
    }


# ─── Fase 1: crossregulation/_templates/TEMPLATE_crossreg_brief.json ──


def parse_crossregulation_brief_template(path: Path) -> dict[str, Any]:
    """Parse the crossregulation sub-agent brief template.

    Same structure as subagent_brief_template but with crossregulation
    specific fields (preserved_tags list).
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    blocks = _split_into_blocks(body)

    mission = ""
    for kind, content in blocks:
        if kind == "blockquote":
            mission = content
            break

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for kind, content in blocks:
        if kind == "h2":
            if current is not None:
                sections.append(current)
            m_num = re.match(r"^(\d+)\.\s+(.+)$", content)
            current = {
                "number": int(m_num.group(1)) if m_num else None,
                "heading": m_num.group(2) if m_num else content,
                "blocks": [],
            }
        elif current is not None:
            current["blocks"].append({"kind": kind, "content": content})
    if current is not None:
        sections.append(current)

    constraints_section = next((s for s in sections if "constraint" in s["heading"].lower()), None)
    constraints: list[dict[str, Any]] = []
    if constraints_section:
        for blk in constraints_section["blocks"]:
            if blk["kind"] == "numbered_list":
                for line in blk["content"].splitlines():
                    m = re.match(r"^\d+\.\s+(.*)$", line.strip())
                    if m:
                        constraints.append({"text": m.group(1)})

    # Preserved tags mentioned in the constraints
    preserved_tags: list[dict[str, str]] = []
    for m in re.finditer(r"<!--\s*(\w+):\s*([^>]+?)\s*-->", body):
        tag_kind = m.group(1)
        tag_value = m.group(2).strip()
        if tag_kind in ("pair", "emergent", "participants"):
            preserved_tags.append({"kind": tag_kind, "value": tag_value})

    bullet_lists: list[dict[str, Any]] = []
    for s in sections:
        for blk in s["blocks"]:
            if blk["kind"] == "bullet_list":
                items = []
                for line in blk["content"].splitlines():
                    m = re.match(r"^-\s+(.*)$", line.strip())
                    if m:
                        items.append(m.group(1))
                if items:
                    bullet_lists.append(
                        {
                            "section_number": s["number"],
                            "section_heading": s["heading"],
                            "items": items,
                        }
                    )

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{path.stem}"),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "frontmatter": fm,
        "purpose": fm.get("purpose", ""),
        "usage": fm.get("usage", ""),
        "mission": mission,
        "constraints": constraints,
        "constraint_count": len(constraints),
        "preserved_tags": preserved_tags,
        "bullet_lists": bullet_lists,
        "sections": sections,
        "raw_md": body,  # zero-loss
        "raw_md_kept_reason": "audit_fallback_for_zero_loss_invariant",
    }


# ─── Table helper ──────────────────────────────────────────────────────


def _extract_table_rows_from_block(table_block_text: str) -> list[list[str]]:
    """Parse a table block (markdown) into a list of rows.

    Returns the header row + data rows. Drops the separator line.
    """
    rows: list[list[str]] = []
    for line in table_block_text.splitlines():
        row = _parse_table_row(line)
        if row is None:
            continue
        if _is_table_separator(line):
            continue
        rows.append(row)
    return rows


# ─── DomainAnalysis pair granularity helpers (CORR-PILOT-DA) ───────────
#
# DomainAnalysis files use a different pair format than DeepAnalysis:
#   1. `<!-- pair: REG_A,REG_B --> ... <!-- /pair -->` markers wrap each pair
#   2. Inside, a 3-column table:
#        | REG_A ↔ REG_B | **Classification** | Tension/difference |
#        | **REG_A** (SR-X, Art. Y) | description | scope/angle |
#        | **REG_B** (SR-X, Art. Y) | description | scope/angle |
#   3. A `**Why CLASSIFICATION (qualifier)**: PARAGRAPH` block follows
#   4. NO blockquoted OJ article — the table cell IS the OJ quote (synthesis)
#   5. NO `**Scope-disjoint test:**` — the verdict is encoded in the
#      classification and the (qualifier) of the Why header
#
# Because the structure differs, we have DA-specific helpers. The DeepAnalysis
# helpers (_extract_oj_quotes_verbatim, _extract_comparison_sections, etc.)
# are NOT reused because their regexes assume `**REG article (...):**`
# headers and `> blockquote` lines that DA files don't have.


# Canonical classification normalization. The MD source uses inconsistent
# casing ("Complementary" vs "complementary") and inconsistent naming
# ("Different perspective" vs "different-perspective"). We canonicalize to
# 4 labels: Complementary, Equal, Different perspective, Contradictory.
_DA_CLASS_CANONICAL: dict[str, str] = {
    "complementary": "Complementary",
    "equal": "Equal",
    "different perspective": "Different perspective",
    "different-perspective": "Different perspective",
    "contradictory": "Contradictory",
    # already-canonical (uppercase first letter)
    "complementary ": "Complementary",  # trailing-space safety
}


def _canonicalize_classification(raw: str) -> str:
    """Map a raw classification string to its canonical form.

    The MD has "complementary" / "Complementary" / "equal" / "Equal" /
    "different-perspective" / "Different perspective" / "contradictory"
    (the only 4 valid verdicts, in canonical form).
    """
    if not raw:
        return ""
    key = raw.strip().lower()
    if key in _DA_CLASS_CANONICAL:
        return _DA_CLASS_CANONICAL[key]
    # Unknown verdict — return as-is (caller will surface as a test failure
    # so the inventory is auditable).
    return raw.strip()


def _extract_why_metadata(block_text: str) -> dict[str, str]:
    """Extract the `**Why CLASSIFICATION (qualifier)**: PARAGRAPH` block.

    Returns:
      - classification: canonical label (Complementary/Equal/...)
      - qualifier: the text in parens, e.g. "with structural differences"
        (may be empty string if no qualifier)
      - note: the prose paragraph after the colon
      - raw_header: the full `**Why CLASSIFICATION (qualifier)**` text
        verbatim (for audit / zero-loss)

    The classification is taken from the Why header (the table cell
    carries the same verdict — they are always identical in DA files).
    """
    # Match "**Why <verdict> (qualifier)**: PARAGRAPH" or "**Why <verdict>**: PARAGRAPH"
    m = re.search(
        r"\*\*Why\s+([^*]+?)\*\*\s*:\s*([^\n]+(?:\n(?!\s*<!--|\s*\*\*)[^\n]+)*)",
        block_text,
    )
    if not m:
        return {
            "classification": "",
            "qualifier": "",
            "note": "",
            "raw_header": "",
        }
    header = m.group(1).strip()
    note = m.group(2).strip()
    # The header may be "complementary (with timeline overlap)",
    # "complementary + partial overlap", or "equal for financial
    # entities" — split verdict from qualifier. Strategy:
    #   1. Try parenthesized form: "verdict (qualifier)"
    #   2. Try "verdict + qualifier"
    #   3. Try "verdict <space> for|with|when|on|in|across <...>"
    #   4. Fall back to whole header as verdict (no qualifier)
    qual_m = re.match(r"^([\w\- ]+?)\s*\(([^)]+)\)\s*$", header)
    if qual_m:
        verdict = _canonicalize_classification(qual_m.group(1))
        qualifier = qual_m.group(2).strip()
    else:
        plus_m = re.match(r"^([\w\- ]+?)\s+\+\s+(.+)$", header)
        if plus_m:
            verdict = _canonicalize_classification(plus_m.group(1))
            qualifier = plus_m.group(2).strip()
        else:
            # "verdict <filler-word> <rest>" — the 4 canonical verdicts
            # are single-word. The filler words we accept: for, with,
            # when, on, in, across, given, under, where, plus.
            split_m = re.match(
                r"^(\w+(?:[\-]\w+)?)\s+(for|with|when|on|in|across|"
                r"given|under|where|plus)\b\s*(.*)$",
                header,
                re.IGNORECASE,
            )
            if split_m:
                verdict = _canonicalize_classification(split_m.group(1))
                rest = split_m.group(3).strip()
                qualifier = (
                    f"{split_m.group(2).lower()} {rest}".strip()
                    if rest
                    else split_m.group(2).lower()
                )
            else:
                verdict = _canonicalize_classification(header)
                qualifier = ""
    return {
        "classification": verdict,
        "qualifier": qualifier,
        "note": note,
        "raw_header": f"Why {header}",
    }


def _extract_oj_quotes_from_table(block_text: str) -> list[dict[str, Any]]:
    """Extract the 2 OJ-quote cells from a DomainAnalysis pair table.

    DA pair block has structure (inside `<!-- pair -->` markers):
        | GDPR ↔ NIS2 | **Complementary** | Tension/difference |
        | **GDPR** (SR-GDPR-001, Art. 32(1)(a)/(b)) | description | scope |
        | **NIS2** (SR-NIS2-001, Art. 21(2)(h)) | description | scope |

    We return one entry per data row (i.e. 2 entries per pair), with:
      - regulation: bold name from col 0 (e.g. "GDPR")
      - citation_raw: text inside the parens (e.g. "SR-GDPR-001, Art. 32(1)(a)/(b)")
      - sr_id: first SR-XXX-NNN matched in citation
      - article: first Art. NN(...) matched
      - annex: first Annex NN matched
      - description: column 1 verbatim
      - scope: column 2 verbatim
    """
    out: list[dict[str, Any]] = []
    # Find the first table block inside the pair body
    table_re = re.compile(
        r"^\s*\|(.+)\|\s*$\n^\s*\|[\s\-:|]+\|\s*$\n((?:^\s*\|.+\|\s*$\n?)+)",
        re.MULTILINE,
    )
    tm = table_re.search(block_text)
    if not tm:
        return out
    rows_raw = tm.group(2).strip().splitlines()
    for row_line in rows_raw:
        row = _parse_table_row(row_line)
        if row is None or len(row) < 2:
            continue
        # First column starts with **REG** (citation)
        col0 = row[0]
        m_oj = re.match(r"^\s*\*\*\s*(\w+)\*\*\s*\(((?:[^()]|\([^)]*\))+)\)", col0)
        if not m_oj:
            continue
        regulation = m_oj.group(1).strip()
        citation = m_oj.group(2).strip()
        sr_m = re.search(r"(SR-[\w\-]+)", citation)
        art_m = re.search(r"(Art(?:icle)?\.?\s*\d+(?:\([^)]+\))*)", citation)
        annex_m = re.search(r"(Annex\s+[IVX]+)", citation)
        out.append(
            {
                "regulation": regulation,
                "citation_raw": citation,
                "sr_id": sr_m.group(1) if sr_m else None,
                "article": art_m.group(1).strip() if art_m else None,
                "annex": annex_m.group(1) if annex_m else None,
                "description": row[1] if len(row) > 1 else "",
                "scope": row[2] if len(row) > 2 else "",
            }
        )
    return out


def _extract_comparison_sections_domain(
    block_text: str, reg_a: str, reg_b: str
) -> list[dict[str, Any]]:
    """Build a 2-axis comparison structure for a DomainAnalysis pair.

    The DA pair table has 3 columns:
      col 0: "**REG** (citation)"
      col 1: 1-line description of the obligation
      col 2: scope/angle (entity type, actor, OJ-literal phrases)

    We model the comparison as 2 axes:
      - "obligation"  (col 1): reg_a_value / reg_b_value
      - "scope"       (col 2): reg_a_value / reg_b_value

    Plus a third axis (optional) when the Why block carries a clear
    "comparison trigger" (e.g. timeline anchor mentioned in the note).
    """
    rows = _extract_oj_quotes_from_table(block_text)
    reg_a_row = next((r for r in rows if r["regulation"] == reg_a), None)
    reg_b_row = next((r for r in rows if r["regulation"] == reg_b), None)
    if not reg_a_row or not reg_b_row:
        return []
    return [
        {
            "axis": "obligation",
            "reg_a_value": reg_a_row["description"],
            "reg_b_value": reg_b_row["description"],
        },
        {
            "axis": "scope",
            "reg_a_value": reg_a_row["scope"],
            "reg_b_value": reg_b_row["scope"],
        },
    ]


# ─── Fase 2: crossregulation/D-XX_*/ per-subdomain ───────────────────


def parse_crossregulation_subdomain(
    path: Path, sub_kind: str = "domain_analysis"
) -> dict[str, Any]:
    """Parse a crossregulation per-subdomain file (DomainAnalysis or
    DeepAnalysis for one D-XX.Y).

    Structure of the raw_md:
      - blockquote with a link to the sibling deep-analysis file
      - H3 "D-XX.Y Name"
      - HTML comment `<!-- participants: REG1, REG2, ... -->`
      - H4 "Participants" + table (Regulation | SO ID | summary | scope)
      - H4 "Pairwise matrix"
      - For each pair:
          `<!-- pair: REG_A,REG_B -->` ...
          table with REG_A row + REG_B row + Why paragraph
          `<!-- /pair -->`
      - Optional H4 "Emergent tensions" with `<!-- emergent: ... -->`
      - Optional H4 "Cross-validation" with SR cross-refs

    Output adds:
      - participants[]: rows of the participants table
      - pairs[]: one entry per `<!-- pair: -->` block, with
        {reg_a, reg_b, classification, why, oj_quotes[],
        table_block_raw} (the verbatim table for audit)
      - emergent_tensions[]: from `<!-- emergent: -->` markers
      - sr_cross_references[]: extracted SR-XXX-NNN references

    **Zero-loss:** raw_md is preserved verbatim AND all extracted
    fields contain the verbatim text from the source.
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    blocks = _split_into_blocks(body)

    # Extract title_h3 (the first H3)
    title = ""
    for kind, content in blocks:
        if kind == "h3":
            title = content
            break

    # Extract participants from the "<!-- participants: ... -->" comment
    # (legacy — keep the raw split for backward-compat with consumers
    # that read participants_meta as a list of strings).
    participants_meta: list[str] = []
    m_part = re.search(r"<!--\s*participants:\s*([^>]+?)\s*-->", body)
    if m_part:
        participants_meta = [r.strip() for r in m_part.group(1).split(",")]

    # CORR-PILOT: DeepAnalysis files do NOT have an H4 "Participants" table —
    # they carry participants in the HTML comment + the bold prose paragraph.
    # We extract structured fields for both kinds (DomainAnalysis keeps
    # the H4 table path; DeepAnalysis fills the new structured fields).
    participants_info = _extract_participants_from_deep(body)
    if sub_kind == "deep_analysis" and not participants_info["participants"]:
        # Fallback to the comment split if the helper found nothing
        participants_info["participants"] = [
            _deep_norm_reg(r) for r in participants_meta
        ]

    # Extract participants table (after H4 "Participants")
    participants_table: list[dict[str, str]] = []
    in_participants_table = False
    for kind, content in blocks:
        if kind == "h4" and "participant" in content.lower():
            in_participants_table = True
            continue
        if in_participants_table:
            if kind in ("h2", "h3", "h4"):
                in_participants_table = False
            elif kind == "table":
                rows = _extract_table_rows_from_block(content)
                if len(rows) >= 2:
                    for r in rows[1:]:  # skip header
                        if len(r) < 2:
                            continue
                        participants_table.append(
                            {
                                "regulation": r[0],
                                "so_id": r[1] if len(r) > 1 else "",
                                "summary": r[2] if len(r) > 2 else "",
                                "scope": r[3] if len(r) > 3 else "",
                            }
                        )

    # Extract pair blocks (split body by `<!-- pair: REG_A,REG_B -->` ... `<!-- /pair -->`)
    pairs: list[dict[str, Any]] = []
    # Use a stateful scan: find each <!-- pair: --> and matching <!-- /pair -->
    pair_open_re = re.compile(r"<!--\s*pair:\s*([\w,\s]+?)\s*-->")
    pair_close_re = re.compile(r"<!--\s*/pair\s*-->")
    pos = 0
    while pos < len(body):
        open_m = pair_open_re.search(body, pos)
        if not open_m:
            break
        regs = [r.strip() for r in open_m.group(1).split(",")]
        if len(regs) != 2:
            pos = open_m.end()
            continue
        close_m = pair_close_re.search(body, open_m.end())
        if not close_m:
            break
        block_text = body[open_m.end() : close_m.start()].strip()
        # Extract classification (first ** word after the table)
        classification = ""
        m_class = re.search(
            r"\*\*\s*(\w[\w\-]*)\s*\*\*",
            block_text,
        )
        if m_class:
            classification = m_class.group(1).strip()
        # Extract "Why" paragraph
        why = ""
        m_why = re.search(
            r"\*\*Why\s+[^*]+\*\*\s*:\s*([^\n]+(?:\n(?!\s*<!--)[^\n]+)*)",
            block_text,
        )
        if m_why:
            why = m_why.group(1).strip()
        # Extract OJ quotes — patterns like "SR-XXX-NNN, Art. NN" or "Annex II §8"
        oj_quotes: list[dict[str, str]] = []
        # Match **REG** (citation) — citation can contain balanced parens
        # by using a non-greedy match that handles nested parens
        for m_oj in re.finditer(
            r"\*\*\s*(\w+)\*\*\s*\(((?:[^()]|\([^)]*\))+)\)",
            block_text,
        ):
            regulation = m_oj.group(1).strip()
            citation = m_oj.group(2).strip()
            # Parse citation into {article, sr_id}
            sr_m = re.search(r"(SR-[\w\-]+)", citation)
            # Article: "Art. NN(N)(letter)" or "Art. NN(N)" — handle nested
            art_m = re.search(
                r"(Art(?:icle)?\.?\s*\d+(?:\([^)]+\))*)",
                citation,
            )
            annex_m = re.search(r"(Annex\s+[IVX]+)", citation)
            oj_quotes.append(
                {
                    "regulation": regulation,
                    "citation_raw": citation,
                    "sr_id": sr_m.group(1) if sr_m else None,
                    "article": art_m.group(1).strip() if art_m else None,
                    "annex": annex_m.group(1) if annex_m else None,
                }
            )
        # Extract the table block raw
        table_block_raw = ""
        sub_blocks = _split_into_blocks(block_text)
        for bk, bv in sub_blocks:
            if bk == "table":
                table_block_raw = bv
                break
        # CORR-PILOT-DA: enrich DomainAnalysis pair with the same
        # granularity fields as DeepAnalysis (so consumers can read both
        # kinds uniformly). The Why metadata gives the canonical
        # classification + qualifier; the table-extracted quotes give
        # per-regulation verbatim description + scope; the comparison
        # sections synthesize a 2-axis structure (obligation + scope).
        why_meta = _extract_why_metadata(block_text)
        canonical_class = why_meta["classification"] or _canonicalize_classification(
            classification
        )
        oj_quotes_table = _extract_oj_quotes_from_table(block_text)
        comparison_sections = _extract_comparison_sections_domain(
            block_text, regs[0], regs[1]
        )
        # Build oj_quotes_verbatim from the table rows (DA has no blockquote
        # — the description cell IS the synthesized OJ quote)
        oj_quotes_verbatim = [
            {
                "regulation": q["regulation"],
                "header": f"{q['regulation']} ({q['citation_raw']})",
                "verbatim": q["description"],
                "sr_ids": [q["sr_id"]] if q["sr_id"] else [],
                "articles": [q["article"]] if q["article"] else [],
                "annexes": [q["annex"]] if q["annex"] else [],
            }
            for q in oj_quotes_table
        ]
        # Scope-disjoint test: derive a verdict from the canonical
        # classification. DA doesn't have a dedicated section, so we map:
        #   Complementary  -> "Y"  (they co-exist in scope)
        #   Equal          -> "Y"  (same scope)
        #   Different perspective -> "N" (scope-disjoint by definition)
        #   Contradictory  -> "Conditional" (scope overlaps but
        #                      obligation conflicts — binding-procedure
        #                      applies)
        _verdict_map = {
            "Complementary": "Y",
            "Equal": "Y",
            "Different perspective": "N",
            "Contradictory": "Conditional",
        }
        scope_disjoint = {
            "verdict": _verdict_map.get(canonical_class, ""),
            "note": why_meta.get("qualifier", "")
            or f"derived_from_classification:{canonical_class}",
        }
        # downstream_implication: look for an H4 "Downstream implication"
        # in the file body (it's a top-level section, not a per-pair
        # field). For per-pair downstream notes, we use the qualifier +
        # the first sentence of why_meta["note"].
        downstream_implication = why_meta["note"][:200] if why_meta["note"] else ""
        p0_notes = _extract_p0_notes(block_text)
        sr_ids_per_pair = sorted(set(_SR_RE.findall(block_text)))
        pairs.append(
            {
                "reg_a": regs[0],
                "reg_b": regs[1],
                "classification": canonical_class or classification,
                "why": why,
                "why_qualifier": why_meta.get("qualifier", ""),
                "why_note": why_meta.get("note", ""),
                "oj_quotes": oj_quotes,
                "oj_quotes_verbatim": oj_quotes_verbatim,
                "comparison_sections": comparison_sections,
                "scope_disjoint_test": scope_disjoint,
                "downstream_implication": downstream_implication,
                "p0_notes": p0_notes,
                "sr_ids_per_pair": sr_ids_per_pair,
                "table_block_raw": table_block_raw,
                "block_text_raw": block_text,
            }
        )
        pos = close_m.end()

    # ─── DeepAnalysis pair extraction (legacy format) ───────────────
    # DeepAnalysis files use H4 headings like ``#### Pair: GDPR ↔ NIS2``
    # without the ``<!-- pair: ... --><!-- /pair -->`` markers. We extract
    # them by scanning H4 blocks and treating the body until the next
    # H2/H3/H4 as the pair body. The set of pairs we extract this way
    # augments the comment-marker set above; duplicates are deduped by
    # (reg_a, reg_b) at the end of the function.
    h4_pair_re = re.compile(r"^#{4}\s+Pair:\s+(.+?)\s*$", re.MULTILINE)
    # CORR-PILOT: include H4 in the boundary regex so consecutive pair
    # blocks don't merge (the old regex used H2/H3 only, which caused
    # every pair's block_text to swallow all subsequent pairs until the
    # next H2/H3 — that masked the granularity in oj_quotes_verbatim and
    # comparison_sections).
    h2_h3_h4_re = re.compile(r"^#{2,4}\s+", re.MULTILINE)
    for h4_m in h4_pair_re.finditer(body):
        header_text = h4_m.group(1).strip()
        # Parse "REG_A ↔ REG_B" (or "REG_A vs REG_B", or comma-separated)
        regs: list[str] = []
        if "↔" in header_text:
            regs = [r.strip() for r in header_text.split("↔")]
        elif " vs " in header_text.lower():
            regs = [r.strip() for r in re.split(r"\s+vs\s+", header_text, flags=re.IGNORECASE)]
        elif "," in header_text and len(header_text.split(",")) == 2:
            regs = [r.strip() for r in header_text.split(",")]
        if len(regs) != 2:
            continue
        # CORR-PILOT: skip "omitted" pairs. The MD may list pair headers
        # like "#### Pair: GDPR ↔ AI_Act (omitted — AI Act not in D-08.1
        # participants)" to document an explicit non-analysis. These are
        # NOT real pairs — they have no body, no OJ quotes, and would
        # pollute the JSON. Filter them out here.
        if re.search(r"\bomitted\b", header_text, re.IGNORECASE):
            continue
        # Also skip headers where one reg is the placeholder
        # "[not in CRDA D-XX.Y]" — these are explicit "no analysis" markers.
        if any("[not in" in r for r in regs):
            continue
        # CORR-PILOT: canonicalize reg_a / reg_b so NIS 2 -> NIS2, AI Act -> AI_Act
        reg_a = _deep_norm_reg(regs[0])
        reg_b = _deep_norm_reg(regs[1])
        # Determine block end: next H2/H3/H4 or EOF
        next_boundary = h2_h3_h4_re.search(body, h4_m.end())
        block_end = next_boundary.start() if next_boundary else len(body)
        block_text = body[h4_m.end():block_end].strip()
        # Extract classification (first ** word) — DeepAnalysis uses phrases
        # like **COMPLEMENTARY**, **SAME — COMPLEMENTARY**, **TENSION** etc.
        classification = ""
        m_class = re.search(r"\*\*\s*(\w[\w\-]*(?:\s*[—-]\s*\w[\w\-]*)*)\s*\*\*", block_text)
        if m_class:
            classification = m_class.group(1).strip()
        # Extract "Why" / "Reasoning" paragraph (DeepAnalysis may have either)
        why = ""
        m_why = re.search(
            r"\*\*Why\s+[^*]+\*\*\s*:\s*([^\n]+(?:\n(?!\s*\*\*)[^\n]+)*)",
            block_text,
        )
        if not m_why:
            m_why = re.search(
                r"\*\*[^*]*Reasoning[^*]*\*\*\s*[:\.]?\s*([^\n]+(?:\n(?!\s*\*\*)[^\n]+)*)",
                block_text,
            )
        if m_why:
            why = m_why.group(1).strip()
        # Extract OJ quotes (same pattern as comment-marker pairs)
        oj_quotes = []
        for m_oj in re.finditer(
            r"\*\*\s*(\w+)\*\*\s*\(((?:[^()]|\([^)]*\))+)\)",
            block_text,
        ):
            regulation = m_oj.group(1).strip()
            citation = m_oj.group(2).strip()
            sr_m = re.search(r"(SR-[\w\-]+)", citation)
            art_m = re.search(r"(Art(?:icle)?\.?\s*\d+(?:\([^)]+\))*)", citation)
            annex_m = re.search(r"(Annex\s+[IVX]+)", citation)
            oj_quotes.append(
                {
                    "regulation": regulation,
                    "citation_raw": citation,
                    "sr_id": sr_m.group(1) if sr_m else None,
                    "article": art_m.group(1).strip() if art_m else None,
                    "annex": annex_m.group(1) if annex_m else None,
                }
            )
        # CORR-PILOT: DeepAnalysis structured extraction
        oj_quotes_verbatim = _extract_oj_quotes_verbatim(block_text)
        comparison_sections = _extract_comparison_sections(block_text)
        relationship_pair = _extract_relationship_pair(block_text)
        scope_disjoint = _extract_scope_disjoint_test(block_text)
        downstream_implication = _extract_labeled_value(
            block_text, "Downstream implication"
        )
        p0_notes = _extract_p0_notes(block_text)
        # SR-IDs that appear inside THIS pair's body (not the whole file)
        sr_ids_per_pair = sorted(set(_SR_RE.findall(block_text)))
        pairs.append(
            {
                "reg_a": reg_a,
                "reg_b": reg_b,
                "header_text": header_text,
                "classification": classification,
                "classified_relationship_crda": relationship_pair[
                    "classified_relationship_crda"
                ],
                "verified_relationship_oj": relationship_pair[
                    "verified_relationship_oj"
                ],
                "why": why,
                "oj_quotes": oj_quotes,
                "oj_quotes_verbatim": oj_quotes_verbatim,
                "comparison_sections": comparison_sections,
                "scope_disjoint_test": scope_disjoint,
                "downstream_implication": downstream_implication,
                "p0_notes": p0_notes,
                "sr_ids_per_pair": sr_ids_per_pair,
                "table_block_raw": "",
                "block_text_raw": block_text,
            }
        )

    # Extract emergent tensions from `<!-- emergent: REG1,REG2,REG3 -->`
    emergent_tensions: list[dict[str, Any]] = []
    for m_em in re.finditer(r"<!--\s*emergent:\s*([^>]+?)\s*-->", body):
        regs = [r.strip() for r in m_em.group(1).split(",")]
        emergent_tensions.append(
            {
                "regulations": regs,
                "verbatim": m_em.group(0),
            }
        )

    # Extract SR-XXX-NNN cross-references
    sr_cross_references: list[str] = []
    for m_sr in re.finditer(r"SR-[A-Z_]+-\d{3}", body):
        sr_id = m_sr.group(0)
        if sr_id not in sr_cross_references:
            sr_cross_references.append(sr_id)

    # CORR-PILOT-DA: extract the top-level "Downstream implication" and
    # "SR cross-validation" H4 sections (these are file-level, not per
    # pair). The Downstream implication in DA files describes the
    # sub-domain's overall implication for Phase 1C Doc 07; the SR
    # cross-validation lists the NIST CSF mapping + supplementary layer.
    # In DA files these appear as `#### Downstream implication\n<text>` or
    # `#### SR cross-validation\n<text>`; in DeepAnalysis the same content
    # is per-pair (in each pair block) so we only need this for DA.
    def _extract_h4_section(text: str, heading: str) -> str:
        """Extract the body of an H4 section. Looks for
        `#### <heading>\\n<body until next H4 or EOF>` — we stop at H4
        only (not H2/H3) because a nested H4 inside another H4-section
        would otherwise eat content meant for the outer section.
        """
        # Match `#### <heading>` (case-insensitive) on its own line, then
        # capture everything until the next H4 (or EOF). If the section
        # has no H4 closer (i.e. it's the last section in the file),
        # capture to EOF.
        pattern = re.compile(
            rf"^####\s+{re.escape(heading)}\s*$\n(.*?)(?=^####\s|\Z)",
            re.MULTILINE | re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
        # Fallback: maybe it's bold-inline (DeepAnalysis style)
        return _extract_labeled_value(text, heading)

    downstream_implication_top = _extract_h4_section(
        body, "Downstream implication"
    )
    sr_cross_validation = _extract_h4_section(body, "SR cross-validation")
    classification_distribution: dict[str, int] = {}
    for p in pairs:
        cls = p.get("classification") or "(empty)"
        classification_distribution[cls] = (
            classification_distribution.get(cls, 0) + 1
        )

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-CRDA-{path.stem}"),
        "sub_kind": sub_kind,
        "macro_domain": fm.get("macro_domain", ""),
        "sub_domain": fm.get("sub_domain", ""),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "frontmatter": fm,
        "title_h3": title,
        "participants_meta": participants_meta,
        "participants_table": participants_table,
        "participant_count": len(participants_table),
        # CORR-PILOT: structured participants (DeepAnalysis has no H4 table)
        "participants": participants_info["participants"],
        "participants_absent": participants_info["participants_absent"],
        "participants_note": participants_info["participants_note"],
        # Dedup pairs by (reg_a, reg_b) — symmetric so we sort the tuple
        "pairs": _dedup_pairs(pairs),
        "pair_count": len(_dedup_pairs(pairs)),
        # CORR-PILOT-DA: top-level fields derived from the pairs
        "classification_distribution": classification_distribution,
        "downstream_implication_top": downstream_implication_top,
        "sr_cross_validation": sr_cross_validation,
        "emergent_tensions": emergent_tensions,
        "sr_cross_references": sr_cross_references,
        "sr_cross_reference_count": len(sr_cross_references),
        "raw_md": body,  # zero-loss
        "raw_md_kept_reason": "audit_fallback_for_zero_loss_invariant",
    }


# ─── DeepAnalysis granularity helpers (CORR-PILOT) ────────────────────
#
# Source-of-truth for _REG_NORMALIZE is scripts/preprocess/parsers/entities/
# subdomain.py. We duplicate the 5-row alias map here to avoid a hard
# import cycle (narrative.py is loaded before entities/subdomain.py in some
# CLI paths). If a new regulation is onboarded, update BOTH tables.
# See AGENTS.md §11.7.
_DEEP_REG_NORMALIZE: dict[str, str] = {
    "CRA": "CRA",
    "GDPR": "GDPR",
    "NIS 2": "NIS2",
    "NIS2": "NIS2",
    "NIS_2": "NIS2",
    "DORA": "DORA",
    "AI Act": "AI_Act",
    "AI_Act": "AI_Act",
    "AIACT": "AI_Act",
    "AIA": "AI_Act",
    "AI": "AI_Act",
}


def _deep_norm_reg(label: str) -> str:
    """Canonicalize a regulation label to its short form (CRA, GDPR, ...)."""
    s = label.strip().rstrip(",.;:")
    return _DEEP_REG_NORMALIZE.get(s, s)


# Pre-compiled regexes used by the DeepAnalysis pair extractor.
# Keep them module-level so the pair loop stays fast.
_DEEP_HEADER_RE = re.compile(
    r"^(\d+)\.\s+\*\*([^*]+?)\*\*\s*:\s*([^\n]+?)\s*$",
    re.MULTILINE,
)
# Match a bullet like "- GDPR trigger: continuous..." — we use this inside
# comparison sections to split "reg_a_value" from "reg_b_value" and
# catch the "Trigger alignment: SAME" / "Tension: NONE" / "Scope overlap: Y"
# trailing lines.
_BULLET_RE = re.compile(r"^\s*-\s+([^\n]+)$", re.MULTILINE)
_SR_RE = re.compile(r"SR-[A-Z_]+-\d{3}")
_ART_RE = re.compile(r"Art(?:icle)?\.?\s*\d+(?:\([^)]+\))*")
_ANNEX_RE = re.compile(r"Annex\s+[IVX]+(?:\s+Part\s+[IVX]+)?")
# Strip leading "- " / "1. " from bullets
_LEAD_DASH_RE = re.compile(r"^\s*[-*+]\s+")
_LEAD_NUM_RE = re.compile(r"^\s*\d+\.\s+")


def _extract_oj_quotes_verbatim(block_text: str) -> list[dict[str, Any]]:
    """Extract OJ verbatim quotes from a DeepAnalysis pair block.

    A DeepAnalysis pair block has structure::

        **GDPR article (verbatim from SR-GDPR-001, Art. 5(1)(f) + Art. 32(1)(a)/(b)):**
        > Art. 5(1)(f) integrity and confidentiality …

        **NIS 2 article (verbatim from SR-NIS2-001, Art. 21(2)(h)):**
        > Article 21(2)(h) of Directive (EU) 2022/2555 (NIS2) …

    We return one entry per (header, blockquote) pair, with the
    regulation normalized, all SR-IDs / articles / annexes extracted
    from both the header line AND the verbatim text.
    """
    out: list[dict[str, Any]] = []
    # Split on bold "**REG article (verbatim ...):**" lines. Capture the
    # FULL header line (including the parenthetical citation) so we can
    # extract SR-IDs / articles / annexes from it.
    header_re = re.compile(
        r"^\*\*\s*([^*\n]+?)\s*:\*\*\s*$",
        re.MULTILINE,
    )
    headers = list(header_re.finditer(block_text))
    # Filter to "**X article (...):**" only (skip unrelated bold headers)
    article_header_re = re.compile(
        r"\barticle\b\s*\(",
        re.IGNORECASE,
    )
    article_headers = [h for h in headers if article_header_re.search(h.group(1))]
    for idx, h in enumerate(article_headers):
        full_header = h.group(1).strip()
        # The regulation name is the first 1-2 tokens BEFORE the word
        # "article" (e.g. "GDPR", "NIS 2", "CRA", "DORA", "AI Act").
        # We deliberately stop at "article" to avoid capturing it.
        reg_m = re.match(
            r"^((?:\S+\s+){0,2}\S+?)\s+article\b",
            full_header,
            re.IGNORECASE,
        )
        reg_label = reg_m.group(1).strip() if reg_m else full_header.split()[0]
        # Find the blockquote(s) immediately following this header
        bq_start = h.end()
        bq_end = (
            article_headers[idx + 1].start()
            if idx + 1 < len(article_headers)
            else len(block_text)
        )
        segment = block_text[bq_start:bq_end]
        # Collect contiguous blockquote lines
        bq_lines: list[str] = []
        for line in segment.splitlines():
            stripped = line.strip()
            if not stripped:
                if bq_lines:
                    break
                continue
            m = _BLOCKQUOTE_RE.match(stripped)
            if not m:
                break
            bq_lines.append(m.group(1))
        if not bq_lines:
            continue
        verbatim = " ".join(bq_lines).strip()
        # Extract IDs from BOTH header and verbatim
        all_text = full_header + " " + verbatim
        sr_ids = sorted(set(_SR_RE.findall(all_text)))
        articles = sorted(set(_ART_RE.findall(all_text)))
        annexes = sorted(set(_ANNEX_RE.findall(all_text)))
        out.append(
            {
                "regulation": _deep_norm_reg(reg_label),
                "header": f"{full_header}:",
                "verbatim": verbatim,
                "sr_ids": sr_ids,
                "articles": articles,
                "annexes": annexes,
            }
        )
    return out


def _extract_comparison_sections(block_text: str) -> list[dict[str, Any]]:
    """Extract the 5 canonical comparison sections from a DeepAnalysis
    pair block.

    The five axes (in canonical order) are:
      - scope
      - trigger
      - threshold_timeline
      - recipient
      - content_template

    Each axis is introduced by ``**Axis comparison:**`` followed by
    bullets. Some axes carry a trailing one-liner marker (e.g.
    "Trigger alignment: SAME", "Tension: NONE", "Scope overlap: Y").
    We capture those in ``<axis>_<marker>`` fields.
    """
    out: list[dict[str, Any]] = []
    # Match a section header like "**Scope comparison:**"
    section_re = re.compile(
        r"\*\*\s*(Scope|Trigger|Threshold/timeline|Recipient|Content template)"
        r"\s+comparison\s*:\*\*\s*",
        re.MULTILINE | re.IGNORECASE,
    )
    sections = list(section_re.finditer(block_text))
    # Map axis name -> canonical key + marker field suffix
    axis_map = {
        "scope": ("scope", "scope_overlap", "scope_overlap_note"),
        "trigger": ("trigger", "trigger_alignment", "trigger_alignment_note"),
        "threshold/timeline": (
            "threshold_timeline",
            "tension",
            "tension_note",
        ),
        "recipient": ("recipient", None, None),
        "content template": ("content_template", None, None),
    }
    # Display-name -> marker label as it appears in the MD (for the
    # trailing one-liner after the bullets).
    marker_label_map = {
        "scope": "scope overlap",
        "trigger": "trigger alignment",
        "threshold/timeline": "tension",
    }
    for idx, s in enumerate(sections):
        axis_display = s.group(1).strip()
        axis_key, marker_key, marker_note_key = axis_map[axis_display.lower()]
        # Body = from end of header to start of next section header
        body_start = s.end()
        body_end = sections[idx + 1].start() if idx + 1 < len(sections) else len(block_text)
        body = block_text[body_start:body_end].strip()
        # Split body into bullets
        bullets: list[str] = []
        for b in _BULLET_RE.finditer(body):
            bullets.append(b.group(1).strip())
        # First two bullets are reg_a_value / reg_b_value (by convention
        # in DeepAnalysis — the pair is (reg_a, reg_b) ordered).
        # We capture them in order; downstream consumers know the order
        # matches the (reg_a, reg_b) header.
        reg_a_value = bullets[0] if len(bullets) >= 1 else ""
        reg_b_value = bullets[1] if len(bullets) >= 2 else ""
        # Marker: look for a non-bullet line that contains
        # "<Marker>: <value>" — e.g. "Trigger alignment: PARTIAL (...)."
        entry: dict[str, Any] = {
            "axis": axis_key,
            "reg_a_value": reg_a_value,
            "reg_b_value": reg_b_value,
        }
        if marker_key:
            # Find first non-empty line in body that starts with the marker
            # label (case-insensitive) followed by ':'. The line may be
            # prefixed by "- " (bullet) in some DeepAnalysis variants.
            marker_label = marker_label_map[axis_display.lower()]
            marker_re = re.compile(
                rf"^[\s\-\*]*{re.escape(marker_label)}\s*:\s*([^\n]+)$",
                re.IGNORECASE | re.MULTILINE,
            )
            m = marker_re.search(body)
            if m:
                full = m.group(1).strip()
                # Split "Y (conditional) — Y when..." into verdict + note.
                # Heuristic: the verdict is everything up to the FIRST " ("
                # (an opening paren preceded by whitespace). We do NOT split
                # on "-" because some MD values contain "at-rest" etc.
                split_m = re.search(r"\s+\((.+)\)\s*(?:[\u2014\-]\s*)?(.*)$", full)
                if split_m:
                    # "Y (conditional) — Y when the at-rest..." -> verdict="Y", note="conditional — Y when..."
                    # The verdict is the leading part, the parenthetical is folded into the note.
                    verdict_part = full[: split_m.start()].strip()
                    parenthetical = split_m.group(1).strip()
                    rest = split_m.group(2).strip()
                    # Combine: "Y (conditional)" as marker value (keeps the
                    # nuance the MD author wrote), the rest as the note.
                    entry[marker_key] = f"{verdict_part} ({parenthetical})"
                    if rest:
                        entry[marker_note_key] = rest
                else:
                    entry[marker_key] = full
        out.append(entry)
    return out


def _extract_labeled_value(block_text: str, key: str) -> str:
    """Extract the value of a single-line ``**Key:** VALUE`` field.

    Used for: Classified relationship (from CRDA), Verified relationship
    (after OJ-text analysis), Reasoning, Scope-disjoint test,
    Downstream implication. Returns "" if not found.
    """
    # Escape regex meta in key, but allow the parens that some keys have
    key_escaped = re.escape(key)
    m = re.search(
        rf"\*\*{key_escaped}[^*\n]*\*\*\s*:?\s*([^\n]+(?:\n(?!\s*\*\*)[^\n]+)*)",
        block_text,
    )
    if m:
        return m.group(1).strip()
    return ""


def _extract_scope_disjoint_test(block_text: str) -> dict[str, str]:
    """Extract the scope-disjoint test result (Y / N / Conditional + note).

    Two formats exist in the source MDs:

    (A) Canonical one-liner (D-01, some D-04/D-07):
        ``**Scope-disjoint test:** Y — the controller ...``

    (B) Multi-line with rhetorical question (D-04, D-07):
        ``**Scope-disjoint test:** Does this pair actually overlap on a
        single event at a single party? Conditional``
        ``- If N or Conditional: the CRDA "contradictory" ...``

    In (A) the verdict is the first whitespace-delimited token of the line.
    In (B) the verdict is the FIRST line of the block (the rhetorical
    question + verdict), and the conditional "If N or Conditional:" is a
    separate sub-paragraph that does NOT change the verdict.

    Strategy: split the block on newlines, take the FIRST non-empty line,
    find the first occurrence of Y / N / Conditional (skipping "Does").
    """
    raw = _extract_labeled_value(block_text, "Scope-disjoint test")
    if not raw:
        return {"verdict": "", "note": ""}
    # Use the FIRST non-empty line of the block (the line that contains
    # the rhetorical question + verdict)
    first_line = ""
    for line in raw.splitlines():
        if line.strip():
            first_line = line.strip()
            break
    if not first_line:
        first_line = raw
    # Find the verdict: first occurrence of Y / N / Conditional in the
    # first line. We use word boundaries so "Does" doesn't match.
    m = re.search(
        r"\b(Y|N|Conditional)\b(?:\s*\(([^)]*)\))?",
        first_line,
    )
    if not m:
        # Fallback: look anywhere in the block
        m = re.search(
            r"\b(Y|N|Conditional)\b(?:\s*\(([^)]*)\))?",
            raw,
        )
    if not m:
        return {"verdict": "", "note": raw}
    verdict = m.group(1)
    qualifier = m.group(2) or ""
    # Note: everything after the verdict in the first line, plus any
    # continuation lines (the "If N or Conditional:" paragraph).
    remainder = first_line[m.end():].strip(" —-")
    # Continuation lines
    rest_lines = raw.splitlines()[1:]
    continuation = " ".join(line.strip() for line in rest_lines if line.strip())
    if qualifier:
        note = f"{qualifier}"
        if remainder:
            note += f" — {remainder}"
    else:
        note = remainder
    if continuation:
        if note:
            note += " || " + continuation
        else:
            note = continuation
    return {"verdict": verdict, "note": note}


def _extract_relationship_pair(block_text: str) -> dict[str, str]:
    """Extract the two canonical relationship lines:
    - classified_relationship_crda: from '**Classified relationship (from CRDA):**'
    - verified_relationship_oj:     from '**Verified relationship (after OJ-text analysis):**'
    """
    crda = _extract_labeled_value(block_text, "Classified relationship (from CRDA)")
    oj = _extract_labeled_value(
        block_text, "Verified relationship (after OJ-text analysis)"
    )
    # Strip trailing punctuation (e.g. "COMPLEMENTARY.") but preserve
    # parentheses that carry nuance (e.g. "SAME (CORRECTED — wording only)").
    def _clean(s: str) -> str:
        s = s.strip()
        if s.endswith(".") and "(" not in s:
            s = s[:-1]
        return s
    return {
        "classified_relationship_crda": _clean(crda),
        "verified_relationship_oj": _clean(oj),
    }


def _extract_p0_notes(block_text: str) -> list[str]:
    """Extract P0 notes (lines starting with '**P0 note:**' or '- **P0 note:**')."""
    out: list[str] = []
    for m in re.finditer(
        r"\*\*P0\s+note\s*:?\*\*\s*([^\n]+(?:\n(?!\s*\*\*)[^\n]+)*)",
        block_text,
        re.IGNORECASE,
    ):
        out.append(m.group(1).strip())
    return out


def _extract_participants_from_deep(body: str) -> dict[str, Any]:
    """Extract participants info from a DeepAnalysis body.

    DeepAnalysis D-XX.Y files typically carry participants in two places:
      1. HTML comment: ``<!-- participants: GDPR, NIS2, CRA, DORA; AI_Act absent -->``
      2. Bold paragraph: ``**Participants (from CRDA):** GDPR, NIS2, CRA, DORA
         (AI_Act is not present; ...).``

    We normalize into:
      - participants: ["GDPR", "NIS2", "CRA", "DORA"]  (canonicals present)
      - participants_absent: ["AI_Act"]                (canonicals marked absent)
      - participants_note: "<parenthetical note>"       (the prose annotation)

    This fixes the v10 bug where the H4 "Participants" table was always
    empty for DeepAnalysis files.
    """
    present: list[str] = []
    absent: list[str] = []
    note = ""
    # 1. HTML comment
    m = re.search(r"<!--\s*participants\s*:\s*([^>]+?)\s*-->", body)
    if m:
        comment_body = m.group(1)
        # Split the comment body into tokens on "," or ";" or "/".
        # Each token may carry a qualifier (e.g. "NIS2 partial via SR-NIS2-007",
        # "AI_Act (partial)", "AI_Act absent"). The qualifier is the
        # "evidence" of the regulation's status:
        #   - "absent" / "not present" / "missing"  -> absent
        #   - anything else (incl. "partial", "(partial)") -> present
        for tok in re.split(r"[,;/]", comment_body):
            tok = tok.strip().rstrip(",")
            if not tok:
                continue
            # Drop any trailing qualifier starting with whitespace + (word|paren)
            # Examples:
            #   "NIS2 partial via SR-NIS2-007" -> "NIS2"
            #   "AI_Act (partial)"             -> "AI_Act"
            #   "AI_Act absent"                -> "AI_Act"  (we detect "absent")
            #   "AI_Act not present"           -> "AI_Act"  (we detect "not present")
            #   "NIS2"                         -> "NIS2"
            base_match = re.match(r"^(\S+?)(?:\s+|\s*\()", tok)
            if base_match:
                reg_label = base_match.group(1)
            else:
                reg_label = tok.split()[0] if tok else ""
            if not reg_label:
                continue
            n = _deep_norm_reg(reg_label)
            if not n:
                continue
            # Detect "absent" / "not present" qualifier anywhere in the token
            is_absent = bool(
                re.search(r"\b(absent|not\s+present|missing|out[\s-]of[\s-]scope)\b", tok, re.IGNORECASE)
            )
            if is_absent:
                if n not in absent and n not in present:
                    absent.append(n)
            else:
                if n not in present:
                    present.append(n)
    # 2. Bold paragraph (prose annotation). The bold line is
    # ``**Participants (from CRDA):**`` — the closing ``**`` comes AFTER
    # the colon, so we have to match ``CRDA):**`` explicitly.
    m2 = re.search(
        r"\*\*Participants[^*]*?CRDA\)\:\*\*\s*([^\n]+)",
        body,
    )
    if m2:
        prose = m2.group(1).strip()
        # Extract the parenthetical note. The prose has the shape
        # "GDPR, NIS2, ... (note text)." — the note is the FIRST
        # balanced paren group that comes after the participant list.
        # We use the position of the first "(" as the start, then walk
        # balanced parens to find the matching ")".
        i = prose.find("(")
        if i != -1:
            depth = 1
            j = i + 1
            while j < len(prose) and depth > 0:
                if prose[j] == "(":
                    depth += 1
                elif prose[j] == ")":
                    depth -= 1
                j += 1
            if depth == 0:
                note = prose[i + 1 : j - 1].strip()
    # Fallback: if the HTML comment was absent (D-04, D-07 use the prose
    # paragraph only), parse the tokens from the bold paragraph itself.
    if not present and m2:
        prose = m2.group(1).strip()
        # Take only the part BEFORE the first "(" (the parenthetical note)
        head = prose.split("(", 1)[0]
        for tok in re.split(r"[,;]", head):
            tok = tok.strip()
            if not tok:
                continue
            # Detect absence qualifier anywhere in the token
            is_absent = bool(
                re.search(
                    r"\b(absent|not\s+present|missing|out[\s-]of[\s-]scope)\b",
                    tok,
                    re.IGNORECASE,
                )
            )
            reg_label = tok.split()[0] if tok else ""
            if not reg_label:
                continue
            n = _deep_norm_reg(reg_label)
            if not n:
                continue
            if is_absent:
                if n not in absent and n not in present:
                    absent.append(n)
            else:
                if n not in present:
                    present.append(n)
    return {
        "participants": present,
        "participants_absent": absent,
        "participants_note": note,
    }


def _dedup_pairs(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate pairs by the unordered (reg_a, reg_b) key.

    The same pair can appear in two forms in the source:
      * ``<!-- pair: GDPR, NIS2 -->`` markers (DomainAnalysis)
      * ``#### Pair: GDPR ↔ NIS2`` headings (DeepAnalysis)

    We merge them and keep the **first** occurrence (in document order)
    so the comment-marker version wins when both are present.
    """
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for p in pairs:
        key = tuple(sorted([p.get("reg_a", ""), p.get("reg_b", "")]))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


# ─── Fase 2: enrich entities/pairs/ from crossregulation ──────────────


def enrich_pair_entity(
    pair_entity: dict[str, Any],
    cr_domain_file: dict[str, Any] | None,
    cr_deep_file: dict[str, Any] | None,
) -> dict[str, Any]:
    """Enrich a single pair entity with data from crossregulation files.

    Adds (or overwrites) these fields on the pair entity:
      - cr_domain_pair: matched pair data from the DomainAnalysis file
        (why, oj_quotes, table_block_raw, block_text_raw)
      - cr_deep_pair: matched pair data from the DeepAnalysis file (if any)
      - cr_pair_source_files: list of source paths used
      - cr_pair_last_enriched: ISO timestamp

    **Zero-loss:** the enriched fields contain VERBATIM text from the
    source. The pair entity's own fields (id, pair, reg_a, reg_b, etc.)
    are NOT modified.
    """
    import datetime as _dt

    enriched = dict(pair_entity)
    sources: list[str] = []

    if cr_domain_file is not None:
        sources.append(cr_domain_file.get("source", ""))
        for p in cr_domain_file.get("pairs", []):
            pa = p.get("reg_a")
            pb = p.get("reg_b")
            # Match against pair entity's reg_a / reg_b (order-insensitive)
            if {pa, pb} == {enriched["reg_a"], enriched["reg_b"]}:
                enriched["cr_domain_pair"] = {
                    "classification": p.get("classification", ""),
                    "why": p.get("why", ""),
                    "why_qualifier": p.get("why_qualifier", ""),
                    "oj_quotes": p.get("oj_quotes", []),
                    "oj_quotes_verbatim": p.get("oj_quotes_verbatim", []),
                    "comparison_sections": p.get("comparison_sections", []),
                    "scope_disjoint_test": p.get("scope_disjoint_test", {}),
                    "downstream_implication": p.get("downstream_implication", ""),
                    "p0_notes": p.get("p0_notes", []),
                    "sr_ids_per_pair": p.get("sr_ids_per_pair", []),
                    "table_block_raw": p.get("table_block_raw", ""),
                    "block_text_raw": p.get("block_text_raw", ""),
                }
                break

    if cr_deep_file is not None:
        sources.append(cr_deep_file.get("source", ""))
        for p in cr_deep_file.get("pairs", []):
            pa = p.get("reg_a")
            pb = p.get("reg_b")
            if {pa, pb} == {enriched["reg_a"], enriched["reg_b"]}:
                enriched["cr_deep_pair"] = {
                    "classification": p.get("classification", ""),
                    "why": p.get("why", ""),
                    "oj_quotes": p.get("oj_quotes", []),
                    "table_block_raw": p.get("table_block_raw", ""),
                    "block_text_raw": p.get("block_text_raw", ""),
                }
                break

    if sources:
        enriched["cr_pair_source_files"] = sources
        enriched["cr_pair_last_enriched"] = _dt.datetime.now(_dt.UTC).isoformat()

    return enriched
