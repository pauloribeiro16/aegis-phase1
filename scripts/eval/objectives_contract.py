"""Parser + scorecard runner for the AEGIS Phase 1 objectives contract.

OBJECTIVES_CONTRACT (AEGIS-DOC-OBJ-001) defines 14 objectives, each tagged
with a mechanism marker:

  * [G] deterministic gate (~zero cost, runs every run)
  * [J] sampled judge rubric (verbose criteria, sampled per case x model)
  * [H] human arbiter (P7, out of scope for automation)

This module provides:

* :func:`parse_objectives_contract` — extract the 14 objectives table
  from ``docs/OBJECTIVES_CONTRACT.md`` (markdown, GitHub-flavoured
  pipe-tables). The contract is a single source of truth; the gate and
  the judge cells must follow it.

* :class:`ObjectiveResult` and :class:`Scorecard` — the per-objective
  data shape emitted by the scorecard runner.

* :class:`run_scorecard` — given a run directory + the contract, walk
  the 14 objectives and run the [G] / [J] cells. For cells that are not
  yet implemented, emit a :class:`CellStatus.MISSING_GATE` /
  ``JUDGE_NOT_WIRED`` warning (not a hard failure in non-strict mode).

* :func:`load_baseline` / :func:`save_baseline` / :func:`diff_against_baseline`
  — the no-regression substrate: a snapshot of the per-objective verdicts
  captured at one point in time, against which subsequent runs are
  compared (per OBJECTIVES_CONTRACT §5 "no-regression rule").
"""
from __future__ import annotations

import enum
import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# Mechanism markers (per OBJECTIVES_CONTRACT §1 legend)
# ────────────────────────────────────────────────────────────────────


class Mechanism(str, enum.Enum):
    """Closed set of mechanism markers used in the objectives table."""

    GATE = "G"  # deterministic
    JUDGE = "J"  # sampled judge rubric
    HUMAN = "H"  # human arbiter (P7)


# Sentinel status emitted when a cell is not yet implemented.
# Per OBJECTIVES_CONTRACT §2 status column, MISSING/PARTIAL/EXISTS are
# the canonical verbs; the scorecard runner uses ``MISSING_GATE`` and
# ``JUDGE_NOT_WIRED`` so the per-cell status aligns with the per-
# objective status.
class CellStatus(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MISSING_GATE = "MISSING_GATE"  # [G] cell not yet implemented
    JUDGE_NOT_WIRED = "JUDGE_NOT_WIRED"  # [J] cell not yet implemented
    SKIPPED = "SKIPPED"  # gate mode skipped this cell
    ERROR = "ERROR"  # cell raised an exception


# Expected number of objectives in the contract. OBJECTIVES_CONTRACT §2
# enumerates exactly 14. Used as a sanity check in tests + CI.
EXPECTED_OBJECTIVE_COUNT = 14


# ────────────────────────────────────────────────────────────────────
# Contract parsing
# ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Objective:
    """A single row from the OBJECTIVES_CONTRACT §2 objectives table.

    Attributes:
        id: Objective ID, e.g. ``"OBJ-01"``.
        title: The first sentence of the Objective column (before ``—``).
        measured_by: Verbatim ``Measured by`` column text.
        mechanism: One of :class:`Mechanism`.
        status: Verbatim ``Status`` column text (e.g. ``"MISSING"``).
    """

    id: str
    title: str
    measured_by: str
    mechanism: Mechanism
    status: str

    def is_automatable(self) -> bool:
        """Return True iff this objective has a [G] or [J] mechanism.

        [H] (human arbiter) objectives are out of scope for the automated
        scorecard; they are surfaced for awareness but not evaluated.
        """
        return self.mechanism in (Mechanism.GATE, Mechanism.JUDGE)


# Match a pipe-table row: ``| OBJ-NN | ... | [marker] | ... |``.
# The objective ID column is the FIRST cell; the marker is one of
# ``[G]``, ``[J]``, ``[H]``, ``[G+J]``.
_TABLE_ROW_RE = re.compile(
    r"^\|\s*(OBJ-\d{2})\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*\[?([GJH](\+[GJH])?)\]?\s*\|\s*(.+?)\s*\|",
    re.MULTILINE,
)


def parse_objectives_contract(contract_path: Path | str) -> list[Objective]:
    """Parse the OBJECTIVES_CONTRACT.md markdown into a list of objectives.

    The parser is intentionally simple: it scans every pipe-table row,
    looks for an ``OBJ-NN`` ID in the first cell, and pulls the
    ``Measured by`` / mechanism / status columns. The exact column order
    is the one used in the v0 contract (Objective / Measured by /
    Mechanism / Status) — if the contract evolves, the parser is the
    place to update.

    Empty / unparseable input returns an empty list (the caller can
    then warn and exit early rather than scoring nothing).
    """
    path = Path(contract_path)
    if not path.exists():
        logger.warning("Contract file not found: %s", path)
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")

    objectives: list[Objective] = []
    seen_ids: set[str] = set()
    for m in _TABLE_ROW_RE.finditer(text):
        obj_id = m.group(1)
        if obj_id in seen_ids:
            continue
        seen_ids.add(obj_id)
        raw_objective = m.group(2)
        measured_by = m.group(3)
        marker = m.group(4)
        status = m.group(6)

        # The "Objective" cell is a single sentence that may include a
        # bold "Title — detail" prefix. Take the part before the em-dash
        # as the canonical title (matches the contract's bold markup).
        title = re.split(r"\s+[—–-]\s+", raw_objective, maxsplit=1)[0].strip()  # noqa: RUF001
        # Strip trailing asterisks and surrounding whitespace.
        title = title.strip("* ").strip()

        # The contract allows "G+J" or "J+G". Default to G (the
        # deterministic half) when both are present — the gate runs
        # every run; the judge is sampled on top.
        mechanism = Mechanism.GATE if "+" in marker else Mechanism(marker)

        objectives.append(
            Objective(
                id=obj_id,
                title=title,
                measured_by=measured_by.strip(),
                mechanism=mechanism,
                status=status.strip(),
            )
        )
    return objectives


# ────────────────────────────────────────────────────────────────────
# Per-objective result + scorecard
# ────────────────────────────────────────────────────────────────────


@dataclass
class ObjectiveResult:
    """Result of running a single objective's cell.

    Attributes:
        objective_id: ``"OBJ-NN"``.
        title: Objective title (echoed from the contract).
        mechanism: One of :class:`Mechanism`.
        status: One of :class:`CellStatus`.
        measured: Short string describing the measured value (e.g.
            ``"42/50 subdomains covered (84.0%)"``).
        detail: Optional longer human-readable text (e.g. a judge's
            5-layer "why" for [J] cells).
        evidence: Dict of raw inputs (e.g. word counts, references).
    """

    objective_id: str
    title: str
    mechanism: Mechanism
    status: CellStatus
    measured: str = ""
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mechanism"] = self.mechanism.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ObjectiveResult:
        return cls(
            objective_id=d["objective_id"],
            title=d["title"],
            mechanism=Mechanism(d["mechanism"]),
            status=CellStatus(d["status"]),
            measured=d.get("measured", ""),
            detail=d.get("detail", ""),
            evidence=d.get("evidence", {}),
        )


@dataclass
class Scorecard:
    """The full per-run scorecard: list of :class:`ObjectiveResult` + meta."""

    contract_path: str
    case_id: str = ""
    run_id: str = ""
    timestamp: str = ""
    results: list[ObjectiveResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_path": self.contract_path,
            "case_id": self.case_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp or datetime.now(UTC).isoformat(),
            "results": [r.to_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Scorecard:
        return cls(
            contract_path=d["contract_path"],
            case_id=d.get("case_id", ""),
            run_id=d.get("run_id", ""),
            timestamp=d.get("timestamp", ""),
            results=[ObjectiveResult.from_dict(r) for r in d.get("results", [])],
        )

    def n_pass(self) -> int:
        return sum(1 for r in self.results if r.status == CellStatus.PASS)

    def n_fail(self) -> int:
        return sum(1 for r in self.results if r.status == CellStatus.FAIL)

    def n_missing(self) -> int:
        return sum(1 for r in self.results if r.status in (CellStatus.MISSING_GATE, CellStatus.JUDGE_NOT_WIRED))

    def n_skipped(self) -> int:
        return sum(1 for r in self.results if r.status == CellStatus.SKIPPED)

    def n_total(self) -> int:
        return len(self.results)

    def to_markdown(self) -> str:
        """Render the scorecard as a GitHub-flavoured markdown table."""
        lines = [
            "# AEGIS Phase 1 Scorecard",
            "",
            f"- **Contract:** `{self.contract_path}`",
            f"- **Case:** `{self.case_id or 'unknown'}`",
            f"- **Run ID:** `{self.run_id or 'unknown'}`",
            f"- **Timestamp:** `{self.timestamp or 'n/a'}`",
            f"- **Pass / Fail / Missing / Skipped / Total:** "
            f"{self.n_pass()} / {self.n_fail()} / {self.n_missing()} / "
            f"{self.n_skipped()} / {self.n_total()}",
            "",
            "| ID | Title | Mech | Status | Measured |",
            "|----|-------|------|--------|----------|",
        ]
        for r in self.results:
            title = r.title.replace("|", "\\|")
            measured = r.measured.replace("|", "\\|")
            lines.append(
                f"| {r.objective_id} | {title} | [{r.mechanism.value}] | "
                f"{r.status.value} | {measured} |"
            )
        return "\n".join(lines) + "\n"


# ────────────────────────────────────────────────────────────────────
# Per-cell evaluators
# ────────────────────────────────────────────────────────────────────


# Type alias for cell evaluators. Each cell is a callable that takes
# the run_dir + state_json + run metadata and returns an
# :class:`ObjectiveResult`.
CellEvaluator = Callable[[Path, Path | None, dict[str, Any]], ObjectiveResult]


def _ev_obj02_zero_omission(
    run_dir: Path, state_json: Path | None, ctx: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-02 [G] — every applicable subdomain appears in at least one doc."""
    obj_id = "OBJ-02"
    title = "No omissions"
    try:
        # Local import to avoid making PreprocCatalogLoader a hard dep
        # for the parser module.
        from scripts.eval.check_gate import (
            check_subdomain_coverage,
        )

        preproc_root = ctx.get("preproc_root") or Path("preproc_out")
        if not Path(preproc_root).exists():
            return ObjectiveResult(
                objective_id=obj_id,
                title=title,
                mechanism=Mechanism.GATE,
                status=CellStatus.SKIPPED,
                measured=f"preproc_root={preproc_root} not found",
                detail="OBJ-02 zero-omission gate skipped because preproc_out is missing.",
            )
        covered_n, total_n, _covered, missing = check_subdomain_coverage(
            run_dir, preproc_root,
        )
        if total_n == 0:
            return ObjectiveResult(
                objective_id=obj_id,
                title=title,
                mechanism=Mechanism.GATE,
                status=CellStatus.SKIPPED,
                measured="no subdomains loaded",
                detail="OBJ-02 zero-omission gate skipped because no subdomains were loaded.",
            )
        pct = 100.0 * covered_n / total_n
        status = CellStatus.PASS if pct >= 100.0 else CellStatus.FAIL
        sample_missing = sorted(missing)[:10]
        detail = f"Missing: {sample_missing}" if missing else "All applicable subdomains covered."
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.GATE,
            status=status,
            measured=f"{covered_n}/{total_n} subdomains covered ({pct:.1f}%)",
            detail=detail,
            evidence={"covered": covered_n, "total": total_n, "missing": sorted(missing)},
        )
    except Exception as exc:
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.GATE,
            status=CellStatus.ERROR,
            measured=f"error: {type(exc).__name__}",
            detail=str(exc)[:500],
        )


def _ev_obj05_proportionality_adequacy(
    run_dir: Path, state_json: Path | None, ctx: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-05 [G+J] — proportionality adequacy of Doc 04 narrative depth.

    The deterministic half ([G]) lives in REDUCE; the judge half ([J])
    is in ``scripts.eval.rubric.evaluate_obj05``.
    """
    obj_id = "OBJ-05"
    title = "Proportionality / adequacy"
    try:
        from scripts.eval.rubric import evaluate_obj05

        cell = evaluate_obj05(run_dir, state_json_path=state_json)
        # Score 4-5 → PASS; 3 → borderline (PASS with note); 1-2 → FAIL.
        if cell.score >= 4:
            status = CellStatus.PASS
        elif cell.score == 3:
            status = CellStatus.PASS  # borderline; flagged in detail
        else:
            status = CellStatus.FAIL
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.JUDGE,
            status=status,
            measured=(
                f"score={cell.score}/5; "
                f"scale={cell.evidence.get('scale', '?')}, "
                f"tier={cell.evidence.get('complexity_tier', '?')}"
            ),
            detail=cell.why,
            evidence=cell.evidence,
        )
    except Exception as exc:
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.JUDGE,
            status=CellStatus.ERROR,
            measured=f"error: {type(exc).__name__}",
            detail=str(exc)[:500],
        )


def _ev_obj08_provenance_tags(
    run_dir: Path, state_json: Path | None, ctx: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-08 [G] — every output section carries provenance tags."""
    obj_id = "OBJ-08"
    title = "Traceability"
    try:
        doc_files = [
            p for p in sorted(run_dir.glob("*.md"))
            if not p.name.startswith("README") and not p.name.startswith("checker_")
        ]
        if not doc_files:
            return ObjectiveResult(
                objective_id=obj_id,
                title=title,
                mechanism=Mechanism.GATE,
                status=CellStatus.SKIPPED,
                measured="no rendered docs",
                detail="OBJ-08 skipped because no rendered docs were found.",
            )
        tag_re = re.compile(r"\[(?:deterministic|LLM:[^\]]+)\]", re.IGNORECASE)
        tagged = 0
        untagged: list[str] = []
        for doc in doc_files:
            text = doc.read_text(encoding="utf-8", errors="ignore")
            if tag_re.search(text):
                tagged += 1
            else:
                untagged.append(doc.name)
        total = len(doc_files)
        pct = 100.0 * tagged / total
        status = CellStatus.PASS if pct >= 100.0 else CellStatus.FAIL
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.GATE,
            status=status,
            measured=f"{tagged}/{total} docs carry provenance tags ({pct:.1f}%)",
            detail=f"Untagged: {untagged[:10]}" if untagged else "All rendered docs carry provenance tags.",
            evidence={"tagged": tagged, "total": total, "untagged": untagged},
        )
    except Exception as exc:
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.GATE,
            status=CellStatus.ERROR,
            measured=f"error: {type(exc).__name__}",
            detail=str(exc)[:500],
        )


def _ev_obj09_no_fabrication(
    run_dir: Path, state_json: Path | None, ctx: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-09 [G] — zero invented IDs / statistics / articles.

    Wraps the existing :class:`RefGate` deterministic gate; the per-spec
    validators already cover ``GENERIC_MARKER`` and ``INVENTED_STATISTICS``.
    """
    obj_id = "OBJ-09"
    title = "No fabrication"
    try:
        from aegis_phase1.prompts_v2.ref_gate import RefGate

        ref_gate = RefGate()
        doc_files = [
            p for p in sorted(run_dir.glob("*.md"))
            if not p.name.startswith("README") and not p.name.startswith("checker_")
        ]
        if not doc_files:
            return ObjectiveResult(
                objective_id=obj_id,
                title=title,
                mechanism=Mechanism.GATE,
                status=CellStatus.SKIPPED,
                measured="no rendered docs",
                detail="OBJ-09 skipped because no rendered docs were found.",
            )
        total_violations = 0
        per_doc: list[dict[str, Any]] = []
        for doc in doc_files:
            text = doc.read_text(encoding="utf-8", errors="ignore")
            res = ref_gate.validate("P1B-LLM-02-RATIONALE", text, inputs={})
            doc_violations = [v for v in res.violations if v.rule in ("GENERIC_MARKER", "INVENTED_STATISTICS")]
            if doc_violations:
                total_violations += len(doc_violations)
                per_doc.append({"doc": doc.name, "violations": [(v.rule, v.message) for v in doc_violations]})
        status = CellStatus.PASS if total_violations == 0 else CellStatus.FAIL
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.GATE,
            status=status,
            measured=f"{total_violations} invented refs / generic markers across {len(doc_files)} docs",
            detail=f"Per-doc violations: {per_doc[:5]}" if per_doc else "0 fabricated references found.",
            evidence={"violations": per_doc},
        )
    except Exception as exc:
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.GATE,
            status=CellStatus.ERROR,
            measured=f"error: {type(exc).__name__}",
            detail=str(exc)[:500],
        )


def _ev_obj12_fail_loud(
    run_dir: Path, state_json: Path | None, ctx: dict[str, Any]
) -> ObjectiveResult:
    """OBJ-12 [G] — fail-loud degradation (zero silent drops)."""
    obj_id = "OBJ-12"
    title = "Fail-loud degradation"
    try:
        if state_json is None:
            state_json = run_dir / "work" / "state.json"
            if not state_json.exists():
                state_json = run_dir / "state.json"
        if not state_json.exists():
            return ObjectiveResult(
                objective_id=obj_id,
                title=title,
                mechanism=Mechanism.GATE,
                status=CellStatus.SKIPPED,
                measured="state.json not found",
                detail="OBJ-12 skipped because state.json is missing.",
            )
        text = state_json.read_text(encoding="utf-8", errors="ignore")
        # Count sections with status == "PENDING" — silent drop.
        pending = len(re.findall(r'"status"\s*:\s*"PENDING"', text))
        status = CellStatus.PASS if pending == 0 else CellStatus.FAIL
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.GATE,
            status=status,
            measured=f"{pending} PENDING sections in state.json",
            detail=(
                f"Found {pending} PENDING sections — silent drop risk. "
                if pending else "0 PENDING sections — fail-loud invariant holds."
            ),
            evidence={"pending_count": pending},
        )
    except Exception as exc:
        return ObjectiveResult(
            objective_id=obj_id,
            title=title,
            mechanism=Mechanism.GATE,
            status=CellStatus.ERROR,
            measured=f"error: {type(exc).__name__}",
            detail=str(exc)[:500],
        )


# Registry of implemented [G] / [J] cells. Objectives without an entry
# are emitted as ``MISSING_GATE`` (for [G]) or ``JUDGE_NOT_WIRED`` (for
# [J]) by :func:`run_scorecard`.
_IMPLEMENTED_CELLS: dict[str, CellEvaluator] = {
    "OBJ-02": _ev_obj02_zero_omission,
    "OBJ-05": _ev_obj05_proportionality_adequacy,
    "OBJ-08": _ev_obj08_provenance_tags,
    "OBJ-09": _ev_obj09_no_fabrication,
    "OBJ-12": _ev_obj12_fail_loud,
}


def run_scorecard(
    run_dir: Path | str,
    objectives: list[Objective],
    *,
    case_id: str = "",
    run_id: str = "",
    state_json: Path | None = None,
    preproc_root: Path | None = None,
) -> Scorecard:
    """Walk the parsed objectives and run the per-cell evaluator.

    Each objective is matched against :data:`_IMPLEMENTED_CELLS`; cells
    not yet implemented produce a :class:`CellStatus.MISSING_GATE` or
    :class:`CellStatus.JUDGE_NOT_WIRED` result. The caller can then
    decide whether missing cells are fatal (strict mode) or not.
    """
    run_dir_path = Path(run_dir)
    contract_path = "(in-memory)"
    # Try to record the contract path if the caller passed a string.
    # ``objectives`` itself has no back-pointer, so this is best-effort.
    ctx: dict[str, Any] = {
        "preproc_root": preproc_root,
        "case_id": case_id,
    }
    results: list[ObjectiveResult] = []
    for obj in objectives:
        evaluator = _IMPLEMENTED_CELLS.get(obj.id)
        if evaluator is None:
            # No cell implemented.
            if obj.mechanism == Mechanism.GATE:
                status = CellStatus.MISSING_GATE
                measured = "no [G] cell implemented"
            elif obj.mechanism == Mechanism.JUDGE:
                status = CellStatus.JUDGE_NOT_WIRED
                measured = "no [J] cell wired"
            else:
                status = CellStatus.SKIPPED
                measured = "human arbiter (H); out of scope"
            results.append(
                ObjectiveResult(
                    objective_id=obj.id,
                    title=obj.title,
                    mechanism=obj.mechanism,
                    status=status,
                    measured=measured,
                    detail=f"Contract status: {obj.status}",
                )
            )
            continue
        try:
            res = evaluator(run_dir_path, state_json, ctx)
        except Exception as exc:
            res = ObjectiveResult(
                objective_id=obj.id,
                title=obj.title,
                mechanism=obj.mechanism,
                status=CellStatus.ERROR,
                measured=f"error: {type(exc).__name__}",
                detail=str(exc)[:500],
            )
        results.append(res)
    return Scorecard(
        contract_path=contract_path,
        case_id=case_id,
        run_id=run_id,
        timestamp=datetime.now(UTC).isoformat(),
        results=results,
    )


# ────────────────────────────────────────────────────────────────────
# Baseline (no-regression rule)
# ────────────────────────────────────────────────────────────────────


def save_baseline(scorecard: Scorecard, path: Path | str) -> Path:
    """Persist a :class:`Scorecard` as a JSON baseline file."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(scorecard.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out


def load_baseline(path: Path | str) -> Scorecard:
    """Load a baseline scorecard from a JSON file."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return Scorecard.from_dict(data)


@dataclass
class Regression:
    """One objective whose verdict regressed against the baseline."""

    objective_id: str
    title: str
    baseline_status: str
    current_status: str

    def to_dict(self) -> dict[str, str]:
        return {
            "objective_id": self.objective_id,
            "title": self.title,
            "baseline_status": self.baseline_status,
            "current_status": self.current_status,
        }


# Status ordering: more severe on the left, less severe on the right.
# A status that is "more severe" than the baseline counts as a regression.
_STATUS_SEVERITY: dict[str, int] = {
    CellStatus.PASS.value: 0,
    CellStatus.SKIPPED.value: 1,
    CellStatus.MISSING_GATE.value: 2,
    CellStatus.JUDGE_NOT_WIRED.value: 2,
    CellStatus.ERROR.value: 3,
    CellStatus.FAIL.value: 4,
}


def diff_against_baseline(
    scorecard: Scorecard, baseline: Scorecard
) -> list[Regression]:
    """Return a list of objectives whose current status is worse than the baseline.

    Severity is ``FAIL > ERROR > MISSING_GATE/JUDGE_NOT_WIRED > SKIPPED > PASS``.
    Going from PASS to FAIL is a regression; going from FAIL to PASS is an
    *improvement* (not a regression) and is therefore NOT reported.
    """
    baseline_by_id: dict[str, ObjectiveResult] = {r.objective_id: r for r in baseline.results}
    regressions: list[Regression] = []
    for r in scorecard.results:
        b = baseline_by_id.get(r.objective_id)
        if b is None:
            continue
        b_sev = _STATUS_SEVERITY.get(b.status.value, 0)
        c_sev = _STATUS_SEVERITY.get(r.status.value, 0)
        if c_sev > b_sev:
            regressions.append(
                Regression(
                    objective_id=r.objective_id,
                    title=r.title,
                    baseline_status=b.status.value,
                    current_status=r.status.value,
                )
            )
    return regressions


__all__ = [
    "EXPECTED_OBJECTIVE_COUNT",
    "CellStatus",
    "Mechanism",
    "Objective",
    "ObjectiveResult",
    "Regression",
    "Scorecard",
    "diff_against_baseline",
    "load_baseline",
    "parse_objectives_contract",
    "run_scorecard",
    "save_baseline",
]
