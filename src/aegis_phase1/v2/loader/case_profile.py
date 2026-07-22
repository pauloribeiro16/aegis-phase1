"""CORR-037-T2: CaseProfileLoader — loads case-specific inputs into CompanyProfile.

Reads from `cases/<case>/input/` (treated as read-only per AGENTS.md §0):
  - company/classification.yaml   (canonical — see contract §T2)
  - company/business_goals.yaml   (BG-01..BG-05)
  - company/stakeholders.yaml     (SH-01..SH-07)
  - regulatory/applicability.yaml (declared applicable regs)
  - architecture/*.yaml          (5 files: auth_systems, cloud_services,
                                  data_flows, data_stores, systems)

Produces a `CompanyProfile` Pydantic with:
  - company (CompanyFacts from classification.yaml)
  - applicability_predicates (derived from applicable_regs)
  - applicable_regs (computed)
  - declared_applicable_regs (from regulatory/applicability.yaml)
  - declaration_gaps (diff declared vs computed)
  - architecture (ArchitectureFacts aggregating the 5 architecture YAMLs)
  - regulatory (RegulatoryFacts with obligated_party_per_reg)
  - business_goals (list[BusinessGoal])
  - stakeholders (list[Stakeholder])

Conventions (AGENTS.md §11):
- AI_Act canonical (not AIACT / AI Act / AIA).
- Scale is one of MICRO / SMALL / MEDIUM / LARGE.
- declaration_gaps is the symmetric difference between declared and computed.
"""

from __future__ import annotations

import logging
from functools import cache as functools_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class _TolerantModel(BaseModel):
    """Base: tolerates extra fields and nulls."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


class CompanyFacts(_TolerantModel):
    """Canonical company facts from classification.yaml#company.

    Post-CORR-036 invariant: TinyTask is MICRO (8 employees, 2M EUR revenue).
    """

    name: str
    legal_structure: str | None = None
    sector: str = ""
    jurisdiction: str = ""
    employees: int
    revenue_eur: int
    scale: str  # MICRO / SMALL / MEDIUM / LARGE
    security_fte: float | None = None
    criticality_level: str | None = None
    tech_stack: list[str] = Field(default_factory=list)


class ApplicableRegulation(_TolerantModel):
    """One entry from classification.yaml#applicable_regulations."""

    id: str  # "REG-GDPR"
    abbreviation: str  # "GDPR"
    applicable: bool
    obligated_party: str = ""  # "controller" / "manufacturer" / ""
    reason: str = ""


class ApplicabilityPredicates(_TolerantModel):
    """Filter 1 booleans (PHASE1_STRATEGY §Inputs MINIMAL).

    Derived deterministically from the set of applicable regulations:
      GDPR applicable  → processes_personal_data = True
      CRA applicable   → places_digital_products_eu = True
      NIS2 applicable  → nis2_sector = non-empty string
      DORA applicable  → dora_financial_entity = True
      AI_Act applicable → aiact_high_risk_system = True
    For regulations NOT applicable, the corresponding predicate is False /
    empty string. `eu_data_subjects_count` is read from classification.yaml
    or defaulted to 0.
    """

    processes_personal_data: bool = False
    places_digital_products_eu: bool = False
    dora_financial_entity: bool = False
    nis2_sector: str = ""
    aiact_high_risk_system: bool = False
    eu_data_subjects_count: int = 0


class DeclaredRegulation(_TolerantModel):
    """One entry from regulatory/applicability.yaml#applicable_regulations."""

    abbreviation: str  # "GDPR"


class BusinessGoal(_TolerantModel):
    """One business goal (BG-XX) from business_goals.yaml."""

    id: str
    description: str = ""
    priority: str | None = None  # HIGH / MEDIUM / LOW


class Stakeholder(_TolerantModel):
    """One stakeholder (SH-XX) from stakeholders.yaml."""

    id: str
    role: str = ""
    responsibilities: list[str] = Field(default_factory=list)


class ArchitectureFacts(_TolerantModel):
    """Aggregated architecture inventory.

    Each field is the raw YAML list from one architecture file. Pydantic
    tolerates schema variations across cases.
    """

    systems: list[dict[str, Any]] = Field(default_factory=list)
    auth_systems: list[dict[str, Any]] = Field(default_factory=list)
    cloud_services: list[dict[str, Any]] = Field(default_factory=list)
    data_flows: list[dict[str, Any]] = Field(default_factory=list)
    data_stores: list[dict[str, Any]] = Field(default_factory=list)


class RegulatoryFacts(_TolerantModel):
    """Regulatory facts from regulatory/applicability.yaml + classification.yaml.

    `obligated_party_per_reg` maps canonical reg name → obligated party
    (e.g. {"GDPR": "controller", "CRA": "manufacturer"}).
    `clause_count_per_reg` is the OPTIONAL clause-count summary from
    applicability.yaml (used by SP-C for parity checks).
    """

    applicable: list[str] = Field(default_factory=list)  # same as ctx.applicable_regs
    non_applicable: list[str] = Field(default_factory=list)
    obligated_party_per_reg: dict[str, str] = Field(default_factory=dict)
    applicability_rationale: dict[str, str] = Field(default_factory=dict)
    clause_count_per_reg: dict[str, int] = Field(default_factory=dict)


class CompanyProfile(_TolerantModel):
    """Top-level case context produced by CaseProfileLoader.

    Consumed by:
      - SP-B ApplicabilityContext (company + predicates + applicable_regs)
      - SP-C ClauseMappingContext (company + applicable_regs + clause counts)
      - Doc 04/04a/04b/04c/04d (company facts + stakeholders + goals + architecture)

    CORR-047: extended with 4 new fields:
      - implementation_readiness: 12 IR areas (Doc 04b capability matrix)
      - regulatory_classification: 5 enums (Doc 05/07 per-regulation state)
      - role_matrix: 5 regs × role (Doc 05 + Layer 3 analyses)
      - regulatory_interactions: Layer 3 scans (temporal/requirement/
        trigger conflicts + negative analyses)
    All 4 are Optional (None if the corresponding YAML is absent).
    """

    case_path: str
    company: CompanyFacts
    applicability_predicates: ApplicabilityPredicates
    applicable_regs: list[str] = Field(default_factory=list)  # computed
    declared_applicable_regs: list[str] = Field(default_factory=list)  # from YAML
    declaration_gaps: list[str] = Field(default_factory=list)  # diff
    architecture: ArchitectureFacts = ArchitectureFacts()
    regulatory: RegulatoryFacts = RegulatoryFacts()
    business_goals: list[BusinessGoal] = Field(default_factory=list)
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    # CORR-047: 4 new categories (Optional; None if YAML missing)
    implementation_readiness: Any | None = None
    regulatory_classification: Any | None = None
    role_matrix: Any | None = None
    regulatory_interactions: Any | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_predicates(
    applicable: list[str], abbrev_to_predicate: dict[str, str]
) -> ApplicabilityPredicates:
    """Build ApplicabilityPredicates from the set of applicable regulations.

    The mapping is hardcoded because the methodology prescribes a 1:1 link
    between applicable regulations and the 5 Filter 1 booleans (PHASE1_STRATEGY
    §Inputs MINIMAL).
    """
    applicable_set = set(applicable)
    return ApplicabilityPredicates(
        processes_personal_data="GDPR" in applicable_set,
        places_digital_products_eu="CRA" in applicable_set,
        dora_financial_entity="DORA" in applicable_set,
        nis2_sector="" if "NIS2" not in applicable_set else "Annex I/II",
        aiact_high_risk_system="AI_Act" in applicable_set,
        # abbrev_to_predicate arg is currently unused but reserved for future
        # extension (e.g. NIS2 sector name resolution).
        eu_data_subjects_count=0,
    )


def _symmetric_diff(a: list[str], b: list[str]) -> list[str]:
    """Sorted symmetric difference (a ^ b)."""
    return sorted(set(a) ^ set(b))


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class CaseProfileLoader:
    """Loads a case directory into a typed CompanyProfile.

    Reads from:
      cases/<case>/input/company/{classification,business_goals,stakeholders}.yaml
      cases/<case>/input/regulatory/applicability.yaml
      cases/<case>/input/architecture/{systems,auth_systems,cloud_services,data_flows,data_stores}.yaml
    """

    def __init__(self, case_path: Path | str) -> None:
        self.case_path = Path(case_path).resolve()
        if not self.case_path.exists():
            raise FileNotFoundError(f"case_path does not exist: {self.case_path}")
        self.input_dir = self.case_path / "input"
        if not self.input_dir.exists():
            raise FileNotFoundError(f"input/ directory missing under case_path: {self.input_dir}")
        logger.debug("CaseProfileLoader(case=%s)", self.case_path)

    # -- YAML helpers -----------------------------------------------------

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError(
                f"Expected YAML mapping at top level in {path}, got {type(data).__name__}"
            )
        return data

    @staticmethod
    def _read_yaml_list(path: Path, key: str) -> list[dict[str, Any]]:
        """Read a list[dict] under `key` from a YAML file. Tolerant of missing key."""
        if not path.exists():
            return []
        data = CaseProfileLoader._read_yaml(path)
        items = data.get(key, [])
        if not isinstance(items, list):
            raise ValueError(f"Expected list at {path}#{key}, got {type(items).__name__}")
        return items

    @staticmethod
    def _read_yaml_list_multi(
        path: Path,
        key_aliases: list[str],
    ) -> list[dict[str, Any]]:
        """CORR-046: read a list from a YAML file under one of several root keys.

        Different case YAMLs use different root-key conventions for what is
        semantically the same data:

          data_stores.yaml:  "data_stores:"  OR  "stores:"
          data_flows.yaml:   "data_flows:"   OR  "flows:"
          cloud_services.yaml: "cloud_services:"  OR  "services:"

        Pre-CORR-046 the loader hard-coded one variant (e.g. "data_stores")
        and the other variant was silently dropped — prompts received an
        empty list. This helper tries each alias in order and returns the
        first non-empty list found, logging WARNING when no alias matches.

        Args:
            path: Path to the YAML file.
            key_aliases: Ordered list of root keys to try. First non-empty
                list wins; empties are skipped (allow legacy keys that are
                explicitly empty to fall through to the next alias).

        Returns:
            The list found under the first matching alias; [] if the file
            is missing or no alias matches.
        """
        if not path.exists():
            logger.warning(
                "_read_yaml_list_multi: file does not exist: %s; aliases=%s",
                path, key_aliases,
            )
            return []
        try:
            data = CaseProfileLoader._read_yaml(path)
        except Exception as e:
            logger.warning(
                "_read_yaml_list_multi: failed to parse %s: %s; returning []",
                path, e,
            )
            return []
        for key in key_aliases:
            if key in data:
                value = data[key]
                if isinstance(value, list):
                    if not value:
                        logger.debug(
                            "_read_yaml_list_multi: key %r in %s is an empty list "
                            "(trying next alias if any)",
                            key, path,
                        )
                        # Don't return yet — try the next alias.
                        continue
                    return value
                logger.warning(
                    "_read_yaml_list_multi: key %r in %s is not a list (got %s); "
                    "skipping",
                    key, path, type(value).__name__,
                )
                continue
        logger.warning(
            "_read_yaml_list_multi: none of aliases %s found in %s; returning []",
            key_aliases, path,
        )
        return []

    # -- loaders ----------------------------------------------------------

    def _load_company(self) -> CompanyFacts:
        path = self.input_dir / "company" / "classification.yaml"
        raw = self._read_yaml(path)
        company_raw = raw.get("company")
        if not isinstance(company_raw, dict):
            raise ValueError(
                f"Expected 'company' key with mapping in {path}, got {type(company_raw).__name__}"
            )
        # CORR-046: tech_stack may be at TOP level (case 1 has it outside
        # the `company:` sub-dict) or inside the `company:` mapping. Accept
        # both. Pre-CORR-046 the loader only read `company_raw["tech_stack"]`
        # so the top-level variant was silently dropped.
        tech_stack_raw = raw.get("tech_stack", company_raw.get("tech_stack", []))
        if isinstance(tech_stack_raw, str):
            # Tolerate "AWS, Django, PostgreSQL" style
            tech_stack_raw = [s.strip() for s in tech_stack_raw.split(",") if s.strip()]
        if not tech_stack_raw:
            logger.warning(
                "_load_company: tech_stack missing in %s (neither top-level "
                "nor under `company:` block); company.tech_stack will be empty",
                path,
            )
        # Replace the (possibly missing) key so Pydantic sees the right value
        company_raw = {**company_raw, "tech_stack": tech_stack_raw}
        return CompanyFacts.model_validate(company_raw)

    def _load_applicable_regulations(self) -> list[ApplicableRegulation]:
        path = self.input_dir / "company" / "classification.yaml"
        raw = self._read_yaml(path)
        items = raw.get("applicable_regulations", [])
        return [ApplicableRegulation.model_validate(it) for it in items]

    def _load_business_goals(self) -> list[BusinessGoal]:
        path = self.input_dir / "company" / "business_goals.yaml"
        return [BusinessGoal.model_validate(it) for it in self._read_yaml_list(path, "goals")]

    def _load_stakeholders(self) -> list[Stakeholder]:
        path = self.input_dir / "company" / "stakeholders.yaml"
        return [Stakeholder.model_validate(it) for it in self._read_yaml_list(path, "stakeholders")]

    def _load_architecture(self) -> ArchitectureFacts:
        arch_dir = self.input_dir / "architecture"
        # CORR-046: case 1 YAMLs use 'stores' / 'flows' / 'services' as root
        # keys; case 2+ may use 'data_stores' / 'data_flows' / 'cloud_services'.
        # Accept both via _read_yaml_list_multi.
        data_stores = self._read_yaml_list_multi(
            arch_dir / "data_stores.yaml", ["data_stores", "stores"],
        )
        data_flows = self._read_yaml_list_multi(
            arch_dir / "data_flows.yaml", ["data_flows", "flows"],
        )
        cloud_services = self._read_yaml_list_multi(
            arch_dir / "cloud_services.yaml", ["cloud_services", "services"],
        )
        # systems / auth_systems: case 1 uses 'systems' / 'auth_systems'
        # (no alias needed for now, but pass via _read_yaml_list for
        # consistency).
        return ArchitectureFacts(
            systems=self._read_yaml_list(arch_dir / "systems.yaml", "systems"),
            auth_systems=self._read_yaml_list(arch_dir / "auth_systems.yaml", "auth_systems"),
            cloud_services=cloud_services,
            data_flows=data_flows,
            data_stores=data_stores,
        )

    def _load_regulatory(self) -> tuple[RegulatoryFacts, list[str], list[str]]:
        """Load regulatory/applicability.yaml → (RegulatoryFacts, applicable, non_applicable)."""
        path = self.input_dir / "regulatory" / "applicability.yaml"
        if not path.exists():
            logger.warning("regulatory/applicability.yaml missing at %s", path)
            return RegulatoryFacts(), [], []
        raw = self._read_yaml(path)
        applicable: list[str] = list(raw.get("applicable_regulations", []) or [])
        non_applicable: list[str] = list(raw.get("non_applicable_regulations", []) or [])
        rationale: dict[str, Any] = raw.get("applicability_rationale", {}) or {}
        clause_count: dict[str, Any] = raw.get("clause_count", {}) or {}
        # rationale and clause_count may have non-string values; coerce safely
        return (
            RegulatoryFacts(
                applicable=applicable,
                non_applicable=non_applicable,
                applicability_rationale={str(k): str(v) for k, v in rationale.items()},
                clause_count_per_reg={
                    str(k): int(v) for k, v in clause_count.items() if isinstance(v, int | float)
                },
            ),
            applicable,
            non_applicable,
        )

    # -- CORR-047: 4 new categories -------------------------------------

    def _load_implementation_readiness(self) -> Any:
        """CORR-047: load implementation_readiness.yaml → ImplementationReadiness.

        Tolerates missing file (WARNING + None) and parse errors
        (WARNING + None) so other categories can still load.
        """
        from aegis_phase1.v2.state import ImplementationReadiness

        path = self.input_dir / "company" / "implementation_readiness.yaml"
        if not path.exists():
            logger.warning(
                "_load_implementation_readiness: missing %s; "
                "implementation_readiness will be None (Doc 04b renders empty capability matrix)",
                path,
            )
            return None
        try:
            return ImplementationReadiness.model_validate(self._read_yaml(path))
        except Exception as e:
            logger.warning(
                "_load_implementation_readiness: failed to parse %s: %s; returning None",
                path, e,
            )
            return None

    def _load_regulatory_classification(self) -> Any:
        """CORR-047: load regulatory_classification.yaml → RegulatoryClassification."""
        from aegis_phase1.v2.state import RegulatoryClassification

        path = self.input_dir / "company" / "regulatory_classification.yaml"
        if not path.exists():
            logger.warning(
                "_load_regulatory_classification: missing %s; returning None",
                path,
            )
            return None
        try:
            return RegulatoryClassification.model_validate(self._read_yaml(path))
        except Exception as e:
            logger.warning(
                "_load_regulatory_classification: failed to parse %s: %s; returning None",
                path, e,
            )
            return None

    def _load_role_matrix(self) -> Any:
        """CORR-047: load role_matrix.yaml → RoleMatrix."""
        from aegis_phase1.v2.state import RoleMatrix

        path = self.input_dir / "company" / "role_matrix.yaml"
        if not path.exists():
            logger.warning("_load_role_matrix: missing %s; returning None", path)
            return None
        try:
            return RoleMatrix.model_validate(self._read_yaml(path))
        except Exception as e:
            logger.warning(
                "_load_role_matrix: failed to parse %s: %s; returning None", path, e,
            )
            return None

    def _load_regulatory_interactions(self) -> Any:
        """CORR-047: load interactions.yaml → RegulatoryInteractions (Layer 3 scans)."""
        from aegis_phase1.v2.state import RegulatoryInteractions

        path = self.input_dir / "regulatory" / "interactions.yaml"
        if not path.exists():
            logger.warning(
                "_load_regulatory_interactions: missing %s; returning None",
                path,
            )
            return None
        try:
            return RegulatoryInteractions.model_validate(self._read_yaml(path))
        except Exception as e:
            logger.warning(
                "_load_regulatory_interactions: failed to parse %s: %s; returning None",
                path, e,
            )
            return None

    # -- main entrypoint --------------------------------------------------

    @functools_cache  # noqa: B019  (intentional: case_path is the cache key)
    def load(self) -> CompanyProfile:
        """Load all case inputs and return a typed CompanyProfile.

        `functools.cache` keyed by `self` (each loader instance is fresh per
        call site, so the cache is effectively per-load — the goal here is
        just to make `load()` idempotent within one instance, not to share
        across instances).
        """
        company = self._load_company()
        applicable_regs_entries = self._load_applicable_regulations()
        computed_applicable: list[str] = sorted(
            e.abbreviation for e in applicable_regs_entries if e.applicable
        )

        regulatory_facts, declared_applicable, declared_non_applicable = self._load_regulatory()

        predicates = _derive_predicates(computed_applicable, {})

        # declaration_gaps: diff between declared and computed
        declaration_gaps = _symmetric_diff(declared_applicable, computed_applicable)

        # Build obligated_party_per_reg from classification.yaml entries
        obligated_party_per_reg: dict[str, str] = {
            e.abbreviation: e.obligated_party for e in applicable_regs_entries if e.obligated_party
        }
        regulatory_facts.obligated_party_per_reg = obligated_party_per_reg
        # If declared non_applicable is missing, derive from computed
        if not declared_non_applicable:
            all_regs = {"GDPR", "CRA", "NIS2", "DORA", "AI_Act"}
            declared_non_applicable = sorted(all_regs - set(computed_applicable))
        regulatory_facts.non_applicable = declared_non_applicable

        return CompanyProfile(
            case_path=str(self.case_path),
            company=company,
            applicability_predicates=predicates,
            applicable_regs=computed_applicable,
            declared_applicable_regs=declared_applicable,
            declaration_gaps=declaration_gaps,
            architecture=self._load_architecture(),
            regulatory=regulatory_facts,
            business_goals=self._load_business_goals(),
            stakeholders=self._load_stakeholders(),
            # CORR-047: 4 new categories (each WARNING-tolerant if YAML missing)
            implementation_readiness=self._load_implementation_readiness(),
            regulatory_classification=self._load_regulatory_classification(),
            role_matrix=self._load_role_matrix(),
            regulatory_interactions=self._load_regulatory_interactions(),
        )


__all__ = [
    "ApplicabilityPredicates",
    "ApplicableRegulation",
    "ArchitectureFacts",
    "BusinessGoal",
    "CaseProfileLoader",
    "CompanyProfile",
    "CompanyFacts",
    "DeclaredRegulation",
    "RegulatoryFacts",
    "Stakeholder",
]
