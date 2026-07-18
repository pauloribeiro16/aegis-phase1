"""Parser for CrossRegulation files (DeepAnalysis, DomainAnalysis, index).

Each CrossRegulation file is a free-form markdown document with
frontmatter. We do NOT re-parse the pair structure here (the SubDomain
parser already does that for ``D-XX.Y.md``). The role of this parser
is to surface the file as a structured shard (frontmatter + raw_md)
so the loaders can find, cite, and traverse the cross-regulation tree
deterministically.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .frontmatter import parse_frontmatter

# ``DomainAnalysis/D-XX_<name>/D-XX.Y.md`` → "domain_analysis" sub_kind
# ``DeepAnalysis/D-XX_<name>/D-XX.Y.md`` → "deep_analysis"
# ``index.md`` → "index"
_KIND_BY_PARENT_DIR = {
    "DomainAnalysis": "domain_analysis",
    "DeepAnalysis": "deep_analysis",
    "_archive": "archived",
}


def parse_crossreg(path: Path, root_dir: Path) -> dict[str, Any]:
    """Parse one CrossRegulation ``*.md`` file into a JSON-ready dict.

    ``root_dir`` is the CrossRegulation/ root, used to classify the file
    by its position in the tree.
    """
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    warnings: list[str] = []

    # Determine sub-kind from path
    rel = path.relative_to(root_dir)
    parts = rel.parts
    sub_kind = "other"
    if parts[0] in _KIND_BY_PARENT_DIR:
        sub_kind = _KIND_BY_PARENT_DIR[parts[0]]
    elif parts[0].endswith(".md"):
        sub_kind = "index" if parts[0] == "index.md" else "other"

    # Try to extract a "Participants" line for the sub-domain
    parts_m = re.search(
        r"\*\*Participants\s+\(from\s+CRDA[^*]*\)\*\*:\s*(?P<regs>[^\n]+)",
        body,
    )
    participants: list[str] = []
    if parts_m:
        participants = [
            r.strip().rstrip(",")
            for r in re.split(r"[,/]", parts_m.group("regs"))
            if r.strip()
        ]

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": frontmatter.get("document_id", f"AEGIS-PREPROC-CRDA-{rel}"),
        "sub_kind": sub_kind,
        "macro_domain": frontmatter.get("macro_domain", ""),
        "sub_domain": frontmatter.get("sub_domain", ""),
        "title": str(frontmatter.get("title", path.stem)),
        "status": str(frontmatter.get("status", "")),
        "frontmatter": frontmatter,
        "participants": participants,
        "raw_md": body.strip(),
        "warnings": warnings,
    }


def parse_global(path: Path) -> dict[str, Any]:
    """Parse one of the top-level ``*.md`` global files.

    Same shape as crossreg but without ``sub_kind`` (always "global").
    """
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": frontmatter.get("document_id", f"AEGIS-PREPROC-GLOBAL-{path.stem}"),
        "title": str(frontmatter.get("title", path.stem)),
        "status": str(frontmatter.get("status", "")),
        "frontmatter": frontmatter,
        "raw_md": body.strip(),
        "warnings": [],
    }
