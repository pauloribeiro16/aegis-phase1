"""Tests for CORR-111 — quant frontmatter & model_capabilities in Phase1LLMInvoker.

Verified:
  T1.  ``_capture_per_spec_markdown`` prepends a single-line aegis:
       frontmatter on first write and is IDEMPOTENT on re-runs.
  T2.  It records the active quant under ``state["v2_model_capabilities"]``
       on the first call only.
  T3.  Subsequent calls for the same spec_id APPEND with ``\\n---\\n`` and
       do NOT duplicate the frontmatter.
  T4.  When a manifest exists on disk under
       ``AEGIS_QUANT_MANIFEST_ROOT``, the recorded quant reflects it.
  T5.  When no manifest exists, ``provider="ollama"`` records
       ``provider_default`` (per user decision 2026-09-02).
  T6.  When no manifest exists for ``provider="vllm"`` or
       ``provider="transformers"``, the recorded quant is ``unknown`` (those
       providers must declare explicitly — we don't silently fill in).
  T7.  ``AEGIS_JOB_ID`` env var wins over ``SLURM_JOB_ID``; both absent
       means ``"unknown"``.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aegis_phase1.llm import quant_manifest as qm
from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker


@pytest.fixture
def invoker() -> Phase1LLMInvoker:
    """Build a no-op invoker whose actual LLM call we never run."""
    # We never call .invoke() — only the helper methods. So the prompt loader
    # is allowed to be a MagicMock and the provider/model are fixed for test
    # stability.
    inv = Phase1LLMInvoker.__new__(Phase1LLMInvoker)
    inv.model = "qwen3.5:27b"
    inv.provider = "ollama"
    return inv


def _write_manifest(root: Path, *, model: str, provider: str, quant: str, provenance: str = "ollama-pull") -> None:
    m = qm.QuantManifest(
        model=model,
        provider=provider,
        quantization=quant,
        quantization_provenance=provenance,
        pulled_at="2026-09-02T20:14:00Z",
        source="registry.ollama.ai/library/" + model,
        size_bytes=0,
    )
    qm.write_manifest(m, root=str(root))


def test_first_write_prepends_frontmatter(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_JOB_ID", "1862819")
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(
        state,
        spec_id="P1B-LLM-01-INTERPRETATION",
        attempt_result={"raw_response": "## Status\n- applicable: true"},
    )
    bucket = state["per_spec_markdown"]["P1B-LLM-01-INTERPRETATION"]
    assert bucket.startswith("<!-- aegis:")
    assert 'model="qwen3.5:27b"' in bucket
    assert 'provider="ollama"' in bucket
    assert 'job="1862819"' in bucket
    assert 'spec="P1B-LLM-01-INTERPRETATION"' in bucket
    assert bucket.endswith("## Status\n- applicable: true")


def test_second_write_is_idempotent(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_JOB_ID", "1862819")
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(
        state, spec_id="S", attempt_result={"raw_response": "first response body"},
    )
    invoker._capture_per_spec_markdown(
        state, spec_id="S", attempt_result={"raw_response": "second response body"},
    )
    bucket = state["per_spec_markdown"]["S"]
    # Exactly ONE frontmatter (the first)
    assert bucket.count("<!-- aegis:") == 1
    # Separator present
    assert "\n\n---\n\n" in bucket
    assert bucket.endswith("second response body")


def test_capabilities_recorded_once(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_JOB_ID", "1862819")
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(state, spec_id="S1", attempt_result={"raw_response": "x"})
    invoker._capture_per_spec_markdown(state, spec_id="S2", attempt_result={"raw_response": "y"})
    cap = state["v2_model_capabilities"]
    assert cap["model"] == "qwen3.5:27b"
    assert cap["provider"] == "ollama"
    assert cap["job_id"] == "1862819"
    # First call wins — quantization doesn't flip to something else mid-run.
    assert "quantization" in cap and "recorded_at" in cap


def test_capabilities_uses_manifest_when_available(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    _write_manifest(tmp_path, model="qwen3.5:27b", provider="ollama", quant="q4_k_m", provenance="ollama-pull")
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(state, spec_id="S", attempt_result={"raw_response": "body"})
    assert state["v2_model_capabilities"]["quantization"] == "q4_k_m"
    assert state["v2_model_capabilities"]["quantization_provenance"] == "ollama-pull"


def test_no_manifest_ollama_defaults_to_provider_default(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(state, spec_id="S", attempt_result={"raw_response": "body"})
    cap = state["v2_model_capabilities"]
    assert cap["quantization"] == "provider_default"
    assert cap["quantization_provenance"] == "provider_default"


def test_no_manifest_vllm_records_unknown(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    invoker.provider = "vllm"
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(state, spec_id="S", attempt_result={"raw_response": "body"})
    # vLLM users must declare explicitly; we don't silently guess.
    assert state["v2_model_capabilities"]["quantization"] == "unknown"


def test_no_manifest_transformers_records_unknown(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    invoker.provider = "transformers"
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(state, spec_id="S", attempt_result={"raw_response": "body"})
    assert state["v2_model_capabilities"]["quantization"] == "unknown"


def test_aegis_job_id_wins_over_slurm_job_id(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    monkeypatch.setenv("AEGIS_JOB_ID", "from-aegis")
    monkeypatch.setenv("SLURM_JOB_ID", "from-slurm")
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(state, spec_id="S", attempt_result={"raw_response": "body"})
    assert state["v2_model_capabilities"]["job_id"] == "from-aegis"


def test_slurm_job_id_used_when_aegis_absent(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    monkeypatch.delenv("AEGIS_JOB_ID", raising=False)
    monkeypatch.setenv("SLURM_JOB_ID", "from-slurm")
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(state, spec_id="S", attempt_result={"raw_response": "body"})
    assert state["v2_model_capabilities"]["job_id"] == "from-slurm"


def test_no_env_job_id_records_unknown(invoker: Phase1LLMInvoker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    monkeypatch.delenv("AEGIS_JOB_ID", raising=False)
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    state: dict = {"per_spec_markdown": {}}
    invoker._capture_per_spec_markdown(state, spec_id="S", attempt_result={"raw_response": "body"})
    assert state["v2_model_capabilities"]["job_id"] == "unknown"
