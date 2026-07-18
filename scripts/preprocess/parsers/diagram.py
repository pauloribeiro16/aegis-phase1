"""Parser for fluxdiagram files (phase1, phase2, phase3, Class_Models).

These files describe the AEGIS workflow. They have:
  - YAML frontmatter (document_id, phase, parent_diagram, related_documents, changes)
  - Sections like "## Diagram 1 — Process (Doc 05 + Doc 06)" with:
    - A ```mermaid``` code block (kept as raw_mermaid)
    - A "### Step Reference" sub-section with a table:
        | # | Step | Inputs | Outputs | LLM? |
    - A "### LLM Reasoning Annotations" sub-section

We extract:
  - step_id, label, inputs[], outputs[], llm_call?{prompt_ref, model, in_tokens_est},
    deterministic?, depends_on[], errors_to[]

The parsed shape is a list of steps + the raw mermaid as a side field.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .frontmatter import parse_frontmatter
from .markdown import extract_fenced_blocks, extract_table_rows, split_by_headings

_STEP_REF_H3_RE = re.compile(r"^###\s+Step\s+Reference\s*$", re.MULTILINE | re.IGNORECASE)
_LLM_ANN_H3_RE = re.compile(
    r"^###\s+LLM\s+Reasoning\s+Annotations?\s*$", re.MULTILINE | re.IGNORECASE
)
_PROMPT_REF_RE = re.compile(r"P1[A-C]-LLM-\d+-[A-Z-]+")


def _row_to_step(row: list[str], headers: list[str], diagram_id: str) -> dict[str, Any] | None:
    """Convert a markdown table row into a step dict, using the header row to
    locate the columns.
    """
    if len(row) < 2:
        return None
    # Build a header→index map (lowercased)
    hmap = {h.strip().lower(): i for i, h in enumerate(headers)}
    if not hmap:
        return None
    # step id (first col with a short alphanumeric label like S1, R, M1-M5)
    n = ""
    for v in row:
        v = v.strip()
        if v and len(v) < 12 and re.fullmatch(r"[A-Z]?\d+(?:-[A-Z]?\d+)?", v):
            n = v
            break
    if not n:
        return None
    label = row[hmap.get("name", 1) if hmap.get("name", 1) < len(row) else 1].strip()
    type_cell = (
        row[hmap["type"]].strip() if "type" in hmap and hmap["type"] < len(row) else ""
    )
    deterministic = type_cell.lower() in {"deterministic", "decision", "process", "dispatch"}
    is_llm = "llm" in type_cell.lower() or "llm" in label.lower()
    llm_cell = row[hmap["llm"]].strip() if "llm" in hmap and hmap["llm"] < len(row) else ""
    prompt_refs = _PROMPT_REF_RE.findall(llm_cell) + _PROMPT_REF_RE.findall(type_cell)
    inputs_cell = row[hmap.get("inputs", -1)] if hmap.get("inputs", -1) < len(row) else ""
    outputs_cell = row[hmap.get("outputs", -1)] if hmap.get("outputs", -1) < len(row) else ""
    inputs = [s.strip() for s in inputs_cell.split(",") if s.strip()] if inputs_cell else []
    outputs = [s.strip() for s in outputs_cell.split(",") if s.strip()] if outputs_cell else []
    return {
        "id": f"{diagram_id}.{n}",
        "n": n,
        "label": label,
        "type": type_cell,
        "doc_section": row[hmap["doc 05 / 06 section"]].strip()
        if "doc 05 / 06 section" in hmap and hmap["doc 05 / 06 section"] < len(row)
        else "",
        "invocation_pattern": row[hmap["invocation_pattern"]].strip()
        if "invocation_pattern" in hmap and hmap["invocation_pattern"] < len(row)
        else "",
        "inputs": inputs,
        "outputs": outputs,
        "deterministic": deterministic,
        "llm_call": {
            "is_llm": is_llm,
            "prompt_refs": list(set(prompt_refs)),
            "raw": llm_cell[:200] or type_cell[:200],
        },
    }


def _extract_steps_from_table(
    text: str, diagram_id: str, default_headers: list[str] | None = None
) -> list[dict[str, Any]]:
    """Find each table under a ``### Step Reference`` header and parse it.

    The first row is treated as the header (unless ``default_headers`` is
    provided) and the rows that follow are converted to step dicts.
    """
    out: list[dict[str, Any]] = []
    # Find each "### Step Reference" block
    for ref_m in re.finditer(
        r"###\s+Step\s+Reference[^\n]*\n+", text, re.MULTILINE
    ):
        after = text[ref_m.end():]
        # Each Step Reference may have a sub-section; the table is the
        # next block of rows starting with "|"
        # Limit to next ### boundary
        nxt = re.search(r"^###\s+", after, re.MULTILINE)
        block = after[: nxt.start()] if nxt else after
        # Find all tables in the block (header row + body rows)
        rows = extract_table_rows(block)
        if not rows:
            continue
        # First non-divider row is the header
        # The first row returned by extract_table_rows that has |Step| or
        # has 4+ cells and starts with a step id pattern
        header_idx = 0
        for i, row in enumerate(rows):
            if any("step" in c.lower() or "name" in c.lower() or "#" in c for c in row):
                header_idx = i
                break
        else:
            header_idx = 0
        headers = rows[header_idx]
        for row in rows[header_idx + 1:]:
            step = _row_to_step(row, headers, diagram_id)
            if step:
                out.append(step)
    return out


def _extract_llm_annotations(text: str) -> list[dict[str, str]]:
    """Extract the LLM Reasoning Annotations block as a list of
    ``{prompt_id, purpose, knowledge_base, output_artefact, quality}``
    dicts.
    """
    m = _LLM_ANN_H3_RE.search(text)
    if not m:
        return []
    after = text[m.end():]
    nxt = re.search(r"^##\s+", after, re.MULTILINE)
    block = after[: nxt.start()] if nxt else after
    annotations: list[dict[str, str]] = []
    # Each annotation is one or more paragraphs beginning with **LLM-N: <id>** ...
    for ann_m in re.finditer(
        r"\*\*(LLM-\d+):\s*([^*]+?)\*\*\s*\n(?P<body>.+?)(?=\n\*\*LLM-\d+:|\Z)",
        block,
        re.DOTALL,
    ):
        annotations.append(
            {
                "label": ann_m.group(1).strip(),
                "purpose": ann_m.group(2).strip(),
                "body": ann_m.group("body").strip()[:1500],
            }
        )
    return annotations


def parse_diagram(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    doc_id = fm.get("document_id", f"AEGIS-DIAG-{path.stem}")
    diagram_id = doc_id.replace("AEGIS-DIAG-", "").lower()
    phase = fm.get("phase", "")
    parent_diagram = fm.get("parent_diagram", "")
    related = fm.get("related_documents", [])
    changes = fm.get("changes", "")

    # Mermaid blocks (one per "## Diagram N — ..." section)
    mermaid_blocks = [b for lang, b in extract_fenced_blocks(body, lang="mermaid")]

    # Steps: look across the whole body, since "### Step Reference" may
    # appear under multiple "## Diagram N" sections. We keep one merged
    # list (per diagram flow) — tagged by which ## section it came from.
    sections = split_by_headings(body, min_level=2, max_level=2)
    all_steps: list[dict[str, Any]] = []
    for sec in sections:
        # Try to extract "Diagram N" prefix from title
        m = re.search(r"Diagram\s+(\d+)\s*[—\-]", sec.title)
        d_n = m.group(1) if m else "1"
        for step in _extract_steps_from_table(sec.body, f"{diagram_id}.d{d_n}"):
            all_steps.append(step)
    # Also try at the top level (some files have "### Step Reference" not
    # nested under a "## Diagram N" section).
    for step in _extract_steps_from_table(body, diagram_id):
        if step not in all_steps:
            all_steps.append(step)

    llm_annotations = _extract_llm_annotations(body)

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": doc_id,
        "id": diagram_id,
        "title": fm.get("title", path.stem),
        "phase": phase,
        "parent_diagram": parent_diagram,
        "related_documents": related if isinstance(related, list) else [related],
        "changes": changes,
        "mermaid_blocks": mermaid_blocks,
        "steps": all_steps,
        "llm_annotations": llm_annotations,
    }
