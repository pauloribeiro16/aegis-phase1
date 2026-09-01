#!/usr/bin/env bash
#SBATCH --job-name=aegis_run_qwen38
#SBATCH --account=F202512235CPCAA1G
#SBATCH --partition=normal-a100-80
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=40G
#SBATCH --time=08:00:00
#SBATCH --output=slurm-run-qwen38-%j.out
#SBATCH --error=slurm-run-qwen38-%j.err
#SBATCH --signal=B:30@300
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#
# Full pipeline run (--run-all) with qwen3.8:27b (Ollama, single
# A100-80). 8h walltime. ONLY submit after scout-qwen38-aegis.sbatch
# exits 0 — it did (JOB 1862819, 2026-09-01, STATUS: SUCCESS).
#
# Same trick as the scout: the pre-installed cluster Ollama (0.31.1)
# cannot run the qwen3.8 renderer, so this job uses the Ollama 0.32.13
# binary from /projects/F202512235CPCAA1/graphify-methodology/{bin,lib}.
#
# Submit from login.deucalion.macc.fccn.pt:
#   cd /projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#   sbatch examples/deucalion/run-qwen38-full.sbatch

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
GFX="/projects/F202512235CPCAA1/graphify-methodology"
MODEL="qwen3.8:27b"

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : $MODEL (1x A100-80, 8h)"
echo " Node  : $(hostname)"
echo " Case  : case1-tinytask (--run-all)"
echo " Ollama: 0.32.13 from $GFX/{bin,lib/ollama}"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# --- Ollama 0.32.13 (shared model cache; never `ollama pull` here) ---
export PATH="$GFX/bin:$PATH"
export LD_LIBRARY_PATH="$GFX/lib/ollama:${LD_LIBRARY_PATH:-}"
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
echo "=== running full pipeline (--run-all) ==="
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --model "$MODEL" \
    --provider ollama \
    --run-all \
    --log-level INFO \
    --output "output/run_qwen38_${SLURM_JOB_ID}"

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
