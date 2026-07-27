"""MiniMax chat adapter for the AEGIS Phase 1 pipeline (CORR-062 S2).

Drop-in replacement for :class:`langchain_ollama.ChatOllama` so the rest
of the pipeline (parser, validator, executor) is **model-agnostic**:
``UnifiedInvoker.invoke`` and ``invoke_spec`` work unchanged regardless
of whether the chat is Ollama or MiniMax.

Speaks the Anthropic Messages protocol because ``config.yaml`` declares
``npm: @ai-sdk/anthropic`` for the ``minimax`` provider
(``~/.mavis/config.yaml``). Request shape::

    POST {base_url}/messages
    Headers:
      x-api-key: <api_key>
      anthropic-version: 2023-06-01
    Body:
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
from typing import Any, Optional, Sequence

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://agent.minimax.io/mavis/api/v1/llm/v1"
DEFAULT_MODEL = "MiniMax-M3"
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_TOKENS = 4096


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

        url = f"{self.base_url.rstrip('/')}/messages"
        headers = {
            "x-api-key": self._resolve_api_key(),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        logger.info(
            "ChatMinimax POST %s model=%s max_tokens=%d messages=%d",
            url, self.model, self.max_tokens, len(converted),
        )

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

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
