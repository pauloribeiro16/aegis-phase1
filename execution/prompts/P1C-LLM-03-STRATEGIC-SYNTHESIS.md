---
prompt_spec_id: P1C-LLM-03-STRATEGIC-SYNTHESIS
prompt_spec_version: 1.0.0
legacy_aliases:
  - LLM-G
  - "Phase 1C strategic implications synthesis"
phase: 1
sub_phase: 1C
semantic_task: cross_lane_strategic_synthesis
invocation_pattern: global_reduce
stage: reduce
reduce_order: 1            # runs BEFORE P1C-LLM-02-COMPOUND-EVENT
author: AEGIS Methodology maintainer
status: ACTIVE
created: 2026-07-13
updated: 2026-07-13
related_documents:
  - ./base_system_prompt.md
  - ./output_schemas.yaml#P1C-LLM-03
  - ./examples/strategic_synthesis_3_lane.yaml
  - ../../../PHASE1_STRATEGY.md
  - ../../../REFERENCE/proportionality_model.md
  - ../../diagrams/fluxdiagram/phase1/phase1c_consolidation.md
  - ../../diagrams/fluxdiagram/phase1/phase1c_synthesis_reference.md
  - ../../diagrams/fluxdiagram/phase1/phase1c_proportionality_synthesis.md
---

# P1C-LLM-03-STRATEGIC-SYNTHESIS

> **Global strategic synthesis (Reduce stage, runs 1st).**
> 1 call per case, after `P1C-LLM-01-OVERLAP-CLASSIFICATION` (all 10 lanes). **Consumes Doc 07b** (deterministic) as a hard constraint.

---

## Why runs FIRST (before LLM-02)?

Strategic synthesis is the **highest-level reasoning** in Phase 1. It needs:
- All 38 sub-domain activations (from 10 lanes)
- All 38 Track B tier assignments (from Doc 07b)
- Cross-lane pattern detection (which sub-domains share architecture, share ownership, share evidence patterns)

Once the strategic picture is clear, `P1C-LLM-02-COMPOUND-EVENT` can use it to contextualize event identification (e.g., "given that this company uses a managed KMS across D-01.1 + D-01.3, an encryption breach event is more likely cross-domain").

## When to invoke

After:
1. All 10 per-domain lanes (`P1C-LLM-01-OVERLAP-CLASSIFICATION`) completed
2. Track B (Doc 07b) ready

**NOT required:** P1B-LLM-02 outputs (rationale) — per-regulation rationale is too narrow for strategic synthesis.

## Inputs

```yaml
case_id: "Case_XX"
lane_id: "global"
applicable_regs: [...]
aggregated_activations:                # 38 rows from P1C-LLM-01 (all 10 lanes)
  - lane_id: D-01
    sub_domain_activations: [...]
  # ... 10 entries
doc07b_profile:                          # 38 rows from Track B (deterministic)
  - sub_domain_id: D-01.1
    tier: LIGHTWEIGHT
    satisfaction_pattern: BUY_MANAGED
    evidence_depth: managed_service_config_plus_annual_review
    verification_method: [DEMONSTRATE, INSPECT]
    ownership: SUPPLIER
    example_controls: ["AWS KMS SSE-KMS"]
p1c_llm_01_outputs_by_domain:            # 10 entries
  - domain_id: D-01
    sub_domain_activations: [...]
  # ...
business_goals:                          # from Doc 04 §4 (if structured)
  - id: BG-01
    description: "Achieve EU customer trust"
    priority: HIGH
company_facts:                           # from Doc 04
  scale: MICRO  # or SMALL, MEDIUM, LARGE, MAX
  architecture_ref: "DOC04:ARCH-XX"
  team_size: 8
```

## Task (verbatim, use as user message)

```
<task>
Produce CROSS-LANE strategic implications — patterns that emerge ONLY when
viewing multiple sub-domains together. Do NOT produce per-lane implications
(those are in P1B-LLM-02 output).

ANALYZE:
1. Pattern detection across sub-domains:
   - Shared architecture: which sub-domains use the same primitive
     (e.g., D-01.1 + D-01.3 share KMS; D-04.x + D-09.4 share incident workflow)
   - Shared ownership: which sub-domains have same owner
   - Shared evidence: which sub-domains use same evidence pattern
   - Shared supplier: which sub-domains inherit from same third party
2. Resource aggregation:
   - Sum Doc 07b ownership loads (e.g., "Company owns 12 sub-domains at LIGHTWEIGHT or above → 0.85 FTE × 30% = 0.255 FTE dedicated")
   - Identify resource bottlenecks
3. Cross-regulation consolidation opportunities:
   - Single implementation satisfying multiple sub-domains
   - Single evidence pack satisfying multiple regulations
   - Unified assessment satisfying multiple tier requirements

EMIT 1-8 strategic implications. Each MUST:
- span ≥2 sub_domains (cross-lane requirement)
- reference ≥2 Doc 07b rows (constraint enforcement)
- have architectural_impact, business_goal_alignment, risk_level
- have ≥2 layer0_refs (Regulatory Baseline source citations)
- have ≥1 doc07b_refs (Track B citation)
- explicitly state assumptions

CRITICAL CONSTRAINTS:
- Do NOT propose controls (Track B already provides example_controls)
- Do NOT estimate per-lane effort (Track B already provides evidence_depth)
- Do NOT change tier assignments (Track B is authoritative)
- Do NOT invent statistics (e.g., "40% effort reduction" without basis)
- Do NOT make final human decisions (budget, headcount, risk acceptance)

Output 1-8 implications max. If you have nothing material, output 1-2
implications acknowledging the cross-lane picture is mostly settled.
</task>
```

## Output Schema

Reference: [`./output_schemas.yaml#P1C-LLM-03`](output_schemas.yaml#P1C-LLM-03)

Top-level fields:
- `prompt_spec_id`: "P1C-LLM-03-STRATEGIC-SYNTHESIS"
- `invocation_pattern`: "global_reduce"
- `lane_id`: "global"
- `implications[]`: 1-8 cross-lane implications
- `status`, `confidence`

Each implication:
- `id`: unique
- `description`: 50+ chars, cross-lane narrative
- `affected_sub_domains[]`: ≥2 entries
- `regulations[]`: ≥2 entries
- `architectural_impact`: 1-2 sentences
- `business_goal_alignment`: 1-2 sentences
- `resource_implications[]`: 1+ items
- `risk_level`: LOW | MEDIUM | HIGH
- `assumptions[]`: explicit assumptions
- `confidence`: HIGH | MEDIUM | LOW
- `layer0_refs[]`: ≥1 entry
- `doc07b_refs[]`: ≥1 entry

## Quality Criteria

- [ ] Every implication has `affected_sub_domains[]` ≥2 (cross-lane)
- [ ] Every implication has `regulations[]` ≥2 (cross-regulation)
- [ ] Every implication has `doc07b_refs[]` ≥1 (Track B enforcement)
- [ ] No controls proposed (Track B has `example_controls`)
- [ ] No per-lane effort estimates (Track B has `evidence_depth`)
- [ ] No tier changes (Track B is authoritative)
- [ ] No invented statistics
- [ ] No budget/headcount decisions (human territory)
- [ ] No risk acceptance decisions (human territory)
- [ ] 1-8 implications (not 0, not >8)

## Model Configuration

```yaml
model: MiniMax-M2.7
temperature: 0.0
max_tokens: 4096
```

## Few-shot Example

See [`./examples/strategic_synthesis_3_lane.yaml`](examples/strategic_synthesis_3_lane.yaml)

## Post-generation Validation

1. JSON Schema validation
2. Cross-lane check: every implication spans ≥2 sub-domains
3. Track B enforcement check: every implication has ≥1 doc07b_refs
4. No-controls check: schema rejects `controls[]` or `effort_estimate[]` fields
5. Citation check: every layer0_refs and doc07b_refs file exists
6. Assumption presence: confidence LOW requires ≥2 assumptions

## Cross-references

- **Diagram:** [`../../diagrams/fluxdiagram/phase1/phase1c_consolidation.md`](../../diagrams/fluxdiagram/phase1/phase1c_consolidation.md)
- **Reference:** [`../../diagrams/fluxdiagram/phase1/phase1c_synthesis_reference.md`](../../diagrams/fluxdiagram/phase1/phase1c_synthesis_reference.md) §4
- **Track B spec:** [`../../../REFERENCE/proportionality_model.md`](../../../REFERENCE/proportionality_model.md)
- **Track B diagram:** [`../../diagrams/fluxdiagram/phase1/phase1c_proportionality_synthesis.md`](../../diagrams/fluxdiagram/phase1/phase1c_proportionality_synthesis.md)
- **Base system prompt:** [`./base_system_prompt.md`](base_system_prompt.md)
- **Schema:** [`./output_schemas.yaml`](output_schemas.yaml#P1C-LLM-03)

---

## Change log

- v1.0.0 (2026-07-13): Initial canonical release. Replaces legacy LLM-G with strict cross-lane scope, Doc 07b consumption enforcement, **NO controls/effort/tier changes** (Track B authoritative). Runs BEFORE LLM-02 in Reduce stage.