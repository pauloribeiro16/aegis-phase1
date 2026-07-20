"""Per-subdomain CSF mapping audit (CORR-027, Phase 3).

Walks all 38 SubDomain shards in preproc_out and produces a coverage
report at preproc_out/audit/csf_mapping_report.json. The report flags
subdomains whose CSF coverage is SPARSE (csf_hint has < 4 IDs OR any
SR has an empty nist_csf_mapping) or BROKEN (csf_hint contains an ID
not in the official 106).

Per-subdomain verdict:
  - OK       : hint >= 4 AND zero empty SR mappings AND no orphans
  - SPARSE   : hint < 4 OR empty SR mapping > 0 (but no orphans)
  - BROKEN   : any orphan in csf_hint

The "expected families" heuristic is derived from the
``## Cross-reference`` table in the frozen-list .md (advisory mapping).
When a subdomain's csf_hint is missing IDs from its expected families,
those IDs are listed in ``expected_families_missing`` to guide the
manual expansion step (CORR-028).

This tool is a **standalone scanner** — it reads the preproc_out and
the .md cross-reference, and writes a report. It does NOT mutate any
shard. Re-runs are idempotent.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
PREPROC_OUT = REPO_ROOT / "preproc_out"
SUBDOMAINS_DIR = PREPROC_OUT / "entities" / "subdomains"
CSF_JSON = PREPROC_OUT / "global" / "NIST_CSF_2.0_subcategories.json"
CSF_MD = (
    REPO_ROOT
    / "methodology-00"
    / "PREPROCESSING"
    / "NIST_CSF_2.0_subcategories.md"
)
AUDIT_OUT = PREPROC_OUT / "audit" / "csf_mapping_report.json"

# A subdomain with fewer than this many csf_hint IDs is flagged SPARSE.
SPARSE_HINT_THRESHOLD = 4


# ─── helpers ───────────────────────────────────────────────────────────


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_frozen_set() -> set[str]:
    """The official 106 CSF 2.0 active subcategory IDs.

    Source of truth: preproc_out/global/NIST_CSF_2.0_subcategories.json
    (xlsx-derived). If the JSON is missing, fall back to extracting IDs
    from the .md.
    """
    if CSF_JSON.is_file():
        data = json.loads(CSF_JSON.read_text())
        return {s["id"] for s in data["subcategories"]}
    if CSF_MD.is_file():
        text = CSF_MD.read_text()
        return set(re.findall(r"^\|\s*([A-Z]{2}\.[A-Z]{2}-\d+)\s*\|", text, re.MULTILINE))
    raise FileNotFoundError(
        f"Neither {CSF_JSON} nor {CSF_MD} present; cannot determine the frozen CSF 2.0 set"
    )


def _load_expected_families() -> dict[str, list[str]]:
    """Per-D-XX expected CSF families from the .md cross-reference table.

    Returns: ``{ "D-01": ["PR.DS", "PR.AA", "ID.AM", "GV.RM", "DE.CM"], ... }``
    """
    if not CSF_MD.is_file():
        return {}
    text = CSF_MD.read_text()
    # The cross-reference table is under `## Cross-reference: CSF 2.0 Functions × AEGIS 10×38 sub-domains`
    m = re.search(
        r"^## Cross-reference.*?\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    if not m:
        return {}
    body = m.group(1)
    out: dict[str, list[str]] = {}
    # Each row: | D-XX.Y (Description) | Likely CSF Functions |
    # The "Likely CSF Functions" cell may list multiple families
    # separated by commas. We extract the FUNC.CAT- prefix (e.g. "PR.DS").
    for row_m in re.finditer(
        r"^\|\s*(D-\d{2}(?:\.\d+)?)\s*\([^)]*\)\s*\|\s*([^|]+?)\s*\|",
        body,
        re.MULTILINE,
    ):
        sd = row_m.group(1)
        cell = row_m.group(2)
        # Extract FUNC.CAT- patterns (function 2 letters, dot, 2 letters, hyphen, digits)
        fams = sorted(
            {
                f"{m.group(1)}.{m.group(2)}"
                for m in re.finditer(r"([A-Z]{2})\.([A-Z]{2})-\d+", cell)
            }
        )
        out[sd] = fams
    return out


def _classify_subdomain(
    csf_hint: list[str],
    sr_csf_mappings: list[list[str]],
    frozen_set: set[str],
) -> tuple[str, list[str]]:
    """Return (verdict, list_of_orphan_ids) for one subdomain."""
    orphan = [c for c in csf_hint if c not in frozen_set]
    if orphan:
        return "BROKEN", orphan
    empty_sr = sum(1 for mapping in sr_csf_mappings if not mapping)
    if len(csf_hint) < SPARSE_HINT_THRESHOLD or empty_sr > 0:
        return "SPARSE", []
    return "OK", []


def _expected_families_missing(
    csf_hint: list[str],
    expected_families: list[str],
) -> list[str]:
    """Return the list of expected-family IDs not covered by csf_hint.

    For each expected family (e.g. "PR.DS"), if no csf_hint ID starts
    with "PR.DS-", add the most common ID for that family (a heuristic
    — typically the first ID, e.g. "PR.DS-01") to the missing list.
    """
    missing: list[str] = []
    for fam in expected_families:
        if not any(c.startswith(fam + "-") for c in csf_hint):
            # Heuristic: suggest the first ID in the family
            missing.append(f"{fam}-01")
    return missing


# ─── main audit ────────────────────────────────────────────────────────


def run_audit(
    preproc_out: Path = PREPROC_OUT,
    audit_path: Path = AUDIT_OUT,
) -> dict:
    """Run the audit; return the report dict (also written to audit_path)."""
    subdomains_dir = preproc_out / "entities" / "subdomains"
    csf_json = preproc_out / "global" / "NIST_CSF_2.0_subcategories.json"
    if csf_json.is_file():
        frozen_set = {s["id"] for s in json.loads(csf_json.read_text())["subcategories"]}
    elif CSF_MD.is_file():
        text = CSF_MD.read_text()
        frozen_set = set(re.findall(r"^\|\s*([A-Z]{2}\.[A-Z]{2}-\d+)\s*\|", text, re.MULTILINE))
    else:
        raise FileNotFoundError(
            f"Neither {csf_json} nor {CSF_MD} present; cannot determine the frozen CSF 2.0 set"
        )
    expected = _load_expected_families()
    if not subdomains_dir.is_dir():
        raise FileNotFoundError(f"{subdomains_dir} not present — run preproc build first")

    rows: list[dict] = []
    subdomains_with_empty_csf_hint: list[str] = []
    subdomains_with_empty_sr_csf_mapping: list[str] = []
    orphan_total = 0
    subdomains_with_orphan: list[str] = []
    verdict_counts: Counter[str] = Counter()

    for shard in sorted(subdomains_dir.glob("D-*.json")):
        sid = shard.stem
        sd = json.loads(shard.read_text())
        csf_hint = sd.get("csf_hint") or []
        srs = sd.get("security_requirements") or []
        sr_mappings = [
            (sr.get("nist_csf_mapping") or sr.get("csf") or []) for sr in srs
        ]
        empty_sr = sum(1 for m in sr_mappings if not m)
        participating = sd.get("participating_regulations") or []
        title = sd.get("title", "")

        verdict, orphans = _classify_subdomain(csf_hint, sr_mappings, frozen_set)
        verdict_counts[verdict] += 1

        if not csf_hint:
            subdomains_with_empty_csf_hint.append(sid)
        if empty_sr > 0:
            subdomains_with_empty_sr_csf_mapping.append(sid)
        if orphans:
            orphan_total += len(orphans)
            subdomains_with_orphan.append(sid)

        # Expected families for this subdomain
        expected_fams = expected.get(sid, [])
        expected_missing = _expected_families_missing(csf_hint, expected_fams)

        rows.append(
            {
                "subdomain_id": sid,
                "title": title,
                "participating_regulations": participating,
                "csf_hint_count": len(csf_hint),
                "csf_hint_ids": csf_hint,
                "sr_csf_mapping_total": len(sr_mappings),
                "sr_csf_mapping_empty": empty_sr,
                "orphan_csf_in_hint": orphans,
                "expected_families": expected_fams,
                "expected_families_missing": expected_missing,
                "audit_verdict": verdict,
            }
        )

    # Summary
    summary = {
        "subdomains_with_empty_csf_hint": sorted(subdomains_with_empty_csf_hint),
        "subdomains_with_empty_sr_csf_mapping": sorted(subdomains_with_empty_sr_csf_mapping),
        "orphan_csf_in_hint_total": orphan_total,
        "subdomains_with_orphan": sorted(subdomains_with_orphan),
        "verdict_counts": dict(verdict_counts),
    }

    # Build the report
    try:
        source_disp = str(csf_json.relative_to(REPO_ROOT))
    except ValueError:
        try:
            source_disp = str(CSF_MD.relative_to(REPO_ROOT))
        except ValueError:
            source_disp = str(csf_json)
    report = {
        "schema_version": "1.0",
        "built_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "frozen_list_source": source_disp,
        "frozen_list_id_count": len(frozen_set),
        "subdomain_count": len(rows),
        "summary": summary,
        "rows": rows,
    }

    # Write
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    audit_path.write_text(text, encoding="utf-8")
    sha = _sha256(text.encode("utf-8"))
    try:
        display_path = str(audit_path.relative_to(REPO_ROOT))
    except ValueError:
        display_path = str(audit_path)
    logger.info(
        "wrote %s (%d subdomains, %d OK, %d SPARSE, %d BROKEN, %d orphan hints)",
        display_path,
        len(rows),
        verdict_counts.get("OK", 0),
        verdict_counts.get("SPARSE", 0),
        verdict_counts.get("BROKEN", 0),
        orphan_total,
    )
    return report


# ─── CLI ───────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit CSF mapping coverage across all 38 subdomains"
    )
    parser.add_argument(
        "--preproc-out",
        type=Path,
        default=PREPROC_OUT,
        help=f"Path to preproc_out/ (default: {PREPROC_OUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=AUDIT_OUT,
        help=f"Path to write the report (default: {AUDIT_OUT})",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress per-row logging (summary only)"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    try:
        report = run_audit(preproc_out=args.preproc_out, audit_path=args.output)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    s = report["summary"]
    print(
        f"audit done: {report['subdomain_count']} subdomains, "
        f"{s['verdict_counts'].get('OK', 0)} OK, "
        f"{s['verdict_counts'].get('SPARSE', 0)} SPARSE, "
        f"{s['verdict_counts'].get('BROKEN', 0)} BROKEN, "
        f"{s['orphan_csf_in_hint_total']} orphan hint IDs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
