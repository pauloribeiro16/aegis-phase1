"""CORR-067 S3: Test get_invoker() with provider=minimax uses M3 gateway.

Before fix: get_invoker() defaulted to OLLAMA_BASE_URL (Ollama local)
even when provider=minimax. The Phase1Executor (REDUCE-LLM) calls
get_invoker() without explicit base_url, so it was creating a
UnifiedInvoker pointed at localhost:11434 with the M3 model name,
which fails to connect (no Ollama running) and silently leaves
per-spec appendix empty.

After fix: when provider=minimax, get_invoker() leaves base_url as
None so UnifiedInvoker.__init__ resolves to the M3 gateway URL
(https://api.minimax.io/anthropic).
"""
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Ensure provider=minimax path is tested
os.environ.setdefault("LANGFUSE_ENABLED", "false")
os.environ.setdefault("MOCK_LLM", "true")
# Force OLLAMA_BASE_URL to a value that should be IGNORED when
# provider=minimax, to make sure the fix actually works.
os.environ["OLLAMA_BASE_URL"] = "http://should-be-ignored:9999"
os.environ["OLLAMA_MODEL"] = "should-be-ignored-model"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ────────────────────────────────────────────────────────────────────
# S3: get_invoker() with provider=minimax
# ────────────────────────────────────────────────────────────────────

def test_get_invoker_minimax_uses_m3_gateway_not_ollama():
    """When provider=minimax, get_invoker() must NOT use OLLAMA_BASE_URL.

    The OLLAMA_BASE_URL env var is a misleading default for the M3
    gateway path; the factory must leave base_url=None so that
    UnifiedInvoker.__init__ resolves it to the M3 gateway.
    """
    from aegis_phase1.prompts_v2.factory import get_invoker
    from aegis_phase1.llm.chat_minimax import DEFAULT_BASE_URL as M3_GATEWAY

    invoker = get_invoker(provider="minimax")
    assert invoker.provider == "minimax", f"provider={invoker.provider}"
    # The M3 gateway URL must be in the base_url
    assert "api.minimax.io" in invoker.base_url, (
        f"base_url={invoker.base_url!r} (expected M3 gateway, got "
        f"Ollama default or override)"
    )
    # The Ollama default must NOT be in the base_url
    assert "localhost:11434" not in invoker.base_url, (
        f"base_url={invoker.base_url!r} leaked Ollama default into M3 path"
    )
    # And must match the canonical M3 gateway
    assert invoker.base_url == M3_GATEWAY, (
        f"base_url={invoker.base_url!r} != M3_GATEWAY={M3_GATEWAY!r}"
    )


def test_get_invoker_minimax_explicit_base_url_honoured():
    """Explicit base_url still wins for provider=minimax (no regression)."""
    from aegis_phase1.prompts_v2.factory import get_invoker

    custom = "https://my-custom-m3-proxy.example.com"
    invoker = get_invoker(provider="minimax", base_url=custom)
    assert invoker.base_url == custom, (
        f"explicit base_url not honoured: got {invoker.base_url!r}"
    )


def test_get_invoker_ollama_uses_ollama_base_url():
    """provider=ollama (default) still uses OLLAMA_BASE_URL — no regression."""
    from aegis_phase1.prompts_v2.factory import get_invoker

    # Set the env var AFTER import so it's used by get_invoker()
    os.environ["OLLAMA_BASE_URL"] = "http://test-ollama:12345"
    try:
        invoker = get_invoker(provider="ollama")
        assert invoker.provider == "ollama"
        assert "test-ollama:12345" in invoker.base_url, (
            f"ollama path didn't pick up OLLAMA_BASE_URL: {invoker.base_url!r}"
        )
    finally:
        os.environ["OLLAMA_BASE_URL"] = "http://should-be-ignored:9999"


def test_get_invoker_minimax_ignores_ollama_model_env():
    """When provider=minimax, OLLAMA_MODEL env var should also be ignored.

    The M3 model has a specific name (MiniMax-M3) that the chat class
    sets by default. If OLLAMA_MODEL=should-be-ignored-model leaks
    through, the invoker would try to use that as the model name.
    """
    from aegis_phase1.prompts_v2.factory import get_invoker
    from aegis_phase1.llm.chat_minimax import DEFAULT_MODEL as M3_MODEL

    invoker = get_invoker(provider="minimax")
    assert invoker.model == M3_MODEL, (
        f"model={invoker.model!r} leaked OLLAMA_MODEL=should-be-ignored-model"
    )
