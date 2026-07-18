"""CORR-023: the article and ambiguity filters must resolve the
preprocessing base path from ``state["preprocessing_path"]`` rather than
the legacy hardcoded module-level constant. This is the portability fix —
the path ``/home/epmq-cyber/.../Methodology-main/...`` was baked into
``filters/articles.py`` and ``filters/ambiguities.py`` before CORR-023.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from aegis_phase1.v2.domain.filters.ambiguities import filter_ambiguities
from aegis_phase1.v2.domain.filters.articles import filter_articles
from aegis_phase1.v2.state import V2State

from .conftest import PREPROCESSING_PATH


def _state_with_path(mock_state: V2State, path: str) -> V2State:
    """Return a copy of ``mock_state`` with the preprocessing path overridden."""
    state = dict(mock_state)
    state["preprocessing_path"] = path
    return state


def test_filter_articles_uses_state_preprocessing_path(mock_state: V2State) -> None:
    """filter_articles must read the base path from state, not from a
    module-level constant. We assert this by pointing state at the real
    Methodology tree via the state key and confirming non-empty output."""
    state = _state_with_path(mock_state, PREPROCESSING_PATH)
    articles = filter_articles(state, "D-04")
    assert articles, "filter_articles returned empty when state path is set correctly"


def test_filter_articles_state_path_overrides_fallback(mock_state: V2State) -> None:
    """When state['preprocessing_path'] is set, the loader must use it even
    if the fallback constant would point elsewhere. We patch the fallback
    constant to a bogus path and confirm the state path still wins."""
    from aegis_phase1.v2.domain.filters import articles as articles_mod

    state = _state_with_path(mock_state, PREPROCESSING_PATH)
    with patch.object(articles_mod, "_FALLBACK_OJ_BASE_PATH", Path("/nonexistent")):
        articles = filter_articles(state, "D-04")
    assert articles, (
        "state['preprocessing_path'] did not override the fallback constant — "
        "the path rewire is broken."
    )


def test_filter_ambiguities_uses_state_preprocessing_path(mock_state: V2State) -> None:
    """Same as test_filter_articles_uses_state_preprocessing_path, for the
    ambiguity filter."""
    state = _state_with_path(mock_state, PREPROCESSING_PATH)
    entries = filter_ambiguities(state, "D-10")
    assert entries, "filter_ambiguities returned empty when state path is set correctly"


def test_filter_ambiguities_state_path_overrides_fallback(mock_state: V2State) -> None:
    """Same override test for the ambiguity filter."""
    from aegis_phase1.v2.domain.filters import ambiguities as ambiguities_mod

    state = _state_with_path(mock_state, PREPROCESSING_PATH)
    with patch.object(ambiguities_mod, "_FALLBACK_AMBIGUITY_BASE_PATH", Path("/nonexistent")):
        entries = filter_ambiguities(state, "D-10")
    assert entries, (
        "state['preprocessing_path'] did not override the fallback constant — "
        "the path rewire is broken."
    )


def test_filters_fall_back_when_state_missing(mock_state: V2State) -> None:
    """When state has no preprocessing_path/regulatory_baseline_path key,
    the filters must use the module-level fallback constant (legacy path)
    rather than crashing. This preserves backward-compat for minimal states."""
    # Strip the path keys
    state = dict(mock_state)
    state.pop("preprocessing_path", None)
    state.pop("regulatory_baseline_path", None)

    # Should not raise; result depends on the fallback constant pointing at
    # a real tree (it does on this machine).
    articles = filter_articles(state, "D-04")
    ambiguities = filter_ambiguities(state, "D-10")
    # We don't assert non-empty here (the fallback might be wrong on a
    # different machine); we only assert no exception.
    assert isinstance(articles, list)
    assert isinstance(ambiguities, list)
