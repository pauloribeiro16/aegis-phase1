#!/usr/bin/env bash
# CORR-035 CI gate: DomainAnalysis outputs audit.
#
# Runs scripts.audit.audit_da_outputs and fails the build on any
# CRITICAL or HIGH finding. MEDIUM/LOW are reported but not gated
# (they're tracked in the audit report for follow-up).
#
# Exits 0 on clean (no CRITICAL/HIGH), 1 on findings, 2 on missing
# inputs, 3 on script failure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

DA_DIR="preproc_out/crossregulation/DomainAnalysis"
PY="${PYTHON:-/home/epmq-cyber/Área de Trabalho/projects/shared-venv/bin/python}"
if [ ! -x "$PY" ]; then
    PY="python"
fi

if [ ! -d "$DA_DIR" ]; then
    echo "FAIL: $DA_DIR not present (run \`python -m scripts.preprocess build\`)" >&2
    exit 2
fi

# Run the audit. Capture the JSON output.
OUT=$(PYTHONPATH=src "$PY" -m scripts.audit.audit_da_outputs --only HIGH --json 2>&1) || {
    echo "FAIL: audit script crashed" >&2
    echo "$OUT" >&2
    exit 3
}

# Parse counts
CRIT=$(echo "$OUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['by_severity'].get('CRITICAL', 0))")
HIGH=$(echo "$OUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['by_severity'].get('HIGH', 0))")
MED=$(echo "$OUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['by_severity'].get('MEDIUM', 0))")
LOW=$(echo "$OUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['by_severity'].get('LOW', 0))")
FILES=$(echo "$OUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['files_scanned'])")

echo "DA audit: $FILES files scanned — CRITICAL=$CRIT HIGH=$HIGH MEDIUM=$MED LOW=$LOW"

if [ "$CRIT" -ne 0 ] || [ "$HIGH" -ne 0 ]; then
    echo "FAIL: $CRIT CRITICAL + $HIGH HIGH findings in $DA_DIR" >&2
    echo "Run \`PYTHONPATH=src python -m scripts.audit.audit_da_outputs\` for details" >&2
    exit 1
fi

echo "OK: no CRITICAL or HIGH findings in $DA_DIR (MEDIUM=$MED LOW=$LOW tracked but not gated)"
