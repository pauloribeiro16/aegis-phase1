#!/usr/bin/env bash
#SBATCH --job-name=aegis-eval-corr057
#SBATCH --account=f202512235cpcaa1g
#SBATCH --partition=dev-a100-40
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --output=slurm-eval-corr057-%j.out
#SBATCH --error=slurm-eval-corr057-%j.err
#SBATCH --chdir=$HOME/aegis-kg

# CORR-057 eval — full pipeline run on GPU + auto report.
# Submit AFTER scout-corr057 PASSes.

set -euo pipefail
set -x
umask 077

# 1. Modules
module purge
module load Python/3.11.3-GCCcore-12.3.0
module load ollama/0.20.3-GCCcore-14.2.0-CUDA-12.8.0 2>/dev/null || true

# 2. Ollama paths (skill: use shared binary + cache)
export PATH="/projects/F202512235CPCAA1/CyberMetric_Deucalion/bin:$PATH"
export LD_LIBRARY_PATH="/projects/F202512235CPCAA1/CyberMetric_Deucalion/lib/ollama:$LD_LIBRARY_PATH"
export OLLAMA_MODELS="/projects/F202512235CPCAA1/CyberMetric_Deucalion/ollama_data/models"
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="gemma4:e2b"

# 3. CRITICAL: Langfuse OFF (Deucalion has no Langfuse; .env default points to localhost:3000)
export LANGFUSE_ENABLED="false"
unset LANGFUSE_BASE_URL LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY

# 4. Secrets
if [ -f "$HOME/.aegis_env" ]; then
    set -a
    source "$HOME/.aegis_env"
    set +a
fi

# 5. Venv
cd "$HOME/aegis-kg"
source .venv/bin/activate
export PYTHONPATH="$PWD:$PYTHONPATH"

# 6. GPU sanity
echo "[eval] === GPU ==="
nvidia-smi 2>&1 | head -10 || { echo "FATAL: no GPU"; exit 1; }

# 7. Start Ollama
echo "[eval] === starting ollama ==="
SCRATCH_JOB="/tmp/aegis-job-${SLURM_JOB_ID}"
mkdir -p "$SCRATCH_JOB"
ollama serve > "$SCRATCH_JOB/ollama.log" 2>&1 &
OLLAMA_PID=$!

cleanup() {
    echo "[eval] cleanup"
    kill "$OLLAMA_PID" 2>/dev/null || true
    wait "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup EXIT SIGTERM SIGINT

# Wait for ready
for i in {1..30}; do
    if curl -sf http://localhost:11434/ >/dev/null 2>&1; then
        echo "[eval] ollama ready after $i attempts"
        break
    fi
    sleep 2
done
curl -sf http://localhost:11434/ >/dev/null 2>&1 \
    || { echo "FATAL: ollama not ready"; cat "$SCRATCH_JOB/ollama.log" >&2; exit 1; }

# 8. Results dir
RESULTS_DIR="$HOME/aegis-kg/results/corr057-${SLURM_JOB_ID}"
mkdir -p "$RESULTS_DIR"

# 9. Run eval
export RESULTS_DIR
bash scripts/eval/run_eval_deucalion.sh

# 10. Done
echo "[eval] === JOB COMPLETE ==="
echo "[eval] results: $RESULTS_DIR"
ls -la "$RESULTS_DIR"
