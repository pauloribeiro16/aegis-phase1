#!/usr/bin/env bash
# CORR-027 CI gate: .md frozen list ↔ preproc_out xlsx-derived truth
# parity check.
#
# Reads:
#   - methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md
#     (the human-edited frozen list)
#   - preproc_out/global/NIST_CSF_2.0_subcategories.json
#     (xlsx-derived; 106 active subcategories — the source of truth)
#
# Asserts: the set of active subcategory IDs in the .md is EQUAL to the
# set in the JSON. Any drift fails the build.
#
# Exits 0 on parity, 1 on mismatch (with a diff printed to stdout),
# 2 on missing input files.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

MD_PATH="methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md"
JSON_PATH="preproc_out/global/NIST_CSF_2.0_subcategories.json"

if [ ! -f "$MD_PATH" ]; then
    echo "FAIL: $MD_PATH not present" >&2
    exit 2
fi
if [ ! -f "$JSON_PATH" ]; then
    echo "FAIL: $JSON_PATH not present (run \`python -m scripts.preprocess build\`)" >&2
    exit 2
fi

# Extract IDs from the .md (the table rows)
MD_IDS=$(grep -oE '^\|\s*[A-Z]{2}\.[A-Z]{2}-[0-9]{2}\s*\|' "$MD_PATH" \
    | grep -oE '[A-Z]{2}\.[A-Z]{2}-[0-9]{2}' \
    | sort -u)

# Extract active IDs from the JSON
JSON_IDS=$(.venv/bin/python -c "
import json
data = json.load(open('$JSON_PATH'))
print('\n'.join(sorted(s['id'] for s in data['subcategories'])))
")

# Diff
DIFF=$(diff <(echo "$MD_IDS") <(echo "$JSON_IDS") || true)
if [ -n "$DIFF" ]; then
    echo "FAIL: $MD_PATH ↔ $JSON_PATH parity broken" >&2
    echo "" >&2
    echo "Differences:" >&2
    echo "$DIFF" >&2
    exit 1
fi

COUNT=$(echo "$MD_IDS" | wc -l)
echo "OK: $COUNT CSF 2.0 subcategories in parity between $MD_PATH and $JSON_PATH"
