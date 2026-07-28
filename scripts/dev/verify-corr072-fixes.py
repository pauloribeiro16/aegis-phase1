"""Isolated verification of all CORR-072 bug fixes.

Tests each fix independently by:
  1. Constructing the minimal state that previously triggered the bug
  2. Calling the fixed function directly
  3. Asserting the bug is gone

This is faster and more reliable than re-running the full pipeline
(which would cost ~11 min and depend on M3 API availability).
"""
from __future__ import annotations

import sys

from aegis_phase1.v2.output.doc_04 import _augment_influence, _section_3_stakeholders, _stakeholders
from aegis_phase1.v2.output.doc_04a import _strip_section_header
from aegis_phase1.v2.output.doc_04b import _active_count
from aegis_phase1.v2.output.doc_04c import _active_subdomain_count as _active_count_04c
from aegis_phase1.v2.output.doc_04d import _active_subdomain_count as _active_count_04d, _section_regulation_level


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def ok(name: str) -> None:
    print(f"  {GREEN}PASS{RESET}  {name}")


def fail(name: str, err: str) -> None:
    print(f"  {RED}FAIL{RESET}  {name}")
    print(f"        {err}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────
# Fix #1 — _augment_influence (doc_04.py)
# ─────────────────────────────────────────────────────────────────────

def test_fix_1_no_org_inheritance() -> None:
    """OmniBank stakeholder with empty org/contact must NOT inherit TinyTask values."""
    print("\n=== Fix #1 — _augment_influence (stakeholder org/contact/responsibilities) ===")

    sh = {
        "id": "SH-01",
        "role": "Chief Executive Officer (CEO)",
        "responsibilities": "executive_sponsor, accountability, ecb_supervised",
        "organisation": "-",
        "contact": "-",
        "influence": "-",
        "interest": "-",
    }
    out = _augment_influence(dict(sh))
    if out["organisation"] != "-":
        fail("no org inheritance", f"got {out['organisation']!r}")
    ok("no org inheritance from TinyTask baseline")

    if out["contact"] != "-":
        fail("no contact inheritance", f"got {out['contact']!r}")
    ok("no contact inheritance from TinyTask baseline")

    if out["responsibilities"] != "executive_sponsor, accountability, ecb_supervised":
        fail("no responsibilities override", f"got {out['responsibilities']!r}")
    ok("responsibilities NOT overwritten by baseline")

    # influence/interest should still inherit (template metadata)
    if out["influence"] == "-":
        fail("influence inheritance broken", f"got {out['influence']!r}")
    ok("influence still inherits from baseline")
    if out["interest"] == "-":
        fail("interest inheritance broken", f"got {out['interest']!r}")
    ok("interest still inherits from baseline")


# ─────────────────────────────────────────────────────────────────────
# Fix #2 — _section_regulation_level (doc_04d.py) + frontmatter
# ─────────────────────────────────────────────────────────────────────

def _build_omnibank_state(applicable_regs: list[str]) -> dict:
    """Minimal state that exercises applicability_context lookup."""
    return {
        "company_context": {
            "company_name": "OmniBank Financial Systems S.A.",
            "sector": "Banking & Financial Services",
            "applicable_regs": applicable_regs,
        },
        "company_facts": {
            "name": "OmniBank Financial Systems S.A.",
            "sector": "Banking & Financial Services",
            "applicable_regs": applicable_regs,
            "scale": "LARGE",
            "employees": 5000,
            "jurisdiction": "Germany (EU)",
            "role": "controller",
            "obligated_party": "controller",
            "complexity_tier": "HIGH",
            "data_categories": ["personal_data"],
            "products": ["mobile app", "web platform"],
            "role_obligations": ["controller"],
        },
        "v2_applicable_regs": applicable_regs,
        "applicability_predicates": {
            "GDPR": {"processes_personal_data": True, "controller": True},
            "CRA": {"places_digital_products_eu": True, "manufacturer": True},
            "NIS2": {"banking_sector": True, "essential_entity": True},
            "DORA": {"financial_entity_art_2": True, "credit_institution": True},
            "AI_Act": {"high_risk_ai_annex_iii": True},
        },
        # TinyTask-only fallback MUST NOT trigger here
        "regulations": [],
    }


def test_fix_2_doc_04d_section_3() -> None:
    """Doc 04d §3 must mark NIS2/DORA/AI_Act as YES for case 3 (OmniBank)."""
    print("\n=== Fix #2 — Doc 04d §3 Regulation-Level Owner ===")

    state = _build_omnibank_state(["GDPR", "CRA", "NIS2", "DORA", "AI_Act"])
    rendered = "\n".join(_section_regulation_level(state))

    # The hardcoded TinyTask fallback said NIS2/DORA/AI_Act=NO.
    # The fix must say YES for case 3 with all 5 regs applicable.
    expected_yes = ["GDPR", "CRA", "NIS2", "DORA", "AI Act"]
    for reg in expected_yes:
        if f"| {reg} | YES |" not in rendered:
            fail(f"{reg} should be YES",
                 f"Doc 04d §3 rendered without {reg}=YES:\n{rendered}")
        ok(f"{reg} marked YES")

    # Also: must NOT contain the old hardcoded NO for these regs
    for reg in ["NIS2", "DORA", "AI Act"]:
        if f"| {reg} | NO |" in rendered:
            fail(f"{reg} should NOT be NO",
                 f"Doc 04d §3 still says {reg}=NO:\n{rendered}")
        ok(f"{reg} not hardcoded NO")


def test_fix_2_doc_04d_tinytask_baseline() -> None:
    """Sanity: for case 1 (TinyTask, only GDPR+CRA) the fix doesn't break."""
    print("\n=== Fix #2 sanity — Doc 04d §3 for case 1 (TinyTask) ===")

    state = _build_omnibank_state(["GDPR", "CRA"])
    rendered = "\n".join(_section_regulation_level(state))

    if "| GDPR | YES |" not in rendered:
        fail("GDPR should be YES", f"Doc 04d §3:\n{rendered}")
    ok("GDPR marked YES")
    if "| CRA | YES |" not in rendered:
        fail("CRA should be YES", f"Doc 04d §3:\n{rendered}")
    ok("CRA marked YES")
    if "| NIS2 | NO |" not in rendered:
        fail("NIS2 should be NO for TinyTask", f"Doc 04d §3:\n{rendered}")
    ok("NIS2 correctly NO for TinyTask")


# ─────────────────────────────────────────────────────────────────────
# Fix #3 — _strip_section_header (doc_04a.py)
# ─────────────────────────────────────────────────────────────────────

def test_fix_3_strip_section_header() -> None:
    """Doc 04a §1 Technical Architecture must not have duplicate header."""
    print("\n=== Fix #3 — _strip_section_header ===")

    # Case A: M3 emits the header in the narrative (the bug)
    buggy_narrative = (
        "## 1. Technical Architecture\n\n"
        "OmniBank Financial Systems S.A. operates a hybrid cloud–on-premises estate..."
    )
    cleaned = _strip_section_header(buggy_narrative, "Technical Architecture")
    if cleaned.startswith("## 1. Technical Architecture"):
        fail("duplicate header NOT stripped",
             f"after strip:\n{cleaned[:200]}")
    if "OmniBank Financial Systems" not in cleaned:
        fail("content lost after strip", f"after strip:\n{cleaned[:200]}")
    ok("duplicate '## 1. Technical Architecture' stripped (content preserved)")

    # Case B: M3 omits the header (clean narrative) — must NOT strip random content
    clean_narrative = "OmniBank Financial Systems S.A. operates a hybrid cloud..."
    cleaned = _strip_section_header(clean_narrative, "Technical Architecture")
    if cleaned != clean_narrative:
        fail("clean narrative should pass through unchanged",
             f"got:\n{cleaned[:200]}")
    ok("clean narrative passes through unchanged")

    # Case C: empty/whitespace input
    cleaned = _strip_section_header("", "Technical Architecture")
    if cleaned != "":
        fail("empty input should pass through", f"got {cleaned!r}")
    ok("empty input handled")


# ─────────────────────────────────────────────────────────────────────
# Fix #4 — _active_subdomain_count fallback
# ─────────────────────────────────────────────────────────────────────

def test_fix_4_active_count_fallback() -> None:
    """Doc 04b/c/d active_subdomains must use state['subdomains'] when ontology empty."""
    print("\n=== Fix #4 — _active_subdomain_count fallback ===")

    # Case 3 state: ontology present but subdomains.empty covered; subdomains dict populated
    state = {
        "ontology": {
            "subdomains": {
                "covered": [],  # empty covered list — the bug
                "not_covered": [],
            }
        },
        "subdomains": {
            f"D-{d:02d}.{s}": {"id": f"D-{d:02d}.{s}", "title": "x"}
            for d in range(1, 11)
            for s in range(1, 5)
        },  # 40 entries
    }

    count_04b = _active_count(state)
    count_04c = _active_count_04c(state)
    count_04d = _active_count_04d(state)

    if count_04b != 40:
        fail("Doc 04b _active_count fallback", f"got {count_04b}, expected 40")
    if count_04c != 40:
        fail("Doc 04c _active_subdomain_count fallback", f"got {count_04c}, expected 40")
    if count_04d != 40:
        fail("Doc 04d _active_subdomain_count fallback", f"got {count_04d}, expected 40")

    ok("Doc 04b: 40 (fallback to state['subdomains'])")
    ok("Doc 04c: 40 (fallback to state['subdomains'])")
    ok("Doc 04d: 40 (fallback to state['subdomains'])")

    # And: when ontology covered IS populated, must use that (canonical)
    state["ontology"]["subdomains"]["covered"] = ["D-01.1", "D-02.1", "D-03.1"]
    if _active_count(state) != 3:
        fail("Doc 04b with populated ontology", f"got {_active_count(state)}, expected 3")
    if _active_count_04c(state) != 3:
        fail("Doc 04c with populated ontology", f"got {_active_count_04c(state)}, expected 3")
    if _active_count_04d(state) != 3:
        fail("Doc 04d with populated ontology", f"got {_active_count_04d(state)}, expected 3")
    ok("All 3 docs prefer ontology when populated (3, not 40)")


# ─────────────────────────────────────────────────────────────────────
# Fix #5 — end-to-end Doc 04 §3.1 render (no TinyTask leak)
# ─────────────────────────────────────────────────────────────────────

def test_fix_5_doc_04_section_3_no_leak() -> None:
    """Render Doc 04 §3 with OmniBank state. TinyTask must NOT appear anywhere."""
    print("\n=== Fix #5 — Doc 04 §3.1 Stakeholder Register end-to-end ===")

    state = {
        "stakeholders": [
            {
                "id": "SH-01",
                "role": "Chief Executive Officer (CEO)",
                "responsibilities": "executive_sponsor, ecb_supervised",
                "organisation": "OmniBank Financial Systems S.A.",
                "contact": "ceo@omnibank.example",
                "influence": "HIGH",
                "interest": "HIGH",
            },
            {
                "id": "SH-02",
                "role": "Chief Information Security Officer (CISO)",
                "responsibilities": "security_lead, dedicated_org_100_plus",
                "organisation": "OmniBank Financial Systems S.A.",
                "contact": "ciso@omnibank.example",
                "influence": "HIGH",
                "interest": "HIGH",
            },
            {
                "id": "SH-03",
                "role": "Data Protection Officer (DPO)",
                "responsibilities": "gdpr_compliance, bafin_oversight",
                "organisation": "OmniBank Financial Systems S.A.",
                "contact": "dpo@omnibank.example",
                "influence": "MEDIUM",
                "interest": "HIGH",
            },
            {
                "id": "SH-04",
                "role": "Chief Risk Officer (CRO)",
                "responsibilities": "dora_ict_risk, operational_resilience",
                "organisation": "OmniBank Financial Systems S.A.",
                "contact": "cro@omnibank.example",
                "influence": "MEDIUM",
                "interest": "MEDIUM",
            },
        ],
        "company_context": {
            "company_name": "OmniBank Financial Systems S.A.",
            "sector": "Banking & Financial Services",
            "applicable_regs": ["AI_Act", "CRA", "DORA", "GDPR", "NIS2"],
        },
    }

    rows = _stakeholders(state)
    rendered = "\n".join(_section_3_stakeholders(rows))

    if "TinyTask" in rendered:
        fail("Doc 04 §3.1 leak",
             f"TinyTask leaked into Doc 04 §3.1:\n{rendered}")
    if "tinytask" in rendered.lower():
        fail("Doc 04 §3.1 leak",
             f"tinytask (case-insensitive) leaked:\n{rendered}")
    if "OmniBank" not in rendered:
        fail("Doc 04 §3.1 missing OmniBank",
             f"OmniBank not found:\n{rendered}")

    ok("TinyTask / tinytask.pt: 0 leaks in §3.1")
    ok("OmniBank present in §3.1")

    # Also verify §3.2 influence matrix doesn't have TinyTask leakage
    if "tinytask" in rendered.lower():
        fail("Doc 04 §3.2 leak",
             f"tinytask leaked into §3.2:\n{rendered}")
    ok("TinyTask: 0 leaks in §3.2 (Influence Matrix)")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"{YELLOW}CORR-072 — Isolated Fix Verification{RESET}")
    print("=" * 60)
    test_fix_1_no_org_inheritance()
    test_fix_2_doc_04d_section_3()
    test_fix_2_doc_04d_tinytask_baseline()
    test_fix_3_strip_section_header()
    test_fix_4_active_count_fallback()
    test_fix_5_doc_04_section_3_no_leak()
    print()
    print(f"{GREEN}═══════════════════════════════════════════════════════{RESET}")
    print(f"{GREEN}  ALL FIXES VERIFIED — CORR-072 Sprint S1 complete{RESET}")
    print(f"{GREEN}═══════════════════════════════════════════════════════{RESET}")


if __name__ == "__main__":
    main()
