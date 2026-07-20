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
    """Build (reg, so_id) → set of subdomain_ids.

    Uses inherits_from (regulatory ID) and id (local ID) as the keys.
    This is the bridge between the two ID conventions.
    """
    out: dict[tuple[str, str], set[str]] = {}
    for sid, sd in subdomains.items():
        for hso in sd.get("hso_per_reg", []):
            reg = hso.get("regulation", "?")
            for k in ("inherits_from", "id", "yaml_id", "source_SR"):
                v = hso.get(k)
                if v and isinstance(v, str) and v.startswith("SO-"):
                    out.setdefault((reg, v), set()).add(sid)
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
    coverage_mismatches: list[dict] = []
    for reg, sr in srs:
        expected_subs: set[str] = set()
        for so_id in sr.get("linked_objectives", []):
            for s in so_index.get((reg, so_id), []):
                expected_subs.add(s)
        actual_subs = set(sr.get("sub_domain", []))
        extras = actual_subs - expected_subs
        if extras:
            coverage_mismatches.append(
                {
                    "sr_id": sr["id"],
                    "sub_domain_actual": sorted(actual_subs),
                    "linked_objectives": sr.get("linked_objectives", []),
                    "so_covered_subdomains": sorted(expected_subs),
                    "extras": sorted(extras),
                }
            )

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
        "coverage_mismatches": {
            "count": len(coverage_mismatches),
            "items": coverage_mismatches[:50],  # cap for readability
            "total_excess": len(coverage_mismatches),
        },
        "known_gaps": {
            "deferred_to": "CORR-030",
            "so_without_sr_count": len(so_no_sr),
            "note": (
                f"{len(so_no_sr)} SO entries have no SR. These may be "
                "intentional (framework coverage without specific obligation) "
                "or may need new SRs. See CORR-030 scope."
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
    print(f"Coverage mismatches: {report['coverage_mismatches']['count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
