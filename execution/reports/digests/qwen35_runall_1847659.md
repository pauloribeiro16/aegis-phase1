# Digest — qwen3.5:27b run-all (JOB 1847659)

**Judge:** GLM-5.3-Flash via ZCode (2026-09-01)
**Rubric:** v1 | **Commit:** a710efd4 | **Case:** case1-tinytask
**Run dir:** `Deucalion/results/qwen35_runall_1847659/`
**Input read:** Doc 05 §6.1b extracts (walk_run_dir) + run log + artefacts

**TL;DR (PT):** Fase 1B sólida (ratio de qualidade; P1B-01 3.5/5,
P1B-02 3.3/5 — prosa boa mas implicações/gaps vazios). P1C-01 falhou por
FORMATO (2.0/5): 0 activations extraídas → REDUCE-LLM skipado → Docs
07/07b vazios de conteúdo. Não é candidato a pipeline completa; é útil
como baseline de formato para comparar com qwen3.8.

---

## P1B-LLM-01-INTERPRETATION — **3.5 / 5** · confidence: HIGH

**What:** activate/deactivate Tipo-2 interpretations and Tipo-3
derogations per regulation with the deciding fact cited.
**How:** rubric v1 weights; parser gate + judge reading of Doc 05 §6.1b.

| Criterion | Score | Measured | Why |
|---|---|---|---|
| Grounding | 4 | fact refs present (DOC04:FACTS-sector, DOC04:architecture.data_flows) | correct predicate→fact mapping; some CRA predicates lack the quoted fact |
| Precision | 4 | correct verdicts, incl. ART14 dual-flow | no audit field (`confidence`) |
| Actionability | 3 | verdicts + prose consequences | no per-item actions |
| Template | 2 | bullets `- ENTRY (VERDICT):` | contract needs `### ENTRY — VERDICT`; tolerant parser required |
| Specificity | 4 | dense | — |

**Evidence:** "derogations TIPO3-CRA-NON-PLACED and TIPO3-CRA-OPEN-SOURCE
are explicitly NOT_ACTIVATED because TinyTask is a commercial entity
placing proprietary software on the market" (Doc 05 §6.1b, CRA).

## P1B-LLM-02-RATIONALE — **3.3 / 5** · confidence: HIGH

**What:** rationale + implications (IMP) + gaps (GAP), structured.
**How:** parser gate (5-section contract) + rubric v1.

| Criterion | Score | Measured | Why |
|---|---|---|---|
| Grounding | 4 | 2.1k chars/reg, fact-referenced prose | refs sparse (2–3/reg) |
| Precision | 4 | no wrong refs | — |
| Actionability | 2 | **Implications and Gaps empty** | actions buried in loose `## Findings`; downstream minItems would fail |
| Template | 2 | `## Findings` blob | 5-section contract violated |
| Specificity | 4 | dense | — |

**Evidence:** scout report §2.6: "implications/gaps end up empty (the
rationale prose itself is high quality — 2.1k chars of grounded analysis
per regulation)."

## P1C-LLM-01-OVERLAP-CLASSIFICATION — **2.0 / 5 → FAIL** · confidence: HIGH

**What:** 10 domain lanes; per-pair overlap verdicts in contract shape;
sole input to REDUCE.
**How:** parser gate counts extracted activations; L4 gate = REDUCE ran?

| Criterion | Score | Measured | Why |
|---|---|---|---|
| Template | 1 | `## Pair classifications` bullets; **0 activations extracted** | wrong shape entirely |
| Grounding | 3 | predicates evaluated per pair (per scout §2.7) | unverifiable at scale |
| Coverage | 1 | 0/38 sub-domains activated | REDUCE starved |
| Precision | 3 | plausible | unvalidated |
| Specificity | 3 | 27–53k tok/lane | unusable density |

**Evidence:** run log: `MAP complete … statuses={'OK': 10}` then
`REDUCE-LLM failed (continuing): aggregated_activations is empty across
all lanes`.

## P1C-LLM-02 / P1C-LLM-03 — **n/a (cascade)** · confidence: HIGH

**Measured:** never invoked. **Why:** REDUCE input empty — this is
cascade failure of P1C-01, not a model defect. Doc 05 §6.1b records
"_(no LLM response for this spec)_" for both.

## L4 downstream + L5 cost

- Docs 07/07b rendered from empty inputs; Doc 06 healthy (222 clauses);
  Doc 04b maturity flat `1×10` (variance 0 — flagged).
- 4 P1B calls: 318/260/207/263 s (125.7k/125.1k/93.5k/95.7k tok);
  ~395 tok/s; deterministic (identical token counts scout vs run-all).

## Spot-check these (lowest confidence)

1. P1C-01 precision 3 — "substantive pair verdicts" is based on the
   scout's spot read of raws, not systematic validation.
2. L4 maturity variance interpretation (conservative model vs scorer
   over-collapse) — hypothesis only.
