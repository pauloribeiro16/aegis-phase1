"""LLM client abstraction layer.

Provides a unified interface for multiple LLM backends (Ollama, llama.cpp).
Use create_llm_client(config) to instantiate the appropriate backend.
"""

from abc import ABC, abstractmethod
from typing import Any

from aegis_phase1.logging_config import get_logger

logger = get_logger(__name__)


class BaseLLMClient(ABC):
    """Base class for LLM clients."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str = "",
        task_name: str = "unnamed",
        temperature: float = 0.1,
        num_predict: int | None = None,
        stop: list | None = None,
        config: dict | None = None,
    ) -> dict[str, Any]:
        """Generate text from the LLM.

        Args:
            prompt: The user prompt
            system: System prompt
            task_name: Name of the task for logging
            temperature: Sampling temperature
            num_predict: Max tokens to generate (None = no limit)
            stop: Stop sequences
            config: Optional RunnableConfig for LangChain callback propagation

        Returns:
            dict with keys: raw (str), latency_ms (float), tokens (dict)
            On error: error (str), raw (""), latency_ms (float), tokens ({})
        """
        ...


def create_llm_client(config: dict | None = None) -> BaseLLMClient:
    """Factory: create the appropriate LLM client based on config.

    Config keys:
        provider: "ollama" | "llamacpp" (default: "ollama")

    Ollama-specific keys:
        base_url: str (default: "http://localhost:11434")
        model: str (default: "gemma4:e4b")
        timeout: int (default: 120)
        num_ctx: int (default 20480) — Ollama context window in tokens

    llama.cpp-specific keys:
        model_path: str (required, path to .gguf file)
        n_gpu_layers: int (default: -1, full GPU offload)
        n_ctx: int (default: 4096)
    """
    if config is None:
        config = {}

    provider = config.get("provider", "ollama")

    if provider == "llamacpp":
        try:
            from aegis_phase1.llm.llamacpp import LlamaCppClient  # type: ignore[attr-defined]

            return LlamaCppClient(config)  # type: ignore[no-any-return]
        except ImportError:
            logger.warning("LlamaCppClient not available, falling back to Ollama")

    from aegis_phase1.llm.ollama import OllamaClient

    return OllamaClient(config=config)
