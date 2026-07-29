#!/usr/bin/env bash
#SBATCH --job-name=aegis-scout-corr057
#SBATCH --account=f202512235cpcaa1g
#SBATCH --partition=dev-a100-40
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=slurm-scout-corr057-%j.out
#SBATCH --error=slurm-scout-corr057-%j.err
#SBATCH --chdir=$HOME/aegis-kg

# CORR-057 scout — environment reconnaissance before eval job.
# Submit FIRST; only submit eval after this PASSes.

set -uo pipefail

echo "=== 1. Identity ==="
echo "whoami=$(whoami) hostname=$(hostname) date=$(date -u)"
echo "SLURM_JOB_ID=${SLURM_JOB_ID:-none}"

echo ""
echo "=== 2. Storage ==="
df -h "$HOME" 2>&1 | tail -2
ls -d "$HOME/aegis-kg" 2>&1

echo ""
echo "=== 3. Project ==="
cd "$HOME/aegis-kg" 2>/dev/null || { echo "FATAL: ~/aegis-kg missing"; exit 1; }
ls -la | head -10

echo ""
echo "=== 4. Python module ==="
module purge 2>/dev/null
module load Python/3.11.3-GCCcore-12.3.0 2>&1 || echo "WARN: python module load failed"
python --version 2>&1

echo ""
echo "=== 5. Venv ==="
if [ -d ".venv" ]; then
    source .venv/bin/activate
    which python
    python -c "import langchain_core; print(f'langchain_core OK')" 2>&1
    python -c "import aegis_phase1; print('aegis_phase1 OK')" 2>&1
else
    echo "MISSING .venv — create with: python -m venv --system-site-packages .venv && pip install -e .[dev]"
fi

echo ""
echo "=== 6. Ollama binary ==="
export PATH="/projects/F202512235CPCAA1/CyberMetric_Deucalion/bin:$PATH"
export OLLAMA_MODELS="/projects/F202512235CPCAA1/CyberMetric_Deucalion/ollama_data/models"
ollama --version 2>&1 || echo "WARN: ollama binary not runnable"

echo ""
echo "=== 7. Model cache (e2b available?) ==="
ollama list 2>&1 | head -30
echo ""
echo "e2b present in cache:"
ollama list 2>&1 | grep -i "e2b" || echo "WARN: e2b NOT in cache"

echo ""
echo "=== 8. GPU (none allocated for scout, but check partition) ==="
sinfo -p dev-a100-40 -o "%P %D %G %t" 2>&1 | head -5

echo ""
echo "=== 9. Case data sanity ==="
ls cases/case1-tinytask/case.yaml 2>&1
ls cases/case1-tinytask/data/phase1/ 2>&1 | head -5

echo ""
echo "=== SCOUT COMPLETE ==="
echo "Decision rules:"
echo "  - If python+venv+ollama+e2b all OK: submit eval-corr057.sbatch"
echo "  - If e2b missing from cache: submit examples/download-models.sbatch first"
echo "  - If venv missing: needs setup (see references/04-environment-setup.md)"
