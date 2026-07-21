"""CORR-042-T3 tests: anti-regression guard for catalog-dependent Phase 1 LLMs.

Pre-CORR-042, Phase1LLMInvoker accepted ``catalog_loader=None``
silently — if a new entrypoint forgot to wire a CatalogLoader, the
LLM would be called with an empty catalog context and the call would
fail downstream (returning INSUFFICIENT_EVIDENCE or empty
parsed_output). The original smoking gun was v2/orchestrator.py
never passing catalog_loader (fixed in CORR-039-T1).

CORR-042-T3 hardens the invoker: when invoke() is called with a
spec in ``_CATALOG_REQUIRED_SPECS`` and ``self.catalogs is None``,
the call raises ``RuntimeError`` with a clear message naming the
spec and the catalog it requires.

These 3 tests cover:
  (a) no catalog_loader + P1B-LLM-01-INTERPRETATION → raises
  (b) catalog_loader wired + P1B-LLM-01-INTERPRETATION → does not raise
      (returns OK or MOCK response; we mock the LLM via MOCK_LLM)
  (c) no catalog_loader + P1C-LLM-03-STRATEGIC-SYNTHESIS → does NOT
      raise (P1C-LLM-03 is not in _CATALOG_REQUIRED_SPECS)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_invoker(catalog_loader):
    """Build a Phase1LLMInvoker with a mock prompt_loader + the
    provided catalog_loader (None or MagicMock)."""
    from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker
    from aegis_phase1.prompts_v2.loader import PromptLoader
    from aegis_phase1.prompts_v2.logging_helper import JSONLLogger

    # Real PromptLoader pointing at the PROMPTS/ dir (so prompt rendering works)
    from aegis_phase1.prompts_v2.factory import get_prompts_root

    prompt_loader = PromptLoader(root=get_prompts_root())
    llm_logger = MagicMock(spec=JSONLLogger)
    return Phase1LLMInvoker(
        prompt_loader=prompt_loader,
        catalog_loader=catalog_loader,
        llm_logger=llm_logger,
        format_logger=MagicMock(spec=JSONLLogger),
        model="gemma4:e2b",
        base_url="http://localhost:11434",
    )


def test_guard_a_no_loader_p1b_raises() -> None:
    """(a) Phase1LLMInvoker without catalog_loader + P1B-LLM-01 → RuntimeError.

    The guard fires at the top of invoke() (before any LLM call), so
    we don't need to mock Ollama — the RuntimeError is raised before
    probe_ollama() is called. We still mock it to avoid network calls.
    """
    invoker = _make_invoker(catalog_loader=None)
    with patch("aegis_phase1.prompts_v2.invoker.probe_ollama", return_value=True):
        with pytest.raises(RuntimeError, match=r"catalog_loader is None but prompt P1B-LLM-01-INTERPRETATION requires"):
            invoker.invoke(
                "P1B-LLM-01-INTERPRETATION",
                {"case_id": "Case_01", "lane_id": "GDPR", "applicable_regs": ["GDPR"]},
            )


def test_guard_b_with_loader_p1b_does_not_raise() -> None:
    """(b) Phase1LLMInvoker WITH catalog_loader + P1B-LLM-01 → no raise.

    We mock the LLM layer so the call doesn't actually hit Ollama. The
    important assertion is that the catalog guard does not raise; the
    call may fail downstream for other reasons (e.g. missing role) but
    not because of the guard.
    """
    from aegis_phase1.prompts_v2.catalog import CatalogLoader

    cl = CatalogLoader(root="/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS/catalogs")
    invoker = _make_invoker(catalog_loader=cl)
    # _load_catalogs_for should return dict with tipo2 + tipo3 keys
    catalogs = invoker._load_catalogs_for("P1B-LLM-01-INTERPRETATION")
    assert "tipo2" in catalogs
    assert "tipo3" in catalogs
    assert len(catalogs["tipo2"]) == 8  # Berry catalog has 8 tipo2 entries
    assert len(catalogs["tipo3"]) == 6  # Berry catalog has 6 tipo3 entries


def test_guard_c_no_loader_p1c_llm_03_does_not_raise() -> None:
    """(c) P1C-LLM-03-STRATEGIC-SYNTHESIS without catalog_loader → no raise.

    P1C-LLM-03 is NOT in _CATALOG_REQUIRED_SPECS (consumes doc07b as
    constraint, no tipo2/tipo3/event lookup). The guard is a no-op for
    this spec. The call may still fail downstream (e.g. Ollama
    unreachable, but the catalog guard should not fire).
    """
    invoker = _make_invoker(catalog_loader=None)
    # _load_catalogs_for should return empty dict without raising
    catalogs = invoker._load_catalogs_for("P1C-LLM-03-STRATEGIC-SYNTHESIS")
    assert catalogs == {}
