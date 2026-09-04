# KG Implementation Contract — AEGIS-KG Phase 1

**Document ID:** `AEGIS-DOC-KG-CONTRACT-001`
**Status:** DRAFT v0 — pending curation by Paulo (P7)
**Date:** 2026-09-03
**Source of Truth:** [`NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md`](NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md) (`AEGIS-DOC-NEO4J-ONTOLOGY-002` v3)
**Companion:** [`OBJECTIVES_CONTRACT.md`](OBJECTIVES_CONTRACT.md) (`AEGIS-DOC-OBJ-001`)
**Scope:** Definition of "done" for the Phase 1 KG ETL — the operational contract for `scripts/kg_etl/` work that does not yet exist.

---

## 1. Purpose

This contract exists to answer the same question the [`OBJECTIVES_CONTRACT.md`](OBJECTIVES_CONTRACT.md) answers for the pipeline, applied to the Knowledge Graph:

**When is the KG ETL "done"? What invariants must hold before any change is accepted?**

The model is intentionally identical to the OBJ contract:
1. Every KG objective is an **acceptance criterion with a stated measurement**, not an aspiration.
2. The list is **versioned and open**: objectives may be ADDED by P7; none may be removed or weakened without an explicit human decision recorded in the change log.
3. Any proposed change **must declare which criteria it could degrade** and re-run the full acceptance loop (§4) before acceptance.

This contract is the **operational counterpart** of the spec v3: the spec defines *what* the graph contains; this contract defines *when the implementation of the load is correct*.

---

## 2. The 13 KG Objectives

Mechanism legend: **[G]** deterministic gate (~zero cost, runs every load) · **[J]** sampled judge (verbose criteria) · **[H]** human arbiter (P7).

Status reflects the code as of 2026-09-03: **0/13 IMPLEMENTED** — `scripts/kg_etl/` does not exist yet (verified). Every objective below is a gap.

| ID | Objective | Measured by | Mechanism | Status |
|----|-----------|-------------|-----------|--------|
| **KG-01** | **Reproducibility from sources** — the graph must be fully reconstructible from `cases/*/input/`, `preproc_out/`, and `data/*` alone. No manual edits survive a `clean + load`. | `clean_and_load()` test: drop database, reload, byte-equal `(:GraphMeta)` fingerprint + same per-label counts. | [G] | **MISSING** |
| **KG-02** | **Catalog fingerprint match** — `(:GraphMeta {key: 'preproc_fingerprint'}).value` equals `sha256(preproc_out/)`; loading with a stale preproc fails. | ETL computes fingerprint before load, asserts match against expected. | [G] | **MISSING** |
| **KG-03** | **Count invariants** — load produces exactly 6 CSF Functions, 34 CSF Categories, 106 CSF Subcategories, 5 Regulations, 331 RegulatoryClauses, 10 SecurityControlDomains, 38 SubDomains, 196 RegulatoryPairs, 9 RegulatoryRoles. Per case: Systems/Stores/Flows counts equal YAML source. | PHASE 4 VERIFY block (spec v3 §6.4) — fail-loud on mismatch. | [G] | **MISSING** |
| **KG-04** | **Orphan-free** — every FK (end node of an edge) has a target node. | Post-load Cypher: `MATCH (n)-[r]->(m) WHERE m IS NULL RETURN count(r) AS orphans` must return 0. | [G] | **MISSING** |
| **KG-05** | **Case isolation** — `Run`-derived nodes (`SubDomainActivation`, `PairActivation`, `AmbiguityDisposition`, `Gate`, `ClauseActivation`, `ProportionalityEntry`) have `run_id` non-null; case-derived nodes have `case_id` non-null. | Post-load invariant query (spec v3 §6.4 isolation check). | [G] | **MISSING** — Rule 0 linter also MISSING (spec v3 §5 acknowledged convention only). |
| **KG-06** | **MERGE collision safety** — two runs of the same case with different models produce two distinct sets of run-derived nodes; nothing is overwritten. | Integration test: run 2 models on case3, assert `count(:SubDomainActivation) = 2 * 38`. | [G] | **MISSING** — depends on `(:Run)` keying (spec v3 §3.1), implemented in code only when ETL lands. |
| **KG-07** | **Provenance coverage** — every run-derived node carries `origin: "deterministic" \| "llm:<spec_id>"`; `(:Run)` nodes carry `spec_versions` JSON. | Post-load: `MATCH (n) WHERE (n:SubDomainActivation OR n:PairActivation OR n:AmbiguityDisposition OR n:Gate) AND n.origin IS NULL RETURN count(n)` = 0. | [G] | **MISSING** |
| **KG-08** | **Run metadata capture** — every ETL invocation produces a `RunMetadata` JSON next to `(:Run)` (or wired through the existing `src/aegis_phase1/runs/metadata.py:RunMetadata` from OBJ-14). | Asserts `run_id`, `model`, `provider`, `quantization`, `gate_mode` present and `gate_mode ∈ {"warn","hard"}` (closed vocabulary, OBJ-14 contract). | [G] | **MISSING** |
| **KG-09** | **Closed-set fidelity** — IDs cited in nodes (subdomain, regulation, article, CSF, asset) belong to their respective catalogues. | Cypher per label: for each `c`-style property, intersect with the canonical set; report and fail any `c ∉ catalog`. Reuses the `ref_gate.py` vocabulary from OBJ-09. | [G] | **MISSING** |
| **KG-10** | **Deterministic IN_SCOPE_OF** — the `(:System)-[:IN_SCOPE_OF]->(:SubDomain)` edge carries `rule_id` + `basis`; one rule = one fixture = one test. | `data/in_scope_of_rules.yaml` exists, is schema-validated, has ≥1 fixture per rule in `tests/unit/v2/test_in_scope_of_rules.py`. | [G] | **MISSING** — `data/in_scope_of_rules.yaml` does not exist yet. |
| **KG-11** | **Ambiguity disposition substrate** — `:AmbiguityDisposition` node exists with closed-vocabulary `disposition ∈ {RESOLVED_BY_FACT, RESOLVED_BY_TIER, NEEDS_HUMAN}`; coverage on every CONDITIONAL pair in scope. | ETL emits one row per CONDITIONAL pair in `(reg_a, reg_b, case)` intersection; gate validates vocabulary + coverage. | [G] | **MISSING** — **depends on Phase 1.2** (Methodology-main specs v1.2). Until bumped, the LLM does not emit dispositions; the substrate exists but is empty. |
| **KG-12** | **No ETL on cluster runtime** — the pipeline `src/aegis_phase1/v2/` does **NOT** import `neo4j` or any `scripts/kg_etl/` module. Cluster runs (Deucalion) need no Neo4j instance. | Static test: `grep -r "import neo4j\|from neo4j\|kg_etl" src/aegis_phase1/v2/` returns no hits. | [G] | **MISSING** — verified absent today by grep, but no automated test. |
| **KG-13** | **Drift detection** — every load records `(:GraphMeta {key: 'preproc_fingerprint', value})` and `(:GraphMeta {key: 'etl_version', value})`; subsequent loads refuse to overwrite if the fingerprint regresses. | ETL step: `MATCH (g:GraphMeta {key: 'preproc_fingerprint'})` — if value differs from incoming, hard-fail with explicit error. | [G] | **MISSING** |

### 2.1 Verification of current state (2026-09-03)

All 13 objectives are MISSING because `scripts/kg_etl/` does not exist. Verified by `find src scripts -name 'kg_etl*' -o -name 'kg_load*' 2>/dev/null` returning empty. Defaults exist (`src/aegis_phase1/config/defaults.py` lines 14-19: ports 7688/7475, no driver code).

---

## 3. Priority Order (PROPOSED — pending P7 confirmation)

```
KG-12 > KG-01 > KG-03 > KG-04 > KG-06 > KG-02 > KG-07 > KG-08 > KG-10 > KG-13 > KG-09 > KG-11 > KG-05
```

**Why this order:**
- **KG-12 (no-runtime)** is the binding decision from spec v3 §1.3 — must be locked first, otherwise ETL code can drift into a runtime dependency.
- **KG-01 + KG-03** are the substrate of any correctness argument: if you can't reproduce the graph from sources or count what's in it, nothing else can be measured.
- **KG-04 + KG-06** are integrity invariants; cheap, mechanical, fail-loud.
- **KG-02 + KG-07 + KG-08 + KG-10** are quality-of-implementation — fingerprint, provenance, metadata, versioned rules.
- **KG-09 + KG-11 + KG-13** are downstream verifications; KG-11 has an explicit Phase 1.2 dependency, so lower priority is honest.
- **KG-05** (case isolation) is partly enforced by KG-06 (run keying); the explicit invariant + linter is the polish, not the foundation.

When objectives collide, the higher one wins **and the trade-off is visible** — same rule as OBJ §3.

---

## 4. Evaluation & Optimization Loop

Mirrors [`OBJECTIVES_CONTRACT.md`](OBJECTIVES_CONTRACT.md) §5 exactly.

Three verification layers:
1. **Deterministic gates [G]** run after every ETL load. Entry point: `scripts/kg_etl/verify.py` (does not exist yet).
2. **Judge [J]** is reserved for objectives where the answer is not a closed-set check (currently none — all 13 are [G] in this v0; [J]/[H] are placeholders for future objectives).
3. **Human [H]** = P7 decides priorities, KG-11 sequencing (Phase 1.2 dependency), and changes to this contract.

**No-regression rule:** a change to any ETL script is accepted only if **no KG criterion regresses** vs the baseline at `docs/KG_BASELINE.json` (to be captured when KG-01 lands). Same rule as OBJ §5 — averages never justify per-objective regression.

**Scorecard (planned):** `scripts/kg_etl/scorecard.py` (does not exist yet) parses this contract (markdown table), runs the [G] cells, emits per-objective status in the same shape as `scripts/eval/objectives_contract.py`. Honest `MISSING_GATE` / `JUDGE_NOT_WIRED` for unimplemented cells — never silent pass.

---

## 5. Pre-conditions and Dependencies

This section is the **operational counterpart of spec v3** — what has to land before what.

| Dependency | Blocks | Source of truth |
|------------|--------|-----------------|
| Phase 1.2 (Methodology-main specs v1.2) | KG-11 (AmbiguityDisposition emissions) | `Methodology-main/00_METHODOLOGY/PROMPTS/` v1.2.0 changelog (separate repo; AGENTS.md §6 = "Ask first"). |
| `data/in_scope_of_rules.yaml` (schema + fixtures) | KG-10 (deterministic IN_SCOPE_OF) | New file; owner TBD (see §6 Q5). |
| Neo4j instance reachable from where ETL runs | KG-01 (reproducibility test), KG-06 (multi-model test) | Spec v3 §1.2 — port 7688/7475 (NOT 7687/7474). Instance availability in Deucalion: TBD (see §6 Q4). |
| `src/aegis_phase1/runs/metadata.py:RunMetadata` (already exists, OBJ-14) | KG-08 (metadata capture) | Branch `feature/aegis-p1-corr-112-provenance-gate-scale`, commit `45b11d4`. Reuse, do not duplicate. |
| `scripts/eval/objectives_contract.py` patterns | KG scorecard | Reference for parsing convention and dataclass shape — do not couple the two, mirror. |
| RefGate vocabulary (`ref_gate.py`) | KG-09 (closed-set fidelity) | Same vocabulary reused; do not duplicate enums. |

**Universal rule (mirrors OBJ §5 + spec v3 §6.5):** any new rule (asset filter, DataFlow derived, IN_SCOPE_OF) is one rule = one fixture = one test. No "we'll add tests later".

---

## 6. Open Questions for P7

1. **Confirm or adjust the priority order** (§3).
2. **KG-11 sequencing:** confirm KG-11 ships as gate-stub-only until Phase 1.2 lands (recommended), or implement what can be implemented now (coverage check on empty dispositions = `MISSING_GATE`).
3. **v0 scope:** accept all 13 objectives, or defer any (KG-09, KG-13 are the easiest to defer; KG-12 is the most important to land first)?
4. **Neo4j in Deucalion:** do we have a running instance (port 7688/7475) reachable from the workstation? Affects KG-01 (cannot test reproducibility without a DB) and KG-06 (cannot test multi-model without a DB).
5. **Owner of `data/in_scope_of_rules.yaml`** (KG-10 dependency): recommended owner is whoever owns the OBJ-01 "assets in MAP context" heuristic v1, since the rule set is the next iteration of that same filter.

---

## 7. Implementation Status (2026-09-03 — placeholder)

| Status | Count | Objectives |
|--------|-------|------------|
| IMPLEMENTED | 0 | — |
| PARTIAL | 0 | — |
| MISSING | 13 | All |
| DEFERRED (depends on Phase 1.2) | 1 | KG-11 |

No `scripts/kg_etl/` exists. Defaults for Neo4j ports live in `src/aegis_phase1/config/defaults.py:14-19`. Spec v3 is the binding data model.

---

## 8. Change Log

- **v0 (2026-09-03):** initial draft. 13 objectives operationalising the spec v3 into acceptance criteria. All MISSING by design — this contract ships before the ETL so the ETL has a definition of done.
