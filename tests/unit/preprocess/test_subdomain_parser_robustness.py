"""Tests for the YAML parser robustness (CORR-029, B.1).

The SubDomain parser extracts fields from a YAML fenced block inside
the MD. The unquoted ``verified_relationship`` value contains special
characters (``:``, ``(``, ``,``, ``**``) that break ``yaml.safe_load``.

The fix (CORR-029 B.1) introduces a regex-based pre-extraction that
populates the critical single-line fields (``id``, ``inherits_from``,
``source_SR``, etc.) even when the YAML parse fails.

This test suite covers the parser's behaviour with various YAML inputs.
"""

from __future__ import annotations

from scripts.preprocess.parsers.entities.subdomain import (
    _extract_yaml_field,
    _parse_yaml_block,
)

# ─── Well-formed YAML ────────────────────────────────────────────────


def test_well_formed_yaml_extracts_all_fields() -> None:
    """A clean YAML block (no special chars in any value) is parsed fully."""
    body = """\
### D-09.2.5 — Sub-SO for AI Act

```yaml
id: SO-D-09.2.AI_Act
subdomain: D-09.2
applies_to: [AI_Act]
inherits_from: SO-AIACT-001
source_SR: SR-AIACT-001 + SR-AIACT-002
activation: if AI_Act in applicable_regs
```
"""
    result = _parse_yaml_block(body)
    assert result["id"] == "SO-D-09.2.AI_Act"
    assert result["inherits_from"] == "SO-AIACT-001"
    assert result["source_SR"] == "SR-AIACT-001 + SR-AIACT-002"


# ─── YAML with unquoted special chars (the CORR-029 fix scenario) ─


def test_yaml_with_unquoted_special_chars_in_verified_relationship() -> None:
    """The CORR-029 fix: a YAML block with ``verified_relationship``
    containing ``:``, ``(``, ``,``, ``**`` (unquoted) breaks
    ``yaml.safe_load`` BUT the critical single-line fields are still
    extracted by the regex fallback.
    """
    body = """\
### D-09.2.5 — Sub-SO for AI Act

```yaml
id: SO-D-09.2.AI_Act
subdomain: D-09.2
applies_to: [AI_Act]
inherits_from: SO-AIACT-001
source_SR: SR-AIACT-001 + SR-AIACT-002
activation: if AI_Act in applicable_regs
phase_1A_role: 1_of_5
verified_relationship: DIFFERENT-PERSPECTIVE / COMPLEMENTARY (CRDA-deep, D-09.2: GDPR↔AI_Act = SAME)
```
"""
    # ``yaml.safe_load`` would fail on this block, but the parser must
    # still extract inherits_from and source_SR via regex.
    result = _parse_yaml_block(body)
    assert result["inherits_from"] == "SO-AIACT-001"
    assert result["source_SR"] == "SR-AIACT-001 + SR-AIACT-002"
    assert result["id"] == "SO-D-09.2.AI_Act"


def test_yaml_with_no_yaml_block_returns_empty() -> None:
    """A body without a YAML fenced block returns an empty dict."""
    body = "### D-09.2.5 — Sub-SO for AI Act\n\nNo YAML here.\n"
    result = _parse_yaml_block(body)
    assert result == {}


def test_yaml_with_partial_special_chars() -> None:
    """A YAML block where some fields are unquoted (with colons) and
    others are quoted should still extract the simple fields.
    """
    body = """\
```yaml
id: SO-D-01.1.GDPR
inherits_from: SO-GDPR-005
anchor: Art. 32(1)(a) — pseudonymisation and encryption
```
"""
    result = _parse_yaml_block(body)
    assert result["id"] == "SO-D-01.1.GDPR"
    assert result["inherits_from"] == "SO-GDPR-005"


def test_yaml_with_multiline_value() -> None:
    """A field whose value spans multiple lines is NOT extracted by
    the simple regex (which only takes the first line). This is the
    documented limitation — multi-line fields must be quoted.
    """
    body = """\
```yaml
id: SO-D-01.1.GDPR
inherits_from: SO-GDPR-005
description: |
  Line 1
  Line 2
```
"""
    result = _parse_yaml_block(body)
    assert result["inherits_from"] == "SO-GDPR-005"
    # description might be in the dict if yaml.safe_load succeeds, OR
    # absent if the block-scalar trips the parser. Either is acceptable
    # for the CORR-029 fix scope (which only guarantees the simple fields).


# ─── _extract_yaml_field direct tests ──────────────────────────────


def test_extract_yaml_field_returns_value() -> None:
    """Direct test of the regex helper."""
    yaml = "id: SO-D-01.1.GDPR\ninherits_from: SO-GDPR-005\n"
    assert _extract_yaml_field(yaml, "id") == "SO-D-01.1.GDPR"
    assert _extract_yaml_field(yaml, "inherits_from") == "SO-GDPR-005"


def test_extract_yaml_field_returns_none_for_missing() -> None:
    yaml = "id: SO-D-01.1.GDPR\n"
    assert _extract_yaml_field(yaml, "inherits_from") is None


def test_extract_yaml_field_rejects_multiline_fields() -> None:
    """Defensive: we should not try to extract fields that may legitimately
    span multiple lines.
    """
    yaml = "verified_relationship: COMPLEX VALUE\n"
    assert _extract_yaml_field(yaml, "verified_relationship") is None
    assert _extract_yaml_field(yaml, "objective") is None
    assert _extract_yaml_field(yaml, "considerations") is None


# ─── Real-world regression: the original CORR-029 trigger ────────


def test_real_d09_2_ai_act_block() -> None:
    """Regression test for the exact D-09.2.5 block from
    methodology-00/PREPROCESSING/SubDomains/D-09_Governance-Documentation/D-09.2.md.

    This block has the unquoted verified_relationship that triggered
    CORR-029 in the first place. After the fix, the critical fields
    must be populated.
    """
    body = """\
### D-09.2.5 — Sub-SO for AI Act

```yaml
id: SO-D-09.2.AI_Act
subdomain: D-09.2
applies_to: [AI_Act]
inherits_from: SO-AIACT-001
source_SR: SR-AIACT-001 + SR-AIACT-002
activation: if AI_Act in applicable_regs
phase_1A_role: 1_of_5
verified_relationship: DIFFERENT-PERSPECTIVE / COMPLEMENTARY (CRDA-deep, D-09.2: GDPR↔AI_Act = DIFFERENT-PERSPECTIVE (SAME — pre-launch DPIA on data-subject rights vs continuous iterative AI Act Art. 9 risk management; AI Act Recital 78 explicit GDPR preservation; **no OJ-level consolidation**); NIS2↔AI_Act = COMPLEMENTARY (SAME — NIS 2 entity-level operational + AI Act AI-system-level continuous iterative); **CRA↔AI_Act = COMPLEMENTARY (SAME) — CRITICAL CONSOLIDATION RULE**: CRA Art. 13(4) sentence 2 unification rule permits the AI Act Art. 9 risk-management system to substitute for the CRA Art. 13(3) cybersecurity risk assessment when both apply to the same product; **only OJ-level cross-regulation consolidation rule in D-09.2**; DORA↔AI_Act = COMPLEMENTARY (SAME — DORA entity-level operational + AI Act AI-system-level continuous iterative; **no OJ-level consolidation**))
```
"""
    result = _parse_yaml_block(body)
    # The four critical fields
    assert result["id"] == "SO-D-09.2.AI_Act"
    assert result["inherits_from"] == "SO-AIACT-001"
    assert result["source_SR"] == "SR-AIACT-001 + SR-AIACT-002"
    assert result["subdomain"] == "D-09.2"
    # The complex field is NOT in the dict (deliberately)
    assert "verified_relationship" not in result
