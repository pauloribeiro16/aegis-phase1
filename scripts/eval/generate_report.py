#!/usr/bin/env python3
"""CORR-057 + CORR-105: generate evaluation report from llm-calls.jsonl.

Produces 2 outputs:
  --output-md   : Markdown report with 4 sections (schema/citation/activation/parity)
  --output-json : Structured JSON for programmatic analysis

Dimensions:
  1. Schema/format compliance: % of calls per spec that pass parser/validator
  2. Citation accuracy: legal_refs/layer0_refs cross-checked against preproc
  3. Substantive content: activation count per spec
  4. Structural parity: presence of critical elements in Doc 04/05/06/07

Operational metrics: latency, tokens, retry count, status distribution.

CORR-105 extensions:
  * --run-dir mode: walk Doc 05 raw markdown and per-spec sections to
    reconstruct a jsonl-like list (no separate jsonl required).
  * ParserGate: invoke MARKDOWN_PARSERS[spec].parse() directly on the
    raw to get a per-spec structural pass/fail independent of any
    recorded status.
  * OllamaJsonlIngest: accept the new Ollama-call jsonl shape used by
    Phase 1B / MAP / REDUCE logs (per-call spec at `metadata.spec_id`,
    raw text under `response.text`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


# ────────────────────────────────────────────────────────────────────
# CORR-105 helpers (kept in this file to keep the eval surface single)
# ────────────────────────────────────────────────────────────────────

# Per-spec section headers in Doc 05 / raw markdown (CORR-074 contract).
SPEC_SECTION_HEADERS: dict[str, list[str]] = {
    "P1B-LLM-01-INTERPRETATION": ["P1B-LLM-01-INTERPRETATION", "P1B-LLM-01"],
    "P1B-LLM-02-RATIONALE":       ["P1B-LLM-02-RATIONALE", "P1B-LLM-02"],
    "P1C-LLM-01-OVERLAP-CLASSIFICATION": ["P1C-LLM-01-OVERLAP-CLASSIFICATION", "P1C-LLM-01"],
    "P1C-LLM-02-COMPOUND-EVENT":         ["P1C-LLM-02-COMPOUND-EVENT", "P1C-LLM-02"],
    "P1C-LLM-03-STRATEGIC-SYNTHESIS":    ["P1C-LLM-03-STRATEGIC-SYNTHESIS", "P1C-LLM-03"],
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--jsonl", required=False, type=Path,
                   help="Path to llm-calls.jsonl (legacy CORR-057 or Ollama shape).")
    p.add_argument("--run-dir", required=False, type=Path,
                   help="Alternative to --jsonl: a Deucalion run output dir; "
                        "walks Doc 05 and reconstructs spec sections.")
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--preproc", required=True, type=Path, help="path to preproc_out")
    p.add_argument("--output-md", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--use-parser-gate", action="store_true",
                   help="Call MARKDOWN_PARSERS[spec].parse() on every reconstructed "
                        "raw to get an independent L1 verdict.")
    return p.parse_args()


def load_jsonl(path: Path) -> list[dict]:
    entries = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries


def load_canonical_refs(preproc: Path) -> set[str]:
    """Load all canonical legal references from preproc clauses."""
    refs: set[str] = set()
    clauses_root = preproc / "entities" / "clauses" / "_root"
    if not clauses_root.exists():
        return refs
    for reg_dir in clauses_root.iterdir():
        if not reg_dir.is_dir():
            continue
        for clause_file in reg_dir.glob("*.json"):
            try:
                data = json.loads(clause_file.read_text(encoding="utf-8"))
                # section_ref is the canonical article ref
                sr = data.get("section_ref")
                if sr:
                    refs.add(sr)
                # also collect berry_anchors (article refs in the clause)
                for anchor in data.get("berry_anchors", []) or []:
                    if anchor:
                        refs.add(anchor)
            except Exception:
                pass
    return refs


def extract_refs_from_output(output) -> list[str]:
    """Extract legal_refs + layer0_refs from LLM output (dict or markdown)."""
    refs = []
    if isinstance(output, dict):
        # Walk common shapes
        for path in [
            ("interpretations",), ("derogations",),
            ("sub_domain_activations",), ("implications",),
            ("positive_events",), ("negative_events",),
        ]:
            node = output
            for k in path:
                node = node.get(k, []) if isinstance(node, dict) else []
                if not isinstance(node, list):
                    node = []
                    break
            if isinstance(node, list):
                for item in node:
                    if isinstance(item, dict):
                        refs.extend(item.get("legal_refs", []) or [])
                        refs.extend(item.get("layer0_refs", []) or [])
    elif isinstance(output, str):
        # Markdown: extract via regex
        for m in re.finditer(r"^-\s*(?:legal_refs|layer0_refs)\s*:\s*(.+)$", output, re.MULTILINE):
            for r in m.group(1).split(","):
                r = r.strip().lstrip("-").strip()
                if r:
                    refs.append(r)
    return refs


# ────────────────────────────────────────────────────────────────────
# CORR-105: OllamaJsonlIngest + RunDirIngest + ParserGate
# ────────────────────────────────────────────────────────────────────


def normalise_ollama_entry(e: dict) -> dict | None:
    """Normalise a new-format Ollama jsonl entry to the legacy shape
    that the existing per_spec aggregator expects.

    New shape (per call): { spec_id, latency_ms, usage.{prompt_tokens,
    completion_tokens}, response.text, status, retries? }
    Legacy shape:        { spec_id|prompt_spec_id, latency_ms|total_latency_ms,
                            usage.{input_tokens|prompt_tokens,
                            output_tokens|completion_tokens}, output|parsed_output,
                            status, all_attempts }

    Returns None if the entry can't be mapped (then it's skipped, not
    crashed on).
    """
    spec = (
        e.get("spec_id")
        or e.get("prompt_spec_id")
        or (e.get("metadata") or {}).get("spec_id")
        or (e.get("metadata") or {}).get("prompt_spec_id")
    )
    if not spec:
        return None
    out = dict(e)
    out["spec_id"] = spec
    if "latency_ms" not in out and "total_latency_ms" in e:
        out["latency_ms"] = e["total_latency_ms"]
    usage = e.get("usage") or {}
    if "input_tokens" not in usage and "prompt_tokens" in usage:
        usage["input_tokens"] = usage["prompt_tokens"]
    if "output_tokens" not in usage and "completion_tokens" in usage:
        usage["output_tokens"] = usage["completion_tokens"]
    out["usage"] = usage
    if "output" not in out:
        resp = e.get("response") or {}
        if isinstance(resp, dict):
            out["output"] = resp.get("text", "")
        elif isinstance(resp, str):
            out["output"] = resp
    return out


def walk_run_dir(run_dir: Path) -> list[dict]:
    """Reconstruct an entries list from a Deucalion run output dir.

    Sources, in order:
      1. <run_dir>/llm-calls.jsonl (if present — new Ollama shape)
      2. <run_dir>/05_Regulatory_Applicability.md (split per spec section)

    Returns a list of {spec_id, output, status, latency_ms, usage} dicts.
    """
    entries: list[dict] = []

    jsonl = run_dir / "llm-calls.jsonl"
    if jsonl.exists():
        for e in load_jsonl(jsonl):
            n = normalise_ollama_entry(e)
            if n is not None:
                entries.append(n)
        if entries:
            return entries

    doc05 = run_dir / "05_Regulatory_Applicability.md"
    if doc05.exists():
        text = doc05.read_text(encoding="utf-8", errors="ignore")
        # Split on the per-spec section headers.
        # `### P1B-LLM-01-INTERPRETATION` etc.
        pattern = re.compile(
            r"^###\s+(" + "|".join(
                re.escape(h)
                for hdrs in SPEC_SECTION_HEADERS.values()
                for h in hdrs
            ) + r")\s*$",
            re.MULTILINE,
        )
        matches = list(pattern.finditer(text))
        for i, m in enumerate(matches):
            header = m.group(1)
            spec_id = next(
                (s for s, hdrs in SPEC_SECTION_HEADERS.items() if header in hdrs),
                "UNKNOWN",
            )
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            entries.append({
                "spec_id": spec_id,
                "output": body,
                "status": "OK",
                "source": f"{doc05.name}:{m.start()}",
            })
    return entries


def parser_gate(entries: list[dict]) -> dict[str, dict]:
    """Invoke MARKDOWN_PARSERS[spec].parse() on each entry's output and
    record PASS/FAIL with error message.

    Returns {spec_id: {"pass": int, "fail": int, "errors": [...]}}.
    Soft-imports the parsers so this script remains runnable without
    the full aegis_phase1 package installed (just stdlib + the parser
    module).
    """
    summary: dict[str, dict] = defaultdict(
        lambda: {"pass": 0, "fail": 0, "errors": []}
    )
    try:
        # Lazy import so we don't make aegis_phase1 a hard dependency
        # for the legacy CORR-057 path.
        from aegis_phase1.prompts_v2.markdown_parser import MARKDOWN_PARSERS
    except Exception as exc:  # pragma: no cover
        for e in entries:
            spec = e.get("spec_id", "UNKNOWN")
            summary[spec]["errors"].append(f"parser import failed: {exc}")
        return summary

    for e in entries:
        spec = e.get("spec_id", "UNKNOWN")
        raw = e.get("output") or ""
        parser_cls = MARKDOWN_PARSERS.get(spec)
        if parser_cls is None:
            summary[spec]["errors"].append(f"no parser registered for {spec}")
            continue
        try:
            parser = parser_cls()
            parsed, err = parser.parse(raw)
        except Exception as exc:
            summary[spec]["fail"] += 1
            summary[spec]["errors"].append(f"{spec}: {type(exc).__name__}: {exc}")
            continue
        if parsed is None:
            summary[spec]["fail"] += 1
            if err:
                summary[spec]["errors"].append(f"{spec}: {err[:200]}")
        else:
            summary[spec]["pass"] += 1
    return summary


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)

    entries = load_jsonl(args.jsonl) if args.jsonl else []
    canonical_refs = load_canonical_refs(args.preproc)

    # CORR-105: --run-dir mode (alternative to --jsonl).
    if args.run_dir:
        entries = walk_run_dir(args.run_dir)
    if not entries:
        print(
            "[report] ERROR: no entries — provide --jsonl or --run-dir",
            file=sys.stderr,
        )
        sys.exit(2)

    # Per-spec aggregation
    per_spec: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "by_status": Counter(),
        "latencies_ms": [], "input_tokens": [], "output_tokens": [], "retries": [],
        "all_refs_cited": [], "invented_refs": [],
        "activations_yes": 0, "activations_total": 0,
    })

    for e in entries:
        # CORR-058: tolerant spec extraction. Legacy jsonl uses top-level
        # `prompt_spec_id` (898/1844 entries); new jsonl uses `spec_id`.
        spec = (
            e.get("spec_id")
            or e.get("prompt_spec_id")
            or (e.get("metadata") or {}).get("prompt_spec_id")
            or "UNKNOWN"
        )
        status = e.get("status", "UNKNOWN")
        spec_data = per_spec[spec]
        spec_data["total"] += 1
        spec_data["by_status"][status] += 1

        # Latency
        lat = e.get("latency_ms") or e.get("total_latency_ms")
        if lat:
            spec_data["latencies_ms"].append(lat)

        # Tokens
        usage = e.get("usage") or {}
        it = usage.get("input_tokens") or usage.get("prompt_tokens")
        ot = usage.get("output_tokens") or usage.get("completion_tokens")
        if it and it > 0: spec_data["input_tokens"].append(it)
        if ot and ot > 0: spec_data["output_tokens"].append(ot)

        # Retries
        attempts = e.get("all_attempts") or []
        if attempts:
            spec_data["retries"].append(len(attempts))

        # Citation accuracy
        output = e.get("output") or e.get("parsed_output") or {}
        cited = extract_refs_from_output(output)
        spec_data["all_refs_cited"].extend(cited)
        for ref in cited:
            # Match against canonical set (loose match: substring)
            if not any(ref in c or c in ref for c in canonical_refs):
                spec_data["invented_refs"].append(ref)

        # Activation count (dict shape OR markdown shape — CORR-105)
        def _count_yes(o):
            if isinstance(o, dict):
                for k in ("interpretations", "derogations", "implications",
                          "positive_events", "negative_events", "sub_domain_activations"):
                    items = o.get(k, []) if isinstance(o, dict) else []
                    if isinstance(items, list):
                        for it in items:
                            if isinstance(it, dict):
                                spec_data["activations_total"] += 1
                                if (it.get("applicable", "").upper() == "YES" or
                                    it.get("activation_verdict", "").upper() == "ACTIVATED"):
                                    spec_data["activations_yes"] += 1
                return
            if isinstance(o, str):
                # CORR-105: count `applicable: YES/NO/N/A` and
                # `activation_verdict: ACTIVATED/NOT_ACTIVATED` field lines
                # anywhere in the markdown body. The `applicable` may be
                # preceded by `- <id>:` or just `-`, so we don't anchor
                # the line start strictly.
                for m in re.finditer(r"applicable\s*:\s*(YES|NO|N/A)\b",
                                     o, re.IGNORECASE):
                    spec_data["activations_total"] += 1
                    if m.group(1).upper() == "YES":
                        spec_data["activations_yes"] += 1
                for m in re.finditer(r"activation_verdict\s*:\s*(ACTIVATED|NOT_ACTIVATED)\b",
                                     o, re.IGNORECASE):
                    spec_data["activations_total"] += 1
                    if m.group(1).upper() == "ACTIVATED":
                        spec_data["activations_yes"] += 1
        _count_yes(output)

    # Compute aggregates
    spec_summary = {}
    for spec, d in per_spec.items():
        spec_summary[spec] = {
            "total_calls": d["total"],
            "status_distribution": dict(d["by_status"]),
            "schema_compliance_pct": round(
                100 * d["by_status"].get("OK", 0) / max(1, d["total"]), 1
            ),
            "latency_ms_mean": round(sum(d["latencies_ms"]) / max(1, len(d["latencies_ms"])), 0) if d["latencies_ms"] else None,
            "latency_ms_max": max(d["latencies_ms"]) if d["latencies_ms"] else None,
            "input_tokens_mean": round(sum(d["input_tokens"]) / max(1, len(d["input_tokens"])), 0) if d["input_tokens"] else None,
            "output_tokens_mean": round(sum(d["output_tokens"]) / max(1, len(d["output_tokens"])), 0) if d["output_tokens"] else None,
            "retries_mean": round(sum(d["retries"]) / max(1, len(d["retries"])), 2) if d["retries"] else None,
            "total_refs_cited": len(d["all_refs_cited"]),
            "invented_refs_count": len(d["invented_refs"]),
            "invented_refs_pct": round(100 * len(d["invented_refs"]) / max(1, len(d["all_refs_cited"])), 1),
            "top_invented_refs": Counter(d["invented_refs"]).most_common(10),
            "activations_yes": d["activations_yes"],
            "activations_total": d["activations_total"],
        }

    # Structural parity check (read output/phase1/*.md if present)
    parity = {}
    out_dir = Path("output/phase1")
    if out_dir.exists():
        # Doc 05: applicable_regs
        doc05 = out_dir / "05_Regulatory_Applicability.md"
        if doc05.exists():
            txt = doc05.read_text(encoding="utf-8", errors="ignore")
            parity["doc05_applicable_regs"] = {
                "has_gdpr": "GDPR" in txt,
                "has_cra": "CRA" in txt,
                "pass": "GDPR" in txt and "CRA" in txt,
            }
        # Doc 07: row count
        doc07 = out_dir / "07_Structured_Compliance_Matrix.md"
        if doc07.exists():
            txt = doc07.read_text(encoding="utf-8", errors="ignore")
            n_rows = len(re.findall(r"^\|\s*D-\d+\.\d+", txt, re.MULTILINE))
            parity["doc07_subdomain_rows"] = {"count": n_rows, "expected": 38, "pass": n_rows >= 30}
        # Doc 04: company facts
        doc04 = out_dir / "04_Company_Context_Assessment.md"
        if doc04.exists():
            txt = doc04.read_text(encoding="utf-8", errors="ignore")
            parity["doc04_company_facts"] = {
                "has_employees_8": "8" in txt and "employees" in txt.lower(),
                "has_portugal": "Portugal" in txt,
                "has_technology": "Technology" in txt,
            }

    # Build full data structure
    data = {
        "contract": "CORR-057 + CORR-105",
        "model": "gemma4:e2b",
        "case": "case1-tinytask",
        "total_entries": len(entries),
        "canonical_refs_loaded": len(canonical_refs),
        "per_spec": spec_summary,
        "structural_parity": parity,
    }

    # CORR-105: independent parser gate (L1)
    if args.use_parser_gate:
        gate = parser_gate(entries)
        # serialise (no Counter)
        gate_serialised = {
            s: {"pass": v["pass"], "fail": v["fail"], "errors": v["errors"][:5]}
            for s, v in gate.items()
        }
        data["parser_gate"] = gate_serialised

    # Write JSON
    args.output_json.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # Build Markdown
    lines = [
        "# CORR-057 — Baseline e2b eval report",
        "",
        f"- **Model:** gemma4:e2b",
        f"- **Case:** case1-tinytask",
        f"- **Total LLM entries in jsonl:** {len(entries)}",
        f"- **Canonical refs loaded from preproc:** {len(canonical_refs)}",
        "",
        "## 1. Schema/format compliance",
        "",
        "| Spec | Total calls | OK | SCHEMA_ERROR | FORMAT_ERROR | FAILED | Compliance % |",
        "|------|-------------|----|--------------|--------------|--------|--------------|",
    ]
    for spec, s in sorted(spec_summary.items()):
        sd = s["status_distribution"]
        lines.append(
            f"| {spec} | {s['total_calls']} | {sd.get('OK', 0)} | "
            f"{sd.get('SCHEMA_ERROR', 0)} | {sd.get('FORMAT_ERROR', 0)} | "
            f"{sd.get('FAILED_AFTER_RETRIES', 0)} | {s['schema_compliance_pct']}% |"
        )
    lines.append("")

    lines += [
        "## 2. Citation accuracy (strict cross-check vs preproc)",
        "",
        "| Spec | Total refs cited | Invented | Invented % | Top 5 invented |",
        "|------|-----------------|----------|-----------|----------------|",
    ]
    for spec, s in sorted(spec_summary.items()):
        top5 = "; ".join(f"{r}({n}x)" for r, n in s["top_invented_refs"][:5]) or "—"
        lines.append(
            f"| {spec} | {s['total_refs_cited']} | {s['invented_refs_count']} | "
            f"{s['invented_refs_pct']}% | {top5} |"
        )
    lines.append("")

    lines += [
        "## 3. Substantive content (activation count)",
        "",
        "| Spec | Activations YES | Activations total | Rate |",
        "|------|----------------|-------------------|------|",
    ]
    for spec, s in sorted(spec_summary.items()):
        rate = round(100 * s["activations_yes"] / max(1, s["activations_total"]), 1) if s["activations_total"] else 0
        lines.append(f"| {spec} | {s['activations_yes']} | {s['activations_total']} | {rate}% |")
    lines.append("")

    lines += [
        "## 4. Structural parity (Doc 04/05/07)",
        "",
    ]
    for elem, info in parity.items():
        lines.append(f"- **{elem}**: `{info}`")
    lines.append("")

    lines += [
        "## 5. Operational metrics (LLM)",
        "",
        "| Spec | Latency mean (ms) | Latency max | Input tok mean | Output tok mean | Retries mean |",
        "|------|-------------------|-------------|----------------|-----------------|--------------|",
    ]
    for spec, s in sorted(spec_summary.items()):
        lines.append(
            f"| {spec} | {s['latency_ms_mean'] or '—'} | {s['latency_ms_max'] or '—'} | "
            f"{s['input_tokens_mean'] or '—'} | {s['output_tokens_mean'] or '—'} | "
            f"{s['retries_mean'] or '—'} |"
        )
    lines.append("")

    # CORR-105: parser gate section (only emitted when --use-parser-gate)
    if args.use_parser_gate and data.get("parser_gate"):
        lines += [
            "## 6. Parser gate (CORR-105 — independent L1 verdict)",
            "",
            "| Spec | Pass | Fail | First 3 errors |",
            "|------|------|------|----------------|",
        ]
        for spec, g in sorted(data["parser_gate"].items()):
            errs = g.get("errors") or []
            shown = "; ".join(errs[:3]) if errs else "—"
            lines.append(
                f"| {spec} | {g['pass']} | {g['fail']} | {shown} |"
            )
        lines.append("")

    args.output_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"[report] Markdown: {args.output_md}")
    print(f"[report] JSON: {args.output_json}")
    print(f"[report] Specs analyzed: {len(spec_summary)}")
    print(f"[report] Total entries: {len(entries)}")


if __name__ == "__main__":
    main()
