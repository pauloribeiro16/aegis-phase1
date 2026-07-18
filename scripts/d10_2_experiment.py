#!/usr/bin/env python3
"""D-10.2 (Audit Logging & Traceability) MAP-stage benchmark.

Single-sub-domain benchmark harness for comparing Ollama model output on
the TinyTask D-10.2 sub-domain through the AEGIS-KG v2 MAP pipeline.

For one --model tag, this script:

  1. Loads the TinyTask case via ``Phase1Orchestrator.load``.
  2. Builds the MAP-stage inputs for D-10 via ``assemble_inputs``.
  3. Renders the full MAP-DOMAIN-ADAPT prompt (v1.3 strict contract —
     3 blocks x 5 fields per sub-domain) via ``render_prompt``.
  4. Prints the per-section char counts and total prompt size.
  5. Invokes the chosen Ollama model ONCE (one retry on parse failure).
  6. Parses the output with ``OutputParserV3`` first; falls back to
     ``OutputParserV2`` (v1.2 spec) if V3 fails to parse.
  7. Saves the run to ``logs/phase1/v2/d10_2/runs/<model>_<timestamp>/``:
     - ``prompt.txt``            — rendered prompt
     - ``response.raw.txt``      — raw LLM output
     - ``response.parsed.txt``   — formatted V3 (preferred) or V2 dump
     - ``meta.json``             — run metadata + 9 gates (G1..G9) + parser_version
  8. Regenerates ``MANIFEST.md`` (one row per run, with G9 column).
  9. Reports latency, raw length, status, parser_version, gate results.

Output layout (CONTRACT-022 §F.1):

    logs/phase1/v2/d10_2/
    ├── runs/<model>_<timestamp>/
    │   ├── prompt.txt
    │   ├── response.raw.txt
    │   ├── response.parsed.txt   (if parseable)
    │   └── meta.json
    └── MANIFEST.md              (auto-regenerated)

Pre-existing flat files (``<model>_<ts>.{prompt,raw}.txt``) and run dirs
whose timestamp matches ``20260717T15*``, ``20260717T16*`` or
``20260717T17*`` are deleted at startup.

The script is intentionally read-only: it does NOT modify any source
file in ``src/`` or ``tests/``, does NOT pull any model, and does NOT
commit. Output files are written under ``logs/phase1/v2/d10_2/`` which
is gitignored.

Usage::

    python scripts/d10_2_experiment.py --model gemma4:e2b
    python scripts/d10_2_experiment.py --model gemma4:26b --output-dir logs/phase1/v2/d10_2
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aegis_phase1.v2.domain.parser import (  # noqa: E402 — after sys.path tweak
    OutputParser,
    OutputParserV2,
    OutputParserV3,
    ParseResultV3,
)

PROJECT_ROOT = REPO_ROOT.parent
DEFAULT_CASE = REPO_ROOT / "cases" / "case1-tinytask"
DEFAULT_PREPROC = PROJECT_ROOT / "Methodology-main" / "00_METHODOLOGY" / "PREPROCESSING"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "logs" / "phase1" / "v2" / "d10_2"

DOMAIN_ID = "D-10"

SECTION_HEADERS = (
    "## 1. COMPANY CONTEXT",
    "## 2. EXISTING IMPLEMENTATIONS",
    "## 3. APPLICABLE ARTICLES",
    "## 4. SUB-DOMAIN HSOs",
    "## 5. CROSS-REG ANALYSIS",
    "## 6. KNOWN AMBIGUITIES",
    "## 7. TRACK B SUGGESTION",
    "## 8. TASK",
    "## 9. OUTPUT FORMAT",
)

LLM_TIMEOUT_SECONDS = 240
LLM_MAX_ATTEMPTS = 2  # initial + 1 retry on parse failure (TASK step 3)

# Gate parameters (CONTRACT-022 §F.1 step 4 + §C12).
AUDIT_THEME_KEYWORDS = ("audit", "logging", "traceability", "log")
GENERIC_HEADING_PROHIBITIONS = (
    "Risk Identification",
    "Governance and Oversight",
    "Control Implementation",
    "Incident Response and Management",
    "Monitoring and Analysis",
)
CONNECTIVE_PROHIBITIONS = ("Furthermore", "Moreover", "Additionally")
# Old run timestamps (CONTRACT-022 §F.1 step 6) — deleted at startup so the
# new layout doesn't mix with legacy flat files / leftover directories.
_OLD_RUN_TIMESTAMP_PATTERNS = (
    re.compile(r".*_20260717T15\d+Z$"),
    re.compile(r".*_20260717T16\d+Z$"),
    re.compile(r".*_20260717T17\d+Z$"),
)
_OLD_FLAT_FILE_PATTERNS = (
    re.compile(r".*_20260717T15\d+Z\.(prompt|raw|fix\.raw)\.txt$"),
    re.compile(r".*_20260717T16\d+Z\.(prompt|raw|fix\.raw)\.txt$"),
    re.compile(r".*_20260717T17\d+Z\.(prompt|raw|fix\.raw)\.txt$"),
)

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    root = logging.getLogger()
    has_stream = any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    if not has_stream:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(logging.INFO)


def _safe_slug(tag: str) -> str:
    return tag.replace(":", "_").replace("/", "_")


def _iso_now() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _slice_sections(prompt: str) -> dict[str, str]:
    """Map ``header → text`` for each ``## N.`` marker."""
    indices: list[tuple[str, int]] = []
    for header in SECTION_HEADERS:
        idx = prompt.find(header)
        if idx < 0:
            logger.warning("render_prompt output missing marker %r", header)
            continue
        indices.append((header, idx))

    out: dict[str, str] = {}
    for i, (header, start) in enumerate(indices):
        end = indices[i + 1][1] if i + 1 < len(indices) else len(prompt)
        out[header] = prompt[start:end]
    return out


def _load_state(case_path: Path, preproc_path: Path):
    """Load the case via the orchestrator; expose ``orch.state``."""
    import aegis_phase1.env  # noqa: F401, I001 — load src/.env side-effect

    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    work_dir = REPO_ROOT / "work"
    orch = Phase1Orchestrator(work_dir=str(work_dir), llm_invoker=None)
    orch.load(str(case_path), str(preproc_path))
    return orch


def _build_invoker(model: str):
    """Build the real Ollama ``UnifiedInvoker`` for the given tag."""
    from aegis_phase1.v2.llm import OllamaUnreachableError, build_llm_invoker

    logger.info("Building Ollama invoker (model=%s, timeout=%ds)...", model, LLM_TIMEOUT_SECONDS)
    try:
        return build_llm_invoker(model=model)
    except OllamaUnreachableError as exc:
        logger.error("Ollama is unreachable for model %s: %s", model, exc)
        return None


def _invoke_once(invoker, prompt: str, feedback: str) -> dict:
    """Single LLM call returning ``{raw, status, latency_s}``.

    Treats ``OllamaUnreachableError`` as a hard stop (the invoker's probe
    has cached "unreachable" — retrying in-process is pointless). The
    caller surfaces the empty ``raw`` and ``OLLAMA_UNREACHABLE`` so the
    outer benchmark loop can move on to the next model.
    """
    from aegis_phase1.v2.llm import OllamaUnreachableError

    t0 = time.monotonic()
    try:
        response = invoker.invoke(prompt, feedback=feedback)
    except OllamaUnreachableError as exc:
        elapsed = time.monotonic() - t0
        logger.error("Ollama unreachable mid-call: %s", exc)
        return {
            "raw": "",
            "status": "OLLAMA_UNREACHABLE",
            "latency_s": elapsed,
            "response": {"error": str(exc)},
        }
    elapsed = time.monotonic() - t0
    raw = response.get("raw") or ""
    status = response.get("status", "FAILED")
    return {"raw": raw, "status": status, "latency_s": elapsed, "response": response}


# ─── Gate evaluators (G1..G8) ───────────────────────────────────────────


def _extract_source_anchors(inputs: dict[str, Any]) -> set[str]:
    """Extract all OJ anchors present in the assembled inputs (articles + sub-SOs)."""
    from aegis_phase1.v2.domain.anchor_validator import extract_anchors

    chunks: list[str] = []
    for art in inputs.get("applicable_articles") or []:
        text = str(art.get("text") or "")
        if text:
            chunks.append(text)
    for sub in inputs.get("subdomains") or []:
        chunks.append(str(sub.get("hso_hl") or ""))
        for pr in sub.get("hso_per_reg") or []:
            chunks.append(str(pr.get("objective") or ""))
    return extract_anchors("\n".join(chunks))


def _gate_audit_theme(response: str) -> bool:
    """G1: response mentions audit / logging / traceability / log."""
    low = response.lower()
    return any(kw in low for kw in AUDIT_THEME_KEYWORDS)


def _gate_no_company(response: str, company_name: str | None) -> bool:
    """G2: response does not name the company (regulation-centric output)."""
    if not company_name:
        return True
    return company_name.lower() not in response.lower()


def _gate_gdpr_cra(response: str, parsed_v3: ParseResultV3 | None = None) -> bool:
    """G3: response mentions both GDPR and CRA (TinyTask's applicable regs).

    V3-aware: when ``parsed_v3`` succeeded, scans the block labels
    (``**GDPR Objective.**``, ``**CRA Objective.**``) and all field
    contents (Original, Adapted, Rationale, Adjustments needed) for the
    regulation codes. Falls back to scanning the raw response otherwise.
    """
    if parsed_v3 is not None and parsed_v3.success and parsed_v3.subdomains:
        haystack_parts: list[str] = []
        for sub in parsed_v3.subdomains:
            for block in sub.blocks:
                haystack_parts.append(block.label)
                haystack_parts.append(block.original)
                haystack_parts.append(block.adapted)
                haystack_parts.append(block.rationale)
                haystack_parts.append(block.adjustments)
        haystack = "\n".join(haystack_parts)
        return "GDPR" in haystack and "CRA" in haystack
    return "GDPR" in response and "CRA" in response


def _gate_anchors(response: str, parsed_v3: ParseResultV3 | None = None) -> bool:
    """G4: response cites at least one legal anchor (Art. / Annex / §).

    V3-aware: when ``parsed_v3`` succeeded, scans across all ``Original``
    and ``Adapted`` fields in all blocks. Falls back to scanning the
    raw response otherwise.
    """
    if parsed_v3 is not None and parsed_v3.success and parsed_v3.subdomains:
        combined = "\n".join(
            (block.original or "") + "\n" + (block.adapted or "")
            for sub in parsed_v3.subdomains
            for block in sub.blocks
        )
        text = combined
    else:
        text = response
    if not text:
        return False
    return bool(
        re.search(r"\bArt\.\s*\d", text)
        or re.search(r"\bAnnex\s+[IVX]+", text, re.IGNORECASE)
        or re.search(r"§\s*\d", text)
    )


def _gate_no_furthermore(response: str) -> bool:
    """G5: response does not start any sentence with a forbidden connective."""
    if not response:
        return True
    sentences = re.split(r"(?<=[.!?])\s+", response)
    for sentence in sentences:
        words = sentence.lstrip().split(maxsplit=1)
        if not words:
            continue
        head = words[0].rstrip(",;:")
        if head in CONNECTIVE_PROHIBITIONS:
            return False
    return True


def _gate_no_generic_headings(response: str) -> bool:
    """G6: response does not introduce forbidden generic consulting headings."""
    if not response:
        return True
    return not any(heading in response for heading in GENERIC_HEADING_PROHIBITIONS)


def _gate_parse(parse_success: bool) -> bool:
    """G7: OutputParserV3.parse succeeded (v1.3 contract; V2 is fallback)."""
    return bool(parse_success)


def _gate_g9_v3_structure(response_raw: str) -> tuple[bool, str]:
    """G9: each block has the 5 fields (Original, Adapted, Rationale, Adjustments needed, Considerations).

    Returns ``(passed, detail)``. When passed, ``detail`` is a short success
    message (``"<N> subdomains x <M> blocks each, all 5 fields present"``).
    When failed, ``detail`` is the specific reason.

    Uses :class:`OutputParserV3` to parse the raw LLM output (v1.3 spec).
    """
    parser_v3 = OutputParserV3()
    result = parser_v3.parse(response_raw)
    if not result.subdomains:
        return (False, "no sub-domains parsed")
    for sub in result.subdomains:
        if len(sub.blocks) < 3:
            return (
                False,
                f"sub-domain '{sub.subdomain_id}' has only {len(sub.blocks)} blocks "
                "(expected >=3: Generic + >=2 regs)",
            )
        for block in sub.blocks:
            if not block.has_all_5_fields():
                missing: list[str] = []
                if not block.original:
                    missing.append("Original")
                if not block.adapted:
                    missing.append("Adapted")
                if not block.rationale:
                    missing.append("Rationale")
                if not block.adjustments:
                    missing.append("Adjustments needed")
                if not block.considerations:
                    missing.append("Considerations")
                return (
                    False,
                    f"block '{block.label}' missing field '{missing[0]}'",
                )
    n_subs = len(result.subdomains)
    n_blocks = sum(len(s.blocks) for s in result.subdomains)
    return (
        True,
        f"{n_subs} subdomains x >=3 blocks each ({n_blocks} total), all 5 fields present",
    )


def _gate_anchor_validation(response: str, source_anchors: set[str]) -> bool:
    """G8: every anchor cited in the response is also present in the source."""
    from aegis_phase1.v2.domain.anchor_validator import validate_output_citations

    ok, _unknown = validate_output_citations(response or "", source_anchors)
    return ok


def _evaluate_gates(
    response: str,
    parse_success: bool,
    source_anchors: set[str],
    company_name: str | None,
    parsed_v3: ParseResultV3 | None = None,
) -> tuple[dict[str, bool], dict[str, str]]:
    """Evaluate all 9 gates (G1..G9).

    Returns ``(gates, details)`` where ``gates`` is the flat boolean
    map written to ``meta.json["gates"]`` and ``details`` carries
    non-boolean per-gate supplementary info (e.g. G9 reason string).
    """
    g9_pass, g9_detail = _gate_g9_v3_structure(response)
    gates = {
        "g1_audit_theme": _gate_audit_theme(response),
        "g2_no_company": _gate_no_company(response, company_name),
        "g3_gdpr_cra": _gate_gdpr_cra(response, parsed_v3),
        "g4_anchors": _gate_anchors(response, parsed_v3),
        "g5_no_furthermore": _gate_no_furthermore(response),
        "g6_no_generic_headings": _gate_no_generic_headings(response),
        "g7_parse": _gate_parse(parse_success),
        "g8_anchor_validation": _gate_anchor_validation(response, source_anchors),
        "g9_v3_structure": g9_pass,
    }
    details = {"g9_v3_structure_detail": g9_detail}
    return gates, details


# ─── Output layout helpers ──────────────────────────────────────────────


def _purge_legacy_runs(output_dir: Path) -> int:
    """Delete legacy runs/flat files matching the 20260717T1[567] timestamps."""
    removed = 0
    runs_dir = output_dir / "runs"
    if runs_dir.exists():
        for entry in sorted(runs_dir.iterdir(), reverse=True):
            if not entry.is_dir():
                continue
            if any(p.match(entry.name) for p in _OLD_RUN_TIMESTAMP_PATTERNS):
                logger.info("Purging legacy run dir %s", entry)
                shutil.rmtree(entry)
                removed += 1
    for pattern in _OLD_FLAT_FILE_PATTERNS:
        for old in output_dir.glob(pattern.pattern.replace("\\", "")):
            logger.info("Purging legacy flat file %s", old)
            old.unlink()
            removed += 1
    return removed


def _run_dir_for(output_dir: Path, model_slug: str, timestamp: str) -> Path:
    return output_dir / "runs" / f"{model_slug}_{timestamp}"


def _write_run_artefacts(
    run_dir: Path,
    prompt: str,
    raw: str,
    parsed_text: str | None,
    meta: dict[str, Any],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (run_dir / "response.raw.txt").write_text(raw or "", encoding="utf-8")
    if parsed_text is not None:
        (run_dir / "response.parsed.txt").write_text(parsed_text, encoding="utf-8")
    (run_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _format_parsed(parsed_v3: ParseResultV3 | None, parsed_v2: Any) -> str:
    """Render a parsed result as a human-readable dump.

    Prefers the v1.3 (3-block x 5-field) format when ``parsed_v3`` parsed
    successfully; otherwise falls back to the v1.2 dump.
    """
    if parsed_v3 is not None and parsed_v3.success:
        return _format_parsed_v3(parsed_v3)
    if parsed_v2 is not None and getattr(parsed_v2, "success", False):
        return _format_parsed_v2(parsed_v2)
    return ""


def _format_parsed_v2(parsed: Any) -> str:
    """Render an OutputParserV2.ParseResultV2 as a JSON-ish dump."""
    try:
        return json.dumps(
            _serialise_parsed(parsed), indent=2, ensure_ascii=False, default=str,
        )
    except Exception:  # pragma: no cover — defensive
        return repr(parsed)


def _format_parsed_v3(parsed: ParseResultV3) -> str:
    """Render a v1.3 ParseResultV3 in the canonical block-by-block form.

    Format (per the contract):

        Parsed subdomains: <N>
          ### <sid> — <title>
            ## <label>
              Original: <first 80 chars>...
              Adapted: <first 80 chars>...
              Rationale: <first 80 chars>...
              Adjustments needed: <first 80 chars>...
              Considerations: <M> bullets
    """
    lines: list[str] = []
    lines.append(f"Parsed subdomains: {len(parsed.subdomains)}")
    for sub in parsed.subdomains:
        lines.append(f"  ### {sub.subdomain_id} — {sub.title}")
        for block in sub.blocks:
            lines.append(f"    ## {block.label}")
            lines.append(f"      Original: {_first_chars(block.original, 80)}")
            lines.append(f"      Adapted: {_first_chars(block.adapted, 80)}")
            lines.append(f"      Rationale: {_first_chars(block.rationale, 80)}")
            lines.append(
                f"      Adjustments needed: {_first_chars(block.adjustments, 80)}",
            )
            lines.append(f"      Considerations: {len(block.considerations)} bullets")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _first_chars(text: str, n: int) -> str:
    """Return ``text`` truncated to its first ``n`` characters.

    Appends ``...`` when the truncation actually shortens the string.
    """
    if not text:
        return ""
    if len(text) <= n:
        return text
    return text[:n] + "..."


def _serialise_parsed(parsed: Any) -> Any:
    if parsed is None:
        return None
    if hasattr(parsed, "_asdict"):
        return {k: _serialise_parsed(v) for k, v in parsed._asdict().items()}
    if hasattr(parsed, "model_dump"):
        return parsed.model_dump()
    if isinstance(parsed, list):
        return [_serialise_parsed(v) for v in parsed]
    if isinstance(parsed, dict):
        return {k: _serialise_parsed(v) for k, v in parsed.items()}
    return parsed


def _regenerate_manifest(output_dir: Path) -> None:
    """Regenerate MANIFEST.md from ``runs/*/meta.json`` files."""
    runs_dir = output_dir / "runs"
    lines: list[str] = ["# D-10.2 Benchmark Runs", ""]
    header = (
        "| Run | Model | Latency | Status | G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 | G9 | Adapted | Notes |"
    )
    sep = "|" + "|".join(["---"] * 15) + "|"
    lines.extend([header, sep])
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            meta_path = run_dir / "meta.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            gates = meta.get("gates") or {}
            row = [
                run_dir.name,
                str(meta.get("model", "")),
                f"{meta.get('latency_seconds', 0.0):.2f}s",
                str(meta.get("status", "")),
                _gate_cell(gates.get("g1_audit_theme")),
                _gate_cell(gates.get("g2_no_company")),
                _gate_cell(gates.get("g3_gdpr_cra")),
                _gate_cell(gates.get("g4_anchors")),
                _gate_cell(gates.get("g5_no_furthermore")),
                _gate_cell(gates.get("g6_no_generic_headings")),
                _gate_cell(gates.get("g7_parse")),
                _gate_cell(gates.get("g8_anchor_validation")),
                _gate_cell(gates.get("g9_v3_structure")),
                str(meta.get("adapted_chars", 0)),
                str(meta.get("notes", "")),
            ]
            lines.append("| " + " | ".join(row) + " |")
    (output_dir / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gate_cell(value: Any) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "-"


# ─── Main entry point ───────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="Ollama model tag (e.g. gemma4:e2b).")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for run artefacts (default: {DEFAULT_OUTPUT_DIR}).",
    )
    args = parser.parse_args()

    _configure_logging()

    case_path = DEFAULT_CASE
    preproc_path = DEFAULT_PREPROC
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print(f"D-10.2 MAP-stage benchmark — model={args.model}")
    print("=" * 78)
    print(f"Case              : {case_path}")
    print(f"Regulatory base   : {preproc_path}")
    print(f"Domain            : {DOMAIN_ID}")
    print(f"Output dir        : {output_dir}")
    print(f"LLM max attempts  : {LLM_MAX_ATTEMPTS} (initial + 1 retry on parse failure)")

    # Purge legacy runs/flat files before the new layout starts.
    removed = _purge_legacy_runs(output_dir)
    print(f"Purged legacy runs: {removed}")

    print()

    # ─── Load state ──────────────────────────────────────────────
    logger.info("Loading case via Phase1Orchestrator...")
    orch = _load_state(case_path, preproc_path)
    state = orch.state
    ctx = state.get("company_context")
    company_name = ctx.company_name if ctx is not None else None
    if ctx is None:
        print("ERROR: company_context is None after load(); aborting.")
        return 2
    print(
        f"Company={ctx.company_name!r} regs={list(ctx.applicable_regs)} "
        f"sector={ctx.sector!r} scale={ctx.scale!r}"
    )
    print()

    # ─── Build inputs + render prompt ────────────────────────────
    from aegis_phase1.v2.domain.inputs import assemble_inputs
    from aegis_phase1.v2.domain.prompt import render_prompt

    inputs = assemble_inputs(state, DOMAIN_ID)
    prompt = render_prompt(inputs, feedback="")
    source_anchors = _extract_source_anchors(inputs)

    print("--- PROMPT SECTION SIZES ---")
    sections = _slice_sections(prompt)
    for header in SECTION_HEADERS:
        text = sections.get(header)
        if text is None:
            print(f"  {header}: <MISSING>")
        else:
            print(f"  {header}: {len(text)} chars")
    print(f"  TOTAL PROMPT       : {len(prompt)} chars")
    print(f"  SOURCE ANCHORS     : {len(source_anchors)} ({sorted(source_anchors)})")
    print()

    slug = _safe_slug(args.model)
    ts = _iso_now()
    run_dir = _run_dir_for(output_dir, slug, ts)

    # ─── Build invoker ───────────────────────────────────────────
    invoker = _build_invoker(args.model)
    if invoker is None:
        print("ABORT: Ollama is unreachable for the requested model; cannot invoke LLM.")
        meta = {
            "model": args.model,
            "timestamp_iso": ts,
            "prompt_chars": len(prompt),
            "response_chars": 0,
            "latency_seconds": 0.0,
            "attempts": 0,
            "status": "OLLAMA_UNREACHABLE",
            "parser_version": "NONE",
            "parser_success": False,
            "parser_v2_success": False,
            "adapted_chars": 0,
            "source_anchor_count": len(source_anchors),
            "gates": {k: False for k in (
                "g1_audit_theme", "g2_no_company", "g3_gdpr_cra", "g4_anchors",
                "g5_no_furthermore", "g6_no_generic_headings", "g7_parse",
                "g8_anchor_validation", "g9_v3_structure",
            )},
            "gate_details": {"g9_v3_structure_detail": "no LLM call made"},
            "notes": "Ollama unreachable; meta only.",
        }
        _write_run_artefacts(run_dir, prompt, "", None, meta)
        _regenerate_manifest(output_dir)
        return 3

    # ─── LLM call (initial + optional retry on parse failure) ────
    parser_v3 = OutputParserV3()
    parser_v2 = OutputParserV2()
    parser_legacy = OutputParser()
    feedback = ""
    attempts = 0
    final: dict[str, Any] = {
        "raw": "",
        "status": "FAILED",
        "latency_s": 0.0,
        "parsed_v3": None,
        "parsed_v2": None,
        "parsed_legacy": None,
        "parser_version": "NONE",
        "feedback_appended": False,
    }

    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        attempts = attempt
        # Re-render the prompt only when feedback is non-empty (cheap path
        # for attempt 1 since the prompt is already computed above).
        attempt_prompt = render_prompt(inputs, feedback=feedback) if feedback else prompt

        logger.info("LLM attempt %d (model=%s, feedback=%s)...", attempt, args.model, "yes" if feedback else "no")
        call = _invoke_once(invoker, attempt_prompt, feedback="")
        parsed_v3 = parser_v3.parse(call["raw"])
        parsed_v2 = parser_v2.parse(call["raw"])
        parsed_legacy = parser_legacy.parse(call["raw"])
        parser_version = (
            "V3" if parsed_v3.success
            else "V2" if parsed_v2.success
            else "NONE"
        )
        logger.info(
            "LLM attempt %d: status=%s raw_len=%d latency=%.2fs parse_v3=%s parse_v2=%s parser_version=%s",
            attempt, call["status"], len(call["raw"]), call["latency_s"],
            parsed_v3.success, parsed_v2.success, parser_version,
        )

        final = {
            "raw": call["raw"],
            "status": call["status"],
            "latency_s": call["latency_s"],
            "parsed_v3": parsed_v3,
            "parsed_v2": parsed_v2,
            "parsed_legacy": parsed_legacy,
            "parser_version": parser_version,
            "feedback_appended": bool(feedback),
            "prompt_used": attempt_prompt,
        }
        # Accept the output as soon as either V3 (preferred, v1.3 contract)
        # or V2 (v1.2 fallback) parses successfully.
        if parsed_v3.success or parsed_v2.success:
            break
        # Hard stop when Ollama itself became unreachable — retrying
        # in-process will just hit the cached probe again.
        if call["status"] == "OLLAMA_UNREACHABLE":
            logger.error("Stopping retries: Ollama became unreachable.")
            break
        feedback = (
            "Previous output was malformed. Re-emit strict v1.3 format: "
            "for each sub-domain, emit Generic + per-reg blocks, each with "
            "Original / Adapted / Rationale / Adjustments needed / Considerations "
            "fields (do NOT emit KEY_ADJUSTMENTS or CONFIDENCE)."
        )

    raw = final["raw"]
    parsed_v3 = final["parsed_v3"]
    parsed_v2 = final["parsed_v2"]
    parsed_legacy = final["parsed_legacy"]
    parser_version = final["parser_version"]
    latency = final["latency_s"]
    parse_success = parsed_v3.success if parsed_v3 is not None else False
    gates, gate_details = _evaluate_gates(
        raw, parse_success, source_anchors, company_name, parsed_v3=parsed_v3,
    )

    adapted_chars = (
        sum(len(b.adapted) for s in parsed_v3.subdomains for b in s.blocks)
        if parsed_v3 is not None and parsed_v3.success
        else len(parsed_v2.legacy_adapted_objective) if parsed_v2 is not None else 0
    )

    meta = {
        "model": args.model,
        "timestamp_iso": ts,
        "prompt_chars": len(prompt),
        "response_chars": len(raw),
        "latency_seconds": latency,
        "attempts": attempts,
        "status": final["status"],
        "parser_version": parser_version,
        "parser_success": bool(parse_success),
        "parser_v2_success": bool(parsed_v2.success) if parsed_v2 is not None else False,
        "adapted_chars": adapted_chars,
        "source_anchor_count": len(source_anchors),
        "gates": gates,
        "gate_details": gate_details,
        "notes": "feedback retry=" + ("yes" if final["feedback_appended"] else "no"),
    }
    parsed_text = _format_parsed(parsed_v3, parsed_v2) or None
    _write_run_artefacts(run_dir, prompt, raw, parsed_text, meta)
    _regenerate_manifest(output_dir)
    logger.info("Saved run artefacts → %s", run_dir)
    print(f"  → saved run artefacts: {run_dir}")

    print()
    print("=" * 78)
    print(f"LLM CALL RESULTS (model={args.model}, attempts={attempts})")
    print("=" * 78)
    print(f"Status           : {final['status']}")
    print(f"Latency          : {latency:.2f} s")
    print(f"Raw length       : {len(raw)} chars")
    print(f"Parser version   : {parser_version}")
    print(f"Parse V3 success : {parsed_v3.success if parsed_v3 is not None else False}")
    print(f"Parse V2 success : {parsed_v2.success if parsed_v2 is not None else False}")
    print(f"Adapted (chars)  : {adapted_chars}")
    if parsed_v3 is not None and parsed_v3.success:
        print(f"V3 subdomains    : {len(parsed_v3.subdomains)}")
        print(f"V3 blocks total  : {sum(len(s.blocks) for s in parsed_v3.subdomains)}")
    elif parsed_v2 is not None and parsed_v2.success:
        print(f"V2 subdomains    : {len(parsed_v2.subdomains)}")
        print(f"Confidence       : {parsed_legacy.confidence}")
    if (parsed_v3 is not None and parsed_v3.error_feedback) or (
        parsed_v2 is not None and parsed_v2.error_feedback
    ):
        v3_fb = parsed_v3.error_feedback if parsed_v3 else ""
        v2_fb = parsed_v2.error_feedback if parsed_v2 else ""
        print(f"Parse feedback   : V3={v3_fb!r} | V2={v2_fb!r}")
    print(f"Feedback retry   : {final['feedback_appended']}")
    print()
    print("Gates:")
    for gate_name, gate_ok in gates.items():
        marker = "PASS" if gate_ok else "FAIL"
        print(f"  {gate_name:<26} {marker}")
    if gate_details.get("g9_v3_structure_detail"):
        print(f"  G9 detail         : {gate_details['g9_v3_structure_detail']}")
    print()
    print("--- first 800 chars of raw response ---")
    print(raw[:800] if raw else "  <EMPTY>")
    print()
    print("Artefacts:")
    print(f"  run dir : {run_dir}")
    print(f"  manifest: {output_dir / 'MANIFEST.md'}")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    sys.exit(main())
