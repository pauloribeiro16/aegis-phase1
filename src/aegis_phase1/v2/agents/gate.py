"""DeterministicGate — CORR-118 [G] layer.

Structural checks on the DrafterAgent's markdown output. Runs every cycle
at ~zero cost (no LLM). Mirrors the OBJECTIVES_CONTRACT mechanism legend:
this is the [G] deterministic gate; the ReviewerAgent is the [J] judge.

Checks (fail → feedback string for the next draft cycle):
  G1  no fenced ```json blocks in any section (OBJ-12: raw responses live
      in the sidecar file, never in the document)
  G2  every required section header present (## 3., ## 4., ## 5., ## 6., ## 7.)
  G3  no empty-placeholder phrases when the underlying data exists
      ("No gaps detected", "No sub-domain catalogue available",
      "No architecture inventory available")
  G4  every gap row carries id + priority (P1|P2|P3) + recommendation
  G5  article references well-formed (Art. N / Annex I Part ...) — light
      regex, full catalogue check stays with RefGate at invoker level
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

REQUIRED_SECTIONS = (
    "## 3. PER-REGULATION APPLICABILITY",
    "## 4. NATIVE VS INHERITED COMPLIANCE",
    "## 5. SUB-DOMAIN COVERAGE PRELIMINARY",
    "## 6. STRATEGIC IMPLICATIONS",
    "## 7. REGULATORY GAPS IDENTIFIED",
)

_FORBIDDEN_PLACEHOLDERS = (
    "no gaps detected",
    "no sub-domain catalogue available",
    "no architecture inventory available",
    "(no llm response)",
)

_JSON_FENCE_RE = re.compile(r"```json", re.IGNORECASE)
_GAP_ROW_RE = re.compile(r"^\|\s*GAP-[A-Z0-9.\-]+\s*\|", re.MULTILINE)
_PRIORITY_RE = re.compile(r"\bP[123]\b")
_ARTICLE_RE = re.compile(r"\bArt\.\s*\d+")


@dataclass
class GateResult:
    """Outcome of one gate pass."""

    passed: bool
    failures: list[str] = field(default_factory=list)

    def feedback(self) -> str:
        """Human/LLM-readable feedback for the next draft cycle."""
        if self.passed:
            return ""
        lines = ["Your previous draft failed these deterministic checks:"]
        lines.extend(f"- {f}" for f in self.failures)
        lines.append(
            "Fix ALL of the above and re-emit the complete sections in "
            "markdown (no ```json fences, no placeholder sentences)."
        )
        return "\n".join(lines)


class DeterministicGate:
    """[G] layer of the CORR-118 agent loop."""

    def check(self, sections: dict[str, str], *, expect_gaps: bool = True) -> GateResult:
        """Validate the drafter's sections dict {section_key: markdown}.

        ``sections`` keys are the agent section names (e.g. "s3", "s4", ...,
        "s7"). ``expect_gaps`` False relaxes G4 (deterministic-only runs).
        """
        failures: list[str] = []
        joined = "\n\n".join(sections.values())

        # G1 — no json fences anywhere
        for key, body in sections.items():
            if _JSON_FENCE_RE.search(body):
                failures.append(
                    f"G1[{key}]: contains a ```json fence. Raw LLM responses are "
                    "forbidden inside the document — write the content as "
                    "markdown prose/tables only."
                )

        # G2 — required section headers
        for header in REQUIRED_SECTIONS:
            if header not in joined:
                failures.append(f"G2: missing required section header '{header}'")

        # G3 — placeholders forbidden (the data exists in state)
        lowered = joined.lower()
        for phrase in _FORBIDDEN_PLACEHOLDERS:
            if phrase in lowered:
                failures.append(
                    f"G3: placeholder phrase '{phrase}' found. The underlying "
                    "data exists in the pipeline state — render it instead."
                )

        # G4 — gap rows well-formed
        if expect_gaps and joined.strip():
            gap_rows = _GAP_ROW_RE.findall(joined)
            if not gap_rows:
                failures.append(
                    "G4: §7 must contain at least one gap row with a GAP-* id "
                    "(or, only when truly no gap exists, an explicit justified "
                    "'no gaps' rationale citing the checked sub-domains)."
                )
            else:
                for row in _gap_row_lines(joined):
                    if not _PRIORITY_RE.search(row):
                        failures.append(
                            f"G4: gap row missing P1/P2/P3 priority: {row[:80]}..."
                        )
                    if "recommendation" not in row.lower() and "|" not in row:
                        failures.append(
                            f"G4: gap row missing recommendation column: {row[:80]}..."
                        )

        # G5 — article references well-formed (when any are attempted)
        bad_articles = re.findall(r"\bArt\.(?!\s*\d)[A-Za-z]{1,3}\b", joined)
        if bad_articles:
            failures.append(
                f"G5: malformed article references found: {sorted(set(bad_articles))[:5]}. "
                "Use 'Art. <number>' or 'Annex I Part <N>'."
            )

        return GateResult(passed=not failures, failures=failures)


def _gap_row_lines(joined: str) -> list[str]:
    """Return full table rows that start with a GAP-* id."""
    rows: list[str] = []
    for line in joined.splitlines():
        if _GAP_ROW_RE.match(line):
            rows.append(line)
    return rows
