#!/usr/bin/env bash
#SBATCH --job-name=aegis_run_40g
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --tasks-per-node=1
#SBATCH -A F202512235CPCAA1G
#SBATCH -t 01:00:00
#SBATCH -p dev-a100-40
#SBATCH --qos=normal
#SBATCH -N 1
#SBATCH --signal=B:30@60
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --out=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-run-40g-%j.out
#SBATCH --err=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-run-40g-%j.err
#
# AEGIS Fast Run on 1x A100-40 (dev-a100-40).
# Usage:
#   sbatch examples/deucalion/run-bench-40g.sbatch qwen3.5:27b case1-tinytask

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
GFX="/projects/F202512235CPCAA1/graphify-methodology"
LOG_DIR="$BD/aegis-phase1/logs/run_40g"
mkdir -p "$LOG_DIR"

MODEL="${1:-qwen3.5:27b}"
CASE_NAME="${2:-case1-tinytask}"
MODEL_SLUG="${MODEL//[:.]/_}"
RUN_LOG="$LOG_DIR/run_40g_${MODEL_SLUG}_${SLURM_JOB_ID}.log"
exec >>"$RUN_LOG" 2>&1

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : $MODEL (1x A100-40, dev-a100-40)"
echo " Case  : cases/$CASE_NAME"
echo " Gate  : AEGIS_GATE_MODE=hard"
echo " Node  : $(hostname)"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

export PATH="$GFX/bin:$BD/bin:$PATH"
export LD_LIBRARY_PATH="$GFX/lib/ollama:$BD/lib/ollama:${LD_LIBRARY_PATH:-}"
export OLLAMA_MODELS="$BD/ollama_data/models"
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_API_KEY="local"

ollama serve > "/tmp/ollama-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!

for i in $(seq 1 90); do
  if curl -sf -m 2 "http://127.0.0.1:11434/api/tags" > /dev/null 2>&1; then
    break
  fi
  sleep 2
done
echo "=== ollama version:"
curl -sf -m 5 "http://127.0.0.1:11434/api/version" | head -c 200; echo

echo "=== warm-up: loading $MODEL"
WARM_OK=0
for attempt in 1 2 3 4 5; do
  if curl -sf -m 180 "http://127.0.0.1:11434/api/generate" \
      -d "{\"model\":\"$MODEL\",\"prompt\":\"ping\",\"stream\":false,\"options\":{\"num_predict\":1}}" \
      > /tmp/warmup.out 2>&1; then
    echo "warm-up OK on attempt $attempt"
    head -c 200 /tmp/warmup.out; echo
    WARM_OK=1
    break
  fi
  echo "warm-up attempt $attempt failed; sleeping 10s..."
  sleep 10
done
if [ $WARM_OK -eq 0 ]; then
  echo "ERROR: warm-up failed; aborting"
  tail -40 "/tmp/ollama-${SLURM_JOB_ID}.log"
  kill $OLLAMA_PID 2>/dev/null || true
  exit 1
fi

cd "$PROJ"
source .venv/bin/activate

echo "=== wiping stale bytecode ==="
find "$PROJ/src" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PROJ/src" -name "*.pyc" -delete 2>/dev/null || true
export PYTHONDONTWRITEBYTECODE=1

export PYTHONPATH="$PROJ/src:$PROJ:${PYTHONPATH:-}"
export LANGFUSE_ENABLED=false
export AEGIS_GATE_MODE=hard

OUT_DIR="output/run_40g_${MODEL_SLUG}_${SLURM_JOB_ID}"
mkdir -p "$OUT_DIR"

echo "=== running Phase 1B on 1x A100-40 ==="
python -m aegis_phase1.v2.runner \
    --case "cases/$CASE_NAME" \
    --model "$MODEL" \
    --provider ollama \
    --run-phase-1b \
    --log-level INFO \
    --output "$OUT_DIR"

PYTHON_EXIT=$?
kill $OLLAMA_PID 2>/dev/null || true

echo ""
echo "=================================================="
echo " JOB $SLURM_JOB_ID FINISHED: $(date)"
if [ $PYTHON_EXIT -eq 0 ]; then
  echo " STATUS: SUCCESS"
else
  echo " STATUS: FAILED ($PYTHON_EXIT)"
fi
echo "=================================================="
exit $PYTHON_EXIT
