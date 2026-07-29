# SPEC — LLM prompts rewritten in functional vocabulary (no person names)

**Spec ID:** SP-2026-19
**Date:** 2026-07-29
**Author:** Planner (opencode / MiniMax-M3)
**Status:** DRAFT
**Level:** spec-first

---

## Context

### Problem Statement

CORR-074 delivered `load_capabilities()` + `ROLE_VOCABULARY` (5 functions: DPO, CISO, Engineering, Operations, Governance). CORR-075 removed the RACI table from doc_04d. But 9 LLM narrative-prompts still ask the model to describe companies in terms of people ("Founder #1", "CEO acting as DPO", "Lead Developer", "2 founders"). At a 5000-employee bank, the LLM produces nonsense — the bank doesn't have 2 founders. The user explicitly demanded in plan-mode (2026-07-29): zero person names anywhere in role-bearing prose.

This contract rewrites the 9 LLM prompts to inject a functional context block (roles + applicable capabilities) and remove person-name references.

### Current State

9 identified prompt functions:

| # | Function | File | Used by section |
|---|----------|------|-----------------|
| 1 | `_reporting_lines_prompt` | `src/aegis_phase1/v2/output/doc_04d.py:932` | doc_04d §5 Reporting Lines |
| 2 | `_escalation_prompt` | `src/aegis_phase1/v2/output/doc_04d.py:946` | doc_04d §9 Escalation Paths |
| 3 | `_risk_narrative_prompt` | `src/aegis_phase1/v2/output/doc_04c.py:642` | doc_04c §5.1 Concentration Risk |
| 4 | `_technical_architecture_prompt` | `src/aegis_phase1/v2/output/doc_04a.py:1004` | doc_04a §1 Technical Architecture |
| 5 | `_network_topology_prompt` | `src/aegis_phase1/v2/output/doc_04a.py:1016` | doc_04a §1.2 Network Topology |
| 6 | `_strategic_prompt` | `src/aegis_phase1/v2/output/doc_05.py:966` | doc_05 §6.1 Strategic Narrative |
| 7 | `_strategic_prompt` | `src/aegis_phase1/v2/output/doc_07.py:764` | doc_07 §6.1 Strategic Narrative |
| 8 | `_cross_check_prompt` | `src/aegis_phase1/v2/output/doc_07b.py:664` | doc_07b §5.1 Narrative |
| 9 | `_domain_notes_prompt` | `src/aegis_phase1/v2/output/doc_04b.py:1092` | doc_04b §3 Per-Domain Notes (called 10 times) |

All 9 prompts mention "Founder", "CEO acting as", "CTO as", "Lead Developer", or "2 founders" in the prompt body. The LLM is then asked to produce prose that includes these phrases.

### Target State

- Each prompt function takes a `tier` and `applicable_regs` (or accepts `state` and derives them) and prepends a **functional context block** listing:
  - The 5 functions in `ROLE_VOCABULARY` (`DPO`, `CISO`, `Engineering`, `Operations`, `Governance`).
  - Tier-scaled role roster from `data/role_models/{tier}.yaml` (only role titles, no person names).
  - Applicable capabilities from `data/capabilities/` for the applicable regulations.
- Explicit instruction: "**DO NOT name individuals**. Use function names only."
- Phrases removed: `Founder`, `CEO acting as`, `CTO as`, `Lead Developer`, `2 founders`, `acting as DPO`, `acting as CISO`.
- The 9 prompts downstream behaviour unchanged (still produce prose prose, still deterministic fallback when no LLM).

---

## Requirements

### Functional Requirements

| # | Requirement | Priority | Rationale |
|---|-------------|----------|-----------|
| FR-1 | Add `_functional_context_block(tier, applicable_regs)` helper in `src/aegis_phase1/v2/output/_functional_prompts.py` (new module) | MUST | Single source for the injected block |
| FR-2 | All 9 prompts prepend the functional context block before the existing narrative instructions | MUST | Uniform treatment |
| FR-3 | Prompts explicitly forbid person names: "DO NOT name individuals (no Founder, CEO acting as, CTO as, Lead Developer, 2 founders)" | MUST | User explicit |
| FR-4 | No targeted phrase appears in any of the 9 prompts | MUST | Verification gate |
| FR-5 | `render_mandatory_narrative` and `render_doc_XX` functions unchanged in signature | MUST | No call-site changes |
| FR-6 | When `applicable_regs` is empty or tier is missing, helper returns minimal block (no error) | MUST | Robustness |

### Non-Functional Requirements

| # | Requirement | Priority | Rationale |
|---|-------------|----------|-----------|
| NFR-1 | No new third-party dependencies | MUST | Stdlib + existing data/loaders only |
| NFR-2 | Helper cacheable on (tier, applicable_regs) tuple | SHOULD | Performance (called 10× in doc_04b) |

### Constraints

- 9 prompt functions are split across 5 files (`doc_04a`, `doc_04b`, `doc_04c`, `doc_04d`, `doc_05`, `doc_07`, `doc_07b`). Each must be modified at its call site.
- The helper module cannot import from `data/loader.py` circularly; locate it in `src/aegis_phase1/v2/output/_functional_prompts.py` and import `data/loader.py` lazily inside the helper.
- Renderer behaviour unchanged: when LLM is unavailable, the deterministic fallback still triggers (helpers don't replace the prompt-build call).
- ROLE_VOCABULARY is the only allowed function vocabulary; no synonyms (e.g., "IT", "Security Team") in the block.

---

## Architecture Decisions

### Decision 1: New module `_functional_prompts.py` (not inline edits)

- **Context:** 9 prompts across 5 files. A shared helper avoids duplication.
- **Options:** (A) New module `_functional_prompts.py` with helper; each prompt prepends the helper output. (B) Inline edit each prompt. (C) Subclass `Phase1LLMInvoker` to inject context.
- **Decision:** A — new module.
- **Rationale:** Single source-of-truth; easy to test the helper in isolation; no LLM invoker changes.
- **Consequences:** 9 callers updated to prepend the block. ~5 lines each.

### Decision 2: Helper takes tier + applicable_regs, not full state

- **Context:** The call sites already have access to `state["company_context"]`; the helper just needs the function roster and applicable capabilities.
- **Options:** (A) Helper takes `tier: str, applicable_regs: list[str]`; (B) Helper takes `state: dict` and derives internally.
- **Decision:** A — explicit parameters.
- **Rationale:** Easier to test (no state construction needed); deterministic output for a given (tier, applicable_regs).
- **Consequences:** Each call site must extract `tier` and `applicable_regs` from `state` before calling the helper.

### Decision 3: Capability list is filtered by applicable_regs

- **Context:** Some capabilities are tied to specific regulations (e.g., `CAP-D01-001` "Encryption at rest" maps to GDPR Art. 32 + CRA Annex I). LLM should only see capabilities for the applicable regs.
- **Options:** (A) Filter by `applicable_regs` (intersection); (B) Show all capabilities regardless.
- **Decision:** A — filter.
- **Rationale:** Minimises prompt size; keeps the LLM focused on what's relevant.
- **Consequences:** For D-XX domains with no `applicable_regs` in capability YAML, no capability is shown. Capability YAML `obligations` field is the filter source.

### Decision 4: Helper is best-effort silent on missing data

- **Context:** If `data/capabilities/{D-XX}.yaml` is missing, the loader returns `{}`. The helper should not crash.
- **Options:** (A) Skip the capability row silently; (B) Emit a placeholder line.
- **Decision:** A — skip.
- **Rationale:** Matches the user's "info-only" policy (CORR-074 decision #3). Capabilities are informational.
- **Consequences:** Helper always returns a valid string; never raises.

---

## Data Model

No new entities. Reuses:
- `ROLE_VOCABULARY` (CORR-074)
- `load_capabilities(domain_id)` (CORR-074)
- `load_role_model(tier)` (CORR-073)
- `classify_tier(employees, sector, applicable_regs)` (CORR-073)

---

## API / Interface Design

### New module

```python
# src/aegis_phase1/v2/output/_functional_prompts.py
def build_functional_context(tier: str, applicable_regs: list[str]) -> str:
    """Return functional context block to prepend to LLM prompts.
    
    Returns empty string when ROLE_VOCABULARY is empty (defensive).
    """
```

### Output format

```
Functional roles available (DO NOT name individuals):
- {role_1_title} (reports to {reports_to}, FTE {fte})
- {role_2_title} (reports to {reports_to}, FTE {fte})
...

Capabilities required by applicable regulations:
- {cap_id}: A={a_function}, R={r_function} ({title})
- {cap_id}: A={a_function}, R={r_function} ({title})
...
```

### Function signatures (unchanged)

```python
def _reporting_lines_prompt(state: dict[str, Any]) -> str: ...   # doc_04d
def _escalation_prompt(state: dict[str, Any]) -> str: ...        # doc_04d
def _risk_narrative_prompt(state, cloud, rows) -> str: ...        # doc_04c
def _technical_architecture_prompt(state, inventory, summary) -> str: ...  # doc_04a
def _network_topology_prompt(state, inventory) -> str: ...       # doc_04a
def _strategic_prompt(state, rows) -> str: ...                   # doc_05, doc_07
def _cross_check_prompt(state, rows) -> str: ...                 # doc_07b
def _domain_notes_prompt(domain_id, current, target, gap, controls, state) -> str: ...  # doc_04b
```

Each internally prepends the functional context block.

---

## Implementation Plan

### Phase Overview (single phase)

| Phase | Name | Scope | Depends On |
|-------|------|-------|------------|
| 1 | Helper + 9-prompt refactor | New module + 5 file edits | CORR-074, CORR-075 |

### File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/aegis_phase1/v2/output/_functional_prompts.py` | create | New helper module |
| `src/aegis_phase1/v2/output/doc_04a.py` | modify | `_technical_architecture_prompt` + `_network_topology_prompt` prepend context |
| `src/aegis_phase1/v2/output/doc_04b.py` | modify | `_domain_notes_prompt` prepends context (called 10×) |
| `src/aegis_phase1/v2/output/doc_04c.py` | modify | `_risk_narrative_prompt` prepends context |
| `src/aegis_phase1/v2/output/doc_04d.py` | modify | `_reporting_lines_prompt` + `_escalation_prompt` prepend context |
| `src/aegis_phase1/v2/output/doc_05.py` | modify | `_strategic_prompt` prepends context |
| `src/aegis_phase1/v2/output/doc_07.py` | modify | `_strategic_prompt` prepends context |
| `src/aegis_phase1/v2/output/doc_07b.py` | modify | `_cross_check_prompt` prepends context |
| `tests/unit/v2/output/test_functional_prompts.py` | create | Tests for the helper + 9-prompt regression |
| `execution/CONTRACT-076.md` | create | Contract document |

---

## Acceptance Criteria

### High-Level Criteria

| # | Criterion | Test Method |
|---|-----------|-------------|
| AC-1 | None of 9 prompts contains banned phrases: `Founder`, `CEO acting as`, `CTO as`, `Lead Developer`, `2 founders`, `acting as DPO`, `acting as CISO` | pytest grep |
| AC-2 | Each of the 9 prompts contains `ROLE_VOCABULARY` (or "DPO, CISO, Engineering, Operations, Governance") in the injected block | pytest regex |
| AC-3 | Each of the 9 prompts contains "DO NOT name individuals" (or equivalent) in the injected block | pytest regex |
| AC-4 | `_functional_prompts.build_functional_context(tier, applicable_regs)` returns deterministic string for same inputs | pytest |
| AC-5 | For empty applicable_regs, helper returns non-empty block with role roster only | pytest |
| AC-6 | For tier with sufficient role model (MICRO..MAX), the role roster lists FTE/reports_to for each role | pytest |
| AC-7 | Existing full v2 suite still green (no new regressions vs main baseline) | pytest |
| AC-8 | Existing stakeholder leakage test + capability-summary test still PASS | pytest |
| AC-9 | `legacy_qa_runner.py` (or equivalent manual smoke) still produces 9 markdown files in 4 cases; no schema break | shell |

### Edge Cases

| # | Edge Case | Expected Behavior |
|---|-----------|-------------------|
| EC-1 | `applicable_regs = []` | Helper returns role roster only (no capability block) |
| EC-2 | `tier = "UNKNOWN"` | Helper falls back to MICRO or empty block |
| EC-3 | A capability YAML has no `obligations` field | Capability is excluded from the block (no reg mapping) |
| EC-4 | A capability YAML has `obligations: {reg: [...]}` but `reg` not in applicable_regs | Capability is excluded |

### Error Scenarios

| # | Error | Expected Behavior |
|---|-------|-------------------|
| ES-1 | `load_capabilities()` raises | Helper catches silently, skips that domain |
| ES-2 | `load_role_model()` raises | Helper falls back to empty role roster, continues |

---

## Testing Strategy

| Level | What to Test | Method |
|-------|-------------|--------|
| Unit | Helper deterministic output, empty case, banned-phrase absence | pytest in `tests/unit/v2/output/` |
| Regression | Existing 9-prompt calls still produce non-empty prompt strings | pytest |
| Manual | Inspect rendered docs to confirm no person names in output | shell |

---

## Open Questions

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| Q1 | Where does the helper live? | `src/aegis_phase1/v2/output/_functional_prompts.py` (new module) |
| Q2 | Mirroring across `doc_05.py` and `doc_07.py` (both define `_strategic_prompt`)? | Each file keeps its own function; both call the helper |

---

## References

- `execution/SPEC.md` (CORR-075 spec — predecessor)
- `execution/contracts/SC-2026-17.json` (CORR-074 contract — capabilities catalog)
- `execution/contracts/SC-2026-18.json` (CORR-075 contract — Capabilities wired into Doc 04d)
- `src/aegis_phase1/data/loader.py` — `load_capabilities`, `load_role_model`, `ROLE_VOCABULARY`

---

## Sign-off

- [x] Requirements reviewed (per-utilizador 2026-07-29)
- [x] Architecture decisions approved
- [x] Acceptance criteria validated
- [ ] Ready for contract generation
