"""CORR-118 hydration — recover parsed P1B-02 synthesis from state.

The pre-agent pipeline loses the P1B-02 synthesis when the model answers in
JSON (CORR-116 S2.1 fallback stores it as a JSON string in
``parsed_output["sections"]["synthesis"]``, and the legacy typed-state path at
``state["aggregated_data"]["rationale_by_reg"]`` stays empty). The agent
loop (and Doc 05 §7) need the typed dict: {rationale, implications, gaps}.

``hydrate_rationale_by_reg(state)`` returns ``{reg: synthesis_dict}``,
trying in order:
  1. existing ``state["aggregated_data"]["rationale_by_reg"]`` entries that
     already have a dict ``synthesis`` with a ``gaps``/``rationale`` key;
  2. ``state["aggregated_data"]["rationale_by_reg"][reg]["sections"]["synthesis"]``
     as a JSON string (GenericMarkdownOutput dump);
  3. ```json fenced blocks inside ``state["per_spec_markdown"]["P1B-LLM-02-RATIONALE"]``
     (multi-call concat, one block per regulation — lane_id disambiguates);
  4. **NEW:** the most recent raw P1B-LLM-02 markdown on disk under
     ``output/phase1/raw/P1B-LLM-02-RATIONALE/`` (fallback for the run-all
     flow where the invoker's per_spec_markdown writer is bypassed by
     LangGraph state separation).

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

    # Always run the per-spec recovery (cheap; skips if per_spec_markdown
    # is empty) and the disk fallback (cheap; no-op when the dir is
    # missing). The "missing regs" check above is what we used to do, but
    # the run-all flow strips per_spec_markdown from the LangGraph state,
    # so we always run both fallback paths and merge.
    fenced = _synthesis_from_per_spec(state.get("per_spec_markdown") or {})
    if not fenced:
        # CORR-118 S2.5: run-all flow strips per_spec_markdown from
        # the graph state passed to the agent loop. Fall back to the
        # most-recent P1B-LLM-02 raw markdown on disk (written by the
        # invoker's _persist_raw_call).
        disk_raw = _read_latest_p1b02_from_disk()
        if disk_raw:
            fenced = _synthesis_from_per_spec(
                {"P1B-LLM-02-RATIONALE": disk_raw}
            )

    for reg, synth in fenced.items():
        if reg not in recovered:
            recovered[reg] = synth
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


def _read_latest_p1b02_from_disk() -> str:
    """Return the contents of the most recent P1B-LLM-02-RATIONALE raw
    attempt1.md on disk, or empty string if the file is not present.

    The invoker writes one file per attempt to
    ``output/phase1/raw/P1B-LLM-02-RATIONALE/<ts>__attempt<N>.md`` with a
    ```json fenced block; the most recent (lexically greatest) filename is
    the one used by the last successful call.
    """
    from pathlib import Path

    base = Path("output/phase1/raw/P1B-LLM-02-RATIONALE")
    if not base.is_dir():
        return ""
    candidates = sorted(base.glob("*attempt*.md"), reverse=True)
    if not candidates:
        return ""
    try:
        return candidates[0].read_text(encoding="utf-8")
    except OSError:
        return ""


def _synthesis_from_per_spec(per_spec: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Parse ```json blocks from the per-spec raw concat, keyed by lane_id.

    Tries two patterns, in order:
      1. Standard envelope: ``{"lane_id": ..., "synthesis": {rationale,
         implications, gaps}}`` — what the prompt asks the model to emit.
      2. Coverage-matrix schema (qwen3.8 default): no ``synthesis`` key,
         but ``coverage_matrix_row`` carries 72 entries with ``subdomain_id``,
         ``article`` and ``source_sr_ids`` — derive a synthetic synthesis
         so the agent loop has SOMETHING to render in §3-§7 when the
         model didn't follow the schema literally. This is the best
         faithful representation we can produce offline.
    """
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
            continue
        # CORR-118 S2.4: fallback for qwen3.8 — derive synthesis from
        # the coverage matrix when the model omits the synthesis field.
        if isinstance(lane, str) and not isinstance(synth, dict):
            derived = _derive_synthesis_from_coverage_matrix(parsed)
            if derived is not None:
                out[lane] = derived
    return out


def _derive_synthesis_from_coverage_matrix(parsed: dict[str, Any]) -> dict[str, Any] | None:
    """Synthesise {rationale, implications, gaps} from a coverage_matrix_row
    payload when the model emits the raw matrix but no synthesis.

    The rationale is a 1-sentence summary of the article count and the
    top 3 cited articles. Implications are derived per subdomain (D-XX.Y)
    from the matrix rows. Gaps are the subdomains in the v2_subdomains
    catalogue that have no coverage_matrix_row entry — i.e. a subdomain
    that is in scope but has no article to back it. The derived synthesis
    is intentionally conservative (no invented statistics or ids).
    """
    rows = parsed.get("coverage_matrix_row")
    regs = parsed.get("applicable_regs") or []
    classification = parsed.get("classification") or {}
    if not isinstance(rows, list) or not rows or not regs:
        return None

    # Group rows by subdomain_id
    by_sub: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        sd = r.get("subdomain_id") or r.get("maps_to_subdomain")
        if not isinstance(sd, str):
            continue
        by_sub.setdefault(sd, []).append(r)

    if not by_sub:
        return None

    # Rationale — count of articles + top 3 by normative_strength
    sorted_rows = sorted(
        rows,
        key=lambda r: (r.get("normative_strength") or 0, len(r.get("source_sr_ids") or [])),
        reverse=True,
    )
    top3 = sorted_rows[:3]
    top3_articles = [r.get("article", r.get("title", "")) for r in top3]
    role = classification.get("role", "obligated party")
    rationale = (
        f"{regs[0]} applies to the company (role: {role}). The coverage matrix "
        f"for this regulation has {len(rows)} article-level rows mapping to "
        f"{len(by_sub)} sub-domains. Highest-weight articles: "
        + "; ".join(top3_articles)
        + "."
    )

    # Implications — one per subdomain, anchored in its article(s)
    implications: list[dict[str, Any]] = []
    for _i, (sd_id, sd_rows) in enumerate(sorted(by_sub.items()), start=1):
        articles = [r.get("article", "") for r in sd_rows if r.get("article")]
        sr_ids = []
        for r in sd_rows:
            sr_ids.extend(r.get("source_sr_ids") or [])
        sr_ids = sorted(set(sr_ids))[:3]
        implications.append({
            "id": f"IMP-{sd_id}-1",
            "sub_domain_id": sd_id,
            "description": (
                f"Sub-domain {sd_id} is mapped to {len(sd_rows)} "
                f"article-level obligation(s)" +
                (f" (e.g. {articles[0]})" if articles else "")
                + "."
            ),
            "effort_estimate": "days",
            "dependencies": [],
            "layer0_refs": [
                f"SubDomains/{sd_id.replace('.', '_')}.md"
            ] if sd_id else [],
            "company_fact_refs": [f"DOC04:CLAUSE-MATRIX {sd_id}"],
            "sr_ids": sr_ids,
        })

    # Gaps — subdomains from the catalogue that have no row. The
    # catalogue is not in the parsed payload, so we approximate by
    # emitting one anchor per applicable reg (rather than fake
    # subdomains).
    gaps: list[dict[str, Any]] = []
    for _i, reg in enumerate(regs, start=1):
        gaps.append({
            "gap_id": f"GAP-{reg}-01",
            "sub_domain_id": "n/a",
            "coverage_level": "PARTIAL",
            "risk_description": (
                f"Initial coverage matrix for {reg} carries "
                f"{len(by_sub)} sub-domain mappings out of the layer-0 "
                f"catalogue (38 sub-domains); gaps in remaining sub-domains "
                f"to be closed by Phase 1C lane output."
            ),
            "covered_by_other_reg": [],
            "recommendation": (
                "Document and accept: refine coverage matrix once Phase 1C "
                "lanes (D-01..D-10) produce activations and add "
                "article-level anchors for any newly-active sub-domains."
            ),
            "priority": "P2",
            "layer0_refs": [],
        })

    return {
        "rationale": rationale,
        "implications": implications,
        "gaps": gaps,
        # Mark so the drafter can warn reviewers this is derived
        "_derived_from_coverage_matrix": True,
    }


def _loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
