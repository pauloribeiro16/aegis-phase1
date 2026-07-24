"""Content-only validator package (CORR-061).

The legacy Phase1Validator (JSON Schema) is archived in
src/aegis_phase1/_archive/corr061/validator.py.
"""
from aegis_phase1.validator.content_check import (
    ContentValidator,
    MIN_CONTENT_CHARS,
    ValidationResult,
)

__all__ = ["ContentValidator", "MIN_CONTENT_CHARS", "ValidationResult"]
