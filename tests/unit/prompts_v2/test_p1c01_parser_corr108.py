"""CORR-108 — tests for the dual-shape P1C-LLM-01 parser.

Pins the behaviour that unblocks REDUCE-LLM: the parser reads BOTH the
canonical shape (M3: `## Sub-domain Activations` + `### D-XX.Y`) and the
shape every non-M3 model emits (`## Pair classifications` +
`## Findings`), merging by sub_domain_id into
``sub_domain_activations`` — the key the executor and the downstream
normalizer consume.

The Shape B fixture is REAL output from the qwen3.8 run-all
(JOB 1862843, 10 lanes, 2026-09-01).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis_phase1._archive.corr061.markdown_parser import (
    MARKDOWN_PARSERS,
    P1CLLM01Parser,
)
from aegis_phase1.v2.state import P1CLLM01Output

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "p1c01" / "qwen38_section.md"


@pytest.fixture
def qwen38_raw() -> str:
    return FIXTURE.read_text(encoding="utf-8")


CANONICAL_RAW = """\
## Status
- applicable: YES
- confidence: HIGH

## Sub-domain Activations

### D-01.1
- sub_domain_id: D-01.1
- reg_pair: [GDPR, CRA]
- company_scope_verdict: APPLICABLE
- regulatory_baseline_relationship: SAME
- layer0_refs: SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA

### D-01.2
- sub_domain_id: D-01.2
- reg_pair: [GDPR]
- company_scope_verdict: NOT_APPLICABLE
- layer0_refs: SubDomains/D-01_Data-Protection/D-01.2.md §2 HSO

## Rationale
All four sub-domains evaluated.
"""


def test_registry_maps_p1c01_to_new_parser():
    """The registry must route P1C-LLM-01 to the dual-shape parser
    (was GenericMarkdownParser, which dropped Shape B entirely)."""
    assert MARKDOWN_PARSERS["P1C-LLM-01-OVERLAP-CLASSIFICATION"] is P1CLLM01Parser


def test_parse_real_qwen38_runall_section(qwen38_raw):
    """Real 10-lane section from JOB 1862843: must extract activations
    for ALL 10 domains (was 0 before CORR-108)."""
    parsed, err = P1CLLM01Parser().parse(qwen38_raw)
    assert err == ""
    assert isinstance(parsed, P1CLLM01Output)
    acts = parsed.sub_domain_activations
    assert len(acts) >= 25, f"expected >=25 activations, got {len(acts)}"
    lanes = {a["sub_domain_id"].split(".")[0] for a in acts}
    assert lanes == {f"D-{i:02d}" for i in range(1, 11)}, f"lanes: {sorted(lanes)}"
    # Every activation carries a normalized verdict (YES/NO/INDETERMINATE).
    for a in acts:
        assert a["company_scope_verdict"] in ("YES", "NO", "INDETERMINATE"), a
    # D-01.1 is the fully-documented case: YES + GDPR/CRA + ref.
    d011 = next(a for a in acts if a["sub_domain_id"] == "D-01.1")
    assert d011["company_scope_verdict"] == "YES"
    assert d011["reg_pair"] == ["GDPR", "CRA"]
    assert d011.get("layer0_refs")


def test_parse_canonical_shape_a():
    parsed, err = P1CLLM01Parser().parse(CANONICAL_RAW)
    assert err == ""
    acts = parsed.sub_domain_activations
    assert len(acts) == 2
    d011 = next(a for a in acts if a["sub_domain_id"] == "D-01.1")
    assert d011["company_scope_verdict"] == "APPLICABLE"  # passed through
    assert d011["reg_pair"] == ["GDPR", "CRA"]
    assert d011["layer0_refs"] == ["SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA"]
    d012 = next(a for a in acts if a["sub_domain_id"] == "D-01.2")
    assert d012["company_scope_verdict"] == "NOT_APPLICABLE"


def test_verdict_normalization_variants(qwen38_raw):
    """All observed verdict spellings map to YES/NO:
    OVERLAP_CONFIRMED→YES, NOT_IN_SCOPE→NO, NOT_APPLICABLE→NO,
    OVERLAP_NOT_TRIGGERED→NO, and D-03's '— SAME — ... Verdict:
    OVERLAP_CONFIRMED' fallback."""
    parsed, _ = P1CLLM01Parser().parse(qwen38_raw)
    verdicts = {a["company_scope_verdict"] for a in parsed.sub_domain_activations}
    assert verdicts <= {"YES", "NO", "INDETERMINATE"}
    # The fixture contains all of these shapes.
    assert "YES" in verdicts
    assert "NO" in verdicts
    # D-03 lane relies on the "Verdict:" fallback.
    d03 = [a for a in parsed.sub_domain_activations if a["sub_domain_id"].startswith("D-03.")]
    assert d03 and any(a["company_scope_verdict"] == "YES" for a in d03)


def test_status_and_confidence_extracted(qwen38_raw):
    parsed, _ = P1CLLM01Parser().parse(qwen38_raw)
    assert parsed.status.value in ("YES", "OK", "INDETERMINATE")
    assert parsed.confidence.value in ("HIGH", "MEDIUM", "LOW")


def test_envelope_fields_injectable(qwen38_raw):
    """The invoker sets these 4 fields post-parse; the model must accept
    them (GenericMarkdownOutput contract)."""
    parsed, _ = P1CLLM01Parser().parse(qwen38_raw)
    parsed.case_id = "case1-tinytask"
    parsed.prompt_spec_id = "P1C-LLM-01-OVERLAP-CLASSIFICATION"
    parsed.schema_version = "1.0.0"
    parsed.invocation_pattern = "per_domain_lane"
    dumped = parsed.model_dump()
    assert dumped["sub_domain_activations"]  # survives model_dump → dict path


def test_sections_captured_for_renderers(qwen38_raw):
    """Renderers consume the verbatim sections blob (CORR-061 S3b);
    the parser must still populate it."""
    parsed, _ = P1CLLM01Parser().parse(qwen38_raw)
    assert "Pair classifications" in parsed.sections
    assert "Findings" in parsed.sections
    assert "Rationale" in parsed.sections


def test_single_lane_input_still_works():
    """Production input is ONE lane per LLM call — a single `## Status`
    block must parse identically to the concatenated doc."""
    single = """\
## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-07.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED — TinyTask is manufacturer and controller.

## Findings
- D-07.1 (Secure Development): ACTIVE. Participating regulations in scope: GDPR, CRA. Layer0 refs: SubDomains/D-07_Secure-Development/D-07.1.md §1 CRDA.
"""
    parsed, err = P1CLLM01Parser().parse(single)
    assert err == ""
    acts = parsed.sub_domain_activations
    assert len(acts) == 1
    a = acts[0]
    assert a["sub_domain_id"] == "D-07.1"
    assert a["company_scope_verdict"] == "YES"
    assert a["reg_pair"] == ["GDPR", "CRA"]
    assert a["layer0_refs"] == ["SubDomains/D-07_Secure-Development/D-07.1.md"]


def test_garbage_pair_bullets_rejected():
    """Bullets like 'No GDPR↔CRA pair exists...' must NOT produce
    records with garbage reg_pair ('No GDPR', 'CRA pair exists...')."""
    raw = """\
## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-02.2 : No GDPR↔CRA pair exists in the Regulatory Baseline for this sub-domain. Pair not activated.

## Findings
- D-02.2 (Patch Management): ACTIVE. Participating regulations in scope: CRA only. Layer0 refs: SubDomains/D-02_Vulnerability-Management/D-02.2.md §1 CRDA.
"""
    parsed, err = P1CLLM01Parser().parse(raw)
    assert err == ""
    acts = parsed.sub_domain_activations
    assert len(acts) == 1
    a = acts[0]
    assert a["sub_domain_id"] == "D-02.2"
    assert a["reg_pair"] == ["CRA"]  # from 'Participating regulations... CRA only'
    assert a["company_scope_verdict"] == "YES"


def test_parse_json_fallback():
    """Verify that when an LLM emits valid JSON output for P1C-01,
    P1CLLM01Parser parses it into P1CLLM01Output seamlessly."""
    raw_json = """```json
{
  "prompt_spec_id": "P1C-LLM-01-OVERLAP-CLASSIFICATION",
  "status": "OK",
  "confidence": "HIGH",
  "sub_domain_activations": [
    {
      "sub_domain_id": "D-01.1",
      "applicable": true,
      "scope_overlap": "Y",
      "applicable_regulations": ["GDPR", "CRA"],
      "verified_relationship_per_pair": [
        {
          "reg_a": "GDPR",
          "reg_b": "CRA",
          "company_scope_verdict": "OVERLAP_CONFIRMED",
          "layer0_refs": ["SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA"]
        }
      ]
    },
    {
      "sub_domain_id": "D-01.2",
      "applicable": false,
      "scope_overlap": "N",
      "applicable_regulations": ["GDPR"],
      "verified_relationship_per_pair": [
        {
          "reg_a": "GDPR",
          "reg_b": "CRA",
          "company_scope_verdict": "OVERLAP_NOT_TRIGGERED",
          "layer0_refs": ["SubDomains/D-01_Data-Protection/D-01.2.md §2 HSO"]
        }
      ]
    }
  ]
}
```"""
    parsed, err = P1CLLM01Parser().parse(raw_json)
    assert err == ""
    assert isinstance(parsed, P1CLLM01Output)
    assert parsed.status.value == "OK"
    assert parsed.confidence.value == "HIGH"
    acts = parsed.sub_domain_activations
    assert len(acts) == 2
    d011 = acts[0]
    assert d011["sub_domain_id"] == "D-01.1"
    assert d011["applicable"] == "YES"
    assert d011["company_scope_verdict"] == "YES"
    assert d011["reg_pair"] == ["GDPR", "CRA"]

    d012 = acts[1]
    assert d012["sub_domain_id"] == "D-01.2"
    assert d012["applicable"] == "NO"
    assert d012["company_scope_verdict"] == "NO"

