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
from aegis_phase1.v2.domain.parser import OutputParser
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
        self.max_retries = max(1, int(max_retries))
        self.config = config
        if (
            langfuse_handler is not None
            and hasattr(self.llm_invoker, "_langfuse_handler")
        ):
            try:
                self.llm_invoker._langfuse_handler = langfuse_handler
            except Exception:  # noqa: BLE001 — handler attachment is best-effort
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
        except Exception as exc:  # noqa: BLE001 — input assembly is recoverable
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
            except Exception as exc:  # noqa: BLE001 — fatal LLM error
                logger.error("LLM invoke raised for %s: %s", domain_id, exc)
                raise OllamaUnreachable(str(exc)) from exc

            last_raw = response.get("raw") or ""
            status = response.get("status", "FAILED")

            if status != "OK":
                feedback = f"LLM returned status={status}. Try again."
                continue

            parsed = self.parser.parse(last_raw)

            if parsed.success:
                self._write_log(
                    domain_id, prompt, last_raw, parsed, attempt + 1
                )
                return self._ok_result(domain_id, parsed, inputs)

            feedback = parsed.error_feedback or "Output format invalid."

        # All retries exhausted — log the last attempt and return FAILED.
        try:
            self._write_log(
                domain_id,
                render_prompt(inputs),
                last_raw,
                None,
                self.max_retries,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to write exhausted-retry log for %s", domain_id)
        return self._failed_result(
            domain_id, f"Parse failed after {self.max_retries} retries"
        )

    # ── Result builders ────────────────────────────────────────────────

    def _ok_result(
        self,
        domain_id: str,
        parsed: Any,
        inputs: dict[str, Any],
    ) -> DomainResult:
        return {
            "domain_id": domain_id,
            "domain_name": DOMAIN_NAMES.get(domain_id, domain_id),
            "subdomains": inputs.get("subdomains", []),
            "coverage": _coverage_from_inputs(inputs),
            "cross_regulation": inputs.get("cross_reg_analysis", []),
            "llm_status": "OK",
            "adapted_objective": parsed.adapted_objective,
            "key_changes": list(parsed.key_adjustments),
            "applicable_regs": list(inputs.get("applicable_regs", [])),
            "confidence": parsed.confidence,
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
            entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "domain_id": domain_id,
                "prompt_length": len(prompt),
                "raw_response_preview": (raw or "")[:1000],
                "parsed": (
                    {
                        "adapted_objective": parsed.adapted_objective,
                        "key_adjustments": list(parsed.key_adjustments),
                        "confidence": parsed.confidence,
                    }
                    if parsed is not None
                    else None
                ),
                "attempts": attempts,
            }
            log_path = self.log_dir / f"{domain_id}.jsonl"
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001 — logging must never break the pipeline
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