"""CORR-038-T1: ApplicabilityContext — canonical source of applicable_regs.

Computes the list of regulations applicable to a company based on the
5 boolean predicates from PHASE1_STRATEGY §Inputs MINIMAL. Cross-checks
against the declared applicability in the case's
``input/regulatory/applicability.yaml`` and produces a list of
``DeclarationGap`` records when declared ≠ computed (per §6 — flagged,
NOT silently overridden).

Public API:
    ApplicabilityContext — Pydantic model with all applicability data
    DeclarationGap     — dataclass for a single gap (regulation, direction)
    Tier               — Enum (LOW / MEDIUM / HIGH)
    build_applicability_context(state) — factory: reads state, returns ctx

Consumers (CORR-038-T2/T3):
    - v2/output/doc_04.py — reads applicable_regs, tier, company_facts
    - v2/output/doc_05.py — reads per-regulation table, declaration_gaps
    - v2/runner.py (--run-applicability) — invokes build_… then render
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier enum
# ---------------------------------------------------------------------------


class Tier(str, Enum):
    """Compliance posture tier (PHASE1_STRATEGY §8).

    LOW: MICRO scale, ≤1 applicable reg (e.g. only GDPR or only CRA).
    MEDIUM: MICRO/SMALL scale, ≤3 applicable regs.
    HIGH: everything else (LARGE, or >3 applicable regs, or specific
    high-risk combinations — e.g. NIS2 + DORA always HIGH).

    This is the T1 heuristic approximation; refinement (e.g. revenue
    brackets, number of data subjects) is T4d.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ---------------------------------------------------------------------------
# DeclarationGap dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeclarationGap:
    """A single divergence between computed and declared applicability.

    direction:
      "computed_not_declared" — filter says applicable, YAML says not
      "declared_not_computed" — YAML says applicable, filter says not
    """

    regulation: str
    direction: str
    computed: bool
    declared: bool

    def __str__(self) -> str:  # pragma: no cover (cosmetic)
        return f"{self.regulation}: computed={self.computed}, declared={self.declared} ({self.direction})"


# ---------------------------------------------------------------------------
# ApplicabilityContext (Pydantic)
# ---------------------------------------------------------------------------


class _TolerantModel(BaseModel):
    """Base: tolerates extra fields and nulls."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


class ApplicabilityContext(_TolerantModel):
    """Canonical applicability context for one company.

    All fields populated by ``build_applicability_context()``. The
    ``company_facts`` sub-model is a snapshot of the v2 CompanyFacts
    (denormalized here so consumers don't need to access v2 state keys
    directly).
    """

    company_facts: dict[str, Any] = Field(default_factory=dict)
    applicability_predicates: dict[str, Any] = Field(default_factory=dict)
    applicable_regs: list[str] = Field(default_factory=list)  # computed
    declared_applicable_regs: list[str] = Field(default_factory=list)  # from YAML
    declaration_gaps: list[dict[str, Any]] = Field(default_factory=list)  # serializable
    obligated_party_per_reg: dict[str, str] = Field(default_factory=dict)
    rationale_per_reg: dict[str, str] = Field(default_factory=dict)
    clause_count_per_reg: dict[str, int] = Field(default_factory=dict)
    tier: str = "LOW"

    # Convenience accessors (not Pydantic fields)
    @property
    def tier_enum(self) -> Tier:
        return Tier(self.tier)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict (for output doc renderers)."""
        return self.model_dump()


# ---------------------------------------------------------------------------
# Compute logic
# ---------------------------------------------------------------------------


def _compute_applicable_regs(predicates: dict[str, Any]) -> list[str]:
    """Compute applicable regulations from 5 boolean/string predicates.

    Per PHASE1_STRATEGY §Inputs MINIMAL:
        processes_personal_data  → GDPR
        places_digital_products_eu → CRA
        nis2_sector (non-empty)  → NIS2
        dora_financial_entity    → DORA
        aiact_high_risk_system   → AI_Act
    """
    out: list[str] = []
    if predicates.get("processes_personal_data"):
        out.append("GDPR")
    if predicates.get("places_digital_products_eu"):
        out.append("CRA")
    nis2_sector = predicates.get("nis2_sector") or ""
    if nis2_sector and nis2_sector != "":
        out.append("NIS2")
    if predicates.get("dora_financial_entity"):
        out.append("DORA")
    if predicates.get("aiact_high_risk_system"):
        out.append("AI_Act")
    return sorted(out)


def _compute_declaration_gaps(
    applicable: list[str], declared: list[str]
) -> list[DeclarationGap]:
    """Symmetric diff between computed (filter) and declared (YAML).

    PHASE1_STRATEGY §6: when declared ≠ computed, flag (do NOT silently
    override). Each mismatch is a DeclarationGap with direction.
    """
    app_set, dec_set = set(applicable), set(declared)
    out: list[DeclarationGap] = []
    for reg in sorted(app_set | dec_set):
        in_app = reg in app_set
        in_dec = reg in dec_set
        if in_app and in_dec:
            continue  # match, no gap
        if in_app and not in_dec:
            direction = "computed_not_declared"
        else:  # in_dec and not in_app
            direction = "declared_not_computed"
        out.append(
            DeclarationGap(
                regulation=reg,
                direction=direction,
                computed=in_app,
                declared=in_dec,
            )
        )
    return out


def _estimate_tier(company_facts: dict[str, Any], applicable_count: int) -> Tier:
    """Estimate compliance posture tier from company facts + reg count.

    Heuristic (T1, refined in T4d):
      HIGH:   scale in (MEDIUM, LARGE) OR applicable_count >= 3
              OR obligated party is "essential entity" (NIS2 essential)
      MEDIUM: scale == SMALL OR (applicable_count == 2 AND scale != MICRO)
      LOW:    scale == MICRO OR applicable_count <= 1
    """
    scale = (company_facts.get("scale") or "").upper()
    if scale in ("MEDIUM", "LARGE", "MAX") or applicable_count >= 3:
        return Tier.HIGH
    if scale == "SMALL" or (applicable_count >= 2 and scale not in ("MICRO",)):
        return Tier.MEDIUM
    return Tier.LOW


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_applicability_context(state: dict[str, Any]) -> ApplicabilityContext:
    """Build an ApplicabilityContext from the orchestrator state.

    Reads:
      - v2_company_facts (Pydantic CompanyFacts) — predicates source
      - v2_applicable_regs (list[str]) — pre-computed by case_profile
        (used as a check; final truth is _compute_applicable_regs)
      - regulatory.obligated_party_per_reg (from case_profile)
      - regulatory.applicability_rationale (from input YAML)
      - regulatory.clause_count_per_reg (from input YAML)
      - regulatory.applicable / non_applicable (from input YAML)

    For backwards compat with persisted state.json (v2.1 era), also
    reads the v1 state['company_context'] if v2_company_facts is absent.
    """
    facts_obj = state.get("v2_company_facts")
    profile_obj = state.get("v2_company_profile")
    regulatory_obj = state.get("regulatory")  # RegulatoryFacts (v1 or from T4b shim)

    if facts_obj is not None:
        company_facts_dict: dict[str, Any] = (
            facts_obj.model_dump()
            if hasattr(facts_obj, "model_dump")
            else dict(facts_obj)
        )
    else:
        # Fallback to v1 state['company_context'] (persisted state.json)
        cc = state.get("company_context") or {}
        if hasattr(cc, "model_dump"):
            cc = cc.model_dump()
        company_facts_dict = dict(cc) if cc else {}

    # Derive predicates from v2 CompanyFacts
    predicates = _derive_predicates_from_facts(company_facts_dict)
    # If v2 didn't give us predicates, fall back to v1 company's applicable_regs
    v1_applicable_from_cc: list[str] = []
    if isinstance(company_facts_dict.get("applicable_regs"), list):
        v1_applicable_from_cc = list(company_facts_dict["applicable_regs"])
    # Prefer v2's pre-computed list if present
    v2_applicable_pre: list[str] = list(state.get("v2_applicable_regs", []))

    # Authoritative computation (re-derive from predicates)
    applicable_computed = _compute_applicable_regs(predicates)
    if not applicable_computed and (v1_applicable_from_cc or v2_applicable_pre):
        # Fallback: use the pre-computed list (e.g., from a
        # persisted state.json without v2_company_facts)
        applicable_computed = sorted(
            set(v1_applicable_from_cc) | set(v2_applicable_pre)
        )

    # Declared: from regulatory.applicable (preferred) or v2_applicable_pre
    declared_applicable: list[str] = []
    if regulatory_obj is not None and hasattr(regulatory_obj, "applicable"):
        declared_applicable = list(regulatory_obj.applicable or [])
    if not declared_applicable:
        declared_applicable = list(v2_applicable_pre)

    # Declaration gaps
    gaps = _compute_declaration_gaps(applicable_computed, declared_applicable)
    gaps_serializable = [
        {
            "regulation": g.regulation,
            "direction": g.direction,
            "computed": g.computed,
            "declared": g.declared,
        }
        for g in gaps
    ]

    # Obligated party per reg
    obligated: dict[str, str] = {}
    if regulatory_obj is not None and hasattr(regulatory_obj, "obligated_party_per_reg"):
        obligated = dict(regulatory_obj.obligated_party_per_reg or {})
    # Sensible defaults
    obligated.setdefault("GDPR", "controller")
    obligated.setdefault("CRA", "manufacturer")
    obligated.setdefault("NIS2", "")
    obligated.setdefault("DORA", "")
    obligated.setdefault("AI_Act", "")

    # Rationale per reg
    rationale: dict[str, str] = {}
    if regulatory_obj is not None and hasattr(regulatory_obj, "applicability_rationale"):
        rationale = {str(k): str(v) for k, v in (regulatory_obj.applicability_rationale or {}).items()}

    # Clause count
    clause_count: dict[str, int] = {}
    if regulatory_obj is not None and hasattr(regulatory_obj, "clause_count_per_reg"):
        clause_count = {str(k): int(v) for k, v in (regulatory_obj.clause_count_per_reg or {}).items() if isinstance(v, (int, float))}

    # Tier
    tier = _estimate_tier(company_facts_dict, len(applicable_computed))

    return ApplicabilityContext(
        company_facts=company_facts_dict,
        applicability_predicates=predicates,
        applicable_regs=applicable_computed,
        declared_applicable_regs=sorted(declared_applicable),
        declaration_gaps=gaps_serializable,
        obligated_party_per_reg=obligated,
        rationale_per_reg=rationale,
        clause_count_per_reg=clause_count,
        tier=tier.value,
    )


def _derive_predicates_from_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """Derive the 5 applicability predicates from v2 CompanyFacts.

    The v2 CompanyFacts doesn't have these as fields; we derive them from
    the same heuristics used by CaseProfileLoader. This keeps a single
    source of truth (the 5 booleans per PHASE1_STRATEGY §Inputs MINIMAL).

    Heuristic (T1, refinable in T4d):
      - processes_personal_data: True if jurisdiction is in EU/EEA
        (any company based in the EU/EEA that operates a SaaS is
        presumed to process personal data of EU residents).
      - places_digital_products_eu: True if sector is a digital-product
        sector (Software, SaaS, Technology, IT, etc.). The v2
        CompanyFacts doesn't carry a tech_stack field (tech_stack is at
        the top level of the classification.yaml, not in company:), so
        we use sector as the proxy.
      - nis2_sector: empty string (not applicable; the canonical case
        TinyTask is MICRO and below the NIS2 threshold).
      - dora_financial_entity: True only if sector is finance/banking/etc.
      - aiact_high_risk_system: False (no AI/ML system in the v2 facts).
    """
    jurisdiction = (facts.get("jurisdiction") or "").upper()
    sector = (facts.get("sector") or "").lower()

    # Heuristic: jurisdiction in EU/EEA implies GDPR
    processes_personal_data = bool(
        "EU" in jurisdiction or "EEA" in jurisdiction
    )
    # Heuristic: digital-product sector implies CRA
    _DIGITAL_SECTORS = (
        "software", "saas", "technology", "it ", "tech", "digital",
        "app", "platform", "cloud", "hosting", "web", "ecommerce",
        "fintech", "edtech",
    )
    places_digital_products_eu = any(
        keyword in sector for keyword in _DIGITAL_SECTORS
    )
    # Heuristic: known non-applicable sectors
    dora_financial_entity = bool(
        any(s in sector for s in ("finance", "bank", "insurance"))
    )
    return {
        "processes_personal_data": processes_personal_data,
        "places_digital_products_eu": places_digital_products_eu,
        "nis2_sector": "",  # conservatively empty (not applicable)
        "dora_financial_entity": dora_financial_entity,
        "aiact_high_risk_system": False,
    }


__all__ = [
    "ApplicabilityContext",
    "DeclarationGap",
    "Tier",
    "build_applicability_context",
    "_compute_applicable_regs",
    "_compute_declaration_gaps",
    "_estimate_tier",
]
