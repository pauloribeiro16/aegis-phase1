#!/usr/bin/env bash
# .hooks/validate-contracts.sh
# Pre-push validation script for AEGIS contracts.
# Runs the 8 critical checks defined in CORR-003 Phase B.
#
# Usage: ./scripts/run_phase1.py  (.hooks/validate-contracts.sh)
#        or manually:  bash .hooks/validate-contracts.sh

set -eu

cd "$(dirname "$0")/.."

REPO_ROOT="$(pwd)"
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
CYAN=$'\033[0;36m'
RESET=$'\033[0m'

PASS=0
FAIL=0
WARN=0

declare -a FAILURES

check() {
    local name="$1"
    local cmd="$2"
    echo "${CYAN}▶ $name${RESET}"
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  ${GREEN}PASS${RESET}"
        PASS=$((PASS+1))
    else
        echo "  ${RED}FAIL${RESET}"
        FAIL=$((FAIL+1))
        FAILURES+=("$name")
    fi
}

warn_check() {
    local name="$1"
    local cmd="$2"
    echo "${CYAN}▶ $name (warning only)${RESET}"
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  ${GREEN}PASS${RESET}"
    else
        echo "  ${YELLOW}WARN${RESET}"
        WARN=$((WARN+1))
    fi
}

echo ""
echo "${CYAN}═══════════════════════════════════════════${RESET}"
echo "${CYAN}  AEGIS Contract Validation${RESET}"
echo "${CYAN}═══════════════════════════════════════════${RESET}"
echo ""

# Check 1: Branch naming (1 branch per contract policy)
check "1. Branch naming (must match feature/aegis-p1-corr-*)" \
    '[[ "$(git branch --show-current)" =~ ^feature/aegis-p1-corr- ]]'

# Check 2: Working tree clean (excluding .venv)
check "2. Working tree clean (tracked files only)" \
    '[ "$(git status --short | grep -v ".venv" | grep -E "^[MAD]" | wc -l)" = "0" ]'

# Check 3: Critical modules importable
check "3. orchestrator imports OK" \
    '.venv/bin/python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator"'

check "4. executor imports OK" \
    '.venv/bin/python -c "from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor"'

# Check 5: Test collection has NO errors (negated grep -> 0 when no errors found)
# Skip pytest-based checks when AEGIS_NO_INNER_PYTEST is set (used by tests/unit)
if [[ "${AEGIS_NO_INNER_PYTEST:-0}" == "1" ]]; then
    check "5. Test collection clean (no ModuleNotFoundError) [SKIPPED]" \
        'true'
    check "6. All tests pass [SKIPPED]" \
        'true'
else
    check "5. Test collection clean (no ModuleNotFoundError)" \
        '! .venv/bin/pytest tests/unit/v2/ --co -q 2>&1 | grep -qE "ERROR|ModuleNotFoundError"'

    # Check 6: All tests pass (final pytest summary line contains "passed" with no failure markers)
    check "6. All tests pass" \
        '.venv/bin/pytest tests/unit/v2/ -q --tb=no 2>&1 | tail -1 | grep -qE "^[0-9]+ (passed|deselected|skipped)"'
fi

# Check 7: Doc 07 gate has 8 rows (CORR-002 invariant)
check "7. Doc 07 gate has 8 rows" \
    '.venv/bin/python -c "
from aegis_phase1.v2.output.doc_07 import _gate_rows
state = {\"aggregated_data\": {\"synthesis\": None, \"compound_events\": None}}
ontology = {\"subdomains\": {}, \"clause_mappings\": [], \"applicability_assessments\": []}
rows = _gate_rows(state, ontology)
exit(0 if len(rows) == 8 else 1)
"'

# Check 8: REDUCE-LLM invoker respects --model (CORR-003 Phase A invariant)
check "8. Invoker bypass fix in place (orchestrator reads llm_invoker.model)" \
    'grep -q "configured_model = getattr(self.llm_invoker, \"model\", None)" src/aegis_phase1/v2/orchestrator.py'

# Check 9 (warning only): No uncommitted v2/ files
warn_check "9. No orphan v2/ untracked files" \
    '[ "$(git ls-files --others --exclude-standard src/aegis_phase1/v2/ | wc -l)" = "0" ]'

echo ""
echo "${CYAN}═══════════════════════════════════════════${RESET}"
echo "${CYAN}  Summary${RESET}"
echo "${CYAN}═══════════════════════════════════════════${RESET}"
echo "  ${GREEN}PASS: $PASS${RESET}"
echo "  ${YELLOW}WARN: $WARN${RESET}"
echo "  ${RED}FAIL: $FAIL${RESET}"

if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo "${RED}FAILED checks:${RESET}"
    for f in "${FAILURES[@]}"; do
        echo "  - $f"
    done
    exit 1
fi

echo ""
echo "${GREEN}All critical checks passed.${RESET}"
exit 0
