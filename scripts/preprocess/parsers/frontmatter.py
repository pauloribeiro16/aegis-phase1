"""Markdown frontmatter extraction.

Mirrors ``aegis_phase1.v2.loader._parse_yaml_frontmatter`` but as an
importable, dependency-free utility. Uses ``yaml.safe_load`` for the
inner block. The fence must be the literal ``---\\n`` at the very start
of the file.
"""
from __future__ import annotations

import re
from typing import Any

import yaml

_FENCE_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_text).

    If the file does not start with a ``---`` fence, returns an empty
    dict and the original text unchanged.
    """
    m = _FENCE_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    try:
        parsed = yaml.safe_load(raw) or {}
        if not isinstance(parsed, dict):
            return {}, body
        return parsed, body
    except yaml.YAMLError:
        # Corrupt frontmatter — return empty so caller can decide.
        return {}, body
