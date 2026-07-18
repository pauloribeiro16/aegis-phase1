"""Parser for per-article ``Art_NN.md`` files.

Each file is a split from the aggregate ``01_SecurityObjectives.md`` /
``02_SecurityRules_NIST.md`` indexes. The structure (per observation
of 5+ files across GDPR/CRA/NIS2/DORA/AI_Act):

  - YAML frontmatter
  - ``# GDPR Art. 30`` (H1 title)
  - ``## Security Objectives (from 01_SecurityObjectives.md)`` — markdown table
    with cols ``SO ID | Description | Source clauses | Sub-domain``
  - ``## Security Rules (from 02_SecurityRules_NIST.md)`` — sequence of
    ``### SO-GDPR-XXX / SO-GDPR-YYY (...)`` blocks, each with a
    ``\\`\\`\\`yaml\\`\\`\\` body containing the SR metadata
    (``sr_id``, ``title``, ``source_clauses``, ``linked_objectives``,
    ``sub_domain``, ``nist_csf_mapping``, ``applies_to_role``,
    ``obligation_type``, ``regulatory_rationale``, ``security_rationale``,
    ``ambiguity_notes``, etc.)

This parser is tolerant: sections may be missing; rows that fail to
parse are skipped (with a warning). Strict mode (default) escalates
warnings to errors.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .frontmatter import parse_frontmatter
from .markdown import extract_fenced_blocks, heading_with_text, split_by_headings

_SO_TABLE_ROW = re.compile(
    r"^\|\s*(?P<so_id>SO-[A-Z_0-9-]+)\s*\|\s*(?P<description>.+?)\s*\|\s*(?P<source_clauses>.+?)\s*\|\s*(?P<sub_domain>[^|]+?)\s*\|\s*$",
    re.MULTILINE,
)
_SR_H3_RE = re.compile(r"^###\s+(?P<header>.+?)\s*$", re.MULTILINE)


def _parse_so_table(text: str) -> list[dict[str, Any]]:
    """Parse the ``## Security Objectives`` markdown table.

    Many files have a duplicate row pattern (one row with the full
    description, a second row with the short summary). We deduplicate
    by ``so_id``, keeping the row with the longer description.
    """
    seen: dict[str, dict[str, Any]] = {}
    for m in _SO_TABLE_ROW.finditer(text):
        so_id = m.group("so_id")
        desc = m.group("description").strip()
        sources = [s.strip() for s in m.group("source_clauses").split(";") if s.strip()]
        sub = m.group("sub_domain").strip()
        if so_id in seen:
            if len(desc) > len(seen[so_id]["description"]):
                seen[so_id] = {
                    "so_id": so_id,
                    "description": desc,
                    "source_clauses": sources,
                    "sub_domain": [s.strip() for s in sub.split(",") if s.strip()],
                }
        else:
            seen[so_id] = {
                "so_id": so_id,
                "description": desc,
                "source_clauses": sources,
                "sub_domain": [s.strip() for s in sub.split(",") if s.strip()],
            }
    return list(seen.values())


def _parse_sr_blocks(text: str) -> list[dict[str, Any]]:
    """Parse the ``## Security Rules`` section into per-SR dicts.

    Each SR block is ``### <header>`` followed by a ``\\`\\`\\`yaml\\`\\`\\` body.
    Multiple SRs may share a header (e.g. ``### SO-GDPR-001 / SO-GDPR-014``).
    """
    srs: list[dict[str, Any]] = []
    matches = list(_SR_H3_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():end]
        yaml_blocks = extract_fenced_blocks(block, lang="yaml")
        if not yaml_blocks:
            # No yaml body — skip
            continue
        # Each yaml block is one SR (or sometimes a list of SRs prefixed by ``-``)
        for lang, body in yaml_blocks:
            try:
                parsed = yaml.safe_load(body)
            except yaml.YAMLError:
                continue
            items: list[dict[str, Any]]
            if isinstance(parsed, list):
                items = [p for p in parsed if isinstance(p, dict)]
            elif isinstance(parsed, dict):
                items = [parsed]
            else:
                continue
            for item in items:
                # Each item is a dict like {sr_id, title, source_clauses, ...}
                srs.append(
                    {
                        "sr_id": str(item.get("sr_id", "")).strip(),
                        "title": str(item.get("title", "")).strip(),
                        "yaml_body": item,
                    }
                )
    return srs


def parse_article(path: Path) -> dict[str, Any]:
    """Parse one ``Art_NN.md`` into a JSON-ready dict."""
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    warnings: list[str] = []

    regulation = str(frontmatter.get("regulation", "UNKNOWN"))
    article_ref = str(frontmatter.get("article", "UNKNOWN"))

    # § Security Objectives
    so_section = heading_with_text(body, 2, lambda t: "Security Objectives" in t)
    if so_section is None:
        warnings.append(f"missing '## Security Objectives' section in {path.name}")
        security_objectives: list[dict[str, Any]] = []
        so_raw = ""
    else:
        so_raw = so_section[1]
        security_objectives = _parse_so_table(so_raw)

    # § Security Rules
    sr_section = heading_with_text(body, 2, lambda t: "Security Rules" in t)
    if sr_section is None:
        warnings.append(f"missing '## Security Rules' section in {path.name}")
        security_rules: list[dict[str, Any]] = []
        sr_raw = ""
    else:
        sr_raw = sr_section[1]
        security_rules = _parse_sr_blocks(sr_raw)

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": frontmatter.get("document_id", f"AEGIS-PREPROC-{regulation}-ART-{article_ref}"),
        "regulation": regulation,
        "article_ref": article_ref,
        "frontmatter": frontmatter,
        "security_objectives": security_objectives,
        "security_rules": security_rules,
        "warnings": warnings,
    }
