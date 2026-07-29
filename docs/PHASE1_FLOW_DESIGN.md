---
document_id: AEGIS-P1-DESIGN
title: Phase 1 — Flow Design & Decision Map
phase: 1 (design)
version: 0.1 (draft)
created: 2026-07-27
updated: 2026-07-27
author: AEGIS Phase 1 design session
status: DRAFT — under discussion
related_documents:
  - ../../Methodology-main/00_METHODOLOGY/diagrams/fluxdiagram/phase1/phase1_contextual_definition.md
  - ../../Methodology-main/00_METHODOLOGY/diagrams/Class_Models/phase0_preprocessing.md
  - ../../Methodology-main/00_METHODOLOGY/PHASE1_STRATEGY.md
  - ./LLM_ARCHITECTURE_DECISION.md
---

# Phase 1 — Flow Design & Decision Map

> **Purpose.** This document captures the **high-level design** of the Phase 1
> pipeline: the decisions it must take, the context each decision requires,
> the dependencies between decisions, and the resulting documents. It is the
> single reference for "what Phase 1 does, end-to-end".
>
> **Audience.** Architect + implementer of the v2 orchestrator.
>
> **Status.** Draft — several decisions are firm, several are pending. Each
> block is tagged with its current status.

---

## Table of contents

1. [Principles (firm)](#1-principles-firm)
2. [Phase 0 → Phase 1 contract (consolidated)](#2-phase-0--phase-1-contract-consolidated)
3. [Decision map (D1–D7)](#3-decision-map-d1d7)
4. [Part A — Decisions D1–D7 (detailed)](#part-a--decisions-d1d7-detailed)
5. [Part B — Document structure (per output)](#part-b--document-structure-per-output)
6. [Part C — Taxonomy decision context](#part-c--taxonomy-decision-context)
7. [Part D — Recommendation on taxonomy](#part-d--recommendation-on-taxonomy)
8. [Critical data findings](#5-critical-data-findings)
9. [Open questions](#6-open-questions)
10. [LLM reduction: 5 → 2](#7-llm-reduction-5--2)

---

## 1. Principles (firm)

These principles were agreed during the design session and frame every
subsequent decision.

| # | Principle | Implication |
|---|---|---|
| **P1** | **Boundary**: Phase 0 = regulation (case-agnostic); Phase 1 = company (case-specific). | All regulatory facts are frozen in Phase 0; Phase 1 never regenerates them. |
| **P2** | **Role of LLMs**: FILTER + CONTEXTUALIZE. | LLMs do **not** discover regulatory facts; they filter (from Phase 0 catalog) and contextualize (for this company). |
| **P3** | **Tier is input** (not derived). | Comes from `case.yaml`; Phase 1 only justifies it. |
| **P4** | **5 outputs**: 04, 05, 06 (Excel), 07, 07b. | All Markdown, except Doc 06 which is **also** Excel. |
| **P5** | **Excel mandatory** for Doc 06. | Not optional. |
| **P6** | **Native/Inherited by clause is REMOVED** from Phase 1. | Returns only when Phase 0 populates `obligated_party` in clauses. |
| **P7** | **5 → 2 LLMs**: only RATIONALE + STRATEGIC remain as LLMs. | The other 3 are replaced by deterministic predicate evaluation against `company_facts`. |

---

## 2. Phase 0 → Phase 1 contract (consolidated)

What Phase 0 delivers (frozen), and what Phase 1 does with it.

| Category | Phase 0 delivers | Phase 1 does |
|---|---|---|
| **Regulatory facts** (regs, clauses, SRs, SOs, NIST CSF) | Universal catalog (498 clauses, 282 SRs, 189 SOs, 106 CSF subcats, 38 sub-domains) | **Filter** by applicable regs |
| **Pair classification** (CRDA + CRDA-deep OJ-verified) | Pairwise analysis complete with `downstream_implication` per pair | **Instantiate** against company facts — does NOT reclassify |
| **Tipo 2/3 nuances** (Berry Lens catalogs) | OJ-anchored, with `activation_predicate` per entry | **Evaluate predicate** against `company_facts` (deterministic) |
| **Scope conditional** (`scope_disjoint_test.verdict = Conditional`) | Identifies WHERE tension is possible | **Evaluate predicate** + generate concrete compound event if activated |
| **Event templates** (8 templates with `trigger_predicates`) | Compound event archetypes | **Evaluate triggers** + instantiate events for this company |
| **Tier** | — | **Input** (from `case.yaml`, justified not derived) |
| **HSO_HL + HSO_PerReg** (38 + ~150 objectives) | Universal objectives | **Filter PerReg by reg**, keep all 38 HL, contextualize in D4 |

### 4 predicate catalogs (executable, in `Methodology-main/00_METHODOLOGY/PROMPTS/catalogs/`)

These YAML catalogs contain Python-evaluable `activation_predicate` strings.
Phase 1 evaluates them against `company_facts` deterministically.

| Catalog | Path | Entries | Used by |
|---|---|---|---|
| `tipo2_interpretations.yaml` | `PROMPTS/catalogs/` | 8 | D3 (interpretation nuances) |
| `tipo3_derogations.yaml` | `PROMPTS/catalogs/` | 6 | D3 (derogation exceptions) |
| `scope_overlap_predicates.yaml` | `PROMPTS/catalogs/` | varies | D3 (pair scope evaluation) |
| `event_templates.yaml` | `PROMPTS/catalogs/` | 8 | D5 (compound event triggers) |

---

## 3. Decision map (D1–D7)

```
case.yaml ──┐
            ├──→ D1 (intake structural, deterministic)
preproc_out─┤    ├─ D1.1 YAML load (multiple roles supported)
(tier input)┘    ├─ D1.2 confidence check
                 ├─ D1.3 block activation B1-B8
                 ├─ D1.5 tier justification
                 └─ D1.6 coherence
                       │
                       ├──→ D2 (capability assessment, deterministic)
                       │    IR-12 × applicable regs × criticality
                       │    [matrix IR→regs: TEMP CONST in P1, then P0]
                       │
                       ├──→ D3 (catalog filtering + predicate eval, deterministic)
                       │    clauses + SRs + HSO + pairs + nuances + ...
                       │    Uses company_facts (derived view from YAMLs)
                       │    + PREDICATE EVALUATION of 4 YAML catalogs
                       │
                       ├──→ D4 (P1B-RATIONALE merged, LLM per_regulation)
                       ├──→ D5 (compound events, LLM or deterministic — TBD)
                       ├──→ D6 (P1C-STRATEGIC synthesis, LLM global)
                       └──→ D7 (Track B / proportionality, deterministic)
```

### Decision → Output mapping

| Decision | Doc(s) it feeds |
|---|---|
| D1 | 04, 05, 06 |
| D2 | 04 (§9 Capability) |
| D3 | 05 (per-reg), 06 (all sheets), 07 (§3, §4) |
| D4 | 05 (§3, §7, §8), 07 (§6 preliminar) |
| D5 | 07 (§5 cross-regulation) |
| D6 | 07 (§6 strategic, §7 gaps, §8 scope declaration) |
| D7 | 07b (entire), 07 (§9 Track B summary) |

---

## Part A — Decisions D1–D7 (detailed)

### D1 — Intake structural (100% deterministic)

**Status**: firm.

**Inputs** (YAML files of the case):

```
input/company/
  ├── classification.yaml             → company facts (name, sector, size, ...)
  ├── regulatory_classification.yaml  → 5 enum classifications per reg
  ├── role_matrix.yaml                → roles per reg (MUST support multiple roles)
  ├── implementation_readiness.yaml   → IR-01..IR-12 status
  ├── stakeholders.yaml
  └── business_goals.yaml
input/regulatory/
  ├── applicability.yaml              → applicable_regs + rationale
  └── interactions.yaml               → regulatory interactions
input/architecture/
  ├── auth_systems.yaml
  ├── cloud_services.yaml
  ├── data_flows.yaml
  ├── data_stores.yaml
  └── systems.yaml
```

**Sub-decisions**:

| ID | Action | Rules | Output |
|---|---|---|---|
| **D1.1a** | Load 9 YAMLs into a `CaseInput` Pydantic model | Schema-validated | `case_input: CaseInput` |
| **D1.1b** | Build `company_facts` (derived view) | Projections + simple derivations (table below) | `company_facts: dict` |
| **D1.2** | Confidence check | Compare applicability × classification × role_matrix. e.g. applicability[NIS2]=true but classification=NOT_APPLICABLE → flag | `confidence_flags: list[{field, declared, computed, severity}]` |
| **D1.3a** | Block activation B1-B8 | 8 static rules (table below) | `blocks_active: list[str]` |
| **D1.3b** | Conditional questions activation | For each ON block, list active conditional Qs | `conditional_questions: dict[block, list[Q]]` |
| **D1.5** | Tier justification | Format text: "Tier MEDIUM justified by: 2 applicable regs + 3 active blocks + 8 employees (micro) + ..." | `tier_justification: str` |
| **D1.6** | Coherence | 5 invariants (e.g. GDPR applicable → role ≠ not_applicable) | `coherence_errors: list[str]` |

**Removed**: D1.4 (Native/Inherited by clause) — removed because `obligated_party` is empty in 100% of Phase 0 clauses. Will return when Phase 0 populates it.

**`company_facts` fields** (the dict that all predicates evaluate against):

| Type | Examples | Source |
|---|---|---|
| **Direct projection** | `name`, `sector`, `employees`, `scale`, `jurisdiction` | Direct from `input/company/classification.yaml` |
| **Simple derivation** | `processes_eu_personal_data` (= GDPR applicable), `is_cra_manufacturer` (= CRA applicable AND role=manufacturer) | Computed from D1.1a inputs |
| **Composite derivation** | `is_manufacturer_and_controller` (has manufacturer in one reg AND controller in another) | Computed from role_matrix |
| **Predicate-specific** | `ai_use_case`, `processing_scope`, `uses_cra_regulated_product` | **MUST be explicit input fields** (intake form) |

**Rule**: when a predicate references a field not in input nor derivable → verdict = `INDETERMINATE` (does not fail; flags client to fill).

**Block activation rules** (D1.3a — static enum in code):

| Block | Trigger ON | Condition |
|---|---|---|
| **B1** AI Governance | AI_Act applicable | `"AI_Act" in applicable_regs` |
| **B2** NIS2/SOC | NIS2 applicable | `"NIS2" in applicable_regs` |
| **B3** DORA Financial | DORA applicable | `"DORA" in applicable_regs` |
| **B4** Security Org | employees ≥ 50 OR tier ∈ {MED, HIGH} | numeric + tier |
| **B5** Special Category | GDPR applicable AND Art. 9 data | `gdpr_has_special_cat_data` (input) |
| **B6** Supply Chain | visibility=Low OR hardware dep | `supply_chain_visibility` (input) |
| **B7** CRA Classification | CRA applicable | `"CRA" in applicable_regs` |
| **B8** Multi-Actor | 2+ applicable regs OR mixed roles | `len(applicable_regs) >= 2` |

**Outputs** (consumed by D2–D7):

```python
{
    "applicable_regs": ["GDPR", "CRA"],
    "classification_per_reg": {"CRA": "CLASS_I", "GDPR": "controller", ...},
    "role_matrix": {"GDPR": ["controller"], "CRA": ["manufacturer"], ...},  # multiple roles
    "blocks_active": ["B6", "B7", "B8"],
    "tier_justification": "...",
    "confidence_flags": [...],
    "coherence_errors": [],
    "company_facts": { ... },  # the view used by predicate evaluation
}
```

---

### D2 — Capability assessment (deterministic)

**Status**: firm.

**Score**: no aggregate score (only the 12 individual IR states).

**Remediation**: NOT in Phase 1 (moves to Phase 2/3 — Phase 1 produces a Scope Declaration, not a remediation plan).

**Cross with regs**: yes — for each IR, determine which applicable regs require it (gives real criticality).

**Matrix IR→regs** (TEMPORARY constant in Phase 1, future Phase 0 contract):

```python
# Phase 1 constant until Phase 0 produces this (future contract)
IR_TO_RELEVANT_REGS = {
    "IR-01": {"regs": ["GDPR", "CRA", "NIS2", "DORA"], "subdomains": ["D-05", "D-10"]},
    "IR-02": {"regs": ["GDPR"], "subdomains": ["D-01"], "conditional": "art9_data"},
    "IR-03": {"regs": ["GDPR", "CRA", "NIS2", "DORA"], "subdomains": ["D-05"]},
    "IR-04": {"regs": ["GDPR", "NIS2", "DORA", "AI_Act"], "subdomains": ["D-08"]},
    "IR-05": {"regs": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"], "subdomains": ["D-04"]},
    "IR-06": {"regs": ["NIS2", "DORA"], "subdomains": ["D-04"]},
    "IR-07": {"regs": ["GDPR", "CRA", "NIS2", "DORA"], "subdomains": ["D-01", "D-05"]},
    "IR-08": {"regs": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"], "subdomains": ["D-03"]},
    "IR-09": {"regs": ["CRA", "NIS2", "DORA"], "subdomains": ["D-02"]},
    "IR-10": {"regs": ["NIS2", "DORA", "CRA"], "subdomains": ["D-06"]},
    "IR-11": {"regs": ["GDPR", "NIS2", "DORA"], "subdomains": ["D-05", "D-09"]},
    "IR-12": {"regs": ["GDPR", "NIS2", "DORA"], "subdomains": ["D-04", "D-06"]},
}
```

**Criticality logic** (per IR):

```
IF IR_state == "NO" OR "PARTIAL":
    exigido_por = IR_TO_RELEVANT_REGS[ir].regs ∩ applicable_regs
    IF len(exigido_por) > 0:
        criticidade = "CRÍTICO" if IR_state == "NO" else "ALTO"
    ELSE:
        criticidade = "BAIXO"  # not demanded by any applicable reg
ELSE:  # IR_state == "YES"
    criticidade = "OK"
```

**Sample output** (case1 — TinyTask, GDPR+CRA applicable):

| IR | Área | Estado | Exigido por | Crítico? |
|---|---|---|---|---|
| IR-01 | CISO | NO | GDPR, CRA | **CRÍTICO** |
| IR-02 | DPO | NO | GDPR | ALTO |
| IR-05 | Incident Response | PARTIAL | GDPR, CRA | ALTO |
| IR-07 | Backup | YES | GDPR, CRA | OK |
| ... | ... | ... | ... | ... |

---

### D3 — Catalog filtering + predicate evaluation (deterministic)

**Status**: firm.

**Sub-steps**:

| ID | Action | Source |
|---|---|---|
| **D3.1** | Filter clauses by applicable regs | `preproc_out/3-entities/clauses/_root/{REG}/*.json` |
| **D3.2** | Filter SRs by applicable regs (via path `srs/D-XX/`) | `preproc_out/3-entities/srs/` |
| **D3.3** | HSO_HL: keep all 38 (universal objectives) | `preproc_out/3-entities/sos/D-XX/*HL*` |
| **D3.4** | Filter HSO_PerReg by applicable regs | `preproc_out/3-entities/sos/D-XX/*{REG}*` |
| **D3.5** | Filter pairs: BOTH regs must be applicable | `preproc_out/3-entities/pairs/D-XX/*_{REG_A}-{REG_B}.json` |
| **D3.6** | Filter DomainAnalysis + DeepAnalysis by sub-domains with ≥1 applicable reg | `preproc_out/2-crossregulation/` |
| **D3.7** | Evaluate Tipo 2 predicates | `tipo2_interpretations.yaml` × `company_facts` |
| **D3.8** | Evaluate Tipo 3 predicates | `tipo3_derogations.yaml` × `company_facts` |
| **D3.9** | Evaluate scope_overlap predicates (for CONDITIONAL pairs) | `scope_overlap_predicates.yaml` × `company_facts` |
| **D3.10** | Evaluate event_templates triggers | `event_templates.yaml` × `company_facts` |

**Filtering rule** (clarification): the filter is **by reg only** for now. Classification (CRA Class I vs II) and role are NOT used to filter, because the Phase 0 catalog does not currently populate `obligated_party` / `applicable_classes` per clause. When those fields are populated, the filter can tighten. For now: reg-only filter + flag classification-specific clauses when known.

**Predicate evaluation logic**:

```python
def evaluate_predicate(predicate_str: str, company_facts: dict) -> str:
    """Evaluate a Python-like predicate against company_facts.
    Returns: 'ACTIVATED' | 'NOT_ACTIVATED' | 'INDETERMINATE'
    """
    try:
        # Safe eval (restricted globals — no builtins)
        result = eval(predicate_str, {"__builtins__": {}}, company_facts)
        return "ACTIVATED" if result else "NOT_ACTIVATED"
    except NameError as e:
        # Field referenced but not in company_facts
        return "INDETERMINATE"
    except Exception as e:
        logger.warning("Predicate eval failed: %s — %s", predicate_str, e)
        return "INDETERMINATE"
```

**Outputs**:

```python
filtered_catalog = {
    "clauses": [...],                # ~54 case1
    "srs": [...],                    # ~70 case1
    "hso_hl": [...],                 # 38 (all)
    "hso_per_reg": [...],            # ~50 case1
    "pairs": [...],                  # ~16 case1 (GDPR-CRA pairs only)
    "tipo2_activated": [...],        # entries with predicate ACTIVATED
    "tipo3_activated": [...],
    "scope_overlap_verdicts": {      # pair_id -> verdict
        "D-04.3_GDPR-CRA": "OVERLAP_CONFIRMED",
        ...
    },
    "event_candidates": [...],       # templates with triggers satisfied
}
```

---

### D4 — P1B-RATIONALE (LLM, per_regulation) — TO BE DETAILED

**Status**: structure agreed, prompt details TBD.

**Reduction**: this LLM merges the legacy LLM-B (rationale), LLM-C (implications), LLM-D (gaps) into a single per-regulation call. The legacy P1B-LLM-01-INTERPRETATION is removed (replaced by D3.7+D3.8 deterministic predicate evaluation).

**Inputs per regulation**:

- `company_facts`
- `classification_per_reg[reg]`
- `role_matrix[reg]` (with multiple roles)
- HSO_HL relevant to this reg (sub-domains this reg covers)
- HSO_PerReg[reg] (the per-reg security objectives)
- `tipo2_activated` filtered for this reg
- `tipo3_activated` filtered for this reg
- All clauses of this reg (from D3.1)
- Pairs involving this reg (from D3.5)
- `tier` (input)

**Expected outputs per regulation**:

```python
{
    "rationale": "2-3 paragraphs grounded in company facts + regulatory articles",
    "implications": [
        {
            "implication": "...",
            "architectural_impact": "...",
            "effort_estimate": "weeks",  # proportional to tier
            "dependencies": ["..."],
            "compound_flags": ["..."]  # cross-reg flags
        }
    ],  # 3-5 per reg
    "gaps": [
        {
            "sub_domain_id": "D-XX.Y",
            "coverage_level": "None|Partial",
            "risk_description": "...",
            "covered_by_other_reg": "GDPR Art.X",  # cross-ref
            "priority": "HIGH|MEDIUM|LOW"
        }
    ]
}
```

**Pending decisions** (to address in next session):

- Exact prompt structure
- Length limits (proportional to tier)
- Whether rationale is regenerated or template-based with LLM polish
- How compound_flags interact with D5 compound events

---

### D5 — Compound events (LLM OR deterministic) — TO BE DECIDED

**Status**: pending decision.

**Key question**: with `event_templates.yaml` already containing `trigger_predicates`, can D5 be 100% deterministic?

**Option A — Deterministic only**:

- D3.10 already evaluates triggers → produces `event_candidates`
- For each candidate, instantiate the event using `if_met.evidence_type` checks against Doc 04 facts + activations
- Output: concrete compound events with regulations, tension_type, severity
- **No LLM** — fully deterministic

**Option B — Deterministic + LLM polish**:

- D3.10 produces candidates (deterministic)
- LLM takes each candidate and produces a narrative scenario (1 paragraph) + concrete resolution approach
- **LLM is per-candidate** (light) — only for narrative

**Option C — Full LLM** (original P1C-LLM-02 design):

- LLM takes all candidates + company operational profile + produces events from scratch
- Most flexible but most expensive

**Default hypothesis**: **Option A** unless evidence shows templates are insufficient.

---

### D6 — P1C-STRATEGIC (LLM, global) — TO BE DETAILED

**Status**: structure agreed, prompt details TBD.

**Inputs** (global, not per-reg):

- `aggregated_complementarity` from D5
- `compound_events` from D5
- `per_reg_rationale` from D4 (rationale + implications + gaps per reg)
- `coverage_matrix` from D3
- `company_facts` (Doc 04)
- `tier` (input)

**Expected outputs**:

```python
{
    "strategic_implications": [
        {
            "id": "SI-01",
            "description": "...",  # MUST reference 2+ regulations
            "affected_sub_domains": ["D-XX.Y", ...],
            "regulations": ["GDPR", "CRA"],
            "architectural_impact": "...",
            "effort_estimate": "weeks",  # proportional to tier
            "business_goal_alignment": "BG-01",
            "resource_implications": [...],
            "risk_level": "..."
        }
    ],  # 5-8 cross-reg implications
    "scope_declaration": {
        # Contract artifact for Phase 2
        "applicable_regs": [...],
        "coverage_summary": {...},
        "priority_subdomains": [...],
        "deferred_subdomains": [...],  # from Track B
    },
    "gaps_aggregated": [...]  # cross-reg gap synthesis
}
```

**Constraint**: each strategic implication MUST reference 2+ regulations (otherwise it's a per-reg implication, belongs to D4).

---

### D7 — Track B (deterministic) — TO BE DETAILED

**Status**: structure agreed, rules TBD.

**Per sub-domain (38 entries)**:

| Field | Source |
|---|---|
| `tier` | LIGHTWEIGHT / MINIMAL / DEFERRED |
| `satisfaction_pattern` | how this sub-domain is satisfied (template-based) |
| `evidence_depth` | depth of evidence required |
| `verification_method` | how to verify |
| `ownership` | who owns this in the company |
| `example_controls` | concrete control examples |

**Tier assignment rule** (provisional — to refine):

```
IF sub_domain.coverage == "NOT_ADDRESSED":
    tier = "DEFERRED"
ELIF tier_company == "LOW" AND ni_sum < 6:
    tier = "LIGHTWEIGHT"
ELIF tier_company == "LOW":
    tier = "MINIMAL"
ELIF tier_company == "MEDIUM" AND ni_sum < 9:
    tier = "LIGHTWEIGHT"
ELSE:
    tier = "MINIMAL"
```

**GATE-P** (validation):
- Every ACTIVE sub-domain has tier assigned
- 5 attributes complete per sub-domain
- Rule 11 critical-overload check (no sub-domain overloaded beyond capacity)

**Pending**: exact tier assignment rule + 5-attribute enumeration templates.

---

## Part B — Document structure (per output)

### Doc 04 — Company Context Assessment

**Nature**: 100% deterministic. No LLM. Renders facts + D1 + D2 derivations.

**Sections**:

| § | Content | Source decision |
|---|---|---|
| §2 | Company Profile (snapshot) | D1.1a |
| §3 | Stakeholder Analysis | D1.1a (direct input) |
| §4 | Business Goals Catalog | D1.1a (direct input) |
| §5 | Intake Form Response Summary (Layer 0/1/2 summary, tier, blocks) | D1.1 + D1.3 + D1.5 |
| §6 | Regulatory Applicability Flags (5 regs × applicable + rationale + threshold) | D1.1 + D1.2 |
| §7 | Architectural Implications (native vs inherited control implications) | D1.1a (direct input) |
| §8 | Data Flow Summary (data elements × legal basis × retention) | D1.1a (direct input) |
| §9 | Compliance Capability Assessment (IR-12 × state × exigido × criticidade) | D2 |
| §10 | Role Matrix (per reg × roles; native/inherited removed) | D1.1 (direct input) |
| §11 | Regulatory Interactions (temporal conflicts, trigger mismatches) | D1.1a (direct input) |
| §12 | Confidence Flags + Coherence Errors | D1.2 + D1.6 |

### Doc 05 — Regulatory Applicability

**Nature**: per-regulation analysis. Includes D4 LLM output.

**Sections**:

| § | Content | Source decision |
|---|---|---|
| §2 | Executive Summary (overview across all regs) | Aggregation |
| §3 | Regulatory Applicability Analysis (per reg: criteria, classification, nuances, thresholds, rationale) | D1 + D3 + D4 |
| §4 | Applicability Summary Matrix (5 regs × applicable status) | D1.1 |
| §5 | Native vs Inherited Matrix | **REMOVED** (P6) — replaced by role matrix only |
| §6 | Preliminary Coverage Assessment (reg × sub-domain × Full/Partial/None) | D3 |
| §7 | Strategic Implications (Preliminary, per reg) | D4 |
| §8 | Regulatory Gaps (per reg) | D4 |

### Doc 06 — Clause Mapping Matrix (Excel, 7 sheets)

**Nature**: 100% deterministic.

| Sheet | Content | Source |
|---|---|---|
| **S1** Coverage Matrix | reg × domain × sub-domain × coverage × NI sum | D3 |
| **S2** Clause Inventory | filtered clauses with metadata | D3 |
| **S3** NI Distribution | reg × Shall/Should/May counts | D3 |
| **S4** Obligated Party Matrix | (offline until Phase 0 populates `obligated_party`) | — |
| **S5** Coverage Gaps | sub-domains with no/partial coverage | D3 |
| **S6** Summary Statistics | dashboard metrics | D3 |
| **S7** Raw Data | all clauses (unfiltered reference) | D3 |

### Doc 07 — Structured Compliance Matrix (hybrid)

**Nature**: synthesis + Phase 2 contract.

**Sections**:

| § | Content | Source |
|---|---|---|
| §2 | Applicable Regulations + classification | D1 |
| §3 | Sub-Domain Coverage Matrix (regs × sub-domains) + **HEATMAP** | D3 |
| §4 | Dashboard (coverage %, NI distribution, sole-authority count) + **CSF GAP MAP** | D3 |
| §5 | Cross-Regulation Analysis: instantiated complementarity + compound events + conflict classification | D5 |
| §6 | Strategic Implications (cross-reg) + Scope Declaration for Phase 2 | D6 |
| §7 | Identified Gaps (aggregated) | D6 |
| §8 | Phase 1 Gate (coverage meets tier?) | D3 + D7 |
| §9 | Track B Section (summary of Doc 07b) | D7 |

**Two new visualizations**:

1. **Heatmap coverage** (regs × 38 sub-domains): each cell colored Full (green) / Partial (yellow) / None (red). Sole-authority sub-domains flagged.
2. **CSF gap map** (106 CSF subcats × 38 sub-domains): each CSF subcat marked as mapped / unmapped. Unmapped shown in red.

### Doc 07b — Proportionality Profile

**Nature**: 100% deterministic (Track B).

**Content**: 38 rows (one per sub-domain) with `tier` + 5 attributes + GATE-P validation.

---

## Part C — Taxonomy decision context

The 10×38 taxonomy is **derived from the 5 regulations**, mapped to NIST CSF 2.0 (106 subcategories). It is **not** a general-purpose security taxonomy.

### Concerns identified

1. **CSF coverage gap**: 46/106 CSF subcategories are referenced in sub-domains. ~60 are not.
2. **8 sub-domains have no `participating_regulations` declared** in Phase 0 — possible orphans.
3. **Aspects not modeled**: business domains (finance, HR, legal) that may affect compliance but are not cybersecurity.

### Three visions for the taxonomy

#### Vision A — Taxonomy PERMANENT (skeleton of AEGIS-KG)

```
Phase 0 → produces taxonomy (38 sub-domains)
Phase 1 → uses to map clauses to company
Phase 2 → groups obligations by sub-domain
Phase 3 → organizes technical rules by sub-domain
Phase 4+ → keeps as reference
```

**Pros**:
- Total traceability clause → sub-domain → obligation → rule → control
- Consistent gap visualization across phases
- Coverage heatmap is the compliance "snapshot"
- Phase 0 investment (282 SRs path-mapped) is leveraged

**Cons**:
- Changing the taxonomy requires re-mapping affected SRs
- Some sub-domains may be too restrictive for non-cyber aspects

**Maintenance**: CSF audit already exists. Adding 1 sub-domain = 1-2 days work (re-map affected clauses, re-run audit).

#### Vision B — Taxonomy PRELIMINARY (initial triage only)

```
Phase 0 → produces taxonomy
Phase 1 → uses for initial triage + visualization
Phase 2+ → abandons, uses NIST CSF 2.0 directly or own ontology
```

**Pros**:
- Freedom to use other structures in later phases
- No "lock-in" to current taxonomy

**Cons**:
- Loses cross-phase traceability (clause → obligation)
- Gaps become invisible after Phase 1
- Phase 0 mapping work partially wasted
- Phase 2 needs to re-map obligations to some structure

#### Vision C — Taxonomy PERMANENT + ADDITIONAL LAYER (compromise)

```
Phase 0 → produces taxonomy 10×38
        + "Business Domains" layer (HR, finance, operations, etc.)
        + crosswalk between the two
Phase 1+ → uses both: taxonomy for compliance, business domains for context
```

**Pros**:
- Maintains traceability
- Captures non-cyber aspects relevant to compliance
- Complete gap visualization

**Cons**:
- More upfront modeling work
- May be over-engineering if few cases justify it

---

## Part D — Recommendation on taxonomy

**Recommended**: **Vision A (Permanent)** with documented exceptions.

**Reasons**:

1. Phase 0 investment is large — abandoning wastes work
2. Traceability is critical for a compliance system
3. The 8 orphan sub-domains and 60 unmapped CSF subcats are tractable without redoing the taxonomy
4. For non-cyber aspects, Doc 04 §7-§11 already captures architecture, data flows, interactions — they don't need their own sub-domains
5. If non-cyber aspects become truly necessary in the future, Vision C can be added without destroying Vision A

**Documented exceptions**:

- Sub-domains without `participating_regulations` → audit and fill
- Clauses without mapping → `UNMAPPED_CSF` marker
- CSF subcats not modeled → justify irrelevance OR create sub-domain

**Decision**: PENDING (user requested more discussion before deciding).

---

## 5. Critical data findings

These findings affect what Phase 1 can and cannot do today.

| # | Finding | Impact |
|---|---|---|
| **C1** | `obligated_party` in **0%** of 498 clauses | Blocks Native/Inherited → removed (P6) |
| **C2** | `appliesToRole` in **0%** of 282 SRs | Same root cause |
| **C3** | `subDomainIds` in **0%** of SRs | Mapping is by file path (`srs/D-XX/`), not by field |
| **C4** | **498 clauses** total (not 150 as diagrams claim) — distribution: 177 CRA + 153 DORA + 86 GDPR + 53 NIS2 + 29 AI_Act | Re-verify coverage claims |
| **C5** | **8 sub-domains** have no `participating_regulations` declared | Possible orphans — audit needed |
| **C6** | **4 YAML catalogs** with executable predicates already exist | Allows eliminating P1B-LLM-01 + P1C-LLM-01 |
| **C7** | **DeepAnalysis (CRDA-deep) already has** `classification` OJ-verified + `scope_disjoint_test` + `downstream_implication` per pair | P1C-LLM-01 was redundant |
| **C8** | **46/106 CSF subcategories** referenced in sub-domains | Potential gap — verify irrelevance |

---

## 6. Open questions

| # | Question | When to resolve |
|---|---|---|
| **Q1** | Role of taxonomy (permanent vs preliminary) | Before D7 / before advancing to Phase 2 |
| **Q2** | Treat 8 orphan sub-domains | Quick Phase 0 audit |
| **Q3** | Populate empty fields (`obligated_party`, `subDomainIds`, `appliesToRole`) in Phase 0 | Separate Phase 0 contract |
| **Q4** | D5: compound events — deterministic via `event_templates.yaml` or LLM? | When reaching D5 |
| **Q5** | D1.4 Native/Inherited — return when Phase 0 populates `obligated_party` | Deferred |
| **Q6** | IR→regs matrix in Phase 0 (future contract) | After Phase 1 stabilizes |
| **Q7** | Predicate-specific fields (`ai_use_case`, `processing_scope`) in intake form | When closing D1 |

---

## 7. LLM reduction: 5 → 2

| Legacy LLM | Status | Replacement |
|---|---|---|
| ~~`P1B-LLM-01-INTERPRETATION`~~ | **REMOVED** | D3.7 + D3.8 (deterministic predicate evaluation) |
| `P1B-LLM-02-RATIONALE` | **KEPT** (renamed `P1B-RATIONALE`) | Merges legacy LLM-B/C/D into one call |
| ~~`P1C-LLM-01-OVERLAP-CLASSIFICATION`~~ | **REMOVED** | D3.9 (`scope_overlap_predicates.yaml` deterministic) |
| `P1C-LLM-02-COMPOUND-EVENT` | **PENDING** | D5 — `event_templates.yaml` may make it deterministic |
| `P1C-LLM-03-STRATEGIC-SYNTHESIS` | **KEPT** (renamed `P1C-STRATEGIC`) | Final cross-reg synthesis |

**Net result**: from 5 LLMs (with `per_regulation × 2` + `per_domain_lane × 10` + `global_reduce × 2`) to **2 LLMs** (`per_regulation × 1` + `global × 1`), with D5 potentially eliminating one more.

---

## 8. Next steps (suggested order)

1. **Decide Q1** (taxonomy permanent vs preliminary) — when comfortable
2. **Detail D4** (P1B-RATIONALE) — prompt structure, inputs, outputs
3. **Decide Q4** (D5: deterministic vs LLM)
4. **Detail D6** (P1C-STRATEGIC) — what is "really new" vs aggregation
5. **Close D7** (Track B) — tier assignment rules
6. **Map orchestration** — LOAD → MAP → REDUCE → OUTPUT, decisions per stage

---

## Version history

| Version | Date | Changes |
|---|---|---|
| 0.1 (draft) | 2026-07-27 | Initial draft from design session. Captures all decisions to date. |
