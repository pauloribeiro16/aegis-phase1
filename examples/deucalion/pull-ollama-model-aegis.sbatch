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
# Account is the canonical x86 account on Deucalion (skill: DEUCALION_ACCOUNT_X86).
# `dev-x86` is the CPU partition paired with that account; GPU accounts (…G) are
# rejected. Egress is needed for `ollama pull` — compute nodes do NOT have it,
# so the script's normal usage is via SSH on the login node (`bash -lc`),
# not sbatch. sbatch is kept here as a fallback for users who want to queue.
#SBATCH -A F202512235CPCAA1X
#SBATCH --partition=dev-x86
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --output=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-aegis-pull-ollama-quant-%j.out
#SBATCH --error=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-aegis-pull-ollama-quant-%j.err

set -euo pipefail
set -x
umask 077

: "${OLLAMA_MODEL:?OLLAMA_MODEL must be set (e.g. qwen3.5:27b)}"
: "${OLLAMA_BIN:=/projects/F202512235CPCAA1/CyberMetric_Deucalion/bin/ollama}"
: "${OLLAMA_PULL_TIMEOUT:=1800}"  # 30 min per model
# Default to a project-shared dir on Lustre. The user's $HOME has a tight
# quota (DISK QUOTA EXCEEDED, confirmed 2026-09-03), so writing to it
# fails with errno 122. The project dir has 39 GB free.
: "${AEGIS_QUANT_MANIFEST_ROOT:=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-quant-manifests}"
mkdir -p "${AEGIS_QUANT_MANIFEST_ROOT}" || true
export AEGIS_QUANT_MANIFEST_ROOT

echo "[pull] ollama=${OLLAMA_BIN}  model=${OLLAMA_MODEL}"
echo "[pull] manifest_root=${AEGIS_QUANT_MANIFEST_ROOT}"
echo "[pull] job_id=${AEGIS_JOB_ID:-${SLURM_JOB_ID:-unknown}}"

# --- 1) pull (skipped if already present) ---
# NOTE: compute nodes (dev-x86, dev-a100-*) have NO egress to
# registry.ollama.ai. Use a login node shell, NOT sbatch, when pulling a
# NEW model. For models already in the shared cache the no-op path below
# works on any node — but the sidecar-write step ALWAYS succeeds (helper
# records `provider_default` when it can't probe; see CORR-111).
if "${OLLAMA_BIN}" show "${OLLAMA_MODEL}" >/dev/null 2>&1; then
    echo "[pull] already present — skipping download"
else
    echo "[pull] ollama pull ${OLLAMA_MODEL}  (egress needed — use login node)"
    timeout "${OLLAMA_PULL_TIMEOUT}" "${OLLAMA_BIN}" pull "${OLLAMA_MODEL}" || {
        echo "[pull] WARN: pull failed (rc=$?); recording manifest anyway with provider_default"
    }
fi

# --- 2) record sidecar via the Phase-1 helper ---
# Use the project's venv python (per-project venv rule — skill hpc-deucalion).
PRJ=${PRJ:-/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1}
PYTHON="${PRJ}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
    echo "[pull] ERROR: venv python missing at ${PYTHON} — fix PRJ or run: python -m venv ${PRJ}/.venv"
    exit 1
fi
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
