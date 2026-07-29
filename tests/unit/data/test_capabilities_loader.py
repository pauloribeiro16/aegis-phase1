"""Tests for src/aegis_phase1/data/loader.py:load_capabilities().

These tests mirror contract SC-2026-17 acceptance criteria C1-C6.
Tier 3 (behavioural) — verifies the loader returns the expected payload,
falls back silently on missing files, and constrains ROLE_VOCABULARY.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml

from aegis_phase1.data import ROLE_VOCABULARY, load_capabilities
from aegis_phase1.data.loader import load_capabilities as _load_capabilities_direct

# ── C1: load_capabilities("D-01") returns dict with non-empty capabilities list ──


def test_capabilities_D01_loads_with_min_3_caps() -> None:
    """D-01 catalog loads with >=3 capabilities, each carrying required keys."""
    payload = load_capabilities("D-01")
    assert isinstance(payload, dict), type(payload)
    caps = payload.get("capabilities", [])
    assert len(caps) >= 3, len(caps)
    for cap in caps:
        assert "id" in cap
        assert "a_function" in cap
        assert "r_function" in cap


# ── C2: load_capabilities("D-04") returns dict with non-empty capabilities list ──


def test_capabilities_D04_loads_with_min_4_caps() -> None:
    """D-04 catalog loads with >=4 capabilities covering IR functions."""
    payload = load_capabilities("D-04")
    assert isinstance(payload, dict), type(payload)
    caps = payload.get("capabilities", [])
    assert len(caps) >= 4, len(caps)
    for cap in caps:
        assert "id" in cap
        assert "a_function" in cap
        assert "r_function" in cap


# ── C3: missing domain_id returns {} silently at DEBUG level ─────────────────


def test_capabilities_missing_returns_empty_silently(caplog: pytest.LogCaptureFixture) -> None:
    """Missing domain returns {} and logs at DEBUG (not WARNING/ERROR)."""
    _load_capabilities_direct.cache_clear()
    with caplog.at_level(logging.DEBUG, logger="aegis_phase1.data.loader"):
        result = _load_capabilities_direct("D-99-NONEXISTENT")
    assert result == {}, result
    debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("D-99-NONEXISTENT" in r.getMessage() for r in debug_records), \
        "Expected DEBUG log mentioning missing domain"
    warning_or_error = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warning_or_error, f"Unexpected warn/error logs: {warning_or_error}"


# ── C4: ROLE_VOCABULARY has exactly 5 elements ──────────────────────────────


def test_role_vocabulary_has_exactly_5() -> None:
    """Vocabulary contains exactly the 5 canonical roles."""
    assert len(ROLE_VOCABULARY) == 5, sorted(ROLE_VOCABULARY)
    expected = {"DPO", "CISO", "Engineering", "Operations", "Governance"}
    assert set(ROLE_VOCABULARY) == expected, sorted(ROLE_VOCABULARY)


# ── C5: every role in shipped YAMLs is within ROLE_VOCABULARY ──────────────


def test_role_vocabulary_in_vocabulary() -> None:
    """a_function / r_function / required_functions entries must be a subset."""
    yaml_dir = Path("data/capabilities")
    yaml_files = sorted(yaml_dir.glob("D-*.yaml"))
    assert yaml_files, "No D-*.yaml found in data/capabilities/"

    roles_used: set[str] = set()
    for ypath in yaml_files:
        parsed = yaml.safe_load(ypath.read_text(encoding="utf-8"))
        for cap in parsed["capabilities"]:
            roles_used.add(cap["a_function"])
            roles_used.add(cap["r_function"])
            for fn in cap.get("required_functions", []) or []:
                roles_used.add(fn)

    assert roles_used <= set(ROLE_VOCABULARY), \
        f"Out-of-vocab roles: {roles_used - set(ROLE_VOCABULARY)}"


# ── C6: capability id is unique within each shipped file ────────────────────


def test_capability_id_unique_per_file() -> None:
    """Within each D-XX.yaml, all capability ids are distinct."""
    for stem in ("D-01", "D-04"):
        path = Path("data/capabilities") / f"{stem}.yaml"
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        ids = [c["id"] for c in parsed["capabilities"]]
        assert len(ids) == len(set(ids)), f"{stem}: duplicate ids {ids}"
