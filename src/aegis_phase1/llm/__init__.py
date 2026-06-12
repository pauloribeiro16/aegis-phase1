"""LLM client abstraction layer.

Public API:
  - create_llm_client(config)
  - ChatOllama
"""

from aegis_phase1.llm.base import create_llm_client
from aegis_phase1.llm.ollama import ChatOllama

__all__ = [
    "ChatOllama",
    "create_llm_client",
]
