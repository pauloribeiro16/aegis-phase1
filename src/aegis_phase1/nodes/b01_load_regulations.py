"""b01_load_regulations — Read 00_regulations.csv and filter by applicable regulations."""

import logging

from aegis_phase1.models import Regulation
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def b01_load_regulations(state: Phase1State) -> dict:
    """Load regulation metadata from CSV, filtered by applicable regulations.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'regulations' list to be merged into state.
    """
    raw_regulations = state.get("regulations", [])
    applicable = state.get("applicable_regulations", [])

    # If raw_regulations already loaded from n01, filter them
    if raw_regulations:
        filtered = []
        for row in raw_regulations:
            reg_id = row.get("regulationId", row.get("id", ""))
            if reg_id in applicable:
                try:
                    reg = Regulation.model_validate(row)
                    filtered.append(reg.model_dump(by_alias=True))
                except Exception:
                    logger.warning("[b01] Skipping invalid regulation: %s", row)
        logger.info(
            "[b01] Loaded %d regulations (filtered from %d)", len(filtered), len(raw_regulations)
        )
        return {"regulations": filtered, "errors": []}

    # Fallback: build minimal regulation dicts from applicable list
    regulations = [{"regulationId": r, "name": r} for r in applicable]
    logger.info("[b01] Built %d minimal regulation entries from applicable list", len(regulations))
    return {"regulations": regulations, "errors": []}
