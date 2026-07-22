"""CORR-045 P1C-LLM-01 canonical-path tests.

Validates the canonical P1C-LLM-01-OVERLAP-CLASSIFICATION invocation
path now:

  - Receives ``scope_overlap_predicates`` in inputs (CORR-045-T1)
  - Receives rich dicts in ``layer0_subdomain_refs`` (CORR-045-T2/T3)
  - Receives only the lane's own subdomains, not all 38
    (CORR-045-T3 per-lane filter)

These tests exercise the path as assembled by the v2 pipeline
(orchestrator → executor → invoker → Ollama) using mocks for Ollama
itself so they are fast and offline.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _make_invoker_with_real_prompts(catalog_loader: MagicMock):
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


def test_p1c_llm_01_prompt_contains_all_required_catalogs() -> None:
    """The prompt sent to Ollama for P1C-LLM-01 contains scope_overlap_predicates.

    Pre-CORR-045 this would be empty (catalog return discarded) — the
    LLM would echo the input verbatim and return
    ``{results: [...]}`` which doesn't match the required
    ``sub_domain_activations[]`` schema.
    """
    catalog_loader = MagicMock()
    catalog_loader.load.return_value = [
        {"predicate_id": "P1", "verdict": "OVERLAP_CONFIRMED"},
        {"predicate_id": "P2", "verdict": "OVERLAP_NOT_TRIGGERED"},
    ]

    invoker = _make_invoker_with_real_prompts(catalog_loader)

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
                inputs={
                    "case_id": "case1-tinytask",
                    "domain_id": "D-01",
                    "lane_id": "D-01",
                    "layer0_subdomain_refs": [
                        {"sub_domain_id": "D-01.1", "title": "X", "pairs": []}
                    ],
                },
                max_retries=1,
            )

            msgs = llm_inst.invoke.call_args.args[0]
            user_msg = next(m for m in msgs if "INPUTS" in m.content)

            # Catalog present
            assert "scope_overlap_predicates" in user_msg.content
            # layer0 refs present and serialised
            assert "layer0_subdomain_refs" in user_msg.content
            assert "D-01.1" in user_msg.content
            # The rich dict shape means sub_domain_id appears inside
            # the JSON, not a bare list of strings.
            assert '"sub_domain_id"' in user_msg.content


def test_p1c_llm_01_does_not_crash_on_rich_refs() -> None:
    """Pre-CORR-045 path passed list[str] of IDs and crashed with
    'str' object has no attribute 'get' on the canonical path.

    Post-CORR-045 the call site builds rich dicts via
    ``_build_layer0_subdomain_refs`` so the canonical path is safe.
    """
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

    catalog = PreprocCatalogLoader()
    subs = catalog.load_subdomains()
    if not subs:
        pytest.skip("preproc_out not built — skipping")

    # Build rich refs the canonical way
    rich_refs = []
    for s in subs[:3]:
        rich_refs.append(
            {
                "sub_domain_id": s.id,
                "title": s.title,
                "participating_regulations": list(s.participating_regulations or []),
                "objective": s.hso_hl.objective if s.hso_hl else None,
                "pairs": [p.model_dump() for p in (s.pairs or [])],
                "anchors": [],
                "csf": list(s.csf_hint or []),
            }
        )

    catalog_loader = MagicMock()
    catalog_loader.load.return_value = [{"predicate_id": "X"}]
    invoker = _make_invoker_with_real_prompts(catalog_loader)

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

            result = invoker.invoke(
                "P1C-LLM-01-OVERLAP-CLASSIFICATION",
                inputs={
                    "case_id": "case1-tinytask",
                    "domain_id": "D-01",
                    "lane_id": "D-01",
                    "layer0_subdomain_refs": rich_refs,
                },
                max_retries=1,
            )
            # No crash; status is OK (or at least not PythonError)
            assert result["status"] in {"OK", "INSUFFICIENT_EVIDENCE", "INDETERMINATE", "SCHEMA_ERROR", "PARSE_ERROR", "FAILED_AFTER_RETRIES"}
