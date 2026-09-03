#!/usr/bin/env python3
"""AEGIS-KG Phase 1 Multi-Run Digest & Evaluation Report Generator.

Scans output/ (both hierarchical output/<case>/phase1/run_* and flat run_*)
and consolidates an executive summary table comparing model runs across cases.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RunSummary:
    case_slug: str
    phase: str
    model: str
    job_id: str
    run_dir: str
    status: str  # SUCCESS, PARTIAL, FAILED
    artefact_count: int
    expected_artefacts: int
    has_xlsx: bool
    schema_errors: int
    warnings: int
    elapsed_sec: float | None
    total_tokens: int | None
    timestamp: str | None
    missing_files: list[str] = field(default_factory=list)


CORE_ARTEFACTS = [
    "04_Company_Context_Assessment.md",
    "05_Regulatory_Applicability.md",
    "06_Clause_Mapping_Matrix.md",
    "07_Structured_Compliance_Matrix.md",
    "07b_Proportionality_Profile.md",
]


def parse_run_dir(run_path: Path) -> RunSummary:
    # 1. Identify Case and Phase
    parts = run_path.parts
    case_slug = "unknown"
    phase = "phase1"
    for part in parts:
        if part.startswith("case") and ("tinytask" in part or "secureborder" in part or "omnibank" in part):
            case_slug = part
        elif part in ("phase1", "phase2"):
            phase = part

    dir_name = run_path.name
    # Extract model and job id from run_<model>_<job_id>
    job_id = "local"
    model = "unknown"
    m_job = re.search(r"_(\d{5,8})$", dir_name)
    if m_job:
        job_id = m_job.group(1)
        model_part = dir_name[len("run_") : -len(job_id) - 1]
        model = model_part.replace("_40g_", "").replace("_", ":", 1).replace("_", ".")
    else:
        model = dir_name.replace("run_", "")

    # 2. Check generated artefacts
    present_files = [p.name for p in run_path.glob("*") if p.is_file() and p.stat().st_size > 0]
    missing = []
    for exp in CORE_ARTEFACTS:
        if exp not in present_files:
            missing.append(exp)

    has_xlsx = any(f.endswith(".xlsx") and not f.startswith("~$") for f in present_files)
    if not has_xlsx:
        missing.append("Case_XX_Phase1.xlsx")

    # 3. Check logs
    schema_errors = 0
    warnings = 0
    elapsed_sec = None
    total_tokens = 0
    timestamp = None

    # Search for matching logs in logs/
    log_candidates = list(Path("logs").rglob(f"*{job_id}*.log")) if job_id != "local" else []
    for log_file in log_candidates:
        try:
            content = log_file.read_text(errors="ignore")
            schema_errors += len(re.findall(r"SCHEMA_ERROR|markdown_parse_error", content))
            warnings += len(re.findall(r"\[WARNING\]|WARNING", content))
            tok_matches = re.findall(r"(\d+)\s*tok", content)
            if tok_matches:
                total_tokens = sum(int(t) for t in tok_matches)
            time_matches = re.findall(r"(\d+)ms", content)
            if time_matches:
                elapsed_sec = round(sum(int(t) for t in time_matches) / 1000.0, 1)
        except Exception:
            pass

    # Determine status
    if len(missing) == 0 and schema_errors == 0:
        status = "SUCCESS"
    elif len(missing) <= 1:
        status = "PARTIAL" if schema_errors > 0 else "SUCCESS"
    else:
        status = "FAILED"

    return RunSummary(
        case_slug=case_slug,
        phase=phase,
        model=model,
        job_id=job_id,
        run_dir=str(run_path),
        status=status,
        artefact_count=len(present_files),
        expected_artefacts=6,
        has_xlsx=has_xlsx,
        schema_errors=schema_errors,
        warnings=warnings,
        elapsed_sec=elapsed_sec,
        total_tokens=total_tokens if total_tokens > 0 else None,
        timestamp=datetime.fromtimestamp(run_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        missing_files=missing,
    )


def scan_all_runs(output_dir: Path) -> list[RunSummary]:
    summaries = []
    if not output_dir.exists():
        return summaries

    # Look for run_* directories
    for root, dirs, files in os.walk(output_dir):
        for d in dirs:
            if d.startswith("run_"):
                run_path = Path(root) / d
                summaries.append(parse_run_dir(run_path))

    # Sort by timestamp descending
    summaries.sort(key=lambda s: (s.case_slug, s.timestamp or ""), reverse=True)
    return summaries


def format_table(summaries: list[RunSummary]) -> str:
    if not summaries:
        return "No runs found in output/ directory."

    lines = [
        "# AEGIS-KG Phase 1 — Consolidated Runs Digest",
        f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "| Case | Phase | Model / Config | Job ID | Status | Artefacts | Excel | Schema Errors | Elapsed (s) | Timestamp |",
        "|---|---|---|---|:---:|:---:|:---:|:---:|:---:|---|",
    ]

    for s in summaries:
        status_badge = "✅ SUCCESS" if s.status == "SUCCESS" else ("⚠️ PARTIAL" if s.status == "PARTIAL" else "❌ FAILED")
        xlsx_badge = "✅" if s.has_xlsx else "❌"
        elapsed_str = f"{s.elapsed_sec}s" if s.elapsed_sec is not None else "-"
        lines.append(
            f"| `{s.case_slug}` | `{s.phase}` | `{s.model}` | `{s.job_id}` | {status_badge} | {s.artefact_count}/{s.expected_artefacts} | {xlsx_badge} | {s.schema_errors} | {elapsed_str} | {s.timestamp} |"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="AEGIS-KG Multi-Run Digest Generator")
    parser.add_argument("--output-dir", default="output", help="Base output directory to scan (default: output)")
    parser.add_argument("--save-report", action="store_true", help="Save report to output/DIGEST_REPORT.md")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    summaries = scan_all_runs(Path(args.output_dir))

    if args.json:
        print(json.dumps([asdict(s) for s in summaries], indent=2))
        return

    table_md = format_table(summaries)
    print(table_md)

    if args.save_report:
        report_path = Path(args.output_dir) / "DIGEST_REPORT.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(table_md)
        print(f"\n[OK] Report saved to {report_path}")


if __name__ == "__main__":
    main()
