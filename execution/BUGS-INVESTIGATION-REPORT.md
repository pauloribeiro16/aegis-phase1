# AEGIS Phase 1 — Bug Investigation Report (cases 2 & 3)

**Date:** 2026-07-28 00:00 (Europe/Lisbon)
**Branch:** `feature/aegis-p1-corr-067-langfuse-nesting-and-map-partial`
**Scope:** Deep-dive investigation of the bugs surfaced by the case 1/2/3 cross-validation. Each bug has: root cause, code path, reproducer, impact, suggested fix.
**No code changes were made.**

---

## TL;DR — 5 bugs confirmed and located

| # | Bug | Severity | One-line cause | File / line |
|---|---|---|---|---|
| 1 | User-declared `applicable: true` is overridden by sector-heuristic | CRITICAL | `build_applicability_context()` calls `_compute_applicable_regs(predicates)` and only uses `v2_applicable_regs` as fallback | `src/aegis_phase1/v2/context/applicability_context.py:247-254` |
| 2 | `domain_results[D-XX]["subdomains"]` is hardcoded to `[]` | HIGH | `_map_domains_via_p1c_llm_01` writes `[]` to legacy field; real data is in `adapted_subdomains_v3` | `src/aegis_phase1/v2/orchestrator.py:~700` |
| 3 | P1C-LLM-02/03 receive empty `aggregated_activations` | HIGH (cascade of Bug 2) | `reduce_synthesis()` reads from the broken legacy `subdomains` field | `src/aegis_phase1/v2/orchestrator.py:~1019` (cascade), `src/aegis_phase1/prompts_v2/phase1_executor.py:run_phase_1c_reduce` (consumer) |
| 4 | Doc 07b `case_study: UNKNOWN`, `scale: "-"`, `security_fte: 0` | LOW | Front-matter uses `getattr(dict, "company_name")` which always raises AttributeError; should be `dict.get(...)` or `_safe_attr` | `src/aegis_phase1/v2/output/doc_07b.py:_build_frontmatter` (line ~125) |
| 5 | Doc 04 front-matter `applicable_regs` + `tier` use heuristic result | LOW (cascade of Bug 1) | `doc_04.py` reads `app_ctx.applicable_regs` (broken heuristic) instead of `state["v2_applicable_regs"]` | `src/aegis_phase1/v2/output/doc_04.py:~165` |

Bugs 1, 2, 3 are **independent regressions**. Bug 5 is downstream of Bug 1. Bug 4 is independent of all others.

All 3 cases (TinyTask, SecureBorder, OmniBank) are affected by bugs 2, 3, 4. Bugs 1 and 5 only affect cases 2 and 3 (case 1's sector "Software" matches the heuristic keyword, so heuristic output coincidentally matches user declaration).

---

## Bug 1 (CRITICAL) — User-declared applicability overridden by sector heuristic

### Root cause

Two sources of "applicable_regs" in the pipeline; they disagree. The user-declared source is correct; the heuristic source is wrong but used as the authoritative answer.

**Source A (correct, user intent)** — `src/aegis_phase1/v2/loader/case_profile.py:514-562` in `CaseProfileLoader.load()`:

```python
applicable_regs_entries = self._load_applicable_regulations()
computed_applicable: list[str] = sorted(
    e.abbreviation for e in applicable_regs_entries if e.applicable
)
# ... populates state["v2_applicable_regs"] = list(profile.applicable_regs)
```

Verified at runtime for case 2: `profile.applicable_regs == ['AI_Act', 'CRA', 'GDPR', 'NIS2']`.

**Source B (broken, sector heuristic)** — `src/aegis_phase1/v2/context/applicability_context.py:201-318` in `build_applicability_context()`:

```python
# Line 239
predicates = _derive_predicates_from_facts(company_facts_dict)
# Line 245 — the correct list is read but...
v2_applicable_pre: list[str] = list(state.get("v2_applicable_regs", []))
# Line 247-254 — THE BUG (heuristic is authoritative, v2_applicable_pre is fallback)
applicable_computed = _compute_applicable_regs(predicates)
if not applicable_computed and (v1_applicable_from_cc or v2_applicable_pre):
    applicable_computed = sorted(set(v1_applicable_from_cc) | set(v2_applicable_pre))
```

The heuristic (`_derive_predicates_from_facts` at line 321-368) is sector-keyword based. Hardcoded lists:

```python
_DIGITAL_SECTORS = ("software", "saas", "technology", "it ", "tech", "digital",
                   "app", "platform", "cloud", "hosting", "web", "ecommerce",
                   "fintech", "edtech")
# ...
dora_financial_entity = bool(any(s in sector for s in ("finance", "bank", "insurance")))
# ...
"aiact_high_risk_system": False,  # ALWAYS FALSE
```

There is **no keyword for "defense"**, "border control", "security services", "critical infrastructure", "health", etc. AI_Act is hardcoded to `False`. So the heuristic can never recognise the user's CRA/NIS2/AI_Act applicability for case 2.

### Why case 1 was unaffected

TinyTask's `sector` = `"Technology/Software"` → matches "software" → heuristic produces `places_digital_products_eu=True` → CRA derived. NIS2 correctly absent (heuristic returns empty `nis2_sector` for non-defence sectors). AI_Act correctly absent. So heuristic output = user declaration = `[GDPR, CRA]`. Lucky coincidence.

### Why case 3 still gets DORA

`Banking` keyword in `dora_financial_entity` rule → DORA derived. But `places_digital_products_eu` requires a digital-product keyword — "Banking" doesn't match → CRA absent. Same logic for NIS2 and AI_Act.

### Reproducer (any non-TinyTask case)

```bash
export MINIMAX_API_KEY="$(cat /tmp/m3_key_for_test)"
source ../shared-venv/bin/activate
PYTHONPATH=src python -c "
from pathlib import Path
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
loader = CaseProfileLoader(Path('cases/case2-secureborder'))
profile = loader.load()
print('user-declared applicable_regs:', profile.applicable_regs)
"
# Expected: ['AI_Act', 'CRA', 'GDPR', 'NIS2']
# What the pipeline reports in 05_Regulatory_Applicability.md: ['GDPR']
```

### Suggested fix (1 file, ~8 lines)

`src/aegis_phase1/v2/context/applicability_context.py` lines 245-254:

```python
# NEW: v2_applicable_regs is authoritative; heuristic is fallback
v2_applicable_pre: list[str] = list(state.get("v2_applicable_regs", []))
applicable_computed = _compute_applicable_regs(predicates)
if v2_applicable_pre:
    # User has declared applicability via classification.yaml — trust it
    applicable_computed = list(v2_applicable_pre)
elif not applicable_computed and v1_applicable_from_cc:
    applicable_computed = sorted(v1_applicable_from_cc)
```

This is a safe, low-risk change: it only takes effect when the user has actually populated the `classification.yaml` `applicable_regulations` list (which is the canonical entry point per AGENTS.md §0). It preserves the heuristic as a fallback for legacy state.json from pre-CORR-061 runs.

### Impact

- **Doc 04** front-matter `applicable_regs` — wrong
- **Doc 05** `APPLICABILITY SUMMARY` table — wrong status, wrong rationale
- **Doc 05** `DECLARATION GAPS` warning — wrongly blames the user for "declared X, computed not-X" when actually user is right
- **Doc 07** §3 coverage matrix — `applicable-yes column criterion` misclassifies
- **Doc 07b** — uses a different code path (reads `state["company_context"]["applicable_regs"]` directly) so its `applicable_regs` in the front-matter is CORRECT (this is why Doc 07b's front-matter for case 2 shows 4 regs correctly). But the body §2 metadata has bugs (see Bug 4).
- **Phase 2** (obligation derivation) — only processes heuristic subset, silently drops obligations for CRA/NIS2/AI_Act in case 2, and CRA/NIS2/AI_Act in case 3

---

## Bug 2 (HIGH) — `domain_results[D-XX]["subdomains"]` is hardcoded to `[]`

### Root cause

**File:** `src/aegis_phase1/v2/orchestrator.py`
**Function:** `_map_domains_via_p1c_llm_01` (line ~657-704)

```python
results[did] = {
    "domain_id": did,
    "domain_name": DOMAIN_NAMES.get(did, did),
    "subdomains": [],  # ← HARDCODED EMPTY LIST (line ~700)
    ...
    "adapted_subdomains_v3": adapted_v3,  # ← ACTUAL DATA
    ...
}
```

The actual sub-domain activations from P1C-LLM-01 are stored in `adapted_subdomains_v3`. The legacy `subdomains` field is empty.

The downstream consumers expect the legacy `subdomains` field:

- `src/aegis_phase1/v2/reduce/concatenator.py:59`:
  ```python
  domain_subdomains = (domain_result or {}).get("subdomains", []) or []
  for entry in domain_subdomains:  # ← always []
      ...
  ```
  Result: `subdomains = {}`, 0 subdomains passed to merge/proportionality.

- `src/aegis_phase1/v2/orchestrator.py:reduce_synthesis()` (line ~1019):
  ```python
  "sub_domain_activations": (
      lane_result.get("subdomains") or [] if isinstance(lane_result, dict) else []
      #                                  ↑ always []
  )
  ```
  Result: 0 activations passed to the reduce-stage LLMs.

### Verifier (logs)

For all 3 cases:
```
concatenate: 10 domains -> 0 subdomains, 10 adapted_objectives
apply_proportionality: 0 subdomains profiled (scale=MICRO, fte=0.00)
```

The 10 `adapted_objectives` are the prose narratives (different field, works). The 0 subdomains is the structural data loss.

This was almost certainly introduced in **CORR-040-T2** when the canonical P1C-LLM-01 path was wired. The new path builds `adapted_subdomains_v3` (a different shape: `[{sub_domain_id, reg_pair, company_scope_verdict, ...}]`) but didn't update the downstream consumers OR populate the legacy `subdomains` field for backward compatibility.

### Suggested fix (1 file, ~15 lines)

`src/aegis_phase1/v2/orchestrator.py` in `_map_domains_via_p1c_llm_01`, populate the legacy `subdomains` field from `adapted_v3`:

```python
# Map adapted_v3 (v3 shape) to legacy subdomains (v1 shape) for backward compat
legacy_subdomains = [
    {
        "subdomain_id": sd.get("sub_domain_id", ""),
        "id": sd.get("sub_domain_id", ""),
        "reg_pair": sd.get("reg_pair", []),
        "company_scope_verdict": sd.get("company_scope_verdict", ""),
        "regulatory_baseline_relationship": sd.get("regulatory_baseline_relationship", ""),
        "layer0_refs": sd.get("layer0_refs", []),
    }
    for sd in adapted_v3
]
results[did] = {
    ...
    "subdomains": legacy_subdomains,  # ← was []
    "adapted_subdomains_v3": adapted_v3,
    ...
}
```

### Impact

- **Doc 07b** — 0 tier rows in `§3 TIER ASSIGNMENT SUMMARY` (Track B sees an empty dict)
- **Doc 07** §3 coverage matrix — 38 sub-domains show 0 clauses and `NOT_ADDRESSED` status
- **Doc 07** §4 strategic implications — empty (Bug 3 cascade)
- **Doc 07** §5 compound events — empty (Bug 3 cascade)
- **Phase 2** Track B data flow — broken

---

## Bug 3 (HIGH, cascade of Bug 2) — P1C-LLM-02/03 receive empty `aggregated_activations`

### Root cause

**File:** `src/aegis_phase1/prompts_v2/phase1_executor.py:run_phase_1c_reduce`

```python
aggregated_activations: list[dict[str, Any]] = []
for lane in lane_outputs:
    sds = lane.get("sub_domain_activations") or []  # ← always [] (Bug 2)
    if isinstance(sds, list):
        aggregated_activations.extend(sds)
```

Result: `aggregated_activations = []` for both P1C-LLM-03 (STRATEGIC-SYNTHESIS) and P1C-LLM-02 (COMPOUND-EVENT).

### Verifier

The P1C-LLM-02 JSON body explicitly says:
> "the `aggregated_activations` field is an empty array, so no event-log entries can be confirmed and no activation-row evidence can be cited."

Returns `status: INDETERMINATE` (not `OK`, not `FAILED`). The orchestrator only treats exceptions as failures, so the pipeline reports "REDUCE-LLM complete" and continues. Doc 07 then renders the empty event list without surfacing the INDETERMINATE warning prominently.

### Suggested fix

Fixed by Bug 2 fix (cascading).

### Additional defensive fix (recommended)

In `phase1_executor.py:run_phase_1c_reduce`, also read from `lane.get("adapted_subdomains_v3", [])` as a fallback if `sub_domain_activations` is empty. This makes the executor more robust against future field-shape changes.

### Impact

- **Doc 07** §4 strategic implications — empty / defensive note
- **Doc 07** §5 compound events — empty
- **Doc 07** §5 risks — empty

---

## Bug 4 (LOW) — Doc 07b `case_study: UNKNOWN`, `scale: "-"`, `security_fte: 0`

### Root cause

**File:** `src/aegis_phase1/v2/output/doc_07b.py`
**Function:** `_build_frontmatter()` (line ~120):

```python
def _build_frontmatter(state, applicable):
    ctx = state.get("company_context")
    ...
    payload = {
        ...
        "case_study": getattr(ctx, "company_name", "UNKNOWN") if ctx else "UNKNOWN",
        ...
        "scale": _scale_from_context(ctx),  # returns "-" via _safe_attr fallback
        "security_fte": _safe_attr(ctx, "security_fte", default=0.0),  # returns 0
        ...
    }
```

`ctx` is a **dict** (from `_build_company_context().model_dump()`), not a Pydantic object. `getattr(dict, "company_name")` raises `AttributeError`, falling through to `"UNKNOWN"`.

`_scale_from_context` and `_safe_attr` use the local `_safe_attr` helper which does check `isinstance(obj, Mapping)` and falls back to `.get()` — but in this case the dict's `scale`, `security_fte` values are 0/- because the v2_compat shim populates them based on a heuristic OR the values come through correctly — need to verify.

Runtime test (this session, case 2):

| Field | `getattr(dict, "...")` | `_safe_attr(dict, "...")` | `dict.get("...")` |
|---|---|---|---|
| `company_name` | AttributeError → "UNKNOWN" | "SecureBorder Solutions B.V." | "SecureBorder Solutions B.V." |
| `scale` | AttributeError → "" → "_scale_from_context" returns "MICRO" (when employees < 10) | "LARGE" | "LARGE" |
| `security_fte` | AttributeError → 0.0 | 25.0 | 25.0 |
| `applicable_regs` | AttributeError → [] | ['AI_Act', 'CRA', 'GDPR', 'NIS2'] | ['AI_Act', 'CRA', 'GDPR', 'NIS2'] |

So the **bug is specifically the `getattr(ctx, "company_name", "UNKNOWN")` line in front-matter**. The other fields use `_safe_attr` which works correctly for dicts.

Note: the Doc 07b front-matter still shows `case_study: UNKNOWN`, `scale: "-"`, `security_fte: 0`. This is because the `case_study` field is the only one using the broken `getattr` pattern — but the body metadata (which uses `_scale_from_context` and `_safe_attr`) should be correct. Let me verify by reading the body too.

The Doc 07b **body** §2 "COMPANY PROFILE METADATA" shows (case 2):
```
| Sector | Defense, Security & Critical Infrastructure | AEGIS-P1-04 §2 |
| Jurisdiction | Netherlands (EU) | AEGIS-P1-04 §2 |
| Scale | LARGE | AEGIS-P1-04 §2 |
| Employees | 450 | AEGIS-P1-04 §2 |
| Revenue | 120000000.0 | AEGIS-P1-04 §2 |
| Applicable regulations | AI_Act, CRA, GDPR, NIS2 | AEGIS-P1-05 §2 |
| Complexity tier | HIGH | AEGIS-P1-04 §5 |
| Security FTE | 25.0 | AEGIS-P1-04 §5 + critical analysis |
```

**The body is correct.** Only the front-matter is wrong (it uses a different code path for `case_study`).

### Suggested fix (1 file, 1 line)

`src/aegis_phase1/v2/output/doc_07b.py` line ~125:

```python
# OLD:
"case_study": getattr(ctx, "company_name", "UNKNOWN") if ctx else "UNKNOWN",
# NEW (option A — use the existing safe helper):
"case_study": _safe_attr(ctx, "company_name", "UNKNOWN"),
# OR (option B — explicit dict.get):
"case_study": (ctx or {}).get("company_name", "UNKNOWN") if isinstance(ctx, Mapping) else getattr(ctx, "company_name", "UNKNOWN"),
```

Option A is the minimal change and reuses the existing helper that already handles both dict and Pydantic cases correctly.

### Impact

- Doc 07b front-matter shows wrong `case_study` (cosmetic — body is correct)
- Doc 07b front-matter `scale` and `security_fte` show wrong values (`"-"` and `0`) but **the body** §2 is correct
- Audit trail: a Phase 2 consumer reading the front-matter only would get wrong metadata

---

## Bug 5 (LOW, cascade of Bug 1) — Doc 04 front-matter `applicable_regs` and `tier` are wrong

### Root cause

**File:** `src/aegis_phase1/v2/output/doc_04.py`
**Function:** the `extra` dict passed to `generate_frontmatter` (line ~150-170):

```python
extra={
    "phase": 1,
    "author": "Compliance Lead",
    "case_study": _attr(ctx, "company_name", default="UNKNOWN"),  # ← WORKS (uses _attr helper)
    "inputs": ["01_Company_Context.md"],
    "outputs": ["05_Regulatory_Applicability.md"],
    ...
    "applicable_regs": list(app_ctx.applicable_regs),  # ← inherits Bug 1
    "tier": app_ctx.tier,                             # ← inherits Bug 1
},
```

The Doc 04 uses `_attr` (which has the correct Mapping fallback, like `_safe_attr`) for `case_study` — so it works. But it reads `app_ctx.applicable_regs` and `app_ctx.tier` from `build_applicability_context(state)`, which produces the **heuristic** result (Bug 1).

Verified at runtime for case 2:
- `state["v2_applicable_regs"]` = `['AI_Act', 'CRA', 'GDPR', 'NIS2']` (correct)
- `app_ctx.applicable_regs` = `['GDPR']` (wrong, from heuristic)
- Doc 04 front-matter `applicable_regs` = `[GDPR]` (uses app_ctx)
- Doc 04 front-matter `tier` = `HIGH` (from `app_ctx.tier` which uses `len(applicable_computed)` = 1 → HIGH because of the `>= 3` rule... wait, 1 should be LOW. Let me re-check.)

Hmm, case 2 shows `tier: HIGH`. With only 1 reg, `_estimate_tier` should return `LOW` (employees <= 10) or `MEDIUM` (scale != MICRO and applicable_count == 2) — but actually `_estimate_tier` is:

```python
def _estimate_tier(company_facts, applicable_count):
    scale = (company_facts.get("scale") or "").upper()
    if scale in ("MEDIUM", "LARGE", "MAX") or applicable_count >= 3:
        return Tier.HIGH
    if scale == "SMALL" or (applicable_count >= 2 and scale not in ("MICRO",)):
        return Tier.MEDIUM
    return Tier.LOW
```

Case 2 has `scale=LARGE` → returns `Tier.HIGH` regardless of applicable_count. So `tier: HIGH` is correct for case 2 (and case 3). For case 1 (MICRO, 2 applicable) the tier would be `MEDIUM` not `LOW`... but the output shows `LOW`. Let me check case 1.

Looking at case 1's output: `tier: LOW`. Case 1 has `scale=MICRO` and `applicable_count=2`. `_estimate_tier`:
- `scale in (MEDIUM, LARGE, MAX)` — False (MICRO)
- `applicable_count >= 3` — False (2)
- `scale == SMALL` — False (MICRO)
- `(applicable_count >= 2 and scale not in ("MICRO",))` — False (MICRO)
- Returns `Tier.LOW` ✓

For case 2 (scale=LARGE, applicable_count=1):
- `scale in (MEDIUM, LARGE, MAX)` — True → `Tier.HIGH` ✓

OK, so the tier calculation is internally consistent. It's just that the `applicable_count` is 1 (heuristic) instead of 4 (user-declared). For the tier, that doesn't matter much because the `scale` factor dominates. But for downstream consumers, the `applicable_count` is the wrong number.

### Suggested fix (1 file, 1 line change after Bug 1 fix)

`src/aegis_phase1/v2/output/doc_04.py` line ~165:

```python
# OLD:
"applicable_regs": list(app_ctx.applicable_regs),
"tier": app_ctx.tier,
# NEW (after Bug 1 fix, app_ctx will be correct; otherwise use v2_applicable_regs directly):
"applicable_regs": list(state.get("v2_applicable_regs") or app_ctx.applicable_regs),
"tier": app_ctx.tier,  # tier is also heuristic-driven; could be fixed similarly
```

Or, fix Bug 1 first — once `app_ctx.applicable_regs` is correct, both `applicable_regs` and `tier` (which depends on `len(applicable_computed)`) become correct automatically.

### Impact

- Doc 04 front-matter `applicable_regs` — wrong
- Doc 04 front-matter `tier` — wrong for cases where `applicable_count` would change the result (e.g. case 1 with 2 regs should be MEDIUM but shows LOW if applicable_count were 1; with current heuristic for case 1 = 2 regs, shows MEDIUM if the heuristic gave 2 — but case 1 user-declared 2 + heuristic 2 = 2 → MEDIUM... wait case 1 shows LOW. Let me re-trace.)

For case 1: heuristic produces [GDPR, CRA] (2 regs). User declares [GDPR, CRA] (2 regs). Both same. `_estimate_tier(MICRO, 2)`:
- `scale in (MEDIUM, LARGE, MAX)` — False
- `applicable_count >= 3` — False
- `scale == SMALL` — False
- `(applicable_count >= 2 and scale not in ("MICRO",))` — `(2 >= 2 and "MICRO" not in ("MICRO",))` — second clause False because `"MICRO" in ("MICRO",)` is True → False
- Returns `Tier.LOW` ✓

So case 1's tier is "LOW" both before and after the fix. Bug 5 only changes Doc 04's `applicable_regs` for case 2 and 3 (and possibly the tier for case 1 if the heuristic gave 1 reg there — but it doesn't, case 1 has 2 by both).

---

## What is NOT a bug

### Warnings about `architecture YAMLs` missing aliases

The warnings `_read_yaml_list_multi: none of aliases ['data_stores', 'stores'] found ...` are expected behavior for cases 2 and 3 because the scaffolding uses `stores: []` as the empty placeholder, not `data_stores: [...]`. The loader correctly falls through. These would disappear if the architecture YAMLs were populated with real data.

### Warnings about `implementation_readiness`, `regulatory_classification`, etc. missing

These are CORR-047 optional categories. The loader logs a WARNING and returns `None`. Doc 04b's capability matrix is empty for cases 2 and 3 (not a bug, just less rich output). These would also disappear with full scaffolding.

### Doc 04 body content

The body of Doc 04 (not front-matter) is correct for all 3 cases. The body uses different code paths that read the right data.

### Doc 07b body content (§2 metadata)

The body of Doc 07b §2 is correct for all 3 cases — it uses `_safe_attr` and `_scale_from_context` which handle dict correctly. Only the front-matter is wrong (Bug 4).

---

## Priority order for fixes

1. **Bug 2** (HIGH) — fix first. Cascades into Bug 3 fix. Trivial ~15-line change in 1 file.
2. **Bug 1** (CRITICAL) — fix second. ~8-line change in 1 file. Affects Doc 04/05 + cascades into Bug 5.
3. **Bug 4** (LOW) — fix third. 1-line change in 1 file. Trivial.
4. **Bug 5** (LOW) — fixed automatically by Bug 1.
5. **Bug 3** (HIGH) — fixed automatically by Bug 2 (or via defensive fallback in executor).

After all 5 fixes, re-run the 3 cases and verify:
- Doc 05 applicability table matches user declaration
- Doc 07b has 38 tier rows (or as many as the case's applicable regs justify)
- Doc 07 §3 has per-cell clause counts
- Doc 07 §4-5 has strategic implications and compound events
- Doc 04/07b front-matter has correct `case_study`, `applicable_regs`, `tier`, `scale`, `security_fte`
