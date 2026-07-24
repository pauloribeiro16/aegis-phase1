"""_common — shared output helpers for Phase 1 v2 generators.

Provides:

* :func:`generate_frontmatter` — YAML frontmatter block between ``---``
  markers for a v2 document.
* :func:`write_output` — versioned file write into ``output/phase1/`` or
  ``output/phase1/versions/`` when the target already exists.
* :func:`markdown_table` — render a list of header strings and row dicts
  (or tuples) as a GitHub-flavoured Markdown table.

These are deliberately small, stateless, and dependency-free (no openpyxl
/ yaml imports) so they can be unit-tested in isolation and shared by
both Markdown and XLSX generators.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_FRONTMATTER_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe_yaml_value(value: Any) -> str:
    """Return a YAML-safe scalar representation of ``value``.

    Falls back to a quoted string when the value is not obviously scalar
    (dicts / lists) so the frontmatter remains valid YAML without pulling
    in a full dumper for the trivial case.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list | tuple):
        if not value:
            return "[]"
        items = [_safe_yaml_value(v) for v in value]
        return "[" + ", ".join(items) + "]"
    text = str(value)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", '"', "'"]) or text[0] in {"-", "?"}:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def generate_frontmatter(
    document_id: str,
    title: str,
    version: float = 1.0,
    status: str = "DRAFT",
    extra: Mapping[str, Any] | None = None,
) -> str:
    """Build a YAML frontmatter block for a v2 markdown document.

    Args:
        document_id: AEGIS document identifier (e.g. ``AEGIS-P1-04``).
        title: Human-readable document title.
        version: Document version. Defaults to ``1.0``.
        status: Document status (e.g. ``DRAFT``, ``REVIEW``, ``FINAL``).
        extra: Optional mapping of additional keys to merge into the
            frontmatter. Reserved keys (``document_id``, ``title``,
            ``version``, ``status``, ``generated_at``) cannot be
            overridden.

    Returns:
        A string containing the frontmatter enclosed in ``---`` markers
        followed by a blank line, ready to prepend to a markdown body.
    """
    reserved = {"document_id", "title", "version", "status", "generated_at"}
    payload: dict[str, Any] = {
        "document_id": document_id,
        "title": title,
        "version": float(version),
        "status": status,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if extra:
        for key, val in extra.items():
            if key in reserved:
                continue
            payload[key] = val

    lines = ["---"]
    for key, val in payload.items():
        lines.append(f"{key}: {_safe_yaml_value(val)}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def next_version(target: Path) -> int:
    """Return the next available integer version for ``target``.

    Scans existing siblings matching the ``<stem>_v<整数>.md`` pattern;
    returns ``version + 1`` of the highest known version, or ``2`` when
    only the base file exists, or ``1`` when nothing exists yet.
    """
    if not target.exists():
        return 1
    stem = target.stem
    parent = target.parent
    highest = 0
    pattern = re.compile(rf"^{re.escape(stem)}_v(\d+)(?:\..+)?$")
    for sibling in parent.iterdir():
        if not sibling.is_file():
            continue
        match = pattern.match(sibling.stem)
        if match:
            try:
                n = int(match.group(1))
            except ValueError:
                continue
            if n > highest:
                highest = n
    if highest == 0:
        return 2
    return highest + 1


def write_output(
    output_dir: str | Path,
    filename: str,
    content: str,
    version: int = 1,
) -> str:
    """Write ``content`` to ``output_dir/filename`` with auto-versioning.

    If the target path already exists, the file is instead written to
    ``output_dir/versions/filename_v{version}.md`` where ``version`` is
    one more than the highest existing version, matching the semantics
    described in the sprint contract.

    Args:
        output_dir: Destination directory. Created if missing.
        filename: File name (e.g. ``AEGIS-P1-04_Company_Context_Assessment.md``).
        content: Full file contents (frontmatter + body).
        version: Requested version number. When ``1`` and the base file
            is missing the base file is written; otherwise the next free
            version is computed automatically.

    Returns:
        Absolute path of the file actually written, as a string.
    """
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)

    target = base / filename
    if target.exists():
        versions_dir = base / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        n = next_version(target)
        stem, suffix = target.stem, target.suffix or ".md"
        versioned = versions_dir / f"{stem}_v{n}{suffix}"
        versioned.write_text(content, encoding="utf-8")
        logger.info("write_output: existing file — archived as %s", versioned)
        return str(versioned.resolve())

    target.write_text(content, encoding="utf-8")
    logger.info("write_output: wrote %s (v%s)", target, version)
    return str(target.resolve())


def markdown_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[Any] | Mapping[str, Any]],
    key_to_col: Mapping[int, str] | None = None,
) -> str:
    """Render a Markdown table from ``headers`` and ``rows``.

    Args:
        headers: Column header strings.
        rows: Iterable of rows. Each row may be a sequence (positional,
            matching ``headers`` order) or a mapping (column name ->
            value). Mixed types are accepted but discouraged.
        key_to_col: When ``rows`` are mappings, optional mapping from
            column index to mapping key. If omitted, columns are looked
            up by header text.

    Returns:
        A Markdown table string with header row, separator, and all
        data rows. Returns an empty string when ``rows`` is empty so
        the caller can ``"\n".join`` cleanly.
    """
    header_cells = [str(h).strip() for h in headers]
    out: list[str] = [
        "| " + " | ".join(header_cells) + " |",
        "| " + " | ".join(["---"] * len(header_cells)) + " |",
    ]
    for row in rows:
        if isinstance(row, Mapping):
            cols: list[str] = []
            for idx, header in enumerate(header_cells):
                if key_to_col and idx in key_to_col:
                    raw = row.get(key_to_col[idx], "")
                else:
                    raw = row.get(header, "")
                cols.append(_format_cell(raw))
            out.append("| " + " | ".join(cols) + " |")
        else:
            cells = [_format_cell(c) for c in row]
            out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def _format_cell(value: Any) -> str:
    """Normalise a Markdown table cell value.

    Replaces pipes and newlines so they do not break the row, collapses
    whitespace, and stringifies non-string values via :func:`repr`-like
    coercion.
    """
    if value is None:
        return ""
    if isinstance(value, list | tuple):
        text = ", ".join(str(v) for v in value)
    elif isinstance(value, dict):
        text = "; ".join(f"{k}={v}" for k, v in value.items())
    elif isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value)
    text = text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())
    return text or ""


def safe_get(obj: Any, *path: str, default: Any = None) -> Any:
    """Drill into nested dicts / Pydantic models safely.

    Args:
        obj: Root object (mapping or object with attributes).
        *path: Sequence of attribute / key names to traverse.
        default: Value returned when any step is missing.

    Returns:
        The resolved value or ``default``.
    """
    cursor: Any = obj
    for step in path:
        if cursor is None:
            return default
        cursor = cursor.get(step) if isinstance(cursor, Mapping) else getattr(cursor, step, None)
    return cursor if cursor is not None else default


__all__ = [
    "generate_frontmatter",
    "markdown_table",
    "next_version",
    "render_per_spec_markdown_appendix",
    "safe_get",
    "write_output",
]


# CORR-061 S3b: canonical spec list used by the appendix and by the
# per-section markdown reads below. Kept in declaration order
# (1B-01 → 1B-02 → 1C-01 → 1C-02 → 1C-03) so the rendered appendix
# always lists specs in the same order across the 9 docs.
PER_SPEC_MD_SPECS: tuple[str, ...] = (
    "P1B-LLM-01-INTERPRETATION",
    "P1B-LLM-02-RATIONALE",
    "P1C-LLM-01-OVERLAP-CLASSIFICATION",
    "P1C-LLM-02-COMPOUND-EVENT",
    "P1C-LLM-03-STRATEGIC-SYNTHESIS",
)


def get_per_spec_markdown(state: Any, spec_id: str) -> str:
    """CORR-061 S3b: read the raw markdown for one spec from pipeline state.

    Reads ``state["per_spec_markdown"][spec_id]``. Returns the empty
    string when the key is absent (deterministic-only / mock / pre-LLM
    run) so the caller can decide whether to render a placeholder or
    skip the section. Never raises; the renderers are best-effort by
    design (Q3 audit finding).
    """
    if not isinstance(state, Mapping):
        return ""
    bucket = state.get("per_spec_markdown")
    if not isinstance(bucket, Mapping):
        return ""
    raw = bucket.get(spec_id)
    return raw if isinstance(raw, str) else ""


def render_per_spec_markdown_appendix(state: Any) -> list[str]:
    """CORR-061 S3b: render the 'Appendix: Source LLM Responses' block.

    Dumps every entry of ``state["per_spec_markdown"]`` as a markdown
    sub-section keyed by spec_id. Used by all 9 doc renderers to give
    reviewers a single place to inspect the raw LLM output (instead of
    parsing the per-section narrative invoker calls).

    Behaviour:
      - Missing or empty ``per_spec_markdown`` → emits a single
        placeholder line so the appendix is always present (per the
        contract: "Add an 'Appendix' section at the end of each doc").
      - Each present spec is wrapped in a level-3 header so the
        appendix is grep-friendly.
      - Multi-call specs (P1B-LLM-01/02 concatenated per reg, P1C-LLM-01
        concatenated per domain) are dumped verbatim — the per-call
        boundary is the ``\\n\\n---\\n\\n`` separator inserted by
        :meth:`Phase1LLMInvoker._capture_per_spec_markdown`.
    """
    parts: list[str] = []
    parts.append("\n## Appendix: Source LLM Responses\n")
    parts.append(
        "Raw markdown responses captured by the S3b invoker wiring. "
        "Each subsection corresponds to one of the 5 canonical Phase 1 "
        "LLM specs. Multi-call specs (P1B-LLM-01/02 per regulation, "
        "P1C-LLM-01 per domain) are concatenated with a horizontal "
        "rule (``---``) between calls. When a spec did not run (mock "
        "mode, deterministic-only, or invoker failure) the section "
        "shows a ``(no LLM response)`` placeholder.\n"
    )
    has_any = False
    for spec_id in PER_SPEC_MD_SPECS:
        raw = get_per_spec_markdown(state, spec_id)
        parts.append(f"\n### {spec_id}\n")
        if raw:
            has_any = True
            parts.append(raw.rstrip() + "\n")
        else:
            parts.append("_(no LLM response for this spec)_\n")
    if not has_any:
        parts.append(
            "\n> **No LLM responses were captured for this run.** "
            "The pipeline ran in deterministic-only / mock mode "
            "(`MOCK_LLM=true` or no `llm_invoker` configured). "
            "Re-run with `MOCK_LLM=false` and Ollama reachable to "
            "populate this appendix.\n"
        )
    return parts
