"""a05_conditional_extensions — Read conditional_extensions.csv and activate based on ontology flags."""

import logging

from aegis_phase1.models import ConditionalExtension
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def a05_conditional_extensions(state: Phase1State) -> dict:
    """Read conditional extensions CSV and determine which are active.

    Each extension has a triggerCondition that is checked against the
    company context flags (processesPersonalData, doraFinancialEntity, etc.).

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'conditional_extensions' list to be merged into state.
    """
    raw_extensions = state.get("conditional_extensions_data", [])
    company_context = state.get("company_context", {})
    applicable = set(state.get("applicable_regulations", []))

    active_extensions: list[dict] = []

    for row in raw_extensions:
        try:
            ext = ConditionalExtension.model_validate(row)
        except Exception:
            logger.warning("[a05] Skipping invalid extension: %s", row)
            continue

        # Activate based on regulation presence or company flags
        is_active = False
        reg_id = ext.regulation_id.upper() if ext.regulation_id else ""

        if reg_id and reg_id in applicable:
            is_active = True
        elif ext.trigger_condition:
            condition_lower = ext.trigger_condition.lower()
            if (
                (
                    "personal_data" in condition_lower
                    and company_context.get("processes_personal_data")
                )
                or ("dora" in condition_lower and company_context.get("dora_financial_entity"))
                or ("ai" in condition_lower and company_context.get("aiact_high_risk_system"))
                or ("nis2" in condition_lower and company_context.get("nis2_sector"))
                or (
                    "digital_products" in condition_lower
                    and company_context.get("places_digital_products_eu")
                )
            ):
                is_active = True

        ext.is_active = is_active
        active_extensions.append(ext.model_dump(by_alias=True))

    logger.info(
        "[a05] Processed %d extensions, %d active",
        len(raw_extensions),
        sum(1 for e in active_extensions if e.get("isActive")),
    )

    return {
        "conditional_extensions": active_extensions,
        "errors": [],
    }
