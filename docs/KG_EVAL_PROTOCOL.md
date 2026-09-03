# KG Reasoning Evaluation Protocol — AEGIS-KG Phase 1 (T1)

**Document ID:** `AEGIS-DOC-KG-EVAL-001`
**Status:** DRAFT v0 — pending curation by Paulo (P7)
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

## 7. Open Questions for P7

1. **Model picker.** v0 ships `KG_EVAL_MODEL` as a CLI flag with a documented default
   that **fails loud if unset and not exported** (no silent gemma4:e4b fallback — the
   protocol must declare the model it evaluates). P7 confirms the first cheap student
   (`qwen3.5:9b` is the proposed default for a 30-run v0 cycle; cheap, deterministic
   on-cluster, and well-known to the AEGIS-KG corpus).
2. **Sample rate.** v0 = 1 task per (case × family × arm). A future bump may go to
   ≥3 tasks per (case × family) — the YAML supports this; the scorecard averages across
   the tasks but always reports the per-task breakdown so a single bad task cannot
   silently drag the family score.
3. **Packet regeneration cadence.** Today the packet is regenerated each run (deterministic
   from sources). A future bump may cache the packet under `output/kg_eval/_cache/` keyed
   on the `preproc_fingerprint` so two runs on the same case share the packet (faster,
   cheaper, but introduces a stale-packet failure mode that needs its own detection).
4. **Judge wiring.** v0 ships `judge: null` in the score JSON. The judge pass (L3 of
   §4) is the next iteration and uses the same GLM-5.3-Flash judge as
   [`execution/reports/EVAL_PROTOCOL.md`](../execution/reports/EVAL_PROTOCOL.md) §1.
   This protocol must not claim `judge ≥ 3.5/5` until the judge is actually wired; the
   pass rule in §4 explicitly allows `JUDGE_NOT_WIRED` in v0.

---

## 8. Implementation Status (2026-09-03 — initial)

| Component | Status | Path |
|---|---|---|
| `docs/KG_EVAL_PROTOCOL.md` | **DRAFT v0** | this file |
| `scripts/kg_eval/generate_context_packets.py` | **NEW (this contract)** | Commit 2 |
| `scripts/kg_eval/run_t1.py` | **NEW (this contract)** | Commit 3 |
| `scripts/kg_eval/tasks.yaml` | **NEW (this contract)** | Commit 3 |
| `scripts/kg_eval/score_t1.py` | **NEW (this contract)** | Commit 4 |
| `tests/unit/kg_eval/test_generate_context_packets.py` | **NEW (this contract)** | Commit 2 |
| `tests/unit/kg_eval/test_run_t1.py` | **NEW (this contract)** | Commit 3 |
| `tests/unit/kg_eval/test_score_t1.py` | **NEW (this contract)** | Commit 4 |
| KG ETL (the real graph) | **MISSING** — `scripts/kg_etl/` does not exist | separate work; KG-01 |
| Judge wiring (L3) | **JUDGE_NOT_WIRED** | deferred (v0 allows it) |

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