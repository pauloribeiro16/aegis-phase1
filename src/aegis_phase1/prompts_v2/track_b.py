"""TrackB - Deterministic tier assignment per proportionality_model.md section 5.

Layer 0 invariant: does NOT modify Layer 0 fit_criterion, HSO, or any
regulatory content. Only assigns a tier (MINIMAL/LIGHTWEIGHT/STANDARD/
RIGOROUS/DEFERRED) and 5 attributes per sub-domain.

Public API:
    TrackB.assign_tier(scale, inheritability, priority, fte=None) -> str
    TrackB.assign_all(scale, fte, per_subdomain_input) -> dict
    TrackB.summarize(profile) -> dict
"""

from __future__ import annotations

from collections import Counter
from typing import Any

# Decision-table constants (proportionality_model.md section 5)

_SCALE_RANK = {"MICRO": 0, "SMALL": 1, "MEDIUM": 2, "LARGE": 3, "MAX": 4}
_INHERIT_RANK = {"INHERITABLE": 0, "BUILD_REQUIRED": 1}
_TIER_RANK = {
    "MINIMAL": 0,
    "LIGHTWEIGHT": 1,
    "STANDARD": 2,
    "RIGOROUS": 3,
    "DEFERRED": -1,
}
_TIER_NAMES = {
    0: "MINIMAL",
    1: "LIGHTWEIGHT",
    2: "STANDARD",
    3: "RIGOROUS",
    -1: "DEFERRED",
}

# Section 5.1 MUST table indexed by (scale_rank, inherit_rank).
# Values are tier ranks (numeric, used for arithmetic in Section 5.2 drop-one-tier).
_MUST_TABLE: dict[tuple[int, int], int] = {
    (0, 0): 0,  # MICRO + INHERITABLE    -> MINIMAL
    (0, 1): 1,  # MICRO + BUILD_REQUIRED -> LIGHTWEIGHT
    (1, 0): 1,  # SMALL + INHERITABLE    -> LIGHTWEIGHT
    (1, 1): 2,  # SMALL + BUILD_REQUIRED -> STANDARD
    (2, 0): 1,  # MEDIUM + INHERITABLE   -> LIGHTWEIGHT
    (2, 1): 2,  # MEDIUM + BUILD_REQUIRED -> STANDARD
    (3, 0): 2,  # LARGE + INHERITABLE    -> STANDARD
    (3, 1): 3,  # LARGE + BUILD_REQUIRED -> RIGOROUS
    (4, 0): 2,  # MAX + INHERITABLE      -> STANDARD
    (4, 1): 3,  # MAX + BUILD_REQUIRED   -> RIGOROUS
}


class TrackB:
    """Deterministic tier assignment per proportionality_model.md section 5.

    The class is stateless and side-effect-free; instances are cheap to
    create and can be shared across threads. All decision logic is driven
    by the section 5.1 MUST table and the section 5.2 / 5.3 modifiers.
    """

    def assign_tier(
        self,
        scale: str,
        inheritability: str,
        priority: str,
        fte: float | None = None,
    ) -> str:
        """Assign a single tier given scale + inheritability + priority.

        Algorithm (section 5.1 -> 5.2 -> 5.3):
          1. Look up base tier in section 5.1 MUST table.
          2. If priority is SHOULD or COULD:
             a. If scale == MICRO and fte is not None and fte <= 1.0
                -> DEFERRED (proportional_priority = P3-defer).
             b. Otherwise -> drop one tier (rank - 1, floored at MINIMAL=0).
          3. Apply section 5.3 floor rule: MUST never below MINIMAL (rank 0).
          4. Return tier name.

        Args:
            scale: one of MICRO | SMALL | MEDIUM | LARGE | MAX.
            inheritability: one of INHERITABLE | BUILD_REQUIRED.
            priority: one of MUST | SHOULD | COULD.
            fte: optional security_FTE; only consulted for the section 5.2
                MICRO + low-FTE DEFERRED path.

        Returns:
            Tier name (MINIMAL | LIGHTWEIGHT | STANDARD | RIGOROUS | DEFERRED).

        Raises:
            ValueError: on invalid scale, inheritability, or priority.
        """
        if scale not in _SCALE_RANK:
            raise ValueError(f"Invalid scale: {scale!r}")
        if inheritability not in _INHERIT_RANK:
            raise ValueError(f"Invalid inheritability: {inheritability!r}")
        if priority not in ("MUST", "SHOULD", "COULD"):
            raise ValueError(f"Invalid priority: {priority!r}")

        s_rank = _SCALE_RANK[scale]
        i_rank = _INHERIT_RANK[inheritability]
        base_tier_rank = _MUST_TABLE[(s_rank, i_rank)]

        if priority in ("SHOULD", "COULD"):
            # Section 5.2 special case: MICRO + low FTE -> DEFERRED.
            if scale == "MICRO" and fte is not None and fte <= 1.0:
                return "DEFERRED"
            # Otherwise drop one tier. Section 5.3 floor: SHOULD/COULD can
            # drop down to MINIMAL (= rank 0) but no further.
            return _TIER_NAMES[max(base_tier_rank - 1, 0)]

        # Section 5.3 floor rule: MUST never below MINIMAL (rank 0).
        # The table already enforces this - every (S, I) MUST rank is >= 0 -
        # so we just return the MUST base tier.
        return _TIER_NAMES[max(base_tier_rank, 0)]

    def assign_all(
        self,
        scale: str,
        fte: float,
        per_subdomain_input: dict[str, dict[str, str]],
    ) -> dict[str, dict[str, Any]]:
        """Assign a tier per sub-domain.

        Args:
            scale: company scale (MICRO | SMALL | MEDIUM | LARGE | MAX).
            fte: security_FTE used for the section 5.2 MICRO + low-FTE DEFERRED path.
            per_subdomain_input: mapping sub_domain_id -> {inheritability,
                priority}. Missing keys default to BUILD_REQUIRED / MUST.

        Returns:
            Mapping sub_domain_id -> {tier, satisfaction_pattern, evidence_depth,
                verification_method, ownership, example_controls}.
                The five attributes are derived per proportionality_model.md section 6.
        """
        if scale not in _SCALE_RANK:
            raise ValueError(f"Invalid scale: {scale!r}")

        out: dict[str, dict[str, Any]] = {}
        for sd_id, inputs in per_subdomain_input.items():
            inheritability = inputs.get("inheritability", "BUILD_REQUIRED")
            priority = inputs.get("priority", "MUST")
            tier = self.assign_tier(scale, inheritability, priority, fte=fte)
            attrs = self._tier_attributes(tier, inheritability)
            out[sd_id] = {"tier": tier, **attrs}
        return out

    @staticmethod
    def _tier_attributes(tier: str, inheritability: str) -> dict[str, Any]:
        """Return the five operational attributes per proportionality_model.md section 6.

        For non-DEFERRED tiers, the attributes are deterministic and
        independent of the specific inheritability value (the section 6
        table does not branch on it). For DEFERRED, attributes are "-"
        placeholders so they remain non-empty strings (per eval gate criteria).
        """
        attrs_by_tier: dict[str, dict[str, Any]] = {
            "MINIMAL": {
                "satisfaction_pattern": "INHERIT",
                "evidence_depth": (
                    "Supplier attestation on file (SOC 2 / ISO 27001) + "
                    "1-page internal statement"
                ),
                "verification_method": ["INSPECT"],
                "ownership": "Supplier (company = validator)",
                "example_controls": [
                    "AWS KMS (inherited)",
                    "Firebase Auth (inherited)",
                ],
            },
            "LIGHTWEIGHT": {
                "satisfaction_pattern": "BUY_MANAGED",
                "evidence_depth": (
                    "Managed-service config documented + annual review; "
                    "no dedicated in-house program"
                ),
                "verification_method": ["DEMONSTRATE", "INSPECT"],
                "ownership": "Shared (supplier infrastructure + company configuration)",
                "example_controls": [
                    "Managed service config",
                    "Annual review notes",
                ],
            },
            "STANDARD": {
                "satisfaction_pattern": "BUILD_LIGHT",
                "evidence_depth": ("Dedicated tooling + documented procedure + quarterly test"),
                "verification_method": ["TEST", "DEMONSTRATE"],
                "ownership": "Company-owned with a named owner",
                "example_controls": [
                    "Dedicated tooling",
                    "Quarterly tests",
                    "Documented procedures",
                ],
            },
            "RIGOROUS": {
                "satisfaction_pattern": "BUILD_FULL",
                "evidence_depth": (
                    "Enterprise tooling + SOC + continuous audit + " "external certification"
                ),
                "verification_method": ["TEST", "ANALYZE"],
                "ownership": "Company-owned, externally audited",
                "example_controls": [
                    "Enterprise SIEM",
                    "External pen test",
                    "ISO 27001 certified ISMS",
                ],
            },
            "DEFERRED": {
                "satisfaction_pattern": "-",
                "evidence_depth": "-",
                "verification_method": ["-"],
                "ownership": "-",
                "example_controls": ["-"],
            },
        }
        return attrs_by_tier.get(tier, attrs_by_tier["DEFERRED"])

    def summarize(self, profile: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Return summary statistics for a profile.

        Computes the tier distribution and active/deferred counts. Used by
        tests and validation scripts to verify that a case profile matches
        the expected proportionality_model.md section 5 distribution.

        Args:
            profile: mapping sub_domain_id -> dict containing at least
                a "tier" key (the format returned by assign_all).

        Returns:
            Dict with keys:
                total_sub_domains (int): number of entries in profile.
                tier_distribution (dict[str, int]): tier name -> count.
                active_sub_domains (int): count of non-DEFERRED tiers.
                deferred_count (int): count of DEFERRED tiers.
        """
        tiers = [entry.get("tier") for entry in profile.values()]
        return {
            "total_sub_domains": len(profile),
            "tier_distribution": dict(Counter(tiers)),
            "active_sub_domains": sum(1 for t in tiers if t != "DEFERRED"),
            "deferred_count": tiers.count("DEFERRED"),
        }
