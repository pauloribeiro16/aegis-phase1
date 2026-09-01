# Digest — ornith:9b scout (JOB 1867097)

**Judge:** GLM-5.3-Flash via ZCode (2026-09-01)
**Rubric:** v1 | **Branch:** `feature/aegis-p1-corr-106-transformers-provider`
**Case:** case1-tinytask (`--run-phase-1b`, 4 calls)
**Run dir:** `Deucalion/results/ornith9b_scout_1867097/`
**Input read:** Doc 05 §6.1b extracts (walk_run_dir) + checker report

**TL;DR (PT):** O mais rápido de todos os testados (~50-80s/call, 4.2 min
de LLM no total — 4× mais rápido que qwen3.8). 9B e produz P1B de
qualidade próxima do qwen3.8: template CORR-074 nativo com
`applicable`/`confidence`, veredictos correctos com predicados citados,
e — ao contrário do qwen3.5 — IMPs e GAPs estruturados com esforço,
dependências e refs. Fact refs com placeholders ("DOC04:SEC-NN") e uma
citação duvidosa (Art. 36 para documentação técnica) são os pontos a
verificar. P1B-01 4.4/5, P1B-02 4.1/5.

---

## P1B-LLM-01-INTERPRETATION — **4.4 / 5** · confidence: HIGH

**What:** Tipo-2/Tipo-3 activation decisions per regulation.
**How:** rubric v1; parser gate 1 PASS; activations 2/2 (applicable YES).

| Criterion | Score | Measured | Why |
|---|---|---|---|
| Grounding (.30) | 5 | Every predicate quotes its deciding fact: "requires both `placing_on_eu_market == False` and `making_available_in_eu == False`, but the company's CRA applicability confirms it places products"; sector check quotes the 4-sector list | — |
| Precision (.25) | 4.5 | Correct verdicts on all 4 CRA entries + 2 GDPR; sophisticated distinction: RTS-DEADLINES (NO) "does not diminish the underlying Art. 33(1) obligation" | "Recital 18" uncited against catalogue |
| Actionability (.20) | 3 | Verdicts + consequences in prose | No per-item actions (belong to P1B-02) |
| Template (.15) | 5 | Native `## Status`/`## Interpretations`/`## Derogations` + `applicable`/`confidence` | Parser clean |
| Specificity (.10) | 4 | Dense, concise | — |
| **Weighted** | **4.4** | | |

**Evidence:** "TIPO3-CRA-NON-PLACED (NOT_ACTIVATED): … CRA Art. 2
exclusion does not apply because the product is placed and made available
in the EU" and GDPR rationale's explicit controller/processor dual-role
split (admin dataset = controller; routed customer data = processor).

## P1B-LLM-02-RATIONALE — **4.1 / 5** · confidence: MEDIUM

**What:** rationale + IMP/GAP records with effort/dependencies/refs.
**How:** rubric v1; parser gate 1 PASS; activations 2/2.

| Criterion | Score | Measured | Why |
|---|---|---|---|
| Grounding (.30) | **4** | IMPs/GAPs carry `layer0_refs` (SubDomains paths) + `company_fact_refs` (DOC04:ARCH-07, ARCH-03…) | **Placeholder-style refs present**: "DOC04:SEC-NN manufacturer role", "DOC04:SEC-NN data categories" — `SEC-NN` is not a real key; spot-check needed |
| Precision (.25) | **4** | Art. 14(1)/(2), Art. 15, Art. 17(4), Art. 30 CE marking, Annex VII/VIII correct | **"CRA Art. 36 requires technical documentation"** — qwen3.8 attributes tech-doc to Art. 13 + Annex VII; one of the two is mis-cited. Flagged, not verified |
| Actionability (.20) | 4.5 | 6 findings: 2 IMPs (`effort_estimate=hours-to-days`) + 4 GAPs (`effort_estimate=months` for conformity, `days-to-weeks` for CE marking) with **dependency chains** (`dependencies=[GAP-CRA-TECHNICAL-DOC]`) and coverage levels | Priorities (P1/P2) absent — gold has them |
| Template (.15) | 4 | Typed `**implication**:`/`**gap**:` records inside `## Findings` with `id=`, `sub_domain_id=`, `coverage_level=` fields — machine-parseable, but the contract shape is separate Implications/Gaps sections (qwen3.8's shape) | Parser still passes |
| Specificity (.10) | 4 | Long but dense; TI-01 temporal conflict handled (24h vs 72h max-SLA workflow) | — |
| **Weighted** | **4.1** | | |

**Evidence:** "gap_id=GAP-CRA-CONFORMITY-ASSESSMENT, sub_domain_id=D-09.1,
coverage_level=NOT_ADDRESSED … effort_estimate=months" — real, structured,
grounded gap records (the thing qwen3.5 completely failed to produce).

## P1C-LLM-01/02/03 — not run (scout scope)

Same caveat as qwen3.8 scout: P1C untested; the run-all question
(template compliance at 10× P1C-01 lanes) remains open for this model.

## L5 cost

| Call | ornith:9b | qwen3.8:27b | Δ |
|---|---|---|---|
| P1B-01 CRA | 50 s / 121k tok | 201 s / 122.6k tok | **4.0× faster** |
| P1B-02 CRA | 69 s / 123k tok | 218 s / 126.3k tok | **3.2× faster** |
| P1B-01 GDPR | 40 s / 90.5k tok | 152 s / 92.8k tok | **3.8× faster** |
| P1B-02 GDPR | 81 s / 96k tok | 188 s / 96k tok | **2.3× faster** |

Total LLM time: **4.2 min** (vs 12.6 min qwen3.8, 17.5 min qwen3.5).
9B model, 5.6 GB blob.

## Spot-check these (lowest confidence)

1. **"DOC04:SEC-NN"** placeholder fact refs in IMP records — likely not
   resolvable keys; if confirmed, Grounding drops to 3 and total to ~3.8.
2. **"Art. 36 requires technical documentation"** — conflicts with
   qwen3.8's Art. 13 + Annex VII attribution; verify against preproc.
3. **Template 4 vs 3 on P1B-02** — typed-Findings-blob vs separate
   sections is a judgement call; if you read the contract strictly, the
   total drops to ~3.95.

## Comparative position (scouts only, P1B)

| Model | P1B-01 | P1B-02 | Speed (P1B total) |
|---|---|---|---|
| qwen3.8:27b | 4.7 | 4.9 | 12.6 min |
| **ornith:9b** | **4.4** | **4.1** | **4.2 min** |
| qwen3.5:27b | 3.5 | 3.3 | 17.5 min |

Best quality-per-second by a wide margin, at 1/3 the blob size. If its
P1C-01 template compliance (untested) matches its P1B discipline, it's a
serious full-pipeline candidate.
