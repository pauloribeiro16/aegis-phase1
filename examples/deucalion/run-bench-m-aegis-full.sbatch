#!/usr/bin/env bash
#SBATCH --job-name=aegis_run_full
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=40G
#SBATCH --tasks-per-node=1
#SBATCH -A F202512235CPCAA1G
#SBATCH -t 04:00:00
#SBATCH -p normal-a100-80
#SBATCH --qos=normal
#SBATCH -N 1
#SBATCH --signal=B:30@300
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --out=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-run-full-%j.out
#SBATCH --err=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-run-full-%j.err
#
# AEGIS CORR-112 Full Pipeline Run (--run-all) on Deucalion (1x A100-80).
# Mode: AEGIS_GATE_MODE=hard (RefGate deterministic + feedback retry)
#
# Usage:
#   sbatch -J "aegis_nemotron_full" examples/deucalion/run-bench-m-aegis-full.sbatch nemotron-3.5-lightning:30b
#   sbatch -J "aegis_qwen38_full" examples/deucalion/run-bench-m-aegis-full.sbatch qwen3.8:27b

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
GFX="/projects/F202512235CPCAA1/graphify-methodology"
LOG_DIR="$BD/aegis-phase1/logs/run_all"
mkdir -p "$LOG_DIR"

if [ $# -lt 1 ]; then
  echo "usage: sbatch $0 <model:tag>"
  exit 2
fi
MODEL="$1"
CASE="${2:-cases/case1-tinytask}"
MODEL_SLUG="${MODEL//[:.]/_}"
CASE_SLUG="$(basename "$CASE")"
RUN_LOG="$LOG_DIR/run_all_${CASE_SLUG}_${MODEL_SLUG}_${SLURM_JOB_ID}.log"
exec >>"$RUN_LOG" 2>&1

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : $MODEL (1x A100-80, 4h, full --run-all)"
echo " Node  : $(hostname)"
echo " Case  : $CASE"
echo " Gate  : AEGIS_GATE_MODE=hard"
echo " Log   : $RUN_LOG"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# Use Ollama 0.32.13 with full architecture support
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

echo "=== wiping stale .pyc + __pycache__ (defense-in-depth) ==="
find "$PROJ/src" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PROJ/src" -name "*.pyc" -delete 2>/dev/null || true
export PYTHONDONTWRITEBYTECODE=1

export PYTHONPATH="$PROJ/src:$PROJ:${PYTHONPATH:-}"
export LANGFUSE_ENABLED=false
export AEGIS_GATE_MODE=hard

echo ""
echo "=== pre-flight ==="
python -c "import aegis_phase1.v2.runner; from aegis_phase1.prompts_v2.ref_gate import RefGate; print('aegis_phase1 + RefGate OK')"

OUT_DIR="output/${CASE_SLUG}/phase1/run_${MODEL_SLUG}_${SLURM_JOB_ID}"
mkdir -p "$OUT_DIR"

echo ""
echo "=== running full pipeline (--run-all) with AEGIS_GATE_MODE=hard ==="
python -m aegis_phase1.v2.runner \
    --case "$CASE" \
    --model "$MODEL" \
    --provider ollama \
    --run-all \
    --log-level INFO \
    --output "$OUT_DIR"

PYTHON_EXIT=$?

kill $OLLAMA_PID 2>/dev/null || true

echo ""
echo "=== checking RefGate & provenance acceptance on output ==="
if [ $PYTHON_EXIT -eq 0 ]; then
  python scripts/eval/check_gate.py --run-dir "$OUT_DIR" || true
fi

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
