"""SO↔SR structural-coherence audit (CORR-029).

Walks the preproc_out entities (subdomains + regulation-aggregated SRs)
and produces a coverage report at preproc_out/audit/so_sr_coherence_report.json.

The audit validates:
  1. **SO→SR direction** (SOs without SRs):
     For each (regulation, subdomain) pair, count the SOs in the subdomain
     and the SRs in the regulation's aggregated file. Report SOs that have
     no matching SR.

  2. **SR→SO direction** (SRs without SOs):
     For each SR, check that the (regulation, sub_domain) pair has a
     matching SO in the subdomain entity. Report SRs whose target
     subdomains have no SO for that regulation.

  3. **Bridge resolution** (the inherits_from SO↔SR bridge):
     For each SR's `linked_objectives` (regulatory IDs like SO-AIACT-001),
     resolve to the corresponding SO in the subdomain via
     `hso_per_reg[].inherits_from`. Report the resolution rate.

  4. **Coverage** (SR.sub_domain ⊆ ∪ of SO-covered subdomains):
     For each SR, check that every subdomain in `sub_domain` is covered
     by at least one of the SR's linked SOs (via the inherits_from bridge).
     Report mismatches (extras).

This is a **standalone scanner** — it reads preproc_out and writes a
report. It does NOT mutate any shard. Re-runs are idempotent.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
PREPROC_OUT = REPO_ROOT / "preproc_out"
SUBDOMAINS_DIR = PREPROC_OUT / "entities" / "subdomains"
REG_DIR = PREPROC_OUT / "regulation"
AUDIT_OUT = PREPROC_OUT / "audit" / "so_sr_coherence_report.json"


def _load_subdomains() -> dict[str, dict]:
    """Load all subdomain entities. Returns {subdomain_id: entity}."""
    out: dict[str, dict] = {}
    for p in sorted(SUBDOMAINS_DIR.glob("D-*.json")):
        with p.open() as f:
            d = json.load(f)
        out[d["id"]] = d
    return out


def _load_srs() -> list[tuple[str, dict]]:
    """Load all regulation-aggregated SRs. Returns [(reg, sr), ...]."""
    out: list[tuple[str, dict]] = []
    for regdir in sorted(REG_DIR.iterdir()):
        if not regdir.is_dir():
            continue
        sr_path = regdir / "aggregated" / "02_SecurityRules_NIST.json"
        if not sr_path.is_file():
            continue
        with sr_path.open() as f:
            data = json.load(f)
        reg = regdir.name
        for sr in data.get("srs", []):
            out.append((reg, sr))
    return out


def _build_so_index(subdomains: dict[str, dict]) -> dict[tuple[str, str], set[str]]:
    """Build (reg, regulatory_so_id) → set of subdomain_ids.

    Only ``inherits_from`` is used (the regulatory SO ID). The local
    ``id`` / ``yaml_id`` are NOT indexed because they don't help resolve
    regulatory IDs referenced in SRs' ``linked_objectives``.

    ``inherits_from`` can be a string (possibly multi-value, separated by
    ',', '+', '/', or ' and ') or a list of strings. We split and dedupe.
    """
    out: dict[tuple[str, str], set[str]] = {}
    for sid, sd in subdomains.items():
        for hso in sd.get("hso_per_reg", []):
            reg = hso.get("regulation", "?")
            inh = hso.get("inherits_from")
            if not inh:
                continue
            if isinstance(inh, list):
                parts = [str(p).strip() for p in inh]
            else:
                parts = re.split(r"[,+/]\s*|\s+and\s+", str(inh))
            # CORR-030: strip surrounding list brackets and any
            # trailing comment/parenthetical from each part so that
            # ``[SO-CRA-039, SO-CRA-040]`` and
            # ``SO-CRA-009 (partial cross-ref ...)`` both split cleanly.
            parts = [
                re.sub(r"^[\[\(]\s*|\s*[\]\)]$", "", p).strip()
                for p in parts
            ]
            parts = [re.sub(r"\s+[#(].*$|\s+\(.*\)$", "", p).strip() for p in parts]
            for part in parts:
                part = part.strip()
                if part.startswith("SO-"):
                    out.setdefault((reg, part), set()).add(sid)
    return out


def _audit() -> dict:
    """Run the audit and return the report dict."""
    subdomains = _load_subdomains()
    srs = _load_srs()
    so_index = _build_so_index(subdomains)

    # Count totals
    total_so_entries = sum(len(sd.get("hso_per_reg", [])) for sd in subdomains.values())
    so_with_inherits = sum(
        1
        for sd in subdomains.values()
        for hso in sd.get("hso_per_reg", [])
        if hso.get("inherits_from")
    )
    total_sr_lo = sum(len(sr.get("linked_objectives", [])) for _, sr in srs)
    resolved_lo = sum(
        1
        for _, sr in srs
        for lo in sr.get("linked_objectives", [])
        if (sr["regulation"], lo) in so_index
    )

    # 1. SO→SR direction
    so_no_sr: list[dict] = []
    so_no_sr_justified: list[dict] = []
    for sid, sd in subdomains.items():
        for hso in sd.get("hso_per_reg", []):
            reg = hso.get("regulation", "?")
            n_srs_in_sub = sum(1 for r, sr in srs if r == reg and sid in sr.get("sub_domain", []))
            if n_srs_in_sub == 0:
                # CORR-029: if the subdomain has a justification for this
                # (reg, sub) SO-orphan, classify as justified (intentional
                # partial / cross-ref / inheritance from primary SO) rather
                # than as a real orphan.
                so_justifications = sd.get("orphan_so_justifications", {})
                if reg in so_justifications:
                    so_no_sr_justified.append({
                        "subdomain": sid,
                        "regulation": reg,
                        "so_id": hso.get("id"),
                        "inherits_from": hso.get("inherits_from"),
                        "justification": so_justifications[reg],
                    })
                else:
                    so_no_sr.append({
                        "subdomain": sid,
                        "regulation": reg,
                        "so_id": hso.get("id"),
                        "inherits_from": hso.get("inherits_from"),
                    })

    # 2. SR→SO direction
    sr_no_so: list[dict] = []
    sr_no_so_justified: list[dict] = []
    for reg, sr in srs:
        for sid in sr.get("sub_domain", []):
            sd = subdomains.get(sid)
            if not sd:
                continue
            has_so = any(hso.get("regulation") == reg for hso in sd.get("hso_per_reg", []))
            if not has_so:
                # CORR-029: if the subdomain has a justification for this
                # (reg, sub) orphan, classify as justified (intentional
                # partial coverage or out-of-scope cross-ref) rather than
                # as a real orphan.
                justifications = sd.get("orphan_sr_justifications", {})
                if reg in justifications:
                    sr_no_so_justified.append(
                        {
                            "subdomain": sid,
                            "regulation": reg,
                            "sr_id": sr["id"],
                            "sr_title": sr.get("title", "")[:80],
                            "justification": justifications[reg],
                        }
                    )
                else:
                    sr_no_so.append(
                        {
                            "subdomain": sid,
                            "regulation": reg,
                            "sr_id": sr["id"],
                            "sr_title": sr.get("title", "")[:80],
                        }
                    )

    # 4. Coverage check (sub_domain ⊆ ∪ of SO-covered subs)
    #    Two failure modes:
    #    a) **Unresolved** — SR references SOs that don't exist in any
    #       hso_per_reg[].inherits_from (the regulatory SO is defined in
    #       01_SecurityObjectives.md but was never propagated to a subdomain).
    #    b) **Partial** — SR.sub_domain is a superset of what the linked
    #       SOs cover (the SO exists but covers fewer subdomains than the
    #       SR claims).
    coverage_unresolved: list[dict] = []
    coverage_partial: list[dict] = []
    coverage_full: int = 0
    for reg, sr in srs:
        expected_subs: set[str] = set()
        unresolved_los: list[str] = []
        for so_id in sr.get("linked_objectives", []):
            resolved = so_index.get((reg, so_id), set())
            if not resolved:
                unresolved_los.append(so_id)
            expected_subs |= resolved
        actual_subs = set(sr.get("sub_domain", []))
        extras = actual_subs - expected_subs
        # Classify
        if unresolved_los and not actual_subs:
            # SR with linked_objectives but none resolve AND no sub_domain
            coverage_unresolved.append({
                "sr_id": sr["id"],
                "sr_title": sr.get("title", "")[:80],
                "linked_objectives": sr.get("linked_objectives", []),
                "unresolved_los": unresolved_los,
                "sub_domain": sorted(actual_subs),
            })
        elif unresolved_los:
            # Some LOs unresolved + SR has sub_domain
            coverage_unresolved.append({
                "sr_id": sr["id"],
                "sr_title": sr.get("title", "")[:80],
                "linked_objectives": sr.get("linked_objectives", []),
                "unresolved_los": unresolved_los,
                "sub_domain": sorted(actual_subs),
            })
        elif extras:
            # All LOs resolved but coverage partial
            # Classify the pattern
            if len(actual_subs) > 1:
                pattern = "multi_subdomain"
            else:
                pattern = "so_narrower"
            coverage_partial.append({
                "sr_id": sr["id"],
                "sr_title": sr.get("title", "")[:80],
                "sub_domain": sorted(actual_subs),
                "linked_objectives": sr.get("linked_objectives", []),
                "so_covered_subdomains": sorted(expected_subs),
                "extras": sorted(extras),
                "pattern": pattern,
            })
        else:
            coverage_full += 1

    # Build distinct-unresolved analysis
    distinct_unresolved: dict[tuple[str, str], dict] = {}
    for entry in coverage_unresolved:
        for so_id in entry["unresolved_los"]:
            key = (entry.get("linked_objectives", []) and
                   next((lo for lo in entry.get("linked_objectives", []) if lo == so_id), so_id),
                   so_id)
            # We don't have the reg in this entry; refactor to include it
    # Rebuild with reg
    distinct_unresolved_with_reg: dict[tuple[str, str], list[str]] = {}
    for reg, sr in srs:
        for so_id in sr.get("linked_objectives", []):
            if (reg, so_id) not in so_index:
                distinct_unresolved_with_reg.setdefault((reg, so_id), []).append(sr["id"])

    return {
        "schema_version": "1.0",
        "built_at": _dt.datetime.now(_dt.UTC).isoformat(),
        "totals": {
            "subdomains": len(subdomains),
            "srs_total": len(srs),
            "so_entries": total_so_entries,
            "so_with_inherits_from": so_with_inherits,
            "so_inherits_from_pct": (
                round(100 * so_with_inherits / total_so_entries, 1) if total_so_entries else 0
            ),
            "sr_linked_objectives_total": total_sr_lo,
            "sr_linked_objectives_resolved": resolved_lo,
            "sr_lo_resolution_pct": (
                round(100 * resolved_lo / total_sr_lo, 1) if total_sr_lo else 0
            ),
            "coverage_full": coverage_full,
            "coverage_partial_count": len(coverage_partial),
            "coverage_unresolved_count": len(coverage_unresolved),
        },
        "so_without_sr": {
            "count": len(so_no_sr),
            "items": so_no_sr,
            "justified_count": len(so_no_sr_justified),
            "justified_items": so_no_sr_justified,
        },
        "sr_without_so": {
            "count": len(sr_no_so),
            "items": sr_no_so,
            "justified_count": len(sr_no_so_justified),
            "justified_items": sr_no_so_justified,
        },
        "coverage_partial": {
            # CORR-029c: every SR whose sub_domain is NOT fully covered
            # by the union of its linked SOs (and all linked SOs resolve).
            # Deferred to CORR-030 (user decision 2026-07-20).
            "count": len(coverage_partial),
            "by_pattern": {
                pattern: sum(1 for e in coverage_partial if e["pattern"] == pattern)
                for pattern in {e["pattern"] for e in coverage_partial}
            },
            "items": coverage_partial,
        },
        "coverage_unresolved": {
            # CORR-029c: every SR whose linked_objectives reference
            # regulatory SOs that don't exist in any hso_per_reg[].inherits_from
            # (the regulatory SOs are defined in 01_SecurityObjectives.md but
            # were never propagated to a subdomain).
            # Deferred to CORR-030.
            "count": len(coverage_unresolved),
            "items": coverage_unresolved,
            "distinct_unresolved": [
                {
                    "regulation": reg,
                    "so_id": so_id,
                    "referenced_by_srs": sorted(sr_ids),
                    "reference_count": len(sr_ids),
                }
                for (reg, so_id), sr_ids in sorted(
                    distinct_unresolved_with_reg.items(),
                    key=lambda x: -len(x[1]),
                )
            ],
            "distinct_count": len(distinct_unresolved_with_reg),
        },
        "known_gaps": {
            "deferred_to": "CORR-030",
            "user_decision": "2026-07-20: 'Só auditar (deferir) — criar um relatório detalhado dos 166 sem mexer nos MDs'",
            "so_without_sr_count": len(so_no_sr),
            "sr_partial_coverage_count": len(coverage_partial),
            "sr_unresolved_lo_count": len(coverage_unresolved),
            "distinct_unresolved_so_count": len(distinct_unresolved_with_reg),
            "note": (
                f"{len(so_no_sr)} SO entries have no SR; {len(coverage_partial)} "
                f"SRs have partial SO coverage; {len(coverage_unresolved)} "
                f"SRs reference unresolved regulatory SOs. All 166 gaps are "
                f"documented in the report (deferred to CORR-030 per user "
                f"decision 2026-07-20)."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    report = _audit()
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_OUT.open("w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("wrote %s", AUDIT_OUT)

    t = report["totals"]
    print(
        f"SO entries with inherits_from: {t['so_with_inherits_from']}/{t['so_entries']} ({t['so_inherits_from_pct']}%)"
    )
    print(
        f"SR linked_objectives resolved: {t['sr_linked_objectives_resolved']}/{t['sr_linked_objectives_total']} ({t['sr_lo_resolution_pct']}%)"
    )
    print(f"SO without SR: {report['so_without_sr']['count']}")
    print(f"SR without SO: {report['sr_without_so']['count']}")
    print(
        f"Coverage: full={t['coverage_full']}, partial={t['coverage_partial_count']}, "
        f"unresolved={t['coverage_unresolved_count']}"
    )
    by_pat = report["coverage_partial"].get("by_pattern", {})
    if by_pat:
        print(
            f"  partial by pattern: "
            + ", ".join(f"{k}={v}" for k, v in sorted(by_pat.items()))
        )
    print(
        f"Coverage partial: {report['coverage_partial']['count']} "
        f"(distinct unresolved: {report['coverage_unresolved']['distinct_count']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
