"""Aggregator: parse a regulation's ``01_SecurityObjectives.md``.

This is the CANONICAL source for SO-* IDs. Each SO row has:
    | SO ID | Description | Source clauses | Sub-domain |

The cross-references in column 3 (e.g. ``\\`GDPR-CL05\\` (Art. 5(1)(e))``)
parse into structured ``source_clauses`` with ``clause_id`` + ``article_ref``.

The cross-references in column 2 (e.g. ``SO-GDPR-001 (cross-ref)``) are
extracted as ``cross_ref_of`` so the pipeline can resolve the indirection.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..frontmatter import parse_frontmatter
from ..markdown import extract_table_rows

# ``GDPR-CL05`` (Art. 5(1)(e)) → ("GDPR-CL05", "Art. 5(1)(e)")
_CLAUSE_REF_RE = re.compile(
    r"`?\b((?:GDPR|NIS2|CRA|DORA|AI_Act|AIACT)-CL\d+)`?\s*" r"(?:\(([^)]+)\))?",
)
# ``SO-GDPR-001 (cross-ref)`` → ("SO-GDPR-001", True)
_CROSS_REF_RE = re.compile(
    r"^SO-([A-Z_0-9]+)-(\d+)\s*\(cross-ref\)\s*$",
)


def _parse_source_clauses(cell: str) -> list[dict[str, str]]:
    """Parse the 'Source clauses' cell into structured refs."""
    refs: list[dict[str, str]] = []
    for m in _CLAUSE_REF_RE.finditer(cell):
        clause_id = m.group(1)
        article_ref = (m.group(2) or "").strip()
        refs.append({"clause_id": clause_id, "article_ref": article_ref})
    return refs


def _parse_subdomain_cell(cell: str) -> list[str]:
    """Sub-domain cell is a comma-separated list of D-XX.Y ids."""
    return [s.strip() for s in cell.split(",") if s.strip()]


def _row_to_so(row: list[str], regulation: str) -> dict[str, Any] | None:
    if len(row) < 4:
        return None
    so_id_raw = row[0].strip()
    # Normalize: ``SO-GDPR-001 (cross-ref)`` → base id is SO-GDPR-001
    m = _CROSS_REF_RE.match(so_id_raw)
    cross_ref = False
    if m:
        so_id = f"SO-{m.group(1)}-{m.group(2)}"
        cross_ref = True
    else:
        so_id = so_id_raw
    # Validate
    if not re.fullmatch(r"SO-[A-Z_0-9]+-\d{3}", so_id):
        return None
    return {
        "id": so_id,
        "regulation": regulation,
        "description": row[1].strip(),
        "source_clauses": _parse_source_clauses(row[2]),
        "sub_domains": _parse_subdomain_cell(row[3]),
        "is_cross_ref": cross_ref,
    }


def parse_security_objectives(path: Path, regulation: str) -> list[dict[str, Any]]:
    """Parse ``01_SecurityObjectives.md`` and return a list of SO dicts."""
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    sos: list[dict[str, Any]] = []
    for row in extract_table_rows(body):
        parsed = _row_to_so(row, regulation)
        if parsed:
            sos.append(parsed)
    return sos
