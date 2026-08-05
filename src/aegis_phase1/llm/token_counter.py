"""CORR-102: Token counting utility for prompt size budgeting.

Universal approximation: 1 token ≈ 4 characters (works for English/code/JSON mix;
slightly underestimates for non-ASCII). For more accurate counts, model-specific
tokenizers would be needed (tiktoken for OpenAI/Claude, Ollama /api/show for gemma).

Used by:
  - scripts/dev/dry_run_prompts.py to size prompts without calling the LLM.
  - Phase1LLMInvoker._attempt (CORR-102 hard cap; raises PromptTooLargeError
    instead of silently truncating).
  - Tests in tests/unit/llm/test_token_counter.py.

The constant 4 chars/token was chosen as a universal safe approximation that
holds for English/code/JSON mixes. It slightly underestimates non-ASCII
(UTF-8 multi-byte), which is acceptable for budgeting — the goal is to catch
obvious overruns, not to compute exact model-native counts.

Thread-safety: the class has no state; all methods are pure.
"""

from __future__ import annotations


class TokenCounter:
    """Estimate token count for a text or for a system+user pair.

    All methods are pure and side-effect-free. Use as a class (no
    instantiation required): ``TokenCounter.count(text)``.
    """

    CHARS_PER_TOKEN = 4  # universal approximation

    @classmethod
    def count(cls, text: str) -> int:
        """Estimate token count for a single string.

        Args:
            text: The text to measure. May be empty or ``None`` (treated
                as empty).

        Returns:
            Estimated token count. Returns at least 1 for any non-empty
            input so we never silently under-count very short strings
                that the LLM still has to process.
        """
        if not text:
            return 0
        return max(1, len(text) // cls.CHARS_PER_TOKEN)

    @classmethod
    def count_pair(cls, system: str, user: str) -> tuple[int, int, int]:
        """Return (system_tokens, user_tokens, total_tokens).

        Convenience helper for the most common use-case in this
        codebase: measuring a rendered prompt that has a system and
        user component. The total is the sum of the two and is the
        value compared against ``MAX_PROMPT_TOKENS``.

        Args:
            system: System prompt text (may be empty).
            user: User prompt text (may be empty).

        Returns:
            Tuple ``(system_tokens, user_tokens, total_tokens)``.
        """
        sys_t = cls.count(system)
        user_t = cls.count(user)
        return sys_t, user_t, sys_t + user_t


__all__ = ["TokenCounter"]