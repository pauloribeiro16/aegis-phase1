"""Langfuse tracing stub for aegis-phase1.

If `langfuse` is installed and `LANGFUSE_ENABLED=true`, provides real tracing.
Otherwise, returns no-op callbacks.

Install: `pip install langfuse`
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def get_langfuse_callback(case_name: str = "default", phase: str = "phase1") -> tuple[Any, Any]:
    """Return a (langfuse_client, callback_handler) tuple.

    If Langfuse is disabled or not available, returns (None, None).
    """
    if os.environ.get("LANGFUSE_ENABLED", "false").lower() not in ("true", "1", "yes"):
        return None, None

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
        host = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            logger.warning("[tracing] LANGFUSE_ENABLED=true but credentials missing")
            return None, None

        client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        handler = CallbackHandler()
        logger.info("[tracing] Langfuse enabled host=%s case=%s phase=%s", host, case_name, phase)
        return client, handler
    except ImportError:
        logger.warning("[tracing] langfuse not installed, skipping")
        return None, None
    except Exception as e:
        logger.exception("[tracing] Langfuse init failed: %s", e)
        return None, None
