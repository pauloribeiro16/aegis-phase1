#!/usr/bin/env bash
#SBATCH --job-name=aegis_scout_gemma4_26b
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=40G
#SBATCH --tasks-per-node=1
#SBATCH -A F202512235CPCAA1G
#SBATCH -t 00:30:00
#SBATCH -p dev-a100-80
#SBATCH --qos=normal
#SBATCH -N 1
#SBATCH --signal=B:30@30
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --out=slurm-scout-gemma4-26b-%j.out
#SBATCH --err=slurm-scout-gemma4-26b-%j.err
#
# AEGIS scout — gemma4:26b (Ollama path) on Phase 1B only.
#
# Pivot from gemma-4-31B-it via HF transformers (which kept failing on
# Phase1LLMInvoker ↔ TransformersInvoker signature mismatches — see
# CORR-106 history). gemma4:26b uses the same Ollama backend the
# qwen3.5 / qwen3.8 scouts use; 17.9 GB blob is already in the
# pre-cached ollama_data store at $BD/ollama_data.
#
# Same shape as scout_qwen35.sh / run_qwen35_full.sh; provider=ollama
# so the orchestrator's heavy path (Phase1LLMInvoker with ChatOllama)
# works end-to-end. Walltime 30 min (qwen3.8 scout ran in 18:04).

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
MODEL="gemma4:26b"

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : $MODEL (Ollama, 1x A100-80, 30m)"
echo " Node  : $(hostname)"
echo " Scope : case1-tinytask, --run-phase-1b only"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# --- Ollama 0.32.13 (same as scout_qwen35.sh / qwen3.8 scouts) ---
export PATH="$BD/bin:$PATH"
export LD_LIBRARY_PATH="$BD/lib/ollama:${LD_LIBRARY_PATH:-}"
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

export PYTHONPATH="$PROJ:${PYTHONPATH:-}"
export LANGFUSE_ENABLED=false

echo ""
echo "=== pre-flight ==="
python -c "import aegis_phase1.v2.runner; print('aegis_phase1 OK')"

echo ""
echo "=== running scout (Phase 1B only) ==="
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --model "$MODEL" \
    --provider ollama \
    --run-phase-1b \
    --log-level INFO \
    --output "output/scout_gemma4_26b_${SLURM_JOB_ID}"

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