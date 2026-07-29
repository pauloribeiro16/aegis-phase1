"""Data layer re-exports.

All hardcoded domain content previously in src/aegis_phase1/v2/output/*.py
is now loaded from data/ YAML files. This package is the single read point.
"""
from aegis_phase1.data.loader import (
    ROLE_VOCABULARY,
    classify_tier,
    get_regulation_articles,
    get_regulation_summary,
    load_capabilities,
    load_control_evidence,
    load_control_maturity,
    load_industry_defaults,
    load_proportionality_rules,
    load_regulatory_refs,
    load_role_model,
    load_tier_template,
    render_role_table,
    render_tier_text,
)

__all__ = [
    "ROLE_VOCABULARY",
    "classify_tier",
    "get_regulation_articles",
    "get_regulation_summary",
    "load_capabilities",
    "load_control_evidence",
    "load_control_maturity",
    "load_industry_defaults",
    "load_proportionality_rules",
    "load_regulatory_refs",
    "load_role_model",
    "load_tier_template",
    "render_role_table",
    "render_tier_text",
]
