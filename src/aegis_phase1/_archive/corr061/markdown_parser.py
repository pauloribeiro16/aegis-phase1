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
from typing import Any, ClassVar

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
        """Tolerate models that wrap markdown in ``` fences or conversational preambles."""
        text = text.strip()
        fence_match = re.search(r"```(?:markdown)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
        if fence_match and ("##" in fence_match.group(1) or "#" in fence_match.group(1)):
            return fence_match.group(1).strip()
        cleaned = re.sub(r"^```[a-zA-Z]*\s*$", "", text, flags=re.MULTILINE)
        return cleaned.strip()

    @classmethod
    def _extract_section(cls, text: str, section: str) -> str | None:
        """Extract the body of a header until the next header of equal/higher level."""
        pat = cls.SECTION_PATTERNS.get(section)
        if pat is None:
            return None
        m = pat.search(text)
        if m is None:
            return None
        start = m.end()
        # Find next # or ## header (not ### or deeper sub-sections if section was ##)
        next_h = re.search(r"^#{1,2}\s+[A-Za-z0-9]", text[start:], re.MULTILINE)
        end = start + next_h.start() if next_h else len(text)
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
        """Extract field_name: value from text, tolerating bold keys, bullets (*, -), and case."""
        escaped = re.escape(field_name)
        pat = re.compile(
            rf"^[ \t*#-]*\**{escaped}\**[ \t]*:[ \t]*(.+?)(?=\n[ \t]*[-*#]|\n[ \t]*\n|\Z)",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        m = pat.search(text)
        if m:
            val = m.group(1).strip()
            val = re.sub(r"^\*+|\*+$", "", val).strip()
            return val.strip("`\"'")
        return None

    @classmethod
    def _extract_list_field(cls, text: str, field_name: str) -> list[str]:
        """Extract list from bullet or comma separated values, tolerating bold keys."""
        escaped = re.escape(field_name)
        pat_multi = re.compile(
            rf"^[ \t*#-]*\**{escaped}\**[ \t]*:[ \t]*\n((?:[ \t]+[-*][ \t]+.+\n?)+)",
            re.MULTILINE | re.IGNORECASE,
        )
        m_multi = pat_multi.search(text)
        if m_multi:
            return [
                re.sub(r"^\*+|\*+$", "", b.strip().lstrip("-*").strip()).strip("`\"'")
                for b in m_multi.group(1).split("\n")
                if b.strip().lstrip("-*").strip()
            ]
        single = cls._extract_field(text, field_name)
        if single is None:
            return []
        single = single.strip("[]")
        return [
            re.sub(r"^\*+|\*+$", "", v.strip()).strip("`\"'")
            for v in single.split(",")
            if v.strip() and re.sub(r"^\*+|\*+$", "", v.strip()).strip("`\"'")
        ]

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
        "status": re.compile(r"^#{1,3}\s+(?:\d+[.:\s]+)?Status\b.*$", re.MULTILINE | re.IGNORECASE),
        "interpretations": re.compile(r"^#{1,3}\s+(?:\d+[.:\s]+)?Interpretations?\b.*$", re.MULTILINE | re.IGNORECASE),
        "derogations": re.compile(r"^#{1,3}\s+(?:\d+[.:\s]+)?Derogations?\b.*$", re.MULTILINE | re.IGNORECASE),
    }
    _SUBSEC_INT = re.compile(r"^#{2,4}\s+(?:###\s*)?(INT-\d+)\b.*$", re.MULTILINE | re.IGNORECASE)
    _SUBSEC_DER = re.compile(r"^#{2,4}\s+(?:###\s*)?(DER-\d+)\b.*$", re.MULTILINE | re.IGNORECASE)

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
        # Accept both `- status:` and `- applicable:` under `## Status`.
        raw_status = (
            self._extract_field(status_body, "status")
            or self._extract_field(status_body, "applicable")
            or ""
        ).upper()
        if raw_status in ("APPLICABLE", "YES", "TRUE", "PASS", "ACTIVATED"):
            status_str = "YES"
        elif raw_status in ("NOT_APPLICABLE", "NO", "FALSE", "FAIL", "NOT_ACTIVATED"):
            status_str = "NO"
        elif raw_status in ("INSUFFICIENT", "INSUFFICIENT_EVIDENCE"):
            status_str = "INSUFFICIENT_EVIDENCE"
        elif raw_status in ("INDETERMINATE", "UNKNOWN", "UNCERTAIN"):
            status_str = "INDETERMINATE"
        elif raw_status in ("OK", "SUCCESS", "VALID"):
            status_str = "OK"
        else:
            status_str = raw_status

        if status_str not in {e.value for e in m["P1BLLM01Status"]}:
            return None

        conf_raw = (self._extract_field(status_body, "confidence") or "").upper()
        if conf_raw in ("HIGH", "MEDIUM", "LOW"):
            conf_str = conf_raw
        else:
            conf_str = "MEDIUM"

        # Interpretations section
        interpretations: list = []
        interp_body = self._extract_section(text, "interpretations") or ""
        interp_subs = self._split_subsections(interp_body, self._SUBSEC_INT)
        if interp_subs:
            # Original format: `### INT-NN` sub-sections
            for sub_id, sub_body in interp_subs:
                entry_id = self._extract_field(sub_body, "entry_id") or sub_id
                raw_app = (self._extract_field(sub_body, "applicable") or "").upper()
                if raw_app in ("APPLICABLE", "YES", "TRUE", "PASS", "ACTIVATED"):
                    applicable_str = "YES"
                elif raw_app in ("NOT_APPLICABLE", "NO", "FALSE", "FAIL", "NOT_ACTIVATED"):
                    applicable_str = "NO"
                elif raw_app in ("INDETERMINATE", "UNKNOWN", "UNCERTAIN"):
                    applicable_str = "INDETERMINATE"
                else:
                    applicable_str = raw_app
                if applicable_str not in {e.value for e in m["P1BLLM01Applicable"]}:
                    continue
                rationale = (
                    self._extract_field(sub_body, "activation_rationale")
                    or self._extract_field(sub_body, "rationale")
                    or ""
                )
                interpretations.append(m["P1BLLM01Interpretation"](
                    entry_id=entry_id,
                    applicable=m["P1BLLM01Applicable"](applicable_str),
                    activation_rationale=rationale,
                    layer0_refs=self._extract_list_field(sub_body, "layer0_refs"),
                    legal_refs=self._extract_list_field(sub_body, "legal_refs"),
                    company_fact_refs=self._extract_list_field(sub_body, "company_fact_refs"),
                ))
        else:
            # Bullet-list fallback
            _BULLET_RE = re.compile(
                r"^(?:[-*]\s*|\d+[.:\s]+)?\**([A-Z][A-Z0-9_]+(?:-[A-Z0-9_]+)*)\**\s*"
                r"\((YES|NO|INDETERMINATE|APPLICABLE|NOT_APPLICABLE)\)\s*:\s*(.+?)(?=\n[-*\d]|\n## |\Z)",
                re.MULTILINE | re.DOTALL | re.IGNORECASE,
            )
            for m_b in _BULLET_RE.finditer(interp_body):
                entry_id = m_b.group(1).strip()
                raw_v = m_b.group(2).strip().upper()
                if raw_v in ("APPLICABLE", "YES"):
                    verdict = "YES"
                elif raw_v in ("NOT_APPLICABLE", "NO"):
                    verdict = "NO"
                else:
                    verdict = "INDETERMINATE"
                rationale = m_b.group(3).strip()
                interpretations.append(m["P1BLLM01Interpretation"](
                    entry_id=entry_id,
                    applicable=m["P1BLLM01Applicable"](verdict),
                    activation_rationale=rationale,
                    layer0_refs=[],
                    legal_refs=[],
                    company_fact_refs=[],
                ))

        # Derogations section
        derogations: list = []
        der_body = self._extract_section(text, "derogations") or ""
        der_subs = self._split_subsections(der_body, self._SUBSEC_DER)
        if der_subs:
            # Original format: `### DER-NN` sub-sections
            for sub_id, sub_body in der_subs:
                entry_id = self._extract_field(sub_body, "entry_id") or sub_id
                raw_verdict = (
                    self._extract_field(sub_body, "activation_verdict")
                    or self._extract_field(sub_body, "verdict")
                    or ""
                ).upper()
                if raw_verdict in ("NOT_ACTIVATED", "NO", "FALSE", "NOT_APPLICABLE"):
                    verdict_str = "NOT_ACTIVATED"
                elif raw_verdict in ("ACTIVATED", "YES", "TRUE", "APPLICABLE"):
                    verdict_str = "ACTIVATED"
                elif raw_verdict in ("INDETERMINATE", "UNKNOWN"):
                    verdict_str = "INDETERMINATE"
                else:
                    verdict_str = raw_verdict
                if verdict_str not in {e.value for e in m["P1BLLM01DerogationVerdict"]}:
                    continue
                rationale = (
                    self._extract_field(sub_body, "activation_rationale")
                    or self._extract_field(sub_body, "rationale")
                    or ""
                )
                derogations.append(m["P1BLLM01Derogation"](
                    entry_id=entry_id,
                    activation_verdict=m["P1BLLM01DerogationVerdict"](verdict_str),
                    activation_rationale=rationale,
                    layer0_refs=self._extract_list_field(sub_body, "layer0_refs"),
                    legal_refs=self._extract_list_field(sub_body, "legal_refs"),
                    company_fact_refs=self._extract_list_field(sub_body, "company_fact_refs"),
                ))
        else:
            # Bullet-list fallback (symmetric to interpretations)
            _BULLET_RE_DER = re.compile(
                r"^(?:[-*]\s*|\d+[.:\s]+)?\**([A-Z][A-Z0-9_]+(?:-[A-Z0-9_]+)*)\**\s*"
                r"\((ACTIVATED|NOT_ACTIVATED|INDETERMINATE|YES|NO)\)\s*:\s*(.+?)(?=\n[-*\d]|\n## |\Z)",
                re.MULTILINE | re.DOTALL | re.IGNORECASE,
            )
            for m_b in _BULLET_RE_DER.finditer(der_body):
                entry_id = m_b.group(1).strip()
                raw_v = m_b.group(2).strip().upper()
                if raw_v in ("ACTIVATED", "YES"):
                    verdict = "ACTIVATED"
                elif raw_v in ("NOT_ACTIVATED", "NO"):
                    verdict = "NOT_ACTIVATED"
                else:
                    verdict = "INDETERMINATE"
                rationale = m_b.group(3).strip()
                derogations.append(m["P1BLLM01Derogation"](
                    entry_id=entry_id,
                    activation_verdict=m["P1BLLM01DerogationVerdict"](verdict),
                    activation_rationale=rationale,
                    layer0_refs=[],
                    legal_refs=[],
                    company_fact_refs=[],
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


class GenericMarkdownParser(MarkdownParser):
    """CORR-066: spec-agnostic markdown parser.

    Captures the canonical ``## Status`` block (with ``- applicable:``
    and ``- confidence:`` fields) and stores every other ``## Section``
    body verbatim in ``sections[section_name]``. Used for the 4 LLMs
    that don't have a hand-rolled parser yet:

      - P1B-LLM-02-RATIONALE
      - P1C-LLM-01-OVERLAP-CLASSIFICATION
      - P1C-LLM-02-COMPOUND-EVENT
      - P1C-LLM-03-STRATEGIC-SYNTHESIS

    The raw markdown is also captured in
    ``state['per_spec_markdown'][spec_id]`` (CORR-061 S3b) for
    renderers that want the original text.
    """

    # Accept any ``# Section`` or ``## Section`` header — the parser is spec-agnostic.
    _H2_SPLIT_RE = re.compile(r"^#{1,2}\s+(.+?)\s*$", re.MULTILINE)

    # Envelope fields injected by the invoker — never treated as content sections.
    _ENVELOPE_KEYS = frozenset(
        {"prompt_spec_id", "schema_version", "case_id", "invocation_pattern", "lane_id"}
    )

    def _parse_json_envelope(self, raw: str, m: dict) -> Any | None:
        """Parse a pure-JSON output envelope into a GenericMarkdownOutput.

        Mirrors P1BLLM01Parser's direct-JSON fallback: status/confidence are
        read from the top-level object, every other key becomes a verbatim
        ``## <key>`` section (JSON pretty-printed) so downstream renderers
        keep the content. Returns None when the raw text is not JSON.
        """
        import json as _json

        text = self._strip_code_fences(raw).strip()
        if not text.startswith("{"):
            return None
        try:
            obj = _json.loads(text)
        except _json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        # Heuristic guard: envelope-ish payloads carry the invoker's spec id.
        if "prompt_spec_id" not in obj and "status" not in obj:
            return None

        raw_status = str(obj.get("status", "")).upper()
        if raw_status in ("APPLICABLE", "YES", "TRUE", "PASS"):
            status_str = "YES"
        elif raw_status in ("NOT_APPLICABLE", "NO", "FALSE", "FAIL"):
            status_str = "NO"
        elif raw_status in ("INSUFFICIENT", "INSUFFICIENT_EVIDENCE"):
            status_str = "INSUFFICIENT_EVIDENCE"
        elif raw_status in ("INDETERMINATE", "UNKNOWN"):
            status_str = "INDETERMINATE"
        elif raw_status in ("OK", "SUCCESS", "VALID"):
            status_str = "OK"
        else:
            status_str = raw_status or "OK"
        try:
            status = m["P1BLLM01Status"](status_str)
        except ValueError:
            status = m["P1BLLM01Status"].INDETERMINATE

        conf_raw = str(obj.get("confidence", "")).upper()
        conf_str = conf_raw if conf_raw in ("HIGH", "MEDIUM", "LOW") else "MEDIUM"
        try:
            confidence = m["P1BLLM01Confidence"](conf_str)
        except ValueError:
            confidence = m["P1BLLM01Confidence"].MEDIUM

        sections: dict[str, str] = {}
        for key, value in obj.items():
            if key.lower() in self._ENVELOPE_KEYS:
                continue
            body = value if isinstance(value, str) else _json.dumps(value, indent=2)
            sections[key] = body
            sections[key.lower()] = body

        from aegis_phase1.v2.state import GenericMarkdownOutput

        return GenericMarkdownOutput(
            status=status,
            confidence=confidence,
            sections=sections,
        )

    def parse(self, raw: str) -> tuple[Any | None, str]:
        text = self._strip_code_fences(raw)
        m = _import_p1b_models()

        # Find all ## section headers and split the body between them
        matches = list(self._H2_SPLIT_RE.finditer(text))
        if not matches:
            # CORR-116 S2.1: strong models (nemotron, qwen3.x) sometimes emit
            # the output contract as pure JSON instead of `##` markdown. The
            # P1B-01 parser already tolerates this via a direct-JSON fallback;
            # mirror it here so a valid JSON envelope is not rejected with
            # "no section headers found in markdown".
            fallback = self._parse_json_envelope(raw, m)
            if fallback is not None:
                return fallback, ""
            return None, "no section headers found in markdown"

        sections: dict[str, str] = {}
        for i, m_h in enumerate(matches):
            raw_sec_name = m_h.group(1).strip()
            norm_name = re.sub(r"^\d+[.:\s]+", "", raw_sec_name).strip().rstrip(":")
            body_start = m_h.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[body_start:body_end].strip()
            sections[raw_sec_name] = body
            sections[norm_name] = body
            sections[norm_name.lower()] = body

        # Extract Status fields
        status_body = ""
        for k, v in sections.items():
            if k.lower().startswith("status"):
                status_body = v
                break
        if not status_body:
            status_body = sections.get("Status", "")
        raw_status = (
            self._extract_field(status_body, "status")
            or self._extract_field(status_body, "applicable")
            or ""
        ).upper()
        if raw_status in ("APPLICABLE", "YES", "TRUE", "PASS"):
            status_str = "YES"
        elif raw_status in ("NOT_APPLICABLE", "NO", "FALSE", "FAIL"):
            status_str = "NO"
        elif raw_status in ("INSUFFICIENT", "INSUFFICIENT_EVIDENCE"):
            status_str = "INSUFFICIENT_EVIDENCE"
        elif raw_status in ("INDETERMINATE", "UNKNOWN"):
            status_str = "INDETERMINATE"
        elif raw_status in ("OK", "SUCCESS", "VALID"):
            status_str = "OK"
        else:
            status_str = raw_status or "OK"

        try:
            status = m["P1BLLM01Status"](status_str)
        except ValueError:
            status = m["P1BLLM01Status"].INDETERMINATE

        conf_raw = (self._extract_field(status_body, "confidence") or "").upper()
        if conf_raw in ("HIGH", "MEDIUM", "LOW"):
            conf_str = conf_raw
        else:
            conf_str = "MEDIUM"

        try:
            confidence = m["P1BLLM01Confidence"](conf_str)
        except ValueError:
            confidence = m["P1BLLM01Confidence"].MEDIUM

        from aegis_phase1.v2.state import GenericMarkdownOutput

        return GenericMarkdownOutput(
            status=status,
            confidence=confidence,
            sections=sections,
        ), ""


# Registry of parsers per spec_id (extensible for CORR-051/CORR-066)
class P1CLLM01Parser(GenericMarkdownParser):
    """CORR-108: dual-shape parser for P1C-LLM-01-OVERLAP-CLASSIFICATION.

    Reads BOTH output shapes observed in production runs and merges them
    by sub_domain_id into ``sub_domain_activations`` — the exact key the
    executor (``run_phase_1c_map`` → ``parsed.get("sub_domain_activations")``)
    and the normalizer (``domain_activation_context._parse_sub_domain_activations``)
    consume. Before this parser, Shape B was silently dropped
    (0 activations → empty REDUCE input → pipeline died after MAP).

    **Shape A (canonical, M3):**
        ## Sub-domain Activations
        ### D-01.1
        - sub_domain_id: D-01.1
        - reg_pair: [GDPR, CRA]
        - company_scope_verdict: APPLICABLE
        - layer0_refs: [...]

    **Shape B (qwen3.5/3.8, granite, nemotron, muse):**
        ## Pair classifications
        - D-01.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. <predicate text>
        ## Findings
        - D-01.1 (Data at Rest Encryption): applicable=YES. scope_overlap=Y.
          applicable_regulations=[GDPR, CRA]. (...) layer0_refs: <paths>

    Verdict mapping (the downstream normalizer converts YES→APPLICABLE):
        OVERLAP_CONFIRMED / ACTIVE / YES → "YES"
        NOT_IN_SCOPE / NO_OVERLAP / NO   → "NO"
        INDETERMINATE / anything else    → "INDETERMINATE"

    Records without an ``applicable``/verdict signal (e.g. pure pair
    lines with NOT_IN_SCOPE) are still emitted — the normalizer
    downgrades them to NOT_APPLICABLE/INDETERMINATE and the lane filter
    (``sd_id.startswith(domain_id + ".")``) drops foreign lanes.
    """

    # Shape B: `- D-01.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. text...`
    # Also tolerates `- D-01.1 : GDPR ↔ CRA - OVERLAP_CONFIRMED.` and
    # `- D-01.1: GDPR vs CRA — OVERLAP_CONFIRMED.` variants.
    _PAIR_BULLET_RE = re.compile(
        r"^-\s*(D-\d+\.\d+)\s*[:\-]\s*"
        r"([A-Za-z0-9_. ]+?)\s*(?:↔|<->|vs\.?)\s*"
        r"([A-Za-z0-9_. ]+?)\s*[—–~:-]+\s*"  # noqa: RUF001 — en dash is intentional
        r"([A-Za-z0-9_]+)\b\.?\s*(.*)$",
        re.MULTILINE,
    )

    # Shape B findings: `- D-01.1 (Name): applicable=YES. ...`
    _FINDINGS_BULLET_RE = re.compile(
        r"^-\s*(D-\d+\.\d+)\s*(?:\([^)]*\))?\s*:\s*(.*)$",
        re.MULTILINE,
    )

    _FINDINGS_VERDICT_FIRST_RE = re.compile(
        r"^-\s*(D-\d+\.\d+)\s*(?:\([^)]*\))?\s*:\s*"
        r"(ACTIVE|INACTIVE|YES|NO|OVERLAP_CONFIRMED|NOT_ACTIVATED|"
        r"INDETERMINATE|APPLICABLE|NOT_APPLICABLE|NOT_IN_SCOPE)\b\.?\s*(.*)$",
        re.MULTILINE,
    )

    _PARTICIPATING_RE = re.compile(
        r"[Pp]articipating regulations[^:]*:\s*([^.\n]*)"
    )

    _LAYER0_REF_RE = re.compile(r"SubDomains/[^\s;)]+")

    # Splits concatenated lane outputs at each `## Status` header;
    # the captured text (including the header) is kept via the lookahead.
    _STATUS_SPLIT_RE = re.compile(r"(?=^##\s+Status\s*$)", re.MULTILINE)

    _VERDICT_MAP: ClassVar[dict[str, str]] = {
        "OVERLAP_CONFIRMED": "YES",
        "ACTIVE": "YES",
        "YES": "YES",
        "APPLICABLE": "YES",
        "NOT_IN_SCOPE": "NO",
        "NOT_APPLICABLE": "NO",
        "OVERLAP_NOT_TRIGGERED": "NO",
        "NO_OVERLAP": "NO",
        "NOT_ACTIVATED": "NO",
        "NO": "NO",
    }

    # ── Shape A helpers ──────────────────────────────────────────────

    _SUBSECTION_SPLIT_RE = re.compile(r"^###\s+(D-\d+\.\d+)", re.MULTILINE)

    def _parse_shape_a(self, text: str) -> list[dict[str, Any]]:
        """Canonical `## Sub-domain Activations` + `### D-XX.Y` blocks."""
        activations: list[dict[str, Any]] = []
        # Locate the `## Sub-domain Activations` section by splitting the
        # block on `##` headers (SECTION_PATTERNS is empty on the generic
        # base class, so _extract_section can't be reused here).
        sec = ""
        matches = list(self._H2_SPLIT_RE.finditer(text))
        for i, m_h in enumerate(matches):
            if m_h.group(1).strip() != "Sub-domain Activations":
                continue
            start = m_h.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sec = text[start:end].strip()
            break
        if not sec:
            return activations
        matches = list(self._SUBSECTION_SPLIT_RE.finditer(sec))
        for i, m in enumerate(matches):
            sd_id = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(sec)
            body = sec[start:end]
            rec: dict[str, Any] = {"sub_domain_id": sd_id}
            for field in (
                "sub_domain_id", "reg_pair", "company_scope_verdict",
                "regulatory_baseline_relationship", "applicable",
            ):
                val = self._extract_field(body, field)
                if val is None:
                    continue
                val = val.strip()
                if field == "reg_pair" and val.startswith("[") and val.endswith("]"):
                    rec[field] = [
                        r.strip() for r in val.strip("[]").split(",") if r.strip()
                    ]
                else:
                    rec[field] = val
            refs_val = self._extract_field(body, "layer0_refs")
            if refs_val:
                # Canonical shape writes the full ref (path + §section);
                # may be a [a, b] list or a single entry.
                refs_val = refs_val.strip()
                if refs_val.startswith("[") and refs_val.endswith("]"):
                    refs = [
                        r.strip() for r in refs_val.strip("[]").split(",") if r.strip()
                    ]
                else:
                    refs = [refs_val]
                rec["layer0_refs"] = refs
            else:
                refs = self._LAYER0_REF_RE.findall(body)
                if refs:
                    rec["layer0_refs"] = refs
            activations.append(rec)
        return activations

    # ── Shape B helpers ──────────────────────────────────────────────

    def _parse_shape_b(self, sections: dict[str, str]) -> list[dict[str, Any]]:
        """`## Pair classifications` + `## Findings` bullets → merged records."""
        by_id: dict[str, dict[str, Any]] = {}

        # 1. Pair classifications → sub_domain_id + reg_pair + verdict text
        pair_body = sections.get("Pair classifications", "")
        for m in self._PAIR_BULLET_RE.finditer(pair_body):
            sd_id, reg_a, reg_b, verdict_raw, tail = (
                g.strip() for g in m.groups()
            )
            verdict_key = verdict_raw.upper().strip()
            if verdict_key != "INDETERMINATE" and verdict_key not in self._VERDICT_MAP:
                # D-03 style: "— SAME — ... Verdict: OVERLAP_CONFIRMED."
                # The token right after the separator is the baseline
                # relationship; the real verdict is stated explicitly.
                v2 = re.search(r"Verdict:\s*([A-Za-z0-9_]+)", m.group(0))
                if v2 and v2.group(1).upper() in self._VERDICT_MAP:
                    verdict_key = v2.group(1).upper()
                else:
                    continue  # not a real pair-verdict bullet
            rec = by_id.setdefault(sd_id, {"sub_domain_id": sd_id})
            # Keep the first pair verdict per sub-domain (the second one
            # is typically a duplicate/N-A restatement).
            if "company_scope_verdict" in rec:
                continue
            rec["company_scope_verdict"] = self._VERDICT_MAP.get(
                verdict_key, "INDETERMINATE"
            )
            rec["reg_pair"] = [reg_a, reg_b]
            rel = tail.strip()
            if rel:
                rec["regulatory_baseline_relationship"] = rel[:500]
            refs = self._LAYER0_REF_RE.findall(m.group(0))
            if refs:
                rec.setdefault("layer0_refs", refs)

        # 2. Findings → applicable (+ override), applicable_regulations,
        #    layer0_refs, scope_overlap. Two sub-shapes:
        #    a) `- D-XX.Y (Name): applicable=YES. ...`  (D-01 lane style)
        #    b) `- D-XX.Y (Name): ACTIVE. Participating regulations
        #       in scope: GDPR, CRA. ...`  (D-02+ lane style)
        findings_body = sections.get("Findings", "")
        for m in self._FINDINGS_BULLET_RE.finditer(findings_body):
            sd_id, tail = m.group(1).strip(), m.group(2)
            applicable = re.search(r"applicable[=:]\s*(\w+)", tail, re.IGNORECASE)
            if not applicable:
                # Verdict-first variant: `- D-XX.Y (Name): ACTIVE. ...`
                vf = self._FINDINGS_VERDICT_FIRST_RE.search(m.group(0))
                if not vf:
                    # Skip summary/meta bullets ("Cross-sub-domain
                    # pattern:", "Total sub-domains...") — no verdict.
                    continue
                sd_id = vf.group(1).strip()
                tail = vf.group(3) or ""
                verdict_key = vf.group(2).upper()
                rec = by_id.setdefault(sd_id, {"sub_domain_id": sd_id})
                mapped = self._VERDICT_MAP.get(verdict_key)
                if mapped:
                    rec["company_scope_verdict"] = mapped
                elif "company_scope_verdict" not in rec:
                    rec["company_scope_verdict"] = "INDETERMINATE"
                parts = self._PARTICIPATING_RE.search(tail)
                if parts:
                    regs = [
                        r.strip().removesuffix(" only").strip()
                        for r in parts.group(1).split(",")
                        if r.strip()
                    ]
                    if regs:
                        rec.setdefault("reg_pair", regs)
                refs = self._LAYER0_REF_RE.findall(tail)
                if refs:
                    rec["layer0_refs"] = list(dict.fromkeys(
                        list(rec.get("layer0_refs") or []) + refs
                    ))
                continue
            rec = by_id.setdefault(sd_id, {"sub_domain_id": sd_id})
            app_val = applicable.group(1).upper()
            if app_val == "YES":
                rec["company_scope_verdict"] = "YES"
            elif app_val == "NO":
                rec["company_scope_verdict"] = "NO"
            elif "company_scope_verdict" not in rec:
                rec["company_scope_verdict"] = "INDETERMINATE"
            regs = re.search(r"applicable_regulations[=:]\s*\[([^\]]*)\]", tail)
            if regs:
                rec["reg_pair"] = [
                    r.strip() for r in regs.group(1).split(",") if r.strip()
                ]
            refs = self._LAYER0_REF_RE.findall(tail)
            if refs:
                rec["layer0_refs"] = refs
            if "layer0_refs" in rec and rec.get("layer0_refs"):
                # Findings refs are more complete; prefer them.
                rec["layer0_refs"] = list(dict.fromkeys(
                    list(rec.get("layer0_refs") or []) + refs
                ))
        return list(by_id.values())

    # ── Main parse ───────────────────────────────────────────────────

    def _split_blocks(self, text: str) -> list[str]:
        """Split concatenated lane outputs on each `## Status` header.

        Production input is a single lane (one `## Status`), but the
        concatenated Doc 05 (10 lanes) and retry-responses also appear
        in tests/audit flows. Splitting on `## Status` makes both work.
        """
        parts = self._STATUS_SPLIT_RE.split(text)
        return [p for p in (part.strip() for part in parts) if p]

    def parse(self, raw: str) -> tuple[Any | None, str]:
        text = self._strip_code_fences(raw)

        blocks = self._split_blocks(text)
        if not blocks:
            return None, "no `## Section` headers found in markdown"

        m = _import_p1b_models()
        from aegis_phase1.v2.state import P1CLLM01Output

        all_activations: dict[str, dict[str, Any]] = {}
        all_sections: dict[str, str] = {}
        status = m["P1BLLM01Status"].INDETERMINATE
        confidence = m["P1BLLM01Confidence"].MEDIUM
        saw_any = False

        for block in blocks:
            matches = list(self._H2_SPLIT_RE.finditer(block))
            if not matches:
                continue
            sections: dict[str, str] = {}
            for i, m_h in enumerate(matches):
                sections[m_h.group(1).strip()] = block[m_h.end():(
                    matches[i + 1].start() if i + 1 < len(matches) else len(block)
                )].strip()
            saw_any = True

            status_body = sections.get("Status", "")
            status_str = (
                self._extract_field(status_body, "status")
                or self._extract_field(status_body, "applicable")
                or ""
            ).upper()
            conf_str = (self._extract_field(status_body, "confidence") or "").upper()

            if status_str:
                try:
                    status = m["P1BLLM01Status"](status_str)
                except ValueError:
                    status = m["P1BLLM01Status"].INDETERMINATE
            if conf_str:
                try:
                    confidence = m["P1BLLM01Confidence"](conf_str)
                except ValueError:
                    confidence = m["P1BLLM01Confidence"].MEDIUM

            # Activations: Shape A first; if empty, Shape B.
            activations = self._parse_shape_a(block)
            if not activations:
                activations = self._parse_shape_b(sections)
            for rec in activations:
                # First lane that claims a sub_domain_id wins (lanes are
                # disjoint in practice — D-01.x only appears in lane D-01).
                all_activations.setdefault(rec["sub_domain_id"], rec)
            all_sections.update(sections)

        if not saw_any:
            return None, "no `## Section` headers found in markdown"

        return P1CLLM01Output(
            status=status,
            confidence=confidence,
            sub_domain_activations=list(all_activations.values()),
            sections=all_sections,
        ), ""


MARKDOWN_PARSERS: dict[str, type[MarkdownParser]] = {
    "P1B-LLM-01-INTERPRETATION": P1BLLM01Parser,
    # CORR-066: the 4 LLMs below don't yet have spec-specific parsers
    # (writing them is a separate contract — P1B-02 has its own
    # section/subsection structure, P1C-01 emits per-domain bullets,
    # etc). For now, the GenericMarkdownParser captures `## Status`
    # and stores every other `## Section` body verbatim in
    # `sections[section_name]` so the v2 orchestrator and doc
    # renderers can consume the raw markdown.
    "P1B-LLM-02-RATIONALE": GenericMarkdownParser,
    "P1C-LLM-01-OVERLAP-CLASSIFICATION": P1CLLM01Parser,  # CORR-108
    "P1C-LLM-02-COMPOUND-EVENT": GenericMarkdownParser,
    "P1C-LLM-03-STRATEGIC-SYNTHESIS": GenericMarkdownParser,
}
