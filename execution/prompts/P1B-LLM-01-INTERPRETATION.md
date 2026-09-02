---
prompt_spec_id: P1B-LLM-01-INTERPRETATION
prompt_spec_version: 1.0.0
legacy_aliases:
  - LLM-A
  - "Phase 1B Interpretation + Derogation"
phase: 1
sub_phase: 1B
semantic_task: per_regulation_interpretation_and_derogation
invocation_pattern: per_regulation
author: AEGIS Methodology maintainer
status: ACTIVE
created: 2026-07-13
updated: 2026-07-13
related_documents:
  - ./base_system_prompt.md
  - ./output_schemas.yaml#P1B-LLM-01
  - ./catalogs/tipo2_interpretations.yaml
  - ./catalogs/tipo3_derogations.yaml
  - ./examples/interpretation_positive.yaml
  - ./examples/interpretation_negative.yaml
  - ../../../PHASE1_STRATEGY.md
  - ../../../REGULATORY_BASELINE.md
  - ../../../PREPROCESSING/SubDomains/index.md
  - ../../diagrams/fluxdiagram/phase1/phase1b_regulatory_mapping.md
  - ../../diagrams/fluxdiagram/phase1/phase1b_nuances_and_reasoning.md
---

# P1B-LLM-01-INTERPRETATION

> **Per-regulation interpretation + derogation catalog activation.**
> Invocation: 1 call per `applicable_reg`. Replaces legacy LLM-A.

---

## When to invoke

After Filter 1 has determined `applicable_regs` for a given company. For each `reg` in `applicable_regs`, invoke this LLM once. Output contributes to Doc 05 §3 (nuances per regulation).

## Inputs

```yaml
case_id: "Case_XX"           # required
lane_id: "REG"               # regulation code (GDPR, CRA, NIS2, DORA, AI_Act)
applicable_regs: [REG]       # single-element array (this call is per-regulation)
classification:                # from Phase 1B Step 3
  role: "Controller"           # Controller | Processor | Both | Manufacturer | etc.
  tier: "LOW"                  # LOW | MEDIUM | HIGH (company scale × regulatory criticality)
  classification_basis: "Doc 04 §5"
company_facts:                 # from Doc 04 (04a-04d)
  architecture_ref: "DOC04:ARCH-07"
  data_categories: ["personal_data", "non_personal_data"]
  products: ["SaaS application with personal data processing"]
  role_obligations: ["controller for admin data, processor for customer data"]
layer0_catalog:                # loaded deterministically
  tipo2: "./catalogs/tipo2_interpretations.yaml"
  tipo3: "./catalogs/tipo3_derogations.yaml"
layer0_subdomain_refs:         # sub-domains this regulation activates
  - "SubDomains/D-01.1.md"
  - "SubDomains/D-04.3.md"
```

## Task (verbatim, use as user message)

```
<task>
For the regulation {REG} and the company's classification:

1. Look up all Tipo 2 (interpretation) entries in
   tipo2_interpretations.yaml that have `applies_to: [{REG}]`.

2. For each entry, determine whether it applies to THIS company based on:
   - classification.role (e.g., Processor applicability for "Controller" classification is N/A)
   - tier (some interpretations are tier-gated)
   - company_facts.architecture_ref, data_categories, products, role_obligations

3. Look up all Tipo 3 (derogation) entries in tipo3_derogations.yaml
   that have `applies_to: [{REG}]`.

4. For each derogation, evaluate the `activation_predicates[]` against
   company_facts. Each predicate is a Python-like expression that must
   evaluate to True for the derogation to activate.

5. Emit TWO lists:
   - interpretations: [{entry_id, applicable, activation_rationale, layer0_refs, company_fact_refs}]
   - derogations: [{entry_id, activation_verdict (ACTIVATED|NOT_ACTIVATED|INDETERMINATE), activation_rationale, layer0_refs, company_fact_refs}]

If you cannot determine applicability due to missing Doc 04 facts, return
status=INSUFFICIENT_EVIDENCE with missing_fact explicitly named.
</task>
```

## Output Schema

Reference: [`./output_schemas.yaml#P1B-LLM-01`](output_schemas.yaml#P1B-LLM-01)

Top-level fields:
- `prompt_spec_id`: "P1B-LLM-01-INTERPRETATION"
- `invocation_pattern`: "per_regulation"
- `lane_id`: "{REG}"
- `interpretations[]`: activated Tipo 2 entries
- `derogations[]`: activated Tipo 3 entries
- `status`: OK | INSUFFICIENT_EVIDENCE | INDETERMINATE
- `confidence`: HIGH | MEDIUM | LOW

## Quality Criteria (PASS requires all)

- [ ] Every `entry_id` matches a row in `tipo2_interpretations.yaml` or `tipo3_derogations.yaml`
- [ ] Every `layer0_refs[]` entry is a real file path that exists
- [ ] No invented article numbers (cross-check against Regulatory Baseline)
- [ ] No reclassification of Regulatory Baseline relationships
- [ ] `applicable: true` only when entry's `applies_to` includes `REG` AND predicates match company facts
- [ ] Tier-gated interpretations respect tier constraints
- [ ] INSUFFICIENT_EVIDENCE returned when predicates require missing facts

## Model Configuration

```yaml
model: MiniMax-M2.7
temperature: 0.0
max_tokens: 2048
provider: MiniMaxChat
# If Anthropic direct:
# model: claude-sonnet-4-6
# temperature: 0.0
# enable_prompt_caching: true
# cache_ttl: 5m
```

## Few-shot Examples

See:
- [`./examples/interpretation_positive.yaml`](examples/interpretation_positive.yaml)
- [`./examples/interpretation_negative.yaml`](examples/interpretation_negative.yaml)

## Post-generation Validation (deterministic)

1. JSON Schema validation against `output_schemas.yaml#P1B-LLM-01`
2. Every `layer0_refs[]` file exists and is readable
3. Every `entry_id` is in the canonical catalog
4. For `entry_id` with `tier_required`, check `lane.tier >= tier_required`
5. No `legal_refs` outside Regulatory Baseline (return INSUFFICIENT_EVIDENCE if discovered)

Failure → retry with extended context (max 1 retry).

## Cross-references

- **Diagram:** [`../../diagrams/fluxdiagram/phase1/phase1b_regulatory_mapping.md`](../../diagrams/fluxdiagram/phase1/phase1b_regulatory_mapping.md)
- **Reference:** [`../../diagrams/fluxdiagram/phase1/phase1b_nuances_and_reasoning.md`](../../diagrams/fluxdiagram/phase1/phase1b_nuances_and_reasoning.md) §2.2 + §2.3
- **Base system prompt:** [`./base_system_prompt.md`](base_system_prompt.md)
- **Schema:** [`./output_schemas.yaml`](output_schemas.yaml#P1B-LLM-01)
- **Catalogs:** [`./catalogs/tipo2_interpretations.yaml`](catalogs/tipo2_interpretations.yaml), [`./catalogs/tipo3_derogations.yaml`](catalogs/tipo3_derogations.yaml)

---

## Change log

- v1.0.0 (2026-07-13): Initial canonical release. Replaces legacy LLM-A (Phase 1B interpretation + derogation).