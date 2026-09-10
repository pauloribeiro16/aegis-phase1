#!/usr/bin/env python3
"""Regenerate methodology-00/.../NIST_CSF_2.0_subcategories.md from preproc_out JSON.

Used to repair drift between the deprecated .md (98 subcats, july 2025) and
the xlsx-derived JSON (106 active subcats, NIST CSWP 29). Run when
`.hooks/ci-csf-frozen-list.sh` reports parity drift:

    .venv/bin/python scripts/regenerate_csf_frozen_list.py

The script writes to BOTH the deprecated location and its `_global/` mirror
so the pre-push hook (which reads `methodology-00/PREPROCESSING/...`) passes
on the next commit.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "preproc_out" / "global" / "NIST_CSF_2.0_subcategories.json"
MD_TARGETS = [
    REPO_ROOT / "methodology-00" / "PREPROCESSING" / "NIST_CSF_2.0_subcategories.md",
    REPO_ROOT / "methodology-00" / "PREPROCESSING_by_domain" / "_global" / "NIST_CSF_2.0_subcategories.md",
]
FUNCTION_NAMES = {
    "GV": "Govern",
    "ID": "Identify",
    "PR": "Protect",
    "DE": "Detect",
    "RS": "Respond",
    "RC": "Recover",
}
ACTIVE_STATUS = "ACTIVE"
SOURCE = "NIST Cybersecurity Framework 2.0 (NIST CSWP 29, February 26, 2024)"


def build_md() -> str:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    active = [s for s in data["subcategories"] if not s.get("withdrawn", False)]
    active.sort(key=lambda s: (s["function"], s["category_id"], s["number"]))

    by_func: dict[str, list[dict]] = defaultdict(list)
    for s in active:
        by_func[s["function"]].append(s)

    # Per-function counts
    func_stats = {
        f: {
            "cats": len({s["category_id"] for s in by_func[f]}),
            "subs": len(by_func[f]),
        }
        for f in FUNCTION_NAMES
    }
    total_cats = sum(v["cats"] for v in func_stats.values())
    total_subs = sum(v["subs"] for v in func_stats.values())

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    lines: list[str] = []
    lines.append("---")
    lines.append("document_id: AEGIS-PREPROC-CSF-REF")
    lines.append("title: NIST CSF 2.0 Subcategory Reference (Frozen List)")
    lines.append("phase: Pre-processing (Regulatory Baseline)")
    lines.append("version: 2.0")
    lines.append(f"created: {today}")
    lines.append(f"updated: {today}")
    lines.append("author: scripts/regenerate_csf_frozen_list.py")
    lines.append(f"status: {ACTIVE_STATUS}")
    lines.append(f"source: {SOURCE}")
    lines.append("chain_version: v2.1")
    lines.append("supersedes: methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md (v1.0, 98 subcats)")
    lines.append("purpose: Authoritative list of NIST CSF 2.0 Subcategories. Sub-agents MUST pick from this list — no invention of IDs allowed.")
    lines.append("related_documents:")
    lines.append("  - ./TEMPLATE_subagent_brief.md")
    lines.append("  - ../../REFERENCE/chain_v2_1.md")
    lines.append("---")
    lines.append("")
    lines.append("# NIST CSF 2.0 Subcategory Reference (Frozen List)")
    lines.append("")
    lines.append(
        f"> **Authority:** This list is the complete set of NIST CSF 2.0 Subcategories"
        f" as published in {SOURCE}. Sub-agents MUST NOT invent new IDs. If a"
        " SecurityRule does not map cleanly to any subcategory below, use"
        " `UNMAPPED_CSF` per the brief."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Function structure")
    lines.append("")
    lines.append(
        f"NIST CSF 2.0 has **{len(FUNCTION_NAMES)} Functions**, **{total_cats}"
        f" Categories**, and **{total_subs} Subcategories**."
    )
    lines.append("")
    lines.append("| Function ID | Function Name | Cat. Count | Subcat. Count |")
    lines.append("|---|---|---:|---:|")
    for fid, fname in FUNCTION_NAMES.items():
        lines.append(
            f"| {fid} | {fname} | {func_stats[fid]['cats']} |"
            f" {func_stats[fid]['subs']} |"
        )
    lines.append(f"| **Total** | — | **{total_cats}** | **{total_subs}** |")
    lines.append("")
    lines.append("---")
    lines.append("")

    for fid, fname in FUNCTION_NAMES.items():
        subs = by_func[fid]
        if not subs:
            continue
        cat_counts = defaultdict(int)
        for s in subs:
            cat_counts[s["category_id"]] += 1
        cat_list = sorted(cat_counts)
        lines.append(
            f"## {fid} — {fname}"
            f" ({len(cat_list)} categories, {len(subs)} subcategories)"
        )
        lines.append("")
        # Group by category, preserving the input order
        for cat_id in cat_list:
            cat_subs = [s for s in subs if s["category_id"] == cat_id]
            cat_name = cat_subs[0]["category_name"]
            lines.append(f"### {cat_id} — {cat_name}")
            lines.append("")
            lines.append("| ID | Subcategory |")
            lines.append("|---|---|")
            for s in cat_subs:
                title = s["title"].replace("|", "\\|")
                lines.append(f"| {s['id']} | {title} |")
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Special tokens")
    lines.append("")
    lines.append("| Token | Use |")
    lines.append("|---|---|")
    lines.append("| `UNMAPPED_CSF` | Use when no subcategory below fits a SecurityRule's intent |")
    lines.append("| `CSF_REVIEW_NEEDED` | Use when mapping is uncertain; triggers human review |")
    lines.append("")
    lines.append("**End of reference.**")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    md = build_md()
    for target in MD_TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(md, encoding="utf-8")
        # Confirm parity in place
        ids = [line.split("|")[1].strip() for line in md.splitlines() if line.startswith("| ") and line.split("|")[1].strip().count(".") == 1]
        active_count = sum(1 for ln in ids if ln.startswith(tuple(FUNCTION_NAMES)) and "-" in ln)
        print(f"  wrote {target.relative_to(REPO_ROOT)} ({active_count} IDs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
