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
| [AEGIS-P1-CORR-005](#corr-005) | Rename layer0_* → regulatory_baseline_* | ✅ MERGED | ⚫ deleted | TBD | 329 | Hard rename with backwards-compat aliases; wire-protocol keys deferred (Methodology-main scope) |
| [AEGIS-P1-CORR-006](#corr-006) | Sequential wizard replaces hub-spoke menu | ✅ MERGED | ⚫ deleted | `fbfb77f` | 217 | Replaced 9-option menu with 6-step linear wizard; legacy `run_menu` kept as 1-release deprecation alias |
| **AEGIS-P1-CORR-007** | beaupy.select wizard + static case catalogue | ✅ MERGED | ⚫ deleted | TBD | 218 | Replaced input()-based prompts with beaupy.select(); 4-step wizard; static catalogue of 3 Methodology-main cases |
| **AEGIS-P1-CORR-008** | Wizard beaupy fix + integration smoke gate (+ run_all fix) | 🚧 IN PROGRESS | 🟢 `feature/aegis-p1-corr-008` | TBD | TBD | Fix `pre_selected=`→`cursor_index=` (4 sites); harden mocks with `assert_called_with`; add integration smoke (beaupy signature + runner subprocess non-TTY) + `scripts/test-quick.sh`; **Phase F user-discovered: fix `_run_pipeline` forwarding args to `orch.run_all(case_path=…)`** |

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

## <a name="corr-006"></a>AEGIS-P1-CORR-006 — Sequential Wizard Replaces Hub-Spoke Menu

### Scope
- Replace 9-option hub-and-spoke menu in `src/aegis_phase1/v2/cli/menu.py` with
  linear 6-step wizard (`run_wizard()`)
- One question at a time; Enter accepts default at every step
- Steps: Case directory → Regulatory Baseline → Mode (Mock/Real) →
  Model (only if Real) → Skip flags → Run? [Y/n]
- Keep `run_menu()` as one-release backwards-compat alias (emits
  DeprecationWarning, delegates to `run_wizard`)
- Remove legacy `build_menu()` and `_resolve_menu_choice()`
- Add 4 new CI gate checks (13-16) to `validate-contracts.sh`

### Decisions
- **Linear, no Back**: simpler than a Back-navigable wizard; user can Ctrl+C
- **5-6 questions**: configuration complete (case, baseline, mode, model,
  skip flags, run confirmation); not ultra-minimal
- **Remove old menu**: `build_menu()` and `_resolve_menu_choice()`
  deleted; `run_menu()` kept as deprecated alias only
- **Defaults work for Case_01**: TinyTask paths auto-detected

### Wizard flow (user-facing)
```
[1/6] Case directory             [default: .../Case_01_TinyTask_SaaS]
[2/6] Regulatory Baseline dir    [default: .../00_METHODOLOGY/PREPROCESSING]
[3/6] Mode                       [1=mock / 2=real]
[4/6] Model                      [gemma4:e4b]  (only shown if Real)
[5/6] Skip flags                 [defaults: no, no]
[6/6] Run pipeline?              [Y/n]
```

### CI gate additions
- Check 13 (critical): Sequential wizard is default
- Check 14 (critical): Legacy `build_menu()` removed
- Check 15 (critical): `runner.py` invokes `run_wizard`
- Check 16 (warn): `run_menu()` backwards-compat alias preserved

### In Progress as of 2026-07-14

> Superseded by **AEGIS-P1-CORR-007** (next section): the wizard was redesigned around `beaupy.select` for arrow-key navigation, the case catalogue was made static (3 Methodology-main cases + local option removed), and Regulatory Baseline became auto-detected.

---

## <a name="corr-007"></a>AEGIS-P1-CORR-007 — beaupy.select Wizard + Static Case Catalogue

### Scope
- Replace `input()`-based prompts with `beaupy.select()` (arrow-key navigation)
- Reduce wizard from 6 steps to 4 (removed explicit Regulatory Baseline + Skip flags prompts; auto-detected defaults)
- Static case catalogue (3 Methodology-main cases) instead of dynamic filesystem scan
- Removed: `_read_applicable_regs()` (no longer needed with static catalogue)

### Decisions
- **Static > dynamic catalogue**: User asked to "not search automatically, leave it static"
- **No local case**: Removed `cases/case1-tinytask/` from catalogue per user request
- **Auto-detect Regulatory Baseline**: walks up from case path to find sibling `Methodology-main/00_METHODOLOGY/PREPROCESSING`
- **beaupy.select for everything**: arrow-key UX, validation handled by library

### Wizard flow (user-facing)
```
[1/4] Select case
  > Case 01 - TinyTask SaaS (GDPR, CRA)
    Case 02 - SecureBorder (GDPR, CRA, NIS2, AI Act)
    Case 03 - OmniBank (GDPR, CRA, NIS2, DORA, AI Act)
    Custom path...
[2/4] Select mode
  > Mock (no Ollama, fast)
    Real (Ollama + gemma4:e4b)
[3/4] Select model       (only if Mode=Real)
  > gemma4:e4b
    gemma4:e2b
    Custom...
[4/4] Confirm
  > Run pipeline
    Cancel
```

### CI gate additions
- Check 17 (critical): Wizard uses `beaupy.select`
- Check 18 (critical): Static case catalogue has 3 cases
- Check 19 (critical): `run_wizard()` importable and callable

### Merged 2026-07-15 (commit `cce9a11`)

_Post-merge fix: see AEGIS-P1-CORR-008 — `pre_selected` kwarg fix + smoke gate added after merge._

---

## <a name="corr-008"></a>AEGIS-P1-CORR-008 — Wizard beaupy fix + Integration Smoke Gate (+ run_all fix)

### Scope
- Fix `pre_selected=` → `cursor_index=` in `src/aegis_phase1/v2/cli/menu.py` (4 wizard-step sites). Installed `beaupy==3.12.0` signature uses `cursor_index=`.
- Harden wizard unit mocks with `assert_called_with(options=..., cursor_index=0)` and a global `for c in mock.call_args_list: assert "pre_selected" not in c.kwargs`.
- Add 2 integration smoke tests under `tests/integration/`: signature+AST check + subprocess `python -m aegis_phase1.v2.runner` non-TTY.
- Add `scripts/test-quick.sh` standalone gate.
- **Phase F (user-discovered mid-contract):** fix `_run_pipeline(...)` in `src/aegis_phase1/v2/cli/menu.py:211` calling `orch.run_all()` without forwarding its already-received `case_path`, `regulatory_baseline_path`, `output_dir`. Correct call: `paths = orch.run_all(case_path=case_path, regulatory_baseline_path=regulatory_baseline_path, output_dir=output_dir)`. Bug surfaced only when the wizard actually reached the Confirm step in a real TTY — existing unit tests mock `orch.run_all`, so they passed through.

### Decisions
- **Single gate, not 3.** Smoke at `scripts/test-quick.sh` + pytest integration suite. Skipped CI gate 20–22.
- **MUST keep failing fast.** Subprocess smoke asserts stderr does NOT contain `"pre_selected"`.
- **Hardened mocks, not removed mocks.** Behavior now validated explicitly via `assert_called_with` plus a global kwarg-absence guard.
- **Phase F added mid-contract.** Orchestrator raised reasoned disagreement (P0): two distinct bugs in one contract complicates revert/bisect. User explicitly overrode; logged here for the record.

### Test additions
- OC1/OC2: kwarg sites in `menu.py` (grep gate)
- OC3: ≥5 `assert_called_with(options=...)` in wizard tests
- OC4: AST walk over `menu.py` against `beaupy.select` signature
- OC5: subprocess `runner` non-TTY → exit 0 + TTY message + no `pre_selected` in stderr
- OC6: `scripts/test-quick.sh` standalone
- OC9: unit test asserting `_run_pipeline(orch, case_path=..., regulatory_baseline_path=..., output_dir=...)` forwards `case_path`/`regulatory_baseline_path`/`output_dir` as kwargs to `orch.run_all`. Uses `MagicMock` only — does NOT invoke the real orchestrator.

### Gates reaffirmed
- No smoke test calls `orch.run_all()` for real.
- All LLM-touching paths remain gated behind Mock mode or real-orchestrator mocks.

### In Progress as of 2026-07-16

---

## Repository stats (as of CORR-003 T4 creation)

| Metric | Value |
|---|---|
| Python source files in `src/aegis_phase1/v2/` | 50 |
| v2 unit tests collected | 218 |
| v2 unit tests passing | 218 |
| Test growth since CORR-002 | +24 (3 invoker bypass + 3 validate-contracts + 12 phase_1b + 5 doc_05_rationale + 12 wizard menu − 11 reorganized) |

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
