"""Tests for CORR-076 — functional vocabulary in LLM prompts (CORR-076 / SC-2026-19).

Contract SC-2026-19 / execution/SPEC.md (SP-2026-19) requires that all 9
narrative-prompt functions across doc_04a/04b/04c/04d/05/07/07b inject a
functional context block (role roster + applicable capabilities) and remove
all person-name references (``Founder``, ``CEO acting as``, ``CTO as``,
``Lead Developer``, ``2 founders``, ``acting as DPO``, ``acting as CISO``).

These tests verify:

  1. ``build_functional_context(tier, applicable_regs)`` is deterministic and
     lists the 5 ROLE_VOCABULARY members.
  2. Empty ``applicable_regs`` returns the role roster only (no capability
     block).
  3. Role roster lines include ``FTE`` and ``reports to``.
  4. ``extract_tier_and_regs`` is defensive against missing/oddly-shaped
     ``company_context``.
  5. None of the 9 prompts contains banned phrases in either its source code
     or its runtime output.
  6. Each prompt source declares the 5 functional roles and an explicit
     "DO NOT name individuals" disclaimer.
"""
from __future__ import annotations

import inspect

import pytest

from aegis_phase1.v2.output import (
    doc_04a,
    doc_04b,
    doc_04c,
    doc_04d,
    doc_05,
    doc_07,
    doc_07b,
)
from aegis_phase1.v2.output._functional_prompts import (
    build_functional_context,
    extract_tier_and_regs,
)

PROMPTS = [
    (doc_04a, "_technical_architecture_prompt"),
    (doc_04a, "_network_topology_prompt"),
    (doc_04b, "_domain_notes_prompt"),
    (doc_04c, "_risk_narrative_prompt"),
    (doc_04d, "_reporting_lines_prompt"),
    (doc_04d, "_escalation_prompt"),
    (doc_05, "_strategic_prompt"),
    (doc_07, "_strategic_prompt"),
    (doc_07b, "_cross_check_prompt"),
]

BANNED = [
    "Founder",
    "CEO acting as",
    "CTO as",
    "Lead Developer",
    "2 founders",
    "acting as DPO",
    "acting as CISO",
]

ROLES = ["DPO", "CISO", "Engineering", "Operations", "Governance"]
DISCLAIMERS = [
    "DO NOT name individuals",
    "do not name individuals",
    "no person names",
    "functional roles only",
    "function names only",
]


def _max_state() -> dict:
    """Case-3 (MAX) state for exercising prompts (per CONTRACT-075 precedent)."""
    return {
        "company_context": {
            "company_name": "X",
            "employees": 5000,
            "sector": "Banking",
            "scale": "MAX",
            "applicable_regs": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"],
        }
    }


def _exercise_prompt(module, name):
    """Exercise a prompt function with a MAX-tier state, returning its output.

    Returns ``""`` if the call signature does not match (the source-code
    portion of the banned-phrase test still runs against the function source).
    """
    fn = getattr(module, name)
    state = _max_state()
    module_name = module.__name__
    try:
        if module_name.endswith("doc_04a"):
            inv = {
                "systems": [],
                "cloud_services": [],
                "auth_systems": [],
                "data_stores": [],
                "data_flows": [],
            }
            sig = inspect.signature(fn)
            if len(sig.parameters) >= 3:
                return fn(state, inv, "summary")
            return fn(state, inv)
        if module_name.endswith("doc_04b"):
            return fn("D-01", 1, 2, 1, [], state)
        if module_name.endswith("doc_04c"):
            return fn(state, [], [])
        if module_name.endswith("doc_04d"):
            return fn(state)
        if module_name.endswith(("doc_05", "doc_07")):
            return fn(state, [])
        if module_name.endswith("doc_07b"):
            return fn(state, [])
    except TypeError:
        return ""
    return ""


# ─────────────────────────────────────────────────────────────────────
# Helper unit tests
# ─────────────────────────────────────────────────────────────────────


def test_helper_deterministic() -> None:
    a = build_functional_context("MAX", ("GDPR", "CRA", "NIS2", "DORA", "AI_Act"))
    b = build_functional_context("MAX", ("GDPR", "CRA", "NIS2", "DORA", "AI_Act"))
    assert a == b
    assert len(a) > 100


def test_helper_accepts_list_input() -> None:
    """Defensive: caller-side may pass either a list or a tuple."""
    a = build_functional_context("MAX", ["GDPR", "CRA"])
    b = build_functional_context("MAX", ("GDPR", "CRA"))
    assert a == b


def test_helper_empty_regs_returns_role_roster() -> None:
    out = build_functional_context("MICRO", ())
    assert "DPO" in out
    assert "Capabilities" not in out


def test_helper_includes_all_5_roles() -> None:
    out = build_functional_context("MAX", ("GDPR", "CRA"))
    for role in ROLES:
        assert role in out, f"missing role {role}"


def test_helper_role_roster_has_fte_and_reports_to() -> None:
    out = build_functional_context("MAX", ("GDPR",))
    roles_section = out.split("Capabilities")[0]
    assert "FTE" in roles_section
    assert "reports to" in roles_section


# ─────────────────────────────────────────────────────────────────────
# extract_tier_and_regs
# ─────────────────────────────────────────────────────────────────────


def test_extract_tier_and_regs() -> None:
    state = {"company_context": {"scale": "MAX", "applicable_regs": ["GDPR", "CRA"]}}
    tier, regs = extract_tier_and_regs(state)
    assert tier == "MAX"
    assert regs == ("GDPR", "CRA")


def test_extract_tier_fallback_to_micro() -> None:
    state = {"company_context": {}}
    tier, regs = extract_tier_and_regs(state)
    assert tier == "MICRO"
    assert regs == ()


def test_extract_tier_fallback_invalid_scale() -> None:
    """An unknown scale string falls back to MICRO rather than raising."""
    state = {"company_context": {"scale": "unknown", "applicable_regs": ["GDPR"]}}
    tier, regs = extract_tier_and_regs(state)
    assert tier == "MICRO"
    assert regs == ("GDPR",)


# ─────────────────────────────────────────────────────────────────────
# 9-prompt regression tests
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("module,name", PROMPTS)
def test_no_banned_phrases(module, name) -> None:
    fn = getattr(module, name)
    src = inspect.getsource(fn)
    out = _exercise_prompt(module, name)
    combined = src + out
    for phrase in BANNED:
        assert phrase not in combined, f"{module.__name__}.{name}: banned phrase {phrase!r}"


@pytest.mark.parametrize("module,name", PROMPTS)
def test_contains_all_5_roles(module, name) -> None:
    fn = getattr(module, name)
    src = inspect.getsource(fn)
    for role in ROLES:
        assert role in src, f"{module.__name__}.{name}: missing role {role}"


@pytest.mark.parametrize("module,name", PROMPTS)
def test_contains_disclaimer(module, name) -> None:
    fn = getattr(module, name)
    src = inspect.getsource(fn)
    assert any(d in src for d in DISCLAIMERS), (
        f"{module.__name__}.{name}: missing disclaimer; expected one of {DISCLAIMERS}"
    )


@pytest.mark.parametrize("module,name", PROMPTS)
def test_prompt_output_non_empty(module, name) -> None:
    """C10: prompts must continue to produce non-empty strings when exercised."""
    out = _exercise_prompt(module, name)
    assert out and out.strip(), f"{module.__name__}.{name} produced empty output"
