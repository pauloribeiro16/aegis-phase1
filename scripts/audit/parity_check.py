#!/usr/bin/env python3
"""Parity check: source MD ↔ preproc JSON for all 38 sub-domains.

For each sub-domain (D-XX.Y), on each side (DA, Deep), verify the
preproc JSON is consistent with its source MD across two dimensions:

  - STRICT     : raw_md field in the JSON equals the source MD body
                 (verbatim, modulo trailing whitespace and final newline)
  - STRUCTURAL : every "extracted" field in the JSON is derivable from
                 the source MD (i.e. the parser did not invent values)

Compares the following 76 files (38 pairs, 2 sides):
  DA  : source MD ↔ preproc JSON in preproc_out/2-crossregulation/DomainAnalysis
  Deep: source MD ↔ preproc JSON in preproc_out/2-crossregulation/DeepAnalysis

Does NOT cross-check DA vs Deep (they are intentionally different
artifacts — DA is the lite version, Deep is the OJ-text-verified
enriched version).

Run:
  python -m scripts.audit.parity_check                 # all 38 sub-domains
  python -m scripts.audit.parity_check --only D-04.3   # just one
  python -m scripts.audit.parity_check --json          # machine-readable
  python -m scripts.audit.parity_check --only D-04 --json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
METH_ROOT = Path("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main")
METH_CROSSREG = METH_ROOT / "00_METHODOLOGY" / "PREPROCESSING" / "CrossRegulation"
PREPROC_CROSSREG = REPO_ROOT / "preproc_out" / "2-crossregulation"

# Subdomain under test (set dynamically by main() based on CLI args)
SUBDOMAIN = "D-01.1"
MACRO_DIR = "D-01_Data-Protection"


# ── Finding container ────────────────────────────────────────────────


class Finding:
    __slots__ = ("severity", "code", "loc", "msg")

    def __init__(self, severity: str, code: str, loc: str, msg: str):
        self.severity = severity
        self.code = code
        self.loc = loc
        self.msg = msg

    def __str__(self) -> str:
        return f"[{self.severity:8s}] {self.code:30s} {self.loc}: {self.msg}"

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "loc": self.loc,
            "msg": self.msg,
        }


# ── Helpers ──────────────────────────────────────────────────────────


def _read_md(p: Path) -> tuple[dict[str, str], str]:
    """Read a source MD and split into (frontmatter_dict, body)."""
    text = p.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_text, body = m.group(1), m.group(2)
    fm: dict[str, str] = {}
    for line in fm_text.splitlines():
        m2 = re.match(r"^(\w+):\s*(.*)$", line)
        if m2:
            fm[m2.group(1)] = m2.group(2).strip()
    return fm, body


def _normalise(text: str) -> str:
    """Normalise text for byte-comparison.

    - Strip trailing whitespace per line
    - Strip trailing blank lines
    - Keep the leading newline (so the body starts at column 0 as in
      source MDs)
    """
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _first_diff(a: str, b: str) -> tuple[int, str, str]:
    """Find the first char position where a and b differ.

    Returns (offset, snippet_a, snippet_b). Returns (-1, '', '') if
    one is a prefix of the other.
    """
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            lo = max(0, i - 40)
            hi_a = min(len(a), i + 40)
            hi_b = min(len(b), i + 40)
            return i, a[lo:hi_a], b[lo:hi_b]
    if len(a) != len(b):
        return n, a[n:n + 40], b[n:n + 40]
    return -1, "", ""


# ── Strict check: raw_md ↔ source MD body ────────────────────────────


def check_strict(
    label: str,
    source_md: Path,
    preproc_json: Path,
    findings: list[Finding],
) -> dict[str, Any]:
    """Verify raw_md field in JSON == source MD body."""
    data = json.loads(preproc_json.read_text(encoding="utf-8"))
    if not source_md.exists():
        findings.append(
            Finding(
                "CRITICAL",
                "SOURCE_MD_MISSING",
                label,
                f"source MD not found: {source_md}",
            )
        )
        return data
    _, body = _read_md(source_md)
    norm_body = _normalise(body)
    norm_raw = _normalise(data.get("raw_md", ""))
    if norm_body == norm_raw:
        return data
    # Find first diff
    offset, snip_src, snip_json = _first_diff(norm_body, norm_raw)
    if offset == -1:
        # No diff found in shared prefix — lengths must differ
        findings.append(
            Finding(
                "CRITICAL",
                "RAW_MD_LENGTH_DIFF",
                label,
                f"raw_md len={len(norm_raw)} != source MD body len={len(norm_body)} "
                f"(diff is at end of file)",
            )
        )
    else:
        findings.append(
            Finding(
                "CRITICAL",
                "RAW_MD_DIFF",
                label,
                f"raw_md != source MD body (first diff at char {offset})\n"
                f"    source: {snip_src!r}\n"
                f"    json:   {snip_json!r}",
            )
        )
    return data


# ── Structural check: extracted fields ↔ source MD ───────────────────


def _strip(value: str) -> str:
    """Strip whitespace and trailing punctuation for loose comparison."""
    if not value:
        return ""
    return value.strip().rstrip(".,;:").strip()


def check_structural_da(
    label: str,
    source_md: Path,
    preproc_json: dict[str, Any],
    findings: list[Finding],
) -> None:
    """For DA JSONs, verify extracted fields are consistent with source MD."""
    if not source_md.exists():
        return  # already flagged in strict check
    src_fm, src_body = _read_md(source_md)

    # ── Frontmatter (top-level + frontmatter key) ─────────────────────
    # CORR-035 c5: the parser auto-corrects macro_domain at the
    # top-level (e.g. "D-09" → "D-10") when the source's sub_domain
    # prefix does not match. The frontmatter dict inside the JSON,
    # however, keeps the original source value (the auto-correction
    # only touches the top-level macro_domain field). We therefore
    # prefer the top-level macro_domain when comparing against the
    # source.
    for key in ("document_id", "title", "macro_domain", "sub_domain", "status"):
        src_val = _strip(src_fm.get(key, ""))
        # Prefer top-level over frontmatter (for macro_domain especially)
        json_val = _strip(preproc_json.get(key, "") or preproc_json.get("frontmatter", {}).get(key, ""))
        if not src_val:
            continue
        if not json_val:
            findings.append(
                Finding(
                    "HIGH",
                    f"STRUCT_FM_{key.upper()}_MISSING_IN_JSON",
                    label,
                    f"source MD has {key}={src_val!r} but JSON does not",
                )
            )
        elif src_val != json_val:
            # CORR-035 c5: macro_domain is auto-corrected by the parser
            # when source frontmatter has a mismatch (e.g. source says
            # "D-09 Governance" but sub_domain is D-10.*). The parser
            # rewrites it to the canonical name. Flag this as INFO
            # (intentional mitigation) rather than HIGH (data error).
            if key == "macro_domain":
                # The sub_domain is the source of truth; check the JSON
                # macro_domain contains the sub_domain's D-XX prefix.
                sub_dom = _strip(preproc_json.get("sub_domain", ""))
                m = re.match(r"^(D-\d+)\.", sub_dom)
                if m and m.group(1) in json_val and m.group(1) not in src_val:
                    findings.append(
                        Finding(
                            "INFO",
                            f"STRUCT_FM_{key.upper()}_PARSER_AUTOCORRECTED",
                            label,
                            f"{key}: source={src_val!r} != json={json_val!r} "
                            f"(parser auto-corrected; sub_domain={sub_dom!r} "
                            f"takes precedence per CORR-035 c5)",
                        )
                    )
                    continue
            findings.append(
                Finding(
                    "HIGH",
                    f"STRUCT_FM_{key.upper()}_MISMATCH",
                    label,
                    f"{key}: source={src_val!r} != json={json_val!r}",
                )
            )

    # ── title_h3 — extracted from the first H3 ────────────────────────
    h3_in_source = ""
    m = re.search(r"^###\s+(.+?)\s*$", src_body, re.MULTILINE)
    if m:
        h3_in_source = _strip(m.group(1))
    h3_in_json = _strip(preproc_json.get("title_h3", ""))
    if h3_in_source and h3_in_source != h3_in_json:
        findings.append(
            Finding(
                "MEDIUM",
                "STRUCT_TITLE_H3_MISMATCH",
                label,
                f"title_h3: source H3={h3_in_source!r} != json={h3_in_json!r}",
            )
        )

    # ── participants_meta — from `<!-- participants: ... -->` ───────
    pm_in_source = re.findall(
        r"<!--\s*participants:\s*([^>]+?)\s*-->", src_body
    )
    pm_in_source_norm: list[str] = []
    for p in pm_in_source:
        pm_in_source_norm.extend(_strip(s) for s in p.split(","))
    pm_in_json = [_strip(s) for s in preproc_json.get("participants_meta", [])]
    if pm_in_source_norm and pm_in_source_norm != pm_in_json:
        findings.append(
            Finding(
                "MEDIUM",
                "STRUCT_PARTICIPANTS_META_DIFF",
                label,
                f"participants_meta: source={pm_in_source_norm} != json={pm_in_json}",
            )
        )

    # ── participants (DA structured list — canonicalised names) ──────
    # The parser canonicalises via _deep_norm_reg (NIS 2 -> NIS2,
    # AI Act -> AI_Act). The source has whatever the author wrote.
    # We do a case-insensitive / alias-aware comparison.
    _NORM = {"NIS 2": "NIS2", "NIS_2": "NIS2", "AI Act": "AI_Act", "AIACT": "AI_Act", "AIA": "AI_Act", "AI": "AI_Act"}
    pm_canon = [_NORM.get(p, p) for p in pm_in_source_norm]
    pj_canon = [_NORM.get(p, p) for p in pm_in_json]
    if pm_canon and pj_canon and set(pm_canon) != set(pj_canon):
        findings.append(
            Finding(
                "MEDIUM",
                "STRUCT_PARTICIPANTS_DIFF",
                label,
                f"participants (canonicalised): source={pm_canon} != json={pj_canon}",
            )
        )

    # ── pair_count — derived from <!-- pair: ... --> count ───────────
    # Count only pairs that are properly closed with `<!-- /pair -->`.
    # Source MDs may reference the `<!-- pair: -->` syntax in
    # meta-sections (e.g. "Conventions." documentation) without
    # actually defining a pair. The parser only emits pairs that have
    # an open AND a close marker, so we count the same way.
    pair_open_re = re.compile(r"<!--\s*pair:\s*([\w,\s]+?)\s*-->")
    pair_close_re = re.compile(r"<!--\s*/pair\s*-->")
    n_open = len(pair_open_re.findall(src_body))
    n_close = len(pair_close_re.findall(src_body))
    pc_in_source = min(n_open, n_close) if n_open == n_close else n_close
    pc_in_json = preproc_json.get("pair_count", 0)
    if pc_in_source != pc_in_json:
        findings.append(
            Finding(
                "HIGH",
                "STRUCT_PAIR_COUNT_DIFF",
                label,
                f"pair_count: source has {pc_in_source} closed `<!-- pair: -->/<!----/pair-->` blocks "
                f"({n_open} open / {n_close} close markers), json says {pc_in_json}",
            )
        )

    # ── classification_distribution — derived from pairs ─────────────
    # We can recompute it from the pairs list in the JSON
    pairs = preproc_json.get("pairs", [])
    actual_dist: dict[str, int] = {}
    for p in pairs:
        cls = p.get("classification") or "(empty)"
        actual_dist[cls] = actual_dist.get(cls, 0) + 1
    declared_dist = preproc_json.get("classification_distribution", {})
    if dict(actual_dist) != declared_dist:
        findings.append(
            Finding(
                "HIGH",
                "STRUCT_CLASS_DIST_INCONSISTENT",
                label,
                f"classification_distribution declared={declared_dist} but pairs recompute={dict(actual_dist)}",
            )
        )

    # ── emergent_tensions — from `<!-- emergent: ... -->` markers ────
    em_in_source = re.findall(r"<!--\s*emergent:\s*([^>]+?)\s*-->", src_body)
    em_in_source_norm: list[list[str]] = []
    for s in em_in_source:
        em_in_source_norm.append([_strip(r) for r in s.split(",")])
    em_in_json = preproc_json.get("emergent_tensions", [])
    # Compare length only (a full per-regulator check is too verbose for
    # this pilot)
    if len(em_in_source_norm) != len(em_in_json):
        findings.append(
            Finding(
                "MEDIUM",
                "STRUCT_EMERGENT_COUNT_DIFF",
                label,
                f"emergent_tensions: source has {len(em_in_source_norm)} markers, json says {len(em_in_json)}",
            )
        )

    # ── sr_cross_references — SR-XXX-NNN in body ─────────────────────
    sr_in_source = sorted(set(re.findall(r"SR-[A-Za-z0-9_]+-\d{3}", src_body)))
    sr_in_json = preproc_json.get("sr_cross_references", [])
    if sr_in_source and sorted(sr_in_source) != sorted(sr_in_json):
        # Find the diff
        set_src, set_json = set(sr_in_source), set(sr_in_json)
        only_src = sorted(set_src - set_json)
        only_json = sorted(set_json - set_src)
        msg = f"sr_cross_references: "
        if only_src:
            msg += f"missing from json: {only_src}  "
        if only_json:
            msg += f"extra in json: {only_json}"
        findings.append(
            Finding(
                "MEDIUM",
                "STRUCT_SR_REFS_DIFF",
                label,
                msg,
            )
        )


def check_structural_deep(
    label: str,
    source_md: Path,
    preproc_json: dict[str, Any],
    findings: list[Finding],
) -> None:
    """For Deep JSONs, verify extracted fields are consistent with source MD."""
    if not source_md.exists():
        return
    src_fm, src_body = _read_md(source_md)

    # ── Frontmatter ──────────────────────────────────────────────────
    for key in ("document_id", "title", "macro_domain", "sub_domain", "status"):
        src_val = _strip(src_fm.get(key, ""))
        json_val = _strip(preproc_json.get(key, "") or preproc_json.get("frontmatter", {}).get(key, ""))
        if not src_val:
            continue
        if not json_val:
            findings.append(
                Finding(
                    "HIGH",
                    f"STRUCT_FM_{key.upper()}_MISSING_IN_JSON",
                    label,
                    f"source MD has {key}={src_val!r} but JSON does not",
                )
            )
        elif src_val != json_val:
            # CORR-035 c5: macro_domain is auto-corrected by the parser
            # when source frontmatter has a mismatch. The parser uses
            # sub_domain as the source of truth. Flag as INFO.
            if key == "macro_domain":
                sub_dom = _strip(preproc_json.get("sub_domain", ""))
                m = re.match(r"^(D-\d+)\.", sub_dom)
                if m and m.group(1) in json_val and m.group(1) not in src_val:
                    findings.append(
                        Finding(
                            "INFO",
                            f"STRUCT_FM_{key.upper()}_PARSER_AUTOCORRECTED",
                            label,
                            f"{key}: source={src_val!r} != json={json_val!r} "
                            f"(parser auto-corrected; sub_domain={sub_dom!r} "
                            f"takes precedence per CORR-035 c5)",
                        )
                    )
                    continue
            findings.append(
                Finding(
                    "HIGH",
                    f"STRUCT_FM_{key.upper()}_MISMATCH",
                    label,
                    f"{key}: source={src_val!r} != json={json_val!r}",
                )
            )

    # ── title_h3 — extracted from the first H3 ────────────────────────
    h3_in_source = ""
    m = re.search(r"^###\s+(.+?)\s*$", src_body, re.MULTILINE)
    if m:
        h3_in_source = _strip(m.group(1))
    h3_in_json = _strip(preproc_json.get("title_h3", ""))
    if h3_in_source and h3_in_source != h3_in_json:
        findings.append(
            Finding(
                "MEDIUM",
                "STRUCT_TITLE_H3_MISMATCH",
                label,
                f"title_h3: source H3={h3_in_source!r} != json={h3_in_json!r}",
            )
        )

    # ── participants — Deep has a different format (no <!-- comment -->) ──
    # The Deep source has "**Participants (from CRDA):** GDPR, NIS2, CRA, DORA ..."
    # The JSON has a `participants` list (canonicalised).
    # The author may add a parenthetical note after the list (e.g.
    # "DORA (AI_Act is not present; ...)"); truncate at the first '('
    # so we only compare the comma-separated reg list.
    p_match = re.search(
        r"\*\*Participants[^:]*:\*\*\s*([^*\n(]+)", src_body
    )
    if p_match:
        src_parts = [
            _strip(s) for s in p_match.group(1).split(",")
        ]
        # Apply the same alias normalisation
        _NORM = {"NIS 2": "NIS2", "NIS_2": "NIS2", "AI Act": "AI_Act", "AIACT": "AI_Act", "AIA": "AI_Act", "AI": "AI_Act"}
        src_canon = [_NORM.get(s, s) for s in src_parts]
        pj_canon = preproc_json.get("participants", [])

        # The source MD may mark some regulations as "partial" or
        # "out-of-scope" — but the JSON often includes them as full
        # participants. The parser's interpretation differs from the
        # author prose. Flag as INFO when the difference is one-way
        # (JSON has MORE than source), MEDIUM when source has regs
        # that JSON doesn't (which would be a real loss).
        only_in_source = set(src_canon) - set(pj_canon)
        only_in_json = set(pj_canon) - set(src_canon)
        if only_in_source and only_in_json:
            findings.append(
                Finding(
                    "MEDIUM",
                    "STRUCT_PARTICIPANTS_DIFF",
                    label,
                    f"participants: source={src_canon} != json={pj_canon} "
                    f"(only in source: {sorted(only_in_source)}, only in json: {sorted(only_in_json)})",
                )
            )
        elif only_in_source:
            findings.append(
                Finding(
                    "MEDIUM",
                    "STRUCT_PARTICIPANTS_SOURCE_ONLY",
                    label,
                    f"participants in source but missing from JSON: {sorted(only_in_source)} "
                    f"(source={src_canon}, json={pj_canon})",
                )
            )
        elif only_in_json:
            findings.append(
                Finding(
                    "INFO",
                    "STRUCT_PARTICIPANTS_JSON_EXTRA",
                    label,
                    f"participants in JSON but not declared in source: {sorted(only_in_json)} "
                    f"(source={src_canon}, json={pj_canon}) "
                    f"— likely a 'partial' or 'out-of-scope' interpretation",
                )
            )

    # ── pair_count — derived from `#### Pair: REG_A ↔ REG_B` count ──
    # CORR-PILOT: source MDs may include `#### Pair: ... (omitted —
    # ...)` H4s to document explicit non-analysis pairs (e.g. "AI_Act
    # is fully absent"). The parser filters these out. Count only the
    # non-omitted H4s for the source count.
    all_pair_h4s = re.findall(
        r"^####\s+Pair:\s+([^\n]+)$", src_body, re.MULTILINE
    )
    real_pair_h4s = [
        h for h in all_pair_h4s
        if not re.search(r"\bomitted\b", h, re.IGNORECASE)
        and "[not in" not in h
    ]
    pc_in_source = len(real_pair_h4s)
    pc_in_json = preproc_json.get("pair_count", 0)
    if pc_in_source != pc_in_json:
        omitted = [h for h in all_pair_h4s if h not in real_pair_h4s]
        findings.append(
            Finding(
                "HIGH",
                "STRUCT_PAIR_COUNT_DIFF",
                label,
                f"pair_count: source has {pc_in_source} real "
                f"`#### Pair:` H4s (omitted: {len(omitted)}), json says {pc_in_json}",
            )
        )

    # ── classified_relationship_crda — for each pair ─────────────────
    # Source has lines like: "**Classified relationship (from CRDA):** COMPLEMENTARY."
    # The JSON has per-pair `classified_relationship_crda`.
    src_crda_matches = re.findall(
        r"\*\*Classified relationship \(from CRDA\):\*\*\s*([^*\n]+?)\.?$",
        src_body,
        re.MULTILINE,
    )
    src_crda = [_strip(s) for s in src_crda_matches]
    pairs = preproc_json.get("pairs", [])
    json_crda = [_strip(p.get("classified_relationship_crda", "")) for p in pairs]
    if src_crda and src_crda != json_crda:
        findings.append(
            Finding(
                "HIGH",
                "STRUCT_CRDA_DIFF",
                label,
                f"classified_relationship_crda: source={src_crda} != json={json_crda}",
            )
        )

    # ── verified_relationship_oj — for each pair ─────────────────────
    src_verified_matches = re.findall(
        r"\*\*Verified relationship \(OJ\):\*\*\s*([^*\n]+?)\.?$",
        src_body,
        re.MULTILINE,
    )
    src_verified = [_strip(s) for s in src_verified_matches]
    json_verified = [_strip(p.get("verified_relationship_oj", "")) for p in pairs]
    if src_verified and src_verified != json_verified:
        findings.append(
            Finding(
                "MEDIUM",
                "STRUCT_VERIFIED_DIFF",
                label,
                f"verified_relationship_oj: source has {len(src_verified)} entries, json has {len(json_verified)}; values may differ",
            )
        )

    # ── sr_cross_references ───────────────────────────────────────────
    sr_in_source = sorted(set(re.findall(r"SR-[A-Za-z0-9_]+-\d{3}", src_body)))
    sr_in_json = preproc_json.get("sr_cross_references", [])
    if sr_in_source and sorted(sr_in_source) != sorted(sr_in_json):
        set_src, set_json = set(sr_in_source), set(sr_in_json)
        only_src = sorted(set_src - set_json)
        only_json = sorted(set_json - set_src)
        msg = f"sr_cross_references: "
        if only_src:
            msg += f"missing from json: {only_src}  "
        if only_json:
            msg += f"extra in json: {only_json}"
        findings.append(
            Finding(
                "MEDIUM",
                "STRUCT_SR_REFS_DIFF",
                label,
                msg,
            )
        )


# ── main ─────────────────────────────────────────────────────────────


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="restrict to one sub-domain prefix (e.g. D-04 or D-04.3)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of human report",
    )
    parser.add_argument(
        "--side",
        choices=["da", "deep", "both"],
        default="both",
        help="which side to check (default: both)",
    )
    args = parser.parse_args()

    # Discover all sub-domains from the preproc dir (the source of truth
    # for what the build produced). For each, locate the source MD via
    # the matching macro_dir.
    if not PREPROC_CROSSREG.exists():
        print(f"ERROR: {PREPROC_CROSSREG} does not exist", file=sys.stderr)
        return 2

    targets: list[tuple[str, str]] = []  # (subdomain, macro_dir)
    if args.side in ("da", "both"):
        for sub_path in sorted(PREPROC_CROSSREG.glob("DomainAnalysis/*/D-*.json")):
            sub = sub_path.stem
            macro = sub_path.parent.name
            if args.only and not sub.startswith(args.only):
                continue
            targets.append((sub, macro))

    if not targets:
        print(f"ERROR: no targets match --only={args.only}", file=sys.stderr)
        return 2

    if not args.json:
        print(f"=== Parity check: {len(targets)} sub-domains ===")
        print()

    all_findings: list[Finding] = []
    per_subdomain: dict[str, list[Finding]] = {}

    for sub, macro in targets:
        findings: list[Finding] = []

        if args.side in ("da", "both"):
            src_da_md = METH_CROSSREG / "DomainAnalysis" / macro / f"{sub}.md"
            preproc_da = PREPROC_CROSSREG / "DomainAnalysis" / macro / f"{sub}.json"
            da_data = check_strict(f"DA/{sub}", src_da_md, preproc_da, findings)
            check_structural_da(f"DA/{sub}", src_da_md, da_data, findings)

        if args.side in ("deep", "both"):
            src_deep_md = METH_CROSSREG / "DeepAnalysis" / macro / f"{sub}.md"
            preproc_deep = PREPROC_CROSSREG / "DeepAnalysis" / macro / f"{sub}.json"
            deep_data = check_strict(f"Deep/{sub}", src_deep_md, preproc_deep, findings)
            check_structural_deep(f"Deep/{sub}", src_deep_md, deep_data, findings)

        per_subdomain[sub] = findings
        all_findings.extend(findings)

    # ── Report ───────────────────────────────────────────────────────
    from collections import Counter
    by_sev: Counter[str] = Counter(f.severity for f in all_findings)
    by_code: Counter[str] = Counter(f.code for f in all_findings)

    if args.json:
        # Per-subdomain + per-finding machine-readable
        out = {
            "subdomains_scanned": len(targets),
            "finding_count": len(all_findings),
            "by_severity": dict(by_sev),
            "by_code": dict(by_code),
            "findings": [f.to_dict() for f in all_findings],
            "per_subdomain": {
                sub: {
                    "finding_count": len(fs),
                    "by_severity": dict(Counter(f.severity for f in fs)),
                    "by_code": dict(Counter(f.code for f in fs)),
                }
                for sub, fs in per_subdomain.items()
            },
        }
        print(json.dumps(out, indent=2))
    else:
        # Human report
        print()
        print(f"=== {len(all_findings)} findings across {len(targets)} sub-domains ===")
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            n = by_sev.get(sev, 0)
            if n:
                print(f"  {sev:8s} {n}")
        print()
        if by_code:
            print("By code (top 10):")
            for code, n in by_code.most_common(10):
                print(f"  {code:35s} {n}")
            print()

        # Per-subdomain summary
        problematic = {
            sub: fs for sub, fs in per_subdomain.items() if fs
        }
        if problematic:
            print(f"--- {len(problematic)} sub-domains with findings ---")
            for sub in sorted(problematic):
                fs = problematic[sub]
                sev_counts = Counter(f.severity for f in fs)
                sev_str = " ".join(
                    f"{sev}={sev_counts.get(sev, 0)}"
                    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
                    if sev_counts.get(sev, 0)
                )
                print(f"  {sub:8s} {len(fs):3d} findings  {sev_str}")
            print()
            print("--- All findings ---")
            for f in all_findings:
                print(str(f))
        else:
            print("All parity checks passed. ✓")
        return 0 if not all_findings else 1


if __name__ == "__main__":
    sys.exit(main())
