"""DrafterAgent — CORR-118. Writes Doc 05 §3-§7 in markdown (qwen3.8, piloto).

Circumscribed: receives ONLY the case facts it is allowed to see (company
profile, applicability, sub-domain catalogue, clause map, P1B-02 synthesis)
and emits markdown sections. Never sees other docs' raw LLM output.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM = """You are the DRAFTER agent for AEGIS Doc 05 (Regulatory Applicability Assessment).

Your job: write the document sections §3-§7 in clean markdown for a compliance
decision-maker. You write FROM the provided facts — you never invent IDs,
articles, statistics or facts (contract OBJ-09). Every claim must cite a
provided anchor: article tokens (Art. N / Annex ...), DOC04 fact ids, or
sub-domain ids (D-XX.Y).

OUTPUT CONTRACT (hard):
- Output ONLY the five sections, in this exact order, with these exact headers:
  ## 3. PER-REGULATION APPLICABILITY
  ## 4. NATIVE VS INHERITED COMPLIANCE
  ## 5. SUB-DOMAIN COVERAGE PRELIMINARY
  ## 6. STRATEGIC IMPLICATIONS
  ## 7. REGULATORY GAPS IDENTIFIED
- Markdown prose + pipe tables only. NO ```json fences, NO raw payloads.
- §3: one subsection per applicable regulation — trigger criterion, company
  value, result, evidence (ontology fields), short reasoning.
- §4: NATIVE vs INHERITED per regulation-domain pair (NATIVE = company
  implements; INHERITED = satisfied via supplier attestation, e.g. ISO 27001
  or SOC 2 from a named cloud provider in the facts).
- §5: coverage per sub-domain: SUBSTANTIVE (>=2 applicable regs), PARTIAL
  (exactly 1), NOT_ADDRESSED (0) + a status-count table.
- §6: strategic implications table (id, source regs, description, effort,
  priority) + a short decision-oriented narrative.
- §7: regulatory gaps table with columns:
  | Gap ID | Sub-domain | Type | Risk description | Priority | Recommendation |
  Every gap row MUST have a GAP-* id, a P1/P2/P3 priority and a concrete
  recommendation. Derive gaps from the provided synthesis.gaps plus
  NOT_ADDRESSED sub-domains; never say "no gaps detected" unless the
  facts truly contain none.
"""

_USER_TMPL = """# CASE FACTS (closed anchors — cite only these)

## Applicable regulations
{applicable_regs}

## Company profile
{company_profile}

## Sub-domain catalogue (D-XX.Y — participating regulations)
{subdomain_catalogue}

## Clause map (article → sub-domains)
{clause_map}

## P1B-02 synthesis per regulation (rationale / implications / gaps)
{synthesis}
"""

# {reg}   : {"rationale": str, "implications": [...], "gaps": [...]}
# Value rendering keeps table cells single-line.
_CELL_CAP = 400


def _cell(value: Any) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text[:_CELL_CAP]


class DrafterAgent:
    """Writes Doc 05 sections via the underlying chat model."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def build_prompt(self, facts: dict[str, Any]) -> tuple[str, str]:
        """Return (system, user) prompts from compact case facts."""
        user = _USER_TMPL.format(
            applicable_regs=json.dumps(facts.get("applicable_regs", [])),
            company_profile=facts.get("company_profile", "(not provided)"),
            subdomain_catalogue=facts.get("subdomain_catalogue", "(not provided)"),
            clause_map=facts.get("clause_map", "(not provided)"),
            synthesis=json.dumps(facts.get("synthesis", {}), indent=1, ensure_ascii=False),
        )
        return _SYSTEM, user

    def draft(
        self,
        facts: dict[str, Any],
        feedback: str = "",
        previous_draft: str = "",
    ) -> str:
        """One drafting call. Returns raw markdown text (may violate the gate)."""
        system, user = self.build_prompt(facts)
        if feedback:
            user = (
                f"{user}\n\n# REVISION REQUEST (attempt feedback)\n\n"
                f"{feedback}\n\n"
                "# YOUR PREVIOUS DRAFT (for reference — do not repeat its mistakes)\n\n"
                f"{previous_draft[:6000]}"
            )
        result = self.llm.invoke(system + "\n\n" + user)
        raw = result.get("raw") or ""
        return self._extract_sections(raw)

    def _extract_sections(self, raw: str) -> dict[str, str]:
        """Split the raw response into the 5 sections; tolerate prose around them."""
        markers = [
            "## 3. PER-REGULATION APPLICABILITY",
            "## 4. NATIVE VS INHERITED COMPLIANCE",
            "## 5. SUB-DOMAIN COVERAGE PRELIMINARY",
            "## 6. STRATEGIC IMPLICATIONS",
            "## 7. REGULATORY GAPS IDENTIFIED",
        ]
        positions: list[tuple[int, str]] = []
        for marker in markers:
            idx = raw.find(marker)
            if idx >= 0:
                positions.append((idx, marker))
        positions.sort()
        if not positions:
            return {"s3": raw}
        sections: dict[str, str] = {}
        keys = ["s3", "s4", "s5", "s6", "s7"]
        for i, (idx, _marker) in enumerate(positions):
            end = positions[i + 1][0] if i + 1 < len(positions) else len(raw)
            sections[keys[i]] = raw[idx:end].strip()
        return sections
