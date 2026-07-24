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
        """Parse the LLM output. Tries markdown first, then JSON as fallback.

        CORR-053: the gemma4:e4b model is too deeply trained to emit JSON for
        regulatory analysis tasks, ignoring both the base_system rule 4
        reformulation (CORR-052) and the body-level "Do NOT emit JSON"
        instruction (CORR-050). So the parser tolerates BOTH formats:

        1. Markdown (preferred, per contract): extracted via regex from
           `## Status / ## Interpretations / ## Derogations` sections.
        2. JSON (fallback): if markdown fails, try RobustParser on raw text.
           If JSON parses AND validates against P1BLLM01Output, return it.
           Otherwise return combined error.

        Returns (model, "") on success or (None, error_msg) on failure.
        The invoker injects envelope fields (prompt_spec_id, schema_version,
        case_id, invocation_pattern) after parse() returns successfully.
        """
        m = _import_p1b_models()
        text = self._strip_code_fences(raw)

        # Attempt 1: markdown extraction (CORR-050 path)
        markdown_error = ""
        try:
            result = self._parse_markdown(text, m)
            if result is not None:
                return result, ""
            markdown_error = "markdown extraction did not match template"
        except Exception as e:
            markdown_error = f"markdown parse exception: {e}"

        # Attempt 2: JSON fallback (CORR-053 path)
        # First, try a direct json.loads — the gemma4:e4b model emits
        # well-formed JSON objects, so this should succeed and skip
        # RobustParser's quirks (e.g. extract_first_array grabbing a
        # nested `[]` before json_strict can see the outer `{}`).
        import json as _json

        def _normalize_json(data: Any) -> Any:
            """Coerce JSON Schema conventions to Pydantic conventions.

            gemma4:e4b follows the legacy JSON Schema (e.g. outputs
            `applicable: true/false` because the JSON Schema in
            output_schemas.yaml says `type: boolean`). The Pydantic
            models in state.py use str enums (YES/NO). This function
            bridges the two without touching either side.
            """
            if isinstance(data, dict):
                return {k: _normalize_json(v) for k, v in data.items()}
            if isinstance(data, list):
                return [_normalize_json(v) for v in data]
            if isinstance(data, bool):
                # Stricter check needed because bool is a subclass of int.
                # This converts `applicable: true` → "YES" / `false` → "NO".
                return "YES" if data else "NO"
            return data

        try:
            stripped = raw.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                json_data = _normalize_json(_json.loads(stripped))
                if isinstance(json_data, dict):
                    try:
                        model = m["P1BLLM01Output"].model_validate(json_data)
                        return model, ""
                    except ValidationError as ve:
                        return None, (
                            f"markdown parsing failed ({markdown_error}); "
                            f"JSON parsed directly but Pydantic validation "
                            f"failed: {ve}"
                        )
        except _json.JSONDecodeError:
            # Not a clean JSON object; fall through to RobustParser
            pass
        except Exception as e:
            logger.exception("Unexpected error in direct JSON path")
            # Fall through to RobustParser

        # Fallback: RobustParser (handles code fences, partial JSON, etc.)
        try:
            from aegis_phase1.prompts_v2.robust_parser import RobustParser
        except ImportError:
            RobustParser = None  # type: ignore[assignment]

        if RobustParser is None:
            return None, (
                f"markdown parsing failed (and RobustParser not available for "
                f"JSON fallback): {markdown_error}"
            )

        try:
            parse_result = RobustParser.parse(raw)
            if not parse_result.ok:
                return None, (
                    f"markdown parsing failed ({markdown_error}); "
                    f"JSON parsing also failed: {parse_result.error}"
                )
            # CORR-053: if RobustParser used the construct_minimal_object
            # fallback, the input was garbage and we got a synthetic dict
            # with placeholders. Reject this — it's not real JSON the LLM
            # emitted, it's a safety net that masks malformed input.
            if parse_result.strategy == "construct_minimal_object":
                return None, (
                    f"markdown parsing failed ({markdown_error}); "
                    f"JSON RobustParser fell back to construct_minimal_object "
                    f"(input has no real JSON structure)"
                )
            json_data = parse_result.json
            if not isinstance(json_data, dict):
                return None, (
                    f"markdown parsing failed ({markdown_error}); "
                    f"JSON parsed but is not a dict (got {type(json_data).__name__})"
                )
            # Pydantic validation: extra="ignore" tolerates envelope fields
            # the LLM might emit (prompt_spec_id, case_id, etc.).
            # The invoker will overwrite them anyway.
            try:
                model = m["P1BLLM01Output"].model_validate(json_data)
                return model, ""
            except ValidationError as ve:
                return None, (
                    f"markdown parsing failed ({markdown_error}); "
                    f"JSON parsed but Pydantic validation failed: {ve}"
                )
        except Exception as e:
            logger.exception("Unexpected error in JSON fallback path")
            return None, (
                f"markdown parsing failed ({markdown_error}); "
                f"JSON fallback raised: {e}"
            )

    def _parse_markdown(self, text: str, m: dict) -> Any | None:
        """Original markdown parser (CORR-050). Returns model or None.

        Split into a separate method so the JSON fallback (CORR-053) can
        call it cleanly and capture the markdown error message.
        """
        # Status section (required)
        status_body = self._extract_section(text, "status")
        if status_body is None:
            return None
        status_str = (self._extract_field(status_body, "status") or "").upper()
        conf_str = (self._extract_field(status_body, "confidence") or "").upper()
        if status_str not in {e.value for e in m["P1BLLM01Status"]}:
            return None

        # Interpretations section
        interpretations: list = []
        interp_body = self._extract_section(text, "interpretations") or ""
        for sub_id, sub_body in self._split_subsections(interp_body, self._SUBSEC_INT):
            entry_id = self._extract_field(sub_body, "entry_id") or ""
            applicable_str = (self._extract_field(sub_body, "applicable") or "").upper()
            if applicable_str not in {e.value for e in m["P1BLLM01Applicable"]}:
                return None
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
                return None
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
            return model
        except ValidationError:
            return None


# Registry of parsers per spec_id (extensible for CORR-051)
MARKDOWN_PARSERS: dict[str, type[MarkdownParser]] = {
    "P1B-LLM-01-INTERPRETATION": P1BLLM01Parser,
}
