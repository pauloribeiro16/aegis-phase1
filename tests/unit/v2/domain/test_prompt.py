from __future__ import annotations

from aegis_phase1.v2.domain.prompt import (
    _extract_considerations,
    _extract_objective_and_first_consideration,
    _extract_objective_paragraph,
    _render_ambiguities,
    _render_articles,
    _render_cross_reg,
    _render_subdomains,
    _render_track_b,
    render_prompt,
)


def test_extract_objective_paragraph_strips_yaml_block() -> None:
    raw_text = """### D-10.2.1 — Sub-SO for GDPR

```yaml
id: SO-D-10.2.GDPR
applies_to: [GDPR]
source_SR: SR-GDPR-044
```

**Objective.** The controller and processor maintain compliance records in writing or in electronic form with integrity and traceability sufficient to demonstrate compliance and to support supervisory-authority inspections (Art. 30(3) + Art. 5(2) + Art. 31 GDPR).

**Considerations.**
- GDPR records must support supervisory-authority inspections and remain available on request.
- A later consideration is not needed in the MAP prompt.

**CSF anchors (from SR-GDPR-044):**
PR.DS-11, PR.PT-01.
"""

    result = _extract_objective_paragraph(raw_text)

    assert "**Objective.**" in result
    assert "Art. 30(3) + Art. 5(2) + Art. 31 GDPR" in result
    assert "**Considerations.**" not in result
    assert "supervisory-authority inspections" in result
    assert "```yaml" not in result
    assert "CSF anchors" not in result
    assert "PR.DS-11" not in result
    assert "A later consideration" not in result


def test_extract_objective_paragraph_handles_missing_marker() -> None:
    text = "The service provider preserves evidence under GDPR Art. 32."

    result = _extract_objective_paragraph(text)

    assert result == "**Objective.** The service provider preserves evidence under GDPR Art. 32."
    assert "**Objective.**" in result
    assert "**Considerations.**" not in result


def test_extract_objective_paragraph_handles_multi_line_objective() -> None:
    text = """**Objective.** The regulated subject maintains evidence under GDPR Art. 30.
The evidence remains traceable and available to the supervisory authority under Art. 31.

**Considerations.**
- Keep the evidence proportional to the company scale.
"""

    result = _extract_objective_paragraph(text)

    assert result.startswith("**Objective.**")
    assert "The regulated subject maintains evidence under GDPR Art. 30." in result
    assert (
        "The evidence remains traceable and available to the supervisory authority under Art. 31."
        in result
    )
    assert "**Considerations.**" not in result
    assert "Keep the evidence proportional" not in result


def test_extract_objective_paragraph_returns_empty_for_empty_input() -> None:
    assert _extract_objective_paragraph("") == ""


def test_extract_objective_paragraph_infers_marker_for_crda_provenance() -> None:
    """When the source HL is a CRDA-deep provenance block without an explicit
    ``**Objective.**`` marker (e.g. D-10 sub-domain files), the function
    surfaces the first sentence of the cleaned paragraph under the canonical
    marker so downstream rendering stays uniform.
    """
    text = """# D-10.1 Continuous Security Monitoring

> **CRDA-deep provenance.** This section was generated from
> [`../../CrossRegulation/DeepAnalysis/D-10.1.md`](../../...).
>
> **Critical note (CRDA flag — Layer 2 review required).** D-10.1
> surfaces **1 CRDA-flagged genuine tension**.

### Participants

| Regulation | Canonical SO | 1-line summary | Scope/angle |
|---|---|---|---|
| GDPR | SO-GDPR-030 | Personal data... | blah |

The continuous-monitoring architecture is **legitimately diverse with one CRDA-flagged genuine tension** — each regulator imposes a distinct monitoring mandate under a distinct anchor.
"""

    result = _extract_objective_paragraph(text)

    assert result.startswith("**Objective.**")
    assert "CRDA-deep provenance" not in result
    assert "The continuous-monitoring architecture" in result


def test_extract_objective_paragraph_stops_at_next_section() -> None:
    text = """**Objective.** The controller maintains records under GDPR Art. 30.

**Considerations.**
- Records remain available on request.

**Something else.**
- A trailing bullet.
"""

    result = _extract_objective_paragraph(text)

    assert result == "**Objective.** The controller maintains records under GDPR Art. 30."
    assert "Considerations" not in result
    assert "Something else" not in result


def test_extract_objective_and_first_consideration_strips_yaml_block() -> None:
    raw_text = """### D-10.2.1 — Sub-SO for GDPR

```yaml
id: SO-D-10.2.GDPR
applies_to: [GDPR]
source_SR: SR-GDPR-044
```

**Objective.** The controller and processor maintain compliance records in writing or in electronic form with integrity and traceability sufficient to demonstrate compliance and to support supervisory-authority inspections (Art. 30(3) + Art. 5(2) + Art. 31 GDPR).

**Considerations.**
- GDPR records must support supervisory-authority inspections and remain available on request.
- A later consideration is not needed in the MAP prompt.

**CSF anchors (from SR-GDPR-044):**
PR.DS-11, PR.PT-01.
"""

    result = _extract_objective_and_first_consideration(raw_text)

    assert "**Objective.**" in result
    assert "Art. 30(3) + Art. 5(2) + Art. 31 GDPR" in result
    assert "**Considerations.**" in result
    assert "supervisory-authority inspections" in result
    assert "```yaml" not in result
    assert "CSF anchors" not in result
    assert "PR.DS-11" not in result
    assert "A later consideration" not in result


def test_extract_objective_handles_missing_considerations() -> None:
    text = "**Objective.** The service provider preserves evidence under GDPR Art. 32."

    result = _extract_objective_and_first_consideration(text)

    assert result == text
    assert "**Considerations.**" not in result


def test_extract_objective_handles_multi_line_objective() -> None:
    text = """**Objective.** The regulated subject maintains evidence under GDPR Art. 30.
The evidence remains traceable and available to the supervisory authority under Art. 31.

**Considerations.**
- Keep the evidence proportional to the company scale.
"""

    result = _extract_objective_and_first_consideration(text)

    assert "The regulated subject maintains evidence under GDPR Art. 30." in result
    assert (
        "The evidence remains traceable and available to the supervisory authority under Art. 31."
        in result
    )


def test_render_subdomains_filters_by_applicable_regs() -> None:
    subs = [
        {
            "id": "D-10.2",
            "title": "Audit Logging",
            "hso_hl": "**Objective.** Maintain audit logs at the domain scope.",
            "hso_per_reg": [
                {"regulation": "GDPR", "objective": "**Objective.** GDPR duty."},
                {"regulation": "NIS2", "objective": "**Objective.** NIS2 duty."},
            ],
        }
    ]

    result = _render_subdomains(subs, applicable_regs=["GDPR"])

    assert "GDPR" in result
    assert "NIS2" not in result
    assert "### D-10.2 — Audit Logging" in result
    assert "**Objective.** Maintain audit logs at the domain scope." in result
    assert "**GDPR Objective.**" in result
    assert "GDPR duty." in result


def test_render_subdomains_emits_per_regulation_bullets() -> None:
    subs = [
        {
            "id": "D-04.1",
            "title": "Risk Identification",
            "hso_hl": "**Objective.** Identify risks at the entity scope.",
            "hso_per_reg": [
                {"regulation": "GDPR", "objective": "**Objective.** GDPR duty."},
                {"regulation": "CRA", "objective": "**Objective.** CRA duty."},
            ],
        }
    ]

    result = _render_subdomains(subs, applicable_regs=["GDPR", "CRA"])

    assert "### D-04.1 — Risk Identification" in result
    assert "**Objective.** Identify risks at the entity scope." in result
    assert "**GDPR Objective.**" in result
    assert "GDPR duty." in result
    assert "**CRA Objective.**" in result
    assert "CRA duty." in result
    assert "#### D-04.1.N" not in result


def test_render_subdomains_no_filter_legacy() -> None:
    subs = [
        {
            "id": "D-10.2",
            "title": "Audit Logging",
            "hso_hl": "**Objective.** Maintain audit logs at the domain scope.",
            "hso_per_reg": [
                {"regulation": "GDPR", "objective": "**Objective.** GDPR duty."},
                {"regulation": "NIS2", "objective": "**Objective.** NIS2 duty."},
            ],
        }
    ]

    result = _render_subdomains(subs, applicable_regs=None)

    assert "GDPR" in result
    assert "NIS2" in result


def test_render_subdomains_caps_objective_at_1500_chars() -> None:
    long_text = "**Objective.** " + ("A" * 2000)
    subs = [
        {
            "id": "D-10.2",
            "title": "Audit Logging",
            "hso_hl": long_text,
            "hso_per_reg": [
                {"regulation": "GDPR", "objective": long_text},
            ],
        }
    ]

    result = _render_subdomains(subs, applicable_regs=["GDPR"])

    assert "_(truncated)_" in result
    for line in result.splitlines():
        assert len(line) <= 1500 + len("_(truncated)_")


def test_render_articles_verbatim_with_safety_net() -> None:
    text = "x" * 6000
    rendered = _render_articles(
        [
            {
                "regulation": "GDPR",
                "article": "Art. 30",
                "title": "Records",
                "text": text,
                "source_file": "GDPR/Articles/Art_30.md",
            }
        ]
    )

    assert "x" * 3000 in rendered
    assert "_(truncated at 3000 chars)_" in rendered
    assert "x" * 3001 not in rendered


def test_render_cross_reg_filters_to_applicable_pairs() -> None:
    entries = [
        {"pair": "GDPR-CRA", "type": "OVERLAP", "summary": "Applicable pair."},
        {"pair": "NIS2-DORA", "type": "OVERLAP", "summary": "Non-applicable pair."},
    ]

    result = _render_cross_reg(entries, applicable_regs=["GDPR", "CRA"])

    assert "GDPR-CRA" in result
    assert "NIS2-DORA" not in result


def test_render_prompt_total_size_for_d10_under_budget() -> None:
    inputs = {
        "case_id": "case1-tinytask",
        "domain_id": "D-10",
        "company_context": {
            "company_name": "TinyTask",
            "sector": "SaaS",
            "scale": "SMALL",
            "employees": 18,
            "security_fte": 1,
            "tech_stack": ["AWS", "Python"],
        },
        "applicable_regs": ["GDPR", "CRA"],
        "subdomains": [
            {
                "id": "D-10.2",
                "title": "Audit Logging & Traceability",
                "hso_hl": (
                    "**Objective.** The regulated subject maintains audit "
                    "logs and traceability at the domain scope."
                ),
                "hso_per_reg": [
                    {
                        "regulation": "GDPR",
                        "objective": "**Objective.** The controller maintains compliance records under GDPR Art. 30(3) and Art. 31.\n\n**Considerations.**\n- Records remain available on request.\n- Omit this bullet.",
                    },
                    {
                        "regulation": "CRA",
                        "objective": "**Objective.** The manufacturer maintains technical documentation under CRA Annex VII §5-§8.",
                    },
                ],
            }
        ],
        "applicable_articles": [
            {"regulation": "GDPR", "article": "Art. 30", "title": "Records", "text": "A" * 1000},
            {
                "regulation": "CRA",
                "article": "Annex VII",
                "title": "Documentation",
                "text": "B" * 1000,
            },
        ],
    }

    prompt = render_prompt(inputs)

    assert len(prompt) <= 10000


def test_render_prompt_drops_ambiguities_stub() -> None:
    inputs = {
        "case_id": "case1-tinytask",
        "domain_id": "D-10",
        "company_context": {"company_name": "TinyTask"},
        "applicable_regs": ["GDPR"],
        "subdomains": [],
        "applicable_articles": [],
        "ambiguities": [
            {"id": "AMB-D10.2-01", "description": "GDPR audit retention floor"},
        ],
        "track_b_suggestion": {"tier": "T2", "rationale": "Not critical path"},
    }

    prompt = render_prompt(inputs)

    section_6 = prompt.split("## 6. KNOWN AMBIGUITIES", 1)[1].split("## 7.", 1)[0]
    assert "(not used at MAP stage)" not in section_6
    assert "AMB-D10.2-01" in section_6
    assert "GDPR audit retention floor" in section_6

    section_7 = prompt.split("## 7. TRACK B SUGGESTION", 1)[1].split("## 8.", 1)[0]
    assert "(not used at MAP stage)" not in section_7
    assert "T2" in section_7
    assert "Not critical path" in section_7


def test_render_prompt_task_excludes_company_specifics() -> None:
    inputs = {
        "case_id": "case1-tinytask",
        "domain_id": "D-10",
        "company_context": {"company_name": "TinyTask"},
        "applicable_regs": ["GDPR"],
        "subdomains": [],
        "applicable_articles": [],
    }

    prompt = render_prompt(inputs)

    # The TASK body sits between the "## 8. TASK" header and the
    # "INPUTS (verbatim, ...)" YAML block marker.
    task_section = prompt.split("## 8. TASK", 1)[1].split("INPUTS (verbatim,", 1)[0]

    # Company-agnostic TASK: no company name, no company-specific scale/FTE/employees
    assert "TinyTask" not in task_section
    assert "Scale to" not in task_section
    # Normalise line wrapping before substring assertions
    task_normalised = " ".join(task_section.split())
    assert "Do NOT mention company" in task_normalised
    assert "generic across companies" in task_normalised

    # The TASK explicitly prohibits the eight connectives. Verify all
    # four initial connectives appear in the prohibition list (with
    # surrounding quotes), not as active instructional prose.
    for connective in ("Furthermore", "Moreover", "Additionally", "Also"):
        assert f'"{connective}"' in task_section or f"“{connective}”" in task_section


def test_render_prompt_output_format_is_per_subdomain() -> None:
    inputs = {
        "case_id": "case1-tinytask",
        "domain_id": "D-10",
        "company_context": {"company_name": "TinyTask"},
        "applicable_regs": ["GDPR"],
        "subdomains": [],
        "applicable_articles": [],
    }

    prompt = render_prompt(inputs)

    output_section = prompt.split("## 9. OUTPUT FORMAT", 1)[1]

    # v1.3 output format: 5-field x 3-blocos structure
    assert "**Generic Objective.**" in output_section
    assert "**GDPR Objective.**" in output_section
    assert "- Original:" in output_section
    assert "- Adapted:" in output_section
    assert "- Rationale:" in output_section
    assert "- Adjustments needed:" in output_section
    assert "**Considerations.**" in output_section
    # Legacy contract keys MUST be absent (Phase 3 dropped them).
    assert "ADAPTED_OBJECTIVE:" not in output_section
    assert "KEY_ADJUSTMENTS:" not in output_section
    assert "CONFIDENCE: HIGH | MEDIUM | LOW" not in output_section


def test_extract_objective_paragraph_handles_d10_2_hl_with_noise() -> None:
    raw = """### D-10.2 — Audit Logging & Traceability

> CRDA-deep provenance: SR-GDPR-044 / SR-CRA-021 (composed via LLM-SR-MERGE).

## Participants

| Role | Owner |
|---|---|
| DPA | Internal |
| NCA | TBD |

**Objective.** Audit logging and traceability are established through a layered audit-records architecture spanning compliance records, application logs, infrastructure telemetry, and security event monitoring; retention floors are set per record class, with supervisory-authority inspections support and integrity guarantees anchored in GDPR Art. 30 + Art. 5(2) and CRA Annex I §1(2)(f) + Annex VII §5-§8.

**Considerations.**
- Retention floor (24 months for compliance records, 12 months for application logs).
- Integrity via hash chain + WORM storage.

**CSF anchors:** PR.PT-01, PR.DS-11.
"""

    result = _extract_objective_paragraph(raw)

    assert result.startswith("**Objective.** Audit logging and traceability")
    assert "CRDA-deep provenance" not in result
    assert "Participants" not in result
    assert "**Considerations.**" not in result
    assert "CSF anchors" not in result
    assert "supervisory-authority inspections" in result


def test_render_subdomains_d10_2_format() -> None:
    subs = [
        {
            "id": "D-10.2",
            "title": "D-10.2 Audit Logging & Traceability",
            "hso_hl": """### D-10.2 — Audit Logging & Traceability

> CRDA-deep provenance: SR-GDPR-044.

**Objective.** Audit logging and traceability are established through a layered audit-records architecture spanning compliance records, application logs, and security event monitoring with supervisory-authority inspections support.

**Considerations.**
- Retention floor 24 months.

**CSF anchors:** PR.PT-01.
""",
            "hso_per_reg": [
                {
                    "regulation": "GDPR",
                    "objective": "**Objective.** The controller and processor maintain compliance records in writing or in electronic form with integrity and traceability sufficient to demonstrate compliance and to support supervisory-authority inspections (Art. 30(3) + Art. 5(2) + Art. 31 GDPR).\n\n**Considerations.**\n- Records must remain available on supervisory-authority request.",
                },
                {
                    "regulation": "CRA",
                    "objective": "**Objective.** The manufacturer establishes audit logging across the product lifecycle to support conformity assessment under CRA Annex VII §5-§8 and post-market monitoring under Art. 13.",
                },
            ],
        }
    ]

    result = _render_subdomains(subs, applicable_regs=["GDPR", "CRA"])

    assert "### D-10.2 — D-10.2 Audit Logging & Traceability" in result
    assert "**Objective.** Audit logging and traceability" in result
    assert "**Generic Objective.**" in result
    assert "**GDPR Objective.**" in result
    assert "**CRA Objective.**" in result
    assert "- Retention floor 24 months." in result
    assert "CRDA-deep provenance" not in result


def test_render_ambiguities_with_real_data() -> None:
    ambigs = [
        {
            "id": "AMB-D10.2-01",
            "description": "GDPR audit retention floor (24 months) vs CRA test reports retention.",
            "resolution": "Set floor at 24 months for both; CRA minimum is satisfied.",
        },
    ]

    rendered = _render_ambiguities(ambigs)

    assert "AMB-D10.2-01" in rendered
    assert "GDPR audit retention floor" in rendered
    assert "Resolution:" in rendered


def test_render_ambiguities_empty_returns_message() -> None:
    rendered = _render_ambiguities([])
    assert rendered == "_No applicable ambiguities for this domain._"


# ─── v1.3 considerations + 5-field shape ───────────────────────────────


def test_extract_considerations_basic() -> None:
    raw = """**Objective.** The controller maintains records under GDPR Art. 30.

**Considerations.**
- Records remain available on request.
- Records must support supervisory-authority inspections.
- Tail bullets are also valid.
"""

    result = _extract_considerations(raw)

    assert "- Records remain available on request." in result
    assert "- Records must support supervisory-authority inspections." in result
    assert "- Tail bullets are also valid." in result
    # Header itself is not part of the returned block.
    assert "**Considerations.**" not in result


def test_extract_considerations_missing() -> None:
    text = "**Objective.** The service provider preserves evidence under GDPR Art. 32."

    result = _extract_considerations(text)

    assert result == ""


def test_extract_considerations_with_yaml_frontmatter() -> None:
    raw = """---
id: SO-D-10.2.GDPR
applies_to: [GDPR]
---

**Objective.** The controller maintains records (Art. 30 GDPR).

**Considerations.**
- Records remain available on supervisory request.
- A second verbatim bullet.
"""

    result = _extract_considerations(raw)

    assert result.startswith("- Records remain available")
    assert "A second verbatim bullet." in result
    assert "id: SO-D-10.2.GDPR" not in result


def test_render_subdomains_d10_2_includes_considerations() -> None:
    subs = [
        {
            "id": "D-10.2",
            "title": "Audit Logging & Traceability",
            "hso_hl": (
                "**Objective.** Audit logging and traceability are established "
                "through a layered audit-records architecture.\n\n"
                "**Considerations.**\n"
                "- HL consideration 1 verbatim.\n"
                "- HL consideration 2 verbatim."
            ),
            "hso_per_reg": [
                {
                    "regulation": "GDPR",
                    "objective": (
                        "**Objective.** The controller maintains compliance "
                        "records under GDPR Art. 30(3).\n\n"
                        "**Considerations.**\n"
                        "- GDPR consideration A verbatim.\n"
                        "- GDPR consideration B verbatim."
                    ),
                },
                {
                    "regulation": "CRA",
                    "objective": (
                        "**Objective.** The manufacturer maintains technical "
                        "documentation under CRA Annex VII §5-§8.\n\n"
                        "**Considerations.**\n"
                        "- CRA consideration X verbatim."
                    ),
                },
            ],
        }
    ]

    result = _render_subdomains(subs, applicable_regs=["GDPR", "CRA"])

    # HL block: Objective + Considerations
    assert "**Generic Objective.**" in result
    assert "**Objective.** Audit logging and traceability are established" in result
    assert "**Considerations.**" in result
    assert "- HL consideration 1 verbatim." in result
    assert "- HL consideration 2 verbatim." in result

    # Per-regulation blocks
    assert "**GDPR Objective.**" in result
    assert "- GDPR consideration A verbatim." in result
    assert "- GDPR consideration B verbatim." in result
    assert "**CRA Objective.**" in result
    assert "- CRA consideration X verbatim." in result


def test_render_subdomains_d10_2_block_headers() -> None:
    subs = [
        {
            "id": "D-10.2",
            "title": "Audit Logging & Traceability",
            "hso_hl": "**Objective.** Audit-logging architecture is layered.\n\n**Considerations.**\n- HL bullet.",
            "hso_per_reg": [
                {"regulation": "GDPR", "objective": "**Objective.** GDPR duty.\n\n**Considerations.**\n- GDPR bullet."},
                {"regulation": "CRA", "objective": "**Objective.** CRA duty.\n\n**Considerations.**\n- CRA bullet."},
            ],
        }
    ]

    result = _render_subdomains(subs, applicable_regs=["GDPR", "CRA"])

    assert "**Generic Objective.**" in result
    assert "**GDPR Objective.**" in result
    assert "**CRA Objective.**" in result

    # v1.3 prohibits `**Directed objectives.**` (legacy v1.2 header).
    assert "**Directed objectives.**" not in result


def test_render_subdomains_d10_2_truncates_considerations() -> None:
    long_cons = "**Considerations.**\n" + ("- X" + "Y" * 1600 + "\n")
    subs = [
        {
            "id": "D-10.2",
            "title": "Audit Logging",
            "hso_hl": "**Objective.** HL sentence.\n\n" + long_cons,
            "hso_per_reg": [],
        }
    ]

    result = _render_subdomains(subs, applicable_regs=None)

    assert "_(truncated)_" in result


def test_render_track_b_with_attrs() -> None:
    suggestion = {
        "tier": "T2",
        "rationale": "Audit logging aligns with existing SIEM investment; minimal marginal cost.",
        "attrs": {
            "inheritability": "partial",
            "scale": "S",
            "by_subdomain": {
                "D-10.2": {"tier": "T2", "priority": "P1", "inheritability": "partial"},
            },
        },
    }

    rendered = _render_track_b(suggestion)

    assert "**Tier**: T2" in rendered
    assert "**Rationale**: Audit logging aligns" in rendered
    assert "**Inheritability**: partial" in rendered
    assert "**Scale**: S" in rendered
    assert "**Per sub-domain:**" in rendered
    assert "`D-10.2`: tier=T2, priority=P1, inheritability=partial" in rendered


def test_render_track_b_empty_returns_message() -> None:
    rendered = _render_track_b({})
    assert rendered == "_No Track B suggestion._"
