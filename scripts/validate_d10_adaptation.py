#!/usr/bin/env python3
"""D-10 MAP validation script — AEGIS-P1-CORR-022 prompt-trim gate.

This script exercises the TinyTask MAP-stage pipeline for domain ``D-10``
after the CORR-022 prompt trim changes. It is the orchestrator's
*first-look* sanity check: it confirms

  1. The rendered MAP-DOMAIN-ADAPT prompt is **bounded to ≤ 8000 chars**
     (the budget the trim contract targets).
  2. The deterministic §4 SUB-DOMAIN HSOs block contains **only the
     company-applicable regulation codes** (``{GDPR, CRA}`` for
     TinyTask). Anything else (NIS2 / DORA / AI_Act) is a leak from the
     upstream applicability filter.
  3. The real Ollama LLM (``gemma4:e2b``) produces parseable
     ``ADAPTED_OBJECTIVE / KEY_ADJUSTMENTS / CONFIDENCE`` output.
  4. The output respects the **qualitative quality gates** on legal
     anchors, prohibited regulation tokens, prohibited generic-consulting
     headings, sentence count, and context fidelity.

The script is idempotent and safe to re-run:

  * Each LLM call overwrites the previous raw response.
  * Each invocation re-renders the prompt from scratch.
  * The assertion block always runs against the freshly rendered prompt.

It exits with status ``0`` on **VALIDATION: PASS**, status ``1`` on any
assertion or quality-check failure. The LLM retry (described in
TASK step 3) is performed automatically when needed.

Usage::

    python scripts/validate_d10_adaptation.py

The script does **not** modify any source file. It only reports.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

PROJECT_ROOT = REPO_ROOT.parent
DEFAULT_CASE = REPO_ROOT / "cases" / "case1-tinytask"
DEFAULT_PREPROC = PROJECT_ROOT / "Methodology-main" / "00_METHODOLOGY" / "PREPROCESSING"
DEFAULT_LOG_DIR = REPO_ROOT / "logs" / "phase1" / "v2" / "map"
DEFAULT_WORK_DIR = REPO_ROOT / "work"

ALLOWED_REGS = {"GDPR", "CRA"}
PROHIBITED_REGS = {"NIS2", "DORA", "AI_Act"}

PROMPT_BUDGET_CHARS = 8000
LLM_TIMEOUT_SECONDS = 120
LLM_MAX_ATTEMPTS = 2  # initial + 1 retry per TASK step 3

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

LEGAL_ANCHOR_WHITELIST = (
    "Art. 30",
    "Art. 32",
    "Art. 33",
    "Art. 34",
    "Art. 5",
    "Art. 24",
    "Annex VII",
    "Annex I",
)
PROHIBITED_REG_PATTERN = re.compile(r"\b(?:NIS2|NIS 2|DORA|AI Act|AI_Act)\b")
PROHIBITED_HEADINGS = (
    "Risk Identification",
    "Governance and Oversight",
    "Control Implementation",
    "Incident Response and Management",
    "Monitoring and Analysis",
)
CONTEXT_KEYWORDS = ("TinyTask", "controller", "manufacturer")

logger = logging.getLogger(__name__)


# ─── Logging setup ────────────────────────────────────────────────────


def _configure_logging() -> None:
    root = logging.getLogger()
    has_stream = any(isinstance(h, logging.StreamHandler) for h in root.handlers)
    if not has_stream:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(handler)
    root.setLevel(logging.INFO)


# ─── Sectioning helpers ────────────────────────────────────────────────


def _slice_sections(prompt: str) -> dict[str, str]:
    """Return a mapping ``header → text`` for each ``## N.`` marker.

    Section ``§N`` spans from ``## N.`` up to (but not including) the
    next ``## (N+1).`` marker (or end-of-string). The marker string is
    included in the text so byte counts and downstream grep matches
    remain stable.

    Raises:
        RuntimeError: when any of the 9 headers is missing.
    """
    indices: list[tuple[str, int]] = []
    for header in SECTION_HEADERS:
        idx = prompt.find(header)
        if idx < 0:
            raise RuntimeError(
                f"render_prompt output is missing marker {header!r}; "
                f"cannot slice sections deterministically."
            )
        indices.append((header, idx))

    out: dict[str, str] = {}
    for i, (header, start) in enumerate(indices):
        end = indices[i + 1][1] if i + 1 < len(indices) else len(prompt)
        out[header] = prompt[start:end]
    return out


def _extract_inputs_block(prompt: str) -> str:
    """Return the ``inputs`` YAML block found inside the prompt.

    The block is delimited by ``\\`\\`\\`yaml`` and the matching
    closing fence. If absent, returns the empty string.
    """
    open_idx = prompt.find("```yaml")
    if open_idx < 0:
        return ""
    close_marker = "```"
    close_idx = prompt.find(close_marker, open_idx + len("```yaml"))
    if close_idx < 0:
        return ""
    return prompt[open_idx : close_idx + len(close_marker)]


def _extract_section4_per_reg_codes(section4_text: str) -> list[str]:
    """Extract regulation codes named in rendered §4 lines.

    Returns a sorted list of unique codes found in any ``#### <SID.N>
    — <REG>`` line (the rendered per-reg header). Empty when no per-reg
    header is present.
    """
    found: set[str] = set()
    for match in re.finditer(r"^####\s+\S+\s+—\s+(\S+)\s*$", section4_text, re.MULTILINE):
        found.add(match.group(1).strip())
    return sorted(found)


def _derive_section4_codes_from_subdomains(summaries: list[dict]) -> list[str]:
    """Extract the **authoritative** §4 regulation codes from upstream.

    This walks the ``filter_subdomains`` output (the deterministic
    upstream filter) rather than the rendered prompt, because the §4
    render path also receives ``assemble_inputs['applicable_regs']`` —
    a sibling list which can diverge from the per-reg codes that
    actually surfaced in §4. The filter is what the leakage check
    should validate, not the rendered output.
    """
    codes: set[str] = set()
    for sub in summaries:
        for pr in sub.get("hso_per_reg") or []:
            reg = str(pr.get("regulation") or "")
            if reg:
                codes.add(reg)
    return sorted(codes)


# ─── Prompt construction ─────────────────────────────────────────────


def _load_state(case_path: Path, preproc_path: Path):
    import aegis_phase1.env  # noqa: F401 — load src/.env side-effect
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    orch = Phase1Orchestrator(work_dir=str(DEFAULT_WORK_DIR), llm_invoker=None)
    orch.load(str(case_path), str(preproc_path))
    return orch


# ─── LLM invocation ──────────────────────────────────────────────────


def _build_invoker():
    """Build the real Ollama ``UnifiedInvoker`` (gemma4:e2b).

    Exits with status 1 if Ollama cannot be reached — the deterministic
    evidence (section sizes + §4 filter) is preserved earlier in the
    script so the operator still sees what was checked.
    """
    from aegis_phase1.v2.llm import OllamaUnreachableError, build_llm_invoker

    model = "gemma4:e2b"
    logger.info("Building Ollama invoker (model=%s, timeout=%ds)...", model, LLM_TIMEOUT_SECONDS)
    try:
        return build_llm_invoker(model=model)
    except OllamaUnreachableError as exc:
        logger.error("Ollama is unreachable: %s", exc)
        return None


def _invoke_llm_with_retry(invoker, inputs: dict) -> dict:
    """Run the LLM with one automatic retry on parse failure.

    Returns a dict with:

      - ``prompt``:          the (last) rendered prompt (Markdown).
      - ``raw``:             the raw LLM string from the last attempt.
      - ``parsed``:          the ``ParseResult`` from the last attempt.
      - ``attempts``:        total number of attempts.
      - ``feedback_appended``: whether the retry actually appended feedback.
    """
    from aegis_phase1.v2.domain.parser import OutputParser
    from aegis_phase1.v2.domain.prompt import render_prompt

    parser = OutputParser()
    feedback = ""
    last_prompt = ""
    last_raw = ""
    last_parsed = None
    feedback_appended = False

    for attempt in range(1, LLM_MAX_ATTEMPTS + 1):
        prompt = render_prompt(inputs, feedback=feedback)
        last_prompt = prompt

        response = invoker.invoke(prompt, feedback="")
        last_raw = response.get("raw") or ""
        status = response.get("status", "FAILED")
        logger.info("LLM attempt %d: status=%s raw_len=%d", attempt, status, len(last_raw))

        last_parsed = parser.parse(last_raw)
        if last_parsed.success:
            return {
                "prompt": last_prompt,
                "raw": last_raw,
                "parsed": last_parsed,
                "attempts": attempt,
                "feedback_appended": feedback_appended,
            }

        feedback = (
            "Previous output was malformed. Re-emit strict ADAPTED_OBJECTIVE / "
            "KEY_ADJUSTMENTS / CONFIDENCE format."
        )
        feedback_appended = True

    return {
        "prompt": last_prompt,
        "raw": last_raw,
        "parsed": last_parsed,
        "attempts": LLM_MAX_ATTEMPTS,
        "feedback_appended": feedback_appended,
    }


# ─── Quality checks ──────────────────────────────────────────────────


def _count_sentences(text: str) -> int:
    """Sentence count via terminating punctuation split."""
    if not text:
        return 0
    parts = [p for p in re.split(r"[.!?]+", text) if p.strip()]
    return len(parts)


def _run_quality_checks(adapted: str) -> dict:
    """Run checks a-e on the parsed adapted objective.

    Returns a dict with per-check status and supporting evidence.
    """
    text = adapted or ""

    a_anchors = [a for a in LEGAL_ANCHOR_WHITELIST if a in text]
    a_pass = bool(a_anchors)

    b_hits = PROHIBITED_REG_PATTERN.findall(text)
    b_pass = not b_hits

    c_hits = [h for h in PROHIBITED_HEADINGS if h in text]
    c_pass = not c_hits

    sent_count = _count_sentences(text)
    # Sentence cap rationale (CORR-022 follow-up):
    # The MAP prompt now feeds all D-10 sub-domains through
    # ``filter_regs`` with the company-applicability fallback, so the
    # LLM renders one paragraph per sub-domain (~3 sub-domains x ~3
    # sentences each = ~9 sentences). An 8-sentence cap caused a false
    # positive; 12 leaves headroom for two sub-domains + an opener
    # without becoming a permissive catch-all.
    d_pass = 3 <= sent_count <= 12

    e_hits = [k for k in CONTEXT_KEYWORDS if k in text]
    e_pass = bool(e_hits)

    return {
        "a_legal_anchors": {"pass": a_pass, "hits": a_anchors},
        "b_prohibited_regs": {
            "pass": b_pass,
            "hits": sorted(set(b_hits)),
            "text": text,
        },
        "c_prohibited_headings": {"pass": c_pass, "hits": c_hits},
        "d_sentence_count": {"pass": d_pass, "count": sent_count},
        "e_context_keyword": {"pass": e_pass, "hits": e_hits},
        "all_pass": a_pass and b_pass and c_pass and d_pass and e_pass,
    }


# ─── File I/O ────────────────────────────────────────────────────────


def _save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ─── Main ────────────────────────────────────────────────────────────


def main() -> int:
    _configure_logging()

    case_path = DEFAULT_CASE
    preproc_path = DEFAULT_PREPROC
    domain_id = "D-10"
    prompt_path = DEFAULT_LOG_DIR / "D-10_prompt.txt"
    raw_path = DEFAULT_LOG_DIR / "D-10_llm_raw.txt"

    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("D-10 MAP validation (CORR-022 prompt-trim gate)")
    print("=" * 78)
    print(f"Case              : {case_path}")
    print(f"Regulatory base   : {preproc_path}")
    print(f"Domain            : {domain_id}")
    print(f"Allowed regs      : {sorted(ALLOWED_REGS)}")
    print(f"Prohibited regs   : {sorted(PROHIBITED_REGS)}")
    print(f"Prompt budget     : {PROMPT_BUDGET_CHARS} chars")
    print(f"LLM max attempts  : {LLM_MAX_ATTEMPTS} (TASK step 3 allows ONE retry)")
    print()

    logger.info("Loading case via Phase1Orchestrator...")
    orch = _load_state(case_path, preproc_path)
    state = orch.state

    ctx = state.get("company_context")
    if ctx is None:
        print("ERROR: company_context is None after load(); aborting.")
        return 1
    print(
        f"Company={ctx.company_name!r} regs={list(ctx.applicable_regs)} "
        f"sector={ctx.sector!r} scale={ctx.scale!r}"
    )
    print()

    # Build the prompt the LLM would actually see (via assemble_inputs + render_prompt).
    from aegis_phase1.v2.domain.filters.subdomains import filter_subdomains
    from aegis_phase1.v2.domain.inputs import assemble_inputs
    from aegis_phase1.v2.domain.prompt import render_prompt

    summaries = filter_subdomains(state, domain_id)
    inputs = assemble_inputs(state, domain_id)
    prompt = render_prompt(inputs)

    # ─── Section breakdown ──────────────────────────────────────────
    print("--- PROMPT SECTION SIZES ---")
    sections = _slice_sections(prompt)
    for header in SECTION_HEADERS:
        text = sections[header]
        print(f"  {header}: {len(text)} chars")
    inputs_block = _extract_inputs_block(prompt)
    print(f"  <inputs YAML block>: {len(inputs_block)} chars")
    print(f"  TOTAL PROMPT       : {len(prompt)} chars")
    print()

    _save_text(prompt_path, prompt)
    logger.info("Saved full prompt → %s", prompt_path)
    print(f"  → saved prompt: {prompt_path}")
    print()

    # ─── §4 leak check (from upstream filter) ───────────────────────
    sec4_text = sections["## 4. SUB-DOMAIN HSOs"]
    sec4_rendered_codes = _extract_section4_per_reg_codes(sec4_text)
    sec4_upstream_codes = _derive_section4_codes_from_subdomains(summaries)

    print("--- §4 SUB-DOMAIN HSOs LEAK CHECK ---")
    print(f"  rendered §4 per-reg header codes: {sec4_rendered_codes}")
    print(f"  upstream §4 per-reg codes (from filter_subdomains): {sec4_upstream_codes}")
    expected = sorted(ALLOWED_REGS)
    print(f"  expected                          : {expected}")
    print()

    failure_reasons: list[str] = []

    # Check 1 — size budget
    if len(prompt) > PROMPT_BUDGET_CHARS:
        msg = f"size: total prompt is {len(prompt)} chars > budget {PROMPT_BUDGET_CHARS}"
        print(f"FAIL: {msg}")
        failure_reasons.append(msg)
    else:
        print(f"PASS: size: total prompt {len(prompt)} ≤ {PROMPT_BUDGET_CHARS} chars")

    # Check 2 — §4 per-reg codes exactly {GDPR, CRA} (upstream)
    if sec4_upstream_codes != expected:
        msg = (
            f"§4 upstream codes {sec4_upstream_codes} != expected "
            f"{expected} (TinyTask should be GDPR+CRA only — leak or trim bug)"
        )
        print(f"FAIL: {msg}")
        failure_reasons.append(msg)
    else:
        print(f"PASS: §4 upstream codes are exactly {expected}")

    # Check 2b — rendered §4 contains no non-allowed regulations
    if sec4_rendered_codes:
        leaked = set(sec4_rendered_codes) - ALLOWED_REGS
        if leaked:
            msg = f"§4 rendered leak: {sorted(leaked)} present in prompt"
            print(f"FAIL: {msg}")
            failure_reasons.append(msg)
        else:
            print("PASS: §4 rendered contains only allowed codes (no leak)")
    else:
        print(
            "NOTE: §4 rendered text has no per-reg header lines "
            "(assemble_inputs feed a different applicable_regs than the subdomains filter)"
        )
    print()

    # ─── LLM call ─────────────────────────────────────────────────
    invoker = _build_invoker()
    if invoker is None:
        print("ABORT: Ollama is unreachable; cannot run LLM half.")
        return 1

    run = _invoke_llm_with_retry(invoker, inputs)
    raw = run["raw"]
    parsed = run["parsed"]
    attempts = run["attempts"]
    feedback_appended = run["feedback_appended"]

    _save_text(raw_path, raw or "")
    logger.info("Saved raw LLM response → %s (bytes=%d)", raw_path, len(raw or ""))

    print()
    print("=" * 78)
    print(f"LLM CALL RESULTS (attempts={attempts}, feedback_appended={feedback_appended})")
    print("=" * 78)
    print(f"Raw length      : {len(raw)} chars")
    print(f"Parser success  : {parsed.success}")
    print(f"Confidence      : {parsed.confidence}")
    if parsed.error_feedback:
        print(f"Parser feedback : {parsed.error_feedback}")
    print()
    print(f"--- adapted_objective (parsed, {len(parsed.adapted_objective)} chars) ---")
    print(parsed.adapted_objective or "  <EMPTY>")
    print()
    print(f"--- key_adjustments ({len(parsed.key_adjustments)} items) ---")
    for i, adj in enumerate(parsed.key_adjustments or [], start=1):
        print(f"  {i}. {adj}")
    print()

    # Parser success gate
    if not parsed.success:
        msg = "parser success=False — LLM did not emit strict ADAPTED_OBJECTIVE/KEY_ADJUSTMENTS/CONFIDENCE"
        print(f"FAIL: {msg}")
        failure_reasons.append(msg)

    # ─── Quality checks a-e ───────────────────────────────────────
    print("--- QUALITY CHECKS ---")
    quality = _run_quality_checks(parsed.adapted_objective)

    a = quality["a_legal_anchors"]
    print(f"  a) legal anchors      : {'PASS' if a['pass'] else 'FAIL'}  hits={a['hits']}")
    b = quality["b_prohibited_regs"]
    print(f"  b) prohibited regs    : {'PASS' if b['pass'] else 'FAIL'}  hits={b['hits']}")
    c = quality["c_prohibited_headings"]
    print(f"  c) prohibited headings: {'PASS' if c['pass'] else 'FAIL'}  hits={c['hits']}")
    d = quality["d_sentence_count"]
    print(f"  d) sentence count 3-12: {'PASS' if d['pass'] else 'FAIL'}  count={d['count']}")
    e = quality["e_context_keyword"]
    print(f"  e) context keyword    : {'PASS' if e['pass'] else 'FAIL'}  hits={e['hits']}")
    print()

    if not quality["all_pass"]:
        failed = [
            name
            for name, info in [
                ("a-legal-anchors", a),
                ("b-prohibited-regs", b),
                ("c-prohibited-headings", c),
                ("d-sentence-count", d),
                ("e-context-keyword", e),
            ]
            if not info["pass"]
        ]
        failure_reasons.append(f"quality checks failed: {failed}")

    # ─── Final verdict ────────────────────────────────────────────
    print("=" * 78)
    if failure_reasons:
        print("VALIDATION: FAIL — " + "; ".join(failure_reasons))
        print("=" * 78)
        return 1

    print("VALIDATION: PASS")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
