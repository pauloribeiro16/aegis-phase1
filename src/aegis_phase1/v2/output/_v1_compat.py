"""CORR-037-T4c: v1-compat shim for the 10 output consumers.

The 8 doc_*.py renderers + xlsx_generator.py were written against the v1
state shape (state['company_context'], state['ontology'],
state['architecture_inventory'], state['stakeholders'], state['business_goals'],
state['regulations']). After T4 removed the v1 loaders, the orchestrator
populated these keys via the T4b shim. This module MOVES that conversion
to the consumer side: each consumer calls a function here to obtain
the v1-shaped data it needs, derived from the v2_* state keys.

Functionally identical to the T4b shim, but lives in the output package
(rather than the orchestrator) so consumers are explicit about their
data dependencies. When all 10 consumers are migrated, this module
shrinks to nothing and is removed.

Public API (one function per v1 state key):
    get_company_context(state)     -> dict | None
    get_regulations(state)         -> list[str]
    get_ontology(state)            -> dict (with regulations + overlaps + ...)
    get_architecture_inventory(state) -> dict[str, list[dict]]
    get_stakeholders(state)        -> list[dict]
    get_business_goals(state)      -> list[dict]
    get_preprocessing(state)       -> dict

Each function reads the corresponding v2_* state key and converts to
the v1 shape. If v2 keys are absent, returns the v1 key from the
state (backwards compat with persisted state.json files from the v2.1
era that may still have v1 keys).
"""

from __future__ import annotations

from typing import Any

from aegis_phase1.models import ComplexityTier
from aegis_phase1.v2.state import CompanyContext as _CompanyContext


def _v2_company_facts(state: dict) -> Any | None:
    return state.get("v2_company_facts")


def _v2_applicable_regs(state: dict) -> list[str]:
    return list(state.get("v2_applicable_regs", []))


def _v2_company_profile(state: dict) -> Any | None:
    return state.get("v2_company_profile")


def _v2_pairs(state: dict) -> list[Any]:
    return list(state.get("v2_pairs", []))


def _v2_audit_both_pass(state: dict) -> bool:
    return bool(state.get("v2_audit_both_pass", False))


def _estimate_complexity_tier(facts: Any) -> str:
    """Estimate complexity tier from v2 CompanyFacts (employees + scale).

    T4c shim approximation. The proper tier comes from a follow-up
    tier-assignment step in SP-B (CORR-038). Until then, the heuristic
    is: HIGH >= 250 employees, MEDIUM >= 50, else LOW.
    """
    employees = getattr(facts, "employees", 0) or 0
    if employees >= 250:
        return ComplexityTier.HIGH.value
    if employees >= 50:
        return ComplexityTier.MEDIUM.value
    return ComplexityTier.LOW.value


def get_company_context(state: dict) -> dict[str, Any] | None:
    """Return v1-shape company_context dict (or None if no data)."""
    facts = _v2_company_facts(state)
    if facts is not None:
        return _CompanyContext(
            company_name=facts.name,
            sector=facts.sector,
            jurisdiction=facts.jurisdiction,
            employees=facts.employees,
            revenue=float(facts.revenue_eur),
            scale=facts.scale,
            applicable_regs=_v2_applicable_regs(state),
            complexity_tier=_estimate_complexity_tier(facts),
            security_fte=facts.security_fte or 0.0,
            tech_stack=list(facts.tech_stack or []),
        ).model_dump()
    return state.get("company_context")


def get_regulations(state: dict) -> list[str]:
    """Return list of applicable regulation short names."""
    v2 = _v2_applicable_regs(state)
    if v2:
        return v2
    return list(state.get("regulations", []))


def get_ontology(state: dict) -> dict[str, Any]:
    """Return v1-shape ontology dict (regulations + overlaps)."""
    pairs = _v2_pairs(state)
    return {
        "regulations": _v2_applicable_regs(state),
        "overlaps": [p.model_dump() for p in pairs],
        "source_regulations": {},
        "stacks": [],
    }


def get_architecture_inventory(state: dict) -> dict[str, list[dict[str, Any]]]:
    """Return v1-shape architecture_inventory (N.1-N.6 buckets)."""
    profile = _v2_company_profile(state)
    if profile is not None:
        arch = profile.architecture
        return {
            "N.1_systems": list(arch.systems),
            "N.2_auth": list(arch.auth_systems),
            "N.3_cloud": list(arch.cloud_services),
            "N.4_data_flows": list(arch.data_flows),
            "N.5_data_stores": list(arch.data_stores),
            "N.6_other": [],
        }
    return dict(state.get("architecture_inventory", {}))


def get_stakeholders(state: dict) -> list[dict[str, Any]]:
    """Return v1-shape stakeholders (list of dicts)."""
    profile = _v2_company_profile(state)
    if profile is not None:
        return [s.model_dump() for s in profile.stakeholders]
    return list(state.get("stakeholders", []))


def get_business_goals(state: dict) -> list[dict[str, Any]]:
    """Return v1-shape business_goals (list of dicts)."""
    profile = _v2_company_profile(state)
    if profile is not None:
        return [g.model_dump() for g in profile.business_goals]
    return list(state.get("business_goals", []))


def get_preprocessing(state: dict) -> dict[str, Any]:
    """Return v1-shape preprocessing (cross_regulation + audit)."""
    pairs = _v2_pairs(state)
    return {
        "cross_regulation": [p.model_dump() for p in pairs],
        "audit_both_pass": _v2_audit_both_pass(state),
    }


def get_taxonomy_entries(state: dict) -> list[dict[str, Any]]:
    """Return v1-shape taxonomy_entries. No v2 source — empty list."""
    return list(state.get("taxonomy_entries", []))


__all__ = [
    "get_company_context",
    "get_regulations",
    "get_ontology",
    "get_architecture_inventory",
    "get_stakeholders",
    "get_business_goals",
    "get_preprocessing",
    "get_taxonomy_entries",
]
