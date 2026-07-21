"""CORR-041-T1: SynthesisContext — canonical source of REDUCE-stage output.

Wraps the output of P1C-LLM-03 (strategic synthesis) and P1C-LLM-02
(compound events) plus the Track B proportionality profile and the
per-reg rationale from P1B-LLM-02 into a typed Pydantic context.

Replaces ad-hoc reads of ``state['aggregated_data']['synthesis']`` /
``['compound_events']`` / ``['profile']`` / ``['rationale_by_reg']``
with a single source of truth that downstream consumers (Doc 04a-d,
Doc 07 §5.2/§6.2, the parity check) can depend on.

Public API:
    CompoundEvent       — one compound event (id, regs, description)
    StrategicSynthesis  — P1C-LLM-03 output (prose + insights)
    SynthesisContext    — full REDUCE-stage context
    build_synthesis_context(state) — factory: reads state, returns ctx

Consumers (CORR-041-T2/T3/T4):
    - v2/output/doc_04a-d.py — reads synthesis for §3 narrative
    - v2/output/doc_07.py    — §5.2 compound_events, §6.2 synthesis
    - v2/output/doc_07b.py   — track_b_profile
    - tests/integration/test_phase1_parity.py — full state for diff
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CompoundEvent(BaseModel):
    """One compound event produced by P1C-LLM-02 (multi-regulation incident)."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    event_id: str = ""
    regulations: list[str] = Field(default_factory=list)
    description: str = ""
    severity: str = "MEDIUM"  # LOW / MEDIUM / HIGH / CRITICAL
    layer0_refs: list[str] = Field(default_factory=list)


class StrategicSynthesis(BaseModel):
    """P1C-LLM-03 output (strategic synthesis prose + insights)."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    prose: str = ""  # 2-3 paragraphs of strategic narrative
    insights: list[str] = Field(default_factory=list)  # key takeaways
    implications: list[str] = Field(default_factory=list)  # what to do
    layer0_refs: list[str] = Field(default_factory=list)


class SynthesisContext(BaseModel):
    """Canonical REDUCE-stage context.

    Built from ``state['aggregated_data']`` populated by
    ``orchestrator.reduce_synthesis`` / ``reduce_compound`` /
    ``run_phase_1b`` (per CORR-041-T2/T3). All four consumers
    read from this single typed object.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    synthesis: StrategicSynthesis = Field(default_factory=StrategicSynthesis)
    compound_events: list[CompoundEvent] = Field(default_factory=list)
    track_b_profile: dict[str, Any] = Field(default_factory=dict)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    per_reg_rationale: dict[str, dict[str, Any]] = Field(default_factory=dict)
    status: str = "EMPTY"  # OK | MIXED | FAILED | EMPTY

    def has_synthesis(self) -> bool:
        """True iff P1C-LLM-03 produced a non-empty synthesis."""
        return bool(self.synthesis.prose or self.synthesis.insights)

    def compound_event_count(self) -> int:
        """Number of compound events detected by P1C-LLM-02."""
        return len(self.compound_events)

    def per_reg_count(self) -> int:
        """Number of regulations with P1B-LLM-02 rationale."""
        return len(self.per_reg_rationale)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict."""
        return {
            "synthesis": self.synthesis.model_dump(),
            "compound_events": [e.model_dump() for e in self.compound_events],
            "track_b_profile": dict(self.track_b_profile),
            "conflicts": list(self.conflicts),
            "per_reg_rationale": {k: dict(v) for k, v in self.per_reg_rationale.items()},
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _parse_compound_events(raw: Any) -> list[CompoundEvent]:
    """Parse compound_events from a P1C-LLM-02 output (or a list of dicts)."""
    if not isinstance(raw, list):
        return []
    out: list[CompoundEvent] = []
    for entry in raw:
        if isinstance(entry, CompoundEvent):
            out.append(entry)
            continue
        if not isinstance(entry, dict):
            continue
        # Common shapes: {event_id, regulations, description, ...}
        #              {id, regs, narrative, ...}
        event_id = str(entry.get("event_id") or entry.get("id") or "")
        regs_raw = entry.get("regulations") or entry.get("regs") or []
        if isinstance(regs_raw, str):
            regs = [r.strip() for r in regs_raw.strip("[]").split(",") if r.strip()]
        elif isinstance(regs_raw, list):
            regs = [str(r) for r in regs_raw]
        else:
            regs = []
        out.append(
            CompoundEvent(
                event_id=event_id,
                regulations=regs,
                description=str(entry.get("description") or entry.get("narrative") or ""),
                severity=str(entry.get("severity") or "MEDIUM"),
                layer0_refs=list(entry.get("layer0_refs") or []),
            )
        )
    return out


def _parse_strategic_synthesis(raw: Any) -> StrategicSynthesis:
    """Parse P1C-LLM-03 output into StrategicSynthesis."""
    if isinstance(raw, StrategicSynthesis):
        return raw
    if not isinstance(raw, dict):
        return StrategicSynthesis()
    return StrategicSynthesis(
        prose=str(raw.get("prose") or raw.get("narrative") or raw.get("synthesis") or ""),
        insights=list(raw.get("insights") or raw.get("key_takeaways") or []),
        implications=list(raw.get("implications") or raw.get("actions") or []),
        layer0_refs=list(raw.get("layer0_refs") or []),
    )


def build_synthesis_context(state: dict[str, Any]) -> SynthesisContext:
    """Build the canonical SynthesisContext from V2 state.

    Reads ``state['aggregated_data']`` (populated by orch.reduce_* and
    orch.run_phase_1b). Falls back to empty fields if not yet populated.

    Args:
        state: V2 pipeline state.

    Returns:
        SynthesisContext with all 5 fields populated (or empty defaults).
    """
    agg = state.get("aggregated_data") or {}
    if not isinstance(agg, dict):
        agg = {}

    # Synthesis (P1C-LLM-03 output)
    synth_raw = agg.get("synthesis")
    synthesis = _parse_strategic_synthesis(synth_raw)

    # Compound events (P1C-LLM-02 output)
    compound_raw = agg.get("compound_events")
    compound_events = _parse_compound_events(compound_raw)

    # Track B profile (apply_proportionality output)
    track_b = agg.get("profile") or {}
    if not isinstance(track_b, dict):
        track_b = {}

    # Conflicts (resolve_conflicts output)
    conflicts = agg.get("conflicts") or []
    if not isinstance(conflicts, list):
        conflicts = []

    # Per-reg rationale (P1B-LLM-02 output)
    rationale = agg.get("rationale_by_reg") or {}
    if not isinstance(rationale, dict):
        rationale = {}

    # Status
    has_synth = bool(synthesis.prose or synthesis.insights)
    has_compounds = bool(compound_events)
    has_rationale = bool(rationale)
    if has_synth and has_compounds and has_rationale:
        status = "OK"
    elif has_synth or has_compounds or has_rationale:
        status = "MIXED"
    else:
        status = "EMPTY"

    return SynthesisContext(
        synthesis=synthesis,
        compound_events=compound_events,
        track_b_profile=track_b,
        conflicts=conflicts,
        per_reg_rationale=rationale,
        status=status,
    )


__all__ = [
    "CompoundEvent",
    "StrategicSynthesis",
    "SynthesisContext",
    "build_synthesis_context",
]
