"""Typed Pydantic models for configuration."""

from pydantic import BaseModel, SecretStr

from aegis_phase1.config.defaults import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_LLM_KEEP_ALIVE,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_NUM_CTX,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_TIMEOUT,
    NEO4J_BOLT_URL,
    NEO4J_DATABASE,
    NEO4J_HTTP_URL,
    NEO4J_USER,
    OLLAMA_BASE_URL,
)


class Neo4jConfig(BaseModel):
    http_url: str = NEO4J_HTTP_URL
    bolt_url: str = NEO4J_BOLT_URL
    user: str = NEO4J_USER
    password: SecretStr = SecretStr("")
    database: str = NEO4J_DATABASE


class LLMConfig(BaseModel):
    provider: str = DEFAULT_LLM_PROVIDER
    base_url: str = OLLAMA_BASE_URL
    model: str = DEFAULT_LLM_MODEL
    timeout: int = DEFAULT_LLM_TIMEOUT
    num_ctx: int = DEFAULT_LLM_NUM_CTX
    keep_alive: int = DEFAULT_LLM_KEEP_ALIVE


class EmbeddingConfig(BaseModel):
    model: str = DEFAULT_EMBEDDING_MODEL
    base_url: str = OLLAMA_BASE_URL


class JudgeConfig(BaseModel):
    model: str = ""
