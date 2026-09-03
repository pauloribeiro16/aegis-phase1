"""Tests for CORR-OBJ-14: run metadata reproducibility snapshot.

OBJECTIVES_CONTRACT §2.2 — OBJ-14 [H] "Reproducibility / comparability:
same input + model + specs → comparable outputs across runs and models".

What we verify here:

1. Two identical ``RunMetadata`` instances produce the same JSON and the
   same ``hash()`` (deterministic contract).
2. A difference in ANY field produces a different ``hash()`` (avalanche).
3. ``validate_gate_mode`` rejects any value outside ``{warn, hard}``
   (closed vocabulary from OBJECTIVES_CONTRACT §5.1).
4. ``from_env`` honours the env-var fallback and validates it.
5. ``is_comparable_to`` and ``diff_fields`` give the right answer for
   various permutations.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from aegis_phase1.runs.metadata import (
    VALID_GATE_MODES,
    InvalidGateModeError,
    RunMetadata,
    from_env,
    validate_gate_mode,
)

# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────


def _make_metadata(**overrides) -> RunMetadata:
    """Build a representative ``RunMetadata`` with sensible defaults."""
    defaults = {
        "run_id": "run-001",
        "case_id": "case1-tinytask",
        "model": "gemma4:e4b",
        "provider": "ollama",
        "quantization": "Q4_K_M",
        "spec_versions": {
            "P1B-LLM-01-INTERPRETATION": "1.0.0",
            "P1B-LLM-02-RATIONALE": "1.0.0",
            "P1C-LLM-01-OVERLAP-CLASSIFICATION": "1.0.0",
        },
        "gate_mode": "hard",
        "started_at": "2026-09-03T10:00:00+00:00",
        "ended_at": "2026-09-03T10:15:00+00:00",
    }
    defaults.update(overrides)
    return RunMetadata(**defaults)


# ────────────────────────────────────────────────────────────────────
# 1. Determinism: identical inputs → identical output
# ────────────────────────────────────────────────────────────────────


def test_identical_metadata_yields_same_json():
    a = _make_metadata()
    b = _make_metadata()
    assert a.to_json() == b.to_json(), "to_json() must be byte-stable for equal inputs"


def test_identical_metadata_yields_same_hash():
    a = _make_metadata()
    b = _make_metadata()
    assert a.hash() == b.hash(), "hash() must be deterministic"
    # SHA-256 hex digests are 64 chars.
    assert re.fullmatch(r"[0-9a-f]{64}", a.hash())


def test_to_dict_is_json_serialisable():
    a = _make_metadata()
    d = a.to_dict()
    # Round-trip via json.dumps / loads must not change the dict.
    roundtrip = json.loads(json.dumps(d))
    assert roundtrip == d


def test_spec_versions_are_sorted_in_to_dict():
    """The spec_versions mapping must be emitted in stable key order."""
    m = _make_metadata(
        spec_versions={
            "P1C-LLM-03-STRATEGIC-SYNTHESIS": "1.0.0",
            "P1B-LLM-01-INTERPRETATION": "1.0.0",
            "P1C-LLM-01-OVERLAP-CLASSIFICATION": "1.0.0",
        },
    )
    keys = list(m.to_dict()["spec_versions"].keys())
    assert keys == sorted(keys)


# ────────────────────────────────────────────────────────────────────
# 2. Avalanche: any field change → different hash
# ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "field,new_value",
    [
        ("run_id", "run-002"),
        ("case_id", "case2-secureborder"),
        ("model", "qwen:7b"),
        ("provider", "transformers"),
        ("quantization", "Q5_K_M"),
        ("gate_mode", "warn"),
        ("started_at", "2026-09-03T11:00:00+00:00"),
        ("ended_at", "2026-09-03T11:15:00+00:00"),
    ],
)
def test_single_field_change_yields_different_hash(field, new_value):
    a = _make_metadata()
    b = _make_metadata(**{field: new_value})
    assert a.hash() != b.hash(), (
        f"hash must change when {field!r} changes; both produced {a.hash()!r}"
    )


def test_spec_versions_change_yields_different_hash():
    a = _make_metadata()
    b = _make_metadata(
        spec_versions={
            "P1B-LLM-01-INTERPRETATION": "1.0.1",  # bumped
            "P1B-LLM-02-RATIONALE": "1.0.0",
            "P1C-LLM-01-OVERLAP-CLASSIFICATION": "1.0.0",
        },
    )
    assert a.hash() != b.hash()


def test_hash_avalanche_unrelated_to_equality():
    """Even a small change in any field must flip the hash."""
    a = _make_metadata(run_id="run-001")
    b = _make_metadata(run_id="run-002")
    # Hashes should differ in many hex positions, not just the last.
    differing = sum(1 for x, y in zip(a.hash(), b.hash(), strict=False) if x != y)
    assert differing >= 8, f"expected avalanche (>=8 chars differ), got {differing}"


# ────────────────────────────────────────────────────────────────────
# 3. validate_gate_mode: closed vocabulary
# ────────────────────────────────────────────────────────────────────


def test_validate_gate_mode_accepts_warn():
    assert validate_gate_mode("warn") == "warn"


def test_validate_gate_mode_accepts_hard():
    assert validate_gate_mode("hard") == "hard"


def test_validate_gate_mode_accepts_case_insensitive():
    assert validate_gate_mode("HARD") == "hard"
    assert validate_gate_mode("Hard") == "hard"
    assert validate_gate_mode("WARN") == "warn"


def test_validate_gate_mode_default_is_warn():
    """Unset env-var → 'warn' (the interactive-development default)."""
    assert validate_gate_mode(None) == "warn"


@pytest.mark.parametrize(
    "value",
    [
        "soft",
        "strict",
        "off",
        "none",
        "production",
        "",  # empty
    ],
)
def test_validate_gate_mode_rejects_invalid_values(value):
    with pytest.raises(InvalidGateModeError) as excinfo:
        validate_gate_mode(value)
    assert "AEGIS_GATE_MODE" in str(excinfo.value)
    assert repr(value) in str(excinfo.value) or value in str(excinfo.value)


def test_validate_gate_mode_strips_whitespace_around_valid_token():
    """Leading/trailing whitespace around a valid token is tolerated (stripped)."""
    assert validate_gate_mode("  warn  ") == "warn"
    assert validate_gate_mode("\thard\n") == "hard"


def test_validate_gate_mode_rejects_padded_invalid_token():
    """Whitespace + invalid token must still be rejected."""
    with pytest.raises(InvalidGateModeError):
        validate_gate_mode("  strict  ")


def test_run_metadata_rejects_invalid_gate_mode_at_construction():
    """The constructor also enforces the closed vocabulary."""
    with pytest.raises(InvalidGateModeError):
        RunMetadata(
            run_id="r",
            case_id="c",
            model="m",
            provider="p",
            quantization="q",
            spec_versions={},
            gate_mode="strict",  # not in {warn, hard}
            started_at="2026-09-03T10:00:00+00:00",
        )


# ────────────────────────────────────────────────────────────────────
# 4. from_env: env-var fallback + validation
# ────────────────────────────────────────────────────────────────────


def test_from_env_reads_hard_mode(monkeypatch):
    monkeypatch.setenv("AEGIS_GATE_MODE", "hard")
    m = from_env(
        run_id="r1",
        case_id="case1-tinytask",
        model="gemma4:e4b",
        provider="ollama",
    )
    assert m.gate_mode == "hard"
    assert m.case_id == "case1-tinytask"


def test_from_env_reads_warn_mode(monkeypatch):
    monkeypatch.setenv("AEGIS_GATE_MODE", "warn")
    m = from_env(
        run_id="r2",
        case_id="case1-tinytask",
        model="gemma4:e4b",
        provider="ollama",
    )
    assert m.gate_mode == "warn"


def test_from_env_default_is_warn(monkeypatch):
    monkeypatch.delenv("AEGIS_GATE_MODE", raising=False)
    m = from_env(
        run_id="r3",
        case_id="case1-tinytask",
        model="gemma4:e4b",
        provider="ollama",
    )
    assert m.gate_mode == "warn"


def test_from_env_rejects_invalid_gate_mode(monkeypatch):
    monkeypatch.setenv("AEGIS_GATE_MODE", "strict")  # invalid
    with pytest.raises(InvalidGateModeError):
        from_env(
            run_id="r4",
            case_id="case1-tinytask",
            model="gemma4:e4b",
            provider="ollama",
        )


def test_from_env_sets_started_at_when_missing(monkeypatch):
    monkeypatch.delenv("AEGIS_GATE_MODE", raising=False)
    m = from_env(
        run_id="r5",
        case_id="case1-tinytask",
        model="gemma4:e4b",
        provider="ollama",
    )
    # ISO-8601 UTC, e.g. "2026-09-03T10:00:00+00:00"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", m.started_at)


def test_from_env_honours_explicit_started_at(monkeypatch):
    monkeypatch.delenv("AEGIS_GATE_MODE", raising=False)
    m = from_env(
        run_id="r6",
        case_id="case1-tinytask",
        model="gemma4:e4b",
        provider="ollama",
        started_at="2026-09-03T10:00:00+00:00",
    )
    assert m.started_at == "2026-09-03T10:00:00+00:00"


# ────────────────────────────────────────────────────────────────────
# 5. Comparability + diff
# ────────────────────────────────────────────────────────────────────


def test_is_comparable_to_returns_true_for_identical_config():
    a = _make_metadata()
    b = _make_metadata(run_id="DIFFERENT", started_at="OTHER")  # config equal
    assert a.is_comparable_to(b)


def test_is_comparable_to_returns_false_for_different_case():
    a = _make_metadata()
    b = _make_metadata(case_id="case2-secureborder")
    assert not a.is_comparable_to(b)


def test_is_comparable_to_returns_false_for_different_model():
    a = _make_metadata()
    b = _make_metadata(model="qwen:7b")
    assert not a.is_comparable_to(b)


def test_is_comparable_to_returns_false_for_different_provider():
    a = _make_metadata()
    b = _make_metadata(provider="transformers")
    assert not a.is_comparable_to(b)


def test_is_comparable_to_returns_false_for_different_spec_versions():
    a = _make_metadata()
    b = _make_metadata(
        spec_versions={
            "P1B-LLM-01-INTERPRETATION": "1.0.1",  # bumped
            "P1B-LLM-02-RATIONALE": "1.0.0",
            "P1C-LLM-01-OVERLAP-CLASSIFICATION": "1.0.0",
        },
    )
    assert not a.is_comparable_to(b)


def test_diff_fields_lists_changes():
    a = _make_metadata()
    b = _make_metadata(
        case_id="case2-secureborder",
        model="qwen:7b",
    )
    diff = RunMetadata.diff_fields(a, b)
    assert set(diff.keys()) == {"case_id", "model"}
    assert diff["case_id"] == ("case1-tinytask", "case2-secureborder")
    assert diff["model"] == ("gemma4:e4b", "qwen:7b")


def test_diff_fields_empty_for_identical():
    a = _make_metadata()
    b = _make_metadata()
    assert RunMetadata.diff_fields(a, b) == {}


# ────────────────────────────────────────────────────────────────────
# 6. Imports + module surface
# ────────────────────────────────────────────────────────────────────


def test_valid_gate_modes_is_frozen_set():
    assert isinstance(VALID_GATE_MODES, frozenset)
    assert frozenset({"warn", "hard"}) == VALID_GATE_MODES


def test_run_metadata_is_frozen():
    """Frozen dataclass — assignment must raise."""
    import dataclasses
    m = _make_metadata()
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.run_id = "x"  # type: ignore[misc]


def test_metadata_module_can_be_imported():
    """Sanity: top-level import works in a fresh subprocess."""
    code = (
        "from aegis_phase1.runs.metadata import RunMetadata, from_env, validate_gate_mode;"
        "print('OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
        env={**os.environ, "PYTHONPATH": "src"},
    )
    assert result.returncode == 0, f"import failed: {result.stderr}"
    assert "OK" in result.stdout
