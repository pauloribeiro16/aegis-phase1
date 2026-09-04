#!/usr/bin/env bash
#SBATCH --job-name=aegis_scout_full
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=40G
#SBATCH --tasks-per-node=1
#SBATCH -A F202512235CPCAA1G
#SBATCH -t 01:30:00
#SBATCH -p dev-a100-80
#SBATCH --qos=normal
#SBATCH -N 1
#SBATCH --signal=B:30@60
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --out=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-scout-bench-m-full-%j.out
#SBATCH --err=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-scout-bench-m-full-%j.err
#
# AEGIS scout — generic model scout (Ollama path) on FULL PIPELINE.
#
# Model is passed as the FIRST CLI argument (NOT via --export):
#   sbatch examples/deucalion/scout-bench-m-aegis-full.sbatch muse-glimmer:30b
#
# IMPORTANT — distinct job-names per model: when running multiple scouts
# in parallel (``sbatch ... nemotron3.5:30b && sbatch ... granite4.2:30b
# && sbatch ... ornith-1.5:9b``), all jobs default to ``aegis_scout_full``
# which makes ``squeue`` unreadable. Use the wrapper below, which sends
# the sanitised model tag as a per-model job-name:
#
#   eval "$(scripts/scouts/scout-full-submit.sh nemotron3.5:30b)"
#   eval "$(scripts/scouts/scout-full-submit.sh granite4.2:30b)"
#   eval "$(scripts/scouts/scout-full-submit.sh ornith-1.5:9b)"
#
# Each invocation prints the exact `sbatch -J aegis_<model-tag> ...`
# command ready to paste so the job-name shows the model in `squeue`.
#
# Differs from scout-bench-m-aegis.sbatch (Phase 1B-only) in:
# 1. Runs the full pipeline (``--run-all``) instead of just
#    ``--run-phase-1b``, so every scout produces the complete set of
#    9 docs + xlsx (matching the gold Doc 05 set plus 04a-04d / 06 /
#    07 / 07b).
# 2. 1h30m walltime (the dev partition often reuses idle queue slots;
#    30 min was being hit by §6 + §7 b LLM rounds).
# 3. Logs every step to /projects/.../logs/scout_full_<MODEL>_<JOBID>.log.
#
# IMPORTANT: only use this for models that have already cleared a
# Phase 1B scout successfully (you've seen ``aggregated_data`` populated
# in the digest). A bare Phase 1B scout is still the right starting
# point for a model you haven't profiled yet.

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
LOG_DIR="$BD/aegis-phase1/logs/scout_runs"
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/scout_full_${1:-unknown}_${SLURM_JOB_ID}.log"

if [ $# -lt 1 ]; then
  echo "usage: sbatch $0 <model:tag>" | tee -a "$RUN_LOG"
  exit 2
fi
MODEL="$1"
exec >>"$RUN_LOG" 2>&1

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : $MODEL (Ollama, 1x A100-80, 1h30m)"
echo " Node  : $(hostname)"
echo " Scope : case1-tinytask, --run-all (full pipeline)"
echo " RUN_LOG: $RUN_LOG"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

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
echo "=== running scout (full pipeline: 1B + MAP + REDUCE + OUTPUT) ==="
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --model "$MODEL" \
    --provider ollama \
    --run-all \
    --log-level INFO \
    --output "output/scout_full_${SLURM_JOB_ID}"

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