"""Collect logs and provenance files into an output run dir, then emit MANIFEST.md.

Used by the post-run protocol after ``scripts/dev/run_phase1.py`` (or any
equivalent Phase 1 v2 invocation). Walks the per-model log directory at
``logs/phase1/<model_tag>/`` and copies the orchestrator log, the
llm-calls.jsonl stream, and the per-domain MAP logs into
``<run-dir>/logs/``. Finally delegates to ``generate-manifest.py`` so the
run dir always carries a fresh ``MANIFEST.md``.

Behavior:
    * Auto-detect ``model_tag`` from ``logs/phase1/*`` if not passed
      explicitly (most recent ``v2/pipeline_*.log`` by mtime).
    * Tolerates missing files: emits a warning, never aborts.
    * Always regenerates ``MANIFEST.md`` (even when no logs were found).

Usage:
    PYTHONPATH=src python3 scripts/dev/collect-output.py \\
        --run-dir output/case3-omnibank/corr072-20260728-155237/

    # Pin to a specific model tag (skip auto-detect):
    PYTHONPATH=src python3 scripts/dev/collect-output.py \\
        --run-dir output/case3-omnibank/corr072-20260728-155237/ \\
        --model-tag minimax_MiniMax-M3

Exit code is 0 unless the run dir itself is missing.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_DIR = REPO_ROOT / "scripts" / "dev"
DEFAULT_LOG_BASE = REPO_ROOT / "logs" / "phase1"


def _candidate_model_tags(log_base: Path) -> list[Path]:
    """Return all subdirs of ``logs/phase1`` that look like model dirs."""
    if not log_base.is_dir():
        return []
    return sorted([p for p in log_base.iterdir() if p.is_dir()])


def _discover_model_tag(log_base: Path) -> Path | None:
    """Pick the model dir whose ``v2/pipeline_*.log`` was updated most recently.

    Falls back to the most recently touched subdir when no log file
    exists at all (e.g. a smoke run that emitted only jsonl).
    """
    if not log_base.is_dir():
        return None
    candidates: list[tuple[float, Path]] = []
    for sub in _candidate_model_tags(log_base):
        v2_dir = sub / "v2"
        logs = list(v2_dir.glob("pipeline_*.log")) if v2_dir.is_dir() else []
        if logs:
            newest = max(logs, key=lambda p: p.stat().st_mtime)
            candidates.append((newest.stat().st_mtime, sub))
        else:
            # No v2/pipeline_*.log — still consider the dir if it has llm-calls.jsonl.
            llm = sub / "llm-calls.jsonl"
            if llm.exists():
                candidates.append((llm.stat().st_mtime, sub))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _copy_file(src: Path, dest: Path, *, warn_prefix: str) -> bool:
    """Copy ``src`` → ``dest`` (creating parents). Return True on success."""
    if not src.exists():
        warnings.warn(f"{warn_prefix}: missing source {src}", stacklevel=2)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        # Overwrite silently — run-dir logs should always reflect latest collect.
        dest.unlink()
    shutil.copy2(src, dest)
    return True


def _copy_pipeline_logs(model_dir: Path, run_dir: Path) -> dict[str, int]:
    """Copy pipeline_*.log, llm-calls.jsonl, and v2/map/D-*.jsonl from model_dir.

    Returns a small stat dict so the caller can log what happened.
    """
    counts = {"logs": 0, "jsonl": 0, "map": 0}
    logs_dest = run_dir / "logs"

    # 1. Orchestrator pipeline log (only one expected; copy first match).
    v2_dir = model_dir / "v2"
    pipeline_logs = sorted(v2_dir.glob("pipeline_*.log")) if v2_dir.is_dir() else []
    if pipeline_logs:
        # Use the latest one.
        pipeline_log = max(pipeline_logs, key=lambda p: p.stat().st_mtime)
        if _copy_file(
            pipeline_log,
            logs_dest / "pipeline.log",
            warn_prefix="pipeline log",
        ):
            counts["logs"] += 1
    else:
        warnings.warn(
            f"no pipeline_*.log under {v2_dir}; skipping orchestrator log copy",
            stacklevel=2,
        )

    # 2. llm-calls.jsonl
    llm_calls = model_dir / "llm-calls.jsonl"
    if _copy_file(
        llm_calls,
        logs_dest / "llm-calls.jsonl",
        warn_prefix="llm-calls.jsonl",
    ):
        counts["jsonl"] += 1

    # 3. per-domain MAP logs
    map_src = v2_dir / "map"
    map_dest = logs_dest / "map"
    if map_src.is_dir():
        for jsonl in sorted(map_src.glob("D-*.jsonl")):
            if _copy_file(
                jsonl,
                map_dest / jsonl.name,
                warn_prefix="map log",
            ):
                counts["map"] += 1
    else:
        warnings.warn(
            f"no map/ under {v2_dir}; skipping per-domain MAP copies",
            stacklevel=2,
        )

    return counts


def _run_generate_manifest(run_dir: Path) -> int:
    """Re-invoke generate-manifest.py as a subprocess so its argparse path is canonical."""
    import subprocess

    script = DEV_DIR / "generate-manifest.py"
    if not script.exists():
        warnings.warn(f"generate-manifest.py not found at {script}", stacklevel=2)
        return 1
    proc = subprocess.run(
        [sys.executable, str(script), "--run-dir", str(run_dir)],
        cwd=str(REPO_ROOT),
        check=False,
    )
    return proc.returncode


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Output run dir (e.g. output/case3-omnibank/corr072-20260728-155237/)",
    )
    p.add_argument(
        "--model-tag",
        default=None,
        help="Per-model log subdir name (default: auto-detect most recent under logs/phase1/)",
    )
    p.add_argument(
        "--log-base",
        default=None,
        type=Path,
        help=f"Base log dir (default: {DEFAULT_LOG_BASE})",
    )
    p.add_argument(
        "--skip-manifest",
        action="store_true",
        help="Do not invoke generate-manifest.py after copying logs",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    run_dir: Path = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run dir does not exist: {run_dir}", file=sys.stderr)
        return 2

    log_base: Path = (args.log_base or DEFAULT_LOG_BASE).resolve()
    if args.model_tag:
        model_dir = log_base / args.model_tag
        if not model_dir.is_dir():
            warnings.warn(
                f"--model-tag {args.model_tag!r} not found under {log_base}; "
                "falling back to auto-detect",
                stacklevel=2,
            )
            model_dir = _discover_model_tag(log_base)
    else:
        model_dir = _discover_model_tag(log_base)

    if model_dir is None:
        warnings.warn(
            f"no model log dirs found under {log_base}; "
            "skipping log copy, regenerating MANIFEST only",
            stacklevel=2,
        )
        counts = {"logs": 0, "jsonl": 0, "map": 0}
        detected_tag = "unknown"
    else:
        detected_tag = model_dir.name
        print(f"[collect-output] model_tag: {detected_tag}")
        counts = _copy_pipeline_logs(model_dir, run_dir)
        print(
            f"[collect-output] copied: "
            f"{counts['logs']} pipeline.log, "
            f"{counts['jsonl']} llm-calls.jsonl, "
            f"{counts['map']} map/D-*.jsonl"
        )

    if args.skip_manifest:
        print("[collect-output] skipping MANIFEST regeneration (--skip-manifest)")
        return 0

    rc = _run_generate_manifest(run_dir)
    if rc != 0:
        print(f"[collect-output] WARNING: generate-manifest exited {rc}", file=sys.stderr)
    return 0 if rc == 0 else rc


if __name__ == "__main__":
    raise SystemExit(main())
