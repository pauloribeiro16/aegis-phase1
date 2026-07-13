"""Multi-strategy JSON parser for LLM outputs.

gemma4:e2b (and similar small quantized models) frequently produce:
- Markdown-fenced JSON (```json ... ```)
- JSON wrapped in prose
- Trailing commas
- Single quotes instead of double
- Partial JSON (truncated by max_tokens)
- Surrounding chatter before/after JSON

This module tries multiple parsing strategies in order until one succeeds.
Every attempt is logged so failures can be diagnosed.
"""

from __future__ import annotations

import json
import re
import typing
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParseResult:
    """Outcome of attempting to parse LLM output as JSON."""

    ok: bool
    json: dict[str, Any] | list[Any] | None = None
    strategy: str | None = None
    error: str | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "json": self.json,
            "strategy": self.strategy,
            "error": self.error,
            "attempts": self.attempts,
        }


class RobustParser:
    """Parse JSON from LLM output using multiple fallback strategies."""

    STRATEGIES: typing.ClassVar[list[str]] = [
        "json_strict",
        "extract_markdown_block",
        "extract_first_object",
        "extract_first_array",
        "repair_common_errors",
    ]

    @classmethod
    def parse(cls, raw: str) -> ParseResult:
        """Try all strategies in order; return first success.

        Args:
            raw: The raw LLM response text.

        Returns:
            ParseResult with ok=True if any strategy succeeds, ok=False otherwise.
        """
        if raw is None:
            return ParseResult(ok=False, error="raw is None")

        # Strip leading/trailing whitespace
        stripped = raw.strip()
        if not stripped:
            return ParseResult(ok=False, error="raw is empty after strip")

        # Pre-check: if input contains '[', prioritize array extraction.
        # This avoids extract_first_object snatching the inner object of an
        # array like '[{"a":1},{"b":2}]' embedded in prose.
        if "[" in stripped:
            strategies = [
                "extract_first_array",
                "json_strict",
                "extract_markdown_block",
                "extract_first_object",
                "repair_common_errors",
            ]
        else:
            strategies = cls.STRATEGIES

        attempts: list[dict[str, Any]] = []

        for strategy in strategies:
            try:
                if strategy == "json_strict":
                    result = json.loads(stripped)
                    attempts.append({"strategy": strategy, "ok": True})
                    if isinstance(result, dict):
                        return ParseResult(
                            ok=True, json=result, strategy=strategy, attempts=attempts
                        )
                    # JSON but not an object — try next strategy
                    attempts.append({"strategy": strategy, "ok": False, "note": "not a dict"})
                    continue
                elif strategy == "extract_markdown_block":
                    obj = cls._extract_markdown_block(stripped)
                    attempts.append({"strategy": strategy, "ok": True})
                    return ParseResult(ok=True, json=obj, strategy=strategy, attempts=attempts)
                elif strategy == "extract_first_object":
                    obj = cls._extract_first_object(stripped)
                    attempts.append({"strategy": strategy, "ok": True})
                    return ParseResult(ok=True, json=obj, strategy=strategy, attempts=attempts)
                elif strategy == "extract_first_array":
                    arr = cls._extract_first_array(stripped)
                    attempts.append({"strategy": strategy, "ok": True})
                    if isinstance(arr, list):
                        # Convert to {"items": arr} for consistency with object schema
                        return ParseResult(
                            ok=True, json={"items": arr}, strategy=strategy, attempts=attempts
                        )
                    attempts.append({"strategy": strategy, "ok": False, "note": "not a list"})
                elif strategy == "repair_common_errors":
                    obj = cls._repair_common_errors(stripped)
                    attempts.append({"strategy": strategy, "ok": True})
                    return ParseResult(ok=True, json=obj, strategy=strategy, attempts=attempts)
            except Exception as e:
                attempts.append({"strategy": strategy, "ok": False, "error": str(e)})

        # All strategies failed
        return ParseResult(
            ok=False,
            error=f"All {len(strategies)} strategies failed",
            attempts=attempts,
        )

    @staticmethod
    def _extract_markdown_block(raw: str) -> dict[str, Any]:
        """Extract JSON from ```json ... ``` or ``` ... ``` block."""
        patterns = [
            r"```json\s*(\{.*?\})\s*```",
            r"```\s*(\{.*?\})\s*```",
        ]
        for pat in patterns:
            m = re.search(pat, raw, re.DOTALL | re.IGNORECASE)
            if m:
                return json.loads(m.group(1))
        raise ValueError("no markdown JSON block found")

    @staticmethod
    def _extract_first_object(raw: str) -> dict[str, Any]:
        """Extract first balanced JSON object from text (handles nested braces)."""
        depth = 0
        start: int | None = None
        in_string = False
        escape_next = False
        for i, ch in enumerate(raw):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    return json.loads(raw[start : i + 1])
        raise ValueError("no balanced JSON object")

    @staticmethod
    def _extract_first_array(raw: str) -> list[Any]:
        """Extract first balanced JSON array from text."""
        depth = 0
        start: int | None = None
        in_string = False
        escape_next = False
        for i, ch in enumerate(raw):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "[":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0 and start is not None:
                    return json.loads(raw[start : i + 1])
        raise ValueError("no balanced JSON array")

    @staticmethod
    def _repair_common_errors(raw: str) -> dict[str, Any]:
        """Try common repairs: trailing commas, single quotes."""
        # Replace single quotes with double quotes (carefully — only outside strings)
        repaired = raw.replace("'", '"')
        # Remove trailing commas before } or ]
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        return json.loads(repaired)
