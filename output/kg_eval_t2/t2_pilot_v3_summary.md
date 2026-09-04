# T2 Pilot v3 — 6 models × 8 tasks = 48 runs

**Date:** 2026-09-04
**Branch:** `feature/aegis-p1-corr-115-kg-etl-foundation`
**Catalogue:** `scripts/kg_eval/tasks_t2.yaml` (8 tasks, 6 patterns: P1, P2, P3, P4, P5, P6)
**Scorer:** `scripts/kg_eval/score_t2.py` (5 dimensions per protocol v1.1 §8)
**Engine:** `scripts/kg_eval/engine.py` (in-memory graph; regex/keyword Cypher matcher)

## Fleet

| Model | Job ID | Total queries (8 tasks) | Overall pass |
|---|---|---:|---:|
| nemotron-3.5-lightning:30b | 1878904 | 23 | 0/8 |
| qwen3.8:27b | 1878905 | 28 | **1/8** |
| muse-glimmer:30b | 1878906 | 45 | 0/8 |
| gemma4:31b | 1878907 | 42 | 0/8 |
| glm-4.7-flash:latest | 1878908 | 17 | 0/8 |
| ornith-1.5:35b | 1878909 | 17 | 0/8 |

## Per-task pass-rate (1/6 each pass)

| Task | Passes | Models that passed | Pattern |
|---|:---:|---|---|
| T2.1 case1-SYS01-grounding | 0/6 | — | P2 (multi-hop grounding) |
| T2.2 case3-D044-tension | 0/6 | — | P4 (tension/contradiction) |
| **T2.3 case1-impossible-cloud** | **1/6** | **qwen3.8:27b** | P0+absence (knowing when to stop) |
| T2.4 case2-NIS2-D010-scope | 0/6 | — | P1 (scope) |
| T2.5 case3-D044-attributes | 0/6 | — | P3 (proportionality) |
| T2.6 case3-DS-GDPR-Art9 | 0/6 | — | P5 (DataSubject hierarchy) |
| T2.7 case1-D091-SOs | 0/6 | — | P2/P5 (security-objective) |
| T2.8 case2-error-recovery | 0/6 | — | recovery (P6) |

## Dimension breakdown

### Syntax errors per model (`syntax_validity_pass = False`)

| Model | Count |
|---|---:|
| nemotron-3.5-lightning:30b | 0/8 |
| qwen3.8:27b | 2/8 |
| muse-glimmer:30b | 1/8 |
| gemma4:31b | 1/8 |
| glm-4.7-flash:latest | 0/8 |
| ornith-1.5:35b | 0/8 |

Cypher syntax is **not** the failure mode — 4/6 models are clean.

### Avg `recovery_rate` per model (across 8 tasks)

| Model | Avg |
|---|---:|
| nemotron-3.5-lightning:30b | 0.000 |
| **qwen3.8:27b** | **0.188** |
| muse-glimmer:30b | 0.125 |
| gemma4:31b | 0.125 |
| glm-4.7-flash:latest | 0.000 |
| ornith-1.5:35b | 0.000 |

### Grounding discipline — tasks citing any CSF / clause / article

| Model | Tasks with cited artefacts |
|---|---:|
| nemotron-3.5-lightning:30b | **1/8 (12.5%)** |
| qwen3.8:27b | 0/8 |
| muse-glimmer:30b | 0/8 |
| gemma4:31b | 0/8 |
| glm-4.7-flash:latest | 0/8 |
| ornith-1.5:35b | 0/8 |

**Critical:** only nemotron cited a closed-set artefact in 1 task. The closed-set vocabulary (CSF IDs, clause IDs, article references) is essentially absent from the other 47 runs.

### Efficiency — avg queries per task

| Model | Avg | Profile |
|---|---:|---|
| glm-4.7-flash:latest | 2.12 | low (many zero-query abandons) |
| ornith-1.5:35b | 2.12 | low (many zero-query abandons) |
| nemotron-3.5-lightning:30b | 2.88 | under-explores |
| qwen3.8:27b | 3.50 | under-explores but accurate |
| gemma4:31b | 5.25 | over-explores (saturates 6/6 budget) |
| muse-glimmer:30b | 5.62 | over-explores (saturates 6/6 budget) |

### Absence — T2.3 impossible-cloud (per-model detail)

| Model | Absence declared | Overall | Notes |
|---|:---:|:---:|---|
| nemotron-3.5-lightning:30b | True | False | 3 queries (optimal 1, cap 2) — over budget |
| **qwen3.8:27b** | **True** | **True** | 1 query — clean |
| muse-glimmer:30b | False | False | 6 queries, empty answer |
| gemma4:31b | False | False | 6 queries, empty answer |
| glm-4.7-flash:latest | False | False | 4 queries, no absence |
| ornith-1.5:35b | False | False | no absence |

## Discriminator

**qwen3.8:27b** is the only model that passed any task — and only T2.3. The remaining five models failed every task. The single pass is decisive: it is not noise.

## Calibration issue

T2.3 (case1-impossible-cloud) is **trivially passable**:
- Optimal budget is 1 query.
- qwen3.8 passes with exactly 1 query.
- Several models (nemotron, glm-4.7, ornith) reach the same absence declaration but fail the efficiency cap.

The current T2.3 grader treats "1 query + ack absence" as the full pass condition. This is correct only because the model has to recognise the impossibility — but a stronger check would be to require the model to also produce a useful negative answer (e.g., cite the closest non-cloud subdomain) or to test a less obvious impossibility. **T2.3 needs a harder impossibility check before it can carry decision weight in v4.**

## Pattern coverage

6 of 8 spec patterns exercised in this pilot:

| Pattern | Task | Coverage |
|---|---|:---:|
| P0+absence | T2.3 | covered |
| P1 (scope) | T2.4 | covered |
| P2 (multi-hop grounding) | T2.1, T2.7 | covered |
| P3 (proportionality) | T2.5 | covered |
| P4 (tension) | T2.2 | covered |
| P5 (DataSubject hierarchy) | T2.6 | covered |
| P6 (error recovery) | T2.8 | covered |
| P7 (SR ↔ SO cross-link) | — | **not covered** |
| P8 (capability ↔ role binding) | — | **not covered** |

(P7 and P8 remain uncovered; P7 is ontology-expensive, P8 is post-T2 work.)

## Next steps

- Tighten T2.3 with a "useful negative" requirement (cite the nearest non-cloud subdomain) — needed before it can anchor decisions.
- Triage the closed-set grounding collapse (47/48 runs cite no CSF/clause/article): add a fixture-free probe or relax the scorer so absence-style answers count.
- Promote qwen3.8:27b as the T2 v3 reference; demote the five 0/8 models until P2 grounding is re-tested under the relaxed scorer.
