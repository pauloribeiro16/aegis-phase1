"""CORR-061 S3a: Backward-compat re-export shim for ``Phase1Validator``.

The canonical implementation was archived to
``aegis_phase1._archive.corr061.validator`` in S0 (alongside
``robust_parser.py`` and ``markdown_parser.py``) as part of the
markdown-only Phase 1 contract. The active code path now uses
``ContentValidator`` (S2) — see ``aegis_phase1.validator.content_check``.

This shim preserves the legacy import path
``aegis_phase1.prompts_v2.validator`` so that:

  - existing test modules (``tests/unit/prompts_v2/test_validator.py``,
    ``test_validator_schema_loading_corr049.py``, ``test_corr005_aliases.py``,
    ``test_smoke_e2e.py``) can collect without changes to their import
    statements;
  - any out-of-tree code or notebook that still uses the old submodule
    name keeps working;
  - the canonical implementation stays single-sourced under
    ``_archive/corr061/`` (no code duplication).

No new logic lives here — this file is a pure re-export.
"""

from aegis_phase1._archive.corr061.validator import (  # noqa: F401
    Phase1Validator,
    ValidationError,
)

__all__ = ["Phase1Validator", "ValidationError"]
