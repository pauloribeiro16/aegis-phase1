#!/usr/bin/env bash
#SBATCH --job-name=aegis_corr111_scout_gemma4_31b
#SBATCH --account=F202512235CPCAA1G
#SBATCH --partition=dev-a100-80
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=12
#SBATCH --mem=40G
#SBATCH --time=00:30:00
#SBATCH --output=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-corr111-scout-gemma4-31b-%j.out
#SBATCH --error=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/slurm-corr111-scout-gemma4-31b-%j.err
#SBATCH --signal=B:30@30
#SBATCH --chdir=/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1

# AEGIS scout for CORR-111 — gemma4:31b (Ollama) on Phase 1B only.
#
# Goal: prove the end-to-end CORR-111 pipeline on the cluster:
#   1. Sidecar manifest exists at /projects/.../aegis-quant-manifests/ollama/gemma4:31b@q4_k_m.json
#   2. Orchestrator.init_model_capabilities() reads it and stamps state["v2_model_capabilities"]
#   3. Doc 05's first line is "Model: gemma4:31b @ q4_K_M (job <JOBID>)"
#   4. The aegis: HTML frontmatter lands inside per_spec_markdown[spec]
#
# Submit from login.deucalion.macc.fccn.pt:
#   cd /projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1
#   sbatch examples/deucalion/scout-gemma4-31b-corr111-aegis.sbatch
#
# Pattern forked from examples/deucalion/scout-qwen38-aegis.sbatch (battle-tested).

set -euo pipefail

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
GFX="/projects/F202512235CPCAA1/graphify-methodology"
MODEL="gemma4:31b"
export AEGIS_QUANT_MANIFEST_ROOT="$BD/aegis-quant-manifests"
mkdir -p "$AEGIS_QUANT_MANIFEST_ROOT"

echo "=================================================="
echo " JOB $SLURM_JOB_ID STARTED: $(date)"
echo " Model: $MODEL (1x A100-80, 30m walltime)"
echo " Sidecar root: $AEGIS_QUANT_MANIFEST_ROOT"
echo "=================================================="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# --- Ollama 0.32.13 (shared cache; never `ollama pull` here) ---
export PATH="$GFX/bin:$PATH"
export LD_LIBRARY_PATH="$GFX/lib/ollama:${LD_LIBRARY_PATH:-}"
export OLLAMA_MODELS="$BD/ollama_data/models"
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_API_KEY="local"

ollama serve > "/tmp/ollama-corr111-${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!

# Wait for server
for i in $(seq 1 90); do
  if curl -sf -m 2 "http://127.0.0.1:11434/api/tags" > /dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "=== ollama version:"
curl -sf -m 5 "http://127.0.0.1:11434/api/version" | head -c 200; echo

# CORR-111 verification hook: confirm the sidecar exists & probe live quant
echo "=== sidecar before scout (CORR-111 expected):"
ls -la "$AEGIS_QUANT_MANIFEST_ROOT/ollama/" 2>&1
echo "=== detected quant (live):"
PATH="$GFX/bin:$PATH" LD_LIBRARY_PATH="$GFX/lib/ollama" ollama show "$MODEL" 2>&1 | grep -E "quantization|architecture" | head -3

# Warm-up: load model onto GPU; gemma4:31b at Q4_K_M ≈ 20 GB
WARM_OK=0
for attempt in 1 2 3 4 5; do
  if curl -sf -m 240 "http://127.0.0.1:11434/api/generate" \
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
  tail -60 "/tmp/ollama-corr111-${SLURM_JOB_ID}.log"
  kill $OLLAMA_PID 2>/dev/null || true
  exit 1
fi

echo "=== ollama ps:"
ollama ps || true

cd "$PROJ"
source .venv/bin/activate
export PYTHONPATH="$PROJ:${PYTHONPATH:-}"
export LANGFUSE_ENABLED=false

echo ""
echo "=== pre-flight ==="
python -c "import aegis_phase1.v2.runner; print('aegis_phase1 OK')"
python -c "
from aegis_phase1.llm.quant_manifest import resolve_quant_for
info = resolve_quant_for('$MODEL', 'ollama')
print('CORR-111 quant probe:', info['quantization'], '(provenance:', info['quantization_provenance'] + ')')
"

echo ""
echo "=== running scout (Phase 1B only) ==="
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --model "$MODEL" \
    --provider ollama \
    --run-phase-1b \
    --log-level INFO \
    --output "output/scout_corr111_gemma4_31b_${SLURM_JOB_ID}"

PYTHON_EXIT=$?

# CORR-111 verification: check that the produced Doc 05 has the aegis preamble
echo ""
echo "=== CORR-111 verification (post-run) ==="
DOC05_DIR="output/scout_corr111_gemma4_31b_${SLURM_JOB_ID}"
if [ -f "$DOC05_DIR/05_Regulatory_Applicability.md" ]; then
    echo "first 5 lines of Doc 05:"
    head -5 "$DOC05_DIR/05_Regulatory_Applicability.md" | sed 's/^/  /'
else
    echo "  (no Doc 05 produced — verifier skipped)"
fi
if [ -f "$DOC05_DIR/work/state.json" ]; then
    echo "v2_model_capabilities from state.json:"
    python -c "
import json
s = json.load(open('$DOC05_DIR/work/state.json'))
cap = s.get('v2_model_capabilities', {})
print('  model     :', cap.get('model'))
print('  provider  :', cap.get('provider'))
print('  quant     :', cap.get('quantization'))
print('  provenance:', cap.get('quantization_provenance'))
print('  job_id    :', cap.get('job_id'))
" 2>&1
fi

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
