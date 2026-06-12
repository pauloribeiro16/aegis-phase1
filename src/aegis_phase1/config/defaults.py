"""Centralized default values for AEGIS-KG.

This module is the SINGLE SOURCE OF TRUTH for default configuration values.
All other modules import defaults from here. To change a default, edit this
file. Never hardcode default values in core/agent/, core/eval/, core/workflow/.

Override priority (highest to lowest):
  1. Runtime arguments (function parameters, CLI flags)
  2. Environment variables (.env file via Pydantic BaseSettings)
  3. case.yaml (per-case config, loaded in Sprint 2)
  4. Defaults from this file
"""

# Neo4j connection
NEO4J_HTTP_URL = "http://localhost:7475"
NEO4J_BOLT_URL = "bolt://localhost:7688"
NEO4J_USER = "neo4j"
NEO4J_DATABASE = "neo4j"
# NEO4J_PASSWORD: no default — must be set via env

# LLM (Ollama)
DEFAULT_LLM_PROVIDER = "ollama"
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_LLM_MODEL = "gemma4:e4b"
DEFAULT_LLM_TIMEOUT = 120
DEFAULT_LLM_NUM_CTX = 8192
DEFAULT_LLM_KEEP_ALIVE = 300
DEFAULT_LLM_TEMPERATURE = 0.1

# Embedding model
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_EMBEDDING_TIMEOUT = 30

# Judge LLM (MiniMax)
DEFAULT_JUDGE_MODEL = "MiniMax-M3"
DEFAULT_JUDGE_MAX_TOKENS = 4096
DEFAULT_JUDGE_TEMPERATURE = 0.1
DEFAULT_JUDGE_BASE_URL = "https://api.minimaxi.chat/v1/text/chatcompletion_v2"

# Langfuse / tracing
DEFAULT_LANGFUSE_ENABLED = False
DEFAULT_LANGFUSE_HOST = "https://cloud.langfuse.com"
DEFAULT_LANGFUSE_BUDGET = 50000
LANGFUSE_PROMPT_LABELS = ["production"]

# Project metadata
PROJECT_NAME = "aegis-kg-eval"
TRACE_NAME = "aegis-kg-unified-eval"
