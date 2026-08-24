"""Re-export shim for the markdown parsers (CORR-050 / CORR-053 / CORR-061 / CORR-074).

The full implementation lives in ``aegis_phase1._archive.corr061.markdown_parser``
(archived during the markdown-only Phase 1 contract). This module exposes the
public surface — ``MARKDOWN_PARSERS``, ``MarkdownParser``, ``GenericMarkdownParser``,
and the per-spec parsers ``P1BLLM01Parser`` / ``P1BLLM02Parser`` /
``P1CLLM01Parser`` / ``P1CLLM02Parser`` / ``P1CLLM03Parser`` — so callers can
import from the canonical ``prompts_v2.markdown_parser`` path.

CORR-074 propagated the markdown + tolerant regex parser pattern to all five
Phase 1 prompt specs (P1B-LLM-01/02, P1C-LLM-01/02/03). New code should import
the per-spec parsers from here, not from the archived submodule.

No new logic lives here — this file is a pure re-export.
"""

from aegis_phase1._archive.corr061.markdown_parser import (
    MARKDOWN_PARSERS,
    GenericMarkdownParser,
    MarkdownParser,
    P1BLLM01Parser,
    P1BLLM02Parser,
    P1CLLM01Parser,
    P1CLLM02Parser,
    P1CLLM03Parser,
)

__all__ = [
    "MARKDOWN_PARSERS",
    "GenericMarkdownParser",
    "MarkdownParser",
    "P1BLLM01Parser",
    "P1BLLM02Parser",
    "P1CLLM01Parser",
    "P1CLLM02Parser",
    "P1CLLM03Parser",
]
