"""CORR-118 hydration — recover parsed P1B-02 synthesis from state.

The pre-agent pipeline loses the P1B-02 synthesis when the model answers in
JSON (CORR-116 S2.1 fallback stores it as a JSON string in
``parsed_output["sections"]["synthesis"]``, and the legacy typed path at
``state["aggregated_data"]["rationale_by_reg"]`` stays empty). The agent
loop (and Doc 05 §7) need the typed dict: {rationale, implications, gaps}.

``hydrate_rationale_by_reg(state)`` returns ``{reg: synthesis_dict}``,
trying in order:
  1. existing ``state["aggregated_data"]["rationale_by_reg"]`` entries that
     already have a dict ``synthesis`` with a ``gaps``/``rationale`` key;
  2. ``state["aggregated_data"]["rationale_by_reg"][reg]["sections"]["synthesis"]``
     as a JSON string (GenericMarkdownOutput dump);
  3. ```json fenced blocks inside ``state["per_spec_markdown"]["P1B-LLM-02-RATIONALE"]``
     (multi-call concat, one block per regulation — lane_id disambiguates).

When new content is recovered, ``state`` is updated in place so Doc 05's
renderer sees the same hydration on its side.
"""

from __future__ import annotations

import json
import re
from typing import Any

_SPEC = "P1B-LLM-02-RATIONALE"
_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def hydrate_rationale_by_reg(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return {regulation: synthesis_dict}, recovering from any state shape."""
    aggregated = state.get("aggregated_data") or {}
    current = aggregated.get("rationale_by_reg") or {}

    recovered: dict[str, dict[str, Any]] = {}
    for reg, entry in current.items():
        synth = _synthesis_from_entry(entry)
        if synth is not None:
            recovered[reg] = synth

    missing = [r for r in _applicable_regs(state) if r not in recovered]
    if missing:
        fenced = _synthesis_from_per_spec(state.get("per_spec_markdown") or {})
        for reg, synth in fenced.items():
            if reg in missing:
                recovered[reg] = synth

    # Write back when we recovered something the state lacked.
    changed = {
        reg: synth
        for reg, synth in recovered.items()
        if (current.get(reg) or {}).get("synthesis") != synth
    }
    if changed:
        new_rbr = dict(current)
        for reg, synth in changed.items():
            entry = dict(new_rbr.get(reg) or {})
            entry["synthesis"] = synth
            new_rbr[reg] = entry
        aggregated["rationale_by_reg"] = new_rbr
        state["aggregated_data"] = aggregated

    return recovered


def _applicable_regs(state: dict[str, Any]) -> list[str]:
    regs = state.get("v2_applicable_regs") or state.get("regulations") or []
    return [str(r) for r in regs]


def _synthesis_from_entry(entry: Any) -> dict[str, Any] | None:
    """Extract synthesis from one rationale_by_reg entry, any shape."""
    if not isinstance(entry, dict):
        return None
    synth = entry.get("synthesis")
    if isinstance(synth, dict) and ("gaps" in synth or "rationale" in synth):
        return synth
    sections = entry.get("sections")
    if isinstance(sections, dict):
        raw = sections.get("synthesis")
        if isinstance(raw, str):
            parsed = _loads(raw)
            if isinstance(parsed, dict) and ("gaps" in parsed or "rationale" in parsed):
                return parsed
    return None


def _synthesis_from_per_spec(per_spec: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Parse ```json blocks from the per-spec raw concat, keyed by lane_id."""
    raw = per_spec.get(_SPEC) or ""
    out: dict[str, dict[str, Any]] = {}
    for match in _JSON_FENCE_RE.finditer(raw):
        parsed = _loads(match.group(1))
        if not isinstance(parsed, dict):
            continue
        if parsed.get("prompt_spec_id") not in (None, _SPEC):
            continue
        lane = parsed.get("lane_id")
        synth = parsed.get("synthesis")
        if isinstance(lane, str) and isinstance(synth, dict):
            out[lane] = synth
    return out


def _loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
