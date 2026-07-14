"""parser — Regex parser for the MAP-DOMAIN-ADAPT LLM output.

The LLM is instructed (in the prompt spec) to emit a strict markdown
block with three sections:

    ADAPTED_OBJECTIVE: <3-6 sentences>
    KEY_ADJUSTMENTS:
    - <adjustment 1>
    - <adjustment 2>
    - <adjustment 3>
    CONFIDENCE: HIGH | MEDIUM | LOW

This module defines :class:`OutputParser` which uses regexes to
extract those three fields and produces a :class:`ParseResult` with
both the parsed values and a human-readable ``error_feedback`` for
retry. It never raises on a malformed output - it always returns a
``ParseResult`` so the orchestrator can decide whether to retry.

Public API:
    ParseResult       NamedTuple(success, adapted_objective,
                                key_adjustments, confidence,
                                error_feedback)
    OutputParser      parse(raw) -> ParseResult
"""

from __future__ import annotations

import logging
import re
from typing import NamedTuple

logger = logging.getLogger(__name__)


class ParseResult(NamedTuple):
    """Result of parsing an LLM MAP-DOMAIN-ADAPT output.

    Attributes:
        success: ``True`` when all three required fields were found.
        adapted_objective: Extracted objective text (may be empty on failure).
        key_adjustments: Bullet items as a list of strings (may be empty).
        confidence: One of ``"HIGH"``, ``"MEDIUM"``, ``"LOW"``. Defaults
            to ``"LOW"`` when missing or invalid (with feedback).
        error_feedback: Human-readable string explaining the parse
            failure. Empty when ``success`` is ``True``.
    """

    success: bool
    adapted_objective: str
    key_adjustments: list[str]
    confidence: str
    error_feedback: str


class OutputParser:
    """Parse LLM markdown output using regex. Generate feedback on failure.

    The parser is stateless and side-effect-free - safe to share across
    threads and to instantiate cheaply per call if preferred.

    Tolerant design — small models (gemma4:e4b) sometimes emit variations
    like ``ADAPTED_OUTPUT:`` instead of ``ADAPTED_OBJECTIVE:``. The parser
    accepts common synonyms and falls back to "lenient" mode (accept the
    output if at least ADAPTED_OBJECTIVE-like text is present).

    Regex strategy:
        * ``ADAPTED_RE`` accepts ``ADAPTED_OBJECTIVE:`` or ``ADAPTED_OUTPUT:``.
          Greedy/lazy across newlines up to the next marker or end of input.
        * ``ADJUSTMENTS_RE`` captures bullet lines starting with ``-`` after
          the marker.
        * ``CONFIDENCE_RE`` matches ``HIGH|MEDIUM|LOW`` case-insensitively.
    """

    # Accept both "ADAPTED_OBJECTIVE:" and "ADAPTED_OUTPUT:" — common model variant
    ADAPTED_RE = re.compile(
        r"ADAPTED_(?:OBJECTIVE|OUTPUT|ADAPTATION):\s*(.+?)(?=KEY_ADJUSTMENTS:|ADJUSTMENTS:|CONFIDENCE:|$)",
        re.DOTALL | re.IGNORECASE,
    )
    ADJUSTMENTS_RE = re.compile(
        r"KEY_ADJUSTMENTS:\s*((?:- .+(?:\n(?:- .+|\s*))+))",
        re.MULTILINE,
    )
    CONFIDENCE_RE = re.compile(
        r"CONFIDENCE:\s*(HIGH|MEDIUM|LOW)",
        re.IGNORECASE,
    )
    # Lenient: any bullet list anywhere in text (used as fallback)
    _BULLET_LINE_RE = re.compile(r"^\s*[\-\*]\s+(.+?)\s*$", re.MULTILINE)
    # Also accept numbered lists "1. text", "2. text"
    _NUMBERED_LINE_RE = re.compile(r"^\s*\d+[\.\)]\s+(.+?)\s*$", re.MULTILINE)
    # Lenient: detect "Key Action Items" or "Key Changes" sections as proxy
    _ACTION_HEADER_RE = re.compile(
        r"(?:KEY ACTION ITEMS|KEY ACTION AREAS|KEY CHANGES|KEY POINTS|ACTION ITEMS|IMPLEMENTATION ROADMAP):",
        re.IGNORECASE,
    )

    def parse(self, raw: str) -> ParseResult:
        """Parse raw LLM output into a :class:`ParseResult`.

        Returns success=True if ADAPTED_OBJECTIVE is found.
        KEY_ADJUSTMENTS and CONFIDENCE are best-effort — defaults applied
        when missing (with feedback for retry).
        """
        if raw is None:
            return ParseResult(
                success=False,
                adapted_objective="",
                key_adjustments=[],
                confidence="LOW",
                error_feedback="Empty LLM output (None).",
            )

        text = self._strip_code_fences(str(raw))

        adapted = self._extract_adapted(text)
        adjustments = self._extract_adjustments(text)
        confidence, confidence_missing = self._extract_confidence(text)

        feedback_parts: list[str] = []
        if not adapted:
            feedback_parts.append(
                "Missing ADAPTED_OBJECTIVE: section. Start your output with "
                "'ADAPTED_OBJECTIVE: <text>' or 'ADAPTED_OUTPUT: <text>'."
            )
        if not adjustments:
            feedback_parts.append(
                "Missing KEY_ADJUSTMENTS: section (bullet list with - prefix). "
                "You may use 'KEY ADJUSTMENTS:' or 'KEY ACTION ITEMS:'."
            )
        if confidence_missing:
            feedback_parts.append(
                "CONFIDENCE must be HIGH, MEDIUM, or LOW on its own line."
            )

        # Lenient success: if we got the main ADAPTED_OBJECTIVE section,
        # accept even with missing secondary fields (apply defaults).
        if adapted and len(adapted) > 50:  # substantive content
            return ParseResult(
                success=True,
                adapted_objective=adapted,
                key_adjustments=adjustments,
                confidence=confidence if not confidence_missing else "MEDIUM",
                error_feedback=("" if not feedback_parts else " ".join(feedback_parts)),
            )

        if feedback_parts:
            return ParseResult(
                success=False,
                adapted_objective=adapted,
                key_adjustments=adjustments,
                confidence=confidence,
                error_feedback=" ".join(feedback_parts),
            )

        return ParseResult(
            success=True,
            adapted_objective=adapted,
            key_adjustments=adjustments,
            confidence=confidence,
            error_feedback="",
        )

    # ── Internal extractors ─────────────────────────────────────────────

    def _extract_adapted(self, text: str) -> str:
        match = self.ADAPTED_RE.search(text)
        if match:
            return match.group(1).strip()
        # Lenient fallback: first long paragraph after any header-like marker
        # Look for "Output:" or "Response:" as last resort
        for marker in ["OUTPUT:", "RESPONSE:"]:
            idx = text.find(marker)
            if idx >= 0:
                tail = text[idx + len(marker):].strip()
                # Take first paragraph (until blank line or end)
                para = tail.split("\n\n")[0].strip()
                if len(para) > 100:
                    return para
        return ""

    def _extract_adjustments(self, text: str) -> list[str]:
        # Try strict KEY_ADJUSTMENTS: first
        match = self.ADJUSTMENTS_RE.search(text)
        if match:
            block = match.group(1)
            items = self._BULLET_LINE_RE.findall(block)
            if items:
                return [self._clean_bullet(item) for item in items if self._clean_bullet(item)]
        # Fallback: any "KEY X ITEMS" / "KEY CHANGES" section
        m = self._ACTION_HEADER_RE.search(text)
        if m:
            tail = text[m.end():]
            # Stop at next blank line or end
            section = tail.split("\n\n")[0]
            items = self._BULLET_LINE_RE.findall(section)
            if not items:
                items = self._NUMBERED_LINE_RE.findall(section)
            cleaned = [self._clean_bullet(item) for item in items if self._clean_bullet(item)]
            if cleaned:
                return cleaned
        # Last resort: any bullet OR numbered items anywhere
        all_items = self._BULLET_LINE_RE.findall(text) + self._NUMBERED_LINE_RE.findall(text)
        cleaned = [self._clean_bullet(item) for item in all_items if self._clean_bullet(item)]
        if len(cleaned) >= 2:
            return cleaned[:5]
        return []

    def _extract_confidence(self, text: str) -> tuple[str, bool]:
        match = self.CONFIDENCE_RE.search(text)
        if not match:
            return "LOW", True
        return match.group(1).upper(), False

    @staticmethod
    def _clean_bullet(item: str) -> str:
        return item.strip().strip('"').strip("'").strip()

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove surrounding ````` fences so the regexes see raw sections."""
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", stripped, count=1)
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]
        return stripped


__all__ = ["OutputParser", "ParseResult"]
