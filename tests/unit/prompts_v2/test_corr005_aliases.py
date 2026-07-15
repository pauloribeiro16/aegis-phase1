"""Backwards-compat alias tests for CORR-005 (Layer 0 -> Regulatory Baseline rename).

These tests verify that:

- ``get_layer0_root()`` still works but emits ``DeprecationWarning``.
- ``Phase1Validator(layer0_root=...)`` still works but emits ``DeprecationWarning``.
- ``Phase1Validator._extract_layer0_refs()`` still works but emits ``DeprecationWarning``.
- The deprecated aliases return identical values to their canonical counterparts.

Kept as a separate file so the CORR-005 alias contract is easy to audit and
remove when the deprecation window closes.
"""
from __future__ import annotations

import warnings

import pytest


# ─────────────────────────────────────────────────────────────────────
# factory.get_layer0_root alias
# ─────────────────────────────────────────────────────────────────────


def test_get_layer0_root_alias_emits_deprecation_warning() -> None:
    """Deprecated get_layer0_root() must still work but emit DeprecationWarning."""
    from aegis_phase1.prompts_v2.factory import (
        get_layer0_root,
        get_regulatory_baseline_root,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        alias_result = get_layer0_root()
        canonical_result = get_regulatory_baseline_root()

    assert alias_result == canonical_result, (
        "alias and canonical must return identical paths"
    )
    assert any(
        issubclass(w.category, DeprecationWarning) for w in caught
    ), f"expected a DeprecationWarning, got {[w.category.__name__ for w in caught]}"
    assert any("layer0_root" in str(w.message) for w in caught), (
        f"warning message should mention 'layer0_root'; got {[str(w.message) for w in caught]}"
    )


def test_get_layer0_root_alias_causes_no_warning_when_canonical_used() -> None:
    """Canonical get_regulatory_baseline_root() must NOT emit a DeprecationWarning."""
    from aegis_phase1.prompts_v2.factory import get_regulatory_baseline_root

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        get_regulatory_baseline_root()

    assert not any(
        issubclass(w.category, DeprecationWarning) for w in caught
    ), "canonical function must not emit DeprecationWarning"


# ─────────────────────────────────────────────────────────────────────
# Phase1Validator(layer0_root=...) alias
# ─────────────────────────────────────────────────────────────────────


def test_phase1_validator_layer0_root_alias_with_deprecation_warning() -> None:
    """Deprecated layer0_root kwarg must still work but emit DeprecationWarning."""
    from aegis_phase1.prompts_v2.validator import Phase1Validator

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validator = Phase1Validator(layer0_root="/tmp/corr-005-alias-target")

    assert any(
        issubclass(w.category, DeprecationWarning) for w in caught
    ), f"expected DeprecationWarning, got {[w.category.__name__ for w in caught]}"
    assert any("layer0_root" in str(w.message) for w in caught)
    assert str(validator.regulatory_baseline_root) == "/tmp/corr-005-alias-target"


def test_phase1_validator_canonical_does_not_warn() -> None:
    """Canonical regulatory_baseline_root kwarg must NOT emit DeprecationWarning."""
    from aegis_phase1.prompts_v2.validator import Phase1Validator

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validator = Phase1Validator(
            regulatory_baseline_root="/tmp/corr-005-canonical-target"
        )

    assert not any(
        issubclass(w.category, DeprecationWarning) for w in caught
    ), "canonical kwarg must not emit DeprecationWarning"
    assert str(validator.regulatory_baseline_root) == "/tmp/corr-005-canonical-target"


def test_phase1_validator_no_args_raises_type_error() -> None:
    """Constructing without either kwarg must raise TypeError (clear contract)."""
    from aegis_phase1.prompts_v2.validator import Phase1Validator

    with pytest.raises(TypeError, match="regulatory_baseline_root"):
        Phase1Validator()


# ─────────────────────────────────────────────────────────────────────
# Phase1Validator._extract_layer0_refs method alias
# ─────────────────────────────────────────────────────────────────────


def test_extract_layer0_refs_method_alias_emits_deprecation_warning() -> None:
    """The deprecated method alias _extract_layer0_refs must work + warn."""
    from aegis_phase1.prompts_v2.validator import Phase1Validator

    validator = Phase1Validator(regulatory_baseline_root="/tmp/corr-005")
    output = {
        "interpretations": [
            {
                "entry_id": "X",
                "regulatory_baseline_refs": ["SubDomains/D-01.1.md"],
            }
        ]
    }

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        alias_refs = validator._extract_layer0_refs(output)
        canonical_refs = validator._extract_regulatory_baseline_refs(output)

    assert alias_refs == canonical_refs == ["SubDomains/D-01.1.md"]
    assert any(
        issubclass(w.category, DeprecationWarning) for w in caught
    ), "method alias must emit DeprecationWarning"


# ─────────────────────────────────────────────────────────────────────
# factory.get_validator(layer0_root=...) alias
# ─────────────────────────────────────────────────────────────────────


def test_get_validator_layer0_root_alias_warns() -> None:
    """factory.get_validator(layer0_root=...) must still work but warn."""
    from aegis_phase1.prompts_v2.factory import get_validator

    # We don't care about the result here (validator will be functional);
    # we only care that the kwarg is accepted and emits a warning.
    # Use a path that the prompts root can co-exist with.
    import os
    target = os.path.join("/tmp", "corr-005-get-validator-alias")
    os.makedirs(target, exist_ok=True)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            get_validator(layer0_root=target)
        assert any(
            issubclass(w.category, DeprecationWarning) for w in caught
        ), "factory.get_validator(layer0_root=...) must emit DeprecationWarning"
    finally:
        import shutil
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)