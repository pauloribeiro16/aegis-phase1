---
contract_id: CONTRACT-111
title: Quantization transparency — record and surface what was actually loaded
date: 2026-09-02
status: DRAFT
branch: feature/aegis-p1-corr-111-quantization-transparency
author: opencode (MiniMax-M3)
depends_on:
  - CORR-108 (parser fix — activation signals now routable)
  - CORR-110 (vLLM provider sidecar; same sidecar path pattern)
  - Teacher M3 evaluations 2026-09-02 (scout comparison baseline)
parent_goal: execution/CORR-111.md
---

# CONTRACT-111 — Quantization transparency

## Problem (user feedback 2026-09-02)

> "quero que metas as quantizações dos modelos para ser mais transparente as coisas,
> porque se não vou a achar que foi o modelo normal que fez isso e não foi o caso"

The same model tag exists in many quantizations (Q4_K_M, Q8_0, FP8, BF16).
When we wrote only the tag in scout digests ("qwen3.5:27b", "nemotron-3.5-lightning:30b"),
two scouts that looked identical on paper might actually have been different
quantizations — and the reader had no way to know. After multiple scout
comparisons across jobs (1847659 / 1862819 / 1862843 / 1867082 / 1867097 /
1867429 / 1867430 / 1867431 — see execution/runs/ digests), this ambiguity
becomes a real evaluation hazard.

## Approach (user decisions)

1. **Metadados + sidecar only** — no gate, no run rejection. Old runs remain
   valid; they show `[quant unknown — verify manifest]` in their doc headers.
2. **Declare provider default** — when no quant is knowable (e.g. ollama
   pulls `qwen3.5:27b` as Q4_K_M silently; vLLM reads from `config.json`),
   the manifest records `provider_default` and the doc header marks
   `[quant = provider default — declare explicitly if reproducible]`.

## Deliverables

### Sidecar manifest
- New module: `src/aegis_phase1/llm/quant_manifest.py` (~330 LoC, stdlib only).
- Layout: `<root>/<provider>/<model>@<quant>.json` (root default
  `$HOME/aegis_quant_manifests/`, override with `AEGIS_QUANT_MANIFEST_ROOT`).
- Schema v1 fields: `schema_version`, `model`, `provider`, `quantization`,
  `quantization_provenance` (one of `ollama-pull | hf-stage | provider_default |
  user-declared | vllm-served`), `pulled_at`, `source`, `size_bytes`,
  `digest_sha256` (head 16 MiB), `digest_method`, `vllm_compat`, `notes`.
- Tests: `tests/unit/llm/test_quant_manifest_corr111.py` (36/36 passing —
  schema, IO, helpers, frontmatter, stdlib-only AST guard).

### Pull / stage scripts
- New: `examples/deucalion/pull-ollama-model-aegis.sbatch` — Ollama pull
  + sidecar (one model per sbatch; trivial wrapper around the helper).
- New: `examples/deucalion/stage-hf-model-aegis.sbatch` — HF stage
  + sidecar (writes provenance `hf-stage`).
- Both register in `execution/contracts/CONTRACT-111.md` so future agents
  know which script to copy for new models.

### Invoker reporting (Fase 2)
- `UnifiedInvoker.invoke()` and `TransformersInvoker.invoke()` prepend the
  `<!-- aegis:model=… provider=… quant=… job=… spec=… ts=… -->` line to
  every value returned in `state["per_spec_markdown"][spec]`.
- `state["v2_model_capabilities"]` is created (if not present) with
  `{model, provider, quantization, provenance, manifest_path}` — populated
  by the first LLM call of the run.

### Doc headers (Fase 3)
- Renderers `v2/output/*.py` inject a single leading line on Doc 01-09:
  `Model: <model> @ <quant> (job <job>)` plus caveats when applicable.
- Renderers strip the `aegis:` HTML comment so it never leaks into the
  user-facing doc.

### Digests (Fase 3)
- Per-spec sidecar: each digest row carries a `Quant` column + `Hash` +
  `Provenance`. Rows where `Quant` is `unknown` are clearly marked.

## Files added / modified

| Path | Status |
|---|---|
| `src/aegis_phase1/llm/quant_manifest.py` | new |
| `tests/unit/llm/test_quant_manifest_corr111.py` | new (36 tests) |
| `examples/deucalion/pull-ollama-model-aegis.sbatch` | new |
| `examples/deucalion/stage-hf-model-aegis.sbatch` | new |
| `src/aegis_phase1/llm/unified.py` | modified (frontmatter prepend) |
| `src/aegis_phase1/llm/transformers_invoker.py` | modified (frontmatter prepend) |
| `src/aegis_phase1/v2/llm.py` | modified (populate `v2_model_capabilities`) |
| `src/aegis_phase1/v2/orchestrator.py` | modified (initialize the capability key) |
| `src/aegis_phase1/v2/output/*.py` | modified (header line + comment strip) |

## Acceptance

- A1. `PYTHONPATH=src ./.venv/bin/python -m pytest tests/unit/llm/test_quant_manifest_corr111.py` passes 36/36.
- A2. `bash .hooks/ci-frameworks.sh` still passes (no new framework refs).
- A3. After a `pull-ollama-model-aegis.sbatch` run, the produced sidecar
  file exists and `python -m aegis_phase1.llm.quant_manifest` lists it.
- A4. After a scout on any model, the Doc 01 markdown shows
  `Model: <model> @ <quant> (job <job>)` as the first line.

## Risks

- **R1 (small)**: Renderers today assume content begins with the first
  heading. We must inject the header line + a blank line so subsequent
  regex extraction still works. Covered by header-comments and a follow-up
  smoke test (Doc 01 parser).
- **R2 (low)**: Old digests don't have the `Quant` column — they show
  `Quant = unknown`. That's intentional (per user decision 1); readers must
  understand this metadata drift.
- **R3 (none)**: Methodology-main is untouched; PROMPTS/ is not part of
  this contract.

## Follow-ups (out of scope)

- (FU-1) Backfill manifests for the 8 historical Ollama scouts from
  `ollama show <model> --json` readings already on disk
  (`$WORK/ollama_data/models/manifests/…`). Non-blocking.
- (FU-2) Decide whether `state["v2_model_capabilities"]["quantization"]`
  should be a hard gate for downstream evaluator comparisons. Currently a
  soft warning only.

## Open questions

None — user decisions locked.
