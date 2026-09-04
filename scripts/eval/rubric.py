"""5-layer scorecard rubric for OBJ-05 (proportionality adequacy) and friends.

This module is the **judge cell** half of the AEGIS Phase 1 evaluation pipeline
(per ``docs/OBJECTIVES_CONTRACT.md`` §2.1 — [G]+[J] cells). Deterministic gates
live in ``scripts/eval/check_gate.py`` and ``aegis_phase1.prompts_v2.ref_gate``;
this file provides the sampled, verbose-criteria judge that the gate alone
cannot do — namely, assessing whether the *depth* of the rendered narrative is
proportional to the company scale and complexity tier.

Five-layer scorecard structure
------------------------------

Every cell of the rubric returns a ``ScorecardCell`` with a 1-5 score and
verbose criteria (what / how / measured / why). Bare PASS/FAIL is unacceptable
(OBJECTIVES_CONTRACT §5.2). Layers:

1. **What** — the dimension being scored (e.g. depth of Doc 04 §3 narrative).
2. **How** — the algorithm that produced the score (e.g. word-count heuristic).
3. **Measured** — the actual numeric or symbolic value observed.
4. **Why** — the explanation connecting the measurement to the [J] verdict.
5. **Score** — 1-5 integer.

Cells
-----

* ``obj05_proportionality_adequacy`` — the headline OBJ-05 judge cell.
* ``obj10_cross_doc_consistency`` — placeholder scaffold for OBJ-10 (consistency).
* ``obj14_run_metadata_completeness`` — scaffold for OBJ-14 (reproducibility).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 5-layer scorecard structure — single cell type used across all [J] objectives.
# ``what / how / measured / why / score`` is the canonical shape requested by
# ``docs/OBJECTIVES_CONTRACT.md`` §5.2 ("the 5-layer scorecard, ... with
# verbose criteria per cell (what / how / measured / why; bare PASS/FAIL is
# unacceptable)").
SCORECARD_LAYERS: tuple[str, ...] = ("what", "how", "measured", "why", "score")

# Valid OBJ-05 tier combos. ``scale`` is the company size (MICRO..MAX) and
# ``complexity_tier`` is the assessment complexity (LOW/MEDIUM/HIGH). Both are
# required for proportionality adequacy (see ``state.CompanyContext``).
VALID_SCALES: tuple[str, ...] = ("MICRO", "SMALL", "MEDIUM", "LARGE", "MAX")
VALID_COMPLEXITY_TIERS: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH")


@dataclass
class ScorecardCell:
    """A single rubric cell, with 5-layer verbose criteria + 1-5 score.

    Attributes:
        objective_id: The OBJ-NN code (e.g. "OBJ-05").
        cell_name: The cell name within the objective.
        what: What this cell is measuring (free text, layer 1).
        how: How the measurement is made (free text, layer 2).
        measured: What the measurement produced (free text, layer 3).
        why: Why the measured value yields this verdict (free text, layer 4).
        score: Integer 1-5; layer 5.
        evidence: Optional dict with raw inputs (e.g. word counts, tier info).
    """

    objective_id: str
    cell_name: str
    what: str
    how: str
    measured: str
    why: str
    score: int
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "cell": self.cell_name,
            "what": self.what,
            "how": self.how,
            "measured": self.measured,
            "why": self.why,
            "score": self.score,
            "evidence": self.evidence,
        }


# ────────────────────────────────────────────────────────────────────
# Word-count helpers (the proportionality heuristic core)
# ────────────────────────────────────────────────────────────────────


def _count_words(text: str) -> int:
    """Return the word count of ``text`` (whitespace split). Cheap & stable."""
    return len(re.findall(r"\b\w+\b", text))


def _split_subdomain_sections(text: str) -> list[tuple[str, str]]:
    """Split a Doc 04 narrative into ``(subdomain_id, body)`` pairs.

    Recognises the canonical ``### D-XX.Y`` markdown headers. Returns the
    section header as the first item of each tuple (e.g. "D-01.4"). Sections
    without a recognised header are skipped.
    """
    pattern = re.compile(r"^(#{2,4})\s+(D-\d{2}\.\d+)\b[^\n]*\n", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        sub_id = m.group(2)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        sections.append((sub_id, body))
    return sections


# ────────────────────────────────────────────────────────────────────
# OBJ-05 — proportionality adequacy
# ────────────────────────────────────────────────────────────────────


# Tier table — expected narrative word-count RANGE per (scale, complexity_tier).
# The width of the range is narrow for LOW complexity and wide for HIGH
# complexity; LOW-tier MICROs should not see 200-word paragraphs and HIGH-tier
# MAXs should not see 50-word stubs. Values are empirically chosen (see
# OBJECTIVES_CONTRACT §2.1 OBJ-05 "depth scales with enterprise tier and role")
# and are a **judge heuristic** — not a deterministic gate.
PROPORTIONALITY_BOUNDS: dict[tuple[str, str], tuple[int, int]] = {
    # (scale, complexity_tier) -> (min_words, max_words) per subdomain section.
    ("MICRO", "LOW"): (20, 80),
    ("MICRO", "MEDIUM"): (40, 140),
    ("MICRO", "HIGH"): (60, 200),
    ("SMALL", "LOW"): (40, 120),
    ("SMALL", "MEDIUM"): (60, 200),
    ("SMALL", "HIGH"): (80, 280),
    ("MEDIUM", "LOW"): (60, 180),
    ("MEDIUM", "MEDIUM"): (90, 300),
    ("MEDIUM", "HIGH"): (120, 400),
    ("LARGE", "LOW"): (80, 240),
    ("LARGE", "MEDIUM"): (120, 400),
    ("LARGE", "HIGH"): (160, 600),
    ("MAX", "LOW"): (100, 320),
    ("MAX", "MEDIUM"): (160, 500),
    ("MAX", "HIGH"): (220, 800),
}


def _proportionality_score(
    scale: str,
    complexity_tier: str,
    word_counts: list[int],
) -> tuple[int, dict[str, Any]]:
    """Compute a 1-5 proportionality score for a set of subdomain word counts.

    The score reflects how well the observed word counts fit the expected
    range for the given (scale, complexity_tier) combination.

    Returns (score, evidence). Score 5 = all sections within range; 1 = every
    section grossly over- or under-scaled.
    """
    bounds = PROPORTIONALITY_BOUNDS.get((scale, complexity_tier))
    if bounds is None:
        return (
            1,
            {"reason": f"unknown (scale={scale!r}, complexity_tier={complexity_tier!r})"},
        )
    lo, hi = bounds
    if not word_counts:
        return (
            1,
            {
                "reason": "no subdomains observed in narrative",
                "scale": scale,
                "complexity_tier": complexity_tier,
                "expected_range": [lo, hi],
            },
        )

    in_range = sum(1 for w in word_counts if lo <= w <= hi)
    over = sum(1 for w in word_counts if w > hi)
    under = sum(1 for w in word_counts if w < lo)
    total = len(word_counts)
    pct_in = in_range / total

    if pct_in >= 0.9:
        score = 5
    elif pct_in >= 0.7:
        score = 4
    elif pct_in >= 0.5:
        score = 3
    elif pct_in >= 0.25:
        score = 2
    else:
        score = 1

    evidence = {
        "scale": scale,
        "complexity_tier": complexity_tier,
        "expected_range_words": [lo, hi],
        "n_subdomains": total,
        "n_in_range": in_range,
        "n_under": under,
        "n_over": over,
        "pct_in_range": round(pct_in, 3),
        "word_counts": word_counts,
    }
    return score, evidence


def obj05_proportionality_adequacy(
    doc_04_text: str,
    scale: str,
    complexity_tier: str,
    case_id: str = "unknown",
) -> ScorecardCell:
    """Judge cell for OBJ-05 (proportionality adequacy).

    Splits Doc 04 by subdomain section (``### D-XX.Y`` headers), measures the
    narrative word count per section, and scores whether the depth is
    proportional to the given ``scale`` and ``complexity_tier``.

    Args:
        doc_04_text: The rendered Doc 04 markdown body.
        scale: Company size tier — one of ``VALID_SCALES``.
        complexity_tier: Assessment complexity — one of ``VALID_COMPLEXITY_TIERS``.
        case_id: Identifier of the case under evaluation (for evidence).

    Returns:
        A :class:`ScorecardCell` with 5-layer verbose criteria.
    """
    if scale not in VALID_SCALES:
        return ScorecardCell(
            objective_id="OBJ-05",
            cell_name="proportionality_adequacy",
            what="Proportionality adequacy of Doc 04 narrative depth vs enterprise tier.",
            how="Score the narrative word counts per `### D-XX.Y` section against the expected range for (scale, complexity_tier).",
            measured=f"INVALID scale={scale!r}",
            why=f"Scale must be one of {VALID_SCALES}; got {scale!r}. Cannot evaluate proportionality.",
            score=1,
            evidence={"case_id": case_id, "scale": scale, "complexity_tier": complexity_tier},
        )
    if complexity_tier not in VALID_COMPLEXITY_TIERS:
        return ScorecardCell(
            objective_id="OBJ-05",
            cell_name="proportionality_adequacy",
            what="Proportionality adequacy of Doc 04 narrative depth vs enterprise tier.",
            how="Score the narrative word counts per `### D-XX.Y` section against the expected range for (scale, complexity_tier).",
            measured=f"INVALID complexity_tier={complexity_tier!r}",
            why=f"complexity_tier must be one of {VALID_COMPLEXITY_TIERS}; got {complexity_tier!r}. Cannot evaluate proportionality.",
            score=1,
            evidence={"case_id": case_id, "scale": scale, "complexity_tier": complexity_tier},
        )

    sections = _split_subdomain_sections(doc_04_text)
    word_counts = [_count_words(body) for _sub_id, body in sections]
    score, evidence = _proportionality_score(scale, complexity_tier, word_counts)
    evidence["case_id"] = case_id
    evidence["subdomain_ids"] = [sub_id for sub_id, _body in sections]
    if not word_counts:
        # The empty-doc branch in _proportionality_score returns a partial
        # evidence dict; build a clear `why` and stop here.
        return ScorecardCell(
            objective_id="OBJ-05",
            cell_name="proportionality_adequacy",
            what="Proportionality adequacy of Doc 04 narrative depth vs enterprise tier.",
            how=(
                "Split Doc 04 markdown by `### D-XX.Y` headers; count words per section; "
                "compare against the (scale, complexity_tier) word-range table in "
                "`scripts/eval/rubric.py:PROPORTIONALITY_BOUNDS`."
            ),
            measured="0 subdomains observed in Doc 04 narrative",
            why=(
                "No `### D-XX.Y` sections found in Doc 04; cannot evaluate "
                "proportionality. Score 1 (lowest) is recorded so the "
                "no-regression rule surfaces the missing narrative."
            ),
            score=score,
            evidence=evidence,
        )
    lo, hi = PROPORTIONALITY_BOUNDS[(scale, complexity_tier)]

    if score == 5:
        why = (
            f"All {evidence['n_subdomains']} subdomain sections sit within the expected "
            f"{lo}-{hi} word range for ({scale}, {complexity_tier}). Narrative depth is "
            f"proportionate to the enterprise tier."
        )
    elif score >= 3:
        why = (
            f"{evidence['n_in_range']}/{evidence['n_subdomains']} subdomain sections "
            f"({evidence['pct_in_range']:.0%}) sit within the expected {lo}-{hi} word range "
            f"for ({scale}, {complexity_tier}). {evidence['n_under']} under-scaled and "
            f"{evidence['n_over']} over-scaled. Adequate but not tight."
        )
    else:
        why = (
            f"Only {evidence['n_in_range']}/{evidence['n_subdomains']} subdomain sections "
            f"({evidence['pct_in_range']:.0%}) sit within the expected {lo}-{hi} word range "
            f"for ({scale}, {complexity_tier}). {evidence['n_under']} under-scaled and "
            f"{evidence['n_over']} over-scaled. Proportionality is poor — narrative depth "
            f"does not match the enterprise tier."
        )

    return ScorecardCell(
        objective_id="OBJ-05",
        cell_name="proportionality_adequacy",
        what="Proportionality adequacy of Doc 04 narrative depth vs enterprise tier.",
        how=(
            "Split Doc 04 markdown by `### D-XX.Y` headers; count words per section; "
            "compare against the (scale, complexity_tier) word-range table in "
            "`scripts/eval/rubric.py:PROPORTIONALITY_BOUNDS`. The score is the share of "
            "sections within range, mapped 1-5 via >=0.9, 0.7, 0.5, 0.25 thresholds."
        ),
        measured=(
            f"{evidence['n_in_range']}/{evidence['n_subdomains']} sections in range "
            f"({evidence['pct_in_range']:.0%}); word counts={word_counts}."
        ),
        why=why,
        score=score,
        evidence=evidence,
    )


# ────────────────────────────────────────────────────────────────────
# Convenience entry points
# ────────────────────────────────────────────────────────────────────


def read_enterprise_context(
    run_dir: Path | str,
    state_json_path: Path | str | None = None,
) -> dict[str, Any]:
    """Extract ``Enterprise.scale`` and ``Enterprise.complexity_tier`` from a run.

    Tries, in order:
      1. ``<run_dir>/work/state.json`` (live orchestrator state)
      2. ``<run_dir>/state.json`` (legacy)
      3. ``state_json_path`` if provided
      4. Doc 04 frontmatter (``scale:`` / ``complexity_tier:`` keys)

    Returns a dict with keys ``scale``, ``complexity_tier``, ``case_id``;
    missing fields default to ``"UNKNOWN"`` so the judge can record the
    failure rather than crashing.
    """
    candidates: list[Path] = []
    if state_json_path is not None:
        candidates.append(Path(state_json_path))
    run_dir_path = Path(run_dir)
    candidates.append(run_dir_path / "work" / "state.json")
    candidates.append(run_dir_path / "state.json")

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            import json

            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Look for Enterprise context — a few common shapes.
        enterprise = data.get("Enterprise") or data.get("enterprise") or {}
        if not enterprise and isinstance(data.get("v2_company_context"), dict):
            enterprise = data["v2_company_context"]
        if enterprise:
            return {
                "scale": enterprise.get("scale", "UNKNOWN"),
                "complexity_tier": enterprise.get("complexity_tier", "UNKNOWN"),
                "case_id": data.get("case_id", "unknown"),
            }

    # Last-ditch: scan Doc 04 frontmatter.
    doc04 = run_dir_path / "04_Company_Context_Assessment.md"
    if doc04.exists():
        text = doc04.read_text(encoding="utf-8", errors="ignore")
        m_scale = re.search(r"^scale\s*:\s*(\S+)\s*$", text, re.MULTILINE | re.IGNORECASE)
        m_tier = re.search(r"complexity_tier\s*:\s*(\S+)\s*$", text, re.MULTILINE | re.IGNORECASE)
        if m_scale or m_tier:
            return {
                "scale": m_scale.group(1) if m_scale else "UNKNOWN",
                "complexity_tier": m_tier.group(1) if m_tier else "UNKNOWN",
                "case_id": "doc04-frontmatter",
            }

    return {"scale": "UNKNOWN", "complexity_tier": "UNKNOWN", "case_id": "unknown"}


def evaluate_obj05(
    run_dir: Path | str,
    state_json_path: Path | str | None = None,
) -> ScorecardCell:
    """End-to-end OBJ-05 evaluation against a run directory.

    Reads Enterprise context, finds the rendered Doc 04, and runs the
    ``obj05_proportionality_adequacy`` cell. Returns a :class:`ScorecardCell`.
    """
    run_dir_path = Path(run_dir)
    ctx = read_enterprise_context(run_dir_path, state_json_path=state_json_path)
    doc04 = run_dir_path / "04_Company_Context_Assessment.md"
    if not doc04.exists():
        return ScorecardCell(
            objective_id="OBJ-05",
            cell_name="proportionality_adequacy",
            what="Proportionality adequacy of Doc 04 narrative depth vs enterprise tier.",
            how="Read rendered Doc 04 markdown from the run directory.",
            measured="Doc 04 markdown not found at " + str(doc04),
            why="Cannot evaluate proportionality without rendered Doc 04.",
            score=1,
            evidence={"case_id": ctx["case_id"], "scale": ctx["scale"], "complexity_tier": ctx["complexity_tier"]},
        )
    text = doc04.read_text(encoding="utf-8", errors="ignore")
    return obj05_proportionality_adequacy(
        doc_04_text=text,
        scale=ctx["scale"],
        complexity_tier=ctx["complexity_tier"],
        case_id=ctx["case_id"],
    )
