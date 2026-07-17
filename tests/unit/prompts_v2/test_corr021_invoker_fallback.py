"""Test for CORR-021 token fallback in Phase1LLMInvoker._extract_usage."""

from unittest.mock import MagicMock

from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker


def test_invoker_extract_usage_falls_back_to_chars_when_metadata_empty():
    """REGRESSION: P1B-LLM-02 returned response_metadata={} → 0 tokens.

    Fallback must estimate from content length.
    """
    response = MagicMock()
    response.response_metadata = {}
    response.usage_metadata = None
    response.content = "x" * 12000  # 12000 chars → 3000 tokens

    usage = Phase1LLMInvoker._extract_usage(response)
    assert usage["completion_tokens"] == 3000
    assert usage["total_tokens"] == 3000


def test_invoker_extract_usage_prefers_response_metadata():
    response = MagicMock()
    response.response_metadata = {"prompt_eval_count": 100, "eval_count": 50}
    response.usage_metadata = None
    response.content = "should not be used"

    usage = Phase1LLMInvoker._extract_usage(response)
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 50
    assert usage["total_tokens"] == 150
