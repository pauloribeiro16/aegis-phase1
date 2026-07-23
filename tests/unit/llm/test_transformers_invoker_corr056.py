"""Unit tests for TransformersInvoker (CORR-056).

These tests mock the HF transformers library so we don't actually load
the 9.6GB gemma-4-E2B-it model — the goal is to verify the contract
of :class:`aegis_phase1.llm.transformers_invoker.TransformersInvoker`:

  - Lazy load (init does NOT load the model)
  - invoke() loads + calls generate + decodes
  - Returns canonical ``{"raw", "status", "usage"}`` dict
  - Feedback is appended to prompt on retry
  - ``_strip_hf_prefix`` / ``_detect_provider`` utilities work correctly
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


class _FakeTensor:
    """Minimal stand-in for a torch.Tensor supporting [int] + [slice] + .shape.

    HF's ``model.generate`` returns a tensor; the invoker indexes it as
    ``outputs[0][input_len:]`` then accesses ``.shape[-1]``. The MagicMock
    default can't model two-level slicing cleanly, so we use this class.

    Indexing rules (matching torch):
      - ``t[int]``  → drops one dim, returns a tensor with one fewer dim
      - ``t[slice]`` → keeps dims, slices along dim 0
    """
    def __init__(self, shape):
        self.shape = tuple(shape)

    def __getitem__(self, key):
        # int indexing drops a dim
        if isinstance(key, int):
            new_shape = self.shape[1:]
            return _FakeTensor(new_shape)
        # slice indexing keeps dims, slices along dim 0
        if isinstance(key, slice):
            dim0 = self.shape[0] if self.shape else 0
            start, stop, _ = key.indices(dim0)
            n = max(0, stop - start)
            new_shape = (n,) + self.shape[1:]
            return _FakeTensor(new_shape)
        # tuple indexing: e.g. (0, slice(5, None))
        if isinstance(key, tuple):
            t = self
            for k in key:
                t = t[k]
            return t
        return self


# ─── helpers ────────────────────────────────────────────────────────────


def _install_transformers_stub(monkeypatch):
    """Install a fake ``transformers`` module so the invoker can import.

    The fake exposes ``AutoTokenizer`` and ``AutoModelForCausalLM`` as
    MagicMocks, so calls into HF return controlled values.
    """
    fake_tf = types.ModuleType("transformers")

    fake_tokenizer = MagicMock(name="AutoTokenizer")
    fake_model_cls = MagicMock(name="AutoModelForCausalLM")

    fake_tf.AutoTokenizer = fake_tokenizer
    fake_tf.AutoModelForCausalLM = fake_model_cls

    monkeypatch.setitem(sys.modules, "transformers", fake_tf)
    return fake_tf, fake_tokenizer, fake_model_cls


def _make_invoker(monkeypatch, **kwargs):
    """Build a TransformersInvoker with stubbed transformers imports.

    Each call gets fresh MagicMock instances for tokenizer + model.
    """
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    inv = TransformersInvoker("google/gemma-4-E2B-it", **kwargs)
    return inv, *sys.modules["transformers"].__dict__["AutoTokenizer"].return_value, \
        sys.modules["transformers"].__dict__["AutoModelForCausalLM"].return_value


# ─── utility functions ──────────────────────────────────────────────────


def test_strip_hf_prefix():
    from aegis_phase1.llm.transformers_invoker import _strip_hf_prefix

    assert _strip_hf_prefix("hf:google/gemma-4-E2B-it") == "google/gemma-4-E2B-it"
    assert _strip_hf_prefix("google/gemma-4-E2B-it") == "google/gemma-4-E2B-it"
    assert _strip_hf_prefix("gemma4:e4b") == "gemma4:e4b"
    assert _strip_hf_prefix("") == ""


def test_detect_provider_ollama():
    from aegis_phase1.llm.transformers_invoker import _detect_provider

    assert _detect_provider("gemma4:e4b") == "ollama"
    assert _detect_provider("gemma4:e2b") == "ollama"
    assert _detect_provider(None) == "ollama"
    assert _detect_provider("") == "ollama"


def test_detect_provider_transformers():
    from aegis_phase1.llm.transformers_invoker import _detect_provider

    assert _detect_provider("google/gemma-4-E2B-it") == "transformers"
    assert _detect_provider("hf:google/gemma-4-E2B-it") == "transformers"
    assert _detect_provider("meta-llama/Llama-3-8B") == "transformers"


# ─── TransformersInvoker class ──────────────────────────────────────────


def test_init_does_not_load_model(monkeypatch):
    """``__init__`` must NOT trigger HF downloads — lazy load on first invoke."""
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    inv = TransformersInvoker("google/gemma-4-E2B-it")

    tf = sys.modules["transformers"]
    tf.AutoTokenizer.from_pretrained.assert_not_called()
    tf.AutoModelForCausalLM.from_pretrained.assert_not_called()
    assert inv.model_id == "google/gemma-4-E2B-it"
    assert inv._model is None
    assert inv._tokenizer is None


def test_init_strips_hf_prefix(monkeypatch):
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    inv = TransformersInvoker("hf:google/gemma-4-E2B-it")
    assert inv.model == "google/gemma-4-E2B-it"
    assert inv.model_id == "google/gemma-4-E2B-it"


def test_init_uses_hf_home_env(monkeypatch):
    _install_transformers_stub(monkeypatch)
    monkeypatch.setenv("HF_HOME", "/tmp/custom-hf-cache")
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    assert inv.cache_dir == "/tmp/custom-hf-cache"


def test_init_uses_default_cache_when_no_env(monkeypatch):
    _install_transformers_stub(monkeypatch)
    monkeypatch.delenv("HF_HOME", raising=False)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker, _DEFAULT_HF_HOME

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    assert inv.cache_dir == _DEFAULT_HF_HOME
    assert _DEFAULT_HF_HOME.startswith("/media")  # CORR-056: 500G disk


def _mocked_tokenizer_with_to(tokenizer_mock, n_input_tokens: int = 5):
    """Configure a tokenizer mock so its ``__call__`` returns a MagicMock with
    ``.to()`` (matching HF real behavior — returns a ModelInputs-like object)."""
    tokenizer_mock.apply_chat_template.return_value = "<formatted chat>"
    input_ids_mock = MagicMock(shape=(-1, n_input_tokens))
    fake_inputs = MagicMock(name="tokenizer_output")
    fake_inputs.input_ids = input_ids_mock
    # Also support dict-style access: inputs["input_ids"] → same mock
    fake_inputs.__getitem__.return_value = input_ids_mock
    fake_inputs.to.return_value = fake_inputs  # .to(device) returns self
    tokenizer_mock.return_value = fake_inputs
    return fake_inputs


def _mocked_model_with_generate(model_mock, n_input_tokens: int = 5, n_output_tokens: int = 8):
    """Configure a model mock so its ``generate()`` returns a tensor-like with
    proper indexing and the model exposes ``.parameters()`` for device resolution.

    The output tensor has shape ``(1, n_input_tokens + n_output_tokens)``:
      - ``outputs[0]`` drops dim 0 → shape ``(n_input_tokens + n_output_tokens,)``
      - ``outputs[0][input_len:]`` slices dim 0 → shape ``(n_output_tokens,)``
    """
    output_tensor = _FakeTensor(shape=(1, n_input_tokens + n_output_tokens))
    model_mock.generate.return_value = output_tensor

    param_mock = MagicMock()
    param_mock.device = "cpu"
    model_mock.parameters.return_value = iter([param_mock])
    return output_tensor


def test_invoke_loads_and_returns_canonical_dict(monkeypatch):
    """invoke() loads model (lazy) + returns {raw, status, usage}."""
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    tf = sys.modules["transformers"]

    tokenizer = tf.AutoTokenizer.from_pretrained.return_value
    _mocked_tokenizer_with_to(tokenizer, n_input_tokens=5)
    tokenizer.decode.return_value = "Why did the computer break up with the RAM? Because it felt too overloaded!"

    model = tf.AutoModelForCausalLM.from_pretrained.return_value
    _mocked_model_with_generate(model, n_input_tokens=5, n_output_tokens=8)

    inv = TransformersInvoker("google/gemma-4-E2B-it", max_new_tokens=128)
    result = inv.invoke("Write a joke about RAM.")

    # Verify the load happened
    tf.AutoTokenizer.from_pretrained.assert_called_once()
    tf.AutoModelForCausalLM.from_pretrained.assert_called_once()

    # Verify result shape (matches UnifiedInvoker.invoke_raw contract)
    assert result["status"] == "OK"
    assert "raw" in result
    assert "usage" in result
    assert result["usage"]["prompt_tokens"] == 5
    assert result["usage"]["completion_tokens"] == 8
    assert result["usage"]["total_tokens"] == 13
    assert "RAM" in result["raw"] or "overloaded" in result["raw"]


def test_invoke_appends_feedback_on_retry(monkeypatch):
    """``feedback`` arg is appended to user content (CORR-056 retry path)."""
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    tf = sys.modules["transformers"]
    tokenizer = tf.AutoTokenizer.from_pretrained.return_value
    _mocked_tokenizer_with_to(tokenizer, n_input_tokens=3)
    tokenizer.decode.return_value = "retry output"
    model = tf.AutoModelForCausalLM.from_pretrained.return_value
    _mocked_model_with_generate(model, n_output_tokens=2)

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    inv.invoke("Original prompt.", feedback="missing Status section")

    # The chat template should have received a user message containing both
    # the original prompt AND the feedback marker.
    call_args = tokenizer.apply_chat_template.call_args
    messages = call_args[0][0]  # first positional arg
    assert len(messages) == 1
    user_content = messages[0]["content"]
    assert "Original prompt." in user_content
    assert "missing Status section" in user_content
    assert "Previous attempt failed" in user_content


def test_invoke_disable_thinking_passed_to_chat_template(monkeypatch):
    """enable_thinking=False (default) is passed to apply_chat_template."""
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    tf = sys.modules["transformers"]
    tokenizer = tf.AutoTokenizer.from_pretrained.return_value
    _mocked_tokenizer_with_to(tokenizer, n_input_tokens=1)
    tokenizer.decode.return_value = "ok"
    model = tf.AutoModelForCausalLM.from_pretrained.return_value
    _mocked_model_with_generate(model, n_output_tokens=1)

    inv = TransformersInvoker("google/gemma-4-E2B-it", enable_thinking=False)
    inv.invoke("hi")

    kwargs = tokenizer.apply_chat_template.call_args.kwargs
    assert kwargs.get("enable_thinking") is False


def test_invoke_uses_deterministic_generation(monkeypatch):
    """do_sample=False for compliance-grade determinism (CORR-056)."""
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    tf = sys.modules["transformers"]
    tokenizer = tf.AutoTokenizer.from_pretrained.return_value
    _mocked_tokenizer_with_to(tokenizer, n_input_tokens=1)
    tokenizer.decode.return_value = "ok"
    model = tf.AutoModelForCausalLM.from_pretrained.return_value
    _mocked_model_with_generate(model, n_output_tokens=1)

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    inv.invoke("hi")

    gen_kwargs = model.generate.call_args.kwargs
    assert gen_kwargs.get("do_sample") is False


# ─── build_llm_invoker integration (provider auto-detect) ───────────────


def test_build_llm_invoker_auto_detects_transformers_from_slash(monkeypatch):
    """Model name with ``/`` (HF Hub) → TransformersInvoker, even without MOCK_LLM."""
    _install_transformers_stub(monkeypatch)
    # Need to be in MOCK_LLM=false to reach the auto-detect branch
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from aegis_phase1.v2.llm import build_llm_invoker, TransformersInvoker

    inv = build_llm_invoker(model="google/gemma-4-E2B-it")
    assert isinstance(inv, TransformersInvoker)
    assert inv.model_id == "google/gemma-4-E2B-it"


def test_build_llm_invoker_explicit_provider_ollama(monkeypatch):
    """``provider='ollama'`` overrides auto-detect → UnifiedInvoker (Ollama)."""
    _install_transformers_stub(monkeypatch)
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from aegis_phase1.v2.llm import build_llm_invoker, UnifiedInvoker

    # Use a real, valid Ollama model name; UnifiedInvoker is built (no probe yet)
    inv = build_llm_invoker(model="google/gemma-4-E2B-it", provider="ollama")
    assert isinstance(inv, UnifiedInvoker)
    assert inv.model == "google/gemma-4-E2B-it"


def test_build_llm_invoker_explicit_provider_transformers(monkeypatch):
    """``provider='transformers'`` works even on Ollama-shaped names."""
    _install_transformers_stub(monkeypatch)
    monkeypatch.delenv("MOCK_LLM", raising=False)
    from aegis_phase1.v2.llm import build_llm_invoker, TransformersInvoker

    inv = build_llm_invoker(model="gemma4:e4b", provider="transformers")
    assert isinstance(inv, TransformersInvoker)
    assert inv.model_id == "gemma4:e4b"


def test_build_llm_invoker_mock_overrides_provider(monkeypatch):
    """``MOCK_LLM=true`` wins over explicit provider."""
    monkeypatch.setenv("MOCK_LLM", "true")
    from aegis_phase1.v2.llm import build_llm_invoker, MockInvoker

    inv = build_llm_invoker(
        model="google/gemma-4-E2B-it", provider="transformers"
    )
    assert isinstance(inv, MockInvoker)


# ─── GPU memory optimisation (CORR-056 extension) ──────────────────────


def test_max_memory_uses_90_percent_of_vram_by_default(monkeypatch):
    """_max_memory caps GPU usage at gpu_memory_utilization (default 0.9) of total VRAM."""
    _install_transformers_stub(monkeypatch)
    import torch

    # Fake CUDA available + 7.6GB total VRAM (RTX 2070)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    fake_props = MagicMock()
    fake_props.total_memory = 7.6 * 1024**3  # 7.6 GiB in bytes
    monkeypatch.setattr(torch.cuda, "get_device_properties", lambda _idx: fake_props)

    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    budget = inv._max_memory()
    assert budget is not None
    assert 0 in budget
    assert "cpu" in budget
    # 7.6 * 0.9 - 0.2 (safety) = 6.64 GiB → formatted as "6.6GiB"
    assert "GiB" in budget[0]
    assert float(budget[0].rstrip("GiB")) < 7.6  # below total
    assert float(budget[0].rstrip("GiB")) >= 1.0  # above the 1GiB floor


def test_max_memory_respects_custom_utilization(monkeypatch):
    """gpu_memory_utilization=0.7 caps at 70% of VRAM."""
    _install_transformers_stub(monkeypatch)
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    fake_props = MagicMock()
    fake_props.total_memory = 8.0 * 1024**3
    monkeypatch.setattr(torch.cuda, "get_device_properties", lambda _idx: fake_props)

    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    inv = TransformersInvoker(
        "google/gemma-4-E2B-it", gpu_memory_utilization=0.7
    )
    budget = inv._max_memory()
    # 8.0 * 0.7 - 0.2 = 5.4 GiB
    assert float(budget[0].rstrip("GiB")) == pytest.approx(5.4, abs=0.1)


def test_max_memory_returns_none_without_cuda(monkeypatch):
    """No CUDA → max_memory=None (let accelerate default to full CPU)."""
    _install_transformers_stub(monkeypatch)
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    assert inv._max_memory() is None


def test_default_attn_implementation_is_sdpa(monkeypatch):
    """attn_implementation defaults to 'sdpa' (memory-efficient attention)."""
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    assert inv.attn_implementation == "sdpa"


def test_default_dtype_is_auto_resolves_to_bfloat16(monkeypatch):
    """dtype='auto' (default) → torch.bfloat16 in _ensure_loaded (Gemma 4 native)."""
    _install_transformers_stub(monkeypatch)
    import torch

    fake_tokenizer = MagicMock()
    fake_model = MagicMock()
    fake_model.parameters.return_value = iter([MagicMock(device="cpu")])
    fake_tokenizer.return_value = MagicMock()
    fake_tokenizer.return_value.input_ids = MagicMock(shape=(-1, 1))
    fake_tokenizer.return_value.to.return_value = fake_tokenizer.return_value
    fake_model.generate.return_value = MagicMock()
    fake_model.generate.return_value.__getitem__.return_value = MagicMock(shape=(-1, 1))
    fake_tokenizer.apply_chat_template.return_value = "<chat>"
    fake_tokenizer.decode.return_value = "ok"

    import sys
    fake_tf = sys.modules["transformers"]
    fake_tf.AutoTokenizer.from_pretrained.return_value = fake_tokenizer
    fake_tf.AutoModelForCausalLM.from_pretrained.return_value = fake_model

    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    inv.invoke("hi")

    # dtype='auto' → resolved to torch.bfloat16
    from_pretrained_kwargs = fake_tf.AutoModelForCausalLM.from_pretrained.call_args.kwargs
    assert from_pretrained_kwargs["dtype"] == torch.bfloat16
    # attn_implementation='sdpa' (default) threaded through
    assert from_pretrained_kwargs["attn_implementation"] == "sdpa"
    # max_memory threaded through
    assert "max_memory" in from_pretrained_kwargs
    # low_cpu_mem_usage=True
    assert from_pretrained_kwargs["low_cpu_mem_usage"] is True


def test_invoke_with_system_prompt_separate_role(monkeypatch):
    """system_prompt= arg is passed as a separate 'system' role message (CORR-056 v2).

    This is the FAIR-comparison path: same as langchain's SystemMessage
    for Ollama, so the P1B-LLM-01 system spec is honoured as a system
    role instead of being merged into user content.
    """
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    tf = sys.modules["transformers"]
    tokenizer = tf.AutoTokenizer.from_pretrained.return_value
    _mocked_tokenizer_with_to(tokenizer, n_input_tokens=1)
    tokenizer.decode.return_value = "ok"
    model = tf.AutoModelForCausalLM.from_pretrained.return_value
    _mocked_model_with_generate(model, n_output_tokens=1)

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    inv.invoke("user message", system_prompt="you are a compliance analyst")

    call_args = tokenizer.apply_chat_template.call_args
    messages = call_args[0][0]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "you are a compliance analyst"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "user message"


def test_invoke_without_system_prompt_keeps_legacy_user_only(monkeypatch):
    """Without system_prompt= (default), behaviour is the legacy single-user path."""
    _install_transformers_stub(monkeypatch)
    from aegis_phase1.llm.transformers_invoker import TransformersInvoker

    tf = sys.modules["transformers"]
    tokenizer = tf.AutoTokenizer.from_pretrained.return_value
    _mocked_tokenizer_with_to(tokenizer, n_input_tokens=1)
    tokenizer.decode.return_value = "ok"
    model = tf.AutoModelForCausalLM.from_pretrained.return_value
    _mocked_model_with_generate(model, n_output_tokens=1)

    inv = TransformersInvoker("google/gemma-4-E2B-it")
    inv.invoke("just a user message")

    call_args = tokenizer.apply_chat_template.call_args
    messages = call_args[0][0]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "just a user message"
