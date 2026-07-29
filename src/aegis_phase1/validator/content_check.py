"""Content-only validator for CORR-061.

The previous Phase1Validator (now archived) enforced a strict JSON Schema
on the LLM output, requiring envelope fields (prompt_spec_id, schema_version,
case_id, invocation_pattern, status, confidence) and minimum lengths. The
gemma4:e2b model cannot reliably produce that shape, so the strict checks
were almost always failing.

The new contract is markdown-only output. There is no schema to enforce.
This validator only checks that the model produced *something*: at least
50 characters of non-whitespace text. Anything below that is treated as
INSUFFICIENT_EVIDENCE (the model emitted no usable content).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Minimum content length (chars) to consider the LLM call "produced something".
# Below this, the call is treated as INSUFFICIENT_EVIDENCE.
MIN_CONTENT_CHARS = 50


@dataclass
class ValidationResult:
    """Result of a content-check validation. Mirrors the Phase1Validator interface."""
    status: str  # "OK" | "INSUFFICIENT_EVIDENCE" | ...
    parsed_output: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]


class ContentValidator:
    """Validates LLM output by content length only.

    Replaces Phase1Validator. Does NOT require structured fields, does NOT
    enforce JSON Schema, does NOT require an envelope. Just checks that
    the model produced non-trivial text.
    """

    def __init__(self, min_chars: int = MIN_CONTENT_CHARS) -> None:
        self.min_chars = min_chars

    def validate(
        self,
        raw_response: str,
        *,
        spec_id: str | None = None,
        case_id: str | None = None,
    ) -> ValidationResult:
        """Validate by content length.

        Args:
            raw_response: The LLM's raw text output (markdown or otherwise).
            spec_id: Optional spec identifier (e.g. "P1B-LLM-01-INTERPRETATION").
                Currently unused; reserved for future spec-specific thresholds.
            case_id: Optional case identifier. Currently unused.

        Returns:
            ValidationResult with:
              - status="OK" if len(raw_response.strip()) >= self.min_chars
              - status="INSUFFICIENT_EVIDENCE" otherwise
              - parsed_output={"raw_response": raw_response} on OK
              - parsed_output=None on INSUFFICIENT_EVIDENCE
              - errors=[] on OK, [description] on INSUFFICIENT_EVIDENCE
              - warnings=[]
        """
        if not raw_response or not raw_response.strip():
            return ValidationResult(
                status="INSUFFICIENT_EVIDENCE",
                parsed_output=None,
                errors=[f"empty or whitespace-only response (min {self.min_chars} chars required)"],
                warnings=[],
            )
        stripped = raw_response.strip()
        if len(stripped) < self.min_chars:
            return ValidationResult(
                status="INSUFFICIENT_EVIDENCE",
                parsed_output=None,
                errors=[f"response too short: {len(stripped)} chars < min {self.min_chars}"],
                warnings=[],
            )
        return ValidationResult(
            status="OK",
            parsed_output={"raw_response": raw_response},
            errors=[],
            warnings=[],
        )
