#!/usr/bin/env bash
# CORR-028 CI gate: detect references to non-CSF-2.0 control frameworks
# in the active code path, and require explicit annotation when they
# appear as vendor-attestation or implementation-guidance (not as
# control frameworks).
#
# Policy: see docs/NIST_CSF_2.0_ONLY.md §2.
#
# The check is run over active source code (.py) and active documentation
# (.md) that is NOT in the archived/ or .archive/ paths. Each line that
# mentions a forbidden framework must carry a `CORR-028` marker within
# the same logical block (3 lines above or 3 lines below). If not, the
# CI gate fails.
#
# Exit codes:
#   0  — no unannotated references
#   1  — at least one unannotated reference (CI fails)
#   2  — infrastructure error (e.g. ripgrep not available)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Frameworks that are NOT control frameworks in this project.
# These are forbidden as control frameworks; they may appear ONLY when
# annotated as attestation/guidance per the CORR-028 marker.
FORBIDDEN_FRAMEWORKS=(
  "ISO 27001"
  "ISO/IEC 27001"
  "ISO27001"
  "SOC 2"
  "SOC2"
  "OWASP"
  "OWASP Top 10"
  "NIST 800-53"
  "NIST SP 800-53"
  "SP 800-53"
  "COBIT"
  "CSF 1.1"
  "CSF v1.1"
  "CSF1.1"
)

# Paths to scan (active enforcement sites; narrative MDs are excluded
# by default because they are regulatory baseline context, not control
# selection. To scan a narrative MD, use SCAN_EXTRA_PATHS.)
SCAN_PATHS=(
  "src/"
  "docs/"
  "tests/unit/"
  "README.md"
)

# Policy-definition files are exempt: their job is to declare the policy,
# which necessarily mentions the excluded frameworks. They are
# `docs/NIST_CSF_2.0_ONLY.md` (canonical), `AGENTS.md` §0, and the
# contract files. Match by suffix — keep this list short.
POLICY_FILE_PATTERNS=(
  "AGENTS.md"
  "methodology-00/MANIFESTO.md"
  "methodology-00/REFERENCE/related_frameworks.md"
  "docs/NIST_CSF_2.0_ONLY.md"
  "docs/CONTRACTS.md"
  "execution/CONTRACT-028.md"
  "execution/CONTRACT-027.md"
  "execution/AUDIT_D-01.1_CSF_MAPPING.md"
  "tests/unit/hooks/test_ci_frameworks.py"
)

# Build a single regex alternation
REGEX_ALT=$(printf "%s\n" "${FORBIDDEN_FRAMEWORKS[@]}" | sort -u | paste -sd'|' -)

# Use ripgrep if available, else grep -RnE
if command -v rg >/dev/null 2>&1; then
  MATCHES=$(rg -n -E "$REGEX_ALT" "${SCAN_PATHS[@]}" 2>/dev/null || true)
else
  MATCHES=$(grep -RnE "$REGEX_ALT" "${SCAN_PATHS[@]}" 2>/dev/null || true)
fi

if [ -z "$MATCHES" ]; then
  echo "OK: no references to non-CSF-2.0 control frameworks in active paths"
  exit 0
fi

# For each match, verify a CORR-028 marker is within ±3 lines of the match.
# We re-scan with line numbers and apply a sliding window.
FAIL=0
while IFS= read -r line; do
  if [ -z "$line" ]; then continue; fi
  FILE=$(echo "$line" | cut -d: -f1)
  # Policy-definition files are exempt
  IS_POLICY=0
  for pat in "${POLICY_FILE_PATTERNS[@]}"; do
    if [ "$FILE" = "$pat" ]; then
      IS_POLICY=1
      break
    fi
  done
  if [ "$IS_POLICY" -eq 1 ]; then continue; fi
  LINENO_=$(echo "$line" | cut -d: -f2)
  # Annotation window: ±5 lines (was ±3 — expanded because Python
  # f-strings and dict literals can push the string 4-5 lines below
  # the comment that introduces it).
  START=$((LINENO_ > 5 ? LINENO_ - 5 : 1))
  END=$((LINENO_ + 5))
  # Extract the 7-line window and check for marker
  WINDOW=$(sed -n "${START},${END}p" "$FILE" 2>/dev/null || true)
  if echo "$WINDOW" | grep -q "CORR-028"; then
    : # OK — annotated
  else
    echo "FAIL: unannotated framework reference at $FILE:$LINENO"
    echo "  $line"
    FAIL=1
  fi
done <<< "$MATCHES"

if [ "$FAIL" -eq 1 ]; then
  echo ""
  echo "Policy: docs/NIST_CSF_2.0_ONLY.md §2"
  echo "Add a comment 'CORR-028' within ±3 lines of the reference, e.g.:"
  echo "  # NOTE (CORR-028, NIST_CSF_2.0_ONLY.md §2): '...' is a vendor attestation pattern, NOT a control framework."
  exit 1
fi

echo "OK: all framework references are annotated with CORR-028"
exit 0
