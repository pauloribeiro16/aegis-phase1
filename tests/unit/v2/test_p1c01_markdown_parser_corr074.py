"""CORR-074 propagation tests for the P1C-LLM-01 markdown parser."""

from __future__ import annotations

from aegis_phase1.prompts_v2.markdown_parser import P1CLLM01Parser
from aegis_phase1.v2.state import (
    P1BLLM01Confidence,
    P1BLLM01Status,
    P1CLLM01CompanyScopeVerdict,
    P1CLLM01Layer0Relationship,
    P1CLLM01ScopeOverlap,
)

M3_STYLE_FULL = """# D-01 Overlap Classification

## Status
**OK** — HIGH confidence. Company facts support the domain-level activation.

## Domain Summary
- `total_sub_domains`: 2
- `active_sub_domains`: 2
- `pairwise_relationships`: 3

## Sub-domain Activations

### D-01.1
- `applicable`: true
- `scope_overlap`: Y
- `applicable_regulations`: [GDPR, CRA, NIS2]
- `layer0_refs`: ["SubDomains/D-01.1.md", "annotations/D-01.yaml"]

#### Verified relationships

#### GDPR ↔ CRA
- `layer0_relationship`: SAME
- `company_scope_verdict`: OVERLAP_CONFIRMED
- `rationale`: TinyTask acts as controller and manufacturer for the same SaaS product.
- `layer0_refs`: ["CrossRegulation/GDPR-CRA.md"]

#### GDPR ↔ NIS2
- `layer0_relationship`: CONDITIONAL
- `company_scope_verdict`: INDETERMINATE
- `rationale`: The available facts do not establish NIS2 entity scope.
- `layer0_refs`: ["CrossRegulation/GDPR-NIS2.md"]

### D-01.2
- `applicable`: True
- `scope_overlap`: CONDITIONAL
- `applicable_regulations`: [CRA, NIS2]
- `layer0_refs`: ["SubDomains/D-01.2.md"]

#### Verified relationships

#### CRA ↔ NIS2
- `layer0_relationship`: SCOPE_DISJOINT
- `company_scope_verdict`: SCOPE_DISJOINT
- `rationale`: The obligations attach to different parties in the supplied facts.
- `layer0_refs`: ["CrossRegulation/CRA-NIS2.md"]

## Notes
Review the unresolved GDPR and NIS2 predicate with the human reviewer.
"""


def _single_activation(
    *,
    activations_heading: str = "## Sub-domain Activations",
    applicable: str = "true",
    scope_overlap: str = "Y",
    pair_heading: str = "GDPR ↔ CRA",
    layer0_relationship: str = "SAME",
    company_scope_verdict: str = "OVERLAP_CONFIRMED",
    include_notes: bool = True,
) -> str:
    notes = "\n## Notes\nNo additional issues.\n" if include_notes else ""
    return f"""## Status
OK — HIGH confidence. The supplied company facts are sufficient.

## Domain Summary
- `total_sub_domains`: 1
- `active_sub_domains`: 1
- `pairwise_relationships`: 1

{activations_heading}

### D-01.1
- `applicable`: {applicable}
- `scope_overlap`: {scope_overlap}
- `applicable_regulations`: [GDPR, CRA]
- `layer0_refs`: ["SubDomains/D-01.1.md"]

#### Verified relationships

#### {pair_heading}
- `layer0_relationship`: {layer0_relationship}
- `company_scope_verdict`: {company_scope_verdict}
- `rationale`: The same SaaS product is in scope for both regulations.
- `layer0_refs`: ["CrossRegulation/GDPR-CRA.md"]
{notes}"""


def test_empirical_m3_output_parses_nested_activations() -> None:
    model, err = P1CLLM01Parser().parse(M3_STYLE_FULL)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.status == P1BLLM01Status.OK
    assert model.confidence == P1BLLM01Confidence.HIGH
    assert model.domain_summary.total_sub_domains == 2
    assert model.domain_summary.active_sub_domains == 2
    assert model.domain_summary.pairwise_relationships == 3
    assert len(model.sub_domain_activations) == 2
    first, second = model.sub_domain_activations
    assert first.sub_domain_id == "D-01.1"
    assert first.applicable is True
    assert first.scope_overlap == P1CLLM01ScopeOverlap.Y
    assert first.applicable_regulations == ["GDPR", "CRA", "NIS2"]
    assert len(first.verified_relationship_per_pair) == 2
    assert first.verified_relationship_per_pair[0].reg_a == "GDPR"
    assert first.verified_relationship_per_pair[0].reg_b == "CRA"
    assert (
        first.verified_relationship_per_pair[0].layer0_relationship
        == P1CLLM01Layer0Relationship.SAME
    )
    assert (
        first.verified_relationship_per_pair[1].company_scope_verdict
        == P1CLLM01CompanyScopeVerdict.INDETERMINATE
    )
    assert second.scope_overlap == P1CLLM01ScopeOverlap.CONDITIONAL
    assert (
        second.verified_relationship_per_pair[0].layer0_relationship
        == P1CLLM01Layer0Relationship.SCOPE_DISJOINT
    )
    assert "unresolved GDPR and NIS2" in model.notes


def test_sub_domain_activations_heading_qualifier_is_tolerated() -> None:
    raw = _single_activation(
        activations_heading="## Sub-domain Activations (D-01)"
    )

    model, err = P1CLLM01Parser().parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert len(model.sub_domain_activations) == 1


def test_scope_verdict_with_spaces_is_normalised() -> None:
    raw = _single_activation(company_scope_verdict="OVERLAP NOT TRIGGERED")

    model, err = P1CLLM01Parser().parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    pair = model.sub_domain_activations[0].verified_relationship_per_pair[0]
    assert pair.company_scope_verdict == (
        P1CLLM01CompanyScopeVerdict.OVERLAP_NOT_TRIGGERED
    )


def test_scope_overlap_with_yes_qualifier_is_normalised() -> None:
    model, err = P1CLLM01Parser().parse(
        _single_activation(scope_overlap="Y (yes)")
    )

    assert model is not None, f"parser returned None: {err!r}"
    assert model.sub_domain_activations[0].scope_overlap == P1CLLM01ScopeOverlap.Y


def test_pair_heading_with_vs_is_parsed() -> None:
    model, err = P1CLLM01Parser().parse(
        _single_activation(pair_heading="GDPR vs CRA")
    )

    assert model is not None, f"parser returned None: {err!r}"
    pair = model.sub_domain_activations[0].verified_relationship_per_pair[0]
    assert (pair.reg_a, pair.reg_b) == ("GDPR", "CRA")


def test_empty_sub_domain_activations_is_valid() -> None:
    raw = """## Status
OK — MEDIUM confidence. No active sub-domains were identified.

## Domain Summary
- `total_sub_domains`: 0
- `active_sub_domains`: 0
- `pairwise_relationships`: 0

## Sub-domain Activations
"""

    model, err = P1CLLM01Parser().parse(raw)

    assert model is not None, f"parser returned None: {err!r}"
    assert model.sub_domain_activations == []


def test_applicable_true_is_case_insensitive() -> None:
    model, err = P1CLLM01Parser().parse(_single_activation(applicable="True"))

    assert model is not None, f"parser returned None: {err!r}"
    assert model.sub_domain_activations[0].applicable is True


def test_empty_applicable_defaults_to_false() -> None:
    model, err = P1CLLM01Parser().parse(_single_activation(applicable=""))

    assert model is not None, f"parser returned None: {err!r}"
    assert model.sub_domain_activations[0].applicable is False


def test_layer0_relationship_variant_is_rejected() -> None:
    raw = _single_activation(layer0_relationship="scope disjoint")

    model, err = P1CLLM01Parser().parse(raw)

    assert model is None
    assert err != ""


def test_notes_section_is_optional() -> None:
    model, err = P1CLLM01Parser().parse(_single_activation(include_notes=False))

    assert model is not None, f"parser returned None: {err!r}"
    assert model.notes == ""


def test_envelope_defaults_are_p1c01_specific() -> None:
    model, err = P1CLLM01Parser().parse(_single_activation())

    assert model is not None, f"parser returned None: {err!r}"
    assert model.prompt_spec_id == "P1C-LLM-01-OVERLAP-CLASSIFICATION"
    assert model.schema_version == "1.0.0"
    assert model.case_id == ""
    assert model.invocation_pattern == "per_domain_lane"
