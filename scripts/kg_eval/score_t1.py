"""T1 scorer — KG reasoning A/B harness (CORR-113 Commit 4).

Reads the artefacts produced by ``scripts.kg_eval.run_t1`` and emits a
per-run JSON with all deterministic metrics from the protocol §2.
The judge cell is stubbed to ``null`` until the GLM-5.3-Flash judge
wiring lands (next iteration, per protocol §7 Q4).

Public API:
    score_run(run_dir) -> dict   # one per-run score record
    score_runs(runs_root) -> list[dict]   # batch over a corpus of runs

CLI:
    python -m scripts.kg_eval.score_t1 --input-dir output/kg_eval/<run>

Stdlib only — keeps the scorer cheap and deterministic.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

# Reuse the canonical closed-vocabulary regexes from ref_gate.py so the
# scorer and the gate cannot drift. Importing the module pulls in YAML
# transitively; that's fine because ref_gate already imports yaml.
from aegis_phase1.prompts_v2.ref_gate import (
    _ASSET_ID_RE,
    _CSF_TOKEN_RE,
)

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent

logger = logging.getLogger(__name__)

# Closed vocabularies (mirrors protocol §2 + OBJECTIVES_CONTRACT §4 + spec v3).
_CANONICAL_REGULATIONS = frozenset({"GDPR", "CRA", "NIS2", "DORA", "AI_Act"})
_TIER_ENUM = frozenset({"MINIMAL", "LIGHTWEIGHT", "STANDARD", "RIGOROUS", "DEFERRED"})
_SEVERITY_ENUM = frozenset({"HIGH", "MEDIUM", "LOW"})
_DISPOSITION_ENUM = frozenset(
    {"RESOLVED_BY_FACT", "RESOLVED_BY_TIER", "NEEDS_HUMAN"}
)
_VERIFICATION_METHOD_ENUM = frozenset({"INSPECT", "DEMONSTRATE", "TEST", "ANALYZE"})
_REG_INTERACTION_TYPES = frozenset(
    {"TEMPORAL_CONFLICT", "REQUIREMENT_CONFLICT", "TRIGGER_MISMATCH", "NEGATIVE_ANALYSIS"}
)

# Markdown section detectors — used by L1 Contract metric.
_TENSION_BLOCK_RE = re.compile(
    r"###\s+Tension Resolution:[^\n]*\n"
    r"(?=[^\n]*Friction:[^\n]*\n"
    r"[^\n]*Resolution adopted:[^\n]*\n"
    r"[^\n]*Severity:[^\n]*\n"
    r"[^\n]*Source reference:[^\n]*\n)",
    re.MULTILINE,
)
_AMBIGUITY_BLOCK_RE = re.compile(
    r"###\s+Ambiguity Disposition:[^\n]*\n"
    r"(?=[^\n]*Reading adopted:[^\n]*\n"
    r"[^\n]*Anchors:[^\n]*\n"
    r"[^\n]*Consequence:[^\n]*\n"
    r"[^\n]*Disposition:[^\n]*\n)",
    re.MULTILINE,
)

# Per-family metric collectors — each returns a dict of metric→value.
# A `None` value means "metric not applicable to this family" (e.g. citation
# ⊆ packet is not a T1.4 metric). The caller filters out None entries before
# serialising the score JSON.


def _citation_subset(raw: str, packet: dict | None) -> dict[str, Any] | None:
    """T1.1 L2: every cited asset ID is in the packet's authoritative asset list."""
    if packet is None:
        return None
    asset_block = packet.get("asset_ids") or {}
    allowed = set()
    for kind in ("systems", "data_stores", "data_flows"):
        for x in asset_block.get(kind) or []:
            allowed.add(str(x).upper())
    if not allowed:
        return {
            "metric": "citation_subset_of_packet",
            "value": None,
            "cited_count": 0,
            "valid_count": 0,
            "invalid_count": 0,
            "invalid_tokens": [],
            "note": "EMPTY_PACKET — packet has no asset_ids (KG-09 substrate missing)",
        }
    cited: list[str] = []
    for m in _ASSET_ID_RE.finditer(raw or ""):
        cited.append(m.group(0).upper())
    invalid = sorted(set(cited) - allowed)
    return {
        "metric": "citation_subset_of_packet",
        "value": len(invalid) == 0,
        "cited_count": len(cited),
        "valid_count": len(cited) - len(invalid),
        "invalid_count": len(invalid),
        "invalid_tokens": invalid,
    }


def _csf_tokens_in_catalogue(raw: str, packet: dict | None) -> dict[str, Any] | None:
    """T1.1 / T1.5 L2: every CSF token is in the packet's csf_anchors list."""
    if packet is None:
        return None
    allowed = set(packet.get("csf_anchors") or [])
    if not allowed:
        # Fall back to catalogue from preproc (the real RefGate path). If the
        # catalogue cannot be loaded, this is a "MISSING_GATE" signal — not a
        # silent pass. The protocol explicitly allows this in v0.
        allowed = _load_csf_catalogue()
        if not allowed:
            return {
                "metric": "csf_tokens_in_catalogue",
                "value": None,
                "cited_count": 0,
                "note": "MISSING_GATE — CSF catalogue unavailable (protocol §7 v0)",
            }
    cited = sorted({m.group(1) for m in _CSF_TOKEN_RE.finditer(raw or "")})
    invalid = sorted(set(cited) - allowed)
    return {
        "metric": "csf_tokens_in_catalogue",
        "value": len(invalid) == 0,
        "cited_count": len(cited),
        "invalid_tokens": invalid,
    }


def _load_csf_catalogue() -> set[str]:
    """Load the 106 CSF subcategory IDs from preproc_out (best effort).

    Returns an empty set on failure — callers must treat empty set as
    "catalogue unavailable" (MISSING_GATE).
    """
    path = (
        _PROJECT_ROOT / "preproc_out" / "global" / "NIST_CSF_2.0_subcategories.json"
    )
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover — defensive
        return set()
    out: set[str] = set()
    for key in ("subcategories", "all_subcategories"):
        for entry in data.get(key) or []:
            if isinstance(entry, dict):
                eid = entry.get("id")
                if isinstance(eid, str) and eid:
                    out.add(eid)
    return out


def _structured_block_present(raw: str, block: str) -> dict[str, Any]:
    """Detect the presence of a structured markdown block per family."""
    if block == "tension":
        present = bool(_TENSION_BLOCK_RE.search(raw or ""))
    elif block == "ambiguity":
        present = bool(_AMBIGUITY_BLOCK_RE.search(raw or ""))
    else:
        present = False
    return {
        "metric": f"structured_block_{block}_present",
        "value": present,
    }


def _severity_in_enum(raw: str) -> dict[str, Any] | None:
    """T1.2: severity token in {HIGH, MEDIUM, LOW}."""
    # Match `Severity: <token>` in a Tension Resolution block only
    m = re.search(r"###\s+Tension Resolution:[^\n]*\n[\s\S]*?Severity:\s*([A-Za-z_]+)", raw or "")
    if not m:
        return None
    sev = m.group(1).strip().upper()
    return {
        "metric": "severity_in_enum",
        "value": sev in _SEVERITY_ENUM,
        "found": sev,
    }


def _disposition_in_vocab(raw: str) -> dict[str, Any] | None:
    """T1.3: disposition token in closed vocabulary."""
    m = re.search(
        r"###\s+Ambiguity Disposition:[^\n]*\n[\s\S]*?Disposition:\s*([A-Za-z_]+)",
        raw or "",
    )
    if not m:
        return None
    disp = m.group(1).strip().upper()
    return {
        "metric": "disposition_in_vocab",
        "value": disp in _DISPOSITION_ENUM,
        "found": disp,
    }


def _reading_in_verbatim_articles(raw: str, packet: dict | None) -> dict[str, Any] | None:
    """T1.3: adopted reading appears in one of the packet's verbatim_articles entries."""
    if packet is None:
        return None
    m = re.search(
        r"###\s+Ambiguity Disposition:[^\n]*\n[\s\S]*?Reading adopted:\s*(.+)",
        raw or "",
    )
    if not m:
        return None
    adopted = (m.group(1) or "").strip()
    verbatim = packet.get("ambiguity_pairs") or []
    for pair in verbatim:
        if not isinstance(pair, dict):
            continue
        va = pair.get("verbatim_articles") or {}
        if not isinstance(va, dict):
            continue
        for article_text in va.values():
            if isinstance(article_text, str) and adopted and adopted in article_text:
                return {
                    "metric": "reading_in_verbatim_articles",
                    "value": True,
                    "pair_id": pair.get("id"),
                }
    # Adopted may equal pair-level downstream_implication (per spec §2.1)
    for pair in verbatim:
        if not isinstance(pair, dict):
            continue
        di = pair.get("downstream_implication") or ""
        if isinstance(di, str) and adopted and adopted in di:
            return {
                "metric": "reading_in_verbatim_articles",
                "value": True,
                "pair_id": pair.get("id"),
                "match": "downstream_implication",
            }
    return {
        "metric": "reading_in_verbatim_articles",
        "value": False,
        "adopted": adopted[:200],
    }


def _tier_in_enum(raw: str) -> dict[str, Any] | None:
    """T1.4: tier token in closed enum."""
    m = re.search(
        r"##\s+Proportionality[^\n]*\n[\s\S]*?Tier:\s*([A-Za-z_]+)",
        raw or "",
    )
    if not m:
        return None
    tier = m.group(1).strip().upper()
    return {
        "metric": "tier_in_enum",
        "value": tier in _TIER_ENUM,
        "found": tier,
    }


def _evidence_depth_non_empty(raw: str) -> dict[str, Any] | None:
    """T1.4: Evidence depth: line carries ≥10 chars after the colon."""
    m = re.search(
        r"##\s+Proportionality[^\n]*\n[\s\S]*?Evidence depth:\s*(.+)",
        raw or "",
    )
    if not m:
        return None
    text = (m.group(1) or "").strip()
    return {
        "metric": "evidence_depth_non_empty",
        "value": len(text) >= 10,
        "length": len(text),
    }


def _example_controls_cited(raw: str) -> dict[str, Any] | None:
    """T1.4: Example controls: line non-empty."""
    m = re.search(
        r"##\s+Proportionality[^\n]*\n[\s\S]*?Example controls:\s*(.+)",
        raw or "",
    )
    if not m:
        return None
    text = (m.group(1) or "").strip()
    return {
        "metric": "example_controls_cited",
        "value": len(text) >= 1,
        "text": text[:200],
    }


def _owner_named(raw: str) -> dict[str, Any] | None:
    """T1.4: Owner: line non-empty OR a stakeholder role mentioned."""
    m = re.search(
        r"##\s+Proportionality[^\n]*\n[\s\S]*?Owner:\s*(.+)",
        raw or "",
    )
    if not m:
        return None
    text = (m.group(1) or "").strip()
    role_match = re.search(
        r"\b(DPO|CISO|Engineering|Operations|Governance)\b", raw or ""
    )
    return {
        "metric": "owner_named",
        "value": len(text) >= 1 or bool(role_match),
        "text": text[:200] if text else None,
        "role_match": role_match.group(0) if role_match else None,
    }


def _verification_method_in_enum(raw: str) -> dict[str, Any] | None:
    """T1.4: verification method token in closed enum."""
    m = re.search(
        r"##\s+Proportionality[^\n]*\n[\s\S]*?Verification method:\s*([A-Za-z_]+)",
        raw or "",
    )
    if not m:
        return None
    vm = m.group(1).strip().upper()
    return {
        "metric": "verification_method_in_enum",
        "value": vm in _VERIFICATION_METHOD_ENUM,
        "found": vm,
    }


def _active_regulations_canonical(raw: str) -> dict[str, Any]:
    """T1.5: every regulation token in ## Active regulations is in canonical 5-vocab.

    Grabs the FIRST whitespace-separated token on each ``- XXX:`` line, then
    checks membership against the closed 5-vocabulary (KG-09 reuse). Tokens
    not in the vocab are surfaced in ``invalid`` so the harness can flag
    invented regulations.
    """
    m = re.search(
        r"##\s+Active regulations\s*\n([\s\S]*?)(?=\n##|\Z)",
        raw or "",
    )
    section = m.group(1) if m else ""
    # Match "- SOMETHING:" line-by-line, then take the first token.
    tokens: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        rest = line[1:].strip()
        if ":" in rest:
            rest = rest.split(":", 1)[0].strip()
        if rest:
            tokens.append(rest)
    canonical = set(_CANONICAL_REGULATIONS)
    invalid: list[str] = []
    for tok in tokens:
        norm = (
            "AI_Act"
            if "AI" in tok.upper()
            else ("NIS2" if "NIS" in tok.upper() else tok.upper().replace(" ", "_"))
        )
        if norm not in canonical:
            invalid.append(norm)
    return {
        "metric": "active_regulations_canonical",
        "value": len(invalid) == 0,
        "count": len(tokens),
        "invalid": sorted(set(invalid)),
    }


def _coverage_metrics(raw: str) -> dict[str, Any]:
    """T1.5: coverage across the 4 sub-sections."""
    subs = re.findall(r"\b(D-\d{2}\.\d+)\b", raw or "")
    csfs = sorted({m.group(1) for m in _CSF_TOKEN_RE.finditer(raw or "")})
    tension = bool(_TENSION_BLOCK_RE.search(raw or ""))
    ambiguity = bool(_AMBIGUITY_BLOCK_RE.search(raw or ""))
    return {
        "metric": "coverage_metrics",
        "subdomains_cited": sorted(set(subs)),
        "csf_anchors_cited": csfs,
        "tension_block_present": tension,
        "ambiguity_block_present": ambiguity,
        "has_any_structured_block": tension or ambiguity,
    }


# ─── Family-specific metric dispatch ────────────────────────────────


def _score_t11(raw: str, packet: dict | None) -> list[dict[str, Any]]:
    return [
            x
            for x in (
                _citation_subset(raw, packet),
                _csf_tokens_in_catalogue(raw, packet),
            )
            if x is not None
        ]


def _score_t12(raw: str, packet: dict | None) -> list[dict[str, Any]]:
    return [
            x
            for x in (
                _structured_block_present(raw, "tension"),
                _severity_in_enum(raw),
            )
            if x is not None
        ]


def _score_t13(raw: str, packet: dict | None) -> list[dict[str, Any]]:
    return [
            x
            for x in (
                _structured_block_present(raw, "ambiguity"),
                _disposition_in_vocab(raw),
                _reading_in_verbatim_articles(raw, packet),
            )
            if x is not None
        ]


def _score_t14(raw: str, packet: dict | None) -> list[dict[str, Any]]:
    return [
            x
            for x in (
                _tier_in_enum(raw),
                _evidence_depth_non_empty(raw),
                _example_controls_cited(raw),
                _owner_named(raw),
                _verification_method_in_enum(raw),
            )
            if x is not None
        ]


def _score_t15(raw: str, packet: dict | None) -> list[dict[str, Any]]:
    return [
        _coverage_metrics(raw),
        _active_regulations_canonical(raw),
        _csf_tokens_in_catalogue(raw, packet) or {},
    ]


# ─── T1.6 — Obligation derivation (deterministic exact-match) ────────


_OBLIGATION_ID_RE = re.compile(r"\b([A-Z][A-Z0-9-]*-C[LP]\d{1,4})\b")  # GDPR-CL06 / GDPR-CP02


def _extract_cited_obligation_ids(raw: str) -> list[str]:
    """Extract every ``<REG>-CL<NN>`` or ``<REG>-CP<NN>`` token from the model's output.

    Returns the list in first-seen order. The scorer compares against a
    set so order is irrelevant for the result.
    """
    return _OBLIGATION_ID_RE.findall(raw or "")


def _score_t16(
    raw: str,
    packet: dict | None,
    ground_truth: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Exact-match against the precomputed ground truth.

    ``ground_truth`` is computed by ``scripts/kg_eval/ground_truth.py`` from
    the same sources the packet is generated from. Same SHA-256 input →
    same activations → reproducible.
    """
    if ground_truth is None:
        # Caller forgot to thread the ground truth → surface as MISSING_GATE
        return [{
            "metric": "obligation_derivation",
            "value": None,
            "pass": None,
            "error": "ground_truth not threaded by caller",
            "status": "MISSING_GATE",
        }]

    gt_ids: set[str] = {c["clause_id"] for c in ground_truth.get("activated_clauses") or [] if c.get("clause_id")}
    cited_ids: set[str] = set(_extract_cited_obligation_ids(raw))

    # Exact-match precision/recall on clause IDs.
    if not gt_ids:
        return [{
            "metric": "obligation_derivation",
            "value": None,
            "pass": None,
            "ground_truth_sha256": ground_truth.get("ground_truth_sha256"),
            "status": "EMPTY_GROUND_TRUTH",
        }]
    true_pos = gt_ids & cited_ids
    false_pos = cited_ids - gt_ids
    false_neg = gt_ids - cited_ids
    precision = len(true_pos) / len(cited_ids) if cited_ids else 0.0
    recall = len(true_pos) / len(gt_ids) if gt_ids else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return [{
        "metric": "obligation_derivation",
        "value": {
            "true_positives": sorted(true_pos),
            "false_positives": sorted(false_pos),
            "false_negatives": sorted(false_neg),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "ground_truth_count": len(gt_ids),
            "cited_count": len(cited_ids),
            "ground_truth_sha256": ground_truth.get("ground_truth_sha256"),
        },
        "pass": (len(false_pos) == 0 and len(false_neg) == 0),
        "status": "OK",
    }]


_FAMILY_SCORERS = {
    "T1.1": _score_t11,
    "T1.2": _score_t12,
    "T1.3": _score_t13,
    "T1.4": _score_t14,
    "T1.5": _score_t15,
    "T1.6": _score_t16,
}


# ─── Per-run + batch scoring ────────────────────────────────────────


def score_run(run_dir: Path | str) -> dict[str, Any]:
    """Score one run directory.

    Reads ``env.json`` (arm, model, family, task_id, packet_sha256) and
    ``raw_response.md`` (LLM output). On the WITH-KG arm, also loads
    ``packet.json`` to provide the closed-list ground truth.

    Returns a per-run score record with:
        - task_id, family, arm (mirrored from env.json)
        - metrics: list of per-metric dicts (one per family scorer)
        - judge: null (deferred to next iteration, per protocol §7 Q4)
        - empty_packet: True when the packet has no asset_ids AND family needs
          them (T1.1, T1.5). Mirrors the protocol §4 EMPTY_PACKET contract.

    Never raises — failure to load artefacts is captured in the record so
    the scorecard can flag the run as INVALID rather than silently passing.
    """
    run_dir = Path(run_dir).resolve()
    score: dict[str, Any] = {
        "run_dir": str(run_dir.relative_to(_PROJECT_ROOT))
        if run_dir.is_relative_to(_PROJECT_ROOT)
        else str(run_dir),
        "task_id": None,
        "family": None,
        "arm": None,
        "model": None,
        "packet_sha256": None,
        "metrics": [],
        "judge": None,
        "empty_packet": False,
        "errors": [],
    }
    env_path = run_dir / "env.json"
    raw_path = run_dir / "raw_response.md"
    if not env_path.exists():
        score["errors"].append(f"missing env.json at {env_path}")
        return score
    if not raw_path.exists():
        score["errors"].append(f"missing raw_response.md at {raw_path}")
        return score

    try:
        env = json.loads(env_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover — defensive
        score["errors"].append(f"failed to parse env.json: {exc}")
        return score
    raw = raw_path.read_text(encoding="utf-8")

    score["task_id"] = env.get("task_id")
    score["family"] = env.get("family")
    score["arm"] = env.get("arm")
    score["model"] = env.get("model")
    score["packet_sha256"] = env.get("packet_sha256")
    score["status"] = env.get("status")

    packet: dict | None = None
    if env.get("arm") == "with_kg":
        packet_path = run_dir / "packet.json"
        if packet_path.exists():
            try:
                packet = json.loads(packet_path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover — defensive
                score["errors"].append(f"failed to parse packet.json: {exc}")
        else:
            score["errors"].append(f"missing packet.json at {packet_path}")

    family = str(env.get("family") or "").strip()
    scorer = _FAMILY_SCORERS.get(family)
    if scorer is None:
        score["errors"].append(f"unknown family: {family!r}")
        return score

    # T1.6: thread the precomputed ground truth through (same sources the
    # packet is generated from; reproducible via SHA-256 in env.json).
    ground_truth: dict[str, Any] | None = None
    if family == "T1.6":
        case_id = env.get("case_id")
        subdomain_id = env.get("subdomain_id")
        if case_id and subdomain_id:
            case_path = _PROJECT_ROOT / "cases" / case_id
            preproc_root = _PROJECT_ROOT / "preproc_out"
            try:
                from scripts.kg_eval.ground_truth import compute_ground_truth
                ground_truth = compute_ground_truth(case_path, preproc_root, subdomain_id)
            except Exception as exc:  # pragma: no cover — defensive
                score["errors"].append(f"failed to compute ground truth: {exc}")
        else:
            score["errors"].append("T1.6 missing case_id or subdomain_id in env.json")
        score["ground_truth_sha256"] = (ground_truth or {}).get("ground_truth_sha256")

    # Call the family scorer. For T1.6 we pass the ground truth as a 3rd
    # positional argument via a thin wrapper (the scorer signatures are
    # (raw, packet) for T1.1..T1.5; (raw, packet, ground_truth) for T1.6).
    if family == "T1.6":
        score["metrics"] = scorer(raw, packet, ground_truth)
    else:
        score["metrics"] = scorer(raw, packet)

    # EMPTY_PACKET detection per protocol §4
    if packet is not None and family in {"T1.1", "T1.5"}:
        assets = packet.get("asset_ids") or {}
        if not any(assets.get(k) for k in ("systems", "data_stores", "data_flows")):
            score["empty_packet"] = True

    return score


def score_runs(runs_root: Path | str) -> list[dict[str, Any]]:
    """Score every immediate child of ``runs_root`` as one run.

    Mirrors the directory layout the runner writes:
        ``output/kg_eval/<task>_<arm>_<ts>/``
    """
    runs_root = Path(runs_root).resolve()
    if not runs_root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for entry in sorted(runs_root.iterdir()):
        if not entry.is_dir():
            continue
        out.append(score_run(entry))
    return out


# ─── CLI ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: score one or many runs."""
    parser = argparse.ArgumentParser(
        description="Score T1 runs (per family, per metric).",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Run directory (or parent of multiple runs).",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress INFO logs."
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Treat --input-dir as a parent and score every immediate child.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    scores = score_runs(args.input_dir) if args.recursive else [score_run(args.input_dir)]

    print(json.dumps(scores, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
