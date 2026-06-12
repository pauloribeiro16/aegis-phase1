"""Shared case.yaml loader for AEGIS-KG.

Replaces the 3 duplicated cases/*/config.py files with a single, generic
loader. Each case provides a case.yaml; the loader returns a typed
Pydantic model. Backward compatibility is maintained via thin wrappers
in each case directory.

Schema (case.yaml):
  case: str
  name: str
  description: str
  neo4j:
    uri: str
    user: str
    password: "${NEO4J_PASSWORD}"  # expanded from env
    database: str
    http_url: str
  llm:
    provider: str
    base_url: str
    model: str
    timeout: int
    keep_alive: int
    num_ctx: int
  embedding:
    model: str
    base_url: str
  judge:
    model: str
    max_tokens: int
    dimensions: list[str]
    thresholds: dict
  tags:
    langfuse_prompt_labels: list[str]
  eval:
    judge_llm: str
    max_tokens: int
    trials: int
  phases: dict
"""

import os
import re
from pathlib import Path
from typing import overload

import yaml
from pydantic import BaseModel, Field

from aegis_phase1.config.defaults import (
    DEFAULT_EMBEDDING_MODEL,
    LANGFUSE_PROMPT_LABELS,
    OLLAMA_BASE_URL,
)
from aegis_phase1.config.models import EmbeddingConfig, JudgeConfig, LLMConfig, Neo4jConfig
from aegis_phase1.env import load_env

load_env()

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


@overload
def _expand_env_in_str(value: str) -> str: ...


@overload
def _expand_env_in_str(value: dict) -> dict: ...


@overload
def _expand_env_in_str(value: list) -> list: ...


@overload
def _expand_env_in_str(value: None) -> None: ...


def _expand_env_in_str(value: str | dict | list | None) -> str | dict | list | None:
    """Recursively expand ${VAR} patterns in strings, dicts, and lists."""
    if isinstance(value, str):

        def _replace(m):
            var_name = m.group(1)
            if var_name == "NEO4J_PASSWORD":
                return os.environ.get(var_name, "d3fendtest")
            return os.environ.get(var_name, m.group(0))

        return _ENV_VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _expand_env_in_str(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_in_str(item) for item in value]
    return value


class CaseConfig(BaseModel):
    """Typed case.yaml configuration."""

    model_config = {"extra": "allow"}

    case: str
    name: str
    description: str = ""
    neo4j: Neo4jConfig | None = None
    llm: LLMConfig
    embedding: EmbeddingConfig = Field(
        default_factory=lambda: EmbeddingConfig(
            model=DEFAULT_EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
    )
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    tags: dict = Field(default_factory=lambda: {"langfuse_prompt_labels": LANGFUSE_PROMPT_LABELS})
    eval: dict = Field(default_factory=dict)
    phases: dict = Field(default_factory=dict)


def load_case_config(case_dir: str | Path) -> CaseConfig:
    """Load and validate case.yaml from the given directory.

    Args:
        case_dir: Path to the case directory (containing case.yaml).

    Returns:
        Validated CaseConfig pydantic model.

    Raises:
        FileNotFoundError: If case.yaml is missing.
        ValidationError: If the schema is invalid.
    """
    case_dir = Path(case_dir)
    case_yaml = case_dir / "case.yaml"
    if not case_yaml.exists():
        raise FileNotFoundError(f"case.yaml not found in {case_dir}")

    with open(case_yaml, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    expanded = _expand_env_in_str(raw)
    return CaseConfig(**expanded)


def load_case_yaml(case_dir: str | Path) -> dict:
    """Load case.yaml as a raw dict (for legacy code that needs untyped access)."""
    case_dir = Path(case_dir)
    case_yaml = case_dir / "case.yaml"
    if not case_yaml.exists():
        return {}
    with open(case_yaml, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _expand_env_in_str(raw) or {}
