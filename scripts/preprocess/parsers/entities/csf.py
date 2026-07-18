"""NIST CSF 2.0 subcategory parser.

Source: ``methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md``.

The file has these distinct structural elements, all of which are mapped to
structured fields in the JSON output (no raw_md dumping):

1. YAML frontmatter (lines 1-16) — 12 keys
2. H1 title (line 18)
3. ``> **Authority:**`` blockquote (line 20)
4. ``## Function structure`` H2 (lines 24-36)
   - summary text + table with 6 functions + total row
5. 6 ``## FUNC — Name (X cats, Y subs)`` H2 sections (lines 40, 100, 135, 189, 213, 252)
6. 22 ``### FUNC.CAT — Category Name`` H3 sections
7. 98 subcategory table rows ``| FUNC.CAT-NN | Subcategory text |``
8. ``## Cross-reference`` H2 (lines 267-310)
   - H2 title (full)
   - table with 38 D-XX rows: ``| AEGIS sub-domain | Likely CSF Functions |``
   - D-XX description in parens (e.g. "Data at Rest")
   - CSF cell prose (e.g. "GV.OV (governance)")
   - trailing blockquote (line 310): "Use only as orientation..."
9. ``## Special tokens`` H2 (lines 314-319)
   - H2 title
   - table with 2 rows: ``| Token | Use |``
10. Closing line: "**End of reference.**" (line 323)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..frontmatter import parse_frontmatter
from ..markdown import extract_table_rows, split_by_headings

# Pattern: subcategory id like "DE.CM-01"
_SUBCAT_ID_RE = re.compile(r"^[A-Z]{2}\.[A-Z]{2}-\d{2}$")
# Pattern: category id like "GV.OV" (FUNC.CAT, no number) — the source
# cross-reference table sometimes points to a whole category, e.g. "GV.OV
# (governance)". This is not a subcategory but the parser must capture it
# so consumers can resolve via the canonical category list.
_CAT_ID_RE = re.compile(r"^[A-Z]{2}\.[A-Z]{2}$")
# Combined: CSF reference (subcategory OR category)
_CSF_REF_RE = re.compile(r"^([A-Z]{2}\.[A-Z]{2})(?:-(\d{2}))?$")
# Pattern: D-XX.Y (Description)
_DXX_ROW_RE = re.compile(r"^\s*(D-\d{2}(?:\.\d+)?)\s*\(([^)]*)\)\s*$")
# Pattern: H3 category header
_H3_CAT_RE = re.compile(r"^###\s+([A-Z]{2}\.[A-Z]{2})\s*—\s*(.+?)\s*$")
# Pattern: H2 function header with counts
_H2_FN_RE = re.compile(
    r"^([A-Z]{2})\s*—\s*([^(]+)\("
    r"(\d+)\s+(?:categor(?:y|ies))"
    r",\s+(\d+)\s+subcategor(?:y|ies)\)"
)
# Pattern: H1 title (just `^# `)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$")
# Pattern: closing line "**End of reference.**"
_END_RE = re.compile(r"^\*\*End of reference\.\*\*\s*$")

# Special tokens table at the end of the file (canonical default fallback)
_SPECIAL_TOKENS_DEFAULT: list[dict[str, str]] = [
    {
        "token": "UNMAPPED_CSF",
        "use": (
            "Mark a SecurityRule as having no natural CSF 2.0 sub-category. "
            "MUST come with `unmapped_csf_justification` and is reported "
            "separately in validation."
        ),
    },
    {
        "token": "UNMAPPED_CSF_PRIVACY",
        "use": (
            "Optional token for rules that map to NIST Privacy Framework rather "
            "than CSF 2.0. **NOT** in scope for this pre-processing pass — "
            "sub-agent should use `UNMAPPED_CSF` and note the privacy-framework "
            "potential in `ambiguity_notes`."
        ),
    },
]


# ─── Helpers ────────────────────────────────────────────────────────────


def _function_name_map() -> dict[str, str]:
    return {
        "GV": "Govern",
        "ID": "Identify",
        "PR": "Protect",
        "DE": "Detect",
        "RS": "Respond",
        "RC": "Recover",
    }


def _line_locus(body: str, start_marker: str, end_marker: str | None) -> dict[str, int]:
    """Compute 1-indexed line range for a logical block delimited by markers."""
    lines = body.splitlines()
    start = 0
    end = len(lines)
    started = False
    for i, line in enumerate(lines, start=1):
        if not started and start_marker in line:
            start = i
            started = True
            continue
        if started and end_marker and end_marker in line:
            end = i - 1
            break
    return {"start_line": start, "end_line": end}


def _category_name_for(cat_id: str, sections: list[Any]) -> str | None:
    """Find a ``### FUNC.CAT — Category Name`` header and return the name."""
    for sec in sections:
        if sec.body:
            for line in sec.body.splitlines():
                m = _H3_CAT_RE.match(line)
                if m and m.group(1) == cat_id:
                    return m.group(2).strip()
    return None


def _function_summary_for(
    function_id: str, sections: list[Any]
) -> dict[str, int] | None:
    """Parse the ``## FUNC — Name (X categories, Y subcategories)`` header."""
    for sec in sections:
        m = _H2_FN_RE.match(sec.title.strip())
        if m and m.group(1) == function_id:
            return {
                "category_count": int(m.group(3)),
                "subcategory_count": int(m.group(4)),
            }
    return None


def _h1_title(body: str) -> str:
    """Extract the H1 title (line 18: ``# NIST CSF 2.0 Subcategory Reference ...``)."""
    for line in body.splitlines():
        m = _H1_RE.match(line)
        if m:
            return m.group(1).strip()
    return ""


def _end_of_reference(body: str) -> dict[str, Any] | None:
    """Detect the closing ``**End of reference.**`` line."""
    for i, line in enumerate(body.splitlines(), start=1):
        if _END_RE.match(line.strip()):
            return {"text": line.strip(), "line": i}
    return None


def _authority_blockquote(body: str) -> dict[str, Any]:
    """Extract the full ``> **Authority:**`` blockquote (may span multiple lines).

    Line numbers returned are **body-relative** (1-indexed within ``body``).
    Callers that want source-relative lines must add the frontmatter offset.
    """
    lines = body.splitlines()
    chunks: list[str] = []
    start_line: int | None = None
    end_line: int | None = None
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if "**Authority:**" in line and stripped.startswith(">"):
            start_line = i
            text = line.lstrip().lstrip(">").lstrip()
            chunks.append(text)
            end_line = i
        elif start_line is not None and stripped.startswith(">"):
            text = line.lstrip().lstrip(">").lstrip()
            chunks.append(text)
            end_line = i
        elif start_line is not None:
            break
    full_text = "\n".join(chunks).strip()
    return {
        "text": full_text,
        "start_line": start_line or 0,
        "end_line": end_line or 0,
    }


def _crossref_advisory_blockquote(body: str) -> dict[str, Any] | None:
    """Extract the ``> **Use only as orientation.**`` blockquote after the
    cross-reference table. Returns body-relative line number."""
    lines = body.splitlines()
    for i, line in enumerate(lines, start=1):
        if "Use only as orientation" in line and line.strip().startswith(">"):
            text = line.lstrip().lstrip(">").lstrip()
            return {"text": text, "line": i}
    return None


# ─── Public API: per-subcategory ────────────────────────────────────────


def parse_csf(path: Path) -> list[dict[str, Any]]:
    """Parse the CSF reference file → 1 dict per subcategory (structured).

    Each dict includes the full source metadata for that subcategory:
    id, function, function_name, category, category_id, category_name,
    number, title, function_summary, source_locus, source_document,
    document metadata, aegis_subdomain_back_refs (advisory).
    """
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    sections = split_by_headings(body, min_level=2, max_level=2)
    fname_map = _function_name_map()

    crossref = _extract_crossref_table(body)
    authority = _authority_blockquote(body)
    cat_name_cache: dict[str, str | None] = {}

    # Pre-compute function section order so we can find each block's end
    fn_section_idx: dict[str, int] = {}
    for i, sec in enumerate(sections):
        m_fn = re.match(r"^([A-Z]{2})\s*—", sec.title)
        if m_fn and m_fn.group(1) not in fn_section_idx:
            fn_section_idx[m_fn.group(1)] = i

    subcats: list[dict[str, Any]] = []
    for sec in sections:
        m_fn = re.match(r"^([A-Z]{2})\s*—", sec.title)
        if not m_fn:
            continue
        function_id = m_fn.group(1)
        function_name = fname_map.get(function_id, function_id)
        fn_summary = _function_summary_for(function_id, sections) or {
            "category_count": 0,
            "subcategory_count": 0,
        }

        my_idx = fn_section_idx[function_id]
        next_idx = None
        for j in range(my_idx + 1, len(sections)):
            nxt = sections[j]
            if re.match(r"^[A-Z]{2}\s*—", nxt.title):
                next_idx = j
                break
        if next_idx is not None:
            nxt_m = re.match(r"^([A-Z]{2})\s*—", sections[next_idx].title)
            end_marker = f"## {nxt_m.group(1)} —" if nxt_m else None
        else:
            end_marker = None
        start_marker = f"## {function_id} —"
        locus = _line_locus(body, start_marker, end_marker)

        # Subcategory table has columns: | ID | Subcategory | (skip header)
        for row in extract_table_rows(sec.body):
            if len(row) < 2:
                continue
            subcat_id = row[0].strip()
            title = row[1].strip()
            if not _SUBCAT_ID_RE.fullmatch(subcat_id):
                continue
            function, rest = subcat_id.split(".", 1)
            cat, num = rest.split("-", 1)
            cat_id = f"{function}.{cat}"
            if cat_id not in cat_name_cache:
                cat_name_cache[cat_id] = _category_name_for(cat_id, sections)
            # Reverse-index back-references (advisory)
            back_refs: list[str] = []
            for d_id, csf_ids in crossref["csf_ids_by_d"].items():
                if subcat_id in csf_ids:
                    back_refs.append(d_id)
            subcats.append(
                {
                    "id": subcat_id,
                    "function": function,
                    "category": cat,
                    "number": num,
                    "title": title,
                    "function_name": function_name,
                    "category_id": cat_id,
                    "category_name": cat_name_cache[cat_id],
                    "function_summary": fn_summary,
                    "source_locus": locus,
                    "source": "NIST_CSF_2.0_subcategories.md",
                    "source_document": {
                        "document_id": fm.get("document_id", ""),
                        "title": fm.get("title", ""),
                        "version": fm.get("version", ""),
                        "chain_version": fm.get("chain_version", ""),
                        "status": fm.get("status", ""),
                        "authority_source": fm.get("source", ""),
                    },
                    # Reference to the document-level authority blockquote
                    # (every subcategory is governed by the same authority).
                    "authority_note": authority["text"],
                    "authority_note_locus": {
                        "start_line": authority["start_line"],
                        "end_line": authority["end_line"],
                    },
                    "aegis_subdomain_back_refs": sorted(back_refs),
                    "aegis_subdomain_back_refs_advisory_only": True,
                }
            )
    return subcats


# ─── Public API: aggregated elements ────────────────────────────────────


def parse_csf_authority_note(path: Path) -> str:
    """Extract the ``> **Authority:**`` blockquote as a single string."""
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    return _authority_blockquote(body)["text"]


def parse_csf_authority_note_full(path: Path) -> dict[str, Any]:
    """Extract the ``> **Authority:**`` blockquote with start/end line."""
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    return _authority_blockquote(body)


def parse_csf_d_subdomain_hints(path: Path) -> dict[str, list[str]]:
    """Parse the D-XX hint table → ``{"D-10.1": ["PR.PS-04", "DE.CM-09"], ...}``.

    Note: this is the *advisory* mapping per the source's own caveat.
    """
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    return _extract_crossref_table(body)["csf_ids_by_d"]


def parse_csf_crossref_full(path: Path) -> dict[str, Any]:
    """Parse the full cross-reference H2 (header + table + advisory quote)."""
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    return _extract_crossref_table(body)


def parse_csf_special_tokens(path: Path) -> list[dict[str, str]]:
    """Parse the ``## Special tokens`` table data rows (skip header)."""
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    sections = split_by_headings(body, min_level=2, max_level=2)
    for sec in sections:
        if sec.title.strip().lower() != "special tokens":
            continue
        rows: list[dict[str, str]] = []
        for row in extract_table_rows(sec.body):
            if len(row) < 2:
                continue
            token = row[0].strip().strip("`")
            use = row[1].strip()
            if not token or token.lower() == "token":
                continue
            rows.append({"token": token, "use": use})
        if rows:
            return rows
    return list(_SPECIAL_TOKENS_DEFAULT)


def parse_csf_special_tokens_full(path: Path) -> dict[str, Any]:
    """Full Special tokens section: H2 title + table header + data rows + locus."""
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    sections = split_by_headings(body, min_level=2, max_level=2)
    for sec in sections:
        if sec.title.strip().lower() != "special tokens":
            continue
        rows: list[dict[str, str]] = []
        header_row: list[str] = []
        for row in extract_table_rows(sec.body):
            if len(row) < 2:
                continue
            cells = [c.strip() for c in row]
            if not header_row and all(
                re.match(r"^[A-Za-z ]+$", c) for c in cells
            ):
                header_row = cells
                continue
            token = cells[0].strip("`")
            use = cells[1]
            if not token or token.lower() == "token":
                continue
            rows.append({"token": token, "use": use})
        locus = _line_locus(body, "## Special tokens", None)
        return {
            "title": sec.title.strip(),
            "table_header": header_row or ["Token", "Use"],
            "rows": rows or list(_SPECIAL_TOKENS_DEFAULT),
            "source_locus": locus,
        }
    # Fallback
    return {
        "title": "Special tokens",
        "table_header": ["Token", "Use"],
        "rows": list(_SPECIAL_TOKENS_DEFAULT),
        "source_locus": {"start_line": 0, "end_line": 0},
    }


def parse_csf_function_structure(path: Path) -> dict[str, Any]:
    """Parse the ``## Function structure`` H2 + table + summary."""
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    sections = split_by_headings(body, min_level=2, max_level=2)
    fname_map = _function_name_map()
    out: dict[str, Any] = {
        "title": "Function structure",
        "summary_text": "",
        "table_header": ["Function ID", "Function Name", "Cat. Count", "Subcat. Count"],
        "functions": [],
        "totals_row": None,
        "totals": {
            "function_count": 0,
            "category_count": 0,
            "subcategory_count": 0,
        },
        "source_locus": {"start_line": 0, "end_line": 0},
    }
    for sec in sections:
        if sec.title.strip().lower() != "function structure":
            continue
        out["title"] = sec.title.strip()
        out["source_locus"] = _line_locus(body, "## Function structure", None)

        for line in sec.body.splitlines():
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("|")
                and not stripped.startswith("#")
            ):
                out["summary_text"] = stripped
                break

        for row in extract_table_rows(sec.body):
            if len(row) < 4:
                continue
            cells = [c.strip() for c in row]
            if cells[0].lower().startswith("**total"):
                try:
                    out["totals_row"] = {
                        "function_label": cells[0],
                        "category_count": int(
                            cells[2].replace(",", "").replace("*", "")
                        ),
                        "subcategory_count": int(
                            cells[3].replace(",", "").replace("*", "")
                        ),
                    }
                    out["totals"]["category_count"] = out["totals_row"][
                        "category_count"
                    ]
                    out["totals"]["subcategory_count"] = out["totals_row"][
                        "subcategory_count"
                    ]
                except (ValueError, IndexError):
                    pass
                continue
            fn_id = cells[0]
            try:
                cat_count = int(cells[2].replace(",", ""))
                sub_count = int(cells[3].replace(",", ""))
            except ValueError:
                continue
            if not re.fullmatch(r"[A-Z]{2}", fn_id):
                continue
            out["functions"].append(
                {
                    "id": fn_id,
                    "name": cells[1],
                    "function_name": fname_map.get(fn_id, cells[1]),
                    "category_count": cat_count,
                    "subcategory_count": sub_count,
                }
            )
        out["totals"]["function_count"] = len(out["functions"])
        break
    return out


def parse_csf_h1_title(path: Path) -> str:
    """Extract the H1 title (line 18)."""
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    return _h1_title(body)


def parse_csf_end_of_reference(path: Path) -> dict[str, Any] | None:
    """Extract the ``**End of reference.**`` closing line (with line number)."""
    text = path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    return _end_of_reference(body)


# ─── Internal ───────────────────────────────────────────────────────────


def _extract_crossref_table(body: str) -> dict[str, Any]:
    """Parse the full ``## Cross-reference`` H2 (header + table + advisory).

    Returns a dict with:
      - ``title`` (full H2 title)
      - ``table_header`` (column names)
      - ``rows`` (list of {aegis_subdomain, description, csf_cell_raw,
        csf_ids, advisory_prose, source_locus})
      - ``csf_ids_by_d`` (legacy shortcut: ``{D-XX: [csf_ids]}``)
      - ``advisory_blockquote`` (the "Use only as orientation" note)
      - ``source_locus``
    """
    sections = split_by_headings(body, min_level=2, max_level=2)
    cross_section = None
    for sec in sections:
        if sec.title.strip().lower().startswith("cross-reference"):
            cross_section = sec
            break
    if cross_section is None:
        return {
            "title": "",
            "table_header": [],
            "rows": [],
            "csf_ids_by_d": {},
            "advisory_blockquote": None,
            "source_locus": {"start_line": 0, "end_line": 0},
        }
    out_rows: list[dict[str, Any]] = []
    csf_ids_by_d: dict[str, list[str]] = {}
    table_header: list[str] = []

    sec_start_line = _line_locus(body, "## Cross-reference", None)["start_line"]
    body_lines = cross_section.body.splitlines()
    # Find the offset of cross_section.body within body (0-indexed newlines
    # before the section start).
    cross_idx = body.find(cross_section.body)
    body_offset = body[:cross_idx].count("\n") if cross_idx >= 0 else 0

    # Build a map from each "| ... |" line in the section to its body-relative
    # 1-indexed line number. The table is contiguous (header + separator +
    # data rows) so the first | line is the header and subsequent | lines are
    # in the same order as `rows_table` from `extract_table_rows` (which
    # strips the separator).
    table_line_locus: list[int] = []
    for i, line in enumerate(body_lines):
        if line.strip().startswith("|"):
            table_line_locus.append(body_offset + i + 1)
    # table_line_locus[0] = header line; table_line_locus[1] = separator;
    # table_line_locus[2:] = data rows in order.
    rows_table: list[list[str]] = list(extract_table_rows(cross_section.body))
    # Map rows_table index → body-relative line (1-indexed).
    # rows_table[0] = header → table_line_locus[0]
    # rows_table[1] = first data row → table_line_locus[2] (skip separator)
    row_line_map: dict[int, int] = {}
    if len(table_line_locus) >= 1:
        row_line_map[0] = table_line_locus[0]  # header
    for i in range(1, len(rows_table)):
        # Skip the separator line; data row i is at table_line_locus[i+1]
        if i + 1 < len(table_line_locus):
            row_line_map[i] = table_line_locus[i + 1]
        else:
            row_line_map[i] = sec_start_line  # fallback

    for r_idx, row in enumerate(rows_table):
        cells = [c.strip() for c in row]
        if r_idx == 0 and all(
            re.match(r"^[A-Za-z .]+$", c) for c in cells
        ):
            # Header row — capture column names, skip data processing.
            table_header = cells
            continue
        if r_idx == 1 and all(set(c) <= set("-: ") for c in cells):
            # Separator row (`|---|---|`) — skip.
            continue
        # Data row
        d_id_m = _DXX_ROW_RE.match(cells[0])
        if not d_id_m:
            continue
        d_id = d_id_m.group(1)
        d_desc = d_id_m.group(2).strip()
        csf_cell_raw = cells[1]
        # CSF refs can be subcategories (FUNC.CAT-NN) or whole categories
        # (FUNC.CAT — e.g. "GV.OV (governance)"). The source uses both. We
        # capture each as {ref, kind} and aggregate csf_ids (subcats only)
        # + csf_categories (whole-category refs) for downstream consumers.
        csf_refs: list[dict[str, str]] = []
        csf_ids: list[str] = []
        csf_categories: list[str] = []
        prose_chunks: list[str] = []
        for part in re.split(r",\s*", csf_cell_raw):
            part_stripped = part.strip()
            prose_m = re.search(r"\(([^)]+)\)", part_stripped)
            if prose_m:
                prose_chunks.append(prose_m.group(1).strip())
            id_candidate = re.sub(r"\s*\([^)]*\)", "", part_stripped).strip()
            ref_m = _CSF_REF_RE.fullmatch(id_candidate)
            if ref_m:
                cat_part = ref_m.group(1)  # e.g. "GV.OV"
                num_part = ref_m.group(2)  # e.g. "01" or None
                if num_part:
                    full_id = f"{cat_part}-{num_part}"
                    csf_refs.append(
                        {"ref": full_id, "kind": "subcategory"}
                    )
                    csf_ids.append(full_id)
                else:
                    csf_refs.append({"ref": cat_part, "kind": "category"})
                    csf_categories.append(cat_part)
        csf_ids_by_d[d_id] = csf_ids
        line_no = row_line_map.get(r_idx, sec_start_line)
        out_rows.append(
            {
                "aegis_subdomain": d_id,
                "description": d_desc,
                "csf_cell_raw": csf_cell_raw,
                "csf_refs": csf_refs,
                "csf_ids": csf_ids,
                "csf_categories": csf_categories,
                "advisory_prose": prose_chunks,
                "source_locus": {
                    "start_line": line_no,
                    "end_line": line_no,
                },
            }
        )

    advisory = _crossref_advisory_blockquote(body)
    return {
        "title": cross_section.title.strip(),
        "table_header": table_header or ["AEGIS sub-domain", "Likely CSF Functions"],
        "rows": out_rows,
        "csf_ids_by_d": csf_ids_by_d,
        "advisory_blockquote": advisory,
        "source_locus": _line_locus(body, "## Cross-reference", None),
    }
