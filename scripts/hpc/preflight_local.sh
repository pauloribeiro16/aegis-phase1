#!/usr/bin/env bash
# preflight_local.sh — Estadio 0 (obrigatorio) antes de qualquer sbatch no Deucalion.
#
# Validacoes que NAO tocam o cluster nem o modelo:
#   1. bash -n em todos os sbatch (sintaxe)
#   2. imports Python (runner, orchestrator, parsers)
#   3. smoke deterministico: MOCK_LLM=true --deterministic-only (pipeline inteiro sem LLM)
#   4. tags de modelo (CLI args $*) vs cache do cluster (ssh read-only ao manifest dir)
#   5. ruff no que mudou
#
# Uso:
#   bash scripts/hpc/preflight_local.sh [--models "<tag1> <tag2>..."] [--sbatch-dir <dir>]
#
# Saida: imprime "OK" no fim se todos os checks passam. Exit code != 0 no primeiro erro.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SBATCH_DIR="${SBATCH_DIR_OVERRIDE:-$REPO_ROOT/examples/deucalion}"
PY_TARGETS=(src/aegis_phase1/v2/runner.py src/aegis_phase1/v2/orchestrator.py src/aegis_phase1/_archive/corr061/markdown_parser.py)
MODELS_TO_CHECK=()

usage() {
  cat <<'EOF'
Uso: bash scripts/hpc/preflight_local.sh [--models "<tags>"] [--sbatch-dir <dir>]
  --models  espaco-separado; verifica cache do cluster para cada tag
            (omite --ssh-check para nao tocar o cluster).
  --sbatch-dir  por omissao: examples/deucalion.
EOF
}

SSH_CHECK=1
models_next=0
while [ $# -gt 0 ]; do
  case "$1" in
    --models)
      models_next=1
      shift
      ;;
    --sbatch-dir) SBATCH_DIR="$2"; shift 2 ;;
    --no-ssh-check) SSH_CHECK=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [ "$models_next" -eq 1 ]; then
        MODELS_TO_CHECK+=("$1")
        shift
      else
        echo "unknown arg: $1"; usage; exit 2
      fi
      ;;
  esac
done

PASS=0
FAIL=0
section() { echo; echo "=== $* ==="; }
ok()      { PASS=$((PASS+1)); echo "  OK   $*"; }
err()     { FAIL=$((FAIL+1)); echo "  FAIL $*"; }

cd "$REPO_ROOT"

# 1. Sintaxe sbatch
section "1. bash -n em todos os sbatch"
missing=0
while IFS= read -r f; do
  if ! bash -n "$f" 2>/dev/null; then
    err "$f: bash -n falhou"
    missing=1
  else
    ok "$f"
  fi
done < <(find "$SBATCH_DIR" -type f -name '*.sbatch' | sort)
[ "$missing" -eq 0 ] || err "${missing} sbatch com sintaxe quebrada"

# 2. Imports Python (smoke load)
section "2. Python imports (runner / orchestrator / parser)"
PYTHONPATH=src LANGFUSE_ENABLED=false MOCK_LLM=true \
  /home/epmq-cyber/Área\ de\ Trabalho/projects/shared-venv-root/bin/python - <<'PY'
import importlib, sys
mods = [
    "aegis_phase1.v2.runner",
    "aegis_phase1.v2.orchestrator",
    "aegis_phase1._archive.corr061.markdown_parser",
    "aegis_phase1.prompts_v2.invoker",
    "aegis_phase1.prompts_v2.phase1_executor",
    "aegis_phase1.v2.output.doc_05",
    "aegis_phase1.v2.output.doc_04",
]
errors = []
for m in mods:
    try:
        importlib.import_module(m)
        print(f"  OK   import {m}", flush=True)
    except Exception as exc:
        print(f"  FAIL import {m}: {exc}", flush=True)
        errors.append(m)
sys.exit(1 if errors else 0)
PY
[ $? -eq 0 ] && ok "imports" || err "imports"

# 3. Smoke deterministico (NAO CHAMA MODELO)
section "3. Smoke deterministico (--deterministic-only)"
PYTHONPATH=src LANGFUSE_ENABLED=false MOCK_LLM=true \
  /home/epmq-cyber/Área\ de\ Trabalho/projects/shared-venv-root/bin/python \
  -m aegis_phase1.v2.runner --case cases/case1-tinytask --mock-llm --deterministic-only --output /tmp/aegis-preflight 2>&1 | tail -3
# Aceitamos o smoke deterministico se produziu Doc 04-07 + xlsx.
# §9 so aparece em runs com dados reais (pre-CORR-114 series),
# por isso nao exigimos aqui.
DOC_COUNT=$(ls /tmp/aegis-preflight/[0-9]*_*.md 2>/dev/null | wc -l)
if [ "$DOC_COUNT" -ge 4 ] && [ -f /tmp/aegis-preflight/Case_01_Phase1.xlsx ]; then
  ok "deterministic-only pipeline ($DOC_COUNT docs + xlsx)"
else
  err "deterministic-only: esperava 4+ docs + xlsx, obtive $DOC_COUNT"
fi

# 4. Cache do cluster (read-only ssh, opcionalmente)
section "4. Tags vs cache do cluster"
if [ -z "${MODELS_TO_CHECK:-}" ] || [ "${MODELS_TO_CHECK:-x}" = "x" ]; then
  echo "  skip (passe --models '<tag1> <tag2>' para verificar cache)"
elif [ "$SSH_CHECK" -eq 0 ]; then
  echo "  skip (--no-ssh-check)"
else
  CACHE_BASE="/projects/F202512235CPCAA1/CyberMetric_Deucalion/ollama_data/models/manifests/registry.ollama.ai/library"
  for tag in "${MODELS_TO_CHECK[@]}"; do
    name="${tag%:*}"
    sha="${tag##*:}"
    found=0
    # Mirror do cluster no workspace local; o mirror_commands.py faz
    # rsync periodico. Sem ele, fallback para ssh read-only.
    LOCAL_BASE="$REPO_ROOT/execution/runs/.cache-mirror"
    for candidate in "$name" "$(echo "$name" | tr '-' '_')"; do
      if [ -f "$LOCAL_BASE/$candidate/$sha" ] || [ -d "$LOCAL_BASE/$candidate/$sha" ]; then
        ok "$tag (cache hit em $candidate, mirror local)"
        found=1
        break
      fi
      if ssh -o ConnectTimeout=4 -o BatchMode=yes paulinho@login.deucalion.macc.fccn.pt \
          "ls $CACHE_BASE/$candidate/$sha" >/dev/null 2>&1 ; then
        ok "$tag (cache hit em $candidate, ssh)"
        found=1
        break
      fi
    done
    if [ "$found" -eq 0 ]; then
      err "$tag: NAO DETECTADO em cache (verifique ssh ou mirror)"
    fi
  done
fi

# 5. ruff nos ficheiros tocados
section "5. ruff lint nos modulos criticos"
/home/epmq-cyber/Área\ de\ Trabalho/projects/shared-venv-root/bin/python -m ruff check \
  "${PY_TARGETS[@]}" \
  tests/unit/v2/test_run_all_partial_docs_corr114.py 2>&1 | tail -5
[ ${PIPESTATUS[0]} -eq 0 ] && ok "ruff clean" || err "ruff reports issues"

echo
echo "============================================================"
if [ "$FAIL" -eq 0 ]; then
  echo "  PREFLIGHT OK ($PASS checks passed)"
  echo "  Submeta so Estadio 1 (smoke 1 GPU no Deucalion) com a certeza."
  exit 0
else
  echo "  PREFLIGHT FAIL ($FAIL problemas, $PASS OK)"
  exit 1
fi
