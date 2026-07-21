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
from dataclasses import dataclass, field
from typing import Any, NamedTuple

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
    _ACTION_HEADER_PAT = re.compile(
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
        m = self._ACTION_HEADER_PAT.search(text)
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


# ─────────────────────────────────────────────────────────────────────
# V2: Per-sub-domain parser (AEGIS-P1-CORR-022 v1.2 spec)
# ─────────────────────────────────────────────────────────────────────


@dataclass
class SubdomainAdaptation:
    """One sub-domain's adaptation result."""

    subdomain_id: str
    title: str
    hl_objective: str
    directed: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "subdomain_id": self.subdomain_id,
            "title": self.title,
            "hl_objective": self.hl_objective,
            "directed": list(self.directed),
        }


@dataclass
class ParseResultV2:
    """Result of parsing per-sub-domain output (v1.2 spec)."""

    success: bool
    subdomains: list[SubdomainAdaptation]
    legacy_adapted_objective: str  # concat of HLs for downstream verbatim rendering
    error_feedback: str


class OutputParserV2:
    """Parser for the per-sub-domain MAP output (v1.2)."""

    _HEADING_RE = re.compile(
        r"^###\s+(D-\d+\.\d+)\s*[—\-]\s*(.+?)\s*$",
        re.MULTILINE,
    )
    _HL_RE = re.compile(
        r"\*\*Objective\.\*\*\s*(?P<hl>.+?)(?=\n\s*\*\*Directed objectives\.|\Z)",
        re.DOTALL,
    )
    _DIRECTED_RE = re.compile(
        r"\*\*Directed objectives\.\*\*\s*\n(?P<body>(?:-\s*\*\*[A-Z][A-Za-z0-9_]*\*\*:.*\n?)+)",
        re.DOTALL,
    )
    _BULLET_RE = re.compile(
        r"-\s*\*\*(?P<reg>[A-Z][A-Za-z0-9_]*)\*\*:\s*(?P<obj>.+?)(?=\n-|\Z)",
        re.DOTALL,
    )

    def parse(self, raw: str | None) -> ParseResultV2:
        if raw is None:
            return ParseResultV2(False, [], "", "Empty LLM output (None).")
        text = raw.strip()
        if not text:
            return ParseResultV2(False, [], "", "Empty LLM output.")
        text = self._strip_code_fences(text)

        subdomains: list[SubdomainAdaptation] = []
        matches = list(self._HEADING_RE.finditer(text))

        if not matches:
            # No headings — treat as single-block "unknown"
            hl = self._extract_hl(text)
            if hl:
                subdomains.append(SubdomainAdaptation("unknown", "unknown", hl, []))
            else:
                return ParseResultV2(False, [], "", "No parseable sub-domain block found.")
        else:
            for i, m in enumerate(matches):
                sid = m.group(1)
                title = m.group(2).strip()
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                block = text[start:end]

                hl = self._extract_hl(block)
                directed = self._extract_directed(block)

                if not hl and directed:
                    hl = "(missing HL — only directed objectives provided)"

                subdomains.append(SubdomainAdaptation(sid, title, hl, directed))

        success = any(s.hl_objective or s.directed for s in subdomains)
        legacy_ao = "\n\n".join(s.hl_objective for s in subdomains if s.hl_objective)

        if not success:
            return ParseResultV2(
                False, subdomains, legacy_ao,
                "No parseable sub-domain block found. Each block must start with '### D-XX.Y — <title>'.",
            )
        return ParseResultV2(True, subdomains, legacy_ao, "")

    def _extract_hl(self, block: str) -> str:
        m = self._HL_RE.search(block)
        if not m:
            return ""
        hl = m.group("hl").strip()
        return f"**Objective.** {hl}"

    def _extract_directed(self, block: str) -> list[dict[str, str]]:
        m = self._DIRECTED_RE.search(block)
        if not m:
            return []
        body = m.group("body")
        directed: list[dict[str, str]] = []
        for bm in self._BULLET_RE.finditer(body):
            reg = bm.group("reg").strip()
            obj = bm.group("obj").strip()
            directed.append({"regulation": reg, "objective": obj})
        return directed

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", stripped, count=1)
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]
        return stripped


# ─────────────────────────────────────────────────────────────────────
# V3: 3-block x 5-field per-sub-domain parser (AEGIS-P1-CORR-022 v1.3 spec)
# ─────────────────────────────────────────────────────────────────────


@dataclass
class ObjectiveBlock:
    """One block (Generic/GDPR/CRA) of the v1.3 output."""

    label: str
    original: str
    adapted: str
    rationale: str
    adjustments: str
    considerations: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "original": self.original,
            "adapted": self.adapted,
            "rationale": self.rationale,
            "adjustments": self.adjustments,
            "considerations": list(self.considerations),
        }

    def has_all_5_fields(self) -> bool:
        return all([
            bool(self.original),
            bool(self.adapted),
            bool(self.rationale),
            bool(self.adjustments),
            bool(self.considerations),
        ])


@dataclass
class SubdomainAdaptationV3:
    """One sub-domain's adaptation result with 3+ ObjectiveBlocks."""

    subdomain_id: str
    title: str
    blocks: list[ObjectiveBlock]

    def as_dict(self) -> dict[str, Any]:
        return {
            "subdomain_id": self.subdomain_id,
            "title": self.title,
            "blocks": [b.as_dict() for b in self.blocks],
        }


@dataclass
class ParseResultV3:
    """Result of parsing v1.3 output."""

    success: bool
    subdomains: list[SubdomainAdaptationV3]
    legacy_adapted_objective: str
    error_feedback: str


class OutputParserV3:
    """Parser for v1.3 output: 3+ blocks per sub-domain, 5 fields per block."""

    _BLOCK_HEADER_PAT = re.compile(
        r"\*\*(?P<label>[A-Za-z0-9 _]+?Objective\.)\*\*\s*\n",
    )
    _FIELD_RE = re.compile(
        r"-\s*(?P<field>Original|Adapted|Rationale|Adjustments needed)\s*:\s*"
        r"(?P<value>.+?)(?=\n-\s*(?:Original|Adapted|Rationale|Adjustments needed)\s*:"
        r"|\n\*\*[A-Za-z]|\Z)",
        re.DOTALL,
    )
    _CONSIDER_HEADER_PAT = re.compile(r"\*\*Considerations\.\*\*\s*\n")
    _CONSIDER_BULLET_RE = re.compile(
        r"-\s+(.+?)(?=\n-|\n\*\*|\Z)",
        re.DOTALL,
    )
    _SUBDOMAIN_HEADER_PAT = re.compile(
        r"^###\s+(D-\d+\.\d+)\s*[—\-]\s*(.+?)\s*$",
        re.MULTILINE,
    )

    def parse(self, raw: str | None) -> ParseResultV3:
        if raw is None:
            return ParseResultV3(False, [], "", "Empty LLM output (None).")
        text = raw.strip()
        if not text:
            return ParseResultV3(False, [], "", "Empty LLM output.")
        text = self._strip_code_fences(text)

        subdomains: list[SubdomainAdaptationV3] = []
        matches = list(self._SUBDOMAIN_HEADER_PAT.finditer(text))

        if not matches:
            blocks = self._extract_blocks(text)
            if blocks:
                subdomains.append(SubdomainAdaptationV3("unknown", "unknown", blocks))
            else:
                return ParseResultV3(False, [], "", "No parseable sub-domain block found.")
        else:
            for i, m in enumerate(matches):
                sid = m.group(1)
                title = m.group(2).strip()
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                block_text = text[start:end]
                blocks = self._extract_blocks(block_text)
                subdomains.append(SubdomainAdaptationV3(sid, title, blocks))

        success = any(s.blocks for s in subdomains)
        legacy_ao = "\n\n".join(
            b.adapted
            for s in subdomains
            for b in s.blocks
            if b.adapted
        )

        if not success:
            return ParseResultV3(
                False, subdomains, legacy_ao,
                "No parseable Objective block found. Each sub-domain must contain "
                "at least one '**<Word> Objective.**' header with the 5 fields.",
            )
        return ParseResultV3(True, subdomains, legacy_ao, "")

    def _extract_blocks(self, text: str) -> list[ObjectiveBlock]:
        blocks: list[ObjectiveBlock] = []
        headers = list(self._BLOCK_HEADER_PAT.finditer(text))
        if not headers:
            return blocks

        for i, h in enumerate(headers):
            label = h.group("label").strip()
            start = h.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            section = text[start:end]

            original = ""
            adapted = ""
            rationale = ""
            adjustments = ""
            for fm in self._FIELD_RE.finditer(section):
                field = fm.group("field").lower()
                value = fm.group("value").strip()
                if field == "original":
                    original = value
                elif field == "adapted":
                    adapted = value
                elif field == "rationale":
                    rationale = value
                elif field == "adjustments needed":
                    adjustments = value

            considerations: list[str] = []
            cm = self._CONSIDER_HEADER_PAT.search(section)
            if cm:
                cons_text = section[cm.end():]
                cons_text = re.split(r"\*\*[A-Za-z]", cons_text, maxsplit=1)[0]
                for bm in self._CONSIDER_BULLET_RE.finditer(cons_text):
                    bullet = bm.group(1).strip()
                    if bullet:
                        considerations.append(bullet)

            if original or adapted or rationale or adjustments or considerations:
                blocks.append(ObjectiveBlock(
                    label=label,
                    original=original,
                    adapted=adapted,
                    rationale=rationale,
                    adjustments=adjustments,
                    considerations=considerations,
                ))

        return blocks

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", stripped, count=1)
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]
        return stripped


__all__ = [
    "ObjectiveBlock",
    "OutputParser",
    "OutputParserV2",
    "OutputParserV3",
    "ParseResult",
    "ParseResultV2",
    "ParseResultV3",
    "SubdomainAdaptation",
    "SubdomainAdaptationV3",
]


# Backwards-compatible aliases: the original module exposed these regexes
# as module-level constants. They are kept for callers that imported them
# directly (the orchestrator/refactor code paths).
OUTPUT_RE = OutputParser.ADAPTED_RE
ADJUSTMENTS_RE = OutputParser.ADJUSTMENTS_RE
CONFIDENCE_RE = OutputParser.CONFIDENCE_RE
