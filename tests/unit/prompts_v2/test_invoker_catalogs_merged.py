"""CORR-045 tests: catalog merge + helper + lane filter.

Three layers of tests:

  (a) test_catalogs_merged_into_inputs_for_p1c_llm_01
      Verifies that ``_load_catalogs_for("P1C-LLM-01-...")`` return
      value is merged into ``inputs`` BEFORE the prompt is rendered.
      Pre-CORR-045 the return was discarded and the LLM never saw
      ``scope_overlap_predicates``.

  (b) test_catalogs_merged_into_inputs_for_p1b_llm_01
      Same as (a) but for P1B-LLM-01 (tipo2 + tipo3 catalogs).

  (c) test_build_layer0_subdomain_refs_returns_dicts
      Verifies ``Phase1Orchestrator._build_layer0_subdomain_refs``
      returns a ``list[dict]`` with the metadata fields the
      P1C-LLM-01 spec requires.

  (d) test_run_phase_1c_map_filters_layer0_subdomain_refs_by_lane
      Verifies that when ``run_phase_1c_map`` iterates 10 D-XX lanes,
      each lane only sees the subdomains whose ``sub_domain_id``
      starts with ``D-XX.`` (D-01 lane gets D-01.* only).
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _make_invoker_with_real_prompts(catalog_loader: MagicMock) -> "Phase1LLMInvoker":
    """Build a Phase1LLMInvoker with real PromptLoader (so render works)."""
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker
    from aegis_phase1.prompts_v2.loader import PromptLoader
    from aegis_phase1.prompts_v2.logging_helper import JSONLLogger

    prompt_loader = PromptLoader(root=get_prompts_root())
    return Phase1LLMInvoker(
        prompt_loader=prompt_loader,
        catalog_loader=catalog_loader,
        llm_logger=MagicMock(spec=JSONLLogger),
        format_logger=MagicMock(spec=JSONLLogger),
        model="gemma4:e2b",
        base_url="http://localhost:11434",
    )


# ──────────────────────────────────────────────────────────────────
# (a) P1C-LLM-01 — catalogs merged
# ──────────────────────────────────────────────────────────────────


def test_catalogs_merged_into_inputs_for_p1c_llm_01() -> None:
    """(a) P1C-LLM-01 inputs contain ``scope_overlap_predicates`` post-merge.

    Smoke test: capture the user message sent to Ollama and assert
    that ``scope_overlap_predicates`` is in the JSON-serialised
    inputs.
    """
    catalog_loader = MagicMock()
    catalog_loader.load.return_value = [
        {"predicate_id": "P1", "trigger": "scope_overlap", "verdict": "OVERLAP_CONFIRMED"},
    ]

    invoker = _make_invoker_with_real_prompts(catalog_loader)

    # Capture the user message Ollama received.
    with patch("aegis_phase1.prompts_v2.invoker.probe_ollama", return_value=True):
        with patch("aegis_phase1.prompts_v2.invoker.ChatOllama") as mock_chat:
            llm_inst = MagicMock()
            llm_inst.invoke.return_value = MagicMock(
                content=json.dumps(
                    {
                        "prompt_spec_id": "P1C-LLM-01-OVERLAP-CLASSIFICATION",
                        "case_id": "case1-tinytask",
                        "domain_id": "D-01",
                        "lane_id": "D-01",
                        "sub_domain_activations": [],
                    }
                )
            )
            mock_chat.return_value = llm_inst

            invoker.invoke(
                "P1C-LLM-01-OVERLAP-CLASSIFICATION",
                inputs={"case_id": "case1-tinytask"},
                max_retries=1,
            )

            # Inspect the HumanMessage that was sent.
            msgs = llm_inst.invoke.call_args.args[0]
            user_msg = next(m for m in msgs if "INPUTS" in m.content)
            assert "scope_overlap_predicates" in user_msg.content, (
                "CORR-045: scope_overlap_predicates not merged into inputs"
            )
            assert "P1" in user_msg.content or "OVERLAP_CONFIRMED" in user_msg.content


# ──────────────────────────────────────────────────────────────────
# (b) P1B-LLM-01 — tipo2 + tipo3 merged
# ──────────────────────────────────────────────────────────────────


def test_catalogs_merged_into_inputs_for_p1b_llm_01() -> None:
    """(b) P1B-LLM-01 inputs contain ``tipo2`` and ``tipo3`` post-merge."""
    catalog_loader = MagicMock()

    def fake_load(name: str):
        return [{"id": f"{name}-entry-1", "title": f"Sample {name}"}]

    catalog_loader.load.side_effect = fake_load

    invoker = _make_invoker_with_real_prompts(catalog_loader)

    with patch("aegis_phase1.prompts_v2.invoker.probe_ollama", return_value=True):
        with patch("aegis_phase1.prompts_v2.invoker.ChatOllama") as mock_chat:
            llm_inst = MagicMock()
            llm_inst.invoke.return_value = MagicMock(
                content=json.dumps(
                    {
                        "prompt_spec_id": "P1B-LLM-01-INTERPRETATION",
                        "case_id": "case1-tinytask",
                        "regulation": "GDPR",
                        "interpretations": [],
                    }
                )
            )
            mock_chat.return_value = llm_inst

            invoker.invoke(
                "P1B-LLM-01-INTERPRETATION",
                inputs={"case_id": "case1-tinytask", "regulation": "GDPR"},
                max_retries=1,
            )

            msgs = llm_inst.invoke.call_args.args[0]
            user_msg = next(m for m in msgs if "INPUTS" in m.content)
            assert "tipo2" in user_msg.content
            assert "tipo3" in user_msg.content


# ──────────────────────────────────────────────────────────────────
# (c) _build_layer0_subdomain_refs returns dicts
# ──────────────────────────────────────────────────────────────────


def test_build_layer0_subdomain_refs_returns_dicts() -> None:
    """(c) Helper returns list[dict] with the metadata fields.

    Uses a real PreprocCatalogLoader (no Ollama needed) so the helper
    iterates real Subdomain Pydantic models.
    """
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    catalog = PreprocCatalogLoader()
    subs = catalog.load_subdomains()
    if not subs:
        pytest.skip("preproc_out not built — skipping")

    orch = Phase1Orchestrator.__new__(Phase1Orchestrator)
    orch.preproc_catalog = catalog

    # Pick first 3 subdomains that have hso_hl so the test is deterministic.
    target_ids = [s.id for s in subs if s.hso_hl is not None][:3]
    if not target_ids:
        target_ids = [s.id for s in subs][:3]

    refs = orch._build_layer0_subdomain_refs(target_ids)

    assert isinstance(refs, list)
    assert len(refs) == len(target_ids)
    for ref in refs:
        assert isinstance(ref, dict)
        assert "sub_domain_id" in ref
        assert "title" in ref
        assert "participating_regulations" in ref
        assert "pairs" in ref
        assert "anchors" in ref
        assert "csf" in ref
        # objective is None if hso_hl absent, but key is always present
        assert "objective" in ref
        assert "hso_hl_objective" in ref


def test_build_layer0_subdomain_refs_missing_silently_skipped() -> None:
    """_build_layer0_subdomain_refs silently skips unknown IDs."""
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    catalog = PreprocCatalogLoader()
    subs = catalog.load_subdomains()
    if not subs:
        pytest.skip("preproc_out not built — skipping")

    orch = Phase1Orchestrator.__new__(Phase1Orchestrator)
    orch.preproc_catalog = catalog

    valid_id = subs[0].id
    refs = orch._build_layer0_subdomain_refs([valid_id, "D-99.99", "D-XX.ZZ"])
    ids = [r["sub_domain_id"] for r in refs]
    assert valid_id in ids
    assert "D-99.99" not in ids
    assert "D-XX.ZZ" not in ids


# ──────────────────────────────────────────────────────────────────
# (d) run_phase_1c_map filters by lane
# ──────────────────────────────────────────────────────────────────


def test_run_phase_1c_map_filters_layer0_subdomain_refs_by_lane() -> None:
    """(d) D-01 lane only sees D-01.* subdomains, not D-02.*.

    Smoke test: build a Phase1Executor with a mock invoker, run
    run_phase_1c_map, and inspect what the invoker received for
    lane D-01 (should be D-01.*) vs lane D-02 (D-02.*).
    """
    from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor

    # Build a fake invoker that records inputs per spec invocation.
    captured_inputs_per_call: list[dict] = []

    class _FakeInvoker:
        def invoke(self, spec_id, inputs, max_retries=None, config=None):
            # Record the inputs the lane received.
            captured_inputs_per_call.append(
                {"spec_id": spec_id, "lane_id": inputs.get("lane_id"), "inputs": inputs}
            )
            return {
                "status": "OK",
                "spec_id": spec_id,
                "parsed_output": {"sub_domain_activations": []},
                "validation": {},
                "total_latency_ms": 0,
                "retry_count": 1,
            }

    executor = Phase1Executor.__new__(Phase1Executor)
    executor.invoker = _FakeInvoker()
    # setattr to bypass __init__; not all attrs needed for this test

    # 3 subdomains for D-01, 2 for D-02
    all_refs = [
        {"sub_domain_id": "D-01.1", "title": "T1"},
        {"sub_domain_id": "D-01.2", "title": "T2"},
        {"sub_domain_id": "D-01.3", "title": "T3"},
        {"sub_domain_id": "D-02.1", "title": "T4"},
        {"sub_domain_id": "D-02.2", "title": "T5"},
    ]

    with patch("aegis_phase1.prompts_v2.phase1_executor.DOMAINS", ["D-01", "D-02"]):
        executor.run_phase_1c_map(
            case_id="case1-tinytask",
            applicable_regs=["GDPR"],
            layer0_subdomain_refs=all_refs,
        )

    # We expect 2 calls (D-01, D-02).
    assert len(captured_inputs_per_call) == 2

    d01_call = next(c for c in captured_inputs_per_call if c["lane_id"] == "D-01")
    d02_call = next(c for c in captured_inputs_per_call if c["lane_id"] == "D-02")

    d01_refs = d01_call["inputs"]["layer0_subdomain_refs"]
    d02_refs = d02_call["inputs"]["layer0_subdomain_refs"]

    d01_ids = sorted(r["sub_domain_id"] for r in d01_refs)
    d02_ids = sorted(r["sub_domain_id"] for r in d02_refs)

    assert d01_ids == ["D-01.1", "D-01.2", "D-01.3"]
    assert d02_ids == ["D-02.1", "D-02.2"]
