#!/usr/bin/env bash
# .hooks/validate-contracts.sh
# Pre-push validation script for AEGIS contracts.
# Runs the 11 critical + 2 warning checks defined across
# CORR-001 → CORR-005 (see docs/CONTRACTS.md).
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

# CORR-059: merged former checks 5 + 6 into one. The previous check 5 ran
# `pytest --co -q` (collection only) and check 6 ran the full suite (which
# re-collects). The collection check is redundant — if collection fails with
# ModuleNotFoundError, the full run's summary line won't match `passed` and
# check 6 fails anyway. Removing check 5 saves one full collection pass
# (~30-90s). Parallelism (-n auto) comes from pyproject.toml addopts.
#
# Skip when AEGIS_NO_INNER_PYTEST is set (used by tests/unit themselves).
if [[ "${AEGIS_NO_INNER_PYTEST:-0}" == "1" ]]; then
    check "5. All v2 tests pass [SKIPPED]" \
        'true'
else
    check "5. All v2 tests pass (collection + run, parallel via xdist)" \
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

# Check 10: P1B-LLM-02 RATIONALE phase wired into orchestrator (CORR-004 invariant)
check "10. P1B-LLM-02 RATIONALE phase wired into orchestrator" \
    'cd "$REPO_ROOT" && grep -q "def run_phase_1b" src/aegis_phase1/v2/orchestrator.py'

# Check 11: layer0_* renamed (CORR-005 invariant)
check "11. layer0_* renamed to regulatory_baseline_* (canonical names exist)" \
    'cd "$REPO_ROOT" && grep -q "def get_regulatory_baseline_root" src/aegis_phase1/prompts_v2/factory.py'

# Check 12 (warn): deprecated layer0_ aliases still present (backwards compat)
warn_check "12. Deprecation aliases for layer0_ preserved (backwards compat)" \
    'cd "$REPO_ROOT" && grep -q "def get_layer0_root" src/aegis_phase1/prompts_v2/factory.py'

# Check 13: Sequential wizard is the default interactive entry (CORR-006)
check "13. Sequential wizard is default (run_wizard exists; legacy run_menu is alias)" \
    'cd "$REPO_ROOT" && grep -q "^def run_wizard" src/aegis_phase1/v2/cli/menu.py'

# Check 14: Hub-spoke menu legacy code removed (CORR-006)
check "14. Legacy build_menu/_resolve_menu_choice removed from menu.py" \
    'cd "$REPO_ROOT" && ! grep -q "^def build_menu" src/aegis_phase1/v2/cli/menu.py'

# Check 15: runner.py invokes run_wizard (not run_menu)
check "15. runner.py invokes run_wizard" \
    'cd "$REPO_ROOT" && grep -q "from aegis_phase1.v2.cli.menu import run_wizard" src/aegis_phase1/v2/runner.py'

# Check 16 (warn): run_menu backwards-compat alias preserved
warn_check "16. run_menu() backwards-compat alias preserved (one-release deprecation)" \
    'cd "$REPO_ROOT" && grep -q "^def run_menu" src/aegis_phase1/v2/cli/menu.py'

# Check 17: Wizard uses beaupy.select (CORR-007)
check "17. Wizard uses beaupy.select (CORR-007)" \
    'cd "$REPO_ROOT" && grep -q "beaupy.select" src/aegis_phase1/v2/cli/menu.py'

# Check 18: Static case catalogue defined (CORR-007)
check "18. Static case catalogue defined (CORR-007 — 3 cases)" \
    'cd "$REPO_ROOT" && grep -q "Case_01_TinyTask_SaaS" src/aegis_phase1/v2/cli/menu.py && grep -q "Case_02_SecureBorder_Solutions" src/aegis_phase1/v2/cli/menu.py && grep -q "Case_03_OmniBank_Financial" src/aegis_phase1/v2/cli/menu.py'

# Check 19: run_wizard importable and callable (CORR-007)
check "19. run_wizard() importable from menu module" \
    'cd "$REPO_ROOT" && .venv/bin/python -c "from aegis_phase1.v2.cli.menu import run_wizard; assert callable(run_wizard)"'

# Check 20: CSF 2.0 frozen-list .md ↔ preproc_out parity (CORR-027)
check "20. CSF 2.0 frozen-list .md ↔ preproc_out parity (CORR-027)" \
    'cd "$REPO_ROOT" && bash .hooks/ci-csf-frozen-list.sh'

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
