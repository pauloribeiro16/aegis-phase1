"""Markdown structural utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_FENCED_RE = re.compile(
    r"^```([a-zA-Z0-9_+-]*)[ \t]*\n(.*?)\n```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
_BULLET_RE = re.compile(r"^-\s+(.+?)\s*$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$", re.MULTILINE)


@dataclass
class Section:
    level: int
    title: str
    body: str
    start_offset: int


def split_by_headings(text: str, min_level: int = 1, max_level: int = 6) -> list[Section]:
    matches: list[tuple[int, int, int, str]] = []
    for m in _HEADING_RE.finditer(text):
        hashes, title = m.group(1), m.group(2)
        level = len(hashes)
        if level < min_level or level > max_level:
            continue
        matches.append((m.start(), level, len(hashes), title))
    if not matches:
        return [Section(level=0, title="", body=text, start_offset=0)]
    out: list[Section] = []
    pre = text[: matches[0][0]]
    if pre.strip():
        out.append(Section(level=0, title="", body=pre, start_offset=0))
    for i, (start, level, _, title) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        out.append(Section(level=level, title=title, body=text[start:end], start_offset=start))
    return out


def heading_with_text(text: str, level: int, predicate) -> tuple[str, str] | None:
    pat = re.compile(r"^" + "#" * level + r"\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(1)
        if predicate(title):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return title, text[m.end() : end]
    return None


def numbered_section(body: str, level: int, section_num: int) -> tuple[str, str] | None:
    """Return the body of the H{level} section ``## N. <title>``.

    Extends until the next H{level} numbered ``> N`` (or EOF). Sub-sections
    with H{level} headings that do NOT start with a number are included —
    they are LOGICALLY part of section N (e.g. "## Participating regulations"
    inside §3 of a SubDomain file).
    """
    pat = re.compile(
        r"^" + "#" * level + r"\s+(?P<num>\d+)\.\s+(?P<title>.+?)\s*$",
        re.MULTILINE,
    )
    matches = list(pat.finditer(body))
    start_idx = None
    for i, m in enumerate(matches):
        if int(m.group("num")) == section_num:
            start_idx = i
            break
    if start_idx is None:
        return None
    start = matches[start_idx].start()
    end = len(body)
    for j in range(start_idx + 1, len(matches)):
        if int(matches[j].group("num")) > section_num:
            end = matches[j].start()
            break
    return matches[start_idx].group("title"), body[start:end]


def extract_fenced_blocks(text: str, lang: str | None = None) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for m in _FENCED_RE.finditer(text):
        block_lang, body = m.group(1), m.group(2)
        if lang is None or block_lang.lower() == lang.lower():
            out.append((block_lang, body))
    return out


def extract_bullets(text: str) -> list[str]:
    return [m.group(1) for m in _BULLET_RE.finditer(text)]


def extract_table_rows(text: str) -> list[list[str]]:
    """Return markdown table rows as list of cells (excluding the header divider)."""
    rows: list[list[str]] = []
    for m in _TABLE_ROW_RE.finditer(text):
        line = m.group(1)
        cells = [c.strip() for c in line.split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue  # skip header divider
        rows.append(cells)
    return rows
