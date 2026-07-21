#!/usr/bin/env python3
"""Audit preproc_out/crossregulation/DomainAnalysis/*.json for schema
inconsistencies and not-well-populated fields.

Runs over all 38 per-subdomain JSON files and reports findings classified
by severity:

  - CRITICAL:    data corruption or invariant violation
  - HIGH:        obvious data quality issue (empty value where required,
                 wrong enum, length mismatch, leaked content from another
                 section, parseable but semantically wrong)
  - MEDIUM:      suspicious pattern that may be intentional (e.g. pair with
                 0 SR IDs and complementary classification)
  - LOW:         cosmetic / informational (extra whitespace, formatting)

Usage:
    python -m scripts.audit.audit_da_outputs          # default path
    python -m scripts.audit.audit_da_outputs --json   # machine-readable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# ── configuration ──────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DA_DIR = REPO_ROOT / "preproc_out" / "crossregulation" / "DomainAnalysis"
INDEX_FILE = DEFAULT_DA_DIR / "index.json"

VALID_REGS = {"GDPR", "NIS2", "CRA", "DORA", "AI_Act"}
VALID_CLASSIFICATIONS = {
    "Contradictory",
    "Complementary",
    "Equal",
    "Different perspective",
}
VALID_VERDICTS = {"Y", "N", "Conditional", ""}  # empty = not derived
EXPECTED_AXES = {"obligation", "scope"}

# Envelope fields every DA JSON must have (CORR-034 contract)
ENVELOPE_FIELDS = [
    "schema_version",
    "source",
    "doc_id",
    "sub_kind",
    "macro_domain",
    "sub_domain",
    "title",
    "status",
    "frontmatter",
    "title_h3",
    "participants_meta",
    "participants_table",
    "participant_count",
    "participants",
    "participants_absent",
    "participants_note",
    "pairs",
    "pair_count",
    "classification_distribution",
    "downstream_implication_top",
    "sr_cross_validation",
    "emergent_tensions",
    "sr_cross_references",
    "sr_cross_reference_count",
    "raw_md",
    "raw_md_kept_reason",
]

# Per-pair fields every pair object must have
PAIR_FIELDS = [
    "reg_a",
    "reg_b",
    "classification",
    "why",
    "why_qualifier",
    "why_note",
    "oj_quotes",
    "oj_quotes_verbatim",
    "comparison_sections",
    "scope_disjoint_test",
    "downstream_implication",
    "p0_notes",
    "sr_ids_per_pair",
    "table_block_raw",
    "block_text_raw",
]

# Per-comparison-section fields
CS_FIELDS = ["axis", "reg_a_value", "reg_b_value"]

# Per-oj-quote fields
OJ_FIELDS = ["regulation", "citation_raw", "sr_id", "article", "annex"]

# Per-oj-quote-verbatim fields
OJV_FIELDS = ["regulation", "header", "verbatim", "sr_ids", "articles", "annexes"]

# Per-scope-disjoint-test fields
SDT_FIELDS = ["verdict", "note"]


# ── finding helpers ────────────────────────────────────────────────────


class Finding:
    __slots__ = ("severity", "code", "path", "msg")

    def __init__(self, severity: str, code: str, path: str, msg: str):
        self.severity = severity
        self.code = code
        self.path = path
        self.msg = msg

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "msg": self.msg,
        }

    def __str__(self) -> str:
        return f"[{self.severity:8s}] {self.code:25s} {self.path}: {self.msg}"


def add(
    findings: list[Finding],
    severity: str,
    code: str,
    path: str,
    msg: str,
) -> None:
    findings.append(Finding(severity, code, path, msg))


# ── per-file audit ─────────────────────────────────────────────────────


def _rel_path(p: Path) -> str:
    """Return a path string relative to REPO_ROOT if possible, else absolute."""
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def audit_da_file(json_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    rel = _rel_path(json_path)

    # ── 1. JSON parse + envelope fields ────────────────────────────────
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add(findings, "CRITICAL", "JSON_PARSE_ERROR", rel, str(exc))
        return findings
    except OSError as exc:
        add(findings, "CRITICAL", "READ_ERROR", rel, str(exc))
        return findings

    for field in ENVELOPE_FIELDS:
        if field not in data:
            add(findings, "CRITICAL", "ENVELOPE_MISSING", rel, f"missing envelope field: {field}")

    if data.get("sub_kind") != "domain_analysis":
        add(
            findings,
            "HIGH",
            "WRONG_SUB_KIND",
            rel,
            f"sub_kind={data.get('sub_kind')!r} (expected 'domain_analysis')",
        )

    # ── 2. pair_count vs len(pairs) ────────────────────────────────────
    pairs = data.get("pairs", [])
    pair_count = data.get("pair_count")
    if pair_count != len(pairs):
        add(
            findings,
            "CRITICAL",
            "PAIR_COUNT_MISMATCH",
            rel,
            f"pair_count={pair_count} but len(pairs)={len(pairs)}",
        )

    # ── 3. participant_count vs len(participants_table) ────────────────
    pt = data.get("participants_table", [])
    pc = data.get("participant_count")
    if pc != len(pt):
        add(
            findings,
            "HIGH",
            "PARTICIPANT_COUNT_MISMATCH",
            rel,
            f"participant_count={pc} but len(participants_table)={len(pt)}",
        )

    # ── 4. sr_cross_reference_count vs list length ─────────────────────
    src = data.get("sr_cross_references", [])
    srcc = data.get("sr_cross_reference_count")
    if srcc != len(src):
        add(
            findings,
            "HIGH",
            "SR_CROSS_REF_COUNT_MISMATCH",
            rel,
            f"sr_cross_reference_count={srcc} but len(sr_cross_references)={len(src)}",
        )

    # ── 5. classification_distribution vs pairs ────────────────────────
    dist = data.get("classification_distribution", {})
    actual_dist: Counter[str] = Counter()
    for p in pairs:
        cls = p.get("classification") or "(empty)"
        actual_dist[cls] += 1
    if dict(actual_dist) != dist:
        add(
            findings,
            "HIGH",
            "CLASSIFICATION_DIST_MISMATCH",
            rel,
            f"declared={dict(dist)} actual={dict(actual_dist)}",
        )

    # ── 6. downstream_implication_top + sr_cross_validation leakage ────
    # These are H4 sections. If the section is the LAST one in the file,
    # the helper stops at EOF but may include the next H2 (e.g. "## D-06
    # Supply Chain"). Detect by checking for the pattern.
    for field in ("downstream_implication_top", "sr_cross_validation"):
        text = data.get(field, "")
        if not text:
            add(findings, "MEDIUM", f"{field.upper()}_EMPTY", rel, f"{field} is empty")
            continue
        # Leak: next H2 or H3 heading from a different sub-domain
        m_leak = re.search(r"\n---\n\n##\s+([^\n]+)$", text)
        if m_leak:
            add(
                findings,
                "HIGH",
                f"{field.upper()}_H2_LEAK",
                rel,
                f"{field} ends with leaked next-section H2: {m_leak.group(1)!r}",
            )
        # Standalone --- at end
        if text.rstrip().endswith("\n---") or text.rstrip().endswith("---"):
            add(
                findings,
                "HIGH",
                f"{field.upper()}_HR_LEAK",
                rel,
                f"{field} ends with horizontal-rule leak ('---')",
            )
        # Trailing whitespace / blank lines
        if text != text.rstrip() + ("\n" if text.endswith("\n") else ""):
            # Allow one trailing newline but no trailing whitespace before
            if text != text.rstrip():
                add(
                    findings,
                    "LOW",
                    f"{field.upper()}_TRAILING_WS",
                    rel,
                    f"{field} has trailing whitespace before final newline",
                )

    # ── 7. pair-level audits ───────────────────────────────────────────
    seen_pairs: set[tuple[str, str]] = set()
    for idx, p in enumerate(pairs):
        pair_rel = f"{rel}::pairs[{idx}]"

        # Missing fields
        for f in PAIR_FIELDS:
            if f not in p:
                add(
                    findings,
                    "CRITICAL",
                    "PAIR_FIELD_MISSING",
                    pair_rel,
                    f"missing field: {f}",
                )

        # reg_a / reg_b must be in VALID_REGS
        for k in ("reg_a", "reg_b"):
            v = p.get(k, "")
            if v not in VALID_REGS:
                add(
                    findings,
                    "HIGH",
                    "INVALID_REG",
                    pair_rel,
                    f"{k}={v!r} is not in {sorted(VALID_REGS)}",
                )

        # Pair must be unique (sorted, since order doesn't matter for
        # symmetric comparison)
        key = tuple(sorted([p.get("reg_a", ""), p.get("reg_b", "")]))
        if key in seen_pairs:
            add(
                findings,
                "HIGH",
                "DUP_PAIR",
                pair_rel,
                f"duplicate pair: {p.get('reg_a')!r} ↔ {p.get('reg_b')!r}",
            )
        seen_pairs.add(key)

        # Pair must NOT be self-pair
        if p.get("reg_a") == p.get("reg_b"):
            add(
                findings,
                "HIGH",
                "SELF_PAIR",
                pair_rel,
                f"self-pair {p.get('reg_a')!r} ↔ {p.get('reg_b')!r}",
            )

        # classification enum
        cls = p.get("classification", "")
        if cls not in VALID_CLASSIFICATIONS:
            add(
                findings,
                "HIGH",
                "INVALID_CLASSIFICATION",
                pair_rel,
                f"classification={cls!r} is not in {sorted(VALID_CLASSIFICATIONS)}",
            )

        # why / why_note
        if not p.get("why"):
            add(findings, "MEDIUM", "WHY_EMPTY", pair_rel, "why field is empty")
        if not p.get("why_note"):
            add(findings, "MEDIUM", "WHY_NOTE_EMPTY", pair_rel, "why_note is empty")

        # why vs why_note should differ (note is supposed to be the
        # qualifier-stripped version of why)
        if p.get("why") and p.get("why_note") and p["why"] == p["why_note"]:
            add(
                findings,
                "MEDIUM",
                "WHY_EQUALS_NOTE",
                pair_rel,
                "why and why_note are identical (expected note to be qualifier-stripped)",
            )

        # oj_quotes must have 2 entries (one per reg)
        oq = p.get("oj_quotes", [])
        if len(oq) != 2:
            add(
                findings,
                "HIGH",
                "OJ_QUOTES_COUNT",
                pair_rel,
                f"len(oj_quotes)={len(oq)} (expected 2 — one per reg)",
            )
        for j, q in enumerate(oq):
            qrel = f"{pair_rel}.oj_quotes[{j}]"
            for f in OJ_FIELDS:
                if f not in q:
                    add(
                        findings,
                        "CRITICAL",
                        "OJ_FIELD_MISSING",
                        qrel,
                        f"missing field: {f}",
                    )
            if q.get("regulation") not in (p.get("reg_a"), p.get("reg_b")):
                add(
                    findings,
                    "HIGH",
                    "OJ_REG_MISMATCH",
                    qrel,
                    f"regulation={q.get('regulation')!r} not in pair regs",
                )

        # oj_quotes_verbatim must have 2 entries
        oqv = p.get("oj_quotes_verbatim", [])
        if len(oqv) != 2:
            add(
                findings,
                "HIGH",
                "OJV_COUNT",
                pair_rel,
                f"len(oj_quotes_verbatim)={len(oqv)} (expected 2 — one per reg)",
            )
        for j, q in enumerate(oqv):
            qrel = f"{pair_rel}.oj_quotes_verbatim[{j}]"
            for f in OJV_FIELDS:
                if f not in q:
                    add(
                        findings,
                        "CRITICAL",
                        "OJV_FIELD_MISSING",
                        qrel,
                        f"missing field: {f}",
                    )
            if q.get("regulation") not in (p.get("reg_a"), p.get("reg_b")):
                add(
                    findings,
                    "HIGH",
                    "OJV_REG_MISMATCH",
                    qrel,
                    f"regulation={q.get('regulation')!r} not in pair regs",
                )
            if not q.get("verbatim"):
                add(
                    findings,
                    "MEDIUM",
                    "OJV_VERBATIM_EMPTY",
                    qrel,
                    "verbatim field is empty",
                )
            if not q.get("header"):
                add(findings, "MEDIUM", "OJV_HEADER_EMPTY", qrel, "header is empty")

        # comparison_sections must have 2 axes (obligation + scope)
        css = p.get("comparison_sections", [])
        axes = {cs.get("axis") for cs in css}
        if not EXPECTED_AXES.issubset(axes):
            add(
                findings,
                "HIGH",
                "MISSING_AXES",
                pair_rel,
                f"axes={axes} — expected to contain {sorted(EXPECTED_AXES)}",
            )
        for j, cs in enumerate(css):
            csrel = f"{pair_rel}.comparison_sections[{j}]"
            for f in CS_FIELDS:
                if f not in cs:
                    add(
                        findings,
                        "CRITICAL",
                        "CS_FIELD_MISSING",
                        csrel,
                        f"missing field: {f}",
                    )
            # The "scope" axis is structurally empty in DA (per CORR-034
            # contract — DA only has 2 axes and scope is informational).
            # We expect scope axis to have empty reg_a_value/reg_b_value,
            # but obligation axis MUST be non-empty.
            if cs.get("axis") == "obligation":
                if not cs.get("reg_a_value") or not cs.get("reg_b_value"):
                    add(
                        findings,
                        "HIGH",
                        "OBLIGATION_AXIS_EMPTY",
                        csrel,
                        f"obligation axis empty: reg_a_value={cs.get('reg_a_value')!r} reg_b_value={cs.get('reg_b_value')!r}",
                    )
            if cs.get("axis") == "scope":
                if cs.get("reg_a_value") or cs.get("reg_b_value"):
                    add(
                        findings,
                        "MEDIUM",
                        "SCOPE_AXIS_POPULATED",
                        csrel,
                        f"scope axis unexpectedly populated: reg_a_value={cs.get('reg_a_value')!r} reg_b_value={cs.get('reg_b_value')!r} (DA scope is intentionally empty per CORR-034)",
                    )

        # scope_disjoint_test
        sdt = p.get("scope_disjoint_test", {})
        if not isinstance(sdt, dict):
            add(
                findings,
                "CRITICAL",
                "SDT_NOT_DICT",
                pair_rel,
                f"scope_disjoint_test is {type(sdt).__name__}, expected dict",
            )
        else:
            for f in SDT_FIELDS:
                if f not in sdt:
                    add(
                        findings,
                        "CRITICAL",
                        "SDT_FIELD_MISSING",
                        pair_rel,
                        f"scope_disjoint_test missing field: {f}",
                    )
            verdict = sdt.get("verdict", "")
            if verdict not in VALID_VERDICTS:
                add(
                    findings,
                    "HIGH",
                    "INVALID_VERDICT",
                    pair_rel,
                    f"scope_disjoint_test.verdict={verdict!r} not in {sorted(VALID_VERDICTS)}",
                )

        # downstream_implication
        di = p.get("downstream_implication", "")
        if not di:
            add(
                findings,
                "MEDIUM",
                "DI_EMPTY",
                pair_rel,
                "downstream_implication is empty",
            )
        elif len(di) > 200:
            # CORR-034 contract: per-pair DI is [:200] of why_note
            add(
                findings,
                "LOW",
                "DI_TRUNCATION",
                pair_rel,
                f"downstream_implication len={len(di)} > 200 chars (expected [:200] slice of why_note)",
            )

        # sr_ids_per_pair
        sids = p.get("sr_ids_per_pair", [])
        if not isinstance(sids, list):
            add(
                findings,
                "CRITICAL",
                "SR_IDS_NOT_LIST",
                pair_rel,
                f"sr_ids_per_pair is {type(sids).__name__}",
            )
        else:
            for sid in sids:
                if not re.fullmatch(r"SR-[A-Z_]+-\d{3}", sid):
                    add(
                        findings,
                        "HIGH",
                        "INVALID_SR_ID",
                        pair_rel,
                        f"invalid SR-ID format: {sid!r}",
                    )
            # An empty sr_ids_per_pair is allowed but suspicious for
            # non-Different-perspective classifications
            if not sids and p.get("classification") in (
                "Contradictory",
                "Complementary",
                "Equal",
            ):
                add(
                    findings,
                    "MEDIUM",
                    "SR_IDS_EMPTY_FOR_KNOWN_CLASS",
                    pair_rel,
                    f"sr_ids_per_pair is empty but classification={p.get('classification')!r}",
                )

        # table_block_raw and block_text_raw must be non-empty
        if not p.get("table_block_raw"):
            add(findings, "MEDIUM", "TABLE_RAW_EMPTY", pair_rel, "table_block_raw is empty")
        if not p.get("block_text_raw"):
            add(
                findings,
                "HIGH",
                "BLOCK_TEXT_EMPTY",
                pair_rel,
                "block_text_raw is empty (zero-loss invariant violation)",
            )

    # ── 8. emergent_tensions must be a list ────────────────────────────
    et = data.get("emergent_tensions", [])
    if not isinstance(et, list):
        add(
            findings,
            "CRITICAL",
            "ET_NOT_LIST",
            rel,
            f"emergent_tensions is {type(et).__name__}",
        )
    # If 5+ participants, an emergent marker is expected (per AEGIS
    # convention for 3+ regulation overlap). But not strictly required,
    # so MEDIUM severity only.
    if len(data.get("participants", [])) >= 3 and not et:
        add(
            findings,
            "LOW",
            "ET_MISSING_FOR_3PLUS",
            rel,
            f"3+ participants but no emergent_tensions marker",
        )

    # ── 9. top-level required fields non-empty when pairs > 0 ─────────
    if pairs:
        if not data.get("downstream_implication_top"):
            add(
                findings,
                "HIGH",
                "DI_TOP_MISSING",
                rel,
                "pairs exist but downstream_implication_top is empty",
            )
        if not data.get("sr_cross_validation"):
            add(
                findings,
                "HIGH",
                "SR_CV_MISSING",
                rel,
                "pairs exist but sr_cross_validation is empty",
            )

    # ── 10. macro_domain/sub_domain consistency ───────────────────────
    sub = data.get("sub_domain", "")
    macro = data.get("macro_domain", "")
    if sub and macro:
        # sub_domain should start with the macro's D-XX prefix
        m = re.match(r"(D-\d+)\.\d+", sub)
        if m:
            prefix = m.group(1)
            if prefix not in macro:
                add(
                    findings,
                    "MEDIUM",
                    "MACRO_SUB_MISMATCH",
                    rel,
                    f"sub_domain={sub!r} prefix {prefix!r} not in macro_domain={macro!r}",
                )

    return findings


# ── index.json audit ───────────────────────────────────────────────────


def audit_index(idx_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not idx_path.exists():
        add(
            findings,
            "HIGH",
            "INDEX_MISSING",
            _rel_path(idx_path),
            "index.json does not exist",
        )
        return findings
    try:
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add(findings, "CRITICAL", "INDEX_PARSE", str(idx_path), str(exc))
        return findings

    if "domains" in idx and isinstance(idx["domains"], list):
        declared_files = {Path(d["path"]).name for d in idx["domains"] if "path" in d}
    else:
        # This index.json is a taxonomy wrapper (relationship_taxonomy
        # + workflow_steps), not a directory listing. The D-*.json
        # files are tracked by the parent pipeline (build.sh), not by
        # this index. Skip the cross-check.
        return findings

    actual_files = {p.name for p in idx_path.parent.glob("**/D-*.json")}
    missing_from_index = actual_files - declared_files
    extra_in_index = declared_files - actual_files
    for m in sorted(missing_from_index):
        add(
            findings,
            "MEDIUM",
            "INDEX_MISSING_ENTRY",
            _rel_path(idx_path),
            f"file {m!r} exists on disk but not in index.json",
        )
    for m in sorted(extra_in_index):
        add(
            findings,
            "LOW",
            "INDEX_EXTRA_ENTRY",
            _rel_path(idx_path),
            f"index.json lists {m!r} but file does not exist on disk",
        )
    return findings


# ── main ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of human report",
    )
    parser.add_argument(
        "--only",
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        help="only show findings of this severity or above",
    )
    parser.add_argument(
        "--da-dir",
        type=Path,
        default=DEFAULT_DA_DIR,
        help="path to DomainAnalysis preproc dir (default: preproc_out/crossregulation/DomainAnalysis)",
    )
    args = parser.parse_args()

    da_dir: Path = args.da_dir
    if not da_dir.is_dir():
        print(f"ERROR: {da_dir} is not a directory", file=sys.stderr)
        return 2

    json_files = sorted(da_dir.glob("**/D-*.json"))
    if not json_files:
        print(f"ERROR: no D-*.json files found in {da_dir}", file=sys.stderr)
        return 2

    all_findings: list[Finding] = []
    for jf in json_files:
        all_findings.extend(audit_da_file(jf))
    all_findings.extend(audit_index(da_dir / "index.json"))

    # Filter by severity
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    if args.only:
        threshold = severity_order[args.only]
        all_findings = [f for f in all_findings if severity_order[f.severity] <= threshold]

    # Sort
    all_findings.sort(
        key=lambda f: (severity_order[f.severity], f.path, f.code)
    )

    if args.json:
        print(
            json.dumps(
                {
                    "files_scanned": len(json_files),
                    "finding_count": len(all_findings),
                    "by_severity": dict(
                        Counter(f.severity for f in all_findings)
                    ),
                    "findings": [f.to_dict() for f in all_findings],
                },
                indent=2,
            )
        )
    else:
        # Human report
        by_sev: Counter[str] = Counter(f.severity for f in all_findings)
        print(f"\nScanned {len(json_files)} DomainAnalysis JSONs (+ index.json)\n")
        print("Findings by severity:")
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            n = by_sev.get(sev, 0)
            print(f"  {sev:8s} {n}")
        print()
        if not all_findings:
            print("No findings. ✓")
            return 0
        for f in all_findings:
            print(str(f))
        return 1


if __name__ == "__main__":
    sys.exit(main())
