# CORR-062 S1 — Real-model end-to-end run (v4, with state= dispatcher fix)

## Pre-conditions
- ollama list: 16 models, gemma4:e2b present
- langchain: OK (langfuse.langchain import works)
- Fix applied: commit 280bdd0 (UnifiedInvoker.invoke() accepts/forwards state=)

## Run
- Command:
  ```
  PYTHONPATH=src timeout 1500 <shared-venv>/python -m aegis_phase1.v2.runner \
      --case "$(pwd)/cases/case1-tinytask" \
      --run-all-traced \
      --model gemma4:e2b
  ```
- Exit code: 1
- Wall time: 685s (11.4 min) — ran until first LLM call, then crashed
- Full log: `/tmp/corr062_s1_v4.log` (256 lines, mostly the traceback)

## Failure point (CRITICAL — new bug exposed by S1 fix)

The `state=` dispatcher fix in commit 280bdd0 **works** — the error no longer originates from
`UnifiedInvoker.invoke()` rejecting `state=`. Instead, the call chain now reaches the invoker
proper and crashes on a different line:

```
File ".../prompts_v2/invoker.py", line 221, in invoke
    existing = list(config.get("callbacks") or [])
TypeError: 'CallbackManager' object is not iterable
```

The `config["callbacks"]` field is now a LangChain `CallbackManager` (dict-like, not a list).
The idempotent-attach code at line 221–224 assumes it is a list and tries to `list(...)` it,
which fails because `CallbackManager` is not iterable.

**Call chain at failure (in order):**
1. `v2/runner.py:782` `cmd_run_all_traced` calls `graph.invoke(initial, config=run_config)`
2. `v2/graph.py:225` (subphase_1b) calls `orch.run_p1b_single("P1B-LLM-01-INTERPRETATION", ...)`
3. `v2/orchestrator.py:1656` calls `executor.run_phase_1b(state=self.state)`
4. `prompts_v2/phase1_executor.py:196` calls `self.invoker.invoke(SPEC_INTERPRETATION, ..., state=state)`
5. `llm/unified.py:365` forwards to `self.invoke_spec(prompt_or_spec_id, inputs, config=config, state=state)`
6. `llm/unified.py:335` calls `heavy.invoke(spec_id, inputs, config=config, state=state)`
7. `prompts_v2/invoker.py:221` — `list(config.get("callbacks") or [])` raises `TypeError`

**Failing task:** `interp_GDPR` (id `4fd9a876-2f5f-004a-fda0-23abef57ee7c`) within
`subphase_1b` (id `2bcbc04c-ef3e-a55d-13f2-70d6d5618d0c`).

The crash happens on the very first LLM call of the first subphase — `P1B-LLM-01-INTERPRETATION`
for `GDPR`. The graph never reaches any later spec, so:

- No raw `.md` or `.json` files were captured
- No `AEGIS-P1-*.md` documents were produced
- No `Case_01_Phase1.xlsx` was produced

## Output
- Docs produced: 0
- Raw capture: 0 `.md`, 0 `.json` across all 5 specs
- xlsx: NOT produced

## Pipeline log summary
- Error count: 105 (all from prior runs, not this one — current run never wrote ERROR)
- Warning count: 25 (mostly "langfuse not installed" from historical runs)
- Langfuse messages: this run logged
  `[tracing] Langfuse enabled host=http://localhost:3000 case=default phase=phase1 trace_id=15c2a5ad625b1762abaf677bbeac30a5`
  at 17:18:02,112 — i.e. tracing is wired but no LLM call completed to be traced.
- LLM call failures: 0 LLM calls reached the model (crash before the first call).

## GPU state after run
- Memory used: 3158 MiB / 8192 MiB
- Utilization: 0% (idle, no model loaded — because no LLM call ever fired)
- Note: pre-run baseline matched this; the crash is at the Python level, before ollama
  is contacted at all.

## Sample raw markdown

N/A — no raw markdown was produced. The pipeline crashed before any LLM call returned
content. Pre-S1 model output quality therefore cannot be evaluated from this run.

## Notes

1. **The S1 fix (280bdd0) is necessary but not sufficient.** It removes one error
   (`UnifiedInvoker.invoke()` rejecting `state=`) and exposes the next one
   (`'CallbackManager' object is not iterable` at `invoker.py:221`).

2. **Root cause of the new bug:** `invoker.py:215-224` assumes `config["callbacks"]`
   is either `None` or a list. Since LangChain's `RunnableConfig` populates
   `callbacks` as a `CallbackManager` (which is dict-like, not list-like), the
   `list(...)` cast fails. The fix likely involves:
   - extracting handlers via `config["callbacks"].handlers` / `.inheritable_handlers`
     and concatenating, or
   - short-circuiting the idempotent-attach path when `config["callbacks"]` is already
     a `BaseCallbackManager` (since `CallbackManager` already accepts `.add_handler(...)`).

3. **No recovery runs were attempted** per sprint instructions. Mavis will decide
   whether to dispatch a follow-up Sprint 1 v5 with another code fix, or escalate
   the design issue with the project owner.

4. **State of repo on this branch** is unchanged from `280bdd0` (the S1 fix commit);
   this run log is the only new commit on top.
