"""b06_implementation_mapping — Read implementation_mappings.csv."""

import logging

from aegis_phase1.models import ImplementationMapping
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def b06_implementation_mapping(state: Phase1State) -> dict:
    """Load implementation mappings from CSV data.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'implementation_mappings' list to be merged into state.
    """
    raw_mappings = state.get("implementation_mappings_data", [])

    mappings: list[dict] = []
    for row in raw_mappings:
        try:
            m = ImplementationMapping.model_validate(row)
            mappings.append(m.model_dump(by_alias=True))
        except Exception:
            logger.warning("[b06] Skipping invalid mapping: %s", row)

    logger.info("[b06] Loaded %d implementation mappings", len(mappings))

    return {
        "implementation_mappings": mappings,
        "errors": [],
    }
