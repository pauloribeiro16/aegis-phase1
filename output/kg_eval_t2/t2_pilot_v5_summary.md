# T2 Pilot v5 — 5 models × 8 tasks = 40 runs (post-5-fixes)

**Date:** 2026-09-05
**Branch:** `feature/aegis-p1-corr-115-kg-etl-foundation`
**Catalogue:** `scripts/kg_eval/tasks_t2.yaml` (8 tasks, 6 patterns: P0+, P1, P2, P3, P4, P5, P6)
**Scorer:** `scripts/kg_eval/score_t2.py` (5 dimensions per protocol v1.1 §8)
**Scorecards:** `output/kg_eval_t2/sc_18811{18,19,20,21,22}.json` (5 models, ornith dropped)

## v3 → v4 → v5 headline

| Pilot | Pass | Rate | Δ vs prev |
|---|:---:|:---:|:---:|
| v3 | 1/48 | 2.1% | — |
| v4 | 4/48 | 8.3% | 4× |
| **v5** | **11/40** | **27.5%** | **3.5× v4, 13× v3** |

**v5 dropped ornith-1.5:35b** (CUDA crash on engine cold-start, not a model bug — the engine never reached the model). Effective comparison is 5 models × 8 tasks = 40 runs.

## Fleet (5 models)

| Model | Pass | Avg q | Grounded tasks | Distinguishing pattern |
|---|:---:|:---:|:---:|---|
| qwen3.8:27b | **4/8** | 4.25 | 3 | Still leads. T2.3 (with useful negative), T2.4, T2.7, T2.2 |
| glm-4.7-flash:latest | **3/8** | 3.50 | 3 | **Surprise.** T2.2 / T2.5 / T2.7 — verification-aware after multi-node filter |
| nemotron-3.5-lightning:30b | 2/8 | 3.88 | 3 | T2.1 (new) + T2.7 (new). T2.6 regressed (source-fix flipped semantics under new scorer) |
| gemma4:31b | 1/8 | 5.50 | 2 | T2.5 — the only task it consistently over-explores correctly into |
| muse-glimmer:30b | 1/8 | 5.38 | 1 | Still over-explores (avg 5.38/6 budget). T2.2 — coincidental shape match |
| **Total** | **11/40** | **4.50** | **12** | — |

## Per-task pass-rate (v5 vs v4 excluding ornith)

| Task | v4 (-orn) | v5 | Δ | Notes |
|---|:---:|:---:|:---:|---|
| T2.1 case1-SYS01-grounding | 0/5 | **1/5** | +1 | nemotron — multi-hop system grounding finally clicked |
| T2.2 case3-D044-tension | 0/5 | **3/5** | +3 | P4 tension cracked (qwen3.8, glm-4.7, muse) — the broadest sweep yet |
| T2.3 case1-impossible-trio | 2/5 | 1/5 | −1 | qwen3.8 still passes (with useful negative); others regressed |
| T2.4 case2-NIS2-D010-scope | 1/5 | 1/5 | — | qwen3.8 still the only passer |
| T2.5 case3-D044-attributes | 0/5 | **2/5** | +2 | P3 proportionality partially solved — gemma4 + glm-4.7 |
| T2.6 case3-DS-GDPR-Art9 | 1/5 | 0/5 | −1 | nemotron regressed — source fix interaction with regex broaden needs re-audit |
| T2.7 case1-D091-SOs | 0/5 | **3/5** | +3 | Big win. P2/P5 single-node MATCH form hit (qwen3.8, glm-4.7, nemotron) |
| T2.8 case2-error-recovery | 0/5 | 0/5 | — | P6 still unsolved |

## Pass grid

| Task | gemma4 | glm-4.7 | muse-glimmer | nemotron | qwen3.8 |
|---|:---:|:---:|:---:|:---:|:---:|
| T2.1 | - | - | - | **P** | - |
| T2.2 | - | **P** | **P** | - | **P** |
| T2.3 | - | - | - | - | **P** |
| T2.4 | - | - | - | - | **P** |
| T2.5 | **P** | **P** | - | - | - |
| T2.6 | - | - | - | - | - |
| T2.7 | - | **P** | - | **P** | **P** |
| T2.8 | - | - | - | - | - |

## The 5 fixes that worked

1. **Regex broaden** — `score_t2.py` artefact-citation patterns now recognise csf/clauses/articles + 6 new shapes (subdomains, tiers, systems, data_subjects, SOs, SRs). The citation-quality axis went from "all-empty except occasional articles" to model-distinguishing.
2. **Useful-negative relaxed** — T2.3 absence declaration now reads "must say *why* nothing matches", not "must reference three siblings by exact ID". qwen3.8 retained the credit; glm-4.7's looser output no longer false-passes.
3. **Engine multi-node filter support** — `MATCH (a)-[r]->(b) WHERE b IN [...]` clauses now execute. T2.5 / T2.7 were structurally blocked before; with multi-node, three models resolved them at once.
4. **Pattern 2 worked example in SYSTEM_PROMPT** — explicit "answer must reference a *label*, not a paraphrase" example in the prompt. Models now cite at least one closed-set ID in 12/40 runs (vs ~1/48 in v4).
5. **Ornith dropped** — ornith-1.5:35b crashed with a CUDA driver fault on engine cold-start. Not a model-capability issue. Removed from the v5 fleet; SLURM err log updated.

## Grounding analysis

**12 of 40 runs cited at least one closed-set artefact** (vs ~1/48 in v4 — over 10×).
- nemotron / qwen3.8 / glm-4.7 each have **3 grounded tasks** (best in class)
- gemma4 has 2 (over-cites mid-reasoning; that's a partial signal — not always right)
- muse has 1

Per-task grounding (how many of 5 runs cited *something*):
T2.2 5/5 · T2.7 3/5 · T2.5 2/5 · T2.1 1/5 · T2.4 1/5 · T2.3 0 · T2.6 0 · T2.8 0

The 0s on T2.3 / T2.6 / T2.8 are expected: impossibility / no-data / error-recovery all encode "no answer", and citation is meaningless there.

## Discriminator

- **qwen3.8 = 4/8** — still the lead. The only model that gets T2.3 (impossible-trio with useful-negative), and one of three to get T2.7.
- **glm-4.7 surprise at 3/8** — flagged as "early terminator" in v4 (declared an answer after 1–3 queries without verifying). The multi-node filter + Pattern 2 worked example flipped its script: now it queries until something matches, then cites.
- **nemotron 2/8 (vs 1/8 v4)** — gained T2.1 (multi-hop) and T2.7 (single-node MATCH). Lost T2.6 — the source-fix + regex broaden interaction needs an audit (a deliberate artefact citation now trips a different scorer rule).
- **muse and gemma4 still weak (1/8 each)** — both still over-explore (avg 5.38 and 5.50 / 6 budget). gemma4's 1/8 is the *one* task it consistently gets right (T2.5).

## Calibration note

**T2.3 absence now properly discriminated.** v3 trivially passed every model (declared "nothing" earned credit); v4 only qwen3.8 + gemma4 passed with the hardened useful-negative; v5 only **qwen3.8 passes** (1/5). That's the desired behaviour — the "impossible path with useful negative" pattern is a real discriminator now.

## Open issues

- **T2.5 / T2.7 — still 0–1 passes for some models.** Multi-hop chain + ID-shape fix helped (T2.7 went 0→3; T2.5 went 0→2), but **T2.5 remains 0/5 for nemotron/muse/qwen3.8**, and **T2.8 (error recovery) is still 0/5 across the board**. The P6 pattern (recover from a syntax error mid-session) is the new frontier.
- **T2.6 regression** — nemotron used to pass this (source fix in v4). Now 0/5. The regex broaden widened the artefact-citation scope in a way that introduced an extra rule nemotron doesn't satisfy. Needs audit, not a fix loop.

## Next steps (v6)

1. **T2.5 / T2.7 redesign** — switch to a single-node `MATCH` form (the multi-hop chain is what blocks nemotron/muse/qwen3.8 on these). If the chain is irreducible, factor T2.7 into 2 sub-tasks.
2. **More pronouns in SYSTEM_PROMPT for citation discipline** — "The answer *it* (the model) writes must reference the IDs *it* (the model) received from queries" — current phrasing worked but is brittle; pronouns force explicit subject links.
3. **Consider `qwen3.5:27b` for one more comparison point** — checks whether qwen3.8's lead is family-specific or general. Pairs well with the qwen3.8:qwen3.5 A/B this fix-set already implies.
