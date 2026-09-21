# CONTRACT-116 — Pipeline staging: offline parser replay + retry-with-feedback + LLM scale-up

**Status:** ACTIVE (2026-09-09)
**Branch:** `feature/aegis-p1-corr-116-pipeline-staging`
**Base:** HEAD of `main` (post-CORR-113/114/115 merge)
**Decision date:** 2026-09-09
**Author:** Planner
**Sprint contracts:** `execution/contracts/SC-2026-22.json` (S1 parser replay), `SC-2026-23.json` (S2 retry feedback), `SC-2026-24.json` (S3 LLM scale-up). Sprinked into this branch in sequence.
**Predecessors:** CORR-114 (run_all partial-docs fix), CORR-108 (P1C-01 parser fix)
**Spec:** this document §3 is the spec.

---

## 1. Resumo executivo

The pipeline's MAP stage aborts 10/10 lanes with `markdown_parse_error` on real
models, and the retry loop is blind (`invoker.py:373-437`) — three identical
attempts at temperature 0 produce identical failing output, then stop. That is
the GLM-4.7-flash P1B symptom and the chief reason aegis c1/c2/c3 all exit 2.

We have 948 raw LLM responses stored verbatim under
`output/phase1/raw/<SPEC>/*.md` (and 2235 entries in `logs/phase1/llm-calls.jsonl`)
from prior real runs. We will use them to (a) diagnose where the parsers fail
without spending any GPU time, (b) fix the parsers, (c) close the blind-retry
hole, and only then run scaled-up LLM tests on Deucalion.

The contract fixes parsers + retry first. RefGate fixes are out of scope
unless S1's matrix shows them to be dominant.

---

## 2. Decisões aprovadas

1. **Staged scale-up, each gate blocks the next.** Order: S1 (offline replay)
   → S2 (retry feedback) → S3 (Deucalion 1-call → 1-domain → run-all).
2. **Offline replay harness is the first deliverable.** It must report a
   per-spec failure matrix (spec × model × error_class) so subsequent fixes
   are guided by data, not hunches.
3. **No raw-response file deletion.** S1 only reads the existing corpus; new
   runs (if any) land alongside, never overwrite.
4. **Retry feedback reuses the RefGate feedback channel.** No new
   infrastructure — extend the existing `feedback_prompt`/`previous_response`
   injection in `invoker.py:_attempt`. `max_retries` stays at 3.
5. **LLM scale-up uses Deucalion dev-a100-40 with nemotron-3.5-lightning:30b**
   (proven-fastest strong model on cluster per CyberMetric 2026-09-08) at
   30-min walltime per smoke. case1-tinytask only.
6. **1 branch per sequence, 1 PR at the end.** This contract owns 3 sprints
   → 3 commits (S1, S2, S3) on `feature/aegis-p1-corr-116-pipeline-staging`.
7. **Baseline preserved.** `pytest tests/unit/ -m "not slow"` finishes with
   no NEW failures vs the documented 48 pre-existing infrastructure failures
   (Ollama/Langfuse absent locally).
8. **No renderer changes, no Neo4j, no Langfuse.** S3 stops at run-all output
   — no eval/judge pass (separate CORR-074/112 work).

---

## 3. Architecture (the spec)

### 3.1 Current state (what fails)

```
LLM raw markdown  ──▶  RobustParser (invoker.py:618)
                          │
                          ▼
                    registered parser (MARKDOWN_PARSERS[spec].parse(raw))
                          │ returns (parsed_model, error_str)
                          ▼
                    parsed_model is None?  ──▶  markdown_parse_error (invoker.py:695)
                                                    │
                                                    ▼
                                              validation_result = invalid
                                              NO feedback injected
                                              attempt N+1 = attempt N verbatim (temp 0)
                                              │
                                              ▼
                                              3× identical failures → status FAILED_AFTER_RETRIES
```

### 3.2 Target state (what S1 + S2 fix)

```
LLM raw markdown  ──▶  RobustParser (unchanged)
                          │
                          ▼
                    registered parser (improved, guided by S1 matrix)
                          │
                          ├── returns (model, None)        ──▶ S1 fix #1: parser handles more template variants
                          │
                          ├── returns (None, "no_headers") ──▶ S2 fix: emit feedback into attempt N+1
                          │                                       "Missing required ## Status + ## Sections headers.
                          │                                        Re-emit using template: <excerpt>"
                          │
                          └── returns (model, gate_violation) ──▶ unchanged (RefGate feedback, CORR-112)
```

### 3.3 S1 — Parser replay harness

- **File:** `scripts/eval/parser_replay.py`
- **Inputs:**
  - `output/phase1/raw/<SPEC>/<ts>__attemptN.md` (verbatim raw responses)
  - `--specs P1B-LLM-01-INTERPRETATION,P1C-LLM-01-OVERLAP-CLASSIFICATION,...` (default: all 5)
  - `--models gemma4:e4b,nemotron-3.5-lightning:30b,...` (default: scan all .md frontmatter)
  - `--limit N` per spec (default: 50 to keep first run fast)
- **Output:**
  - `execution/reports/parser_replay_<ts>.md` — human summary table (rows = spec, cols = model; cells = pass/N+parse_error/N+gate_violation/N+other)
  - `execution/reports/parser_replay_<ts>.json` — full per-file outcome record with first 200 chars of failure for triage
  - `execution/reports/parser_replay_<ts>_failures.md` — one block per failure class with the offending raw excerpt (≤300 chars) so the next fix has a target
- **Algorithm:**
  - For each `*.md` under `output/phase1/raw/<SPEC>/`:
    1. Parse YAML frontmatter for `model`, `status`, `spec_id`, `attempt`.
    2. Extract the body after `## Raw response\n`.
    3. Call `MARKDOWN_PARSERS[spec_id]().parse(body)`.
    4. If `parsed_model is None`: classify failure:
       - `'no_headers'` if parser error contains 'no header' / 'no `##`'
       - `'no_status_section'` if error mentions 'Status'/'status'
       - `'missing_int'` / `'missing_der'` / `'shape_a_misread'` per spec-specific signatures (best-effort regex on the error message; not exhaustive)
       - `'gate_violation'` if parser returned a model but RefGate raised (run gate independently on parsed model)
       - `'other'` otherwise
    5. Record outcome + status from frontmatter (so we can split parse-OK
       from raws that were already FAILED_AFTER_RETRIES in the original run).
  - Aggregate counts per (spec × model × error_class).
- **Exit code:** 0 (always — informational harness).
- **Dependencies:** existing `aegis_phase1._archive.corr061.markdown_parser.MARKDOWN_PARSERS`, `aegis_phase1.prompts_v2.ref_gate.RefGate`.

### 3.4 S2 — Retry feedback for parse errors

- **File modified:** `src/aegis_phase1/prompts_v2/invoker.py` (`Phase1LLMInvoker._attempt`)
- **Change:**
  - When `markdown_parse_error` fires and we still have retries left, build
    a feedback string: `"Your previous response did not match the expected
    markdown template. Parser error: {err}. Required structure: <excerpt of
    template for this spec>."`
  - Inject it via the existing `feedback_prompt` field, alongside the raw
    response (as `previous_response`), **exactly** how RefGate already
    injects its feedback (`invoker.py:375-378`, :390-394).
  - `max_retries` unchanged. `temperature=0` unchanged.
- **Test:** add a unit test that drives a `MockInvoker` returning
  `"no headers, just prose"` on attempt 1 and a valid markdown on attempt 2;
  assert the attempt 2 user prompt contains the error feedback text.
- **Compatibility:** no behaviour change when the parser succeeds on
  attempt 1 (the common case) — feedback is only injected on the failure
  branch.

### 3.5 S3 — Deucalion scale-up

- **Scope:** case1-tinytask only (GDPR+CRA, smallest YAMLs, ~54 clauses).
- **Sequence** (each gates the next):
  - **3a:** 1 LLM call — P1B-01 on GDPR, 30 min walltime. Gate: raw in
    `output/phase1/raw/P1B-LLM-01-INTERPRETATION/`, parser succeeds offline.
  - **3b:** `--run-phase-1b` case1 (4 calls). Gate: `rationale_by_reg` has
    2 entries (GDPR + CRA).
  - **3c:** `map_single_domain("D-01")` (programmatic). Gate: 0 parser
    failures for that one lane. Then `--map-only` case1 (10 lanes). Gate:
    ≤2 lanes failed (corresponds to the documented threshold).
  - **3d:** `--run-all` case1 (full pipeline, 9 docs + xlsx). Gate: exit 0.
- **Cluster discipline:** local validation battery (bash -n + ruff + py_compile +
  smoke) before every sbatch. Walltime budgets per skill
  `hpc-deucalion` (30 min for 1B, 1.5h for scout-full, 8h for run-all — but
  case1 is small, expect ≤1h).
- **Deferral:** `--map-only` and `--run-all` on case2/case3, and the
  remaining 4 strong models, are NOT in this contract. They become a
  follow-up CORR after this one is merged and case1 is green end-to-end.

---

## 4. Files delivered (target)

### Created

| File | Lines (~) | Purpose |
|------|----------:|---------|
| `scripts/eval/parser_replay.py` | ~150 | S1 harness |
| `scripts/eval/__init__.py` | 0 | Package marker (if missing) |
| `tests/unit/eval/test_parser_replay_corr116.py` | ~80 | Unit test for S1 harness |
| `execution/CONTRACT-116.md` | this | Contract document |
| `execution/contracts/SC-2026-22.json` | ~200 | S1 criteria, default-FAIL |
| `execution/contracts/SC-2026-23.json` | ~150 | S2 criteria, default-FAIL |
| `execution/contracts/SC-2026-24.json` | ~200 | S3 criteria, default-FAIL |
| `execution/reports/parser_replay_<ts>.{md,json}` | (output) | S1 outputs |

### Modified

| File | Change |
|------|--------|
| `src/aegis_phase1/prompts_v2/invoker.py` | S2: parse-error feedback injection (~10 lines) |
| `tests/unit/prompts_v2/test_invoker_retry_corr116.py` | S2 unit test (new file, listed above) |

Total: ~7 new files, 1 modified, ~600 LOC added (not counting report outputs).

---

## 5. Acceptance criteria summary

Full default-FAIL criteria with executable commands live in:
- `SC-2026-22.json` — S1: parser replay harness
- `SC-2026-23.json` — S2: retry feedback injection
- `SC-2026-24.json` — S3: LLM scale-up

All criteria are MUST with Tier 3 (behavioural) validation. Each must end
with `passed: true` + observed evidence before being committed.

---

## 6. Risks and out-of-scope

| Risk | Mitigation |
|------|------------|
| Raw corpus is too small / too biased for S1 to be representative | `--limit 50` default; matrix reports N= per cell; if N<10 cells are empty, note as warning |
| S2 feedback injection changes behaviour in untested cases (e.g. when parser succeeds but RefGate later fails) | Feedback only on `parsed_model is None` branch — RefGate branch is untouched |
| S3 cluster run queue contention (dev-a100-40 congested in past) | Fall back to dev-a100-80 if Priority reason persists >30 min (skill rule) |
| GLM-4.7-flash P1B still loops after S2 (because parser cannot recover even with feedback) | Out of scope — captured as known limitation in S3 report |

| Out of scope |
|--------------|
| RefGate rule fixes (only analysed, not edited, by S1) |
| Eval / judge pass (separate CORR-074/112 contract) |
| Case2/case3 + remaining models (follow-up CORR after merge) |
| Option D (exit 2 → 0 reclassification) — re-evaluated post S1 |
| Neo4j KG writes (separate CORR-115) |
| Langfuse / observability changes |
