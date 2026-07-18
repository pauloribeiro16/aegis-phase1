"""Parser for a per-regulation ``Ambiguity/{REG}-CLxx_*.md`` file.

These are the GDPR-CL01 / CRA-CL12 / etc. files. Each one contains 1
clause analysis with:

  - ``**Clause: <id>`` (canonical ID)
  - ``**Berry anchor:`` (cross-reference to the framework §)
  - ``### Instance N — <tag>`` (e.g. ``Instance 1 — VAG / S3``)
  - ``**Variant readings:**`` table with ``| # | Reading | Disambiguation source |``

We extract each clause as one entity in the ``clause`` collection. The
file may contain multiple clauses (one per ``**Clause:`` marker).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..frontmatter import parse_frontmatter

_CLAUSE_RE = re.compile(
    r"\*\*Clause:\s*(?P<id>(?:GDPR|NIS2|CRA|DORA|AI_Act|AIACT)-C[LP]\d+)\*\*"
)
_BERRY_RE = re.compile(r"\*\*Berry\s+anchor:\*\*\s*(?P<anchor>.+?)(?=\n\n|\Z)", re.DOTALL)
_TYPE_RE = re.compile(r"type:\s*([a-z_-]+)")
_OBLIGATED_RE = re.compile(r"obligatedParty:\s*([A-Z_]+)")
_OBLIGATION_RE = re.compile(r"obligationType:\s*([A-Z_]+)")
_TITLE_RE = re.compile(r"###\s+([^\n]+?)\s*—\s+(.+)")
_INSTANCE_RE = re.compile(
    r"###\s+Instance\s+(\d+)\s+—\s+(?P<label>.+?)(?:\n|$)",
    re.MULTILINE,
)
_VARIANT_TABLE_RE = re.compile(
    r"\|\s*(?P<n>R\d+|\d+)\s*\|\s*(?P<reading>[^|]+?)\s*\|\s*(?P<source>[^|]+?)\s*\|",
)
_TAG_TOKENS_RE = re.compile(r"\b(VAG|POLY|VAG\+|POLY-VAG|COORDS?|S[0-9]+|V[0-9]+|A[0-9]+)\b")
_VERBATIM_RE = re.compile(
    r"###\s+Verbatim\s+\(with highlighting\)\s*\n(?P<body>.+?)(?=\n###\s+|\Z)",
    re.DOTALL,
)
_ARTICLE_RE = re.compile(
    r"\*\*Article\s+(?P<n>[\dIVX]+)\*\*[^\n]*\n(?P<title>[^\n]+)",
)


def _extract_verbatim(body: str) -> str:
    m = _VERBATIM_RE.search(body)
    return m.group("body").strip()[:3000] if m else ""


def _extract_articles(body: str) -> list[dict[str, str]]:
    return [
        {"article": m.group("n"), "title": m.group("title").strip()}
        for m in _ARTICLE_RE.finditer(body)
    ]


def _extract_instances(body: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in _INSTANCE_RE.finditer(body):
        label = m.group("label").strip()
        # The block from this match to the next ### or end
        start = m.end()
        nxt = re.search(r"###\s+(?!Instance\b)", body[start:])
        end = start + nxt.start() if nxt else len(body)
        block = body[start:end]
        # Extract tags/tokens from label
        tags = _TAG_TOKENS_RE.findall(label)
        # Extract variant readings table
        variant_readings: list[dict[str, str]] = []
        for v in _VARIANT_TABLE_RE.finditer(block):
            variant_readings.append(
                {
                    "reading": v.group("reading").strip(),
                    "source": v.group("source").strip(),
                }
            )
        out.append(
            {
                "instance_n": int(m.group(1)),
                "label": label,
                "tags": list(dict.fromkeys(tags)),
                "variant_readings": variant_readings,
                "raw": block.strip()[:1500],
            }
        )
    return out


def parse_clause_file(path: Path, regulation: str) -> list[dict[str, Any]]:
    """Parse an Ambiguity/{REG}-CLxx_*.md file → list of clause entities."""
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    warnings: list[str] = []

    # Find each clause block (starts with ``**Clause: <id>``)
    matches = list(_CLAUSE_RE.finditer(body))
    clauses: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        clause_id = m.group("id")
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]

        # Title is the first H3 in the block before the clause marker
        title_m = re.search(r"###\s+(.+)", body[:start])
        title = title_m.group(1).strip() if title_m else ""

        # Type / obligatedParty / obligationType (sometimes in inline)
        type_m = _TYPE_RE.search(block)
        obligated_m = _OBLIGATED_RE.search(block)
        obligation_m = _OBLIGATION_RE.search(block)

        berry_m = _BERRY_RE.search(block)
        berry = berry_m.group("anchor").strip()[:500] if berry_m else ""

        verbatim = _extract_verbatim(body[:start] + block)
        articles = _extract_articles(body[:start] + block)
        instances = _extract_instances(block)

        clauses.append(
            {
                "schema_version": "1.0",
                "id": clause_id,
                "regulation": regulation,
                "title": title,
                "type": type_m.group(1) if type_m else "",
                "obligated_party": obligated_m.group(1) if obligated_m else "",
                "obligation_type": obligation_m.group(1) if obligation_m else "",
                "berry_anchor": berry,
                "articles_covered": articles,
                "verbatim_text": verbatim,
                "instances": instances,
                "warnings": warnings,
            }
        )
    return clauses
