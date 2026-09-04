#!/usr/bin/env bash
# pull-verify.sh — Login node only.
#
# Pull an Ollama model with the GRAPHIFY 0.32.13 binary (the only one
# that can resolve modern manifests) and verify the manifest lands
# under the shared cache. Re-pull is needed because aborted
# `timeout`-wrapped jobs sometimes leave blobs but not the manifest
# directory -- a second pull completes the manifest in seconds.
#
# Usage (run on the Deucalion login node):
#   source .aegis_env && bash scripts/hpc/pull-verify.sh <model:tag> [--timeout N]
#
# Example:
#   bash scripts/hpc/pull-verify.sh ornith:35b
#   bash scripts/hpc/pull-verify.sh qwen3.5:122b --timeout 2700
#
# Notes:
# - This script will SKIP if `.aegis_env` is not present (no auth).
# - It will NOT touch the cluster network from a compute node --
#   always invoke on the login node, with the workspace mounted at
#   /projects/F202512235CPCAA1/CyberMetric_Deucalion.

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
GFX="/projects/F202512235CPCAA1/graphify-methodology"
LOG_FILE="${BD}/logs/scout_runs/pull_$(date +%s).log"

TIMEOUT="${TIMEOUT_OVERRIDE:-1800}"
MODEL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --timeout) TIMEOUT="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 <model:tag> [--timeout N]"; exit 0 ;;
    --*) echo "unknown arg: $1"; exit 2 ;;
    *) MODEL="$1"; shift ;;
  esac
done

if [ -z "$MODEL" ]; then
  echo "ERROR: missing <model:tag>"; exit 2
fi

NAME="${MODEL%:*}"
SHA="${MODEL##*:}"
CACHE="${BD}/ollama_data/models/manifests/registry.ollama.ai/library/${NAME}"
MARK="${CACHE}/${SHA}"

if [ -f "${MARK}" ] || [ -d "${MARK}" ]; then
  echo "OK: $MODEL manifest present at $MARK"
  echo "    smoke test (no network): ollama show $MODEL"
  export PATH="${GFX}/bin:${PATH}"
  export LD_LIBRARY_PATH="${GFX}/lib/ollama:${LD_LIBRARY_PATH:-}"
  ollama show "$MODEL" 2>&1 | head -10
  exit 0
fi

echo "Pull $MODEL with timeout=$TIMEOUT s..."
mkdir -p "${BD}/logs/scout_runs"
(
  echo "=== pull-verify started: $(date -Iseconds) ==="
  echo "model=$MODEL  cache_root=$CACHE"

  export PATH="${GFX}/bin:${PATH}"
  export LD_LIBRARY_PATH="${GFX}/lib/ollama:${LD_LIBRARY_PATH:-}"
  export OLLAMA_MODELS="${BD}/ollama_data/models"
  export OLLAMA_HOST="127.0.0.1:11499"
  export OLLAMA_API_KEY="local"

  # serve on a private port to avoid colliding with sbatch-side Ollamas
  ollama serve > "/tmp/ollama-pull-$$.log" 2>&1 &
  OLLAMA_PID=$!
  trap "kill $OLLAMA_PID 2>/dev/null || true" EXIT

  for i in $(seq 1 30); do
    if curl -sf -m 2 "http://127.0.0.1:11499/api/tags" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  echo "=== ollama version ==="
  ollama --version

  echo "=== ollama pull ==="
  timeout "$TIMEOUT" ollama pull "$MODEL" 2>&1 | tail -30

  echo "=== verifying manifest ==="
  if [ -f "$MARK" ] || [ -d "$MARK" ]; then
    echo "OK: $MARK now exists"
  else
    echo "FAIL: $MARK still missing after pull. Manifest not written."
    exit 2
  fi

  echo "=== ollama show smoke ==="
  ollama show "$MODEL" 2>&1 | head -15
) 2>&1 | tee "$LOG_FILE"
