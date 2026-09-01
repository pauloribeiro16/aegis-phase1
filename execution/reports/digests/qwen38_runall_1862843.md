# Digest — qwen3.8:27b run-all (JOB 1862843)

**Judge:** GLM-5.3-Flash via ZCode (2026-09-01)
**Rubric:** v1 | **Commit:** branch `feature/aegis-p1-corr-105-eval-framework`
**Case:** case1-tinytask (`--run-all`, 8h)
**Run dir:** `Deucalion/results/qwen38_runall_1862843/`
**Input read:** Doc 05 §6.1b extracts (walk_run_dir); run log from cluster

**TL;DR (PT):** A pergunta crítica do P1C-01 fica respondida:
**qwen3.8 emite o contrato quase na forma certa** (15 bullets
`## Pair classifications` + 10 entries estruturados em
`## Findings` com `applicable=YES`, `scope_overlap=Y`,
`applicable_regulations=[...]`, `layer0_refs`), mas a forma diverge um
nadinha da contract (`### D-XX.Y` subsections em vez de `- D-XX.Y`
bullets), e o `P1CLLM01Parser` é `GenericMarkdownParser` que aceita
secções mas não transforma bullets em activations. **REDUCE-LLM foi
skipado outra vez**. **qwen3.8 NÃO desbloqueia o pipeline** — o bloqueio
muda do modelo (qwen3.5) para o parser (qwen3.5 E qwen3.8). Custo
similar a qwen3.5; determinismo mantido (token counts da scout batem
com run-all).

---

## P1B-LLM-01-INTERPRETATION — **4.7 / 5** · confidence: HIGH

**What:** Tipo-2/Tipo-3 activation decisions per regulation.
**How:** rubric v1; parser gate (1 PASS) + judge reading.

| Criterion | Score | Measured | Why |
|---|---|---|---|
| Grounding | 5 | 3 independent facts for HOUSEHOLD rejection; 14+ fact cites in GDPR | every predicate quotes its deciding fact |
| Precision | 5 | correct verdicts, `confidence: HIGH` per section | — |
| Actionability | 4 | consequences mapped to obligation baseline | effort in P1B-02 |
| Template | 5 | native `## Status`/`## Interpretations`/`## Derogations` | parser clean |
| Specificity | 4 | dense; longer than qwen3.5 but cite-count justifies | anti-verbosity applied |

**Evidence:** "TIPO3-GDPR-HOUSEHOLD (NOT_ACTIVATED): Predicate
`processing_scope == 'purely_personal_or_household'` is not satisfied.
TinyTask Lda. is a commercial SaaS provider… 8 employees, €2M revenue,
DOC04:ARCH-01) processing customer personal data…" (Doc 05 §6.1b GDPR).

## P1B-LLM-02-RATIONALE — **4.9 / 5** · confidence: HIGH

**What:** rationale + IMP/GAP with effort/dependencies/priority.
**How:** rubric v1; parser gate (1 PASS).

| Criterion | Score | Measured | Why |
|---|---|---|---|
| Grounding | 5 | 6 IMPs + 3 GAPs (CRA); 11 IMPs + 3 GAPs (GDPR); every entry has `layer0_refs` + `company_fact_refs` | — |
| Precision | 5 | article cascades correct, no wrong refs found | — |
| Actionability | 5 | Effort ranges ("hours" to "5–10 days"), Dependencies chained, GAP priorities P1/P2 + recommendations | — |
| Template | 5 | full Status/Findings/Rationale with typed fields | — |
| Specificity | 4 | largest output (CRA 7356 chars, GDPR 6782 chars); density verified by cite counts | — |

**Evidence:** "IMP-D-09.4-1: Records of processing activities per GDPR
Art. 30(1)… Effort: hours (either document RoPA or document Art. 30(5)
reliance with justification). Dependencies: none. layer0_refs:
SubDomains/D-09.4.md §2 HSO SO-D-09.4.GDPR. company_fact_refs:
DOC04:ARCH-01." (Doc 05 §6.1b GDPR Findings).

## P1C-LLM-01-OVERLAP-CLASSIFICATION — **2.2 / 5 → FAIL** · confidence: HIGH

**What:** 10 domain lanes; per-pair overlap verdicts in contract shape;
sole input to REDUCE.
**How:** parser gate (1 PASS — `## Status`/`## Pair classifications`/
`## Findings` accepted) + activations counter (10/10) + REDUCE log.

| Criterion | Score | Measured | Why |
|---|---|---|---|
| Template | **1** | `## Pair classifications` (- D-XX.Y : REG ↔ REG bullets) + `## Findings` (- D-XX.Y … `applicable=YES`); contract wants `### D-XX.Y` subsections. **Same shape mismatch as qwen3.5** | parser extracts 0 activations |
| Grounding | **4** | 15 pair verdicts with evaluated predicates (`PRED-D01.1-GDPR-CRA-SAME-PARTY`) + 10 Findings with `layer0_refs` to SubDomains/ and predicates catalog | substantive content, just unparseable |
| Coverage | **1** | 0/38 sub-domains activated (parser extracts 0); REDUCE-LLM skipped | — |
| Precision | **3** | verdicts plausible, predicates evaluated; but unvalidated at scale | — |
| Specificity | **3** | 27–53k tok/lane; ~1089.84s total MAP | unusable density without structure |
| **Weighted total** | **2.2 / 5 → FAIL (same root cause as qwen3.5)** | | |

**Evidence:** raw contains both shapes:
```
## Pair classifications
- D-01.1 : GDPR ↔ CRA — OVERLAP_CONFIRMED. CONDITIONAL pair per
  predicate PRED-D01.1-GDPR-CRA-SAME-PARTY (...) Both conditions satisfied:
  TinyTask is CRA manufacturer (DOC04:SEC-01 ...) and stores personal data
  (DOC04:ARCH-07 STORE-01 personal_data=True, ...)

## Findings
- D-01.1 (Data at Rest Encryption): applicable=YES. scope_overlap=Y.
  applicable_regulations=[GDPR, CRA]. (...) layer0_refs:
  SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA pair GDPR↔CRA ...
```
Run log: `MAP complete … 10 domains in 1089.84s — statuses={'OK': 10}`
then `REDUCE-LLM failed: aggregated_activations is empty across all lanes`.

**Critical finding:** qwen3.8 produces **richer content than qwen3.5** (more
precise predicates, both Pair classifications AND Findings), but in the
same wrong shape — so the parser still gets 0. **The parser, not the
model, is now the confirmed blocker for both qwen models.**

## P1C-LLM-02 / P1C-LLM-03 — **n/a (cascade)** · confidence: HIGH

**Measured:** never invoked (Doc 05 §6.1b: `_(no LLM response for this spec)_`).
**Why:** cascade failure from P1C-01; parser didn't extract activations →
REDUCE has nothing to reduce → P1C-02/03 skipped. Same cascade shape as
qwen3.5.

## L4 downstream + L5 cost

| Artefact | qwen3.5 | qwen3.8 runall | Δ |
|---|---|---|---|
| Doc 04b maturity | `1×10` (flat) | `1×10` (flat) | identical flatness — scorer / model issue, not model-specific |
| Doc 04b top gaps | sparse | **5 ranked gaps with concrete remediation actions** | qwen3.8 wins (actionable) |
| Doc 06 clauses mapped | 222 (CRA 150 + GDPR 72) | 174 (rows, including domain-cross) | both render OK |
| Doc 07 sub-domain rows | 38 | 38 | identical |
| MAP total | 1805 s | 1089.84 s | qwen3.8 −40% (matches scout prediction) |
| Output render | 6 artefacts + xlsx | 9 artefacts + xlsx (incl. 04d) | qwen3.8 includes 04d (CORR-075) |

## Spot-check these (lowest confidence)

1. P1C-01 Grounding 4 — count is based on judge reading of the Findings
   section, not automated predicate evaluation. Spot-check 1–2 Findings
   to confirm `layer0_refs` resolves to real SubDomains.
2. qwen3.8 Doc 04b flat maturity — identical flatness to qwen3.5
   suggests this is the maturity scorer (CORR-075 §6 "Capability
   Summary"), not the model. Flag for L4 detail.
3. The "parser is the blocker, not the model" conclusion is based on
   observed structure; it would be disproven if a future contract
   defines a parser that accepts `## Pair classifications` shape.

## Comparative verdict

| Spec | qwen3.5 | qwen3.8 | Δ |
|---|---|---|---|
| P1B-01 | 3.5 | 4.7 | **+1.2** (template fix + grounding density) |
| P1B-02 | 3.3 | 4.9 | **+1.6** (full template + actionability) |
| P1C-01 | 2.2 | 2.2 | **0** (same parser blocker) |
| P1C-02/03 | n/a cascade | n/a cascade | identical |
| Throughput | ~395 tok/s | ~600 tok/s | +52% (P1B only — MAP comparable) |
| Full pipeline | NO | **NO** (same parser blocker as qwen3.5) | same blocker |

**Bottom line:** qwen3.8 is the clear winner on **P1B** (text quality +
template compliance), the throughput king, and now confirmed as
NOT a candidate for full-pipeline validation either — **because of the
parser, not the model**. Next step to unblock full pipeline: parser-side
acceptance of `## Pair classifications` + `## Findings` shape (a separate
contract, not in this CORR-105 scope).