---
contract: CONTRACT-110
title: CORR-110 — vLLM provider (OpenAI-compatible HTTP) for HuggingFace models on Deucalion
status: ACTIVE
created: 2026-09-02
author: opencode (MiniMax-M3)
branch: feature/aegis-p1-corr-110-vllm-provider
scope: 1 new module + 6 wiring edits + 1 test file + 1 sbatch + 1 contract
depends_on: CORR-106 (transformers factory), CORR-062 S2 (minimax adapter pattern)
problem: |
  The Deucalion HPC cluster cannot evaluate gemma-4-31B-it through
  the local Ollama daemon:
    * Ollama 0.31.1 (the cluster-shipped binary) lacks the renderer
      for newer GGUF blobs (qwen3.8 scout 1846584 — HTTP 500 "unknown
      renderer"; muse-glimmer 30B aborted the same way in JOB 1867429).
    * The HF transformers provider (CORR-106) loads the model
      in-process. JOB 1846584 then died at the invoker factory —
      the factory probed Ollama at localhost:11434 (absent on the
      cluster) and aborted before any HF call. The user's 2026-08-24
      decision was "drop the transformers path on Deucalion".
    * Even with CORR-106's plumbing fix, transformers path only
      supports Phase 1B — REDUCE-LLM (P1C-02/03) is intentionally
      skipped, so scout-full comparisons against Ollama models are
      apples-to-oranges.
    * Manual hardcoded transformers tags (nemotron3.5 vs
      nemotron-3.5-lightning) have bitten us twice with silent
      pull-aborts due to no-egress on compute nodes.

  Sibling project cybermetric-vllm already operates a working vLLM
  install on the cluster (BF16 DiffusionGemma 26B on 2xA100-40,
  TP=2, OpenAI-compatible HTTP at port 8000), but the AEGIS pipeline
  has no way to talk to it.

approach: |
  1. NEW ADAPTER: src/aegis_phase1/llm/openai_compat.py —
     ``ChatOpenAICompat(BaseChatModel)`` speaks the OpenAI chat-
     completions protocol via httpx (already required by
     chat_minimax.py — no new dependency). Same LangChain shim
     pattern as ChatMinimax (CORR-062 S2). Returns AIMessage with
     usage_metadata so UnifiedInvoker._extract_usage keeps working
     unchanged. Defaults: timeout 600s, max_tokens 4096, base_url
     http://localhost:8000/v1. Env overrides: AEGIS_VLLM_BASE_URL /
     AEGIS_VLLM_MODEL / AEGIS_VLLM_API_KEY / AEGIS_VLLM_TIMEOUT.

  2. PROVIDER TAG: ``provider="vllm"`` added to all 6 selection
     points: runner --provider choices, build_llm_invoker,
     _detect_provider (recognises ``vllm:`` prefix), UnifiedInvoker
     chat backend + _ensure_ollama probe guard, Phase1LLMInvoker
     _attempt chat backend (heavy path), get_invoker (REDUCE-LLM
     factory). REDUCE-LLM is ACTIVE on this provider (no skip) —
     unlike transformers, which intentionally skips it.

  3. NO NEW PROJECT DEPS. Test
     tests/unit/llm/test_openai_compat_corr110.py::test_module_imports_only_httpx_and_langchain_core
     asserts the AST contains exactly httpx / langchain_core /
     pydantic — no openai / langchain-openai / anthropic / tiktoken.

  4. TESTS: 26 unit tests in tests/unit/llm/test_openai_compat_corr110.py
     cover message conversion, env overrides, _generate against
     mocked httpx (200 + 404 + empty choices + connection refused +
     missing usage), UnifiedInvoker integration (chat backend +
     base_url + probe skip + env timeout propagation), auto-detect
     (``vllm:org/repo`` resolves to vLLM, not transformers),
     build_llm_invoker / get_invoker factory paths, and the
     CORR-106 regression guard (methods live on the class, not in
     nested closures). The full LLM/invoker suite stays at
     86/86 PASS — no regression.

  5. PILOT SBATCH: examples/deucalion/scout-vllm-gemma431b-aegis.sbatch
     — Pattern A (single job, server in background). TP=2 on
     dev-a100-40, 2h walltime, AEGIS_SCOPE=run-all by default
     (override to phase-1b for the cheap scout). Reuses the
     cybermetric vLLM venv via AEGIS_VLLM_VENV env. Pre-staged HF
     weights, HF_HUB_OFFLINE=1, two separate venvs (pipeline +
     vLLM), pip-deps don't overlap. Cleanup trap kills the vLLM
     PID on exit.

files_added:
  - src/aegis_phase1/llm/openai_compat.py (ChatOpenAICompat)
  - tests/unit/llm/test_openai_compat_corr110.py (26 tests)
  - examples/deucalion/scout-vllm-gemma431b-aegis.sbatch
  - execution/contracts/CONTRACT-110.md
files_modified:
  - src/aegis_phase1/llm/__init__.py (ChatOpenAICompat export)
  - src/aegis_phase1/llm/transformers_invoker.py (_detect_provider
    recognises vllm: prefix)
  - src/aegis_phase1/llm/unified.py (chat backend branch +
    _ensure_ollama probe skip)
  - src/aegis_phase1/v2/llm.py (build_llm_invoker + auto-detect)
  - src/aegis_phase1/v2/runner.py (--provider choices)
  - src/aegis_phase1/prompts_v2/invoker.py (heavy-path branch)
  - src/aegis_phase1/prompts_v2/factory.py (get_invoker + base_url default)
accept: |
  * tests/unit/llm/test_openai_compat_corr110.py: 26/26 PASS
  * tests/unit/llm/ + tests/unit/prompts_v2/ + tests/unit/v2/
    (LLM/invoker/provider scope): 86/86 PASS, no regression
  * ruff check (changed files): only pre-existing errors remain
    (F821 forward-refs in runner.py are not ours; SIM105 in
    transformers_invoker.py is from before this contract).
  * pre-flight `python -c "from aegis_phase1.v2.runner import main;
    print('OK')"`: OK
  * pending real-run gate (user must authorise):
    sbatch examples/deucalion/scout-vllm-gemma431b-aegis.sbatch
    → STATUS: SUCCESS + rationale_by_reg has 2 entries (Phase 1B
      only scout) OR full run-all 9 docs + xlsx (default).
risks: |
  * vLLM compile + CUDA graph capture eats ~60-90s on startup; the
    sbatch polls /v1/models every 10s for 15 min (90 attempts) — if
    a 31B class model takes longer, lower VLLM_GPU_MEMORY_UTILIZATION
    first (less KV-cache warmup) or pass --enforce-eager (already on
    by default in the sbatch — disables CUDA graphs entirely).
  * 31B BF16 ≈ 62 GB. TP=2 + VLLM_GPU_MEMORY_UTILIZATION=0.85 leaves
    ~2 GB/GPU for KV cache. If OOM during generation, lower
    VLLM_MAX_MODEL_LEN from 16384 → 8192 or bump
    VLLM_GPU_MEMORY_UTILIZATION to 0.92. The sbatch lets all three
    be overridden via --export on the sbatch command line.
  * HF_HUB_OFFLINE=1 in the sbatch — the model MUST be pre-staged
    on Lustre before the job starts. Compute nodes have no egress
    to huggingface.co. Stage with
        huggingface-cli download <repo> --local-dir $BD/models/hf/<repo>
    on the login node. For gated repos, set HF_TOKEN in
    ~/.aegis_env first.
  * The pilot runs ``.venv/bin/python`` for the pipeline and a
    SEPARATE venv for vLLM. The project has no vLLM dependency in
    pyproject.toml — keep it that way (the test
    test_module_imports_only_httpx_and_langchain_core enforces
    "no vllm / no openai imports" in the pipeline source).
  * Served-model-name mismatch: ``--served-model-name gemma4-31b``
    in ``vllm serve`` MUST match what the pipeline passes as
    ``--model 'vllm:gemma4-31b'``. The sbatch uses
    $SERVED_NAME consistently; if you change one, change both.
  * If vLLM readiness hangs, the most likely cause is a 31B model
    that needs more than 15 min to compile (rare). Inspect
    /tmp/aegis-job-${JOBID}/vllm.log (the sbatch dumps the last 80
    lines on hard fail).

follow_ups:
  - Once a successful scout on Deucalion is logged, mirror the run
    dir under execution/runs/ and cross-ref from by_model/.
  - Update hpc-deucalion skill (Standard facts) with the vLLM
    recipe — NOT before a successful cluster run.
  - Consider adding ``--trust-remote-code`` to the sbatch by
    default if a future model needs it (some HF repos ship custom
    code in __init__.py). Currently opt-out to avoid silent
    execution of model-side code.
  - Cybermetric-vllm uses ``--served-model-name diffusiongemma``,
    so the cybermetric shim pattern (Ollama-API → vLLM-API proxy)
    is NOT needed for the AEGIS pipeline — it speaks OpenAI natively
    via ChatOpenAICompat.
---