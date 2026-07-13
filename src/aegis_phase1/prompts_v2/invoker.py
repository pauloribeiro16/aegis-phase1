"""Phase1LLMInvoker — single LLM call orchestration with parse retry + validation.

Per implementation contract:
  - Per-regulation:  P1B-LLM-01-INTERPRETATION, P1B-LLM-02-RATIONALE
  - Per-domain lane: P1C-LLM-01-OVERLAP-CLASSIFICATION
  - Global reduce:   P1C-LLM-02-COMPOUND-EVENT, P1C-LLM-03-STRATEGIC-SYNTHESIS

Flow per call:
  1. Load + render prompt (PromptLoader)
  2. Load applicable catalogs (CatalogLoader, optional)
  3. Call LLM (Ollama ChatOllama with format=json_schema)
  4. Robust parse (RobustParser)
  5. Validate (Phase1Validator)
  6. Log result (JSONLLogger)
  7. Retry on parse/schema failure (max_retries, default 2)
"""

from __future__ import annotations

import time
import traceback
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.prompts_v2.llm_inventory import (
    get_invocation_pattern,
    get_stage,
)
from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.logging_helper import JSONLLogger
from aegis_phase1.prompts_v2.robust_parser import RobustParser
from aegis_phase1.prompts_v2.validator import Phase1Validator


class Phase1LLMInvoker:
    """Orchestrates a single Phase 1 LLM call with retry + logging + validation."""

    DEFAULT_MODEL = "gemma4:e2b"
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_TIMEOUT = 180  # 3 min for local inference
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_TEMPERATURE = 0.0

    def __init__(
        self,
        prompt_loader: PromptLoader,
        catalog_loader: CatalogLoader | None = None,
        validator: Phase1Validator | None = None,
        llm_logger: JSONLLogger | None = None,
        format_logger: JSONLLogger | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.prompts = prompt_loader
        self.catalogs = catalog_loader
        self.validator = validator
        self.llm_logger = llm_logger
        self.format_logger = format_logger
        self.model = model or self.DEFAULT_MODEL
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.timeout = timeout or self.DEFAULT_TIMEOUT

    def invoke(
        self,
        spec_id: str,
        inputs: dict[str, Any],
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """Invoke a Phase 1 LLM with full orchestration.

        Args:
            spec_id: Canonical Phase 1 LLM ID (e.g. "P1B-LLM-01-INTERPRETATION")
            inputs: Dict of input data (case_facts, regulation, applicable_regs, etc.)
            max_retries: Override default retry count

        Returns:
            {
              "status": "OK" | "INSUFFICIENT_EVIDENCE" | "INDETERMINATE" | "FAILED_AFTER_RETRIES" | "PYTHON_ERROR",
              "spec_id": str,
              "invocation_pattern": str,
              "parsed_output": dict | None,
              "validation": dict | None,
              "retry_count": int,
              "total_latency_ms": float,
              "all_attempts": [list of attempt dicts],
            }
        """
        max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        invocation_pattern = get_invocation_pattern(spec_id)
        stage = get_stage(spec_id)

        all_attempts: list[dict[str, Any]] = []
        total_start = time.time()

        for attempt in range(1, max_retries + 1):
            attempt_result = self._attempt(
                spec_id=spec_id,
                inputs=inputs,
                invocation_pattern=invocation_pattern,
                stage=stage,
                attempt=attempt,
            )
            all_attempts.append(attempt_result)

            if attempt_result["ok"]:
                return {
                    "status": "OK",
                    "spec_id": spec_id,
                    "invocation_pattern": invocation_pattern,
                    "parsed_output": attempt_result.get("parsed_output"),
                    "validation": attempt_result.get("validation"),
                    "retry_count": attempt,
                    "total_latency_ms": (time.time() - total_start) * 1000,
                    "all_attempts": all_attempts,
                }

        # All retries failed
        final_status = "FAILED_AFTER_RETRIES"
        if all_attempts and any(a.get("parse_status") == "PARSE_ERROR" for a in all_attempts):
            final_status = "PARSE_ERROR"
        elif all_attempts and any(a.get("validation", {}).get("schema_errors") for a in all_attempts):
            final_status = "SCHEMA_ERROR"

        return {
            "status": final_status,
            "spec_id": spec_id,
            "invocation_pattern": invocation_pattern,
            "parsed_output": None,
            "validation": None,
            "retry_count": max_retries,
            "total_latency_ms": (time.time() - total_start) * 1000,
            "all_attempts": all_attempts,
        }

    def _attempt(
        self,
        spec_id: str,
        inputs: dict[str, Any],
        invocation_pattern: str,
        stage: str,
        attempt: int,
    ) -> dict[str, Any]:
        """Single attempt at invoking the LLM."""
        try:
            # 1. Load + render prompt
            prompt = self.prompts.render(spec_id, inputs)
            schema = self.prompts.load(spec_id).get("schema") or {}

            # 2. Build Ollama client with optional format constraint
            llm_kwargs: dict[str, Any] = {
                "model": self.model,
                "base_url": self.base_url,
                "temperature": self.DEFAULT_TEMPERATURE,
            }
            if schema:
                llm_kwargs["format"] = schema  # Ollama accepts dict for JSON Schema
            llm = ChatOllama(**llm_kwargs)

            # 3. Call LLM
            start = time.time()
            try:
                response = llm.invoke(
                    [
                        SystemMessage(content=prompt["system"]),
                        HumanMessage(content=prompt["user"]),
                    ]
                )
                latency_ms = (time.time() - start) * 1000
                raw = response.content if hasattr(response, "content") else str(response)
            except Exception as e:
                # LLM call failed (timeout, connection, etc.)
                latency_ms = (time.time() - start) * 1000
                error_event = {
                    "event": "python_error",
                    "level": "ERROR",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "spec_id": spec_id,
                    "invocation_pattern": invocation_pattern,
                    "stage": stage,
                    "attempt": attempt,
                    "error": str(e),
                    "traceback": traceback.format_exc()[:1000],
                    "latency_ms": latency_ms,
                }
                if self.llm_logger:
                    self.llm_logger.log(error_event)
                return {
                    "ok": False,
                    "parse_status": "PYTHON_ERROR",
                    "error": str(e),
                    "latency_ms": latency_ms,
                    "validation": None,
                    "parsed_output": None,
                }

            # 4. Robust parse
            parse_result = RobustParser.parse(raw)

            if not parse_result.ok:
                # Log format error
                if self.format_logger:
                    self.format_logger.log({
                        "event": "format_error",
                        "level": "ERROR",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "spec_id": spec_id,
                        "stage": stage,
                        "attempt": attempt,
                        "model": self.model,
                        "raw_response": raw,
                        "raw_response_length": len(raw),
                        "parse_attempts": parse_result.attempts,
                        "final_error": parse_result.error,
                    })
                return {
                    "ok": False,
                    "parse_status": "PARSE_ERROR",
                    "error": parse_result.error,
                    "raw_response": raw,
                    "latency_ms": latency_ms,
                    "validation": None,
                    "parsed_output": None,
                }

            # 5. Validate
            output = parse_result.json
            # Ensure dict
            if not isinstance(output, dict):
                # If LLM returned an array, wrap it (e.g. for events)
                output = {"items": output}

            validation_result: dict[str, Any] = {"valid": True, "warnings": []}
            if self.validator:
                validation_result = self.validator.validate(spec_id, output, inputs)

            # Token usage (best-effort; Ollama may not always expose it)
            usage = self._extract_usage(response)

            # 6. Log call
            status = "OK" if validation_result["valid"] else "SCHEMA_ERROR"
            call_event = {
                "event": "llm_call",
                "level": "INFO" if validation_result["valid"] else "WARNING",
                "timestamp": datetime.now(UTC).isoformat(),
                "prompt_spec_id": spec_id,
                "invocation_pattern": invocation_pattern,
                "stage": stage,
                "model": self.model,
                "attempt": attempt,
                "request": {
                    "system_prompt_length": len(prompt["system"]),
                    "user_prompt_length": len(prompt["user"]),
                    "temperature": self.DEFAULT_TEMPERATURE,
                    "json_schema_provided": bool(schema),
                },
                "response": {
                    "raw_content": raw,
                    "parsed_json": output,
                    "parse_strategy": parse_result.strategy,
                    "parse_error": None,
                    "latency_ms": latency_ms,
                    "usage": usage,
                },
                "validation": validation_result,
                "status": status,
            }
            if self.llm_logger:
                self.llm_logger.log(call_event)

            return {
                "ok": validation_result["valid"],
                "parse_status": "PARSED",
                "parsed_output": output,
                "validation": validation_result,
                "latency_ms": latency_ms,
                "usage": usage,
            }

        except Exception as e:
            # Catastrophic failure (e.g. PromptLoader error)
            error_event = {
                "event": "python_error",
                "level": "ERROR",
                "timestamp": datetime.now(UTC).isoformat(),
                "spec_id": spec_id,
                "invocation_pattern": invocation_pattern,
                "stage": stage,
                "attempt": attempt,
                "error": str(e),
                "traceback": traceback.format_exc()[:1000],
            }
            if self.llm_logger:
                self.llm_logger.log(error_event)
            return {
                "ok": False,
                "parse_status": "PYTHON_ERROR",
                "error": str(e),
                "validation": None,
                "parsed_output": None,
            }

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, Any]:
        """Best-effort extraction of token usage from LangChain response."""
        usage: dict[str, Any] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            if hasattr(response, "response_metadata"):
                meta = response.response_metadata
                if isinstance(meta, dict):
                    tu = meta.get("token_usage", {}) or meta.get("usage", {})
                    if isinstance(tu, dict):
                        usage["prompt_tokens"] = tu.get("prompt_tokens", tu.get("input_tokens", 0))
                        usage["completion_tokens"] = tu.get(
                            "completion_tokens", tu.get("output_tokens", 0)
                        )
                        usage["total_tokens"] = tu.get("total_tokens", 0)
            if hasattr(response, "usage_metadata"):
                meta = response.usage_metadata
                if meta is not None and hasattr(meta, "input_tokens"):
                    usage["prompt_tokens"] = getattr(meta, "input_tokens", 0) or 0
                    usage["completion_tokens"] = getattr(meta, "output_tokens", 0) or 0
                    usage["total_tokens"] = getattr(meta, "total_tokens", 0) or 0
        except Exception:
            pass
        return usage
