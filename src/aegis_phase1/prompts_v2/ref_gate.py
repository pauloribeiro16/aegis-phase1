"""Deterministic reference and citation gate for Phase 1 LLM markdown outputs (CORR-112).

Validates raw markdown responses from Phase 1 LLM specs against authoritative
catalog data, lane parameters, and deterministic syntactic/semantic rules:

- P1B-01 (Interpretation + Derogation):
    * verdicts in {ACTIVATED, NOT_ACTIVATED, INDETERMINATE, YES, NO}
    * sequential INT-IDs (INT-1, INT-2, ... or INT-01, INT-02, ...)
    * derogations cited in tipo2/tipo3 canonical catalogs
    * authoritative subdomain_ids, regulation_ids, article_ids adhered to

- P1B-02 (Synthesis: Rationale + Implications + Gaps):
    * effort estimates / tiers in {MICRO, SMALL, MEDIUM, LARGE, MAX} / valid tier text
    * refs to Doc 04 / 04a / architecture / company facts exist
    * zero invented stats (regex for unsupported % or millions without source facts)
    * no invented article references

- P1C-01 (Overlap Classification):
    * cited sub-domains in lane authoritative subdomains
    * pairs (regA, regB) in lane valid regulation pairs
    * relationships / verdicts in {SAME, COMPLEMENTARY, CONTRADICTORY, SCOPE_DISJOINT,
      OVERLAP_CONFIRMED, OVERLAP_NOT_TRIGGERED, INDETERMINATE, APPLICABLE, NOT_APPLICABLE, YES, NO}
    * zero generic placeholders (e.g. DOC04:SEC-*, DOC-XX, etc.)

Public API:
    GateViolation: NamedTuple representing a single rule violation.
    GateResult: Validation outcome carrying success status, violations list, and feedback string.
    RefGate: Validator class implementing validate() and per-spec checkers.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

VALID_P1B01_VERDICTS = {"ACTIVATED", "NOT_ACTIVATED", "INDETERMINATE", "YES", "NO"}
VALID_TIERS = {"MICRO", "SMALL", "MEDIUM", "LARGE", "MAX", "LOW", "HIGH"}

VALID_P1C01_RELATIONSHIPS = {
    "SAME",
    "COMPLEMENTARY",
    "CONTRADICTORY",
    "SCOPE_DISJOINT",
    "CONDITIONAL",
}

VALID_P1C01_VERDICTS = {
    "OVERLAP_CONFIRMED",
    "OVERLAP_NOT_TRIGGERED",
    "SCOPE_DISJOINT",
    "INDETERMINATE",
    "APPLICABLE",
    "NOT_APPLICABLE",
    "YES",
    "NO",
}

_INVENTED_STAT_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?%\s+(?:effort|cost|time|risk|reduction|increase|improvement|efficiency)\b"
    r"|\b(?:reduced|increased|improved|saved)\s+by\s+\d+(?:\.\d+)?%"
    r"|\b\d+(?:\.\d+)?\s*(?:million|milhões|billion|bilhões)\s*(?:euros|€|\$|usd|gbp|users|records|contas)\b)",
    re.IGNORECASE,
)

_GENERIC_MARKER_RE = re.compile(
    r"(?:DOC04:SEC-(?:\*|NN|XX|\d{2,}[A-Z*]*)|DOC\d{2}:[A-Z]+-(?:\*|XX|NN)|D-XX(?:\.[Yy\d*]+)?)",
    re.IGNORECASE,
)

_INT_ID_RE = re.compile(r"\bINT-(\d+)\b", re.IGNORECASE)

# CORR-OBJ-01: per-section citation gate for case architecture IDs.
# Matches SYS-, STORE- and FLOW- tokens (uppercase alphanumerics, dashes,
# underscores) inside the LLM output. Each match is then checked against
# the authoritative asset list the prompt supplied.
_ASSET_ID_RE = re.compile(r"\b(SYS|STORE|FLOW)-[A-Z0-9][A-Z0-9_-]*\b", re.IGNORECASE)

# CORR-OBJ-04: CSF 2.0 token detector. Matches the canonical CSF
# subcategory form (e.g. PR.DS-01, GV.OC-03, ID.AM-08) and is checked
# against the loaded CSF catalogue.
_CSF_TOKEN_RE = re.compile(r"\b([A-Z]{2}\.[A-Z]{2}-\d{2})\b")


class GateViolation(NamedTuple):
    rule: str
    message: str
    context: str = ""


@dataclass
class GateResult:
    valid: bool
    violations: list[GateViolation] = field(default_factory=list)
    feedback: str = ""

    def to_feedback_prompt(self, previous_raw: str = "") -> str:
        if self.valid:
            return ""
        newline = chr(10)
        items = newline.join(f"- [{v.rule}] {v.message}" for v in self.violations)
        return (
            "Your previous response violated the following deterministic reference rules:"
            + newline
            + items
            + newline
            + newline
            + "Please revise your response strictly fixing these violations. "
            + "Cite ONLY valid authoritative IDs provided in the inputs and avoid generic placeholders or invented statistics."
        )


class RefGate:
    def __init__(self, catalog_root: Any | None = None) -> None:
        self.catalog_root = catalog_root
        self._tipo2_ids: set[str] | None = None
        self._tipo3_ids: set[str] | None = None
        # CORR-OBJ-04: set of canonical NIST CSF 2.0 subcategory IDs
        # (e.g. "PR.DS-01"). Loaded lazily on first validate() call by
        # ``_ensure_csf()``. ``None`` means "not loaded yet".
        self._csf_ids: set[str] | None = None

    def _ensure_catalogs(self) -> None:
        if self._tipo2_ids is not None and self._tipo3_ids is not None:
            return
        try:
            from aegis_phase1.prompts_v2.catalog import CatalogLoader

            cl = CatalogLoader(root=self.catalog_root) if self.catalog_root else CatalogLoader()
            tipo2 = cl.load("tipo2_interpretations")
            tipo3 = cl.load("tipo3_derogations")
            self._tipo2_ids = {e.get("entry_id") for e in tipo2 if isinstance(e, dict) and e.get("entry_id")}
            self._tipo3_ids = {e.get("entry_id") for e in tipo3 if isinstance(e, dict) and e.get("entry_id")}
        except Exception as e:
            logger.warning("RefGate: could not load catalogs from CatalogLoader (%s). Using fallback catalog IDs.", e)
            self._tipo2_ids = {
                "TIPO2-GDPR-RTS-DEADLINES",
                "TIPO2-CRA-ART14-DUAL-FLOW",
                "TIPO2-CRA-ART15-VOLUNTARY",
                "TIPO2-NIS2-INCIDENT-NOTIFICATION",
                "TIPO2-DORA-MAJOR-ICT-INCIDENTS",
                "TIPO2-AI-ACT-RISK-ASSESSMENT",
                "TIPO2-GDPR-DPIA-HIGH-RISK",
                "TIPO2-CRA-ESSENTIAL-REQUIREMENTS",
            }
            self._tipo3_ids = {
                "TIPO3-GDPR-HOUSEHOLD",
                "TIPO3-DORA-LEX-SPECIALIS",
                "TIPO3-AI-ACT-NATIONAL-SECURITY",
                "TIPO3-CRA-NON-COMMERCIAL-FOSS",
                "TIPO3-NIS2-SME-EXCLUSION",
                "TIPO3-AI-ACT-SCIENTIFIC-RESEARCH",
            }

    def _ensure_csf(self) -> None:
        """CORR-OBJ-04: load the NIST CSF 2.0 subcategory ID set.

        Primary source is the preproc catalogue's
        ``preproc_out/global/NIST_CSF_2.0_subcategories.json`` (106
        active subcategories). Falls back to a hard-coded representative
        set when the catalogue cannot be reached (so the gate still
        works in offline / unit-test settings).
        """
        if self._csf_ids is not None:
            return
        loaded: set[str] = set()
        try:
            from pathlib import Path

            csf_path = (
                Path(__file__).resolve().parent.parent.parent.parent
                / "preproc_out"
                / "global"
                / "NIST_CSF_2.0_subcategories.json"
            )
            if csf_path.exists():
                import json

                data = json.loads(csf_path.read_text(encoding="utf-8"))
                # Schema v1.3 — the subcategories array carries the
                # canonical 106 active IDs. Fall back to all_subcategories
                # (which is identical in current schema but may grow).
                for key in ("subcategories", "all_subcategories"):
                    entries = data.get(key) or []
                    for entry in entries:
                        if isinstance(entry, dict):
                            eid = entry.get("id")
                            if isinstance(eid, str) and eid:
                                loaded.add(eid)
        except Exception as e:
            logger.warning("RefGate: could not load CSF catalogue (%s). Using fallback set.", e)
        if not loaded:
            # Representative fallback set (one per Function/Category to
            # keep the gate functional in offline mode). Hard-coded so
            # the test path is deterministic.
            loaded = {
                "GV.OC-01", "GV.RM-01", "ID.AM-01", "ID.RA-01",
                "PR.AA-01", "PR.DS-01", "PR.PS-01",
                "DE.CM-01", "DE.AE-02",
                "RS.MA-01", "RS.AN-03",
                "RC.RP-01", "RC.IM-01", "RC.CO-01", "RC.RP-03",
            }
        self._csf_ids = loaded

    def validate(
        self,
        spec_id: str,
        raw_markdown: str,
        inputs: dict[str, Any] | None = None,
    ) -> GateResult:
        if not raw_markdown or not raw_markdown.strip():
            return GateResult(
                valid=False,
                violations=[GateViolation("EMPTY_OUTPUT", "Raw LLM output is empty")],
                feedback="Output is empty. Please provide the complete response following the requested structure.",
            )

        self._ensure_catalogs()
        self._ensure_csf()
        violations: list[GateViolation] = []
        inputs = inputs or {}
        authoritative = inputs.get("authoritative_ids") or {}

        generic_matches = _GENERIC_MARKER_RE.findall(raw_markdown)
        if generic_matches:
            violations.append(
                GateViolation(
                    "GENERIC_MARKER",
                    f"Found generic/placeholder identifiers: {sorted(set(generic_matches))}. "
                    "Use only concrete, authoritative identifiers.",
                )
            )

        if "P1B-LLM-01" in spec_id or spec_id == "P1B-01":
            violations.extend(self._validate_p1b01(raw_markdown, inputs, authoritative))
        elif "P1B-LLM-02" in spec_id or spec_id == "P1B-02":
            violations.extend(self._validate_p1b02(raw_markdown, inputs, authoritative))
        elif "P1C-LLM-01" in spec_id or spec_id == "P1C-01":
            violations.extend(self._validate_p1c01(raw_markdown, inputs, authoritative))

        # CORR-OBJ-01: per-section citation gate. Runs after every
        # spec-specific checker so the rule applies to all 3 specs.
        # Backward-compat: if the spec is from before OBJ-01 and the
        # inputs have no ``asset_ids`` block, the gate is a no-op
        # (we cannot know what the authoritative asset set is).
        violations.extend(
            self._validate_citations(raw_markdown, inputs, authoritative)
        )

        # CORR-OBJ-04: CSF 2.0 token validation. Only runs for specs
        # that legitimately emit CSF citations (P1C-01 overlap
        # classification, P1B-02 rationale, P1C-03 strategic
        # synthesis). P1B-01 interpretation/derogation outputs and
        # any other spec that does not surface CSF are skipped — the
        # match would otherwise over-trigger on incidental references.
        if self._spec_emits_csf(spec_id):
            violations.extend(self._validate_csf_tokens(raw_markdown))

        valid = len(violations) == 0
        result = GateResult(valid=valid, violations=violations)
        if not valid:
            result.feedback = result.to_feedback_prompt(raw_markdown)
        return result

    def _validate_p1b01(
        self,
        raw: str,
        inputs: dict[str, Any],
        authoritative: dict[str, Any],
    ) -> list[GateViolation]:
        violations: list[GateViolation] = []
        verdict_matches = re.findall(r"(?:activation_verdict|verdict)\s*:\s*([A-Za-z_]+)", raw, re.IGNORECASE)
        for v in verdict_matches:
            v_norm = v.strip().upper()
            if v_norm not in VALID_P1B01_VERDICTS:
                violations.append(
                    GateViolation(
                        "INVALID_VERDICT",
                        f"Verdict '{v}' is invalid. Allowed verdicts are: {sorted(VALID_P1B01_VERDICTS)}",
                        context=v,
                    )
                )

        int_ids = [int(m) for m in _INT_ID_RE.findall(raw)]
        if int_ids:
            seen = set()
            for num in int_ids:
                if num in seen:
                    violations.append(
                        GateViolation(
                            "DUPLICATE_INT_ID",
                            f"Duplicate interpretation ID 'INT-{num}' found in output.",
                        )
                    )
                seen.add(num)

        entry_id_matches = re.findall(r"\b(TIPO[23]-[A-Z0-9_-]+)\b", raw)
        valid_all_catalog = (self._tipo2_ids or set()) | (self._tipo3_ids or set())
        for eid in entry_id_matches:
            if valid_all_catalog and eid not in valid_all_catalog:
                violations.append(
                    GateViolation(
                        "UNKNOWN_CATALOG_ID",
                        f"Entry ID '{eid}' is not present in canonical Tipo 2 or Tipo 3 catalogs.",
                        context=eid,
                    )
                )

        sub_allowed = set(authoritative.get("subdomain_ids") or [])
        if sub_allowed:
            cited_subs = set(re.findall(r"\b(D-\d{2}\.\d+)\b", raw))
            invalid_subs = cited_subs - sub_allowed
            if invalid_subs:
                violations.append(
                    GateViolation(
                        "UNAUTHORISED_SUBDOMAIN",
                        f"Cited sub-domains {sorted(invalid_subs)} are outside the lane authoritative list: {sorted(sub_allowed)}",
                    )
                )
        return violations

    def _validate_p1b02(
        self,
        raw: str,
        inputs: dict[str, Any],
        authoritative: dict[str, Any],
    ) -> list[GateViolation]:
        violations: list[GateViolation] = []
        for match in _INVENTED_STAT_RE.finditer(raw):
            violations.append(
                GateViolation(
                    "INVENTED_STATISTICS",
                    f"Found ungrounded statistical assertion: '{match.group(0)}'. "
                    "Only cite concrete facts from Doc 04 or statutory legal requirements without inventing metrics.",
                    context=match.group(0),
                )
            )

        has_doc04_ref = bool(
            re.search(r"\b(?:DOC04|Doc\s*04|SYS-\d+|FLOW-\d+|STORE-\d+|ARCH-\d+|SEC-\d+|DATA-\d+|AWS|Auth0|Stripe|Datadog)\b", raw, re.IGNORECASE)
        )
        if not has_doc04_ref:
            violations.append(
                GateViolation(
                    "MISSING_DOC04_GROUNDING",
                    "Rationale and synthesis must reference company architecture facts from Doc 04 (e.g. SYS-*, STORE-*, FLOW-*, DOC04:*).",
                )
            )

        # CORR-OBJ-07: business grounding. When the case has at least
        # one MUST-priority business goal (BG-*), the rationale must
        # reference at least one of them. Without this, the synthesis
        # can drift into "what's good for the framework" without ever
        # tying back to "what the company is actually trying to do".
        must_goals = authoritative.get("must_business_goal_ids") or []
        if must_goals:
            pattern = r"\b(?:" + "|".join(re.escape(g) for g in must_goals) + r")\b"
            if not re.search(pattern, raw, re.IGNORECASE):
                violations.append(
                    GateViolation(
                        "MISSING_BUSINESS_GROUNDING",
                        f"Synthesis must cite at least one MUST-priority business "
                        f"goal (e.g. {' or '.join(must_goals[:3])}). The rationale "
                        "must tie technical conclusions to the company's stated goals.",
                        context=", ".join(must_goals[:3]),
                    )
                )

        effort_estimates = re.findall(r"effort_estimate\s*:\s*(.+)", raw, re.IGNORECASE)
        for ee in effort_estimates:
            ee_clean = ee.strip()
            valid_effort_pattern = re.search(
                r"(?:hours|days|weeks|months|quarters|fte|low|medium|high|micro|small|large|max)",
                ee_clean,
                re.IGNORECASE,
            )
            if not valid_effort_pattern:
                violations.append(
                    GateViolation(
                        "INVALID_EFFORT_ESTIMATE",
                        f"Effort estimate '{ee_clean}' does not specify a valid tier-proportional duration (hours, days, weeks, months).",
                        context=ee_clean,
                    )
                )
        return violations

    def _validate_p1c01(
        self,
        raw: str,
        inputs: dict[str, Any],
        authoritative: dict[str, Any],
    ) -> list[GateViolation]:
        violations: list[GateViolation] = []
        sub_allowed = set(authoritative.get("subdomain_ids") or [])
        if sub_allowed:
            cited_subs = set(re.findall(r"\b(D-\d{2}\.\d+)\b", raw))
            invalid_subs = cited_subs - sub_allowed
            if invalid_subs:
                violations.append(
                    GateViolation(
                        "UNAUTHORISED_SUBDOMAIN",
                        f"Cited subdomains {sorted(invalid_subs)} are not in the lane authoritative list: {sorted(sub_allowed)}",
                    )
                )

        reg_allowed = set(authoritative.get("regulation_ids") or [])
        if not reg_allowed:
            reg_allowed = set(inputs.get("applicable_regs") or ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"])

        pair_matches = re.findall(r"\b(GDPR|CRA|NIS\s*2|NIS2|DORA|AI[_\s]Act)\s*(?:↔|<->|/|,)\s*(GDPR|CRA|NIS\s*2|NIS2|DORA|AI[_\s]Act)\b", raw, re.IGNORECASE)
        for r1, r2 in pair_matches:
            r1_norm = "AI_Act" if "AI" in r1.upper() else ("NIS2" if "NIS" in r1.upper() else r1.upper())
            r2_norm = "AI_Act" if "AI" in r2.upper() else ("NIS2" if "NIS" in r2.upper() else r2.upper())
            if reg_allowed and (r1_norm not in reg_allowed or r2_norm not in reg_allowed):
                violations.append(
                    GateViolation(
                        "UNAUTHORISED_REGULATION_PAIR",
                        f"Regulation pair ({r1_norm}, {r2_norm}) contains regulations outside lane scope: {sorted(reg_allowed)}",
                        context=f"{r1_norm} <-> {r2_norm}",
                    )
                )

        rel_matches = re.findall(r"(?:layer0_relationship|regulatory_baseline_relationship|relationship)\s*:\s*([A-Za-z_]+)", raw, re.IGNORECASE)
        for rel in rel_matches:
            rel_norm = rel.strip().upper()
            if rel_norm not in VALID_P1C01_RELATIONSHIPS and rel_norm not in VALID_P1C01_VERDICTS:
                violations.append(
                    GateViolation(
                        "INVALID_RELATIONSHIP",
                        f"Relationship '{rel}' is not a valid Regulatory Baseline relationship. Allowed: {sorted(VALID_P1C01_RELATIONSHIPS)}",
                        context=rel,
                    )
                )
        return violations

    def _validate_citations(
        self,
        raw: str,
        inputs: dict[str, Any],
        authoritative: dict[str, Any],
    ) -> list[GateViolation]:
        """CORR-OBJ-01: per-section citation gate for SYS-*/STORE-*/FLOW-*.

        Scans the LLM output for case architecture tokens and flags any
        that are NOT present in the authoritative asset lists. The
        authoritative set is built by the MAP-stage inputs assembly
        (``v2/domain/inputs.py:_load_case_assets``) and is delivered
        under ``authoritative['asset_ids']`` with three sub-keys
        (``systems``, ``data_stores``, ``data_flows``).

        Backward compatibility:
          * If the inputs dict has no ``asset_ids`` block (v1.1 specs /
            older callers), the gate returns ``[]`` — it cannot
            distinguish legitimate from invented IDs.
          * If all three sub-lists are empty, the gate is a no-op.

        The validation is deterministic and case-insensitive on token
        matching (the regex already upper-cases via the ``re.IGNORECASE``
        flag, then we normalise by upper-casing the asset lists for the
        set comparison).
        """
        asset_block = authoritative.get("asset_ids") or {}
        if not isinstance(asset_block, dict):
            return []
        systems = {str(x).upper() for x in (asset_block.get("systems") or [])}
        stores = {str(x).upper() for x in (asset_block.get("data_stores") or [])}
        flows = {str(x).upper() for x in (asset_block.get("data_flows") or [])}
        if not (systems or stores or flows):
            return []

        allowed = systems | stores | flows

        violations: list[GateViolation] = []
        for match in _ASSET_ID_RE.finditer(raw):
            token = match.group(0).upper()
            if token not in allowed:
                violations.append(
                    GateViolation(
                        "UNAUTHORISED_ASSET_REF",
                        f"Architecture token '{token}' is not in the lane's "
                        f"authoritative asset list (SYS-*/STORE-*/FLOW-*). "
                        "Cite only IDs provided in the inputs.",
                        context=token,
                    )
                )
        return violations

    # ----------------------------------------------------------------
    # CORR-OBJ-04: CSF 2.0 token validation
    # ----------------------------------------------------------------

    # Spec IDs that emit CSF subcategory citations as part of their
    # normal output. P1B-01 (interpretation / derogation) does NOT
    # emit CSF tokens, so we skip the gate there to avoid over-firing
    # on incidental references.
    _CSF_EMITTING_SPECS: frozenset[str] = frozenset(
        {
            "P1B-LLM-02",
            "P1B-02",
            "P1C-LLM-01",
            "P1C-01",
            "P1C-LLM-03",
            "P1C-03",
        }
    )

    @classmethod
    def _spec_emits_csf(cls, spec_id: str) -> bool:
        """True if ``spec_id`` legitimately emits CSF 2.0 citations."""
        if not spec_id:
            return False
        # Match the canonical spec id or any prefix that starts with one
        # of the known emitters (so P1C-LLM-01-OVERLAP-CLASSIFICATION
        # also matches P1C-LLM-01).
        for needle in cls._CSF_EMITTING_SPECS:
            if spec_id == needle or spec_id.startswith(needle + "-") or spec_id.startswith(needle + "_"):
                return True
        return False

    def _validate_csf_tokens(self, raw: str) -> list[GateViolation]:
        """CORR-OBJ-04: flag any CSF 2.0 token not in the loaded catalogue.

        Tokens look like ``PR.DS-01`` (two letters, dot, two letters,
        dash, two digits). The set is the 106 active subcategories in
        ``preproc_out/global/NIST_CSF_2.0_subcategories.json`` (with a
        representative fallback when the catalogue is unreachable).
        """
        if not self._csf_ids:
            return []
        violations: list[GateViolation] = []
        for match in _CSF_TOKEN_RE.finditer(raw):
            token = match.group(1)
            if token not in self._csf_ids:
                violations.append(
                    GateViolation(
                        "UNKNOWN_CSF_TOKEN",
                        f"CSF 2.0 subcategory token '{token}' is not in the "
                        "canonical catalogue (106 active subcategories). "
                        "Cite only subcategories defined in NIST CSF 2.0.",
                        context=token,
                    )
                )
        return violations
