"""LLM client abstraction layer.

Public API:
  - create_llm_client(config)
  - ChatOllama
  - UnifiedInvoker, TransformersInvoker, MockInvoker
  - quant_manifest (CORR-111 sidecar helpers)
"""

from aegis_phase1.llm.base import create_llm_client
from aegis_phase1.llm.ollama import ChatOllama
from aegis_phase1.llm.unified import UnifiedInvoker
from aegis_phase1.llm import quant_manifest as quant_manifest

__all__ = [
    "ChatOllama",
    "UnifiedInvoker",
    "create_llm_client",
    "quant_manifest",
]
