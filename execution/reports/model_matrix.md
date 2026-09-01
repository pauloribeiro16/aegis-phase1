# Model matrix — AEGIS-KG Phase 1

**Source of truth** for the per-model scorecard. Updated each cycle by
the judge (GLM-5.3-Flash via ZCode) on each completed Deucalion run.
See `EVAL_PROTOCOL.md` for the rubric and `digests/` for per-run detail.

**Legend:**
- **L1** PASS / WARN / FAIL / n/a (deterministic parser gate)
- **L2** PASS / WARN / FAIL / n/a (grounding; deterministic)
- **L3** 1–5 (judge verdict; gold = M3 = 5 by construction)
- **L4** PASS / WARN / FAIL / n/a (downstream artefacts present + variance)
- **L5** numbers only (tokens, tok/s, walltime)
- empty cell = not yet measured (not "failed")

---

## Last update

**2026-09-01 16:00 WEST** — judge = GLM-5.3-Flash via ZCode
**Branch:** `feature/aegis-p1-corr-105-eval-framework`
**Commit:** a710efd4fc309f72d54b0bc49b499a277e56e4e3

---

## Per-spec matrix

### P1B-LLM-01-INTERPRETATION (per-regulation interpretations + derogations)

| Model | JOB | L1 | L2 | L3 | L4 | L5 (tok/s) | Verdict |
|-------|-----|----|----|----|----|------------|---------|
| **M3 (gold)** | — | — | — | **5** | — | — | baseline |
| qwen3.5:27b | 1847659 | PASS | n/a | 4 | PASS | ~395 | **PASS** |
| qwen3.8:27b | 1862819 (scout) | PASS | n/a | 5 | PASS | ~610 | **PASS** |

### P1B-LLM-02-RATIONALE (per-regulation rationale + implications + gaps)

| Model | JOB | L1 | L2 | L3 | L4 | L5 (tok/s) | Verdict |
|-------|-----|----|----|----|----|------------|---------|
| **M3 (gold)** | — | — | — | **5** | — | — | baseline |
| qwen3.5:27b | 1847659 | PASS | n/a | 3 | PASS (Doc 05) | ~395 | **WARN** (implications/gaps empty) |
| qwen3.8:27b | 1862819 (scout) | PASS | n/a | 5 | PASS (Doc 05) | ~580 | **PASS** |

### P1C-LLM-01-OVERLAP-CLASSIFICATION (per-domain overlap activation)

| Model | JOB | L1 | L2 | L3 | L4 | L5 (tok/s) | Verdict |
|-------|-----|----|----|----|----|------------|---------|
| **M3 (gold)** | — | — | — | **5** | — | — | baseline |
| qwen3.5:27b | 1847659 | PASS (parser) | n/a | 1 | **FAIL** (0 activations; REDUCE skipped) | ~175 | **FAIL** |
| qwen3.8:27b | 1862819 (scout) | n/a | n/a | n/a | n/a | n/a | **PENDING** (run-all JOB 1862843) |

### P1C-LLM-02-COMPOUND-EVENT (cross-domain compound events)

| Model | JOB | L1 | L2 | L3 | L4 | L5 | Verdict |
|-------|-----|----|----|----|----|----|---------|
| **M3 (gold)** | — | — | — | **5** | — | — | baseline |
| qwen3.5:27b | 1847659 | **FAIL** (no LLM response) | n/a | n/a | **FAIL** (REDUCE skipped) | n/a | **FAIL** |
| qwen3.8:27b | 1862819 (scout) | not run | n/a | n/a | n/a | n/a | **PENDING** |

### P1C-LLM-03-STRATEGIC-SYNTHESIS (cross-lane strategic implications)

| Model | JOB | L1 | L2 | L3 | L4 | L5 | Verdict |
|-------|-----|----|----|----|----|----|---------|
| **M3 (gold)** | — | — | — | **5** | — | — | baseline |
| qwen3.5:27b | 1847659 | **FAIL** (no LLM response) | n/a | n/a | **FAIL** (REDUCE skipped) | n/a | **FAIL** |
| qwen3.8:27b | 1862819 (scout) | not run | n/a | n/a | n/a | n/a | **PENDING** |

---

## Cross-spec verdict (today)

| Model | P1B-01 | P1B-02 | P1C-01 | P1C-02 | P1C-03 | Full pipeline |
|-------|--------|--------|--------|--------|--------|---------------|
| **M3 (gold)** | ✓ | ✓ | ✓ | ✓ | ✓ | **YES** |
| qwen3.5:27b | ✓ | ⚠ | ✗ | ✗ | ✗ | **NO** (P1C-01 template fail) |
| qwen3.8:27b | ✓ | ✓ | — | — | — | **PENDING** |

---

## Open questions / follow-ups

1. **P1C-01 parser-following** — does qwen3.8 follow the
   `## Sub-domain Activations` template? Run-all JOB 1862843 will
   answer this within ~1 h.
2. **L2 grounding checker** — not yet wired (regex + canonical lookup
   for `layer0_refs`, `DOC04:*`, legal refs). Defer until the parser
   gate data stabilises.
3. **Activations counter** — `extract_refs_from_output` returns 0 even
   when `## Status / - applicable: YES` is present in the raw. Bug;
   will fix when the run-all data motivates the change.
4. **Maturity variance check (L4 detail)** — Doc 04b returns `1/1/1/1/1/1/1/1/1/1`
   for qwen3.5. Either model is conservatively flat or scorer
   over-collapses. Re-measure on qwen3.8 run-all and consider whether
   the maturity scorer needs calibration.
5. **gemma4:e4b P1C** — already noted in `corr074_e2b_validation.md`;
   not run on Deucalion.

---

## How to update this file

When a new run lands:

```bash
# 1. rsync the new run dir to the mirror
rsync -a <run_dir>/ Deucalion/results/<model>_<jobid>/

# 2. run the checker
PYTHONPATH=src python3 scripts/eval/generate_report.py \
  --run-dir Deucalion/results/<model>_<jobid> \
  --preproc preproc_out \
  --output-dir /tmp/<corr_id> \
  --output-md /tmp/<corr_id>/report.md \
  --output-json /tmp/<corr_id>/report.json \
  --use-parser-gate

# 3. read the digests and add a row here
# 4. update digests/<model>_<jobid>.md with the L3 verdict
```