"""Tests for CatalogLoader — loads YAML catalogs + evaluates predicates."""

from __future__ import annotations

import pytest

from aegis_phase1.prompts_v2.catalog import CatalogLoader, CatalogLoadError


def test_catalog_loads_tipo2():
    """tipo2_interpretations.yaml has 8 entries (per v1.0 contract)."""
    cl = CatalogLoader()
    entries = cl.load("tipo2_interpretations")
    assert len(entries) >= 6  # At least 6 (per catalog; may grow)
    # Each entry must have entry_id
    for e in entries:
        assert "entry_id" in e
        assert "applies_to" in e


def test_catalog_loads_tipo3():
    """tipo3_derogations.yaml has 6 entries."""
    cl = CatalogLoader()
    entries = cl.load("tipo3_derogations")
    assert len(entries) >= 5
    for e in entries:
        assert "entry_id" in e
        assert "applies_to" in e
        assert "activation_predicate" in e


def test_filter_applicable_by_regulation():
    """filter_applicable returns entries whose applies_to includes the regulation."""
    cl = CatalogLoader()
    tipo2 = cl.load("tipo2_interpretations")
    gdpr = cl.filter_applicable(tipo2, regulation="GDPR")
    for e in gdpr:
        assert "GDPR" in e["applies_to"]


def test_filter_applicable_excludes_other_regulation():
    """filter_applicable excludes entries not applicable to the given regulation."""
    cl = CatalogLoader()
    tipo2 = cl.load("tipo2_interpretations")
    gdpr = cl.filter_applicable(tipo2, regulation="GDPR")
    for e in gdpr:
        assert "GDPR" in e["applies_to"]
        # Make sure no non-GDPR entries slip through
        assert "AI_Act" not in e.get("applies_to", [])


def test_evaluate_predicate_true():
    """Predicate with valid company_facts returns True."""
    cl = CatalogLoader()
    facts = {"sector": "health", "employees": 100, "is_manufacturer": True}
    assert cl.evaluate_predicate("company_facts.sector == 'health'", facts) is True
    assert cl.evaluate_predicate("company_facts.employees > 50", facts) is True
    assert cl.evaluate_predicate("company_facts.is_manufacturer == True", facts) is True


def test_evaluate_predicate_false():
    """Predicate that evaluates to False returns False."""
    cl = CatalogLoader()
    facts = {"sector": "saas", "employees": 8, "is_manufacturer": False}
    assert cl.evaluate_predicate("company_facts.sector == 'health'", facts) is False
    assert cl.evaluate_predicate("company_facts.employees > 50", facts) is False


def test_evaluate_predicate_insufficient_evidence():
    """Predicate with unknown names returns None (INSUFFICIENT_EVIDENCE)."""
    cl = CatalogLoader()
    facts = {"sector": "health"}
    # 'missing_var' not in facts -> NameError -> None
    assert cl.evaluate_predicate("company_facts.missing_var == 1", facts) is None


def test_evaluate_predicate_empty():
    """Empty predicate returns True (no constraint = always applicable)."""
    cl = CatalogLoader()
    assert cl.evaluate_predicate("", {"sector": "health"}) is True
    assert cl.evaluate_predicate("   ", {"sector": "health"}) is True


def test_invalid_catalog_raises():
    """Loading a non-existent catalog raises CatalogLoadError."""
    cl = CatalogLoader()
    with pytest.raises(CatalogLoadError):
        cl.load("nonexistent_catalog")


def test_evaluate_predicates_batch():
    """evaluate_predicates returns (entry, verdict) tuples."""
    cl = CatalogLoader()
    tipo3 = cl.load("tipo3_derogations")
    facts = {"employees": 5, "annual_revenue": 1000000, "annual_balance": 1000000}
    results = cl.evaluate_predicates(tipo3, facts)
    assert len(results) == len(tipo3)
    for entry, verdict in results:
        assert isinstance(entry, dict)
        assert verdict in (True, False, None)
