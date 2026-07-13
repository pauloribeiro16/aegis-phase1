"""Registry of the 5 Phase 1 LLMs (canonical v1.2 names + invocation patterns).

Source of truth: 00_METHODOLOGY/diagrams/fluxdiagram/phase1/ (post-v1.2 refactor)
PROMPTS/ library: 00_METHODOLOGY/PROMPTS/P1?-LLM-*.md
"""

from __future__ import annotations

from typing import Literal

InvocationPattern = Literal["per_regulation", "per_domain_lane", "global_reduce"]

LLM_SPECS: dict[str, dict[str, str]] = {
    "P1B-LLM-01-INTERPRETATION": {
        "invocation_pattern": "per_regulation",
        "stage": "Phase 1B",
        "function": "Per-regulation interpretation + derogation catalog activation",
        "legacy_alias": "LLM-A",
    },
    "P1B-LLM-02-RATIONALE": {
        "invocation_pattern": "per_regulation",
        "stage": "Phase 1B",
        "function": (
            "Per-regulation synthesis (rationale + implications + gaps merged; "
            "replaces legacy LLM-B + LLM-C + LLM-D)"
        ),
        "legacy_alias": "LLM-B/C/D (merged)",
    },
    "P1C-LLM-01-OVERLAP-CLASSIFICATION": {
        "invocation_pattern": "per_domain_lane",
        "stage": "Phase 1C Map",
        "function": (
            "Per-domain overlap activation. NO re-classification of Layer 0 relationships. "
            "Activates Layer 0 CONDITIONAL entries."
        ),
        "legacy_alias": "LLM-E",
    },
    "P1C-LLM-02-COMPOUND-EVENT": {
        "invocation_pattern": "global_reduce",
        "stage": "Phase 1C Reduce (runs 2nd)",
        "function": (
            "Cross-domain compound event identification. "
            "NO resolution design (resolution moves to Phase 2B)."
        ),
        "legacy_alias": "LLM-F",
    },
    "P1C-LLM-03-STRATEGIC-SYNTHESIS": {
        "invocation_pattern": "global_reduce",
        "stage": "Phase 1C Reduce (runs 1st)",
        "function": (
            "Cross-lane strategic implications. Consumes Doc 07b (deterministic) "
            "as constraint. NO control/effort/tier changes (Track B authoritative)."
        ),
        "legacy_alias": "LLM-G",
    },
}


def get_invocation_pattern(spec_id: str) -> InvocationPattern:
    """Return the canonical invocation pattern for a Phase 1 LLM."""
    if spec_id not in LLM_SPECS:
        raise KeyError(f"Unknown Phase 1 LLM spec_id: {spec_id}")
    return LLM_SPECS[spec_id]["invocation_pattern"]  # type: ignore[return-value]


def get_stage(spec_id: str) -> str:
    """Return the canonical stage label for a Phase 1 LLM."""
    if spec_id not in LLM_SPECS:
        raise KeyError(f"Unknown Phase 1 LLM spec_id: {spec_id}")
    return LLM_SPECS[spec_id]["stage"]


def get_legacy_alias(spec_id: str) -> str:
    """Return the legacy LLM alias (e.g. LLM-A) for a Phase 1 LLM."""
    if spec_id not in LLM_SPECS:
        raise KeyError(f"Unknown Phase 1 LLM spec_id: {spec_id}")
    return LLM_SPECS[spec_id]["legacy_alias"]


def list_specs() -> list[str]:
    """List all registered Phase 1 LLM spec_ids (sorted)."""
    return sorted(LLM_SPECS.keys())
