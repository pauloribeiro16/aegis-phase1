#!/usr/bin/env bash
# CORR-057: orchestrator for the e2b baseline eval on Deucalion GPU.
# Called by eval-corr057.sbatch after env setup + Ollama start.
#
# Usage (inside sbatch):
#   bash scripts/eval/run_eval_deucalion.sh
#
# Requires these env vars (set by sbatch):
#   OLLAMA_HOST (default http://localhost:11434)
#   OLLAMA_BIN  (path to ollama binary)
#   RESULTS_DIR (where to persist artefacts)
#   PWD         (~/aegis-kg after cd)

set -euo pipefail
set -x  # trace para rastreabilidade

MODEL="${OLLAMA_MODEL:-gemma4:e2b}"
CASE="${EVAL_CASE:-cases/case1-tinytask}"
RESULTS_DIR="${RESULTS_DIR:-results/corr057-unknown}"
mkdir -p "$RESULTS_DIR"

echo "[eval] === CORR-057 eval baseline e2b ==="
echo "[eval] model=$MODEL case=$CASE"
echo "[eval] results=$RESULTS_DIR"

# 1. Verificar que o modelo está disponível no cache (não pull — pré-loaded)
echo "[eval] checking model availability"
ollama list 2>&1 | head -20
if ! ollama list 2>&1 | grep -q "e2b"; then
    echo "[eval] WARN: e2b not in list — will try anyway (may auto-download from registry)"
fi

# 2. Smoke de 1 chamada (validar que Ollama responde)
echo "[eval] === smoke test: 1 direct LLM call ==="
python <<EOF
import sys, time
sys.path.insert(0, "src")
from aegis_phase1.v2.llm import build_llm_invoker
inv = build_llm_invoker(model="gemma4:e2b", provider="ollama")
msg = inv.chat.invoke([{"role": "user", "content": "Reply with the word READY"}])
print(f"smoke response: {msg.content[:100]}")
print("SMOKE OK")
EOF

# 3. Limpar logs anteriores (cada run começa limpo)
rm -f logs/phase1/llm-calls.jsonl logs/phase1/format-errors.jsonl logs/phase1/performance.csv
mkdir -p logs/phase1

# 4. Correr a pipeline completa
echo "[eval] === full pipeline run ==="
START=$(date +%s)
python -m aegis_phase1.v2.runner \
    --case "$CASE" \
    --model "$MODEL" \
    --provider ollama \
    --run-all \
    2>&1 | tee "$RESULTS_DIR/corr057_run.log"
PIPELINE_EXIT=$?
END=$(date +%s)
echo "[eval] pipeline exit=$PIPELINE_EXIT duration=$((END-START))s"

# 5. Gerar relatório (mesmo se pipeline falhou — para ver onde parou)
echo "[eval] === generating report ==="
python scripts/eval/generate_report.py \
    --jsonl logs/phase1/llm-calls.jsonl \
    --output-dir "$RESULTS_DIR" \
    --preproc preproc_out \
    --output-md "$RESULTS_DIR/corr057_eval_report.md" \
    --output-json "$RESULTS_DIR/corr057_eval_data.json" \
    2>&1 | tee "$RESULTS_DIR/corr057_report.log" || echo "[eval] report generation failed (continuing)"

# 6. Copiar artefactos relevantes para RESULTS_DIR
cp -r logs/phase1 "$RESULTS_DIR/logs_phase1" 2>/dev/null || true
cp -r output/phase1/*.md "$RESULTS_DIR/" 2>/dev/null || true
cp -r output/phase1/*.xlsx "$RESULTS_DIR/" 2>/dev/null || true

echo "[eval] === DONE — artefacts in $RESULTS_DIR ==="
ls -la "$RESULTS_DIR"
