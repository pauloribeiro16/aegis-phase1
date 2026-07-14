# LLM Architecture Decision — Post-Corrections Analysis

> **Status:** DRAFT (awaiting human decision)
> **Date:** 2026-07-14
> **Authors:** Orchestrator + Executor
> **Contract:** AEGIS-P1-CORR-001 Phase 6
> **Predecessor phases:** 0 (rebranding), 1 (clause IDs), 2 (adapted_objective), 3 (decouple), 4 (mandatory narratives), 5 (YAML input)

## Executive Summary

After Phases 0–5, the `aegis-phase1` v2 pipeline has:

- 10 mandatory MAP-stage LLM invocations per case, one for each domain D-01 through D-10, producing `adapted_objective` and related adjustments;
- 18 mandatory narrative invocations across seven output documents, with a visible `PENDING REVIEW` marker on failure rather than silent fallback;
- 28 logical LLM invocations in a successful full case run before retries, not 18;
- five canonical Phase 1 LLM specifications in `Methodology-main/00_METHODOLOGY/PROMPTS/`, plus an implemented `Phase1Executor`, but no connection from that executor to the v2 runner;
- 232 passing tests in `tests/unit/v2/`;
- a human review loop for each MAP-stage `adapted_objective`.

**Recommendation:** Adopt the **2-LLM minimal architecture** for the next production increment: retain the per-domain `adapted_objective` task and add one persisted global strategic-synthesis task. Replace generic narrative LLM invocations with structured deterministic rendering whose provenance is explicit. Do **not** restore silent fallback. Keep the canonical five-LLM architecture as the research-grade target for a later program increment, after model-quality, input-contract, and cost evidence justify it.

This recommendation reduces a normal full run from 28 to 11 logical invocations (approximately 61%) while preserving the two tasks where contextual reasoning adds the clearest value.

## Current State Inventory

### Scope and counting method

A **logical invocation** is one intended task execution. A **provider attempt** includes retries. The MAP processor allows up to three attempts per domain, so a nominal 10-call MAP can produce up to 30 provider attempts. Narrative invocations do not use the MAP retry loop.

### Active v2 LLM call points after Phases 0–5

All output narratives converge on `render_mandatory_narrative()` and its single `invoker.invoke(prompt)` call at `src/aegis_phase1/v2/output/_narrative.py:87`.

| Stage | File and line | Logical calls per case | What it does | Failure semantics |
|---|---|---:|---|---|
| MAP | `v2/domain/processor.py:123` | 10 | Produces per-domain `adapted_objective`, key adjustments, and confidence | LLM connectivity exception aborts MAP; exhausted parse retries produce a failed domain and ultimately block REDUCE |
| OUTPUT 04a §1 | `v2/output/doc_04a.py:113` | 1 | Technical architecture narrative | Visible `PENDING REVIEW`; document generation continues |
| OUTPUT 04a §1.2 | `v2/output/doc_04a.py:126` | 1 | Network topology narrative | Visible `PENDING REVIEW`; document generation continues |
| OUTPUT 04b §3 | `v2/output/doc_04b.py:478`, `:488`, `:795` | 10 | One maturity Notes narrative for each domain | Visible `PENDING REVIEW` per domain; document generation continues |
| OUTPUT 04c §5.1 | `v2/output/doc_04c.py:318` | 1 | Concentration-risk narrative | Visible `PENDING REVIEW`; document generation continues |
| OUTPUT 04d §5 | `v2/output/doc_04d.py:404` | 1 | Reporting-lines narrative | Visible `PENDING REVIEW`; document generation continues |
| OUTPUT 04d §9 | `v2/output/doc_04d.py:568` | 1 | Escalation-path narrative | Visible `PENDING REVIEW`; document generation continues |
| OUTPUT 05 §6.1 | `v2/output/doc_05.py:412` | 1 | Strategic applicability narrative | Visible `PENDING REVIEW`; document generation continues |
| OUTPUT 07 §6.1 | `v2/output/doc_07.py:302` | 1 | Cross-regulation strategic narrative | Visible `PENDING REVIEW`; document generation continues |
| OUTPUT 07b §5.1 | `v2/output/doc_07b.py:269` | 1 | Proportionality cross-check narrative | Visible `PENDING REVIEW`; document generation continues |
| **Total** | | **28** | **10 MAP + 18 output narratives** | |

There are nine named narrative concerns in the output layer. The phrase “eight mandatory narrative sections” understates the implementation because Doc 04a and Doc 04d each have two call sites, while Doc 04b expands one per-domain concern into ten invocations.

### Orchestrator dispatch and execution boundaries

The v2 orchestrator dispatches output renderers in two groups:

- `generate_deterministic_docs()` dispatches Docs 04 body, 05, 06, 07, and 07b at `v2/orchestrator.py:357-363`;
- `generate_enhanced_docs()` dispatches Docs 04a–04d at `v2/orchestrator.py:445-450`.

The deterministic group is decoupled from MAP, but it is not necessarily free of LLM calls. The runner constructs an invoker before mode dispatch at `v2/runner.py:177-178`, and `generate_deterministic_docs()` passes it to Docs 05, 07, and 07b. Their `_should_use_llm()` functions accept the invoker unless `MOCK_LLM` is set. Therefore, `--deterministic-only` can perform three real narrative calls. This is an execution-boundary inconsistency to correct in any selected architecture.

### Other LLM implementations not active in the v2 runner

The repository also contains canonical invocation code outside the active v2 path:

- `prompts_v2/phase1_executor.py:182`, `:191`, `:246`, `:365`, and `:379` implement all five canonical tasks;
- `_v2` functions in legacy LangGraph nodes invoke four canonical task types;
- the active legacy subphase graphs import the non-`_v2` node functions, and the active v2 runner never constructs or invokes `Phase1Executor`.

The canonical architecture is therefore **implemented as a callable subsystem but operationally unwired into the v2 runner**. Calling it merely “documented” would overlook existing code; calling it “integrated” would overstate the current execution path.

## Canonical Five-LLM Specifications

The canonical library is versioned in `Methodology-main/00_METHODOLOGY/PROMPTS/`. All specifications require structured output, Regulatory Baseline citations in `layer0_refs`, no silent reclassification, and an `INSUFFICIENT_EVIDENCE` outcome when facts do not support a verdict.

| Specification | Invocation | Calls per case | Purpose |
|---|---|---:|---|
| `P1B-LLM-01-INTERPRETATION` | `per_regulation` | 2–5 | Evaluates company-specific activation of canonical Tipo 2 interpretations and Tipo 3 derogations after deterministic applicability filtering. It uses company role, tier, architecture, products, data categories, and role obligations. |
| `P1B-LLM-02-RATIONALE` | `per_regulation` | 2–5 | Produces one coherent per-regulation synthesis: company-specific applicability rationale, structured implications, and gaps. It consumes the preceding interpretation/derogation result and replaces three legacy calls. |
| `P1C-LLM-01-OVERLAP-CLASSIFICATION` | `per_domain_lane` | 1–10 | Activates company-scope verdicts for Regulatory Baseline `CONDITIONAL` relationships per active domain. It must preserve frozen `SAME`, `COMPLEMENTARY`, `CONTRADICTORY`, and `SCOPE_DISJOINT` classifications. |
| `P1C-LLM-03-STRATEGIC-SYNTHESIS` | `global_reduce` | 1 | Detects cross-lane architectural, ownership, evidence, supplier, resource, and consolidation patterns. Track B/Doc 07b is authoritative; the model may not change tiers, prescribe controls, or make budget/risk-acceptance decisions. Runs first in REDUCE. |
| `P1C-LLM-02-COMPOUND-EVENT` | `global_reduce` | 1 | Identifies catalog-backed events that trigger incompatible or coordinated obligations across at least two domains and two regulations. It identifies events only; resolution design remains Phase 2. Runs after strategic synthesis. |
| **Total** | | **16–22** | **4–10 Phase 1B + 10 Phase 1C MAP + 2 Phase 1C REDUCE** |

The canonical architecture provides substantially stronger invariants than the current free-text narrative calls. It also demands richer inputs than the current v2 MAP result. In particular, canonical strategic synthesis expects aggregated overlap activations and Doc 07b references. A minimal integration must either provide a deterministic adapter with equivalent fields or version the strategic-synthesis input contract; it must not claim strict conformance while omitting required evidence.

## Test Baseline

On 2026-07-14, the scoped command below completed successfully:

```bash
PYTHONPATH=src .venv/bin/pytest tests/unit/v2 -q
```

Result: **232 passed in 2.38 seconds**. No regressions were introduced in this analysis-only phase.

## Architecture Principles

The decision should satisfy five constraints:

1. **Reasoning only where ambiguity is genuine.** Deterministic source facts, tables, arithmetic, routing, and formatting should not require generative prose.
2. **Compliance and security both remain explicit.** Regulatory citations alone are insufficient; outputs must also explain security rationale and operational effect.
3. **Proportionality is authoritative.** Track B and human-reviewed `adapted_objective` outputs constrain implementation depth; an LLM must not raise or lower the regulatory floor.
4. **Provenance must remain visible.** Generated, deterministic, and pending content must be distinguishable. Silent fallback is not acceptable.
5. **Human decisions remain human.** No model decides budget, headcount, scope, risk acceptance, or timeline commitments.

## Three Architecture Options

### Option A: Status quo

**Shape:**

- 10 MAP calls for `adapted_objective`;
- 18 generic output narrative calls;
- 28 logical calls per normal full run, with up to 48 provider attempts if every MAP call exhausts its three-attempt allowance;
- visible `PENDING REVIEW` markers for narrative failure.

**Advantages:**

- already implemented;
- no immediate migration cost;
- preserves prose density across all current output documents;
- MAP review loop is operational.

**Disadvantages:**

- generic narrative calls duplicate data already present in tables;
- two strategic narrative calls in Docs 05 and 07 can diverge;
- Doc 04b uses 10 calls for short Notes alongside the already generated per-domain `adapted_objective`;
- output calls lack the canonical JSON Schemas and Regulatory Baseline citation invariants;
- `--deterministic-only` can still invoke a real model;
- no consolidated per-case budget, cache, or call-count policy is enforced in the v2 path.

**Assessment:** Viable as a temporary baseline, but inefficient and internally inconsistent.

### Option B: Canonical five-LLM architecture

**Shape:**

- 2 calls per applicable regulation in Phase 1B;
- 1 overlap-activation call per active domain in Phase 1C MAP;
- 2 global REDUCE calls;
- 16–22 logical calls for the three reference cases.

**Advantages:**

- research-grade map/reduce topology;
- structured schemas and deterministic post-generation validation;
- citation, no-reclassification, and insufficient-evidence invariants;
- explicit synchronization and conflict handling;
- fewer calls than the current 28-call implementation for the reference cases.

**Disadvantages:**

- the callable `Phase1Executor` is not wired to v2 state or runner lifecycle;
- current v2 MAP outputs and canonical lane activations have different contracts;
- output renderers do not consume canonical structured results;
- model quality, latency, and cost have not been validated end-to-end for all five tasks;
- two-repository prompt drift remains unpinned;
- estimated integration and validation effort is approximately 4–6 weeks.

The implementation supports local Ollama, while the canonical specs name MiniMax-M2.7 and an Anthropic alternative. A remote provider is not a formal prerequisite, but production adoption requires comparative evaluation demonstrating that the selected model satisfies schemas and legal/security reasoning criteria.

**Assessment:** Methodologically strongest target, but premature for the next production increment.

### Option C: Minimal two-LLM architecture — recommended

“Two LLMs” means two **semantic tasks**, not two calls:

1. **Per-domain adaptation task — 10 calls.** Retain the current MAP-stage `adapted_objective` generation and human review loop. This interprets the Track B tier and company facts into a domain-specific objective without changing the regulatory/security floor.
2. **Global strategic-synthesis task — 1 call.** Add one persisted case-level synthesis after deterministic REDUCE/Track B. Reuse that single structured result wherever strategic prose is required; do not invoke separately from each renderer.

**Shape:** 11 logical calls per normal case, approximately 61% fewer than the current 28.

**Output treatment:**

- replace the 16 non-strategic narrative calls in Docs 04a, 04b, 04c, 04d, and 07b with structured deterministic summaries derived from their existing tables and source fields;
- remove the two independent strategic renderer calls in Docs 05 and 07;
- render one persisted strategic-synthesis result in the human-selected destination, preferably Doc 07 §6;
- mark deterministic prose explicitly, for example `Source: deterministic rendering from <fields>`;
- retain `PENDING REVIEW` if the one strategic call fails or lacks evidence;
- never represent deterministic text as model-generated text and never silently substitute one for the other.

**Advantages:**

- concentrates model usage in contextual adaptation and cross-lane reasoning;
- preserves the proven human review loop;
- eliminates duplicated and potentially inconsistent strategic calls;
- makes `--deterministic-only` capable of a true zero-LLM guarantee;
- reduces latency, local resource use, and remote-provider cost;
- keeps deterministic facts auditable and reproducible;
- supports compliance, security, business, risk, and technical perspectives in the single global synthesis rather than scattering them across decorative prose.

**Disadvantages:**

- documents will contain less generative prose;
- deterministic renderers need explicit source/provenance labels;
- the canonical `P1C-LLM-03` input contract cannot be reused unchanged unless the required activation and Doc 07b reference structures are supplied;
- compound-event identification remains deterministic/catalog-driven or deferred rather than receiving a dedicated LLM;
- a single global synthesis is a quality and availability concentration point.

**Assessment:** Best production fit now, provided the strategic task receives a versioned, validated input contract and all removed narrative sections retain explicit provenance.

## Recommendation Rationale

The recommendation is based on the post-correction implementation trace rather than on call-count minimization alone:

- `adapted_objective` performs company-specific interpretation and already has a human approval/edit/reject loop;
- cross-lane strategic synthesis is the clearest location for multi-perspective reasoning that cannot be recovered by formatting one table at a time;
- architecture summaries, network descriptions, maturity Notes, reporting lines, escalation paths, concentration summaries, and proportionality cross-checks are generated from structured facts already present in the same documents;
- the generic output calls do not enforce the canonical schema/citation invariants, so prose volume does not equal research rigor;
- two separate strategic narratives create inconsistency risk without adding an independent control;
- restoring pre-Phase-4 silent fallback would erase provenance and contradict the correction contract.

Option C is therefore a reduction in unvalidated generative surface, not a reduction in compliance or security analysis. The deterministic tables and gates remain authoritative; the two semantic LLM tasks operate only where company-specific interpretation or cross-lane synthesis is material.

## Proposed Migration Path

### Phase 6a — Execution boundary and observability (approximately 1 week)

- guarantee that `--deterministic-only` passes no invoker and performs zero provider calls;
- centralize logical-invocation and provider-attempt counting;
- record task ID, model, prompt version, latency, token use, retry count, and status per call;
- define one policy layer for required, optional, and prohibited LLM tasks.

### Phase 6b — Deterministic narrative replacement (approximately 1 week)

- replace the 16 non-strategic output calls with structured deterministic summaries;
- include explicit source-field and provenance labels;
- remove the 10 Doc 04b Notes calls and retain the human-reviewed `adapted_objective` as the domain-specific narrative;
- retain visible `PENDING REVIEW` only where a section truly requires unresolved human or model reasoning.

### Phase 6c — One persisted strategic synthesis (approximately 1–2 weeks)

- version the strategic-synthesis input contract for the v2 data actually available;
- invoke once after deterministic REDUCE/Track B;
- validate structured output, citations, assumptions, cross-lane span, and human-decision boundaries;
- persist the result in state and render it without re-invocation;
- use `MockInvoker` for deterministic tests and an explicitly selected provider for acceptance evaluation.

### Phase 6d — Production evidence and gate (approximately 1 week)

- run representative cases across company tiers and regulation counts;
- compare quality, latency, retry rate, and cost against Option A;
- require human review of low-confidence or insufficient-evidence results;
- update contracts only after the human decisions in this document are recorded.

### Deferred research-grade integration (approximately 4–6 weeks)

- connect `Phase1Executor` to the v2 runner and state model;
- adapt renderers to canonical structured outputs;
- pin or vendor the methodology prompt version;
- validate all five canonical tasks and provider/model combinations;
- treat this as a later Phase 1 architecture increment, not as an automatic consequence of approving Option C.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Leaner documents are perceived as incomplete | Preserve required tables, gates, and concise deterministic summaries; use explicit provenance and human sign-off |
| Silent fallback returns under a new name | Prohibit silent substitution; label deterministic content and retain `PENDING REVIEW` for unresolved reasoning |
| Cross-regulation tension is missed without canonical overlap/compound-event LLMs | Evaluate catalog predicates deterministically, preserve `INDETERMINATE`, and route unresolved conflicts to human/Phase 2 review |
| Strategic synthesis lacks canonical upstream activations | Version and validate a v2-specific input adapter before invoking; do not claim canonical conformance without required fields |
| One global synthesis fails | Persist status and inputs, allow controlled retry, leave visible `PENDING REVIEW`, and keep deterministic tables usable |
| Model produces unsupported legal claims | Require Regulatory Baseline references, schema validation, article cross-checking, and human review |
| Local model cannot satisfy structured quality criteria | Benchmark local Ollama against MiniMax/Anthropic on the same cases; select from evidence rather than preference |
| Model configuration is inconsistent | Resolve the current `gemma4:e4b` runner default versus `gemma4:e2b` repository guidance and canonical MiniMax configuration |
| Prompt changes in Methodology-main silently affect runs | Pin a prompt-library version or content hash and fail clearly on incompatible schema versions |
| Cost and retry growth remain invisible | Log logical calls separately from attempts, token usage, cache hits, latency, and per-case/month caps |
| Compliance prose is reduced but security reasoning is also lost | Require every retained LLM output to connect Regulatory Baseline sources to a concrete security rationale and company fact |
| Proportionality is overridden by synthesis | Treat Track B and approved `adapted_objective` values as read-only constraints; schema-reject tier/control changes |

## Change Propagation Analysis

Creating this decision record has no runtime or generated-document dependency. Implementing Option C would affect more than three artefacts and therefore requires an explicit propagation plan.

At minimum, implementation touches the seven output documents/renderers represented by Docs 04a, 04b, 04c, 04d, 05, 07, and 07b, plus runner/orchestrator state, LLM policy/logging, and tests. The methodology dependency graph further shows:

- Doc 05 feeds Docs 06 and 07;
- Doc 07 feeds Doc 08;
- Doc 07b feeds Docs 08, 11, and 14.

Accordingly, acceptance must include revalidation of downstream Phase 1 outputs and the Phase 2/3 consumers identified by `dependency_graph.yaml`. No such propagation is executed in this analysis-only phase.

## Open Questions for Human Decision (P7)

1. **How should the current narrative sections be treated?**
   - (a) Remove non-essential narrative subsections and retain authoritative tables only.
   - (b) Keep concise, explicitly labelled deterministic summaries where structured data is sufficient — **recommended**.
   - (c) Keep all current sections mandatory with `PENDING REVIEW` on model failure.
   - (d) Restore silent fallback — **not recommended**, because it removes provenance established in Phase 4.

2. **Where should the one strategic-synthesis output land?**
   - (a) Doc 07 §6 — **recommended**, because Doc 07 is the canonical Phase 1 handoff and already owns cross-lane implications.
   - (b) New `07c_Strategic_Synthesis.md`.
   - (c) Doc 04 as a CEO-facing summary.
   - (d) Persist once and render excerpts in more than one document without re-invocation.

3. **When should the five canonical LLMs be connected to v2?**
   - (a) Wire all five now (approximately 4–6 weeks, research-grade).
   - (b) Keep the callable subsystem unwired while Option C gathers production evidence — **recommended**.
   - (c) Wire only the Phase 1C REDUCE tasks.

4. **Must `--deterministic-only` guarantee zero model/provider calls?**
   - (a) Yes — **recommended**.
   - (b) No; it means independent of MAP only.

5. **What model-selection gate is required?**
   - (a) Local Ollama only.
   - (b) Remote MiniMax/Anthropic only.
   - (c) Evidence-based selection using the same schemas, cases, quality rubric, latency, and cost measurements — **recommended**.

## Cross-Cutting Decisions Deferred

- **JSON Schema field renaming:** `layer0_refs` to `regulatory_baseline_refs` is a breaking change deferred by the Phase 0 contract.
- **Model selection:** reconcile local Ollama model naming and benchmark it against MiniMax/Anthropic.
- **Cost tracking:** define per-case token/attempt budgets and monthly caps.
- **Caching:** define content-addressed caching by task ID, prompt version, model, and normalized input hash.
- **Prompt/version pinning:** replace the unpinned two-repository dependency with a versioned contract.
- **Strategic input schema:** decide whether to adapt v2 state to canonical `P1C-LLM-03` or publish a new compatible spec version.
- **Compound-event ownership:** keep deterministic/catalog-driven, add the canonical LLM later, or defer unresolved events to Phase 2.

## Acceptance

- [ ] Human decision on narrative-section treatment (Q1)
- [ ] Human decision on strategic-synthesis placement (Q2)
- [ ] Human decision on canonical five-LLM timing (Q3)
- [ ] Human decision on zero-LLM semantics for `--deterministic-only` (Q4)
- [ ] Human decision on model-selection gate (Q5)
- [ ] Propagation plan approved for all affected documents and downstream consumers
- [ ] Updated contracts created only after decisions are recorded
