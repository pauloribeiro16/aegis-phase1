#!/usr/bin/env python3
"""Regenerate ``docs/PROVENANCE.md`` from the PROVENANCE registry.

CORR-112: the provenance audit doc must mirror exactly what the renderers
emit, including its own per-section provenance. Editing the MD by hand
would create drift — the registry is the source of truth, this
generator is a thin renderer.

The MD has three sections:

  1. **Provenance matrix** — per doc, every section's origin.
  2. **Spec legend** — what each ``[LLM: SPEC_ID]`` tag means.
  3. **Audit checklist** — manual review prompts for a reviewer.

Usage::

    PYTHONPATH=src python scripts/eval/generate_provenance_map.py
    # writes docs/PROVENANCE.md (default)
    PYTHONPATH=src python scripts/eval/generate_provenance_map.py --check
    # exits 0 if docs/PROVENANCE.md matches what the registry says,
    # non-zero otherwise. Used in CI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from aegis_phase1.v2.output.provenance import (  # noqa: E402
    DOC_TITLES,
    PROVENANCE,
    SPEC_P1B_01,
    SPEC_P1B_02,
    SPEC_P1C_01,
    SPEC_P1C_02,
    SPEC_P1C_03,
    docs_covered,
)

DOC_OUT = REPO / "docs" / "PROVENANCE.md"

SPEC_DESCRIPTIONS: dict[str, str] = {
    SPEC_P1B_01: "Per-regulation interpretation of the regime (when does each "
                  "regulation activate / derogate?).",
    SPEC_P1B_02: "Per-regulation rationale + implications + gaps. Synthesises "
                  "the catalog facts into prose for the reviewer.",
    SPEC_P1C_01: "Per-domain overlap classification between applicable "
                  "regulations (SAME / COMPLEMENTARY / CONTRADICTORY / SCOPE_DISJOINT).",
    SPEC_P1C_02: "Compound events that cross regulations (e.g. an incident that "
                  "triggers GDPR + NIS2 simultaneously).",
    SPEC_P1C_03: "Global strategic synthesis that ties the per-domain signals "
                  "into the company's overall posture.",
}

ORIGIN_DESCRIPTIONS: dict[str, str] = {
    "deterministic": "Rendered by a deterministic pipeline stage — facts "
                     "from the catalog (company_facts, type 2/3 nuances, "
                     "scope overlaps, ...). No LLM call in this section.",
    "hybrid":        "Composed from deterministic facts PLUS an LLM-derived "
                     "narrative. (Currently only doc_04b §3 — maturity "
                     "per capability.)",
}


def render() -> str:
    """Render the full Markdown file content."""
    out: list[str] = []
    out.append("# Docs Provenance (CORR-112)\n")
    out.append("")
    out.append(
        "> **Auto-generated** from "
        "`src/aegis_phase1/v2/output/provenance.py::PROVENANCE`. "
        "Do not edit by hand — re-run `python "
        "scripts/eval/generate_provenance_map.py` after changing the "
        "registry.\n"
    )
    out.append("")
    out.append(
        "This file is the audit trail for **which section of which "
        "document comes from where**. Each produced Markdown has its "
        "LLM-derived sections tagged inline (`[LLM: P1B-LLM-01-INTERPRETATION]`, "
        "`[hybrid: deterministic facts + LLM narrative]`); the matrix "
        "below is the canonical reference.\n"
    )
    out.append("")

    # --- Section 1: matrix ---
    out.append("## 1. Provenance matrix\n")
    out.append("")
    out.append(
        "| Doc | Section title | Origin | Render tag |\n"
        "|---|---|---|---|\n"
    )
    for doc_id in docs_covered():
        out.append(f"| **{doc_id}** ({DOC_TITLES.get(doc_id, doc_id)}) | | | |\n")
        # Iterate in registry-insertion order; aggregate by doc.
        for (d, _h), entry in PROVENANCE.items():
            if d != doc_id:
                continue
            origin = entry.origin
            tag = _render_tag(origin)
            heading_disp = entry.heading.strip().lstrip("# ")
            out.append(
                f"|  | `{heading_disp}` | `{origin}` | {tag} |\n"
            )
        out.append("")

    # --- Section 2: origin legend ---
    out.append("## 2. Origin legend\n")
    out.append("")
    out.append("| Origin | Meaning |\n|---|---|\n")
    out.append(
        "| `deterministic` | "
        f"{ORIGIN_DESCRIPTIONS['deterministic']} |\n"
    )
    out.append(
        "| `hybrid` | "
        f"{ORIGIN_DESCRIPTIONS['hybrid']} |\n"
    )
    for spec_id, desc in SPEC_DESCRIPTIONS.items():
        out.append(f"| `{spec_id}` | {desc} |\n")
    out.append("")

    # --- Section 3: audit checklist ---
    out.append("## 3. Audit checklist\n")
    out.append("")
    out.append(
        "A reviewer auditing `output/case*/<Doc>.md` can use this "
        "checklist:\n"
    )
    out.append("")
    out.append(
        "1. **Each LLM-derived section has an inline tag.** "
        "Deterministic sections do NOT need a tag (they're self-evident), "
        "but LLM sections must have `[LLM: <spec-id>]` immediately "
        "after the heading.\n"
    )
    out.append(
        "2. **Each tag matches the matrix above.** If you see "
        "`[LLM: P1B-LLM-02-RATIONALE]` in a section that's marked "
        "`deterministic` in the matrix, that's a bug — file an issue.\n"
    )
    out.append(
        "3. **Spec output is captured.** LLM sections are sourced from "
        "`state[\"per_spec_markdown\"][spec_id]` (via "
        "`render_per_spec_markdown_appendix` for the Source LLM "
        "Responses block) AND/OR parsed into typed dicts "
        "(`domain_results`, `aggregated_data`).\n"
    )
    out.append(
        "4. **No unknown origins.** Use "
        "`python -c \"from aegis_phase1.v2.output.provenance "
        "import is_known_origin; print(is_known_origin('<origin>'))\"` "
        "to check. The F3 gate refuses to ship docs with `unknown` "
        "origin on non-trivial sections.\n"
    )
    out.append("")
    return "".join(out)


def _render_tag(origin: str) -> str:
    if origin == "deterministic":
        return "_(no tag)_\n"
    if origin == "hybrid":
        return "`[hybrid]`"
    return f"`[LLM: {origin}]`"


def write_or_check(path: Path, *, check_only: bool) -> int:
    rendered = render()
    if check_only:
        if not path.exists():
            print(f"ERROR: {path} does not exist", file=sys.stderr)
            return 1
        existing = path.read_text(encoding="utf-8")
        if existing != rendered:
            print(
                f"ERROR: {path} is out of sync with PROVENANCE. "
                f"Re-run scripts/eval/generate_provenance_map.py.",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {path} matches the registry.")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {path} ({len(rendered.splitlines())} lines).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the MD doesn't match the registry.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DOC_OUT,
        help=f"Output path (default: {DOC_OUT.relative_to(REPO)}).",
    )
    args = parser.parse_args()
    return write_or_check(args.out, check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
