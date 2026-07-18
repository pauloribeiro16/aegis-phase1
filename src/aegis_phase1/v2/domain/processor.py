"""processor — Per-domain MAP worker (Option C: direct Ollama).

Sequential processing. Each domain is adapted through the LLM, with up
to ``MAX_RETRIES`` attempts. On parse failure the parser's feedback is
appended to the next prompt. The invoker's contract is::

    invoker.invoke(prompt: str, feedback: str = "") -> dict
        # returns {"raw": str, "status": "OK" | "FAILED_AFTER_RETRIES"}

Network or Ollama failures propagate as :class:`OllamaUnreachable`
so the orchestrator can abort the whole MAP stage — there is no
silent fallback.

Public API:
    DomainProcessor.process(domain_id, state) -> DomainResult
    OllamaUnreachable    fatal LLM failure
    MapPartialFailure    raised by the orchestrator when ≥1 domain fails
    DOMAIN_NAMES         D-XX → human-readable name
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegis_phase1.v2.domain.inputs import assemble_inputs
from aegis_phase1.v2.domain.parser import OutputParser, OutputParserV2, OutputParserV3
from aegis_phase1.v2.domain.prompt import render_prompt
from aegis_phase1.v2.state import DomainResult, V2State

logger = logging.getLogger(__name__)


# ─── Domain catalogue ──────────────────────────────────────────────────

DOMAIN_NAMES: dict[str, str] = {
    "D-01": "Data Protection",
    "D-02": "Vulnerability Management",
    "D-03": "Access Control",
    "D-04": "Incident Response",
    "D-05": "Data Lifecycle",
    "D-06": "Supply Chain",
    "D-07": "Secure Development",
    "D-08": "Human Factors",
    "D-09": "Governance & Documentation",
    "D-10": "Monitoring & Audit",
}


# ─── Exceptions ────────────────────────────────────────────────────────


class OllamaUnreachable(Exception):
    """Fatal: the LLM is unreachable. Propagates to abort MAP."""


class MapPartialFailure(Exception):
    """One or more domains failed. Blocks advance to REDUCE."""


# ─── Processor ─────────────────────────────────────────────────────────


class DomainProcessor:
    """Per-domain MAP-stage worker.

    Holds an invoker with the contract::

        invoke(prompt, feedback="") -> {"raw": str, "status": str}

    Stateless apart from the constructor parameters; instances are
    safe to reuse across sequential calls.
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        llm_invoker: Any,
        log_dir: Path | str | None = None,
        max_retries: int = 3,
        *,
        langfuse_handler: Any = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.llm_invoker = llm_invoker
        self.log_dir = Path(log_dir) if log_dir else None
        self.parser = OutputParser()
        self.parser_v2 = OutputParserV2()
        self.parser_v3 = OutputParserV3()
        self.max_retries = max(1, int(max_retries))
        self.config = config
        if (
            langfuse_handler is not None
            and hasattr(self.llm_invoker, "_langfuse_handler")
        ):
            try:
                self.llm_invoker._langfuse_handler = langfuse_handler
            except Exception:
                logger.debug(
                    "Could not attach langfuse_handler to %s",
                    type(self.llm_invoker).__name__,
                )

    # ── Public API ─────────────────────────────────────────────────────

    def process(self, domain_id: str, state: V2State) -> DomainResult:
        """Run MAP for a single domain and return the result.

        Args:
            domain_id: Domain identifier (e.g. ``"D-04"``).
            state: Pipeline ``V2State`` (must have ``company_context``).

        Returns:
            A :class:`DomainResult`. ``llm_status`` is ``"OK"`` on
            success or ``"FAILED"`` when all retries are exhausted.

        Raises:
            OllamaUnreachable: When the invoker raises (network/Ollama
                down). The orchestrator catches this to abort MAP.
        """
        domain_id = domain_id.upper()

        try:
            inputs = assemble_inputs(state, domain_id)
        except Exception as exc:
            logger.exception("Input assembly failed for %s", domain_id)
            return self._failed_result(domain_id, f"Input assembly: {exc}")

        feedback = ""
        last_raw: str | None = None

        for attempt in range(self.max_retries):
            prompt = render_prompt(inputs, feedback=feedback)

            try:
                response = self.llm_invoker.invoke(
                    prompt, feedback=feedback, config=self.config
                )
            except Exception as exc:
                logger.error("LLM invoke raised for %s: %s", domain_id, exc)
                raise OllamaUnreachable(str(exc)) from exc

            last_raw = response.get("raw") or ""
            status = response.get("status", "FAILED")

            if status != "OK":
                feedback = f"LLM returned status={status}. Try again."
                continue

            # Try V3 first (v1.3 spec is canonical for CORR-022 Phase 3).
            parsed_v3 = self.parser_v3.parse(last_raw)
            if parsed_v3.success:
                self._write_log(
                    domain_id, prompt, last_raw,
                    {"v3_parsed": True, "parsed": parsed_v3},
                    attempt + 1,
                )
                return self._ok_result_v3(domain_id, parsed_v3, inputs)

            # Fallback to V2 (legacy per-sub-domain compat).
            parsed_v2 = self.parser_v2.parse(last_raw)
            if parsed_v2.success:
                self._write_log(
                    domain_id, prompt, last_raw,
                    {"v2_parsed": True, "v3_failed": parsed_v3.error_feedback,
                     "parsed": parsed_v2},
                    attempt + 1,
                )
                return self._ok_result(domain_id, parsed_v2, inputs)

            feedback = parsed_v3.error_feedback or parsed_v2.error_feedback or "Output format invalid."

        # All retries exhausted — log the last attempt and return FAILED.
        try:
            self._write_log(
                domain_id,
                render_prompt(inputs),
                last_raw,
                None,
                self.max_retries,
            )
        except Exception:
            logger.exception("Failed to write exhausted-retry log for %s", domain_id)
        return self._failed_result(
            domain_id, f"Parse failed after {self.max_retries} retries"
        )

    # ── Result builders ────────────────────────────────────────────────

    def _ok_result_v3(
        self,
        domain_id: str,
        parsed: Any,  # ParseResultV3
        inputs: dict[str, Any],
    ) -> DomainResult:
        adapted_subdomains_v3 = [s.as_dict() for s in parsed.subdomains]
        legacy_ao = parsed.legacy_adapted_objective
        return {
            "domain_id": domain_id,
            "domain_name": DOMAIN_NAMES.get(domain_id, domain_id),
            "subdomains": inputs.get("subdomains", []),
            "coverage": _coverage_from_inputs(inputs),
            "cross_regulation": inputs.get("cross_reg_analysis", []),
            "llm_status": "OK",
            "adapted_objective": legacy_ao,
            "adapted_subdomains": [],
            "adapted_subdomains_v3": adapted_subdomains_v3,
            "key_changes": [],
            "applicable_regs": list(inputs.get("applicable_regs", [])),
            "confidence": "UNKNOWN",
        }

    def _ok_result(
        self,
        domain_id: str,
        parsed: Any,  # ParseResultV2
        inputs: dict[str, Any],
    ) -> DomainResult:
        adapted_subdomains = [s.as_dict() for s in parsed.subdomains]
        legacy_ao = parsed.legacy_adapted_objective
        return {
            "domain_id": domain_id,
            "domain_name": DOMAIN_NAMES.get(domain_id, domain_id),
            "subdomains": inputs.get("subdomains", []),
            "coverage": _coverage_from_inputs(inputs),
            "cross_regulation": inputs.get("cross_reg_analysis", []),
            "llm_status": "OK",
            "adapted_objective": legacy_ao,
            "adapted_subdomains": adapted_subdomains,
            "adapted_subdomains_v3": [],
            "key_changes": [],
            "applicable_regs": list(inputs.get("applicable_regs", [])),
            "confidence": "UNKNOWN",  # v1.2 spec doesn't include CONFIDENCE
        }

    def _failed_result(self, domain_id: str, reason: str) -> DomainResult:
        return {
            "domain_id": domain_id,
            "domain_name": DOMAIN_NAMES.get(domain_id, domain_id),
            "subdomains": [],
            "coverage": "NOT_ADDRESSED",
            "cross_regulation": [],
            "llm_status": "FAILED",
            "adapted_objective": "",
            "adapted_subdomains": [],
            "adapted_subdomains_v3": [],
            "key_changes": [],
            "applicable_regs": [],
            "confidence": "LOW",
            "error_reason": reason,
        }

    # ── Logging ────────────────────────────────────────────────────────

    def _write_log(
        self,
        domain_id: str,
        prompt: str,
        raw: str | None,
        parsed: Any,
        attempts: int,
    ) -> None:
        """Append a JSONL entry to ``<log_dir>/<domain_id>.jsonl``."""
        if self.log_dir is None:
            return
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            parsed_dict: dict[str, Any] | None
            v3_parsed = False
            v2_parsed = False
            adapted_subdomains: list[dict[str, Any]] = []
            adapted_subdomains_v3: list[dict[str, Any]] = []
            # Wrapper dict from the retry loop (V3-first): carries v3_parsed/v2_parsed
            if isinstance(parsed, dict) and (
                "v3_parsed" in parsed or "v2_parsed" in parsed
            ):
                v3_parsed = bool(parsed.get("v3_parsed"))
                v2_parsed = bool(parsed.get("v2_parsed"))
                inner = parsed.get("parsed")
                legacy_ao = (
                    getattr(inner, "legacy_adapted_objective", "")
                    if inner is not None else ""
                )
                if v3_parsed and inner is not None and hasattr(inner, "subdomains"):
                    adapted_subdomains_v3 = [
                        s.as_dict() for s in getattr(inner, "subdomains", [])
                    ]
                elif v2_parsed and inner is not None and hasattr(inner, "subdomains"):
                    adapted_subdomains = [
                        s.as_dict() if hasattr(s, "as_dict") else s
                        for s in getattr(inner, "subdomains", [])
                    ]
                parsed_dict = {
                    "parser_version": "v3" if v3_parsed else "v2",
                    "adapted_objective": legacy_ao,
                    "key_adjustments": [],
                    "confidence": "UNKNOWN",
                    "adapted_subdomains": adapted_subdomains,
                    "adapted_subdomains_v3": adapted_subdomains_v3,
                    "v3_failed_feedback": parsed.get("v3_failed", ""),
                }
            elif parsed is None:
                parsed_dict = None
            elif hasattr(parsed, "subdomains") and hasattr(parsed, "blocks"):
                # Direct ParseResultV3 (defensive — call path uses wrapper)
                adapted_subdomains_v3 = [
                    s.as_dict() for s in getattr(parsed, "subdomains", [])
                ]
                parsed_dict = {
                    "parser_version": "v3",
                    "adapted_objective": getattr(parsed, "legacy_adapted_objective", ""),
                    "key_adjustments": [],
                    "confidence": "UNKNOWN",
                    "adapted_subdomains": [],
                    "adapted_subdomains_v3": adapted_subdomains_v3,
                }
                v3_parsed = True
            elif hasattr(parsed, "subdomains"):
                # ParseResultV2: per-sub-domain (hl + directed)
                adapted_subdomains = [
                    s.as_dict() if hasattr(s, "as_dict") else s
                    for s in getattr(parsed, "subdomains", [])
                ]
                parsed_dict = {
                    "parser_version": "v2",
                    "adapted_objective": getattr(parsed, "legacy_adapted_objective", ""),
                    "key_adjustments": [],
                    "confidence": "UNKNOWN",
                    "adapted_subdomains": adapted_subdomains,
                    "adapted_subdomains_v3": [],
                }
                v2_parsed = True
            else:
                # Legacy ParseResult (NamedTuple)
                parsed_dict = {
                    "parser_version": "legacy",
                    "adapted_objective": getattr(parsed, "adapted_objective", ""),
                    "key_adjustments": list(getattr(parsed, "key_adjustments", []) or []),
                    "confidence": getattr(parsed, "confidence", "LOW"),
                }
            entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "domain_id": domain_id,
                "prompt_length": len(prompt),
                "raw_response_preview": (raw or "")[:1000],
                "parsed": parsed_dict,
                "adapted_subdomains": adapted_subdomains,
                "adapted_subdomains_v3": adapted_subdomains_v3,
                "v3_parsed": v3_parsed,
                "v2_parsed": v2_parsed,
                "attempts": attempts,
            }
            log_path = self.log_dir / f"{domain_id}.jsonl"
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write domain log for %s", domain_id)


# ─── Module-level helpers ──────────────────────────────────────────────


def _coverage_from_inputs(inputs: dict[str, Any]) -> str:
    """Map applicable_regs count to a CoverageLevel string."""
    regs = inputs.get("applicable_regs") or []
    if len(regs) >= 2:
        return "SUBSTANTIVE"
    if len(regs) == 1:
        return "PARTIAL"
    return "NOT_ADDRESSED"


__all__ = [
    "DOMAIN_NAMES",
    "DomainProcessor",
    "MapPartialFailure",
    "OllamaUnreachable",
]
