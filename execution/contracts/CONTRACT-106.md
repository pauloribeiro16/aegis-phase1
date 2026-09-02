---
contract: CONTRACT-106
title: CORR-106 — Transformers provider plumbing fix
status: ACTIVE
created: 2026-09-01
author: opencode (MiniMax-M3)
branch: feature/aegis-p1-corr-106-transformers-provider
scope: 3 source files + 1 test file
depends_on: CONTRACT-074 (markdown parser), CORR-056 (transformers path),
  CORR-067 (factory) — all in main
---

# CORR-106 — Transformers provider plumbing

## Goal

Fix the transformers (`--provider transformers`) path so the gemma-4
family of models can be evaluated through AEGIS-KG Phase 1, end-to-end
on Deucalion. The factory and heavy invoker were silently ignoring the
provider flag (scout report §4.1 + §4.2) and falling back to the Ollama
backend, which then probed localhost:11434 and aborted before the HF
model was ever asked to load (JOB 1846584).

## Diagnosis (recap from scout report §2.1)

Three layered bugs that compound into the abort:

1. `TransformersInvoker` has no `.provider` attribute.
   `v2/orchestrator.py:1254` does
   `getattr(self.llm_invoker, "provider", "ollama")` → falls back to
   `"ollama"` for transformers runs. (scout §4.1, sketch fix #1)
2. `prompts_v2/factory.get_invoker()` always returns a `UnifiedInvoker`,
   even when `provider="transformers"`. (scout §4.1, sketch fix #2)
3. `unified.py:_ensure_ollama()` only skips the Ollama probe for
   `"minimax"`; it probes `localhost:11434` for every other provider,
   raising `LLMUnreachableError` before the heavy child runs. (scout
   §4.2, one-line fix)

## Fix (3 files + 1 test)

| File | Change |
|---|---|
| `src/aegis_phase1/llm/transformers_invoker.py` | Add class attribute `provider = "transformers"`. Add `TransformersChat` shim (LangChain-compatible; routes `[SystemMessage, HumanMessage]` to the underlying `TransformersInvoker.invoke(prompt, system_prompt=...)`). |
| `src/aegis_phase1/prompts_v2/invoker.py` | Add `elif self.provider == "transformers": llm = TransformersChat(self._hf_invoker)`. Reuse one `TransformersInvoker` across calls within the same `Phase1LLMInvoker` (lazy model load on first `.invoke()`). |
| `src/aegis_phase1/llm/unified.py` | Generalise the `_ensure_ollama` early-return from `if self.provider == "minimax"` to `if self.provider != "ollama"`. |
| `tests/unit/scripts/test_corr106_transformers_provider.py` | 6 stdlib-only tests: class attr, factory routing, shim `system_prompt` extraction, shim user-only fallback, `_ensure_ollama` no-op for transformers, regression guard for the Ollama path. |

## Out of scope (deliberately)

- `v2/orchestrator.py` does NOT need changes — the getattr fallback
  now returns `"transformers"` (via the class attribute) instead of
  `"ollama"`, so the heavy invoker gets the right provider.
- `factory.py` does NOT need the sketch fix #2 from scout §4.1:
  the orchestrator path goes through `v2/llm.py:build_llm_invoker`,
  which already early-returns `TransformersInvoker` for the
  transformers provider. The `prompts_v2/factory.get_invoker()` path
  is only used by `phase1_executor` (REDUCE-LLM); see note below.
- Methodology-main is untouched (stable pin).
- No new Python deps.

## Caveats

- **Phase 1 heavy path** (`prompts_v2/invoker.py`) is the one fixed
  here. **`prompts_v2/factory.py` is NOT fixed in this contract** —
  it still has the original failure mode (returns `UnifiedInvoker`
  regardless of provider). If you wire REDUCE-LLM through the factory
  path (orchestrator line 1252 does), the unified-invoker will be
  created with `provider="transformers"` and the chat backend will be
  `ChatOllama` — which will then fail at the first `invoke()` call
  because there is no Ollama server. The heavy path bypasses the
  factory (`Phase1LLMInvoker(self.llm_invoker=…)` in the executor),
  so the REDUCE-LLM calls go through `TransformersChat` correctly.
  Net effect: end-to-end run is correct, but the unified-invoker
  constructed for the heavy executor is unused overhead.
- First `.invoke()` on the transformers path is **lazy-load** — the
  HF model loads on demand (the scout confirmed ~26 s on 3×A100-40
  for gemma-4-31B-it at 33.6 GB / 39.5 GB VRAM).
- `AEGIS_MAX_NEW_TOKENS` from `scout_31b.sh` (`16384`) overrides the
  default `TransformersInvoker.max_new_tokens` (1024) for the
  AEGIS prompts — the sbatch sets the env var; the invoker does not
  yet read it. **This is the next follow-up contract** (CORR-107
  candidate): make `TransformersInvoker` honour
  `AEGIS_MAX_NEW_TOKENS`.

## Risks

| Risk | Mitigation |
|---|---|
| `torch` not installed in the local venv | Tested by importing only — no model load in CI. Actual smoke runs on Deucalion GPU nodes. |
| HF model download on Deucalion | `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` set in the sbatch (same as scout_31b.sh); blob is pre-cached at `$BD/models/hf/`. |
| `TransformersChat` shim drops system_prompt content accidentally | Test `test_transformers_chat_routes_system_and_user` asserts exact (prompt, feedback, system_prompt) tuple. |
| Regression in Ollama path (the most common) | Test `test_ensure_ollama_still_runs_for_ollama` guards with `monkeypatch.setattr(probe_ollama, ...)` to force a probe and assert `LLMUnreachableError` is raised. |

## Acceptance

1. `pytest tests/unit/scripts/test_corr106_transformers_provider.py -v`
   → 6/6 PASS.
2. `bash .hooks/ci-frameworks.sh` → OK.
3. The scout job on Deucalion (next task) loads gemma-4-31B-it
   through the transformers path and runs Phase 1B to completion
   (4 LLM calls OK, 2 regs in `rationale_by_reg`).
4. Logs show `TransformersInvoker: model loaded on device=cuda:0` (or
   equivalent) and `provider=transformers` in the executor instantiation
   line — no `Ollama not reachable` warning.