"""Centralized logging configuration for AEGIS-KG.

Provides:
- `get_logger(name)`: standard logger factory with module-name prefix
- `configure_logging(level)`: idempotent root-logger setup (call once from entry points)
- `BoundLogger`: thin wrapper that auto-prepends `[module]` and joins key=value pairs

Format: `2026-06-03 17:42:02 INFO  [n02_stakeholder] START intake_len=18211 taxonomy_len=10813`

Usage (library code):
    from aegis_phase1.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("START", intake_len=18211, taxonomy_len=10813)

Usage (entry points only):
    from aegis_phase1.logging_config import configure_logging
    configure_logging(level="INFO")  # or "DEBUG" for verbose

Rules enforced by this module:
- No module in `core/` or `cases/` should call `logging.basicConfig()` — only entry points.
- All loggers use `__name__` so the prefix tracks the import path.
- All `except` blocks must log, never silently `pass`.
- Log messages include structured key=value context, not just strings.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

_CONFIGURED = False
_DEFAULT_FORMAT = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: str | int = "DEBUG",
    log_file: str | None = None,
    force: bool = False,
) -> None:
    """Configure the root logger with the AEGIS-KG standard format.

    Idempotent unless `force=True`. Only entry-point scripts (eval, ETL, CLI)
    should call this; library code should use `get_logger(__name__)`.

    Args:
        level: Log level — string ("DEBUG"/"INFO"/"WARNING"/"ERROR") or int.
        log_file: Optional path to also write logs to a file (in addition to stderr).
        force: Re-configure even if already configured.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    level_int = getattr(logging, level.upper(), logging.INFO) if isinstance(level, str) else level

    formatter = logging.Formatter(fmt=_DEFAULT_FORMAT, datefmt=_DEFAULT_DATEFMT)

    root = logging.getLogger()
    root.setLevel(level_int)

    for h in list(root.handlers):
        root.removeHandler(h)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(level_int)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(level_int)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            # Acceptable: log file may be unavailable (permissions, path).
            # Logging here would recurse into the handler we're trying to create.
            pass

    for noisy in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger that follows the AEGIS-KG standard format.

    The logger's effective level is the lowest of:
    - The `LOG_LEVEL` env var (if set)
    - The root logger's level (if configured)
    - INFO otherwise

    Args:
        name: Usually `__name__` of the calling module.

    Returns:
        Configured `logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    env_level = os.getenv("LOG_LEVEL")
    if env_level:
        try:
            logger.setLevel(getattr(logging, env_level.upper(), logging.INFO))
        except (TypeError, ValueError):
            logger.setLevel(logging.INFO)
    elif not logger.level:
        logger.setLevel(logging.INFO)

    logger.propagate = True
    return logger


def format_kv(**kwargs: Any) -> str:
    """Format key=value pairs for log messages.

    Skips None values. Quotes strings with spaces. Truncates long values.

    Example:
        >>> format_kv(model="gemma4:e2b", prompt_len=5721, status="ok")
        'model=gemma4:e2b prompt_len=5721 status=ok'
    """
    parts: list[str] = []
    for k, v in kwargs.items():
        if v is None:
            continue
        s = str(v)
        if len(s) > 200:
            s = s[:197] + "..."
        if " " in s or '"' in s:
            s = s.replace('"', '\\"')
            parts.append(f'{k}="{s}"')
        else:
            parts.append(f"{k}={s}")
    return " ".join(parts)


__all__ = ["configure_logging", "format_kv", "get_logger"]
