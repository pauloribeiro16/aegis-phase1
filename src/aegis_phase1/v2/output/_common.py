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
    "safe_get",
    "write_output",
]
