"""_narrative — shared helper for mandatory LLM narrative sections.

When the LLM invoker is unavailable, raises an exception, or returns
empty content, narrative sections render a ``[PENDING REVIEW — reason]``
marker instead of a silent deterministic fallback. This makes narrative
sections auditable: a human reviewer can see at a glance which prose
came from the LLM and which still requires generation or manual review.

Replacement target:
    The previous ``_invoke_or_fallback(invoker, prompt, fallback)``
    helper silently emitted the deterministic ``fallback`` string when
    the LLM was absent, errored, or returned empty. That made narrative
    sections indistinguishable from LLM output and prevented reviewers
    from identifying which sections still needed LLM coverage.

Usage:
    from aegis_phase1.v2.output._narrative import render_mandatory_narrative

    narrative = render_mandatory_narrative(
        invoker=llm_invoker,
        prompt=my_prompt,
        section_id="doc_05.section_6.strategic_narrative",
        max_chars=4000,
    )

References:
    - contracts/AEGIS-P1-CORR-001 (Phase 4 — activate dormant LLM call
      points + convert narrative sections to mandatory-with-PENDING)
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class LLMInvoker(Protocol):
    """Structural type for the LLM invoker passed through the renderer chain.

    Concrete invokers live in ``aegis_phase1.llm`` and
    ``aegis_phase1.prompts_v2``. They all expose ``invoke(prompt,
    feedback="") -> dict[str, Any]`` returning at least ``"raw"`` and
    ``"status"`` keys.
    """

    def invoke(self, prompt: str, feedback: str = "") -> dict[str, Any]: ...


def render_mandatory_narrative(
    invoker: LLMInvoker | None,
    prompt: str,
    section_id: str,
    max_chars: int = 4000,
) -> str:
    """Render a mandatory LLM narrative section.

    On success: returns the LLM response text (truncated to ``max_chars``).
    On failure (no invoker, empty ``raw``, non-OK status, or exception):
    returns a ``[PENDING REVIEW — reason]`` marker that is auditable in
    the rendered Markdown.

    Args:
        invoker: The LLM invoker, or ``None`` if no LLM is configured for
            this run. ``None`` is the normal case for the deterministic
            pipeline and for offline test runs.
        prompt: The fully-formatted LLM prompt for this narrative.
        section_id: Stable identifier for this narrative section
            (e.g. ``"doc_04a.section_1.technical_architecture"``). The
            ID is embedded in the PENDING marker for traceability and
            so reviewers can grep the rendered Markdown for all pending
            sections.
        max_chars: Maximum length of the returned narrative. Defaults to
            4000, matching the previous ``_MAX_FRAGMENT_BYTES`` ceiling
            for strategic-narrative sections. Smaller sections
            (per-domain Notes in ``doc_04b``) override this to 2000.

    Returns:
        The LLM response text on success, or a ``[PENDING REVIEW]``
        marker block on failure. Never returns the empty string.
    """
    if invoker is None:
        return _pending_marker(section_id, "LLM not configured")

    try:
        result = invoker.invoke(prompt)
    except Exception as exc:
        logger.warning(
            "render_mandatory_narrative[%s]: LLM invoke raised — %s",
            section_id,
            exc,
        )
        return _pending_marker(section_id, f"LLM error: {exc}")

    if not isinstance(result, dict):
        return _pending_marker(
            section_id, f"LLM returned non-dict result: {type(result).__name__}"
        )

    status = result.get("status", "UNKNOWN")
    raw = str(result.get("raw") or "").strip()
    if status != "OK" or not raw:
        return _pending_marker(
            section_id, f"LLM status={status}, raw empty"
        )

    return raw[:max_chars]


def _pending_marker(section_id: str, reason: str) -> str:
    """Return a ``[PENDING REVIEW — reason]`` marker block.

    The block is a Markdown blockquote so it survives Markdown
    rendering and is visually distinct from narrative content. The
    ``section_id`` is rendered as inline code so a reviewer can grep
    for it.
    """
    return (
        f"> **[PENDING REVIEW — {reason}]**\n"
        f"> Section ID: `{section_id}`\n"
        f"> \n"
        f"> This section requires LLM-generated content. Once the LLM is "
        f"configured and the pipeline re-run, this placeholder will be "
        f"replaced with the LLM's narrative. Human review may also be needed.\n"
    )


__all__ = [
    "LLMInvoker",
    "render_mandatory_narrative",
]
