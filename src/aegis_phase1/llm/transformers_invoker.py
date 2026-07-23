"""Transformers-based LLM invoker (CORR-056).

Alternative to :class:`aegis_phase1.llm.unified.UnifiedInvoker` (which
targets Ollama). Uses Hugging Face ``transformers`` directly to load
and run models from the Hub — useful for testing against canonical
research models (e.g. ``google/gemma-4-E2B-it``) without requiring
Ollama to be installed locally.

Interface:
    Same :meth:`invoke` signature as ``UnifiedInvoker.invoke_raw``:
        ``invoke(prompt: str, feedback: str = "") -> {"raw", "status", "usage"}``

CORR-056 (2026-07-23): added as opt-in provider. ``Ollama`` remains the
default; transformers is selected via ``provider="transformers"`` or by
passing a model name with the ``hf:`` prefix (or containing ``/``).

Multimodal note:
    The Phase 1 pipeline is text-only (regulatory analysis). Even though
    Gemma 4 E2B is multimodal, this invoker only sends text content via
    the chat template. We use ``AutoTokenizer`` + ``AutoModelForCausalLM``
    (NOT the multimodal ``AutoProcessor`` / ``AutoModelForMultimodalLM``)
    to skip the image processor chain (which requires ``torchvision``).
    The language model head is identical in both wrappers, so text-only
    inference is unaffected.

Lazy load:
    The tokenizer + model are loaded on first :meth:`invoke` call (not
    in ``__init__``). This makes the class cheap to instantiate in tests
    that mock the model — you can ``TransformersInvoker(model_id="x")``
    without any HF download until you actually call ``invoke()``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


# Env var name → cache directory. Default matches the path used in CORR-056
# on the 500G disk so the model + cache stays off the SSD.
_HF_HOME_ENV = "HF_HOME"
_DEFAULT_HF_HOME = "/media/epmq-cyber/191a70fe-626c-409b-a8ca-caed8a953c33/hf_cache"


def _strip_hf_prefix(model: str) -> str:
    """Strip the ``hf:`` prefix used in CLI choices to mark HF Hub models.

    >>> _strip_hf_prefix("hf:google/gemma-4-E2B-it")
    'google/gemma-4-E2B-it'
    """
    if model.startswith("hf:"):
        return model[3:]
    return model


def _detect_provider(model: str | None) -> str:
    """Auto-detect provider from model name.

    Returns ``"transformers"`` if the model name contains ``/`` (HF Hub
    convention: ``org/repo``) or has the ``hf:`` prefix; otherwise
    ``"ollama"`` (default).

    >>> _detect_provider("google/gemma-4-E2B-it")
    'transformers'
    >>> _detect_provider("hf:google/gemma-4-E2B-it")
    'transformers'
    >>> _detect_provider("gemma4:e4b")
    'ollama'
    """
    if not model:
        return "ollama"
    if model.startswith("hf:") or "/" in model:
        return "transformers"
    return "ollama"


class TransformersInvoker:
    """LLM invoker backed by Hugging Face ``transformers`` (text-only path).

    Args:
        model_id: HF Hub model identifier (e.g. ``"google/gemma-4-E2B-it"``).
            The ``hf:`` prefix is accepted and stripped.
        max_new_tokens: Max tokens to generate per call. Default 1024.
        enable_thinking: Whether to enable Gemma 4's native thinking mode.
            Default ``False`` (matches Phase 1's non-reasoning expectations).
        cache_dir: HF cache directory. Default: ``$HF_HOME`` or the
            CORR-056 default on the 500G disk.
        device_map: Device map for ``from_pretrained``. Default ``"auto"``
            (GPU if available, else CPU).
        dtype: torch dtype string (``"auto"``, ``"bfloat16"``, ``"float16"``).
            Default ``"auto"``.

    Attributes:
        model: Resolved HF Hub model id (without ``hf:`` prefix).
        model_id: Alias for :attr:`model`.
        device: Resolved torch device after model load (set lazily).
        max_new_tokens: As passed to constructor.
        enable_thinking: As passed to constructor.
        cache_dir: Resolved cache directory.
    """

    DEFAULT_MAX_NEW_TOKENS = 1024
    DEFAULT_DEVICE_MAP = "auto"
    DEFAULT_DTYPE = "auto"

    def __init__(
        self,
        model_id: str,
        *,
        max_new_tokens: int | None = None,
        enable_thinking: bool = False,
        cache_dir: str | None = None,
        device_map: str | None = None,
        dtype: str | None = None,
        attn_implementation: str | None = None,
        gpu_memory_utilization: float | None = None,
    ) -> None:
        """Build a TransformersInvoker.

        Args:
            model_id: HF Hub model identifier (e.g. ``"google/gemma-4-E2B-it"``).
                The ``hf:`` prefix is accepted and stripped.
            max_new_tokens: Max tokens to generate per call. Default 1024.
            enable_thinking: Whether to enable Gemma 4's native thinking mode.
                Default ``False`` (matches Phase 1's non-reasoning expectations).
            cache_dir: HF cache directory. Default: ``$HF_HOME`` or the
                CORR-056 default on the 500G disk.
            device_map: Device map for ``from_pretrained``. Default ``"auto"``
                (GPU if available, else CPU).
            dtype: torch dtype string (``"auto"``, ``"bfloat16"``, ``"float16"``).
                Default ``"auto"`` (resolves to ``torch.bfloat16``).
            attn_implementation: Attention implementation. Default ``"sdpa"``
                (Scaled Dot-Product Attention; ~30% less VRAM than eager).
                Pass ``"eager"`` if SDPA is not supported on your GPU.
            gpu_memory_utilization: Fraction of GPU VRAM (0-1) to use for
                model weights. Default 0.9 (leaves 10% for KV cache +
                activations during generate). Increase to 0.95 if you
                see headroom; lower to 0.7 if you OOM during generate.
        """
        self.model = _strip_hf_prefix(model_id)
        self.model_id = self.model
        self.max_new_tokens = max_new_tokens or self.DEFAULT_MAX_NEW_TOKENS
        self.enable_thinking = enable_thinking
        self.cache_dir = (
            cache_dir
            or os.environ.get(_HF_HOME_ENV)
            or _DEFAULT_HF_HOME
        )
        self.device_map = device_map or self.DEFAULT_DEVICE_MAP
        self.dtype = dtype or self.DEFAULT_DTYPE
        self.attn_implementation = attn_implementation or "sdpa"
        self.gpu_memory_utilization = (
            gpu_memory_utilization
            if gpu_memory_utilization is not None
            else 0.9
        )

        # Lazy-loaded on first invoke() call.
        self._tokenizer: Any = None
        self._model: Any = None
        self._device: Any | None = None

    def _max_memory(self) -> dict[Any, str] | None:
        """Compute the ``max_memory`` budget for ``from_pretrained``.

        Returns:
            ``{"0": "<X>GiB", "cpu": "30GiB"}`` when CUDA is available —
            accelerates distributes layers to fit within these caps, putting
            the maximum possible on GPU without OOM during generate.

            ``None`` when CUDA is unavailable (lets accelerate default to
            full CPU).

        The GPU cap is computed from
        ``total_VRAM * self.gpu_memory_utilization`` minus a 200MB safety
        margin for activations. 30 GiB on CPU is the standard
        accelerate-suggested budget for laptops.
        """
        import torch

        if not torch.cuda.is_available():
            return None
        try:
            total = torch.cuda.get_device_properties(0).total_memory
        except Exception:
            return None
        # Convert bytes → GiB, apply utilization, subtract 200MB safety
        budget_gib = (total / 1024**3) * self.gpu_memory_utilization - 0.2
        budget_gib = max(1.0, budget_gib)  # never below 1GiB
        return {0: f"{budget_gib:.1f}GiB", "cpu": "30GiB"}

    @property
    def device(self) -> Any:
        """Resolved torch device (set on first invoke)."""
        if self._device is None:
            import torch
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return self._device

    def _ensure_loaded(self) -> None:
        """Lazy-load tokenizer + model. Called by :meth:`invoke`.

        CORR-056: uses ``AutoTokenizer`` (text-only path) instead of
        ``AutoProcessor``. The Gemma 4 ``Gemma4Processor`` requires
        ``torchvision`` at import time (multimodal image processor
        chain), which we don't need for Phase 1's text-only regulatory
        analysis. The tokenizer is shared across ``gemma``/``gemma2``/
        ``gemma3``/``gemma4`` so text-only inference works correctly.

        Loading strategy (CORR-056, optimised for max GPU usage):
          - ``torch_dtype=torch.bfloat16`` (halves VRAM vs FP32; Gemma 4
            is trained in BF16 — no precision loss)
          - ``attn_implementation="sdpa"`` (Scaled Dot-Product Attention;
            ~30% less VRAM than the eager default on supported GPUs)
          - ``max_memory={"0": "<X>GiB", "cpu": "30GiB"}`` (cap GPU usage
            to leave headroom for KV cache during generate; remainder
            offloaded to CPU. Without this, accelerate's "auto" tends
            to over-offload.)
          - ``device_map="auto"`` (accelerate distributes layers per
            the ``max_memory`` budget)
          - ``low_cpu_mem_usage=True`` (avoid peak RAM spike during load)
        """
        if self._model is not None and self._tokenizer is not None:
            return

        import torch

        logger.info(
            "TransformersInvoker: loading model_id=%s (cache_dir=%s, device_map=%s, "
            "dtype=%s, attn=%s, max_memory=%s)",
            self.model_id,
            self.cache_dir,
            self.device_map,
            self.dtype,
            self.attn_implementation,
            self._max_memory(),
        )

        # Free any cached allocations from previous loads
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Import here to keep module import cheap (avoid pulling torch on every import)
        from transformers import AutoTokenizer, AutoModelForCausalLM

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id, cache_dir=self.cache_dir
        )

        # Resolve dtype: "auto" → torch.bfloat16 (the CORR-056 default; Gemma 4
        # was trained in BF16, so no precision loss).
        torch_dtype: Any
        if self.dtype == "auto":
            torch_dtype = torch.bfloat16
        elif isinstance(self.dtype, str):
            torch_dtype = getattr(torch, self.dtype)
        else:
            torch_dtype = self.dtype

        # AutoModelForCausalLM (not AutoModelForMultimodalLM) — the LM head
        # works on text tokens alone, regardless of the multimodal wrapper.
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            dtype=torch_dtype,
            device_map=self.device_map,
            cache_dir=self.cache_dir,
            attn_implementation=self.attn_implementation,
            max_memory=self._max_memory(),
            low_cpu_mem_usage=True,
        )
        # Refresh device after model load (model may live on cuda:0, cuda:1, etc.)
        try:
            self._device = next(self._model.parameters()).device
        except StopIteration:
            pass
        # Report actual GPU usage so the user sees the split
        if torch.cuda.is_available():
            used = torch.cuda.memory_allocated() / 1024**3
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(
                "TransformersInvoker: model loaded on device=%s — "
                "GPU memory: %.1fGB / %.1fGB (%.0f%% of VRAM)",
                self._device, used, total, 100 * used / total,
            )
        else:
            logger.info(
                "TransformersInvoker: model loaded on device=%s (CPU only — no CUDA)",
                self._device,
            )

    def invoke(
        self,
        prompt: str,
        feedback: str = "",
        *,
        system_prompt: str | None = None,
        config: Any = None,
    ) -> dict[str, Any]:
        """Run one text-only chat completion.

        Args:
            prompt: The user message content.
            feedback: Optional error feedback from a previous failed
                attempt (Phase 1 retry path). When non-empty, appended
                to the user content with a ``[Previous attempt failed]``
                marker.
            system_prompt: Optional system message (CORR-056 fair-comparison
                mode). When supplied, the chat template receives
                ``[{"role": "system", ...}, {"role": "user", ...}]``,
                so the system role is honoured instead of being merged
                into the user content. When ``None`` (default), the
                behaviour is the legacy single-user-message path.
            config: Accepted for signature parity with
                :class:`UnifiedInvoker`. Not used by transformers (no
                LangChain callbacks); ignored.

        Returns:
            Canonical ``{"raw": str, "status": "OK", "usage": dict}`` dict.
            Matches the shape ``UnifiedInvoker.invoke_raw`` returns.
        """
        self._ensure_loaded()

        user_content = prompt
        if feedback:
            user_content = (
                f"{prompt}\n\n"
                f"[Previous attempt failed: {feedback}]\n"
                f"Please try again with the correct format."
            )

        # Build the messages list — system role is preserved when supplied.
        if system_prompt is not None:
            messages: list[dict[str, str]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
        else:
            messages = [{"role": "user", "content": user_content}]

        # Gemma 4 tokenizer has apply_chat_template; build the chat-formatted
        # text string and tokenize it. For thinking mode, the tokenizer handles
        # the special control tokens automatically.
        t0 = time.perf_counter()

        chat_text: str
        try:
            chat_text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=self.enable_thinking,
            )
        except TypeError:
            # Older tokenizer signature without enable_thinking kwarg.
            chat_text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = self._tokenizer(
            chat_text,
            return_tensors="pt",
            add_special_tokens=False,
        ).to(self._device)
        input_len = inputs["input_ids"].shape[-1]

        outputs = self._model.generate(
            **inputs,
            max_new_tokens=self.max_new_tokens,
            do_sample=False,  # deterministic for compliance review
        )
        output_ids = outputs[0][input_len:]
        raw = self._tokenizer.decode(output_ids, skip_special_tokens=True)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        usage = {
            "prompt_tokens": int(input_len),
            "completion_tokens": int(output_ids.shape[-1]),
            "total_tokens": int(input_len + output_ids.shape[-1]),
        }
        logger.info(
            "TransformersInvoker: model_id=%s status=OK latency_ms=%d "
            "prompt_tokens=%d completion_tokens=%d",
            self.model_id,
            latency_ms,
            usage["prompt_tokens"],
            usage["completion_tokens"],
        )
        return {"raw": raw, "status": "OK", "usage": usage}


__all__ = [
    "TransformersInvoker",
    "_strip_hf_prefix",
    "_detect_provider",
]
