# T2 Navigation & Usability Pilot v1 — Summary

**Date:** 2026-09-04
**Branch:** `feature/aegis-p1-corr-115-kg-etl-foundation`
**Cluster sync commit:** `dcc3f1b` (post-fix 2)
**Pilot scope:** 4 models × 3 tasks = 12 runs (then repeated for the bugfix-validation fleet — total 8 scorecards in this directory)

## Setup

- Sbatch: `examples/deucalion/kg-eval-t2-pilot.sbatch`
- Engine: `scripts/kg_eval/engine.py` (in-memory graph; Cypher is a regex/keyword matcher, not a full parser)
- Catalogue: `scripts/kg_eval/tasks_t2.yaml` (3 tasks covering Pattern 2 + Pattern 4 + Pattern 0+absence)
- Scorer: `scripts/kg_eval/score_t2.py` (5 dimensions per protocol v1.1 §8)
- Models: 30-31b tier on Ollama 0.32.13; 1× A100-80, partition `normal-a100-80`, port dynamic per JOB

## Bugfix log (necessary before signals were real)

| Job ID batch | Failure | Cause | Fix commit |
|---|---|---|---|
| 1875164-1875193 | `ImportError: build_llm_invoker` | sbatch imported a symbol that did not exist | `5264d4a` (use `get_invoker` from `aegis_phase1.prompts_v2.factory`) |
| 1875224-1875227 | `total_queries=0` across all 12 runs | sbatch read `res.get('content')` but `UnifiedInvoker.invoke_raw` returns `{raw, status, usage}` | `dcc3f1b` (read `raw` first, fall back to `content`/`text`) |

The four scorecards from each pre-fix batch are kept in this directory as audit trail (prefix `sc_18752{24,25,26,27}` are bugfix-validation, `sc_18752{37,38,39,40}` are the real pilot signal).

## Pilot signal (4 models × 3 tasks, jobs 1875237-1875240)

| Model | T2.1 grounding (case1, opt=2) | T2.2 tension (case3, opt=1) | T2.3 absence (case1, opt=1) | Total |
|---|---|---|---|---|
| **qwen3.8:27b** | ✓ (2 queries) | ✓ (4 queries) | ✓ (2 queries) | **3/3** |
| nemotron-3.5-lightning:30b | ✗ (6 queries; budget exceeded) | ✓ (1 query) | ✓ (1 query) | 2/3 |
| gemma4:31b | ✗ (6 queries; budget exceeded) | ✓ (2 queries) | ✗ (5 queries; budget exceeded, absence declared) | 1/3 |
| muse-glimmer:30b | ✗ (6 queries; budget exceeded) | ✓ (4 queries) | ✗ (6 queries; budget exceeded, no absence declared) | 1/3 |

### Attribute breakdown

- **Schema/Syntax validity:** 12/12 runs clean. Cypher-syntax is not the failure mode for any model.
- **Query efficiency (optimal cap = 2×optimal):** 3 of 4 models burn the full budget on T2.1 and T2.3 — over-exploration. Only qwen3.8:27b honours the optimal budget.
- **Error recovery:** not yet measured by scorer (see CORR-115 T2-EXP-2 follow-up); zero errors observed in this pilot so the dimension was uninformative.
- **Grounding discipline:** binary "answer non-empty + >10 chars" — too lax; qwen3.8 passes it, but empty-answer cases fail, which is downstream of over-exploration, not of fabrication.
- **Know when to stop:** only qwen3.8 + nemotron declare absence in T2.3; muse and gemma4 either over-explore or confabulate.

### Headline

**Winner of pilot v1: qwen3.8:27b** — only model to clear all three dimensions. **Runner-up: nemotron-3.5-lightning:30b** — clean on tension and absence, fails only on the multi-hop grounding (a planning gap, not a Cypher gap). **Out of contention for T2 v2: gemma4:31b, muse-glimmer:30b** — over-exploration on at least 2/3 tasks, and one of them does not declare absence in T2.3 (a hard fail for the usability-of-knowledge-work claim).

### Known limitations of the pilot

1. **3 tasks is too few to separate models** — qwen3.8 is 3/3 and nemotron is 2/3, but only the T2.1 distinguishes them; not enough power to rank.
2. **Case2 (secureborder) is absent from T2** — case1 + case3 only.
3. **Patterns 1 (scope), 3 (proportionality), 5 (SO hierarchy), 6 (DataSubject) are uncovered** by the catalogue. The engine supports only 8 of 39 ontology labels.
4. **Scorer does not implement Error Recovery (dim 4 of protocol §8)** — collapsed into Schema/Syntax.
5. **Query efficiency floor `max(2*optimal, 4)` is too generous** for low-optimal tasks (T2.2 with optimal=1 should cap at 2; floor of 4 masks nemotron's 4-query inefficiency).

## Next-cycle plan

See `docs/NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md` (spec v3, 1127 lines) for what is missing; this summary focuses on actionable next steps.

| Action | Owner | Target |
|---|---|---|
| Expand tasks_t2.yaml to 8 tasks covering 6 of 8 patterns | this PR | T2-EXP-1 |
| Implement scorer dim 4 (Error Recovery) + tighten efficiency floor | this PR | T2-EXP-2 |
| Engine: instantiate ProportionalityEntry / SecurityObjective / DataSubject | this PR | unlock P3/P5/P6 |
| Add fixtures + anti-mock guard per task | this PR | T2-EXP-3 |
| Re-run mini-fleet (4 models × 8 tasks) on cluster | next deploy | T2-EXP-4 |
| Gate decision: qwen3.8:27b promoted to T2 standard; nemotron as runner-up | after fleet re-run | decision |
| Move to Neo4j real (Fase B ETL, KG-01..KG-06) | next contract | deprecate in-memory engine |
