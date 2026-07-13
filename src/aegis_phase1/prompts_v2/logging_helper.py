"""Structured JSONL logger for Phase 1 LLM calls + parse failures + errors.

Outputs:
  - logs/phase1/llm-calls.jsonl         (one line per LLM call, full I/O)
  - logs/phase1/format-errors.jsonl    (one line per parse failure)
  - logs/phase1/errors.log              (Python exceptions, plain text)
  - logs/phase1/performance.csv         (latency + token metrics)

Also emits a concise human-readable summary to stdout (via Python logging).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOGGER_NAME = "phase1"
_STDOUT_LOGGER_NAME = "phase1.stdout"


class JSONLLogger:
    """JSONL logger that appends one event per line + mirrors summary to stdout.

    Thread-unsafe by default (single-threaded Phase 1 executor is OK).
    """

    def __init__(
        self,
        filepath: Path,
        name: str = _LOGGER_NAME,
        also_stdout: bool = True,
    ) -> None:
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.also_stdout = also_stdout

        if also_stdout:
            self._stdout_logger = logging.getLogger(f"{_STDOUT_LOGGER_NAME}.{name}")
            if not self._stdout_logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(
                    logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
                )
                self._stdout_logger.addHandler(handler)
                self._stdout_logger.setLevel(logging.INFO)

    def log(self, event: dict[str, Any]) -> None:
        """Append one event to JSONL file (and emit summary to stdout)."""
        # Add timestamp if not present
        if "timestamp" not in event:
            event = {**event, "timestamp": datetime.now(UTC).isoformat()}
        if "level" not in event:
            event = {**event, "level": "INFO"}

        # Write JSONL (one line per event)
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            # Fallback: write to stderr if file write fails
            print(f"[JSONLLogger] Failed to write to {self.filepath}: {e}", file=__import__("sys").stderr)

        # Stdout summary
        if self.also_stdout:
            self._emit_stdout(event)

    def _emit_stdout(self, event: dict[str, Any]) -> None:
        level = event.get("level", "INFO")
        evt = event.get("event", "?")
        spec = event.get("prompt_spec_id", "")
        if evt == "llm_call":
            status = event.get("status", "?")
            elapsed = event.get("response", {}).get("latency_ms", 0)
            tokens = event.get("response", {}).get("usage", {})
            tot = tokens.get("total_tokens", 0) if isinstance(tokens, dict) else 0
            self._stdout_logger.info(
                f"[{level}] LLM_CALL {spec} → {status} ({elapsed:.0f}ms, {tot} tok)"
            )
            # Surface schema errors
            val = event.get("validation", {})
            for err in val.get("schema_errors", []) or []:
                self._stdout_logger.error(f"  schema: {err}")
            for err in val.get("citation_errors", []) or []:
                self._stdout_logger.error(f"  citation: {err}")
            # Surface parse error
            parse_err = event.get("response", {}).get("parse_error")
            if parse_err:
                self._stdout_logger.error(f"  parse: {parse_err}")
        elif evt == "format_error":
            raw_len = len(str(event.get("raw_response", "")))
            self._stdout_logger.error(
                f"[{level}] FORMAT_ERROR {spec} (raw_len={raw_len})"
            )
            for attempt in event.get("parse_attempts", []):
                err = attempt.get("error", "?")
                self._stdout_logger.error(f"  attempt {attempt.get('strategy', '?')}: {err}")
        elif evt == "python_error":
            self._stdout_logger.error(
                f"[{level}] PYTHON_ERROR {spec or '?'}: {event.get('error', '?')[:200]}"
            )
        else:
            # Generic event
            self._stdout_logger.info(f"[{level}] {evt}: {json.dumps(event)[:200]}")
