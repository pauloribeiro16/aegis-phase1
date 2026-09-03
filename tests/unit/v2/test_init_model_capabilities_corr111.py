"""Tests for CORR-111 — Phase1Orchestrator.init_model_capabilities.

Verified:
  T1.  Without an llm_invoker → fields are populated (model='unknown',
       provider='unknown', quantization='unknown'). Pipeline never
       crashes for missing invoker.
  T2.  With an Ollama invoker + no manifest → records
       ``provider_default`` (per user decision 2026-09-02).
  T3.  Idempotent: the second call does NOT overwrite an already-set
       capability dict (first call wins).
  T4.  AEGIS_JOB_ID wins over SLURM_JOB_ID; both absent → 'unknown'.
  T5.  A manifest on disk under AEGIS_QUANT_MANIFEST_ROOT makes the
       recorded quant reflect it.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aegis_phase1.llm import quant_manifest as qm
from aegis_phase1.v2.orchestrator import Phase1Orchestrator


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir()
    return d


def _orch(work_dir: Path, *, model: str | None, provider: str | None) -> Phase1Orchestrator:
    invoker = None
    if model is not None or provider is not None:
        invoker = MagicMock()
        invoker.model = model
        invoker.provider = provider
    return Phase1Orchestrator(work_dir=str(work_dir), llm_invoker=invoker)


def test_no_llm_invoker_records_unknown(work_dir: Path) -> None:
    orch = _orch(work_dir, model=None, provider=None)
    info = orch.init_model_capabilities()
    assert info["model"] == "unknown"
    assert info["provider"] == "unknown"
    assert info["quantization"] == "unknown"
    assert "recorded_at" in info


def test_ollama_without_manifest_defaults_to_provider_default(work_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    monkeypatch.setenv("AEGIS_JOB_ID", "1869082")
    orch = _orch(work_dir, model="gemma4:31b", provider="ollama")
    info = orch.init_model_capabilities()
    assert info["model"] == "gemma4:31b"
    assert info["provider"] == "ollama"
    assert info["quantization"] == "provider_default"
    assert info["quantization_provenance"] == "provider_default"
    assert info["job_id"] == "1869082"


def test_idempotent_first_call_wins(work_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    monkeypatch.setenv("AEGIS_JOB_ID", "1869082")
    orch = _orch(work_dir, model="gemma4:31b", provider="ollama")
    first = orch.init_model_capabilities()
    # Mutate invoker mid-run (e.g. a fallback switched models).
    orch.llm_invoker.model = "different-model"
    second = orch.init_model_capabilities()
    assert first == second
    assert second["model"] == "gemma4:31b"  # unchanged


def test_manifest_present_uses_quant(work_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    monkeypatch.setenv("AEGIS_JOB_ID", "1869082")
    qm.write_manifest(
        qm.QuantManifest(
            model="gemma4:31b",
            provider="ollama",
            quantization="q4_k_m",
            quantization_provenance="ollama-pull",
            pulled_at="2026-09-02T20:00:00Z",
            source="registry.ollama.ai/library/gemma4:31b",
        ),
        root=str(tmp_path),
    )
    orch = _orch(work_dir, model="gemma4:31b", provider="ollama")
    info = orch.init_model_capabilities()
    assert info["quantization"] == "q4_k_m"
    assert info["quantization_provenance"] == "ollama-pull"
    assert info["manifest_path"] != ""


def test_aegis_job_id_wins_over_slurm(work_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEGIS_JOB_ID", "from-aegis")
    monkeypatch.setenv("SLURM_JOB_ID", "from-slurm")
    orch = _orch(work_dir, model="x", provider="ollama")
    info = orch.init_model_capabilities()
    assert info["job_id"] == "from-aegis"


def test_no_env_job_id_records_unknown(work_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEGIS_JOB_ID", raising=False)
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    orch = _orch(work_dir, model="x", provider="ollama")
    info = orch.init_model_capabilities()
    assert info["job_id"] == "unknown"
