"""ReviewerAgent — CORR-118 [J] layer (qwen3.8 as judge, piloto).

Evaluates the draft against the OBJECTIVES_CONTRACT subset relevant to
Doc 05 (OBJ-01 grounding, OBJ-03 citation precision, OBJ-09 no fabrication,
OBJ-12 fail-loud) with verbose verdicts in the EVAL_PROTOCOL format
(what / how / measured / why). Output is parsed with a closed regex — the
reviewer's verdict format is part of the contract.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM = """You are the REVIEWER agent for AEGIS Doc 05. Another agent wrote
the draft sections §3-§7; you audit them against the objectives below and
produce a structured verdict. You are strict but concrete: every FAIL must
quote the offending line and say what a fix looks like.

For EACH objective below emit one verdict block in EXACTLY this format:

OBJ-XX: PASS | WARN | FAIL
what: <one line — what the objective demands>
measured: <what you actually observed in the draft, quoting the draft>
why: <why this passes or fails>

Objectives:
- OBJ-01 company grounding: obligations/claims tied to real anchors — every
  factual claim cites DOC04:* fact ids, an Art./Annex token, or a D-XX.Y id
  from the provided facts. Uncited claims = FAIL.
- OBJ-02 no omissions: every applicable regulation from the facts has a §3
  subsection; every sub-domain id present in the catalogue appears in §5;
  §7 covers the gaps listed in the provided synthesis (if any).
- OBJ-03 citation precision: article/annex tokens are well-formed
  (Art. <digits>, Annex I Part ...) and consistent with the regulation they
  are attributed to. Invented-looking tokens = FAIL.
- OBJ-09 no fabrication: no statistics, dates, article numbers or IDs that
  do not appear in the provided facts. Fabricated content = FAIL.
- OBJ-12 fail-loud: no placeholders, no "no data" claims when data was
  provided; if something is genuinely unknown the draft says so explicitly
  with what would be needed to resolve it.

After the 5 verdict blocks emit EXACTLY one line:

LOOP_VERDICT: PASS | REVISE

PASS only if no objective is FAIL (WARN is acceptable). If REVISE, your
verdict blocks are the feedback the drafter will receive — make each FAIL
actionable.
"""

_VERDICT_RE = re.compile(
    r"^(OBJ-\d{2}):\s*(PASS|WARN|FAIL)\s*$", re.MULTILINE
)
_LOOP_RE = re.compile(r"^LOOP_VERDICT:\s*(PASS|REVISE)\s*$", re.MULTILINE)


@dataclass
class ReviewVerdict:
    """Parsed reviewer output."""

    loop_verdict: str  # "PASS" | "REVISE" | "UNPARSEABLE"
    objectives: dict[str, str] = field(default_factory=dict)  # OBJ-XX → verdict
    raw: str = ""

    @property
    def feedback(self) -> str:
        """The reviewer raw output is the drafter's feedback (it contains
        per-objective FAIL details)."""
        if self.loop_verdict == "PASS":
            return ""
        return self.raw


class ReviewerAgent:
    """Judges a draft against the Doc-05 objective subset."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def review(self, facts: dict[str, Any], draft_sections: dict[str, str]) -> ReviewVerdict:
        draft_md = "\n\n".join(draft_sections.values())
        user = (
            "# FACTS GIVEN TO THE DRAFTER (closed anchors)\n\n"
            f"- applicable regulations: {facts.get('applicable_regs')}\n"
            f"- synthesis gaps ids: "
            f"{self._gap_ids(facts.get('synthesis') or {})}\n\n"
            "# DRAFT TO REVIEW\n\n"
            f"{draft_md}\n\n"
            "Produce the verdict blocks now."
        )
        result = self.llm.invoke(_SYSTEM + "\n\n" + user)
        raw = result.get("raw") or ""
        return self._parse(raw)

    def _parse(self, raw: str) -> ReviewVerdict:
        objectives = {m.group(1): m.group(2) for m in _VERDICT_RE.finditer(raw)}
        loop_match = _LOOP_RE.search(raw)
        if loop_match:
            loop = loop_match.group(1)
        elif objectives and all(v != "FAIL" for v in objectives.values()):
            loop = "PASS"
        elif objectives:
            loop = "REVISE"
        else:
            loop = "UNPARSEABLE"
        return ReviewVerdict(loop_verdict=loop, objectives=objectives, raw=raw)

    @staticmethod
    def _gap_ids(synthesis: dict[str, Any]) -> list[str]:
        ids: list[str] = []
        for reg_synth in synthesis.values():
            if not isinstance(reg_synth, dict):
                continue
            for gap in reg_synth.get("gaps") or []:
                if isinstance(gap, dict) and gap.get("gap_id"):
                    ids.append(str(gap["gap_id"]))
        return sorted(set(ids))
