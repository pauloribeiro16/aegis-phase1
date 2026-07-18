"""Tests for OutputParser (v2/domain/parser.py).

Covers the happy path, every error path, and feedback generation for
retry. Regex edge cases (trailing whitespace, code fences, lowercase
confidence) are also exercised. OutputParserV2 is exercised separately
in the V2 section below (per-sub-domain v1.2 spec).
"""

from __future__ import annotations

import pytest

from aegis_phase1.v2.domain.parser import (
    ObjectiveBlock,
    OutputParser,
    OutputParserV2,
    OutputParserV3,
    ParseResult,
    ParseResultV2,
    ParseResultV3,
    SubdomainAdaptation,
    SubdomainAdaptationV3,
)


@pytest.fixture
def parser() -> OutputParser:
    return OutputParser()


# ─── Happy path ────────────────────────────────────────────────────────


def test_parses_well_formed_output(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: This is the adapted objective spanning\n"
        "three sentences for the domain. It references the company reality.\n"
        "It is bounded by proportionality.\n"
        "KEY_ADJUSTMENTS:\n"
        "- added explicit incident classification\n"
        "- tightened 24h notification target\n"
        "- excluded redundant sub-domain\n"
        "CONFIDENCE: HIGH"
    )

    result = parser.parse(raw)
    assert result.success is True
    assert "adapted objective" in result.adapted_objective.lower()
    assert len(result.key_adjustments) == 3
    assert result.confidence == "HIGH"
    assert result.error_feedback == ""


def test_parses_multiline_adapted_objective(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: First sentence.\n"
        "Second sentence.\n"
        "KEY_ADJUSTMENTS:\n"
        "- adj 1\n"
        "- adj 2\n"
        "CONFIDENCE: MEDIUM"
    )

    result = parser.parse(raw)
    assert result.success is True
    assert "First sentence." in result.adapted_objective
    assert "Second sentence." in result.adapted_objective
    assert result.confidence == "MEDIUM"


def test_parses_lowercase_confidence(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: Objective text.\n"
        "KEY_ADJUSTMENTS:\n"
        "- one\n"
        "CONFIDENCE: low"
    )

    result = parser.parse(raw)
    assert result.success is True
    assert result.confidence == "LOW"


def test_parses_with_code_fences(parser: OutputParser) -> None:
    raw = (
        "```\n"
        "ADAPTED_OBJECTIVE: Objective.\n"
        "KEY_ADJUSTMENTS:\n"
        "- one\n"
        "CONFIDENCE: HIGH\n"
        "```"
    )

    result = parser.parse(raw)
    assert result.success is True
    assert result.confidence == "HIGH"
    assert len(result.key_adjustments) == 1


def test_parses_strips_bullet_punctuation_and_quotes(parser: OutputParser) -> None:
    raw = (
        'ADAPTED_OBJECTIVE: obj.\n'
        'KEY_ADJUSTMENTS:\n'
        '-  "quoted adjustment"\n'
        "- 'another'\n"
        "CONFIDENCE: HIGH"
    )

    result = parser.parse(raw)
    assert result.success
    assert result.key_adjustments == ["quoted adjustment", "another"]


def test_parses_five_adjustments(parser: OutputParser) -> None:
    bullets = "\n".join(f"- adj {i}" for i in range(1, 6))
    raw = (
        "ADAPTED_OBJECTIVE: obj.\n"
        f"KEY_ADJUSTMENTS:\n{bullets}\n"
        "CONFIDENCE: HIGH"
    )

    result = parser.parse(raw)
    assert result.success
    assert len(result.key_adjustments) == 5


# ─── Error paths ───────────────────────────────────────────────────────


def test_missing_adapted_objective_feedback(parser: OutputParser) -> None:
    raw = "KEY_ADJUSTMENTS:\n- one\nCONFIDENCE: HIGH"
    result = parser.parse(raw)
    assert result.success is False
    assert "ADAPTED_OBJECTIVE" in result.error_feedback
    assert result.adapted_objective == ""


def test_missing_adjustments_feedback(parser: OutputParser) -> None:
    raw = "ADAPTED_OBJECTIVE: Some objective text.\nCONFIDENCE: HIGH"
    result = parser.parse(raw)
    assert result.success is False
    assert "KEY_ADJUSTMENTS" in result.error_feedback
    assert result.key_adjustments == []


def test_missing_confidence_defaults_to_low_with_feedback(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: Objective.\n"
        "KEY_ADJUSTMENTS:\n- one\n"
        "CONFIDENCE: BOGUS"
    )
    result = parser.parse(raw)
    assert result.success is False
    assert result.confidence == "LOW"
    assert "CONFIDENCE" in result.error_feedback


def test_missing_all_sections(parser: OutputParser) -> None:
    raw = "no format here"
    result = parser.parse(raw)
    assert result.success is False
    assert "ADAPTED_OBJECTIVE" in result.error_feedback
    assert "KEY_ADJUSTMENTS" in result.error_feedback
    assert "CONFIDENCE" in result.error_feedback


def test_empty_string_returns_failure(parser: OutputParser) -> None:
    result = parser.parse("")
    assert result.success is False
    assert result.error_feedback


def test_none_input_returns_clean_failure(parser: OutputParser) -> None:
    result = parser.parse(None)  # type: ignore[arg-type]
    assert result.success is False
    assert "Empty" in result.error_feedback


def test_adjustments_without_dash_prefix(parser: OutputParser) -> None:
    raw = (
        "ADAPTED_OBJECTIVE: obj.\n"
        "KEY_ADJUSTMENTS:\n"
        "first item\n"
        "second item\n"
        "CONFIDENCE: HIGH"
    )
    result = parser.parse(raw)
    assert result.success is False
    assert "KEY_ADJUSTMENTS" in result.error_feedback


def test_parse_result_is_immutable_namedtuple() -> None:
    """ParseResult is a NamedTuple — verifying the contract."""
    r = ParseResult(
        success=True,
        adapted_objective="x",
        key_adjustments=["a"],
        confidence="HIGH",
        error_feedback="",
    )
    assert r.success is True
    assert r.adapted_objective == "x"
    assert r.key_adjustments == ["a"]
    assert r.confidence == "HIGH"
    assert r.error_feedback == ""
    # NamedTuples are iterable for backwards compat
    assert tuple(r) == (True, "x", ["a"], "HIGH", "")


# ─── Retry-feedback round-trip ─────────────────────────────────────────


def test_parser_feedback_is_suitable_for_retry_prompt(parser: OutputParser) -> None:
    """The feedback string is non-empty and references actionable keywords
    so the orchestrator can pass it to render_prompt(feedback=...)."""
    raw = "garbage"
    result = parser.parse(raw)
    assert result.success is False
    assert result.error_feedback
    # Must contain at least one of the section names so the LLM can fix it.
    lowered = result.error_feedback.lower()
    assert any(
        keyword in lowered
        for keyword in ("adapted_objective", "key_adjustments", "confidence")
    )


# ─── V2: OutputParserV2 (per-sub-domain v1.2 spec) ─────────────────────


@pytest.fixture
def parser_v2() -> OutputParserV2:
    return OutputParserV2()


@pytest.fixture
def three_block_output() -> str:
    """Canonical 3-block per-sub-domain v1.2 output."""
    return (
        "### D-10.1 — Continuous Monitoring\n"
        "**Objective.** Continuous monitoring is established through a "
        "layered telemetry architecture that captures application, "
        "infrastructure, and security events.\n\n"
        "**Directed objectives.**\n"
        "- **GDPR**: Art. 32(1)(d) requires regular testing of security "
        "measures and effective monitoring.\n"
        "- **CRA**: Annex I Part I §1(2)(h) requires monitoring of "
        "vulnerabilities and effectiveness of implemented controls.\n"
        "\n"
        "### D-10.2 — Audit Logging & Traceability\n"
        "**Objective.** Audit logging and traceability are established "
        "through a layered audit-records architecture.\n\n"
        "**Directed objectives.**\n"
        "- **GDPR**: Art. 5(2) accountability requires ability to "
        "demonstrate compliance; Art. 32(1)(b) requires testing.\n"
        "- **CRA**: Annex I Part II §(6) requires automatic logging of "
        "security-relevant events; Annex I Part I §1(2)(k) requires "
        "monitoring.\n"
        "\n"
        "### D-10.3 — Compliance Testing\n"
        "**Objective.** Compliance testing is established through "
        "scheduled control reviews.\n\n"
        "**Directed objectives.**\n"
        "- **GDPR**: Art. 28(3)(g) requires processor audit trail.\n"
        "- **CRA**: Annex I Part I §1(2)(j) requires testing of "
        "effectiveness of cybersecurity measures.\n"
    )


def test_v2_parses_three_subdomains(
    parser_v2: OutputParserV2, three_block_output: str,
) -> None:
    result = parser_v2.parse(three_block_output)
    assert result.success is True
    assert isinstance(result, ParseResultV2)
    assert len(result.subdomains) == 3
    for s in result.subdomains:
        assert isinstance(s, SubdomainAdaptation)
        assert s.hl_objective.startswith("**Objective.**")
        assert len(s.directed) >= 1
    # Sub-domain IDs are extracted in order
    assert [s.subdomain_id for s in result.subdomains] == [
        "D-10.1", "D-10.2", "D-10.3",
    ]


def test_v2_handles_single_subdomain(parser_v2: OutputParserV2) -> None:
    raw = (
        "### D-04.2 — Detection and Triage\n"
        "**Objective.** Establish detection capabilities with documented "
        "triage steps and thresholds.\n\n"
        "**Directed objectives.**\n"
        "- **GDPR**: Art. 32(1)(d) requires regular testing.\n"
        "- **CRA**: Annex I Part II requires handling of vulnerabilities.\n"
    )
    result = parser_v2.parse(raw)
    assert result.success is True
    assert len(result.subdomains) == 1
    sub = result.subdomains[0]
    assert sub.subdomain_id == "D-04.2"
    assert sub.title == "Detection and Triage"
    assert len(sub.directed) == 2


def test_v2_handles_block_with_only_hl(parser_v2: OutputParserV2) -> None:
    raw = (
        "### D-04.1 — Incident Response Planning\n"
        "**Objective.** Maintain a documented incident response plan "
        "tailored to TinyTask scope.\n"
    )
    result = parser_v2.parse(raw)
    assert result.success is True
    assert len(result.subdomains) == 1
    sub = result.subdomains[0]
    assert sub.hl_objective.startswith("**Objective.**")
    assert sub.directed == []


def test_v2_handles_block_with_only_directed(parser_v2: OutputParserV2) -> None:
    raw = (
        "### D-04.2 — Detection and Triage\n"
        "**Directed objectives.**\n"
        "- **GDPR**: Art. 32(1)(d) requires regular testing.\n"
        "- **CRA**: Annex I Part II requires handling of vulnerabilities.\n"
    )
    result = parser_v2.parse(raw)
    assert result.success is True
    assert len(result.subdomains) == 1
    sub = result.subdomains[0]
    assert sub.hl_objective == "(missing HL — only directed objectives provided)"
    assert len(sub.directed) == 2


def test_v2_legacy_adapted_objective_concatenates_hls(
    parser_v2: OutputParserV2, three_block_output: str,
) -> None:
    result = parser_v2.parse(three_block_output)
    assert result.success is True
    ao = result.legacy_adapted_objective
    # All 3 HLs are concatenated with double-newlines
    assert ao.count("**Objective.**") == 3
    assert "\n\n" in ao
    assert (
        "**Objective.** Continuous monitoring" in ao
    )
    assert (
        "**Objective.** Audit logging" in ao
    )
    assert (
        "**Objective.** Compliance testing" in ao
    )


def test_v2_handles_no_heading(parser_v2: OutputParserV2) -> None:
    raw = (
        "**Objective.** Goal without any heading.\n\n"
        "**Directed objectives.**\n"
        "- **GDPR**: x.\n"
    )
    result = parser_v2.parse(raw)
    # No heading → single "unknown" block (lenient path)
    assert result.success is True
    assert len(result.subdomains) == 1
    assert result.subdomains[0].subdomain_id == "unknown"


def test_v2_empty_input(parser_v2: OutputParserV2) -> None:
    assert parser_v2.parse(None).success is False  # type: ignore[arg-type]
    assert parser_v2.parse("").success is False
    assert parser_v2.parse("   \n  ").success is False
    assert parser_v2.parse(None).error_feedback  # type: ignore[arg-type]


def test_v2_strips_code_fences(parser_v2: OutputParserV2) -> None:
    inner = (
        "### D-04.1 — Incident Response Planning\n"
        "**Objective.** Maintain a documented plan.\n\n"
        "**Directed objectives.**\n"
        "- **GDPR**: x.\n"
        "- **CRA**: y.\n"
    )
    raw = "```\n" + inner + "\n```"
    result = parser_v2.parse(raw)
    assert result.success is True
    assert len(result.subdomains) == 1
    assert result.subdomains[0].subdomain_id == "D-04.1"
    assert result.subdomains[0].hl_objective.startswith("**Objective.**")
    assert len(result.subdomains[0].directed) == 2


def test_v2_subdomain_adaptation_as_dict(parser_v2: OutputParserV2) -> None:
    s = SubdomainAdaptation(
        subdomain_id="D-10.2",
        title="Audit Logging & Traceability",
        hl_objective="**Objective.** Audit logging established.",
        directed=[{"regulation": "GDPR", "objective": "Art. 5(2)"}],
    )
    d = s.as_dict()
    assert d["subdomain_id"] == "D-10.2"
    assert d["title"] == "Audit Logging & Traceability"
    assert d["hl_objective"].startswith("**Objective.**")
    assert d["directed"] == [{"regulation": "GDPR", "objective": "Art. 5(2)"}]


def test_v2_handles_en_dash_in_heading(parser_v2: OutputParserV2) -> None:
    raw = (
        "### D-04.1 — Incident Response Planning\n"
        "**Objective.** Maintain a documented incident response plan.\n\n"
        "**Directed objectives.**\n"
        "- **GDPR**: Art. 32 requires testing.\n"
    )
    result = parser_v2.parse(raw)
    assert result.success is True
    assert result.subdomains[0].title == "Incident Response Planning"


# ─── V3: OutputParserV3 (per-sub-domain 3 blocks x 5 fields v1.3 spec) ──


@pytest.fixture
def parser_v3() -> OutputParserV3:
    return OutputParserV3()


@pytest.fixture
def worked_example_d10_2() -> str:
    """Worked example for D-10.2 from CONTRACT-022 Phase 3."""
    return (
        "### D-10.2 — Audit Logging & Traceability\n\n"
        "**Generic Objective.**\n"
        "- Original: Audit logging and traceability are established through a "
        "layered audit-records architecture spanning compliance records with "
        "integrity and traceability.\n"
        "- Adapted: Audit logging and traceability are established through a "
        "2-layer audit-records architecture spanning entity-level compliance "
        "records (GDPR) and product-level technical documentation traceability "
        "(CRA).\n"
        "- Rationale: Source HL describes 4 layers (GDPR/CRA/DORA/AI_Act); for "
        "this regulatory perimeter only GDPR + CRA apply.\n"
        "- Adjustments needed: Drop DORA Art. 9(4)(a) CIA+A policy layer and "
        "AI Act Art. 12(1)+(2) automatic event logging layer from scope.\n"
        "**Considerations.**\n"
        "- 4 of 5 regulations participate (GDPR, CRA, DORA, AI Act — NIS 2 is "
        "fully out-of-scope per CRDA T3-vs-text gap).\n"
        "- CRDA-deep verified (6 pairs: 6 SAME — COMPLEMENTARY — no EQUAL).\n"
        "- Notable OJ-consistent reconciliation (NOT a tension) — "
        "floor-within-ceiling pattern.\n\n"
        "**GDPR Objective.**\n"
        "- Original: The controller and processor maintain compliance records "
        "in writing or in electronic form with integrity and traceability "
        "(Art. 30(3) + Art. 5(2) + Art. 31 GDPR).\n"
        "- Adapted: The controller and processor maintain compliance records "
        "in writing or in electronic form with integrity and traceability. "
        "For a micro-entity with limited security FTE, this is operationalised "
        "through lightweight electronic records with a defined retention "
        "envelope.\n"
        "- Rationale: Original is already applicable (GDPR is in scope); "
        "adaptation adds operationalisation guidance for micro-scale entities.\n"
        "- Adjustments needed: Define retention envelope explicitly. Establish "
        "record integrity controls.\n"
        "**Considerations.**\n"
        "- GDPR's anchor is the strictest for personal data on the at-rest "
        "dimension even where CRA state-of-the-art is the strictest in "
        "absolute terms.\n"
        "- The `appropriate` threshold is anchored by the five Art. 32(1) "
        "preamble factors.\n"
        "- Records include RoPA, consent, processor contracts, breach "
        "notifications, DPIA.\n\n"
        "**CRA Objective.**\n"
        "- Original: The manufacturer maintains the technical documentation "
        "(Annex VII §5-§8 CRA — harmonised standards applied, test reports).\n"
        "- Adapted: The manufacturer maintains the technical documentation "
        "(Annex VII §5-§8 CRA), preserves the cybersecurity risk-assessment "
        "documentation. For a micro-entity product, the technical documentation "
        "may leverage existing CI pipelines for test reports.\n"
        "- Rationale: Original is already applicable (CRA is in scope); "
        "adaptation adds operationalisation guidance for micro-scale product "
        "manufacturers.\n"
        "- Adjustments needed: Define support period explicitly. Implement "
        "SBOM generation as part of the build pipeline.\n"
        "**Considerations.**\n"
        "- CRA's anchor is the strictest in absolute terms (state-of-the-art "
        "harmonised-standards floor).\n"
        "- 10-year or support-period retention aligns with D-09.4 Records of "
        "Processing.\n"
        "- Test reports (Annex VII §6) and risk-assessment documentation "
        "(Annex VII §3) are the operational artefacts that MSAs inspect.\n"
    )


def test_v3_parses_3_blocks_5_fields(
    parser_v3: OutputParserV3, worked_example_d10_2: str,
) -> None:
    result = parser_v3.parse(worked_example_d10_2)
    assert result.success is True
    assert isinstance(result, ParseResultV3)
    assert len(result.subdomains) == 1
    sub = result.subdomains[0]
    assert isinstance(sub, SubdomainAdaptationV3)
    assert sub.subdomain_id == "D-10.2"
    assert sub.title == "Audit Logging & Traceability"
    assert len(sub.blocks) == 3
    expected_labels = ["Generic Objective.", "GDPR Objective.", "CRA Objective."]
    actual_labels = [b.label for b in sub.blocks]
    assert actual_labels == expected_labels
    for block in sub.blocks:
        assert isinstance(block, ObjectiveBlock)
        assert block.has_all_5_fields(), (
            f"Block {block.label} missing fields: "
            f"original={bool(block.original)} adapted={bool(block.adapted)} "
            f"rationale={bool(block.rationale)} "
            f"adjustments={bool(block.adjustments)} "
            f"considerations={bool(block.considerations)}"
        )


def test_v3_parses_multiple_subdomains(parser_v3: OutputParserV3) -> None:
    raw = (
        "### D-10.1 — Continuous Monitoring\n\n"
        "**Generic Objective.**\n"
        "- Original: Generic HL for monitoring.\n"
        "- Adapted: Generic adapted.\n"
        "- Rationale: Why adapted.\n"
        "- Adjustments needed: Adjust A.\n"
        "**Considerations.**\n"
        "- bullet 1.\n"
        "- bullet 2.\n\n"
        "**GDPR Objective.**\n"
        "- Original: GDPR HL.\n"
        "- Adapted: GDPR adapted.\n"
        "- Rationale: Why.\n"
        "- Adjustments needed: Adjust B.\n"
        "**Considerations.**\n"
        "- gdpr bullet.\n\n"
        "**CRA Objective.**\n"
        "- Original: CRA HL.\n"
        "- Adapted: CRA adapted.\n"
        "- Rationale: Why.\n"
        "- Adjustments needed: Adjust C.\n"
        "**Considerations.**\n"
        "- cra bullet.\n\n"
        "### D-10.2 — Audit Logging & Traceability\n\n"
        "**Generic Objective.**\n"
        "- Original: Generic HL for audit logging.\n"
        "- Adapted: Generic adapted audit.\n"
        "- Rationale: Why adapted.\n"
        "- Adjustments needed: Adjust D.\n"
        "**Considerations.**\n"
        "- bullet 1.\n\n"
        "**GDPR Objective.**\n"
        "- Original: GDPR audit HL.\n"
        "- Adapted: GDPR audit adapted.\n"
        "- Rationale: Why.\n"
        "- Adjustments needed: Adjust E.\n"
        "**Considerations.**\n"
        "- gdpr audit bullet.\n\n"
        "**CRA Objective.**\n"
        "- Original: CRA audit HL.\n"
        "- Adapted: CRA audit adapted.\n"
        "- Rationale: Why.\n"
        "- Adjustments needed: Adjust F.\n"
        "**Considerations.**\n"
        "- cra audit bullet.\n"
    )
    result = parser_v3.parse(raw)
    assert result.success is True
    assert len(result.subdomains) == 2
    assert result.subdomains[0].subdomain_id == "D-10.1"
    assert result.subdomains[1].subdomain_id == "D-10.2"
    for sub in result.subdomains:
        assert len(sub.blocks) == 3


def test_v3_missing_field_marks_block_partial(parser_v3: OutputParserV3) -> None:
    """A block with only Original is parsed but has_all_5_fields is False."""
    raw = (
        "### D-10.2 — Audit Logging & Traceability\n\n"
        "**Generic Objective.**\n"
        "- Original: Only the original text.\n"
    )
    result = parser_v3.parse(raw)
    assert result.success is True
    assert len(result.subdomains) == 1
    assert len(result.subdomains[0].blocks) == 1
    block = result.subdomains[0].blocks[0]
    assert block.label == "Generic Objective."
    assert block.original == "Only the original text."
    assert block.has_all_5_fields() is False


def test_v3_no_subdomain_heading_single_block(parser_v3: OutputParserV3) -> None:
    """Without a `### D-XX.Y` heading the parser still extracts a single block."""
    raw = (
        "**Generic Objective.**\n"
        "- Original: Text without a heading.\n"
        "- Adapted: Adapted text.\n"
        "- Rationale: Why.\n"
        "- Adjustments needed: Adjust.\n"
        "**Considerations.**\n"
        "- bullet 1.\n"
        "- bullet 2.\n"
    )
    result = parser_v3.parse(raw)
    assert result.success is True
    assert len(result.subdomains) == 1
    sub = result.subdomains[0]
    assert sub.subdomain_id == "unknown"
    assert sub.title == "unknown"
    assert len(sub.blocks) == 1


def test_v3_empty_input(parser_v3: OutputParserV3) -> None:
    assert parser_v3.parse(None).success is False  # type: ignore[arg-type]
    assert parser_v3.parse("").success is False
    assert parser_v3.parse("   \n  ").success is False
    fb = parser_v3.parse(None).error_feedback  # type: ignore[arg-type]
    assert fb
    assert "Empty" in fb


def test_v3_strips_code_fences(
    parser_v3: OutputParserV3, worked_example_d10_2: str,
) -> None:
    raw = "```\n" + worked_example_d10_2 + "\n```"
    result = parser_v3.parse(raw)
    assert result.success is True
    assert len(result.subdomains) == 1
    assert len(result.subdomains[0].blocks) == 3
    for block in result.subdomains[0].blocks:
        assert block.has_all_5_fields()


def test_v3_considerations_bullets_preserved(parser_v3: OutputParserV3) -> None:
    raw = (
        "### D-10.2 — Audit Logging\n\n"
        "**Generic Objective.**\n"
        "- Original: HL text.\n"
        "- Adapted: Adapted text.\n"
        "- Rationale: Why.\n"
        "- Adjustments needed: Adjust.\n"
        "**Considerations.**\n"
        "- First consideration verbatim.\n"
        "- Second consideration verbatim.\n"
        "- Third consideration verbatim.\n"
    )
    result = parser_v3.parse(raw)
    assert result.success is True
    block = result.subdomains[0].blocks[0]
    assert len(block.considerations) == 3
    assert block.considerations[0] == "First consideration verbatim."
    assert block.considerations[1] == "Second consideration verbatim."
    assert block.considerations[2] == "Third consideration verbatim."


def test_v3_legacy_adapted_objective_concatenates_blocks(
    parser_v3: OutputParserV3, worked_example_d10_2: str,
) -> None:
    """legacy_adapted_objective = all block.adapted joined by ``\\n\\n``."""
    result = parser_v3.parse(worked_example_d10_2)
    ao = result.legacy_adapted_objective
    assert "2-layer audit-records architecture" in ao
    assert "operationalised through lightweight electronic records" in ao
    assert "may leverage existing CI pipelines for test reports" in ao
    assert ao.count("\n\n") == 2  # 3 blocks → 2 separators
