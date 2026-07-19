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
    participants_meta: list[str] = []
    m_part = re.search(r"<!--\s*participants:\s*([^>]+?)\s*-->", body)
    if m_part:
        participants_meta = [r.strip() for r in m_part.group(1).split(",")]

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
        pairs.append(
            {
                "reg_a": regs[0],
                "reg_b": regs[1],
                "classification": classification,
                "why": why,
                "oj_quotes": oj_quotes,
                "table_block_raw": table_block_raw,
                "block_text_raw": block_text,
            }
        )
        pos = close_m.end()

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
        "pairs": pairs,
        "pair_count": len(pairs),
        "emergent_tensions": emergent_tensions,
        "sr_cross_references": sr_cross_references,
        "sr_cross_reference_count": len(sr_cross_references),
        "raw_md": body,  # zero-loss
        "raw_md_kept_reason": "audit_fallback_for_zero_loss_invariant",
    }


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
                    "oj_quotes": p.get("oj_quotes", []),
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
