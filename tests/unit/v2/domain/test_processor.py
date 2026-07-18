"""Unit tests for the v2 DomainProcessor (Option C — direct Ollama).

These tests use a :class:`MockInvoker` with scripted responses so the
suite stays hermetic and does NOT need a live Ollama instance.

Coverage:
    - test_ok_first_try                 first attempt succeeds
    - test_parse_fail_retry_with_feedback  parse fails twice then succeeds
    - test_retries_exhausted_returns_failed  all retries fail
    - test_ollama_exception_raises_OllamaUnreachable
    - test_input_assembly_failure_returns_failed
    - test_subdomain_summary_includes_subdomains
    - test_coverage_substantive_when_two_regs
    - test_log_writes_jsonl
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aegis_phase1.v2.domain.processor import (
    DOMAIN_NAMES,
    DomainProcessor,
    MapPartialFailure,
    OllamaUnreachable,
)
from aegis_phase1.v2.llm import MockInvoker


# make_empty_state is a factory function in tests/unit/v2/domain/filters/conftest.py
# Re-declare it here to keep the test hermetic without importing conftest as a module.
def _make_empty_state() -> dict:
    """Minimal V2State with no context/ontology (assemble_inputs raises)."""
    return {
        "current_stage": "INIT",
        "case_path": "",
        "preprocessing_path": "",
        "company_context": None,
        "taxonomy_entries": [],
        "ontology": {},
        "regulations": [],
        "subdomains": {},
        "preprocessing": {},
        "domain_results": {},
        "aggregated_data": {},
        "output_paths": {},
        "errors": [],
    }


VALID_OUTPUT = (
    "### D-04.1 — Incident Response Planning\n"
    "**Objective.** Maintain a documented incident response plan tailored "
    "to TinyTask scope.\n\n"
    "**Directed objectives.**\n"
    "- **GDPR**: Art. 33 requires breach notification within 72 hours to "
    "the supervisory authority.\n"
    "- **CRA**: Annex I Part I requires incident handling and disclosure "
    "aligned with EN ISO/IEC 30111.\n\n"
    "### D-04.2 — Detection and Triage\n"
    "**Objective.** Establish detection capabilities with documented "
    "triage steps and thresholds.\n\n"
    "**Directed objectives.**\n"
    "- **GDPR**: Art. 32(1)(d) requires regular testing of effectiveness.\n"
    "- **CRA**: Annex I Part II requires handling of vulnerabilities.\n"
)

INVALID_OUTPUT_NO_OBJECTIVE = "**Directed objectives.**\n- **GDPR**: just a directive"
INVALID_OUTPUT_NO_HEADINGS = (
    "**Objective.** Objective text without proper heading.\n"
    "**Directed objectives.**\n"
    "- **GDPR**: x\n"
)


class _ExplodingInvoker:
    """Invoker that always raises — used to test OllamaUnreachable."""

    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc or ConnectionError("Ollama not reachable")
        self.calls = 0

    def invoke(
        self,
        prompt: str,
        feedback: str = "",
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        raise self.exc


class _FailingStatusInvoker:
    """Invoker that returns FAILED_AFTER_RETRIES status on every call."""

    def __init__(self) -> None:
        self.calls = 0

    def invoke(
        self,
        prompt: str,
        feedback: str = "",
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls += 1
        return {"raw": "", "status": "FAILED_AFTER_RETRIES", "error": "boom"}


# ─── Happy path ────────────────────────────────────────────────────────


def test_ok_first_try(mock_state) -> None:
    """Mock returns valid output on first call → llm_status=OK."""
    invoker = MockInvoker(script=[{"raw": VALID_OUTPUT, "status": "OK"}])
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "OK"
    assert result["domain_id"] == "D-04"
    assert result["domain_name"] == DOMAIN_NAMES["D-04"]
    assert "**Objective.**" in result["adapted_objective"]
    assert len(result["key_changes"]) == 0
    assert result["confidence"] == "UNKNOWN"  # v1.2 spec doesn't include CONFIDENCE
    assert invoker.call_count == 1


def test_ok_response_with_default_script(mock_state) -> None:
    """An empty script → the MockInvoker returns a default OK response.

    Note: the default mock response is the legacy ``ADAPTED_OBJECTIVE:``
    format, which the v2 parser does not recognize (no ``### D-XX.Y``
    headings). Expectation is FAILED with parse-related error.
    """
    invoker = MockInvoker()
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    # Default mock LLM emits legacy format → parser v2 fails → result FAILED
    assert result["llm_status"] == "FAILED"
    assert "Parse failed" in result["error_reason"]


def test_parse_fail_retry_with_feedback(mock_state) -> None:
    """Invalid output on attempt 1 → retry with feedback → success on attempt 2."""
    invoker = MockInvoker(
        script=[
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
            {"raw": VALID_OUTPUT, "status": "OK"},
        ]
    )
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "OK"
    assert invoker.call_count == 2
    assert invoker.last_feedback  # the second call had feedback from the first failure


def test_parse_fail_status_fail_then_success(mock_state) -> None:
    """Retry logic handles mixed status=FAILED_AFTER_RETRIES + parse failures."""
    invoker = MockInvoker(
        script=[
            {"raw": "", "status": "FAILED_AFTER_RETRIES"},
            {"raw": "not parseable at all", "status": "OK"},
            {"raw": VALID_OUTPUT, "status": "OK"},
        ]
    )
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "OK"
    assert invoker.call_count == 3


def test_retries_exhausted_returns_failed(mock_state) -> None:
    """All 3 attempts return invalid output → llm_status=FAILED."""
    invoker = MockInvoker(
        script=[
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
        ]
    )
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "FAILED"
    assert "Parse failed after 3 retries" in result["error_reason"]
    assert result["adapted_objective"] == ""
    assert invoker.call_count == 3


def test_max_retries_can_be_lowered(mock_state) -> None:
    """max_retries=2 stops after 2 attempts even with persistent parse failure."""
    invoker = MockInvoker(
        script=[
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
        ]
    )
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=2)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "FAILED"
    assert invoker.call_count == 2
    assert "Parse failed after 2 retries" in result["error_reason"]


def test_all_retries_returning_failed_status_returns_failed(mock_state) -> None:
    """Three FAILED_AFTER_RETRIES statuses → result is FAILED (no exception)."""
    invoker = _FailingStatusInvoker()
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "FAILED"
    assert invoker.calls == 3


# ─── Fatal LLM error ───────────────────────────────────────────────────


def test_ollama_exception_raises_OllamaUnreachable(mock_state) -> None:
    """A raising invoker → OllamaUnreachable propagates (no fallback)."""
    invoker = _ExplodingInvoker(ConnectionError("localhost:11434 refused"))
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    with pytest.raises(OllamaUnreachable) as exc_info:
        proc.process("D-04", mock_state)

    assert "localhost:11434" in str(exc_info.value)
    assert invoker.calls == 1


# ─── Input assembly failure ────────────────────────────────────────────


def test_input_assembly_failure_returns_failed() -> None:
    """If assemble_inputs raises (no company_context), result is FAILED (no exception)."""
    invoker = MockInvoker()
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    # _make_empty_state has company_context=None → assemble_inputs raises ValueError
    result = proc.process("D-04", _make_empty_state())

    assert result["llm_status"] == "FAILED"
    assert "Input assembly" in result["error_reason"]
    assert invoker.call_count == 0  # LLM never called


# ─── Sub-domain and coverage ──────────────────────────────────────────


def test_subdomain_summary_includes_subdomains(mock_state) -> None:
    """The result's subdomains list is populated from inputs."""
    invoker = MockInvoker(script=[{"raw": VALID_OUTPUT, "status": "OK"}])
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert isinstance(result["subdomains"], list)
    assert len(result["subdomains"]) == 4  # D-04.1 .. D-04.4 in mock_state


def test_coverage_substantive_when_two_regs(mock_state) -> None:
    """Coverage=SUBSTANTIVE when applicable_regs has ≥2 entries."""
    invoker = MockInvoker(script=[{"raw": VALID_OUTPUT, "status": "OK"}])
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)  # D-04 has both GDPR and CRA

    assert result["coverage"] == "SUBSTANTIVE"


def test_applicable_regs_includes_short_names(mock_state) -> None:
    """applicable_regs in the result is a list of strings."""
    invoker = MockInvoker(script=[{"raw": VALID_OUTPUT, "status": "OK"}])
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert "GDPR" in result["applicable_regs"]
    assert "CRA" in result["applicable_regs"]


# ─── Logging ───────────────────────────────────────────────────────────


def test_log_writes_jsonl(tmp_path: Path, mock_state) -> None:
    """Successful process() writes a JSONL entry to <log_dir>/<domain_id>.jsonl."""
    log_dir = tmp_path / "logs"
    invoker = MockInvoker(script=[{"raw": VALID_OUTPUT, "status": "OK"}])
    proc = DomainProcessor(llm_invoker=invoker, log_dir=log_dir, max_retries=3)

    proc.process("D-04", mock_state)

    log_path = log_dir / "D-04.jsonl"
    assert log_path.exists()
    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["domain_id"] == "D-04"
    assert entry["attempts"] == 1
    # v1.2 spec doesn't include CONFIDENCE → "UNKNOWN"
    assert entry["parsed"]["confidence"] == "UNKNOWN"
    assert isinstance(entry["adapted_subdomains"], list)
    assert len(entry["adapted_subdomains"]) == 2


def test_log_writes_on_exhausted_retries(tmp_path: Path, mock_state) -> None:
    """Even when all retries fail, an entry is written with attempts=max_retries."""
    log_dir = tmp_path / "logs"
    invoker = MockInvoker(
        script=[
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
        ]
    )
    proc = DomainProcessor(llm_invoker=invoker, log_dir=log_dir, max_retries=3)

    proc.process("D-04", mock_state)

    log_path = log_dir / "D-04.jsonl"
    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["attempts"] == 3
    assert entries[0]["parsed"] is None


# ─── DOMAIN_NAMES ──────────────────────────────────────────────────────


def test_domain_names_has_ten_entries() -> None:
    """The catalogue covers D-01..D-10."""
    assert len(DOMAIN_NAMES) == 10
    assert DOMAIN_NAMES["D-01"] == "Data Protection"
    assert DOMAIN_NAMES["D-10"] == "Monitoring & Audit"


def test_map_partial_failure_is_an_exception() -> None:
    """MapPartialFailure can be raised and caught as a regular Exception."""
    with pytest.raises(MapPartialFailure):
        raise MapPartialFailure("3 domain(s) failed: ['D-04', 'D-07', 'D-09']")


# ─── v1.2 per-sub-domain handling ──────────────────────────────────────


def test_processor_passes_adapted_subdomains(mock_state) -> None:
    """result["adapted_subdomains"] is populated from the parser."""
    invoker = MockInvoker(script=[{"raw": VALID_OUTPUT, "status": "OK"}])
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert "adapted_subdomains" in result
    adapted = result["adapted_subdomains"]
    assert isinstance(adapted, list)
    assert len(adapted) == 2
    ids = {s["subdomain_id"] for s in adapted}
    assert ids == {"D-04.1", "D-04.2"}
    for s in adapted:
        assert s["title"]
        assert s["hl_objective"].startswith("**Objective.**")
        assert isinstance(s["directed"], list)
        assert len(s["directed"]) >= 1


def test_processor_legacy_adapted_objective_is_concatenated_hls(mock_state) -> None:
    """result["adapted_objective"] is the HL paragraphs joined by ``\\n\\n``."""
    invoker = MockInvoker(script=[{"raw": VALID_OUTPUT, "status": "OK"}])
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    ao = result["adapted_objective"]
    assert "Maintain a documented incident response plan" in ao
    assert "Establish detection capabilities" in ao
    assert "\n\n" in ao  # joined with double-newline
    # First half ends before the second half starts
    assert ao.find("incident response plan") < ao.find("**Objective.** Establish")


# ─── v1.3: per-sub-domain 3 blocks x 5 fields ──────────────────────────


VALID_V3_OUTPUT = (
    "### D-04.1 — Incident Response Planning\n\n"
    "**Generic Objective.**\n"
    "- Original: Maintain a documented incident response plan tailored to "
    "TinyTask scope.\n"
    "- Adapted: Maintain a documented incident response plan scaled to a "
    "micro-entity with limited security FTE.\n"
    "- Rationale: Source HL already addresses the in-scope perimeter; "
    "adaptation adds operationalisation for micro-scale.\n"
    "- Adjustments needed: Define IR roles explicitly. Document breach "
    "notification timing (24h CRA / 72h GDPR).\n"
    "**Considerations.**\n"
    "- GDPR Art. 33(1) 72h clock and CRA early-warning 24h clock are the "
    "two timing anchors.\n"
    "- Records include incident logs, root-cause analyses, post-mortems.\n\n"
    "**GDPR Objective.**\n"
    "- Original: Personal-data breach notification to the supervisory "
    "authority within 72 hours (Art. 33 GDPR).\n"
    "- Adapted: Personal-data breach notification to the supervisory "
    "authority within 72 hours, with documented internal escalation "
    "timeline.\n"
    "- Rationale: Original is already applicable (GDPR in scope); adaptation "
    "adds internal escalation step for a small team.\n"
    "- Adjustments needed: Document internal escalation procedure. Define "
    "DPO notification trigger.\n"
    "**Considerations.**\n"
    "- Art. 33(1) 72h clock starts from awareness.\n"
    "- Documentation must be sufficient to demonstrate compliance.\n\n"
    "**CRA Objective.**\n"
    "- Original: Manufacturer handles vulnerabilities and discloses them "
    "(Annex I Part II §(7) + §(8) CRA).\n"
    "- Adapted: Manufacturer handles vulnerabilities and discloses them, "
    "with a documented CVD policy published via security.txt.\n"
    "- Rationale: Original is already applicable (CRA in scope); adaptation "
    "adds publishable CVD channel for the product.\n"
    "- Adjustments needed: Publish security.txt. Document coordinated "
    "disclosure procedure.\n"
    "**Considerations.**\n"
    "- CRA Annex I Part II §(7) handles vulnerabilities.\n"
    "- Annex I Part II §(8) requires active dissemination of disclosed "
    "fixes.\n"
)


def test_processor_passes_adapted_subdomains_v3(mock_state) -> None:
    """When the LLM emits a v1.3-compliant output, the result carries
    ``adapted_subdomains_v3`` with 3 blocks per sub-domain and ``adapted_subdomains``
    is empty.
    """
    invoker = MockInvoker(script=[{"raw": VALID_V3_OUTPUT, "status": "OK"}])
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "OK"
    assert "adapted_subdomains_v3" in result
    assert isinstance(result["adapted_subdomains_v3"], list)
    assert len(result["adapted_subdomains_v3"]) == 1
    sub = result["adapted_subdomains_v3"][0]
    assert sub["subdomain_id"] == "D-04.1"
    assert sub["title"] == "Incident Response Planning"
    assert len(sub["blocks"]) == 3
    labels = [b["label"] for b in sub["blocks"]]
    assert labels == ["Generic Objective.", "GDPR Objective.", "CRA Objective."]
    for block in sub["blocks"]:
        assert block["original"]
        assert block["adapted"]
        assert block["rationale"]
        assert block["adjustments"]
        assert isinstance(block["considerations"], list)
        assert len(block["considerations"]) >= 1
    # V2 path is not taken when V3 succeeds
    assert result["adapted_subdomains"] == []


def test_processor_falls_back_to_v2_when_v3_fails(mock_state) -> None:
    """If the LLM output does not match v1.3 (no 'Generic Objective' header),
    the processor falls back to the v1.2 parser.
    """
    invoker = MockInvoker(script=[{"raw": VALID_OUTPUT, "status": "OK"}])
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "OK"
    # V3 path produces no blocks (output has only "**Objective.**" not "Generic Objective.")
    assert result["adapted_subdomains_v3"] == []
    # V2 fallback populates adapted_subdomains
    assert len(result["adapted_subdomains"]) == 2


def test_processor_v3_failed_result_includes_empty_v3(mock_state) -> None:
    """When all retries fail, the result still has ``adapted_subdomains_v3 == []``."""
    invoker = MockInvoker(
        script=[
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
            {"raw": INVALID_OUTPUT_NO_OBJECTIVE, "status": "OK"},
        ]
    )
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "FAILED"
    assert result["adapted_subdomains_v3"] == []
