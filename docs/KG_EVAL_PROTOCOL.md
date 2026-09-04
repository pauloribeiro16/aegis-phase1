# KG Reasoning Evaluation Protocol — AEGIS-KG Phase 1 (T1)

**Document ID:** `AEGIS-DOC-KG-EVAL-001`
**Status:** DRAFT v1.1 — adds §3.5 pilot validation, §4.5 inference taxonomy, §6 T2 navigation spec, §7 sweep plan
**Date:** 2026-09-03
**Source of Truth:** [`OBJECTIVES_CONTRACT.md`](OBJECTIVES_CONTRACT.md) (`AEGIS-DOC-OBJ-001`),
[`KG_IMPLEMENTATION_CONTRACT.md`](KG_IMPLEMENTATION_CONTRACT.md) (`AEGIS-DOC-KG-CONTRACT-001`),
[`NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md`](NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md) (`AEGIS-DOC-NEO4J-ONTOLOGY-002` v3)
**Companion:** [`execution/reports/EVAL_PROTOCOL.md`](../execution/reports/EVAL_PROTOCOL.md) (rubric pattern)
**Scope:** Definition of T1 (KG reasoning) evaluation — the harness that measures whether
the KG substrate (or its file-based stand-in, since ETL does not exist yet) actually
improves LLM reasoning over the same questions asked without that context.

---

## 1. Purpose

This protocol exists to answer a specific question for the KG work:

**Does providing structured KG context (clauses, assets, tier, interactions, CONDITIONAL
pairs) improve model reasoning over the same questions asked without that context?**

The same Goodhart framing as [`OBJECTIVES_CONTRACT.md`](OBJECTIVES_CONTRACT.md) §1 applies:
*when a goal becomes an instruction to an optimiser, the optimiser satisfies the
instruction and loses the goal*. For the KG, the danger is:

1. Building a substrate that is **well-formed** (counts match, no orphans, fingerprints
   agree — see KG-01/03/04 in the KG contract) but **reasoning-empty** — a clean graph
   that no LLM consultation actually exploits.
2. Reporting "the model cited more IDs" as a win without checking that the cited IDs
   carried the right *information* (the disposition, the resolution, the tier, the
   example control) into the answer.

T1 closes that gap with a **reasoning value** measure, not a retrieval one. The unit of
measurement is the **delta in structured-output correctness** between the same question
asked with and without the KG context packet. The KG is *useful* iff the WITH-KG arm
emits more structured, anchored, correctly-disposed reasoning than the NO-KG arm — and
not just more text (specificity-per-100-chars is in the rubric, see `EVAL_PROTOCOL.md`
§2b).

**Mechanism rule (mirrors OBJ §1):**

1. Every T1 metric is an **acceptance criterion with a stated measurement**, not a
   sentiment. If the metric cannot be computed deterministically from the LLM output,
   the criterion is `JUDGE_NOT_WIRED` — never silently passed.
2. The list is **versioned and open**: criteria may be ADDED by P7; none may be removed
   or weakened without an explicit human decision recorded in the change log.
3. Any proposed change **must declare which criteria it could degrade** and re-run the
   full A/B loop (§3) before acceptance.

---

## 2. Five Task Families

Each task family probes a different reasoning layer that the KG substrate (or its
file-based stand-in) is meant to support. They mirror the navigation patterns of
[`NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md`](NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md) §5:

- T1.1 — **Grounding fidelity** (Pattern 2)
- T1.2 — **Tension resolution** (Pattern 4)
- T1.3 — **Ambiguity disposition** (Pattern 8)
- T1.4 — **Proportionality adequacy** (Pattern 3)
- T1.5 — **Cross-tier synthesis** (Patterns 1+2+4+8 combined)

For every task family we specify: definition, KG signals it uses, sample question
shape, expected output structure, and scoring.

### 2.1 T1.1 — Grounding fidelity

**Definition.** Given a system (or system set) named by the question, list every
obligation that binds it and cite the articles. The KG substrate gives asset → clause
edges (Pattern 2); the LLM is expected to surface the affected systems, the legal
clauses (with article references), and the CSF anchors.

**KG signals used.**

- `(:System)-[:IN_SCOPE_OF]->(:SubDomain)` (`rule_id`, `basis`)
- `(:RegulatoryClause)-[:MAPPED_TO_SUBDOMAIN]->(:SubDomain)`
- `(:SubDomain)-[:ANCHORED_TO_CSF]->(:CSFSubcategory)`
- `(:SubDomain)-[:HAS_ACTIVATION]->(:SubDomainActivation {run_id})`

**Sample question shape.**

```
For case <case_id> system <SYS-XXX>, list every regulatory obligation that binds it,
cite the source article(s), and the NIST CSF 2.0 subcategories that anchor them.
```

**Expected output structure (markdown).**

```markdown
## Affected systems
- <SYS-XXX> | <name> | criticality=<CRIT>

## Legal clauses (per regulation)
- <REG>: <CLAUSE-ID> — <article_reference>
- <REG>: <CLAUSE-ID> — <article_reference>

## CSF anchors
- <CSFFN.CAT-NN>: <outcome summary>
- <CSFFN.CAT-NN>: <outcome summary>

## In-scope rule
- rule_id=<R-XX>, basis="<verbatim from data/in_scope_of_rules.yaml>"
```

**Scoring.**

| Metric | Mechanism | Threshold |
|---|---|---|
| **Citation ⊆ packet** — every SYS-/STORE-/FLOW- token in the output appears in the context packet's `authoritative_ids.asset_ids` | `[G]` regex + set intersection (reuses `_ASSET_ID_RE` and `_validate_citations` from `ref_gate.py`) | 100% of cited asset IDs ⊆ packet |
| **Zero invented article references** — every cited article token resolves to a clause in `preproc_out/entities/clauses/_root/` | `[G]` regex for `Art. NN(...)` patterns + lookup | 0 inventions |
| **CSF tokens in canonical catalogue** | `[G]` reuses `_CSF_TOKEN_RE` and `_validate_csf_tokens` | 0 unknown tokens |
| **At least one legal clause cited** | `[G]` markdown-section detection (`## Legal clauses`) | ≥1 entry, non-empty |
| **At least one CSF anchor cited** | `[G]` markdown-section detection (`## CSF anchors`) | ≥1 entry, non-empty |

### 2.2 T1.2 — Tension resolution

**Definition.** Given a HIGH/MEDIUM cross-regulation conflict involving a subdomain of
the case, produce the structured resolution block that the navigation spec Pattern 4
demands. The KG substrate gives `(:RegulatoryInteraction)` with `interaction_type`,
`conflict_description`, `resolution_principle`, `severity`, `source_id`.

**KG signals used.**

- `(:Enterprise)-[:HAS_REGULATORY_INTERACTION]->(:RegulatoryInteraction)`
- `(:RegulatoryInteraction)-[:SCOPED_TO_SUBDOMAIN]->(:SubDomain)`
- `(:RegulatoryInteraction)-[:INVOLVES_REGULATION]->(:Regulation)`

**Sample question shape.**

```
For case <case_id> subdomain <D-XX.Y>, resolve the tension between <REG_A>
(interaction_type=<TYPE>) and <REG_B>. Cite the resolution principle the
methodology records and state the severity.
```

**Expected output structure (markdown).**

```markdown
### Tension Resolution: <REG_A> vs <REG_B> — <TYPE>
- Friction: <verbatim conflict_description>
- Resolution adopted: <verbatim resolution_principle>
- Severity: <HIGH|MEDIUM|LOW>
- Source reference: <source_id>
```

**Scoring.**

| Metric | Mechanism | Threshold |
|---|---|---|
| **Structured-block presence** — output contains the `### Tension Resolution:` heading with the required sub-bullets | `[G]` regex | block present and 4 sub-bullets filled |
| **Resolution cited** — `resolution_principle` text appears (verbatim or close paraphrase) in the output | `[G]` substring / fuzzy match | ≥80% token overlap |
| **Severity ∈ closed vocabulary** — output severity token ∈ {HIGH, MEDIUM, LOW} | `[G]` regex + enum check | exact match |
| **Regulations cited** — both `<REG_A>` and `<REG_B>` appear in output | `[G]` regex | both present |

### 2.3 T1.3 — Ambiguity disposition

**Definition.** Given a CONDITIONAL pair (documented ambiguity surface) between two
regulations, choose the applicable reading for this company and emit a disposition in
the closed vocabulary defined by [`OBJECTIVES_CONTRACT.md`](OBJECTIVES_CONTRACT.md) §4.

**KG signals used.**

- `(:RegulatoryPair {classification: 'CONDITIONAL'})` with `verbatim_articles`,
  `downstream_implication`, `scope_disjoint_test`
- `(:AmbiguityDisposition {run_id, disposition, applicable_reading, anchors, consequence})`

**Sample question shape.**

```
For case <case_id>, the CONDITIONAL pair <PAIR-ID> binds <REG_A> and <REG_B> on
subdomain <D-XX.Y>. Which documented reading applies to this company? State the
disposition and the anchors (article IDs, tier, asset IDs, business goal IDs) that
support the call.
```

**Expected output structure (markdown).**

```markdown
### Ambiguity Disposition: <REG_A> vs <REG_B> — <D-XX.Y>
- Reading adopted: <verbatim applicable_reading from verbatim_articles>
- Anchors: <comma-separated closed-list IDs>
- Consequence: <one-sentence consequence>
- Disposition: <RESOLVED_BY_FACT|RESOLVED_BY_TIER|NEEDS_HUMAN>
```

**Scoring.**

| Metric | Mechanism | Threshold |
|---|---|---|
| **Structured-block presence** — `### Ambiguity Disposition:` heading present with 4 sub-bullets | `[G]` regex | block present |
| **Disposition ∈ closed vocabulary** — output token ∈ {RESOLVED_BY_FACT, RESOLVED_BY_TIER, NEEDS_HUMAN} | `[G]` enum check | exact match |
| **Reading ∈ verbatim_articles** — chosen reading appears in the packet's `verbatim_articles` map | `[G]` substring match | 1+ reading match |
| **Anchors ⊆ closed lists** — every cited anchor ∈ article catalogue ∪ tier enum ∪ asset IDs ∪ BG-* IDs | `[G]` set intersection per anchor | 100% ⊆ |

### 2.4 T1.4 — Proportionality adequacy

**Definition.** Given a subdomain at a known enterprise tier, state the evidence depth
the methodology requires and give example controls that satisfy it. KG substrate gives
`(:ProportionalityEntry {tier, evidence_depth, example_controls, verification_method,
ownership})`.

**KG signals used.**

- `(:ProportionalityProfile)-[:CONTAINS_ENTRY]->(:ProportionalityEntry {sub_domain_id, tier, evidence_depth, example_controls})`
- `(:ProportionalityEntry)-[:OWNED_BY]->(:Stakeholder)`

**Sample question shape.**

```
For case <case_id> subdomain <D-XX.Y> at tier <TIER>, what evidence depth does the
methodology require? Name at least one example control and who owns the evidence.
```

**Expected output structure (markdown).**

```markdown
## Proportionality for D-XX.Y at tier <TIER>
- Tier: <verbatim from packet>
- Evidence depth: <verbatim evidence_depth>
- Verification method: <INSPECT|DEMONSTRATE|TEST|ANALYZE>
- Example controls: <verbatim example_controls>
- Owner: <stakeholder name / role>
```

**Scoring.**

| Metric | Mechanism | Threshold |
|---|---|---|
| **Tier ∈ closed enum** — output tier token ∈ {MINIMAL, LIGHTWEIGHT, STANDARD, RIGOROUS, DEFERRED} | `[G]` enum check | exact match |
| **Evidence depth non-empty** — `## Proportionality` block has the `Evidence depth:` line with ≥10 chars after the colon | `[G]` regex | non-empty |
| **At least one example control cited** — `Example controls:` line non-empty | `[G]` regex | ≥1 control name or vendor token |
| **Owner named** — `Owner:` line non-empty OR a stakeholder role (CISO/DPO/Engineering/Ops/Governance) appears | `[G]` substring match | ≥1 match |
| **Verification method ∈ enum** | `[G]` enum check | exact match (or N/A when omitted) |

### 2.5 T1.5 — Cross-tier synthesis

**Definition.** Given the case and a named system, produce the integrated regulatory
posture: which regulations apply, which subdomains are activated, the highest-tier
proportionality requirement, the open tensions, and any unresolved ambiguities.
Combines Patterns 1+2+4+8.

**KG signals used.** All of the above, plus:

- `(:Enterprise)-[:ACTS_AS {context}]->(:RegulatoryRole)`
- `(:Enterprise)-[:HAS_REGULATORY_INTERACTION]->(:RegulatoryInteraction)`

**Sample question shape.**

```
For case <case_id> system <SYS-XXX>, synthesise the regulatory posture: active
regulations, activated subdomains, the most rigorous proportionality requirement,
open tensions, and unresolved ambiguities. Cite the regulation IDs and CSF
subcategories for every claim.
```

**Expected output structure (markdown).**

```markdown
## Active regulations
- <REG>: <role> (context=<context>)
## Activated subdomains (top 5 by tier)
- <D-XX.Y> | tier=<TIER> | priority=<MUST|SHOULD|COULD>
## Open tensions
### Tension Resolution: ...
## Unresolved ambiguities
### Ambiguity Disposition: ...
## CSF anchors (per active regulation)
- <REG>: <CSF-ID>, <CSF-ID>
```

**Scoring.**

| Metric | Mechanism | Threshold |
|---|---|---|
| **Active regulation count cited** — count of `REG:` lines in `## Active regulations` section | `[G]` line counting | ≥1, ≤5 (closed vocabulary: GDPR, CRA, NIS2, DORA, AI_Act) |
| **At least one activated subdomain cited** | `[G]` regex for `D-XX.Y` in section | ≥1 |
| **At least one CSF anchor cited** | `[G]` regex | ≥1 |
| **At least one tension block OR ambiguity block present** | `[G]` regex | ≥1 structured block |
| **No invented regulation tokens** — every `REG` token ∈ canonical {GDPR, CRA, NIS2, DORA, AI_Act} | `[G]` set check | 0 inventions |

---

## 3. A/B Design (the value measure)

Every task runs **twice**, on the same case + same model + same temperature:

- **WITH-KG arm** (`--with-kg`): the LLM receives the task question + the deterministic
  context packet (see §6). The packet carries the closed lists of clauses, assets,
  interactions, CONDITIONAL pairs, and proportionality rows that the KG would surface
  in production. The packet SHA-256 is recorded for reproducibility.
- **NO-KG arm** (`--no-kg`): the LLM receives only the bare question + a 3-sentence
  case context (company name, sector, tier). No packet, no closed lists, no
  per-section anchors.

**Value of the KG substrate** = `(score on WITH-KG arm) - (score on NO-KG arm)`
per metric. We expect:

- T1.1 (citation ⊆ packet, zero inventions) → **WITH-KG strictly better** because the
  packet *defines* the closed list; without it the model is unconstrained.
- T1.2 (structured-block presence, resolution cited) → **WITH-KG strictly better**
  because the resolution text only lives in the packet.
- T1.3 (disposition vocabulary, anchors ⊆ closed lists) → **WITH-KG strictly better**
  because the closed-vocab constraint and the verbatim readings come from the packet.
- T1.4 (tier ∈ enum, evidence_depth non-empty) → **WITH-KG strictly better** because
  the tier + evidence text are not public domain knowledge.
- T1.5 (cross-tier synthesis) → **WITH-KG moderately better** because synthesis is
  in part memorisable; the strict win is on the *coverage* of active regulations and
  *CSF anchors present*.

A flat delta (WITH-KG ≈ NO-KG on every metric) means the KG substrate is not adding
reasoning value — that is the failure mode this protocol exists to detect, not the
success condition.

The A/B protocol mirrors `EVAL_PROTOCOL.md` §3 anti-bias rules: same judge, same
model, same temperature; the only difference is the presence of the packet. Position
bias is irrelevant (single-answer scoring); verbosity is penalised by
specificity-per-100-chars in `EVAL_PROTOCOL.md` §2b; self-preference is impossible
because the judge is never the model under test.

### 3.5 Pilot Validation Criteria (what "validado" means for a pilot run)

P7 chose to run a **pilot on one model first, then a sweep** (instead of N-model
run-all up front). A pilot is "validado" — and a sweep is authorised — only when:

- **Technical completeness.** 100% of pilot runs complete (no `RUN_ERROR` env
  records); ≥90% outputs are parseable; packet SHA + model + provider +
  gate_mode recorded in every `env.json`; scorer executes without crash on
  every artefact; **zero MockInvoker responses** (enforced by the
  `abort_on_mock` guard wired in commit 5).
- **Signal computable.** Each metric for each family produces a numeric value;
  the delta table (`WITH-KG − NO-KG`) is populated for every (case, family);
  invented-reference counts are present in both arms.
- **Sanity of the gap.** With-KG invented-reference rate ≤ No-KG invented-reference
  rate, OR a documented explanation (e.g. "model invented DORA Art. 99 because
  it always confuses DORA Art. 9 with Art. 99 — observed in 2/3 runs").
- **Cost in budget.** Pilot walltime ≤ 4h on `dev-a100-80` (one A100). If the
  pilot hits the cap, fix scope (fewer cases, smaller model) before sweep.
- **Human sign-off.** Digest in plain PT (≤1 page, no jargon) presented to P7;
  P7 replies GO or NO-GO with reasons captured in `OBJECTIVES_CONTRACT.md` §7.

A pilot that fails any criterion does **not** block the work — it triggers a
focused fix (harness bug, model swap, scope trim) and a re-run. No sweep until
all criteria pass.

---

## 4. Rubric (5-layer scorecard, per task family)

For each task family, we emit the same 5-layer scorecard as
[`execution/reports/EVAL_PROTOCOL.md`](../execution/reports/EVAL_PROTOCOL.md) §2:

| Layer | What | How | Deterministic? |
|---|---|---|---|
| **L1 Contract** | Output structure matches `expected_structure` from §2 | markdown-section regex + sub-bullet presence check | YES |
| **L2 Grounding** | Citation ⊆ packet, CSF tokens ∈ catalogue, asset IDs ∈ authoritative list | `_ASSET_ID_RE`, `_CSF_TOKEN_RE` from `ref_gate.py` | YES |
| **L3 Content quality** | Substance vs gold (M3) — defensibility of the chosen reading / resolution / proportionality | LLM judge, 1–5 with evidence quote, per rubric | NO |
| **L4 Downstream** | Structured-block presence and field completeness — the parts that downstream synthesis actually consumes | regex + JSON-shape check | YES |
| **L5 Cost** | tokens/call, walltime, retries | jsonl aggregation | YES |

**Pass rule per task family.** Pass = at least **1 [G] metric in L1 or L2 improved on
WITH-KG vs NO-KG AND the L3 judge ≥ 3.5/5 on WITH-KG AND no [G] regression on the same
metrics** (mirrors `OBJECTIVES_CONTRACT.md` §5 no-regression rule — a single regression
on a structured metric is enough to fail the family, averages never save it).

**Empty-context guard.** If the packet generator returns an empty list for any of
`asset_ids`, `clause_pairs`, `ambiguity_pairs`, `proportional_profile`, or
`regulatory_interactions`, the family is marked `EMPTY_PACKET` and the result is
**NOT** counted toward KG value — it is a signal that the file-based stand-in is
incomplete for that family on that case. KG-09 (closed-set fidelity) is the upstream
check that prevents an `EMPTY_PACKET` from being silently accepted.

---

### 4.5 Inference Taxonomy (what kinds of derivation we measure)

T1.6 (and the broader T2 work) decomposes "reasoning about the KG" into five
distinct kinds of inference. The taxonomy determines **what kind of ground
truth is available** and **what score function is honest**:

| Type | Description | Example | Ground truth | Scoring |
|------|-------------|--------|--------------|---------|
| **(a) Deterministic composition** | Combine facts already in the packet via a deterministic rule | "This `subprocessor=Y` flow, given the company role, requires DORA Art. 28 + GDPR Art. 28" | Pre-computable from packet by a script that uses the same sources | **Exact-match** on the output set |
| **(b) Inherited / composed obligation** | Cross-reference rows that say "this rule inherits from that clause" | "DORA obligations inherit from the AWS Frankfurt ThirdPartyService — what evidence depth?" | Pre-computable from packet | **Exact-match** |
| **(c) Trade-off between tensions** | Pick a `resolution_principle` when two regulations pull apart | "GDPR Art. 5(1)(c) vs NIS2 Art. 21(2)(e) for case X" | Semi-open (structure is closed; content is judged) | **Deterministic structure + judge on content** |
| **(d) Gap detection** | Identify obligations the enterprise's architecture does NOT satisfy | "What obligations cannot be met with the current inventory?" | Open | **Deterministic pre-checks + judge** |
| **(e) Counterfactual** | "If this store moves outside the EU, what obligations change?" | Open | Open; needs Art. 44 SCCS reasoning | **Fase 3 — not now** |

**Ground-truth rule:** wherever the truth is pre-computable (a, b, c
structure, d pre-checks), the scorer is **exact-match against a
pre-computed reference** (T1.6's `ground_truth.py`). Wherever it is open,
the judge carries the burden (and its cells are sampled + verbose, never
bare PASS/FAIL).

T1.1–T1.5 already cover type (c) at varying depth; **T1.6 is the canonical
type-(a) implementation** — same sources, same activation rule, exact-match
scoring. Type (b) gets partial coverage via T1.4 (proportionality); type (d)
is the next big stretch (Doc 09 territory); type (e) is Phase 2 / Phase 3.

---

## 5. Sampling

For v0 (this contract):

- **3 cases** — `case1-tinytask`, `case2-secureborder`, `case3-omnibank`
  (the canonical AEGIS-KG Phase 1 case corpus; same set used by
  [`execution/reports/EVAL_PROTOCOL.md`](../execution/reports/EVAL_PROTOCOL.md))
- **5 task families** — T1.1 through T1.5
- **2 arms** — WITH-KG and NO-KG
- **1 model** — one cheap, deterministic, on-cluster student (picked by P7; v0 ships
  with the model name as a required CLI flag, defaults to `qwen3.5:9b` if
  `KG_EVAL_MODEL` is unset; the default is a placeholder that the harness refuses
  silently-PASSing — see §7 Q1).

Total runs: **3 cases × 5 families × 2 arms × 1 model = 30 runs**. Each run is a single
LLM call on a single (case, subdomain, family, arm) tuple; ~1 minute on cluster with
the cheap student; total walltime ≤ 30 minutes plus judge pass.

**Per (case × family × arm)** we ship **1 representative task** — the most informative
subdomain for that family on that case (e.g. T1.1 for case1 → D-01.1 encryption at
rest, because SYS-01 + STORE-01 + FLOW-01 all converge there). This gives **15 unique
tasks × 2 arms = 30 runs**. Scaling to ≥2 models is a future bump and does not change
the protocol.

`scripts/kg_eval/tasks.yaml` carries the 15 task definitions (see Commit 3).

---

## 6. Environment Recording (per-run reproducibility record)

Every run writes the following sidecar (`output/kg_eval/<task>_<arm>_<ts>/env.json`):

```json
{
  "task_id": "T1.1-case1-D-01.1",
  "case_id": "case1-tinytask",
  "subdomain_id": "D-01.1",
  "family": "T1.1",
  "arm": "with_kg",
  "model": "qwen3.5:9b",
  "provider": "ollama",
  "quantization": "q4_k_m",
  "temperature": 0.1,
  "seed": null,
  "packet_sha256": "abc123…",
  "case_context_sha256": "def456…",
  "commit_sha": "<git rev-parse HEAD>",
  "timestamp_utc": "2026-09-03T12:34:56Z",
  "task_yaml_path": "scripts/kg_eval/tasks.yaml",
  "prompt_spec_version": "v0 (built inline; see scripts/kg_eval/run_t1.py)",
  "spec_versions": {}
}
```

The `packet_sha256` is the SHA-256 of the JSON-serialised context packet produced by
`scripts/kg_eval/generate_context_packets.py`. Two runs with identical inputs and
identical packet produce identical `packet_sha256` — that is the reproducibility
guarantee for the WITH-KG arm. The `commit_sha` ties the run to the exact code state
on this branch.

This sidecar is **mandatory** — any run without an `env.json` is `INVALID` and
excluded from the scorecard. This mirrors `EVAL_PROTOCOL.md` §7.

---

## 7. Sweep Plan (after pilot is validated)

The sweep is the **N-model run-all** that turns the pilot's single-model
delta into a matrix. It runs **only** after the pilot passes every criterion
in §3.5. The order is deliberate:

1. **Model list.** Start with the 5 co-leaders from the most recent
   `OBJECTIVES_CONTRACT_BASELINE` / DIGEST round that already proved they
   produce parseable output (track record matters — a model that the
   parse gate has rejected historically costs a job slot without producing
   data). For the first sweep the proposed set is:

   - **Co-leaders (proven)**: `nemotron-3.5-lightning:30b`, `qwen3.8:27b`
   - **Likely strong**: `gemma4:e4b`, `qwen3.5:27b`, `muse-glimmer:30b`
   - **Edge cases** (1 sweep only — confirms they don't break infra): `ornith:9b`, `mistral:7b`

   P7 confirms the final list before sweep submission.

2. **Submission shape.** 1 model per `sbatch` (sequential by node per
   `hpc-deucalion` skill rule), `dev-a100-80` partition (4h cap), no
   dependency between jobs (let the scheduler decide). Job names carry
   sanitised model + case to keep `squeue` readable.

3. **Per-model walltime budget.** 30 runs × ~30s/run ≈ 15 min for the
   scoring + I/O; warm-up adds ~5 min; margin = 1h. Two case3 cases with
   T1.6 ground truth computation can push 30 → 60 min — still well under
   4h. If any model crosses 1h walltime, the model is dropped from the
   sweep (recorded as `SWEEP_TIMEOUT` in the digest).

4. **Collect + score.** `score_runs(output/kg_eval/)` is re-run on the
   workstation against the cluster artefacts; the scorecard JSON per
   model is the input to the sweep digest.

5. **Digest.** One plain-PT page per model, matrix of `(model × family)`
   delta on the headline metrics; GO/NO-GO recommendation per model
   (no model that violates OBJ-02 zero-omission may join Phase 2
   integration without remediation).

6. **Anti-patterns.** No new families added during a sweep (lock the
   catalogue; bumps go in a new contract iteration). No silent model
   swaps. No averaging over models with different temperaments — each
   model gets its own digest page.

7. **Sweep budget.** Aim for ≤1 week walltime on `dev-a100-80`. If the
   queue is hostile, defer models one-by-one rather than burning the
   budget on partial data.

---

## 8. T2 — Navigation (agent with cypher() tool, separate work)

T1 measures generation quality under controlled conditions (the packet
removes the need to *find* the data). T2 measures the next question:
**does the model know what to ask for?** Requires the real KG ETL (Phase
2 work) + an agent harness that exposes a `cypher(query) → rows` tool.
Outline only — not implemented in v1.1.

**Harness shape.** The model receives: a small prompt with the schema
summary (from spec v3 §3), the task question, and a turn budget of
8–10 invocations. Every query and response is logged verbatim. Judge
cells carry 5 dimensions:

1. **Query strategy** — number of queries to reach the answer vs the
   optimal (we pre-compute the optimal against our own graph). Sub-optimal
   ≥2x flags for review.
2. **Syntactic + schema validity** — labels, relations, properties used
   in `MATCH` must exist in the spec catalogue. Parsed + checked
   deterministically. (Failure mode expected: `(:Company)` instead of
   `(:Enterprise)`; `[:DEPENDS_ON]` invented.)
3. **Error recovery** — when a query returns empty or wrong, does the
   model adapt or repeat? Counted and categorised.
4. **Grounding discipline** — every fact in the final response must come
   from a query the agent actually issued (grounded in the conversation
   log; same `⊆` discipline as T1.1 but over the agent's own history).
5. **Knowing when to stop** — 3–5 "impossible" questions per task
   family whose answer is genuinely absent from the graph. Correct
   behaviour = declare absence + describe what would be needed
   (`NEEDS_HUMAN`); failure = confabulate.

**Attribution discipline.** A model that fails navigation may fail for
three distinct reasons (skill L2.3 of `agent-orchestration`):

- (i) doesn't know Cypher syntax,
- (ii) is overwhelmed by the schema size in the prompt,
- (iii) can't plan multi-hop.

The harness **must** separate these signals (syntax error rate; prompt
size ablations; query count vs optimal) before blaming the model. The
schema summary in the prompt must be **fixed** across ablations — varying
the prompt changes the question.

---

## 9. Open Questions for P7

1. **Model picker (pilot).** P7 confirms the first model for the pilot
   run. Recommendation: `nemotron-3.5-lightning:30b` (proven co-leader,
   zero PENDING history in the cluster memory, 30B on A100 fits the 4h
   cap). Backup: `qwen3.8:27b`. See `execution/runs/...` history and
   the model scoring matrix.
2. **Sample rate.** v0 = 1 task per (case × family × arm); the pilot
   reuses the same catalogue (now 20 tasks after T1.6 commit).
3. **Packet regeneration cadence.** Today the packet is regenerated each
   run. A future bump may cache the packet under `output/kg_eval/_cache/`
   keyed on `preproc_fingerprint` — out of scope for the pilot.
4. **Judge wiring.** v0 ships `judge: null` in the score JSON. The judge
   pass (L3 of §4) is the next iteration and uses the same judge as
   `OBJECTIVES_CONTRACT` §5; the pass rule explicitly allows
   `JUDGE_NOT_WIRED` in v0.
5. **T2 readiness.** §8 is outline-only. The T2 pilot requires the mini-ETL
   (KG-01..04 of `KG_IMPLEMENTATION_CONTRACT.md`) to land first; P7
   confirms whether T2 enters the next sprint.

---

## 10. Implementation Status (2026-09-03 — initial + v1.1 updates)

| Component | Status | Path |
|---|---|---|
| `docs/KG_EVAL_PROTOCOL.md` | **DRAFT v1.1** | this file |
| `scripts/kg_eval/generate_context_packets.py` | **NEW** | Commit 2 |
| `scripts/kg_eval/run_t1.py` | **NEW (anti-mock guard wired in v1.1)** | Commit 3 + Commit 5 |
| `scripts/kg_eval/tasks.yaml` | **NEW (T1.6 added in v1.1)** | Commit 3 + Commit 6 |
| `scripts/kg_eval/score_t1.py` | **NEW (T1.6 scorer + _score_t16)** | Commit 4 + Commit 6 |
| `scripts/kg_eval/ground_truth.py` | **NEW (deterministic T1.6 reference)** | Commit 6 |
| `tests/unit/kg_eval/test_generate_context_packets.py` | **NEW** | Commit 2 |
| `tests/unit/kg_eval/test_run_t1.py` | **NEW (anti-mock tests added)** | Commit 3 + Commit 5 |
| `tests/unit/kg_eval/test_score_t1.py` | **NEW** | Commit 4 |
| `tests/unit/kg_eval/test_ground_truth.py` | **NEW** | Commit 6 |
| KG ETL (the real graph) | **MISSING** — `scripts/kg_etl/` does not exist | separate work; KG-01..04 |
| Judge wiring (L3) | **JUDGE_NOT_WIRED** | deferred (v0 allows it) |
| T2 navigation harness | **OUTLINE ONLY** | §8; depends on KG-01..04 |
| Pilot sbatch template | **PLANNED** | `examples/deucalion/kg-eval-t1-pilot.sbatch` (Phase 2 of the implementation plan) |

**Anti-mock guard (v1.1):** the previous v0 had a silent MockInvoker fallback in
`run_t1.py` — if the build_llm_invoker call raised, the runner would quietly use
the mock and the run would produce mock answers. v1.1 closes this gap
(`abort_on_mock=True` + explicit `allow_mock=True` opt-in for tests + `--abort-on-mock`
CLI flag the pilot job sets hard). See commit 5.

**T1.6 obligation derivation (v1.1):** new family with deterministic ground truth
generated from `preproc_out/regulation/<REG>/aggregated/02_SecurityRules_NIST.json`
(matches the KG ETL contract KG-10 — what `(:ClauseActivation)` would emit in
production). Scoring is exact-match precision/recall/F1 against the precomputed
SHA-256-pinned reference. See commit 6.

**56 unit tests** as of v1.1; ruff clean on `scripts/kg_eval/` + `tests/unit/kg_eval/`.

The protocol ships before any real KG ETL so the value question (does the substrate
*help reasoning*) can be answered from the start, with the file-based stand-in. When
the ETL lands, the packet generator is replaced by a Cypher-driven equivalent that
emits the same JSON shape; the A/B loop, the rubric, and the scorecard do not change.

---

## Change Log

- **v0 (2026-09-03):** initial draft. 5 task families (T1.1–T1.5) mapped 1-to-1 to
  the navigation patterns of the spec v3. A/B design (with-KG vs no-KG). 5-layer
  rubric per family. 30 runs v0 (3 cases × 5 families × 2 arms × 1 model).
  Scorecard emission deferred to `scripts/kg_eval/score_t1.py`; judge cell stubbed
  to `null` until the next iteration wires the GLM-5.3-Flash judge.
- **v1.1 (2026-09-03):** adds T1.6 obligation-derivation family with
  deterministic precomputed ground truth (commit 6); closes the silent-MockInvoker
  gap with `abort_on_mock` + explicit `allow_mock=True` (commit 5); introduces
  §3.5 pilot validation criteria (the answer to "what does validado mean");
  §4.5 inference taxonomy (5 types — composition, inheritance, trade-off,
  gap-detection, counterfactual — with ground-truth feasibility per type);
  §7 sweep plan (model picker, queue etiquette, anti-patterns); §8 T2 navigation
  outline (5 dimensions, attribution discipline for skill L2.3). Catalogue grows
  from 15 → 20 tasks (T1.6: 5 new across the 3 cases). Tests: 41 → 56.
  Rubric and A/B design unchanged — backward-compatible v0 scorecards remain valid.