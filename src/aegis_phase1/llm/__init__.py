"""LLM client abstraction layer.

Public API:
  - create_llm_client(config)
  - ChatOllama
"""

from aegis_phase1.llm.base import create_llm_client
from aegis_phase1.llm.ollama import ChatOllama
from aegis_phase1.llm.unified import UnifiedInvoker

__all__ = [
    "ChatOllama",
    "UnifiedInvoker",
    "create_llm_client",
] 
