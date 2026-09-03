# Proposal: Adaptive Execution Engine & Anti-Lazy Quality Gates

**Document ID:** `AEGIS-DOC-PROP-001`  
**Status:** DRAFT / PENDING PEER MODEL REVIEW  
**Author:** Antigravity (Pair Programming Session)  
**Date:** 2026-09-03  
**Target Repository:** `aegis-phase1` (Phase 1 Baseline Pipeline)  
**Audience:** Peer LLMs (Claude 3.5 Sonnet, GPT-4o, DeepSeek-R1, Gemini Pro), System Architects, Academic Reviewers.

---

## 1. Executive Summary & Problem Statement

### 1.1 The Fundamental Dilemma: Determinism vs. Generative Depth
In regulatory compliance automation (GDPR, CRA, NIS2, DORA, AI Act), pipelines face a classic optimization pathology:
1. **If over-deterministic:** The system generates rigid, hollow templates that fail to capture nuanced company architecture, real single-points-of-failure, or subtle regulatory tensions.
2. **If over-generative without constraints:** The LLM produces "lazy compliance" — generic, verbose prose (*"the enterprise should implement robust access controls..."*) that hallucinates article citations, omits 30% of mandatory clauses, and forgets the company's actual technical assets.
3. **If optimized for latency/tokens:** Engineers batch multiple subdomains into massive prompts (e.g., analyzing 4 subdomains across 5 regulations in a single 25k-token prompt). Models glide over details, miss specific systems, and collapse complex obligations into generic bullet points.

### 1.2 The Goal
Ensure that the generated compliance baseline (Phase 1: Docs 04 through 07b + Excel) achieves:
* **Zero legal omissions:** 100% clause coverage across all 38 subdomains.
* **Radical architectural grounding:** Every obligation and assessment is tied to specific company inventory items (`SYS-*`, `STORE-*`, `FLOW-*`, `AS-*`).
* **Zero ambiguity:** Direct citations of legal articles and explicit technical mechanisms.
* **Proportional rigor:** Evaluation depth scales dynamically with the enterprise's true risk surface (from Micro SaaS to Systemic Global Bank).

---

## 2. Proposed Architecture: The Two Pillars

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                               PILLAR 1: ADAPTIVE EXECUTION                       │
│                     (Execution Proportionality & Dynamic Budget)                 │
├────────────────────────────────────────┬─────────────────────────────────────────┤
│ • Micro Scale (Case 1 — TinyTask):     │ 14–16 LLM Calls (Batched Domain MAP)    │
│ • Large Scale (Case 2 — SecureBorder): │ 25–30 LLM Calls (Subdomain Split MAP)   │
│ • Systemic Bank (Case 3 — OmniBank):   │ 40–50 LLM Calls (Asset & Conflict Split)│
└────────────────────────────────────────┴─────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            PILLAR 2: ANTI-LAZY QUALITY GATES                     │
│                        (Deterministic Grounding Enforcement)                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│ [Gate 1: Asset Citation]   Must explicitly cite real IDs (SYS-*, STORE-*, FLOW-*) │
│ [Gate 2: Article Citation] Must cite specific articles (e.g., DORA Art. 9(2))   │
│ [Gate 3: Friction-Compromise] Multi-reg tensions must yield concrete trade-offs │
│ ──> Failure at any gate triggers immediate parser rejection & targeted retry    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Pillar 1: Complexity-Adaptive Execution Engine

Instead of a fixed call graph, the Orchestrator calculates the **Compliance Evaluation Surface**:
$$\text{Surface} = f(\text{Applicable Regs}, \text{Subdomains with } \ge 2 \text{ Regs}, \text{Critical Systems Count}, \text{Enterprise Tier})$$

### 3.1 Dynamic Call Allocation Across the 3 Cases

| Parameter | Case 1: TinyTask SaaS | Case 2: SecureBorder Sol. | Case 3: OmniBank Financial |
|---|---|---|---|
| **Enterprise Scale & Tier** | `MICRO` / 8 FTE / Tier `LOW` | `LARGE` / 150 FTE / Tier `HIGH` | `LARGE` / 5,000 FTE / Tier `HIGH` |
| **Applicable Regulations** | 2 (`GDPR`, `CRA`) | 4 (`AI_Act`, `CRA`, `GDPR`, `NIS2`) | 5 (`AI_Act`, `CRA`, `DORA`, `GDPR`, `NIS2`) |
| **Architecture Footprint** | 4 systems, 2 stores, 2 flows | 12 systems, 7 stores, 6 flows | 10 critical systems, 9 stores, 10 flows |
| **P1B (Applicability Rationale)** | 4 calls (2 regs × 2) | 8 calls (4 regs × 2) | 10 calls (5 regs × 2) |
| **MAP Stage Granularity** | 10 calls (Domain-level D-01..D-10) | 15–18 calls (Dense subdomains split) | 25–30 calls (Subdomain-level for D-01, D-02, D-04, D-09) |
| **Doc 04b/c (Asset Risk Analysis)** | 0 calls (Static suffices) | 2 calls (CRA edge & camera AI) | 4 calls (Mainframe CBS, Credit AI, HSM, SEPA) |
| **REDUCE (Synthesis & Tensions)** | 2 calls (Synthesis + Events) | 3 calls (+ Pairwise Tension) | 4 calls (+ DORA/NIS2/GDPR Tri-lemma) |
| **Total LLM Invocations** | **~16 calls** | **~28–31 calls** | **~43–48 calls** |

### 3.2 Concrete Execution Triggers

1. **Subdomain Split Trigger:**  
   If a subdomain has $\ge 3$ active regulations (e.g. `D-01.1` in Case 3 has GDPR + CRA + DORA + NIS2), it is decoupled from the broad `D-01` domain prompt and dispatched as an isolated, dedicated LLM call with a tightly focused context.
2. **Asset-Centric Trigger:**  
   If a system is tagged `criticality: critical` or `ai_annex_iii: true` (e.g., `SYS-CREDITAI` in OmniBank), the pipeline launches a dedicated architectural failure-mode analysis pass for Doc 04b.
3. **Pairwise Conflict Trigger:**  
   When the deterministic matrix flags a direct regulatory tension (e.g., GDPR Art. 5(1)(c) data minimization vs. NIS2 Art. 21(2)(e) & DORA Art. 12 logging requirements), an isolated conflict-resolution call is dispatched.

---

## 4. Pillar 2: Anti-Lazy Quality Gates (Grounding Verification)

To prevent the LLM from producing vacuous summaries, outputs must pass a deterministic verification layer with a **Default-FAIL** policy:

### Gate A: Real Asset Identifier Check
* **Rule:** The output section evaluating a subdomain or system MUST contain at least one valid system ID (`SYS-[A-Z0-9_-]+`), datastore ID (`STORE-[A-Z0-9_-]+`), or dataflow ID (`FLOW-[A-Z0-9_-]+`) present in that case's architecture inventory.
* **Failure Penalty:** Schema error / rejection with feedback: `REJECTED: Output is generic. Must reference specific architectural assets from inventory.`

### Gate B: Exact Legal Citation Check
* **Rule:** References to obligations must cite specific article/paragraph tokens (e.g., `GDPR Art. 32(1)(a)`, `DORA Art. 9(2)`). General references like *"according to GDPR"* or *"under European guidelines"* trigger an immediate rejection.

### Gate C: Tripartite Tension Resolution Schema
When evaluating overlapping or conflicting regulations, the model is strictly forbidden from stating *"the company must balance both"*. It must provide a structured resolution block:
```markdown
### Tension Resolution: [REG_A] vs [REG_B]
- Conflict Point: [Specific mandate friction]
- Primary Risk: [Legal or operational consequence of prioritizing one over the other]
- Technical Compromise Control: [Concrete implementation, e.g., segregated cryptographic key management with differential retention]
```

---

## 5. Model Assessment: What Should Live in Phase 1 vs. Phase 2?

As an AI coding assistant evaluating this architecture, here is my direct recommendation on boundaries:

### What Belongs in Phase 1 (This Repository):
1. **The Legal Grounding & Applicability Foundation:** Absolute determinism on the 331 clauses, 106 NIST CSF subcategories, and 5 regulation roles.
2. **Dynamic Context Ingestion:** Populating and validating the complete 9-document suite (Docs 04, 04a, 04b, 04c, 04d, 05, 06, 07, 07b).
3. **Subdomain-Level Overlap & Asset Mapping:** Ensuring that for every active subdomain, we know *which* systems and *which* clauses collide.
4. **Identification of Tensions:** Registering all active conflict pairs between regulations.

### What Should Be Handled in Phase 2 (`aegis-phase2`):
1. **Obligation Derivation (Doc 08):** Synthesizing the 15-field rich obligation detail cards (`OBL-D-XX.X-NNN`).
2. **Strategic Tensions Report (Doc 09):** The full multi-paragraph root-cause analysis and business trade-off documentation.
3. **Privacy & Security Objectives (Docs 10 & 10b):** Deriving `PG-*` and `SG-*` goals mapped to NIST CSF 2.0.
4. **Rules Catalog (Docs 11, 12, 13):** Emitting the final 46+ prescriptive rules (`CR-*` and `BPR-*`) and the 14-sheet Excel catalog.

**Key Distinction:** Phase 1 establishes the **grounded fact base and collision map**; Phase 2 performs the **normative and prescriptive rule engineering**.

---

## 6. Reviewer Guide: Questions for Peer Models

If you are a peer LLM reviewing this proposal, please evaluate and critique the following questions:

1. **Scalability vs. Latency Trade-Off:**  
   *Does scaling from 16 to 48 calls for large cases (OmniBank) introduce unacceptable queue delays on an HPC cluster (SLURM A100), or is the resulting analytical depth worth the execution time?*
2. **Quality Gate Fragility:**  
   *Is the deterministic Asset Identifier Gate (requiring `SYS-*` tokens) prone to false rejections when an LLM writes valid governance prose that applies to the whole enterprise rather than a single technical system? How can we make it robust?*
3. **Granularity Threshold:**  
   *Is the split trigger threshold ($\ge 3$ regulations in a subdomain) optimal, or should subdomains with high normative intensity ($NI \ge 2.0$) also trigger isolated calls regardless of regulation count?*
4. **Failure Recovery:**  
   *If 2 out of 45 calls fail during a large OmniBank run, what is the best partial-recovery strategy to avoid re-running the entire pipeline?*

---

## 7. Review Findings (ZCode, 2026-09-03)

Grounded review against the code on `feature/aegis-p1-corr-112-provenance-gate-scale`. The proposal's direction (Pillar 1 + Pillar 2) is endorsed; the findings below are blind spots to fix before implementation. The full acceptance framework is [`OBJECTIVES_CONTRACT.md`](OBJECTIVES_CONTRACT.md) (`AEGIS-DOC-OBJ-001`).

### 7.1 Blind Spot 1 — Architecture assets never reach the LLM (Gate A is unenforceable as written)

MAP context assembly (`src/aegis_phase1/v2/domain/inputs.py`) builds closed lists of subdomain IDs, regulation IDs, and article IDs (`authoritative_ids`, CORR-112 F2) — but **no architecture assets** (`SYS-*`, `STORE-*`, `FLOW-*`). Assets exist only in the deterministic renderers (`doc_04a.py`, `doc_04b.py`). Consequently:

- "Radical architectural grounding" (§1.2) is structurally impossible today — not a model-quality issue: the model has never seen the inventory.
- Gate A would reject models for failing to cite assets they were never given.

**Fix:** per-domain closed asset lists in MAP context + gate check **citation ⊆ list provided to that call**. The ⊆-check is the strong form: because the pipeline knows exactly what it handed each call, decorative citation of out-of-scope assets becomes mechanically detectable. Highest-leverage change in this review, at zero extra LLM calls.

### 7.2 Blind Spot 2 — Conflicts are detected, not resolved (Gate C lacks its calls)

The deterministic conflicts matrix (`run_sync`) flags `INDETERMINATE` pairs as "Flag for Phase 2 / human review"; conflict-resolution prose exists only inside the single global P1C-03 synthesis call. The proposal's pairwise tension calls (§3.2, trigger 3) are the right fix and align with the design law *scale coverage, not task complexity* — but they are load-bearing for Gate C, not an optional refinement.

### 7.3 Gates A/B as written cause false rejections — make them per-section

Blanket gates (any section must cite `SYS-*`; "according to GDPR" rejects anywhere) penalize legitimate enterprise-wide governance prose — the proposal's own reviewer question 2 concedes this. The mechanism to fix it already exists: the provenance section tags (CORR-112, `v2/output/provenance.py`). Gates should be **per-section**: obligation sections require article tokens; narrative sections do not.

### 7.4 Underestimated risks of 43–48 calls

1. **Synthesis scaling:** REDUCE feeds ALL lanes' activations into ONE global P1C-03 call with no truncation (CORR-102 fails loud on cap overflow). More MAP calls → larger aggregate → either `PromptTooLargeError` or quality dilution. Needs hierarchical synthesis (per-cluster → global) or deterministic pre-reduction.
2. **Partial recovery:** at this call count, partial failures are certain on a cluster; per-call checkpoint/resume is required (the proposal's question 4), otherwise one failed call loses the run.
3. **Gate mode:** `AEGIS_GATE_MODE` defaults to `warn`. Validation runs must use `hard`, otherwise Pillar 2 exists only on paper.

### 7.5 Ambiguity analysis is missing — and it is grounding gold

Preproc ambiguity pairs are injected into MAP inputs as data, but no spec references them (zero mentions across the 5 specs) and no gate checks them. Documented ambiguities are curated anchors: the LLM should emit a per-pair company-specific disposition (`applicable_reading` + `anchors[]` + `disposition ∈ {RESOLVED_BY_FACT, RESOLVED_BY_TIER, NEEDS_HUMAN}`), mirroring the CONDITIONAL-activation pattern without violating the NO-re-classification invariant. Full mechanism: `OBJECTIVES_CONTRACT.md` §4.

### 7.6 Answers to the reviewer questions (§6 of this proposal)

1. **Scalability vs latency:** more calls are justified only if each new call has a narrower closed context and its own gate; otherwise they add failure surface without verification. The cheap win is not a call — it is assets in MAP context (§7.1).
2. **Gate A fragility:** real; fix via per-section gates + citation ⊆ provided-context (§7.1, §7.3).
3. **Granularity threshold:** regulation-count triggers are fine; normative intensity can be added, but the trigger table must stay deterministic and testable — drop the unspecified `Surface = f(...)` formula in §3 in favor of the explicit trigger table.
4. **Failure recovery:** per-call checkpointing of LangGraph state + resume from last good call; degraded sections render visibly (fail-loud), never silently dropped.

---
