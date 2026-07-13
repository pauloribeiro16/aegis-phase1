"""Helper factory for instantiating Phase1LLMInvoker with sensible defaults.

This module provides a single entry point for nodes to get a fully-wired
Phase1LLMInvoker. Handles:
  - Loading PROMPTS/ from default location (../Methodology-main/00_METHODOLOGY/PROMPTS)
  - Loading Layer 0 source (../Methodology-main/00_METHODOLOGY/PREPROCESSING/SubDomains)
  - Setting up JSONLLogger (logs/phase1/llm-calls.jsonl + format-errors.jsonl)
  - Setting up Phase1Validator with Layer 0 root

Usage:
    from aegis_phase1.prompts_v2.factory import get_invoker, get_validator

    invoker = get_invoker()  # default location
    result = invoker.invoke("P1B-LLM-01-INTERPRETATION", inputs)

    validator = get_validator()
    ok = validator.validate(spec_id, output)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Default paths (sibling repo Methodology-main)
_DEFAULT_PROMPTS_ROOT = (
    Path(__file__).parent.parent.parent.parent.parent
    / "Methodology-main"
    / "00_METHODOLOGY"
    / "PROMPTS"
)
_DEFAULT_LAYER0_ROOT = (
    Path(__file__).parent.parent.parent.parent.parent
    / "Methodology-main"
    / "00_METHODOLOGY"
    / "PREPROCESSING"
    / "SubDomains"
)
_DEFAULT_LOGS_DIR = Path(__file__).parent.parent.parent.parent / "logs" / "phase1"


def get_prompts_root() -> Path:
    """Return the PROMPTS/ root directory (sibling Methodology-main repo)."""
    return _DEFAULT_PROMPTS_ROOT


def get_layer0_root() -> Path:
    """Return the Layer 0 SubDomains/ root directory."""
    return _DEFAULT_LAYER0_ROOT


def get_logs_dir() -> Path:
    """Return the logs/phase1/ directory (creates if missing)."""
    _DEFAULT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return _DEFAULT_LOGS_DIR


def get_validator(layer0_root: Path | None = None) -> Any:
    """Get a Phase1Validator with default Layer 0 root."""
    from aegis_phase1.prompts_v2.validator import Phase1Validator

    root = layer0_root or get_layer0_root()
    schemas_path = get_prompts_root() / "output_schemas.yaml"
    return Phase1Validator(layer0_root=root, output_schemas_path=schemas_path)


def get_invoker(
    model: str | None = None,
    base_url: str | None = None,
    prompts_root: Path | None = None,
    layer0_root: Path | None = None,
) -> Any:
    """Get a fully-wired Phase1LLMInvoker with default config.

    Reads OLLAMA_MODEL and OLLAMA_BASE_URL from environment if not provided.
    """
    import os

    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker
    from aegis_phase1.prompts_v2.loader import PromptLoader
    from aegis_phase1.prompts_v2.logging_helper import JSONLLogger

    prompts = prompts_root or get_prompts_root()
    layer0 = layer0_root or get_layer0_root()
    logs = get_logs_dir()

    model = model or os.getenv("OLLAMA_MODEL", Phase1LLMInvoker.DEFAULT_MODEL)
    base_url = base_url or os.getenv(
        "OLLAMA_BASE_URL", Phase1LLMInvoker.DEFAULT_BASE_URL
    )

    prompt_loader = PromptLoader(root=prompts)
    catalog_loader = CatalogLoader(root=prompts / "catalogs")
    validator = get_validator(layer0_root=layer0)
    llm_logger = JSONLLogger(logs / "llm-calls.jsonl")
    format_logger = JSONLLogger(logs / "format-errors.jsonl")

    invoker = Phase1LLMInvoker(
        prompt_loader=prompt_loader,
        catalog_loader=catalog_loader,
        validator=validator,
        llm_logger=llm_logger,
        format_logger=format_logger,
        model=model,
        base_url=base_url,
    )
    invoker.prompts = prompt_loader
    invoker.catalogs = catalog_loader
    invoker.validator = validator
    invoker.llm_logger = llm_logger
    invoker.format_logger = format_logger
    return invoker
