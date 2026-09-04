#!/usr/bin/env bash
# scout-full-submit.sh — print a `sbatch -J aegis_<model-tag> ...` command.
#
# When running multiple scout-full jobs in parallel (one per model on a
# different node), the default ``--job-name=aegis_scout_full`` in the
# sbatch makes ``squeue`` unreadable — every row says the same name.
#
# This wrapper emits the exact one-liner to run on the cluster login
# node, with the model tag sanitised into the SLURM job-name. Paste
# each invocation into the cluster shell; squeue then shows e.g.
# ``aegis_nemotron3_5_30b`` / ``aegis_granite4_2_30b``.
#
# Usage (from any directory):
#   eval "$(scripts/scouts/scout-full-submit.sh nemotron3.5:30b)"
#
# The colon in the Ollama tag ``:`` becomes ``__`` so the job-name
# stays portable across SLURM versions; the script slot (currently
# ``full``) is the last segment.
#
# Args:
#   $1  model:tag              (e.g. ``muse-glimmer:30b``)
#   $2  sbatch script path     (default: ``examples/deucalion/scout-bench-m-aegis-full.sbatch``)
#   $3  slot suffix            (default: ``full``)
#
# Output:
#   Prints an ``echo "sbatch -J aegis_<sanitised> ..." `` snippet
#   ready for ``eval``.

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "usage: $0 <model:tag> [sbatch_path] [slot]" >&2
    exit 2
fi

MODEL="$1"
SCRIPT_PATH="${2:-examples/deucalion/scout-bench-m-aegis-full.sbatch}"
SLOT="${3:-full}"

# Sanitise colon and dot to underscore so the tag stays one shell token.
SANITISED=$(printf '%s' "$MODEL" | tr ':.' '__')

# emit the one-liner
echo "sbatch -J \"aegis_${SANITISED}_${SLOT}\" \"$SCRIPT_PATH\" \"$MODEL\""
