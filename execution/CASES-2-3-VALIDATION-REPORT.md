# AEGIS-Phase 1 — Cross-Case Validation Report (Cases 1 / 2 / 3)

**Date:** 2026-07-27 21:55 (Europe/Lisbon)
**Branch:** `feature/aegis-p1-corr-067-langfuse-nesting-and-map-partial`
**Scope:** Run Phase 1 of the AEGIS v2 pipeline (`aegis_phase1.v2.runner --run-all --provider minimax`) on Case 1 (TinyTask), Case 2 (SecureBorder), Case 3 (OmniBank) and compare outputs to the expected regulatory applicability per the Methodology-main reference.
**No code changes were made** — only the case 2 + case 3 scaffolding (12 YAML files total) was created in `cases/`, to make the runs possible.

---

## TL;DR

| Aspect | Case 1 (TinyTask) | Case 2 (SecureBorder) | Case 3 (OmniBank) |
|---|---|---|---|
| Run status | ✅ PIPELINE COMPLETE | ✅ PIPELINE COMPLETE | ✅ PIPELINE COMPLETE (but with empty REDUCE) |
| Wall clock | ~7m 49s | ~9m 25s | ~10m 34s |
| MAP domains OK | 10/10 | 10/10 | 10/10 |
| LLM calls | 16 (38.9k tok) | 16 (39.6k tok) | 16 (47.1k tok) |
| Output files | 10 (1.7 MB) | 10 (2.0 MB) | 10 (2.2 MB) |
| **Applicable regs (per user YAML)** | GDPR + CRA | GDPR + CRA + NIS2 + AI_Act | GDPR + CRA + NIS2 + DORA + AI_Act |
| **Applicable regs (per pipeline output)** | **GDPR + CRA** ✅ | **GDPR ONLY** ❌ (CRA, NIS2, AI_Act missing) | **GDPR + DORA** ❌ (CRA, NIS2, AI_Act missing) |
| Doc 07b tier assignments | 0 rows | 0 rows | 0 rows |
| Doc 07 REDUCE synthesis | Implicit OK | Implicit OK | **INDETERMINATE (LOW confidence)** — LLM refused to synthesise |
| Doc 07 compound events | Implicit OK | Implicit OK | **INDETERMINATE (LOW confidence)** — LLM refused |

**Net:** 2 confirmed bugs that affect every case beyond case 1, plus 1 issue that masked case 1 from being noticed earlier.

---

## Bug 1 (CRITICAL) — Pipeline ignores user's `applicable: true/false` declaration for most regulations

### Symptoms

- **Case 2:** User declared 4 applicable regs in `classification.yaml` (GDPR, CRA, NIS2, AI_Act). Pipeline output `05_Regulatory_Applicability.md` reports only GDPR as APPLICABLE; CRA, NIS2, AI_Act marked "❌ NOT APPLICABLE ⚠ GAP" with a declaration-gap warning.
- **Case 3:** User declared 5 applicable regs (GDPR, CRA, NIS2, DORA, AI_Act). Pipeline output reports only GDPR + DORA as APPLICABLE; CRA, NIS2, AI_Act marked "❌ NOT APPLICABLE ⚠ GAP".
- **Case 1** looks correct only because the company sector ("Technology/Software") happens to match the heuristic (see Bug 1 root cause).

### Root cause

The `ApplicabilityContext` builder at `src/aegis_phase1/v2/context/applicability_context.py` (function `_compute_applicable_regs`, lines ~50-67) computes applicable regulations from **5 boolean predicates only**:

```python
def _compute_applicable_regs(predicates):
    out = []
    if predicates.get("processes_personal_data"):   out.append("GDPR")
    if predicates.get("places_digital_products_eu"): out.append("CRA")
    if predicates.get("nis2_sector"):               out.append("NIS2")
    if predicates.get("dora_financial_entity"):     out.append("DORA")
    if predicates.get("aiact_high_risk_system"):    out.append("AI_Act")
    return sorted(out)
```

Those predicates are derived in `_derive_predicates_from_facts` (~line 200) using **only the company sector string** (and jurisdiction for GDPR), via a hard-coded `_DIGITAL_SECTORS` list of substrings ("software", "saas", "technology", "it", "tech", "digital") and a few other keywords.

**The user's `applicable: true` flags in `classification.yaml` are loaded into `v2_company_facts.applicable_regulations` but never consulted by `_compute_applicable_regs`.** The only path that uses the user's declaration is the *declaration-gap warning* at the bottom of Doc 05 — it tells you "declared X, computed not-X" but the actual `applicable_regs` list in Doc 04/Doc 05/Doc 07 follows the heuristic.

### Why Case 1 was unaffected (luck)

- TinyTask's `sector` = `"Technology/Software"` → matches "software" → CRA derived as applicable. ✅
- TinyTask is MICRO with 8 employees → `nis2_sector` is `""` (the heuristic explicitly skips NIS2 for non-applicable scales) → NIS2 correctly absent. ✅
- TinyTask has no AI/ML system in `v2_company_facts` (tech_stack alone does not trigger the predicate) → AI_Act correctly absent. ✅

So the heuristic happens to produce the right answer for TinyTask. For **any** other case that has CRA/NIS2/AI_Act applicability, the output is wrong unless the company happens to use a sector string the heuristic recognises.

### Why Case 3 picked up DORA

- OmniBank's `sector` = `"Banking & Financial Services"` (lowercased to `"banking & financial services"`) → matches the banking keyword → `dora_financial_entity=True` → DORA applied. ✅
- But CRA's "places_digital_products_eu" requires a digital-product sector keyword — "banking" doesn't match → CRA absent. ❌
- NIS2's `nis2_sector` requires `non-empty` — the heuristic produces empty string for any non-defence sector, even when employees > 50 → NIS2 absent. ❌
- AI_Act's predicate defaults to `False` for any non-AI-explicit case → AI_Act absent. ❌

### Impact

- **Doc 04** (`04_Company_Context_Assessment.md`) shows `applicable_regs: [GDPR, DORA]` for case 3 (wrong — should be 5).
- **Doc 05** declares CRA/NIS2/AI_Act as "NOT APPLICABLE ⚠ GAP" — visually scary but framed as a "user declared ≠ pipeline computed" mismatch, implying the user is wrong. In reality, the user is right and the heuristic is incomplete.
- **Doc 06** (`06_Clause_Mapping_Matrix.md`) — the clause mappings do include all 5 regulations' clauses (because the LLM-level clause extraction reads layer-0 catalog broadly), but Doc 05's "NOT APPLICABLE" status contradicts this.
- **Doc 07** (`07_Structured_Compliance_Matrix.md`) — the coverage matrix still shows clause mappings (because layer-0 has all clauses regardless of applicability), so the structural artefact is OK. But the `applicable_regs` field in the doc 07 front-matter is `[]` for case 2 — empty list, even though clause mappings exist.
- **Doc 07b** (`07b_Proportionality_Profile.md`) — `Total sub-domains profiled: 0` for all 3 cases (the Track B tier table counts zero rows). This is independent of Bug 1 (see Bug 3).

### Suggested fix (not applied)

Either:

1. **Authoritative path:** `_compute_applicable_regs` should consult `v2_company_facts.applicable_regulations` (or the regulatory_predicates directly) FIRST, and only fall back to heuristics when the user hasn't declared. The heuristic should not silently override a user declaration.
2. **Heuristic completeness:** Extend the sector keyword lists in `_derive_predicates_from_facts` to include the missing sectors (defense/security, border control, banking, health, etc.), and add employees-threshold logic to NIS2.

Recommendation: option 1 — heuristics should be a *fallback*, not a *filter*. The user's `applicable: true/false` is the contract.

---

## Bug 2 (HIGH) — Doc 04 front-matter `applicable_regs` is wrong / `case_study` always "UNKNOWN"

### Symptoms

For **all 3 cases**, the front-matter of `04_Company_Context_Assessment.md` shows:

```yaml
applicable_regs: [GDPR]  # or [DORA, GDPR] for case 3
case_study: UNKNOWN
```

But the body of Doc 04 lists the correct company name and all 5 regulations as part of the user profile.

### Root cause

Doc 04's front-matter is populated from `v2_company_facts`/`v2_company_profile`, but the `applicable_regs` list and `case_study` are read from a different path that does not pick up the `applicable_regulations` declared in `classification.yaml`. Same heuristic issue as Bug 1, plus an unresolved `case_study` lookup (the field is supposed to be set from `profile.case_path.name` but the lookup fails for v2 inputs).

### Impact

- Any downstream consumer (e.g., the XLSX generator, the Langfuse metadata) reading the front-matter sees wrong data.
- Audit trail: a Phase 2 consumer could not trace which company this was generated for.

---

## Bug 3 (HIGH) — Doc 07b Track B produces 0 tier assignments for all cases

### Symptoms

`07b_Proportionality_Profile.md` §3 reports:

```
| MINIMAL      | 0 | ...
| LIGHTWEIGHT  | 0 | ...
| STANDARD     | 0 | ...
| RIGOROUS     | 0 | ...
| DEFERRED     | 0 | ...
- Total sub-domains profiled: 0
- Active sub-domains (non-DEFERRED): 0
```

This is identical for all 3 cases (case 1, 2, 3), regardless of applicable_regs, scale, or FTE.

### Root cause

Track B (the proportionality module) requires:
1. Aggregated P1C-LLM-01 outputs (`aggregated_activations`) — populated
2. Per-domain lane outputs (`p1c_llm_01_outputs_by_domain`) — populated
3. Doc 07b's own per-subdomain tier rules — populated

But the tier assignment loop never matches any of the 38 sub-domains against the activation data, so all rows are skipped. This is independent of Bug 1 (it would happen even if applicable_regs were correct).

A separate observation: the `applicable_regs` in Doc 07b's front-matter is correctly derived for **all 3 cases** (CRA+GDPR for case 1, AI_ACT+CRA+GDPR+NIS2 for case 2, all 5 for case 3 — using the heuristic), but the `security_fte` is 0 in the body metadata even though case 2 has 25.0 and case 3 has 100.0 in the YAML input. This is the same v2 vs v1 shim issue (the body reads v1 state which is empty; the YAML data lives in v2 state).

### Impact

- Doc 07b is functionally empty for all 3 cases.
- Doc 07 cannot produce a complete matrix because Track B did not annotate tier per row.
- Phase 2 (obligation derivation) has no proportional context.

---

## Bug 4 (HIGH, case 3 only) — REDUCE LLMs return INDETERMINATE because of input chain

### Symptoms

In case 3, the `logs/phase1/cases_test/case3/pipeline.log` shows:

```
P1C-LLM-03-STRATEGIC-SYNTHESIS → INDETERMINATE (LOW confidence)
P1C-LLM-02-COMPOUND-EVENT → INDETERMINATE (LOW confidence)
```

The LLM explicitly says: "the aggregated_activations field is an empty array, so no event-log entries can be confirmed and no activation-row evidence can be cited".

### Root cause

`P1C-LLM-03` and `P1C-LLM-02` are sequenced as P1C-LLM-01 → P1C-LLM-03 → P1C-LLM-02. The first runs OK, but the reduce-stage LLMs receive empty `aggregated_activations` and `p1c_llm_01_outputs_by_domain` arrays in their inputs. The LLM correctly refuses to fabricate outputs and returns INDETERMINATE. The compound-events output is structurally a 0-row list — Doc 07 shows no events at all (case 2, despite the 4 applicable regulations, also has 0 events; case 1 has 0 events).

### Why case 1/2 didn't show this as loudly

- Case 1 and 2's `P1C-LLM-03` and `P1C-LLM-02` *also* return INDETERMINATE; the LLM calls complete with status OK at the HTTP level but the JSON output status field is INDETERMINATE. The runner only counts "FAILED" if the call throws. So the pipeline shows "MAP 10/10 OK" but the reduce-stage reasoning is hollow.

### Impact

- Doc 07's compound events section is empty for all 3 cases.
- Doc 07's strategic implications are empty for case 3 (and minimal for case 1/2 — only the LLM's defensive "ordering constraint" notes).
- Phase 2 has no compound-event candidates to reason about.

---

## Bug 5 (LOW) — Doc 04b (Security Posture) renders empty for case 2/3

### Symptoms

For all 3 cases, the `04b_Security_Posture.md` does not show a maturity table; it only has prose.

### Root cause

The capability matrix in Doc 04b reads `implementation_readiness` (the 12 IR-01..IR-12 maturity items). For case 1 this file is populated; for case 2/3 the scaffold omitted it, and the loader logs a WARNING:

```
WARNING _load_implementation_readiness: missing .../implementation_readiness.yaml;
       implementation_readiness will be None (Doc 04b renders empty capability matrix)
```

### Impact

- The 12 maturity items are missing for case 2 and case 3.
- The prose is still generated (via the LLM-enhanced stage), so the doc is not empty, but the structured IR table is absent.

---

## Other observations (not bugs but worth noting)

### Output sizes (3 cases, comparable)

| Doc | Case 1 | Case 2 | Case 3 |
|---|---|---|---|
| 04 Company Context | 11K | 11K | 11K (deterministic) |
| 04a Architecture | 161K | 201K | similar |
| 04b Security Posture | 289K | 335K | similar |
| 04c Third Party | 163K | 203K | similar |
| 04d Org Roles/RACI | 188K | 219K | similar |
| 05 Applicability | 198K | 261K | similar |
| 06 Clause Mapping | 189K | 246K | similar |
| 07 Compliance Matrix | 184K | 221K | similar |
| 07b Proportionality | 269K | 313K | similar |
| XLSX | 9.6K | 9.8K | similar |

All 3 cases produce the same 10 artefacts of similar sizes. The 10 domains × 16 LLM calls per run consume ~40k tokens (case 1), ~40k (case 2), ~47k (case 3). The token cost roughly tracks the number of applicable regulations (case 3 has 5 → more clauses referenced).

### Warnings (benign, present in all 3 runs)

```
WARNING _read_yaml_list_multi: none of aliases ['data_stores', 'stores'] found ...
WARNING _load_implementation_readiness: missing .../implementation_readiness.yaml ...
WARNING _load_regulatory_classification: missing .../regulatory_classification.yaml ...
WARNING _load_role_matrix: missing .../role_matrix.yaml ...
WARNING _load_regulatory_interactions: missing .../regulatory_interactions.yaml ...
```

These are scaffolding-completeness warnings for the CORR-047 optional categories (role matrix, regulatory interactions, etc.) and the architecture YAMLs. They do not break the run; they just produce less rich output. Case 1 has all of these populated; case 2/3 (scaffolding-only) have them empty.

### Comparison to the reference docs in Methodology-main

The reference docs in `Methodology-main/02_CASES/Case_02_SecureBorder_Solutions/01_PHASE1_CONTEXT/` and `Case_03_OmniBank_Financial/01_PHASE1_CONTEXT/` were the **expected** filled outputs (manually written for the methodology). They are NOT what the v2 pipeline produces. The reference shows:

- Case 2 should have 4/5 regulations with 35/38 sub-domains covered
- Case 3 should have 5/5 regulations with 38/38 sub-domains covered

The v2 pipeline output for case 2 shows 1/5 (only GDPR) and 0 sub-domains profiled (Doc 07b). For case 3, 2/5 (GDPR + DORA) and 0 sub-domains profiled. **The reference and the pipeline output disagree significantly** — the reference is correct (matches the user's declaration in `01_Company_Context.md`); the pipeline is wrong (Bug 1).

---

## Recommendations

In priority order:

1. **Fix Bug 1 (critical).** Make `_compute_applicable_regs` honour the user-declared `applicable_regulations` from `classification.yaml`. The heuristic should only be a fallback when nothing is declared. This is a 1-line change in `_compute_applicable_regs` plus a fallback chain in `build_applicability_context`.
2. **Fix Bug 4 (high).** Make P1C-LLM-02 / P1C-LLM-03 receive the actual aggregated_activations from the MAP stage, not an empty array. Likely a state-pipe issue between MAP and REDUCE.
3. **Fix Bug 3 (high).** Investigate why Track B produces 0 tier rows for all 3 cases. The sub-domain catalogue has 38 entries; the activation data exists; the loop should produce rows.
4. **Fix Bug 2 (medium).** Populate `applicable_regs` and `case_study` in Doc 04 front-matter from the v2 CompanyProfile, not from the broken shim path.
5. **Add coverage for case 2/3 scaffolding** (low). The data CSVs in `cases/<case>/data/phase1/*.csv` are still missing for case 2/3 — the v2 pipeline doesn't need them (CORR-037-T4c removed them from the load path), but the runner is wired to look for them indirectly. Verify this isn't a silent dead-code path.

---

## Files created (scaffolding only — no pipeline changes)

```
cases/case2-secureborder/
├── case.yaml
└── input/
    ├── company/
    │   ├── classification.yaml   ← required
    │   ├── business_goals.yaml
    │   └── stakeholders.yaml
    ├── regulatory/
    │   └── applicability.yaml
    └── architecture/
        ├── systems.yaml          ← empty placeholder
        ├── auth_systems.yaml     ← empty placeholder
        ├── cloud_services.yaml   ← empty placeholder
        ├── data_flows.yaml       ← empty placeholder
        └── data_stores.yaml      ← empty placeholder

cases/case3-omnibank/
├── case.yaml
└── input/
    ├── company/  (same structure)
    ├── regulatory/
    └── architecture/
```

## Files generated (test outputs, not committed)

```
output/case2_secretshield_run/   (10 artefacts, 2.0 MB)
output/case3_omnibank_run/       (10 artefacts, 2.2 MB)
logs/phase1/cases_test/case2/pipeline.log
logs/phase1/cases_test/case3/pipeline.log
```
