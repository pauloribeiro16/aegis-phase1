"""b05_responsibility — Deterministic: for each applicable reg, create ResponsibilityEntry.

NATIVE if company is primary actor, INHERITED if from third-party.
"""

import logging

from aegis_phase1.models import ResponsibilityEntry
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def b05_responsibility(state: Phase1State) -> dict:
    """Deterministically create responsibility entries per applicable regulation.

    Determines whether the company has NATIVE compliance responsibility
    (direct obligations) or INHERITED (through third-party providers).

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'responsibility_entries' list to be merged into state.
    """
    applicable = state.get("applicable_regulations", [])
    regulations = state.get("regulations", [])
    company_context = state.get("company_context", {})

    entries: list[dict] = []

    # Simple heuristic: company is directly responsible for most regs
    # INHERITED only when company is clearly a downstream user/processor
    for reg in regulations:
        reg_id = reg.get("regulationId", reg.get("id", ""))
        reg_name = reg.get("name", reg_id)
        if reg_id not in applicable:
            continue

        # Determine responsibility type
        responsibility_type = "NATIVE"
        rationale = f"Company has direct obligations under {reg_name}"

        # DORA: financial entities have native responsibility
        if reg_id.upper() == "DORA":
            if company_context.get("dora_financial_entity"):
                responsibility_type = "NATIVE"
                rationale = "Company is a financial entity under DORA"
            else:
                responsibility_type = "INHERITED"
                rationale = "Company is not a direct DORA financial entity"

        # For processor-only scenarios under GDPR
        if reg_id.upper() == "GDPR" and not company_context.get("processes_personal_data"):
            responsibility_type = "INHERITED"
            rationale = "Company does not directly process personal data"

        entry = ResponsibilityEntry(
            entryId=f"RE-{reg_id}-{len(entries) + 1:03d}",
            responsibilityType=responsibility_type,
            rationale=rationale,
            regulationId=reg_id,
        )
        entries.append(entry.model_dump(by_alias=True))

    logger.info("[b05] Created %d responsibility entries", len(entries))

    return {
        "responsibility_entries": entries,
        "errors": [],
    }
