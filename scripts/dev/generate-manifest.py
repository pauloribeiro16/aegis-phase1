"""Generate MANIFEST.md for an existing output run directory.

Walks the run dir, counts artefacts by size, parses
``logs/llm-calls.jsonl`` if present to summarise LLM-call volume,
retries, parse errors and schema errors, then writes ``MANIFEST.md``
to the same directory.

Path parsing conventions:
    output/<case>[/<contract>-]<YYYYMMDD-HHMMSS>/

    where ``<contract>-`` is optional. When present it must match
    ``corrNNN`` (case-insensitive) or the literal ``baseline``.

    Examples:
        output/case3-omnibank/corr072-20260728-155237/
            → case=case3-omnibank, contract=CORR-072,
              timestamp=20260728-155237
        output/case3-omnibank/baseline-20260727-220646/
            → case=case3-omnibank, contract=baseline,
              timestamp=20260727-220646
        output/case3/20260728-155237/
            → case=case3, contract=baseline,
              timestamp=20260728-155237

llm-calls.jsonl is keyed on:
    * prompt_spec_id     (groups call counts)
    * status             ("OK" / "SCHEMA_ERROR" / ...)
    * attempt            (>=2 means retry)
    * response.parse_error truthy → parse error
    * model              (first occurrence wins for the header line)

Usage:
    PYTHONPATH=src python3 scripts/dev/generate-manifest.py \\
        --run-dir output/case3/20260728-155237/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_NAME = "aegis-phase1"


# ── Path parsing ─────────────────────────────────────────────────────


_TS_RE = re.compile(r"^(\d{8})-(\d{6})$")
# Timestamp anchored to end-of-string with a leading ``-`` separator, so it
# matches the *trailing* timestamp in merged tokens like ``corr072-20260728-155237``.
_TS_TAIL_RE = re.compile(r"-(\d{8})-(\d{6})$")
_CONTRACT_RE = re.compile(r"^corr[-_]?(\d{1,3})$", re.IGNORECASE)


def _normalise_contract(token: str) -> str:
    """Canonical form for ``corr72`` / ``CORR-072`` / ``baseline``."""
    m = _CONTRACT_RE.match(token)
    if m:
        return f"CORR-{int(m.group(1)):03d}"
    if token.lower() == "baseline":
        return "baseline"
    return token


def _parse_run_path(run_dir: Path) -> tuple[str, str, str]:
    """Return (case, contract, timestamp) parsed from the run-dir path.

    Accepts three shapes that all occur in this repo:

      A. ``output/<case>/<contract>-<YYYYMMDD-HHMMSS>/``
         e.g. ``output/case3-omnibank/corr072-20260728-155237/``
      B. ``output/<case>/<contract>/<YYYYMMDD-HHMMSS>/``
         e.g. ``output/case3-omnibank/CORR-072/20260728-155237/``
      C. ``output/<case>/<YYYYMMDD-HHMMSS>/``              (legacy / no contract)
         e.g. ``output/case3/20260728-155237/``

    ``<contract>`` is either ``baseline`` or ``corrNNN`` (case-insensitive,
    optional ``-``/``_`` separator in the standalone form).

    Raises ValueError on structural mismatch. The caller can recover with
    sensible defaults.
    """
    parts = run_dir.resolve().parts
    if len(parts) < 3:
        raise ValueError(f"run dir is too shallow to parse: {run_dir}")

    last = parts[-1]
    penult = parts[-2]

    # Shape A — merged: last component is ``<contract>-<YYYYMMDD-HHMMSS>``.
    m_combined = _TS_TAIL_RE.search(last)
    if m_combined and len(parts) >= 3:
        head = last[: m_combined.start()]
        ts_match = _TS_RE.fullmatch(m_combined.group(0).lstrip("-"))
        if head and ts_match:
            return parts[-2], _normalise_contract(head), ts_match.group(0)

    # Shapes B / C — last component is a pure timestamp.
    m_ts = _TS_RE.match(last)
    if m_ts:
        # Shape B: penult is a contract token, case is parts[-3].
        if len(parts) >= 4 and (_CONTRACT_RE.match(penult) or penult.lower() == "baseline"):
            return parts[-3], _normalise_contract(penult), last
        # Shape C: no contract info; penult is the case slug.
        if len(parts) >= 3:
            return penult, "baseline", last

    raise ValueError(f"could not parse run-dir path: {run_dir}")


def _iso_timestamp_from_run(run_ts: str) -> str:
    """Convert YYYYMMDD-HHMMSS → ISO-8601 UTC."""
    date, time = run_ts.split("-", 1)
    return f"{date[:4]}-{date[4:6]}-{date[6:8]}T{time[:2]}:{time[2:4]}:{time[4:6]}Z"


# ── llm-calls.jsonl parsing ─────────────────────────────────────────


def _scan_llm_calls(jsonl_path: Path) -> dict:
    """Walk the jsonl stream and summarise LLM-call volume.

    Returns a dict with keys:
        present         bool
        path_or_none    str | None
        events          int   (total lines, all events)
        llm_calls       int   (event == 'llm_call')
        by_spec         dict[str,int]   (spec → call count)
        retries         int   (event == 'llm_call' AND attempt > 1)
        parse_errors    int   (response.parse_error truthy)
        schema_errors   int   (status == 'SCHEMA_ERROR')
        model           str | None  (first non-empty 'model' field)
    """
    out: dict = {
        "present": False,
        "path_or_none": None,
        "events": 0,
        "llm_calls": 0,
        "by_spec": {},
        "retries": 0,
        "parse_errors": 0,
        "schema_errors": 0,
        "model": None,
    }
    if not jsonl_path.exists():
        return out
    out["present"] = True
    out["path_or_none"] = str(jsonl_path)

    try:
        with jsonl_path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                out["events"] += 1
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    # Tolerate malformed lines — count them but do not crash.
                    continue
                if not isinstance(ev, dict):
                    continue

                if out["model"] is None:
                    model_field = ev.get("model")
                    if isinstance(model_field, str) and model_field.strip():
                        out["model"] = model_field.strip()

                # Only llm_call events carry prompt_spec_id / status / attempt.
                if ev.get("event") != "llm_call":
                    continue
                out["llm_calls"] += 1

                spec = ev.get("prompt_spec_id")
                if isinstance(spec, str) and spec:
                    out["by_spec"][spec] = out["by_spec"].get(spec, 0) + 1

                if isinstance(ev.get("attempt"), int) and ev["attempt"] > 1:
                    out["retries"] += 1

                resp = ev.get("response") or {}
                if isinstance(resp, dict) and resp.get("parse_error"):
                    out["parse_errors"] += 1

                if ev.get("status") == "SCHEMA_ERROR":
                    out["schema_errors"] += 1
    except OSError as exc:
        warnings.warn(f"could not read {jsonl_path}: {exc}", stacklevel=2)

    return out


# ── Artefact enumeration ─────────────────────────────────────────────


_EXCLUDE_FROM_ARTEFACTS = {"MANIFEST.md"}


def _list_artefacts(run_dir: Path) -> list[tuple[Path, int]]:
    """List regular files under ``run_dir`` (excluding logs/ and MANIFEST.md).

    Returns a list of (relative_path, size_bytes).
    """
    out: list[tuple[Path, int]] = []
    for entry in sorted(run_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.name in _EXCLUDE_FROM_ARTEFACTS:
            continue
        out.append((entry, entry.stat().st_size))
    return out


def _list_logs(run_dir: Path) -> dict[str, list[Path]]:
    """Classify entries of ``run_dir/logs/`` by category for the manifest.

    Returns dict with keys: pipeline, jsonl, map, other.
    """
    logs_dir = run_dir / "logs"
    if not logs_dir.is_dir():
        return {"pipeline": [], "jsonl": [], "map": [], "other": []}
    out = {"pipeline": [], "jsonl": [], "map": [], "other": []}
    for entry in sorted(logs_dir.iterdir()):
        if entry.is_file() and entry.suffix == ".log":
            out["pipeline"].append(entry)
        elif entry.is_file() and entry.suffix == ".jsonl":
            out["jsonl"].append(entry)
        elif entry.is_dir() and entry.name == "map":
            for j in sorted(entry.iterdir()):
                if j.is_file():
                    out["map"].append(j)
        elif entry.is_file():
            out["other"].append(entry)
    return out


# ── Markdown rendering ──────────────────────────────────────────────


def _format_lld_table(artefacts: list[tuple[Path, int]]) -> list[str]:
    if not artefacts:
        return ["_(no artefacts)_"]
    rows = ["| File | Size (bytes) | Notes |", "|------|-------------:|-------|"]
    total = 0
    for path, size in artefacts:
        total += size
        rel = path.name
        rows.append(f"| {rel} | {size} | |")
    rows.append(f"| **TOTAL** | **{total}** | |")
    return rows


def _format_llm_summary(stats: dict) -> list[str]:
    if not stats["present"]:
        return [
            "_(no logs — llm-calls.jsonl missing)_",
        ]
    by_spec = stats["by_spec"]
    if not by_spec:
        breakdown = "(no llm_call events)"
    else:
        # Stable order, compact, sorted descending then alphabetical.
        items = sorted(by_spec.items(), key=lambda kv: (-kv[1], kv[0]))
        breakdown = ", ".join(f"{spec}: {n}" for spec, n in items)
    return [
        f"Total events: {stats['events']}  ",
        f"LLM calls: {stats['llm_calls']} ({breakdown})  ",
        f"Retries: {stats['retries']}  ",
        f"Parse errors: {stats['parse_errors']}  ",
        f"Schema errors: {stats['schema_errors']}",
    ]


def _format_logs_section(logs: dict[str, list[Path]], run_dir: Path) -> list[str]:
    if not any(logs.values()):
        return ["_(no logs collected — see ``scripts/dev/collect-output.py``)_"]
    lines = []
    for path in logs["pipeline"]:
        rel = path.relative_to(run_dir)
        lines.append(f"- `logs/{path.name}` — orchestrator log (raw path: `{rel}`)")
    for path in logs["jsonl"]:
        lines.append(f"- `logs/{path.name}` — all LLM calls (request + response)")
    if logs["map"]:
        map_names = sorted(p.name for p in logs["map"])
        if len(map_names) <= 6:
            joined = ", ".join(f"`logs/map/{n}`" for n in map_names)
        else:
            head = ", ".join(f"`logs/map/{n}`" for n in map_names[:3])
            tail = f"`logs/map/{map_names[-1]}`"
            joined = f"{head} … {tail}"
        lines.append(f"- `logs/map/` — per-domain MAP logs ({joined})")
    for path in logs["other"]:
        lines.append(f"- `logs/{path.name}` — auxiliary log")
    return lines


def _format_run_dir(run_dir: Path) -> str:
    """Pretty-print the run dir, preferring the in-repo relative form."""
    try:
        return f"`{run_dir.resolve().relative_to(REPO_ROOT.resolve())}/`"
    except ValueError:
        return f"`{run_dir}/`"


def _build_markdown(
    run_dir: Path,
    case: str,
    contract: str,
    timestamp: str,
    stats: dict,
    artefacts: list[tuple[Path, int]],
    logs: dict[str, list[Path]],
) -> str:
    iso_ts = _iso_timestamp_from_run(timestamp)
    model = stats["model"] or "unknown"
    n_files = len(artefacts)
    out: list[str] = []
    out.append("# MANIFEST — output run")
    out.append("")
    out.append(f"- **Run dir:** {_format_run_dir(run_dir)}")
    out.append(f"- **Case:** {case}")
    out.append(f"- **Contract:** {contract}")
    out.append(f"- **Generated at:** {iso_ts}")
    out.append(f"- **Model:** {model}")
    out.append(f"- **Total files:** {n_files}")
    out.append("")

    out.append("## LLM activity")
    out.append("")
    for line in _format_llm_summary(stats):
        out.append(f"- {line}")
    out.append("")

    out.append("## Artefacts")
    out.append("")
    out.extend(_format_lld_table(artefacts))
    out.append("")

    out.append("## Logs (if present)")
    out.append("")
    out.extend(_format_logs_section(logs, run_dir))
    out.append("")

    out.append("---")
    out.append("")
    out.append(f"_Generated by `scripts/dev/generate-manifest.py` at {iso_ts}._")
    out.append("")
    return "\n".join(out)


# ── CLI ─────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="Output run dir (e.g. output/case3/20260728-155237/)",
    )
    p.add_argument(
        "--stdout",
        action="store_true",
        help="Print MANIFEST.md to stdout in addition to (or instead of) writing to disk",
    )
    p.add_argument(
        "--no-write",
        action="store_true",
        help="Do not write MANIFEST.md to disk (useful with --stdout for previews)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    run_dir: Path = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"ERROR: run dir does not exist: {run_dir}", file=sys.stderr)
        return 2

    try:
        case, contract, timestamp = _parse_run_path(run_dir)
    except ValueError as exc:
        warnings.warn(f"could not parse run-dir structure ({exc}); using defaults", stacklevel=2)
        case, contract, timestamp = run_dir.name, "baseline", "19700101-000000"

    stats = _scan_llm_calls(run_dir / "logs" / "llm-calls.jsonl")
    artefacts = _list_artefacts(run_dir)
    logs = _list_logs(run_dir)

    md = _build_markdown(run_dir, case, contract, timestamp, stats, artefacts, logs)

    if args.stdout or args.no_write:
        sys.stdout.write(md)
        if not md.endswith("\n"):
            sys.stdout.write("\n")
    if not args.no_write:
        target = run_dir / "MANIFEST.md"
        target.write_text(md, encoding="utf-8")
        if not args.stdout:
            print(f"[generate-manifest] wrote {target}  ({len(md)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
