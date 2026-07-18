"""Filter ambiguity analyses by applicable regulations."""

from __future__ import annotations

import logging
from pathlib import Path

from aegis_phase1.v2.domain.filters.regs import filter_regs
from aegis_phase1.v2.loader.ambiguity_loader import load_ambiguities_for_regs
from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)

# Fallback only — the canonical source is ``state["preprocessing_path"]``
# (set by ``Phase1Orchestrator.load`` from the case loader). Kept so the
# filter does not crash if a caller constructs a minimal state without the
# preprocessing path (e.g. legacy tests).
_FALLBACK_AMBIGUITY_BASE_PATH = Path(
    "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/" "00_METHODOLOGY/PREPROCESSING"
)


def _resolve_base_path(state: V2State) -> Path:
    """Return the preprocessing base path from state, falling back to the
    historical constant when the state key is absent."""
    raw = state.get("preprocessing_path") or state.get("regulatory_baseline_path")
    if raw:
        return Path(raw)
    logger.debug(
        "state has no preprocessing_path/regulatory_baseline_path; using fallback %s",
        _FALLBACK_AMBIGUITY_BASE_PATH,
    )
    return _FALLBACK_AMBIGUITY_BASE_PATH


def filter_ambiguities(state: V2State, domain_id: str) -> list[dict[str, str]]:
    """Return ambiguity entries for regulations applicable to a domain.

    Regulation applicability is taken from the domain filter first and from
    ``company_context.applicable_regs`` when the domain filter has no result.
    Missing ambiguity source directories produce an empty result.

    When ``domain_id`` is a known AEGIS domain (``D-01``..``D-10``) the
    loaded entries are filtered to clause families relevant to that
    domain (records of processing, manufacturer documentation, etc.),
    keeping the §6 KNOWN AMBIGUITIES section under the prompt budget.
    Unknown domain IDs fall back to the unfiltered set.
    """
    regs = filter_regs(state, domain_id)
    if not regs:
        ctx = state.get("company_context")
        if ctx is not None:
            regs = list(getattr(ctx, "applicable_regs", []) or [])
    if not regs:
        return []

    base_path = _resolve_base_path(state)
    result = load_ambiguities_for_regs(regs, base_path, domain_id=domain_id)
    logger.debug(
        "filter_ambiguities(%s): %d entries (filtered)", domain_id, len(result)
    )
    return result


__all__ = ["filter_ambiguities"]
