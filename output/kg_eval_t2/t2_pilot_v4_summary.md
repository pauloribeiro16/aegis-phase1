# T2 Pilot v4 — 6 models × 8 tasks = 48 runs (post-fix)

**Date:** 2026-09-05
**Branch:** `feature/aegis-p1-corr-115-kg-etl-foundation`
**Catalogue:** `scripts/kg_eval/tasks_t2.yaml` (8 tasks, 6 patterns: P0+, P1, P2, P3, P4, P5, P6)
**Scorer:** `scripts/kg_eval/score_t2.py` (5 dimensions per protocol v1.1 §8)
**Scorecards:** `output/kg_eval_t2/sc_18809{29,30,31,32,33,34}.json`
**Fixes applied since v3:** SYSTEM_PROMPT expansion (artefact-aware framing), T2.3 useful-negative hardening (cite nearest non-target subdomain on impossible path), T2.6 source fix (DataSubject hierarchy grounded on the right upstream node).

## v3 → v4 headline

**1/48 → 4/48 pass (4× improvement).** Three coordinated fixes moved the needle:

- **SYSTEM_PROMPT expansion** — explicit artefact-citation framing helps models recognise when an answer must reference closed-set IDs.
- **T2.3 useful-negative hardening** — impossible tasks now require a useful negative (cite the nearest non-target subdomain) instead of bare absence. The easier "stop at zero queries" trick no longer earns credit.
- **T2.6 source fix** — DataSubject hierarchy was being queried from the wrong upstream node; correct source unblocks the only model (nemotron) that already reached the right shape in v3.

## Fleet

| Model | Pass | Avg queries | Distinguishing pattern |
|---|:---:|:---:|---|
| qwen3.8:27b | **2/8** | 3.75 | Best baseline: passes T2.3 trio + newly gains T2.4 NIS2 scope from prompt fix |
| gemma4:31b | **1/8** | 4.75 | Gains T2.3 trio (passes harder impossibility check) |
| nemotron-3.5-lightning:30b | **1/8** | 2.62 | Picks up T2.6 DataSubject — new pattern it never saw in v3 |
| muse-glimmer:30b | 0/8 | 5.75 | Over-explores (saturates 6/6 budget); no discrimination |
| glm-4.7-flash:latest | 0/8 | 2.12 | Early terminator (declares answer after 1-3 queries without verifying) |
| ornith-1.5:35b | 0/8 | **0.00** | Silent failure (no queries attempted on any task; investigate SLURM err log if curious) |
| **Total** | **4/48 (8.3%)** | — | — |

## Per-task pass-rate

| Task | v3 pass | v4 pass | Delta | Note |
|---|:---:|:---:|:---:|---|
| T2.1 case1-SYS01-grounding | 0/6 | 0/6 | — | P2 multi-hop grounding still unsolved |
| T2.2 case3-D044-tension | 0/6 | 0/6 | — | P4 tension still unsolved |
| T2.3 case1-impossible-trio | 1/6 | **2/6** | +1 | gemma4 joins qwen3.8 — useful-negative fix worked |
| T2.4 case2-NIS2-D010-scope | 0/6 | **1/6** | +1 | qwen3.8 gains this — prompt-driven |
| T2.5 case3-D044-attributes | 0/6 | 0/6 | — | P3 proportionality still unsolved |
| T2.6 case3-DS-GDPR-Art9 | 0/6 | **1/6** | +1 | nemotron gains this — source fix worked |
| T2.7 case1-D091-SOs | 0/6 | 0/6 | — | P2/P5 still unsolved |
| T2.8 case2-error-recovery | 0/6 | 0/6 | — | P6 still unsolved |

## Pass grid

| Task | gemma4 | glm-4.7 | muse-glimmer | nemotron | ornith | qwen3.8 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| T2.1 | - | - | - | - | - | - |
| T2.2 | - | - | - | - | - | - |
| T2.3 | **P** | - | - | - | - | **P** |
| T2.4 | - | - | - | - | - | **P** |
| T2.5 | - | - | - | - | - | - |
| T2.6 | - | - | - | **P** | - | - |
| T2.7 | - | - | - | - | - | - |
| T2.8 | - | - | - | - | - | - |

## Critical observations

- **qwen3.8:27b (2/8)** retains its lead and gains T2.4 NIS2 scope from the prompt fix. Still the only model with multi-task coverage.
- **nemotron (1/8)** — was 0/8 in v3, now passes T2.6 DataSubject. The pattern it always produced is finally matched by a grader that recognises it.
- **gemma4 (1/8)** — gains T2.3 trio. Useful-negative hardening was the unlock: it could already find nothing; now it has to say *what* is nearest.
- **muse-glimmer (0/8)** — over-explores (5.75 avg q, saturates 6/6 budget on most tasks). No discrimination between signal and noise.
- **glm-4.7-flash (0/8)** — early terminator. Declares an answer after 1-3 queries on 7/8 tasks without verifying. v5 should consider a verification step.
- **ornith-1.5:35b (0/8, 0 avg queries)** — silent failure across all 8 tasks. No queries attempted; the model never reached the engine. Caveat: this is a data-quality issue worth checking the SLURM err log before drawing any model-capability conclusion.

## Cross-cutting: artefact citation gap

CSF and clauses artefact fields are **empty across all 48 runs** (articles occasionally cited). The hypothesis is that the prompt teaches the model the *labels* and *edges* of the KG but does not teach it to *cite* those IDs in its final-answer prose. Models reach the right nodes via queries but then describe the answer in natural language.

**v5 fix candidate:** add an explicit instruction to SYSTEM_PROMPT —

> "Your final answer MUST cite at least one CSF ID (e.g., PR.DS-01) or clause ID (e.g., GDPR-CL06) if one was returned by a query. If no closed-set artefact was returned, say so explicitly."

## Next steps

1. Investigate ornith-1.5 silent failure — confirm whether it's an environment issue (SLURM/Ollama) or a model issue before drawing any conclusion.
2. Add explicit artefact-citation instruction to SYSTEM_PROMPT (v5) — should turn the 4/48 pass rate into a higher score that also reflects citation quality.
3. Pilot a 7th model (`qwen3.5:27b`) for completeness — checks whether qwen3.8's lead is family-specific or general.
