#!/usr/bin/env bash
#SBATCH --account=F202512235CPCAA1G
#SBATCH --partition=normal-a100-80
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=2-00:00:00
#SBATCH --output=slurm-kgeval-pilot-%j.out
#SBATCH --error=slurm-kgeval-pilot-%j.err
#SBATCH --signal=B:30@300
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#
# CORR-113 — KG Eval T1 pilot sbatch (Protocol v1.1).
#
# Runs one model on T1 across 3 cases × 5 families × 2 arms = 30 generations.
# Hard abort on MockInvoker (the v1.1 anti-mock guard). Scoreboard via
# scripts/kg_eval/score_t1.py on the workstation after scp.
#
# Submission (from login.deucalion.macc.fccn.pt):
#   cd /projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#   sbatch -J aegis_kgeval_pilot_<sanitised-tag> \
#          examples/deucalion/kg-eval-t1-pilot.sbatch <model:tag>
#   e.g.  sbatch -J aegis_kgeval_pilot_nemotron_30b \
#             examples/deucalion/kg-eval-t1-pilot.sbatch nemotron-3.5-lightning:30b
#
# The job self-verifies: anti-mock smoke test BEFORE the 30-run loop. If the
# invoker resolves to MockInvoker, the job aborts with status=2 (no run-dir
# artefacts produced). This closes the silent-mock gap.

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
GFX="/projects/F202512235CPCAA1/graphify-methodology"

MODEL="${1:?usage: sbatch kg-eval-t1-pilot.sbatch <model:tag>}"
SANITISED_TAG=$(echo "$MODEL" | tr ':.' '__')

CASES=(case1-tinytask case2-secureborder case3-omnibank)
FAMILIES=(T1.1 T1.2 T1.3 T1.4 T1.5)
ARMS=(with-kg no-kg)

PORT=$((11434 + SLURM_JOB_ID % 20000))

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : $MODEL (1x A100-80, 2-day walltime, port $PORT)"
echo " Pilot : 3 cases × 5 families × 2 arms = 30 runs"
echo " Node  : $(hostname)"
echo " Code  : $(cat "$PROJ/.synced_sha" 2>/dev/null || echo unknown)"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# --- Ollama 0.32.13 (shared model cache; never `ollama pull` here) ---
export PATH="$GFX/bin:$PATH"
export LD_LIBRARY_PATH="$GFX/lib/ollama:${LD_LIBRARY_PATH:-}"
export OLLAMA_MODELS="$BD/ollama_data/models"
export OLLAMA_HOST="127.0.0.1:$PORT"
export OLLAMA_BASE_URL="http://127.0.0.1:$PORT"
export OLLAMA_API_KEY="local"

ollama serve > "/tmp/ollama-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!

for i in $(seq 1 90); do
  if curl -sf -m 2 "http://127.0.0.1:${PORT}/api/tags" > /dev/null 2>&1; then
    break
  fi
  sleep 2
done
echo "=== ollama version:"
curl -sf -m 5 "http://127.0.0.1:${PORT}/api/version" | head -c 200; echo
echo "=== warm-up: loading $MODEL"
WARM_OK=0
for attempt in 1 2 3 4 5; do
  if curl -sf -m 180 "http://127.0.0.1:${PORT}/api/generate" \
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
export PYTHONDONTWRITEBYTECODE=1
export KG_EVAL_MODEL="$MODEL"
export KG_EVAL_PROVIDER="ollama"
export KG_EVAL_TEMP="0.1"

echo ""
echo "=== wiping stale .pyc + __pycache__ (defense-in-depth) ==="
find "$PROJ/src" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PROJ/src" -name "*.pyc" -delete 2>/dev/null || true

echo ""
echo "=== pre-flight (anti-mock smoke test) ==="
python -c "import aegis_phase1.v2.runner; print('aegis_phase1 OK')"
# Build the invoker exactly as run_t1 does; abort if it resolves to MockInvoker.
python -c "
from scripts.kg_eval.run_t1 import _invoker_from_env, _is_mock
inv = _invoker_from_env(model='$MODEL', provider='ollama', allow_mock=False)
if _is_mock(inv):
    raise SystemExit('ANTI-MOCK FAIL: invoker resolved to MockInvoker; aborting (status=2).')
print(f'anti-mock smoke OK: invoker class={type(inv).__name__}')
"

PILOT_LOG="$PROJ/logs/scout_runs/kgeval_pilot_${SANITISED_TAG}_${SLURM_JOB_ID}.log"
mkdir -p "$PROJ/logs/scout_runs"
{
  echo "pilot_id=${SANITISED_TAG}_${SLURM_JOB_ID}"
  echo "model=$MODEL"
  echo "cases=${CASES[*]}"
  echo "families=${FAMILIES[*]}"
  echo "arms=${ARMS[*]}"
  echo "gate_mode=hard"
  echo "workstation_sha=$(cat "$PROJ/.synced_sha" 2>/dev/null || echo unknown)"
  echo "started=$(date -Is)"
} > "$PILOT_LOG"

echo ""
echo "=== running pilot (30 generations; anti-mock guard on every call) ==="
set +e
PILOT_OK=0
PILOT_RC=0
for case in "${CASES[@]}"; do
  for family in "${FAMILIES[@]}"; do
    for arm in "${ARMS[@]}"; do
      echo ""
      echo "--- run case=$case family=$family arm=$arm ---"
      python -m scripts.kg_eval.run_t1 \
          --case "cases/${case}" \
          --task-family "$family" \
          --arm "$arm" \
          --model "$MODEL" \
          --provider "ollama" \
          --abort-on-mock \
          2>&1 | tee -a "$PILOT_LOG"
      RC=${PIPESTATUS[0]}
      if [ $RC -ne 0 ]; then
        echo "WARN: run failed rc=$RC (continuing pilot)" | tee -a "$PILOT_LOG"
        PILOT_RC=$RC
      else
        PILOT_OK=$((PILOT_OK + 1))
      fi
    done
  done
done
set -e

kill $OLLAMA_PID 2>/dev/null || true

# Scoring on the workstation happens after scp, but a quick deterministic
# pass here helps catch obvious issues before the model artefacts leave
# the cluster.
echo ""
echo "=== scoring runs locally ==="
python -m scripts.kg_eval.score_t1 --input-dir "$PROJ/output/kg_eval" --recursive 2>&1 | tee -a "$PILOT_LOG" | tail -30

# Tar the pilot output so scp back is one shot.
PILOT_TGZ="$PROJ/output/kgeval_pilot_${SANITISED_TAG}_${SLURM_JOB_ID}.tgz"
tar -czf "$PILOT_TGZ" -C "$PROJ/output" kg_eval 2>/dev/null || true
echo ""
echo "pilot_output_tgz=$PILOT_TGZ" | tee -a "$PILOT_LOG"
echo "ok_runs=$PILOT_OK / 30" | tee -a "$PILOT_LOG"
echo "ended=$(date -Is)" | tee -a "$PILOT_LOG"

echo ""
echo "=================================================="
echo " JOB $SLURM_JOB_ID FINISHED: $(date)"
echo " STATUS: pilot_complete ok_runs=$PILOT_OK / 30 (last_rc=$PILOT_RC)"
echo "=================================================="
exit $PILOT_RC
