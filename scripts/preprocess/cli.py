"""CLI entry: ``python -m scripts.preprocess build``."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .pipeline import build

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO_ROOT / "methodology-00" / "PREPROCESSING"
# Diagrams live one level up from PREPROCESSING (under methodology-00/diagrams)
DEFAULT_SOURCE_ROOT = REPO_ROOT / "methodology-00"
DEFAULT_OUTPUT = REPO_ROOT / "preproc_out"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.preprocess",
        description="CORR-024 preprocessor v2: PREPROCESSING/ + diagrams/ → JSON shards",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build all shards from source")
    b.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help=f"methodology-00 root (default: {DEFAULT_SOURCE_ROOT})",
    )
    b.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output dir (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not args.source.is_dir():
        print(f"ERROR: --source {args.source} is not a directory", file=sys.stderr)
        return 2

    manifest = build(args.source, args.output)
    n_shards = manifest["shard_count"]
    n_errors = len(manifest["errors"])

    print(f"Built {n_shards} shards → {args.output}")
    if n_errors:
        print(f"BUILD FAILED: {n_errors} error(s) in strict mode", file=sys.stderr)
        for e in manifest["errors"][:20]:
            print(f"  {e['file']}: {e['error']}", file=sys.stderr)
        if n_errors > 20:
            print(f"  … and {n_errors - 20} more", file=sys.stderr)
        return 1
    print("BUILD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
