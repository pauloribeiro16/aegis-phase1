"""CORR-049-T5: Schema loader fix (fenced-block parser).

Pre-CORR-049 the loader treated output_schemas.yaml as YAML+frontmatter
and discarded the body (where the actual schemas live in Markdown
fenced blocks). _resolve_schema() always returned {} → "0 sub_domain_activations"
in every real LLM run.

Post-CORR-049 the loader uses a regex to extract ```yaml ... ``` blocks
and indexes by properties.prompt_spec_id.const. All 5 canonical
LLM specs now resolve.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from aegis_phase1.prompts_v2.validator import Phase1Validator


# Phase1Validator requires regulatory_baseline_root; use the canonical
# Methodology-main path which is required for the LLM specs.
@pytest.fixture(scope="module")
def validator() -> Phase1Validator:
    return Phase1Validator(
        regulatory_baseline_root=Path(
            "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PREPROCESSING"
        )
    )


def test_p1b_llm_01_schema_resolves(validator: Phase1Validator) -> None:
    """CORR-049-T5: P1B-LLM-01-INTERPRETATION must resolve to a real schema."""
    schema = validator._resolve_schema("P1B-LLM-01-INTERPRETATION")
    assert schema, "schema is empty — fenced block parsing failed"
    assert (
        schema.get("properties", {}).get("prompt_spec_id", {}).get("const")
        == "P1B-LLM-01-INTERPRETATION"
    )
    assert "interpretations" in schema.get("properties", {}), (
        "missing interpretations field"
    )


def test_p1c_llm_01_schema_resolves(validator: Phase1Validator) -> None:
    """P1C-LLM-01-OVERLAP-CLASSIFICATION must resolve with sub_domain_activations."""
    schema = validator._resolve_schema("P1C-LLM-01-OVERLAP-CLASSIFICATION")
    assert schema, "schema is empty"
    assert "sub_domain_activations" in schema.get("properties", {}), (
        "missing sub_domain_activations — root cause of LLM emitting {pairs:[...]}"
    )


def test_p1c_llm_03_schema_resolves(validator: Phase1Validator) -> None:
    """P1C-LLM-03-STRATEGIC-SYNTHESIS must resolve with implications."""
    schema = validator._resolve_schema("P1C-LLM-03-STRATEGIC-SYNTHESIS")
    assert schema, "schema is empty"
    assert "implications" in schema.get("properties", {})


def test_all_5_schemas_loaded(validator: Phase1Validator) -> None:
    """All 5 canonical LLM specs should have schemas after CORR-049-T5."""
    expected_specs = [
        "P1B-LLM-01-INTERPRETATION",
        "P1B-LLM-02-RATIONALE",
        "P1C-LLM-01-OVERLAP-CLASSIFICATION",
        "P1C-LLM-02-COMPOUND-EVENT",
        "P1C-LLM-03-STRATEGIC-SYNTHESIS",
    ]
    for spec in expected_specs:
        s = validator._resolve_schema(spec)
        assert s, f"missing schema for {spec}"
        # Each schema should have a `required` field with the
        # canonical structure (per output_schemas.yaml)
        assert "required" in s, f"schema for {spec} missing `required`"
        assert "properties" in s, f"schema for {spec} missing `properties`"
