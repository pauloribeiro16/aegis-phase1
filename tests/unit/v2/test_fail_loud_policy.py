"""CORR-102: Fail-loud policy tests.

Validates that the Phase 1 pipeline RAISES (does not silently fallthrough)
when:
- applicable_regs is empty
- layer0_subdomain_refs is empty
- aggregated_activations is empty
- prompt exceeds 100K token cap
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aegis_phase1.prompts_v2.invoker import (
    BASE_PROMPT_TOKENS,
    MAX_PROMPT_TOKENS,
    PromptTooLargeError,
    _effective_token_cap,
)
from aegis_phase1.prompts_v2.llm_inventory import get_invocation_pattern, get_stage
from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.logging_helper import JSONLLogger
from aegis_phase1.prompts_v2.phase1_executor import (
    Phase1BEmptyApplicabilityError,
    Phase1BEmptyLayer0Error,
    Phase1CMapEmptyDomainListError,
    Phase1CReduceEmptyAggregationsError,
)


class TestCapConstants:
    def test_base_is_100k(self):
        assert BASE_PROMPT_TOKENS == 100000

    def test_max_is_124k(self):
        assert MAX_PROMPT_TOKENS == 124000

    def test_base_le_max(self):
        assert BASE_PROMPT_TOKENS <= MAX_PROMPT_TOKENS


class TestEffectiveTokenCap:
    def test_gemma4_gets_100k(self):
        assert _effective_token_cap("gemma4:e4b") == 100000

    def test_minimax_gets_100k(self):
        assert _effective_token_cap("MiniMax-M3") == 100000
        assert _effective_token_cap("MiniMax-M2.7") == 100000
        assert _effective_token_cap("MiniMax-M2.7-highspeed") == 100000

    def test_llama3_gets_100k(self):
        assert _effective_token_cap("llama3.1:8b") == 100000

    def test_unknown_model_falls_back_to_base(self):
        assert _effective_token_cap("some-future-model") == 100000


class TestFailLoudExceptions:
    def test_phase1b_empty_applicability_raises(self):
        from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor

        executor = Phase1Executor(
            prompt_loader=MagicMock(spec=PromptLoader),
            catalog_loader=MagicMock(),
            validator=MagicMock(),
            llm_logger=MagicMock(spec=JSONLLogger),
            format_logger=MagicMock(spec=JSONLLogger),
        )
        with pytest.raises(Phase1BEmptyApplicabilityError):
            executor.run_phase_1b(
                case_id="test",
                applicable_regs=[],
                layer0_subdomain_refs=[{"sub_domain_id": "D-01.1"}],
            )

    def test_phase1b_empty_layer0_raises(self):
        from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor

        executor = Phase1Executor(
            prompt_loader=MagicMock(spec=PromptLoader),
            catalog_loader=MagicMock(),
            validator=MagicMock(),
            llm_logger=MagicMock(spec=JSONLLogger),
            format_logger=MagicMock(spec=JSONLLogger),
        )
        with pytest.raises(Phase1BEmptyLayer0Error):
            executor.run_phase_1b(
                case_id="test",
                applicable_regs=["GDPR"],
                layer0_subdomain_refs=[],
            )

    def test_phase1c_map_empty_applicability_raises(self):
        from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor

        executor = Phase1Executor(
            prompt_loader=MagicMock(spec=PromptLoader),
            catalog_loader=MagicMock(),
            validator=MagicMock(),
            llm_logger=MagicMock(spec=JSONLLogger),
            format_logger=MagicMock(spec=JSONLLogger),
        )
        with pytest.raises(Phase1CMapEmptyDomainListError):
            executor.run_phase_1c_map(
                case_id="test",
                applicable_regs=[],
                layer0_subdomain_refs=[{"sub_domain_id": "D-01.1"}],
            )

    def test_phase1c_reduce_empty_aggregations_raises(self):
        from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor

        executor = Phase1Executor(
            prompt_loader=MagicMock(spec=PromptLoader),
            catalog_loader=MagicMock(),
            validator=MagicMock(),
            llm_logger=MagicMock(spec=JSONLLogger),
            format_logger=MagicMock(spec=JSONLLogger),
        )
        with pytest.raises(Phase1CReduceEmptyAggregationsError):
            executor.run_phase_1c_reduce(
                case_id="test",
                lane_outputs=[],
                sync_result={"conflicts": []},
                track_b_profile={},
            )


class TestPromptTooLarge:
    def test_prompt_too_large_raises_on_huge_inputs(self):
        """Build inputs large enough to exceed BASE_PROMPT_TOKENS."""
        from aegis_phase1.prompts_v2.factory import get_prompts_root
        from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker

        prompt_loader = PromptLoader(root=get_prompts_root())
        invoker = Phase1LLMInvoker(
            prompt_loader=prompt_loader,
            catalog_loader=MagicMock(),
            llm_logger=MagicMock(spec=JSONLLogger),
            format_logger=MagicMock(spec=JSONLLogger),
            model="gemma4:e4b",
            base_url="http://localhost:11434",
        )

        # 60K entries * ~12 chars each = ~720K chars = ~180K tokens (>>100K cap)
        huge_inputs = {
            "case_id": "test",
            "tech_stack": [f"tech_{i:08d}" for i in range(60000)],
            "applicable_regs": ["GDPR", "CRA"],
        }

        with (
            patch("aegis_phase1.prompts_v2.invoker.probe_ollama", return_value=True),
            pytest.raises(PromptTooLargeError) as exc_info,
        ):
            invoker._attempt(
                spec_id="P1C-LLM-01-OVERLAP-CLASSIFICATION",
                inputs=huge_inputs,
                invocation_pattern=get_invocation_pattern(
                    "P1C-LLM-01-OVERLAP-CLASSIFICATION"
                ),
                stage=get_stage("P1C-LLM-01-OVERLAP-CLASSIFICATION"),
                attempt=1,
            )

        assert exc_info.value.spec_id == "P1C-LLM-01-OVERLAP-CLASSIFICATION"
        assert exc_info.value.model == "gemma4:e4b"
        assert exc_info.value.cap == 100000
        assert exc_info.value.sys_tokens + exc_info.value.user_tokens > 100000
        assert "gemma4:e4b" in str(exc_info.value)
        assert "P1C-LLM-01-OVERLAP-CLASSIFICATION" in str(exc_info.value)
