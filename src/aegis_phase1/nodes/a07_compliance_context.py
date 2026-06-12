"""a07_compliance_context — Deterministic aggregation of applicable regulations into ComplianceContext."""

import logging
from datetime import date

from aegis_phase1.models import ComplianceContext
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def a07_compliance_context(state: Phase1State) -> dict:
    """Deterministic assembly of ComplianceContext from applicable regulations.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with 'compliance_context' dict to be merged into state.
    """
    applicable_regulations = state.get("applicable_regulations", [])
    regulations = state.get("regulations", [])

    # Determine jurisdiction from regulations or default to EU
    jurisdiction_id = "EU"
    for reg in regulations:
        j = reg.get("jurisdiction", "")
        if j:
            jurisdiction_id = j
            break

    ctx = ComplianceContext(
        jurisdictionId=jurisdiction_id,
        applicable_regulations=applicable_regulations,
        assessmentDate=date.today(),
    )

    # Serialize to JSON-safe (date → ISO string) for LangGraph state propagation
    ctx_dict = ctx.model_dump(by_alias=True)
    ctx_dict["assessmentDate"] = date.today().isoformat()

    logger.info(
        "[a07] ComplianceContext: jurisdiction=%s, applicable=%s",
        jurisdiction_id,
        applicable_regulations,
    )

    return {
        "compliance_context": ctx_dict,
        "errors": [],
    }
