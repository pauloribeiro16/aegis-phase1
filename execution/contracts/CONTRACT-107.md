---
contract: CONTRACT-107
title: CORR-107 — Doc 04b maturity variance = 0 (scorer reads DOC04, not static tier)
status: ACTIVE
created: 2026-09-02
author: opencode (MiniMax-M3)
branch: feature/aegis-p1-corr-107-maturity-dynamic
scope: 1 source file + 1 yaml + 1 test
depends_on: CORR-073 (tier-aware maturity), CORR-105 (eval framework)
---

# CORR-107 — Doc 04b maturity variance = 0

## The bug (re-confirmed 2026-09-02)

Doc 04b's maturity-by-domain matrix prints the same value across all 10
domains in **every** scout:

```
| D-01 | 1 | 1 | Data Protection          (variance 0)
| D-02 | 1 | 1 | Vulnerability Management
| D-03 | 1 | 1 | Access Control
...
```

M3 gold, qwen3.5, qwen3.8, ornith:9b — all paint the same flat `1`s on
case1-tinytask. The judge flagged it as "scorer over-collapse" in every
digest; the suspected cause was wrong.

### Root cause

`doc_04b.py:_section_maturity_evaluation` reads maturity from
`data/control_maturity/{tier}.yaml` (a **compile-time constant per tier**):

```yaml
# MICRO.yaml — case1-tinytask is MICRO (8 employees)
current_by_domain:
  D-01: 1   D-02: 1   D-03: 1   D-04: 1   D-05: 1
  D-06: 1   D-07: 1   D-08: 1   D-09: 1   D-10: 1
```

The scorer has a runtime override path (`state["security_posture_overrides"]`,
line 1241) but **nothing in the pipeline populates it from DOC04 facts**.
The case1 input file `input/company/implementation_readiness.yaml`
already carries `backup: YES, information_security_policy: PARTIAL, ...`
— the data is there, the bridge is missing.

This explains the "judge impressions" in the digests: the model quality
was never the issue; the scorer has been static since CORR-073.

## Fix

Replace the read in `_section_maturity_evaluation` with a function that
maps DOC04 readiness facts → maturity overrides. Tier YAML stays as the
floor (don't go below tier defaults).

### Mapping (heuristic v1, refined via case data)

| DOC04 readiness field | DOC04 value → maturity override |
|----------------------|----------------------------------|
| `backup: "YES"` | D-04 (Incident Response) +1 |
| `backup: "PARTIAL"` | D-04 (Incident Response) +0.5 |
| `access_control: "PARTIAL"` | D-03 (Access Control) +0.5 |
| `access_control: "YES"` | D-03 (Access Control) +1 |
| `information_security_policy: "PARTIAL"` | D-09 (Governance) +0.5 |
| `information_security_policy: "YES"` | D-09 (Governance) +1 |
| `risk_assessment: "YES"` | D-09 (Governance) +0.5 |
| `incident_response: "PARTIAL"` | D-04 +0.5 |
| `incident_response: "YES"` | D-04 +1 |
| `business_continuity: "YES"` | D-04 +0.5 |
| `vulnerability_management: "PARTIAL"` | D-02 +0.5 |
| `vulnerability_management: "YES"` | D-02 +1 |
| `audit_logging: "PARTIAL"` | D-10 (Monitoring) +0.5 |
| `audit_logging: "YES"` | D-10 +1 |
| `security_awareness: "PARTIAL"` | D-08 (Human Factors) +0.5 |
| `security_awareness: "YES"` | D-08 +1 |
| `dpo: "YES"` or `ciso: "YES"` | D-09 +0.5 (governance anchor) |
| `third_party_risk: "PARTIAL"` | D-06 (Supply Chain) +0.5 |
| `third_party_risk: "YES"` | D-06 +1 |

For case1-tinytask the heuristic should yield:
- D-02 vm=PARTIAL → current 1.5 (was 1)
- D-03 ac=PARTIAL → current 1.5 (was 1)
- D-04 ir=PARTIAL+backup=YES → current 2.0 (was 1)
- D-06 tpr=NO → current 1 (unchanged)
- D-08 aw=NO → current 1 (unchanged)
- D-09 isp=PARTIAL, ra=NO → current 1.5 (was 1)
- D-10 al=PARTIAL → current 1.5 (was 1)

Variance goes from 0 → non-zero. **Re-grade the L4 criterion in all 4
existing digests** — note that the model quality scores were unaffected;
this only changes the L4 downstream metric.

## Scope

| File | Action |
|---|---|
| `src/aegis_phase1/v2/output/doc_04b.py` | Add `_dynamic_maturity_from_readiness(state, tier)` that returns overrides dict; merge with `_overrides` in `_section_maturity_evaluation` and the maturity-distribution section |
| `tests/unit/v2/output/test_doc_04b_maturity_dynamic.py` | New stdlib-only tests: 3 scenarios (all-NO → flat 1, all-YES → high, mixed → variance > 0) |
| `tests/unit/v2/test_doc_04b_scorer_regression.py` | Snapshot the current behaviour as a regression baseline so the fix doesn't accidentally break the tier-floor invariant |

## Out of scope

- Methodology-main is untouched (stable pin)
- Changing the heuristic per case (this is a generic rule; per-case
  overrides can still come via `state["security_posture_overrides"]`)
- Re-running the 4 old scouts (their LLM outputs are unaffected by the
  scorer fix; only the L4 cell in their digests would change)

## Acceptance

1. `pytest tests/unit/v2/output/test_doc_04b_maturity_dynamic.py` → 3+ tests PASS.
2. `pytest tests/unit/v2/test_doc_04b_scorer_regression.py` → regression green.
3. After rerunning **just the deterministic stages** (no LLM, ~3 s)
   for case1-tinytask, the Doc 04b maturity table shows variance > 0
   across the 10 domains.
4. The 4 existing digests' L4 notes are **not edited** — they're a
   historical record of what the user actually saw.

## Backwards compatibility

The tier YAML stays as the floor (`max(1, ...)` in the merge). A MICRO
company that has nothing in DOC04 still shows 1/1/1 — no regression for
the empty case. A MICRO company with strong readiness shows maturity
**above the tier floor**, which is the desired behaviour.