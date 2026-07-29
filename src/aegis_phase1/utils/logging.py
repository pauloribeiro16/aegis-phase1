"""Centralized logging setup for aegis-phase1 (CORR-063 S1).

Provides a single :func:`setup_logging` function that the runner calls
once at the start of ``main()``. The setup is **idempotent** — calling
it multiple times (e.g. from tests) does not duplicate handlers.

Format:
    ``YYYY-MM-DD HH:MM,SSS | LEVEL     | logger_name            | message``

Levels (Python stdlib semantics):

* ``DEBUG``    — verbose: HTTP request/response, raw LLM I/O, timings
* ``INFO``     — pipeline progress, stage transitions, key decisions
* ``WARNING``  — recoverable failures (e.g. retries, parse fallbacks)
* ``ERROR``    — fatal but handled (e.g. node raises, we re-raise)
* ``CRITICAL`` — pipeline-aborting errors (e.g. config corruption)

Usage::

    from aegis_phase1.utils.logging import setup_logging
    setup_logging(level="INFO", log_file="logs/run.log")

    # Or, with per-model log dir (CORR-060 backward compat):
    setup_logging(level="INFO", model_tag="gemma4_e4b")

Then use ``logger = logging.getLogger(__name__)`` anywhere in the tree.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Final

# Module-level flag so we don't add handlers twice on repeat calls.
_SETUP_DONE: bool = False

# Canonical format used across the project. The width on the logger name
# (30 chars) keeps multi-module logs aligned.
_FORMAT: Final[str] = "%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s"
_DATEFMT: Final[str] = "%Y-%m-%d %H:%M:%S"

# Default level if the user doesn't set one. Honored only if the
# root logger hasn't been configured yet — explicit user choice wins.
_DEFAULT_LEVEL: Final[str] = "INFO"

# Loggers that are too chatty at INFO when running a full pipeline
# (per-renderer INFO logs would flood the console with hundreds of
# lines per run). Kept at WARNING unless user explicitly bumps to DEBUG.
_QUIET_LOGGERS: Final[tuple[str, ...]] = (
    "aegis_phase1.v2.output",
    "aegis_phase1.v2.output.doc_04a",
    "aegis_phase1.v2.output.doc_04b",
    "aegis_phase1.v2.output.doc_04c",
    "aegis_phase1.v2.output.doc_04d",
    "aegis_phase1.v2.output.doc_05",
    "aegis_phase1.v2.output.doc_07",
    "aegis_phase1.v2.output.doc_07b",
    "aegis_phase1.v2.output.xlsx_generator",
    "aegis_phase1.v2.output._common",
    "httpx",
    "httpcore",
    "urllib3",
)


def setup_logging(
    level: str = _DEFAULT_LEVEL,
    log_file: str | os.PathLike[str] | None = None,
    model_tag: str | None = None,
) -> None:
    """Configure the root logger for aegis-phase1.

    Args:
        level: One of ``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``,
            ``"CRITICAL"``. Case-insensitive. Defaults to ``"INFO"``.
        log_file: Optional explicit path to write logs to. Parent
            directories are created if missing. If None and ``model_tag``
            is provided, defaults to ``logs/phase1/<model_tag>/v2/pipeline_<model_tag>.log``
            (CORR-060 backward compat).
        model_tag: Optional model tag. When set and ``log_file`` is None,
            the file handler is placed under
            ``logs/phase1/<model_tag>/v2/pipeline_<model_tag>.log``
            (per-model log dir, supports multi-model eval).

    Notes:
        - Idempotent: a second call updates the level and (optionally)
          re-targets the file handler, but does not add duplicate handlers.
        - Honors ``LOG_LEVEL`` env var if ``level`` is left at default
          AND no CLI flag overrides.
        - Does NOT touch Langfuse's own loggers (Langfuse configures
          itself in :mod:`aegis_phase1.llm.tracing`).
    """
    global _SETUP_DONE

    # Resolve effective level: explicit arg > LOG_LEVEL env > default.
    effective_level_str = (
        level or os.environ.get("LOG_LEVEL", _DEFAULT_LEVEL)
    ).upper()
    effective_level = getattr(logging, effective_level_str, logging.INFO)

    # Resolve the log file path. Priority:
    #   1. explicit log_file=
    #   2. AEGIS_LOG_DIR env var + model_tag (CORR-060 pattern)
    #   3. logs/phase1/<model_tag>/v2/pipeline_<model_tag>.log if model_tag
    #   4. None (console only)
    resolved_log_file: Path | None = None
    if log_file:
        resolved_log_file = Path(log_file)
    elif model_tag:
        log_base = os.environ.get("AEGIS_LOG_DIR")
        if log_base:
            log_dir = Path(log_base) / "v2"
        else:
            log_dir = Path("logs") / "phase1" / model_tag / "v2"
        log_dir.mkdir(parents=True, exist_ok=True)
        resolved_log_file = log_dir / f"pipeline_{model_tag}.log"

    root = logging.getLogger()
    root.setLevel(effective_level)

    # Strip any pre-existing handlers (from a previous setup_logging call
    # OR from an earlier basicConfig). Keeps a clean slate.
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    # Console handler — always present, writes to stderr.
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(effective_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Optional file handler.
    if resolved_log_file is not None:
        resolved_log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            resolved_log_file, mode="a", encoding="utf-8"
        )
        file_handler.setLevel(effective_level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Make the aegis_phase1 namespace chatty at the chosen level.
    logging.getLogger("aegis_phase1").setLevel(effective_level)

    # Quiet down well-known noisy loggers. If user explicitly chose
    # DEBUG, the verbose mode wins (overrides even the quiet loggers).
    quiet_level = effective_level if effective_level <= logging.DEBUG else logging.WARNING
    for noisy in _QUIET_LOGGERS:
        logging.getLogger(noisy).setLevel(max(logging.getLogger(noisy).level, quiet_level))

    _SETUP_DONE = True
    root.info(
        "logging configured: level=%s, file=%s, console=true",
        effective_level_str,
        str(resolved_log_file) if resolved_log_file else "(none)",
    )


def is_setup_done() -> bool:
    """Test/debug helper — True after the first :func:`setup_logging` call."""
    return _SETUP_DONE


__all__ = ["setup_logging", "is_setup_done"]
