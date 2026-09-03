# Objectives Contract — AEGIS Phase 1 Pipeline

**Document ID:** `AEGIS-DOC-OBJ-001`
**Status:** DRAFT v0 — pending curation by Paulo (P7)
**Date:** 2026-09-03
**Source:** Working session reviewing [`PROPOSAL_ADAPTIVE_EXECUTION_AND_QUALITY_GATES.md`](PROPOSAL_ADAPTIVE_EXECUTION_AND_QUALITY_GATES.md) (`AEGIS-DOC-PROP-001`); findings recorded in its §7.
**Scope:** Definition of "done" for Phase 1 outputs (Docs 04–07b + Excel) and the acceptance rule for ANY change to this repository (prompt, gate, spec, routing, renderer, provider).

---

## 1. Purpose

This contract exists to answer a specific failure mode: **when a goal becomes an instruction to an optimizer, the optimizer satisfies the instruction and loses the goal** (Goodhart's law). This applies to the LLMs inside the pipeline and to the AI agents developing it.

Therefore:

1. Every objective below is an **acceptance criterion with a stated measurement**, not an aspiration.
2. The list is **versioned and open**: objectives may be ADDED by the human arbiter (P7); none may be removed or weakened without an explicit human decision recorded in the change log.
3. Any proposed change **must declare which criteria it could degrade** and re-run the full acceptance loop (§5) before acceptance.

## 2. The 14 Objectives

Mechanism legend: **[G]** deterministic gate (runs every run, ~zero cost) · **[J]** sampled judge rubric (verbose criteria) · **[H]** human arbiter (P7).
Status reflects the code as of 2026-09-03 on `feature/aegis-p1-corr-112-provenance-gate-scale`.

### 2.1 Original objectives (defined by Paulo, 2026-09-03)

| ID | Objective | Measured by | Mechanism | Status |
|----|-----------|-------------|-----------|--------|
| OBJ-01 | **Company grounding** — obligations/assessments tied to real inventory (`SYS-*`, `STORE-*`, `FLOW-*`, `AS-*`) | Share of LLM sections citing ≥1 asset; gate: citations ⊆ closed asset list of that call | [G] | **MISSING** — assets never enter MAP context (`v2/domain/inputs.py` builds closed subdomain/reg/article ID lists only; assets live solely in deterministic renderers doc_04a/04b). PROP-001 Gate A is unenforceable as written. |
| OBJ-02 | **No omissions** — every applicable clause/subdomain appears in outputs | Set-difference: emitted IDs vs preproc catalogue per case | [G] | **PARTIAL** — deterministic renderers emit full catalogues; LLM-authored sections have no coverage gate. |
| OBJ-03 | **Zero output ambiguity** — obligation statements cite article tokens from the closed catalogue; vague phrasing rejected | Per-section regex: article tokens ∈ catalogue; banned-vague-phrase list | [G] | **PARTIAL** — `ref_gate.py` checks placeholder markers, invented statistics, verdict vocab; no per-section article-token requirement yet. |
| OBJ-04 | **Controls** — control references restricted to the 106 NIST CSF 2.0 subcategories | CSF token ⊆ closed catalogue | [G] | **PARTIAL** — deterministic rendering from preproc is safe; LLM-side CSF mentions unchecked. |
| OBJ-05 | **Proportionality / adequacy** — depth scales with enterprise tier and role | Deterministic tier/role matrix + judge on adequacy of depth | [G+J] | **EXISTS** — deterministic proportionality in REDUCE; Doc 04b dynamic maturity (CORR-109). |
| OBJ-06 | **Tensions resolved** — every flagged conflict either resolved with an anchored trade-off or explicitly escalated | Per-pair structured resolution block present; disposition ∈ closed vocabulary | [G+J] | **MISSING (resolution half)** — deterministic matrix flags conflicts; `INDETERMINATE` → "Flag for Phase 2 / human review" (`phase1_executor.py` run_sync); resolution prose exists only inside the single global P1C-03 synthesis call. |
| OBJ-07 | **Business alignment** — objectives/assessments reference the case's business objectives | Reference gate against closed business-objective anchor list from case profile | [G] | **MISSING** — business objectives are not a gated anchor set. |

### 2.2 Added objectives (ZCode review, 2026-09-03)

| ID | Objective | Measured by | Mechanism | Status |
|----|-----------|-------------|-----------|--------|
| OBJ-08 | **Traceability** — every output section carries provenance tags (source clause / asset / LLM judgment) | Coverage: % sections with valid section tags | [G] | **PARTIAL** — provenance registry + section tags exist (`v2/output/provenance.py`, CORR-112); full 9-doc coverage not enforced. |
| OBJ-09 | **No fabrication** — zero invented IDs, statistics, articles | Invented-stat + closed-ID checks | [G] | **PARTIAL** — `ref_gate.py` covers invented statistics + catalog IDs; extend to all closed sets (incl. assets, OBJ-01). |
| OBJ-10 | **Internal consistency** — LLM content must not contradict deterministic sections across the 9 docs | Cross-doc contradiction check where both sides are structured | [G+J] | **MISSING**. |
| OBJ-11 | **Interpretive transparency** — every interpretive choice recorded with rationale; documented ambiguities get explicit dispositions | P1B rationale coverage + ambiguity disposition coverage (§4) | [G+J] | **PARTIAL** — P1B-01/02 produce interpretations/rationale; ambiguity pairs are injected into MAP inputs as **data** but no spec mentions them (zero "ambiguity" references across the 5 specs) — the model may ignore them and no gate notices. |
| OBJ-12 | **Fail-loud degradation** — a failed call degrades its section visibly; never silent drop, never fabricated completeness | Failed-call sections render an explicit degradation notice | [G] | **PARTIAL** — CORR-102 token cap fails loud; call-level failure → visible doc-section marking not guaranteed. |
| OBJ-13 | **Phase-2 actionability** — every escalated conflict carries owner/status/anchors sufficient to act later | Escalated rows have non-empty action context | [G] | **MISSING** — `INDETERMINATE` rows carry no resolution context. |
| OBJ-14 | **Reproducibility / comparability** — same input + model + specs → comparable outputs across runs and models | Run metadata completeness (specs version, provider, sampling params); scorecard cross-run stability | [H] | **PARTIAL** — runs organized + quantization sidecars (CORR-111); no enforced sampling/version pinning contract. |

## 3. Priority Order (PROPOSED — pending P7 confirmation)

```
coverage (OBJ-02) > company grounding (OBJ-01) > citation precision (OBJ-03) > depth
```

When objectives collide (e.g., full clause coverage vs proportional depth on a MICRO case), the higher objective wins **and the trade-off must be visible in the document** (fail-loud note, OBJ-12) — never resolved silently. Without an explicit order, an optimizer resolves objective conflicts silently, which is precisely the failure this contract exists to prevent.

## 4. Ambiguity-as-Anchor Mechanism (under OBJ-11)

**Problem:** preproc ambiguity pairs are injected into MAP context filtered per subdomain (`v2/domain/inputs.py`) but are contractually inert — no spec references them, no gate checks them.

**Mechanism** (mirrors the CONDITIONAL-activation pattern of P1C-LLM-01; preserves the NO-re-classification invariant — Layer 0 stays read-only):

- **Input:** closed list of documented ambiguity pairs per lane/domain.
- **LLM emits per pair:** `ambiguity_id`, `applicable_reading` (which documented reading applies to THIS company), `anchors[]` (article / tier / asset / business objective — IDs from closed lists only), `consequence`, `disposition ∈ {RESOLVED_BY_FACT, RESOLVED_BY_TIER, NEEDS_HUMAN}`.
- **Gate [G]:** coverage (every pair in context has exactly one disposition); disposition vocabulary closed; anchors ⊆ closed lists.
- **Judge [J]:** is the chosen reading defensible given `company_facts`?
- **Human [H]:** `NEEDS_HUMAN` rows surface in the doc with full context (feeds OBJ-13).

The same ambiguity may legitimately resolve differently for TinyTask vs OmniBank — that company-specific anchoring is exactly the grounding value the LLM adds. Escalation is a valid outcome; silent absorption is not.

**Vehicle:** prompt specs v1.2 (deliberate, versioned bump — as CORR-112 did v1.0→v1.1 in `Methodology-main/00_METHODOLOGY/PROMPTS/`).

## 5. Evaluation & Optimization Loop

Three verification layers plus one acceptance rule:

1. **Deterministic gates [G]** run on every pipeline run; validation runs use `AEGIS_GATE_MODE=hard` (the default `warn` mode is for interactive development only).
2. **Judge [J]** — the 5-layer scorecard, sampled per case × model, with verbose criteria per cell (what / how / measured / why; bare PASS/FAIL is unacceptable).
3. **Human [H]** (P7) decides priorities, trade-offs, and changes to this contract.

**No-regression rule:** a change is accepted only if **no criterion regresses on all 3 cases**. A rising average never justifies a per-objective regression — averaging is where the objectives that matter die. Change proposals must declare up front which criteria they could degrade.

**Role separation:** whoever optimizes (agent or model) is never the sole grader. The pipeline equivalent of this contract is: gates check presence and closed-set membership; the judge checks correctness; the human checks priority.

## 6. Open Questions for Paulo (P7)

1. Confirm or adjust the priority order (§3).
2. v0 scope: accept all 14 objectives, or defer any (e.g., OBJ-14)?
3. Switch validation runs to `AEGIS_GATE_MODE=hard` now, before additional LLM calls are added?
4. Ambiguity mechanism vehicle: extend P1B-02 vs a dedicated per-pair dispositions pass (recommendation: dedicated pass — mirrors the activation pattern and keeps P1B per-regulation).

## Change Log

- **v0 (2026-09-03):** initial contract from the review session on PROP-001. 7 original objectives (Paulo) + 7 added (review); priority order proposed; ambiguity-as-anchor mechanism specified.
