#!/usr/bin/env bash
# Launcher: loads src/.env (where MINIMAX_API_KEY lives) and runs the
# AEGIS Phase 1 v2 pipeline in full run-all mode against MiniMax M3.
#
# Usage: _run_pipeline_m3.sh <case_dir> <output_dir> [<log_path>]
# No token appears in argv or stdout.

set -euo pipefail

REPO="/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1"
CASE_DIR="${1:?case dir required}"
OUTPUT_DIR="${2:?output dir required}"
LOG_PATH="${3:-/tmp/m3-runs/$(basename "$CASE_DIR").log}"

mkdir -p "$(dirname "$LOG_PATH")"

cd "$REPO"

# Load env vars from src/.env (where MINIMAX_API_KEY is stored)
set -a
source src/.env
set +a

export PYTHONPATH=src

exec python3 -m aegis_phase1.v2.runner \
  --case "$CASE_DIR" \
  --provider minimax \
  --model minimax/MiniMax-M3 \
  --run-all \
  --skip-reduce-llms \
  --output "$OUTPUT_DIR" \
  --log-level INFO
