#!/usr/bin/env bash
# _lib/common.sh — snippets partilhados pelos scripts em examples/deucalion/.
# Source este ficheiro UMA vez no inicio do sbatch (depois do set -euo pipefail),
# depois chama aegis_sbatch_hardening "<model:tag>" "<case-dir>".
#
# Politica:
# - Porta unica por JOB (resolve colisao Ollama no mesmo no).
# - RUN_LOG desde a linha 1 + trap (resolve jobs sem rasto).
# - Cache check por manifest dir (resolve ollama pull sem egress).
# - PYTHONDONTWRITEBYTECODE=1 (resolve .pyc stale).
# - AEGIS_LOG_BASE=logs/phase1/<case>/<JOB> (resolve logs por run).

BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"
PROJ="$BD/aegis-phase1"
GFX="/projects/F202512235CPCAA1/graphify-methodology"

aegis_sbatch_hardening() {
    if [ "$#" -ne 2 ]; then
        echo "usage: aegis_sbatch_hardening '<model:tag>' '<case-dir>'" >&2
        return 2
    fi
    local model_tag="$1"
    local case_dir="$2"

    # Porta unica por JOB (11434 + JOBID % 20000). Multi-job no mesmo no -> sem colisao.
    local port=$((11434 + SLURM_JOB_ID % 20000))
    export OLLAMA_HOST="127.0.0.1:${port}"
    export OLLAMA_BASE_URL="${OLLAMA_HOST}"
    export OLLAMA_API_KEY="local"

    # RUN_LOG desde a linha 1 (resolve jobs sem rasto). Tag limpa.
    local name="${model_tag%:*}"
    local sha="${model_tag##*:}"
    local sanitised=$(echo "${name}-${sha}" | tr ':.' '__' | tr -d '/')
    local log_dir="${PROJ}/logs/scout_runs"
    mkdir -p "${log_dir}"
    RUN_LOG="${log_dir}/run_${sanitised}_${case_dir}_${SLURM_JOB_ID}.log"
    export RUN_LOG
    exec >>"${RUN_LOG}" 2>&1
    trap 'aegis_sbatch_finalize' EXIT

    # Cache check por MANIFEST DIR. Fail-fast com mensagem clara.
    local name_norm=$(echo "${name}" | tr '.' '_')
    local cache_root="${BD}/ollama_data/models/manifests/registry.ollama.ai/library"
    if [ ! -e "${cache_root}/${name_norm}/${sha}" ] && [ ! -e "${cache_root}/${name}/${sha}" ]; then
        echo "ERROR: model '${model_tag}' NOT in cache."
        echo "       Run on login node:  bash scripts/hpc/pull-verify.sh ${model_tag}"
        exit 1
    fi

    # Logs por run (sem colisao entre jobs do mesmo modelo+caso).
    export AEGIS_LOG_BASE="${PROJ}/logs/phase1/${case_dir}/${SLURM_JOB_ID}"

    echo "JOB $SLURM_JOB_ID STARTED: $(date)"
    echo "MODEL: ${model_tag}  CASE: ${case_dir}  PORT: ${port}"
    echo "RUN_LOG: ${RUN_LOG}"
    echo "LOG_BASE: ${AEGIS_LOG_BASE}"
    echo "CACHE: OK (${cache_root}/${name})"
}

aegis_sbatch_finalize() {
    local rc=$?
    echo "END: $(date -Is)"
    echo "EXIT_CODE=$rc"
}

# Helper para o ollama warm-up, redireciona para a porta unica.
aegis_ollama_warmup() {
    local model_tag="$1"
    local attempts="${2:-5}"
    for i in $(seq 1 "$attempts"); do
        if curl -sf -m 180 "${OLLAMA_HOST}/api/generate" \
            -d "{\"model\":\"${model_tag}\",\"prompt\":\"ping\",\"stream\":false,\"options\":{\"num_predict\":1}}" \
            > /tmp/warmup.out 2>&1 ; then
            echo "warm-up OK on attempt $i"
            head -c 200 /tmp/warmup.out; echo
            return 0
        fi
        echo "warm-up attempt $i failed; sleeping 10s..."
        sleep 10
    done
    echo "ERROR: warm-up failed after $attempts attempts; aborting"
    return 1
}

# Helper para preparar o Python venv + .pyc defesa + Ollama env.
aegis_python_env() {
    cd "${PROJ}" || exit 2
    # shellcheck disable=SC1091
    source .venv/bin/activate
    export PYTHONPATH="${PROJ}:${PYTHONPATH:-}"
    export LANGFUSE_ENABLED=false
    export PYTHONDONTWRITEBYTECODE=1
}

# Atalho para iniciar ollama serve com o PATH correcto e porta unica.
aegis_start_ollama() {
    export PATH="${GFX}/bin:${PATH}"
    export LD_LIBRARY_PATH="${GFX}/lib/ollama:${LD_LIBRARY_PATH:-}"
    export OLLAMA_MODELS="${BD}/ollama_data/models"
    ollama serve > "/tmp/ollama-${SLURM_JOB_ID}.log" 2>&1 &
    OLLAMA_PID=$!

    for i in $(seq 1 90); do
        if curl -sf -m 2 "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    echo "ERROR: ollama serve nao respondeu em ${OLLAMA_HOST} (90 tentativas)"
    kill "${OLLAMA_PID}" 2>/dev/null || true
    return 1
}
