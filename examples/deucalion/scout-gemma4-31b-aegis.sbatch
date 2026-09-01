#!/usr/bin/env bash
#SBATCH --job-name=aegis_scout_gemma4_31b
#SBATCH --gres=gpu:a100:3
#SBATCH --cpus-per-task=12
#SBATCH --mem=30G
#SBATCH --tasks-per-node=1
#SBATCH -A F202512235CPCAA1G
#SBATCH -t 01:00:00
#SBATCH -p dev-a100-40
#SBATCH --qos=normal
#SBATCH -N 1
#SBATCH --signal=B:30@30
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --out=slurm-scout-gemma4-31b-%j.out
#SBATCH --err=slurm-scout-gemma4-31b-%j.err
#
# AEGIS scout — gemma-4-31B-it (HF transformers) on Phase 1B only.
#
# CORR-106: `--provider transformers` is now respected end-to-end.
# Before this fix, the factory ignored the flag and probed Ollama at
# localhost:11434 (which is absent on Deucalion) → run aborted with
# "Ollama not reachable" before the HF model was ever asked to load.
# See CONTRACT-106 for the full diagnosis.
#
# Walltime 1h: model load ~30 s + 4 LLM calls (Phase 1B). qwen3.5
# scout on the same shape (qwen3.5:27b) ran in 18:33 — generous
# budget for the first transformers scout where load path is unknown.

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
HF_MODEL="$BD/models/hf/google_gemma-4-31B-it"

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : gemma-4-31B-it (HF transformers, 3x A100-40, 1h)"
echo " Node  : $(hostname)"
echo " Scope : case1-tinytask, --run-phase-1b only"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

cd "$PROJ"
source .venv/bin/activate

export HF_HOME="$BD/models/hf/.cache"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export LANGFUSE_ENABLED=false
export PYTHONPATH="$PROJ:${PYTHONPATH:-}"
# CORR-107 follow-up: TransformersInvoker should read this. For now
# the env var is set so a future fix can pick it up; gemma4 31B with
# 1024 default tokens truncates Phase 1B rationale.
export AEGIS_MAX_NEW_TOKENS="${AEGIS_MAX_NEW_TOKENS:-16384}"

CACHE_ROOT="$BD/.cache"
mkdir -p "$CACHE_ROOT"
export TRITON_CACHE_DIR="$CACHE_ROOT/triton"
export TORCHINDUCTOR_CACHE_DIR="$CACHE_ROOT/inductor"
export XDG_CACHE_HOME="$CACHE_ROOT/xdg"
export HF_HUB_CACHE="$CACHE_ROOT/hub"
export TRANSFORMERS_CACHE="$CACHE_ROOT/transformers"
export TORCH_HOME="$CACHE_ROOT/torch"
export TMPDIR="$CACHE_ROOT/tmp"
mkdir -p "$TRITON_CACHE_DIR" "$TORCHINDUCTOR_CACHE_DIR" "$XDG_CACHE_HOME" \
         "$HF_HUB_CACHE" "$TRANSFORMERS_CACHE" "$TORCH_HOME" "$TMPDIR"

echo ""
echo "=== pre-flight ==="
python -c "
import os
os.environ.setdefault('HF_HUB_OFFLINE','1')
import torch, transformers
print('torch:', torch.__version__, 'cuda:', torch.cuda.is_available(), 'devices:', torch.cuda.device_count())
from transformers import AutoTokenizer
t = AutoTokenizer.from_pretrained(os.environ.get('HF_MODEL', '$HF_MODEL'))
print('tokenizer loaded:', t.__class__.__name__)
"
python -c "import aegis_phase1.v2.runner; print('aegis_phase1 OK')"

echo ""
echo "=== running scout (Phase 1B only) ==="
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --model "$HF_MODEL" \
    --provider transformers \
    --run-phase-1b \
    --log-level INFO \
    --output "output/scout_gemma4_31b_${SLURM_JOB_ID}"

PYTHON_EXIT=$?

echo ""
echo " JOB $SLURM_JOB_ID FINISHED: $(date)"
if [ $PYTHON_EXIT -eq 0 ]; then
  echo " STATUS: SUCCESS"
else
  echo " STATUS: FAILED ($PYTHON_EXIT)"
fi
exit $PYTHON_EXIT