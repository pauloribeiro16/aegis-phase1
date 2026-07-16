#!/usr/bin/env bash
# AEGIS-Phase1 quick test gate (AEGIS-P1-CORR-008 Phase D).
# - Collection gate (Validator Integrity Rule)
# - Unit + integration tests
# - Hand-test of `python -m aegis_phase1.v2.runner` non-TTY
# - menu.py sites check
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "== [1/4] Collection gate =="
if .venv/bin/python -m pytest tests/unit/ tests/integration/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError"; then
  echo "COLLECTION ERROR detected" >&2
  exit 1
fi

echo "== [2/4] Unit (v2 + prompts_v2) + integration smoke =="
.venv/bin/python -m pytest \
    tests/unit/v2/ \
    tests/unit/prompts_v2/ \
    tests/integration/test_runner_smoke.py \
    tests/integration/test_wizard_signature_smoke.py \
    -q

echo "== [3/4] Hand-test runner non-TTY =="
if ! echo "" | .venv/bin/python -m aegis_phase1.v2.runner | grep -q "Interactive wizard requires a TTY"; then
  echo "Hand-test FAILED: TTY message missing" >&2
  exit 1
fi

echo "== [4/4] menu.py sites =="
pre=$(grep -c pre_selected src/aegis_phase1/v2/cli/menu.py || true)
cur=$(grep -c "cursor_index=0" src/aegis_phase1/v2/cli/menu.py || true)
if [ "$pre" != "0" ] || [ "$cur" != "4" ]; then
  echo "menu.py site check FAILED: pre_selected=$pre (expect 0); cursor_index=4 expected, got $cur" >&2
  exit 1
fi

echo "== ALL GATES PASS =="
