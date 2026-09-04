#!/usr/bin/env bash
#SBATCH --account=F202512235CPCAA1G
#SBATCH --partition=normal-a100-80
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=2:00:00
#SBATCH --output=slurm-kgeval-t2-pilot-%j.out
#SBATCH --error=slurm-kgeval-t2-pilot-%j.err
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1

# CORR-115 — KG Eval T2 Navigation & Usability Pilot (Protocol v1.1 §8).
#
# Runs an interactive multi-turn graph navigation assessment with a model on Deucalion.
# Uses local Ollama instance with per-job random port (hpc-deucalion safe pattern).
#
# Usage:
#   sbatch examples/deucalion/kg-eval-t2-pilot.sbatch <model:tag>
#   e.g. sbatch examples/deucalion/kg-eval-t2-pilot.sbatch nemotron-3.5-lightning:30b

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
GFX="/projects/F202512235CPCAA1/graphify-methodology"

MODEL="${1:?usage: sbatch kg-eval-t2-pilot.sbatch <model:tag>}"
SANITISED_TAG=$(echo "$MODEL" | tr ':.' '__')

PORT=$((11434 + SLURM_JOB_ID % 20000))

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model : $MODEL (T2 Usability Navigation, port $PORT)"
echo " Node  : $(hostname)"
echo " Code  : $(cat "$PROJ/.synced_sha" 2>/dev/null || echo unknown)"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# --- Ollama 0.32.13 ---
export PATH="$GFX/bin:$PATH"
export LD_LIBRARY_PATH="$GFX/lib/ollama:${LD_LIBRARY_PATH:-}"
export OLLAMA_MODELS="$BD/ollama_data/models"
export OLLAMA_HOST="127.0.0.1:$PORT"
export OLLAMA_BASE_URL="http://127.0.0.1:$PORT"

ollama serve > "/tmp/ollama-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!

for i in $(seq 1 90); do
  if curl -sf -m 2 "http://127.0.0.1:${PORT}/api/tags" > /dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "=== warm-up: loading $MODEL"
WARM_OK=0
for attempt in 1 2 3 4 5; do
  if curl -sf -m 180 "http://127.0.0.1:${PORT}/api/generate" \
      -d "{\"model\":\"$MODEL\",\"prompt\":\"ping\",\"stream\":false,\"options\":{\"num_predict\":1}}" \
      > /tmp/warmup.out 2>&1; then
    echo "warm-up OK on attempt $attempt"
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

echo ""
echo "=== wiping stale .pyc + __pycache__ ==="
find "$PROJ/src" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PROJ/src" -name "*.pyc" -delete 2>/dev/null || true

OUT_DIR="$PROJ/output/kg_eval_t2/${SANITISED_TAG}_${SLURM_JOB_ID}"
mkdir -p "$OUT_DIR"

echo "=== running T2 navigation usability suite ==="
python -c "
import json
import yaml
from pathlib import Path
from scripts.kg_eval.run_t2 import run_t2_agent
from scripts.kg_eval.score_t2 import score_t2_run
from aegis_phase1.prompts_v2.invoker import build_llm_invoker

inv = build_llm_invoker(provider='ollama', model='$MODEL')

def invoker_call(prompt: str) -> str:
    res = inv.invoke(prompt)
    if hasattr(res, 'content'):
        return res.content
    return str(res)

invoker_call.model_name = '$MODEL'
invoker_call.provider_name = 'ollama'

tasks_file = Path('scripts/kg_eval/tasks_t2.yaml')
with tasks_file.open('r') as f:
    tasks_data = yaml.safe_load(f)

scorecards = []
for t in tasks_data.get('tasks', []):
    print(f'Running T2 task: {t[\"id\"]}')
    case_path = Path('cases') / t.get('case', 'case1-tinytask')
    preproc_root = Path('preproc_out')
    log = run_t2_agent(t, case_path, preproc_root, invoker_call)
    card = score_t2_run(log, optimal_query_count=t.get('optimal_query_count', 2))
    scorecards.append(card.__dict__)

out_path = Path('$OUT_DIR') / 't2_scorecards.json'
with out_path.open('w') as f:
    json.dump(scorecards, f, indent=2)
print('T2 suite finished successfully. Scorecards saved to', out_path)
"

kill $OLLAMA_PID 2>/dev/null || true
echo "=== JOB COMPLETED: $(date) ==="
