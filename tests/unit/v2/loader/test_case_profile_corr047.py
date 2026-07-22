"""CORR-047 — 4 new categories of company context data.

Pre-CORR-047 the loader returned 25 fields. Post-CORR-047 it returns
29 (the 4 new ones being implementation_readiness,
regulatory_classification, role_matrix, regulatory_interactions).

These tests cover:
  (a) test_implementation_readiness_loaded
      case1 YAML has 12 IR areas; verify the loader returns a
      populated ImplementationReadiness with the right Enum values.

  (b) test_regulatory_classification_loaded
      case1 has NIS2/DORA/AI_Act = NOT_APPLICABLE and CRA = CLASS_I.

  (c) test_role_matrix_loaded
      case1 has gdpr=controller, cra=manufacturer, nis2/dora/ai=not_applicable.

  (d) test_regulatory_interactions_loaded
      case1 has 1 temporal_conflict (TI-01 GDPR-CRA) and 5 negative
      analyses (NA-01..NA-05).

  (e) test_loader_tolerates_missing_yaml
      Build a tmp case with only the 3 original company YAMLs
      (no implementation_readiness, no regulatory_classification,
      no role_matrix, no interactions). Loader must return
      gracefully with 4 fields == None and 4 WARNINGs logged.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from aegis_phase1.v2.loader.case_profile import (
    CaseProfileLoader,
    CompanyProfile,
)


@pytest.fixture(scope="module")
def ctx() -> CompanyProfile:
    """Module-scoped: shared CompanyProfile for case1-tinytask."""
    return CaseProfileLoader(case_path=Path("cases/case1-tinytask")).load()


# ──────────────────────────────────────────────────────────────────
# (a) ImplementationReadiness
# ──────────────────────────────────────────────────────────────────


def test_implementation_readiness_loaded(ctx: CompanyProfile) -> None:
    """12 IR areas populated with YES/NO/PARTIAL values."""
    assert ctx.implementation_readiness is not None, (
        "CORR-047: implementation_readiness not loaded"
    )
    ir = ctx.implementation_readiness
    # All 12 areas present
    expected = [
        "ciso", "dpo", "information_security_policy", "risk_assessment",
        "incident_response", "business_continuity", "backup", "access_control",
        "vulnerability_management", "third_party_risk", "security_awareness",
        "audit_logging",
    ]
    for area in expected:
        assert hasattr(ir, area), f"CORR-047: IR area '{area}' missing"
        v = getattr(ir, area)
        assert v.value in {"YES", "NO", "PARTIAL"}, f"IR.{area} = {v.value}"
    # Spot-check expected values from the case1 YAML
    assert ir.ciso.value == "NO"
    assert ir.dpo.value == "NO"
    assert ir.backup.value == "YES"
    assert ir.audit_logging.value == "PARTIAL"


# ──────────────────────────────────────────────────────────────────
# (b) RegulatoryClassification
# ──────────────────────────────────────────────────────────────────


def test_regulatory_classification_loaded(ctx: CompanyProfile) -> None:
    """5 enums populated (case1: NIS2/DORA/AI_Act=NOT_APPLICABLE, CRA=CLASS_I)."""
    assert ctx.regulatory_classification is not None, (
        "CORR-047: regulatory_classification not loaded"
    )
    rc = ctx.regulatory_classification
    assert rc.nis2_entity_class.value == "NOT_APPLICABLE"
    assert rc.dora_article_2_entity.value == "NOT_APPLICABLE"
    assert rc.cra_product_class.value == "CLASS_I"
    assert rc.ai_system_classification.value == "NOT_APPLICABLE"
    assert rc.critical_or_important_ict.value == "NOT_APPLICABLE"


# ──────────────────────────────────────────────────────────────────
# (c) RoleMatrix
# ──────────────────────────────────────────────────────────────────


def test_role_matrix_loaded(ctx: CompanyProfile) -> None:
    """5 regs × role entries; case1 has gdpr=controller, cra=manufacturer."""
    assert ctx.role_matrix is not None, "CORR-047: role_matrix not loaded"
    rm = ctx.role_matrix
    assert rm.gdpr.role == "controller"
    assert rm.cra.role == "manufacturer"
    assert rm.nis2.role == "not_applicable"
    assert rm.dora.role == "not_applicable"
    assert rm.ai_act.role == "not_applicable"
    # Inherited obligations populated for applicable regs
    assert len(rm.gdpr.inherited_obligations) >= 1
    assert len(rm.cra.inherited_obligations) >= 1
    # Native compliance = False for all (company is not in full compliance yet)
    assert rm.gdpr.native_compliance is False
    assert rm.cra.native_compliance is False


# ──────────────────────────────────────────────────────────────────
# (d) RegulatoryInteractions
# ──────────────────────────────────────────────────────────────────


def test_regulatory_interactions_loaded(ctx: CompanyProfile) -> None:
    """Layer 3 scans: 1 temporal_conflict (TI-01) + 5 negative_analyses."""
    assert ctx.regulatory_interactions is not None, (
        "CORR-047: regulatory_interactions not loaded"
    )
    ri = ctx.regulatory_interactions
    # 1 temporal conflict
    assert len(ri.temporal_conflicts) == 1
    tc = ri.temporal_conflicts[0]
    assert tc.id == "TI-01"
    assert tc.type.value == "TEMPORAL"
    assert "GDPR" in tc.regulations
    assert "CRA" in tc.regulations
    assert "D-04.3" in tc.sub_domains
    # 0 requirement_conflicts, 0 trigger_mismatches
    assert len(ri.requirement_conflicts) == 0
    assert len(ri.trigger_mismatches) == 0
    # 5 negative analyses
    assert len(ri.negative_analyses) == 5
    ids = sorted(na.id for na in ri.negative_analyses)
    assert ids == ["NA-01", "NA-02", "NA-03", "NA-04", "NA-05"]
    # Severities are LOW/MEDIUM/HIGH
    sevs = {na.severity for na in ri.negative_analyses}
    assert sevs.issubset({"LOW", "MEDIUM", "HIGH"})


# ──────────────────────────────────────────────────────────────────
# (e) Loader tolerance: missing YAMLs → None + WARNING
# ──────────────────────────────────────────────────────────────────


def test_loader_tolerates_missing_yaml(tmp_path: Path, caplog) -> None:
    """When the 4 new YAMLs are absent, the loader returns None for each
    field and logs WARNING (does not crash)."""
    # Build a tmp case with only the 3 ORIGINAL company YAMLs
    # (classification, business_goals, stakeholders) and 1 regulatory
    # YAML (applicability). No 4 new YAMLs.
    (tmp_path / "input" / "company").mkdir(parents=True)
    (tmp_path / "input" / "regulatory").mkdir(parents=True)

    (tmp_path / "input" / "company" / "classification.yaml").write_text(
        "company:\n  name: X\n  employees: 1\n  revenue_eur: 0\n  scale: MICRO\n"
        "applicable_regulations: []\n",
        encoding="utf-8",
    )
    (tmp_path / "input" / "company" / "business_goals.yaml").write_text(
        "goals: []\n", encoding="utf-8",
    )
    (tmp_path / "input" / "company" / "stakeholders.yaml").write_text(
        "stakeholders: []\n", encoding="utf-8",
    )
    (tmp_path / "input" / "regulatory" / "applicability.yaml").write_text(
        "applicable_regulations: []\nnon_applicable_regulations: []\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        profile = CaseProfileLoader(case_path=tmp_path).load()

    # 4 new fields are None
    assert profile.implementation_readiness is None
    assert profile.regulatory_classification is None
    assert profile.role_matrix is None
    assert profile.regulatory_interactions is None

    # 4 WARNINGs about missing files
    warning_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("implementation_readiness" in m for m in warning_msgs), (
        f"missing impl_readiness WARNING; got: {warning_msgs}"
    )
    assert any("regulatory_classification" in m for m in warning_msgs), (
        f"missing reg_class WARNING; got: {warning_msgs}"
    )
    assert any("role_matrix" in m for m in warning_msgs), (
        f"missing role_matrix WARNING; got: {warning_msgs}"
    )
    assert any("regulatory_interactions" in m for m in warning_msgs), (
        f"missing reg_interactions WARNING; got: {warning_msgs}"
    )
