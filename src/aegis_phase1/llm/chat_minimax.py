"""MiniMax chat adapter for the AEGIS Phase 1 pipeline (CORR-062 S2).

Drop-in replacement for :class:`langchain_ollama.ChatOllama` so the rest
of the pipeline (parser, validator, executor) is **model-agnostic**:
``UnifiedInvoker.invoke`` and ``invoke_spec`` work unchanged regardless
of whether the chat is Ollama or MiniMax.

Speaks the Anthropic Messages protocol. Per the MiniMax Token Plan docs
(``https://platform.minimax.io/docs/token-plan/quickstart`` and
``/docs/api-reference/text-anthropic-api``), the M3 / M-series models
are served at the Anthropic-compatible base URL::

    Base URL:    https://api.minimax.io/anthropic
    Endpoint:    POST {base_url}/v1/messages
    Models:      MiniMax-M3, MiniMax-M2.7, MiniMax-M2.7-highspeed
    Auth:        Authorization: Bearer <sk-cp-... token plan key>
    Required hdr: anthropic-version: 2023-06-01
    Required hdr: content-type: application/json

Request body (Anthropic Messages)::

    {
      "model": "MiniMax-M3",
      "max_tokens": 4096,
      "messages": [{"role": "user", "content": "..."}],
      "system": "..."   # optional
    }

Response shape (Anthropic Messages)::

    {
      "id": "msg_...",
      "content": [{"type": "text", "text": "..."}],
      "stop_reason": "end_turn",
      "usage": {"input_tokens": N, "output_tokens": M}
    }

Auth resolution order (first non-empty wins):
  1. ``api_key=`` constructor kwarg
  2. ``MINIMAX_API_KEY`` env var
  3. ``MAVIS_ACCESS_TOKEN`` env var (the user-profile default)

Used by :class:`aegis_phase1.llm.unified.UnifiedInvoker` when the user
passes ``--provider minimax`` to the runner. Default model is
``"MiniMax-M3"`` (per the methodology's ``Model Configuration`` block
in each Phase 1 prompt file).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional, Sequence

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import model_validator

logger = logging.getLogger(__name__)

# CORR-062 S2: corrected 2026-07-27 after MiniMax API docs review.
# The previous URL (``https://agent.minimax.io/mavis/api/v1/llm/v1``)
# was the Mavis agent gateway, which uses a different auth system
# (MAVIS_ACCESS_TOKEN env, not the Token Plan). The Token Plan key
# (sk-cp-...) targets the Anthropic-compatible endpoint documented at
# https://platform.minimax.io/docs/api-reference/text-anthropic-api.
DEFAULT_BASE_URL = "https://api.minimax.io/anthropic"
DEFAULT_MODEL = "MiniMax-M3"
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_TOKENS = 4096

# CORR-062 S2 (2026-07-27): the MiniMax Token Plan has a per-second
# rate limit (no public doc on the exact number; user-flagged during
# the S1 run that 18 calls in 91ms was a bad pattern). We enforce a
# minimum interval between successive chat calls — default 5.0s, so
# max 12 calls/min. Override via the ``MINIMAX_MIN_INTERVAL`` env var
# (float, seconds) — set to 0.0 to disable the throttle entirely.
#
# Module-level lock + last-call timestamp so the throttle is process-
# wide (not per-instance) — multiple UnifiedInvoker objects in the
# same Python process would otherwise bypass it.
_throttle_lock = threading.Lock()
_last_call_ts: list[float] = [0.0]


def _throttle(min_interval: float) -> None:
    """Sleep until at least ``min_interval`` seconds have passed since
    the last ``_throttle`` call. No-op when ``min_interval <= 0``.
    """
    if min_interval <= 0:
        return
    with _throttle_lock:
        now = time.monotonic()
        wait = _last_call_ts[0] + min_interval - now
        if wait > 0:
            time.sleep(wait)
        _last_call_ts[0] = time.monotonic()


class ChatMinimax(BaseChatModel):
    """LangChain-compatible chat model for the MiniMax M-series (M2.7/M3).

    Implements the ``_generate`` hook only (no streaming, no tool calls,
    no function calling) — the Phase 1 pipeline calls ``chat.invoke(messages)``
    once per LLM spec and parses the markdown response via
    ``P1BLLM01Parser`` etc. The returned :class:`AIMessage` carries
    ``response_metadata`` + ``usage_metadata`` so the existing token
    accounting in ``UnifiedInvoker._extract_usage`` keeps working
    unchanged.
    """

    model: str = DEFAULT_MODEL
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = 0.0
    min_interval: float = 5.0  # CORR-062 S2: throttle between calls (5s default)

    @model_validator(mode="after")
    def _resolve_min_interval(self) -> "ChatMinimax":
        """Resolve the effective ``min_interval`` from env if not explicit.

        ``MINIMAX_MIN_INTERVAL`` (float, seconds) overrides the default
        without touching code. Set to ``0.0`` to disable the throttle.
        Reads the env only when the caller passed the field-default value
        (5.0) so explicit ``min_interval=...`` constructor args win.
        """
        if self.min_interval == 5.0:
            env_val = os.environ.get("MINIMAX_MIN_INTERVAL")
            if env_val is not None:
                try:
                    self.min_interval = float(env_val)
                except ValueError:
                    logger.warning(
                        "ChatMinimax: invalid MINIMAX_MIN_INTERVAL=%r, keeping 5.0",
                        env_val,
                    )
        return self

    # ─── BaseChatModel interface ─────────────────────────────────────

    @property
    def _llm_type(self) -> str:
        return "minimax"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        # CORR-062 S2: throttle between calls so we don't trip the
        # MiniMax Token Plan rate limit. Module-level lock makes the
        # throttle process-wide (multiple UnifiedInvoker instances
        # would otherwise bypass it). min_interval=0 disables.
        _throttle(self.min_interval)

        system_prompt, converted = self._convert_messages(messages)

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": converted,
        }
        if system_prompt:
            body["system"] = system_prompt
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if stop:
            body["stop_sequences"] = stop

        url = f"{self.base_url.rstrip('/')}/v1/messages"
        # Defensive: send BOTH Anthropic-style (x-api-key) and OpenAI-style
        # (Authorization: Bearer). The Mavis gateway is a proxy and some
        # routes accept one or the other depending on the underlying
        # upstream. Including both never hurts and avoids 401s from
        # header-shape mismatches.
        api_key = self._resolve_api_key()
        headers = {
            "x-api-key": api_key,
            "Authorization": f"Bearer {api_key}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # CORR-063 S3: DEBUG-level request log — visible only with
        # --log-level DEBUG. NEVER logs the auth headers (x-api-key /
        # Authorization) or the system prompt body (privacy + size).
        logger.debug(
            "ChatMinimax POST %s model=%s max_tokens=%d messages=%d system_len=%d",
            url, self.model, self.max_tokens, len(converted),
            len(system_prompt) if system_prompt else 0,
        )

        # CORR-064 S5.1: retry on transient errors (5xx, 408, 429,
        # connection error, timeout). Exponential backoff 1s/2s/4s.
        # Do NOT retry on 4xx (auth, bad request, forbidden) — those
        # are operator errors that won't fix themselves. Max 3 attempts
        # (1 initial + 2 retries) before giving up. Set
        # ``CHAT_MINIMAX_MAX_RETRIES=0`` to disable (for tests).
        import time as _time
        import os as _os
        max_retries = int(_os.environ.get("CHAT_MINIMAX_MAX_RETRIES", "2"))
        _TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504, 529}
        _TRANSIENT_EXC = (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadError,
            httpx.ReadTimeout,
            httpx.PoolTimeout,
        )

        _t0 = _time.monotonic()
        resp = None
        data = None
        for attempt in range(1 + max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=body, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                break  # success
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                is_transient = status in _TRANSIENT_STATUS
                if not is_transient or attempt == max_retries:
                    logger.debug(
                        "ChatMinimax HTTP error after %.2fs: status=%d (attempt %d/%d, transient=%s)",
                        _time.monotonic() - _t0, status, attempt + 1,
                        max_retries + 1, is_transient,
                    )
                    raise
                wait = 2 ** attempt
                logger.warning(
                    "ChatMinimax transient error: status=%d (attempt %d/%d); retrying in %ds",
                    status, attempt + 1, max_retries + 1, wait,
                )
                _time.sleep(wait)
            except _TRANSIENT_EXC as exc:
                if attempt == max_retries:
                    logger.debug(
                        "ChatMinimax connection error after %.2fs: %s (attempt %d/%d)",
                        _time.monotonic() - _t0, type(exc).__name__,
                        attempt + 1, max_retries + 1,
                    )
                    raise
                wait = 2 ** attempt
                logger.warning(
                    "ChatMinimax connection error: %s (attempt %d/%d); retrying in %ds",
                    type(exc).__name__, attempt + 1, max_retries + 1, wait,
                )
                _time.sleep(wait)
            except Exception as exc:
                # Non-transient (parse error, programming bug). No retry.
                logger.debug(
                    "ChatMinimax non-transient error after %.2fs: %s: %s",
                    _time.monotonic() - _t0, type(exc).__name__, str(exc)[:200],
                )
                raise
        if resp is None or data is None:
            # Defensive: should never reach here, but satisfy the type-checker.
            raise RuntimeError("ChatMinimax._generate: no response after retries")
        elapsed = _time.monotonic() - _t0
        usage = data.get("usage", {}) or {}
        logger.debug(
            "ChatMinimax response: status=%d in %.2fs, "
            "input_tokens=%d output_tokens=%d stop_reason=%s",
            resp.status_code, elapsed,
            int(usage.get("input_tokens", 0) or 0),
            int(usage.get("output_tokens", 0) or 0),
            data.get("stop_reason"),
        )

        return ChatResult(generations=[ChatGeneration(message=self._parse_response(data))])

    # ─── Helpers ─────────────────────────────────────────────────────

    def _resolve_api_key(self) -> str:
        """Pick the first non-empty API key from (in order):

        1. ``api_key`` constructor kwarg (if not the placeholder)
        2. ``MINIMAX_API_KEY`` env var
        3. ``MAVIS_ACCESS_TOKEN`` env var
        """
        if self.api_key and self.api_key != "sk-xxx":
            return self.api_key
        for env_name in ("MINIMAX_API_KEY", "MAVIS_ACCESS_TOKEN"):
            env_val = os.environ.get(env_name)
            if env_val:
                logger.debug("ChatMinimax: using api_key from env %s", env_name)
                return env_val
        raise ValueError(
            "ChatMinimax: no api_key configured. Set api_key=, "
            "MINIMAX_API_KEY env var, or MAVIS_ACCESS_TOKEN env var."
        )

    @staticmethod
    def _convert_messages(
        messages: Sequence[BaseMessage],
    ) -> tuple[Optional[str], list[dict[str, str]]]:
        """Split messages into (system_prompt, rest).

        Anthropic Messages wants a top-level ``system`` field separate
        from the ``messages`` array. Any number of SystemMessage objects
        are concatenated with double newlines.
        """
        system_parts: list[str] = []
        rest: list[dict[str, str]] = []
        for m in messages:
            if m.type == "system":
                content = m.content if isinstance(m.content, str) else str(m.content)
                if content:
                    system_parts.append(content)
            else:
                # langchain message types: "human" -> "user", "ai" -> "assistant"
                role = "user" if m.type == "human" else "assistant"
                content = m.content if isinstance(m.content, str) else str(m.content)
                rest.append({"role": role, "content": content})
        system_prompt = "\n\n".join(system_parts) if system_parts else None
        return system_prompt, rest

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> AIMessage:
        """Convert Anthropic Messages response → langchain AIMessage.

        Mirrors the field shape that ``UnifiedInvoker._extract_usage``
        and the rest of the AEGIS pipeline expect: ``content`` as a
        string, ``response_metadata`` with ``model`` + token counts,
        ``usage_metadata`` with ``input_tokens`` / ``output_tokens`` /
        ``total_tokens``.
        """
        content_blocks = data.get("content", []) or []
        text_parts = [
            block.get("text", "")
            for block in content_blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        text = "".join(text_parts)

        usage = data.get("usage", {}) or {}
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)

        response_metadata: dict[str, Any] = {
            "model": data.get("model", ""),
            "stop_reason": data.get("stop_reason"),
            "id": data.get("id"),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

        usage_metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

        return AIMessage(
            content=text,
            response_metadata=response_metadata,
            usage_metadata=usage_metadata,
        )


__all__ = ["ChatMinimax", "DEFAULT_BASE_URL", "DEFAULT_MODEL"]
