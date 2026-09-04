#!/usr/bin/env bash
# status.sh — quick view of all jobs for the current Deucalion user.
#
# Reads SLURM squeue+sacct in one place; replaces the 4-path grep
# dance that follows jobs across scout_runs/run-*.log, slurm-*.out,
# /logs/phase1/<model>/v2/pipeline.log, and pipeline_<case>.log.
#
# Usage (Deucalion login node):
#   bash scripts/runs_tools/status.sh [--case <c1|c2|c3>]
#
# Output (one row per job):
#   JOBID  NAME  STATE  ELAPSED  NODES  LAST_LOG_LINE  OUTPUT_FILES

set -euo pipefail

CLUSTER_HOST="login.deucalion.macc.fccn.pt"
BD="/projects/F202512235CPCAA1/CyberMetric_Deucalion"

case_filter=""
while [ $# -gt 0 ]; do
  case "$1" in
    --case) case_filter="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--case c1|c2|c3]"; exit 0 ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
done

# Run on cluster (no cluster-local shell quoting here — output is plain text)
ssh "paulinho@${CLUSTER_HOST}" bash <<EOF
  echo '=== JOBID  STATE   ELAPSED   NODES  NAME'
  squeue -u \$USER -h -o '%10i %10T %.8M %R %.32j' 2>/dev/null \
    | awk -v cf="${case_filter}" 'BEGIN{IGNORECASE=1} {
        if (cf=="" || tolower(\$NF) ~ "c"substr(cf,2)||tolower(\$NF)==tolower(cf)) {
          printf "%-9s %-7s %-9s %-5s %s\n", \$1,\$2,\$3,\$4,\$NF
        }
      }'

  echo
  echo '=== ENDED jobs (last 24h) / last log line'
  for j in \$(sacct -u \$USER -X --noheader -o JobID,State,Elapsed,JobName,End -n -P 2>/dev/null \
              | awk '\$5>="2026-09-03T00" {print \$1}' | head -25); do
    log=\$(ls -t ${BD}/aegis-phase1/logs/scout_runs/*\$j.log ${BD}/aegis-phase1/logs/scout_runs/run_*\$j.log 2>/dev/null | head -1)
    state=\$(sacct -j \$j -X --noheader -o State -n -P 2>/dev/null | head -1)
    elapsed=\$(sacct -j \$j -X --noheader -o Elapsed -n -P 2>/dev/null | head -1)
    tail_line=\$( [ -n "\$log" ] && tail -1 "\$log" 2>/dev/null | cut -c-100 || echo "<no log>")
    out_count=\$(ls -1 ${BD}/aegis-phase1/output/*\$j* 2>/dev/null | wc -l)
    printf "%-9s %-7s %-9s out=%-3s | %s\n" \$j \$state \$elapsed \$out_count "\$tail_line"
  done
EOF
