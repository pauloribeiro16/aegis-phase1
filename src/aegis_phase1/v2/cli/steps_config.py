"""steps_config — Stage definitions for the v2 pipeline.

Defines the 4 pipeline stages (LOAD → MAP → REDUCE → OUTPUT) with their
metadata and a lookup helper.

References:
    - contracts/SPRINT001_v2-core.md (C-005)
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StageDef:
    """Metadata for a single pipeline stage.

    Attributes:
        id: Stage identifier (e.g. ``"load"``).
        name: Human-readable stage name.
        description: One-line description of the stage's purpose.
        order: Zero-based execution order.
        handler: Method name on ``Phase1Orchestrator``, resolved at runtime.
    """

    id: str
    name: str
    description: str
    order: int
    handler: str = ""


STAGES: list[StageDef] = [
    StageDef(
        id="load",
        name="Load inputs",
        description=(
            "Load company context, taxonomy, ontology, sub-domains from 3 sources"
        ),
        order=0,
        handler="load",
    ),
    StageDef(
        id="map",
        name="Map domains (LLM)",
        description=(
            "Process each macro-domain with LLM — adapt HSOs to company scale"
        ),
        order=1,
        handler="map_domains",
    ),
    StageDef(
        id="reduce",
        name="Reduce & resolve",
        description="Concatenate, merge, resolve conflicts, apply proportionality",
        order=2,
        handler="reduce",
    ),
    StageDef(
        id="output",
        name="Generate outputs",
        description="Generate all 10 output documents from templates",
        order=3,
        handler="generate_outputs",
    ),
]


def get_stage_by_id(stage_id: str) -> StageDef | None:
    """Look up a stage definition by its identifier.

    Args:
        stage_id: The stage ``id`` to find.

    Returns:
        The matching ``StageDef``, or ``None`` if not found.
    """
    for stage in STAGES:
        if stage.id == stage_id:
            return stage
    return None
