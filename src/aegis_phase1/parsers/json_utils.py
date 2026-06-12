"""Shared JSON parsing utilities for Phase 1 LLM responses."""

import json
import re
from typing import Any


def parse_json_response(raw: str) -> dict[str, Any] | None:
    """Tolerant JSON parser for LLM responses.

    Handles: pure JSON, JSON in code fences, JSON embedded in prose.
    Returns parsed dict or None if no JSON found.
    """
    if not raw or not isinstance(raw, str):
        return None

    text = raw.strip()

    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Strip code fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            result = json.loads(fence_match.group(1))
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Find first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(text[start : end + 1])
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    return None
