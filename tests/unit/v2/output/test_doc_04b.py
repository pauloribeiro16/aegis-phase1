"""Unit tests for ``_section_adapted_objective`` v1.2 per-sub-domain output.

Verifies the per-sub-domain rendering path (when ``adapted_subdomains``
is populated) and the legacy verbatim fallback (when ``adapted_subdomains``
is empty but ``adapted_objective`` has the legacy concat).
"""

from __future__ import annotations

from typing import Any

from aegis_phase1.v2.output.doc_04b import _section_adapted_objective


def _domain_result_with_subdomains() -> dict[str, Any]:
    return {
        "domain_id": "D-10",
        "adapted_objective": (
            "**Objective.** Continuous monitoring...\n\n"
            "**Objective.** Audit logging...\n\n"
            "**Objective.** Compliance testing..."
        ),
        "adapted_subdomains": [
            {
                "subdomain_id": "D-10.1",
                "title": "Continuous Monitoring",
                "hl_objective": (
                    "**Objective.** Continuous monitoring is established "
                    "through a layered telemetry architecture."
                ),
                "directed": [
                    {
                        "regulation": "GDPR",
                        "objective": "Art. 32(1)(d) requires regular testing.",
                    },
                    {
                        "regulation": "CRA",
                        "objective": "Annex I Part I §1(2)(h) requires monitoring.",
                    },
                ],
            },
            {
                "subdomain_id": "D-10.2",
                "title": "Audit Logging & Traceability",
                "hl_objective": (
                    "**Objective.** Audit logging and traceability are "
                    "established through a layered audit-records architecture."
                ),
                "directed": [
                    {
                        "regulation": "GDPR",
                        "objective": "Art. 5(2) accountability requirement.",
                    },
                    {
                        "regulation": "CRA",
                        "objective": "Annex I Part II §(6) automatic logging.",
                    },
                ],
            },
            {
                "subdomain_id": "D-10.3",
                "title": "Compliance Testing",
                "hl_objective": (
                    "**Objective.** Compliance testing is established "
                    "through scheduled control reviews."
                ),
                "directed": [
                    {
                        "regulation": "GDPR",
                        "objective": "Art. 28(3)(g) audit trail.",
                    },
                    {
                        "regulation": "CRA",
                        "objective": "Annex I Part I §1(2)(j) testing effectiveness.",
                    },
                ],
            },
        ],
        "key_changes": [],
        "confidence": "UNKNOWN",
        "tier": "LIGHTWEIGHT",
        "llm_status": "OK",
    }


def _domain_result_legacy(text: str = "legacy text") -> dict[str, Any]:
    return {
        "domain_id": "D-01",
        "adapted_objective": text,
        "adapted_subdomains": [],
        "key_changes": ["change 1", "change 2"],
        "confidence": "HIGH",
        "tier": "LIGHTWEIGHT",
        "llm_status": "OK",
    }


# ─── New: per-sub-domain rendering ─────────────────────────────────────


def test_doc_04b_renders_per_subdomain_when_adapted_subdomains_present() -> None:
    """``##### D-XX.Y — <title>`` headings, ``Directed objectives.``, and
    ``- **<REG>**:`` bullets are all rendered when ``adapted_subdomains``
    is populated.
    """
    section = _section_adapted_objective("D-10", _domain_result_with_subdomains())

    # Per-sub-domain headings (Markdown ##### + subdomain id + em-dash + title)
    assert "##### D-10.1 — Continuous Monitoring" in section
    assert "##### D-10.2 — Audit Logging & Traceability" in section
    assert "##### D-10.3 — Compliance Testing" in section

    # Per-sub-domain HL verbatim text
    assert (
        "**Objective.** Continuous monitoring is established" in section
    )
    assert (
        "**Objective.** Audit logging and traceability are" in section
    )

    # Directed objectives list and bullets
    assert section.count("**Directed objectives.**") == 3
    assert "- **GDPR**:" in section
    assert "- **CRA**:" in section
    assert "Art. 5(2) accountability requirement." in section
    assert "Annex I Part II §(6) automatic logging." in section


def test_doc_04b_renders_pedning_marker_with_subdomains() -> None:
    """When the v1.2 path renders, [PENDING REVIEW] wraps each HL."""
    domain_result = _domain_result_with_subdomains()
    review = {"status": "PENDING", "edited_text": "", "notes": ""}
    section = _section_adapted_objective("D-10", domain_result, review)
    assert "[PENDING REVIEW]" in section
    # The marker must wrap the HL text on the per-sub-domain block
    assert "[PENDING REVIEW]\n**Objective.** Continuous monitoring" in section


def test_doc_04b_approved_marker_with_subdomains() -> None:
    """APPROVED removes the PENDING prefix on each sub-domain block."""
    domain_result = _domain_result_with_subdomains()
    review = {"status": "APPROVED", "edited_text": "", "notes": ""}
    section = _section_adapted_objective("D-10", domain_result, review)
    assert "[PENDING REVIEW]" not in section
    assert "[RE-GENERATION REQUIRED]" not in section
    # HL is still rendered verbatim
    assert "**Objective.** Continuous monitoring" in section


# ─── Legacy fallback ──────────────────────────────────────────────────


def test_doc_04b_falls_back_to_verbatim_when_no_adapted_subdomains() -> None:
    """When ``adapted_subdomains`` is ``[]`` but ``adapted_objective`` has
    text, render it verbatim.
    """
    section = _section_adapted_objective("D-01", _domain_result_legacy("legacy text"))
    assert "legacy text" in section
    # key_changes list still rendered below the legacy text
    assert "**Key changes**" in section
    assert "change 1" in section


def test_doc_04b_legacy_renders_pending_marker() -> None:
    """Legacy text is wrapped in [PENDING REVIEW] when no review entry."""
    section = _section_adapted_objective("D-01", _domain_result_legacy("legacy body"))
    assert "[PENDING REVIEW]" in section
    assert "legacy body" in section


# ─── v1.3: 3-block x 5-field rendering ─────────────────────────────────


def _domain_result_with_subdomains_v3() -> dict[str, Any]:
    return {
        "domain_id": "D-10",
        "adapted_objective": "ignored (V3 path used instead)",
        "adapted_subdomains": [],
        "adapted_subdomains_v3": [
            {
                "subdomain_id": "D-10.2",
                "title": "Audit Logging & Traceability",
                "blocks": [
                    {
                        "label": "Generic Objective.",
                        "original": "Source HL verbatim for audit logging.",
                        "adapted": "Adapted HL for audit logging at micro scale.",
                        "rationale": "Perimeter narrows to GDPR + CRA only.",
                        "adjustments": "Drop DORA/AI Act layers.",
                        "considerations": [
                            "4 of 5 regs participate (NIS 2 out-of-scope).",
                            "CRDA-deep verified (6 pairs SAME).",
                        ],
                    },
                    {
                        "label": "GDPR Objective.",
                        "original": "GDPR Art. 30(3) compliance records verbatim.",
                        "adapted": "GDPR compliance records with retention envelope.",
                        "rationale": "Adds operationalisation for micro-scale entity.",
                        "adjustments": "Define retention envelope explicitly.",
                        "considerations": [
                            "GDPR's anchor is strictest for personal-data at-rest.",
                            "Records include RoPA, consent, processor contracts.",
                        ],
                    },
                    {
                        "label": "CRA Objective.",
                        "original": "CRA Annex VII §5-§8 technical documentation verbatim.",
                        "adapted": "CRA Annex VII technical documentation via CI pipelines.",
                        "rationale": "Adds micro-scale product manufacturing guidance.",
                        "adjustments": "Define support period explicitly.",
                        "considerations": [
                            "CRA's anchor is strictest in absolute terms.",
                            "10-year retention aligns with D-09.4.",
                        ],
                    },
                ],
            },
        ],
        "key_changes": [],
        "confidence": "UNKNOWN",
        "tier": "LIGHTWEIGHT",
        "llm_status": "OK",
    }


def test_doc_04b_renders_v3_blocks_when_adapted_subdomains_v3_present() -> None:
    """When ``adapted_subdomains_v3`` is populated, the renderer emits
    the 3-block x 5-field structure with all canonical labels and field
    markers.
    """
    section = _section_adapted_objective(
        "D-10", _domain_result_with_subdomains_v3()
    )

    # Sub-domain heading
    assert "##### D-10.2 — Audit Logging & Traceability" in section

    # Three block headers
    assert "**Generic Objective.**" in section
    assert "**GDPR Objective.**" in section
    assert "**CRA Objective.**" in section

    # Five fields per block (one occurrence per block x 3 blocks = 3 each)
    assert section.count("- Original:") == 3
    assert section.count("- Adapted:") == 3
    assert section.count("- Rationale:") == 3
    assert section.count("- Adjustments needed:") == 3

    # Considerations section header appears once per block
    assert section.count("**Considerations.**") == 3

    # Content samples
    assert "Source HL verbatim for audit logging." in section
    assert "GDPR Art. 30(3) compliance records verbatim." in section
    assert "CRA Annex VII §5-§8 technical documentation verbatim." in section
    assert "4 of 5 regs participate (NIS 2 out-of-scope)." in section


def test_doc_04b_v3_preferred_over_v2_when_both_present() -> None:
    """When both ``adapted_subdomains_v3`` and ``adapted_subdomains`` are
    populated, the renderer prefers the V3 structure.
    """
    dr = _domain_result_with_subdomains_v3()
    # Inject a V2 entry that must NOT be rendered when V3 is present
    dr["adapted_subdomains"] = [
        {
            "subdomain_id": "D-10.99",
            "title": "SHOULD NOT APPEAR",
            "hl_objective": "**Objective.** This V2 entry should be ignored.",
            "directed": [{"regulation": "GDPR", "objective": "x."}],
        },
    ]
    section = _section_adapted_objective("D-10", dr)
    assert "SHOULD NOT APPEAR" not in section
    assert "##### D-10.2 — Audit Logging" in section


def test_doc_04b_v3_falls_back_to_v2_when_v3_empty() -> None:
    """When ``adapted_subdomains_v3`` is empty (or absent), the renderer
    falls back to ``adapted_subdomains`` (v1.2 rendering).
    """
    dr = _domain_result_with_subdomains()
    dr["adapted_subdomains_v3"] = []
    section = _section_adapted_objective("D-10", dr)
    # V1.2 rendering markers
    assert "##### D-10.1 — Continuous Monitoring" in section
    assert "**Directed objectives.**" in section
