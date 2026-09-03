"""Provenance registry — CORR-112.

Single source of truth for: which **section** of which **Doc** comes from where.
Cited explicitly in each produced Markdown via ``section_tag_for_heading()``,
and rendered to ``docs/PROVENANCE.md`` by
``scripts/output_tools/generate_provenance_map.py``.

Why a separate file (not in ``_common.py``):

* Renderers import ``doc_preamble`` from ``_common``. Provenance is read
  at render time but is **code-as-data** — a separate module lets the
  ``docs/PROVENANCE.md`` regenerator reach into the registry without
  dragging in any heavy render-time deps.
* Provenance is short and stable; a one-screen lookup table that a
  reviewer can grep.

Vocabulary (locked — see grill 2026-09-03):

  * ``"deterministic"``     — produced by a deterministic renderer (no
    LLM call in the chain for that section). Default origin; renderers
    do NOT need to emit a tag for deterministic sections (they're
    self-evident), but the registry records them for completeness so the
    PROVENANCE map is the full audit trail.
  * ``"P1B-LLM-01-INTERPRETATION"`` etc. — produced by the named spec.
    The renderer's raw response is captured in
    ``state["per_spec_markdown"][spec_id]`` and structured into
    ``domain_results`` / ``aggregated_data``.
  * ``"hybrid"``             — deterministic facts + an LLM-derived
    narrative composed together. Doc 04b §3 falls here (maturity from
    DOC04 readiness facts is mechanical, but per-capability prose is LLM).

Anything else (``"unknown"``, ``""``, ``None``) renders as the section
has no origin declared — callers should NEVER ship a Doc 01-09 with
those values; the gate in F3 will refuse.

Headings uses the **exact string** emitted by the renderer
(``"## 1. PURPOSE"``, etc. — the same line that ``parts.append(...)``
writes). Each entry carries a ``human_label`` that the regenerated
``docs/PROVENANCE.md`` shows for readability; it is **not** used at render
time so any small wording drift in the heading stays editable without
breaking the registry.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# Spec IDs are referenced as strings (not enums) so the registry has no
# dependency on Methodology-main prompt IDs — they are an exchange
# format, not internal code.
SPEC_P1B_01 = "P1B-LLM-01-INTERPRETATION"
SPEC_P1B_02 = "P1B-LLM-02-RATIONALE"
SPEC_P1C_01 = "P1C-LLM-01-OVERLAP-CLASSIFICATION"
SPEC_P1C_02 = "P1C-LLM-02-COMPOUND-EVENT"
SPEC_P1C_03 = "P1C-LLM-03-STRATEGIC-SYNTHESIS"

ALL_SPECS: tuple[str, ...] = (
    SPEC_P1B_01,
    SPEC_P1B_02,
    SPEC_P1C_01,
    SPEC_P1C_02,
    SPEC_P1C_03,
)

# Used by is_known_origin as the closed set of admissible values.
_ALL_ORIGINS: frozenset[str] = frozenset(
    {"deterministic", "hybrid"} | set(ALL_SPECS)
)


# The 9 produced docs. Map doc_id -> human title used in PROVENANCE.md.
DOC_TITLES: dict[str, str] = {
    "AEGIS-P1-04":  "Company Context Assessment",
    "AEGIS-P1-04a": "Architecture & Data Inventory",
    "AEGIS-P1-04b": "Capability Maturity",
    "AEGIS-P1-04c": "Strategic Implications (P1C-LLM-03)",
    "AEGIS-P1-04d": "Strategy Diagram (P1C-LLM-03)",
    "AEGIS-P1-05":  "Regulatory Applicability",
    "AEGIS-P1-06":  "Clause Mapping Matrix",
    "AEGIS-P1-07":  "Structured Compliance Matrix",
    "AEGIS-P1-07b": "Proportionality Profile",
}


@dataclass(frozen=True)
class SectionEntry:
    """One section of one Doc.

    ``heading`` is the exact substring emitted by the renderer (without
    the trailing ``\\n``). ``human_label`` is what ``docs/PROVENANCE.md``
    shows. ``origin`` is one of ``deterministic``, ``hybrid``, or any
    value in :data:`ALL_SPECS`.
    """
    heading: str
    human_label: str
    origin: str


# Section-by-section provenance. Keys are (doc_id, heading_exact).
# Headings are emitted by the renderer in this order; missing ones
# resolve to "deterministic" via :func:`origin_for_heading` (with a
# WARNING log so the registry is the canonical truth over time).
PROVENANCE: dict[tuple[str, str], SectionEntry] = {}


def _e(doc_id: str, heading: str, human_label: str, origin: str) -> tuple[str, str]:
    """Internal: build a SectionEntry + register it in PROVENANCE."""
    key = (doc_id, heading)
    PROVENANCE[key] = SectionEntry(heading, human_label, origin)
    return key


# --- Doc 04 — Company Context Assessment ------------------------------
_e("AEGIS-P1-04", "## 1. DOCUMENT PURPOSE\n",               "DOC PURPOSE",            "deterministic")
_e("AEGIS-P1-04", "## 2. ASSESSMENT SUMMARY\n",              "ASSESSMENT SUMMARY",     "deterministic")
_e("AEGIS-P1-04", "## 3. STAKEHOLDER ANALYSIS (A1)\n",       "STAKEHOLDERS",            "deterministic")
_e("AEGIS-P1-04", "## 4. BUSINESS GOALS CATALOG\n",          "BUSINESS GOALS",          "deterministic")
_e("AEGIS-P1-04", "## 5. INTAKE FORM RESPONSE SUMMARY\n",   "INTAKE SUMMARY",          "deterministic")
_e("AEGIS-P1-04", "## 6. REGULATORY APPLICABILITY FLAGS\n", "REGULATORY FLAGS",         "deterministic")
_e("AEGIS-P1-04", "## 7. ARCHITECTURAL IMPLICATIONS\n",     "ARCHITECTURAL IMPLICATIONS", "deterministic")
_e("AEGIS-P1-04", "## 8. DATA FLOW SUMMARY\n",              "DATA FLOW SUMMARY",       "deterministic")
_e("AEGIS-P1-04", "## 9. COMPLIANCE CAPABILITY ASSESSMENT\n","COMPLIANCE CAPABILITY",   "deterministic")
_e("AEGIS-P1-04", "## 10. TIER & COMPLIANCE POSTURE (CORR-038)\n", "TIER + COMPLIANCE POSTURE", "deterministic")
_e("AEGIS-P1-04", "## N. DOCUMENT APPROVAL\n",             "DOCUMENT APPROVAL",       "deterministic")
_e("AEGIS-P1-04", "## N-1. VERSION HISTORY\n",              "VERSION HISTORY",         "deterministic")
# NOTE: Doc 04 has NO H2 LLM section. The renderer's
# render_per_spec_markdown_appendix() call (in doc_04.py line ~1042)
# emits a single "Source: P1B-LLM-0X" appendix; we tag that whole
# appendix with a single provenance line below.

# --- Doc 04a — Architecture & Data Inventory --------------------------
_e("AEGIS-P1-04a", "## 1. Technical Architecture\n",          "ARCHITECTURE",       "deterministic")
_e("AEGIS-P1-04a", "## 2. Data Inventory\n",                   "DATA INVENTORY",     "deterministic")
_e("AEGIS-P1-04a", "## 3. Compliance Mapping (Layer 0)\n",     "LAYER 0 MAPPING",    "deterministic")
_e("AEGIS-P1-04a", "## 4. Gate\n",                              "GATE",                "deterministic")
# NOTE: Doc 04a carries Phase 1B content only in the
# Source Appendix (render_per_spec_markdown_appendix). No H2 LLM.

# --- Doc 04b — Capability Maturity ------------------------------------
_e("AEGIS-P1-04b", "## 1. Purpose\n",              "PURPOSE",                   "deterministic")
_e("AEGIS-P1-04b", "## 2. Assessment Methodology\n","METHODOLOGY",              "deterministic")
_e("AEGIS-P1-04b", "## 3. Per-Domain Assessment\n", "PER-DOMAIN ASSESSMENT",    "hybrid")
_e("AEGIS-P1-04b", "## 3b. LLM Source — P1C-LLM-01 Overlap Classification\n", "P1C-01 SOURCE APPENDIX", SPEC_P1C_01)
_e("AEGIS-P1-04b", "## 4. Summary Dashboard\n",    "DASHBOARD",                "deterministic")
_e("AEGIS-P1-04b", "## 5. Top Gaps (feeds Doc 07)\n","GAPS",                    "deterministic")
_e("AEGIS-P1-04b", "## 6. Consistency Check\n",    "CONSISTENCY",              "deterministic")
_e("AEGIS-P1-04b", "## 7. Gate\n",                 "GATE",                     "deterministic")
# NOTE: Doc 04b H2 sections end at §7. The P1B-LLM-02 narrative
# content lives in the Source Appendix emitted via
# render_per_spec_markdown_appendix.

# --- Doc 04c — Strategic Implications --------------------------------
_e("AEGIS-P1-04c", "## 1. Purpose & Scope\n",                  "PURPOSE + SCOPE",         "deterministic")
_e("AEGIS-P1-04c", "## 2. Inherited Infrastructure\n",          "INHERITED",              "deterministic")
_e("AEGIS-P1-04c", "## 3. Overlap-Implied Third Parties\n",     "THIRD PARTIES",          "deterministic")
_e("AEGIS-P1-04c", "## 4. Contractual Controls\n",              "CONTRACTUAL",            "deterministic")
_e("AEGIS-P1-04c", "## 5. Supply Chain Risk Assessment\n",      "SUPPLY-CHAIN RISK",      SPEC_P1C_01)
_e("AEGIS-P1-04c", "## 6. Compliance Mapping (Layer 0)\n",       "LAYER 0",                "deterministic")
_e("AEGIS-P1-04c", "## 7. Gaps & Known Limitations\n",          "GAPS",                   "deterministic")
_e("AEGIS-P1-04c", "## 8. Gate\n",                               "GATE",                   "deterministic")

# --- Doc 04d — Strategy Diagram ---------------------------------------
_e("AEGIS-P1-04d", "## 1. Purpose & Scope\n",           "PURPOSE + SCOPE",     "deterministic")
_e("AEGIS-P1-04d", "## 2. Company-Level Responsible\n", "COMPANY-LEVEL OWNER", "deterministic")
_e("AEGIS-P1-04d", "## 3. Regulation-Level Owner\n",    "REGULATION OWNER",    "deterministic")
_e("AEGIS-P1-04d", "## 4. Key Roles\n",                 "KEY ROLES",            "deterministic")
_e("AEGIS-P1-04d", "## 5. Reporting Lines\n",          "REPORTING LINES",      "deterministic")
_e("AEGIS-P1-04d", "## 6. Capability Summary\n",       "CAPABILITY SUMMARY",   "deterministic")
_e("AEGIS-P1-04d", "## 7. Training Status\n",         "TRAINING",             "deterministic")
_e("AEGIS-P1-04d", "## 8. Compliance Mapping (Layer 0)\n", "LAYER 0",           "deterministic")
_e("AEGIS-P1-04d", "## 9. Escalation Paths\n",        "ESCALATION",           "deterministic")
_e("AEGIS-P1-04d", "## 10. Gaps & Known Limitations\n", "GAPS",                "deterministic")
_e("AEGIS-P1-04d", "## 11. Gate\n",                    "GATE",                "deterministic")

# --- Doc 05 — Regulatory Applicability --------------------------------
_e("AEGIS-P1-05", "## 0. APPLICABILITY SUMMARY (CORR-038 — v2 source of truth)\n",
                                                       "APPLICABILITY SUMMARY (CORR-038)", "deterministic")
_e("AEGIS-P1-05", "## 1. PURPOSE\n",                  "PURPOSE",               "deterministic")
_e("AEGIS-P1-05", "## 2. APPLICABLE SUMMARY\n",     "APPLICABLE SUMMARY",    "deterministic")
_e("AEGIS-P1-05", "## 3. PER-REGULATION APPLICABILITY\n","PER-REG APPL.",      SPEC_P1C_01)
_e("AEGIS-P1-05", "## 4. NATIVE VS INHERITED COMPLIANCE\n", "NATIVE VS INHERITED", "deterministic")
_e("AEGIS-P1-05", "## 5. SUB-DOMAIN COVERAGE PRELIMINARY\n", "SUBDOMAIN COVERAGE", "deterministic")
_e("AEGIS-P1-05", "## 6. STRATEGIC IMPLICATIONS\n", "STRATEGIC IMPLICATIONS", SPEC_P1B_02)  # contains the rationale LLM body
_e("AEGIS-P1-05", "## 7. REGULATORY GAPS IDENTIFIED\n", "GAPS",                SPEC_P1B_02)
_e("AEGIS-P1-05", "## 8. INPUT TO PHASE 2\n",        "INPUT TO PHASE 2",    "deterministic")

# --- Doc 06 — Clause Mapping Matrix -----------------------------------
_e("AEGIS-P1-06", "## 1. PURPOSE\n",                       "PURPOSE",     "deterministic")
_e("AEGIS-P1-06", "## 2. SUMMARY\n",                        "SUMMARY",     "deterministic")
_e("AEGIS-P1-06", "## 3. CLAUSE-TO-SUBDOMAIN MAPPINGS\n",   "MAPPINGS",    "deterministic")
_e("AEGIS-P1-06", "## 4. NOTES\n",                          "NOTES",       "deterministic")
# NOTE: Doc 06 has only 4 H2 sections — all deterministic. The
# renderer's render_per_spec_markdown_appendix() call (in doc_06.py
# line ~126) emits a single "Source LLM Responses" appendix; we tag
# that whole appendix with one provenance line.

# --- Doc 07 — Structured Compliance Matrix ---------------------------
_e("AEGIS-P1-07", "## 1. PURPOSE\n",                 "PURPOSE",         "deterministic")
_e("AEGIS-P1-07", "## 2. INPUTS\n",                  "INPUTS",          "deterministic")
_e("AEGIS-P1-07", "## 3. COVERAGE MATRIX\n",        "COVERAGE MATRIX", "deterministic")
_e("AEGIS-P1-07", "## 4. SUMMARY\n",                "SUMMARY",         "deterministic")
_e("AEGIS-P1-07", "## 5. COMPLEMENTARITY\n",         "COMPLEMENTARITY", SPEC_P1C_01)
_e("AEGIS-P1-07", "## 6. STRATEGIC IMPLICATIONS\n", "STRATEGIC IMPL.",  SPEC_P1C_03)
_e("AEGIS-P1-07", "## 7. GAPS\n",                    "GAPS",            SPEC_P1C_02)
_e("AEGIS-P1-07", "## 8. GATE CHECKLIST\n",         "GATE",            "deterministic")

# --- Doc 07b — Proportionality Profile -------------------------------
_e("AEGIS-P1-07b", "## 1. PURPOSE\n",                 "PURPOSE",         "deterministic")
_e("AEGIS-P1-07b", "## 2. COMPANY PROFILE METADATA\n","COMPANY META",    "deterministic")
_e("AEGIS-P1-07b", "## 3. TIER ASSIGNMENT SUMMARY\n","TIER SUMMARY",     "deterministic")
_e("AEGIS-P1-07b", "## 4. PER-SUBDOMAIN TABLE\n",    "PER-SUBDOMAIN",   "deterministic")
_e("AEGIS-P1-07b", "## 5. CROSS-CHECK VS CRITICAL ANALYSIS\n", "CROSS-CHECK", "deterministic")
_e("AEGIS-P1-07b", "## 6. KEY ADJUSTMENTS NARRATIVE\n", "KEY ADJUSTMENTS", SPEC_P1B_02)
_e("AEGIS-P1-07b", "## 7. GATE-P READINESS\n",        "GATE-P",          "deterministic")
_e("AEGIS-P1-07b", "## 8. VERSION HISTORY\n",        "VERSION",         "deterministic")
# NOTE: Doc 07b has only 8 H2 sections. Phase 1B Interpretations
# (P1B-LLM-01) content lives in the Source Appendix.


# ---------------------------------------------------------------------------
# Lookup helpers used at render time and by the docs/PROVENANCE.md regenerator
# ---------------------------------------------------------------------------


def origin_for_heading(doc_id: str, heading: str) -> str:
    """Look up the origin for a specific heading in a specific doc.

    ``heading`` is the **full heading line** emitted by the renderer
    (e.g. ``"## 7. GATE CHECKLIST"``). Caller should pass the full
    string from ``parts.append(...)``, NOT a stripped prefix.

    Returns one of:
        * ``"deterministic"`` — explicit entry, or no entry (unknown
          headings default to deterministic with a quiet log message
          — kept this way because deterministic sections are
          self-evident and warnings make the audit noisy).
        * ``SPEC_P1B_01`` / ``SPEC_P1B_02`` / ``SPEC_P1C_01`` / ``SPEC_P1C_02`` / ``SPEC_P1C_03``
        * ``"hybrid"`` — composed deterministic + LLM.

    Never returns ``None`` or ``""``.
    """
    key = (doc_id, heading)
    entry = PROVENANCE.get(key)
    if entry is not None:
        return entry.origin
    return "deterministic"


def human_label_for_heading(doc_id: str, heading: str) -> str:
    """Human-readable label for the heading — used in PROVENANCE.md."""
    entry = PROVENANCE.get((doc_id, heading))
    if entry is not None:
        return entry.human_label
    return heading.strip(" #\n")


def section_tag_for_heading(doc_id: str, heading: str) -> str:
    """Markdown-safe tag emitted right after the heading.

    * ``deterministic``  → ``[deterministic]``
    * spec id            → ``[LLM: P1B-LLM-01-INTERPRETATION]``
    * ``hybrid``         → ``[hybrid: deterministic facts + LLM narrative]``
    * unknown            → ``[origin unknown — verify]``  (should be impossible)
    """
    origin = origin_for_heading(doc_id, heading)
    if origin == "deterministic":
        return "[deterministic]"
    if origin == "hybrid":
        return "[hybrid: deterministic facts + LLM narrative]"
    if origin in ALL_SPECS:
        return f"[LLM: {origin}]"
    return f"[origin unknown: {origin!r}]"


def should_tag(doc_id: str, heading: str) -> bool:
    """True if a heading is LLM-derived (deterministic sections skip the tag).

    Renderers use this to decide whether to emit the tag on the line
    AFTER the heading — avoiding noise in fully-deterministic docs.
    """
    origin = origin_for_heading(doc_id, heading)
    return origin != "deterministic"


def sections_for_doc(doc_id: str) -> list[SectionEntry]:
    """Return all sections for ``doc_id`` in emit order.

    Sections appear in PROVENANCE insertion order (which mirrors the
    render order of headings in the renderer). Docs that introduce a
    heading not in PROVENANCE show up implicitly with origin
    "deterministic" — they aren't returned here but the renderer still
    works via :func:`origin_for_heading`.
    """
    return [e for (d, _h), e in PROVENANCE.items() if d == doc_id]


def is_known_origin(origin: str | None) -> bool:
    """Used by the F3 gate: True if ``origin`` is in the closed set."""
    if not origin:
        return False
    return origin in _ALL_ORIGINS


def all_unknown_in_doc(doc_id: str, headings_seen: Iterable[str]) -> list[str]:
    """Diagnostic: list headings in a doc that are NOT in the registry.

    Used by ``docs/PROVENANCE.md`` to flag drift between renderer and
    registry.
    """
    return [h for h in headings_seen if (doc_id, h) not in PROVENANCE]


def docs_covered() -> list[str]:
    """Iterate over the doc IDs that have at least one provenance entry."""
    seen: set[str] = set()
    for (d, _h) in PROVENANCE:
        seen.add(d)
    return sorted(seen)


__all__ = [
    "ALL_SPECS",
    "DOC_TITLES",
    "PROVENANCE",
    "SPEC_P1B_01",
    "SPEC_P1B_02",
    "SPEC_P1C_01",
    "SPEC_P1C_02",
    "SPEC_P1C_03",
    "SectionEntry",
    "all_unknown_in_doc",
    "docs_covered",
    "human_label_for_heading",
    "is_known_origin",
    "origin_for_heading",
    "section_tag_for_heading",
    "sections_for_doc",
    "should_tag",
]
