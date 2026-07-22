"""CORR-046 — CaseProfileLoader silent data drops: regression tests.

Pre-CORR-046 the loader dropped 4 rich data fields silently:

  - tech_stack (top-level in classification.yaml)
  - data_stores (YAML key was 'stores:', loader looked for 'data_stores:')
  - data_flows  (YAML key was 'flows:',  loader looked for 'data_flows:')
  - cloud_services (YAML key was 'services:', loader looked for 'cloud_services:')

These tests assert all 4 are populated for the canonical case1.
Plus one holistic test that exercises the full shape.

Reference: execution/CONTRACT-046.md §T4.
"""
from __future__ import annotations

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
# (a) tech_stack loaded from TOP level
# ──────────────────────────────────────────────────────────────────


def test_tech_stack_loaded_from_top_level(ctx: CompanyProfile) -> None:
    """tech_stack is in classification.yaml at the TOP level (line 14),
    outside the `company:` sub-dict. Pre-CORR-046 the loader only
    read the sub-dict and tech_stack came back empty."""
    assert ctx.company.tech_stack == ["AWS", "Firebase", "GitHub Actions"], (
        f"CORR-046: tech_stack not loaded; got {ctx.company.tech_stack}"
    )


# ──────────────────────────────────────────────────────────────────
# (b) data_stores loaded from `stores:` key (not `data_stores:`)
# ──────────────────────────────────────────────────────────────────


def test_data_stores_loaded_from_stores_key(ctx: CompanyProfile) -> None:
    """data_stores.yaml has 'stores:' as root key (3 entries: STORE-01..03).
    Pre-CORR-046 loader looked for 'data_stores:' and got []."""
    stores = ctx.architecture.data_stores
    assert len(stores) == 3, f"CORR-046: n_stores={len(stores)}"
    ids = sorted(s["id"] for s in stores)
    assert ids == ["STORE-01", "STORE-02", "STORE-03"]
    # Each store has the rich fields the prompt needs
    for s in stores:
        assert "id" in s
        assert "name" in s or "type" in s  # at least one of these
    # Sanity: STORE-01 has personal_data and encryption_at_rest
    s1 = next(s for s in stores if s["id"] == "STORE-01")
    assert s1.get("personal_data") is True
    assert s1.get("encryption_at_rest")


# ──────────────────────────────────────────────────────────────────
# (c) data_flows loaded from `flows:` key
# ──────────────────────────────────────────────────────────────────


def test_data_flows_loaded_from_flows_key(ctx: CompanyProfile) -> None:
    """data_flows.yaml has 'flows:' as root key (5 entries: FLOW-01..05)."""
    flows = ctx.architecture.data_flows
    assert len(flows) == 5, f"CORR-046: n_flows={len(flows)}"
    ids = sorted(f["id"] for f in flows)
    assert ids == [f"FLOW-0{i}" for i in range(1, 6)]
    # FLOW-01 has source/destination/data_types/encryption_in_transit
    f1 = next(f for f in flows if f["id"] == "FLOW-01")
    assert f1.get("source")
    assert f1.get("destination")
    assert f1.get("data_types")
    assert f1.get("encryption_in_transit")


# ──────────────────────────────────────────────────────────────────
# (d) cloud_services loaded from `services:` key
# ──────────────────────────────────────────────────────────────────


def test_cloud_services_loaded_from_services_key(ctx: CompanyProfile) -> None:
    """cloud_services.yaml has 'services:' as root key (4 entries: CS-01..04)."""
    services = ctx.architecture.cloud_services
    assert len(services) == 4, f"CORR-046: n_services={len(services)}"
    ids = sorted(s["id"] for s in services)
    assert ids == [f"CS-0{i}" for i in range(1, 5)]
    # CS-01 is AWS with dpa_status signed
    cs1 = next(s for s in services if s["id"] == "CS-01")
    assert cs1.get("provider") == "AWS"
    assert cs1.get("dpa_status") == "signed"


# ──────────────────────────────────────────────────────────────────
# (e) Holistic: all 4 fields populated
# ──────────────────────────────────────────────────────────────────


def test_case_profile_loader_populates_all_expected_fields(ctx: CompanyProfile) -> None:
    """All 4 silent-drop fields are populated for the canonical case1."""
    summary = {
        "tech_stack": ctx.company.tech_stack,
        "data_stores": ctx.architecture.data_stores,
        "data_flows": ctx.architecture.data_flows,
        "cloud_services": ctx.architecture.cloud_services,
    }
    expectations = {
        "tech_stack": 3,        # AWS, Firebase, GitHub Actions
        "data_stores": 3,       # STORE-01..03
        "data_flows": 5,        # FLOW-01..05
        "cloud_services": 4,    # CS-01..04
    }
    for field, expected_n in expectations.items():
        actual = summary[field]
        assert len(actual) == expected_n, (
            f"CORR-046: {field} expected n={expected_n}, got n={len(actual)}"
        )


# ──────────────────────────────────────────────────────────────────
# Helper unit tests (not in contract T4 but useful for regressions)
# ──────────────────────────────────────────────────────────────────


def test_read_yaml_list_multi_tries_aliases_in_order(tmp_path: Path) -> None:
    """_read_yaml_list_multi returns the first non-empty list across aliases."""
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader

    # First alias has data
    f1 = tmp_path / "first_wins.yaml"
    f1.write_text("data_stores:\n  - id: A\n  - id: B\n", encoding="utf-8")
    assert CaseProfileLoader._read_yaml_list_multi(
        f1, ["data_stores", "stores"]
    ) == [{"id": "A"}, {"id": "B"}]

    # First alias is empty list; falls through to second
    f2 = tmp_path / "second_wins.yaml"
    f2.write_text("data_stores: []\nstores:\n  - id: C\n", encoding="utf-8")
    assert CaseProfileLoader._read_yaml_list_multi(
        f2, ["data_stores", "stores"]
    ) == [{"id": "C"}]

    # No alias matches; logs WARNING and returns []
    f3 = tmp_path / "missing.yaml"
    f3.write_text("something_else:\n  - x: 1\n", encoding="utf-8")
    assert CaseProfileLoader._read_yaml_list_multi(
        f3, ["data_stores", "stores"]
    ) == []


def test_read_yaml_list_multi_missing_file_returns_empty(tmp_path: Path) -> None:
    """Missing file → empty list + WARNING (not exception)."""
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader

    missing = tmp_path / "does_not_exist.yaml"
    assert CaseProfileLoader._read_yaml_list_multi(
        missing, ["data_stores", "stores"]
    ) == []


def test_load_company_handles_csv_string_tech_stack(tmp_path: Path) -> None:
    """When tech_stack is a string (\"AWS, Django\"), split by comma."""
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader

    # Build a minimal case with a CSV-style tech_stack at top level
    (tmp_path / "input" / "company").mkdir(parents=True)
    (tmp_path / "input" / "architecture").mkdir(parents=True)
    (tmp_path / "input" / "regulatory").mkdir(parents=True)
    (tmp_path / "input" / "company" / "classification.yaml").write_text(
        "company:\n  name: X\n  employees: 1\n  revenue_eur: 0\n  scale: MICRO\n"
        "tech_stack: 'AWS, Django, PostgreSQL'\n",
        encoding="utf-8",
    )
    (tmp_path / "input" / "regulatory" / "applicability.yaml").write_text(
        "applicable_regulations: []\nnon_applicable_regulations: []\n",
        encoding="utf-8",
    )
    loader = CaseProfileLoader(case_path=tmp_path)
    profile = loader.load()
    assert profile.company.tech_stack == ["AWS", "Django", "PostgreSQL"]
