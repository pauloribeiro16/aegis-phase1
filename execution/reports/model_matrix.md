# Model matrix — AEGIS-KG Phase 1

**Rubric version:** v1 (locked 2026-09-01 — see `EVAL_PROTOCOL.md` §2b for
weights and judge protocol).
**Judge:** GLM-5.3-Flash via ZCode. **Gold:** M3 (= 5 by construction).
**How to read:** per spec — PT TL;DR first, then one table row per
criterion per model with score, measured numbers, and justification.
Every claim carries an evidence pointer. Score transitions live in the
Changelog at the bottom; full history in git.

**Runs currently scored:**
- qwen3.5:27b → JOB 1847659 (full `--run-all`, 2026-08-24)
- qwen3.8:27b → JOB 1862819 (scout, Phase 1B only, 2026-09-01)
- JOB 1862843 (qwen3.8 run-all) → in flight; P1C cells pending

---

## P1B-LLM-01-INTERPRETATION — per-regulation interpretation & derogation activation

**TL;DR (PT):** Avalia se o modelo lê os catálogos Tipo-2/Tipo-3 e decide
correctamente, por regulação, quais as interpretações/derogações activam
para a TinyTask — citando o facto da empresa que decide o veredicto.
qwen3.8 supera qwen3.5: segue o template CORR-074 nativamente e cita o
predicado em todas as decisões; qwen3.5 chega às respostas certas mas em
formato bullets que exige parser tolerante.

**What is evaluated:** For each applicable regulation (CRA, GDPR), the
model must evaluate every Tipo-2 interpretation and Tipo-3 derogation
predicate against company facts and emit a verdict with the deciding
fact cited.

**How it is evaluated:** L1 = `P1BLLM01Parser.parse()` on the Doc 05
§6.1b section (deterministic). L3 = 5 criteria (weights: grounding .30,
precision .25, actionability .20, template .15, specificity .10).

| Criterion | qwen3.5 (JOB 1847659) | qwen3.8 (JOB 1862819) | M3 gold |
|---|---|---|---|
| Grounding (.30) | **4** — verdicts tied to facts: "sector ('Technology/Software') does not match this list (DOC04:FACTS-sector)" (Doc 05 §6.1b GDPR). Not 5: some CRA predicates asserted without quoting the fact value. | **5** — every predicate decision quotes the deciding fact: HOUSEHOLD "NOT_ACTIVATED" justified with 3 independent facts (8 employees, €2M revenue, signed DPAs with AWS/Firebase/Stripe/Datadog) (Doc 05 §6.1b GDPR Derogations). | 5 |
| Precision (.25) | **4** — correct verdicts incl. dual-track reasoning TIPO2-CRA-ART14-DUAL-FLOW (24h CRA vs 72h GDPR); no wrong article refs found. Not 5: no confidence field to audit. | **5** — correct verdicts + explicit `applicable: YES, confidence: HIGH` per section (auditable). | 5 |
| Actionability (.20) | **3** — verdicts only; consequences described in prose but no per-item next actions. | **4** — consequences tied to obligations (e.g. "GDPR obligations proceed on the standard controller baseline (Art. 5, 24, 25, 28, 30, 32, 33, 35)") but no effort estimates at this spec (they belong to P1B-02). | 5 |
| Template (.15) | **2** — emits `- ENTRY (VERDICT): text` bullets instead of `### ENTRY — VERDICT` sections; parser needed tolerant mode (scout report §2.6). | **5** — native `## Status` / `## Interpretations` / `## Derogations` sections with `applicable:` + `confidence:` fields; P1BLLM01Parser passes clean. | 5 |
| Specificity (.10) | **4** — concise, dense. | **4** — longer but every sentence carries a fact ref; density holds. | 5 |
| **Weighted total** | **3.5 / 5** | **4.7 / 5** | 5 |

**Evidence anchors:** qwen3.5 — Doc 05 §6.1b CRA + GDPR interpretations;
qwen3.8 — `Deucalion/results/qwen38_scout_1862819/05_Regulatory_Applicability.md`
(CRA rationale 7 356 chars; GDPR 6 782 chars).

---

## P1B-LLM-02-RATIONALE — per-regulation rationale, implications, gaps

**TL;DR (PT):** Avalia o rationale por regulação + implicações (IMP) +
gaps (GAP) accionáveis. A diferença é brutal: qwen3.5 escreve boa prosa
(2.1k chars) mas deixa implications/gaps VAZIOS (tudo em bullets soltos
em `## Findings`), que é exactamente o que a pipeline consome; qwen3.8
entrega 6 IMPs + 3 GAPs (CRA) e 11 IMPs + 3 GAPs (GDPR) com esforço,
dependências, prioridades e refs — accionável por um DPO/CISO.

**What is evaluated:** Per regulation: rationale grounded in company
facts; implications (IMP-*) with effort; gaps (GAP-*) with coverage
level and priority.

**How:** L1 = parser expects 5 sections (Status/Rationale/Implications/
Gaps/Notes); empty required lists ⇒ WARN. L3 = same 5 weights as P1B-01.

| Criterion | qwen3.5 (JOB 1847659) | qwen3.8 (JOB 1862819) | M3 gold |
|---|---|---|---|
| Grounding (.30) | **4** — applicability arguments correct and fact-referenced (2.1k chars/reg); prose itself never contradicts DOC04. Not 5: fact refs sparser (2–3 per reg). | **5** — every IMP cites `company_fact_refs` + `layer0_refs` (14 fact cites in GDPR lane alone, e.g. "IMP-D-06.1-1 … DOC04:CS-01…CS-04, DOC04:NA-03"). | 5 |
| Precision (.25) | **4** — no wrong refs found; correct controller/manufacturer reasoning. | **5** — article cascade correct: "Art. 14(1) requires 24h … Art. 14(2) requires user notification", "Art. 13(8) sentence 3 (5-year minimum support) + Art. 13(9) (10-year update availability)". | 5 |
| Actionability (.20) | **2** — Implications and Gaps sections **empty**; actions folded into loose `## Findings` bullets without effort/priority fields. Downstream `minItems` would fail — masked in Doc 05 by the §6.1b fallback. | **5** — every IMP carries Effort ("2–3 days to draft a CRA-specific IR runbook"), Dependencies ("IMP-D-02.1-1"), and every GAP a priority ("P1") + recommendation ("Generate initial SBOM from GitHub Actions dependency manifests"). | 5 |
| Template (.15) | **2** — 5-section contract violated: `## Findings` blob instead of structured Implications/Gaps lists. | **5** — full Status/Findings/Rationale structure with typed fields; parser passes clean. | 5 |
| Specificity (.10) | **4** — dense prose. | **4** — largest output of the two, but density verified (not padding); anti-verbosity rule applied. | 5 |
| **Weighted total** | **3.3 / 5** | **4.9 / 5** | 5 |

**Evidence anchors:** qwen3.5 — Doc 05 §6.1b (CRA + GDPR `## Rationale`
blocks); scout report §2.6 documents the empty implications/gaps;
qwen3.8 — IMP-D-04.3-1, IMP-D-02.1-1, GAP-D-02.1, GAP-D-09.4 in
`qwen38_scout_1862819/05_Regulatory_Applicability.md`.

---

## P1C-LLM-01-OVERLAP-CLASSIFICATION — per-domain overlap activation (the pipeline's core step)

**TL;DR (PT):** É a etapa que alimenta o REDUCE: 10 domínios ×
classificação de overlaps. qwen3.5 FALHOU por formato: as 10 lanes
correram OK (conteúdo real, 27–53k tokens cada) mas emitiram
`## Pair classifications` em bullets — o parser extraiu 0 activations e
o REDUCE-LLM foi skipado. O fracasso é de formato, não de inteligência.
qwen3.8: PENDING (run-all JOB 1862843) — a célula mais importante da
matriz.

**What is evaluated:** For each of the 10 domains, classify regulation
pairs and emit sub-domain activations in the contract shape. This output
is the ONLY input to REDUCE.

**How:** L1 = `P1CLLM01Parser` expects `## Sub-domain Activations` +
`### D-XX.Y`; the gate counts extracted activations. L4 = REDUCE runs
only if `aggregated_activations` non-empty. Weights: template .30,
grounding .25, coverage .20, precision .15, specificity .10.

| Criterion | qwen3.5 (JOB 1847659) | qwen3.8 | M3 gold |
|---|---|---|---|
| Template (.30) | **1** — emitted `## Pair classifications` with `- D-XX.Y : REG ↔ REG (VERDICT): …` bullets; completely different shape from the contract; parser extracted 0 activations. | PENDING | 5 |
| Grounding (.25) | **4** — pair verdicts came with evaluated predicates (substantive content per scout report §2.7) but unverifiable at scale because nothing was extracted. | PENDING | 5 |
| Coverage (.20) | **1** — 0 of 38 sub-domains with an activation; REDUCE had nothing. | PENDING | 5 |
| Precision (.15) | **3** — verdicts plausible but unvalidated (nothing reached validation). | PENDING | 5 |
| Specificity (.10) | **3** — 27–53k tok/lane spent; unusable density without structure. | PENDING | 5 |
| **Weighted total** | **2.0 / 5 → FAIL (blocks REDUCE)** | **PENDING** | 5 |

**F2 update (2026-09-01, post-counter fix):** the markdown-shape
counter now reveals that qwen3.5 **did** emit `- applicable: YES`
in 10 of 10 lanes (`Activations YES = 10, total = 10`). The field is
there; the parser is what cannot extract it because the surrounding
shape is `## Pair classifications`. Coverage 1 stays — the parser still
gets 0 — but Grounding rises from 3 to **4** (the model emitted the
right predicate result, just in the wrong section). Total 2.0 → **2.2 / 5**.

**Evidence anchors:** scout report §2.7 (root cause + raw shape);
run log JOB 1847659 line `MAP complete … statuses={'OK': 10}` followed by
`REDUCE-LLM failed (continuing): aggregated_activations is empty across
all lanes`.

---

## P1C-LLM-02-COMPOUND-EVENT and P1C-LLM-03-STRATEGIC-SYNTHESIS (REDUCE stage)

**TL;DR (PT):** Nunca chegaram a correr no qwen3.5 — falha em cascata do
P1C-01 (REDUCE sem input → "P1C-LLM-03/02 have nothing to reduce").
Não é defeito do modelo; é a propagação do fracasso de formato acima.
qwen3.8: PENDING.

| Model | qwen3.5 (JOB 1847659) | qwen3.8 | M3 gold |
|---|---|---|---|
| Result | **Not invoked** — log: "aggregated_activations is empty across all lanes; P1C-LLM-03/02 have nothing to reduce". Score n/a per criterion (unmeasurable); L4 = FAIL by cascade. | PENDING | 5 |
| Important distinction | This is **cascade failure, not model failure**. The model never got the chance to succeed or fail on its own merits. | PENDING | — |

---

## L4 — Downstream artefacts (deterministic)

**TL;DR (PT):** qwen3.5: REDUCE skipado → Docs 07/07b renderizados a
partir de inputs vazios; Doc 04b com maturidade plana 1/1/…/1 (variância
zero = sinal de alarme). qwen3.8 scout: só Fase 1B, não aplicável.

| Check | qwen3.5 | qwen3.8 scout |
|---|---|---|
| REDUCE input | 0 activations → REDUCE-LLM skipped | n/a (Phase 1B only) |
| Doc 06 clause mapping | 222 clauses (CRA 150 + GDPR 72), 41 unmapped — deterministic, healthy | n/a |
| Doc 04b maturity variance | **0** — `1/1/1/1/1/1/1/1/1/1` across D-01..D-10; scorer does not differentiate (model conservative or scorer over-collapse — flagged, needs re-measure on qwen3.8) | n/a |
| Output render | 6 artefacts + xlsx in 291.5s | Doc 05 only (42 KB) |

---

## L5 — Cost (measured, both runs A100-80)

| Metric | qwen3.5 | qwen3.8 | Δ |
|---|---|---|---|
| P1B-01 CRA | 318 s / 125.7k tok | 201 s / 122.6k tok | −37% time |
| P1B-02 CRA | 260 s / 125.1k tok | 218 s / 126.3k tok | −16% |
| P1B-01 GDPR | 207 s / 93.5k tok | 152 s / 92.8k tok | −27% |
| P1B-02 GDPR | 263 s / 95.7k tok | 188 s / 96.0k tok | −29% |
| Throughput | ~395 tok/s | ~600 tok/s | +52% |
| Determinism | scout vs run-all token counts identical (temp=0) | identical across its own 2 runs (122 599 / 126 261 / 92 775 tok) | both deterministic |

---

## Cross-model summary

| | M3 gold | qwen3.5 (runall) | qwen3.8 (scout; run-all pending) |
|---|---|---|---|
| P1B-01 | 5 | 3.5 | 4.7 |
| P1B-02 | 5 | 3.3 | 4.9 |
| P1C-01 | 5 | 2.0 (FAIL) | **PENDING** |
| P1C-02/03 | 5 | n/a (cascade) | PENDING |
| Full pipeline | **YES** | **NO** (format fail at P1C-01) | **PENDING** |

## Spot-check flags (review these first)

1. **qwen3.5 P1C-01 precision 3/5** — lowest-confidence verdict: pair
   verdicts "substantive" per scout report, but never validated at
   scale. If you want, we can hand-validate 3 pairs from the raw.
2. **qwen3.5 L4 maturity variance 0** — interpretation ("model
   conservative vs scorer over-collapse") is a hypothesis, not a
   measured fact. Re-measure on qwen3.8 run-all.
3. **qwen3.8 specificity 4/5 (both P1B)** — anti-verbosity judgement;
   the density claim ("every sentence carries a fact ref") is judge
   impression, quantified only by fact-cite counts.

---

## Changelog

- 2026-09-01 (16:00) — rubric v1 locked; matrix rewritten in verbose
  per-criterion format; qwen3.5 runall + qwen3.8 scout scored (judge =
  GLM-5.3-Flash via ZCode, commit `a710efd…` branch
  `feature/aegis-p1-corr-105-eval-framework`). JOB 1862843 pending.
- 2026-09-01 (16:30) — F2 fix: markdown-shape activation counter (regex)
  reveals qwen3.5 emits `- applicable: YES` in 10/10 lanes (was hidden
  by dict-only counter). P1C-01 Grounding 3 → 4; weighted 2.0 → 2.2.
  Critical insight: failure is parser/template mismatch, not zero
  emissions. Commits `2e36a30` (docs v1) and `0f2d64a` (F2 fix).