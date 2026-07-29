# SPEC — Capabilities wired into Doc 04d (remove RACI)

**Spec ID:** SP-2026-18
**Date:** 2026-07-29
**Author:** Planner (opencode / MiniMax-M3)
**Status:** DRAFT
**Level:** spec-first

---

## Context

### Problem Statement

CORR-074 created the `data/capabilities/{D-XX}.yaml` catalog and `load_capabilities()` loader. Doc 04d however still renders `04d_Org_Roles_RACI.md` with the hardcoded `_RACI_BY_DOMAIN` (40 activities × 6 individual people) and `_STAKEHOLDER_COLUMNS` (6 individual names). The user explicitly said in plan mode (2026-07-29): **"remover isso, o raci não deve estar presente"**.

This contract removes the RACI section and replaces it with a **Capability Summary** — a prose + compact list of capability IDs sourced from the new data/capabilities/ catalog. Zero person names. Zero R/A/C/I columns.

### Current State

- `src/aegis_phase1/v2/output/doc_04d.py:80-142` defines `_RACI_BY_DOMAIN` (hardcoded).
- `src/aegis_phase1/v2/output/doc_04d.py:65-72` defines `_STAKEHOLDER_COLUMNS` (hardcoded).
- `_section_raci_matrix` renders 6 columns × N activities, with `Board = 2 founders` literal text on large cases.
- Available infrastructure (delivered by CORR-074): `load_capabilities(domain_id)` + `ROLE_VOCABULARY`.

### Target State

- `_RACI_BY_DOMAIN` and `_STAKEHOLDER_COLUMNS` deleted.
- `_section_raci_matrix` replaced by `_section_capabilities_summary` rendering prose + a compact list of capability IDs with their accountable function.
- No `R/A/C/I` table; no person names; no "Founder"/"CEO acting as"/"Lead Developer"/"2 founders" anywhere in the output.
- Other docs (04a/04b/04c/04e/05/06/07/07b) untouched.
- Tests confirm: (a) capability summary appears for case 3 (MAX), (b) no person names in output, (c) stakeholder leakage test remains green.

---

## Requirements

### Functional Requirements

| # | Requirement | Priority | Rationale |
|---|-------------|----------|-----------|
| FR-1 | Delete `_RACI_BY_DOMAIN` and `_STAKEHOLDER_COLUMNS` from `doc_04d.py` | MUST | User explicit: "remover isso" |
| FR-2 | Replace `_section_raci_matrix` with `_section_capabilities_summary` | MUST | New required section |
| FR-3 | New section renders: (a) 1-paragraph intro on capabilities-not-people; (b) compact list of capability IDs (CAP-DXX-NNN) with `a_function` per D-XX | MUST | Info-only, no RACI |
| FR-4 | When `data/capabilities/{D-XX}.yaml` is missing → emit `_(Capability catalog for D-XX not yet authored; see data/capabilities/D-XX.yaml.)_` | MUST | Per user decision #3 (info-only, no PENDING) |
| FR-5 | No person names in output: `Founder`, `CEO acting as`, `CTO as`, `Lead Developer`, `2 founders` | MUST | User explicit |
| FR-6 | Update version history: 2.3 entry "Remove RACI; add Capability Summary" | MUST | Doc discovery |
| FR-7 | Tests: 3 cases (Micro/Large/Max) — capability list renders, no person names | MUST | Validation |

### Non-Functional Requirements

| # | Requirement | Priority | Rationale |
|---|-------------|----------|-----------|
| NFR-1 | Only `doc_04d.py` modified | MUST | Other docs untouched |
| NFR-2 | Full v2 suite pre-existing failures unchanged | MUST | No new regressions |

### Constraints

- No mention of "RACI" in the rendered doc body (only in the "we replaced it" narrative in the version history).
- `data/capabilities/` only has D-01 and D-04 YAMLs (per CORR-074). Other D-XX render the info-only note.
- `ROLE_VOCABULARY` constants are respected (no out-of-vocab roles in prose).

---

## Architecture Decisions

### Decision 1: §6 is renumbered and renamed

- **Context:** Doc 04d structure is `§1 Purpose → §2 Company-Level → §3 Regulation-Level → §4 Key Roles → §5 Reporting Lines → §6 RACI → §7 Training Status → §8 Compliance Mapping → §9 Escalation → §10 Gaps → §11 Gate`. Removing §6 RACI breaks numbering.
- **Options:** (A) Renumber subsequent sections; (B) Keep §6 title but emit capability summary; (C) Drop section entirely.
- **Decision:** A — renumber. `§6 Capability Summary` (new) was `§6 RACI`. Everything after shifts +1.
- **Rationale:** Stable section numbering is a contract invariant for downstream consumers (PDF parsers, Phase 2B ingestion).
- **Consequences:** Internal references in `doc_04d.py` between sections need updating.

### Decision 2: Capability summary is a TABLE OF CAPABILITY IDs, not a description dump

- **Context:** D-04 has 5 capabilities each with `description`, `obligations`, `a_function`, `r_function`. Listing all fields makes §6 verbose.
- **Options:** (A) Compact table: ID | Accountable Function | Trigger Obligation; (B) Full dump per capability.
- **Decision:** A — compact table with the 3 most useful fields. Full dump goes to the per-spec markdown appendix (already exists for all 5 LLM specs; capabilities appendix if added later).
- **Rationale:** Doc 04d §6 must fit in 1 page. Detail is delegated to the appendix.
- **Consequences:** Add a 1-line trailer pointing to `data/capabilities/{D-XX}.yaml` for full detail.

### Decision 3: No mapping of capabilities to "extra" sections

- **Context:** Capabilities could be cross-referenced into §7 Training (which function needs which training), §9 Escalation (which function has incident authority), §10 Gaps (which function has 0 capability coverage).
- **Options:** (A) Cross-reference everywhere; (B) Single source in §6; (C) Cross-reference only in §10 Gaps.
- **Decision:** C — only §10 Gaps gets a cross-reference (gaps = functions with no capability assigned).
- **Rationale:** Avoid scope creep. Other sections stay untouched. Gaps are the most actionable area.

---

## Data Model

No new data structures. Reuses:
- `load_capabilities(domain_id) -> dict` (CORR-074)
- `ROLE_VOCABULARY` (CORR-074)

---

## API / Interface Design

### Internal function (replaces existing `_section_raci_matrix`)

```python
def _section_capabilities_summary(state: dict[str, Any]) -> list[str]:
    """§6 Capability Summary — prose + compact capability list per D-XX.
    
    Reads `load_capabilities(domain_id)` for each D-01..D-10. Renders info-only
    note when YAML is missing. Never names individuals.
    """
```

### Behavior contract

- For D-XX ∈ {D-01..D-10}:
  - If `load_capabilities(D-XX)` returns non-empty dict: emit `### D-XX Capability Summary` table with columns `{ID | Accountable Function | Regulation Anchor}`. Sorted by capability ID.
  - If empty: emit `_(Capability catalog for D-XX not yet authored; see data/capabilities/D-XX.yaml.)_`.
- Add 1-paragraph intro before the tables: "These capabilities are required by the applicable regulatory perimeter. RACI per individual is intentionally out of scope; capability-to-person allocation is the company's responsibility (see Phase 2B)."

---

## Implementation Plan

### Phase Overview (single phase)

| Phase | Name | Scope | Depends On |
|-------|------|-------|------------|
| 1 | Replace RACI with Capability Summary | `src/aegis_phase1/v2/output/doc_04d.py` + tests | — |

### File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/aegis_phase1/v2/output/doc_04d.py` | modify | Delete `_RACI_BY_DOMAIN`, `_STAKEHOLDER_COLUMNS`; replace `_section_raci_matrix` with `_section_capabilities_summary`; renumber §7→§8, §8→§9, §9→§10, §10→§11, §11→§12; update prologue/PR references; add version history entry |
| `tests/unit/v2/output/test_doc_04d_capability_summary.py` | create | New test: 3 cases (Micro/Large/Max); no person names in output; capability summary section appears |
| `tests/unit/v2/output/test_doc_04_stakeholder_leakage.py` | modify (if needed) | Update column-abbreviation assertions to reflect new content (kept by §4 Key Roles display) |

---

## Acceptance Criteria

### High-Level Criteria

| # | Criterion | Test Method |
|---|-----------|-------------|
| AC-1 | `doc_04d.py` no longer exports `_RACI_BY_DOMAIN` or `_STAKEHOLDER_COLUMNS` | grep + pytest |
| AC-2 | All 10 D-XX rendered in §6 as table (if YAML exists) or info-only note (if missing) | pytest 3 cases |
| AC-3 | No person names in `04d_Org_Roles_RACI.md` output (no `Founder`, `CEO acting as`, `CTO as`, `Lead Developer`, `2 founders`) | pytest regex |
| AC-4 | Stakeholder leakage test (existência) ainda PASS | pytest |
| AC-5 | Full v2 suite unchanged (no new regressions in non-infra tests) | pytest |
| AC-6 | Case 3 (MAX) §6 has ≥7 capability rows (D-01..D-04 + sample) | pytest render |
| AC-7 | §6 prose intro present (mentions "capabilities" + "out of scope") | pytest render |

### Edge Cases

| # | Edge Case | Expected Behavior |
|---|-----------|-------------------|
| EC-1 | `load_capabilities(D-XX)` returns `{}` (missing YAML) | Info-only note in §6 for that D-XX |
| EC-2 | YAML malformed | Info-only note (C3 fallback propagates) |
| EC-3 | Capability has no `obligations` field | Table row shows `—` in Regulation Anchor column |

### Error Scenarios

| # | Error | Expected Behavior |
|---|-------|-------------------|
| ES-1 | `load_capabilities()` raises | Caught by `data/loader.py` (silent `{}`) — never reaches renderer |

---

## Testing Strategy

| Level | What to Test | Method |
|-------|-------------|--------|
| Unit | Section renders, no person names, capability list correct | pytest in `tests/unit/v2/output/` |
| Regression | Stakeholder leakage test, full v2 suite | pytest |
| Manual | Inspect 3 cases' `04d_Org_Roles_RACI.md` for human verification | output redirect |

---

## Open Questions

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| Q1 | What's the new doc filename? | Keep `04d_Org_Roles_RACI.md` for backward compatibility (PDF parsers, Phase 2B ingest). Add deprecation note in frontmatter. |

---

## References

- `execution/SPEC.md` — CORR-074 spec (predecessor)
- `execution/CONTRACT-074.md` — capabilities catalog delivery
- `execution/contracts/SC-2026-17.json` — CORR-074 contract
- `execution/CORR-073.md` — data-driven pipeline extraction
- `src/aegis_phase1/data/loader.py:load_capabilities`
- `src/aegis_phase1/v2/output/doc_04d.py` — to be modified

---

## Sign-off

- [x] Requirements reviewed (per-utilizador 2026-07-29)
- [x] Architecture decisions approved (per-utilizador)
- [x] Acceptance criteria validated
- [ ] Ready for contract generation
