"""CORR-072 regression test: stakeholder cross-case leakage.

Bug history: in case 3 (OmniBank Financial Systems S.A.) the rendered
Doc 04 §3.1 Stakeholder Register showed ``Organisation: TinyTask Lda.``
and contact emails like ``cto@tinytask.pt`` for stakeholders SH-01..SH-04
even though the case-3 YAML had OmniBank-specific roles (CEO, CISO, DPO,
CRO). Root cause: ``_augment_influence`` in doc_04.py inherited not just
``influence``/``interest`` from the TinyTask baseline but also
``organisation``, ``contact`` and ``responsibilities`` by ID match. Because
case 3 used IDs SH-01..SH-07 matching TinyTask's, the helper silently
filled OmniBank stakeholder rows with TinyTask data.

This test ensures:
  1. The fixed helper does NOT inherit org/contact/responsibilities from
     baseline even when IDs match.
  2. Influence/interest inheritance still works (those are template
     metadata, not case-specific facts).
  3. TinyTask-style stakeholders (with full data) still pass through
     unchanged.
"""
from __future__ import annotations

from aegis_phase1.v2.output.doc_04 import _augment_influence, _stakeholders


def _omnibank_stakeholder() -> dict:
    """Case-3 style: role differs from TinyTask, but contact/org missing."""
    return {
        "id": "SH-01",
        "role": "Chief Executive Officer (CEO)",
        "responsibilities": "executive_sponsor, accountability, ecb_supervised",
        "organisation": "-",
        "contact": "-",
        "influence": "-",
        "interest": "-",
    }


def test_omnibank_stakeholder_does_not_inherit_organisation() -> None:
    """The fix: organisation from baseline is NOT inherited by ID match."""
    out = _augment_influence(_omnibank_stakeholder())
    assert out["organisation"] == "-", (
        f"CORR-072 REGRESSION: organisation was silently inherited from "
        f"TinyTask baseline: got {out['organisation']!r}"
    )


def test_omnibank_stakeholder_does_not_inherit_contact() -> None:
    out = _augment_influence(_omnibank_stakeholder())
    assert out["contact"] == "-", (
        f"CORR-072 REGRESSION: contact was silently inherited from "
        f"TinyTask baseline: got {out['contact']!r}"
    )


def test_omnibank_stakeholder_does_not_inherit_responsibilities() -> None:
    out = _augment_influence(_omnibank_stakeholder())
    assert out["responsibilities"] != "executive_sponsor, accountability", (
        f"CORR-072 REGRESSION: responsibilities were overwritten from "
        f"TinyTask baseline: got {out['responsibilities']!r}"
    )


def test_influence_inheritance_still_works() -> None:
    """The fix preserves influence/interest inheritance (template metadata)."""
    sh = _omnibank_stakeholder()
    out = _augment_influence(sh)
    assert out["influence"] == "HIGH", (
        f"influence should be inherited from baseline, got {out['influence']!r}"
    )
    assert out["interest"] == "HIGH", (
        f"interest should be inherited from baseline, got {out['interest']!r}"
    )


def test_tinytask_stakeholder_unchanged() -> None:
    """Stakeholders with full data should pass through unchanged."""
    sh = {
        "id": "SH-01",
        "role": "Chief Executive Officer (CEO)",
        "responsibilities": "executive_sponsor, accountability",
        "organisation": "TinyTask Lda.",
        "contact": "ceo@tinytask.pt",
        "influence": "HIGH",
        "interest": "HIGH",
    }
    out = _augment_influence(sh)
    assert out["organisation"] == "TinyTask Lda."
    assert out["contact"] == "ceo@tinytask.pt"
    assert out["influence"] == "HIGH"


def test_stakeholders_state_drives_no_tinytask_fallback() -> None:
    """When state['stakeholders'] is provided, fallback must NOT trigger.

    Regression for the OmniBank case: ``_stakeholders(state)`` was
    returning the TinyTask baseline list because ``state['stakeholders']``
    was not set in the case 3 state dict. With this fix the consumer
    of doc_04 should always inject the case-specific stakeholder list
    via state.
    """
    state = {
        "stakeholders": [
            {
                "id": "SH-01",
                "role": "CEO",
                "responsibilities": "executive",
                "organisation": "OmniBank Financial Systems S.A.",
                "contact": "ceo@omnibank.example",
                "influence": "HIGH",
                "interest": "HIGH",
            }
        ]
    }
    rows = _stakeholders(state)
    assert len(rows) == 1
    assert rows[0]["organisation"] == "OmniBank Financial Systems S.A."
    assert rows[0]["contact"] == "ceo@omnibank.example"


def test_section_3_stakeholder_register_no_tinytask_leak_in_render(
    monkeypatch: object,
) -> None:
    """Render Doc 04 §3.1 with an OmniBank-only stakeholder list and assert
    no TinyTask strings leak into the output.
    """
    from aegis_phase1.v2.output import doc_04

    state = {
        "stakeholders": [
            {
                "id": "SH-01",
                "role": "Chief Executive Officer (CEO)",
                "responsibilities": "executive_sponsor, ecb_supervised",
                "organisation": "OmniBank Financial Systems S.A.",
                "contact": "ceo@omnibank.example",
                "influence": "HIGH",
                "interest": "HIGH",
            },
            {
                "id": "SH-02",
                "role": "Chief Information Security Officer (CISO)",
                "responsibilities": "security_lead",
                "organisation": "OmniBank Financial Systems S.A.",
                "contact": "ciso@omnibank.example",
                "influence": "HIGH",
                "interest": "HIGH",
            },
        ],
        "company_context": {
            "company_name": "OmniBank Financial Systems S.A.",
            "sector": "Banking & Financial Services",
            "applicable_regs": ["AI_Act", "CRA", "DORA", "GDPR", "NIS2"],
        },
    }

    # _section_3_stakeholders expects normalised dicts (post-_stakeholders).
    rows = _stakeholders(state)
    rendered = "\n".join(doc_04._section_3_stakeholders(rows))
    assert "OmniBank" in rendered, "expected OmniBank to appear"
    assert "TinyTask" not in rendered, (
        f"CORR-072 REGRESSION: TinyTask leaked into Doc 04 §3.1 "
        f"Stakeholder Register:\n{rendered}"
    )
    assert "tinytask.pt" not in rendered.lower(), (
        f"CORR-072 REGRESSION: tinytask.pt email leaked:\n{rendered}"
    )
