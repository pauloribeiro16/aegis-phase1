"""KG-eval context packet generator (CORR-113).

Generates a deterministic JSON context packet for one (case, subdomain) tuple from the
same source files the real Neo4j KG ETL would consume. The packet mirrors the shape
of the relevant KG entities (`:System`, `:DataStore`, `:DataFlow`, `:RegulatoryClause`,
`:RegulatoryPair`, `:AmbiguityDisposition`, `:ProportionalityEntry`,
`:RegulatoryInteraction`) so the T1 evaluator can run an A/B comparison without the
KG itself existing.

Public API:
    generate_packet(case_path, subdomain_id, preproc_root) -> dict
    main() -> 0/1 (CLI entry point)

CLI:
    python -m scripts.kg_eval.generate_context_packets \
        --case cases/case1-tinytask --subdomain D-01.1 [--output PATH]

Writes the packet to ``--output`` (default: ``output/kg_eval/<case>/<subdomain>.json``)
plus a sibling ``<basename>.sha256`` containing the hex digest of the packet bytes.

Stdlib only — keeps the harness cheap and avoids coupling to project dependencies
beyond ``PyYAML`` (already a project dep).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# Project root = parent of scripts/. Used to resolve case_path and preproc_root when
# the caller passes a workspace-relative path.
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent

logger = logging.getLogger(__name__)

# Top-level canonical regulations (per NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC §2.1).
# Five nodes; matches the closed vocabulary used by the KG contract (KG-09).
CANONICAL_REGULATIONS = ("GDPR", "CRA", "NIS2", "DORA", "AI_Act")

# Subdomain ID regex (closed vocabulary). Mirrors `ref_gate.py:_validate_p1b01`.
_SUBDOMAIN_ID_RE = re.compile(r"^D-\d{2}\.\d+$")

# Case architecture YAML aliases — same convention as
# `src/aegis_phase1/v2/domain/inputs.py:_ASSET_KEY_ALIASES`.
_ASSET_KEY_ALIASES: dict[str, list[str]] = {
    "systems": ["systems"],
    "data_stores": ["data_stores", "stores"],
    "data_flows": ["data_flows", "flows"],
    "auth_systems": ["auth_systems"],
    "cloud_services": ["cloud_services"],
    "data_subjects": ["data_subjects"],
}

# Tier closed vocabulary (mirrors ProportionalityEntry.tier in the spec).
_TIER_ENUM = frozenset(
    {"MINIMAL", "LIGHTWEIGHT", "STANDARD", "RIGOROUS", "DEFERRED"}
)

# Scale closed vocabulary (mirrors Enterprise.scale in the spec).
_SCALE_ENUM = frozenset({"MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"})


# ─── Pure helpers ─────────────────────────────────────────────────────


def _read_yaml_list(path: Path, key_aliases: list[str]) -> list[dict[str, Any]]:
    """Read a list[dict] from a YAML file under one of several root keys.

    Tolerant of missing files (returns ``[]``) and parse errors (logs WARNING
    and returns ``[]``). Mirrors the safety policy of `inputs.py` so the
    packet generator can never crash a run on malformed source data.
    """
    if not path.exists():
        logger.debug("_read_yaml_list: missing %s; returning []", path)
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("_read_yaml_list: failed to parse %s: %s; returning []", path, exc)
        return []
    if not isinstance(raw, dict):
        logger.debug(
            "_read_yaml_list: top-level YAML at %s is not a dict (got %s); returning []",
            path,
            type(raw).__name__,
        )
        return []
    for alias in key_aliases:
        if alias in raw and isinstance(raw[alias], list):
            return [item for item in raw[alias] if isinstance(item, dict)]
    logger.debug(
        "_read_yaml_list: none of aliases %s found in %s; returning []",
        key_aliases, path,
    )
    return []


def _read_yaml_doc(path: Path) -> dict[str, Any]:
    """Read a YAML document (single dict) tolerant of missing/parse errors.

    Returns ``{}`` on missing file or parse error. Used for the company
    classification YAML which is a single dict, not a list of dicts.
    """
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("_read_yaml_doc: failed to parse %s: %s; returning {}", path, exc)
        return {}
    return raw if isinstance(raw, dict) else {}


def _project_company_context(classification: dict[str, Any]) -> dict[str, Any]:
    """Project the company classification YAML into the company_context shape.

    Mirrors `inputs.py:_project_company_context` (the Pydantic path). For the
    packet we only need the 4 fields the T1 prompts require:
    `company_name`, `scale`, `employees`. ``applicable_regs`` is filled
    separately from ``applicability.yaml`` (NOT from this classification doc).
    """
    company = classification.get("company") or {}
    return {
        "company_name": company.get("name") or "",
        "scale": company.get("scale") or company.get("complexity_tier") or "MICRO",
        "employees": company.get("employees") or 0,
    }


def _read_applicability(case_path: Path) -> list[str]:
    """Read the regulatory/applicability.yaml and return ``applicable_regulations``."""
    path = case_path / "input" / "regulatory" / "applicability.yaml"
    raw = _read_yaml_doc(path)
    regs = raw.get("applicable_regulations") or []
    return [str(r) for r in regs if isinstance(r, str)]


def _read_interactions(case_path: Path) -> dict[str, Any]:
    """Read the regulatory/interactions.yaml into a structured dict.

    Returns the four buckets the spec defines:
    ``temporal_conflicts``, ``requirement_conflicts``, ``trigger_mismatches``,
    ``negative_analyses``. Each item carries the sub_domains list so the
    packet can filter per-subdomain.
    """
    path = case_path / "input" / "regulatory" / "interactions.yaml"
    raw = _read_yaml_doc(path)
    return {
        "temporal_conflicts": list(raw.get("temporal_conflicts") or []),
        "requirement_conflicts": list(raw.get("requirement_conflicts") or []),
        "trigger_mismatches": list(raw.get("trigger_mismatches") or []),
        "negative_analyses": list(raw.get("negative_analyses") or []),
    }


def _read_business_goals(case_path: Path) -> list[dict[str, Any]]:
    """Read business_goals.yaml — the closed list for OBJ-07 anchors."""
    path = case_path / "input" / "company" / "business_goals.yaml"
    raw = _read_yaml_doc(path)
    goals = raw.get("goals") or []
    return [g for g in goals if isinstance(g, dict)]


def _read_case_assets(case_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Read all architecture YAMLs into a single dict keyed by category.

    Returns ``{systems, data_stores, data_flows, auth_systems, cloud_services,
    data_subjects}`` — each a list of dicts (possibly empty).
    """
    arch_dir = case_path / "input" / "architecture"
    if not arch_dir.is_dir():
        logger.debug("_read_case_assets: %s is not a directory; returning empty", arch_dir)
        return {k: [] for k in _ASSET_KEY_ALIASES}
    out: dict[str, list[dict[str, Any]]] = {}
    for category, aliases in _ASSET_KEY_ALIASES.items():
        out[category] = _read_yaml_list(arch_dir / f"{category}.yaml", aliases)
    return out


def _filter_assets_for_subdomain(
    assets: dict[str, list[dict[str, Any]]],
    subdomain_id: str,
) -> dict[str, list[str]]:
    """Heuristically filter case assets to those likely relevant to one subdomain.

    Strategy: substring match between each asset's text fields and the numeric
    tokens from the subdomain ID (e.g. for D-01.1 → "01" and "1") plus the
    subdomain's literal name. Same heuristic family as
    `inputs.py:_filter_assets_for_domain` but adapted to single-subdomain use.

    Falls back to returning ALL asset IDs when no keyword can be derived —
    conservative, mirrors the v1 heuristic's safety preference.
    """
    # Use the macro-domain digits (e.g. "01" for D-01.1), not the full
    # subdomain digits — yields "011" otherwise and matches nothing. Same
    # convention as `inputs.py:_domain_keywords`.
    macro = subdomain_id.split(".")[0]  # "D-XX"
    macro_digits = "".join(ch for ch in macro if ch.isdigit())
    keywords: list[str] = []
    if macro_digits:
        keywords.append(macro_digits)
        if len(macro_digits) > 1 and macro_digits.startswith("0"):
            keywords.append(macro_digits.lstrip("0") or "0")

    out: dict[str, list[str]] = {k: [] for k in _ASSET_KEY_ALIASES}
    for category, items in assets.items():
        for item in items:
            if not isinstance(item, dict):
                continue
            aid = item.get("id")
            if not aid:
                continue
            haystack = " ".join(
                str(v) for v in item.values() if v is not None
            ).lower()
            if not keywords or any(kw in haystack for kw in keywords):
                out[category].append(str(aid))
    for k in out:
        out[k] = sorted(set(out[k]))
    return out


# ─── Preproc (KG source data) loaders ─────────────────────────────────


def _load_clauses(preproc_root: Path, regulation: str) -> list[dict[str, Any]]:
    """Load all clauses for a single regulation from preproc_out.

    Mirrors ``PreprocCatalogLoader.load_clauses(regulation=...)`` but operates on
    raw dicts (the catalog loader returns Pydantic objects that are harder to
    JSON-serialise). Walks ``preproc_root/entities/clauses/_root/<REG>/`` and
    parses each ``<REG>_CL*.json`` file.
    """
    clauses_dir = preproc_root / "entities" / "clauses" / "_root" / regulation
    if not clauses_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(clauses_dir.glob(f"{regulation}_CL*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("_load_clauses: failed to parse %s: %s; skipping", path, exc)
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def _load_pairs(preproc_root: Path, subdomain_id: str) -> list[dict[str, Any]]:
    """Load all ``RegulatoryPair`` entries for one subdomain from preproc_out.

    Reads ``preproc_root/entities/pairs/D-<XX>/D-<XX.Y>_<A>-<B>.json``. Returns
    the raw dicts so callers can JSON-serialise them.
    """
    # Subdomain ID is "D-XX.Y" → parent is "D-XX"
    parts = subdomain_id.split(".")
    if len(parts) != 2:
        return []
    parent = parts[0]  # "D-XX"
    pairs_dir = preproc_root / "entities" / "pairs" / parent
    if not pairs_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(pairs_dir.glob(f"{subdomain_id}_*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("_load_pairs: failed to parse %s: %s; skipping", path, exc)
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def _load_interactions_for_subdomain(
    interactions: dict[str, Any],
    subdomain_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Filter the case-level interactions to those that mention this subdomain."""
    out: dict[str, list[dict[str, Any]]] = {
        "temporal_conflicts": [],
        "requirement_conflicts": [],
        "trigger_mismatches": [],
        "negative_analyses": [],
    }
    for bucket in out:
        for item in interactions.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            subs = item.get("sub_domains") or []
            if subdomain_id in subs or not subs:
                out[bucket].append(item)
    return out


def _load_proportionality_entry(
    preproc_root: Path,
    subdomain_id: str,
    case_path: Path,
) -> dict[str, Any]:
    """Load the ProportionalityEntry-shaped profile for one subdomain.

    The real KG would surface a ``(:ProportionalityEntry)`` row carrying
    ``tier``, ``evidence_depth``, ``example_controls``, etc. In the
    file-based stand-in we synthesise a minimal but anchored profile from
    the per-domain control evidence YAML plus the company classification
    (tier defaults to STANDARD when unknown).
    """
    macro_id = subdomain_id.split(".")[0]  # "D-XX"
    ctrl_path = preproc_root.parent / "data" / "control_evidence" / f"{macro_id}.yaml"
    if not ctrl_path.exists():
        return {
            "subdomain_id": subdomain_id,
            "tier": "STANDARD",
            "evidence_depth": "",
            "example_controls": "",
            "verification_method": "ANALYZE",
            "ownership": "COMPANY",
        }
    try:
        with ctrl_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "_load_proportionality_entry: failed to parse %s: %s; returning empty",
            ctrl_path, exc,
        )
        data = {}
    controls = data.get("controls") or []
    if not isinstance(controls, list):
        controls = []
    classification = _read_yaml_doc(case_path / "input" / "company" / "classification.yaml")
    company = classification.get("company") or {}
    scale = str(company.get("scale") or "MICRO").upper()
    if scale not in _SCALE_ENUM:
        scale = "MICRO"
    # Pick the first control's tier-scaled current_by_tier entry as evidence_depth
    evidence_depth = ""
    example_controls: list[str] = []
    for ctrl in controls:
        if not isinstance(ctrl, dict):
            continue
        if isinstance(ctrl.get("control"), str):
            example_controls.append(ctrl["control"])
        cbt = ctrl.get("current_by_tier") or {}
        if not evidence_depth and isinstance(cbt, dict):
            evidence_depth = str(cbt.get(scale) or "")
    # Tier defaults to STANDARD; we do NOT invent proportionality_rules.yaml semantics here
    return {
        "subdomain_id": subdomain_id,
        "tier": "STANDARD",
        "scale": scale,
        "evidence_depth": evidence_depth,
        "example_controls": "; ".join(example_controls[:3]),
        "verification_method": "ANALYZE",
        "ownership": "COMPANY",
    }


def _csf_anchors_for_subdomain(subdomain_id: str) -> list[str]:
    """Best-effort heuristic for CSF anchors per subdomain.

    The real KG would traverse ``(:SubDomain)-[:ANCHORED_TO_CSF]->(:CSFSubcategory)``.
    In the file-based stand-in we provide a deterministic, conservative mapping
    keyed on the macro-domain (D-XX) using the NIST CSF 2.0 subcategories most
    commonly cited in the methodology. The mapping is intentionally tiny — the
    packet is *honest about being a stand-in*; a future bump replaces this with
    the real traversal from the ETL.
    """
    macro = subdomain_id.split(".")[0]  # "D-XX"
    mapping: dict[str, list[str]] = {
        "D-01": ["PR.DS-01", "PR.DS-11", "PR.DS-02"],
        "D-02": ["PR.AC-01", "PR.AC-04", "PR.AA-01"],
        "D-03": ["PR.IP-01", "PR.IP-03", "ID.AM-08"],
        "D-04": ["DE.CM-01", "DE.AE-02", "RS.AN-01"],
        "D-05": ["PR.IR-01", "PR.IR-04", "RC.RP-01"],
        "D-06": ["GV.OC-01", "GV.RM-01", "GV.SC-01"],
        "D-07": ["PR.PS-01", "PR.PS-06"],
        "D-08": ["ID.RA-01", "ID.SC-02"],
        "D-09": ["DE.CM-06", "RS.MA-01"],
        "D-10": ["RC.IM-01", "RC.CO-01"],
    }
    return mapping.get(macro, [])


# ─── Packet assembly ─────────────────────────────────────────────────


def _validate_subdomain_id(subdomain_id: str) -> str:
    """Validate and return the canonical subdomain ID; raise on bad input."""
    if not subdomain_id or not _SUBDOMAIN_ID_RE.match(subdomain_id):
        raise ValueError(
            f"subdomain_id must match D-XX.Y pattern; got {subdomain_id!r}"
        )
    return subdomain_id


def _build_clause_pairs(
    pairs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split pairs into (clause_pairs, ambiguity_pairs) — the spec §2.1 split.

    CONDITIONAL pairs are the documented ambiguity surface and feed T1.3.
    Non-CONDITIONAL pairs (SAME / COMPLEMENTARY / CONTRADICTORY / SCOPE_DISJOINT)
    are the clause-pair substrate for cross-regulation analysis (T1.2).
    """
    clause_pairs: list[dict[str, Any]] = []
    ambiguity_pairs: list[dict[str, Any]] = []
    for p in pairs:
        classification = str(p.get("classification") or "").upper()
        entry = {
            "id": p.get("id"),
            "reg_a": p.get("reg_a"),
            "reg_b": p.get("reg_b"),
            "classification": classification,
            "scope_overlap": p.get("scope_overlap"),
            "verbatim_articles": p.get("verbatim_articles") or {},
            "downstream_implication": p.get("downstream_implication") or "",
        }
        if "CONDITIONAL" in classification:
            ambiguity_pairs.append(entry)
        else:
            clause_pairs.append(entry)
    return clause_pairs, ambiguity_pairs


def _build_regulatory_interactions(
    interactions: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Format regulatory interactions as a flat list, normalised to KG shape.

    Each entry: ``{interaction_type, involved_regs, sub_domains, conflict_description,
    resolution_principle, severity, source_id}`` — mirrors the
    ``(:RegulatoryInteraction)`` schema from the spec v3 §2.1.

    Normalises the YAML field-name inconsistency: temporal/requirement/trigger
    buckets carry ``regulations:`` (list), while negative_analyses carries
    ``expected_regulations:``. We surface both under ``involved_regs``.
    """
    out: list[dict[str, Any]] = []
    for bucket_name, items in interactions.items():
        for item in items:
            if not isinstance(item, dict):
                continue
            involved_regs = list(item.get("regulations") or []) or list(
                item.get("expected_regulations") or []
            )
            sub_domains = list(item.get("sub_domains") or [])
            out.append(
                {
                    "interaction_type": _bucket_to_type(bucket_name),
                    "involved_regs": involved_regs,
                    "sub_domains": sub_domains,
                    "conflict_description": str(item.get("description") or ""),
                    "resolution_principle": str(item.get("resolution") or ""),
                    "severity": str(item.get("severity") or "").upper() or "MEDIUM",
                    "source_id": str(item.get("id") or ""),
                }
            )
    return out


def _bucket_to_type(bucket: str) -> str:
    """Map an interactions.yaml bucket name to the spec InteractionType enum."""
    return {
        "temporal_conflicts": "TEMPORAL_CONFLICT",
        "requirement_conflicts": "REQUIREMENT_CONFLICT",
        "trigger_mismatches": "TRIGGER_MISMATCH",
        "negative_analyses": "NEGATIVE_ANALYSIS",
    }.get(bucket, "REQUIREMENT_CONFLICT")


def generate_packet(
    case_path: Path | str,
    subdomain_id: str,
    preproc_root: Path | str | None = None,
) -> dict[str, Any]:
    """Generate the context packet for one (case, subdomain).

    The packet is a JSON-serialisable dict with the keys the T1 scorecard expects
    (and which mirror the spec v3 KG entities). The shape is *deliberately
    identical* to what the real Cypher traversal would emit — the file-based
    stand-in must not become its own substrate.

    Args:
        case_path: Path to the case directory (must contain ``input/``).
        subdomain_id: Canonical subdomain ID (e.g. ``"D-01.1"``).
        preproc_root: Path to ``preproc_out/``; defaults to
            ``<project_root>/preproc_out``.

    Returns:
        Dict with keys ``subdomain_id``, ``case_id``, ``regulation_ids``,
        ``article_ids``, ``asset_ids``, ``business_goal_ids``, ``csf_anchors``,
        ``clause_pairs``, ``ambiguity_pairs``, ``proportional_profile``,
        ``regulatory_interactions``, ``company_context``.

    Raises:
        ValueError: when ``subdomain_id`` is malformed or ``case_path`` is missing.
    """
    subdomain_id = _validate_subdomain_id(subdomain_id)
    case_path = Path(case_path).resolve()
    if not case_path.is_dir():
        raise ValueError(f"case_path is not a directory: {case_path}")
    if preproc_root is None:
        preproc_root = _PROJECT_ROOT / "preproc_out"
    preproc_root = Path(preproc_root).resolve()

    case_id = case_path.name
    classification = _read_yaml_doc(case_path / "input" / "company" / "classification.yaml")
    company = classification.get("company") or {}
    company_context = {
        "case_id": case_id,
        "company_name": company.get("name") or "",
        "sector": company.get("sector") or "",
        "scale": str(company.get("scale") or "MICRO").upper(),
        "employees": company.get("employees") or 0,
        "applicable_regs": _read_applicability(case_path),
    }

    # Assets + filtered per-subdomain view
    all_assets = _read_case_assets(case_path)
    assets_filtered = _filter_assets_for_subdomain(all_assets, subdomain_id)

    # Business goals (closed list for OBJ-07 anchors)
    goals = _read_business_goals(case_path)
    business_goal_ids = sorted(
        g.get("id") for g in goals if isinstance(g, dict) and g.get("id")
    )
    must_business_goal_ids = sorted(
        g.get("id") for g in goals
        if isinstance(g, dict) and g.get("id") and str(g.get("priority") or "").upper() in {"MUST", "HIGH"}
    )

    # Preproc: clauses per applicable regulation; pairs per subdomain
    regulation_ids = list(company_context["applicable_regs"])
    article_ids: list[str] = []
    clauses_by_reg: dict[str, list[dict[str, Any]]] = {}
    for reg in regulation_ids:
        clauses = _load_clauses(preproc_root, reg)
        clauses_by_reg[reg] = clauses
        for c in clauses:
            cid = c.get("id")
            if isinstance(cid, str) and cid:
                article_ids.append(cid)
    article_ids = sorted(set(article_ids))

    pairs = _load_pairs(preproc_root, subdomain_id)
    clause_pairs, ambiguity_pairs = _build_clause_pairs(pairs)

    # Regulatory interactions (case-level interactions.yaml, filtered per subdomain)
    interactions = _load_interactions_for_subdomain(
        _read_interactions(case_path), subdomain_id
    )
    regulatory_interactions = _build_regulatory_interactions(interactions)

    # Proportionality profile + CSF anchors
    proportional_profile = _load_proportionality_entry(
        preproc_root, subdomain_id, case_path
    )
    csf_anchors = _csf_anchors_for_subdomain(subdomain_id)

    packet: dict[str, Any] = {
        "schema_version": "kg_eval_packet/v0",
        "subdomain_id": subdomain_id,
        "case_id": case_id,
        "regulation_ids": regulation_ids,
        "article_ids": article_ids,
        "asset_ids": {
            "systems": assets_filtered.get("systems") or [],
            "data_stores": assets_filtered.get("data_stores") or [],
            "data_flows": assets_filtered.get("data_flows") or [],
            "auth_systems": assets_filtered.get("auth_systems") or [],
            "cloud_services": assets_filtered.get("cloud_services") or [],
            "data_subjects": assets_filtered.get("data_subjects") or [],
        },
        "business_goal_ids": business_goal_ids,
        "must_business_goal_ids": must_business_goal_ids,
        "csf_anchors": csf_anchors,
        "clause_pairs": clause_pairs,
        "ambiguity_pairs": ambiguity_pairs,
        "proportional_profile": proportional_profile,
        "regulatory_interactions": regulatory_interactions,
        "company_context": company_context,
    }
    return packet


def packet_sha256(packet: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of the canonical JSON serialisation.

    Uses ``sort_keys=True`` and stable separators so the hash is reproducible
    across Python versions and OSes (mirrors the KG-02 fingerprint pattern
    from the KG contract).
    """
    blob = json.dumps(
        packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# ─── CLI ──────────────────────────────────────────────────────────────


def _default_output_path(case_path: Path, subdomain_id: str) -> Path:
    """Return the default output path for a packet: ``output/kg_eval/<case>/<sub>.json``."""
    out_dir = _PROJECT_ROOT / "output" / "kg_eval" / case_path.name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{subdomain_id}.json"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse args, generate packet, write JSON + sha256."""
    parser = argparse.ArgumentParser(
        description="Generate a KG-eval context packet for one (case, subdomain).",
    )
    parser.add_argument(
        "--case",
        required=True,
        type=Path,
        help="Path to case directory (e.g. cases/case1-tinytask).",
    )
    parser.add_argument(
        "--subdomain",
        required=True,
        help="Canonical subdomain ID, e.g. D-01.1.",
    )
    parser.add_argument(
        "--preproc-root",
        type=Path,
        default=_PROJECT_ROOT / "preproc_out",
        help="Path to preproc_out/ (default: <repo>/preproc_out).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: output/kg_eval/<case>/<sub>.json).",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress INFO logs."
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        packet = generate_packet(args.case, args.subdomain, args.preproc_root)
    except Exception as exc:
        logger.error("generate_packet failed: %s", exc)
        return 1

    output_path = args.output or _default_output_path(args.case, args.subdomain)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False)
    output_path.write_text(blob, encoding="utf-8")

    digest = packet_sha256(packet)
    sha_path = output_path.with_suffix(output_path.suffix + ".sha256")
    sha_path.write_text(digest + "\n", encoding="utf-8")

    logger.info(
        "Wrote %s (%d bytes, sha256=%s)", output_path, len(blob), digest[:12]
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
