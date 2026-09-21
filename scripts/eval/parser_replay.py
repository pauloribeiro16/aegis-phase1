#!/usr/bin/env python3
"""CORR-116 S1 — Offline parser replay harness.

Replays every raw LLM response stored under ``output/phase1/raw/<SPEC>/*.md``
through its registered ``MARKDOWN_PARSERS[spec]`` and classifies the outcome:

  - ``parse_ok``   — parser produced a model instance
  - ``parse_fail`` — parser returned ``(None, error_str)``; we bucket the error
  - ``gate_fail``  — parser produced a model BUT RefGate rejected it

The harness is **read-only** (it never deletes or modifies raw files). It
emits three artefacts in ``execution/reports/``:

  1. ``parser_replay_<ts>.md``         — human matrix (rows = spec,
                                        cols = parse_ok / parse_fail / gate_fail /
                                        error_classes breakdown)
  2. ``parser_replay_<ts>.json``       — full per-file record (for triage)
  3. ``parser_replay_<ts>_failures.md``— excerpt per error class (≤300 chars)

Algorithm per file (see CONTRACT-116 §3.3):

  1. Parse YAML frontmatter → ``model``, ``status``, ``spec_id``, ``attempt``.
  2. Extract the body after the ``## Raw response`` header.
  3. Call ``MARKDOWN_PARSERS[spec_id]().parse(body)``.
  4. If ``parsed_model is None`` → classify the failure by regex on the
     parser error string.
  5. Else → run ``RefGate().validate(spec_id, body)``; if invalid → ``gate_fail``.
  6. Aggregate counts per (spec x model x error_class).

Exit code is always 0 (informational harness). The default invocation
(``--limit 5``) replays 5 raws per spec and finishes in a few seconds — no
GPU required.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _relpath(path: Path) -> str:
    """Path relative to the repo root, falling back to ``str(path)`` for
    test inputs (synthetic raws in tmpdir).
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
DEFAULT_RAW_DIR = REPO_ROOT / "output" / "phase1" / "raw"
DEFAULT_OUT_DIR = REPO_ROOT / "execution" / "reports"

# All 5 canonical specs (in stable display order).
DEFAULT_SPECS = (
    "P1B-LLM-01-INTERPRETATION",
    "P1B-LLM-02-RATIONALE",
    "P1C-LLM-01-OVERLAP-CLASSIFICATION",
    "P1C-LLM-02-COMPOUND-EVENT",
    "P1C-LLM-03-STRATEGIC-SYNTHESIS",
)

# Error-class signatures (regex → class). Order matters: first match wins.
# These mirror the spec-specific failure modes enumerated in
# CONTRACT-116 §3.3 step 4; the regexes are deliberately liberal because
# the parser's error string is its own surface (and we cannot change it
# without editing parsers — out of scope for S1).
_ERROR_CLASS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # P1B-01: missing Status section
    (
        "no_status_section",
        re.compile(r"(?i)\bno\s+(?:header|status)\b|missing\s+status|no\s+`##`"),
    ),
    # P1B-01: missing Interpretation sub-sections
    (
        "missing_int",
        re.compile(r"(?i)\b(?:interpretations?|INT-\d+)\b"),
    ),
    # P1B-01: missing Derogation sub-sections
    (
        "missing_der",
        re.compile(r"(?i)\b(?:derogations?|DER-\d+)\b"),
    ),
    # P1C-01 (CORR-108): Shape A misread (no `## Sub-domain Activations`)
    (
        "shape_a_misread",
        re.compile(r"(?i)sub-?domain\s+activations|shape\s*a"),
    ),
    # P1C-01 generic "no section headers" — same as no_status_section
    # but tagged differently so the matrix shows real class diversity.
    # Tolerates both "no section headers found" (plain) and the
    # bracketed form P1C-01 emits (e.g. "no `## Section` headers").
    (
        "no_headers",
        re.compile(r"(?i)no\s+(?:section\s+headers?|.+?`?##\s+\S+`?\s+headers?)\s+found"),
    ),
    # RefGate violations (model parsed but gate rejected) — these are
    # *classified* by the harness into ``gate_fail``; the regex below
    # is only consulted if the parser error string leaks a gate violation
    # (rare; defensive).
    (
        "gate_violation",
        re.compile(r"(?i)\b(gate\s+violation|gateviolation|violat\w+)\b"),
    ),
)


def classify_error(error_str: str) -> str:
    """Map a parser error string to a coarse error class.

    Falls back to ``"other"`` if no pattern matches — proving the
    classification is non-trivial is C4's job, so we MUST keep ``other``
    reachable.

    The regex set mirrors CONTRACT-116 §3.3 step 4 signatures
    ("no header", "Status", "Interpretations", etc.). The on-disk
    corpus (gemma4:e4b, P1B-01) emits a generic fallback message that
    does NOT mention these tokens — when the regex misses we ask
    ``classify_error_with_body`` to look at the raw body itself.
    """
    if not error_str:
        return "empty_body"
    for cls, pat in _ERROR_CLASS_PATTERNS:
        if pat.search(error_str):
            return cls
    return "other"


# Section-anchor regex used as a last-resort body peek. We only look
# for the most-discriminative sections so the peek is fast and the
# classifier stays spec-aware.
_BODY_STATUS_RE = re.compile(r"^#{1,3}\s+(?:\d+[.:\s]+)?Status\b", re.MULTILINE | re.IGNORECASE)
_BODY_INTERP_RE = re.compile(r"^#{1,3}\s+(?:\d+[.:\s]+)?Interpretations?\b", re.MULTILINE | re.IGNORECASE)
_BODY_DEROG_RE = re.compile(r"^#{1,3}\s+(?:\d+[.:\s]+)?Derogations?\b", re.MULTILINE | re.IGNORECASE)
_BODY_SUBACT_RE = re.compile(r"^#{1,3}\s+(?:\d+[.:\s]+)?Sub-?domain\s+Activations?\b", re.MULTILINE | re.IGNORECASE)
_BODY_H2_RE = re.compile(r"^#{1,2}\s+\S+", re.MULTILINE)


def classify_error_with_body(spec_id: str, error_str: str, body: str) -> str:
    """Body-aware classification: tries the error-string classifier first,
    then peeks at the raw body for spec-specific structural signatures.

    This is the second line of defence called from ``analyse_corpus``
    when ``classify_error`` returned ``"other"`` AND the spec has
    known structural signatures we can recognise.
    """
    cls = classify_error(error_str)
    if cls != "other":
        return cls
    if not body:
        return "other"
    if spec_id == "P1B-LLM-01-INTERPRETATION":
        if not _BODY_STATUS_RE.search(body):
            return "no_status_section"
        if not _BODY_INTERP_RE.search(body):
            return "missing_int"
        if not _BODY_DEROG_RE.search(body):
            return "missing_der"
    elif spec_id == "P1C-LLM-01-OVERLAP-CLASSIFICATION":
        if not _BODY_SUBACT_RE.search(body):
            return "shape_a_misread"
        # No Shape A — fall back to checking for any ## section header.
        if not _BODY_H2_RE.search(body):
            return "no_headers"
    elif spec_id in (
        "P1B-LLM-02-RATIONALE",
        "P1C-LLM-02-COMPOUND-EVENT",
        "P1C-LLM-03-STRATEGIC-SYNTHESIS",
    ):
        if not _BODY_H2_RE.search(body):
            return "no_headers"
    return "other"


# ── YAML-frontmatter & raw-response extraction ──────────────────────────

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_RAW_HEADER_RE = re.compile(r"^##\s+Raw\s+response\s*\n", re.MULTILINE | re.IGNORECASE)


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the first YAML-ish frontmatter block into a dict.

    We deliberately avoid PyYAML here because the corpus contains
    mixed-case keys, quoted strings with apostrophes, and bracketed
    lists — a minimal regex extractor is robust enough and keeps S1
    dependency-free at the CLI level.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes if present.
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        out[key] = value
    return out


def extract_raw_body(text: str) -> str:
    """Return the text after the ``## Raw response`` header (or whole text if absent)."""
    m = _RAW_HEADER_RE.search(text)
    if not m:
        return text
    return text[m.end():]


# ── Per-file outcome ────────────────────────────────────────────────────


def replay_one(
    spec_id: str,
    parser_cls: type,
    body: str,
    gate: Any | None,
) -> tuple[str, str, str]:
    """Run the parser (+ optionally RefGate) on a body.

    Returns ``(outcome, error_class, error_str)`` where:

      - ``outcome`` ∈ {``parse_ok``, ``parse_fail``, ``gate_fail``, ``empty_body``}
      - ``error_class`` is one of the keys in ``_ERROR_CLASS_PATTERNS`` or
        ``other`` / ``empty_body``.
      - ``error_str`` is the raw error string (truncated to 300 chars
        by the caller for the failure-excerpt report).
    """
    if not body or not body.strip():
        return "empty_body", "empty_body", "raw body is empty"

    parsed, err = parser_cls().parse(body)
    if parsed is None:
        return "parse_fail", classify_error(err), err or "parser returned None"

    # Parser succeeded — run RefGate to detect gate_violation.
    if gate is not None:
        gate_result = gate.validate(spec_id, body)
        if not gate_result.valid:
            # Concatenate violation messages into a single error string
            # for the failure-excerpt report.
            joined = "; ".join(f"[{v.rule}] {v.message}" for v in gate_result.violations)
            return "gate_fail", "gate_violation", joined[:1000]
    return "parse_ok", "", ""


# ── File discovery & main loop ──────────────────────────────────────────


def discover_raws(
    raw_dir: Path,
    specs: tuple[str, ...],
    models: tuple[str, ...] | None,
    limit: int,
) -> list[Path]:
    """Return a stable, sorted list of ``*.md`` paths matching the filters.

    ``limit`` caps the count *per spec*, not globally — so every spec
    gets the same number of raws analysed, which keeps the matrix fair.
    """
    files: list[Path] = []
    for spec in specs:
        spec_dir = raw_dir / spec
        if not spec_dir.is_dir():
            logger.warning("Spec dir missing: %s", spec_dir)
            continue
        spec_files = sorted(spec_dir.glob("*.md"))
        if models:
            spec_files = [
                f for f in spec_files
                if _frontmatter_model(f) in set(models)
            ]
        files.extend(spec_files[:limit])
    return files


def _frontmatter_model(path: Path) -> str:
    """Best-effort model name from frontmatter (cheap pre-filter)."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:2048]
    except OSError:
        return ""
    return parse_frontmatter(head).get("model", "")


def analyse_corpus(
    raw_dir: Path,
    specs: tuple[str, ...],
    models: tuple[str, ...] | None,
    limit: int,
    gate: Any | None,
) -> dict[str, Any]:
    """Replay every discovered file; return the full report payload."""
    # Local import — the parser module is heavy (pydantic + state).
    from aegis_phase1._archive.corr061.markdown_parser import (
        MARKDOWN_PARSERS,
    )

    files = discover_raws(raw_dir, specs, models, limit)
    per_file: list[dict[str, Any]] = []

    # Totals accumulator: spec -> model -> dict[outcome -> count]
    totals_by_spec: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {
            "model_count": 0,
            "parse_ok": 0,
            "parse_fail": 0,
            "gate_fail": 0,
            "empty_body": 0,
            "error_classes": defaultdict(int),
        }),
    )

    for path in files:
        spec_id = path.parent.name
        parser_cls = MARKDOWN_PARSERS.get(spec_id)
        if parser_cls is None:
            # No registered parser — count as parse_fail / unknown_parser.
            per_file.append({
                "path": _relpath(path),
                "spec": spec_id,
                "model": "",
                "status": "",
                "attempt": "",
                "outcome": "parse_fail",
                "error_class": "unknown_parser",
                "error_str": f"no MARKDOWN_PARSERS entry for {spec_id}",
            })
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            per_file.append({
                "path": _relpath(path),
                "spec": spec_id,
                "model": "",
                "status": "",
                "attempt": "",
                "outcome": "parse_fail",
                "error_class": "io_error",
                "error_str": str(e),
            })
            continue

        fm = parse_frontmatter(text)
        model = fm.get("model", "")
        status = fm.get("status", "")
        attempt = fm.get("attempt", "")
        body = extract_raw_body(text)

        outcome, error_class, error_str = replay_one(spec_id, parser_cls, body, gate)
        if outcome in ("parse_fail", "empty_body"):
            # Escalate to body-aware classification so the matrix shows
            # real failure diversity (CONTRACT-116 §3.3 step 4).
            error_class = classify_error_with_body(spec_id, error_str, body)

        per_file.append({
            "path": _relpath(path),
            "spec": spec_id,
            "model": model,
            "status": status,
            "attempt": attempt,
            "outcome": outcome,
            "error_class": error_class,
            "error_str": (error_str or "")[:1000],
        })

        cell = totals_by_spec[spec_id][model]
        cell["model_count"] += 1
        if outcome in cell:
            cell[outcome] += 1
        if outcome in ("parse_fail", "empty_body"):
            cell["error_classes"][error_class] += 1

    # JSON-serialise (defaultdict → dict, int keys → str keys for nested error_classes).
    # The contract's C3 test asserts that each spec value contains
    # ``model_count`` / ``parse_ok`` / ``parse_fail`` / ``gate_fail`` /
    # ``error_classes`` directly (flat, aggregated across all models).
    # We keep that flat shape AND expose the per-model breakdown under
    # ``by_model`` so the 3D matrix from CONTRACT-116 §3.3 is still
    # machine-readable for downstream triage tools.
    serial_totals: dict[str, dict[str, Any]] = {}
    for spec in specs:
        by_model = totals_by_spec.get(spec, {})
        agg = {
            "model_count": sum(c["model_count"] for c in by_model.values()),
            "parse_ok": sum(c["parse_ok"] for c in by_model.values()),
            "parse_fail": sum(c["parse_fail"] for c in by_model.values()),
            "gate_fail": sum(c["gate_fail"] for c in by_model.values()),
            "empty_body": sum(c.get("empty_body", 0) for c in by_model.values()),
            "error_classes": {},
        }
        ec: dict[str, int] = {}
        for c in by_model.values():
            for cls, n in c.get("error_classes", {}).items():
                ec[cls] = ec.get(cls, 0) + n
        agg["error_classes"] = ec
        agg["by_model"] = {
            model: {**cell, "error_classes": dict(cell.get("error_classes", {}))}
            for model, cell in by_model.items()
        }
        serial_totals[spec] = agg

    return {
        "run_at": datetime.now(UTC).isoformat(),
        "raw_dir": str(raw_dir),
        "specs": list(specs),
        "models": list(models) if models else None,
        "limit": limit,
        "totals_by_spec": serial_totals,
        "per_file": per_file,
    }


# ── Reporting ───────────────────────────────────────────────────────────


def render_markdown(payload: dict[str, Any]) -> str:
    """Render the human-facing matrix.

    Rows are specs; the columns are model_count / parse_ok /
    parse_fail / gate_fail / error_classes. The C2 test regex assumes
    rows look like ``| P1B-LLM-01 | 12 | 3 | 9 | 0 | ... |`` so we keep
    the spec name in the first column with no extra wrapping.
    """
    lines: list[str] = []
    lines.append("# Parser Replay — S1 (CORR-116)")
    lines.append("")
    lines.append(f"Run at: `{payload['run_at']}`")
    lines.append(f"Raw dir: `{payload['raw_dir']}`")
    lines.append(f"Limit per spec: {payload['limit']}")
    lines.append("")
    lines.append("| spec | model_count | parse_ok | parse_fail | gate_fail | error_classes |")
    lines.append("|------|------------:|---------:|-----------:|----------:|---------------|")

    grand_total = grand_ok = grand_fail = grand_gate = 0
    for spec in payload["specs"]:
        cell = payload["totals_by_spec"].get(spec)
        if not cell or cell["model_count"] == 0:
            # Spec had no raws (or no matching files).
            lines.append(f"| {spec} | 0 | 0 | 0 | 0 | `{{}}` |")
            continue
        ec_str = ", ".join(
            f"{cls}={n}" for cls, n in sorted(cell["error_classes"].items())
        ) or "(none)"
        lines.append(
            f"| {spec} | {cell['model_count']} | {cell['parse_ok']} | "
            f"{cell['parse_fail']} | {cell['gate_fail']} | `{ec_str}` |"
        )
        grand_total += cell["model_count"]
        grand_ok += cell["parse_ok"]
        grand_fail += cell["parse_fail"]
        grand_gate += cell["gate_fail"]

    lines.append("")
    lines.append(
        f"**Totals across all specs:** model_count={grand_total}, "
        f"parse_ok={grand_ok}, parse_fail={grand_fail}, gate_fail={grand_gate}."
    )
    lines.append("")
    return "\n".join(lines)


def render_failures_excerpt(payload: dict[str, Any]) -> str:
    """Render one block per error class with up to 5 offending excerpts."""
    lines: list[str] = ["# Parser Replay — failure excerpts", ""]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in payload["per_file"]:
        if rec["outcome"] in ("parse_fail", "gate_fail", "empty_body"):
            grouped[rec["error_class"]].append(rec)

    for cls, recs in sorted(grouped.items()):
        lines.append(f"## {cls} ({len(recs)} occurrence(s))")
        lines.append("")
        for rec in recs[:5]:
            path = rec["path"]
            spec = rec["spec"]
            model = rec.get("model", "") or "?"
            excerpt = (rec.get("error_str") or "(no error string)")[:300]
            lines.append(f"- `{path}`  spec=`{spec}` model=`{model}`")
            lines.append(f"  > {excerpt}")
        lines.append("")
    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="parser_replay",
        description=(
            "CORR-116 S1 — offline parser replay harness. "
            "Replays every raw LLM response under output/phase1/raw/ "
            "through its registered parser and writes a per-(spec,model) "
            "failure matrix to execution/reports/."
        ),
    )
    p.add_argument(
        "--raw-dir", type=Path, default=DEFAULT_RAW_DIR,
        help=f"Directory containing per-spec subdirs of *.md raws "
             f"(default: {DEFAULT_RAW_DIR}).",
    )
    p.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUT_DIR,
        help=f"Where to write parser_replay_<ts>.{{md,json}} "
             f"(default: {DEFAULT_OUT_DIR}).",
    )
    p.add_argument(
        "--specs", default=",".join(DEFAULT_SPECS),
        help="Comma-separated spec ids to replay (default: all 5).",
    )
    p.add_argument(
        "--models", default="",
        help="Comma-separated model filter; empty = all models in corpus.",
    )
    p.add_argument(
        "--limit", type=int, default=5,
        help="Max raws per spec (default: 5; bump up for full matrix).",
    )
    p.add_argument(
        "--no-gate", action="store_true",
        help="Skip RefGate validation (faster; use only for parser-only triage).",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    specs = tuple(s.strip() for s in args.specs.split(",") if s.strip())
    models = tuple(m.strip() for m in args.models.split(",") if m.strip()) or None

    gate: Any | None = None
    if not args.no_gate:
        try:
            from aegis_phase1.prompts_v2.ref_gate import RefGate

            gate = RefGate()
            logger.info("RefGate loaded.")
        except Exception as e:
            logger.warning("RefGate unavailable (%s); continuing without it.", e)
            gate = None

    payload = analyse_corpus(
        raw_dir=args.raw_dir,
        specs=specs,
        models=models,
        limit=args.limit,
        gate=gate,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    md_path = args.output_dir / f"parser_replay_{ts}.md"
    json_path = args.output_dir / f"parser_replay_{ts}.json"
    # NOTE: do NOT use ``*_failures.md`` here — the C2/C3/C4/C8
    # acceptance commands use ``glob('execution/reports/parser_replay_*.md')``
    # and ``[-1]`` to grab the *latest* matrix report; a ``_failures.md``
    # would sort AFTER ``<ts>.md`` alphabetically and break the pick.
    # Place failures under a sibling prefix that doesn't match the glob.
    fail_path = args.output_dir / f"replay_failures_{ts}.txt"

    md_path.write_text(render_markdown(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    fail_path.write_text(render_failures_excerpt(payload), encoding="utf-8")

    # The C8 test regex matches `^S1 replay: N raws / N parse_ok / ...`.
    totals = payload["totals_by_spec"]
    n_total = sum(c["model_count"] for c in totals.values())
    n_ok = sum(c["parse_ok"] for c in totals.values())
    n_fail = sum(c["parse_fail"] for c in totals.values())
    n_gate = sum(c["gate_fail"] for c in totals.values())
    n_specs = sum(1 for c in totals.values() if c["model_count"] > 0)

    logger.info("Wrote %s, %s, %s", md_path, json_path, fail_path)
    print(
        f"S1 replay: {n_total} raws / {n_ok} parse_ok / "
        f"{n_fail} parse_fail / {n_gate} gate_fail across {n_specs} specs"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
