"""Unified LLM invoker for v1.2 (5 canonical specs) and v2 (free-text) call sites.

Replaces (does NOT yet delete — CORR-014 will remove):
- Phase1LLMInvoker (Layer A, prompts_v2/invoker.py)

Two public methods plus a polymorphic dispatcher:

- :meth:`UnifiedInvoker.invoke_spec` — heavy path: load prompt from PROMPTS/,
  render, parse JSON, validate, log, retry. Returns the canonical heavy dict.
- :meth:`UnifiedInvoker.invoke_raw` — light path: chat → ``{raw, status, usage}``
  with feedback channel for retry loops.
- :meth:`UnifiedInvoker.invoke` — polymorphic dispatcher used by legacy call
  sites that share the ``invoke(...)`` method name across both paths:
    - ``invoke(spec_id, inputs_dict)`` (inputs is a dict) → ``invoke_spec``
    - ``invoke(prompt)`` or ``invoke(prompt, feedback="...")`` → ``invoke_raw``

Both methods thread ``config["callbacks"]`` for Langfuse; both extract
Ollama-native token counts via :func:`_extract_usage`.

Strangler pattern: the heavy path internally delegates to a lazily-built
``Phase1LLMInvoker`` child so the battle-tested prompt-load / parse /
validate / retry logic is reused verbatim. CORR-014 will extract the body
of ``Phase1LLMInvoker.invoke`` into :meth:`invoke_spec` once the unified
API is validated.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


_PROBE_TTL_SECONDS = 30.0


class LLMUnreachableError(RuntimeError):
    """Raised when Ollama is not reachable at the configured base_url.

    Distinct from connection-during-invocation: this is detected BEFORE any
    chat attempt, so callers don't waste `max_retries` attempts on a known-down
    server. The orchestrator/CLI catches this and surfaces a clean user
    message instead of letting 788 lines of `python_error` flood the log.
    """

    def __init__(self, base_url: str, source: str = "unknown") -> None:
        self.base_url = base_url
        self.source = source
        super().__init__(f"Ollama not reachable at {base_url} (probe from {source})")


def probe_ollama(base_url: str = "http://localhost:11434", timeout: float = 1.5) -> bool:
    """Return True iff Ollama responds to GET /api/version within timeout.

    Fast (single http GET, short timeout). Used to short-circuit retry-storms
    when Ollama is unreachable.
    """
    import urllib.request
    from urllib.error import URLError

    try:
        req = urllib.request.Request(f"{base_url}/api/version", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except (URLError, OSError, ConnectionRefusedError, TimeoutError):
        return False


def _estimate_tokens_by_chars(text: str) -> int:
    """Best-effort token estimate from raw text.

    ~4 chars per token for English (rule of thumb). Used as a LAST RESORT
    fallback when both ``response_metadata`` (Ollama) and ``usage_metadata``
    (LangChain) are empty — e.g. when Ollama constrained generation returns
    a malformed nested-JSON response and drops the metadata.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def _extract_usage(response: Any) -> dict[str, int]:
    """Read Ollama-native or langchain-core token counts from a chat response.

    Primary path — Ollama's ``response_metadata`` exposes
    ``prompt_eval_count`` / ``eval_count`` at the top level (NOT nested
    under ``token_usage`` / ``usage`` as OpenAI does).

    Fallback path — langchain-core canonical ``usage_metadata`` with
    ``input_tokens`` / ``output_tokens`` / ``total_tokens``.

    CORR-021: when BOTH official paths are empty (e.g. Ollama constrained
    generation returns a malformed nested-JSON response and drops the
    metadata — observed with P1B-LLM-02 at e2b model), fall back to a
    character-based estimate from the response content. Guarantees the
    user never sees ``0 tok`` in the logs for an LLM call that clearly
    produced output.
    """
    usage: dict[str, int] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    try:
        meta = getattr(response, "response_metadata", None)
        if isinstance(meta, dict) and meta:
            usage["prompt_tokens"] = int(meta.get("prompt_eval_count", 0) or 0)
            usage["completion_tokens"] = int(meta.get("eval_count", 0) or 0)
            usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        else:
            um = getattr(response, "usage_metadata", None)
            if isinstance(um, dict) and um:
                usage["prompt_tokens"] = int(um.get("input_tokens", 0) or 0)
                usage["completion_tokens"] = int(um.get("output_tokens", 0) or 0)
                usage["total_tokens"] = int(
                    um.get("total_tokens", 0) or usage["prompt_tokens"] + usage["completion_tokens"]
                )
    except Exception:
        pass
    if usage["total_tokens"] == 0:
        content = getattr(response, "content", None)
        if isinstance(content, str) and content:
            usage["completion_tokens"] = _estimate_tokens_by_chars(content)
            usage["total_tokens"] = usage["completion_tokens"]
    return usage


def _merge_handler_into_config(
    handler: Any,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a copy of ``config`` with ``handler`` appended to ``callbacks``.

    Matches the CORR-011 / CORR-012 convention: dedupe by identity so a
    caller-supplied chain is preserved (Langfuse handler is APPENDED, not
    overwritten). Always returns a dict whose ``callbacks`` key is a
    list — empty when no handler is attached — so downstream chat
    invokers always receive a stable ``config["callbacks"]`` shape.

    CORR-019: LangGraph injects a ``CallbackManager`` (not a list) into
    ``config["callbacks"]`` when it invokes a sub-graph. We normalize to a
    list of handlers via ``handlers`` attribute, falling back to a
    single-item list if it's already a plain handler object.
    """
    cfg: dict[str, Any] = dict(config) if config else {}
    raw = cfg.get("callbacks")
    existing: list[Any] = []
    if raw is None:
        existing = []
    elif isinstance(raw, list):
        existing = list(raw)
    elif hasattr(raw, "handlers"):
        existing = list(raw.handlers or [])
    else:
        existing = [raw]
    if handler is not None and handler not in existing:
        existing.append(handler)
    cfg["callbacks"] = existing
    return cfg


class UnifiedInvoker:
    """Single invoker for all LLM calls in the Phase 1 pipeline.

    Args:
        model: Ollama model name (e.g. ``"gemma4:e4b"``). Default
            ``"gemma4:e4b"``.
        base_url: Ollama HTTP base. Default ``http://localhost:11434``.
        timeout: Ollama HTTP timeout in seconds. Default 120.
        langfuse_handler: Optional Langfuse ``CallbackHandler`` (or any
            ``BaseCallbackHandler``-compatible object). Threaded into
            every chat call's ``config["callbacks"]`` when set; ignored
            when ``None`` so legacy byte-identical behaviour is preserved
            under ``LANGFUSE_ENABLED=false``.
        prompt_loader: Required for :meth:`invoke_spec`. The v1.2 prompt
            loader (5 specs in ``00_METHODOLOGY/PROMPTS/``). When
            supplied, used directly; otherwise lazily built from
            ``prompts_root`` on first ``invoke_spec`` call.
        catalog_loader: Optional, forwarded to the heavy child.
        validator: Optional, forwarded to the heavy child.
        llm_logger: Optional, forwarded to the heavy child.
        format_logger: Optional, forwarded to the heavy child.
        prompts_root: Path-like root for the PROMPTS/ tree. Used to lazy-
            build ``prompt_loader`` if it was not supplied.

    Attributes:
        model: Resolved model name.
        prompts: ``prompt_loader`` (or ``None`` before first
            ``invoke_spec`` call). Exposed for ``invoker_to_executor``
            compatibility.
        catalogs: Forwarded ``catalog_loader`` (or ``None``).
        validator: Forwarded ``validator`` (or ``None``).
        llm_logger: Forwarded ``llm_logger`` (or ``None``).
        format_logger: Forwarded ``format_logger`` (or ``None``).
        chat: The shared ``langchain_ollama.ChatOllama`` instance for the
            light path.
        _langfuse_handler: The injected Langfuse handler (or ``None``).
        _heavy: Lazily-built ``Phase1LLMInvoker`` for the heavy path.
    """

    DEFAULT_MODEL = "gemma4:e4b"  # CORR-056 (2026-07-23): switched from gemma4:e2b
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_TIMEOUT = 120
    DEFAULT_NUM_CTX = 32768  # AEGIS-P1-CORR-022: match spec (docs/LLM_ARCHITECTURE_DECISION.md)

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        num_ctx: int | None = None,
        langfuse_handler: Any | None = None,
        prompt_loader: Any = None,
        catalog_loader: Any = None,
        validator: Any = None,
        llm_logger: Any = None,
        format_logger: Any = None,
        prompts_root: Any = None,
        provider: str = "ollama",
        api_key: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        # CORR-062 S2: ``provider`` selects the chat backend. The default
        # stays "ollama" for backward compat (existing tests + recovery
        # modes all use the local Ollama daemon). Pass "minimax" to use
        # the M-series models (M2.7 / M3) via the Mavis gateway.
        self.provider = provider
        self.api_key = api_key or ""
        self.max_tokens = max_tokens or 4096

        self.model = model or self.DEFAULT_MODEL

        # CORR-062 S2: when provider=minimax and no explicit base_url is
        # given, fall back to the Mavis gateway (the Anthropic-Messages
        # endpoint) instead of the Ollama default. ``ChatMinimax`` has
        # its own DEFAULT_BASE_URL, but we resolve here so the rest of
        # the pipeline (e.g. log paths) sees the right URL too.
        if base_url:
            self.base_url = base_url
        elif provider == "minimax":
            from aegis_phase1.llm.chat_minimax import DEFAULT_BASE_URL

            self.base_url = DEFAULT_BASE_URL
        else:
            env_url = os.environ.get("OLLAMA_BASE_URL")
            if env_url:
                self.base_url = env_url
            elif "OLLAMA_HOST" in os.environ:
                host = os.environ["OLLAMA_HOST"].strip()
                self.base_url = host if host.startswith("http") else f"http://{host}"
            else:
                self.base_url = self.DEFAULT_BASE_URL

        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.num_ctx = num_ctx or self.DEFAULT_NUM_CTX
        self._langfuse_handler = langfuse_handler

        self.prompts = prompt_loader
        self.catalogs = catalog_loader
        self.validator = validator
        self.llm_logger = llm_logger
        self.format_logger = format_logger
        self._prompts_root = prompts_root

        if provider == "minimax":
            from aegis_phase1.llm.chat_minimax import ChatMinimax

            self.chat = ChatMinimax(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_tokens=self.max_tokens,
            )
            logger.info(
                "UnifiedInvoker.__init__: provider=minimax, chat=%s model=%s base_url=%s",
                type(self.chat).__name__,
                self.chat.model,
                self.chat.base_url,
            )
        else:
            from langchain_ollama import ChatOllama

            self.chat = ChatOllama(
                model=self.model,
                base_url=self.base_url,
                timeout=self.timeout,
                num_ctx=self.num_ctx,
                # CORR-056: force all model layers onto GPU (gemma4:e2b fits
                # in 7.6GB VRAM; default `num_gpu=None` lets Ollama decide,
                # which under-uses VRAM on small models).
                num_gpu=99,
            )
            logger.info(
                "UnifiedInvoker.__init__: provider=ollama, chat=%s model=%s base_url=%s",
                type(self.chat).__name__,
                self.model,
                self.base_url,
            )
        self._heavy: Any | None = None
        self._ollama_reachable: bool | None = None
        self._ollama_probe_ts: float = 0.0

    def invoke_raw(
        self,
        prompt: str,
        *,
        feedback: str = "",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Light path — free-text prompt → ``{raw, status, usage}``.

        Mirrors the CORR-011/012 convention for backward compatibility:
        - the Langfuse handler is appended to ``config["callbacks"]``;
        - the response is best-effort parsed for token counts via
          :func:`_extract_usage`;
        - Ollama errors are returned as
          ``{"raw": "", "status": "FAILED_AFTER_RETRIES", "error": ...}``
          so callers can decide whether to retry or propagate.

        Probes Ollama before invocation (cached for
        ``_PROBE_TTL_SECONDS``) and raises
        :class:`LLMUnreachableError` immediately when down — no retry,
        no log spam (CORR-015).
        """
        self._ensure_ollama("invoke_raw")

        msgs: list[Any] = [HumanMessage(content=prompt)]
        if feedback:
            msgs.append(SystemMessage(content=f"PREVIOUS ERROR: {feedback}\nPlease correct."))

        # CORR-063 S3: DEBUG-level entry log. Visible only with
        # --log-level DEBUG. Does NOT log prompt content (privacy +
        # size — can be 10+ KB for AEGIS prompts).
        logger.debug(
            "invoke_raw called: prompt_len=%d feedback=%s chat=%s",
            len(prompt),
            bool(feedback),
            type(self.chat).__name__,
        )

        cfg = _merge_handler_into_config(self._langfuse_handler, config)
        try:
            import time as _time

            _t0 = _time.monotonic()
            resp = self.chat.invoke(msgs, config=cfg)
            elapsed = _time.monotonic() - _t0
            usage = _extract_usage(resp)
            logger.debug(
                "invoke_raw result: status=OK in %.2fs, raw_len=%d, " "input=%d output=%d",
                elapsed,
                len(resp.content),
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )
            return {
                "raw": str(resp.content),
                "status": "OK",
                "usage": usage,
            }
        except Exception as exc:
            logger.warning("UnifiedInvoker.invoke_raw failed: %s", exc)
            logger.debug("invoke_raw traceback:", exc_info=True)
            return {
                "raw": "",
                "status": "FAILED_AFTER_RETRIES",
                "error": str(exc),
            }

    def invoke_spec(
        self,
        spec_id: str,
        inputs: dict[str, Any],
        *,
        config: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Heavy path — load prompt, render, invoke, parse, validate, log, retry.

        Delegates to a lazily-built ``Phase1LLMInvoker`` child that owns the
        prompt-load / parse / validate / retry machinery. The
        ``config`` kwarg is reserved for future use — the child already has
        the Langfuse handler baked into its constructor, matching CORR-011
        semantics.

        Args:
            spec_id: Canonical Phase 1 LLM ID.
            inputs: Forwarded to the heavy invoker as prompt inputs.
            config: Optional LangChain RunnableConfig.
            state: Optional pipeline state (CORR-061 S3b). When provided,
                the raw markdown response is captured into
                ``state["per_spec_markdown"][spec_id]``. Pass ``None`` to
                disable capture (test paths).

        Probes Ollama before delegating (cached for
        ``_PROBE_TTL_SECONDS``); raises :class:`LLMUnreachableError`
        when down — no retry, no log spam (CORR-015). The heavy child also
        re-probes as defense-in-depth.
        """
        self._ensure_ollama("invoke_spec")
        heavy = self._get_heavy()
        return heavy.invoke(spec_id, inputs, config=config, state=state)

    def invoke(
        self,
        prompt_or_spec_id: str,
        inputs: Any = None,
        *,
        feedback: str = "",
        config: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Polymorphic dispatcher.

        Distinguishes the two call-site shapes by the type of ``inputs``:

        - ``invoke(spec_id, inputs_dict, state=state)` → :meth:`invoke_spec` (heavy)
        - ``invoke(prompt, feedback="...", config={...})` →
          :meth:`invoke_raw` (light)

        This preserves backward compatibility with both
        ``Phase1LLMInvoker.invoke(spec_id, inputs, state=state)`` (heavy) and
        ``UnifiedInvoker.invoke_raw(prompt)`` (light) without changing any
        caller in the tree.

        CORR-062 S1 fix: ``state`` kwarg was added to the 9 call sites in
        ``phase1_executor.py`` during CORR-061 S3b but the dispatcher
        signature and forward were not updated; this is the 2-line
        forwarder that closes the gap.
        """
        if isinstance(inputs, dict):
            return self.invoke_spec(prompt_or_spec_id, inputs, config=config, state=state)
        return self.invoke_raw(
            prompt_or_spec_id,
            feedback=feedback,
            config=config,
        )

    def _get_heavy(self) -> Any:
        """Lazy-build the underlying ``Phase1LLMInvoker`` child.

        The first call constructs it from the loaders/handlers passed at
        construction time; subsequent calls return the cached instance.
        The heavy child owns its own ``prompts_root`` (resolved via the
        supplied ``prompt_loader``), so the unified wrapper does not have
        to know about prompt directory conventions.
        """
        if self._heavy is not None:
            return self._heavy

        from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker
        from aegis_phase1.prompts_v2.loader import PromptLoader

        prompt_loader = self.prompts
        if prompt_loader is None:
            if self._prompts_root is None:
                raise RuntimeError(
                    "UnifiedInvoker.invoke_spec requires a prompt_loader or "
                    "prompts_root; neither was supplied at construction."
                )
            prompt_loader = PromptLoader(root=self._prompts_root)
            self.prompts = prompt_loader

        self._heavy = Phase1LLMInvoker(
            prompt_loader=prompt_loader,
            catalog_loader=self.catalogs,
            validator=self.validator,
            llm_logger=self.llm_logger,
            format_logger=self.format_logger,
            model=self.model,
            base_url=self.base_url,
            langfuse_handler=self._langfuse_handler,
            provider=self.provider,  # CORR-062 S2: pass through to heavy
        )
        return self._heavy

    def _ensure_ollama(self, source: str) -> None:
        """Probe the chat backend; raise ``LLMUnreachableError`` if down.

        Caches the probe result for ``_PROBE_TTL_SECONDS`` to avoid probing
        on every invocation when many calls happen in sequence.

        CORR-062 S2: the probe is provider-aware. For the Ollama path we
        GET ``/api/version``; for the MiniMax path we skip the probe
        entirely (the Mavis gateway has no equivalent version endpoint,
        and the LLM call itself will fail-fast with an HTTP error if
        the API is down).
        """
        # CORR-062 S2: MiniMax / Mavis gateway has no ``/api/version``
        # equivalent — skip the probe. The first real call will surface
        # any network / auth / model errors as HTTPStatusError, which
        # invoke_raw / invoke_spec already handle.
        # CORR-106: same exemption for the transformers path — no HTTP
        # server is involved; if the model fails to load, the first
        # ``.invoke()`` raises and the invoker wraps it as a soft
        # ``FAILED_AFTER_RETRIES`` like any other backend error.
        if self.provider != "ollama":
            return

        now = time.time()
        if (
            self._ollama_reachable is not None
            and (now - self._ollama_probe_ts) < _PROBE_TTL_SECONDS
        ):
            if not self._ollama_reachable:
                raise LLMUnreachableError(self.base_url, source)
            return
        reachable = probe_ollama(self.base_url)
        self._ollama_reachable = reachable
        self._ollama_probe_ts = now
        if not reachable:
            raise LLMUnreachableError(self.base_url, source)


__all__ = [
    "LLMUnreachableError",
    "UnifiedInvoker",
    "_extract_usage",
    "_merge_handler_into_config",
    "probe_ollama",
]
