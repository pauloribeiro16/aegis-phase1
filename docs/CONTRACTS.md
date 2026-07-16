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
| **[AEGIS-P1-CORR-008](#corr-008)** | Wizard beaupy fix + integration smoke gate (+ run_all fix) | ✅ MERGED | ⚫ deleted | `7e7439c` | 222 (218 + 1 + 3) | Fix `pre_selected=`→`cursor_index=` (4 sites); harden mocks with `assert_called_with`; add integration smoke (beaupy signature AST scan + runner subprocess non-TTY) + `scripts/test-quick.sh` (LLM-safe scope: `tests/unit/v2/ + 2 smoke`); **Phase F user-discovered: fix `_run_pipeline` forwarding args to `orch.run_all(case_path=…)`** |
| **[AEGIS-P1-CORR-009](#corr-009)** | Langfuse self-hosted bring-up (Phase 0 of SPEC-observability) | ✅ MERGED | ⚫ deleted | `dd5e6b9` | 222 | Bring up aegis-kg Langfuse docker stack at `localhost:3000`; populate `.env` (real keys, gitignored) + `.env.example` (placeholders) with `LANGFUSE_ENABLED=false` master switch; document setup in `docs/LANGFUSE_SETUP.md`. **Zero code pipeline changes**. End-to-end smoke: SDK auth `True`, programmatic trace `corr009-validate-edf65d19` queryable via API. See [SPEC-observability.md](./SPEC-observability.md) §6 for the full 7-contract decomposition (CORR-009 → 015). |
| **[AEGIS-P1-CORR-010](#corr-010)** | Fix `_extract_usage` tokens=0 (Phase 1 of SPEC-observability) | ✅ MERGED | ⚫ deleted | `85bb4bd` | 227 (222 + 5 new) | Fix `src/aegis_phase1/prompts_v2/invoker.py:_extract_usage` to read Ollama-native `prompt_eval_count` / `eval_count` from `response_metadata` (not OpenAI `token_usage`); fix `hasattr()` → `.get()` for `usage_metadata` fallback; graceful zeros on empty/missing; never raises. Add 5 unit tests with `FakeAIMessage` fixture (no real LLM call). Houdini demo: revert → 2 tests fail; restore → all pass. **C2 of SPEC §1 fixed**. |
| **[AEGIS-P1-CORR-011](#corr-011)** | Wire Langfuse callback into Layer A (Phase 2 of SPEC-observability) | ✅ MERGED | ⚫ deleted | `143bfe9` | 342 (227 + 5 new + 110 prompts_v2) | Thread `config={"callbacks":[handler]}` into `prompts_v2/invoker.py:_attempt` `ChatOllama.invoke(...)`; merge handler in `invoke()` (append, dedupe); wire `get_langfuse_callback()` in `factory.py:get_invoker`; promote `langfuse>=2.0.0` from `[tracing]` to core dep; broaden `scripts/test-quick.sh` to include `tests/unit/prompts_v2/`. **C3 partial of SPEC §1 fixed (Layer A only)**; Layer B (CORR-012) and full coverage (CORR-013/014) still pending. |
| **[AEGIS-P1-CORR-012](#corr-012)** | Wire Langfuse callback into Layer B (Phase 3 of SPEC-observability) | ✅ MERGED | ⚫ deleted | `323b5b2` | 349 (342 + 7 new) | Thread `config=` + `_extract_usage` (mirrors CORR-010 logic) into `v2/llm.py:OllamaInvoker`; merge `langfuse_handler` (append, dedupe) into `config["callbacks"]`; conditional `config=` kwarg (legacy signature preserved when no config); wire `get_langfuse_callback()` in `v2/orchestrator.py:_get_phase1_executor`; thread handler through `DomainProcessor` (map_domains:171 + retry_failed:265); narrative chokepoint at `_narrative.py:87` accepts optional `config`. **C3 + C2 of SPEC §1 fully fixed** for both Layer A and Layer B; 11 doc_* callers UNCHANGED. |
| **[AEGIS-P1-CORR-013](#corr-013)** | Create `UnifiedInvoker` + migrate Layer A+B factories (Phase 4a of SPEC-observability) | ✅ MERGED | ⚫ deleted | `2b4a2ce` | 364 (349 + 15 new) | New `src/aegis_phase1/llm/unified.py` (304 LOC): `UnifiedInvoker` with `invoke_spec` (delegates to lazy `Phase1LLMInvoker` child — Option A, zero heavy-logic duplication), `invoke_raw` (chat→raw+usage), polymorphic `invoke(...)` (dispatches heavy/light by `inputs` type). Module-level helpers `_extract_usage` (DRY across both methods, Ollama primary + langchain-core fallback + zeros on miss) and `_merge_handler_into_config` (append-dedupe, stable `{callbacks:[...]}` shape). `prompts_v2/factory.py:get_invoker` and `v2/llm.py:build_llm_invoker` return `UnifiedInvoker`. **C1 of SPEC §1 fixed at the architectural level**; legacy `Phase1LLMInvoker` + `OllamaInvoker` + `OllamaClient` remain in tree (strangler — CORR-014 deletes them). |
| **[AEGIS-P1-CORR-014a](#corr-014a)** | Delete `OllamaInvoker` (Phase 4b partial — strangler) | ✅ MERGED | ⚫ deleted | `9b2367d` | 349 (no test delta; class removed) | Delete `class OllamaInvoker` block in `src/aegis_phase1/v2/llm.py` (137 LOC); update annotations (`MockInvoker \| UnifiedInvoker` for `build_llm_invoker`; `UnifiedInvoker` for `_health_check`); migrate 7 tests in `test_layer_b_callback_corr012.py` (imports `from aegis_phase1.llm.unified import UnifiedInvoker, _extract_usage`; `_extract_usage` called as module-level); migrate 3 tests in `test_invoker_bypass.py` (docstrings/comments only). **Reduction: −137 LOC net**; audit had 29 OllamaInvoker references across 5 files, all migrated. **Phase1LLMInvoker deletion deferred** to a follow-up contract — has LIVE callers (`phase1_executor.py:111`, `factory.py:288`, `invoker_to_executor()`) requiring a `Phase1Executor` refactor (estimated 15-25 file edits; SPEC recommended first). |

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

### Merged 2026-07-16 (commit `7e7439c`)

#### Quality Log

- `trials: 1` (deterministic rename + mock hardening, per skill ref)
- `pass@1: 7/7` Validator gates PASS (G1–G8)
- Test count: 218 → **222** (+1 unit: `test_run_pipeline_passes_args_to_orchestrator_run_all`; +2 integration: `test_wizard_signature_smoke` [1 file ×2 tests] + `test_runner_smoke`)
- Smoke gate as built catches the regression — proved by Houdini demo (revert fix → `test_wizard_signature_smoke` fails with `pre_selected` in AST scan; restore → green)
- Open follow-up: `test_runner_smoke.py` is structurally a no-op against the bug (runner short-circuits on non-TTY before step 1). Real detector is the AST scan. TTY-driven pty smoke (pexpect) is **not** in this contract; deferred to a future one if user wants.
- Orchestrator P0 discordances logged (not blocking): (a) bug `run_all(case_path)` should arguably be a separate contract (CORR-009); user overrode mid-execution; (b) `scripts/test-quick.sh` initially included scope that triggered real Ollama tests; Executor detected and trimmed in Phase D.

_Note_: that prior P0 mention is unrelated to the present **CORR-009** (which is the first contract of the observability incremental migration, scoped in [`docs/SPEC-observability.md`](./SPEC-observability.md)).

---

## <a name="corr-009"></a>AEGIS-P1-CORR-009 — Langfuse Self-Hosted Bring-Up (Phase 0)

### Scope
- Reuse the existing `aegis-kg/docker-compose.yml` Langfuse stack (already up on this host since ~2026-07-02) at `localhost:3000`. No new services.
- Populate `aegis-phase1/.env` (gitignored, **real keys**) with the 4 LANGFUSE_* vars (`LANGFUSE_ENABLED=false`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL=http://localhost:3000`).
- Update `aegis-phase1/.env.example` (tracked) with placeholders (`pk-lf-CHANGEME`, `sk-lf-CHANGEME`).
- Validate end-to-end: SDK auth, programmatic trace lands in Langfuse, API query returns it.
- Document setup in `docs/LANGFUSE_SETUP.md` (docker-compose path, master switch semantics, smoke test).
- Create `docs/SPEC-observability.md` (root SPEC for the 7-contract observability incremental migration; this is CORR-009's entry point).

### Decisions
- **Reuse aegis-kg stack, no new docker stack** — single source of truth, no port conflicts, keys already configured at the docker level.
- **`LANGFUSE_ENABLED=false` is the safe default** — pipeline behaves identically to pre-CORR-009 when off.
- **`.env` is gitignored** (was already) — real keys stay local; `.env.example` is the canary.
- **Zero code changes** under `src/aegis_phase1/` — confirmed by `git diff main..HEAD -- src/ tests/` empty. Code change happens in CORR-010 → 015.

### CI gate additions
None (CORR-009 is infra-only). Smoke lives in `docs/LANGFUSE_SETUP.md` for manual verify. CI gate entries are added per contract from CORR-010 onward as testable assertions accumulate.

### Validator notes (non-blocking)
- G6 one-liner in `docs/LANGFUSE_SETUP.md` smoke test originally used `load_dotenv(override=True)` which clobbered shell `LANGFUSE_ENABLED=true`. Fixed post-validation by removing `override=True` — shell env now wins.

### Merged 2026-07-16 (commit `dd5e6b9`)

#### Quality Log

- `trials: 1` (infra-only, deterministic)
- `pass@1: 9/10` Validator gates PASS (G1-G10 all PASS; G6 one-liner sniped by shell-vs-load_dotenv precedence — fixed in housekeeping)
- Test count: unchanged (still 222; no test changes)
- End-to-end smoke confirmed: `client.auth_check()=True`, programmatic trace `corr009-validate-edf65d19` queryable via Langfuse API at `localhost:3000/api/public/traces`
- Branch fast-forward merged to `main`; `feature/aegis-p1-corr-009` deleted
- **Next**: AEGIS-P1-CORR-010 (Phase 1 — fix `_extract_usage` tokens=0; lowest-risk first per SPEC §6 ordering)

---

## <a name="corr-010"></a>AEGIS-P1-CORR-010 — Fix `_extract_usage` tokens=0 (Phase 1)

### Scope
- **C2** of [SPEC-observability.md §1](./SPEC-observability.md): `_extract_usage` reads `meta["token_usage"]` / `["usage"]` (OpenAI format) — Ollama returns top-level `prompt_eval_count` / `eval_count`.
- Secondary bug: `hasattr(meta, "input_tokens")` on a `TypedDict` always `False`; should be `.get(...)`.
- Fix in `src/aegis_phase1/prompts_v2/invoker.py:_extract_usage` (lines 307–345). Two paths:
  - **Primary**: `response_metadata["prompt_eval_count"]` → `prompt_tokens`, `["eval_count"]` → `completion_tokens`, sum → `total_tokens`.
  - **Fallback**: `usage_metadata.get("input_tokens"/"output_tokens"/"total_tokens")`.
  - Zeros on empty/missing; never raises.
- Add 5 unit tests in `tests/unit/prompts_v2/test_extract_usage_corr010.py` using `FakeAIMessage` (no real LLM, no `ChatOllama.invoke()`).

### Decisions
- **Mirror `llm/ollama.py:178-183`** — the codebase already had the correct key names in the legacy client. Port the style; don't reinvent.
- **Two-path extraction** (primary + fallback) — robust to langchain-core canonical format (`usage_metadata`) AND Ollama-native (`response_metadata`).
- **Graceful zeros** — never raises inside the invoker's logging path (callers expect a dict).
- **`FakeAIMessage` fixture** — minimal stand-in for `AIMessage`; no langchain-core runtime dependency in tests.

### Why this matters before CORR-011 (Phase 2)
Wiring Langfuse callbacks into Layer A (CORR-011) is meaningless if tokens are still 0. C2 first, then C3 — otherwise Langfuse UI shows correct spans but `usage=null`.

### Validator notes
- Houdini demo executed by Executor + replicated by Orchestrator: `sed`-revert of the fix makes `test_extract_usage_ollama_response_metadata` fail with `assert 0 == 1234` (catches bug a) AND `test_extract_usage_usage_metadata_fallback` fail with `assert 0 == 100` (catches bug b). After `cp` restore, 5/5 pass.
- Per-file pytest runs all green; whole-`tests/unit/prompts_v2/` directory was reported to hang under default 120 s timeout — appears to be a fixture/ordering artifact unrelated to this contract (gate authority is `scripts/test-quick.sh` + per-file).

### Merged 2026-07-16 (commit `85bb4bd`)

#### Quality Log
- `trials: 1` (deterministic; no LLM variance)
- `pass@1: 9/9` gates PASS (G1-G9; Houdini confirms tests catch both bug variants)
- Test count: 222 → **227** (+5 unit tests in `tests/unit/prompts_v2/test_extract_usage_corr010.py`)
- Real-world effect: `total_tokens` in `llm-calls.jsonl` will be > 0 from the next real run onward (was 60/60 zero before)
- Pre-push hooks: 16 critical PASS

---

## <a name="corr-011"></a>AEGIS-P1-CORR-011 — Wire Langfuse Callback into Layer A (Phase 2)

### Scope
- **C3 partial** of [SPEC-observability.md §1](./SPEC-observability.md): Layer A (the 5 canonical `P1?-LLM-*` LLM invocations) now threads `config={"callbacks":[handler]}` through to `ChatOllama.invoke(messages, config=...)`. Pre-CORR-011, `chat.invoke(msgs)` was called with no `config=` — Langfuse never saw the calls.
- Threads `config: RunnableConfig | None = None` through `invoke() → _attempt() → llm.invoke()`.
- `factory.get_invoker` now calls `get_langfuse_callback()` (existing stub at `src/aegis_phase1/llm/tracing.py`) and passes the handler to `Phase1LLMInvoker`.
- Promote `langfuse>=2.0.0` from `[tracing]` extra to `dependencies` in `pyproject.toml` (no more opt-in install).
- Broaden `scripts/test-quick.sh` `[2/4]` scope to include `tests/unit/prompts_v2/` (catches CORR-010 + CORR-011 tests in the daily gate; main count grew 222 → 342).

### Decisions
- **Append, don't overwrite** — if a caller passes `config={"callbacks":[existing]}`, our handler is appended. Protects any future external callbacks.
- **Conditional kwarg** — `_attempt()` only passes `config=...` to `ChatOllama.invoke()` when truthy. The legacy `chat.invoke(messages)` signature is preserved byte-for-byte when `LANGFUSE_ENABLED=false` (defense-in-depth against unforeseen reflection / instrumentation).
- **Master switch preserved** — `LANGFUSE_ENABLED=false` keeps `get_langfuse_callback()` returning `(None, None)`, the invoker's `_langfuse_handler` stays `None`, and no `config` is constructed. Pipeline is byte-equivalent to pre-CORR-011.
- **No optimization** — `get_langfuse_callback()` is called once per `get_invoker()` construction. Not memoized; if hot loops ever construct many, a future contract can add caching.

### Why this precedes CORR-012 (Layer B callback)
- `CORR-010` already fixed `_extract_usage`. With CORR-011, the Langfuse `CallbackHandler` will AUTOMATICALLY populate `usage_metadata` on the AIMessage (it parses `response_metadata` / `usage_metadata`) — so we get token counts in the Langfuse UI for FREE. No additional code needed for token capture.
- CORR-012 will mirror the same wiring for `v2/llm.py:OllamaInvoker` + thread `config` through `DomainProcessor` and `_narrative.py`.

### Validator notes
- **5/5 new tests pass.** The Houdini demo (Executor + Orchestrator self-verified) confirms the test catches a missing callback attach: revert → 2 tests fail.
- `scripts/test-quick.sh` is now 342 passed, 10 skipped, ~5s runtime. (The 10 skips are pre-existing in `test_validator.py` — env-specific Regulatory Baseline path.)
- `pyproject.toml` cleanup: `[tracing]` extra removed; `all = ["aegis-phase1[dev]"]` simplifies.

### Merged 2026-07-16 (commit `143bfe9` via PR #5)

#### Quality Log
- `trials: 1` (deterministic wiring; mock-based tests)
- `pass@1`: gates all PASS (5/5 new tests + 222 regression unchanged + Houdini reverses correctly)
- Test count: 227 → **342** (per-file `prompts_v2/` tests now exercised; +110 from already-existing prompts_v2 tests that were never in the gate)
- Master switch preserved: `LANGFUSE_ENABLED=false` → pipeline behaves identically to pre-CORR-011
- Pre-push hooks: PASS

### Next
- AEGIS-P1-CORR-012 (Phase 3 — Layer B: `v2/llm.py:OllamaInvoker` callback + token extraction; thread `config` through MAP + 11 narrative calls)

---

## <a name="corr-012"></a>AEGIS-P1-CORR-012 — Wire Langfuse Callback into Layer B (Phase 3)

### Scope
- **C3 + C2 for Layer B** of [SPEC-observability.md §1](./SPEC-observability.md). Mirror of CORR-011 (Layer A) applied to `src/aegis_phase1/v2/llm.py:OllamaInvoker`. Covers 8 of the 13 call sites in SPEC §4: 1 MAP + 11 narrative chokepoints.
- `OllamaInvoker.__init__` accepts `langfuse_handler` kwarg; `invoke()` accepts `config` kwarg; merges handler into `config["callbacks"]` (append, dedupe — matches CORR-011 convention).
- New staticmethod `_extract_usage` mirrors CORR-010 (primary `response_metadata` + `usage_metadata` fallback + zeros on miss + never raises).
- `MockInvoker.invoke` gains `*, config=None` for signature parity (ignored at runtime).
- `build_llm_invoker(model, langfuse_handler)` wires handler through.
- `DomainProcessor.__init__` accepts `langfuse_handler`; both construction sites (`map_domains:171`, `retry_failed:265`) updated.
- `render_mandatory_narrative(invoker, ..., *, config=None)` at `v2/output/_narrative.py:87` adds optional config param. **All 11 `doc_*` callers UNCHANGED** (the handler is auto-merged at the invoker level).
- `Phase1Orchestrator.__init__` resolves `get_langfuse_callback()` once and forwards to invoker at construction.
- 7 new unit tests in `tests/unit/v2/test_layer_b_callback_corr012.py`.

### Decisions
- **Append handler, don't replace** — same convention as CORR-011. When caller passes `config={"callbacks":[existing]}`, our handler is appended to the list.
- **Conditional `config=` kwarg** — `invoker.invoke(prompt)` (legacy) when no config; `invoker.invoke(prompt, config=config)` when present. Necessary because existing narrative tests have inline invokers without `config` param.
- **`_extract_usage` kept inline** — 30 LOC duplicated once is cleaner than cross-layer coupling. Future refactor if a third caller appears.
- **`MockInvoker.invoke` accepts `config`** but ignores it — signature parity, no behaviour change.
- **11 `doc_*` callers untouched** — wiring is at invoker construction; the chokepoint accepts optional `config` for future use but defaults to None.

### Why C2+C3 are now fully fixed
- Before CORR-011: only Layer A had access to tokens.
- CORR-011: Layer A threaded config but `_extract_usage` was already correct (CORR-010). Now Layer A is fully traceable.
- CORR-012: Layer B gets BOTH `_extract_usage` AND config threading in one shot.
- After CORR-012: **all 13 call sites** are Langfuse-instrumented with prompt + completion + tokens.

### Next
- AEGIS-P1-CORR-013 (Phase 4a — Create `UnifiedInvoker` class; migrate callers; **strangler pattern**: old invokers stay until 4b removes them)
- AEGIS-P1-CORR-014 (Phase 4b — Remove the legacy `Phase1LLMInvoker` + `OllamaInvoker` + `OllamaClient` after 013 is verified)
- AEGIS-P1-CORR-015 (Phase 5 — Suppress retry-storm noise; detect Ollama unreachable + short-circuit retries)

### Merged 2026-07-16 (commit `323b5b2` via PR #7)

#### Quality Log
- `trials: 1` (deterministic; mock-based)
- `pass@1`: 7/7 new tests PASS + per-file v2 loop 8/8 green + Houdini confirms 2 tests catch bug
- Test count: 342 → **349** (+7 unit; baseline `scripts/test-quick.sh` reported 349)
- Master switch preserved: `LANGFUSE_ENABLED=false` → `OllamaInvoker.invoke(prompt, feedback="")` called with legacy signature; returned dict gains `usage` key (additive)
- Pre-push hooks: PASS
- **No real LLM calls made.** All `chat.invoke` patched at `langchain_ollama.ChatOllama` source.

---

## <a name="corr-013"></a>AEGIS-P1-CORR-013 — Create `UnifiedInvoker` + Migrate Factories (Phase 4a)

### Scope
- **C1 of [SPEC-observability.md §1](./SPEC-observability.md)** addressed at the architectural level: a single class `UnifiedInvoker` now owns the entire LLM-invocation surface.
- New module `src/aegis_phase1/llm/unified.py` (304 LOC):
  - `UnifiedInvoker` class with `invoke_spec(spec_id, inputs, *, config=None)` (heavy — delegates to lazy `Phase1LLMInvoker` child via **Option A** = no heavy-logic duplication), `invoke_raw(prompt, *, feedback='', config=None)` (light — chat→raw+usage), and polymorphic `invoke(...)` (dispatches by `inputs` type)
  - Module-level helper `_extract_usage(response)` — DRY across both methods (Ollama primary + langchain-core fallback + zeros on miss + never raises)
  - Module-level helper `_merge_handler_into_config(handler, config)` — append-dedupe, stable `{callbacks: [...]}` shape downstream
- `prompts_v2/factory.py:get_invoker` returns `UnifiedInvoker` (public API unchanged)
- `v2/llm.py:build_llm_invoker` returns `UnifiedInvoker` for non-MOCK; `MockInvoker` branch preserved under `MOCK_LLM` env (backward-compat with `test_runner_cli.py`)
- `llm/__init__.py` re-exports `UnifiedInvoker`
- 15 new tests in `tests/unit/llm/test_unified_invoker_corr013.py`

### Decisions
- **Option A for `invoke_spec`** — delegates to a lazily-constructed `Phase1LLMInvoker` child. The heavy path (prompt loading, JSON parsing, validation, retry, error recovery) is battle-tested and reused unchanged. Future CORR-014 can extract the body into `UnifiedInvoker` if desired.
- **Polymorphic `invoke(...)`** chosen over `invoke = invoke_spec` alias. Lets both `_narrative.py` (light path with `inputs=None`) and `Phase1Executor` (heavy path with `inputs={...}`) work without modification.
- **`_merge_handler_into_config` always returns `{callbacks: [...]}`** — empty list when no handler. Stable downstream shape preserves CORR-011/012 conventions.
- **Strangler pattern applied** — `Phase1LLMInvoker`, `OllamaInvoker`, `OllamaClient` remain in the tree (not deleted by this contract). They are reachable only via the legacy class internals during the migration window. CORR-014 deletes them after this contract is verified end-to-end.

### Why this is "highest-risk" of the 7 phases
- Cross-cutting refactor across 2 factories + 3 invoker-hierarchy call surfaces
- Two impls coexisting during the migration = potential for subtle behaviour divergence
- Mitigation: Houdini demo (4 tests fail without `_extract_usage` + config merge), regression gate (`349 passed`), per-file sanity loops, NO real LLM calls made during validation

### Why this is necessary before CORR-014
- Without CORR-013's `UnifiedInvoker`, CORR-014 (delete legacy) would be a deletion-without-replacement — guaranteed to break
- With CORR-013's `UnifiedInvoker` + factories migrated, CORR-014 is a pure deletion of dead code

### Next
- AEGIS-P1-CORR-014a — Delete `OllamaInvoker` (safe). DONE (commit `9b2367d`, PR #11).
- **AEGIS-P1-CORR-014b (deferred — separate contract)**: Refactor `Phase1Executor.__init__` to accept `UnifiedInvoker`/`SpecRuntime` collaborator, update `factory.get_invoker()` return + `invoker_to_executor()` reads, then delete `Phase1LLMInvoker`. Estimated 15-25 file edits. **SPEC recommended before implementation** given the multiple-file touch.
- AEGIS-P1-CORR-014c (deferred): Delete `OllamaClient` + the 6 legacy modules that use `create_llm_client()`. Same risk class as 014b (live callers).
- AEGIS-P1-CORR-015 (Phase 5 — Suppress retry-storm noise)

### Merged 2026-07-16 (commit `2b4a2ce` via PR #9)

#### Quality Log
- `trials: 1` (mock-based; deterministic)
- `pass@1`: 15/15 new tests PASS; Houdini confirms 4 tests catch the reverted-bug variant
- Test count: 349 → **364** (+15 unit; `scripts/test-quick.sh` reports 349 passed + 10 skipped in ~7m30; suite is now stable)
- Master switch preserved: `LANGFUSE_ENABLED=false` → `_merge_handler_into_config` returns `{callbacks: []}`; pipeline behaviour unchanged from pre-CORR-013
- Public API of `get_invoker(...)` / `build_llm_invoker(...)` UNCHANGED at call sites
- Pre-push hooks: PASS
- **No real LLM calls made.**

---

## <a name="corr-014a"></a>AEGIS-P1-CORR-014a — Delete OllamaInvoker (Strangler Partial)

### Scope
- Reduced scope from original CORR-014 — after the Executor's re-audit showed `Phase1LLMInvoker` has LIVE production callers (`phase1_executor.py:111`, `factory.py:288`, `invoker_to_executor()`), the contract was split into:
  - **CORR-014a (this)**: Delete `OllamaInvoker` only. Genuinely safe per audit (29 references across 5 files, all DOCSTRING/TEST).
  - **CORR-014b (deferred)**: `Phase1LLMInvoker` refactor + delete (requires `Phase1Executor` refactor — multi-file, SPEC recommended).
  - **CORR-014c (deferred)**: `OllamaClient` deletion + 6 legacy modules (`section_refill.py`, `nodes/a06/c01/c02`, `shared/document_producer.py`, `doc_evaluator.py`) retire `create_llm_client`.
- 5 files changed: `src/aegis_phase1/v2/llm.py` (137 LOC class block deleted; annotations updated), `src/aegis_phase1/v2/orchestrator.py` (docstring), `src/aegis_phase1/llm/unified.py` (docstrings), `tests/unit/v2/test_layer_b_callback_corr012.py` (7 tests migrated), `tests/unit/v2/test_invoker_bypass.py` (3 docstrings).

### Decisions
- **No backward-compat alias** — `OllamaInvoker` is gone; `from aegis_phase1.v2.llm import OllamaInvoker` now raises `ImportError` (verified via Houdini).
- **`_health_check` annotation `UnifiedInvoker`** — works because `UnifiedInvoker` has `.base_url`.
- **`MockInvoker` stays independent** — no inheritance from `OllamaInvoker`; not affected by deletion.
- **`build_llm_invoker` return annotation `MockInvoker | UnifiedInvoker`** — string forward-ref if needed; re-verified.

### Why Orchestrator P0 flagged this
- The original CORR-014 audit (Orchestrator) called `Phase1LLMInvoker` "LEGACY-ONLY" but Executor's re-audit correctly identified LIVE callers. The split into 014a (safe) + 014b (refactor) is a textbook strangler: delete what is truly dead first, refactor what has callers with a SPEC.

### Next
- AEGIS-P1-CORR-014b (deferred): `Phase1LLMInvoker` deletion via `Phase1Executor` refactor. SPEC recommended.
- AEGIS-P1-CORR-014c (deferred): `OllamaClient` retirement + 6 legacy modules.
- AEGIS-P1-CORR-015 (Phase 5 — Suppress retry-storm noise).

### Merged 2026-07-16 (commit `9b2367d` via PR #11)

#### Quality Log
- `trials: 1` (deterministic class deletion)
- `pass@1`: 7/7 migrated tests + 3/3 docstring tests + ALL GATES PASS
- Test count: **349 passed + 10 skipped** (no test delta — old tests now use `UnifiedInvoker`; same count)
- Master switch preserved: `LANGFUSE_ENABLED=false` → no behaviour change
- Final grep: `grep -rn OllamaInvoker src/ tests/` → **NO MATCHES** (class fully purged)
- Houdini demo: re-include class → import OK; restore → ImportError as expected; migrated tests still pass via `UnifiedInvoker`
- Pre-push hooks: PASS
- **No real LLM calls made.**

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
| 7 | TTY-driven smoke (pexpect/pty) for wizard step 1 | Separate contract (CORR-009?); current `test_runner_smoke.py` is structurally a no-op against the `pre_selected` bug because `run_wizard` short-circuits on non-TTY before reaching `beaupy.select` | Open (follow-up CORR-008) |

## Known limitations

- **Adapter design**: The `_get_phase1_executor()` fix (CORR-003 Phase A) reads `model` from `self.llm_invoker` but still creates a fresh `Phase1LLMInvoker` via `get_invoker()`. A full adapter (single invoker for both stages) would require refactoring `Phase1LLMInvoker` to accept `MockInvoker`/`OllamaInvoker` via duck-typing — deferred.
- **CI gate only runs on push**: `validate-contracts.sh` is wired to `pre-push` only. For team-scale CI, GitHub Action integration is future work.
- **Methodology-main contracts**: This index only covers `aegis-phase1` repo. `Methodology-main` has its own contracts (rebranding was a sub-step of CORR-001 but covered there).
- **CORR-008 sub-detector** (open follow-up): the AST-scan signature smoke (`tests/integration/test_wizard_signature_smoke.py`) is what actually catches a `pre_selected=` regression. The runner-subprocess smoke (`tests/integration/test_runner_smoke.py`) and the wizard non-TTY hand-test (`scripts/test-quick.sh` step 3) both short-circuit before reaching the bug site. A TTY-driven smoke (pexpect / pty) would close the loop end-to-end — see Pending decisions #7.

## See also

- `.hooks/validate-contracts.sh` — the script enforcing these contracts
- `LLM_ARCHITECTURE_DECISION.md` — strategic decision doc that motivates CORR-002
- `AGENTS.md §10` — Branch Policy + Pre-flight Check policy
