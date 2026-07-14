"""Shared JSON parsing utilities for Phase 1 LLM responses."""

import json
import re
from typing import Any


def parse_json_response(raw: str) -> dict[str, Any] | list[Any] | None:
    """Tolerant JSON parser for LLM responses.

    Handles: pure JSON (dict or list), JSON in code fences,
    JSON embedded in prose. Falls back to extracting the first
    JSON array if no dict found.

    Returns parsed dict, list, or None if no JSON found.
    """
    if not raw or not isinstance(raw, str):
        return None

    text = raw.strip()

    # ── Helper: try json.loads and return result if dict or list ──
    def _try_parse(t: str) -> dict | list | None:
        try:
            result = json.loads(t)
            if isinstance(result, (dict, list)):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    # 1. Direct parse
    result = _try_parse(text)
    if result is not None:
        return result

    # 2. Code fences (dict or array)
    for pat in (
        r"```(?:json)?\s*(\{.*?\})\s*```",
        r"```(?:json)?\s*(\[.*?\])\s*```",
    ):
        m = re.search(pat, text, re.DOTALL)
        if m:
            result = _try_parse(m.group(1))
            if result is not None:
                return result

    # 3. Find first { → last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        result = _try_parse(text[start : end + 1])
        if result is not None:
            return result

    # 4. Find first [ → last ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        result = _try_parse(text[start : end + 1])
        if result is not None:
            return result

    return None
