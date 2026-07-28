#!/usr/bin/env bash
# CORR-070 CI gate: pipeline-input contract verification.
#
# Validates that the orchestrator's prompt-input construction has not
# silently dropped or added required fields. Two layers:
#
# 1. STRUCTURAL (hard fail): runs pytest
#    tests/unit/prompts_v2/test_pipeline_inputs.py::TestPipelineInputsStructural
#    which asserts the schema-declared required fields are present in
#    every (case, spec, lane) golden file.
#
# 2. GOLDEN (warn): runs the drift-detection tests
#    TestPipelineInputsGoldenDrift which log unexpected key/size changes.
#
# Exits 0 on pass, 1 on structural failure, 2 on missing fixtures.
#
# Usage:
#   bash .hooks/ci-pipeline-inputs.sh
#
# When the orchestrator changes intentionally, regenerate golden files:
#   python scripts/dev/regenerate-pipeline-inputs-golden.py
#   git add tests/fixtures/pipeline_inputs_golden/
#   git commit -m "chore: regenerate pipeline-inputs golden"

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SCHEMA="tests/fixtures/pipeline_inputs_golden/_schema.json"
GOLDEN_DIR="tests/fixtures/pipeline_inputs_golden"

# Check schema + golden files exist
if [ ! -f "$SCHEMA" ]; then
    echo "FAIL: $SCHEMA not present" >&2
    exit 2
fi
if [ ! -d "$GOLDEN_DIR/case1-tinytask" ] \
   || [ ! -d "$GOLDEN_DIR/case2-secureborder" ] \
   || [ ! -d "$GOLDEN_DIR/case3-omnibank" ]; then
    echo "FAIL: golden case directories missing" >&2
    echo "  Run: python scripts/dev/regenerate-pipeline-inputs-golden.py" >&2
    exit 2
fi

# Activate venv
if [ -d "../shared-venv" ]; then
    # shellcheck disable=SC1091
    source ../shared-venv/bin/activate
fi

# Run structural assertions (HARD fail)
echo "=== Layer 1: structural assertions (hard fail) ==="
PYTHONPATH=src pytest tests/unit/prompts_v2/test_pipeline_inputs.py::TestPipelineInputsStructural -v --tb=short
STRUCT_RC=$?

if [ $STRUCT_RC -ne 0 ]; then
    echo "" >&2
    echo "FAIL: structural assertions failed ($STRUCT_RC)" >&2
    echo "  Required fields are missing from one or more spec inputs." >&2
    echo "  If the pipeline change is intentional:" >&2
    echo "    1. Update $SCHEMA" >&2
    echo "    2. Run: python scripts/dev/regenerate-pipeline-inputs-golden.py" >&2
    echo "    3. Commit both" >&2
    exit 1
fi

# Run golden drift tests (WARN only)
echo ""
echo "=== Layer 2: golden drift detection (warn only) ==="
PYTHONPATH=src pytest tests/unit/prompts_v2/test_pipeline_inputs.py::TestPipelineInputsGoldenDrift -v --tb=line -W error::DeprecationWarning 2>&1 | tail -30 || true

# Count warnings (best-effort)
N_FILES=$(find "$GOLDEN_DIR" -name "*.json" -not -name "_schema.json" | wc -l)
echo ""
echo "OK: $N_FILES golden files verified, structural contract intact"
