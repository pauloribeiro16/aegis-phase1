"""Lightweight markdown structural utilities.

Pure regex-based — we are NOT building a full AST, just enough to split
sections, extract ``\\`\\`\\`yaml\\`\\`\\` blocks, and find heading anchors.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Heading at any level (##, ###, #### ...)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_H3_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)

# Fenced code block: ```lang\n...\n```
_FENCED_RE = re.compile(
    r"^```([a-zA-Z0-9_+-]*)[ \t]*\n(.*?)\n```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)

# Bullet list item (only ` `-prefixed for now)
_BULLET_RE = re.compile(r"^-\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Section:
    level: int
    title: str
    body: str
    start_offset: int


def split_by_headings(text: str, min_level: int = 1, max_level: int = 6) -> list[Section]:
    """Split ``text`` into sections at headings ``#`` ... ``######``.

    The first section (before any heading) has ``level=0`` and
    ``title=""``. Section bodies are inclusive of the heading line.
    """
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


def find_h2_sections(text: str) -> list[Section]:
    """Shortcut for ``split_by_headings(text, 2, 2)``."""
    return split_by_headings(text, min_level=2, max_level=2)


def extract_fenced_blocks(text: str, lang: str | None = None) -> list[tuple[str, str]]:
    """Return ``[(lang, body), ...]`` for each fenced code block.

    If ``lang`` is set, only blocks with that language are returned.
    """
    out: list[tuple[str, str]] = []
    for m in _FENCED_RE.finditer(text):
        block_lang, body = m.group(1), m.group(2)
        if lang is None or block_lang.lower() == lang.lower():
            out.append((block_lang, body))
    return out


def extract_bullets(text: str) -> list[str]:
    """Return the bullet lines (without the leading ``- ``) in ``text``."""
    return [m.group(1) for m in _BULLET_RE.finditer(text)]


def heading_with_text(text: str, level: int, predicate) -> tuple[str, str] | None:
    """Find the first heading of ``level`` whose title matches ``predicate(title)``.

    Returns ``(title, body_after_heading_until_next_same_level_heading)``.
    """
    pat = re.compile(r"^" + "#" * level + r"\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(1)
        if predicate(title):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return title, text[m.end():end]
    return None
