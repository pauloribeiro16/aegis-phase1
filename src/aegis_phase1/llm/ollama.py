"""Centralized Ollama client for all AEGIS modules using LangChain ChatOllama.

Uses langchain_ollama.ChatOllama for automatic Langfuse integration.
When callbacks are passed via LangGraph, the Langfuse CallbackHandler
automatically captures: model name, prompts, responses, token usage, latency.
"""

import os
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from aegis_phase1.config.defaults import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_NUM_CTX,
    DEFAULT_LLM_TIMEOUT,
    OLLAMA_BASE_URL,
)
from aegis_phase1.llm.base import BaseLLMClient
from aegis_phase1.logging_config import get_logger

logger = get_logger(__name__)


class OllamaClient(BaseLLMClient):
    """Unified client for Ollama API calls with LangChain integration.

    Wraps ChatOllama to provide a simple interface while enabling
    automatic tracing via Langfuse CallbackHandler.
    """

    def __init__(self, config: dict | None = None, model_config: dict | None = None):
        if config is None:
            config = {}
        if model_config is None:
            model_config = {}

        self.base_url = config.get("base_url", OLLAMA_BASE_URL)
        self.model = config.get("model", DEFAULT_LLM_MODEL)
        self.timeout = config.get("timeout", DEFAULT_LLM_TIMEOUT)
        self.num_ctx = config.get("num_ctx", DEFAULT_LLM_NUM_CTX)
        self._config = config
        self._model_config = model_config

        self._langfuse_handlers: list = []
        self._setup_langfuse()

        # keep_alive: how long model stays in VRAM (default 5min = 300s)
        # Ollama accepts: int (seconds) or str ("30m", "1h")
        self.keep_alive = config.get("keep_alive", 300)

        self._llm = ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=0.1,
            num_ctx=self.num_ctx,
            client_kwargs={"timeout": self.timeout},
        )

    def _setup_langfuse(self) -> None:
        """Auto-attach Langfuse CallbackHandler if enabled via env vars."""
        if os.environ.get("LANGFUSE_ENABLED", "").lower() not in ("true", "1", "yes"):
            return
        try:
            from langfuse.langchain import CallbackHandler  # type: ignore[import-untyped]

            pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
            sk = os.environ.get("LANGFUSE_SECRET_KEY", "")
            host = os.environ.get(
                "LANGFUSE_BASE_URL", "https://cloud.langfuse.com"
            )
            if pk and sk:
                self._langfuse_handlers = [CallbackHandler()]
                logger.info(
                    "[ollama] Langfuse auto-attached host=%s model=%s",
                    host,
                    self.model,
                )
        except ImportError:
            logger.debug("[ollama] langfuse not installed, skipping auto-attach")

    def generate(
        self,
        prompt: str,
        system: str = "",
        task_name: str = "unnamed",
        temperature: float = 0.1,
        num_predict: int | None = None,
        stop: list | None = None,
        config: dict | None = None,
        format: dict | str | None = None,
    ) -> dict:
        """Generate text using Ollama via ChatOllama.

        Args:
            prompt: The user prompt
            system: System prompt
            task_name: Name of the task for logging
            temperature: Sampling temperature
            num_predict: Max tokens to generate (None = no limit)
            stop: Stop sequences
            config: Optional RunnableConfig for LangChain callback propagation.
                When passed from a LangGraph node, the Langfuse CallbackHandler
                automatically creates a nested GENERATION observation with
                real prompts, output, and token usage.
            format: Optional output format constraint. Pass a dict (JSON Schema)
                or a string ("json" for plain JSON, or ""/None to disable).
                Used by Ollama's structured-output feature to constrain the
                response format.

        Returns:
            dict with keys: raw, latency_ms, tokens, error
        """
        if self._model_config:
            task_cfg = self._model_config.get(task_name, {})
            if task_cfg:
                temperature = task_cfg.get("temperature", temperature)
                if "num_predict" in task_cfg:
                    num_predict = task_cfg["num_predict"]
                if "stop" in task_cfg and stop is None:
                    stop = task_cfg["stop"]

        logger.debug(
            "[ollama] task=%s model=%s prompt_len=%d",
            task_name,
            self.model,
            len(prompt),
        )

        # Build messages for ChatOllama
        messages: list[SystemMessage | HumanMessage] = []
        if system:
            # Append anti-numbering instruction to existing system prompt
            system = (
                system
                + "\n\nCRITICAL: NEVER use line numbers (1., 2., 3.) in your output. Write raw Cypher only."
            )
            messages.append(SystemMessage(content=system))
        else:
            # Default system prompt with anti-numbering instruction
            messages.append(
                SystemMessage(
                    content="You are a Neo4j Cypher query generator. CRITICAL: NEVER use line numbers (1., 2., 3.) in your output. Write raw Cypher only."
                )
            )
        messages.append(HumanMessage(content=prompt))

        # Configure generation parameters by updating the LLM instance
        # ChatOllama doesn't accept params in invoke(), so we set them beforehand
        if temperature is not None:
            self._llm.temperature = temperature
        if num_predict is not None and num_predict > 0:
            self._llm.num_predict = num_predict
        if stop:
            self._llm.stop = stop
        if format is not None:
            # Ollama accepts dict (JSON Schema) or string ("json") as format
            self._llm.format = format

        start = time.time()
        try:
            # Invoke ChatOllama — callbacks are auto-propagated by LangGraph
            # When config is provided (from a LangGraph node), the Langfuse
            # CallbackHandler automatically creates a nested GENERATION observation
            # with real prompts, output, and token usage.
            # keep_alive controls how long model stays in VRAM (e.g., 1800 = 30min)
            invoke_kwargs = {}
            if self.keep_alive is not None:
                invoke_kwargs["keep_alive"] = self.keep_alive
            response = self._llm.invoke(messages, config=config, **invoke_kwargs)  # type: ignore[arg-type]
            elapsed = (time.time() - start) * 1000

            content = response.content if hasattr(response, "content") else str(response)

            # Extract token usage from response metadata if available
            tokens = {}
            if hasattr(response, "response_metadata") and response.response_metadata:
                meta = response.response_metadata
                tokens = {
                    "prompt_eval_count": meta.get("prompt_eval_count", 0),
                    "eval_count": meta.get("eval_count", 0),
                }

            logger.debug(
                "[ollama] task=%s done elapsed_s=%.1f eval_tokens=%d",
                task_name,
                elapsed / 1000,
                tokens.get("eval_count", 0),
            )

            return {
                "raw": content,
                "latency_ms": elapsed,
                "tokens": tokens,
            }

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(
                "[ollama] task=%s error: %s",
                task_name,
                e,
                exc_info=True,
            )
            return {
                "error": str(e),
                "raw": "",
                "latency_ms": elapsed,
                "tokens": {},
            }


_default_client = None


def get_ollama_client() -> OllamaClient:
    """Get or create the global OllamaClient instance (backward compat)."""
    global _default_client
    if _default_client is None:
        _default_client = OllamaClient()
    return _default_client
