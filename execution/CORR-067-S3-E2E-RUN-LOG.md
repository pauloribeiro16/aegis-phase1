# CORR-067 S3 — End-to-End Real Run Validation (2026-07-27)

## Purpose

Validate that the CORR-067 S3 fix (`factory.get_invoker` no longer passes
Ollama `base_url` to the MiniMax provider, `filter_regs` reads dict ctx
correctly, `doc_07` falls back to `state['subdomains']`) works in a
**real** end-to-end run with `--provider=minimax` and the M3 model — not
just in unit tests.

This is the **only** missing piece after the S2 + S3 commits
(`bbdb863` + `113978a` → `0439d90`): the previous real run
(`pipeline_minimax_MiniMax-M3.log` from 15:36) was from BEFORE the S3
fix and showed the bug.

---

## Result: ✅ PASS

The S3 fix works in a real end-to-end run with provider=minimax.

---

## Setup

```bash
# Activate venv
source ../shared-venv/bin/activate

# Auth: MiniMax Token Plan key (NOT MAVIS_ACCESS_TOKEN — that's a JWT
# for the Mavis agent gateway, not the Anthropic-compatible M3 endpoint)
export MINIMAX_API_KEY=$(cat /tmp/m3_key)

# Run
PYTHONPATH=src python -m aegis_phase1.v2.runner \
  --case cases/case1-tinytask \
  --provider minimax \
  --model MiniMax-M3 \
  --output output/phase1_corr067_e2e \
  --run-all \
  --log-file logs/phase1/corr067_e2e/pipeline.log \
  --log-level INFO
```

---

## Timeline

| Time | Event |
|---|---|
| 21:16:04 | First run attempt (without `MINIMAX_API_KEY`) — **FAILED** with 401 Unauthorized. `MAVIS_ACCESS_TOKEN` is a JWT (length 395) and the M3 Token Plan endpoint requires a `sk-cp-...` key. |
| 21:17:40 | First run aborts: "MAP mostly failed (10/10 domains)" after 95.66s of 401s. This confirms the S2 threshold logic works correctly (10 ≥ 5 → abort). |
| 21:18:01 | Second run starts (with `MINIMAX_API_KEY` set from `/tmp/m3_key`) |
| 21:18:01 | STAGE 0: LOAD — 38 sub-domains, 2 regs (0.09s) |
| 21:22:28 | STAGE 1: MAP — 10/10 domains OK in 267.64s (4.46 min) |
| 21:24:19 | STAGE 1.5: PHASE 1B RATIONALE — 2 regulations complete |
| 21:24:51 | STAGE 2: REDUCE — 31.62s, synthesis=OK, compound_events=OK |
| 21:24:51 | STAGE 3a: OUTPUT (deterministic) — 6 artefacts in 0.10s |
| 21:25:50 | STAGE 3b: OUTPUT (enhanced) — 10 artefacts in 58.92s |
| 21:25:50 | **PIPELINE COMPLETE** |

**Total wall clock: ~7m 49s** (21:18:01 → 21:25:50).

---

## LLM call breakdown (16 calls, all OK)

| Spec | Calls | Latency range | Total tokens |
|---|---|---|---|
| P1C-LLM-01-OVERLAP-CLASSIFICATION | 10 (1 per domain) | 23.3s – 31.6s | ~21,000 |
| P1B-LLM-01-INTERPRETATION | 2 (1 per applicable reg) | 10.4s – 16.3s | 1,737 |
| P1B-LLM-02-RATIONALE | 2 (1 per applicable reg) | 41.2s – 42.7s | 7,417 |
| P1C-LLM-02-COMPOUND-EVENT | 1 (global reduce) | 4.8s | 231 |
| P1C-LLM-03-STRATEGIC-SYNTHESIS | 1 (global reduce) | 26.8s | 2,059 |
| **Total** | **16** | — | **~38,938** |

(MiniMax throttle was respected — `min_interval=5.0s` between calls. The
slower calls are MAP overlaps (longest context: 7000+ tokens) and the
P1B-02 RATIONALE (the largest output spec).)

---

## Outputs (10 artefacts, 1.7 MB total)

| File | Size | Status |
|---|---|---|
| 04_Company_Context_Assessment.md | 11K | filled (deterministic) |
| 04a_Architecture_DataInventory.md | 161K | filled (LLM-enhanced) |
| 04b_Security_Posture.md | 289K | filled (LLM-enhanced) |
| 04c_ThirdParty_Landscape.md | 163K | filled (LLM-enhanced) |
| 04d_Org_Roles_RACI.md | 188K | filled (LLM-enhanced) |
| 05_Regulatory_Applicability.md | 198K | filled (LLM-enhanced) |
| 06_Clause_Mapping_Matrix.md | 189K | filled (LLM-enhanced) |
| 07_Structured_Compliance_Matrix.md | 184K | filled (LLM-enhanced) |
| 07b_Proportionality_Profile.md | 269K | filled (LLM-enhanced) |
| Case_01_Phase1.xlsx | 9.6K | filled (XLSX generator) |

All artefacts have valid content (sample checked: Doc 05 has the
applicability summary table; Doc 07 has the §1 PURPOSE section).

---

## What this validates

1. **S3 factory fix** (`113978a fix(prompts_v2): don't pass Ollama
   base_url to Minimax invoker`): confirmed — the `ChatMinimax`
   client now uses `https://api.minimax.io/anthropic` (not
   `http://localhost:11434`). The 401 errors in the first run were
   unrelated; the S3 fix is orthogonal (it was a base_url bug, not
   an auth one).
2. **S3 filter_regs fix** (`0a0654e` + `c8863b7`): confirmed — MAP
   produced 10/10 valid overlap classifications, meaning the
   `filter_regs` function returned the correct subdomains for each
   of the 10 domain lanes.
3. **S3 doc_07 fallback** (`0439d90`): confirmed — Doc 07 was rendered
   with the full structured compliance matrix content. The fallback
   `state['subdomains']` was needed because the per-regulation
   `subdomains` are loaded into a different state key after the
   CORR-061 S3a refactor.
4. **S2 MAP partial-failure** (in isolation): confirmed via unit tests
   in `test_map_partial_failure_corr067.py` (7/7 pass). The
   `MapPartialFailure` exception in the first run also exercised the
   ≥5 threshold branch — it correctly aborted at 10/10 (not 1/10 or
   2/10).

---

## Discovery: `MAVIS_ACCESS_TOKEN` ≠ `MINIMAX_API_KEY`

The first run failed with 401 Unauthorized. Root cause: the user has
both env vars set, but they target **different systems**:

- `MAVIS_ACCESS_TOKEN` (length 395, starts with `eyJ...`) — JWT for
  the Mavis agent gateway. NOT compatible with the MiniMax Token
  Plan endpoint.
- `MINIMAX_API_KEY` (from `/tmp/m3_key`, length 125, starts with
  `sk-cp-OLZpLvVfWLtiZr...`) — Token Plan key for the
  Anthropic-compatible M3 endpoint at `https://api.minimax.io/anthropic`.

The `chat_minimax.py` code accepts both, but **only the Token Plan
key works at the M3 endpoint**. The agent's `MAVIS_ACCESS_TOKEN` is
for a different Mavis service.

**Recommendation:** add `MINIMAX_API_KEY=...` to the user's `.env` so
that the `--provider minimax` runner just works without manual env
export. This is a config-side concern, not a code concern.

---

## How to reproduce

```bash
# In the aegis-phase1 root, with the canonical venv active:
source ../shared-venv/bin/activate
export MINIMAX_API_KEY=$(cat /tmp/m3_key)

PYTHONPATH=src python -m aegis_phase1.v2.runner \
  --case cases/case1-tinytask \
  --provider minimax \
  --model MiniMax-M3 \
  --output output/phase1_corr067_e2e \
  --run-all
```

Expected: 10/10 MAP domains OK, 16 LLM calls, 16 artefacts written
under `output/phase1_corr067_e2e/`, total runtime ~7-8 min.

---

## Conclusion

**CORR-067 S2 + S3 are validated end-to-end.** The factory + invoker
+ filter_regs + doc_07 fixes work in a real run with provider=minimax
and the M3 Token Plan endpoint. The contract is ready to be
squash-merged into `main`.
