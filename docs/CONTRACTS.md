---
document_id: AEGIS-DOCS-CONTRACTS
title: AEGIS Contracts Master Index
phase: Cross-phase (reference)
version: 1.0
created: 2026-07-14
author: Orchestrator
status: ACTIVE
related_documents:
  - ../.hooks/validate-contracts.sh
  - ../LLM_ARCHITECTURE_DECISION.md
  - ../../AGENTS.md (Branch Policy §10)
---

# AEGIS Contracts Master Index

> **Purpose.** This document tracks every implementation contract in the `aegis-phase1` repository: its scope, status, branches, main commit, test count, and key decisions. Updated as new contracts are MERGED.

---

## How to read this index

- **Status legend**:  🟢 MERGED | ✅ MERGED | ❌ ABANDONED | ⏸ DEFERRED
- **Branch legend**: 🟢 active | ⚫ deleted (after merge) | ⚠️ stale
- **Tests**: number of passing v2 unit tests at the time of merge

---

## Contracts

| Contract | Phase | Status | Branch | Main commit | Tests | Story |
|---|---|---|---|---|---|---|
| [AEGIS-P1-CORR-001](#corr-001) | Rebranding + 7-phase consolidation | ✅ MERGED | ⚫ deleted | `7e6c8b8` | 174 | Consolidation after Phase 0–6 fragments lost; established 1-branch-per-contract policy |
| [AEGIS-P1-CORR-002](#corr-002) | REDUCE synthesis wire-up | ✅ MERGED | ⚫ deleted | `2c43064` | 188 | Wired P1C-LLM-03 + P1C-LLM-02 into `Phase1Orchestrator.reduce()`; rendered Doc 07 §5.2/§6.2 |
| [AEGIS-P1-CORR-002-fix](#corr-002-fix) | LLM context size correction | ✅ MERGED | ⚫ deleted | `f624c24` | 188 | Corrected `gemma4:e4b` context from 5K to 32K in `LLM_ARCHITECTURE_DECISION.md` |
| **AEGIS-P1-CORR-003** | Validator cleanup + adapter fix + CI gate |  🟢 MERGED | 🟢 `feature/aegis-p1-corr-003` | TBD | 194 | Re-validated CORR-002 with correct signatures; fixed invoker bypass; pre-push hook script |
| [AEGIS-P1-CORR-004](#corr-004) | Wire P1B-LLM-02 RATIONALE | ✅ MERGED | ⚫ deleted | TBD | 206+ | Wired per-regulation rationale synthesis into Phase1Orchestrator; rendered into Doc 05 §6.1b |
| **AEGIS-P1-CORR-005** | Rename layer0_* → regulatory_baseline_* | 🚧 IN PROGRESS | 🟢 `feature/aegis-p1-corr-004` | TBD | 329 | Hard rename with backwards-compat aliases; wire-protocol keys deferred (Methodology-main scope) |

---

## <a name="corr-001"></a>AEGIS-P1-CORR-001 — Rebranding + 7-Phase Consolidation

### Scope
Rebranding "Layer 0" → "Regulatory Baseline"; consolidating 7 phase branches into 1; AGENTS.md §10 (Branch Policy + Pre-flight Check).

### Decisions
- **1 branch per contract** — phases become commits, not branches
- **Pre-flight check** before subagent dispatch
- **Validator integrity rule** — surface collection errors via `--co -q | grep ERROR`

### Merged: 2026-07-14

---

## <a name="corr-002"></a>AEGIS-P1-CORR-002 — REDUCE Synthesis Wire-up

### Scope
Wire `Phase1Executor.run_phase_1c_reduce()` into `Phase1Orchestrator.reduce()`; render Doc 07 §5.2 (compound events from P1C-LLM-02) and §6.2 (strategic implications from P1C-LLM-03) with PENDING REVIEW markers; add 2 gate rows.

### Decisions
- **Hybrid Option B**: retain 8 mandatory narrative sections + add 2 REDUCE LLMs
- **PENDING REVIEW** on failure (never silent fallback)
- **Doc 07 §5.2** = LLM compound events; **§6.2** = LLM strategic synthesis

### Merged: 2026-07-14

---

## <a name="corr-002-fix"></a>AEGIS-P1-CORR-002-fix — gemma4:e4b Context Correction

### Scope
Correct `LLM_ARCHITECTURE_DECISION.md` warning about `gemma4:e4b` context. Was stated as 5K, actually 32K (num_ctx=32768 in `src/aegis_phase1/v2/llm.py`).

### Merged: 2026-07-14 (commit on main, no separate branch)

---

## <a name="corr-003"></a>AEGIS-P1-CORR-003 — Validator Cleanup + Adapter Fix + CI Gate

### Scope
- **Phase A (T2)**: Fix `Phase1Orchestrator._get_phase1_executor()` invoker bypass — now reads `model` from `self.llm_invoker` instead of env var
- **Phase B (T3)**: Create `.hooks/validate-contracts.sh` (9 contract checks) + `.git/hooks/pre-push` installer
- **Phase C (T4)**: This document

### Decisions
- **Architectural fix over conservative warning** for T2 (Phase A)
- **Pre-push hook over pre-commit** for T3 (less intrusive, allows local iteration)
- **Master index for contract traceability** for T4

### In Progress as of 2026-07-14

---

## <a name="corr-004"></a>AEGIS-P1-CORR-004 — Wire P1B-LLM-02 RATIONALE

### Scope
- Add `Phase1Orchestrator.run_phase_1b()` method (~170 lines)
- Call between MAP and REDUCE in `run_all()` (5-stage pipeline: LOAD → MAP → PHASE_1B → REDUCE → OUTPUT)
- Render per-regulation rationale + implications + gaps into Doc 05 §6.1b
- Add `--skip-phase-1b` CLI flag
- Add Check 10 to validate-contracts.sh

### Decisions
- **§6.1b layout**: NEW section (don't replace §6.1 deterministic)
- **N LLM calls** (one per applicable_reg): accepted; documented; --skip-phase_1b for fast iteration
- **PENDING REVIEW** marker on failure (never silent fallback)
- **Backwards-compat**: P1B-LLM-01 output not yet wired (--no --skip Phase 1B can still run)

### LLM calls/case after CORR-004
- 10 (MAP adapted_objective)
- N (Phase 1B RATIONALE, one per applicable_reg)
- 2 (REDUCE: P1C-LLM-03 + P1C-LLM-02)
- 8 (mandatory narrative sections from CORR-004 + earlier)
- **Total**: 20 + N LLM calls per case

### In Progress as of 2026-07-14 (merged same day)

---

## <a name="corr-005"></a>AEGIS-P1-CORR-005 — Rename layer0_* → regulatory_baseline_*

### Scope
- Hard rename `layer0_refs` → `regulatory_baseline_refs` (JSON field name)
- Hard rename `layer0_relationship` → `regulatory_baseline_relationship`
- Hard rename `layer0_root` (Python attr) → `regulatory_baseline_root`
- Hard rename `get_layer0_root()` → `get_regulatory_baseline_root()` (function name)
- Keep backwards-compat aliases for Python (emit DeprecationWarning)

### Decisions
- **Option B.1 chosen**: hard rename for JSON field names (single producer internal)
- **Alias pattern** for Python identifiers (function names, params)
- **Wire-protocol keys deferred**: `layer0_catalog` and `layer0_subdomain_refs` kept
  in 3 files because they serialize into prompts that live in `Methodology-main/`
  (sibling repo, out of this contract's scope). Future contract owns PROMPTS-side rename.

### In Progress as of 2026-07-14

### Known limitations (updated)
- **Wire-protocol constraint**: 3 files still use `layer0_catalog` / `layer0_subdomain_refs`
  in `invoker.invoke(inputs=...)` payloads. Renaming them in this contract would
  silently break the rendered PROMPTS templates (different repo).
  Deferred to a future contract that owns PROMPTS-side renames.
- **Documentation references**: `docs/CONTRACTS.md`, `docs/LLM_ARCHITECTURE_DECISION.md`,
  `docs/prompts_v2_usage.md` still mention old names in historical context.
  New documents use new names.

---

## Repository stats (as of CORR-003 T4 creation)

| Metric | Value |
|---|---|
| Python source files in `src/aegis_phase1/v2/` | 50 |
| v2 unit tests collected | 194 |
| v2 unit tests passing | 194 |
| Test growth since CORR-002 | +6 (3 invoker bypass + 3 validate-contracts) |

---

## Pending decisions (P7)

| # | Topic | Decision needed | Status |
|---|---|---|---|
| 1 | P1B-LLM-01 INTERPRETATION wire-up | Separate contract? | Open |
| 2 | P1B-LLM-02 RATIONALE wire-up | **✅ MERGED via CORR-004** | Closed |
| 3 | P1C-LLM-01 OVERLAP-CLASSIFICATION wire-up | Separate contract? | Open |
| 4 | JSON Schema field renaming `layer0_refs` → `regulatory_baseline_refs` | **✅ MERGED via CORR-005** | Closed |
| 5 | Case_02 / Case_03 rebranding in `Methodology-main` | Separate contract? | Open |
| 6 | Switch Ollama → remote `MiniMax-M2.7` | Separate contract with API key handling | Open |

## Known limitations

- **Adapter design**: The `_get_phase1_executor()` fix (CORR-003 Phase A) reads `model` from `self.llm_invoker` but still creates a fresh `Phase1LLMInvoker` via `get_invoker()`. A full adapter (single invoker for both stages) would require refactoring `Phase1LLMInvoker` to accept `MockInvoker`/`OllamaInvoker` via duck-typing — deferred.
- **CI gate only runs on push**: `validate-contracts.sh` is wired to `pre-push` only. For team-scale CI, GitHub Action integration is future work.
- **Methodology-main contracts**: This index only covers `aegis-phase1` repo. `Methodology-main` has its own contracts (rebranding was a sub-step of CORR-001 but covered there).

## See also

- `.hooks/validate-contracts.sh` — the script enforcing these contracts
- `LLM_ARCHITECTURE_DECISION.md` — strategic decision doc that motivates CORR-002
- `AGENTS.md §10` — Branch Policy + Pre-flight Check policy
