#!/usr/bin/env bash
#SBATCH --job-name=aegis_scout_qwen38
#SBATCH --account=F202512235CPCAA1G
#SBATCH --partition=dev-a100-80
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=40G
#SBATCH --time=00:30:00
#SBATCH --output=slurm-scout-qwen38-%j.out
#SBATCH --error=slurm-scout-qwen38-%j.err
#SBATCH --signal=B:30@30
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#
# AEGIS scout — qwen3.8:27b on Deucalion, Phase 1B only.
#
# Pre-installed cluster Ollama (0.31.1) rejects the `qwen3.8` renderer
# (HTTP 500: unknown renderer "qwen3.8"). This job uses the NEW Ollama
# 0.32.13 binary that already lives in
# /projects/F202512235CPCAA1/graphify-methodology/{bin,lib} — same
# trick that worked for graphify (JOB 1825982, 2026-08-15).
#
# Scope: case1-tinytask, --run-phase-1b (4 LLM calls: P1B-01 + P1B-02
# x 2 applicable regulations). 30 min walltime matches the qwen3.5
# scout budget (JOB 1846944 ran in 18:33).
#
# Submit from login.deucalion.macc.fccn.pt:
#   cd /projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#   sbatch examples/deucalion/scout-qwen38-aegis.sbatch

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
GFX="/projects/F202512235CPCAA1/graphify-methodology"
MODEL="qwen3.8:27b"

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model: $MODEL (1x A100-80, 30m walltime)"
echo " Node : $(hostname)"
echo " Scope: case1-tinytask, --run-phase-1b (4 LLM calls)"
echo " Ollama: 0.32.13 from $GFX/{bin,lib/ollama}"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# --- Ollama 0.32.13 (shared cache; never `ollama pull` here) ---
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
echo "=== ollama tags (first 200 chars):"
curl -sf -m 5 "http://127.0.0.1:11434/api/tags" | head -c 200; echo

# Warm-up: load model onto GPU; qwen3.8:27b blob is ~17.7GB
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
  tail -60 "/tmp/ollama-${SLURM_JOB_ID}.log"
  kill $OLLAMA_PID 2>/dev/null || true
  exit 1
fi

echo "=== ollama ps:"
ollama ps || true

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
    --output "output/scout_qwen38_${SLURM_JOB_ID}"

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