"""Multi-strategy JSON parser for LLM outputs.

gemma4:e2b (and similar small quantized models) frequently produce:
- Markdown-fenced JSON (```json ... ```)
- JSON wrapped in prose
- Trailing commas
- Single quotes instead of double
- Partial JSON (truncated by max_tokens)
- Surrounding chatter before/after JSON
- Prose with embedded JSON-like fragments
- Long prose with structured data scattered throughout

This module tries multiple parsing strategies in order until one succeeds.
The last strategy (construct_minimal_object) is a FALLBACK that always
succeeds with a minimal valid object, so the caller always gets something
back rather than 5 retries failing.
Every attempt is logged so failures can be diagnosed.
"""

from __future__ import annotations

import contextlib
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
        "extract_json_like_block",
        "regex_extract_fields",
        "construct_minimal_object",
    ]

    @classmethod
    def parse(cls, raw: str) -> ParseResult:
        """Try all strategies in order; return first success.

        Args:
            raw: The raw LLM response text.

        Returns:
            ParseResult with ok=True if any strategy succeeds. The last
            strategy (construct_minimal_object) is a fallback that always
            succeeds, so ok=True is guaranteed unless raw is None/empty.
        """
        if raw is None:
            return ParseResult(ok=False, error="raw is None")

        stripped = raw.strip()
        if not stripped:
            return ParseResult(ok=False, error="raw is empty after strip")

        # Pre-check: if the text contains "[", the response likely contains a
        # top-level array. Prioritize extract_first_array so we don't grab a
        # nested inner object first (e.g. "Output: [{"a": 1}, {"b": 2}] end"
        # would otherwise match {"a": 1} via extract_first_object).
        strategies: list[str] = list(cls.STRATEGIES)
        if "[" in stripped and "extract_first_array" in strategies:
            strategies.remove("extract_first_array")
            strategies.insert(0, "extract_first_array")

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
                        return ParseResult(
                            ok=True, json={"items": arr}, strategy=strategy, attempts=attempts
                        )
                    attempts.append({"strategy": strategy, "ok": False, "note": "not a list"})
                elif strategy == "repair_common_errors":
                    obj = cls._repair_common_errors(stripped)
                    attempts.append({"strategy": strategy, "ok": True})
                    return ParseResult(ok=True, json=obj, strategy=strategy, attempts=attempts)
                elif strategy == "extract_json_like_block":
                    obj = cls._extract_json_like_block(stripped)
                    if obj is not None:
                        attempts.append({"strategy": strategy, "ok": True})
                        return ParseResult(ok=True, json=obj, strategy=strategy, attempts=attempts)
                    attempts.append({"strategy": strategy, "ok": False, "note": "no json-like block"})
                elif strategy == "regex_extract_fields":
                    obj = cls._regex_extract_fields(stripped)
                    if obj:
                        attempts.append({"strategy": strategy, "ok": True})
                        return ParseResult(ok=True, json=obj, strategy=strategy, attempts=attempts)
                    attempts.append({"strategy": strategy, "ok": False, "note": "no fields matched"})
                elif strategy == "construct_minimal_object":
                    obj = cls._construct_minimal_object(stripped)
                    attempts.append({"strategy": strategy, "ok": True})
                    return ParseResult(ok=True, json=obj, strategy=strategy, attempts=attempts)
            except Exception as e:
                attempts.append({"strategy": strategy, "ok": False, "error": str(e)})

        # Fallback (should never reach here since construct_minimal_object always succeeds)
        return ParseResult(
            ok=True,
            json=cls._construct_minimal_object(stripped),
            strategy="construct_minimal_object_fallback",
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
        """Try common repairs: trailing commas, single quotes, Python booleans."""
        repaired = raw.replace("'", '"')
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        repaired = re.sub(r"\bTrue\b", "true", repaired)
        repaired = re.sub(r"\bFalse\b", "false", repaired)
        repaired = re.sub(r"\bNone\b", "null", repaired)
        return json.loads(repaired)

    @staticmethod
    def _extract_json_like_block(raw: str) -> dict[str, Any] | list[Any] | None:
        """Find the LONGEST balanced {...} or [...] block in the text.

        Useful when extract_first_object grabs a short inner object before
        finding the real outer one. Picks the largest candidate.
        """
        candidates: list[tuple[int, str]] = []
        for open_ch, close_ch in [("{", "}"), ("[", "]")]:
            i = 0
            while i < len(raw):
                if raw[i] == open_ch:
                    depth = 0
                    in_string = False
                    escape_next = False
                    for j in range(i, len(raw)):
                        ch = raw[j]
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
                        if ch == open_ch:
                            depth += 1
                        elif ch == close_ch:
                            depth -= 1
                            if depth == 0:
                                candidate = raw[i : j + 1]
                                if candidate.count(open_ch) == candidate.count(close_ch):
                                    candidates.append((len(candidate), candidate))
                                i = j
                                break
                    else:
                        break
                i += 1
        if not candidates:
            return None
        # Return the longest candidate (largest block)
        best = max(candidates, key=lambda x: x[0])[1]
        # Try parse as-is, then with Python-boolean repair
        try:
            return json.loads(best)
        except json.JSONDecodeError:
            repaired = best
            repaired = re.sub(r"\bTrue\b", "true", repaired)
            repaired = re.sub(r"\bFalse\b", "false", repaired)
            repaired = re.sub(r"\bNone\b", "null", repaired)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                return None

    @staticmethod
    def _regex_extract_fields(raw: str) -> dict[str, Any] | None:
        """Extract structured fields from prose using regex.

        Handles long prose with embedded JSON-like fragments like:
          "key": "value"     (strings)
          "key": true|false  (booleans)
          "key": number       (integers)
          "key": ["a", "b"]   (simple string arrays)
        """
        result: dict[str, Any] = {}
        # Strings
        for m in re.finditer(r'"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:\s*"([^"\\]*)"', raw):
            key = m.group(1)
            if key not in result:
                result[key] = m.group(2)
        # Booleans
        for m in re.finditer(r'"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:\s*(true|false)\b', raw):
            key = m.group(1)
            if key not in result:
                result[key] = m.group(2) == "true"
        # Numbers
        for m in re.finditer(r'"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:\s*(-?\d+)\b', raw):
            key = m.group(1)
            if key not in result:
                with contextlib.suppress(ValueError):
                    result[key] = int(m.group(2))
        # Arrays (simplified: just strings)
        for m in re.finditer(r'"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:\s*\[([^\]]*)\]', raw):
            key = m.group(1)
            if key not in result:
                items_str = m.group(2)
                items = re.findall(r'"([^"]*)"', items_str)
                result[key] = items
        return result if result else None

    @staticmethod
    def _construct_minimal_object(text: str) -> dict[str, Any]:
        """Last-resort: construct a minimal valid object from any data we can detect.

        This is the FALLBACK that always succeeds so the caller gets SOMETHING
        back instead of 5 retries failing. The result has status=INSUFFICIENT_EVIDENCE
        (caller can decide to retry with more context, or proceed with empty data).
        """
        result: dict[str, Any] = {
            "status": "INSUFFICIENT_EVIDENCE",
            "interpretations": [],
            "derogations": [],
            "synthesis": {"rationale": ""},
            "sub_domain_activations": [],
        }
        # Try to extract any entry_id-like things from the prose
        ids = re.findall(
            r'(?:entry_id|spec_id|event_id|interpretation_id)["\s:=]+["\']?([A-Z0-9_\-]+)',
            text,
        )
        if ids:
            result["interpretations"] = [
                {
                    "entry_id": ids[0],
                    "applicable": False,
                    "activation_rationale": "Parser fallback (incomplete response)",
                    "layer0_refs": [],
                    "company_fact_refs": [],
                }
            ]
        return result
