"""Data loaders for proportionality, role models, regulatory refs.

All hardcoded domain content previously in src/aegis_phase1/v2/output/*.py
is now loaded from data/ YAML files. This module is the single read point.

Usage:
    from aegis_phase1.data.loader import classify_tier, load_role_model, render_tier_text

    tier = classify_tier(employees=5000, sector="Banking & Financial Services", applicable_regs=["GDPR", "CRA", "NIS2", "DORA", "AI_Act"])
    # Returns: "LARGE" (because banking min_tier = LARGE)

    roles = load_role_model(tier)
    # Returns: list of role dicts
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DATA_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "data"


@lru_cache(maxsize=1)
def _load_yaml(path_str: str) -> Any:
    """Cached YAML loader. Cache keyed by file path string."""
    return yaml.safe_load(Path(path_str).read_text())


def load_proportionality_rules() -> dict:
    """Load data/proportionality_rules.yaml."""
    return _load_yaml(str(DATA_ROOT / "proportionality_rules.yaml"))


def load_tier_template(tier: str) -> dict:
    """Load data/tiers/{tier}.yaml."""
    return _load_yaml(str(DATA_ROOT / "tiers" / f"{tier}.yaml"))


def load_role_model(tier: str) -> list[dict]:
    """Load data/role_models/{tier}.yaml and return roles list."""
    return _load_yaml(str(DATA_ROOT / "role_models" / f"{tier}.yaml"))["roles"]


def load_regulatory_refs(regulation: str) -> dict:
    """Load data/regulatory/{regulation}.yaml."""
    return _load_yaml(str(DATA_ROOT / "regulatory" / f"{regulation}.yaml"))


def load_industry_defaults(industry: str) -> dict:
    """Load data/industry_defaults/{industry}.yaml."""
    return _load_yaml(str(DATA_ROOT / "industry_defaults" / f"{industry}.yaml"))


def load_control_maturity(tier: str) -> dict:
    """Load data/control_maturity/{tier}.yaml.

    Returns a dict with keys ``current_by_domain`` (dict[str, int]),
    ``target_by_domain`` (dict[str, int]), and ``tier`` (str).
    """
    return _load_yaml(str(DATA_ROOT / "control_maturity" / f"{tier}.yaml"))


def load_control_evidence(domain_id: str) -> dict:
    """Load data/control_evidence/{domain_id}.yaml.

    Returns a dict with keys ``domain_id``, ``title``, ``controls``.
    """
    return _load_yaml(str(DATA_ROOT / "control_evidence" / f"{domain_id}.yaml"))


def classify_tier(employees: int, sector: str = "", applicable_regs: list[str] | None = None) -> str:
    """Pure function: classify company into MICRO/SMALL/MEDIUM/LARGE/MAX.

    Returns one of: MICRO, SMALL, MEDIUM, LARGE, MAX.
    Applies (in order):
      1. ai_act_overrides (if has high-risk AI)
      2. sector_overrides (Banking/Healthcare/Insurance have min_tier)
      3. default_thresholds (by employees)
    """
    rules = load_proportionality_rules()
    applicable = applicable_regs or []

    ai_overrides = rules.get("ai_act_overrides", {})
    has_high_risk_ai = any(_is_high_risk_ai(reg) for reg in applicable)
    if has_high_risk_ai and "has_high_risk_ai_system" in ai_overrides:
        override_min = ai_overrides["has_high_risk_ai_system"].get("min_tier")
        if override_min:
            return _enforce_min(_classify_by_employees(employees), override_min)

    sector_overrides = rules.get("sector_overrides", {})
    if sector in sector_overrides:
        override_min = sector_overrides[sector].get("min_tier")
        if override_min:
            return _enforce_min(_classify_by_employees(employees), override_min)

    return _classify_by_employees(employees)


def _classify_by_employees(employees: int) -> str:
    """Pure function: employees → tier from default_thresholds."""
    rules = load_proportionality_rules()
    by_emp = rules["default_thresholds"]["by_employees"]
    for tier in ("MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"):
        threshold = by_emp.get(tier)
        if threshold is None or employees < threshold:
            return tier
    return "MAX"


def _enforce_min(actual_tier: str, min_tier: str) -> str:
    """If actual_tier < min_tier (in order MICRO<SMALL<MEDIUM<LARGE<MAX), return min_tier."""
    order = ["MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"]
    if order.index(actual_tier) < order.index(min_tier):
        return min_tier
    return actual_tier


def _is_high_risk_ai(regulation: str) -> bool:
    """AI Act is a high-risk indicator when present in applicable_regs."""
    return regulation == "AI_Act"


def render_tier_text(tier: str, ctx: dict) -> str:
    """Format tier template identity.description with company context.

    ctx: {"name": str, "sector": str, "employees": int|str, "scale": str}
    """
    template = load_tier_template(tier)
    desc = template["identity"]["description"]
    return desc.format(**ctx)


def render_role_table(tier: str) -> str:
    """Render role model as markdown table for Doc 04d."""
    roles = load_role_model(tier)
    lines = [
        "| Role | Person / Team | Reports To | FTE | Backup |",
        "|---|---|---|---|---|",
    ]
    for r in roles:
        lines.append(
            f"| {r.get('role', '-')} | {r.get('person', '-')} | {r.get('reports_to', '-')} | {r.get('fte', '-')} | {r.get('backup', '-')} |"
        )
    return "\n".join(lines)


def get_regulation_articles(regulation: str) -> list[dict]:
    """Get list of article dicts for a regulation."""
    refs = load_regulatory_refs(regulation)
    return refs.get("articles", [])


def get_regulation_summary(regulation: str) -> str:
    """Get phase1_summary text for a regulation."""
    refs = load_regulatory_refs(regulation)
    return refs.get("phase1_summary", "").strip()
