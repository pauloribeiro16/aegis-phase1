"""LLM client abstraction layer.

Public API:
  - create_llm_client(config)
  - ChatOllama
  - ChatMinimax
  - ChatOpenAICompat
"""

from aegis_phase1.llm.base import create_llm_client
from aegis_phase1.llm.chat_minimax import ChatMinimax
from aegis_phase1.llm.ollama import ChatOllama
from aegis_phase1.llm.openai_compat import ChatOpenAICompat
from aegis_phase1.llm.unified import UnifiedInvoker

__all__ = [
    "ChatMinimax",
    "ChatOllama",
    "ChatOpenAICompat",
    "UnifiedInvoker",
    "create_llm_client",
]
