#!/usr/bin/env bash
# CORR-111 — Stage a HuggingFace model and record its quantization sidecar.
#
# Why this exists (user feedback 2026-09-02): HF checkpoints are usually
# published with a quant in the repo name (Qwen3.8-Flash-Next-FP8 has FP8
# weights). Recording it explicitly prevents "which quant was actually
# loaded?" guesswork later.
#
# Usage:
#   HF_REPO="Qwen/Qwen3.8-Flash-Next" HF_QUANT="fp8" \
#       sbatch examples/deucalion/stage-hf-model-aegis.sbatch
#   HF_REPO="meta-llama/Llama-3.1-8B"  # defaults to bf16
#
# Logic:
#   1. Resolve local target under ${HF_STAGING_ROOT} (defaults to aegis Lustre
#      path; override with env var).
#   2. `hf download` (or skip if already staged).
#   3. Inspect config.json to confirm architecture + size.
#   4. Record sidecar via the Phase-1 helper.
#
# Notes:
#   - COMPUTE NODES HAVE NO EGRESS. Prefer running on the login node, or
#     `sbatch -p login`. (Cluster policy discovered 2026-09-02.)

#SBATCH --job-name=aegis-stage-hf-quant
# -A F202512235CPCAA1X is the canonical x86 account on Deucalion.
# Compute nodes have NO egress for HF download — this script must run on the
# login node (`bash`, NOT sbatch) or on the dev-x86 partition. The default
# below lets you sbatch it; for interactive pulls prefer login node.
#SBATCH -A F202512235CPCAA1X
#SBATCH --partition=dev-x86
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --output=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-aegis-stage-hf-quant-%j.out
#SBATCH --error=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-aegis-stage-hf-quant-%j.err

set -euo pipefail
set -x
umask 077

: "${HF_REPO:?HF_REPO must be set (e.g. Qwen/Qwen3.8-Flash-Next)}"
: "${HF_QUANT:=bf16}"
: "${HF_TOKEN:=}"
: "${HF_STAGING_ROOT:=/projects/F202512235CPCAA1/CyberMetric_Deucalion/models/hf}"
# See pull-ollama-model-aegis.sbatch for why $HOME is not used.
: "${AEGIS_QUANT_MANIFEST_ROOT:=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-quant-manifests}"
mkdir -p "${AEGIS_QUANT_MANIFEST_ROOT}" || true
export AEGIS_QUANT_MANIFEST_ROOT

LOCAL_DIR="${HF_STAGING_ROOT}/$(echo "${HF_REPO}" | tr '/' '_')"

echo "[stage] repo=${HF_REPO} quant=${HF_QUANT} → ${LOCAL_DIR}"

# --- 1) download (skip if already staged) ---
if [[ -f "${LOCAL_DIR}/config.json" ]]; then
    echo "[stage] config.json already present — skipping download"
else
    mkdir -p "${LOCAL_DIR}"
    ARGS=(download "${HF_REPO}" --local-dir "${LOCAL_DIR}" --max-workers 8)
    if [[ -n "${HF_TOKEN}" ]]; then ARGS+=(--token "${HF_TOKEN}"); fi
    hf "${ARGS[@]}"
fi

# --- 2) confirm + capture config-driven facts ---
CONFIG_JSON="${LOCAL_DIR}/config.json"
if [[ ! -f "${CONFIG_JSON}" ]]; then
    echo "[stage] WARN: config.json missing at ${CONFIG_JSON} — quant provenance marked 'hf-stage'"
fi

# --- 3) record sidecar ---
PRJ=${PRJ:-/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1}
PYTHON="${PRJ}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
    echo "[stage] ERROR: venv python missing at ${PYTHON} — fix PRJ or run: python -m venv ${PRJ}/.venv"
    exit 1
fi
"${PYTHON}" - <<PYEOF
import json, os, re
from pathlib import Path
from datetime import datetime, timezone
import aegis_phase1.llm.quant_manifest as qm

repo = "${HF_REPO}"
target = Path("${LOCAL_DIR}")
config = Path("${CONFIG_JSON}")
size_bytes = 0
if target.is_dir():
    size_bytes = sum(p.stat().st_size for p in target.rglob("*") if p.is_file())

m = qm.QuantManifest(
    model=repo.replace("/", "_"),
    provider="hf",
    quantization=qm._normalize_quant_tag("${HF_QUANT}"),
    quantization_provenance="hf-stage",
    pulled_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    source=f"https://huggingface.co/{repo}",
    size_bytes=size_bytes,
    digest_sha256=qm.head_sha256(config) if config.exists() else "",
    digest_method="head-16MiB-sha256",
    vllm_compat=False,
    notes="written by stage-hf-model-aegis.sbatch (CORR-111)",
)

p = qm.write_manifest(m)
print("[stage] wrote", p)
print("[stage] size_bytes=", size_bytes)
PYEOF

echo "[stage] DONE — verify with: ls -la ${AEGIS_QUANT_MANIFEST_ROOT}/hf/ 2>&1"
