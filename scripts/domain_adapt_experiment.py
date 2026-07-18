#!/usr/bin/env python3
"""MAP-stage benchmark — generalized across AEGIS domains (CORR-023).

Per-domain benchmark harness for the AEGIS-KG v2 MAP pipeline. Evolved
from ``scripts/d10_2_experiment.py`` (CORR-022, D-10 only) to accept any
``--domain D-XX`` in D-01..D-10. The gates are parameterized on the
case's applicable regulations rather than hardcoded to GDPR + CRA.

For one ``--model`` tag and one ``--domain``, this script:

  1. Loads the case via ``Phase1Orchestrator.load``.
  2. Builds the MAP-stage inputs for the chosen domain via ``assemble_inputs``.
  3. Renders the full MAP-DOMAIN-ADAPT prompt (v1.3 strict contract —
     Generic + one block per applicable regulation, 5 fields each).
  4. Prints the per-section char counts and total prompt size.
  5. Invokes the chosen Ollama model ONCE (one retry on parse failure).
  6. Parses the output with ``OutputParserV3`` first; falls back to
     ``OutputParserV2`` (v1.2 spec) if V3 fails to parse.
  7. Saves the run to ``logs/phase1/v2/<domain_slug>/runs/<model>_<timestamp>/``:
     - ``prompt.txt``            — rendered prompt
     - ``response.raw.txt``      — raw LLM output
     - ``response.parsed.txt``   — formatted V3 (preferred) or V2 dump
     - ``meta.json``             — run metadata + 9 gates (G1..G9) + parser_version
  8. Regenerates ``MANIFEST.md`` (one row per run, with gate columns).
  9. Reports latency, raw length, status, parser_version, gate results.

Gate parameterization (CORR-023 changes vs CORR-022):

  - **G1 (audit_theme)**: retained as informational only. The D-10-specific
    ``AUDIT_THEME_KEYWORDS`` are still computed and recorded in meta.json,
    but the gate is set to ``True`` unconditionally (it was a domain-affinity
    probe redundant with G4 + G7 + G9).
  - **G3 (regs_present)**: takes ``applicable_regs`` from inputs and checks
    each appears in the V3 haystack. For TinyTask (GDPR + CRA) this is
    equivalent to the old ``g3_gdpr_cra``; for a case with three applicable
    regs it checks all three.
  - **G5 (no_forbidden_connectives)**: ``CONNECTIVE_PROHIBITIONS`` aligned
    with the full 7-item list in ``prompt.py`` (was only 3 of 7 in CORR-022).
  - **G9 (v3_structure)**: minimum blocks per sub-domain is now
    ``len(applicable_regs) + 1`` (Generic + one per applicable reg), not
    the hardcoded ``3`` from CORR-022.
  - G2/G4/G6/G7/G8: unchanged (already domain- and regulation-agnostic).

Usage::

    python scripts/domain_adapt_experiment.py --domain D-10 --model gemma4:e2b
    python scripts/domain_adapt_experiment.py --domain D-09 --model gemma4:e2b
    python scripts/domain_adapt_experiment.py --model gemma4:e2b          # --domain defaults to D-10
"""

from __future__ import annotations

import argparse
import json
import logging
import re
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
DEFAULT_DOMAIN = "D-10"

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
LLM_MAX_ATTEMPTS = 2  # initial + 1 retry on parse failure

# Gate parameters (CORR-023).
# G1 audit-theme keywords — D-10-specific; kept for informational logging
# only, the gate itself is set to True (see _evaluate_gates).
AUDIT_THEME_KEYWORDS = ("audit", "logging", "traceability", "log")
GENERIC_HEADING_PROHIBITIONS = (
    "Risk Identification",
    "Governance and Oversight",
    "Control Implementation",
    "Incident Response and Management",
    "Monitoring and Analysis",
)
# G5: aligned with the full 7-item list in prompt.py (CONTRACT-022 only
# checked the first 3). All connectives the prompt prohibits are now gated.
CONNECTIVE_PROHIBITIONS = (
    "Furthermore",
    "Moreover",
    "Additionally",
    "Also",
    "In addition",
    "Besides",
    "On top of that",
    "As well as",
)

# Canonical regulation label variants — used to detect a regulation's
# presence in the output even when the LLM uses spaced/punctuated forms
# (e.g. "NIS 2" vs "NIS2", "AI Act" vs "AI_Act").
_REG_LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "GDPR": ("GDPR",),
    "CRA": ("CRA",),
    "NIS2": ("NIS2", "NIS 2", "NIS-2"),
    "DORA": ("DORA",),
    "AI_Act": ("AI Act", "AI_Act", "AIAct", "AIA"),
}

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


def _domain_slug(domain_id: str) -> str:
    """Folder name for a domain's runs dir (e.g. ``D-10`` → ``d10``)."""
    return domain_id.lower().replace("-", "")


def _iso_now() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _canonical_regs(regs: list[str]) -> list[str]:
    """Map raw regulation codes to the canonical short names used in the
    catalog (GDPR, CRA, NIS2, DORA, AI_Act). Tolerates spaces/underscores."""
    out: list[str] = []
    for reg in regs:
        compact = re.sub(r"[\s_-]+", "", reg).lower()
        canonical = {
            "gdpr": "GDPR",
            "cra": "CRA",
            "nis2": "NIS2",
            "dora": "DORA",
            "aiact": "AI_Act",
            "ai": "AI_Act",
        }.get(compact, reg)
        if canonical not in out:
            out.append(canonical)
    return out


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
    """Single LLM call returning ``{raw, status, latency_s}``."""
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


# ─── Gate evaluators ────────────────────────────────────────────────────


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
    """G1 (informational): response mentions an audit/logging keyword.

    The keyword list is D-10-specific; for other domains this is not a
    meaningful domain-affinity signal, so the gate value is forced True
    in :func:`_evaluate_gates`. This function is retained for the meta
    audit-trail.
    """
    low = response.lower()
    return any(kw in low for kw in AUDIT_THEME_KEYWORDS)


def _gate_no_company(response: str, company_name: str | None) -> bool:
    """G2: response does not name the company (regulation-centric output)."""
    if not company_name:
        return True
    return company_name.lower() not in response.lower()


def _gate_all_applicable_regs(
    response: str,
    applicable_regs: list[str],
    parsed_v3: ParseResultV3 | None = None,
) -> bool:
    """G3: every applicable regulation appears in the output.

    CORR-023 generalization of CORR-022's ``g3_gdpr_cra``. For TinyTask
    (GDPR + CRA) this is equivalent to the old check; for a case with
    three applicable regs it requires all three. The check is alias-aware
    so ``NIS2`` matches an output that writes ``NIS 2``.
    """
    if not applicable_regs:
        return True
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
    else:
        haystack = response
    for reg in applicable_regs:
        aliases = _REG_LABEL_ALIASES.get(reg, (reg,))
        if not any(alias in haystack for alias in aliases):
            return False
    return True


def _gate_anchors(response: str, parsed_v3: ParseResultV3 | None = None) -> bool:
    """G4: response cites at least one legal anchor (Art. / Annex / §)."""
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


def _gate_no_forbidden_connectives(response: str) -> bool:
    """G5: response does not start any sentence with a forbidden connective.

    CORR-023: the prohibition list is aligned with the full 7-item list
    in ``prompt.py`` (CONTRACT-022 only checked 3 of 7).
    """
    if not response:
        return True
    sentences = re.split(r"(?<=[.!?])\s+", response)
    for sentence in sentences:
        words = sentence.lstrip().split(maxsplit=2)
        if not words:
            continue
        # Two-word connectives ("In addition", "On top of that", "As well as",
        # "Besides,") need a wider check than the first token. We compare the
        # first up-to-3 words against each prohibition's leading tokens.
        head3 = " ".join(words).rstrip(",;:")
        head1 = words[0].rstrip(",;:")
        for conn in CONNECTIVE_PROHIBITIONS:
            conn_words = conn.split()
            if len(conn_words) == 1 and head1 == conn_words[0]:
                return False
            if len(conn_words) > 1 and head3.split()[: len(conn_words)] == conn_words:
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


def _gate_g9_v3_structure(
    response_raw: str, min_blocks_per_sub: int
) -> tuple[bool, str]:
    """G9: each sub-domain has the expected number of blocks and all 5 fields.

    CORR-023: ``min_blocks_per_sub`` is derived from ``len(applicable_regs)+1``
    rather than the hardcoded ``3`` from CORR-022. A domain whose only
    applicable regulation is GDPR (e.g. a hypothetical case) would need
    only 2 blocks (Generic + GDPR) per sub-domain.

    Returns ``(passed, detail)``.
    """
    parser_v3 = OutputParserV3()
    result = parser_v3.parse(response_raw)
    if not result.subdomains:
        return (False, "no sub-domains parsed")
    for sub in result.subdomains:
        if len(sub.blocks) < min_blocks_per_sub:
            return (
                False,
                f"sub-domain '{sub.subdomain_id}' has only {len(sub.blocks)} blocks "
                f"(expected >= {min_blocks_per_sub}: Generic + "
                f"{min_blocks_per_sub - 1} applicable regs)",
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
        f"{n_subs} subdomains x >= {min_blocks_per_sub} blocks each "
        f"({n_blocks} total), all 5 fields present",
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
    applicable_regs: list[str],
    parsed_v3: ParseResultV3 | None = None,
) -> tuple[dict[str, bool], dict[str, str]]:
    """Evaluate all 9 gates (G1..G9).

    Returns ``(gates, details)``. ``gates`` is the flat boolean map written
    to ``meta.json["gates"]``; ``details`` carries supplementary info.

    CORR-023: G1 is recorded as ``True`` unconditionally (audit-theme is a
    D-10-specific probe redundant with G4/G7/G9). The raw audit-theme check
    is preserved in ``details["g1_audit_theme_detail"]`` for the audit trail.
    """
    min_blocks = max(2, len(applicable_regs) + 1)
    g9_pass, g9_detail = _gate_g9_v3_structure(response, min_blocks)
    audit_present = _gate_audit_theme(response)
    gates = {
        # G1 forced True (see docstring); raw value recorded in details.
        "g1_audit_theme": True,
        "g2_no_company": _gate_no_company(response, company_name),
        "g3_regs_present": _gate_all_applicable_regs(response, applicable_regs, parsed_v3),
        "g4_anchors": _gate_anchors(response, parsed_v3),
        "g5_no_forbidden_connectives": _gate_no_forbidden_connectives(response),
        "g6_no_generic_headings": _gate_no_generic_headings(response),
        "g7_parse": _gate_parse(parse_success),
        "g8_anchor_validation": _gate_anchor_validation(response, source_anchors),
        "g9_v3_structure": g9_pass,
    }
    details = {
        "g9_v3_structure_detail": g9_detail,
        "g1_audit_theme_detail": f"audit-keyword present={audit_present} (informational; gate forced True)",
        "g3_regs_present_detail": f"applicable_regs={applicable_regs}, min_blocks_per_sub={min_blocks}",
    }
    return gates, details


# ─── Output layout helpers ──────────────────────────────────────────────


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
    """Render a parsed result as a human-readable dump."""
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
    """Render a v1.3 ParseResultV3 in the canonical block-by-block form."""
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


def _regenerate_manifest(output_dir: Path, domain_id: str) -> None:
    """Regenerate MANIFEST.md from ``runs/*/meta.json`` files."""
    runs_dir = output_dir / "runs"
    lines: list[str] = [f"# {domain_id} MAP-stage Benchmark Runs", ""]
    header = (
        "| Run | Model | Latency | Status | G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 | G9 | Adapted | Notes |"
    )
    sep = "|" + "|".join(["---"] * 15) + "|"
    lines.extend([header, sep])
    # Gate keys: CORR-022 used g3_gdpr_cra; CORR-023 uses g3_regs_present.
    # Manifest reads whichever is present in meta.json so old runs render.
    g3_key_options = ("g3_regs_present", "g3_gdpr_cra")
    g5_key_options = ("g5_no_forbidden_connectives", "g5_no_furthermore")
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
                _gate_cell(_first_present(gates, g3_key_options)),
                _gate_cell(gates.get("g4_anchors")),
                _gate_cell(_first_present(gates, g5_key_options)),
                _gate_cell(gates.get("g6_no_generic_headings")),
                _gate_cell(gates.get("g7_parse")),
                _gate_cell(gates.get("g8_anchor_validation")),
                _gate_cell(gates.get("g9_v3_structure")),
                str(meta.get("adapted_chars", 0)),
                str(meta.get("notes", "")),
            ]
            lines.append("| " + " | ".join(row) + " |")
    (output_dir / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _first_present(gates: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in gates:
            return gates[k]
    return None


def _gate_cell(value: Any) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "-"


# ─── Main entry point ───────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--domain",
        default=DEFAULT_DOMAIN,
        help=f"AEGIS domain id (default: {DEFAULT_DOMAIN}).",
    )
    parser.add_argument("--model", required=True, help="Ollama model tag (e.g. gemma4:e2b).")
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            f"Directory for run artefacts (default: "
            f"logs/phase1/v2/<{DEFAULT_DOMAIN.lower().replace('-', '')}>/)."
        ),
    )
    args = parser.parse_args()

    _configure_logging()

    domain_id = args.domain.strip().upper()
    if not re.match(r"^D-\d{2}$", domain_id):
        print(f"ERROR: --domain must match D-XX (e.g. D-09); got {args.domain!r}.")
        return 2

    case_path = DEFAULT_CASE
    preproc_path = DEFAULT_PREPROC
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = REPO_ROOT / "logs" / "phase1" / "v2" / _domain_slug(domain_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print(f"MAP-stage benchmark — domain={domain_id} model={args.model}")
    print("=" * 78)
    print(f"Case              : {case_path}")
    print(f"Regulatory base   : {preproc_path}")
    print(f"Domain            : {domain_id}")
    print(f"Output dir        : {output_dir}")
    print(f"LLM max attempts  : {LLM_MAX_ATTEMPTS} (initial + 1 retry on parse failure)")
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
    applicable_regs = _canonical_regs(list(ctx.applicable_regs or []))
    print(
        f"Company={ctx.company_name!r} regs={applicable_regs} "
        f"sector={ctx.sector!r} scale={ctx.scale!r}"
    )
    print()

    # ─── Build inputs + render prompt ────────────────────────────
    from aegis_phase1.v2.domain.inputs import assemble_inputs
    from aegis_phase1.v2.domain.prompt import render_prompt

    inputs = assemble_inputs(state, domain_id)
    # inputs["applicable_regs"] is the per-domain filtered list; prefer it
    # over the company-wide list when non-empty (a domain may legitimately
    # apply to a subset of the company's regs).
    domain_regs_raw = inputs.get("applicable_regs") or []
    applicable_regs_for_gates = (
        _canonical_regs(domain_regs_raw) if domain_regs_raw else applicable_regs
    )
    min_blocks = max(2, len(applicable_regs_for_gates) + 1)

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
    print(f"  SOURCE ANCHORS     : {len(source_anchors)}")
    print(
        f"  APPLICABLE REGS    : {applicable_regs_for_gates} "
        f"→ G3 checks these, G9 min blocks/sub = {min_blocks}"
    )
    print()

    slug = _safe_slug(args.model)
    ts = _iso_now()
    run_dir = _run_dir_for(output_dir, slug, ts)

    # ─── Build invoker ───────────────────────────────────────────
    invoker = _build_invoker(args.model)
    if invoker is None:
        print("ABORT: Ollama is unreachable for the requested model; cannot invoke LLM.")
        meta = {
            "domain": domain_id,
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
            "applicable_regs": applicable_regs_for_gates,
            "gates": {k: False for k in (
                "g1_audit_theme", "g2_no_company", "g3_regs_present", "g4_anchors",
                "g5_no_forbidden_connectives", "g6_no_generic_headings", "g7_parse",
                "g8_anchor_validation", "g9_v3_structure",
            )},
            "gate_details": {"g9_v3_structure_detail": "no LLM call made"},
            "notes": "Ollama unreachable; meta only.",
        }
        _write_run_artefacts(run_dir, prompt, "", None, meta)
        _regenerate_manifest(output_dir, domain_id)
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
        attempt_prompt = render_prompt(inputs, feedback=feedback) if feedback else prompt

        logger.info(
            "LLM attempt %d (domain=%s, model=%s, feedback=%s)...",
            attempt, domain_id, args.model, "yes" if feedback else "no",
        )
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
        if parsed_v3.success or parsed_v2.success:
            break
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
        raw,
        parse_success,
        source_anchors,
        company_name,
        applicable_regs_for_gates,
        parsed_v3=parsed_v3,
    )

    adapted_chars = (
        sum(len(b.adapted) for s in parsed_v3.subdomains for b in s.blocks)
        if parsed_v3 is not None and parsed_v3.success
        else len(parsed_v2.legacy_adapted_objective) if parsed_v2 is not None else 0
    )

    meta = {
        "domain": domain_id,
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
        "applicable_regs": applicable_regs_for_gates,
        "min_blocks_per_sub": min_blocks,
        "gates": gates,
        "gate_details": gate_details,
        "notes": "feedback retry=" + ("yes" if final["feedback_appended"] else "no"),
    }
    parsed_text = _format_parsed(parsed_v3, parsed_v2) or None
    _write_run_artefacts(run_dir, prompt, raw, parsed_text, meta)
    _regenerate_manifest(output_dir, domain_id)
    logger.info("Saved run artefacts → %s", run_dir)
    print(f"  → saved run artefacts: {run_dir}")

    print()
    print("=" * 78)
    print(f"LLM CALL RESULTS (domain={domain_id}, model={args.model}, attempts={attempts})")
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
        print(f"  {gate_name:<32} {marker}")
    for dk, dv in gate_details.items():
        print(f"  {dk + ' detail':<32} {dv}")
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
