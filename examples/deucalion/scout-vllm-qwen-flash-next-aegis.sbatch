#!/usr/bin/env bash
#SBATCH --job-name=aegis_scout_vllm_qwen_flash_next
#SBATCH --gres=gpu:a100:8
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --tasks-per-node=1
#SBATCH -A F202512235CPCAA1G
#SBATCH -t 04:00:00
#SBATCH -p dev-a100-80
#SBATCH --qos=normal
#SBATCH -N 1
#SBATCH --signal=B:30@120
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --out=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-scout-vllm-qwen-flash-next-%j.out
#SBATCH --err=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-scout-vllm-qwen-flash-next-%j.err
#
# AEGIS scout — Qwen3.8-Flash-Next (HuggingFace repo Qwen/Qwen3.8-Flash-Next)
# served via vLLM on the cluster.
#
# CORR-110 + Phase-1B scout (4 LLM calls only). Submission
# overrrides AEGIS_SCOPE=phase-1b (the file default is run-all; we
# want the cheap scout for first contact with this model).
#
# Allocation (overrides the file-defaults sized for the original
# gemma-4-31B-it pilot):
#   * 8 × A100-80GB on the same node (TP=8)
#   * dev-a100-80 partition (dev slots are <4h; this fits at 4h)
#   * 4h walltime (vLLM compile + load for a 125B MoE BF16 = ~360 GB
#     weights is non-trivial; the first minute after `vllm serve`
#     can hit CUDA-graph compile)
#   * 32 CPUs + 128G RAM (CPUs for vLLM workers / dataloader; RAM for
#     the ~360 GB weight staging buffer)
#
# CORR-110 plumbing: ChatOpenAICompat (no new project dep, only httpx).
# Pipeline connects to vLLM via ``--provider vllm --model
# 'vllm:qwen3.8-flash-next'``; env vars ``AEGIS_VLLM_BASE_URL`` (default
# http://localhost:8000/v1) and ``AEGIS_VLLM_TIMEOUT`` (default 600s)
# override defaults without touching code.
#
# Submit:
#   sbatch --export=AEGIS_SCOPE=phase-1b \
#          examples/deucalion/scout-vllm-qwen-flash-next-aegis.sbatch
#
# Override defaults via env on the submit line:
#   sbatch --export=AEGIS_SCOPE=phase-1b,VLLM_MAX_MODEL_LEN=8192,VLLM_GPU_MEMORY_UTILIZATION=0.90 \
#          examples/deucalion/scout-vllm-qwen-flash-next-aegis.sbatch

set -euo pipefail
umask 077

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
LOG_DIR="$BD/aegis-phase1/logs/scout_runs"
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/scout_vllm_qwen3_8_flash_next_${SLURM_JOB_ID}.log"
exec >>"$RUN_LOG" 2>&1

# --- HF base (CORR-110 follow-up, 2026-09-02) ---
# Qwen3.8-Flash-Next is ~360 GB in BF16 — too big for the 500 GB
# Lustre volume ($BD). Stage on $HOME (NFS, 23 TB free) instead.
# Override HFB on the sbatch line if the staging dir differs.
: "${HFB:=/home/paulinho/models/hf}"
mkdir -p "$HFB"
echo "[vllm] HF base = $HFB"

# --- Config (override via env on sbatch line) ---
: "${VLLM_MODEL:=$HFB/Qwen_Qwen3.8-Flash-Next}"
: "${VLLM_PORT:=8000}"
: "${VLLM_MAX_MODEL_LEN:=16384}"
: "${VLLM_GPU_MEMORY_UTILIZATION:=0.92}"
: "${VLLM_TENSOR_PARALLEL_SIZE:=8}"
: "${VLLM_DTYPE:=bfloat16}"
: "${AEGIS_SCOPE:=run-all}"   # submit --export=AEGIS_SCOPE=phase-1b for the cheap scout
export VLLM_MODEL VLLM_PORT VLLM_MAX_MODEL_LEN VLLM_GPU_MEMORY_UTILIZATION VLLM_DTYPE VLLM_TENSOR_PARALLEL_SIZE
export AEGIS_VLLM_BASE_URL="http://127.0.0.1:${VLLM_PORT}/v1"
export AEGIS_VLLM_TIMEOUT=900   # long rationales on Flash-Next

# --- Served model name the pipeline asks for (must match vllm --served-model-name) ---
SERVED_NAME="qwen3.8-flash-next"

# --- vLLM environment (cybermetric venv reuses the cluster venv) ---
VENV_PATH="${AEGIS_VLLM_VENV:-$BD/aegis-venv-root}"
if [[ ! -x "$VENV_PATH/bin/python" ]]; then
  echo "FATAL: venv not found at $VENV_PATH"
  echo "       set AEGIS_VLLM_VENV to the venv that has vllm installed"
  echo "       (cybermetric-vllm-cache/venv is the working one)"
  exit 3
fi

JOB_TMP="/tmp/aegis-job-${SLURM_JOB_ID}"
mkdir -p "$JOB_TMP"
VLLM_LOG="$JOB_TMP/vllm.log"

echo "=================================================="
echo " vLLM SCOUT — Qwen3.8-Flash-Next (CORR-110)"
echo " Job       : $SLURM_JOB_ID on $(hostname)"
echo " HF repo   : Qwen/Qwen3.8-Flash-Next"
echo " Weights   : $VLLM_MODEL"
echo " Served as : $SERVED_NAME"
echo " Port      : $VLLM_PORT"
echo " Scope     : $AEGIS_SCOPE"
echo " TP        : $VLLM_TENSOR_PARALLEL_SIZE (matches --gres=gpu:a100:8)"
echo " max-len   : $VLLM_MAX_MODEL_LEN"
echo " dtype     : $VLLM_DTYPE"
echo " RUN_LOG   : $RUN_LOG"
echo " VLLM_LOG  : $VLLM_LOG"
echo " Started   : $(date)"
echo "=================================================="

# --- GPU sanity ---
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# --- vLLM sanity ---
"$VENV_PATH/bin/vllm" --version || {
  echo "FATAL: vllm binary not on PATH inside venv $VENV_PATH"
  exit 4
}

# --- HF cache co-located with the model on NFS ($HFB) ---
# Compute nodes have no egress. Pre-stage model on the login node
# with `hf download Qwen/Qwen3.8-Flash-Next --local-dir $HFB/...`.
export HF_HOME="${HF_HOME:-$HFB/.cache}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME/hub}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
mkdir -p "$HF_HUB_CACHE"
echo "[vllm] HF_HOME=$HF_HOME"
echo "[vllm] HF_HUB_CACHE=$HF_HUB_CACHE"
echo "[vllm] HF_HUB_OFFLINE=$HF_HUB_OFFLINE"

# --- Start vLLM in background ---
echo "[vllm] starting vllm serve (background) ..."
"$VENV_PATH/bin/vllm" serve "$VLLM_MODEL" \
  --host 127.0.0.1 \
  --port "$VLLM_PORT" \
  --tensor-parallel-size "$VLLM_TENSOR_PARALLEL_SIZE" \
  --dtype "$VLLM_DTYPE" \
  --max-model-len "$VLLM_MAX_MODEL_LEN" \
  --gpu-memory-utilization "$VLLM_GPU_MEMORY_UTILIZATION" \
  --served-model-name "$SERVED_NAME" \
  --enforce-eager \
  > "$VLLM_LOG" 2>&1 &
VLLM_PID=$!
echo "[vllm] pid=$VLLM_PID"

cleanup() {
  echo "[vllm] cleanup"
  if [[ -n "${VLLM_PID:-}" ]] && kill -0 "$VLLM_PID" 2>/dev/null; then
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT SIGTERM SIGINT

# --- Wait for vLLM readiness ---
echo "[vllm] waiting for HTTP on http://127.0.0.1:${VLLM_PORT}/v1/models ..."
READY=0
for i in $(seq 1 90); do  # 90 * 10s = 15 min upper bound
  if curl -sf "http://127.0.0.1:${VLLM_PORT}/v1/models" >/dev/null 2>&1; then
    echo "[vllm] HTTP ready after ${i} attempts (~$(($i * 10))s)"
    READY=1
    break
  fi
  sleep 10
done
if [[ "$READY" -ne 1 ]]; then
  echo "[vllm] FATAL: not ready after 15 min"
  echo "----- last 80 lines of $VLLM_LOG -----"
  tail -80 "$VLLM_LOG" || true
  exit 5
fi

echo "[vllm] served models:"
curl -sf "http://127.0.0.1:${VLLM_PORT}/v1/models" || true
echo ""

# --- Pipeline venv (separate from vLLM venv — pip-deps don't overlap) ---
cd "$PROJ"
source .venv/bin/activate

export PYTHONPATH="$PROJ:${PYTHONPATH:-}"
export LANGFUSE_ENABLED=false

# CORR-109 follow-up: stale .pyc cache in src/aegis_phase1/**/__pycache__/
# has bitten us twice (2026-09-02 — ImportError 'P1BLLM02Parser'). Wipe
# + disable bytecode-write for the duration of the run.
echo "=== wiping stale .pyc + __pycache__ (defense-in-depth) ==="
find "$PROJ/src" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PROJ/src" -name "*.pyc" -delete 2>/dev/null || true
export PYTHONDONTWRITEBYTECODE=1

echo ""
echo "=== pre-flight ==="
python -c "import aegis_phase1.v2.runner; print('aegis_phase1 OK')"

# --- Run the pipeline ---
echo ""
echo "=== running scout ($AEGIS_SCOPE) ==="
case "$AEGIS_SCOPE" in
  phase-1b)
    RUN_FLAG="--run-phase-1b"
    OUT_DIR="output/scout_vllm_qwen3_8_flash_next_${SLURM_JOB_ID}"
    ;;
  run-all)
    RUN_FLAG="--run-all"
    OUT_DIR="output/scout_full_vllm_qwen3_8_flash_next_${SLURM_JOB_ID}"
    ;;
  *)
    echo "FATAL: AEGIS_SCOPE=$AEGIS_SCOPE (expected phase-1b or run-all)"
    exit 6
    ;;
esac

python -m aegis_phase1.v2.runner \
  --case cases/case1-tinytask \
  --model "vllm:${SERVED_NAME}" \
  --provider vllm \
  "$RUN_FLAG" \
  --log-level INFO \
  --output "$OUT_DIR"

PYTHON_EXIT=$?

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