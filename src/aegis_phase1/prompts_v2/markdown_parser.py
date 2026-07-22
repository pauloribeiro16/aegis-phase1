"""Markdown+regex output parsers for Phase 1 LLMs.

CORR-050: replaces JSON Schema enforcement with markdown+regex parsing.
LLM emits markdown following a section/bullet template; parser extracts
structured fields via regex. Pattern proven by OutputParserV3 (used for
MAP-DOMAIN-ADAPT in src/aegis_phase1/v2/domain/parser.py).

Public API:
  - MarkdownParser: base class with helpers (_strip_code_fences,
    _extract_section, _split_subsections, _extract_field,
    _extract_list_field). Subclasses define SECTION_PATTERNS and
    implement parse().
  - P1BLLM01Parser: concrete parser for P1B-LLM-01-INTERPRETATION.
  - MARKDOWN_PARSERS: registry {spec_id: parser_class} consulted by
    Phase1LLMInvoker to dispatch markdown-based outputs.

Envelope injection (prompt_spec_id, schema_version, case_id,
invocation_pattern) is the invoker's responsibility — NOT the parser's.
Parsers produce the content fields only; the invoker wraps the parsed
model with the envelope after parse() succeeds.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class MarkdownParser:
    """Base class. Subclasses define SECTION_PATTERNS and override parse().

    Subclasses must implement `parse(raw: str) -> tuple[BaseModel | None, str]`
    returning (parsed_model, error_feedback). If parsing fails, error_feedback
    is a human-readable message the invoker can feed back to the LLM for
    a retry.
    """

    # Override in subclasses: {section_name: compiled_regex_with_named_group}
    SECTION_PATTERNS: dict[str, re.Pattern] = {}

    # Common helpers
    _CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n|\n```\s*$", re.MULTILINE)

    @classmethod
    def _strip_code_fences(cls, text: str) -> str:
        """Tolerate models that wrap markdown in ``` fences."""
        return cls._CODE_FENCE_RE.sub("", text).strip()

    @classmethod
    def _extract_section(cls, text: str, section: str) -> str | None:
        """Extract the body of a `## Section` header until the next `## ` header."""
        pat = cls.SECTION_PATTERNS.get(section)
        if pat is None:
            return None
        m = pat.search(text)
        if m is None:
            return None
        start = m.end()
        # Find next ## header (not ### which is sub-section)
        next_h2 = re.search(r"^##\s+\S", text[start:], re.MULTILINE)
        end = start + next_h2.start() if next_h2 else len(text)
        return text[start:end].strip()

    @classmethod
    def _split_subsections(
        cls, section_body: str, header_pattern: re.Pattern
    ) -> list[tuple[str, str]]:
        """Split a section body into (sub_header_match, sub_body) pairs.

        Used to split `## Interpretations` into individual `### INT-NN` blocks.
        """
        results: list[tuple[str, str]] = []
        matches = list(header_pattern.finditer(section_body))
        for i, m in enumerate(matches):
            sub_id = m.group(1) if m.groups() else m.group(0)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(section_body)
            results.append((sub_id, section_body[start:end].strip()))
        return results

    @classmethod
    def _extract_field(cls, text: str, field_name: str) -> str | None:
        """Extract `- field_name: value` from text. Returns stripped value or None."""
        pat = re.compile(
            rf"^- \s*{re.escape(field_name)}\s*:\s*(.+?)(?=\n- |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pat.search(text)
        return m.group(1).strip() if m else None

    @classmethod
    def _extract_list_field(cls, text: str, field_name: str) -> list[str]:
        """Extract `- field_name: a, b, c` OR `- field_name:\\n  - a\\n  - b`.

        Returns list of stripped values.
        """
        # Check multi-bullet form first
        pat_multi = re.compile(
            rf"^- \s*{re.escape(field_name)}\s*:\s*\n((?:\s+-\s+.+\n?)+)",
            re.MULTILINE,
        )
        m_multi = pat_multi.search(text)
        if m_multi:
            return [
                b.strip().lstrip("-").strip()
                for b in m_multi.group(1).split("\n")
                if b.strip().lstrip("-").strip()
            ]
        # Single line, comma-separated
        single = cls._extract_field(text, field_name)
        if single is None:
            return []
        return [v.strip() for v in single.split(",") if v.strip()]

    def parse(self, raw: str) -> tuple[BaseModel | None, str]:
        """Override in subclass. Returns (model_instance, error_feedback)."""
        raise NotImplementedError


# Import here to avoid forward refs (state.py imports many things).
def _import_p1b_models():
    """Lazy import to avoid circular imports at module load."""
    from aegis_phase1.v2.state import (
        P1BLLM01Applicable,
        P1BLLM01Confidence,
        P1BLLM01Derogation,
        P1BLLM01DerogationVerdict,
        P1BLLM01Interpretation,
        P1BLLM01Output,
        P1BLLM01Status,
    )
    return {
        "P1BLLM01Output": P1BLLM01Output,
        "P1BLLM01Interpretation": P1BLLM01Interpretation,
        "P1BLLM01Derogation": P1BLLM01Derogation,
        "P1BLLM01Status": P1BLLM01Status,
        "P1BLLM01Confidence": P1BLLM01Confidence,
        "P1BLLM01Applicable": P1BLLM01Applicable,
        "P1BLLM01DerogationVerdict": P1BLLM01DerogationVerdict,
    }


class P1BLLM01Parser(MarkdownParser):
    """Parser for P1B-LLM-01-INTERPRETATION markdown output."""

    SECTION_PATTERNS = {
        "status": re.compile(r"^##\s+Status\s*$", re.MULTILINE),
        "interpretations": re.compile(r"^##\s+Interpretations\s*$", re.MULTILINE),
        "derogations": re.compile(r"^##\s+Derogations\s*$", re.MULTILINE),
    }
    _SUBSEC_INT = re.compile(r"^###\s+(INT-\d+)\s*$", re.MULTILINE)
    _SUBSEC_DER = re.compile(r"^###\s+(DER-\d+)\s*$", re.MULTILINE)

    def parse(self, raw: str) -> tuple[Any | None, str]:
        m = _import_p1b_models()
        text = self._strip_code_fences(raw)

        # Status section (required)
        status_body = self._extract_section(text, "status")
        if status_body is None:
            return None, (
                "Missing '## Status' section. Add it with "
                "`- status: OK|INSUFFICIENT_EVIDENCE|INDETERMINATE` and "
                "`- confidence: HIGH|MEDIUM|LOW`."
            )
        status_str = (self._extract_field(status_body, "status") or "").upper()
        conf_str = (self._extract_field(status_body, "confidence") or "").upper()
        if status_str not in {e.value for e in m["P1BLLM01Status"]}:
            return None, (
                f"Invalid status '{status_str}'. Must be one of: "
                "OK, INSUFFICIENT_EVIDENCE, INDETERMINATE."
            )

        # Interpretations section
        interpretations: list = []
        interp_body = self._extract_section(text, "interpretations") or ""
        for sub_id, sub_body in self._split_subsections(interp_body, self._SUBSEC_INT):
            entry_id = self._extract_field(sub_body, "entry_id") or ""
            applicable_str = (self._extract_field(sub_body, "applicable") or "").upper()
            if applicable_str not in {e.value for e in m["P1BLLM01Applicable"]}:
                return None, (
                    f"{sub_id}: invalid 'applicable' value '{applicable_str}'. "
                    "Must be YES or NO."
                )
            rationale = self._extract_field(sub_body, "activation_rationale") or ""
            interpretations.append(m["P1BLLM01Interpretation"](
                entry_id=entry_id,
                applicable=m["P1BLLM01Applicable"](applicable_str),
                activation_rationale=rationale,
                layer0_refs=self._extract_list_field(sub_body, "layer0_refs"),
                legal_refs=self._extract_list_field(sub_body, "legal_refs"),
                company_fact_refs=self._extract_list_field(sub_body, "company_fact_refs"),
            ))

        # Derogations section
        derogations: list = []
        der_body = self._extract_section(text, "derogations") or ""
        for sub_id, sub_body in self._split_subsections(der_body, self._SUBSEC_DER):
            entry_id = self._extract_field(sub_body, "entry_id") or ""
            verdict_str = (self._extract_field(sub_body, "activation_verdict") or "").upper()
            if verdict_str not in {e.value for e in m["P1BLLM01DerogationVerdict"]}:
                return None, (
                    f"{sub_id}: invalid 'activation_verdict' value '{verdict_str}'. "
                    "Must be ACTIVATED, NOT_ACTIVATED, or INDETERMINATE."
                )
            rationale = self._extract_field(sub_body, "activation_rationale") or ""
            derogations.append(m["P1BLLM01Derogation"](
                entry_id=entry_id,
                activation_verdict=m["P1BLLM01DerogationVerdict"](verdict_str),
                activation_rationale=rationale,
                layer0_refs=self._extract_list_field(sub_body, "layer0_refs"),
                legal_refs=self._extract_list_field(sub_body, "legal_refs"),
                company_fact_refs=self._extract_list_field(sub_body, "company_fact_refs"),
            ))

        # Build envelope-less model; envelope injected by invoker
        try:
            confidence = (
                m["P1BLLM01Confidence"](conf_str)
                if conf_str in {e.value for e in m["P1BLLM01Confidence"]}
                else m["P1BLLM01Confidence"].MEDIUM
            )
            model = m["P1BLLM01Output"](
                status=m["P1BLLM01Status"](status_str),
                confidence=confidence,
                interpretations=interpretations,
                derogations=derogations,
            )
            return model, ""
        except ValidationError as e:
            return None, f"Pydantic validation failed: {e}"


# Registry of parsers per spec_id (extensible for CORR-051)
MARKDOWN_PARSERS: dict[str, type[MarkdownParser]] = {
    "P1B-LLM-01-INTERPRETATION": P1BLLM01Parser,
}
