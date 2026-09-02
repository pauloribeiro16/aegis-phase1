#!/usr/bin/env bash
#SBATCH --job-name=aegis_pull_qwen
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --tasks-per-node=1
#SBATCH -A F202512235CPCAA1G
#SBATCH -t 01:00:00
#SBATCH -p dev-a100-40
#SBATCH --qos=normal
#SBATCH -N 1
#SBATCH --signal=B:30@60
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --out=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-pull-qwen-%j.out
#SBATCH --err=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-pull-qwen-%j.err
#
# Re-stage Ollama models for the post-cleanup lineup.
#
# After the 2026-09-02 purge (see CONTRACT-110 + commit 7e30685) only
# glm-4.7-flash remains in ollama_data. This job re-pulls the qwen
# tags that scouts need back: qwen3.5:27b + qwen3.8:27b.
#
# Runs ollama 0.32.13 (graphify build) — the cluster-shipped 0.31.1
# cannot resolve modern manifests (qwen3.8 needs the 0.32.13
# renderer; pulled successfully 2026-09-01).
#
# Models list:
#   qwen3.5:27b  — Ollama scout baseline (4 scouts + run-all done 2026-09-01)
#   qwen3.8:27b  — Ollama scout baseline (4 scouts done 2026-09-01)
#
# Total footprint: ~40 GB. Currently 117 GB free on Lustre.

set -euo pipefail
umask 077

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
LOG_DIR="$BD/aegis-phase1/logs/scout_runs"
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/pull_qwen_${SLURM_JOB_ID}.log"
exec >>"$RUN_LOG" 2>&1

MODELS=(
  "glm-4.7-flash"
  "qwen3.5:27b"
  "qwen3.8:27b"
)

export PATH="$BD/../graphify-methodology/bin:$PATH"
export LD_LIBRARY_PATH="$BD/../graphify-methodology/lib/ollama:${LD_LIBRARY_PATH:-}"
export OLLAMA_MODELS="$BD/ollama_data/models"
export OLLAMA_HOST="127.0.0.1:11436"
export OLLAMA_API_KEY="local"

echo "=================================================="
echo " OLLAMA PULL — post-cleanup re-staging"
echo " Job : $SLURM_JOB_ID on $(hostname)"
echo " BD  : $BD"
echo " Started : $(date)"
echo " Models: ${MODELS[*]}"
echo " RUN_LOG: $RUN_LOG"
echo "=================================================="

ollama serve > "/tmp/ollama-pull-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!

cleanup() {
  if kill -0 "$OLLAMA_PID" 2>/dev/null; then
    kill "$OLLAMA_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

for i in $(seq 1 90); do
  if curl -sf -m 2 "http://127.0.0.1:11436/api/tags" > /dev/null 2>&1; then
    echo "[pull] ollama up after ${i}s"
    break
  fi
  sleep 1
done

echo "[pull] ollama version:"
curl -sf -m 5 "http://127.0.0.1:11436/api/version" | head -c 200; echo

for MODEL in "${MODELS[@]}"; do
  if ollama list 2>/dev/null | awk '{print $1}' | grep -q "^${MODEL}$"; then
    echo "[pull] $MODEL already in cache, skipping"
    continue
  fi
  echo "[pull] pulling $MODEL ..."
  if ! timeout 1800 ollama pull "$MODEL" 2>&1 | tail -3; then
    echo "[pull] ERROR: $MODEL failed"
  fi
done

echo "[pull] final state:"
ollama list 2>&1 | head -20

echo "=================================================="
echo " JOB $SLURM_JOB_ID FINISHED: $(date)"
echo "=================================================="