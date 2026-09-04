#!/usr/bin/env bash
#SBATCH --job-name=aegis_scout_bench
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
#SBATCH --out=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-scout-bench-m-%j.out
#SBATCH --err=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-scout-bench-m-%j.err
#
# AEGIS scout — generic model scout (Ollama path) on Phase 1B only.
#
# Model is passed as the FIRST CLI argument (NOT via --export):
#   sbatch examples/deucalion/scout-bench-m-aegis.sbatch muse-glimmer:30b
#
# Differs from scout-bench-aegis.sbatch in:
# 1. Model = $1 (positional arg) — works around SLURM's --export quirks.
# 2. --out / --err write to the project dir (NFS) so we can read
#    logs after job exit even when the compute node scratch is wiped.
# 3. Logs every step to /projects/.../logs/scout_<MODEL>_<JOBID>.log.

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
LOG_DIR="$BD/aegis-phase1/logs/scout_runs"
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/scout_${1:-unknown}_${SLURM_JOB_ID}.log"

if [ $# -lt 1 ]; then
  echo "usage: sbatch $0 <model:tag>" | tee -a "$RUN_LOG"
  exit 2
fi
MODEL="$1"

# Cache check ANTES do exec >> para nao perder o fail-fast.
NAME_LIB="${MODEL%:*}"; SHA_LIB="${MODEL##*:}"; NAME_NORM=$(echo "$NAME_LIB" | tr '.' '_')
for cand in "$NAME_NORM" "$NAME_LIB"; do
  if [ -e "${BD}/ollama_data/models/manifests/registry.ollama.ai/library/${cand}/${SHA_LIB}" ]; then
    break
  fi
done
if [ "$cand" != "$NAME_NORM" ] && [ "$cand" != "$NAME_LIB" ]; then
  echo "ERROR: model '${MODEL}' NOT in cache (manifest ${NAME_NORM}/${SHA_LIB} nao existe)."
  echo "       bash scripts/hpc/pull-verify.sh ${MODEL}"
  exit 1
fi

# Porta unica por JOB (multi-job no mesmo no -> sem colisao Ollama)
PORT=$((11434 + SLURM_JOB_ID % 20000))
export OLLAMA_HOST="127.0.0.1:${PORT}"
export OLLAMA_BASE_URL="${OLLAMA_HOST}"
export OLLAMA_API_KEY="local"

exec >>"$RUN_LOG" 2>&1
trap 'echo "EXIT_CODE=$?  END=$(date -Is)"' EXIT

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : $MODEL (Ollama, 1x A100-80, 30m)"
echo " Node  : $(hostname)"
echo " Port  : ${PORT}"
echo " Scope : case1-tinytask, --run-phase-1b only"
echo " RUN_LOG: $RUN_LOG"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

export PATH="$BD/bin:$PATH"
export LD_LIBRARY_PATH="$BD/lib/ollama:${LD_LIBRARY_PATH:-}"
export OLLAMA_MODELS="$BD/ollama_data/models"
export PYTHONDONTWRITEBYTECODE=1
export AEGIS_LOG_BASE="${PROJ}/logs/phase1/scout_phase1b/${SLURM_JOB_ID}"

ollama serve > "/tmp/ollama-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!

for i in $(seq 1 90); do
  if curl -sf -m 2 "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; then
    break
  fi
  sleep 2
done
echo "=== ollama version:"
curl -sf -m 5 "${OLLAMA_HOST}/api/version" | head -c 200; echo

# If model isn't already cached, attempt ollama pull (spotty egress).
if ! ollama list 2>/dev/null | awk '{print $1}' | grep -q "^${MODEL}$"; then
  echo "=== model $MODEL not in cache; attempting ollama pull"
  if ! timeout 600 ollama pull "$MODEL" 2>&1 | tail -5; then
    echo "ERROR: ollama pull failed; aborting"
    kill $OLLAMA_PID 2>/dev/null || true
    exit 1
  fi
fi

echo "=== warm-up: loading $MODEL"
WARM_OK=0
for attempt in 1 2 3 4 5; do
  if curl -sf -m 180 "${OLLAMA_HOST}/api/generate" \
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
    --output "output/scout_${SLURM_JOB_ID}"

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