#!/usr/bin/env bash
#SBATCH --account=F202512235CPCAA1G
#SBATCH --partition=normal-a100-80
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=40G
#SBATCH --time=08:00:00
#SBATCH --output=slurm-run-full-m-%j.out
#SBATCH --error=slurm-run-full-m-%j.err
#SBATCH --signal=B:30@300
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#
# CORR-112 F4 — generic full-pipeline run-all on one model + one case.
# Takes TWO positional args (pass model via sbatch CLI, NOT --export):
#   sbatch -J "aegis_run_<sanitised-tag>_<case>" \
#          examples/deucalion/run-full-m-aegis.sbatch <model:tag> <case-dir-name>
#   e.g.  sbatch -J aegis_run_nemotron_30b_c1 \
#             examples/deucalion/run-full-m-aegis.sbatch nemotron-3.5-lightning:30b case1-tinytask
#
# Uses the Ollama 0.32.13 binary from graphify-methodology (superset of
# 0.31.1 architectures: nemotron + qwen3.8 renderers both need it).
# Gates run in HARD mode (CORR-112 F4 done criterion).
# Logs go to NFS ($PROJ/slurm-* and logs/scout_runs/) — never scratch.

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
GFX="/projects/F202512235CPCAA1/graphify-methodology"

MODEL="${1:?usage: sbatch run-full-m-aegis.sbatch <model:tag> <case-dir-name>}"
CASE_NAME="${2:?usage: sbatch run-full-m-aegis.sbatch <model:tag> <case-dir-name>}"
SANITISED_TAG=$(echo "$MODEL" | tr ':.' '__')

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : $MODEL (1x A100-80, 8h)"
echo " Case  : $CASE_NAME (--run-all)"
echo " Node  : $(hostname)"
echo " Gates : AEGIS_GATE_MODE=hard (CORR-112 F4)"
echo " Code  : synced from workstation (SHA recorded below)"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# Porta unica por JOB (permite multi-job no mesmo no sem colisao Ollama)
OLLAMA_PORT=$((11434 + SLURM_JOB_ID % 20000))
export PATH="$GFX/bin:$PATH"
export LD_LIBRARY_PATH="$GFX/lib/ollama:${LD_LIBRARY_PATH:-}"
export OLLAMA_MODELS="$BD/ollama_data/models"
export OLLAMA_HOST="127.0.0.1:${OLLAMA_PORT}"
export OLLAMA_BASE_URL="http://127.0.0.1:${OLLAMA_PORT}"
export OLLAMA_API_KEY="local"

ollama serve > "/tmp/ollama-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!

for i in $(seq 1 90); do
  if curl -sf -m 2 "http://127.0.0.1:${OLLAMA_PORT}/api/tags" > /dev/null 2>&1; then
    break
  fi
  sleep 2
done
echo "=== ollama version:"
curl -sf -m 5 "http://127.0.0.1:${OLLAMA_PORT}/api/version" | head -c 200; echo
echo "=== warm-up: loading $MODEL"
WARM_OK=0
for attempt in 1 2 3 4 5; do
  if curl -sf -m 180 "http://127.0.0.1:${OLLAMA_PORT}/api/generate" \
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
export AEGIS_GATE_MODE=hard
export PYTHONDONTWRITEBYTECODE=1

echo ""
echo "=== wiping stale .pyc + __pycache__ (defense-in-depth) ==="
find "$PROJ/src" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PROJ/src" -name "*.pyc" -delete 2>/dev/null || true

echo ""
echo "=== pre-flight ==="
python -c "import aegis_phase1.v2.runner; print('aegis_phase1 OK')"
python -c "from aegis_phase1.prompts_v2.ref_gate import RefGate; print('ref_gate OK')"

RUN_LOG="$PROJ/logs/scout_runs/run_${SANITISED_TAG}_${CASE_NAME}_${SLURM_JOB_ID}.log"
mkdir -p "$PROJ/logs/scout_runs"
{
  echo "run_id=${SANITISED_TAG}_${CASE_NAME}_${SLURM_JOB_ID}"
  echo "model=${MODEL}"
  echo "case=${CASE_NAME}"
  echo "provider=ollama"
  echo "gate_mode=hard"
  echo "workstation_sha=$(cat "$PROJ/.synced_sha" 2>/dev/null || echo unknown)"
  echo "started=$(date -Is)"
} > "$RUN_LOG"

echo ""
echo "=== running full pipeline (--run-all, gates=hard) ==="
set +e
python -m aegis_phase1.v2.runner \
    --case "cases/${CASE_NAME}" \
    --model "$MODEL" \
    --provider ollama \
    --run-all \
    --log-level INFO \
    --output "output/run_${SANITISED_TAG}_${CASE_NAME}_${SLURM_JOB_ID}" 2>&1 | tee -a "$RUN_LOG"
PYTHON_EXIT=${PIPESTATUS[0]}
set -e

kill $OLLAMA_PID 2>/dev/null || true

echo "ended=$(date -Is)" >> "$RUN_LOG"
echo "python_exit=$PYTHON_EXIT" >> "$RUN_LOG"

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
