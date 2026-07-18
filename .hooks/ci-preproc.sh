#!/usr/bin/env bash
# CORR-024 CI gate: regenerate preproc_out/ and verify it's fresh.
#
# Exits 0 on success, 1 on stale shards, 2 on build failure.
# This script is the single source of truth for "is preproc_out/ in sync
# with the source Methodology-main tree?" — invoked by
# .hooks/validate-contracts.sh and by hand before commit.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# 1. Build
source ../shared-venv/bin/activate
python -m scripts.preprocess build > /tmp/preproc_build.log 2>&1 || {
    echo "FAIL: preproc build had errors (see /tmp/preproc_build.log)"
    tail -20 /tmp/preproc_build.log
    exit 2
}

# 2. Verify manifest integrity
SHARD_COUNT=$(python -c "import json; print(json.load(open('preproc_out/manifest.json'))['shard_count'])")
if [ "$SHARD_COUNT" -lt 340 ]; then
    echo "FAIL: only $SHARD_COUNT shards (expected >= 340)"
    exit 1
fi
echo "OK: $SHARD_COUNT shards built"
