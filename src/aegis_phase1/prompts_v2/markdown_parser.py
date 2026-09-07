"""CORR-061 S3a: Backward-compat re-export shim for ``MarkdownParser``.

The canonical implementation was archived to
``aegis_phase1._archive.corr061.markdown_parser`` in S0 (alongside
``robust_parser.py`` and ``validator.py``) as part of the
markdown-only Phase 1 contract. The active code path will consume
raw markdown directly (S3b) and skip the JSON-wrapper parsing
dance this module was designed for.

This shim preserves the legacy import path
``aegis_phase1.prompts_v2.markdown_parser`` so that:

  - existing test modules (``tests/unit/prompts_v2/test_markdown_parser_corr050.py``,
    ``test_markdown_parser_corr053.py``) can collect without changes to
    their import statements;
  - the invoker's lazy imports of ``MARKDOWN_PARSERS`` at runtime still
    resolve to a valid submodule (defense-in-depth — those imports are
    inside methods, so they don't fail collection, but they would still
    fail at runtime if called).

No new logic lives here — this file is a pure re-export.
"""

from aegis_phase1._archive.corr061.markdown_parser import (  # noqa: F401
    MARKDOWN_PARSERS,
    GenericMarkdownParser,
    MarkdownParser,
    P1BLLM01Parser,
    P1CLLM01Parser,
)

__all__ = [
    "MARKDOWN_PARSERS",
    "GenericMarkdownParser",
    "MarkdownParser",
    "P1BLLM01Parser",
    "P1CLLM01Parser",
]
