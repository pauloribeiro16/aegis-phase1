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
    SECTION_PATTERNS: ClassVar[dict[str, re.Pattern]] = {}

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
    ) -> list[tuple[str, str, str]]:
        """Split a section body into ``(sub_id, heading_line, sub_body)`` triples.

        Used to split ``## Interpretations`` into individual ``### INT-NN``
        or ``### ENTRY_ID — VERDICT`` blocks.

        Returns triples so callers can inspect the full heading line —
        CORR-074 puts the verdict in the heading itself
        (``### TIPO2-CRA-ART14-DUAL-FLOW — APPLIES``).
        """
        results: list[tuple[str, str, str]] = []
        matches = list(header_pattern.finditer(section_body))
        for i, m in enumerate(matches):
            heading_line = m.group(0)
            # Extract the entry id from the heading text. Patterns match
            # EITHER `### INT-NN` / `### DER-NN` OR `### IMP-...` /
            # `### GAP-...` (P1B-02 propagation, CORR-074) OR generic
            # `### ENTRY_ID[— verdict]`.
            id_match = re.match(
                r"^#{3,4}\s+(?:(INT-\d+)|(DER-\d+)|(IMP-[A-Z0-9.\-]+)"
                r"|(GAP-[A-Z0-9.\-]+)"
                r"|([A-Z][A-Z0-9_.\-]+))\b",
                heading_line,
            )
            if id_match is None:
                sub_id = ""
            else:
                sub_id = next((g for g in id_match.groups() if g is not None), "")
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(section_body)
            results.append((sub_id, heading_line, section_body[start:end].strip()))
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

    @staticmethod
    def _parse_status_prose(body: str) -> tuple[str, str, str]:
        """Parse `## Status` body — supports BOTH bullet and prose forms.

        **Prose form** (CORR-074): ``OK — HIGH confidence. <justification>``.
        Accepts status tokens `OK`, `INSUFFICIENT_EVIDENCE`, `INDETERMINATE`
        (and legacy `YES` / `NO`), optional `—`/`-`/`:` separator, optional
        `(HIGH|MEDIUM|LOW) confidence`, and any trailing prose is treated as
        justification.

        **Bullet form** (CORR-050 legacy): ``- status: OK`` /
        ``- confidence: HIGH``. Both shapes are still accepted so existing
        callers (notably `tests/unit/prompts_v2/test_markdown_parser_corr050.py`)
        keep working.

        Returns ``(status, confidence, justification)``. ``justification``
        is empty when the body matches the bullet form (legacy contracts
        didn't capture one). When the body matches the prose form, the
        residual text after the confidence token is returned as the
        justification. When no token matches at all, the entire body is
        returned as justification so the caller still has a fallback.

        CORR-074 propagation (P1B-LLM-02 / P1C-LLM-02): extracted from
        ``P1BLLM01Parser`` to the base class so the markdown-using specs
        (P1B-01, P1B-02, P1C-02) can share it. ``P1BLLM01Parser`` keeps
        its own staticmethod (same body) for backward compatibility with
        any external callers.
        """
        s = (body or "").strip()
        if not s:
            return "", "", ""

        # ── Bullet form (CORR-050) ────────────────────────────────────
        # First try the bullet style — single status + confidence lines.
        status_bullet = re.search(
            r"^-\s*status\s*:\s*(\S+)",
            s,
            re.MULTILINE | re.IGNORECASE,
        )
        if status_bullet is None:
            status_bullet = re.search(
                r"^-\s*applicable\s*:\s*(\S+)",
                s,
                re.MULTILINE | re.IGNORECASE,
            )
        confidence_bullet = re.search(
            r"^-\s*confidence\s*:\s*(\S+)",
            s,
            re.MULTILINE | re.IGNORECASE,
        )
        if status_bullet is not None:
            status = status_bullet.group(1).upper()
            confidence = (
                confidence_bullet.group(1).upper()
                if confidence_bullet is not None
                else "MEDIUM"
            )
            return status, confidence, ""

        # ── Prose form (CORR-074) ─────────────────────────────────────
        # Strip leading bullets / markdown emphasis so a single-line body
        # is matched directly. `**OK**` and `**OK** — HIGH confidence`
        # both need the bold markers removed before the regex anchor.
        s = re.sub(r"^[-*]\s*", "", s)
        s = re.sub(r"\*+", "", s)
        m = re.match(
            r"^(OK|INSUFFICIENT_EVIDENCE|INDETERMINATE|YES|NO)\s*"
            r"(?:[—\-:]\s*|\s+)?"
            r"(?:(HIGH|MEDIUM|LOW)\s+confidence\.?)?\s*"
            r"(.*)$",
            s,
            re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return "", "", s
        status = m.group(1).upper()
        confidence = (m.group(2) or "").upper() or "MEDIUM"
        justification = (m.group(3) or "").strip()
        return status, confidence, justification

    # -----------------------------------------------------------------
    # Shared field / list helpers (CORR-074 propagation).
    #
    # `_extract_field_bt` and `_extract_bracketed_list_field` were
    # originally defined inside ``P1BLLM02Parser`` and re-defined in
    # ``P1CLLM01Parser``. CORR-074 propagation extracts them to the
    # base class so P1C-LLM-03 (and future specs) can share them
    # without duplicating the regex logic. Existing subclasses keep
    # their own overrides via MRO — they continue to behave
    # identically (the override wins over the base method when
    # called on instances of that subclass).
    # -----------------------------------------------------------------

    @classmethod
    def _extract_field_bt(cls, text: str, field_name: str) -> str | None:
        """Extract ``field_name: value`` with tolerant name decoration.

        Strips ``*`` and backtick decorations from each line, then
        matches ``field_name: value`` case-insensitively. Handles all
        shapes M3 and gemma4 emit:

          - ``- id: value``
          - ``- `id`: value``
          - ``- **id**: value``
          - ``**id:** value``  (gemma4)
          - ``id: value``      (no bullet)
        """
        plain = cls._extract_field(text, field_name)
        if plain is not None:
            return plain
        fn = re.escape(field_name)
        for line in text.splitlines():
            stripped = line.strip()
            stripped = re.sub(r"^[-*]\s+", "", stripped)
            cleaned = re.sub(r"[\*`]", "", stripped)
            m = re.match(rf"^{fn}\s*:\s*(.+)$", cleaned, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    @classmethod
    def _extract_bracketed_list_field(
        cls, text: str, field_name: str
    ) -> list[str]:
        """Extract ``- field_name: [a, b, c]`` (JSON-style bracketed list).

        Empirical M3 alternates between the canonical
        comma-separated shape (``D-01.1, D-04.3``) and the JSON-array
        literal shape (``[D-01.1, D-04.3]``). This helper tries the
        comma-separated form first, then the bracketed form (stripping
        the ``[ ]``), and tolerates backticked / bold field names via
        ``_extract_field_bt``. Falls back to ``_extract_list_field``
        for the multi-bullet ``- field_name:\\n  - a\\n  - b`` shape.
        """
        plain = cls._extract_field_bt(text, field_name)
        if plain is None:
            return cls._extract_list_field(text, field_name)
        s = plain.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        return [v.strip().strip('"').strip("'") for v in s.split(",") if v.strip()]

    @classmethod
    def _extract_field_with_aliases(
        cls, text: str, field_name: str, aliases: tuple[str, ...] = ()
    ) -> str | None:
        """Extract a field by canonical name OR any of the given aliases.

        Tries the canonical name first via ``_extract_field_bt``; if
        that fails, tries each alias in order. Used by ``P1CLLM03Parser``
        to tolerate ``Risk Level:`` and ``Confidence:`` style prefixes
        alongside the canonical ``risk_level:`` / ``confidence:`` body
        fields — empirical M3 emits both shapes across runs.
        """
        for name in (field_name, *aliases):
            value = cls._extract_field_bt(text, name)
            if value is not None:
                return value
        return None


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


def _import_p1b02_models():
    """Lazy import to avoid circular imports at module load.

    CORR-074 propagation: imports the P1B-LLM-02-RATIONALE Pydantic
    models from ``state``. Used by ``P1BLLM02Parser`` to build the
    structured ``P1BLLM02Output`` after markdown extraction.
    """
    from aegis_phase1.v2.state import (
        P1BLLM01Confidence,
        P1BLLM01Status,
        P1BLLM02CoverageLevel,
        P1BLLM02EffortEstimate,
        P1BLLM02Gap,
        P1BLLM02Implication,
        P1BLLM02Output,
        P1BLLM02Priority,
    )
    return {
        "P1BLLM02Output": P1BLLM02Output,
        "P1BLLM02Implication": P1BLLM02Implication,
        "P1BLLM02Gap": P1BLLM02Gap,
        "P1BLLM02EffortEstimate": P1BLLM02EffortEstimate,
        "P1BLLM02CoverageLevel": P1BLLM02CoverageLevel,
        "P1BLLM02Priority": P1BLLM02Priority,
        "P1BLLM01Status": P1BLLM01Status,
        "P1BLLM01Confidence": P1BLLM01Confidence,
    }


class P1CLLM02Parser(MarkdownParser):
    """Parser for P1C-LLM-02-COMPOUND-EVENT markdown output.

    CORR-074 propagation: contract switched from JSON Schema
    (``output_schemas.yaml#P1C-LLM-02``) to markdown+regex, mirroring the
    CORR-050 / CORR-074 P1B-LLM-01 pattern. The parser tolerates:

      - Optional qualifiers on `## Positive Events` / `## Negative Events`
        headings (e.g. `## Positive Events (Phase 1C)` — empirical M3
        variability, same shape as the P1B-01 `(Tipo 2)` qualifier).
      - Tension-type variants: `TEMPORAL_CONFLICT` /
        `temporal conflict` / `temporal_conflict` all normalise to
        ``TEMPORAL_CONFLICT``; same for ``REQUIREMENT_CONFLICT``,
        ``FREQUENCY_MISMATCH``, ``TRIGGER_MISMATCH``, ``INTENSITY_GAP``.
      - Severity variants: ``LOW`` / ``MEDIUM`` / ``HIGH`` / ``CRITICAL``
        (case-insensitive; canonical uppercase).
      - Optional `## Notes` section — if missing, `notes=""`.
      - Empty `## Positive Events` / `## Negative Events` (header only) —
        parser returns empty list with success (zero confirmed events
        is a valid output per the spec).

    Per the spec (CORR-074 propagation), resolution design is
    DELIBERATELY EXCLUDED — `resolution_approach` lives in Phase 2B.
    The Pydantic model (`P1CLLM02Output`) has no `resolution_approach`
    field, so any LLM-emitted value is silently dropped by the
    `extra="ignore"` config.
    """

    SECTION_PATTERNS: ClassVar[dict[str, re.Pattern]] = {
        "status": re.compile(r"^##\s+Status\b.*$", re.MULTILINE),
        "positive_events": re.compile(
            r"^##\s+Positive\s+Events\b.*$", re.MULTILINE
        ),
        "negative_events": re.compile(
            r"^##\s+Negative\s+Events\b.*$", re.MULTILINE
        ),
        "notes": re.compile(r"^##\s+Notes\b.*$", re.MULTILINE),
    }
    # Subsection header regex (no inline verdict — CORR-074 propagation
    # shape, distinct from P1B-01's `### ENTRY_ID — VERDICT`).
    _SUBSEC_EVT: ClassVar[re.Pattern[str]] = re.compile(
        r"^#{3,4}\s+(EVT-\d+)\s*$",
        re.MULTILINE,
    )
    _SUBSEC_NEG: ClassVar[re.Pattern[str]] = re.compile(
        r"^#{3,4}\s+(NEG-\d+)\s*$",
        re.MULTILINE,
    )
    # CORR-074 propagation: tension type canonical taxonomy maps every
    # variant the LLM might emit (uppercase with underscore, lowercase,
    # spaced, titlecase, etc.) onto the strict enum token. Mirrors the
    # P1B-01 `_VERDICT_NORMALISE_INTERP` / `_VERDICT_NORMALISE_DEROG`
    # helpers.
    _VERDICT_NORMALISE_TENSION: ClassVar[dict[str, str]] = {
        "temporal_conflict": "TEMPORAL_CONFLICT",
        "temporal conflict": "TEMPORAL_CONFLICT",
        "temporal-conflict": "TEMPORAL_CONFLICT",
        "requirement_conflict": "REQUIREMENT_CONFLICT",
        "requirement conflict": "REQUIREMENT_CONFLICT",
        "requirement-conflict": "REQUIREMENT_CONFLICT",
        "frequency_mismatch": "FREQUENCY_MISMATCH",
        "frequency mismatch": "FREQUENCY_MISMATCH",
        "frequency-mismatch": "FREQUENCY_MISMATCH",
        "trigger_mismatch": "TRIGGER_MISMATCH",
        "trigger mismatch": "TRIGGER_MISMATCH",
        "trigger-mismatch": "TRIGGER_MISMATCH",
        "intensity_gap": "INTENSITY_GAP",
        "intensity gap": "INTENSITY_GAP",
        "intensity-gap": "INTENSITY_GAP",
    }
    _VERDICT_NORMALISE_SEVERITY: ClassVar[dict[str, str]] = {
        "low": "LOW",
        "medium": "MEDIUM",
        "med": "MEDIUM",
        "high": "HIGH",
        "critical": "CRITICAL",
        "crit": "CRITICAL",
    }

    @classmethod
    def _normalise_tension(cls, raw: str) -> str:
        """Map LLM-emitted tension-type variants to the strict enum token.

        Unknown tokens are upper-cased and returned as-is so Pydantic
        validation surfaces the mismatch.
        """
        s = (raw or "").strip().lower()
        if not s:
            return ""
        return cls._VERDICT_NORMALISE_TENSION.get(s, s.upper())

    @classmethod
    def _normalise_severity(cls, raw: str) -> str:
        """Map LLM-emitted severity variants to the strict enum token."""
        s = (raw or "").strip().lower()
        if not s:
            return ""
        return cls._VERDICT_NORMALISE_SEVERITY.get(s, s.upper())

    @classmethod
    def _extract_bracketed_list_field(
        cls, text: str, field_name: str
    ) -> list[str]:
        """Extract `- field_name: [a, b, c]` (single-line bracketed list).

        The P1C-02 spec mandates the bracketed form for list fields
        (``- sub_domains: [D-XX.Y, ...]``, ``- regulations_triggered:
        [REG, ...]``). The shared ``_extract_list_field`` doesn't
        strip the surrounding ``[ ]``, so a value like ``[D-01.1, D-04.3]``
        would yield ``['[D-01.1', 'D-04.3]'``.

        Empirical M3 wraps field names in backticks (CORR-074
        propagation hardening, mirroring P1C-03): ``- `sub_domains`:
        [D-01.1, D-04.3]``. Try plain field name first; fall back to
        the backtick/bold-tolerant ``_extract_field_bt`` on miss.

        Falls back to ``_extract_list_field`` for the multi-bullet form
        (``- field_name:\\n  - a\\n  - b``) — defensive, in case the LLM
        emits either shape.
        """
        raw = cls._extract_field(text, field_name)
        if raw is None:
            raw = cls._extract_field_bt(text, field_name)
        if raw is None:
            return cls._extract_list_field(text, field_name)
        s = raw.strip()
        # Strip outer brackets — spec mandates `[a, b, c]` shape.
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        return [v.strip() for v in s.split(",") if v.strip()]

    @classmethod
    def _extract_field_ci(cls, text: str, field_name: str) -> str | None:
        """Case-insensitive, backtick/bold-tolerant variant of ``_extract_field``.

        The P1C-02 spec lowercases field names (``severity``, ``tension_type``)
        but empirical M3 sometimes emits them titlecased (``Severity``,
        ``Tension_Type``) AND wraps them in backticks (``- `severity`:
        HIGH``). This helper accepts plain / backticked / bold shapes
        with case-insensitive name matching so the parser doesn't fail
        on cosmetic drift.
        """
        # Try a single regex that accepts plain / backticked / bold
        # field names with case-insensitive name match (mirrors the
        # P1C-03 helper shape).
        decorated = re.compile(
            rf"^- \s*"
            rf"(?:\*{{0,2}}|`+){re.escape(field_name)}(?:\*{{0,2}}|`+)"
            rf"\s*:\s*(.+?)(?=\n- |\Z)",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        m = decorated.search(text)
        if m is not None:
            return m.group(1).strip()
        # Fall back to the plain case-insensitive regex (defensive).
        pat = re.compile(
            rf"^- \s*{re.escape(field_name)}\s*:\s*(.+?)(?=\n- |\Z)",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        m = pat.search(text)
        return m.group(1).strip() if m else None

    def parse(self, raw: str) -> tuple[Any | None, str]:
        """Parse the LLM output. Returns (model_instance, error_feedback).

        CORR-074 propagation: the spec asks for markdown (see
        `## Output Format (mandatory)` section). The parser:

        1. Strips code fences (defensive — spec explicitly forbids them).
        2. Extracts `## Status` via `_parse_status_prose` (reused from
           P1BLLM01Parser; same `OK — HIGH confidence. <justification>`
           shape).
        3. Splits `## Positive Events` by `### EVT-NN` and extracts
           body fields (`description`, `sub_domains`, `regulations_triggered`,
           `tension_type`, `severity`, `layer0_refs`) via `_extract_field`
           / `_extract_list_field`.
        4. Symmetrically splits `## Negative Events` by `### NEG-NN`
           and extracts `scenario`, `regulations_checked`, `why_not_compound`.
        5. Captures `## Notes` body verbatim (optional; missing → "").
        6. Builds `P1CLLM02Output` and returns it.

        Returns `(model, "")` on success, `(None, error_msg)` on failure.
        The invoker injects envelope fields (prompt_spec_id, schema_version,
        case_id, invocation_pattern) after parse() returns successfully.
        """
        m = _import_p1c02_models()
        text = self._strip_code_fences(raw)

        try:
            result = self._parse_markdown(text, m)
            if result is not None:
                return result, ""
            return None, "P1C-LLM-02 markdown extraction did not match template"
        except Exception as e:
            return None, f"P1C-LLM-02 markdown parse exception: {e}"

    def _parse_markdown(self, text: str, m: dict) -> Any | None:
        """Markdown parser for P1C-LLM-02 (CORR-074 propagation)."""
        # ── Status section (required) ─────────────────────────────────
        status_body = self._extract_section(text, "status")
        if status_body is None:
            return None
        # Reuse P1B-01's prose helper — same `OK — HIGH confidence. <just>`
        # shape per the spec's "Output Format (mandatory)" section.
        status_str, conf_str, _justification = P1BLLM01Parser._parse_status_prose(
            status_body
        )
        if not status_str:
            return None
        if status_str not in {e.value for e in m["P1BLLM01Status"]}:
            return None
        if conf_str not in {e.value for e in m["P1BLLM01Confidence"]}:
            conf_str = "MEDIUM"

        # ── Positive Events section ───────────────────────────────────
        positive_events: list = []
        pos_body = self._extract_section(text, "positive_events") or ""
        pos_subs = self._split_subsections(pos_body, self._SUBSEC_EVT)
        for sub_id, _heading_line, sub_body in pos_subs:
            # CORR-074 propagation shape: `event_id` in body (preferred)
            # OR in heading (`### EVT-NN`). Body wins when present.
            # Empirical M3 wraps field names in backticks (CORR-074
            # propagation hardening, mirroring P1C-03):
            # ``- `event_id`: EVT-01`` / ``- `description`: ...``.
            # Use the tolerant helper so plain / backticked / bold
            # shapes all match.
            event_id = (
                self._extract_field_bt(sub_body, "event_id") or sub_id
            )
            description = (
                self._extract_field_bt(sub_body, "description") or sub_body.strip()
            )
            sub_domains = self._extract_bracketed_list_field(
                sub_body, "sub_domains"
            )
            regulations_triggered = self._extract_bracketed_list_field(
                sub_body, "regulations_triggered"
            )
            # Field-name case-insensitive (per empirical M3 — `Severity`,
            # `Tension_Type` are emitted titlecased sometimes).
            tension_raw = self._extract_field_ci(sub_body, "tension_type") or ""
            tension_str = self._normalise_tension(tension_raw)
            if tension_str not in {e.value for e in m["P1CLLM02TensionType"]}:
                # Empirical M3 sometimes emits ``INDETERMINATE`` for
                # ``tension_type`` / ``severity`` when uncertain (e.g.
                # missing ``event_templates.yaml`` content). Per the
                # spec the strict taxonomy does NOT include
                # ``INDETERMINATE`` for these fields, but skipping the
                # event is more graceful than failing the whole parse
                # — better to surface the confirmed events than to drop
                # everything when M3 drifts on one candidate.
                continue
            severity_raw = self._extract_field_ci(sub_body, "severity") or ""
            severity_str = self._normalise_severity(severity_raw)
            if severity_str not in {e.value for e in m["P1CLLM02Severity"]}:
                continue
            layer0_refs = self._extract_bracketed_list_field(
                sub_body, "layer0_refs"
            )
            positive_events.append(m["P1CLLM02PositiveEvent"](
                event_id=event_id,
                description=description,
                sub_domains=sub_domains,
                regulations_triggered=regulations_triggered,
                tension_type=m["P1CLLM02TensionType"](tension_str),
                severity=m["P1CLLM02Severity"](severity_str),
                layer0_refs=layer0_refs,
            ))

        # ── Negative Events section ───────────────────────────────────
        negative_events: list = []
        neg_body = self._extract_section(text, "negative_events") or ""
        neg_subs = self._split_subsections(neg_body, self._SUBSEC_NEG)
        for _sub_id, _heading_line, sub_body in neg_subs:
            scenario = (
                self._extract_field_bt(sub_body, "scenario") or sub_body.strip()
            )
            regulations_checked = self._extract_bracketed_list_field(
                sub_body, "regulations_checked"
            )
            why_not_compound = (
                self._extract_field_bt(sub_body, "why_not_compound") or ""
            )
            negative_events.append(m["P1CLLM02NegativeEvent"](
                scenario=scenario,
                regulations_checked=regulations_checked,
                why_not_compound=why_not_compound,
            ))

        # ── Optional Notes section ────────────────────────────────────
        notes_body = self._extract_section(text, "notes") or ""

        # ── Build envelope-less model; envelope injected by invoker ──
        try:
            confidence = (
                m["P1BLLM01Confidence"](conf_str)
                if conf_str in {e.value for e in m["P1BLLM01Confidence"]}
                else m["P1BLLM01Confidence"].MEDIUM
            )
            return m["P1CLLM02Output"](
                status=m["P1BLLM01Status"](status_str),
                confidence=confidence,
                positive_events=positive_events,
                negative_events=negative_events,
                notes=notes_body,
            )
        except ValidationError:
            return None


# Import here to avoid forward refs (state.py imports many things).
def _import_p1c02_models():
    """Lazy import to avoid circular imports at module load."""
    from aegis_phase1.v2.state import (
        P1BLLM01Confidence,
        P1BLLM01Status,
        P1CLLM02NegativeEvent,
        P1CLLM02Output,
        P1CLLM02PositiveEvent,
        P1CLLM02Severity,
        P1CLLM02TensionType,
    )
    return {
        "P1CLLM02Output": P1CLLM02Output,
        "P1CLLM02PositiveEvent": P1CLLM02PositiveEvent,
        "P1CLLM02NegativeEvent": P1CLLM02NegativeEvent,
        "P1CLLM02TensionType": P1CLLM02TensionType,
        "P1CLLM02Severity": P1CLLM02Severity,
        "P1BLLM01Status": P1BLLM01Status,
        "P1BLLM01Confidence": P1BLLM01Confidence,
    }


class P1BLLM01Parser(MarkdownParser):
    """Parser for P1B-LLM-01-INTERPRETATION markdown output.

    CORR-074 (post-fix 2026-08-05): contract switched from JSON to flexible
    markdown (`## Status / ## Interpretations / ## Derogations / ## Notes`).
    The parser tolerates:
      - Optional `(Tipo 2)` / `(Tipo 3)` qualifiers on `## Interpretations`
        / `## Derogations` headings.
      - Inline annotations after the heading (e.g. `## Interpretations — details`).
      - Verdict variants for interpretations: `YES` / `APPLIES` /
        `APPLIES (YES)` are all normalised to `YES`; `NO` /
        `DOES_NOT_APPLY` / `DOES_NOT_APPLY (NO)` → `NO` (canonical
        taxonomy is `YES / NO / INDETERMINATE`, per user decision).
      - Verdict variants for derogations: `ACTIVATED` / `ACTIVATED (YES)`;
        `NOT_ACTIVATED` / `NOT ACTIVATED` / `NOT ACTIVATED (NO)`;
        `INDETERMINATE`.
      - Optional `## Notes` section — if missing, `notes=""` (empty string).
      - `### ENTRY_ID — VERDICT` subsections (the CORR-074 shape) in
        addition to the older `### INT-NN` / `### DER-NN` and the
        CORR-065 bullet fallback.
    """

    SECTION_PATTERNS: ClassVar[dict[str, re.Pattern]] = {
        "status": re.compile(r"^##\s+Status\b.*$", re.MULTILINE),
        "interpretations": re.compile(r"^##\s+Interpretations\b.*$", re.MULTILINE),
        "derogations": re.compile(r"^##\s+Derogations\b.*$", re.MULTILINE),
        "notes": re.compile(r"^##\s+Notes\b.*$", re.MULTILINE),
    }
    # CORR-074 (post-fix 2026-08-05): subsection header regex captures the
    # entry id AND an optional verdict token in the heading itself.
    # Group 1 = legacy `INT-NN` / `DER-NN` id (if present).
    # Group 2 = new `ENTRY_ID` token (TIPO2-..., TIPO3-...).
    # Group 3 = optional verdict token (`YES` / `APPLIES (YES)` /
    # `NOT ACTIVATED`, etc.) — captured directly so the caller doesn't
    # need a second regex pass over the heading line.
    #
    # The verdict group tolerates:
    #   - optional `**` bold markers around the token,
    #   - multi-word tokens separated by spaces (`NOT ACTIVATED`),
    #   - trailing parenthesised annotations (`(YES)`, `(NO)`).
    _SUBSEC_INT: ClassVar[re.Pattern[str]] = re.compile(
        r"^###\s+"
        r"(?:(INT-\d+)|"                                           # legacy INT-NN
        r"([A-Z][A-Z0-9_.\-]+))"                                    # ENTRY_ID or sub_domain_id (D-XX.Y)
        r"(?:\s*[—\-:]\s*\*{0,2}"
        r"([A-Z_]+(?:\s+[A-Z_]+)*?)"                                # verdict token
        r"(?:\s*\([^)]*\))?"                                        # optional (annotation)
        r"\s*\*{0,2})?"
        r"\s*$",
        re.MULTILINE,
    )
    _SUBSEC_DER: ClassVar[re.Pattern[str]] = re.compile(
        r"^###\s+"
        r"(?:(DER-\d+)|"
        r"([A-Z][A-Z0-9_.\-]+))"
        r"(?:\s*[—\-:]\s*\*{0,2}"
        r"([A-Z_]+(?:\s+[A-Z_]+)*?)"
        r"(?:\s*\([^)]*\))?"
        r"\s*\*{0,2})?"
        r"\s*$",
        re.MULTILINE,
    )

    # CORR-074 (post-fix 2026-08-05): canonical interpretation verdict
    # taxonomy is `YES / NO / INDETERMINATE` (per user decision). The
    # parser normalises legacy `APPLIES` / `DOES_NOT_APPLY` (and the
    # `APPLIES (YES)` / `DOES_NOT_APPLY (NO)` annotated variants) into the
    # canonical tokens so the model value never drifts.
    _VERDICT_NORMALISE_INTERP: ClassVar[dict[str, str]] = {
        "yes": "YES", "applies": "YES", "applicable": "YES",
        "no": "NO", "does_not_apply": "NO",
        "does not apply": "NO", "not applicable": "NO",
        "indeterminate": "INDETERMINATE", "uncertain": "INDETERMINATE",
        "applies (yes)": "YES", "does_not_apply (no)": "NO",
    }
    _VERDICT_NORMALISE_DEROG: ClassVar[dict[str, str]] = {
        "activated": "ACTIVATED", "active": "ACTIVATED", "yes": "ACTIVATED",
        "not_activated": "NOT_ACTIVATED", "not activated": "NOT_ACTIVATED",
        "not activated (no)": "NOT_ACTIVATED",
        "not_activated (no)": "NOT_ACTIVATED",
        "no": "NOT_ACTIVATED", "inactive": "NOT_ACTIVATED",
        "indeterminate": "INDETERMINATE", "uncertain": "INDETERMINATE",
    }

    @classmethod
    def _normalise_verdict(cls, raw: str, kind: str) -> str:
        """Map LLM-emitted verdict variants to the strict enum token.

        ``kind`` is ``"interp"`` for interpretations or ``"derog"`` for
        derogations. Unknown tokens are upper-cased and returned as-is so
        Pydantic validation surfaces the mismatch.
        """
        s = (raw or "").strip().lower()
        if not s:
            return ""
        table = cls._VERDICT_NORMALISE_INTERP if kind == "interp" else cls._VERDICT_NORMALISE_DEROG
        return table.get(s, s.upper())

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

        # Attempt 1: markdown extraction (CORR-050 path; CORR-074 hardened)
        markdown_error = ""
        try:
            result = self._parse_markdown(text, m)
            if result is not None:
                return result, ""
            markdown_error = "markdown extraction did not match template"
        except Exception as e:
            markdown_error = f"markdown parse exception: {e}"

        # CORR-074: the spec asks for markdown. Falling back to JSON is a
        # regression signal (the LLM emitted something we did not expect) —
        # log a warning so we can see if M3 ever drifts away from markdown.
        if markdown_error:
            logger.warning(
                "P1B-LLM-01: M3 output did not match markdown contract (%s); "
                "falling back to JSON RobustParser. Spec asked for markdown.",
                markdown_error,
            )

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
        except Exception:
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
        """Markdown parser (CORR-050 / CORR-074 hardened). Returns model or None.

        Accepts the following subsection shapes (in order of preference):
          - CORR-074 `### ENTRY_ID — VERDICT` (e.g.
            `### TIPO2-CRA-ART14-DUAL-FLOW — APPLIES`)
          - CORR-050 legacy `### INT-NN` / `### DER-NN`
          - CORR-065 bullet-list fallback:
            `- ENTRY_ID (VERDICT): rationale...`

        Verdict variants (`YES`, `APPLIES (YES)`, `NOT ACTIVATED`, ...) are
        normalised to the strict enum token via `_normalise_verdict`.

        The `## Notes` section is optional; if present its body is captured
        into ``model.notes`` (free-form prose). If missing, ``notes=""``.
        """
        # Status section (required)
        status_body = self._extract_section(text, "status")
        if status_body is None:
            return None
        # CORR-074 (post-fix 2026-08-05): the spec emits `## Status` as a
        # single line of prose, e.g.
        # `**OK** — HIGH confidence. <justification>`. Use the dedicated
        # prose helper to extract (status, confidence, justification) in
        # one pass.
        status_str, conf_str, justification = self._parse_status_prose(status_body)
        if not status_str:
            return None
        if status_str not in {e.value for e in m["P1BLLM01Status"]}:
            return None
        if conf_str not in {e.value for e in m["P1BLLM01Confidence"]}:
            conf_str = "MEDIUM"

        # Interpretations section
        interpretations: list = []
        interp_body = self._extract_section(text, "interpretations") or ""
        interp_subs = self._split_subsections(interp_body, self._SUBSEC_INT)
        if interp_subs:
            for sub_id, heading_line, sub_body in interp_subs:
                # CORR-050: legacy shape uses `- entry_id: TIPO-...` in the body.
                # CORR-074: new shape puts the entry_id in the heading
                # (`### TIPO-... — VERDICT`). Prefer the body field when
                # present; otherwise fall back to the heading id.
                entry_id = (
                    self._extract_field(sub_body, "entry_id")
                    or sub_id
                )
                applicable_str_raw = self._extract_field(sub_body, "applicable") or ""
                # CORR-074 (post-fix 2026-08-05): verdict token captured
                # directly by `_SUBSEC_INT` from the heading line — no
                # second regex pass needed. Group 3 is `None` for legacy
                # `### INT-NN` headings (no inline verdict).
                if not applicable_str_raw:
                    heading_m = self._SUBSEC_INT.match(heading_line)
                    applicable_str_raw = (
                        heading_m.group(3) if heading_m and heading_m.group(3) else ""
                    )
                applicable_str = self._normalise_verdict(applicable_str_raw, "interp")
                if applicable_str not in {e.value for e in m["P1BLLM01Applicable"]}:
                    return None
                rationale = self._extract_field(sub_body, "activation_rationale") or sub_body.strip()
                interpretations.append(m["P1BLLM01Interpretation"](
                    entry_id=entry_id,
                    applicable=m["P1BLLM01Applicable"](applicable_str),
                    activation_rationale=rationale,
                    layer0_refs=self._extract_list_field(sub_body, "layer0_refs"),
                    legal_refs=self._extract_list_field(sub_body, "legal_refs"),
                    company_fact_refs=self._extract_list_field(sub_body, "company_fact_refs"),
                ))
        else:
            # CORR-065: bullet-list fallback. Some models (notably
            # MiniMax-M3) emit `## Interpretations` as a flat bullet
            # list of `- ENTRY_ID (VERDICT): rationale...` instead of
            # `### INT-NN` sub-sections. Accept that shape; normalise
            # the verdict via the CORR-074 helper so variants like
            # `(YES)` / `(NO)` / `(INDETERMINATE)` keep working.
            _BULLET_RE = re.compile(
                r"^- \s*([A-Z][A-Z0-9_]+(?:-[A-Z0-9_]+)*)\s*"
                r"\(([^)]+)\)\s*:\s*(.+?)(?=\n- |\n## |\Z)",
                re.MULTILINE | re.DOTALL,
            )
            for m_b in _BULLET_RE.finditer(interp_body):
                entry_id, verdict_raw, rationale = (
                    m_b.group(1).strip(),
                    m_b.group(2).strip(),
                    m_b.group(3).strip(),
                )
                verdict = self._normalise_verdict(verdict_raw, "interp")
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
            for sub_id, heading_line, sub_body in der_subs:
                # CORR-050: legacy shape uses `- entry_id:` in body.
                # CORR-074: new shape puts the entry_id in the heading.
                # Prefer body field when present.
                entry_id = (
                    self._extract_field(sub_body, "entry_id")
                    or sub_id
                )
                verdict_str_raw = self._extract_field(sub_body, "activation_verdict") or ""
                # CORR-074 (post-fix 2026-08-05): verdict token captured
                # directly by `_SUBSEC_DER` from the heading line.
                if not verdict_str_raw:
                    heading_m = self._SUBSEC_DER.match(heading_line)
                    verdict_str_raw = (
                        heading_m.group(3) if heading_m and heading_m.group(3) else ""
                    )
                verdict_str = self._normalise_verdict(verdict_str_raw, "derog")
                if verdict_str not in {e.value for e in m["P1BLLM01DerogationVerdict"]}:
                    return None
                rationale = self._extract_field(sub_body, "activation_rationale") or sub_body.strip()
                derogations.append(m["P1BLLM01Derogation"](
                    entry_id=entry_id,
                    activation_verdict=m["P1BLLM01DerogationVerdict"](verdict_str),
                    activation_rationale=rationale,
                    layer0_refs=self._extract_list_field(sub_body, "layer0_refs"),
                    legal_refs=self._extract_list_field(sub_body, "legal_refs"),
                    company_fact_refs=self._extract_list_field(sub_body, "company_fact_refs"),
                ))
        else:
            # CORR-065: bullet-list fallback (symmetric to interpretations)
            _BULLET_RE_DER = re.compile(
                r"^- \s*([A-Z][A-Z0-9_]+(?:-[A-Z0-9_]+)*)\s*"
                r"\(([^)]+)\)\s*:\s*(.+?)(?=\n- |\n## |\Z)",
                re.MULTILINE | re.DOTALL,
            )
            for m_b in _BULLET_RE_DER.finditer(der_body):
                entry_id, verdict_raw, rationale = (
                    m_b.group(1).strip(),
                    m_b.group(2).strip(),
                    m_b.group(3).strip(),
                )
                verdict = self._normalise_verdict(verdict_raw, "derog")
                derogations.append(m["P1BLLM01Derogation"](
                    entry_id=entry_id,
                    activation_verdict=m["P1BLLM01DerogationVerdict"](verdict),
                    activation_rationale=rationale,
                    layer0_refs=[],
                    legal_refs=[],
                    company_fact_refs=[],
                ))

        # Optional ## Notes section (CORR-074). Missing → empty string.
        notes_body = self._extract_section(text, "notes") or ""
        # CORR-074 (post-fix 2026-08-05): the status justification is
        # captured by `_parse_status_prose` but not surfaced into the
        # model — `P1BLLM01Output` has no dedicated `justification`
        # field (per user minimal-change directive), so we drop it for
        # now. The justification is preserved in the raw markdown
        # captured under `state['per_spec_markdown'][spec_id]` (CORR-061 S3b).

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
                notes=notes_body,
            )
            return model
        except ValidationError:
            return None

    @staticmethod
    def _parse_status_prose(body: str) -> tuple[str, str, str]:
        """Parse `## Status` body — supports BOTH bullet and prose forms.

        **Prose form** (CORR-074): ``OK — HIGH confidence. <justification>``.
        Accepts status tokens `OK`, `INSUFFICIENT_EVIDENCE`, `INDETERMINATE`
        (and legacy `YES` / `NO`), optional `—`/`-`/`:` separator, optional
        `(HIGH|MEDIUM|LOW) confidence`, and any trailing prose is treated as
        justification.

        **Bullet form** (CORR-050 legacy): ``- status: OK`` /
        ``- confidence: HIGH``. Both shapes are still accepted so existing
        callers (notably `tests/unit/prompts_v2/test_markdown_parser_corr050.py`)
        keep working.

        Returns ``(status, confidence, justification)``. ``justification``
        is empty when the body matches the bullet form (legacy contracts
        didn't capture one). When the body matches the prose form, the
        residual text after the confidence token is returned as the
        justification. When no token matches at all, the entire body is
        returned as justification so the caller still has a fallback.

        CORR-074 propagation (P1B-LLM-02 / P1C-LLM-02): this helper was
        extracted from ``P1BLLM01Parser`` to the base class so the
        three markdown-using specs (P1B-01, P1B-02, P1C-02) can share it.
        Existing callers using ``P1BLLM01Parser._parse_status_prose(...)``
        keep working via a thin staticmethod alias.
        """
        s = (body or "").strip()
        if not s:
            return "", "", ""

        # ── Bullet form (CORR-050) ────────────────────────────────────
        # First try the bullet style — single status + confidence lines.
        status_bullet = re.search(
            r"^-\s*status\s*:\s*(\S+)",
            s,
            re.MULTILINE | re.IGNORECASE,
        )
        if status_bullet is None:
            status_bullet = re.search(
                r"^-\s*applicable\s*:\s*(\S+)",
                s,
                re.MULTILINE | re.IGNORECASE,
            )
        confidence_bullet = re.search(
            r"^-\s*confidence\s*:\s*(\S+)",
            s,
            re.MULTILINE | re.IGNORECASE,
        )
        if status_bullet is not None:
            status = status_bullet.group(1).upper()
            confidence = (
                confidence_bullet.group(1).upper()
                if confidence_bullet is not None
                else "MEDIUM"
            )
            return status, confidence, ""

        # ── Prose form (CORR-074) ─────────────────────────────────────
        # Strip leading bullets / markdown emphasis so a single-line body
        # is matched directly. `**OK**` and `**OK** — HIGH confidence`
        # both need the bold markers removed before the regex anchor.
        s = re.sub(r"^[-*]\s*", "", s)
        s = re.sub(r"\*+", "", s)
        m = re.match(
            r"^(OK|INSUFFICIENT_EVIDENCE|INDETERMINATE|YES|NO)\s*"
            r"(?:[—\-:]\s*|\s+)?"
            r"(?:(HIGH|MEDIUM|LOW)\s+confidence\.?)?\s*"
            r"(.*)$",
            s,
            re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return "", "", s
        status = m.group(1).upper()
        confidence = (m.group(2) or "").upper() or "MEDIUM"
        justification = (m.group(3) or "").strip()
        return status, confidence, justification


class P1BLLM02Parser(MarkdownParser):
    """Parser for P1B-LLM-02-RATIONALE markdown output.

    CORR-074 propagation: contract switched from JSON Schema
    (``output_schemas.yaml#P1B-LLM-02``) to markdown+regex, mirroring
    the CORR-050 / CORR-074 P1B-LLM-01 pattern. The parser tolerates:

      - Optional qualifiers on top-level section headings (e.g.
        ``## Rationale (P1B-02)``, ``## Implications (per regulation)``).
      - Empty sections: a missing ``## Rationale`` yields
        ``rationale=""``; a missing ``## Implications`` /
        ``## Gaps`` / ``## Notes`` yields empty lists / empty string.
      - One ``### IMP-D-XX.Y-N`` subsection per implication with
        body fields (``id``, ``description``, ``effort_estimate``,
        ``dependencies``, ``layer0_refs``, ``company_fact_refs``).
      - One ``### GAP-D-XX.Y`` subsection per gap with body fields
        (``gap_id``, ``sub_domain_id``, ``coverage_level``,
        ``risk_description``, ``covered_by_other_reg``,
        ``recommendation``, ``priority``, ``layer0_refs``).
      - Effort-estimate aliases (``"hours to days"``, ``"weeks (1-2)"``,
        ``"1-3 months"``, ``"~1 week"``, ``"fte_quarter"``, ...) are
        normalised onto the canonical 8-value enum.
      - Priority variants (``"P1"`` / ``"p1"`` / ``"1"`` /
        ``"priority 1"``) → canonical ``"P1"``.
      - Coverage variants (``"NOT_ADDRESSED"`` / ``"NOT ADDRESSED"`` /
        ``"partial"`` / ``"partially_addressed"``) → strict enum token.

    Missing or malformed subsection IDs (no heading id, no body
    ``id:`` field) cause the subsection to be silently dropped (with
    a regex capture group still emitted as the canonical entry ID).
    An invalid ``effort_estimate`` / ``coverage_level`` / ``priority``
    (not in the canonical enum and not in the alias table) fails the
    whole parse — Pydantic surfaces the mismatch instead of silently
    accepting.
    """

    SECTION_PATTERNS: ClassVar[dict[str, re.Pattern]] = {
        "status": re.compile(r"^##\s+Status\b.*$", re.MULTILINE),
        "rationale": re.compile(r"^##\s+Rationale\b.*$", re.MULTILINE),
        "implications": re.compile(r"^#{2,3}\s+Implications\b.*$", re.MULTILINE),
        "gaps": re.compile(r"^#{2,3}\s+Gaps\b.*$", re.MULTILINE),
        "notes": re.compile(r"^##\s+Notes\b.*$", re.MULTILINE),
    }
    # CORR-074 propagation shape (no inline verdict in the heading —
    # all verdict info lives in the body fields). Captures the full
    # subsection id (``IMP-D-02.3-1`` / ``GAP-D-07.1``).
    _SUBSEC_IMP: ClassVar[re.Pattern[str]] = re.compile(
        r"^#{3,4}\s+(IMP-[A-Z0-9.\-]+)\s*$",
        re.MULTILINE,
    )
    _SUBSEC_GAP: ClassVar[re.Pattern[str]] = re.compile(
        r"^#{3,4}\s+(GAP-[A-Z0-9.\-]+)\s*$",
        re.MULTILINE,
    )
    # CORR-074 propagation: canonical verdict taxonomy normalisers.
    # Aliases are matched case-insensitively against the lowercased
    # input. Unknown tokens are upper-cased and returned as-is so
    # Pydantic validation surfaces the mismatch (fail-loud).
    _VERDICT_NORMALISE_COVERAGE: ClassVar[dict[str, str]] = {
        "not_addressed": "NOT_ADDRESSED",
        "not addressed": "NOT_ADDRESSED",
        "partial": "PARTIAL",
        "partially_addressed": "PARTIAL",
    }
    _VERDICT_NORMALISE_PRIORITY: ClassVar[dict[str, str]] = {
        "p1": "P1",
        "1": "P1",
        "priority 1": "P1",
        "p2": "P2",
        "2": "P2",
        "priority 2": "P2",
        "p3": "P3",
        "3": "P3",
        "priority 3": "P3",
    }
    _VERDICT_NORMALISE_EFFORT: ClassVar[dict[str, str]] = {
        "hours": "hours",
        "hour": "hours",
        "days": "days",
        "day": "days",
        "1-2 days": "days",
        "hours to days": "days",
        "weeks_1": "weeks_1",
        "1 week": "weeks_1",
        "~1 week": "weeks_1",
        "weeks (1-2)": "weeks_1",
        "1-2 weeks": "weeks_1",
        "weeks_2_4": "weeks_2_4",
        "2-4 weeks": "weeks_2_4",
        "weeks (2-4)": "weeks_2_4",
        "months_1_3": "months_1_3",
        "1-3 months": "months_1_3",
        "months_3_6": "months_3_6",
        "3-6 months": "months_3_6",
        "fte_quarter": "fte_quarter",
        "quarter fte": "fte_quarter",
        "fte_permanent": "fte_permanent",
        "permanent fte": "fte_permanent",
    }

    @classmethod
    def _normalise_effort(cls, raw: str) -> str:
        """Map LLM-emitted effort-estimate aliases to the 8-value enum."""
        s = (raw or "").strip().lower()
        if not s:
            return ""
        return cls._VERDICT_NORMALISE_EFFORT.get(s, s.upper())

    @classmethod
    def _extract_bracketed_list_field(
        cls, text: str, field_name: str
    ) -> list[str]:
        """Extract ``- field_name: [a, b, c]`` (JSON-style bracketed list).

        Empirical MiniMax-M3 sometimes emits list values as JSON-like
        arrays (``["foo.md", "bar.md"]``) instead of the spec's
        comma-separated form (``foo.md, bar.md``). The base
        ``_extract_list_field`` doesn't strip the surrounding
        brackets, so a value like ``[D-01.1, D-04.3]`` would yield
        ``['[D-01.1', 'D-04.3]'``. This helper:
        1. Tries the plain comma-separated form first (spec canonical).
        2. Falls back to bracketed form, stripping ``[`` / ``]``.
        3. Tolerates backticked field names.

        Falls back to ``_extract_list_field`` for multi-bullet form
        (``- field_name:\\n  - a\\n  - b``) — defensive, in case M3
        emits that shape too.
        """
        # Try the backticked/plain field name extraction first.
        plain = cls._extract_field(text, field_name)
        if plain is None:
            plain = cls._extract_field_bt(text, field_name)
        if plain is None:
            return cls._extract_list_field(text, field_name)
        s = plain.strip()
        # Strip outer brackets — spec is permissive between
        # `[a, b]` (JSON array literal) and `a, b` (bare list).
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        return [v.strip().strip('"').strip("'") for v in s.split(",") if v.strip()]

    @classmethod
    def _normalise_coverage(cls, raw: str) -> str:
        """Map LLM-emitted coverage-level variants to the strict enum."""
        s = (raw or "").strip().lower()
        if not s:
            return ""
        return cls._VERDICT_NORMALISE_COVERAGE.get(s, s.upper())

    @classmethod
    def _normalise_priority(cls, raw: str) -> str:
        """Map LLM-emitted priority variants to the strict enum."""
        s = (raw or "").strip().lower()
        if not s:
            return ""
        return cls._VERDICT_NORMALISE_PRIORITY.get(s, s.upper())

    def parse(self, raw: str) -> tuple[Any | None, str]:
        """Parse the LLM output. Returns (model_instance, error_feedback).

        CORR-074 propagation: the spec asks for markdown (see
        ``## Output Format (mandatory)`` in P1B-LLM-02-RATIONALE.md).
        The parser:

        1. Strips code fences (defensive — spec explicitly forbids them).
        2. Extracts ``## Status`` via
           ``MarkdownParser._parse_status_prose`` (shared with
           P1B-LLM-01).
        3. Captures ``## Rationale`` body verbatim (single string).
        4. Splits ``## Implications`` by ``### IMP-D-XX.Y-N`` and
           extracts body fields via ``_extract_field`` /
           ``_extract_list_field``. Invalid effort → fail the whole
           parse.
        5. Splits ``## Gaps`` by ``### GAP-D-XX.Y``; falls back to
           the heading token for ``sub_domain_id`` when the body
           omits it. Invalid coverage / priority → fail.
        6. Captures ``## Notes`` body verbatim (optional → empty string).
        7. Builds ``P1BLLM02Output`` and returns it.

        On failure returns ``(None, error_msg)``. The invoker injects
        envelope fields (``prompt_spec_id``, ``schema_version``,
        ``case_id``, ``invocation_pattern``) after parse() succeeds.
        """
        m = _import_p1b02_models()
        text = self._strip_code_fences(raw)

        try:
            result = self._parse_markdown(text, m)
            if result is not None:
                return result, ""
            return None, "markdown extraction did not match template"
        except Exception as e:
            return None, f"P1B-LLM-02 markdown parse exception: {e}"

    def _parse_markdown(self, text: str, m: dict) -> Any | None:
        """Markdown parser (CORR-074 propagation, P1B-LLM-02-RATIONALE)."""
        # ── Status section (required) ─────────────────────────────────
        status_body = self._extract_section(text, "status")
        if status_body is None:
            return None
        # CORR-074: prose form ``**OK** — HIGH confidence. <just>``.
        # Shared helper on the base class — same shape as P1B-01.
        status_str, conf_str, _justification = MarkdownParser._parse_status_prose(
            status_body
        )
        if not status_str:
            return None
        if status_str not in {e.value for e in m["P1BLLM01Status"]}:
            return None
        if conf_str not in {e.value for e in m["P1BLLM01Confidence"]}:
            conf_str = "MEDIUM"

        # ── Rationale section (optional body) ────────────────────────
        rationale = self._extract_section(text, "rationale") or ""

        # ── Implications section ─────────────────────────────────────
        implications: list = []
        impl_body = self._extract_section(text, "implications") or ""
        impl_subs = self._split_subsections(impl_body, self._SUBSEC_IMP)
        for sub_id, _heading_line, sub_body in impl_subs:
            # CORR-074 propagation: id is in the heading
            # (``### IMP-D-XX.Y-N``). Body's ``- id:`` field is the
            # legacy fallback (defensive). Empirical M3 wraps field
            # names in backticks (``- `id`: ...``) — ``_extract_field_bt``
            # accepts both shapes.
            imp_id = self._extract_field_bt(sub_body, "id") or sub_id
            if not imp_id:
                continue
            description = self._extract_field_bt(sub_body, "description") or ""
            if not description:
                # Required field missing → reject the subsection.
                continue
            effort_raw = self._extract_field_bt(sub_body, "effort_estimate") or ""
            effort_str = self._normalise_effort(effort_raw)
            if effort_str not in {e.value for e in m["P1BLLM02EffortEstimate"]}:
                # Invalid value → reject the whole doc (fail-loud).
                return None
            dependencies = self._extract_bracketed_list_field(
                sub_body, "dependencies"
            )
            layer0_refs = self._extract_bracketed_list_field(
                sub_body, "layer0_refs"
            )
            company_fact_refs = self._extract_bracketed_list_field(
                sub_body, "company_fact_refs"
            )
            implications.append(m["P1BLLM02Implication"](
                id=imp_id,
                description=description,
                effort_estimate=m["P1BLLM02EffortEstimate"](effort_str),
                dependencies=dependencies,
                layer0_refs=layer0_refs,
                company_fact_refs=company_fact_refs,
            ))

        # ── Gaps section ──────────────────────────────────────────────
        gaps: list = []
        gap_body = self._extract_section(text, "gaps") or ""
        gap_subs = self._split_subsections(gap_body, self._SUBSEC_GAP)
        for sub_id, _heading_line, sub_body in gap_subs:
            # gap_id from body (preferred) or heading token (fallback).
            gap_id = self._extract_field_bt(sub_body, "gap_id") or sub_id
            if not gap_id:
                continue
            # sub_domain_id from body (preferred) or heading token
            # ``### GAP-D-XX.Y`` → ``D-XX.Y`` (fallback).
            sub_domain_id = self._extract_field_bt(
                sub_body, "sub_domain_id"
            ) or ""
            if not sub_domain_id and sub_id:
                _sub_match = re.match(r"^GAP-(D-\d+\.\d+)$", sub_id)
                if _sub_match is not None:
                    sub_domain_id = _sub_match.group(1)
            if not sub_domain_id:
                continue
            coverage_raw = self._extract_field_bt(
                sub_body, "coverage_level"
            ) or ""
            coverage_str = self._normalise_coverage(coverage_raw)
            if coverage_str not in {e.value for e in m["P1BLLM02CoverageLevel"]}:
                return None
            risk_description = self._extract_field_bt(
                sub_body, "risk_description"
            ) or ""
            if not risk_description:
                continue
            covered_by_other_reg = self._extract_bracketed_list_field(
                sub_body, "covered_by_other_reg"
            )
            recommendation = self._extract_field_bt(
                sub_body, "recommendation"
            ) or ""
            priority_raw = self._extract_field_bt(sub_body, "priority") or ""
            priority_str = self._normalise_priority(priority_raw)
            if priority_str not in {e.value for e in m["P1BLLM02Priority"]}:
                return None
            layer0_refs = self._extract_bracketed_list_field(
                sub_body, "layer0_refs"
            )
            gaps.append(m["P1BLLM02Gap"](
                gap_id=gap_id,
                sub_domain_id=sub_domain_id,
                coverage_level=m["P1BLLM02CoverageLevel"](coverage_str),
                risk_description=risk_description,
                covered_by_other_reg=covered_by_other_reg,
                recommendation=recommendation,
                priority=m["P1BLLM02Priority"](priority_str),
                layer0_refs=layer0_refs,
            ))

        # ── Notes section (optional → "") ─────────────────────────────
        notes_body = self._extract_section(text, "notes") or ""

        # ── Build envelope-less model; envelope injected by invoker ──
        try:
            confidence = (
                m["P1BLLM01Confidence"](conf_str)
                if conf_str in {e.value for e in m["P1BLLM01Confidence"]}
                else m["P1BLLM01Confidence"].MEDIUM
            )
            return m["P1BLLM02Output"](
                status=m["P1BLLM01Status"](status_str),
                confidence=confidence,
                rationale=rationale,
                implications=implications,
                gaps=gaps,
                notes=notes_body,
            )
        except ValidationError:
            return None


class P1CLLM03Parser(MarkdownParser):
    """Parser for P1C-LLM-03-STRATEGIC-SYNTHESIS markdown output.

    CORR-074 propagation: contract switched from JSON Schema
    (``output_schemas.yaml#P1C-LLM-03``) to markdown+regex, mirroring
    the CORR-050 / CORR-074 P1B-LLM-01 pattern and the symmetric
    P1C-LLM-02 propagation shape. The parser tolerates:

      - Optional qualifiers on ``## Implications`` (e.g.
        ``## Implications (Phase 1C)`` — empirical M3 drift; same
        shape as the P1B-01 ``(Tipo 2)`` qualifier).
      - Risk-level variants: ``low`` / ``medium`` / ``high`` (case
        variants) and ``Risk Level: medium`` style prefixes all
        normalise to the strict enum token.
      - Confidence variants: ``low`` / ``medium`` / ``high`` (case
        variants) and ``Confidence: high`` style prefixes all
        normalise to ``HIGH / MEDIUM / LOW``.
      - Optional ``## Notes`` section — if missing, ``notes=""``.
      - Empty ``## Implications`` (header only) — zero implications
        is a valid output per the spec's "1-2 acknowledging mostly
        settled" case.
      - Empty ``## Status`` justification body — handled by the
        shared ``_parse_status_prose`` helper (same shape as P1B-01).

    Pydantic enforces:

      - ``affected_sub_domains`` and ``regulations`` with
        ``min_length=2`` (cross-lane + cross-regulation requirement)
        — any implication that spans fewer than 2 sub-domains or
        regulations raises ``ValidationError`` and the parser
        returns ``(None, error_msg)``.
      - ``model_config = {"extra": "ignore"}`` so envelope fields
        the LLM might emit are silently dropped (the invoker
        re-injects them post-parse).
    """

    SECTION_PATTERNS: ClassVar[dict[str, re.Pattern]] = {
        "status": re.compile(r"^##\s+Status\b.*$", re.MULTILINE),
        "implications": re.compile(r"^##\s+Implications\b.*$", re.MULTILINE),
        "notes": re.compile(r"^##\s+Notes\b.*$", re.MULTILINE),
    }
    # CORR-074 propagation shape: subsection heading is the bare
    # ``### IMP-NN`` token (no inline verdict — all verdict info
    # lives in the body fields). Distinct from P1B-01's
    # ``### ENTRY_ID — VERDICT`` shape.
    _SUBSEC_IMP: ClassVar[re.Pattern[str]] = re.compile(
        r"^#{3,4}\s+IMP-\d+\s*$",
        re.MULTILINE,
    )
    # CORR-074 propagation: canonical taxonomy normalisers. Aliases
    # are matched case-insensitively against the lowercased input.
    # Unknown tokens are upper-cased and returned as-is so Pydantic
    # validation surfaces the mismatch (fail-loud).
    _VERDICT_NORMALISE_RISK: ClassVar[dict[str, str]] = {
        "low": "LOW",
        "medium": "MEDIUM",
        "med": "MEDIUM",
        "high": "HIGH",
    }
    _VERDICT_NORMALISE_CONFIDENCE: ClassVar[dict[str, str]] = {
        "low": "LOW",
        "medium": "MEDIUM",
        "med": "MEDIUM",
        "high": "HIGH",
    }

    @classmethod
    def _normalise_risk(cls, raw: str) -> str:
        """Map LLM-emitted risk-level variants to the strict enum token.

        ``low → LOW``, ``medium → MEDIUM``, ``high → HIGH``. Unknown
        tokens are upper-cased and returned as-is so Pydantic surfaces
        the mismatch.
        """
        s = (raw or "").strip().lower()
        if not s:
            return ""
        return cls._VERDICT_NORMALISE_RISK.get(s, s.upper())

    @classmethod
    def _normalise_confidence(cls, raw: str) -> str:
        """Map LLM-emitted confidence variants to the strict enum token.

        Same shape as ``_normalise_risk`` but operates on the
        confidence domain (canonical: HIGH / MEDIUM / LOW).
        """
        s = (raw or "").strip().lower()
        if not s:
            return ""
        return cls._VERDICT_NORMALISE_CONFIDENCE.get(s, s.upper())

    def parse(self, raw: str) -> tuple[Any | None, str]:
        """Parse the LLM output. Returns (model_instance, error_feedback).

        CORR-074 propagation: the spec asks for markdown (see
        ``## Output Format (mandatory)`` in P1C-LLM-03-STRATEGIC-SYNTHESIS.md).
        The parser:

        1. Strips code fences (defensive — spec explicitly forbids them).
        2. Extracts ``## Status`` via the shared
           ``MarkdownParser._parse_status_prose`` helper (same
           ``OK — HIGH confidence. <justification>`` shape as
           P1B-01 / P1B-02 / P1C-02).
        3. Splits ``## Implications`` by ``### IMP-NN`` and
           extracts body fields (``id``, ``description``,
           ``affected_sub_domains``, ``regulations``,
           ``architectural_impact``, ``business_goal_alignment``,
           ``risk_level``, ``assumptions``, ``layer0_refs``,
           ``doc07b_refs``, ``confidence``). Tolerates ``Risk Level:``
           and ``Confidence:`` style prefixes via
           ``_extract_field_with_aliases``.
        4. Captures ``## Notes`` body verbatim (optional → empty string).
        5. Builds ``P1CLLM03Output`` and returns it. Pydantic
           enforces ``min_length=2`` on ``affected_sub_domains`` and
           ``regulations`` — a parse-time ``ValidationError`` is
           caught by the outer ``parse()`` and surfaced as a
           ``(None, error_msg)`` tuple (the invoker feeds the error
           back to the LLM as a retry signal).

        Returns ``(model, "")`` on success, ``(None, error_msg)`` on
        failure. The invoker injects envelope fields (``prompt_spec_id``,
        ``schema_version``, ``case_id``, ``invocation_pattern``) after
        parse() returns successfully.
        """
        m = _import_p1c03_models()
        text = self._strip_code_fences(raw)

        try:
            return self._parse_markdown(text, m), ""
        except Exception as e:
            return None, f"P1C-LLM-03 markdown parse exception: {e}"

    def _parse_markdown(self, text: str, m: dict) -> Any | None:
        """Markdown parser (CORR-074 propagation, P1C-LLM-03)."""
        # ── Status section (required) ─────────────────────────────────
        status_body = self._extract_section(text, "status")
        if status_body is None:
            return None
        # Shared prose helper — same shape as P1B-01 /
        # P1B-02 / P1C-02.
        status_str, conf_str, _justification = MarkdownParser._parse_status_prose(
            status_body
        )
        if not status_str:
            return None
        if status_str not in {e.value for e in m["P1BLLM01Status"]}:
            return None
        if conf_str not in {e.value for e in m["P1BLLM01Confidence"]}:
            conf_str = "MEDIUM"

        # ── Implications section ──────────────────────────────────────
        implications: list = []
        impl_body = self._extract_section(text, "implications") or ""
        impl_subs = self._split_subsections(impl_body, self._SUBSEC_IMP)
        for sub_id, _heading_line, sub_body in impl_subs:
            # CORR-074 propagation: id is in the heading
            # (``### IMP-NN``). Body's ``- id:`` field is the legacy
            # fallback (defensive). Empirical M3 wraps field names in
            # backticks (``- `id`: ...``) — ``_extract_field_bt``
            # accepts plain / backticked / bold shapes.
            imp_id = self._extract_field_bt(sub_body, "id") or sub_id
            if not imp_id:
                continue
            description = self._extract_field_bt(sub_body, "description") or ""
            if not description:
                # Required field missing → reject this subsection.
                continue
            affected_sub_domains = self._extract_bracketed_list_field(
                sub_body, "affected_sub_domains"
            )
            regulations = self._extract_bracketed_list_field(
                sub_body, "regulations"
            )
            architectural_impact = (
                self._extract_field_bt(sub_body, "architectural_impact") or ""
            )
            business_goal_alignment = (
                self._extract_field_bt(sub_body, "business_goal_alignment") or ""
            )
            # CORR-074 propagation: tolerate ``Risk Level:`` /
            # ``risk_level:`` / ``- **Risk Level**:`` shape variants.
            risk_raw = self._extract_field_with_aliases(
                sub_body, "risk_level", aliases=("Risk Level",)
            ) or ""
            risk_str = self._normalise_risk(risk_raw)
            if risk_str not in {e.value for e in m["P1CLLM03RiskLevel"]}:
                return None
            assumptions = self._extract_list_field(sub_body, "assumptions")
            layer0_refs = self._extract_bracketed_list_field(
                sub_body, "layer0_refs"
            )
            doc07b_refs = self._extract_bracketed_list_field(
                sub_body, "doc07b_refs"
            )
            # CORR-074 propagation: tolerate ``Confidence:`` /
            # ``confidence:`` shape variants via the same alias helper.
            conf_raw = self._extract_field_with_aliases(
                sub_body, "confidence", aliases=("Confidence",)
            ) or ""
            conf_local_str = self._normalise_confidence(conf_raw)
            if conf_local_str not in {e.value for e in m["P1BLLM01Confidence"]}:
                return None
            implications.append(m["P1CLLM03Implication"](
                id=imp_id,
                description=description,
                affected_sub_domains=affected_sub_domains,
                regulations=regulations,
                architectural_impact=architectural_impact,
                business_goal_alignment=business_goal_alignment,
                risk_level=m["P1CLLM03RiskLevel"](risk_str),
                assumptions=assumptions,
                layer0_refs=layer0_refs,
                doc07b_refs=doc07b_refs,
                confidence=m["P1BLLM01Confidence"](conf_local_str),
            ))

        # ── Notes section (optional → "") ─────────────────────────────
        notes_body = self._extract_section(text, "notes") or ""

        # ── Build envelope-less model; envelope injected by invoker ──
        try:
            confidence = (
                m["P1BLLM01Confidence"](conf_str)
                if conf_str in {e.value for e in m["P1BLLM01Confidence"]}
                else m["P1BLLM01Confidence"].MEDIUM
            )
            return m["P1CLLM03Output"](
                status=m["P1BLLM01Status"](status_str),
                confidence=confidence,
                implications=implications,
                notes=notes_body,
            )
        except ValidationError:
            return None


# Lazy import to avoid forward refs (state.py imports many things).
def _import_p1c03_models():
    """Lazy import to avoid circular imports at module load.

    CORR-074 propagation: imports the P1C-LLM-03-STRATEGIC-SYNTHESIS
    Pydantic models from ``state``. Used by ``P1CLLM03Parser`` to build
    the structured ``P1CLLM03Output`` after markdown extraction.
    """
    from aegis_phase1.v2.state import (
        P1BLLM01Confidence,
        P1BLLM01Status,
        P1CLLM03Implication,
        P1CLLM03Output,
        P1CLLM03RiskLevel,
    )
    return {
        "P1BLLM01Status": P1BLLM01Status,
        "P1BLLM01Confidence": P1BLLM01Confidence,
        "P1CLLM03Output": P1CLLM03Output,
        "P1CLLM03Implication": P1CLLM03Implication,
        "P1CLLM03RiskLevel": P1CLLM03RiskLevel,
    }


class P1CLLM01Parser(MarkdownParser):
    """Parser for P1C-LLM-01-OVERLAP-CLASSIFICATION markdown output.

    CORR-074 propagation: contract switched from JSON Schema
    (``output_schemas.yaml#P1C-LLM-01``) to markdown+regex, mirroring
    the CORR-050 / CORR-074 P1B-LLM-01 pattern. The parser tolerates:

      - Optional qualifiers on ``## Sub-domain Activations`` (e.g.
        ``## Sub-domain Activations (D-01)`` — empirical M3 drift).
      - Boolean ``applicable`` values (``true`` / ``True`` / ``false`` /
        ``False`` / missing → ``False``).
      - Scope overlap variants: ``Y (yes)`` / ``N (no)`` /
        ``CONDITIONAL`` all normalise to the strict enum token.
      - Scope verdict variants: ``OVERLAP NOT TRIGGERED`` (with space),
        ``not_triggered`` (snake), ``disjoint`` → canonical token.
      - Pair-separator: ``#### REG-A ↔ REG-B`` (em-dash arrow) OR
        ``#### REG-A vs REG-B`` (empirical fallback).
      - Optional ``## Notes`` section — if missing, ``notes=""``.
      - Empty ``## Sub-domain Activations`` (header only) — zero
        activations is a valid output per the spec.

    Backticked body fields (``- `id`: value``) and JSON-style
    bracketed lists (``["foo.md", "bar.md"]``) are normalised via
    the shared helpers reused from the P1B-02 parser (fall back to
    the base class implementation; if the P1B-02 helpers are not
    subclass-accessible we use the base class directly).

    An invalid ``layer0_relationship`` (not in the strict 5-value
    frozen enum) fails the whole parse — the LLM is not allowed to
    re-classify the FROZEN Regulatory Baseline relationships.
    """

    SECTION_PATTERNS: ClassVar[dict[str, re.Pattern]] = {
        "status": re.compile(r"^##\s+Status\b.*$", re.MULTILINE),
        "domain_summary": re.compile(r"^##\s+Domain\s+Summary\b.*$", re.MULTILINE),
        "sub_domain_activations": re.compile(
            r"^##\s+Sub-domain\s+Activations\b.*$", re.MULTILINE
        ),
        "notes": re.compile(r"^##\s+Notes\b.*$", re.MULTILINE),
    }
    # CORR-074 propagation: subsection header regex matches the bare
    # `### D-XX.Y` token (no inline verdict — all verdict info lives
    # in the body fields). Empirical (gemma4:e4b): models often append
    # the sub-domain title after the id (`### D-01.1 Data at Rest
    # Encryption`), so the title is tolerated as an optional suffix.
    _SUBSEC_DXX: ClassVar[re.Pattern[str]] = re.compile(
        # CORR-074 fix: anchor `$` directly after the id (or after an
        # optional inline title on the same line). The previous
        # ``(?:\s+.*)?$`` made ``\s+`` greedy and consumed the
        # newline + first body line of the activation, causing
        # ``applicable`` to be dropped on D-XX.Y subsections.
        r"^#{3,4}\s+(D-\d+\.\d+)(?:[ \t]+[^\n]*)?$",
        re.MULTILINE,
    )
    # CORR-074 propagation: pair heading accepts `#### REG-A ↔ REG-B`
    # (em-dash arrow) OR `#### REG-A vs REG-B` (empirical fallback).
    # The separator class is `[↔vs]+` — tolerant of `↔`, `↔`, `vs`,
    # `VS` (case-insensitive).
    _SUBSEC_PAIR: ClassVar[re.Pattern[str]] = re.compile(
        r"^####\s+([A-Z][A-Z0-9_]+)\s*[↔vs]+\s*([A-Z][A-Z0-9_]+)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    # CORR-074 propagation: canonical taxonomy normalisers. Aliases
    # are matched case-insensitively against the lowercased input.
    # Unknown tokens are upper-cased and returned as-is so Pydantic
    # validation surfaces the mismatch (fail-loud).
    _VERDICT_NORMALISE_SCOPE_VERDICT: ClassVar[dict[str, str]] = {
        "overlap_confirmed": "OVERLAP_CONFIRMED",
        "confirmed": "OVERLAP_CONFIRMED",
        "overlap not triggered": "OVERLAP_NOT_TRIGGERED",
        "not_triggered": "OVERLAP_NOT_TRIGGERED",
        "not triggered": "OVERLAP_NOT_TRIGGERED",
        "not_triggered (no)": "OVERLAP_NOT_TRIGGERED",
        "not triggered (no)": "OVERLAP_NOT_TRIGGERED",
        "no": "OVERLAP_NOT_TRIGGERED",
        "scope disjoint": "SCOPE_DISJOINT",
        "disjoint": "SCOPE_DISJOINT",
        "indeterminate": "INDETERMINATE",
        "uncertain": "INDETERMINATE",
    }
    _VERDICT_NORMALISE_SCOPE_OVERLAP: ClassVar[dict[str, str]] = {
        "y": "Y",
        "yes": "Y",
        "y (yes)": "Y",
        "n": "N",
        "no": "N",
        "n (no)": "N",
        "conditional": "CONDITIONAL",
    }

    @classmethod
    def _normalise_scope_verdict(cls, raw: str) -> str:
        """Map LLM-emitted scope-verdict variants to the strict enum."""
        s = (raw or "").strip().lower()
        if not s:
            return ""
        return cls._VERDICT_NORMALISE_SCOPE_VERDICT.get(s, s.upper())

    @classmethod
    def _normalise_scope_overlap(cls, raw: str) -> str:
        """Map LLM-emitted scope-overlap variants to the strict enum."""
        s = (raw or "").strip().lower()
        if not s:
            return ""
        return cls._VERDICT_NORMALISE_SCOPE_OVERLAP.get(s, s.upper())

    @classmethod
    def _parse_applicable(cls, raw: str) -> bool:
        """Coerce LLM-emitted ``applicable`` tokens to a boolean.

        Accepts ``true`` / ``True`` / ``TRUE`` / ``yes`` / ``y`` (→ True)
        and ``false`` / ``False`` / ``FALSE`` / ``no`` / ``n`` / ``""``
        (→ False). Missing or unrecognised values default to ``False``
        so the parser doesn't reject the subsection for cosmetic drift.
        """
        s = (raw or "").strip().lower()
        if s in {"true", "yes", "y", "1"}:
            return True
        return False

    @classmethod
    def _split_dxx_sections(
        cls, section_body: str
    ) -> list[tuple[str, str]]:
        """Split a section body into ``(sub_domain_id, sub_body)`` pairs.

        The shared ``MarkdownParser._split_subsections`` id-extraction
        regex doesn't match the ``D-XX.Y`` shape (it expects a final
        ``[A-Z0-9_]+`` token after the dash). This helper locates each
        ``### D-XX.Y`` heading line directly using ``_SUBSEC_DXX`` and
        returns the body verbatim — same shape contract as the shared
        splitter, minus the heading-line echo (we don't need it).
        """
        matches = list(cls._SUBSEC_DXX.finditer(section_body))
        results: list[tuple[str, str]] = []
        for i, m in enumerate(matches):
            sub_id = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(section_body)
            results.append((sub_id, section_body[start:end].strip()))
        return results

    @classmethod
    def _split_activation_pairs(
        cls, activation_body: str
    ) -> list[tuple[str, str, str]]:
        """Split an activation body into ``(reg_a, reg_b, pair_body)`` triples.

        The activation body contains body fields followed by one or
        more ``#### REG-A ↔ REG-B`` nested subsections. The helper
        locates every ``####`` heading and returns each block's body
        verbatim so the caller can extract the body fields.
        """
        # Local pattern: matches the pair heading itself (used to
        # locate block starts). Same regex as ``_SUBSEC_PAIR``.
        pair_header_re = cls._SUBSEC_PAIR
        matches = list(pair_header_re.finditer(activation_body))
        results: list[tuple[str, str, str]] = []
        for i, m in enumerate(matches):
            reg_a = m.group(1).upper()
            reg_b = m.group(2).upper()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(activation_body)
            results.append((reg_a, reg_b, activation_body[start:end].strip()))
        return results

    def parse(self, raw: str) -> tuple[Any | None, str]:
        """Parse the LLM output. Returns (model_instance, error_feedback).

        CORR-074 propagation: the spec asks for markdown (see
        ``## Output Format (mandatory)`` in
        P1C-LLM-01-OVERLAP-CLASSIFICATION.md). The parser:

        1. Strips code fences (defensive — spec explicitly forbids them).
        2. Extracts ``## Status`` via
           ``MarkdownParser._parse_status_prose`` (shared with P1B-01).
        3. Parses ``## Domain Summary`` body — extracts 3 integer fields.
        4. Splits ``## Sub-domain Activations`` by ``### D-XX.Y`` and
           extracts the body fields (``applicable``, ``scope_overlap``,
           ``applicable_regulations``, ``layer0_refs``), then splits
           the activation body by ``#### REG-A ↔ REG-B`` and extracts
           the pair body fields (``layer0_relationship``,
           ``company_scope_verdict``, ``rationale``, ``layer0_refs``).
        5. Captures ``## Notes`` body verbatim (optional → empty string).
        6. Builds ``P1CLLM01Output`` and returns it.

        On failure returns ``(None, error_msg)``. The invoker injects
        envelope fields (``prompt_spec_id``, ``schema_version``,
        ``case_id``, ``invocation_pattern``) after parse() succeeds.
        """
        m = _import_p1c01_models()
        text = self._strip_code_fences(raw)

        try:
            result = self._parse_markdown(text, m)
            if result is not None:
                return result, ""
            return None, "markdown extraction did not match template"
        except Exception as e:
            return None, f"P1C-LLM-01 markdown parse exception: {e}"

    def _parse_activations_body(self, body: str, m: dict) -> list | None:
        """Parse a body containing ``### D-XX.Y`` subsections into activations.

        Returns ``[P1CLLM01SubDomainActivation, ...]`` on success. Returns
        ``None`` to signal a fatal parse error (caller propagates the same
        fail-loud behaviour as the inline path). Returns ``[]`` when the
        body has no ``### D-XX.Y`` headings — i.e. the model omitted the
        activations section, prompting the caller's fallback path.

        CORR-074 propagation (empirical fix, gemma4:e4b): the model often
        skips the ``## Sub-domain Activations`` header and emits
        ``### D-XX.Y`` directly after ``## Domain Summary``. This helper
        is invoked on both the explicit activations body and a fallback
        region so both layouts are accepted.
        """
        activations: list = []
        for sub_id, sub_body in self._split_dxx_sections(body):
            if not sub_id:
                continue
            applicable = self._parse_applicable(
                self._extract_field_bt(sub_body, "applicable") or ""
            )
            scope_raw = self._extract_field_bt(sub_body, "scope_overlap") or ""
            scope_str = self._normalise_scope_overlap(scope_raw)
            if scope_str not in {e.value for e in m["P1CLLM01ScopeOverlap"]}:
                return None
            applicable_regs = self._extract_bracketed_list_field_local(
                sub_body, "applicable_regulations"
            )
            sub_layer0_refs = self._extract_bracketed_list_field_local(
                sub_body, "layer0_refs"
            )
            pairs: list = []
            for reg_a, reg_b, pair_body in self._split_activation_pairs(sub_body):
                # ``layer0_relationship`` is FROZEN — strict token only,
                # no normalise. If the LLM emits a variant, reject.
                l0_raw = (
                    self._extract_field_bt(pair_body, "layer0_relationship") or ""
                ).strip().upper()
                if l0_raw not in {e.value for e in m["P1CLLM01Layer0Relationship"]}:
                    return None
                verdict_raw = (
                    self._extract_field_bt(pair_body, "company_scope_verdict") or ""
                )
                verdict_str = self._normalise_scope_verdict(verdict_raw)
                if verdict_str not in {
                    e.value for e in m["P1CLLM01CompanyScopeVerdict"]
                }:
                    return None
                pairs.append(m["P1CLLM01Pair"](
                    reg_a=reg_a,
                    reg_b=reg_b,
                    layer0_relationship=m["P1CLLM01Layer0Relationship"](l0_raw),
                    company_scope_verdict=m["P1CLLM01CompanyScopeVerdict"](verdict_str),
                    rationale=self._extract_field_bt(pair_body, "rationale") or "",
                    layer0_refs=self._extract_bracketed_list_field_local(
                        pair_body, "layer0_refs"
                    ),
                ))
            activations.append(m["P1CLLM01SubDomainActivation"](
                sub_domain_id=sub_id,
                applicable=applicable,
                scope_overlap=m["P1CLLM01ScopeOverlap"](scope_str),
                applicable_regulations=applicable_regs,
                layer0_refs=sub_layer0_refs,
                verified_relationship_per_pair=pairs,
            ))
        return activations

    def _parse_markdown(self, text: str, m: dict) -> Any | None:
        """Markdown parser (CORR-074 propagation, P1C-LLM-01)."""
        # ── Status section (required) ─────────────────────────────────
        status_body = self._extract_section(text, "status")
        if status_body is None:
            return None
        # CORR-074: prose form ``**OK** — HIGH confidence. <just>``.
        # Shared helper on the base class — same shape as P1B-01.
        status_str, conf_str, _justification = MarkdownParser._parse_status_prose(
            status_body
        )
        if not status_str:
            return None
        if status_str not in {e.value for e in m["P1BLLM01Status"]}:
            return None
        if conf_str not in {e.value for e in m["P1BLLM01Confidence"]}:
            conf_str = "MEDIUM"

        # ── Domain Summary section ───────────────────────────────────
        domain_summary = m["P1CLLM01DomainSummary"]()
        ds_body = self._extract_section(text, "domain_summary") or ""
        for fname, target in [
            ("total_sub_domains", "total_sub_domains"),
            ("active_sub_domains", "active_sub_domains"),
            ("pairwise_relationships", "pairwise_relationships"),
        ]:
            raw_val = self._extract_field_bt(ds_body, fname) or "0"
            try:
                coerced = int(str(raw_val).strip())
            except (TypeError, ValueError):
                coerced = 0
            if target == "total_sub_domains":
                domain_summary.total_sub_domains = coerced
            elif target == "active_sub_domains":
                domain_summary.active_sub_domains = coerced
            else:
                domain_summary.pairwise_relationships = coerced

        # ── Sub-domain Activations section ────────────────────────────
        activations: list = []
        act_body = self._extract_section(text, "sub_domain_activations") or ""
        # The base ``_split_subsections`` id regex doesn't match the
        # ``D-XX.Y`` shape (expects a trailing letter pattern). Use a
        # local splitter that pulls the id from each ``### D-XX.Y``
        # heading line directly.
        activations = self._parse_activations_body(act_body, m)
        if activations is None:
            return None
        # CORR-074 propagation: empirical fallback (gemma4:e4b).
        # Some models skip the ``## Sub-domain Activations`` header and
        # emit ``### D-XX.Y`` headings directly after ``## Domain Summary``.
        # When the explicit activations section is absent, scan the
        # ``## Domain Summary`` body region for the same ``### D-XX.Y``
        # headings and parse them as activations. Triggered only when the
        # explicit section is empty (no double-parse when the model emits
        # both).
        if not activations and not act_body.strip():
            ds_body = self._extract_section(text, "domain_summary") or ""
            if ds_body and self._SUBSEC_DXX.search(ds_body):
                fb_acts = self._parse_activations_body(ds_body, m)
                if fb_acts is None:
                    return None
                activations = fb_acts

        # ── Notes section (optional → "") ─────────────────────────────
        notes_body = self._extract_section(text, "notes") or ""

        # ── Build envelope-less model; envelope injected by invoker ──
        try:
            confidence = (
                m["P1BLLM01Confidence"](conf_str)
                if conf_str in {e.value for e in m["P1BLLM01Confidence"]}
                else m["P1BLLM01Confidence"].MEDIUM
            )
            return m["P1CLLM01Output"](
                status=m["P1BLLM01Status"](status_str),
                confidence=confidence,
                domain_summary=domain_summary,
                sub_domain_activations=activations,
                notes=notes_body,
            )
        except ValidationError:
            return None

    @classmethod
    def _extract_bracketed_list_field_local(
        cls, text: str, field_name: str
    ) -> list[str]:
        """Local bracketed-list helper (mirrors P1B-02 behaviour).

        Tries plain comma-separated form first, then bracketed form
        (``[a, b, c]``), and tolerates backticked/bold field names.
        Falls back to the base ``_extract_list_field`` for the
        multi-bullet form. Mirrors the P1B-02 helper so the parser
        behaves identically across CORR-074 propagation contracts.
        """
        plain = cls._extract_field(text, field_name)
        if plain is None:
            plain = cls._extract_field_bt(text, field_name)
        if plain is None:
            return cls._extract_list_field(text, field_name)
        s = plain.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        return [v.strip().strip('"').strip("'") for v in s.split(",") if v.strip()]


# Lazy import to avoid forward refs (state.py imports many things).
def _import_p1c01_models():
    """Lazy import to avoid circular imports at module load.

    CORR-074 propagation: imports the P1C-LLM-01-OVERLAP-CLASSIFICATION
    Pydantic models from ``state``. Used by ``P1CLLM01Parser`` to build
    the structured ``P1CLLM01Output`` after markdown extraction.
    """
    from aegis_phase1.v2.state import (
        P1BLLM01Confidence,
        P1BLLM01Status,
        P1CLLM01CompanyScopeVerdict,
        P1CLLM01DomainSummary,
        P1CLLM01Layer0Relationship,
        P1CLLM01Output,
        P1CLLM01Pair,
        P1CLLM01ScopeOverlap,
        P1CLLM01SubDomainActivation,
    )
    return {
        "P1CLLM01Output": P1CLLM01Output,
        "P1CLLM01SubDomainActivation": P1CLLM01SubDomainActivation,
        "P1CLLM01Pair": P1CLLM01Pair,
        "P1CLLM01DomainSummary": P1CLLM01DomainSummary,
        "P1CLLM01CompanyScopeVerdict": P1CLLM01CompanyScopeVerdict,
        "P1CLLM01ScopeOverlap": P1CLLM01ScopeOverlap,
        "P1CLLM01Layer0Relationship": P1CLLM01Layer0Relationship,
        "P1BLLM01Status": P1BLLM01Status,
        "P1BLLM01Confidence": P1BLLM01Confidence,
    }


class GenericMarkdownParser(MarkdownParser):
    """CORR-066: spec-agnostic markdown parser.

    Captures the canonical ``## Status`` block (with ``- applicable:``
    and ``- confidence:`` fields) and stores every other ``## Section``
    body verbatim in ``sections[section_name]``. Used for the 3 LLMs
    that don't yet have a hand-rolled parser:

      - P1C-LLM-01-OVERLAP-CLASSIFICATION
      - P1C-LLM-03-STRATEGIC-SYNTHESIS
      (P1B-LLM-02 has ``P1BLLM02Parser`` since CORR-074 propagation;
       P1C-LLM-02 has ``P1CLLM02Parser``.)

    The raw markdown is also captured in
    ``state['per_spec_markdown'][spec_id]`` (CORR-061 S3b) for
    renderers that want the original text.
    """

    # Accept any ``## Section`` header — the parser is spec-agnostic.
    _H2_SPLIT_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

    def parse(self, raw: str) -> tuple[Any | None, str]:
        text = self._strip_code_fences(raw)
        m = _import_p1b_models()

        # Find all ## section headers and split the body between them
        matches = list(self._H2_SPLIT_RE.finditer(text))
        if not matches:
            return None, "no `## Section` headers found in markdown"

        sections: dict[str, str] = {}
        for i, m_h in enumerate(matches):
            section_name = m_h.group(1).strip()
            body_start = m_h.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections[section_name] = text[body_start:body_end].strip()

        # Extract Status fields (fall back to applicable per the
        # CORR-065 fix that accepts both `- status:` and
        # `- applicable:` under `## Status`).
        status_body = sections.get("Status", "")
        status_str = (
            self._extract_field(status_body, "status")
            or self._extract_field(status_body, "applicable")
            or ""
        ).upper() or "OK"
        conf_str = (self._extract_field(status_body, "confidence") or "MEDIUM").upper()

        try:
            status = m["P1BLLM01Status"](status_str)
        except ValueError:
            # Unknown status token — fall back to INDETERMINATE
            status = m["P1BLLM01Status"].INDETERMINATE
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
MARKDOWN_PARSERS: dict[str, type[MarkdownParser]] = {
    "P1B-LLM-01-INTERPRETATION": P1BLLM01Parser,
    "P1B-LLM-02-RATIONALE": P1BLLM02Parser,  # CORR-074 propagation
    "P1C-LLM-01-OVERLAP-CLASSIFICATION": P1CLLM01Parser,  # CORR-074 propagation
    "P1C-LLM-02-COMPOUND-EVENT": P1CLLM02Parser,  # CORR-074 propagation
    "P1C-LLM-03-STRATEGIC-SYNTHESIS": P1CLLM03Parser,  # CORR-074 propagation
}
