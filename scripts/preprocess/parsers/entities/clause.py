r"""Universal Ambiguity parser for the 5 AEGIS regulations.

Each `methodology-00/PREPROCESSING/Regulation/{REG}/Ambiguity/*.md`
file falls into one of three shapes:

  - **GDPR-style** (``**Clause: <id>``** + ``**Berry anchor:**`` + Instance tables
    per clause) — used by GDPR, CRA-03_CRA.md, NIS2-04_NIS2.md, DORA-05_DORA.md
  - **H3-style** (``### 3.N <clause-id> — <Article> — <title>`` + Instance tables
    per clause) — used by CRA per-article files, NIS2 per-article, DORA per-chapter
  - **AI_Act-style** (H3 with AIA-Cxx ID + **Source locus:** + Instance tables
    with severity INSIDE the label `**Instance N — POLY — S2 — `xxx`**`)

Output entity (one per clause_id):
  {
    "id": "AIA-C01",
    "regulation": "AI_Act",
    "section_ref": "Art. 9(1)",
    "title": "Risk management system",
    "source_locus": "...",
    "instances": [
      {
        "instance_n": 1,
        "label": "POLY",
        "severity": "S2",
        "token": "risk management system",
        "commentary": "...",
        "readings": [{"reading": "R1", "text": "...", "source": "..."}, ...],
        "severity_rationale": "R1 is the literal reading. S2.",
        "berry_anchors": ["§3.3.1", "§5.1"],
        "propagation_notes": "..."
      }
    ],
    "intra_section_notes": [...],
    "source_path": "..."
  }
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# Re-used from the frontmatter + markdown utilities
from ..frontmatter import parse_frontmatter
from ..markdown import extract_fenced_blocks, extract_table_rows

# ─── Clause-level extraction ─────────────────────────────────────────────

# GDPR-style: ``**Clause: <ID>``**  followed by ID, type, obligated party,
# obligation type, Berry anchor, then instances. Supports multiple ID
# conventions across the corpus:
#   - v0.1: GDPR-C01, NIS2-C01, CRA-C01, DORA-C01, AI_Act-C01
#   - v0.2 Ch2 (Principles): GDPR-CL01..CL26
#   - v0.2 Ch3 (Rights): GDPR-RT01..RT20
#   - v0.2 Ch4 (Controller/Processor): GDPR-CP01..CP28
#   - v0.2 Ch5 (International Flows): GDPR-IF01..IF10
#   - CRA: CRA-CL01..CL176
#   - NIS2: NIS2-CL01..CL53
#   - DORA: DORA-CL4-1, CL4-2, etc. (also v0.1 DORA-C01..C28)
#   - AI_Act: AI_Act-CL01 (legacy) or AIA-C01 (canonical)
_GDPR_CLAUSE_RE = re.compile(
    r"\*\*Clause:\s*"
    r"(?P<id>(?:GDPR|NIS2|CRA|DORA|AI_Act|AIACT|AIA)"
    r"-(?:C[LP]?\d+|RT\d+|CP\d+|IF\d+|[A-Z]+\d+)(?:[a-z]|\(T5 ref\))?"
    r")\*\*"
)
# v0.1 cross-article (legacy pilot): H3 ``### 2.1 GDPR-C01 — Art. 5(1)(c) Title``
# followed by Source locus + bullet items with ``* **TAG — SEV — `token`**``
_V01_H3_CLAUSE_RE = re.compile(
    r"^###\s+(?P<num>\d+\.\d+)\s+(?P<id>(?:GDPR|NIS2|CRA|DORA|AI_Act|AIACT)-C\d+(?:[a-z]|\(T5 ref\))?)\s*—\s*(?P<article>Art\.[^—]+?)\s*—\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)
_V01_BULLET_RE = re.compile(
    r"^\*\s+\*\*(?P<tag>[A-Z][A-Za-z0-9+\- ]+?)\s+—\s+S(?P<sev>[123])\s+—\s+`(?P<token>[^`]+)`\*\*\s*(?P<commentary>.*)$",
    re.MULTILINE,
)
_GDPR_TYPE_INLINE_RE = re.compile(r"type:\s*(?P<v>[a-z_-]+)")
_GDPR_OBLIGATED_RE = re.compile(r"obligatedParty:\s*(?P<v>[A-Z_]+)")
_GDPR_OBLIGATION_RE = re.compile(r"obligationType:\s*(?P<v>[A-Z_]+)")
_GDPR_BERRY_RE = re.compile(r"\*\*Berry\s+anchor:\*\*\s*(?P<v>.+?)(?=\n\n|\Z)", re.DOTALL)
_GDPR_VARIANT_RE = re.compile(
    r"\|\s*(?P<n>R\d+|\d+)\s*\|\s*(?P<reading>[^|]+?)\s*\|\s*(?P<source>[^|]+?)\s*\|",
)

# H3-style (CRA/NIS2/DORA): ``### 3.N <CL-ID> — <Article> — <title>``
_H3_CLAUSE_RE = re.compile(
    r"^###\s+(?P<num>\d+\.\d+)\s+(?P<id>(?:CRA|NIS2|DORA)-CL[\w-]+|CL\d+-\d+)\s*—\s*(?P<article>Art\.[^—]+?)\s*—\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)
# DORA Article-style: ``### 3.1 Article 4 — Proportionality principle``
# (the detailed clauses under each Article are then numbered 4.1/4.2/...)
_DORA_ARTICLE_RE = re.compile(
    r"^###\s+(?P<num>\d+\.\d+)\s+Article\s+(?P<n>\d+)\s*—\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)
# AI_Act-style: ``### 3.N AIA-Cxx — Art. NN(N) <title>``
_AI_ACT_H3_RE = re.compile(
    r"^###\s+(?P<num>\d+\.\d+)\s+(?P<id>AIA-C\d+)\s*—\s*(?P<article>Art\.[^—]+?)\s+(?P<title>.+?)\s*$",
    re.MULTILINE,
)
_AI_ACT_H3_NUMONLY_RE = re.compile(
    r"^###\s+(?P<num>\d+\.\d+)\s+(?P<id>(?:CRA|NIS2|DORA|AIACT|AIA)-C[LP]?\d+(?:[a-z]|\(T5 ref\))?)\s*$",
    re.MULTILINE,
)

# Instance label: ``**Instance N — <LABEL> — S<SEV> — `xxx`**``
_INSTANCE_RE = re.compile(
    r"\*\*Instance\s+(?P<n>\d+)\s+—\s+(?P<label>.+?)\s+—\s+S(?P<sev>[123])\s+—\s+`(?P<token>[^`]+)`\*\*"
)
# Italic Berry anchor (used in H3-style): ``*Berry anchor:* §3.3.1``
_BERRY_ITALIC_RE = re.compile(
    r"\*Berry\s+anchor:\*\s*(?P<v>.+?)(?=\n\n|\n\*\*|\n###|\Z)", re.DOTALL
)
# Variant reading table: ``| R1 | ... | ... |``
_VARIANT_TABLE_RE = re.compile(
    r"^\|\s*(?P<n>R\d+|\d+)\s*\|\s*(?P<reading>[^|]+?)\s*\|\s*(?P<source>[^|]+?)\s*\|\s*$",
    re.MULTILINE,
)


def _extract_berries(text: str) -> list[str]:
    """Extract a list of Berry-anchor references from a block of text.
    Handles both ``**Berry anchor:**`` (GDPR) and ``*Berry anchor:*`` (H3-style).
    """
    out: list[str] = []
    # GDPR-style bold
    for m in re.finditer(r"\*\*Berry\s+anchor:\*\*\s*([^\n]+)", text):
        # Comma-separated, may include §…; §…; §…
        out.extend(s.strip() for s in m.group(1).split(";") if s.strip())
    # H3-style italic
    for m in re.finditer(r"\*Berry\s+anchor:\*\s*([^\n]+)", text):
        out.extend(s.strip() for s in m.group(1).split(";") if s.strip())
    # Dedupe, preserve order
    return list(dict.fromkeys(out))


def _extract_variants_table(text: str) -> list[dict[str, str]]:
    """Extract the variant-readings table from a block of text.

    Returns a list of ``{reading, source}`` dicts (the leading ``#`` column is
    dropped — it's just a sequence number).
    """
    out: list[dict[str, str]] = []
    for m in _VARIANT_TABLE_RE.finditer(text):
        out.append(
            {
                "reading": m.group("reading").strip(),
                "source": m.group("source").strip(),
            }
        )
    return out


def _extract_readings_from_bullets(text: str) -> list[dict[str, str]]:
    """Extract the R1/R2/R3 reading bullets that appear between Instance label
    and the variant-readings table. The bullets are formatted as
    ``- **R1:** ...`` or ``- **R1:** ...; **R2:** ...; **R3:** ...``.
    """
    out: list[dict[str, str]] = []
    for m in re.finditer(
        r"-\s+\*\*(R\d+):\*\*\s*([^\n]+)",
        text,
    ):
        out.append(
            {
                "reading": m.group(1).strip(),
                "text": m.group(2).strip(),
                "source": "",  # not separated; caller can pair with table
            }
        )
    return out


def _extract_one_instance(block: str) -> dict[str, Any] | None:
    """Extract one ``**Instance N — ... — S<SEV> — `xxx`**`` block from
    the clause text. Returns ``None`` if no Instance label is found.
    """
    m = _INSTANCE_RE.search(block)
    if not m:
        return None
    n = int(m.group("n"))
    label = m.group("label").strip()
    severity = "S" + m.group("sev")
    token = m.group("token").strip()
    # Body: from end of label to end of block (or to next Instance / next H3 / end)
    body = block[m.end() :]
    next_inst = _INSTANCE_RE.search(body)
    if next_inst:
        body = body[: next_inst.start()]
    # Commentary: text between end of label and start of R1 bullet
    r1_bullet = re.search(r"-\s+\*\*R1:\*\*", body)
    commentary = body[: r1_bullet.start()].strip() if r1_bullet else body.strip()
    # Readings: combine bullets + table
    bullet_readings = _extract_readings_from_bullets(body)
    table_readings = _extract_variants_table(body)
    # Pair by reading label
    readings_by_label: dict[str, dict[str, str]] = {}
    for r in bullet_readings:
        readings_by_label.setdefault(r["reading"], {}).update(
            {"reading": r["reading"], "text": r["text"]}
        )
    for r in table_readings:
        readings_by_label.setdefault(r["reading"], {}).update(r)
    # Preserve R1, R2, R3, R4 order
    readings = []
    for label in sorted(
        readings_by_label.keys(), key=lambda k: int(k[1:]) if k[1:].isdigit() else 999
    ):
        readings.append(readings_by_label[label])
    # Severity rationale: text after the variant table until next *Berry* / end
    berry_m = _BERRY_ITALIC_RE.search(body)
    end = berry_m.start() if berry_m else len(body)
    sev_text = body[:end].strip() if not table_readings else ""
    if not sev_text:
        # Try to find text after table like "R1 is the literal reading. S2."
        m2 = re.search(r"\| R\d +\|[^\n]+\n\s*\n([^\n]+)", body, re.MULTILINE)
        sev_text = m2.group(1).strip() if m2 else ""
    # Berry anchors
    berries = _extract_berries(body)
    # Propagation notes: text after the berry anchors, if any
    propagation = ""
    if berries:
        # everything after the last Berry anchor line
        last_berry_m = list(re.finditer(r"\*?\*?Berry\s+anchor:?\*?\*?\s*[^\n]+", body))
        if last_berry_m:
            tail = body[last_berry_m[-1].end() :].strip()
            # Strip the --- separator if present
            tail = re.sub(r"^---\s*", "", tail).strip()
            if tail and not tail.startswith("---"):
                propagation = tail
    return {
        "instance_n": n,
        "label": label,
        "severity": severity,
        "token": token,
        "commentary": commentary,
        "readings": readings,
        "severity_rationale": sev_text,
        "berry_anchors": berries,
        "propagation_notes": propagation,
    }


# ─── Clause detection dispatchers ───────────────────────────────────────


def _extract_clauses_gdpr_style(body: str, regulation: str) -> list[dict[str, Any]]:
    """GDPR (and similarly CRA-03_CRA.md, NIS2-04_NIS2.md, DORA-05_DORA.md)
    format: each clause is delimited by ``**Clause: <id>``** markers.
    """
    clauses: list[dict[str, Any]] = []
    matches = list(_GDPR_CLAUSE_RE.finditer(body))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]
        clause_id = m.group("id")
        # Extract the metadata block (id, type, obligatedParty, obligationType, ...).
        # The first ```yaml``` block usually has the metadata.
        yaml_blocks = extract_fenced_blocks(block, lang="yaml")
        meta: dict[str, Any] = {}
        for _, ybody in yaml_blocks:
            try:
                parsed = yaml.safe_load(ybody)
            except yaml.YAMLError:
                continue
            if isinstance(parsed, dict):
                meta.update(parsed)
                break  # only the first yaml block per clause carries metadata
        # Title: look for an H3 right before the **Clause:** marker
        title = ""
        h3_m = re.search(r"^###\s+(.+?)$", body[:start], re.MULTILINE)
        if h3_m:
            title = h3_m.group(1).strip()
        # Fallback title from H4
        if not title:
            h4_m = re.search(r"^####\s+(.+?)$", body[:start], re.MULTILINE)
            if h4_m:
                title = h4_m.group(1).strip()
        # Instances: find all instance blocks in the clause body
        instances = _extract_all_instances_in_block(block)
        # Berry anchor (bold, GDPR-style)
        berries = _extract_berries(block)
        # Source locus: the **Source locus:** / **Berry anchor:** pattern
        source_m = re.search(
            r"\*\*Source\s+locus:\*\*\s*\n\s*>\s*\"?(.+?)\"?\s*(?=\n\n|\Z)",
            block,
            re.DOTALL,
        )
        source_locus = source_m.group(1).strip() if source_m else ""
        # Intra-section notes
        notes = _extract_intra_section_notes(block)
        clauses.append(
            {
                "id": clause_id,
                "regulation": regulation,
                "section_ref": meta.get("article_ref", meta.get("article", "")),
                "title": title or meta.get("title", ""),
                "type": meta.get("type", ""),
                "obligated_party": meta.get("obligatedParty", ""),
                "obligation_type": meta.get("obligationType", ""),
                "source_locus": source_locus,
                "instances": instances,
                "intra_section_notes": notes,
                "berry_anchors": berries,
            }
        )
    return clauses


def _extract_clauses_h3_style(
    body: str, regulation: str, re_obj=re.compile("foo")
) -> list[dict[str, Any]]:
    """H3-style (CRA/NIS2/DORA/AI_Act): each clause is delimited by H3 headings
    like ``### 3.7 CRA-CL20 — Art. 13(3) sentence 3 — ...``.
    """
    clauses: list[dict[str, Any]] = []
    matches = list(re_obj.finditer(body))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]
        clause_id = m.group("id")
        section_ref = m.group("article").strip()
        title = m.group("title").strip()
        # Source locus: a > quoted block immediately after **Source locus:**
        source_m = re.search(
            r"\*\*Source\s+locus:\*\*\s*\n\s*>\s*\"?(.+?)\"?\s*(?=\n\n|\Z)",
            block,
            re.DOTALL,
        )
        source_locus = source_m.group(1).strip() if source_m else ""
        # Instances
        instances = _extract_all_instances_in_block(block)
        # Berry anchors
        berries = _extract_berries(block)
        # Intra-section notes
        notes = _extract_intra_section_notes(block)
        clauses.append(
            {
                "id": clause_id,
                "regulation": regulation,
                "section_ref": section_ref,
                "title": title,
                "source_locus": source_locus,
                "instances": instances,
                "intra_section_notes": notes,
                "berry_anchors": berries,
            }
        )

    # ── Add skeleton clauses from the atomic_clause_map table ──
    # For clauses that appear in the `## 2. Atomic clause map` table but
    # do NOT have a detailed H3 card (CRA 11/12, NIS2 chapters where only
    # the table is present, etc.), we synthesise a minimal skeleton entry
    # with the table's gist + type + severity.
    acm_table = _extract_atomic_clause_map_table(body)
    if acm_table:
        headers = acm_table["headers"]
        rows = acm_table["rows"]
        # Identify the column indices from the headers (case-insensitive)
        h_lower = [h.strip().lower() for h in headers]
        col_id = next(
            (i for i, h in enumerate(h_lower) if h in ("clause id", "#", "id")),
            0,
        )
        col_locus = next(
            (
                i
                for i, h in enumerate(h_lower)
                if h in ("locus", "article", "article / annex", "article/annex")
            ),
            1,
        )
        col_type = next(
            (i for i, h in enumerate(h_lower) if h in ("type", "types found")),
            None,
        )
        col_sev = next(
            (i for i, h in enumerate(h_lower) if h in ("highest sev.", "highest sev", "severity")),
            None,
        )
        col_gist = next(
            (i for i, h in enumerate(h_lower) if h == "gist"),
            None,
        )
        col_subdomain = next(
            (i for i, h in enumerate(h_lower) if h == "sub-domain"),
            None,
        )

        # Collect existing clause_ids (from the detailed H3 cards)
        existing_ids = {c["id"] for c in clauses}
        for row in rows:
            if len(row) <= col_id:
                continue
            cid = row[col_id].strip()
            if not cid or cid in existing_ids:
                continue
            locus = row[col_locus].strip() if col_locus < len(row) else ""
            type_cell = (
                row[col_type].strip() if col_type is not None and col_type < len(row) else ""
            )
            sev_cell = row[col_sev].strip() if col_sev is not None and col_sev < len(row) else ""
            gist = row[col_gist].strip() if col_gist is not None and col_gist < len(row) else ""
            subdomain = (
                row[col_subdomain].strip()
                if col_subdomain is not None and col_subdomain < len(row)
                else ""
            )
            # Strip markdown bold from the severity
            sev = sev_cell.replace("**", "").strip()
            # Strip markdown bold from types
            types_list = [t.strip() for t in re.split(r"[,;]", type_cell) if t.strip()]
            clauses.append(
                {
                    "id": cid,
                    "regulation": regulation,
                    "section_ref": locus,
                    "title": gist[:120] if gist else "",
                    "type": types_list[0] if types_list else "",
                    "types_found": types_list,
                    "sub_domain": subdomain,
                    "source_locus": "",
                    "instances": [],
                    "intra_section_notes": [
                        {
                            "label": "Atomic clause map entry",
                            "value": f"Listed in §2 atomic clause map table of this file; types={type_cell}, severity={sev}, locus={locus}, gist={gist[:200]}",
                        }
                    ],
                    "berry_anchors": [],
                    "is_skeleton": True,
                }
            )
    return clauses


def _extract_clauses_v01(body: str, regulation: str) -> list[dict[str, Any]]:
    """v0.1 cross-article (legacy pilot) format: each clause is delimited by
    ``### 2.N <CL-ID> — <Article> — <title>`` headings. Each instance is a
    markdown bullet ``* **<TAG> — S<SEV> — `token`** ...`` — no Instance N
    numbering, no reading tables, no source_locus heading (it's the first
    thing in the block).
    """
    clauses: list[dict[str, Any]] = []
    matches = list(_V01_H3_CLAUSE_RE.finditer(body))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]
        clause_id = m.group("id")
        section_ref = m.group("article").strip()
        title = m.group("title").strip()
        # Source locus: a ``**Source locus:**`` blockquote-like line
        source_m = re.search(
            r"\*\*Source\s+locus:\*\*\s*`?(.+?)`?\s*(?=\n\n|\n\*|\Z)",
            block,
            re.DOTALL,
        )
        source_locus = source_m.group(1).strip() if source_m else ""
        # Instances: each ``* **TAG — S<SEV> — `token`** ...`` bullet
        instances: list[dict[str, Any]] = []
        for bm in _V01_BULLET_RE.finditer(block):
            tag = bm.group("tag").strip()
            sev = "S" + bm.group("sev")
            token = bm.group("token").strip()
            commentary = bm.group("commentary").strip()
            instances.append(
                {
                    "instance_n": len(instances) + 1,
                    "label": tag,
                    "severity": sev,
                    "token": token,
                    "commentary": commentary,
                    "readings": [],  # v0.1 has no R1/R2/R3 tables
                    "severity_rationale": "",
                    "berry_anchors": [],
                    "propagation_notes": "",
                }
            )
        # Berry anchor (italic at the end of the block)
        berries = _extract_berries(block)
        notes = _extract_intra_section_notes(block)
        clauses.append(
            {
                "id": clause_id,
                "regulation": regulation,
                "section_ref": section_ref,
                "title": title,
                "source_locus": source_locus,
                "instances": instances,
                "intra_section_notes": notes,
                "berry_anchors": berries,
            }
        )

    # Also fall back to the atomic clause map table for any clause_ids
    # that appear only in the table (not in detailed cards).
    acm_table = _extract_atomic_clause_map_table(body)
    if acm_table:
        headers = acm_table["headers"]
        rows = acm_table["rows"]
        h_lower = [h.strip().lower() for h in headers]
        col_id = next((i for i, h in enumerate(h_lower) if h in ("clause id", "#", "id")), 0)
        col_locus = next(
            (
                i
                for i, h in enumerate(h_lower)
                if h in ("locus", "article", "article / annex", "article/annex")
            ),
            1,
        )
        col_type = next((i for i, h in enumerate(h_lower) if h in ("type", "types found")), None)
        col_sev = next(
            (i for i, h in enumerate(h_lower) if h in ("highest sev.", "highest sev", "severity")),
            None,
        )
        col_gist = next((i for i, h in enumerate(h_lower) if h == "gist"), None)
        col_subdomain = next((i for i, h in enumerate(h_lower) if h == "sub-domain"), None)
        existing_ids = {c["id"] for c in clauses}
        for row in rows:
            if len(row) <= col_id:
                continue
            cid = row[col_id].strip()
            if not cid or cid in existing_ids:
                continue
            locus = row[col_locus].strip() if col_locus < len(row) else ""
            type_cell = (
                row[col_type].strip() if col_type is not None and col_type < len(row) else ""
            )
            sev_cell = row[col_sev].strip() if col_sev is not None and col_sev < len(row) else ""
            gist = row[col_gist].strip() if col_gist is not None and col_gist < len(row) else ""
            subdomain = (
                row[col_subdomain].strip()
                if col_subdomain is not None and col_subdomain < len(row)
                else ""
            )
            sev = sev_cell.replace("**", "").strip()
            types_list = [t.strip() for t in re.split(r"[,;]", type_cell) if t.strip()]
            clauses.append(
                {
                    "id": cid,
                    "regulation": regulation,
                    "section_ref": locus,
                    "title": gist[:120] if gist else "",
                    "type": types_list[0] if types_list else "",
                    "types_found": types_list,
                    "sub_domain": subdomain,
                    "source_locus": "",
                    "instances": [],
                    "intra_section_notes": [
                        {
                            "label": "Atomic clause map entry",
                            "value": f"Listed in §1 summary table of this v0.1 file; types={type_cell}, severity={sev}, locus={locus}, gist={gist[:200]}",
                        }
                    ],
                    "berry_anchors": [],
                    "is_skeleton": True,
                }
            )
    return clauses


def _extract_all_instances_in_block(block: str) -> list[dict[str, Any]]:
    """Find every ``**Instance N — ... — S<SEV> — `xxx`**`` block within
    ``block`` and extract it. Skips anything that isn't an Instance block.
    """
    out: list[dict[str, Any]] = []
    # Find all Instance label positions
    label_positions = [(m.start(), m.end()) for m in _INSTANCE_RE.finditer(block)]
    for i, (start, end) in enumerate(label_positions):
        sub_block = block[end:]
        if i + 1 < len(label_positions):
            sub_block = block[end : label_positions[i + 1][0]]
        # Cut at next H3
        h3_m = re.search(r"^###\s+", sub_block, re.MULTILINE)
        if h3_m:
            sub_block = sub_block[: h3_m.start()]
        # Also cut at --- separator
        sep_m = re.search(r"^---\s*$", sub_block, re.MULTILINE)
        if sep_m:
            sub_block = sub_block[: sep_m.start()]
        instance = _extract_one_instance(block[start:end] + sub_block)
        if instance:
            out.append(instance)
    return out


def _extract_intra_section_notes(block: str) -> list[dict[str, str]]:
    """Extract **Proportionality-status:**, **Scope:**, **Definitional anchor:**,
    **T5 mapping mismatch:**, **In-Directive:** etc. — any ``**...:**`` block
    that is NOT an Instance, Clause, or Berry anchor.
    """
    skip_labels = {
        "Source locus",
        "Berry anchor",
        "Berry anchors",
    }
    notes: list[dict[str, str]] = []
    for m in re.finditer(
        r"\*\*(?P<label>[^*]+):\*\*\s*(?P<value>[^\n]+(?:\n(?!\*\*[^*]+:\*\*)[^\n]*)*)",
        block,
    ):
        label = m.group("label").strip()
        if label in skip_labels or label.startswith("Instance "):
            continue
        if label.startswith("Clause"):
            continue
        value = m.group("value").strip()
        if value:
            notes.append({"label": label, "value": value})
    return notes


# ─── File-level (per-article / per-chapter) extraction ───────────────────


def _extract_intro_blockquote(text: str) -> list[str]:
    """Extract the first N ``> ...`` blockquote lines that appear immediately
    after the H1 title, before the first H2.
    """
    out: list[str] = []
    for m in re.finditer(r"^>\s*(.+?)$", text, re.MULTILINE):
        out.append(m.group(1).strip())
    return out


def _extract_atomic_clause_map_table(body: str) -> dict[str, Any] | None:
    """Find the ``## 2. Atomic clause map`` table (or ``## 1. Summary table`` for
    cross-article v0.1 files).
    """
    for h2_m in re.finditer(
        r"^##\s+\d+\.\s+(Atomic clause map|Summary table)\b", body, re.MULTILINE
    ):
        after = body[h2_m.end() :]
        # Limit to next H2
        nxt = re.search(r"^##\s+", after, re.MULTILINE)
        block = after[: nxt.start()] if nxt else after
        rows = extract_table_rows(block)
        if not rows:
            return None
        # First row is the header
        return {"headers": rows[0], "rows": rows[1:]}
    return None


def _extract_clause_count_intro(body: str) -> str:
    """Find the ``**Total: N atomic clauses for <X>.**`` line."""
    m = re.search(r"\*\*Total:\s*\d+\s+atomic\s+clauses[^.]*\.?\*\*", body)
    return m.group(0).strip() if m else ""


def _extract_verbatim_text(body: str) -> str:
    """Find the ``## 1. Article X — full text`` (or similar) blockquote."""
    for h2_m in re.finditer(
        r"^##\s+1\.\s+(?:Article[^—]*—\s*full text|Module architecture|Annex[^—]*—\s*full text)",
        body,
        re.MULTILINE,
    ):
        after = body[h2_m.end() :]
        nxt = re.search(r"^##\s+", after, re.MULTILINE)
        block = after[: nxt.start()] if nxt else after
        # Take only the blockquote content
        parts: list[str] = []
        for m in re.finditer(r"^>\s*(.+?)$", block, re.MULTILINE):
            parts.append(m.group(1).strip())
        if parts:
            return "\n".join(parts)
    return ""


def _extract_intra_clause_sections(body: str) -> list[dict[str, str]]:
    """Extract any ``### 4.1 Intra-regulation``, ``### 4.2 Cross-regulation``,
    ``### 4.3 Recital anchor``-style sections (only present in AI_Act).
    """
    out: list[dict[str, str]] = []
    for h3_m in re.finditer(
        r"^###\s+(?P<num>\d+\.\d+)\s+(?P<title>[A-Z][^\n]+?)\s*$",
        body,
        re.MULTILINE,
    ):
        num = h3_m.group("num")
        title = h3_m.group("title").strip()
        # Skip H3s that are clause-cards (they have a clause_id pattern)
        if re.search(r"(GDPR|NIS2|CRA|DORA|AIACT|AIA)-C[LP]?\d", title):
            continue
        if re.search(r"^CL\d+-\d+", title):
            continue
        if re.search(r"^Article\s+\d+", title):
            continue
        # Otherwise it's an intra-clause section
        after = body[h3_m.end() :]
        nxt = re.search(r"^###\s+", after, re.MULTILINE)
        block = after[: nxt.start()] if nxt else after
        out.append({"number": num, "title": title, "raw": block.strip()})
    return out


# ─── Index / Synthesis file extraction ────────────────────────────────


def _extract_index_file(path: Path, body: str, fm: dict[str, Any]) -> dict[str, Any]:
    """Extract the structure of a 00_*_Index.md file."""
    intro = _extract_intro_blockquote(body)
    # The first table is usually a Status / Files / Chapter navigation table
    tables: list[dict[str, Any]] = []
    for h2_m in re.finditer(r"^##\s+", body, re.MULTILINE):
        after = body[h2_m.end() :]
        nxt = re.search(r"^##\s+", after, re.MULTILINE)
        block = after[: nxt.start()] if nxt else after
        for row in extract_table_rows(block):
            if row and len(row) > 1:
                tables.append(
                    {"under_h2": h2_m.group(0).strip(), "rows": tables_rows_to_dict(block)}
                )
                break
    return {
        "schema_version": "1.0",
        "id": path.stem,
        "path": str(path),
        "title": fm.get("title", path.stem),
        "intro_paragraphs": intro,
        "tables": tables,
    }


def tables_rows_to_dict(block: str) -> list[list[str]]:
    return extract_table_rows(block)


def _extract_synthesis_file(path: Path, body: str, fm: dict[str, Any]) -> dict[str, Any]:
    """Extract the structure of a 99_*_Synthesis.md file. Multiple tables
    of various shapes — keep them all as a list of named tables.
    """
    tables: list[dict[str, Any]] = []
    for h2_m in re.finditer(r"^##\s+(?P<num>\d+\.\s+[^—\n]+)", body, re.MULTILINE):
        after = body[h2_m.end() :]
        nxt = re.search(r"^##\s+", after, re.MULTILINE)
        block = after[: nxt.start()] if nxt else after
        rows = extract_table_rows(block)
        if rows:
            tables.append(
                {
                    "section": h2_m.group("num").strip(),
                    "headers": rows[0],
                    "rows": rows[1:],
                }
            )
    return {
        "schema_version": "1.0",
        "id": path.stem,
        "path": str(path),
        "title": fm.get("title", path.stem),
        "tables": tables,
    }


# ─── Public entry: parse a single Ambiguity file ───────────────────────


def parse_ambiguity_file(path: Path, regulation: str) -> dict[str, Any]:
    """Parse one Ambiguity/{REG}/*.md file and return a structured dict.

    The result has TWO top-level keys:

      - ``file``: the file-level entity (frontmatter, title, intro,
        verbatim_text, atomic_clause_map_table, etc.)
      - ``clauses``: a list of per-clause entities (one per clause_id)

    Plus a discriminator ``kind``: ``index``, ``synthesis``,
    ``cross_article``, or ``per_article``.
    """
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    stem = path.stem
    # Discriminate by filename
    if stem.startswith("00_"):
        kind = "index"
    elif stem.startswith("99_"):
        kind = "synthesis"
    else:
        # Per-article detection: filename contains a numbered Article /
        # Annex / Chapter / Section / Incident reference (e.g. Art4, AnnexI,
        # Ch2, Sec1, Inc2). Cross-article files (06_AI_Act, 02_GDPR, 03_CRA,
        # 04_NIS2, 05_DORA) do NOT have these.
        if re.search(r"_(Art|Annex|Ch|Sec|Inc)\d", stem):
            kind = "per_article"
        else:
            # No Article/Annex/Chapter/Section/Incident ref → cross-article
            # legacy v0.1 file (e.g. 06_AI_Act.md, 02_GDPR.md, 03_CRA.md,
            # 04_NIS2.md, 05_DORA.md)
            kind = "cross_article"

    if kind == "index":
        file_entity = _extract_index_file(path, body, fm)
        return {"kind": kind, "file": file_entity, "clauses": []}
    if kind == "synthesis":
        file_entity = _extract_synthesis_file(path, body, fm)
        return {"kind": kind, "file": file_entity, "clauses": []}

    # Per-article OR cross-article
    file_entity = {
        "schema_version": "1.0",
        "id": stem,
        "path": str(path),
        "frontmatter": fm,
        "title": _extract_h1_title(body) or fm.get("title", stem),
        "intro_blockquotes": _extract_intro_blockquote(body),
        "verbatim_text": _extract_verbatim_text(body),
        "atomic_clause_map_table": _extract_atomic_clause_map_table(body),
        "clause_count_intro": _extract_clause_count_intro(body),
        "intra_clause_sections": _extract_intra_clause_sections(body),
    }
    # Extract clauses
    clauses = _extract_clauses_for_kind(body, regulation, kind)
    file_entity["clause_ids"] = [c["id"] for c in clauses]
    return {"kind": kind, "file": file_entity, "clauses": clauses}


def _extract_h1_title(body: str) -> str:
    m = re.search(r"^#\s+(.+?)$", body, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _extract_clauses_for_kind(body: str, regulation: str, kind: str) -> list[dict[str, Any]]:
    """Dispatch clause extraction to the right format handler based on the
    file kind + regulation.

    Per-article H3 formats vary subtly by regulation:
      - CRA/NIS2/DORA: ``### 3.7 CRA-CL20 — Art. 13(3) sentence 3 — Title``
        (3 segments separated by ``—``)
      - AI_Act:        ``### 3.1 AIA-C01 — Art. 9(1) Risk management system``
        (2 segments — Article + title glued together)
      - DORA has both formats: per-chapter files use ``### 4.1 CL4-1 — Art. 4(1) — Title``
        (3 segments) AND ``### 3.1 Article 4 — Proportionality principle`` (no clause_id)

    v0.1 cross-article (legacy pilot) — used by GDPR 02_GDPR.md, CRA 03_CRA.md,
    NIS2 04_NIS2.md, DORA 05_DORA.md: H3 with ``### 2.1 GDPR-C01 — Art. 5(1)(c) Title``
    (2 segments separated by ``—``) + bullet items ``* **TAG — S<SEV> — `token`** ...``.
    """
    if regulation == "GDPR" and kind == "per_article":
        return _extract_clauses_gdpr_style(body, regulation)
    if regulation == "GDPR" and kind == "cross_article":
        return _extract_clauses_v01(body, regulation)
    if regulation == "CRA" and kind == "per_article":
        return _extract_clauses_h3_style(body, regulation, _H3_CLAUSE_RE)
    if regulation == "CRA" and kind == "cross_article":
        return _extract_clauses_v01(body, regulation)
    if regulation == "NIS2" and kind == "per_article":
        return _extract_clauses_h3_style(body, regulation, _H3_CLAUSE_RE)
    if regulation == "NIS2" and kind == "cross_article":
        return _extract_clauses_v01(body, regulation)
    if regulation == "DORA" and kind == "per_article":
        return _extract_clauses_h3_style(body, regulation, _H3_CLAUSE_RE)
    if regulation == "DORA" and kind == "cross_article":
        return _extract_clauses_v01(body, regulation)
    if regulation == "AI_Act" and kind in ("per_article", "cross_article"):
        return _extract_clauses_h3_style(body, regulation, _AI_ACT_H3_RE)
    return _extract_clauses_gdpr_style(body, regulation)
