"""Shared fixtures for v2 domain unit tests.

Re-exports the fixtures from ``filters/conftest.py`` so that tests in
``tests/unit/v2/domain/`` (the parent of ``filters/``) can use them.
Pytest's conftest discovery only propagates fixtures downward, so
the parent directory needs its own conftest to bridge.
"""

from __future__ import annotations

from tests.unit.v2.domain.filters.conftest import (
    make_empty_state,
    mock_company_context,
    mock_ontology,
    mock_preprocessing,
    mock_state,
    mock_subdomains,
)

__all__ = [
    "make_empty_state",
    "mock_company_context",
    "mock_ontology",
    "mock_preprocessing",
    "mock_state",
    "mock_subdomains",
]
