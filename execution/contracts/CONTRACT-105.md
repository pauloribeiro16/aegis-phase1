---
contract: CONTRACT-105
title: CORR-105 — Eval framework: judge GLM-5.3-Flash + digest-first workflow
status: ACTIVE
created: 2026-09-01
author: opencode (MiniMax-M3)
branch: feature/aegis-p1-corr-105-eval-framework
scope: docs + 1 read-only eval script
depends_on: CONTRACT-074, CORR-100..103 (specs + parser, in main)
---

# CORR-105 — Eval framework

## Goal

Provide a **consistent, reproducible** way to compare LLMs on the AEGIS-KG
Phase 1 pipeline. The output is small and decision-supporting, not a
research paper.

**Constraint (user explicit, 2026-09-01):**
- Judge = **GLM-5.3-Flash** (the operating model in this ZCode session),
  NOT M3 (M3 stays as the gold reference / teacher).
- Human (you) must remain able to spot-check each judge verdict in
  ≤1 page per run, regardless of how many tokens the run produced.
- **No new dependencies** (no DeepEval, Ragas, promptfoo, etc.).
- Methodology-main is **untouched** (stable pin — see
  `feedback/methodology-main-stable-pin.md`).

## Scope

| File | Action | Purpose |
|---|---|---|
| `execution/reports/EVAL_PROTOCOL.md` | create | Judge identity, rubric L1–L5, anti-bias, repro rules, digest format |
| `execution/reports/model_matrix.md` | create | Scorecard matrix: model × spec × L1–L5 |
| `execution/reports/digests/<model>_<jobid>.md` | create per run | ≤1 page judge digest: "Faz bem / Faz mal / Evidência" per spec |
| `scripts/eval/generate_report.py` | extend | Add `OllamaJsonlIngest` (new runs) and `ParserGate` (calls `P1*LLM*Parser` directly) |
| `tests/unit/scripts/test_eval_extensions.py` | create | Stdlib-only fixtures + 4 tests |

## Rubric (L1–L5)

| Layer | What | Deterministic? | Tool |
|---|---|---|---|
| L1 Contract | parse OK; required fields populated; minItems respected; no empty arrays in critical fields | YES | `P1*LLM*Parser.parse()` |
| L2 Grounding | `layer0_refs` resolve to file/section; `company_fact_refs` resolve to DOC04:* keys; legal refs exist in preproc; TIPO2/TIPO3 IDs exist in ontology | YES | regex + canonical lookup |
| L3 Content quality | substance of rationale vs gold M3; precision of regulatory references; actionable specificity; not just length | NO (LLM judge) | rubric 1–5 per cell; always with **evidence quote** |
| L4 Downstream | REDUCE receives what it needs; Doc 06/07/07b complete; Doc 04b maturity variance (low = flat score = bad) | YES | parse artefacts |
| L5 Cost | tokens/call, walltime, tok/s, retries | YES | jsonl aggregation |

## Anti-bias rules (judge)

- **Anti-verbosity**: rubric explicitly penalises padding (criterion
  "specificity per 100 chars"). qwen3.8 writes more than qwen3.5 —
  this stops raw length from biasing scores.
- **Anti-self-preference**: judge model family ≠ student family
  (students: qwen, gemma, glm; judge: GLM-5.3-Flash). If a qwen or
  glm-4 family is added as student later, swap judge.
- **Anti-fabrication of evidence**: judge may only quote text actually
  present in the raw digest chunk; if it cannot find evidence, it
  must output "NO EVIDENCE" rather than paraphrasing.

## Repro

Every digest records:
- judge model + version (`GLM-5.3-Flash via ZCode, <date>`)
- case + run name + JOB ID
- commit SHA of the repo (git rev-parse)
- preproc SHA (already captured in the run's state.json)
- a "judge confidence" field (high/medium/low) so the user knows
  when to spot-check harder.

## Digest format (1 page per spec)

```markdown
### <spec> — <model> — JOB <id>
**Status:** OK|SKIP|FAIL  |  **Confidence:** H|M|L
**L1:** …  **L2:** …  **L3:** …  **L4:** …  **L5:** …

**Faz bem (com evidência)**
- …quote from raw… (location: <file>:<line>)

**Faz mal (com evidência)**
- …quote from raw… (location: <file>:<line>)

**Verdict** (1 frase)
```

## Out of scope

- New Python deps
- Spec changes in Methodology-main
- Code changes in `src/` (the checker reads `output/`, never mutates)
- Automated regression on every commit (deferred — would need CI
  integration + cached jsonl + deterministic eval container)

## Risks

| Risk | Mitigation |
|---|---|
| Parser is sensitive to slight spec edits | checker uses `MarkdownParser` import; if the parser refuses to run, L1 surfaces the error explicitly |
| OllamaJsonl format differs from legacy (no top-level `prompt_spec_id`) | already handled in the existing `generate_report.py` (CORR-058 path); new ingest layer just extends the shape detection |
| Judge drift across sessions | every digest logs the judge version + ZCode session id |
| Digest too long | hard cap: 1 page / spec; if > 1 page, the judge must compress, not expand |

## Acceptance

1. `python scripts/eval/generate_report.py --help` shows the new flags.
2. `pytest tests/unit/scripts/test_eval_extensions.py -q` passes.
3. `EVAL_PROTOCOL.md` + `model_matrix.md` exist in repo.
4. At least one digest produced for a completed run (qwen3.5 runall
   or qwen3.8 scout — both already in `Deucalion/results/`).
5. When the run-all qwen3.8 (JOB 1862843) lands, a third digest is
   added and `model_matrix.md` is updated.