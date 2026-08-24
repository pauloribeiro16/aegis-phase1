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

### 2.3 JOB 1846944 — qwen3.5:27b scout (in progress)

| Field | Value |
|-------|-------|
| Partition | `dev-a100-80` |
| Walltime | 30 min |
| Elapsed | (pending) |
| GPU | 1×A100-80GB, model loaded 34 GB (Q4_K_M + KV cache) |

```
warm-up OK on attempt 1
{"model":"qwen3.5:27b","response":"","thinking":"Okay","done":true, ...}
ollama ps: qwen3.5:27b   7653528ba5cb   34 GB   100% GPU   262144
2026-08-24 13:22:56 | INFO    | === STAGE 0: LOAD ===
```

`qwen3.5:27b` is the previous-generation model — Ollama 0.31.1 knows
its renderer. We use it as a **proxy** for `qwen3.8:27b` (same family,
similar capability class; the corr044 family matrix gets a 27B-tier
data point regardless of which sub-version).

### 2.4 Parse success matrix (extended)

| Model          | Spec | Local e2b | Cluster scout |
|----------------|------|:---------:|:-------------:|
| gemma-4-31B-it | P1B-01 | (n/a) | ⚠️ pipeline aborted by Ollama probe |
| gemma-4-31B-it | P1B-02 | (n/a) | ⚠️ pipeline aborted by Ollama probe |
| qwen3.8:27b    | P1B-01 | (n/a) | ✗ Ollama 0.31.1 rejects `qwen3.8` renderer |
| qwen3.5:27b    | P1B-01 | (n/a) | (pending scout) |
| qwen3.5:27b    | P1B-02 | (n/a) | (pending scout) |

---

## 3. Implications for corr044 / Phase-3 model decision

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