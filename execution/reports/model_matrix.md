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
- qwen3.8:27b → JOB 1862843 (full `--run-all`, 2026-09-01)

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

| Criterion | qwen3.5 (JOB 1847659) | qwen3.8 (JOB 1862843) | M3 gold |
|---|---|---|---|
| Template (.30) | **1** — emitted `## Pair classifications` with `- D-XX.Y : REG ↔ REG (VERDICT): …` bullets; completely different shape from the contract; parser extracted 0 activations. | **1** — same shape as qwen3.5 (`## Pair classifications` bullets) PLUS a `## Findings` section with `- D-XX.Y … applicable=YES … layer0_refs` entries. Richer, still unparseable. | 5 |
| Grounding (.25) | **4** — pair verdicts came with evaluated predicates (substantive content per scout report §2.7) but unverifiable at scale because nothing was extracted. | **4** — 15 pair verdicts with named predicates (e.g. `PRED-D01.1-GDPR-CRA-SAME-PARTY`) + 10 Findings entries with `layer0_refs` to SubDomains/ and the predicates catalog. Substantively stronger than qwen3.5. | 5 |
| Coverage (.20) | **1** — 0 of 38 sub-domains with an activation; REDUCE had nothing. | **1** — same parser result (0 activations extracted); REDUCE-LLM skipped (run log: `aggregated_activations is empty across all lanes`). | 5 |
| Precision (.15) | **3** — verdicts plausible but unvalidated (nothing reached validation). | **3** — predicates evaluated and named (e.g. `is_manufacturer AND product_stores_personal_data`); but unvalidated at scale. | 5 |
| Specificity (.10) | **3** — 27–53k tok/lane spent; unusable density without structure. | **3** — 1089.84 s MAP; ~40% faster than qwen3.5 on the same hardware, but unusable density without structure. | 5 |
| **Weighted total** | **2.2 / 5 → FAIL (parser blocks REDUCE)** | **2.2 / 5 → FAIL (same parser blocks REDUCE)** | 5 |

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

| Model | qwen3.5 (JOB 1847659) | qwen3.8 (JOB 1862843) | M3 gold |
|---|---|---|---|
| Result | **Not invoked** — log: "aggregated_activations is empty across all lanes; P1C-LLM-03/02 have nothing to reduce". Score n/a per criterion (unmeasurable); L4 = FAIL by cascade. | **Not invoked** — same cascade; Doc 05 §6.1b records `_(no LLM response for this spec)_` for both. Same root cause (P1C-01 parser). | 5 |
| Important distinction | This is **cascade failure, not model failure**. The model never got the chance to succeed or fail on its own merits. | Same cascade — confirmed in two different runs, two different models. **The pipeline architecture (P1C-01 parser → REDUCE input) is the gate, not the model family.** | — |

---

## L4 — Downstream artefacts (deterministic)

**TL;DR (PT):** REDUCE skipado em ambos os runs → Docs 07/07b
renderizam a partir de inputs vazios; Doc 04b com maturidade plana
1/1/…/1 (variância zero = sinal de alarme — scorer, não modelo);
qwen3.8 ganhou **5 gaps ranqueados com remediações concretas**
(§5 do Doc 04b) — única vitória real downstream.

| Check | qwen3.5 (runall) | qwen3.8 (scout) | qwen3.8 (runall) |
|---|---|---|---|
| REDUCE input | 0 activations → REDUCE-LLM skipped | n/a (Phase 1B only) | 0 activations → REDUCE-LLM skipped |
| Doc 06 clause mapping | 222 clauses (CRA 150 + GDPR 72), 41 unmapped | n/a | 174 rows (includes domain-cross); healthy |
| Doc 04b maturity variance | **0** — `1×10` across D-01..D-10; scorer does not differentiate | n/a | **0** — identical flatness → confirmed scorer issue, not model |
| Doc 04b top gaps | sparse | n/a | **5 ranked gaps with concrete remediation actions** ✓ |
| Doc 07 sub-domain rows | 38 | n/a | 38 |
| Output render | 6 artefacts + xlsx in 291.5s | Doc 05 only (42 KB) | **9 artefacts + xlsx** (includes Doc 04d from CORR-075) |

---

## L5 — Cost (measured, both runs A100-80)

| Metric | qwen3.5 | qwen3.8 (scout) | qwen3.8 (runall) | Δ runall vs qwen3.5 |
|---|---|---|---|---|
| P1B-01 CRA | 318 s / 125.7k tok | 201 s / 122.6k tok | ~200 s / 122.6k tok | **−37% time** |
| P1B-02 CRA | 260 s / 125.1k tok | 218 s / 126.3k tok | similar | similar |
| P1B-01 GDPR | 207 s / 93.5k tok | 152 s / 92.8k tok | similar | similar |
| P1B-02 GDPR | 263 s / 95.7k tok | 188 s / 96.0k tok | similar | similar |
| MAP (10× P1C-01) | 1805 s (10 lanes) | n/a | **1089.84 s** (10 lanes) | **−40%** |
| Throughput (P1B) | ~395 tok/s | ~600 tok/s | ~600 tok/s | **+52%** |
| Determinism | scout vs runall counts identical | identical across its own 2 runs | identical to scout | **all deterministic (temp=0)** |
| Total runall | ~53 min (5 stages) | n/a | ~50 min predicted | qwen3.8 ~6% faster end-to-end |
| Walltime headroom | 8 h allocated, used 53 min | 30 min allocated, used 18:04 | 8 h allocated, used 50 min | both very comfortable |

---

## Cross-model summary

| | M3 gold | qwen3.5 (runall) | qwen3.8 (runall) | ornith:9b (scout) |
|---|---|---|---|---|
| P1B-01 | 5 | 3.5 | 4.7 | 4.4 |
| P1B-02 | 5 | 3.3 | 4.9 | 4.1 |
| P1C-01 | 5 | 2.2 (parser FAIL) | 2.2 (parser FAIL — same root cause) | not run (scout) |
| P1C-02/03 | 5 | n/a cascade | n/a cascade | not run |
| P1B LLM time | — | 17.5 min | 12.6 min | **4.2 min** |
| Full pipeline | **YES** | **NO** (parser blocker) | **NO** (parser blocker, same) | pending run-all |

**Pending (queued on Deucalion, chain 1867429→30→31, 60 min each,
normal-a100-80; cluster queue backlog ≈2 days at submission):**
granite4.2:30b, nemotron-3.5-lightning:30b, muse-glimmer:30b.

**Comparative verdict:**
- **P1B**: qwen3.8 wins clearly (+1.2 / +1.6 vs qwen3.5); 52% faster.
- **ornith:9b**: near-qwen3.8 P1B quality (4.4/4.1) at **3× the speed and
  1/3 the blob size** — best quality-per-second measured. Placeholders in
  fact-refs (`DOC04:SEC-NN`) and one doubtful Art. 36 citation are the
  deltas; see its digest spot-checks.
- **P1C-01**: qwen3.5 and qwen3.8 identical (2.2) — not a model issue; parser is the gate.
- **P1C-02/03**: cascade, not measured.
- **Pipeline**: both blocked by the same architecture issue.

## Spot-check flags (review these first)

1. **qwen3.5 / qwen3.8 P1C-01 Grounding 4** — judge reading of Findings
   section; spot-check 1–2 Findings to confirm `layer0_refs` resolves
   to real SubDomains.
2. **Both runs L4 maturity variance 0** — confirmed scorer issue (Doc 04b
   §6 "Capability Summary"), not model-specific. Flag for separate fix.
3. **"Parser is the blocker" conclusion** — based on observed structure
   of two runs / two models. Would be disproven only if a future contract
   defines a parser that accepts the `## Pair classifications` shape
   (currently out of scope for CORR-105).
4. **ornith:9b "DOC04:SEC-NN" placeholder fact-refs** and **"Art. 36 =
   technical documentation"** citation (conflicts with qwen3.8's
   Art. 13 + Annex VII) — see its digest; if confirmed, P1B-02 drops
   4.1 → ~3.8.

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
- 2026-09-01 (17:30) — JOB 1862843 (qwen3.8 run-all) complete. P1B
  confirmed at 4.7 / 4.9 (matches scout prediction). **P1C-01 also
  fails at 2.2** — same root cause as qwen3.5: parser, not model.
  REDUCE-LLM skipped; P1C-02/03 cascade. qwen3.8 wins Doc 04b §5
  (actionable remediations) but not full pipeline. **Critical finding:
  the parser, not the model family, is the gate for non-M3 runs.**
  Comparator added to matrix; qwen3.5 L4 maturity variance now
  confirmed scorer issue (qwen3.8 also flat). Commits pending.
- 2026-09-01 (18:45) — ornith:9b scout (JOB 1867097) judged: P1B-01
  4.4, P1B-02 4.1 at 4.2 min LLM time (3× faster than qwen3.8, 1/3 blob).
  Added to cross-model summary; spot-check items 4 (SEC-NN placeholders,
  Art. 36 citation). Benchmark chain for granite4.2/nemotron-3.5/
  muse-glimmer (30B, 60 min each) queued on normal-a100-80
  (1867429→30→31); cluster backlog ≈2 days at submission.
  Ollama on cluster upgraded in place: $BD/bin now 0.32.13
  (0.31.1 kept as ollama-0.31.1.bak).
