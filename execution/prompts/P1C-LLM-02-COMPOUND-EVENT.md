---
prompt_spec_id: P1C-LLM-02-COMPOUND-EVENT
prompt_spec_version: 1.0.0
legacy_aliases:
  - LLM-F
  - "Phase 1C compound event identification + resolution design"
phase: 1
sub_phase: 1C
semantic_task: cross_domain_compound_event_identification
invocation_pattern: global_reduce
stage: reduce
reduce_order: 2            # runs AFTER P1C-LLM-03-STRATEGIC-SYNTHESIS
author: AEGIS Methodology maintainer
status: ACTIVE
created: 2026-07-13
updated: 2026-07-13
related_documents:
  - ./base_system_prompt.md
  - ./output_schemas.yaml#P1C-LLM-02
  - ./catalogs/event_templates.yaml
  - ./examples/compound_event_supply_chain.yaml
  - ../../../PHASE1_STRATEGY.md
  - ../../../REGULATORY_BASELINE.md
  - ../../diagrams/fluxdiagram/phase1/phase1c_consolidation.md
  - ../../diagrams/fluxdiagram/phase1/phase1c_synthesis_reference.md
---

# P1C-LLM-02-COMPOUND-EVENT

> **Global compound event identification (Reduce stage, runs 2nd).**
> 1 call per case, after `P1C-LLM-03-STRATEGIC-SYNTHESIS`. **NO resolution design** — that moves to Phase 2B.

---

## Why runs SECOND (after LLM-03)?

After `P1C-LLM-03-STRATEGIC-SYNTHESIS` has produced the cross-lane strategic implications, we have a clearer picture of:
- Which sub-domains share architectural primitives (e.g., D-01.1 + D-01.3 share KMS)
- Which strategic priorities matter most
- Which event candidates have real business impact vs theoretical

This contextualizes compound event identification. LLM-02 reads LLM-03's strategic output as additional input.

## When to invoke

After:
1. All 10 per-domain lanes (`P1C-LLM-01-OVERLAP-CLASSIFICATION`) completed
2. Track B (Doc 07b) ready
3. `P1C-LLM-03-STRATEGIC-SYNTHESIS` completed (its output feeds this)

## Inputs

```yaml
case_id: "Case_XX"
lane_id: "global"
applicable_regs: [GDPR, CRA, NIS2, DORA, AI_Act]
aggregated_activations:                # from P1C-LLM-01 (all 10 lanes)
  - lane_id: D-01
    sub_domain_activations: [...]
  - lane_id: D-02
    sub_domain_activations: [...]
  # ... 10 entries, one per domain
doc07b_profile:                          # from Track B
  - sub_domain_id: D-01.1
    tier: LIGHTWEIGHT
    satisfaction_pattern: BUY_MANAGED
    evidence_depth: managed_service_config_plus_annual_review
  # ... 38 entries
p1c_llm_03_output:                       # from P1C-LLM-03-STRATEGIC-SYNTHESIS
  implications: [...]
company_facts:                           # from Doc 04
  products: [...]
  data_categories: [...]
layer0_event_templates: "catalogs/event_templates.yaml"
layer0_subdomain_refs: [...]             # 38 sub-domain files
```

## Task (verbatim, use as user message)

```
<task>
Identify cross-domain compound events — factual events that simultaneously
trigger incompatible obligations from multiple regulations.

DEFINITION (per phase1c_synthesis_reference.md §2.1):
A compound event requires:
1. ONE factual event
2. At least TWO applicable regulation triggers evaluate TRUE
3. Resulting obligations are incompatible or require coordinated routing

For each candidate event, evaluate ALL three criteria.

SCOPE: Cross-domain only. Within-lane events are handled in Doc 05 (per-reg).
If an event fits within a single regulation's obligations, it is NOT a compound
event and should NOT appear here.

USE REGULATORY BASELINE event_templates.yaml AS A CATALOG — these are pre-computed
event templates with trigger predicates. Evaluate each template's
trigger_predicates against:
  - aggregated_activations (which sub-domains are active)
  - doc07b_profile (which satisfaction patterns are used)
  - company_facts (what the company actually does)

Emit TWO lists:

1. positive_events (CONFIRMED compound events):
   - event_id: "EVT-NN"
   - description: 1-2 sentences
   - sub_domains: [D-XX.Y, ...] minItems 2
   - regulations_triggered: [REG, ...] minItems 2
   - tension_type: TEMPORAL_CONFLICT | REQUIREMENT_CONFLICT | FREQUENCY_MISMATCH | TRIGGER_MISMATCH | INTENSITY_GAP
   - severity: LOW | MEDIUM | HIGH | CRITICAL
   - layer0_refs: which Regulatory Baseline files (event_templates, SubDomains) support this

2. negative_events (apparent but NOT actually compound):
   - scenario: what looked like a compound event
   - regulations_checked: [REG, REG]
   - why_not_compound: 1-2 sentences explaining why criteria fail

CRITICAL RULES:
- You are IDENTIFYING events, not designing responses. NO resolution_approach
  in output schema — resolution goes to Phase 2B.
- Use Regulatory Baseline event templates as the source of plausible events; do NOT invent
  event archetypes from scratch.
- If no compound events apply to this company, return empty positive_events[].

If you cannot determine due to missing facts, return INSUFFICIENT_EVIDENCE.
</task>
```

## Output Schema

Reference: [`./output_schemas.yaml#P1C-LLM-02`](output_schemas.yaml#P1C-LLM-02)

Top-level fields:
- `prompt_spec_id`: "P1C-LLM-02-COMPOUND-EVENT"
- `invocation_pattern`: "global_reduce"
- `lane_id`: "global"
- `positive_events[]`: confirmed compound events (cross-domain)
- `negative_events[]`: apparent-but-not compounds (calibration)
- `status`, `confidence`

## Quality Criteria

- [ ] Every `positive_events[].sub_domains` has ≥2 entries (cross-domain)
- [ ] Every `positive_events[].regulations_triggered` has ≥2 entries
- [ ] Every `tension_type` is from the allowed enum
- [ ] Every `layer0_refs[]` resolves to existing file
- [ ] No `resolution_approach` field (explicitly excluded — Phase 2B territory)
- [ ] Events use Regulatory Baseline event templates as source (no invented archetypes)
- [ ] `negative_events[]` populated when relevant (calibration)

## Model Configuration

```yaml
model: MiniMax-M2.7
temperature: 0.0
max_tokens: 4096
```

## Few-shot Example

See [`./examples/compound_event_supply_chain.yaml`](examples/compound_event_supply_chain.yaml)

## Post-generation Validation

1. JSON Schema validation
2. Cross-domain check: every positive event has sub_domains from ≥2 different domains (D-XX.Y where XX differs)
3. No-resolution check: schema rejects `resolution_approach` field if present
4. Catalog reference check: every `tension_type` ∈ event_templates.yaml catalog
5. Conflict detection: if LLM-03 strategic output mentions an event that LLM-02 missed, flag INDETERMINATE
6. Citation check: every positive event cites a Regulatory Baseline event template

## Cross-references

- **Diagram:** [`../../diagrams/fluxdiagram/phase1/phase1c_consolidation.md`](../../diagrams/fluxdiagram/phase1/phase1c_consolidation.md)
- **Reference:** [`../../diagrams/fluxdiagram/phase1/phase1c_synthesis_reference.md`](../../diagrams/fluxdiagram/phase1/phase1c_synthesis_reference.md) §2
- **Catalog:** [`./catalogs/event_templates.yaml`](catalogs/event_templates.yaml)
- **Base system prompt:** [`./base_system_prompt.md`](base_system_prompt.md)
- **Schema:** [`./output_schemas.yaml`](output_schemas.yaml#P1C-LLM-02)

---

## Change log

- v1.0.0 (2026-07-13): Initial canonical release. Replaces legacy LLM-F with strict cross-domain scope, **NO resolution design** (moved to Phase 2B), runs AFTER LLM-03 in Reduce stage.