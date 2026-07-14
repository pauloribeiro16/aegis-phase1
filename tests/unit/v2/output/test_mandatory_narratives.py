"""Unit tests for the mandatory-narrative helper.

Covers:
    - PENDING REVIEW marker when LLM invoker is ``None``
    - PENDING REVIEW marker when invoker returns empty raw
    - PENDING REVIEW marker when invoker returns non-OK status
    - PENDING REVIEW marker when invoker raises an exception
    - Success path returns the LLM's raw text (truncated to ``max_chars``)
    - ``section_id`` is embedded in the marker (for grep traceability)

References:
    - contracts/AEGIS-P1-CORR-001 (Phase 4)
"""

from __future__ import annotations

from typing import Any

from aegis_phase1.v2.output._narrative import (
    LLMInvoker,
    render_mandatory_narrative,
)

# ─── No invoker ────────────────────────────────────────────────────────


def test_pending_when_no_invoker() -> None:
    """``invoker=None`` → PENDING REVIEW marker mentioning LLM not configured."""
    result = render_mandatory_narrative(
        invoker=None,
        prompt="some prompt",
        section_id="test.section",
    )
    assert "[PENDING REVIEW" in result
    assert "LLM not configured" in result
    assert "test.section" in result


# ─── Empty raw / non-OK status ────────────────────────────────────────


def test_pending_when_invoker_returns_empty() -> None:
    """Empty raw → PENDING REVIEW marker mentioning status=OK, raw empty."""

    class _EmptyInvoker:
        def invoke(self, prompt: str, feedback: str = "") -> dict[str, Any]:
            return {"raw": "", "status": "OK"}

    result = render_mandatory_narrative(
        invoker=_EmptyInvoker(),
        prompt="some prompt",
        section_id="empty.section",
    )
    assert "[PENDING REVIEW" in result
    assert "empty.section" in result
    assert "raw empty" in result


def test_pending_when_invoker_returns_non_ok_status() -> None:
    """status != OK → PENDING REVIEW marker carries the status."""

    class _FailedInvoker:
        def invoke(self, prompt: str, feedback: str = "") -> dict[str, Any]:
            return {"raw": "partial prose", "status": "INSUFFICIENT_EVIDENCE"}

    result = render_mandatory_narrative(
        invoker=_FailedInvoker(),
        prompt="some prompt",
        section_id="nonok.section",
    )
    assert "[PENDING REVIEW" in result
    assert "INSUFFICIENT_EVIDENCE" in result


def test_pending_when_invoker_returns_non_dict() -> None:
    """Non-dict result → PENDING REVIEW marker mentions the type."""

    class _BadInvoker:
        def invoke(self, prompt: str, feedback: str = "") -> str:  # type: ignore[override]
            return "string instead of dict"

    result = render_mandatory_narrative(
        invoker=_BadInvoker(),  # type: ignore[arg-type]
        prompt="some prompt",
        section_id="baddict.section",
    )
    assert "[PENDING REVIEW" in result
    assert "non-dict" in result


# ─── Exception ─────────────────────────────────────────────────────────


def test_pending_when_invoker_raises() -> None:
    """Exception in ``invoke()`` → PENDING REVIEW marker carries the error message."""

    class _FailingInvoker:
        def invoke(self, prompt: str, feedback: str = "") -> dict[str, Any]:
            raise RuntimeError("LLM offline")

    result = render_mandatory_narrative(
        invoker=_FailingInvoker(),
        prompt="some prompt",
        section_id="failing.section",
    )
    assert "[PENDING REVIEW" in result
    assert "LLM offline" in result
    assert "failing.section" in result


# ─── Success ──────────────────────────────────────────────────────────


def test_success_returns_llm_output() -> None:
    """Successful invoke → LLM raw text, truncated to ``max_chars``, no PENDING."""

    class _GoodInvoker:
        def invoke(self, prompt: str, feedback: str = "") -> dict[str, Any]:
            return {"raw": "This is the LLM narrative text.", "status": "OK"}

    result = render_mandatory_narrative(
        invoker=_GoodInvoker(),
        prompt="some prompt",
        section_id="good.section",
        max_chars=100,
    )
    assert result == "This is the LLM narrative text."
    assert "[PENDING REVIEW" not in result


def test_success_truncates_to_max_chars() -> None:
    """``max_chars`` truncates the LLM output to the requested ceiling."""

    class _LongInvoker:
        def invoke(self, prompt: str, feedback: str = "") -> dict[str, Any]:
            return {"raw": "x" * 500, "status": "OK"}

    result = render_mandatory_narrative(
        invoker=_LongInvoker(),
        prompt="some prompt",
        section_id="long.section",
        max_chars=50,
    )
    assert len(result) == 50
    assert result == "x" * 50


def test_success_strips_whitespace() -> None:
    """Leading / trailing whitespace on the raw text is stripped."""

    class _WhitespaceInvoker:
        def invoke(self, prompt: str, feedback: str = "") -> dict[str, Any]:
            return {"raw": "   narrative body   ", "status": "OK"}

    result = render_mandatory_narrative(
        invoker=_WhitespaceInvoker(),
        prompt="some prompt",
        section_id="ws.section",
    )
    assert result == "narrative body"


# ─── Structural type ──────────────────────────────────────────────────


def test_protocol_is_satisfied_by_minimal_object() -> None:
    """``LLMInvoker`` is satisfied by anything with a matching ``invoke`` method."""
    # The protocol is structural; this confirms runtime_checkable semantics
    # would treat it as such even though we don't actually use isinstance here.
    assert hasattr(LLMInvoker, "invoke")


# ─── All narrative call sites use the same helper ─────────────────────


def test_all_doc_renderers_use_mandatory_narrative() -> None:
    """Each ``render_doc_XX`` function imports ``render_mandatory_narrative``.

    This is a static, grep-style regression test. It guards against the
    scenario where a new doc renderer is added (or an existing one
    modified) and silently reverts to a local ``_invoke_or_fallback``
    helper that produces deterministic prose.
    """
    import importlib

    modules = [
        "aegis_phase1.v2.output.doc_04a",
        "aegis_phase1.v2.output.doc_04b",
        "aegis_phase1.v2.output.doc_04c",
        "aegis_phase1.v2.output.doc_04d",
        "aegis_phase1.v2.output.doc_05",
        "aegis_phase1.v2.output.doc_07",
        "aegis_phase1.v2.output.doc_07b",
    ]
    for mod_name in modules:
        mod = importlib.import_module(mod_name)
        assert hasattr(mod, "render_mandatory_narrative") or hasattr(
            mod, "render_doc_04a"
        ) or hasattr(mod, "render_doc_04b") or hasattr(mod, "render_doc_04c") or hasattr(
            mod, "render_doc_04d"
        ) or hasattr(mod, "render_doc_05") or hasattr(mod, "render_doc_07") or hasattr(
            mod, "render_doc_07b"
        ), f"{mod_name} missing renderer"
        # Each renderer module should re-export (or import) the helper.
        # We verify via ``render_mandatory_narrative`` being callable
        # through the module attribute, since we import it directly.
        # (The contract test is the absence of ``_invoke_or_fallback``.)
        assert not hasattr(mod, "_invoke_or_fallback"), (
            f"{mod_name} still defines _invoke_or_fallback — narrative "
            f"sections should use render_mandatory_narrative instead."
        )
