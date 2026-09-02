"""link_run.py — register a new run folder into `execution/runs/by_model/`.

Generates symlinks so a run can be discovered both via its primary
key (`<model>_<kind>_<JOBID>`) and via the model bucket
(`execution/runs/by_model/<model>/<run>/`).

The bucket tree is local-only — paths are absolute inside the repo
root, which makes them non-portable across hosts, so we add the
directory to `.gitignore` and let the user regenerate it locally
(`python -m scripts.runs_tools.link_run --all`).

Usage:
    # register one run
    python -m scripts.runs_tools.link_run qwen38_27b_runall_1868946
    # register everything currently in execution/runs/
    python -m scripts.runs_tools.link_run --all
    # remove the symlinks under by_model/ and rebuild
    python -m scripts.runs_tools.link_run --all --rebuild
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "execution" / "runs"
BUCKET_DIR = RUNS_DIR / "by_model"

# Match `<model>_<kind>_<JOBID>` where kind ∈ {scout, scout_full, runall}.
# The model token is whatever precedes `_kind_`.
_RUN_RE = re.compile(r"^(?P<model>.+)_(?P<kind>scout_full|scout|runall)_(?P<jobid>\d+)$")


def _model_key(name: str) -> str:
    m = _RUN_RE.match(name)
    if m is None:
        return ""
    model = m.group("model")
    # Canonicalise the small quirks: ``qwen38_27b`` represents qwen3.8 27B.
    # This is project-specific naming; if more aliases are needed add
    # to the table below.
    aliases = {
        "qwen38_27b": "qwen3.8",
        "qwen35_27b": "qwen3.5",
    }
    return aliases.get(model, model)


def _link_one(name: str) -> Path:
    """Create a symlink under by_model/<canonical_model>/<name> pointing at name.

    Returns the symlink path for reporting.
    """
    src = RUNS_DIR / name
    if not src.exists():
        raise FileNotFoundError(src)
    model_key = _model_key(name)
    if not model_key:
        print(f"  SKIP {name} (does not match the <model>_<kind>_<jobid> pattern)")
        return Path()
    bucket = BUCKET_DIR / model_key
    bucket.mkdir(parents=True, exist_ok=True)
    target = bucket / name
    if target.is_symlink() or target.exists():
        target.unlink()
    # Symlink is relative so it survives the path changing inside this
    # workspace (e.g. on a workstation vs the cluster mirror copy).
    target.symlink_to(Path("..") / ".." / name)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Register runs under execution/runs/by_model/<model>/."
    )
    parser.add_argument(
        "names",
        nargs="*",
        help="One or more run folder names. Omit with --all to scan the dir.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan every folder in execution/runs/ except by_model/.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="With --all: wipe by_model/ first then recreate (idempotent).",
    )
    args = parser.parse_args(argv)

    if not args.names and not args.all:
        parser.error("give run folder names OR pass --all")

    if args.rebuild and args.all and BUCKET_DIR.exists():
        for child in BUCKET_DIR.iterdir():
            # do not touch real folders inside by_model; only symlinks
            if child.is_symlink() or child.is_file() or not child.is_dir():
                child.unlink()
            else:
                for sub in child.iterdir():
                    if sub.is_symlink() or sub.exists():
                        sub.unlink()
                child.rmdir()
        print(f"wiped {BUCKET_DIR}")

    if args.all:
        # Walk through every folder at execution/runs/* and link each
        # one that matches <model>_<kind>_<jobid>.
        names = sorted(p.name for p in RUNS_DIR.iterdir() if p.is_dir() and p.name != "by_model")
    else:
        names = args.names

    for name in names:
        try:
            link = _link_one(name)
        except FileNotFoundError as e:
            print(f"  ERROR {name}: {e}")
            continue
        if link:
            print(f"  OK {name} -> {link.parent.name}/{link.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
