#!/usr/bin/env bash
# CORR-111 — Pull a single Ollama model and record its quantization sidecar.
#
# Why this exists (user feedback 2026-09-02): same tag can exist in many
# quantizations; without an explicit record, scout digests become ambiguous.
#
# Usage:
#   OLLAMA_MODEL="qwen3.5:27b" sbatch examples/deucalion/pull-ollama-model-aegis.sbatch
#   OLLAMA_MODEL="gemma4:31b" OLLAMA_QUANT="q4_K_M" sbatch ...
#   OLLAMA_MODEL="gemma4:31b" sbatch ...  # quant will be auto-detected via
#                                            `ollama show --json`; if no quant
#                                            field is found, falls back to
#                                            'provider_default'.
#
# Sidecar path:
#   ${AEGIS_QUANT_MANIFEST_ROOT:-${HOME}/aegis_quant_manifests}/ollama/
#       <slug(model)>@<quant>.json
#
# Notes:
#   - Login node HAS egress to registry.ollama.ai; compute nodes do NOT.
#     Submit with --partition=login or run interactively.
#   - Override OLLAMA_BIN if your cluster wraps ollama under a different path.

#SBATCH --job-name=aegis-pull-ollama-quant
#SBATCH --account=f202512235cpcaa1g
#SBATCH --partition=login
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=slurm-aegis-pull-ollama-quant-%j.out
#SBATCH --error=slurm-aegis-pull-ollama-quant-%j.err

set -euo pipefail
set -x
umask 077

: "${OLLAMA_MODEL:?OLLAMA_MODEL must be set (e.g. qwen3.5:27b)}"
: "${OLLAMA_BIN:=/projects/F202512235CPCAA1/CyberMetric_Deucalion/bin/ollama}"
: "${OLLAMA_PULL_TIMEOUT:=1800}"  # 30 min per model
: "${AEGIS_QUANT_MANIFEST_ROOT:=${HOME}/aegis_quant_manifests}"
export AEGIS_QUANT_MANIFEST_ROOT

echo "[pull] ollama=${OLLAMA_BIN}  model=${OLLAMA_MODEL}"
echo "[pull] manifest_root=${AEGIS_QUANT_MANIFEST_ROOT}"

# --- 1) pull (skipped if already present) ---
if "${OLLAMA_BIN}" show "${OLLAMA_MODEL}" >/dev/null 2>&1; then
    echo "[pull] already present — skipping download"
else
    echo "[pull] ollama pull ${OLLAMA_MODEL}"
    timeout "${OLLAMA_PULL_TIMEOUT}" "${OLLAMA_BIN}" pull "${OLLAMA_MODEL}"
fi

# --- 2) record sidecar via the Phase-1 helper ---
# Reuse the project's venv python so we don't depend on system packages.
PYTHON=${PYTHON:-${HOME}/Área\ de\ Trabalho/projects/aegis-phase1/.venv/bin/python}
# shellcheck disable=SC2086
"${PYTHON}" - <<PYEOF
import os, json
from pathlib import Path
import aegis_phase1.llm.quant_manifest as qm

m = qm.QuantManifest(
    model="${OLLAMA_MODEL}",
    provider="ollama",
    quantization=qm.detect_ollama_quantization("${OLLAMA_MODEL}") or "unknown",
    quantization_provenance="ollama-pull",
    pulled_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    source="registry.ollama.ai/library/${OLLAMA_MODEL//:/\/}",
    size_bytes=0,
    digest_sha256="",
    digest_method="not-hashed",
    vllm_compat=False,
    notes="written by pull-ollama-model-aegis.sbatch (CORR-111)",
)
# Fall back to provider_default when probe yields no signal.
if m.quantization == "unknown":
    m.quantization = "provider_default"
    m.quantization_provenance = "provider_default"

p = qm.write_manifest(m)
print("[pull] wrote", p)
PYEOF

echo "[pull] DONE — verify with: ls -la ${AEGIS_QUANT_MANIFEST_ROOT}/ollama/ 2>&1"
