"""OpenAI-compatible chat adapter for the AEGIS Phase 1 pipeline (CORR-110).

Drop-in replacement for :class:`langchain_ollama.ChatOllama` so the rest
of the pipeline (parser, validator, executor) is **model-agnostic**:
``UnifiedInvoker.invoke`` and ``invoke_spec`` work unchanged regardless
of whether the chat is Ollama, the MiniMax gateway, or an OpenAI-
compatible HTTP endpoint (vLLM / TGI / SGLang).

Speaks the OpenAI Chat Completions protocol::

    POST {base_url}/v1/chat/completions
    Headers: Authorization: Bearer <api_key>  (optional)
             Content-Type: application/json
    Body:    {"model": "<served_model_name>",
              "messages": [{"role": "system"|"user"|"assistant",
                            "content": "..."}],
              "temperature": 0.0,
              "max_tokens": 4096,
              "stream": false}

    Response (non-streaming)::
        {"id": "chatcmpl-...",
         "choices": [{"index": 0,
                      "message": {"role": "assistant", "content": "..."},
                      "finish_reason": "stop"}],
         "usage": {"prompt_tokens": N,
                   "completion_tokens": M,
                   "total_tokens": N+M}}

CORR-110 motivation:
    The Deucalion HPC cluster cannot run new Ollama model blobs through
    the local Ollama 0.31.1 binary (renderer / manifest mismatches)
    and the older GGUF-only pipeline blocked gemma-4-31B evaluation
    (JOB 1846584 — aborted at the invoker factory). vLLM serves any
    HuggingFace model that has been pre-staged on Lustre
    (``HF_HUB_OFFLINE=1``) via its OpenAI-compatible HTTP server, so
    we route through this adapter instead. No new project dependency —
    only ``httpx`` (already required by ``chat_minimax.py``) and
    ``langchain-core``.

Auth:
    ``api_key`` is optional — local vLLM servers usually run without
    auth. Set the ``--api-key`` flag of ``vllm serve`` (and pass
    ``AEGIS_VLLM_API_KEY`` env to the pipeline) for hardened clusters.
    The adapter sends ``Authorization: Bearer <key>`` when a non-empty
    key is configured.

Used by :class:`aegis_phase1.llm.unified.UnifiedInvoker` when the user
passes ``--provider vllm`` to the runner, or by
``prompts_v2/invoker._attempt`` for the heavy (Phase 1C) path.
Default model is ``"gemma4-31b"`` (matches the served-model-name the
sbatch scripts emit via ``--served-model-name``).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import model_validator

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8000/v1"
DEFAULT_MODEL = "gemma4-31b"
DEFAULT_TIMEOUT = 600  # CORR-110: Phase 1B rationales routinely run 60-180s
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.0

# Env vars consumed by the adapter (resolved in the model_validator so
# ctor args always win, then env, then defaults).
_BASE_URL_ENV = "AEGIS_VLLM_BASE_URL"
_MODEL_ENV = "AEGIS_VLLM_MODEL"
_API_KEY_ENV = "AEGIS_VLLM_API_KEY"
_TIMEOUT_ENV = "AEGIS_VLLM_TIMEOUT"


class ChatOpenAICompat(BaseChatModel):
    """LangChain-compatible chat model for OpenAI-style HTTP endpoints.

    Implements the ``_generate`` hook only (no streaming, no tool calls,
    no function calling) — the Phase 1 pipeline calls
    ``chat.invoke(messages)`` once per LLM spec and parses the markdown
    response via ``P1BLLM01Parser`` etc. The returned
    :class:`AIMessage` carries ``response_metadata`` +
    ``usage_metadata`` so the existing token accounting in
    ``UnifiedInvoker._extract_usage`` keeps working unchanged.
    """

    model: str = DEFAULT_MODEL
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE

    @model_validator(mode="after")
    def _resolve_env_overrides(self) -> ChatOpenAICompat:
        """Read env overrides when the caller left a field at its default.

        Honour order: explicit ctor kwarg > env var > module default.
        Only fills a field that is still at its module default value so
        explicit constructor arguments always win.
        """
        if self.base_url == DEFAULT_BASE_URL:
            env_val = os.environ.get(_BASE_URL_ENV)
            if env_val:
                self.base_url = env_val
        if self.model == DEFAULT_MODEL:
            env_val = os.environ.get(_MODEL_ENV)
            if env_val:
                self.model = env_val
        if not self.api_key:
            self.api_key = os.environ.get(_API_KEY_ENV) or ""
        if self.timeout == DEFAULT_TIMEOUT:
            env_val = os.environ.get(_TIMEOUT_ENV)
            if env_val:
                try:
                    self.timeout = float(env_val)
                except ValueError:
                    logger.warning(
                        "ChatOpenAICompat: invalid %s=%r, keeping %s",
                        _TIMEOUT_ENV,
                        env_val,
                        DEFAULT_TIMEOUT,
                    )
        return self

    # ─── BaseChatModel interface ─────────────────────────────────────

    @property
    def _llm_type(self) -> str:
        return "openai_compat"

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
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [_openai_message(m) for m in messages],
            "stream": False,
        }
        if stop:
            body["stop"] = stop

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # CORR-110: network-level timeout, not wall-clock. Long
        # generations on 31B-class models routinely exceed 120 s; we
        # default to 600 s. Per-call ``request_timeout`` kwarg still
        # wins if the executor passes one.
        call_timeout = kwargs.get("request_timeout", self.timeout)

        try:
            with httpx.Client(timeout=call_timeout) as client:
                resp = client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise ConnectionError(
                f"ChatOpenAICompat: cannot reach {url}: {exc}. "
                f"Is the vLLM server running? (Check VLLM_PORT and "
                f"curl http://<node>:{self.base_url.split(':')[-1].split('/')[0]}"
                f"/v1/models)"
            ) from exc

        if resp.status_code >= 400:
            # Surface the upstream error verbatim so the parser /
            # executor sees the real cause (model not found, OOM,
            # guided-decode failure, etc.) rather than a generic
            # "HTTP 4xx" — same convention as ChatMinimax.
            raise ConnectionError(
                f"ChatOpenAICompat: HTTP {resp.status_code} from {url}: " f"{resp.text[:500]}"
            )

        payload = resp.json()
        choices = payload.get("choices") or []
        if not choices:
            raise ConnectionError(
                f"ChatOpenAICompat: empty choices in response from {url}: " f"{str(payload)[:500]}"
            )
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        finish_reason = choices[0].get("finish_reason") or "stop"

        usage = payload.get("usage") or {}
        usage_metadata = {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
        response_metadata = {
            "model": payload.get("model", self.model),
            "finish_reason": finish_reason,
            "id": payload.get("id", ""),
            "usage": usage,
        }
        ai_message = AIMessage(
            content=content,
            response_metadata=response_metadata,
            usage_metadata=usage_metadata,
        )
        return ChatResult(
            generations=[ChatGeneration(message=ai_message)],
            llm_output={"model": self.model, "usage": usage},
        )


def _openai_message(msg: BaseMessage) -> dict[str, Any]:
    """Convert a LangChain BaseMessage into the OpenAI chat message dict.

    Supports ``system`` / ``user`` / ``assistant`` roles — the four the
    Phase 1 pipeline actually emits. Multimodal content lists are
    coerced to plain text (Phase 1 is text-only — CORR-110 inherits
    this from the Ollama path).
    """
    role = getattr(msg, "role", None) or msg.type
    if role == "human":
        role = "user"
    elif role == "ai":
        role = "assistant"
    elif role == "system":
        role = "system"
    content = msg.content
    if isinstance(content, list):
        # Flatten multimodal content blocks down to text segments.
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                # else: skip non-text blocks (image_url, etc.)
            else:
                text_parts.append(str(block))
        content = "\n".join(p for p in text_parts if p)
    return {"role": role, "content": content}


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT",
    "ChatOpenAICompat",
]
