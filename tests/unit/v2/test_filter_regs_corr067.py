"""CORR-067 S4: filter_regs handles dict ctx and empty ontology shim.

Before fix:
  - ctx from Pydantic .model_dump() is a dict
  - getattr(dict, "applicable_regs", []) returns [] (NOT the dict key)
  - filter_regs saw applicable_regs=[] and fell through to fallback
  - even the fallback returned [] because _build_ontology_shim
    doesn't populate ontology["subdomains"]["covered"]

After fix:
  - isinstance(ctx, dict) branch uses ctx.get("applicable_regs", [])
  - when ontology shim is empty, fallback to state["subdomains"]
    (the preproc_catalog dict of Subdomain objects)
"""
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# Bug 2 reproduction: getattr on dict returns []
# ────────────────────────────────────────────────────────────────────

def test_filter_regs_dict_ctx_uses_get_not_getattr():
    """The ctx from Pydantic .model_dump() is a dict; use .get(), not getattr."""
    from aegis_phase1.v2.domain.filters.regs import filter_regs

    # Simulate the S1 state shape
    state = {
        "company_context": {
            "company_name": "TinyTask Lda.",
            "sector": "saas",
            "applicable_regs": ["GDPR", "CRA"],
        },
        "ontology": {},  # Empty shim
        "subdomains": {
            "D-01.1": _fake_subdomain("D-01.1", "D-01", ["GDPR", "CRA"]),
            "D-01.2": _fake_subdomain("D-01.2", "D-01", ["GDPR"]),
        },
    }
    result = filter_regs(state, "D-01")
    # Should intersect ontology D-01 regs (GDPR, CRA) with applicable (GDPR, CRA)
    assert result == ["CRA", "GDPR"], f"got {result!r}"


def test_filter_regs_object_ctx_still_works():
    """Legacy object ctx (Pydantic model instance) still works."""
    from aegis_phase1.v2.domain.filters.regs import filter_regs
    from types import SimpleNamespace

    ctx = SimpleNamespace(applicable_regs=["GDPR", "CRA"])
    state = {
        "company_context": ctx,
        "ontology": {},
        "subdomains": {
            "D-01.1": _fake_subdomain("D-01.1", "D-01", ["GDPR", "CRA"]),
        },
    }
    result = filter_regs(state, "D-01")
    assert result == ["CRA", "GDPR"], f"got {result!r}"


# ────────────────────────────────────────────────────────────────────
# Bug 3 reproduction: empty ontology shim, fallback to state['subdomains']
# ────────────────────────────────────────────────────────────────────

def test_filter_regs_falls_back_to_state_subdomains_when_ontology_empty():
    """When _build_ontology_shim returns no 'subdomains' key, fall back."""
    from aegis_phase1.v2.domain.filters.regs import filter_regs

    state = {
        "company_context": {
            "applicable_regs": ["GDPR", "CRA", "AI_Act"],
        },
        "ontology": {
            "regulations": ["GDPR", "CRA", "AI_Act"],
            "overlaps": [],
            "source_regulations": {},  # Empty (current shim)
            "stacks": [],
            # NB: no "subdomains" key
        },
        "subdomains": {
            "D-04.3": _fake_subdomain("D-04.3", "D-04", ["GDPR", "CRA", "AI_Act"]),
            "D-09.1": _fake_subdomain("D-09.1", "D-09", ["GDPR"]),
        },
    }
    result = filter_regs(state, "D-04")
    assert result == ["AI_Act", "CRA", "GDPR"], f"got {result!r}"

    result2 = filter_regs(state, "D-09")
    assert result2 == ["GDPR"], f"got {result2!r}"


def test_filter_regs_ontology_with_covered_still_works():
    """Legacy ontology with subdomains.covered list is honoured (no regression)."""
    from aegis_phase1.v2.domain.filters.regs import filter_regs

    state = {
        "company_context": {"applicable_regs": ["GDPR"]},
        "ontology": {
            "subdomains": {
                "covered": [
                    {"id": "D-01.1", "domain_id": "D-01", "source_regulations": ["GDPR", "CRA"]},
                ],
            },
        },
        "subdomains": {},  # Fallback would be empty
    }
    result = filter_regs(state, "D-01")
    # ontology has CRA but applicable is only GDPR → intersection = GDPR
    assert result == ["GDPR"], f"got {result!r}"


# ────────────────────────────────────────────────────────────────────
# Test the S1 reproduction case (3-reg applicable, full TinyTask)
# ────────────────────────────────────────────────────────────────────

def test_filter_regs_s1_tinytask_reproduction():
    """Reproduce the S1 bug: state with the actual S1 shape, expect 2 regs."""
    from aegis_phase1.v2.domain.filters.regs import filter_regs

    state = {
        "company_context": {
            "applicable_regs": ["GDPR", "CRA"],
        },
        "ontology": {},  # Empty (current shim doesn't populate subdomains)
        "subdomains": {
            # D-01 — Data Protection (GDPR-relevant)
            "D-01.1": _fake_subdomain("D-01.1", "D-01", ["GDPR"]),
            "D-01.2": _fake_subdomain("D-01.2", "D-01", ["GDPR"]),
            "D-01.3": _fake_subdomain("D-01.3", "D-01", ["GDPR"]),
            "D-01.4": _fake_subdomain("D-01.4", "D-01", ["GDPR"]),
            # D-04 — Incident Response
            "D-04.1": _fake_subdomain("D-04.1", "D-04", ["GDPR", "CRA"]),
            "D-04.2": _fake_subdomain("D-04.2", "D-04", ["CRA"]),
            "D-04.3": _fake_subdomain("D-04.3", "D-04", ["GDPR", "CRA"]),
            "D-04.4": _fake_subdomain("D-04.4", "D-04", ["CRA"]),
        },
    }
    # D-01 should intersect [GDPR] with [GDPR, CRA] → [GDPR]
    result_d01 = filter_regs(state, "D-01")
    assert result_d01 == ["GDPR"], f"D-01: {result_d01!r}"

    # D-04 should intersect [GDPR, CRA] with [GDPR, CRA] → [GDPR, CRA]
    result_d04 = filter_regs(state, "D-04")
    assert result_d04 == ["CRA", "GDPR"], f"D-04: {result_d04!r}"


# ────────────────────────────────────────────────────────────────────
# Helper
# ────────────────────────────────────────────────────────────────────

def _fake_subdomain(sid: str, domain_id: str, source_regs: list[str]):
    """Build a fake Subdomain Pydantic-like object."""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=sid,
        domain_id=domain_id,
        source_regulations=source_regs,
        applies_to=source_regs,
    )
