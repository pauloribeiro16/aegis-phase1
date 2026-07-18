"""NIST CSF 2.0 subcategory parser.

Source: ``methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md``.

Format: one H2 per Function (GV, ID, PR, DE, RS, RC) followed by a markdown
table with columns ``| Subcategory | Description |``. Additionally,
the file has a final "D-XX hint table" that maps sub-domains to
recommended CSF subcategories — we extract that too as a side index.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..frontmatter import parse_frontmatter
from ..markdown import extract_table_rows, split_by_headings


def _row_to_subcat(row: list[str]) -> dict[str, Any] | None:
    if len(row) < 2:
        return None
    subcat_id = row[0].strip()
    title = row[1].strip()
    if not re.fullmatch(r"[A-Z]{2}\.[A-Z]{2}-\d{2}", subcat_id):
        return None
    # e.g. "DE.CM-01" → function="DE", category="CM", number="01"
    function, rest = subcat_id.split(".", 1)
    cat, num = rest.split("-", 1)
    return {
        "id": subcat_id,
        "function": function,
        "category": cat,
        "number": num,
        "title": title,
    }


def parse_csf(path: Path) -> list[dict[str, Any]]:
    """Parse the CSF reference file. Returns a list of subcategory dicts."""
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    sections = split_by_headings(body, min_level=2, max_level=2)

    subcats: list[dict[str, Any]] = []
    for sec in sections:
        # Skip non-function sections (Special tokens, Function structure table, etc.)
        if not re.match(r"^[A-Z]{2}\b", sec.title):
            continue
        for row in extract_table_rows(sec.body):
            parsed = _row_to_subcat(row)
            if parsed:
                parsed["source"] = "NIST_CSF_2.0_subcategories.md"
                subcats.append(parsed)
    return subcats


def parse_csf_d_subdomain_hints(path: Path) -> dict[str, list[str]]:
    """Parse the D-XX hint table at the end of the CSF reference.

    Returns ``{"D-10.1": ["PR.PS-04", "DE.CM-09"], ...}``.
    """
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    sections = split_by_headings(body, min_level=2, max_level=2)
    hints: dict[str, list[str]] = {}
    for sec in sections:
        if not sec.title.startswith("D-") or "CSF" in sec.title:
            # look for sections whose title starts with "D-XX" (the hint table rows)
            continue
        # The hint table is a single line per row, no ## header — it's in the
        # body of an H2 with the function summary. Easier: scan the entire
        # text for the pattern "| D-XX.Y (description) | CSF-id, CSF-id |"
        for line in sec.body.splitlines():
            m = re.match(
                r"\|\s*(D-\d{2}(?:\.\d+)?)\s*\([^)]*\)\s*\|\s*([^|]+?)\s*\|\s*$",
                line,
            )
            if m:
                d_id = m.group(1)
                csf_ids = [s.strip() for s in m.group(2).split(",") if s.strip()]
                if csf_ids and re.fullmatch(r"[A-Z]{2}\.[A-Z]{2}-\d{2}", csf_ids[0]):
                    hints[d_id] = csf_ids
    # The hint table is actually in a code block — fall back to scanning
    # the whole text for the pattern if we found nothing.
    if not hints:
        for line in body.splitlines():
            m = re.match(
                r"\|\s*(D-\d{2}(?:\.\d+)?)\s*\([^)]*\)\s*\|\s*([^|]+?)\s*\|\s*$",
                line,
            )
            if m:
                d_id = m.group(1)
                csf_ids = [s.strip() for s in m.group(2).split(",") if s.strip()]
                if csf_ids and re.fullmatch(r"[A-Z]{2}\.[A-Z]{2}-\d{2}", csf_ids[0]):
                    hints[d_id] = csf_ids
    return hints
