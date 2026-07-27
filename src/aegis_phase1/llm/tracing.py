"""Langfuse tracing stub for aegis-phase1.

If `langfuse` is installed and `LANGFUSE_ENABLED=true`, provides real tracing.
Otherwise, returns no-op callbacks.

Install: `pip install langfuse`
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)


# CORR-021: module-level cache so every caller in a single pipeline run gets
# the SAME handler (and therefore the SAME trace_id). Without this, every
# call to get_langfuse_callback() generated a fresh trace, splitting the
# pipeline into multiple disjoint traces in Langfuse.
#
# CORR-063 S4: the cache key now also includes ``run_id`` so two
# concurrent pipeline runs (e.g. background + foreground) get distinct
# handlers. Pass ``run_id=...`` from the orchestrator. When the
# orchestrator does not pass run_id, the function falls back to a
# process-wide default generated at import time — this preserves
# the original CORR-021 contract (successive get_langfuse_callback
# calls with no args return the same cached handler).
_default_run_id: str = str(uuid.uuid4())
_langfuse_cache: tuple[Any, Any] | None = None
_langfuse_cache_key: tuple[str, str, str, str, str, str] | None = None


def _invalidate_langfuse_cache() -> None:
    """Test helper — clears the module-level cache."""
    global _langfuse_cache, _langfuse_cache_key
    _langfuse_cache = None
    _langfuse_cache_key = None


def get_langfuse_callback(
    case_name: str = "default",
    phase: str = "phase1",
    run_id: str | None = None,
) -> tuple[Any, Any]:
    """Return a (langfuse_client, callback_handler) tuple.

    CORR-021: cached at module level — subsequent calls with the same
    (host, public_key, secret_key, case_name, phase, run_id) return the
    cached handler so all LLM calls in a pipeline run land under the
    same Langfuse trace.

    CORR-063 S4: every trace created by the handler now carries:
      - ``session_id`` = run_id (groups all traces of one S1 run)
      - ``user_id``    = case_name (groups traces by case across runs)
      - ``tags``       = ["phase:...", "case:...", "run:..."]
    Without session_id, the 18 LangGraph nodes of a single S1 run
    appeared as 18 disjoint traces in the Langfuse UI; now they all
    share ``session_id=<run_id>`` and can be filtered as a group.

    If Langfuse is disabled or not available, returns (None, None).
    """
    global _langfuse_cache, _langfuse_cache_key

    if os.environ.get("LANGFUSE_ENABLED", "true").lower() not in ("true", "1", "yes"):
        return None, None

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    # CORR-063 S4: default the run_id to a process-wide stable UUID
    # (generated once at import time) when the caller doesn't pass one.
    # This preserves the CORR-021 contract: successive calls without
    # args share the same cached handler. Real orchestrators should
    # pass run_id= explicitly to scope the cache to a single S1 run.
    effective_run_id = run_id or _default_run_id

    cache_key = (host, public_key, secret_key, case_name, phase, effective_run_id)
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
        # CORR-063 S4: session_id + user_id on every trace created by
        # the handler. The LangGraph integration creates 1 trace per
        # node (18 per S1 run); without session_id, the 18 traces are
        # visually disconnected in the UI. With session_id = run_id,
        # the operator can filter the UI by session and see the full
        # 18-node timeline as a group.
        trace_context: dict[str, Any] = {
            "trace_id": trace_id,
            "session_id": effective_run_id,
            "user_id": case_name,
        }
        handler = CallbackHandler(trace_context=trace_context)
        handler.tags = [t for t in [
            f"phase:{phase}" if phase else None,
            f"case:{case_name}" if case_name else None,
            f"run:{effective_run_id[:8]}" if effective_run_id else None,
        ] if t]
        logger.info(
            "[tracing] Langfuse enabled host=%s case=%s phase=%s run=%s trace_id=%s",
            host, case_name, phase, effective_run_id[:8], trace_id,
        )
        _langfuse_cache = (client, handler)
        _langfuse_cache_key = cache_key
        return client, handler
    except ImportError:
        logger.warning("[tracing] langfuse not installed, skipping")
        return None, None
    except Exception as e:
        logger.exception("[tracing] Langfuse init failed: %s", e)
        return None, None
