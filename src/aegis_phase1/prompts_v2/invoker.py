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

import json
import logging
import os
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_ollama import ChatOllama

from aegis_phase1.config.defaults import RAW_OUTPUT_DIR
from aegis_phase1.llm.token_counter import TokenCounter
from aegis_phase1.llm.unified import LLMUnreachableError, probe_ollama
from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.prompts_v2.llm_inventory import (
    get_invocation_pattern,
    get_stage,
)
from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.logging_helper import JSONLLogger
from aegis_phase1.prompts_v2.robust_parser import RobustParser
from aegis_phase1.prompts_v2.validator import Phase1Validator
from aegis_phase1.validator import ContentValidator

# CORR-048: module-level logger. Required for the prompt truncation
# warning (line ~250) and any other logger calls in this file.
logger = logging.getLogger(__name__)


# CORR-102: two-tier token cap.
#
# - BASE_PROMPT_TOKENS is the standard budget for all models. It is the
#   default cap when a model has no entry in MODEL_TOKEN_CAPS.
# - MAX_PROMPT_TOKENS is the absolute ceiling — no prompt may ever
#   exceed this, regardless of model.
#
# The effective cap for a model is min(BASE, MODEL_TOKEN_CAPS[model],
# MAX). Smaller-context models (e.g. gemma4:e4b with 8K native window)
# are capped at their native limit; larger-context models (e.g.
# MiniMax-M3 with native 200K) are capped at BASE for safety.
#
# Hard fail (raise PromptTooLargeError) if exceeded. Replaces the
# legacy CORR-049 byte-based silent truncation at 512KB — silent
# truncation was hiding contract violations and degrading model
# output. The new policy is fail-loud so the caller can fix the
# prompt budget before retrying.
BASE_PROMPT_TOKENS = 100000  # standard base cap for all models
MAX_PROMPT_TOKENS = 124000  # absolute ceiling (cannot be exceeded)

# Per-model cap. All models default to BASE_PROMPT_TOKENS (100K).
# MiniMax-M3 / M2.7 / M2.7-highspeed can do 200K natively but are
# aligned with the standard BASE for safety. Native limits below
# BASE (e.g. gemma4:e4b's 8K server-side window) are NOT modelled
# here — Ollama handles its own server-side truncation; our cap is
# a budgeting guard, not a server limit.
MODEL_TOKEN_CAPS: dict[str, int] = {
    "gemma4:e4b": BASE_PROMPT_TOKENS,
    "llama3.1:8b": BASE_PROMPT_TOKENS,
    "MiniMax-M3": BASE_PROMPT_TOKENS,
    "MiniMax-M2.7": BASE_PROMPT_TOKENS,
    "MiniMax-M2.7-highspeed": BASE_PROMPT_TOKENS,
}


def _effective_token_cap(model: str) -> int:
    """Return the effective token cap for ``model``.

    Falls back to :data:`BASE_PROMPT_TOKENS` when the model is not in
    :data:`MODEL_TOKEN_CAPS` (defensive default for newly added
    models). The result is always ``<= MAX_PROMPT_TOKENS``.
    """
    per_model_cap = MODEL_TOKEN_CAPS.get(model, BASE_PROMPT_TOKENS)
    return min(per_model_cap, MAX_PROMPT_TOKENS)


class PromptTooLargeError(RuntimeError):
    """Raised when a rendered prompt exceeds the model's effective token cap.

    Replaces the legacy CORR-049 byte-based silent truncation. The
    orchestrator / runner / invoker must propagate this exception
    upward; never silently truncate to fit the cap.

    Attributes:
        spec_id: The canonical spec ID (e.g. ``P1B-LLM-01-INTERPRETATION``).
        model: The model tag (e.g. ``gemma4:e4b``).
        sys_tokens: Token estimate of the system prompt.
        user_tokens: Token estimate of the user prompt.
        cap: The effective cap (the smaller of ``MAX_PROMPT_TOKENS``
            and the model's native cap).
    """

    def __init__(
        self,
        spec_id: str,
        model: str,
        sys_tokens: int,
        user_tokens: int,
        cap: int,
    ) -> None:
        self.spec_id = spec_id
        self.model = model
        self.sys_tokens = sys_tokens
        self.user_tokens = user_tokens
        self.cap = cap
        super().__init__(
            f"CORR-102: prompt too large for {model} "
            f"(sys={sys_tokens} + user={user_tokens} = "
            f"{sys_tokens + user_tokens} tokens > cap={cap}). "
            f"spec_id={spec_id}. Refusing to send to LLM."
        )


# CORR-042-T3: Specs that require deterministic catalogs.
# These specs reference tipo2 / tipo3 / scope_overlap / event_templates
# YAML content during prompt rendering. If self.catalogs is None, the
# LLM prompt is incomplete and the call would fail silently (returning
# INSUFFICIENT_EVIDENCE or empty parsed_output). The guard below makes
# the failure explicit at construction-or-invocation time.
_CATALOG_REQUIRED_SPECS: frozenset[str] = frozenset(
    {
        "P1B-LLM-01-INTERPRETATION",  # tipo2 + tipo3
        "P1B-LLM-02-RATIONALE",  # inherits tipo2/tipo3 from 01
        "P1C-LLM-01-OVERLAP-CLASSIFICATION",  # scope_overlap_predicates
        "P1C-LLM-02-COMPOUND-EVENT",  # event_templates
        # P1C-LLM-03-STRATEGIC-SYNTHESIS does NOT require catalogs
        # (consumes doc07b as constraint, no tipo2/tipo3/event lookup).
    }
)


class Phase1LLMInvoker:
    """Orchestrates a single Phase 1 LLM call with retry + logging + validation."""

    DEFAULT_MODEL = "gemma4:e4b"  # CORR-056 (2026-07-23): switched from gemma4:e2b
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_TIMEOUT = 180  # 3 min for local inference
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_TEMPERATURE = 0.0

    def __init__(
        self,
        prompt_loader: PromptLoader,
        catalog_loader: CatalogLoader | None = None,
        validator: Phase1Validator | ContentValidator | None = None,
        llm_logger: JSONLLogger | None = None,
        format_logger: JSONLLogger | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        langfuse_handler: Any | None = None,
        provider: str = "ollama",  # CORR-062 S2: "ollama" | "minimax"
    ) -> None:
        self.prompts = prompt_loader
        self.catalogs = catalog_loader
        # CORR-061 S2: default to ContentValidator (markdown-only
        # content-length check) instead of None. Callers can still
        # pass Phase1Validator explicitly for strict JSON-Schema
        # validation (legacy path; the source lives in
        # _archive/corr061/validator.py).
        self.validator = validator if validator is not None else ContentValidator()
        self.llm_logger = llm_logger
        self.format_logger = format_logger
        self.model = model or self.DEFAULT_MODEL
        # CORR-062 S2: when provider=minimax, use the Mavis gateway
        # base URL (M3 Token Plan endpoint), not Ollama's localhost.
        if base_url:
            self.base_url = base_url
        elif provider == "minimax":
            from aegis_phase1.llm.chat_minimax import DEFAULT_BASE_URL as _MINIMAX_URL

            self.base_url = _MINIMAX_URL
        else:
            self.base_url = self.DEFAULT_BASE_URL
        self.provider = provider
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._langfuse_handler = langfuse_handler

    def _load_catalogs_for(self, prompt_spec_id: str) -> dict[str, list[dict[str, Any]]]:
        """CORR-042-T3: guard for catalog-dependent Phase 1 LLMs.

        Returns the catalog content for ``prompt_spec_id`` if it is in
        ``_CATALOG_REQUIRED_SPECS``. Raises ``RuntimeError`` with a
        helpful message if ``self.catalogs`` is None — preventing the
        silent-smoking-gun regression of LLM calls being made with
        empty catalog context.

        For specs not in the set (e.g. P1C-LLM-03), returns an empty
        dict and does NOT touch ``self.catalogs`` (which may be None).

        Catalog names loaded per spec (matches PROMPTS/P1?-LLM-*.md
        references and the catalog content of
        ``00_METHODOLOGY/PROMPTS/catalogs/``):
          - P1B-LLM-01: tipo2_interpretations, tipo3_derogations
          - P1B-LLM-02: tipo2, tipo3 (consumes LLM-01's filtered output too)
          - P1C-LLM-01: scope_overlap_predicates
          - P1C-LLM-02: event_templates
          - P1C-LLM-03: (none)
        """
        if prompt_spec_id not in _CATALOG_REQUIRED_SPECS:
            return {}
        if self.catalogs is None:
            raise RuntimeError(
                f"catalog_loader is None but prompt {prompt_spec_id} requires "
                f"deterministic catalogs (tipo2/tipo3/scope_overlap/event_templates). "
                f"Wire a CatalogLoader at Phase1LLMInvoker construction time. "
                f"(CORR-042 anti-regression guard; original smoking gun was "
                f"v2/orchestrator.py never passing catalog_loader — see CORR-039-T1.)"
            )
        out: dict[str, list[dict[str, Any]]] = {}
        try:
            if (
                prompt_spec_id == "P1B-LLM-01-INTERPRETATION"
                or prompt_spec_id == "P1B-LLM-02-RATIONALE"
            ):
                out["tipo2"] = self.catalogs.load("tipo2_interpretations")
                out["tipo3"] = self.catalogs.load("tipo3_derogations")
            elif prompt_spec_id == "P1C-LLM-01-OVERLAP-CLASSIFICATION":
                out["scope_overlap_predicates"] = self.catalogs.load("scope_overlap_predicates")
            elif prompt_spec_id == "P1C-LLM-02-COMPOUND-EVENT":
                out["event_templates"] = self.catalogs.load("event_templates")
        except Exception as e:
            logger.warning(
                "Catalog load failed for %s: %s — proceeding with empty content",
                prompt_spec_id,
                e,
            )
            out = {}
        return out

    def invoke(
        self,
        spec_id: str,
        inputs: dict[str, Any],
        max_retries: int | None = None,
        config: RunnableConfig | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke a Phase 1 LLM with full orchestration.

        Args:
            spec_id: Canonical Phase 1 LLM ID (e.g. "P1B-LLM-01-INTERPRETATION")
            inputs: Dict of input data (case_facts, regulation, applicable_regs, etc.)
            max_retries: Override default retry count
            config: Optional LangChain RunnableConfig (callbacks, run_name, etc.)
            state: Optional pipeline state. When provided, the raw markdown
                response of each successful attempt is appended to
                ``state["per_spec_markdown"][spec_id]`` (CORR-061 S3b). For
                multi-call specs (P1B-LLM-01/02 are called per regulation;
                P1C-LLM-01 is called per domain) the per-call raw responses
                are concatenated with a ``\\n\\n---\\n\\n`` separator so the
                downstream doc renderers see the full spec output in a
                single string. Pass ``None`` (default) to disable capture
                (e.g. in tests that don't have an orchestrator state).

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

        # CORR-042-T3: guard against missing catalog_loader for the
        # 4 catalog-dependent specs. Raises RuntimeError if a catalog
        # is required but not wired. No-op for P1C-LLM-03.
        try:
            catalog_inputs = self._load_catalogs_for(spec_id)
            # CORR-045: merge catalogs into inputs BEFORE render so the
            # prompt template substitution can interpolate them.
            # Without this merge, the prompt never sees
            # scope_overlap_predicates / tipo2 / event_templates even
            # though _load_catalogs_for loaded them successfully.
            # Order: inputs on top of catalog_inputs so callers can
            # override (rare); catalog keys are the new ones.
            if catalog_inputs:
                inputs = {**catalog_inputs, **inputs}
        except RuntimeError:
            # Re-raise — this is a configuration error, not a recoverable one.
            raise

        if config is None:
            config = {}
        # CORR-048: idempotent attach of Langfuse callback. We attach our
        # stored handler (if any) but only if not already present in
        # ``config["callbacks"]`` — prevents double-attach on retry.
        # CORR-062 S1 v5 fix: ``config["callbacks"]`` may be a list (legacy
        # call sites, tests) OR a ``BaseCallbackManager`` (LangChain
        # ``RunnableConfig`` set by ``with_config()`` / ``bind()`` in graph
        # executor paths — see ``phase1_executor.py:run``). The previous
        # ``list(config.get("callbacks") or [])`` raised
        # ``TypeError: 'CallbackManager' object is not iterable`` on the
        # v4 run when called from the LangGraph path. Defensive read:
        if self._langfuse_handler is not None:
            _cbs = config.get("callbacks")
            if _cbs is None:
                _existing: list = []
            elif isinstance(_cbs, list):
                _existing = list(_cbs)
            elif hasattr(_cbs, "handlers"):
                # BaseCallbackManager — combine regular + inheritable handlers
                _existing = list(getattr(_cbs, "handlers", []) or []) + list(
                    getattr(_cbs, "inheritable_handlers", []) or []
                )
            else:
                # Unknown container type — best-effort iterate
                try:
                    _existing = list(_cbs)
                except TypeError:
                    _existing = []
            if self._langfuse_handler not in _existing:
                _existing.append(self._langfuse_handler)
            config = {**config, "callbacks": _existing}

        # CORR-064 fix: Ollama probe only meaningful for the Ollama
        # provider. Calling it on the MiniMax gateway URL would 404
        # at /api/tags and raise a spurious LLMUnreachableError.
        if self.provider == "ollama" and not probe_ollama(base_url=self.base_url):
            raise LLMUnreachableError(self.base_url, "Phase1LLMInvoker.invoke")

        all_attempts: list[dict[str, Any]] = []
        total_start = time.time()

        for attempt in range(1, max_retries + 1):
            attempt_result = self._attempt(
                spec_id=spec_id,
                inputs=inputs,
                invocation_pattern=invocation_pattern,
                stage=stage,
                attempt=attempt,
                config=config,
            )
            all_attempts.append(attempt_result)

            if attempt_result["ok"]:
                # CORR-061 S3b: capture the raw markdown response to
                # ``state["per_spec_markdown"][spec_id]`` so the doc
                # renderers can consume it directly instead of the
                # legacy typed dicts. Only fires when the caller
                # passes ``state`` (test paths pass None).
                if state is not None:
                    self._capture_per_spec_markdown(
                        state,
                        spec_id,
                        attempt_result,
                    )
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
        elif all_attempts and any(
            (a.get("validation") or {}).get("schema_errors") for a in all_attempts
        ):
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
        config: RunnableConfig | None = None,
    ) -> dict[str, Any]:
        """Single attempt at invoking the LLM.

        Raises:
            PromptTooLargeError: CORR-102 hard cap. Raised when the
                rendered prompt exceeds ``_effective_token_cap(self.model)``.
                Replaces the legacy CORR-049 byte-based silent
                truncation. Callers must propagate this upward.
        """
        try:
            # 1. Load + render prompt
            prompt = self.prompts.render(spec_id, inputs)
            # CORR-102: token-based hard cap (replaces the CORR-049
            # byte-based silent truncation at 512KB). If the prompt
            # exceeds the effective token cap for the model, raise
            # PromptTooLargeError — do NOT silently truncate. The
            # caller must fix the prompt budget.
            sys_t, user_t, total_t = TokenCounter.count_pair(
                prompt["system"],
                prompt["user"],
            )
            effective_cap = _effective_token_cap(self.model)
            if total_t > effective_cap:
                logger.error(
                    "CORR-102: prompt exceeds token cap "
                    "(sys=%d + user=%d = %d tokens > cap=%d, model=%s, spec=%s)",
                    sys_t,
                    user_t,
                    total_t,
                    effective_cap,
                    self.model,
                    spec_id,
                )
                raise PromptTooLargeError(
                    spec_id=spec_id,
                    model=self.model,
                    sys_tokens=sys_t,
                    user_tokens=user_t,
                    cap=effective_cap,
                )
            # Visibility log: byte sizes for backward-compat tooling
            # that greps for prompt sizes. DEBUG-level — not a
            # truncation event anymore.
            logger.debug(
                "CORR-102: prompt within budget "
                "(sys=%d + user=%d = %d tokens, cap=%d, model=%s, spec=%s)",
                sys_t,
                user_t,
                total_t,
                effective_cap,
                self.model,
                spec_id,
            )
            schema = self.prompts.load(spec_id).get("schema") or {}

            # 2. Build the chat client. CORR-062 S2: provider-aware —
            #    provider="minimax" → ChatMinimax (M3/M2.7 via Mavis
            #    gateway); otherwise ChatOllama (legacy local path).
            from aegis_phase1.prompts_v2.markdown_parser import MARKDOWN_PARSERS

            llm_kwargs: dict[str, Any] = {
                "model": self.model,
                "base_url": self.base_url,
                "temperature": self.DEFAULT_TEMPERATURE,
            }
            # CORR-050: do NOT pass format=schema for specs with a
            # MarkdownParser. The model is instructed (in the prompt)
            # to emit markdown; constraining it with JSON Schema fights
            # the instruction. Legacy specs (no parser) keep format=.
            if schema and spec_id not in MARKDOWN_PARSERS:
                llm_kwargs["format"] = schema
            if self.provider == "minimax":
                # ChatMinimax has its own DEFAULT_BASE_URL; don't pass
                # base_url= here (we already set self.base_url to the
                # gateway URL in __init__, which ChatMinimax will pick
                # up via the constructor below).
                from aegis_phase1.llm.chat_minimax import ChatMinimax

                llm = ChatMinimax(
                    model=self.model,
                    base_url=self.base_url,
                )
            elif self.provider == "vllm":
                # CORR-110: OpenAI-compatible HTTP backend. ChatOpenAICompat
                # reads AEGIS_VLLM_BASE_URL / AEGIS_VLLM_API_KEY /
                # AEGIS_VLLM_TIMEOUT from env inside its model_validator;
                # we pass the values already resolved on self so ctor args
                # win (avoids surprises if the env drifted since the
                # UnifiedInvoker was built).
                from aegis_phase1.llm.openai_compat import ChatOpenAICompat

                llm = ChatOpenAICompat(
                    model=self.model,
                    base_url=self.base_url,
                )
            else:
                llm = ChatOllama(**llm_kwargs)

            # 3. Call LLM
            start = time.time()
            try:
                invoke_kwargs: dict[str, Any] = {}
                if config is not None:
                    invoke_kwargs["config"] = config
                response = llm.invoke(
                    [
                        SystemMessage(content=prompt["system"]),
                        HumanMessage(content=prompt["user"]),
                    ],
                    **invoke_kwargs,
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
                    # CORR-054: log the full prompts so the user can
                    # inspect what was actually sent to the model when
                    # the call fails. This was previously impossible —
                    # only the lengths were recorded. Full content is
                    # preserved verbatim (no truncation, no sampling) —
                    # if the model failed to receive it, the user must
                    # see exactly what was attempted.
                    "request": {
                        "system_prompt": prompt["system"],
                        "user_prompt": prompt["user"],
                        "system_prompt_length": len(prompt["system"]),
                        "user_prompt_length": len(prompt["user"]),
                    },
                }
                if self.llm_logger:
                    self.llm_logger.log(error_event)
                # CORR-061 S4: capture every attempt to disk, even on
                # connection / timeout failures. The raw response is
                # empty here — that itself is signal.
                self._persist_raw_call(
                    spec_id=spec_id,
                    attempt=attempt,
                    prompt_system=prompt["system"],
                    prompt_user=prompt["user"],
                    raw_response="",
                    status="PYTHON_ERROR",
                    latency_ms=latency_ms,
                    model=self.model,
                    error=str(e),
                )
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
                    self.format_logger.log(
                        {
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
                            # CORR-054: include the prompts that were sent
                            # so the user can correlate the parse failure
                            # with the exact request the model saw.
                            "request": {
                                "system_prompt": prompt["system"],
                                "user_prompt": prompt["user"],
                                "system_prompt_length": len(prompt["system"]),
                                "user_prompt_length": len(prompt["user"]),
                            },
                        }
                    )
                # CORR-061 S4: capture every attempt — the raw
                # response landed but failed to parse; we still want
                # it on disk so reviewers can see what the model said.
                self._persist_raw_call(
                    spec_id=spec_id,
                    attempt=attempt,
                    prompt_system=prompt["system"],
                    prompt_user=prompt["user"],
                    raw_response=raw,
                    status="PARSE_ERROR",
                    latency_ms=latency_ms,
                    model=self.model,
                    error=parse_result.error,
                )
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
            # CORR-050: markdown+regex parsing path for LLMs with a
            # registered MarkdownParser. JSON Schema validator
            # (Phase1Validator) is bypassed for these specs — Pydantic
            # models are the new source of truth. Legacy JSON Schema
            # path kept for the other 4 LLMs (until CORR-051).
            from aegis_phase1.prompts_v2.markdown_parser import MARKDOWN_PARSERS

            output = parse_result.json
            parser_cls = MARKDOWN_PARSERS.get(spec_id)
            if parser_cls is not None:
                # markdown+regex path: parse the raw text directly
                # (the JSON wrapper from RobustParser is discarded).
                parser = parser_cls()
                parsed_model, error_feedback = parser.parse(raw)
                if parsed_model is None:
                    # CORR-053: log raw + error_feedback so debugging
                    # markdown+regex failures is possible. Previously
                    # the path was silent and only logged SCHEMA_ERROR
                    # with no detail. Use format_logger if available
                    # (similar to RobustParser path above).
                    if self.format_logger:
                        self.format_logger.log(
                            {
                                "event": "markdown_parse_error",
                                "level": "ERROR",
                                "timestamp": datetime.now(UTC).isoformat(),
                                "spec_id": spec_id,
                                "stage": stage,
                                "attempt": attempt,
                                "model": self.model,
                                "raw_response": raw,
                                "raw_response_length": len(raw),
                                "error_feedback": error_feedback,
                                # CORR-054: include the prompts that were
                                # sent so the user can correlate the
                                # markdown parse failure with the exact
                                # request the model saw.
                                "request": {
                                    "system_prompt": prompt["system"],
                                    "user_prompt": prompt["user"],
                                    "system_prompt_length": len(prompt["system"]),
                                    "user_prompt_length": len(prompt["user"]),
                                },
                            }
                        )
                    validation_result = {
                        "valid": False,
                        "errors": [error_feedback],
                        "warnings": [],
                    }
                    output = None
                else:
                    # CORR-050: inject deterministic envelope fields.
                    # These are NEVER emitted by the LLM; the invoker
                    # is the single source of truth.
                    parsed_model.case_id = inputs.get("case_id", "")
                    parsed_model.prompt_spec_id = spec_id
                    parsed_model.schema_version = "1.0.0"
                    parsed_model.invocation_pattern = invocation_pattern
                    output = parsed_model.model_dump()
                    validation_result = {"valid": True, "warnings": []}
            else:
                # Legacy JSON Schema path (CORR-051 will convert)
                if not isinstance(output, dict):
                    # If LLM returned an array, wrap it (e.g. for events)
                    output = {"items": output}
                validation_result = {"valid": True, "warnings": []}
                if self.validator:
                    if isinstance(self.validator, ContentValidator):
                        # CORR-061 S2: markdown-only path.
                        # ContentValidator checks raw text length,
                        # not JSON Schema. Convert its dataclass
                        # result to the dict shape the rest of
                        # this method expects.
                        case_id = (inputs or {}).get("case_id") if inputs else None
                        _cv = self.validator.validate(
                            raw,
                            spec_id=spec_id,
                            case_id=case_id,
                        )
                        validation_result = {
                            "valid": _cv.status == "OK",
                            "errors": list(_cv.errors),
                            "warnings": list(_cv.warnings),
                        }
                    else:
                        # Legacy JSON Schema path (Phase1Validator)
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
                    # CORR-054: log the full prompts (system + user)
                    # so the user can see exactly what was sent to
                    # the model — not just the lengths. The lengths
                    # are kept for backward-compat (existing tooling
                    # that greps for them).
                    "system_prompt": prompt["system"],
                    "user_prompt": prompt["user"],
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

            # CORR-061 S4: persist every attempt — success (status=OK)
            # and validation failure (status=SCHEMA_ERROR) both go to
            # disk so reviewers can audit what the model produced.
            self._persist_raw_call(
                spec_id=spec_id,
                attempt=attempt,
                prompt_system=prompt["system"],
                prompt_user=prompt["user"],
                raw_response=raw,
                status=status,
                latency_ms=latency_ms,
                model=self.model,
                error=None
                if validation_result["valid"]
                else str(validation_result.get("errors") or "validation failed"),
            )

            return {
                "ok": validation_result["valid"],
                "parse_status": "PARSED",
                "parsed_output": output,
                "validation": validation_result,
                "latency_ms": latency_ms,
                "usage": usage,
                # CORR-061 S3b: thread the raw markdown response back
                # to ``invoke()`` so it can be captured into
                # ``state["per_spec_markdown"][spec_id]``. Was previously
                # not returned — only the parsed structured output was.
                "raw_response": raw,
            }

        except PromptTooLargeError:
            # CORR-102: re-raise the hard cap failure without
            # converting it into a PYTHON_ERROR return value. The
            # orchestrator / runner / caller must propagate this
            # exception upward; never silently swallow.
            raise
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
                # CORR-054: log the full prompts even on catastrophic
                # failure (e.g. PromptLoader error). If the render
                # itself blew up, fall back to an empty placeholder so
                # the event is still well-formed.
                "request": {
                    "system_prompt": (prompt.get("system", "") if isinstance(prompt, dict) else ""),
                    "user_prompt": (prompt.get("user", "") if isinstance(prompt, dict) else ""),
                    "system_prompt_length": (
                        len(prompt.get("system", "")) if isinstance(prompt, dict) else 0
                    ),
                    "user_prompt_length": (
                        len(prompt.get("user", "")) if isinstance(prompt, dict) else 0
                    ),
                },
            }
            if self.llm_logger:
                self.llm_logger.log(error_event)
            # CORR-061 S4: capture even catastrophic failures. If
            # ``prompt`` was never bound (render itself blew up) we
            # write empty placeholders so the file is well-formed.
            self._persist_raw_call(
                spec_id=spec_id,
                attempt=attempt,
                prompt_system=(prompt.get("system", "") if isinstance(prompt, dict) else ""),
                prompt_user=(prompt.get("user", "") if isinstance(prompt, dict) else ""),
                raw_response="",
                status="PYTHON_ERROR",
                latency_ms=0.0,
                model=self.model,
                error=str(e),
            )
            return {
                "ok": False,
                "parse_status": "PYTHON_ERROR",
                "error": str(e),
                "validation": None,
                "parsed_output": None,
            }

    @staticmethod
    def _capture_per_spec_markdown(
        state: dict[str, Any],
        spec_id: str,
        attempt_result: dict[str, Any],
    ) -> None:
        """CORR-061 S3b: append the successful attempt's raw markdown to ``state``.

        Writes to ``state["per_spec_markdown"][spec_id]``. The
        ``per_spec_markdown`` dict is initialised at orchestrator-load time
        (see ``Phase1Orchestrator._init_state``) as a
        ``dict[spec_id, str]`` so a missing key here means the state
        was not initialised — we initialise it lazily and log a warning.

        For specs invoked multiple times (P1B-LLM-01/02 per regulation,
        P1C-LLM-01 per domain), each successful call appends its raw
        response with a markdown horizontal-rule separator
        (``\\n\\n---\\n\\n``) so the renderer sees the full spec output
        in a single string. The first call's response is stored verbatim
        (no leading separator).

        Args:
            state: Pipeline state (mutated in place).
            spec_id: Canonical Phase 1 LLM ID.
            attempt_result: The successful attempt's return value
                (carries ``raw_response``; threaded through from
                :meth:`_attempt` since S3b).
        """
        raw = attempt_result.get("raw_response")
        if not raw:
            return

        bucket = state.setdefault("per_spec_markdown", {})
        if not isinstance(bucket, dict):
            logger.warning(
                "CORR-061 S3b: state['per_spec_markdown'] is not a dict "
                "(type=%s); re-initialising — downstream renderers may miss "
                "previous responses",
                type(bucket).__name__,
            )
            bucket = {}
            state["per_spec_markdown"] = bucket

        existing = bucket.get(spec_id)
        if isinstance(existing, str) and existing:
            # Subsequent call for the same spec — append with a
            # horizontal-rule separator so reviewers can grep the
            # boundary between lanes.
            bucket[spec_id] = existing + "\n\n---\n\n" + raw
        else:
            bucket[spec_id] = raw

    @staticmethod
    def _persist_raw_call(
        spec_id: str,
        attempt: int,
        prompt_system: str,
        prompt_user: str,
        raw_response: str,
        status: str,
        latency_ms: float,
        model: str,
        error: str | None = None,
    ) -> None:
        """CORR-061 S4: persist every LLM attempt to disk for offline audit.

        Writes TWO files under ``<AEGIS_RAW_OUTPUT_DIR>/<spec_id>/``:

          * ``<UTC-timestamp>__attempt<N>.md``  — YAML frontmatter with
            metadata, the full system + user prompts (clearly delimited
            by ``## Prompt (system)`` / ``## Prompt (user)``), and the
            raw model response. This is the human-review artefact.
          * ``<UTC-timestamp>__attempt<N>.json`` — the same metadata as
            structured JSON, plus a 200-char preview of the raw response
            (the full body is in the ``.md`` to keep the JSON small).
            This is the programmatic-access artefact.

        Both files are always written; the JSON omits the full prompt
        body on purpose so the index stays small even for very long
        prompts (P1C-LLM-01 prompts are ~850KB).

        The base directory is resolved from the ``AEGIS_RAW_OUTPUT_DIR``
        env var, falling back to the canonical default
        :data:`aegis_phase1.config.defaults.RAW_OUTPUT_DIR`
        (``output/phase1/raw``). The directory is created lazily
        (mkdir -p) on every call — capture works even on the very
        first attempt of a fresh run.

        Timestamp format: ``YYYY-MM-DDTHH-MM-SS`` in **UTC** (matches
        the existing ``datetime.now(UTC)`` usage elsewhere in this
        module; deterministic and timezone-independent for cross-team
        review).

        Errors during persistence are swallowed with a warning — the
        run must not be aborted just because disk capture failed. The
        in-memory state capture (S3b ``_capture_per_spec_markdown``)
        remains the primary in-process record.

        Args:
            spec_id: Canonical Phase 1 LLM ID (e.g. ``P1B-LLM-01-INTERPRETATION``).
            attempt: 1-based attempt number within the retry loop.
            prompt_system: Full system prompt sent to the model.
            prompt_user: Full user prompt sent to the model.
            raw_response: Raw model response (may be empty on connection failure).
            status: Attempt status (``OK``, ``SCHEMA_ERROR``, ``PARSE_ERROR``,
                ``PYTHON_ERROR``, ``INSUFFICIENT_EVIDENCE``, …).
            latency_ms: Wall-clock latency in milliseconds.
            model: Model tag (e.g. ``gemma4:e2b``).
            error: Optional human-readable error string; included in
                frontmatter and JSON when set.
        """
        try:
            base_dir = Path(os.environ.get("AEGIS_RAW_OUTPUT_DIR", RAW_OUTPUT_DIR))
            spec_dir = base_dir / spec_id
            spec_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
            md_path = spec_dir / f"{timestamp}__attempt{attempt}.md"
            json_path = spec_dir / f"{timestamp}__attempt{attempt}.json"

            # YAML frontmatter + prompt + raw response
            fm_lines = [
                "---",
                f"spec_id: {spec_id}",
                f"attempt: {attempt}",
                f"model: {model}",
                f"status: {status}",
                f"latency_ms: {latency_ms}",
                f"timestamp: {timestamp}",
            ]
            if error:
                # Use a quoted scalar so newlines / colons in error
                # text don't break YAML parsing during offline review.
                escaped = str(error).replace("\n", " ").replace('"', "'")
                fm_lines.append(f'error: "{escaped}"')
            fm_lines.append("---")
            fm_lines.append("")

            md_content = "\n".join(fm_lines) + "\n"
            md_content += "## Prompt (system)\n\n"
            md_content += (prompt_system or "(empty)") + "\n\n"
            md_content += "## Prompt (user)\n\n"
            md_content += (prompt_user or "(empty)") + "\n\n"
            md_content += "## Raw response\n\n"
            md_content += (raw_response or "(empty)") + "\n"

            md_path.write_text(md_content, encoding="utf-8")

            json_content = {
                "spec_id": spec_id,
                "attempt": attempt,
                "model": model,
                "status": status,
                "latency_ms": latency_ms,
                "timestamp": timestamp,
                "prompt_system_chars": len(prompt_system or ""),
                "prompt_user_chars": len(prompt_user or ""),
                "raw_response_chars": len(raw_response or ""),
                "raw_response_preview": (raw_response or "")[:200],
                "error": error,
            }
            json_path.write_text(
                json.dumps(json_content, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as _persist_err:
            # Never let a capture failure abort the run — log and move on.
            logger.warning(
                "CORR-061 S4: failed to persist raw call for %s attempt %d: %s",
                spec_id,
                attempt,
                _persist_err,
            )

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, Any]:
        """Best-effort extraction of token usage from a LangChain response.

        Primary path: ``response.response_metadata`` — Ollama puts token counts
        at the top level as ``prompt_eval_count`` / ``eval_count`` (NOT nested
        under ``token_usage`` / ``usage`` like the OpenAI format).

        Fallback path: ``response.usage_metadata`` — langchain-core canonical
        shape is a dict-like with ``input_tokens`` / ``output_tokens`` /
        ``total_tokens``. We read it via ``.get()`` because in practice it is
        a TypedDict / ``UsageMetadata``, NOT an object with attributes.

        CORR-021: when BOTH official paths are empty (e.g. Ollama constrained
        generation returns a malformed nested-JSON response and drops the
        metadata — observed with P1B-LLM-02 at e2b model), fall back to a
        character-based estimate from the response content. Guarantees the
        user never sees ``0 tok`` in the logs for an LLM call that clearly
        produced output.

        Always returns the three-key dict; never raises (mock/empty fixtures
        must produce zeros unless the response has actual content).
        """
        usage: dict[str, Any] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            meta = getattr(response, "response_metadata", None)
            if isinstance(meta, dict) and meta:
                prompt_tokens = int(meta.get("prompt_eval_count", 0) or 0)
                completion_tokens = int(meta.get("eval_count", 0) or 0)
                usage["prompt_tokens"] = prompt_tokens
                usage["completion_tokens"] = completion_tokens
                usage["total_tokens"] = prompt_tokens + completion_tokens
            else:
                usage_meta = getattr(response, "usage_metadata", None)
                if isinstance(usage_meta, dict) and usage_meta:
                    prompt_tokens = int(usage_meta.get("input_tokens", 0) or 0)
                    completion_tokens = int(usage_meta.get("output_tokens", 0) or 0)
                    total_tokens = int(
                        usage_meta.get("total_tokens", prompt_tokens + completion_tokens) or 0
                    )
                    usage["prompt_tokens"] = prompt_tokens
                    usage["completion_tokens"] = completion_tokens
                    usage["total_tokens"] = total_tokens
        except Exception:
            pass
        if usage["total_tokens"] == 0:
            content = getattr(response, "content", None)
            if isinstance(content, str) and content:
                estimated = max(1, len(content) // 4)
                usage["completion_tokens"] = estimated
                usage["total_tokens"] = estimated
        return usage
