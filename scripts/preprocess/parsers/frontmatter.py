"""Markdown frontmatter extraction."""
from __future__ import annotations

import re
from typing import Any

import yaml

_FENCE_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return ``(frontmatter_dict, body_text)``."""
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
        return {}, body
