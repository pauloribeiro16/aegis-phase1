# EVAL_PROTOCOL — AEGIS-KG Phase 1 model evaluation

**Status:** ACTIVE (CORR-105)
**Created:** 2026-09-01
**Owner:** opencode (GLM-5.3-Flash via ZCode)

This protocol produces small, decision-supporting artefacts to compare
LLMs running the AEGIS-KG Phase 1 pipeline. It is **not** a research
benchmark — it is a working scorecard that the user can read end to end
each cycle.

---

## 1. Judge identity

| Role | Model | Where it lives |
|---|---|---|
| **Judge** | GLM-5.3-Flash (operating model in ZCode, this session) | Local — invoked by the assistant, never on cluster |
| **Gold / teacher** | M3 (Anthropic via Mavis) | Used as the reference answer, **not** as judge |
| **Students** | qwen3.5:27b, qwen3.8:27b, gemma4:e2b, … | Run on Deucalion |

**Why GLM-5.3-Flash, not M3:**
- decouples judging from the gold (avoids self-enhancement bias);
- runs locally (no cluster cost, no API quota);
- lets the user audit each verdict in the chat (no need to spin up
  another job);
- consistent: the judge is always present in the conversation.

**Every digest records:** `judge = GLM-5.3-Flash via ZCode,
<commit_sha>, <session_id>, <date>`.

---

## 2. Rubric (5 layers)

| Layer | What | Deterministic? | Tool / source |
|---|---|---|---|
| **L1 Contract** | parse OK; required fields populated; `minItems` respected; no empty arrays in critical fields | YES | `MarkdownParser` (per spec) + `Phase1Validator` |
| **L2 Grounding** | `layer0_refs` resolve to file/section; `company_fact_refs` resolve to DOC04:*; legal refs exist in preproc; TIPO2/TIPO3 IDs exist in ontology; D-XX.Y IDs are in scope | YES | regex + canonical lookup |
| **L3 Content quality** | substance vs gold M3; precision of regulatory references; actionable specificity; **not** raw length | NO (LLM judge) | rubric 1–5 per cell, with evidence quote |
| **L4 Downstream** | REDUCE received what it needs; Doc 06/07/07b complete; Doc 04b maturity variance (low = flat score = bad signal) | YES | parse artefacts |
| **L5 Cost** | tokens/call, walltime, tok/s, retries | YES | jsonl aggregation |

Each cell produces a value: `PASS / WARN / FAIL / N/A` for L1/L2/L4;
`1–5` for L3; raw numbers for L5. The scorecard's last column is
**verdict** = the smallest L-layer that fails.

---

## 3. Anti-bias rules

| Bias | Risk in AEGIS | Mitigation |
|---|---|---|
| **Verbosity** | qwen3.8 writes ~30% more chars than qwen3.5; raw length ≠ quality | Rubric criterion `specificity per 100 chars` (penalises padding); no length bonus |
| **Self-preference** | if M3 ever judged students, qwen-style prose would systematically lose | Judge is a **different family** (GLM); if a qwen or glm-4 student is added later, swap judge |
| **Position bias** | only matters for pairwise; we don't use pairwise | N/A — we judge single answers vs gold |
| **Evidence fabrication** | LLM judges tend to invent plausible-looking quotes | Judge **may only quote text actually present** in the digest chunk; if not found, output `NO EVIDENCE` rather than paraphrase |

---

## 4. Workflow (digest-first)

```
Deucalion run completes
  └──> rsync output/run_<model>_<JOBID>/  →  Deucalion/results/
        └──> python scripts/eval/generate_report.py \
              --jsonl ... --preproc ... --output-md ... --output-json ...
              (L1, L2, L4, L5 — deterministic)
        └──> Judge pass (GLM-5.3-Flash, chunked over raws) → L3 verdict
              └──> write execution/reports/digests/<model>_<jobid>.md
                    └──> update execution/reports/model_matrix.md
                          └──> commit on the eval branch
```

**Cadence:** one cycle per Deucalion run. Cycle takes <1 hour locally.

---

## 5. Digest format (≤1 page per spec)

```markdown
### <SPEC> — <model> — JOB <id>

**Status:** OK | SKIP | FAIL        **Confidence:** H | M | L

| Layer | Value | Note |
|-------|-------|------|
| L1 Contract | PASS/WARN/FAIL/N/A | … |
| L2 Grounding| PASS/WARN/FAIL/N/A | … |
| L3 Quality  | 1–5 | one-line rationale |
| L4 Downstream| PASS/WARN/FAIL/N/A | … |
| L5 Cost     | tok/s, walltime | … |

**Faz bem (com evidência)**
- "<exact quote from raw>" — <file>:<line>

**Faz mal (com evidência)**
- "<exact quote from raw>" — <file>:<line>
  (or "NO EVIDENCE" if the verdict is by absence)

**Verdict:** <one sentence>
```

The digest is what the user reads. The raw outputs stay in
`Deucalion/results/<run>/` for audit. Total per-run reading load for the
user: **≤ 1 page × 5 specs = 5 pages**, regardless of how many tokens
the run produced.

---

## 6. Scorecard (model_matrix.md)

Single table, updated each cycle:

```
| Spec | Layer | M3 (gold) | gemma4:e2b | qwen3.5:27b | qwen3.8:27b |
```

- M3 column is the expected baseline (filled once at protocol start).
- Other columns are filled by the checker + judge per run.
- Empty cells mean "not yet measured", not "failed".

---

## 7. Repro requirements

Each digest and each scorecard update must record:

- judge model + version (`GLM-5.3-Flash via ZCode, <date>`)
- commit SHA of the repo (`git rev-parse HEAD`)
- preproc SHA (already in `state.json`)
- case name + run dir + JOB ID
- judge confidence per spec (H/M/L) — lets the user know when to
  spot-check harder

If any of these is missing from a digest, the digest is **not
acceptable** and must be re-issued.

---

## 8. What this protocol does NOT do

- It is **not** a regression test (no CI integration yet — deferred
  until we have a deterministic eval container).
- It does **not** change the parser, the prompts, or the specs
  (Methodology-main is a stable pin).
- It does **not** introduce new Python dependencies.

---

## 9. References

- MT-Bench paper (Zheng et al., 2023) — introduced LLM-as-judge and
  documented position / verbosity / self-enhancement biases.
- arXiv 2604.25359 — schema compliance is not enough; per-field
  evaluation is needed.
- ACM 2025 (10.1145/3731120.3744592) — Correctness is not Faithfulness;
  up to 57% of citations are post-hoc rationalisations.
- Watershed — multi-step LLM eval framework (component-level metrics
  for stage-wise diagnosis).