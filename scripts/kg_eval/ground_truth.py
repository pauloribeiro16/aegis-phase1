"""Ground truth generator for KG eval T1 (deterministic).

Computes the set of ``(clause_id, regulation, article)`` tuples that a
correct response to a T1.6 task ("derive obligations for subdomain X
at tier T") MUST cite. Same source data as the context packet generator
(``generate_context_packets.py``) — no Neo4j dependency. Mirrors what the
KG ETL would emit as ``(:ClauseActivation)-[:HAS_CLAUSE_ACTIVATION]->``
once that lands (KG-10 of ``KG_IMPLEMENTATION_CONTRACT.md``).

Canonical source: ``preproc_out/regulation/<REG>/aggregated/
02_SecurityRules_NIST.json``. Each ``SecurityRule`` declares:

  - ``sub_domain``: list of subdomain IDs where the rule applies;
  - ``applies_to_role``: list of obligated parties (CONTROLLER, etc.);
  - ``source_clauses``: list of ``{clause_id, article_ref}`` to cite.

Activation rule (deterministic):
  A clause is ACTIVATED for ``(subdomain, enterprise)`` iff:
    1. Some ``SecurityRule`` has ``sub_domain`` containing
       ``subdomain_id`` for the regulation, AND
    2. Its ``applies_to_role`` intersects the enterprise's applicable
       role for that regulation (from ``applicability.yaml`` /
       ``interactions.yaml``), AND
    3. The clause_id is one of that rule's ``source_clauses``.

If a regulation has no SecurityRules file (or it does not list the
subdomain), the contribution is empty for that regulation — surfacing
the gap rather than fabricating.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_security_rules(preproc_root: Path, regulation: str) -> list[dict[str, Any]]:
    """Read every ``02_SecurityRules_NIST.json`` for ``regulation``.

    Walks ``preproc_out/regulation/<REG>/`` and ``<REG>/aggregated/``,
    collecting the ``srs[]`` array from each. Returns a flat list of
    SecurityRule dicts.
    """
    reg_dir = preproc_root / "regulation" / regulation
    if not reg_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(reg_dir.rglob("02_SecurityRules_NIST.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("ground_truth: failed to parse %s: %s; skipping", path, exc)
            continue
        if isinstance(data, dict):
            for sr in data.get("srs") or []:
                if isinstance(sr, dict):
                    out.append(sr)
    return out


def _load_applicable_roles(case_path: Path, regulation: str) -> set[str]:
    """Read the applicable obligated-party roles for ``(case, regulation)``.

    Falls back to a permissive empty set when no applicability data is
    present (the activation filter then accepts every rule — intentional
    open-license for sparse data, surfaces as the test "test_compute_ground
    _truth_subdomain_with_no_clauses_returns_empty" failing if we ever
    fabricate).
    """
    inter_path = case_path / "input" / "regulatory" / "interactions.yaml"
    roles: set[str] = set()

    # Try applicability.yaml — clause_count doesn't carry roles; we look
    # at the RAR-style sibling (`*_rar*.yaml` etc.). Skip if absent.
    # interactions.yaml carries role information in negative_analyses.
    if inter_path.is_file():
        try:
            import yaml

            data = yaml.safe_load(inter_path.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover
            data = None
        if isinstance(data, dict):
            for bucket in ("temporal_conflicts", "requirement_conflicts",
                           "trigger_mismatches", "negative_analyses"):
                for item in data.get(bucket) or []:
                    if not isinstance(item, dict):
                        continue
                    regs = item.get("regulations") or item.get("expected_regulations") or []
                    if regulation in regs:
                        role = item.get("role")
                        if isinstance(role, str):
                            roles.add(role)
    return roles


def compute_ground_truth(
    case_path: Path,
    preproc_root: Path,
    subdomain_id: str,
) -> dict[str, Any]:
    """Compute the canonical ``ACTIVATED`` clauses for ``(case, subdomain)``.

    Returns a dict with the activated clause IDs, their regulation, and a
    stable SHA-256 over the sorted tuple list. The shape mirrors what the
    scorer compares against (see ``score_t1.py:score_obligation_derivation``).
    """
    case_path = Path(case_path).resolve()
    preproc_root = Path(preproc_root).resolve()

    from scripts.kg_eval.generate_context_packets import _read_applicability

    regs = _read_applicability(case_path)
    activated: dict[tuple[str, str], dict[str, Any]] = {}  # (reg, clause_id) → record

    for reg in regs:
        roles = _load_applicable_roles(case_path, reg)
        for sr in _load_security_rules(preproc_root, reg):
            sd_field = sr.get("sub_domain") or []
            if isinstance(sd_field, str):
                sd_field = [sd_field]
            if subdomain_id not in sd_field:
                continue
            # Role filter: if the rule names roles and the case has no
            # applicable role for this regulation, skip (no leak).
            sr_roles = sr.get("applies_to_role") or []
            if isinstance(sr_roles, str):
                sr_roles = [sr_roles]
            if sr_roles and roles and not (set(sr_roles) & roles):
                continue
            for c in sr.get("source_clauses") or []:
                clause_id = c.get("clause_id")
                if not clause_id:
                    continue
                activated[(reg, clause_id)] = {
                    "clause_id": clause_id,
                    "regulation": reg,
                    "article_reference": c.get("article_ref"),
                    "via_security_rule": sr.get("id"),
                }

    activated_list = sorted(
        activated.values(), key=lambda x: (x["regulation"], x["clause_id"] or "")
    )
    sha = hashlib.sha256(
        json.dumps(activated_list, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    return {
        "case_id": case_path.name,
        "subdomain_id": subdomain_id,
        "activated_clauses": activated_list,
        "count": len(activated_list),
        "ground_truth_sha256": sha,
    }
