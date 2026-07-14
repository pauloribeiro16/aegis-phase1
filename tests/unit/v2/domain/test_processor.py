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
    "ADAPTED_OBJECTIVE: Adapted objective text spanning three sentences. "
    "It references the company reality. It is bounded by proportionality.\n"
    "KEY_ADJUSTMENTS:\n"
    "- adjustment 1\n"
    "- adjustment 2\n"
    "- adjustment 3\n"
    "CONFIDENCE: HIGH"
)

INVALID_OUTPUT_NO_OBJECTIVE = "KEY_ADJUSTMENTS:\n- one\nCONFIDENCE: HIGH"
INVALID_OUTPUT_NO_ADJUSTMENTS = (
    "ADAPTED_OBJECTIVE: Just an objective.\nCONFIDENCE: HIGH"
)


class _ExplodingInvoker:
    """Invoker that always raises — used to test OllamaUnreachable."""

    def __init__(self, exc: Exception | None = None) -> None:
        self.exc = exc or ConnectionError("Ollama not reachable")
        self.calls = 0

    def invoke(self, prompt: str, feedback: str = "") -> dict[str, Any]:
        self.calls += 1
        raise self.exc


class _FailingStatusInvoker:
    """Invoker that returns FAILED_AFTER_RETRIES status on every call."""

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, prompt: str, feedback: str = "") -> dict[str, Any]:
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
    assert "Adapted objective text" in result["adapted_objective"]
    assert len(result["key_changes"]) == 3
    assert result["confidence"] == "HIGH"
    assert invoker.call_count == 1


def test_ok_response_with_default_script(mock_state) -> None:
    """An empty script → the MockInvoker returns a default OK response."""
    invoker = MockInvoker()
    proc = DomainProcessor(llm_invoker=invoker, log_dir=None, max_retries=3)

    result = proc.process("D-04", mock_state)

    assert result["llm_status"] == "OK"
    assert result["adapted_objective"]


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
            {"raw": INVALID_OUTPUT_NO_ADJUSTMENTS, "status": "OK"},
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
    assert entry["parsed"]["confidence"] == "HIGH"


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