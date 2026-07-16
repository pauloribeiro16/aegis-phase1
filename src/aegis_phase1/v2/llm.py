"""LLM invoker factory for v2 pipeline (Option C — direct Ollama).

Architecture (Option C):
    The processor calls Ollama DIRECTLY via ``langchain_ollama.ChatOllama``,
    bypassing the legacy ``Phase1LLMInvoker``. This is a thin wrapper
    with a scriptable mock for tests.

Public API:
    OllamaInvoker       Real LLM (ChatOllama) wrapper.
    MockInvoker         Scriptable mock for tests / MOCK_LLM mode.
    build_llm_invoker   Factory selecting MockInvoker vs OllamaInvoker.
    OllamaUnreachableError  Raised when Ollama is unreachable.

References:
    - decisions/MAP3_OPTION_C.md
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

from aegis_phase1.llm.unified import UnifiedInvoker  # noqa: E402 — re-exported for callers

_MOCK_TRUTHS = {"1", "true", "yes", "on"}

_DEFAULT_OK_RESPONSE = (
    "ADAPTED_OBJECTIVE: Default mock response for testing. "
    "This text is intentionally short but valid.\n"
    "KEY_ADJUSTMENTS:\n"
    "- mock adjustment 1\n"
    "- mock adjustment 2\n"
    "CONFIDENCE: HIGH"
)


class OllamaUnreachableError(Exception):
    """Raised when Ollama is unreachable at startup health-check."""


class MockInvoker:
    """Scriptable mock for tests and ``MOCK_LLM=true`` mode.

    Each call to :meth:`invoke` returns the next scripted response. If
    the script is exhausted, a default OK response is returned.

    Expected response shape:
        ``{"raw": str, "status": "OK" | "FAILED_AFTER_RETRIES"}``

    Tests can supply a list of dicts; production use case is empty script
    (always returns the default OK response).
    """

    def __init__(self, script: list[dict] | None = None) -> None:
        self.script: list[dict] = list(script or [])
        self.call_count = 0
        self.last_prompt = ""
        self.last_feedback = ""

    def invoke(
        self,
        prompt: str,
        feedback: str = "",
        *,
        config: Any = None,
    ) -> dict[str, Any]:
        """Return the next scripted response, or a default OK response.

        ``config`` is accepted for signature parity with
        :class:`OllamaInvoker`; mock responses do not need Langfuse
        tracing, so the argument is ignored.
        """
        self.last_prompt = prompt
        self.last_feedback = feedback
        if self.call_count < len(self.script):
            response = dict(self.script[self.call_count])
        else:
            response = {"raw": _DEFAULT_OK_RESPONSE, "status": "OK"}
        self.call_count += 1
        return response


class OllamaInvoker:
    """Thin wrapper over ``langchain_ollama.ChatOllama``.

    Default model: ``gemma4:e4b``, num_ctx=32768, max_tokens=2048.
    Health-checked at construction by :func:`build_llm_invoker`.
    """

    def __init__(
        self,
        model: str = "gemma4:e4b",
        base_url: str = "http://localhost:11434",
        num_ctx: int = 32768,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        *,
        langfuse_handler: Any = None,
    ) -> None:
        from langchain_ollama import ChatOllama

        self.model = model
        self.base_url = base_url
        self.num_ctx = num_ctx
        self.max_tokens = max_tokens
        self._langfuse_handler = langfuse_handler
        self.chat = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            num_ctx=num_ctx,
            num_predict=max_tokens,
        )

    def invoke(
        self,
        prompt: str,
        feedback: str = "",
        *,
        config: Any = None,
    ) -> dict[str, Any]:
        """Call the LLM. Returns ``{"raw": str, "status": ...}``.

        When ``self._langfuse_handler`` is set, a ``callbacks=[handler]``
        entry is merged into ``config`` (without overwriting any
        caller-supplied callbacks). Network or Ollama errors are caught
        and returned as ``FAILED_AFTER_RETRIES`` so the processor can
        decide whether to retry or propagate.

        Returns:
            ``{"raw": str, "status": str, "usage": dict}`` on success.
            ``"usage"`` carries ``prompt_tokens`` / ``completion_tokens``
            / ``total_tokens`` extracted from Ollama's
            ``response_metadata`` (or the langchain-core fallback).
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        msgs: list[Any] = [HumanMessage(content=prompt)]
        if feedback:
            msgs.append(
                SystemMessage(
                    content=f"PREVIOUS ERROR: {feedback}\nPlease correct."
                )
            )

        if config is None:
            config = {}
        if self._langfuse_handler is not None:
            existing = list(config.get("callbacks") or [])
            if self._langfuse_handler not in existing:
                existing.append(self._langfuse_handler)
            config = {**config, "callbacks": existing}

        invoke_kwargs: dict[str, Any] = {}
        if config:
            invoke_kwargs["config"] = config

        try:
            resp = self.chat.invoke(msgs, **invoke_kwargs)
            usage = self._extract_usage(resp)
            return {
                "raw": str(resp.content),
                "status": "OK",
                "usage": usage,
            }
        except Exception as exc:  # noqa: BLE001 — any Ollama error becomes a status
            logger.warning("Ollama invoke failed: %s", exc)
            return {
                "raw": "",
                "status": "FAILED_AFTER_RETRIES",
                "error": str(exc),
            }

    @staticmethod
    def _extract_usage(response: Any) -> dict[str, int]:
        """Extract token usage from an Ollama / langchain-core response.

        Primary path: Ollama's top-level ``response_metadata`` keys
        ``prompt_eval_count`` and ``eval_count``.

        Fallback: langchain-core canonical ``usage_metadata`` with
        ``input_tokens`` / ``output_tokens`` / ``total_tokens``.

        Always returns a dict with ``prompt_tokens``,
        ``completion_tokens`` and ``total_tokens`` keys (zeros on miss).
        """
        usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        try:
            meta = getattr(response, "response_metadata", None)
            if isinstance(meta, dict) and meta:
                usage["prompt_tokens"] = int(meta.get("prompt_eval_count", 0) or 0)
                usage["completion_tokens"] = int(meta.get("eval_count", 0) or 0)
                usage["total_tokens"] = (
                    usage["prompt_tokens"] + usage["completion_tokens"]
                )
            else:
                um = getattr(response, "usage_metadata", None)
                if isinstance(um, dict) and um:
                    usage["prompt_tokens"] = int(um.get("input_tokens", 0) or 0)
                    usage["completion_tokens"] = int(
                        um.get("output_tokens", 0) or 0
                    )
                    usage["total_tokens"] = int(
                        um.get("total_tokens", 0)
                        or usage["prompt_tokens"] + usage["completion_tokens"]
                    )
        except Exception:  # noqa: BLE001 — usage extraction must never raise
            pass
        return usage


def build_llm_invoker(
    model: str | None = None,
    *,
    langfuse_handler: Any = None,
) -> MockInvoker | "OllamaInvoker | UnifiedInvoker":
    """Build the LLM invoker for the current run (CORR-013).

    Selection rule:
        - If ``MOCK_LLM`` env var is truthy, returns a :class:`MockInvoker`.
        - Otherwise returns a :class:`aegis_phase1.llm.UnifiedInvoker`
          (the new unified entry point; the legacy ``OllamaInvoker``
          child is constructed lazily for the heavy path). A 1-line
          health-check ping runs first; raises
          :class:`OllamaUnreachableError` if Ollama is down.

    Args:
        model: Optional model name override (default ``gemma4:e4b``).
        langfuse_handler: Optional Langfuse ``CallbackHandler`` (or any
            ``BaseCallbackHandler``-compatible object) to attach to the
            invoker. MockInvoker ignores it (no network call → no tracing
            benefit). When ``LANGFUSE_ENABLED=false`` (default), pass
            ``None`` — behaviour is byte-identical to the pre-CORR-012
            implementation.

    Returns:
        A configured invoker instance.

    Raises:
        OllamaUnreachableError: When Ollama cannot be reached.
    """
    if os.environ.get("MOCK_LLM", "").strip().lower() in _MOCK_TRUTHS:
        logger.info("MOCK_LLM=true → MockInvoker")
        return MockInvoker()

    invoker = UnifiedInvoker(
        model=model or "gemma4:e4b",
        langfuse_handler=langfuse_handler,
    )
    _health_check(invoker)
    return invoker


def _health_check(invoker: OllamaInvoker) -> None:
    """Fast HTTP probe to verify Ollama is reachable.

    Uses ``urllib`` (no extra deps) with a 3-second timeout. Skips the
    heavy LLM call so a missing Ollama fails immediately.

    Raises:
        OllamaUnreachableError: When the probe fails.
    """
    import urllib.request
    from urllib.error import URLError

    try:
        # Probe the Ollama version endpoint — no model load, returns fast.
        req = urllib.request.Request(
            f"{invoker.base_url.rstrip('/')}/api/version",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status != 200:
                raise OllamaUnreachableError(
                    f"Ollama returned HTTP {resp.status} at {invoker.base_url}"
                )
    except OllamaUnreachableError:
        raise
    except (URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise OllamaUnreachableError(
            f"Cannot reach Ollama at {invoker.base_url}: {exc}. "
            f"Set MOCK_LLM=true to use mock mode, or run "
            f"`ollama serve` + `ollama pull gemma4:e4b`."
        ) from exc


__all__ = [
    "MockInvoker",
    "OllamaInvoker",
    "OllamaUnreachableError",
    "UnifiedInvoker",
    "build_llm_invoker",
] 