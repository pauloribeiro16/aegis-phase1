#!/usr/bin/env bash
#SBATCH --job-name=aegis_stage_qwen_flash
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --tasks-per-node=1
#SBATCH -A F202512235CPCAA1G
#SBATCH -t 03:00:00
#SBATCH -p dev-a100-40
#SBATCH --qos=normal
#SBATCH -N 1
#SBATCH --signal=B:30@120
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#SBATCH --out=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-stage-qwen-flash-%j.out
#SBATCH --err=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-stage-qwen-flash-%j.err
#
# Stage Qwen/Qwen3.8-Flash-Next onto NFS ($HOME) for the vLLM scout.
#
# The model is ~360 GB in BF16 — too big for the 500 GB Lustre
# volume that already holds the rest of the project. CORR-110
# follow-up (2026-09-02): stage on NFS /home/paulinho (23 TB free).
#
# Uses the project's venv (hf download replaces the deprecated
# huggingface-cli).

set -euo pipefail
umask 077

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
# CORR-110 follow-up (2026-09-02): staging moved back to Lustre
# after the ollama_data + gemma-4-31B-it purge freed 266 GB.
# Override HFB on the sbatch line to use $HOME (NFS) if Lustre is
# saturated again.
HFB="${HFB:-$BD/models/hf}"
DEST="$HFB/Qwen_Qwen3.8-Flash-Next"
LOG_DIR="$BD/aegis-phase1/logs/scout_runs"
mkdir -p "$LOG_DIR" "$DEST" "$HFB"
RUN_LOG="$LOG_DIR/stage_qwen_flash_next_${SLURM_JOB_ID}.log"
exec >>"$RUN_LOG" 2>&1

echo "=================================================="
echo " HF DOWNLOAD — Qwen/Qwen3.8-Flash-Next"
echo " Job       : $SLURM_JOB_ID on $(hostname)"
echo " Dest      : $DEST"
echo " Started   : $(date)"
echo " RUN_LOG   : $RUN_LOG"
echo "=================================================="
df -h /home/paulinho 2>&1 | tail -2
df -h /projects/F202512235CPCAA1 2>&1 | tail -2

cd "$PROJ"
source .venv/bin/activate

export HF_HOME="$HFB/.cache"
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_TOKEN=$(cat ~/.aegis_env 2>/dev/null | grep HF_TOKEN | cut -d= -f2- || echo "")
mkdir -p "$HF_HUB_CACHE"

echo "[stage] activating venv OK; HF_HOME=$HF_HOME"
echo "[stage] HF_TOKEN=${HF_TOKEN:+set (${#HF_TOKEN} chars)}"

if [ -f "$DEST/config.json" ] && [ -f "$DEST/tokenizer.model" ]; then
  echo "[stage] $DEST already populated, skipping"
else
  cd "$DEST"
  # NOTE: the new `hf` CLI (successor of the deprecated huggingface-cli)
  # has NO --resume-download flag; resumption is the default behaviour.
  hf download Qwen/Qwen3.8-Flash-Next \
    --local-dir . \
    --token "$HF_TOKEN" \
    --max-workers 8 2>&1 | tail -20
fi

echo "[stage] final state:"
ls -la "$DEST" | head -20
du -sh "$DEST"

echo "=================================================="
echo " JOB $SLURM_JOB_ID FINISHED: $(date)"
echo "=================================================="