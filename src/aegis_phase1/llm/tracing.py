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


# CORR-021: module-level cache so every caller in a single pipeline run gets
# the SAME handler (and therefore the SAME trace_id). Without this, every
# call to get_langfuse_callback() generated a fresh trace, splitting the
# pipeline into multiple disjoint traces in Langfuse.
_langfuse_cache: tuple[Any, Any] | None = None
_langfuse_cache_key: tuple[str, str, str, str, str] | None = None


def _invalidate_langfuse_cache() -> None:
    """Test helper — clears the module-level cache."""
    global _langfuse_cache, _langfuse_cache_key
    _langfuse_cache = None
    _langfuse_cache_key = None


def get_langfuse_callback(case_name: str = "default", phase: str = "phase1") -> tuple[Any, Any]:
    """Return a (langfuse_client, callback_handler) tuple.

    CORR-021: cached at module level — subsequent calls with the same
    (host, public_key, secret_key, case_name, phase) return the cached
    handler so all LLM calls in a pipeline run land under the same
    Langfuse trace_id.

    If Langfuse is disabled or not available, returns (None, None).
    """
    global _langfuse_cache, _langfuse_cache_key

    if os.environ.get("LANGFUSE_ENABLED", "true").lower() not in ("true", "1", "yes"):
        return None, None

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    cache_key = (host, public_key, secret_key, case_name, phase)
    if _langfuse_cache_key == cache_key and _langfuse_cache is not None:
        return _langfuse_cache

    if not public_key or not secret_key:
        logger.warning("[tracing] LANGFUSE_ENABLED=true but credentials missing")
        return None, None

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        trace_id = client.create_trace_id()
        handler = CallbackHandler(trace_context={"trace_id": trace_id})
        handler.tags = [t for t in [
            f"phase:{phase}" if phase else None,
            f"case:{case_name}" if case_name else None,
        ] if t]
        logger.info("[tracing] Langfuse enabled host=%s case=%s phase=%s trace_id=%s", host, case_name, phase, trace_id)
        _langfuse_cache = (client, handler)
        _langfuse_cache_key = cache_key
        return client, handler
    except ImportError:
        logger.warning("[tracing] langfuse not installed, skipping")
        return None, None
    except Exception as e:
        logger.exception("[tracing] Langfuse init failed: %s", e)
        return None, None
