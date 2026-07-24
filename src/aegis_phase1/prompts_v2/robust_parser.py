"""CORR-061 S3a: Backward-compat re-export shim for ``RobustParser``.

The canonical implementation was archived to
``aegis_phase1._archive.corr061.robust_parser`` in S0 (alongside
``validator.py`` and ``markdown_parser.py``) as part of the
markdown-only Phase 1 contract. The active code path now uses
``ContentValidator`` (S2) and a raw-markdown capture flow (S4).

This shim preserves the legacy import path
``aegis_phase1.prompts_v2.robust_parser`` so that:

  - existing test modules (``tests/unit/prompts_v2/test_robust_parser.py``)
    can collect without changes to their import statements;
  - any out-of-tree code or notebook that still uses the old submodule
    name keeps working;
  - the canonical implementation stays single-sourced under
    ``_archive/corr061/`` (no code duplication).

No new logic lives here — this file is a pure re-export.
"""

from aegis_phase1._archive.corr061.robust_parser import (  # noqa: F401
    ParseResult,
    RobustParser,
)

__all__ = ["ParseResult", "RobustParser"]
