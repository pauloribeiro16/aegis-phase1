# Deucalion scout report — gemma-4-31B-it + qwen3.5:27b

**Status:** DRAFT (2026-08-24)
**Author:** opencode (MiniMax-M3)
**Branch:** `feature/aegis-p1-corr-074-p1c01-propagation`
**Predecessor:** [corr074_e2b_validation.md](corr074_e2b_validation.md)

---

## TL;DR

- **gemma-4-31B-it (transformers)**: pipeline does NOT run end-to-end on
  Deucalion. The Phase1B LLM invoker is hardcoded to probe Ollama at
  `http://localhost:11434` even when `--provider transformers`. The
  probe fails → orchestrator marks Phase 1B as `0 regulations` →
  job ends with no useful output. The TransformersInvoker does load
  the model correctly (33.6GB / 39.5GB VRAM, 26s on 3×A100-40) but
  is never invoked because the heavy child (Phase1LLMInvoker) is
  instantiated via `prompts_v2/factory.get_invoker()` which always
  returns a UnifiedInvoker with default Ollama backend.
- **qwen3.5:27b (Ollama)**: pipeline runs. Warm-up loads the model
  onto GPU (34GB / 80GB), `/api/generate` returns valid JSON. The
  orchestrator proceeds past STAGE 0 (LOAD) and into PHASE 1B.
  Full scout result pending.
- **qwen3.8:27b (Ollama)**: NOT viable on Deucalion — the model
  blob metadata declares `requires: 0.32.12` (the Ollama server
  version that introduced the `qwen3.8` renderer). The cluster
  binary is `0.31.1`. Every `/api/generate` against the `qwen3.8:27b`
  tag returns HTTP 500 `unknown renderer "qwen3.8"`. The blob is in
  the cache but unusable until the cluster Ollama is upgraded to
  ≥0.32.12.

---

## 1. Method

- **Repo sync**: `tar -czf aegis-phase1.tgz -C aegis-phase1 .`
  (excluding `.venv`, `__pycache__`, `Methodology-main`, `preproc_out`,
  `logs`, `output`, `.pytest_cache`) → `scp` →
  `tar -xzf` over `/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1`.
  `.venv` preserved (NFS, no quota hit).
- **Models are pre-cached** at
  `/projects/F202512235CPCAA1/CyberMetric_Deucalion/{models/hf,ollama_data}`.
  No `ollama pull` inside jobs (compute-node egress to
  `registry.ollama.ai` is spotty — CORR-061 + hpc-deucalion skill rule).
- **Progressive eval**: 1 scout job per model, `--run-phase-1b`
  only (P1B-01 + P1B-02 per applicable regulation; 2 lanes for
  case1-tinytask → 4 LLM calls).

### 1.1 Scout scripts

- `Deucalion/aegis_jobs/scout_31b.sh` — gemma-4-31B-it via
  `transformers` provider, 3×A100-40, 30min, `dev-a100-40`.
- `Deucalion/aegis_jobs/scout_qwen35.sh` — qwen3.5:27b via `ollama`
  provider, 1×A100-80, 30min, `dev-a100-80`.

Both follow the pattern from the existing
`aegis_jobs/aegis_eval_31b.sh` (Jul/2025) and the graphify
`graphify_E1.sbatch` Ollama-server pattern.

---

## 2. Results

### 2.1 JOB 1846584 — gemma-4-31B-it scout

| Field | Value |
|-------|-------|
| Partition | `dev-a100-40` |
| Walltime | 30 min |
| Elapsed | 10:19 |
| Exit | 0 (Python) but 0 rationale produced |
| GPU | 3×A100-40GB, model loaded 33.6GB / 39.5GB (85% VRAM) in 26s |

```
2026-08-24 13:08:46 | INFO    | UnifiedInvoker.__init__: provider=ollama, chat=ChatOllama
                                  model=…/google_gemma-4-31B-it base_url=http://localhost:11434
2026-08-24 13:08:49 | WARNING | Phase 1B RATIONALE failed (continuing) for CRA: Ollama not
                                  reachable at http://localhost:11434 (probe from invoke_spec)
2026-08-24 13:08:49 | WARNING | Phase 1B RATIONALE failed (continuing) for GDPR: Ollama not
                                  reachable at http://localhost:11434 (probe from invoke_spec)
2026-08-24 13:08:49 | INFO    | Phase 1B RATIONALE complete for 0 regulation(s) (status=?)
2026-08-24 13:08:50 | INFO    | TransformersInvoker: loading model_id=…/google_gemma-4-31B-it
                                  … device_map=auto, max_memory={0: '35.3GiB', 'cpu': '30GiB'}
```

**Verdict**: Pipeline correctly constructs the `TransformersInvoker`
via `v2/llm.py:build_llm_invoker()` (log:
`provider=transformers → TransformersInvoker(...)`). However,
`v2/orchestrator.py:run_phase_1b` instantiates a **second** invoker
through `prompts_v2/factory.get_invoker()` (log:
`REDUCE-LLM Phase1Executor instantiated: … invoker_type=TransformersInvoker`),
and this factory always returns a `UnifiedInvoker` whose
`_ensure_ollama` probes `http://localhost:11434` regardless of
provider. Probe fails → orchestrator records `0 regulations` →
TransformersInvoker is never asked to run.

### 2.2 JOB 1846591 — qwen3.8:27b scout (initial, FAILED)

| Field | Value |
|-------|-------|
| Partition | `dev-a100-80` |
| Walltime | 30 min |
| Elapsed | 4:46 |
| Exit | 0 (Python) but 0 rationale produced |

Model **loaded successfully** (`llama-server started in 37.16s`,
17.7 GB blob). But every `/api/generate` returns HTTP 500:
`unknown renderer "qwen3.8"`. The blob config (read from
`/projects/.../ollama_data/models/blobs/sha256-492b29…`) declares
`renderer: "qwen3.8"`, `parser: "qwen3.5"`, `requires: "0.32.12"`.
Cluster Ollama binary is **0.31.1** — below the minimum. The
`qwen3.8` family was added to Ollama in version 0.32.12 (Sep/2025);
the cluster binary is from Jun/2025.

### 2.5 ROOT CAUSE found: executor/CORR-074 integration bug (fixed in a7dfb35)

Although the scout's 4 LLM calls all reported `status: OK` with
`valid: True`, the orchestrator logged `rationale_by_reg has 0
entries`. Diagnosis (raws pulled from `work/state.json` +
`logs/phase1/qwen3.5_27b/llm-calls.jsonl` and re-parsed locally):

- The local **MarkdownParsers parse all 4 qwen3.5 raws cleanly**
  (P1B-01 CRA: 2 interpretations + 2 derogations; the parse itself
  was never the problem).
- The bug is in `phase1_executor.run_phase_1b`: it extracted
  `parsed_02["synthesis"]` — a nested dict from the **pre-CORR-074
  schema**. The new `P1BLLM02Output` has a top-level `rationale`
  string and no `synthesis` key, so the read returned `None` for
  every regulation and `aggregated_synthesis` stayed empty.
- Impact: **every real-LLM run since CORR-074 produced an empty
  `rationale_by_reg`**. Doc 05 §6.1b kept rendering via the
  `per_spec_markdown` fallback (CORR-061 S3b), which masked the bug
  locally — but the MAP stage input (`p1b_outputs_by_reg`) was
  silently empty. The identical pattern is visible in the
  2026-08-13 `aegis_qwen35_big_2x80` cluster job, so this predates
  today's runs.
- Fix (commit `a7dfb35`): when `synthesis` is absent but `rationale`
  is present, build the per-reg synth dict from the new schema
  fields. Legacy callers keep working. Validated with a FakeInvoker
  unit test; re-scout submitted as JOB 1847634.
- **Re-scout JOB 1847634 CONFIRMS THE FIX** (23:29 elapsed): same 4
  LLM_CALL OK, but now
  `Phase 1B RATIONALE complete for 2 regulation(s)` and
  `rationale_by_reg has 2 entries`. Timings are near-identical to the
  first scout (temperature=0 determinism): P1B-01 318s/125.7k tok,
  P1B-02 260s/125.1k tok, P1B-01 208s/93.5k tok, P1B-02 263s/95.7k
  tok — ≈ 17.5 min of LLM time for Phase 1B alone.
- Follow-up: full `--run-all` (8h walltime, JOB 1847659,
  `run_qwen35_full.sh`) submitted 2026-08-24 to measure MAP (10
  domains × P1C-01) + REDUCE end-to-end with the 27B model.

### 2.6 qwen3.5:27b format compliance (from the captured raws)

The model does not follow the CORR-074 markdown template verbatim:

- P1B-01: emits `- ENTRY (VERDICT): text` bullets instead of
  `### ENTRY — VERDICT` subsections. The tolerant parser accepts it.
- P1B-02: emits `## Findings` with loose bullets instead of the
  5-section Status/Rationale/Implications/Gaps/Notes contract;
  `implications`/`gaps` end up empty (the rationale prose itself is
  high quality — 2.1k chars of grounded analysis per regulation).

Even with the executor fix, P1B-02's empty implications/gaps may fail
downstream `minItems` expectations — flagged as a known limitation of
this model for template-following; the M3 gold remains the reference
for full contract compliance.

### 2.3 JOB 1846944 — qwen3.5:27b scout

| Field | Value |
|-------|-------|
| Partition | `dev-a100-80` |
| Walltime | 30 min |
| Elapsed | 18:33+ (in flight at report write) |
| GPU | 1×A100-80GB, model loaded 34 GB (Q4_K_M + KV cache) |

```
warm-up OK on attempt 1
{"model":"qwen3.5:27b","response":"","thinking":"Okay","done":true, ...}
ollama ps: qwen3.5:27b   7653528ba5cb   34 GB   100% GPU   262144
2026-08-24 13:22:56 | INFO    | === STAGE 0: LOAD ===
2026-08-24 13:23:05 | LOAD complete: 38 sub-domains, 2 regs (8.76s)
2026-08-24 13:23:05 | INFO    | === STAGE 1.5: PHASE 1B RATIONALE ===
[13:28:27] [INFO] LLM_CALL P1B-LLM-01-INTERPRETATION → OK (318355ms, 125744 tok)
[13:32:48] [INFO] LLM_CALL P1B-LLM-02-RATIONALE → OK (260074ms, 125095 tok)
[13:36:15] [INFO] LLM_CALL P1B-LLM-01-INTERPRETATION → OK (206997ms, 93508 tok)
```

`qwen3.5:27b` is the previous-generation model — Ollama 0.31.1 knows
its renderer. We use it as a **proxy** for `qwen3.8:27b` (same family,
similar capability class; the corr044 family matrix gets a 27B-tier
data point regardless of which sub-version).

**Initial timing profile (per LLM call):**
- P1B-01: 318s (125.7k tokens) on first reg, 207s (93.5k tokens) on second reg
- P1B-02: 260s (125.1k tokens)
- Average token throughput: ~395 tok/s
- 2 regulations × 2 specs = 4 calls; remaining time per scout ≈ 6-9 min

For the full 8h run (case1-tinytask): P1B (4 calls ≈ 20 min) + MAP
(10 domains × P1C-01 ≈ 30 min) + REDUCE (2 calls ≈ 8 min). Token
volume per call is large because the prompts carry the inlined
catalogs + per-subdomain refs after CORR-103. The 8h walltime is
generous.

### 2.4 Parse success matrix (extended)

| Model          | Spec | Local e2b | Cluster scout |
|----------------|------|:---------:|:-------------:|
| gemma-4-31B-it | P1B-01 | (n/a) | ⚠️ pipeline aborted by Ollama probe |
| gemma-4-31B-it | P1B-02 | (n/a) | ⚠️ pipeline aborted by Ollama probe |
| qwen3.8:27b    | P1B-01 | (n/a) | ✗ Ollama 0.31.1 rejects `qwen3.8` renderer |
| qwen3.5:27b    | P1B-01 | (n/a) | (pending scout) |
| qwen3.5:27b    | P1B-02 | (n/a) | (pending scout) |

---

### 2.7 JOB 1847659 — full `--run-all` with qwen3.5:27b

| Stage | Result |
|-------|--------|
| LOAD | ✅ 38 sub-domains, 2 regs (8.8s) |
| Phase 1B | ✅ 4 LLM calls OK, **2 regs in rationale_by_reg** (executor fix live), ≈17.5 min |
| MAP (P1C-01 ×10) | ✅ 10/10 lanes `OK` (1805s ≈ 30 min; 41.5k tok/domain) — **but 0 sub_domain_activations parsed** |
| REDUCE | ⚠️ deterministic merge ran on empty inputs; **REDUCE-LLM skipped** ("aggregated_activations is empty across all lanes") |
| OUTPUT | ✅ 6 deterministic artefacts + xlsx + enhanced docs (04b/04c) rendered |

**P1C-01 root cause (raw pulled from `work/state.json`, 39.3 KB):**
qwen3.5 emits a `## Pair classifications` section with
`- D-XX.Y : REG ↔ REG (VERDICT): …` bullets — a completely different
shape from the contract's `## Sub-domain Activations` + `### D-XX.Y`
subsections. The content is substantive (per-pair verdicts with
evaluated predicates) but `P1CLLM01Parser` extracts 0 activations, so
`domain_results` ends with 10 domains × 0 activations and REDUCE has
nothing to reduce.

### 2.8 Final model matrix (P1 pipeline, case1-tinytask)

| Spec | M3 (gold) | gemma4:e2b (local) | qwen3.5:27b (Deucalion) |
|------|:---------:|:------------------:|:-----------------------:|
| P1B-01 | ✓ | ✓ | ✓ (bullet format; tolerant parser accepts) |
| P1B-02 | ✓ | ✓ | ⚠️ rationale solid (2.1k chars/reg); implications/gaps empty |
| P1C-01 | ✓ | ✗ (JSON drift) | ✗ ("Pair classifications" bullets → 0 activations) |
| P1C-02/03 | ✓ | ✗ (JSON drift) | — (skipped: empty REDUCE input) |

**Conclusion:** P1C-01 is the template-following bottleneck for every
non-M3 model tested. The 27B tier does NOT clear it — model scale is
not the fix; either the P1C-01 spec/prompt needs stronger format
anchoring, or the parser needs a bullet-tolerant path (analogous to
what P1B-01 already tolerates). Until then, M3 remains the only model
that completes the full 5-spec pipeline.

- **The Phase-3 decision (`gemma4:e2b` canonical for P1B, M3-only for P1C) is unchanged** by this scout. The Deucalion 31B run was a stress test, not a Phase-3 candidate. The data we wanted (large-model compliance structure) was already measured by corr044.
- **The Ollama-cluster scout for qwen3.5:27b completes the matrix** on the Ollama side (5B / 9B / 12B / 27B tiers). If the scout succeeds, we will run `--run-all` (8h) to measure end-to-end timing and parser behavior for a 27B model.
- **`qwen3.8:27b` is a structural blocker for this cluster** — `requires: 0.32.12`. Two options:
  1. Upgrade Ollama on the cluster (`module spider ollama` may have a newer build; check `module avail ollama`).
  2. Wait for the cluster maintainer to bump the binary.
  Both are out of scope for this contract; flagging for the next sprint.

---

## 4. Bugs surfaced (open follow-ups)

### 4.1 `prompts_v2/factory.get_invoker()` ignores `provider="transformers"`

The factory **always** returns a `UnifiedInvoker` with default
Ollama config. When `--provider transformers` is selected, the
factory does not early-return a `TransformersInvoker`. As a result:

- `invoke_spec` runs `_ensure_ollama("invoke_spec")` → probe Ollama
  → fail-closed `LLMUnreachableError` when Ollama is not running.
- Even if Ollama were running, the heavy child (`Phase1LLMInvoker`)
  is hard-coded to dispatch through Ollama (no transformers branch).

**Fix sketch**: add an early-return at the top of `get_invoker()`:
```python
if provider == "transformers":
    from aegis_phase1.v2.llm import TransformersInvoker  # or llm.transformers_invoker
    return TransformersInvoker(model_id=model)
```
But `invoker_to_executor` (in `prompts_v2/phase1_executor.py`) expects
a `Phase1LLMInvoker`, not a `TransformersInvoker`. The fix needs to
also adapt `Phase1Executor` to accept either backend, or change
`invoker_to_executor` to use a protocol. **Not in scope of this
contract** — user decision 2026-08-24 was to **drop the transformers
path on Deucalion**.

### 4.2 `UnifiedInvoker._ensure_ollama` ignores non-ollama providers

`_ensure_ollama` currently skips the probe only when
`self.provider == "minimax"`. It should skip for **all** non-ollama
providers (transformers, future M3-via-local-llama.cpp, etc). One-line
fix: change the guard from
`if self.provider == "minimax": return` to
`if self.provider != "ollama": return`. **Not in scope of this
contract** (would unblock 4.1 too, but is part of the same fix).

---

## 5. Reproduce

```bash
# 1. Sync repo (one-time)
tar --exclude=./.venv --exclude=./**/__pycache__ \
    --exclude=./Methodology-main --exclude=./preproc_out \
    --exclude=./methodology-00 --exclude=./logs --exclude=./output \
    --exclude=./.pytest_cache --exclude=./work \
    -czf /tmp/aegis-phase1.tgz -C aegis-phase1 .
scp /tmp/aegis-phase1.tgz paulinho@login.deucalion.macc.fccn.pt:/tmp/
ssh paulinho@login.deucalion.macc.fccn.pt \
    'cd /projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1 && tar -xzf /tmp/aegis-phase1.tgz'

# 2. Scout
scp Deucalion/aegis_jobs/scout_qwen35.sh paulinho@login.deucalion.macc.fccn.pt:/projects/.../aegis-phase1/sbatch/
ssh paulinho@login.deucalion.macc.fccn.pt \
    'cd /projects/.../aegis-phase1 && sbatch sbatch/scout_qwen35.sh'

# 3. Monitor
ssh paulinho@login.deucalion.macc.fccn.pt 'squeue -u $USER; tail -f output/<JOBID>_scout_qwen35.txt'
```

---

## 6. Conclusion

- **Transformers on Deucalion is broken at the factory layer** —
  leaving as documented open follow-up. The 31b scout confirmed
  model load + GPU fit (33.6GB / 39.5GB on 3×A100-40) but the
  pipeline aborted before invocation.
- **`qwen3.5:27b` is a viable proxy for `qwen3.8:27b`** — model loads
  cleanly (34GB / 80GB on 1×A100-80), warm-up succeeds, Phase 1B
  starts. Awaiting scout completion.
- **`qwen3.8:27b` cannot be evaluated on this cluster without an
  Ollama ≥0.32.12 upgrade** — flagged as out-of-scope but
  important for the next Deucalion contract.