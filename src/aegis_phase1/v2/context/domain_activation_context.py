"""CORR-040-T1: DomainActivationContext — canonical source of per-domain activation.

Wraps the output of P1C-LLM-01 (overlap classification) into a
typed Pydantic context. Replaces the legacy ``state['aggregated_data']``
shim as the single source of truth for the per-domain lane output.

Public API:
    CoverageLevel          — Enum (FULL / PARTIAL / NOT_ADDRESSED)
    SubDomainActivation    — one sub-domain verdict within a lane
    DomainLaneActivation   — one lane (D-XX) with its sub_domain_activations
    DomainActivationContext — all 10 lanes aggregated
    build_domain_activation_context(state) — factory: reads state, returns ctx

Consumers (CORR-040-T2/T3/T4):
    - v2/output/doc_07.py — reads lanes, sub_domain_activations, coverage
    - v2/output/doc_07b.py — reads lanes for Track B proportionality
    - v2/runner.py (--run-map) — invokes build_… then prints summary
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CoverageLevel(str, Enum):
    """Sub-domain coverage level (P1C-LLM-01 output)."""

    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NOT_ADDRESSED = "NOT_ADDRESSED"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SubDomainActivation(BaseModel):
    """One sub-domain verdict within a lane (P1C-LLM-01 activation record).

    Fields mirror the output schema in
    ``prompts/P1C-LLM-01-OVERLAP-CLASSIFICATION.md``.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    sub_domain_id: str  # "D-01.1"
    reg_pair: list[str] = Field(default_factory=list)  # ["GDPR", "CRA"] or []
    company_scope_verdict: str = "INDETERMINATE"  # APPLICABLE / NOT_APPLICABLE / INDETERMINATE
    regulatory_baseline_relationship: str = ""  # SUBSTANTIVE / OVERLAPPING / etc.
    layer0_refs: list[str] = Field(default_factory=list)
    confidence: str = "UNKNOWN"  # HIGH / MEDIUM / LOW / UNKNOWN


class DomainLaneActivation(BaseModel):
    """One domain lane (D-XX) with its sub-domain activations."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    lane_id: str  # "D-01"
    domain_name: str = ""  # "Data Protection"
    coverage_level: CoverageLevel = CoverageLevel.NOT_ADDRESSED
    llm_status: str = "SKIPPED"  # OK / FAILED / SKIPPED
    sub_domain_activations: list[SubDomainActivation] = Field(default_factory=list)
    latency_ms: int = 0
    error_reason: str = ""


class DomainActivationContext(BaseModel):
    """Canonical activation context: 10 lanes (D-01..D-10) aggregated.

    Built from ``state['domain_results']`` (set by orch.map_domains)
    + ``state['v2_subdomains']`` (set by _load_v2_catalog).
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    lanes: list[DomainLaneActivation] = Field(default_factory=list)
    total_lanes: int = 0
    ok_lanes: int = 0
    failed_lanes: int = 0
    total_sub_domain_activations: int = 0
    per_reg_count: dict[str, int] = Field(default_factory=dict)

    def by_domain(self, lane_id: str) -> DomainLaneActivation | None:
        """Return the lane for a given D-XX (or None if absent)."""
        for lane in self.lanes:
            if lane.lane_id == lane_id:
                return lane
        return None

    def sub_domains_covered(self) -> set[str]:
        """Return the set of sub-domain IDs with at least one APPLICABLE verdict."""
        out: set[str] = set()
        for lane in self.lanes:
            for sd in lane.sub_domain_activations:
                if sd.company_scope_verdict == "APPLICABLE":
                    out.add(sd.sub_domain_id)
        return out

    def pairs_with_indeterminate(self) -> set[tuple[str, tuple[str, str]]]:
        """Return (sub_domain_id, (reg_a, reg_b)) tuples flagged INDETERMINATE."""
        out: set[tuple[str, tuple[str, str]]] = set()
        for lane in self.lanes:
            for sd in lane.sub_domain_activations:
                if sd.company_scope_verdict == "INDETERMINATE" and len(sd.reg_pair) == 2:
                    key = (sd.sub_domain_id, tuple(sorted(sd.reg_pair)))
                    out.add(key)
        return out

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict."""
        return {
            "lanes": [lane.model_dump() for lane in self.lanes],
            "total_lanes": self.total_lanes,
            "ok_lanes": self.ok_lanes,
            "failed_lanes": self.failed_lanes,
            "total_sub_domain_activations": self.total_sub_domain_activations,
            "per_reg_count": dict(self.per_reg_count),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _lane_coverage_from_activations(
    activations: list[SubDomainActivation],
) -> CoverageLevel:
    """Compute a lane's coverage level from its sub-domain activations."""
    if not activations:
        return CoverageLevel.NOT_ADDRESSED
    applicable = sum(
        1 for a in activations if a.company_scope_verdict == "APPLICABLE"
    )
    if applicable == len(activations):
        return CoverageLevel.FULL
    if applicable > 0:
        return CoverageLevel.PARTIAL
    return CoverageLevel.NOT_ADDRESSED


def _parse_sub_domain_activations(
    raw_activations: Any,
    domain_id: str,
) -> list[SubDomainActivation]:
    """Parse sub_domain_activations from a v3 parser result.

    The v3 parser returns ``adapted_subdomains_v3`` (list of dicts).
    We also accept the legacy ``adapted_subdomains`` shape (list of
    dicts with sub_domain_id + applicable flag).
    """
    out: list[SubDomainActivation] = []
    if not isinstance(raw_activations, list):
        return out
    for raw in raw_activations:
        if not isinstance(raw, dict):
            continue
        sd_id = str(raw.get("sub_domain_id") or raw.get("id") or "")
        if not sd_id.startswith(domain_id + "."):
            # Skip sub-domains that don't belong to this lane
            continue
        # reg_pair may be a list, a single string, or a string like "[GDPR, CRA]"
        reg_pair_raw = raw.get("reg_pair") or raw.get("regulations") or []
        if isinstance(reg_pair_raw, str):
            # Strip brackets
            reg_pair_raw = reg_pair_raw.strip("[]")
            reg_pair = [r.strip() for r in reg_pair_raw.split(",") if r.strip()]
        elif isinstance(reg_pair_raw, list):
            reg_pair = [str(r) for r in reg_pair_raw]
        else:
            reg_pair = []
        # company_scope_verdict: APPLICABLE / NOT_APPLICABLE / INDETERMINATE
        verdict = str(
            raw.get("company_scope_verdict")
            or raw.get("verdict")
            or raw.get("applicable")
            or "INDETERMINATE"
        )
        if verdict.lower() in ("true", "yes", "1"):
            verdict = "APPLICABLE"
        elif verdict.lower() in ("false", "no", "0"):
            verdict = "NOT_APPLICABLE"
        else:
            verdict = verdict.upper()
            if verdict not in ("APPLICABLE", "NOT_APPLICABLE", "INDETERMINATE"):
                verdict = "INDETERMINATE"
        out.append(
            SubDomainActivation(
                sub_domain_id=sd_id,
                reg_pair=reg_pair,
                company_scope_verdict=verdict,
                regulatory_baseline_relationship=str(
                    raw.get("regulatory_baseline_relationship")
                    or raw.get("relationship")
                    or ""
                ),
                layer0_refs=list(raw.get("layer0_refs") or []),
                confidence=str(raw.get("confidence") or "UNKNOWN"),
            )
        )
    return out


def build_domain_activation_context(
    state: dict[str, Any],
) -> DomainActivationContext:
    """Build the canonical DomainActivationContext from V2 state.

    Reads:
      - ``state['domain_results']`` (set by orch.map_domains; per-D-XX dict)
      - ``state['v2_subdomains']`` (38 sub-domains for ID validation)

    Returns:
        DomainActivationContext with 10 lanes (D-01..D-10), most with
        llm_status='SKIPPED' if MAP has not run.
    """
    from aegis_phase1.v2.domain.processor import DOMAIN_NAMES

    domain_results = state.get("domain_results") or {}
    v2_subdomains = state.get("v2_subdomains") or []
    v2_sd_ids = {getattr(s, "id", None) for s in v2_subdomains}
    v2_sd_ids.discard(None)

    lanes: list[DomainLaneActivation] = []
    total_sd_activations = 0
    per_reg_count: dict[str, int] = {}
    ok_count = 0
    failed_count = 0

    for did in [f"D-{i:02d}" for i in range(1, 11)]:
        result = domain_results.get(did) if isinstance(domain_results, dict) else None
        if not isinstance(result, dict):
            # Lane not yet processed — emit a SKIPPED lane
            lanes.append(
                DomainLaneActivation(
                    lane_id=did,
                    domain_name=DOMAIN_NAMES.get(did, did),
                    coverage_level=CoverageLevel.NOT_ADDRESSED,
                    llm_status="SKIPPED",
                    sub_domain_activations=[],
                    latency_ms=0,
                )
            )
            continue

        # Extract sub_domain_activations from result
        sd_raw = (
            result.get("adapted_subdomains_v3")
            or result.get("adapted_subdomains")
            or []
        )
        activations = _parse_sub_domain_activations(sd_raw, did)
        coverage = _lane_coverage_from_activations(activations)
        status = str(result.get("llm_status") or "SKIPPED")
        if status == "OK":
            ok_count += 1
        elif status == "FAILED":
            failed_count += 1

        # Per-reg count (count activations where reg_pair includes the reg)
        for a in activations:
            for r in a.reg_pair:
                per_reg_count[r] = per_reg_count.get(r, 0) + 1

        total_sd_activations += len(activations)
        lanes.append(
            DomainLaneActivation(
                lane_id=did,
                domain_name=DOMAIN_NAMES.get(did, did),
                coverage_level=coverage,
                llm_status=status,
                sub_domain_activations=activations,
                latency_ms=int(result.get("latency_ms") or 0),
                error_reason=str(result.get("error_reason") or ""),
            )
        )

    return DomainActivationContext(
        lanes=lanes,
        total_lanes=len(lanes),
        ok_lanes=ok_count,
        failed_lanes=failed_count,
        total_sub_domain_activations=total_sd_activations,
        per_reg_count=per_reg_count,
    )


__all__ = [
    "CoverageLevel",
    "DomainActivationContext",
    "DomainLaneActivation",
    "SubDomainActivation",
    "build_domain_activation_context",
]
